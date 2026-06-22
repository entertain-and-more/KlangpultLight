"""video.multi_capture_loop — Mehrquellen-Capture-Loop mit Compositing.

Kein GUI-Import. Kein PySide6.

MultiSourceCaptureLoop öffnet N VideoSource-Instanzen parallel,
liest je Tick den neuesten Frame jeder Quelle, ruft compose_layout() auf
und liefert den komponierten Frame via on_frame-Callback und latest_frame().

Thread-Modell:
  - Pro Quelle: ein VideoCaptureLoop-Thread (FPS-throttled, latest_frame nur lesen)
  - Ein Compositor-Thread: pollt alle Kinder-latest_frame(), komponiert, liefert on_frame
  - Alle Threads sind Daemon-Threads; stop() jointed alle mit Timeout
  - Keine GUI-Aufrufe erlaubt

API (duck-type zu VideoCaptureLoop):
  start()           → startet alle Kind-Loops + Compositor-Thread
  stop()            → stoppt alles sauber (join mit Timeout)
  latest_frame()    → letzter komponierter Frame (thread-safe, kann None sein)
  _alle_threads()   → interne Liste aller verwalteten Threads (für Tests)
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Optional

import numpy as np


class MultiSourceCaptureLoop:
    """Mehrquellen-Capture-Loop: N VideoSource-Instanzen → 1 komponierter Frame.

    Args:
        sources: Liste von VideoSource-Instanzen (noch nicht geöffnet).
        out_size: Ziel-Canvas-Größe als (width, height).
        ziel_fps: Ziel-FPS des Compositor-Tickers (Standard: 30).
        on_frame: Optionaler Callback der bei jedem komponierten Frame aufgerufen wird.
                  Wird im Compositor-Thread aufgerufen — KEIN GUI-Aufruf erlaubt.
    """

    def __init__(
        self,
        sources: list,
        out_size: tuple[int, int] = (1280, 720),
        ziel_fps: int = 30,
        on_frame: Optional[Callable[[np.ndarray], None]] = None,
    ) -> None:
        self._sources = list(sources)
        self._out_size = out_size
        self._ziel_fps = ziel_fps
        self._on_frame = on_frame

        # Letzter komponierter Frame (thread-safe via Lock)
        self._letzter_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()

        # Steuer-Event
        self._stop_event = threading.Event()

        # Kind-Loops (VideoCaptureLoop je Quelle)
        self._kind_loops: list = []

        # Compositor-Thread
        self._compositor_thread: Optional[threading.Thread] = None

        self._gestartet = False

    # -------------------------------------------------------------------------
    # Öffentliche API
    # -------------------------------------------------------------------------

    def start(self) -> None:
        """Startet alle Kind-Loops und den Compositor-Thread.

        Bei Fehler im Compositor-Thread-Start werden bereits gestartete
        Kind-Loops gestoppt (kein Ressourcenleck bei partiellem Start).
        """
        if self._gestartet:
            return

        self._stop_event.clear()

        # Kind-Loops starten (ein VideoCaptureLoop pro Quelle)
        from video.video_capture_loop import VideoCaptureLoop
        neue_kind_loops = []
        try:
            for source in self._sources:
                loop = VideoCaptureLoop(source=source, ziel_fps=self._ziel_fps)
                loop.start()
                neue_kind_loops.append(loop)

            # Compositor-Thread starten
            compositor = threading.Thread(
                target=self._compositor_loop,
                name="MultiSourceCompositor",
                daemon=True,
            )
            compositor.start()
        except Exception:
            # Rollback: alle gestarteten Kind-Loops stoppen
            for loop in neue_kind_loops:
                try:
                    loop.stop()
                except Exception:
                    pass
            raise

        self._kind_loops = neue_kind_loops
        self._compositor_thread = compositor
        self._gestartet = True

    def stop(self) -> None:
        """Stoppt alle Kind-Loops und den Compositor-Thread sauber."""
        self._stop_event.set()
        self._gestartet = False

        # Compositor-Thread joinen
        if self._compositor_thread is not None:
            self._compositor_thread.join(timeout=3.0)
            self._compositor_thread = None

        # Kind-Loops stoppen
        for loop in self._kind_loops:
            try:
                loop.stop()
            except Exception:
                pass
        self._kind_loops.clear()

    def latest_frame(self) -> Optional[np.ndarray]:
        """Gibt den letzten komponierten Frame thread-safe zurück (kann None sein)."""
        with self._frame_lock:
            f = self._letzter_frame
            if f is None:
                return None
            return f.copy()

    def _alle_threads(self) -> list[threading.Thread]:
        """Gibt alle verwalteten Threads zurück (für Tests)."""
        threads = []
        if self._compositor_thread is not None:
            threads.append(self._compositor_thread)
        for loop in self._kind_loops:
            if hasattr(loop, "_thread") and loop._thread is not None:
                threads.append(loop._thread)
        return threads

    # -------------------------------------------------------------------------
    # Interner Compositor-Loop
    # -------------------------------------------------------------------------

    def _compositor_loop(self) -> None:
        """Compositor-Thread: pollt Kind-Loops, komponiert, feuert on_frame."""
        from video.compositor import compose_layout

        interval = 1.0 / max(1, self._ziel_fps)
        naechster = time.monotonic()

        while not self._stop_event.is_set():
            jetzt = time.monotonic()
            if jetzt < naechster:
                time.sleep(naechster - jetzt)
                naechster = time.monotonic() + interval
            else:
                naechster = jetzt + interval

            # Neueste Frames von allen Kind-Loops lesen
            frames = []
            for loop in self._kind_loops:
                try:
                    frames.append(loop.latest_frame())
                except Exception:
                    frames.append(None)

            if not frames:
                continue

            # Compositing
            try:
                canvas = compose_layout(frames, self._out_size)
            except Exception:
                continue

            # Letzten Frame speichern
            with self._frame_lock:
                self._letzter_frame = canvas

            # Callback feuern
            if self._on_frame is not None:
                try:
                    self._on_frame(canvas)
                except Exception:
                    pass
