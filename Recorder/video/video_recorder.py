"""video.video_recorder — VideoRecorder via FFmpeg-Subprocess-Pipe + mux_audio_video.

Kein GUI-Import. Kein PySide6.
ffmpeg muss im PATH oder als expliziter Pfad übergeben werden.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
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
    ) -> None:
        """
        Args:
            width: Frame-Breite in Pixeln.
            height: Frame-Höhe in Pixeln.
            fps: Ziel-Bildrate (Frames pro Sekunde).
            ffmpeg_bin: Pfad oder Name des FFmpeg-Binaries.
        """
        self._width = width
        self._height = height
        self._fps = fps
        self._ffmpeg_bin = ffmpeg_bin

        self._prozess: Optional[subprocess.Popen] = None
        self._frames_geschrieben: int = 0
        self._out_pfad: Optional[str] = None
        self._dauer: float = 0.0  # letzte geschlossene Dauer — für idempotentes close()
        self._stderr_datei: Optional[tempfile.TemporaryFile] = None  # type: ignore[type-arg]

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
        self._dauer = 0.0

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

        self._prozess.stdin.write(frame.astype(np.uint8).tobytes())
        self._frames_geschrieben += 1

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

        # stdin schließen — FFmpeg signalisiert: keine weiteren Frames
        if self._prozess.stdin is not None:
            try:
                self._prozess.stdin.close()
            except BrokenPipeError:
                pass  # FFmpeg hat ggf. bereits beendet

        # Auf FFmpeg warten und Exit-Code prüfen
        returncode = self._prozess.wait()
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

        self._dauer = self._frames_geschrieben / self._fps if self._fps > 0 else 0.0
        return self._dauer


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
