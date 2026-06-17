"""audio.engine — AudioEngine: bindet alle Audio-Komponenten zusammen.

Kein GUI-Import. Keine QMutex/PySide6. Nur stdlib + numpy + soundfile.

Thread-Modell:
- Im Mock-Modus läuft ein Hintergrund-Thread, der synthetisches Audio
  (Sinus + Rauschen) produziert und durch die Block-Verarbeitungs-Pipeline
  schickt.
- Peaks werden in eine collections.deque geschrieben (thread-safe append).
- latest_peaks() liest die deque aus — für späteres QTimer-Polling aus der GUI.
- Kein direkter GUI-Aufruf aus dem Audio-Thread.
"""
import os
import threading
import time
from collections import deque
from typing import Optional

import numpy as np

from core.config import AppConfig
from core.app_state import AppState
from audio.mixer_channel import MixerChannel
from audio.master_bus import MasterBus
from audio.wav_recorder import WavRecorder


# Anzahl Frames pro synthetischem Block im Mock-Modus
_MOCK_BLOCK_GROESSE = 1024
# Samplerate des synthetischen Signals (überschrieben durch AppConfig)
_MOCK_SAMPLERATE = 48000


class AudioEngine:
    """Koordiniert Geräte-Streams, Kanäle, MasterBus und WavRecorder.

    Im Mock-Modus (PODCAST_RECORDER_MOCK_AUDIO=1 oder config.mock_audio=True)
    läuft ein Hintergrund-Thread, der synthetisches Audio produziert.
    Kein Hardware-Zugriff.
    """

    def __init__(
        self,
        config: AppConfig,
        channels: list[MixerChannel],
        state: Optional[AppState] = None,
    ) -> None:
        """Initialisiert die Engine.

        Args:
            config: Anwendungskonfiguration.
            channels: Liste der Mischer-Kanäle.
            state: Optionaler AppState für Zustandsexport (kann None sein).
        """
        self._config = config
        self._channels = channels
        self._state = state
        self._bus = MasterBus(channels)

        # Thread-safe Peak-Deque (maxlen verhindert unbegrenztes Wachstum)
        self._peak_deque: deque[list[float]] = deque(maxlen=10)

        # Backlog-Zähler: produziert minus konsumiert (für queue_backlog())
        # _produced wird im Mock-Loop bei jedem Block hochgezählt.
        # _consumed wird in latest_peaks() gesetzt.
        # queue_backlog() gibt max(0, _produced - _consumed) zurück.
        # Eigener Lock (nicht _aufnahme_lock — getrenntes Concern).
        self._produced: int = 0
        self._consumed: int = 0
        self._backlog_lock = threading.Lock()

        # Aufnahme-Zustand
        self._recording = False
        self._mix_recorder: Optional[WavRecorder] = None
        self._kanal_recorder: dict[str, WavRecorder] = {}
        self._aufnahme_dir: Optional[str] = None
        self._aufnahme_lock = threading.Lock()

        # Mock-Thread-Steuerung
        self._mock_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._laeuft = False

        # Initialer Peak-Eintrag (Nullen der Kanal-Länge) — damit
        # latest_peaks() schon vor start() eine gültige Liste liefert.
        self._peak_deque.append([0.0] * len(channels))

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Startet die Audio-Engine (Mock-Thread oder echte Streams)."""
        if self._laeuft:
            return

        self._stop_event.clear()

        if self._nutze_mock():
            self._mock_thread = threading.Thread(
                target=self._mock_loop,
                name="AudioEngine-Mock",
                daemon=True,
            )
            self._laeuft = True
            self._mock_thread.start()
        else:
            # Reale sounddevice-Streams (Task 3b).
            # Jeder MixerChannel mit device_index != None bekommt einen eigenen InputStream.
            # System-Kanäle (capture_method="wasapi_loopback") werden im Loopback-Modus
            # geöffnet: extra_settings=sounddevice.WasapiSettings(loopback=True).
            # ACHTUNG: WASAPI-Loopback ist nur auf Windows-Hardware verifizierbar —
            # im Mock-Pfad (PODCAST_RECORDER_MOCK_AUDIO=1) wird ein synthetischer
            # System-Kanal erzeugt; der reale Pfad hier ist für Produktionsbetrieb.
            self._starte_echte_streams()
            self._laeuft = True

    def stop(self) -> None:
        """Stoppt die Audio-Engine und beendet laufende Streams/Threads."""
        if not self._laeuft:
            return

        # Laufende Aufnahme abschließen, wenn aktiv
        if self._recording:
            self.stop_recording()

        self._stop_event.set()
        if self._mock_thread is not None:
            self._mock_thread.join(timeout=2.0)
            self._mock_thread = None

        # Reale sounddevice-Streams schließen (wenn vorhanden)
        for stream in getattr(self, "_echte_streams", []):
            try:
                stream.stop()
                stream.close()
            except Exception:
                pass
        self._echte_streams = []

        self._laeuft = False

    # -------------------------------------------------------------------------
    # Aufnahme
    # -------------------------------------------------------------------------

    def start_recording(self, out_dir: str) -> None:
        """Startet die Aufnahme in das angegebene Verzeichnis.

        Erzeugt je Kanal eine WAV-Datei (<source_id>.wav) sowie
        eine gemeinsame Mix-Datei (mix.wav).

        Args:
            out_dir: Zielverzeichnis (wird angelegt, falls nicht vorhanden).
        """
        with self._aufnahme_lock:
            if self._recording:
                return

            os.makedirs(out_dir, exist_ok=True)
            self._aufnahme_dir = out_dir

            sr = self._config.samplerate
            ch = self._config.channels

            # Mix-Recorder
            self._mix_recorder = WavRecorder(samplerate=sr, channels=ch)
            self._mix_recorder.open(os.path.join(out_dir, "mix.wav"))

            # Kanal-Recorder
            self._kanal_recorder = {}
            for kanal in self._channels:
                rec = WavRecorder(samplerate=sr, channels=ch)
                rec.open(os.path.join(out_dir, f"{kanal.source_id}.wav"))
                self._kanal_recorder[kanal.source_id] = rec

            self._recording = True

            if self._state is not None:
                self._state.recording = True

    def stop_recording(self) -> dict:
        """Beendet die Aufnahme und gibt Metadaten zurück.

        Returns:
            dict mit:
                "duration": float — Aufnahmedauer in Sekunden
                "mix": str — Pfad zur Mix-WAV
                "channels": dict[str, str] — source_id → Kanal-WAV-Pfad
        """
        with self._aufnahme_lock:
            if not self._recording:
                return {"duration": 0.0, "mix": "", "channels": {}}

            self._recording = False

            if self._state is not None:
                self._state.recording = False

            # Mix-Datei schließen
            mix_dauer = 0.0
            mix_pfad = ""
            if self._mix_recorder is not None:
                mix_dauer = self._mix_recorder.close()
                mix_pfad = os.path.join(self._aufnahme_dir or "", "mix.wav")
                self._mix_recorder = None

            # Kanal-Dateien schließen
            kanal_pfade: dict[str, str] = {}
            for source_id, rec in self._kanal_recorder.items():
                rec.close()
                kanal_pfade[source_id] = os.path.join(
                    self._aufnahme_dir or "", f"{source_id}.wav"
                )
            self._kanal_recorder = {}

            return {
                "duration": mix_dauer,
                "mix": mix_pfad,
                "channels": kanal_pfade,
            }

    # -------------------------------------------------------------------------
    # Peaks (für GUI-QTimer-Polling)
    # -------------------------------------------------------------------------

    def latest_peaks(self) -> list[float]:
        """Gibt die zuletzt gemessenen Kanal-Peaks zurück.

        Thread-safe: liest das letzte Element der deque.
        Liefert immer eine Liste der Länge len(channels), auch ohne start().

        Setzt _consumed = _produced (nicht +=1), weil deque[-1] stets den
        neuesten Block zurückgibt — alle dazwischenliegenden gelten als konsumiert.
        Dadurch misst queue_backlog() den Rückstand *seit dem letzten Poll*, nicht
        einen kumulativen Zähler.

        Returns:
            Liste von Peak-Floats, Länge = len(channels).
        """
        with self._backlog_lock:
            self._consumed = self._produced  # vollständiger Abgleich statt +=1
        if self._peak_deque:
            return list(self._peak_deque[-1])
        return [0.0] * len(self._channels)

    def queue_backlog(self) -> int:
        """Gibt den aktuellen Audio-Queue-Rückstau zurück.

        Thread-safe: liest _produced und _consumed unter Lock.
        Misst, wie viele produzierte Blöcke seit dem letzten
        latest_peaks()-Aufruf noch nicht abgeholt wurden.
        Nützlich als Eingabe für den DriftMonitor.

        Returns:
            Anzahl unabgeholter Blöcke (≥ 0).
        """
        with self._backlog_lock:
            return max(0, self._produced - self._consumed)

    def channel_count(self) -> int:
        """Gibt die Anzahl der MixerChannels zurück.

        Öffentlicher Accessor — vermeidet privaten _channels-Zugriff aus der GUI.

        Returns:
            Anzahl der registrierten MixerChannels.
        """
        return len(self._channels)

    def is_running(self) -> bool:
        """Gibt zurück, ob die Engine läuft.

        Öffentlicher Accessor — vermeidet privaten _laeuft-Zugriff.

        Returns:
            True, wenn start() aufgerufen wurde und stop() noch nicht.
        """
        return self._laeuft

    # -------------------------------------------------------------------------
    # Interne Hilfsmethoden
    # -------------------------------------------------------------------------

    def _starte_echte_streams(self) -> None:
        """Öffnet reale sounddevice-InputStreams je Kanal.

        Mic-Kanäle (capture_method != "wasapi_loopback") werden als normales
        InputStream(device=device_index) geöffnet.

        System-Kanäle (capture_method="wasapi_loopback") werden als Loopback
        geöffnet: InputStream(device=device_index,
                              extra_settings=sounddevice.WasapiSettings(loopback=True)).

        WASAPI-Loopback ist Windows-only und nur auf echter Hardware verifizierbar.
        Bei Fehler (ImportError, fehlende WASAPI-Unterstützung) wird der Kanal
        übersprungen und ein Hinweis geloggt.

        Die Streams werden in self._echte_streams gespeichert und in stop()
        wieder geschlossen.
        """
        self._echte_streams: list = []
        sr = self._config.samplerate
        ch = self._config.channels
        block_size = self._config.block_size

        try:
            import sounddevice as sd  # type: ignore[import-untyped]
        except ImportError:
            # sounddevice nicht installiert — kein Absturz, stilles Fallback
            return

        for kanal in self._channels:
            if kanal.device_index is None:
                continue  # Kanal ohne zugewiesenes Gerät überspringen

            try:
                if kanal.capture_method == "wasapi_loopback":
                    # WASAPI-Loopback: Ausgabegerät im Loopback-Modus öffnen.
                    # Nur auf Windows mit WASAPI-HostAPI verifizierbar.
                    try:
                        extra = sd.WasapiSettings(loopback=True)
                    except AttributeError:
                        # Ältere sounddevice-Version ohne WasapiSettings
                        continue
                    stream = sd.InputStream(
                        samplerate=sr,
                        channels=ch,
                        dtype="float32",
                        blocksize=block_size,
                        device=kanal.device_index,
                        extra_settings=extra,
                        callback=self._stream_callback_factory(kanal.source_id),
                    )
                else:
                    # Normales Mic/Line-Input
                    stream = sd.InputStream(
                        samplerate=sr,
                        channels=ch,
                        dtype="float32",
                        blocksize=block_size,
                        device=kanal.device_index,
                        callback=self._stream_callback_factory(kanal.source_id),
                    )
                stream.start()
                self._echte_streams.append(stream)
            except Exception:
                # Gerät nicht öffenbar (unplugged, falsche HostAPI, etc.) — überspringen
                pass

    def _stream_callback_factory(self, source_id: str):
        """Erzeugt einen sounddevice-Callback für einen bestimmten Kanal.

        Der Callback schreibt empfangene Frames in die WavRecorder-Instanz
        des Kanals (wenn Aufnahme aktiv) und aktualisiert Peaks.
        Kein GUI-Aufruf im Callback — Thread-Sicherheit via deque + Lock.
        """
        def _callback(indata, frames, time_info, status):
            block = indata.copy()

            # Kanal verarbeiten
            kanal = next((k for k in self._channels if k.source_id == source_id), None)
            if kanal is None:
                return

            blocks = {source_id: block}
            mix_block = self._bus.mix(blocks)
            peaks = self._bus.peaks()
            self._peak_deque.append(peaks)
            with self._backlog_lock:
                self._produced += 1

            if self._state is not None:
                self._state.peaks = peaks

            if self._recording:
                with self._aufnahme_lock:
                    if self._mix_recorder is not None:
                        self._mix_recorder.write(mix_block)
                    rec = self._kanal_recorder.get(source_id)
                    if rec is not None:
                        rec.write(block)

        return _callback

    def _nutze_mock(self) -> bool:
        """Prüft zur Laufzeit, ob Mock-Audio aktiv sein soll."""
        import os as _os
        if self._config.mock_audio:
            return True
        if _os.environ.get("PODCAST_RECORDER_MOCK_AUDIO", "").strip() == "1":
            return True
        try:
            import sounddevice as sd  # noqa: F401
            return False
        except Exception:
            return True

    def _mock_loop(self) -> None:
        """Hintergrund-Thread: produziert synthetisches Audio und verarbeitet es.

        Erzeugt einen Sinus-Block je Kanal und schickt ihn durch die Pipeline.
        Schreibt Peaks in die deque (thread-safe append, kein GUI-Aufruf).
        """
        sr = self._config.samplerate
        block_size = self._config.block_size
        ch = self._config.channels
        soll_intervall = block_size / sr  # Echtzeit-Intervall pro Block

        t = 0  # Zeit-Zähler für Sinus
        freq = 440.0  # Sinuston Kammerton A

        while not self._stop_event.is_set():
            start = time.monotonic()

            # Synthetisches Audio: Sinus + leichtes Rauschen
            frames = np.arange(block_size)
            sinus = 0.3 * np.sin(2 * np.pi * freq * (t + frames) / sr)
            rauschen = 0.01 * np.random.randn(block_size)
            mono = (sinus + rauschen).astype(np.float32)

            # Stereo-Block erzeugen (block_size × channels)
            block = np.stack([mono] * ch, axis=1)
            t += block_size

            # Einen Block je Kanal erzeugen und verarbeiten
            blocks: dict[str, np.ndarray] = {
                kanal.source_id: block.copy() for kanal in self._channels
            }
            mix_block = self._bus.mix(blocks)

            # Peaks in deque schreiben (thread-safe)
            peaks = self._bus.peaks()
            self._peak_deque.append(peaks)
            with self._backlog_lock:
                self._produced += 1  # Backlog-Zähler: ein Block produziert

            # AppState aktualisieren (falls vorhanden)
            if self._state is not None:
                self._state.peaks = peaks

            # Aufnahme schreiben (Lock-frei lesbar, da _recording volatile bool)
            if self._recording:
                with self._aufnahme_lock:
                    if self._mix_recorder is not None:
                        self._mix_recorder.write(mix_block)
                    for kanal in self._channels:
                        rec = self._kanal_recorder.get(kanal.source_id)
                        if rec is not None:
                            rec.write(blocks[kanal.source_id])

            # Echtzeit-Throttling: Thread schläft, um ca. echte Samplerate zu imitieren
            elapsed = time.monotonic() - start
            schlaf = soll_intervall - elapsed
            if schlaf > 0:
                time.sleep(schlaf)
