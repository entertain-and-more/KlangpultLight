"""stt.stt_manager — SttManager und Engine-Auswahllogik.

Der SttManager hängt sich in den Audio-Mix-Tap der AudioEngine ein,
akkumuliert Audio-Blöcke bis ein Fenster von ``window_seconds`` erreicht ist
und ruft dann im Worker-Thread die STT-Engine auf.

Kein GUI-Import. Keine optionalen Abhängigkeiten außer numpy (bereits Requirement).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, Optional

import numpy as np

from stt.engine_base import LiveSttEngine
from stt.transcript_models import TranscriptChunk

_log = logging.getLogger(__name__)


class SttManager:
    """Verbindet einen Audio-Tap mit einer STT-Engine.

    Akkumuliert Audio-Blöcke über :py:meth:`feed` und dispatcht sobald
    genug Audio für ein vollständiges Fenster vorliegt an den internen
    Worker-Thread, der :py:meth:`~stt.engine_base.LiveSttEngine.transcribe`
    aufruft.

    Thread-Sicherheit:
    - :py:meth:`feed` wird aus dem MixWorker-Thread aufgerufen → nie blockieren.
    - :py:meth:`on_chunk` wird aus dem STT-Worker-Thread aufgerufen → nie GUI direkt.

    Args:
        engine:         Zu verwendende STT-Engine.
        on_chunk:       Callback bei erkanntem Chunk, z. B.
                        ``lambda c: bridge.push_transcript_chunk(c.text, ...)``.
        samplerate:     Audio-Samplerate in Hz.
        window_seconds: Länge des Akkumulationsfensters in Sekunden (Standard 4.0 s).
    """

    def __init__(
        self,
        engine: LiveSttEngine,
        on_chunk: Callable[[TranscriptChunk], None],
        samplerate: int,
        window_seconds: float = 4.0,
    ) -> None:
        self._engine = engine
        self._on_chunk = on_chunk
        self._samplerate = samplerate
        self._window_seconds = window_seconds

        # Anzahl Samples, die ein vollständiges Fenster ausmachen
        self._fenster_samples = int(samplerate * window_seconds)

        # Akkumulations-Puffer (Liste von float32-Mono-Arrays)
        self._puffer: list[np.ndarray] = []
        self._puffer_samples: int = 0
        self._puffer_lock = threading.Lock()

        # Zeitmarke des ersten Samples im aktuellen Puffer (Sekunden)
        self._t_puffer_start: float = 0.0
        self._t_monoton: float = 0.0  # läuft mit feed()-Aufrufen mit

        # Worker-Thread
        self._work_event = threading.Event()
        self._stop_event = threading.Event()
        self._pending: list[tuple[np.ndarray, float]] = []  # (audio, t_start)
        self._pending_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Startet den internen Worker-Thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        self._work_event.clear()

        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="SttWorker",
            daemon=True,
        )
        self._worker_thread.start()
        _log.debug("SttManager gestartet (Engine: %s).", self._engine.name)

    def stop(self) -> None:
        """Stoppt den Worker-Thread sauber (kein Orphan-Thread)."""
        self._stop_event.set()
        self._work_event.set()  # Worker aus dem Wait wecken

        if self._worker_thread is not None:
            self._worker_thread.join(timeout=5.0)
            if self._worker_thread.is_alive():
                _log.warning(
                    "SttWorker-Thread hat nicht rechtzeitig beendet (Timeout 5 s)."
                )
            self._worker_thread = None

        _log.debug("SttManager gestoppt.")

    # -------------------------------------------------------------------------
    # Audio-Tap
    # -------------------------------------------------------------------------

    def feed(self, block: np.ndarray) -> None:
        """Nimmt einen Audio-Block entgegen (nicht-blockierend).

        Wird aus dem MixWorker-Thread aufgerufen. Akkumuliert Audio;
        sobald ``window_seconds`` erreicht, wird ein Job in die
        Worker-Queue gestellt.

        Args:
            block: Audio-Block als numpy-Array (beliebige Shape, wird zu Mono float32
                   konvertiert). Kein Crash bei ungültigem Shape.
        """
        try:
            mono = _zu_mono_float32(block)
        except Exception as exc:
            _log.warning("SttManager.feed: Konvertierungsfehler %s — Block verworfen.", exc)
            return

        n = len(mono)
        dt = n / max(1, self._samplerate)

        with self._puffer_lock:
            if not self._puffer:
                # Erstes Stück im neuen Fenster → Zeitmarke merken
                self._t_puffer_start = self._t_monoton
            self._puffer.append(mono)
            self._puffer_samples += n
            self._t_monoton += dt

            if self._puffer_samples >= self._fenster_samples:
                # Fenster voll → Kopie extrahieren und an Worker übergeben
                audio_chunk = np.concatenate(self._puffer)
                t_start = self._t_puffer_start
                # Puffer zurücksetzen
                self._puffer = []
                self._puffer_samples = 0

                with self._pending_lock:
                    self._pending.append((audio_chunk, t_start))
                self._work_event.set()

    # -------------------------------------------------------------------------
    # Interner Worker
    # -------------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Zentraler Worker-Thread: wartet auf Jobs und ruft transcribe() auf."""
        while not self._stop_event.is_set():
            self._work_event.wait()
            self._work_event.clear()

            # Jobs abarbeiten
            while True:
                with self._pending_lock:
                    if not self._pending:
                        break
                    audio, t_start = self._pending.pop(0)

                try:
                    chunks = self._engine.transcribe(
                        audio,
                        samplerate=self._samplerate,
                        t_start=t_start,
                    )
                except Exception as exc:
                    _log.warning(
                        "SttManager: engine.transcribe Fehler (Engine %s): %s",
                        self._engine.name,
                        exc,
                    )
                    chunks = []

                for chunk in chunks:
                    try:
                        self._on_chunk(chunk)
                    except Exception as exc:
                        _log.warning("SttManager: on_chunk Fehler: %s", exc)


