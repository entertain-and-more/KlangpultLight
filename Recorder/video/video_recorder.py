"""video.video_recorder — VideoRecorder via FFmpeg-Subprocess-Pipe + mux_audio_video.

Kein GUI-Import. Kein PySide6.
ffmpeg muss im PATH oder als expliziter Pfad übergeben werden.
"""
from __future__ import annotations

import os
import queue
import shutil
import subprocess
import tempfile
import threading
from typing import Optional

import numpy as np


class VideoRecorder:
    """Schreibt Video-Frames via FFmpeg-Stdin-Pipe in eine MP4/H.264-Datei.

    Funktionsprinzip:
        open()       → startet FFmpeg-Subprocess (rawvideo bgr24 → mp4)
        write_frame() → schreibt Roh-Bytes in FFmpeg-stdin
        close()      → schließt stdin, wartet auf FFmpeg, gibt Dauer zurück

    FFmpeg-Stderr wird nach DEVNULL geleitet, um Deadlocks zu vermeiden.
    Stdout ebenfalls auf DEVNULL (kein interaktiver Output erwartet).
    """

    def __init__(
        self,
        width: int,
        height: int,
        fps: int = 30,
        ffmpeg_bin: str = "ffmpeg",
        writer_queue_size: int = 8,
        writer_join_timeout: float = 2.0,
    ) -> None:
        """
        Args:
            width: Frame-Breite in Pixeln.
            height: Frame-Höhe in Pixeln.
            fps: Ziel-Bildrate (Frames pro Sekunde).
            ffmpeg_bin: Pfad oder Name des FFmpeg-Binaries.
            writer_queue_size: Maximale Zahl wartender Frames. Bei Rückstau
                werden neue Frames gezählt verworfen, statt den Capture-Thread
                am FFmpeg-stdin zu blockieren.
            writer_join_timeout: Maximale Wartezeit beim kontrollierten
                Writer-Shutdown, bevor FFmpeg beendet wird.
        """
        self._width = width
        self._height = height
        self._fps = fps
        self._ffmpeg_bin = ffmpeg_bin
        if writer_queue_size < 1:
            raise ValueError("writer_queue_size muss mindestens 1 sein.")
        if writer_join_timeout <= 0:
            raise ValueError("writer_join_timeout muss größer als 0 sein.")
        self._writer_queue_size = writer_queue_size
        self._writer_join_timeout = writer_join_timeout

        self._prozess: Optional[subprocess.Popen] = None
        self._frames_geschrieben: int = 0
        self._frames_verworfen: int = 0
        self._out_pfad: Optional[str] = None
        self._dauer: float = 0.0  # letzte geschlossene Dauer — für idempotentes close()
        self._stderr_datei: Optional[tempfile.TemporaryFile] = None  # type: ignore[type-arg]
        self._writer_queue: Optional[queue.Queue[object]] = None
        self._writer_thread: Optional[threading.Thread] = None
        self._writer_error: Optional[BaseException] = None
        self._closing = False
        self._status_lock = threading.Lock()

    def open(self, out_path: str) -> None:
        """Startet FFmpeg und bereitet die Aufnahme vor.

        Args:
            out_path: Pfad zur Ausgabedatei (Verzeichnis wird angelegt).

        Raises:
            RuntimeError: Wenn ffmpeg nicht gefunden wurde oder nicht startete.
        """
        if self._prozess is not None:
            return  # idempotent

        # ffmpeg-Binary prüfen
        if shutil.which(self._ffmpeg_bin) is None:
            raise RuntimeError(
                f"ffmpeg-Binary '{self._ffmpeg_bin}' nicht gefunden. "
                "Bitte ffmpeg installieren und im PATH bereitstellen."
            )

        # Ausgabeverzeichnis anlegen
        verzeichnis = os.path.dirname(os.path.abspath(out_path))
        os.makedirs(verzeichnis, exist_ok=True)

        self._out_pfad = out_path
        self._frames_geschrieben = 0
        self._frames_verworfen = 0
        self._dauer = 0.0
        self._writer_error = None
        self._closing = False

        # FFmpeg-Kommando: rawvideo bgr24 von stdin → H.264 mp4
        cmd = [
            self._ffmpeg_bin,
            "-y",                               # Ausgabedatei überschreiben
            "-f", "rawvideo",
            "-pix_fmt", "bgr24",
            "-s", f"{self._width}x{self._height}",
            "-r", str(self._fps),
            "-i", "-",                           # von stdin lesen
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-pix_fmt", "yuv420p",              # breite Kompatibilität
            out_path,
        ]

        # stderr in Temp-Datei — verhindert Puffer-Deadlock bei langer Aufnahme,
        # ermöglicht aber Auslesen im Fehlerfall.
        self._stderr_datei = tempfile.TemporaryFile()

        try:
            self._prozess = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,       # kein stdout benötigt
                stderr=self._stderr_datei,       # Temp-Datei verhindert Deadlock + ermöglicht Auslesen
            )
        except FileNotFoundError as exc:
            self._stderr_datei.close()
            self._stderr_datei = None
            raise RuntimeError(
                f"ffmpeg-Binary '{self._ffmpeg_bin}' konnte nicht gestartet werden: {exc}"
            ) from exc

        self._writer_queue = queue.Queue(maxsize=self._writer_queue_size)
        self._writer_thread = threading.Thread(
            target=self._writer_loop,
            name="VideoRecorderWriter",
            daemon=True,
        )
        self._writer_thread.start()

    def write_frame(self, frame: np.ndarray) -> None:
        """Schreibt einen Frame in die FFmpeg-Stdin-Pipe.

        Args:
            frame: numpy-Array (H, W, 3), dtype=uint8, BGR.

        Raises:
            RuntimeError: Wenn open() nicht aufgerufen wurde.
            ValueError: Wenn die Frame-Größe nicht passt.
        """
        if self._prozess is None or self._prozess.stdin is None:
            raise RuntimeError("VideoRecorder ist nicht geöffnet — open() muss zuerst aufgerufen werden.")

        erw_shape = (self._height, self._width, 3)
        if frame.shape != erw_shape:
            raise ValueError(
                f"Frame-Shape {frame.shape} passt nicht zur erwarteten Shape {erw_shape}. "
                f"Erwartung: (H={self._height}, W={self._width}, 3) BGR uint8."
            )

        with self._status_lock:
            if self._closing:
                raise RuntimeError("VideoRecorder wird bereits geschlossen.")
            if self._writer_error is not None:
                raise RuntimeError("FFmpeg-Frame-Writer ist fehlgeschlagen.") from self._writer_error

        writer_queue = self._writer_queue
        if writer_queue is None:
            raise RuntimeError("VideoRecorder-Writer ist nicht initialisiert.")

        try:
            # Bytes statt des veränderlichen numpy-Arrays einreihen: Capture-Backends
            # dürfen ihren Frame-Puffer nach Rückkehr aus diesem Callback wiederverwenden.
            writer_queue.put_nowait(frame.astype(np.uint8, copy=False).tobytes())
        except queue.Full:
            with self._status_lock:
                self._frames_verworfen += 1

    @property
    def diagnostics(self) -> dict[str, int]:
        """Gibt die Capture-Writer-Diagnostik für Event-Logs und UI zurück."""
        with self._status_lock:
            queue_depth = self._writer_queue.qsize() if self._writer_queue is not None else 0
            return {
                "frames_written": self._frames_geschrieben,
                "frames_dropped": self._frames_verworfen,
                "queue_depth": queue_depth,
            }

    def close(self) -> float:
        """Schließt stdin und wartet auf FFmpeg.

        Idempotent: zweiter Aufruf gibt die bereits berechnete Dauer zurück.

        Returns:
            Aufnahmedauer in Sekunden (aus Framezahl / fps).

        Raises:
            RuntimeError: Wenn FFmpeg mit Fehler-Exit-Code beendet hat (enthält stderr).
        """
        if self._prozess is None:
            return self._dauer  # idempotent — letzte bekannte Dauer

        with self._status_lock:
            self._closing = True

        writer_thread = self._writer_thread
        if writer_thread is not None:
            self._request_writer_stop()
            writer_thread.join(timeout=self._writer_join_timeout)
            if writer_thread.is_alive():
                # Ein blockiertes stdin.write darf den Aufnahme-Stopp nicht dauerhaft
                # festhalten. Das Ende wird als klarer FFmpeg-Fehler gemeldet.
                self._prozess.terminate()
                writer_thread.join(timeout=self._writer_join_timeout)
            if writer_thread.is_alive():
                raise RuntimeError("FFmpeg-Frame-Writer konnte nicht kontrolliert beendet werden.")
        self._writer_thread = None
        self._writer_queue = None

        # stdin schließen — FFmpeg signalisiert: keine weiteren Frames
        if self._prozess.stdin is not None:
            try:
                self._prozess.stdin.close()
            except BrokenPipeError:
                pass  # FFmpeg hat ggf. bereits beendet

        # Auf FFmpeg warten und Exit-Code prüfen
        returncode = self._prozess.wait(timeout=self._writer_join_timeout)
        prozess = self._prozess
        self._prozess = None

        # stderr auslesen für Fehlermeldung
        stderr_text = ""
        if self._stderr_datei is not None:
            try:
                self._stderr_datei.seek(0)
                stderr_text = self._stderr_datei.read(4096).decode("utf-8", errors="replace")
            except Exception:
                pass
            self._stderr_datei.close()
            self._stderr_datei = None

        if returncode != 0:
            raise RuntimeError(
                f"FFmpeg beendete sich mit Exit-Code {returncode}. "
                f"Ausgabe: {stderr_text[-2000:]!r}"
            )

        if self._writer_error is not None:
            raise RuntimeError("FFmpeg-Frame-Writer ist fehlgeschlagen.") from self._writer_error

        self._dauer = self._frames_geschrieben / self._fps if self._fps > 0 else 0.0
        return self._dauer

    def _writer_loop(self) -> None:
        """Schreibt Frames entkoppelt vom Capture-Thread in die FFmpeg-Pipe."""
        writer_queue = self._writer_queue
        if writer_queue is None:
            return

        while True:
            item = writer_queue.get()
            try:
                if item is None:
                    return
                if self._prozess is None or self._prozess.stdin is None:
                    raise RuntimeError("FFmpeg-Pipe ist nicht verfügbar.")
                self._prozess.stdin.write(item)
                with self._status_lock:
                    self._frames_geschrieben += 1
            except BaseException as exc:
                with self._status_lock:
                    self._writer_error = exc
                return
            finally:
                writer_queue.task_done()

    def _request_writer_stop(self) -> None:
        """Reiht den Shutdown ein und verwirft bei Bedarf Restframes kontrolliert."""
        writer_queue = self._writer_queue
        if writer_queue is None:
            return

        while True:
            try:
                writer_queue.put(None, timeout=self._writer_join_timeout)
                return
            except queue.Full:
                try:
                    writer_queue.get_nowait()
                    writer_queue.task_done()
                    with self._status_lock:
                        self._frames_verworfen += 1
                except queue.Empty:
                    continue


