"""video.video_capture_loop — VideoCaptureLoop: Frames aus einer VideoSource in eigenem Thread.

Kein GUI-Import. Kein PySide6.
Thread-Modell:
  - _capture_thread läuft als Daemon-Thread und liest Frames aus der VideoSource.
  - Letzter Frame wird in self._letzter_frame (Lock-geschützt) abgelegt.
  - GUI-QTimer liest latest_frame() — niemals direkt aus dem Capture-Thread.
  - Optionaler on_frame-Callback für Weiterverarbeitung (z. B. VideoRecorder).
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable, Optional

import numpy as np


class VideoCaptureLoop:
    """Liest Frames aus einer VideoSource in einem eigenen Thread.

    Funktionsprinzip:
        start()    → öffnet die Quelle und startet den Capture-Thread
        stop()     → signalisiert Abbruch, wartet auf Thread-Ende, schließt Quelle
        latest_frame() → gibt den zuletzt gelesenen Frame zurück (thread-safe, Lock)

    Args:
        source: VideoSource-Instanz (noch nicht geöffnet).
        ziel_fps: Ziel-Bildrate (Frames pro Sekunde) des Capture-Threads.
        on_frame: Optionaler Callback, der bei jedem neuen Frame aufgerufen wird.
                  Wird im Capture-Thread aufgerufen — keine GUI-Zugriffe darin!
    """

    def __init__(
        self,
        source,  # VideoSource (kein direkter Import — vermeidet zirkuläre Abhängigkeiten)
        ziel_fps: int = 30,
        on_frame: Optional[Callable[[np.ndarray], None]] = None,
    ) -> None:
        self._source = source
        self._ziel_fps = max(1, ziel_fps)
        self._on_frame = on_frame

        # Thread-safe Speicher für letzten Frame
        self._frame_lock = threading.Lock()
        self._letzter_frame: Optional[np.ndarray] = None

        # Thread-Steuerung
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._laeuft = False

    def start(self) -> None:
        """Öffnet die Quelle und startet den Capture-Thread.

        Idempotent: zweiter Aufruf ohne vorherigem stop() ist ein No-op.
        """
        if self._laeuft:
            return

        self._source.open()
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="VideoCaptureLoop",
            daemon=True,
        )
        try:
            self._thread.start()
        except Exception:
            # Thread-Start gescheitert — Quelle wieder schließen und Zustand
            # konsistent halten (kein _laeuft=True bei totem Thread).
            self._thread = None
            try:
                self._source.close()
            except Exception:
                pass
            raise
        self._laeuft = True

    def stop(self) -> None:
        """Signalisiert Abbruch, wartet auf Thread-Ende und schließt Quelle.

        Idempotent: Aufruf ohne vorherigem start() ist ein No-op.
        """
        if not self._laeuft:
            return

        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

        try:
            self._source.close()
        except Exception:
            pass  # Quelle-Close-Fehler darf stop() nicht blockieren

        self._laeuft = False

    def latest_frame(self) -> Optional[np.ndarray]:
        """Gibt den zuletzt gelesenen Frame zurück.

        Thread-safe (Lock). Gibt None zurück, bevor der erste Frame gelesen wurde.

        Returns:
            numpy-Array (H, W, 3) BGR uint8 oder None.
        """
        with self._frame_lock:
            if self._letzter_frame is not None:
                return self._letzter_frame.copy()
            return None

    @property
    def is_running(self) -> bool:
        """True, wenn der Capture-Thread aktiv ist."""
        return self._laeuft

    # -------------------------------------------------------------------------
    # Interner Capture-Thread
    # -------------------------------------------------------------------------

    def _capture_loop(self) -> None:
        """Capture-Thread: liest Frames mit Ziel-FPS-Throttling.

        Kein GUI-Aufruf! on_frame-Callback + _letzter_frame-Update.
        """
        intervall = 1.0 / self._ziel_fps

        while not self._stop_event.is_set():
            start = time.monotonic()

            try:
                frame = self._source.read_frame()
            except Exception:
                frame = None

            if frame is not None:
                with self._frame_lock:
                    self._letzter_frame = frame

                if self._on_frame is not None:
                    try:
                        self._on_frame(frame)
                    except Exception:
                        pass  # Callback-Fehler darf den Loop nicht stoppen

            # Echtzeit-Throttling: Thread schläft, um die Ziel-FPS zu halten
            elapsed = time.monotonic() - start
            schlaf = intervall - elapsed
            if schlaf > 0:
                time.sleep(schlaf)