# ---------------------------------------------------------------------------
# Engine-Auswahllogik
# ---------------------------------------------------------------------------


def select_engine(
    prefer: str,
    local: LiveSttEngine,
    cloud: LiveSttEngine,
    mock: Optional[LiveSttEngine] = None,
) -> LiveSttEngine:
    """Wählt die passende STT-Engine gemäß Prioritätsstrategie.

    Strategie:
    1. ``prefer="cloud"`` → Cloud, wenn :py:meth:`~stt.engine_base.LiveSttEngine.available`.
       Sonst: lokal, wenn verfügbar. Sonst: mock (falls übergeben) oder lokal (inaktiv).
    2. ``prefer="local"`` (oder anderer Wert) → lokal, wenn verfügbar.
       Sonst: mock (falls übergeben) oder lokal (inaktiv).

    Die Funktion gibt NIE ``None`` zurück (verhindert NoneType-Fehler).

    Args:
        prefer: ``"cloud"`` oder ``"local"`` (Standard: ``"local"``).
        local:  Lokale Engine-Instanz.
        cloud:  Cloud-Engine-Instanz.
        mock:   Optionaler Mock (nur in Tests übergeben).

    Returns:
        Die gewählte :class:`~stt.engine_base.LiveSttEngine`-Instanz.
    """
    if prefer == "cloud":
        if cloud.available():
            _log.info("STT: Cloud-Engine gewählt.")
            return cloud
        _log.info(
            "STT: Cloud-Engine nicht verfügbar (fehlende Lib oder API-Schlüssel). "
            "Fallback auf lokale Engine."
        )

    # Lokal versuchen
    if local.available():
        _log.info("STT: Lokale Engine gewählt.")
        return local

    # Mock (nur in Tests/Entwicklung)
    if mock is not None and mock.available():
        _log.info("STT: Weder lokal noch Cloud verfügbar — Mock-Engine gewählt.")
        return mock

    # Kein funktionierender Adapter → lokal zurückgeben (inaktiv, aber kein Crash)
    _log.warning(
        "STT: Keine Engine verfügbar (faster-whisper und openai nicht installiert, "
        "kein API-Schlüssel). Live-Transkription deaktiviert."
    )
    return local


# ---------------------------------------------------------------------------
# Hilfsfunktionen (modulprivat)
# ---------------------------------------------------------------------------


def _zu_mono_float32(audio: np.ndarray) -> np.ndarray:
    """Konvertiert ein Audio-Array zu 1D Mono float32."""
    arr = np.asarray(audio, dtype=np.float32)
    if arr.ndim == 1:
        return arr
    if arr.ndim == 2:
        if arr.shape[1] == 1:
            return arr[:, 0]
        return arr.mean(axis=1)
    return arr.flatten()