def mux_audio_video(
    video_path: str,
    audio_path: str,
    out_path: str,
    ffmpeg_bin: str = "ffmpeg",
) -> str:
    """Kombiniert ein (stummes) Video + eine WAV-Datei zu einer MP4 mit Audio.

    Nutzt FFmpeg mit `-c:v copy -c:a aac -shortest` — kopiert Video-Stream,
    kodiert Audio als AAC, beendet beim kürzeren der beiden Streams.

    Args:
        video_path: Pfad zur (stummen) Eingabe-MP4.
        audio_path: Pfad zur WAV-Datei.
        out_path: Pfad zur Ausgabe-MP4.
        ffmpeg_bin: Pfad oder Name des FFmpeg-Binaries.

    Returns:
        out_path (immer der übergebene Ausgabepfad).

    Raises:
        RuntimeError: Wenn ffmpeg nicht gefunden wurde oder fehlschlug.
        FileNotFoundError: Wenn Eingabedateien nicht existieren.
    """
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video-Eingabedatei nicht gefunden: {video_path}")
    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio-Eingabedatei nicht gefunden: {audio_path}")

    if shutil.which(ffmpeg_bin) is None:
        raise RuntimeError(
            f"ffmpeg-Binary '{ffmpeg_bin}' nicht gefunden. "
            "Bitte ffmpeg installieren und im PATH bereitstellen."
        )

    verzeichnis = os.path.dirname(os.path.abspath(out_path))
    os.makedirs(verzeichnis, exist_ok=True)

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", video_path,
        "-i", audio_path,
        "-c:v", "copy",
        "-c:a", "aac",
        "-shortest",
        out_path,
    ]

    ergebnis = subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,   # subprocess.run drainent PIPE automatisch — kein Deadlock
        timeout=60,
    )

    if ergebnis.returncode != 0:
        stderr_text = ergebnis.stderr.decode("utf-8", errors="replace") if ergebnis.stderr else ""
        raise RuntimeError(
            f"ffmpeg Mux fehlgeschlagen (Exit-Code {ergebnis.returncode}). "
            f"Eingaben: video={video_path}, audio={audio_path}. "
            f"FFmpeg-Ausgabe: {stderr_text[-2000:]!r}"
        )

    return out_path
