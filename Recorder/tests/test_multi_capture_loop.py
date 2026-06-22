"""Tests für video.multi_capture_loop — MultiSourceCaptureLoop (Task 6b, TDD).

Prüft:
  - 2 Mock-Quellen → komponierter Frame kommt am Callback an
  - latest_frame() liefert den komponierten Frame (nicht None)
  - sauberer stop() — kein verwaister Thread
  - stop() vor start() → kein Absturz
"""
import threading
import time

import numpy as np
import pytest


@pytest.fixture(autouse=True)
def mock_video_env(monkeypatch):
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _zwei_mock_quellen():
    """Erstellt 2 MockVideoSource-Instanzen mit je eigenem Info-Objekt."""
    from video.video_source import MockVideoSource, VideoSourceInfo
    info0 = VideoSourceInfo(
        source_id="mock_0", name="Mock 0", kind="mock",
        verified=True, is_mock=True, width=128, height=72,
    )
    info1 = VideoSourceInfo(
        source_id="mock_1", name="Mock 1", kind="mock",
        verified=True, is_mock=True, width=128, height=72,
    )
    return MockVideoSource(info0), MockVideoSource(info1)


class TestMultiSourceCaptureLoop:
    def test_komponierter_frame_kommt_am_callback_an(self):
        """2 Mock-Quellen → on_frame-Callback empfängt mindestens einen komponierten Frame."""
        from video.multi_capture_loop import MultiSourceCaptureLoop

        src0, src1 = _zwei_mock_quellen()
        empfangen = threading.Event()
        frames_erhalten = []

        def on_frame(frame):
            frames_erhalten.append(frame)
            empfangen.set()

        loop = MultiSourceCaptureLoop(
            sources=[src0, src1],
            out_size=(128, 72),
            ziel_fps=30,
            on_frame=on_frame,
        )
        loop.start()
        try:
            ankam = empfangen.wait(timeout=3.0)
        finally:
            loop.stop()

        assert ankam, "on_frame-Callback wurde nicht innerhalb von 3 s aufgerufen"
        assert len(frames_erhalten) >= 1

    def test_callback_frame_hat_compositor_aufloesung(self):
        """Frames am Callback haben die richtige Zielgröße."""
        from video.multi_capture_loop import MultiSourceCaptureLoop

        out_size = (128, 72)
        W, H = out_size
        src0, src1 = _zwei_mock_quellen()
        erster_frame = []
        fertig = threading.Event()

        def on_frame(frame):
            if not erster_frame:
                erster_frame.append(frame)
                fertig.set()

        loop = MultiSourceCaptureLoop(
            sources=[src0, src1],
            out_size=out_size,
            ziel_fps=30,
            on_frame=on_frame,
        )
        loop.start()
        try:
            fertig.wait(timeout=3.0)
        finally:
            loop.stop()

        assert erster_frame, "Kein Frame empfangen"
        f = erster_frame[0]
        assert f.shape == (H, W, 3), f"Erwartete Form {(H, W, 3)}, erhalten {f.shape}"
        assert f.dtype == np.uint8

    def test_latest_frame_nicht_none_nach_start(self):
        """latest_frame() liefert nach kurzer Zeit einen Frame (nicht None)."""
        from video.multi_capture_loop import MultiSourceCaptureLoop

        src0, src1 = _zwei_mock_quellen()
        loop = MultiSourceCaptureLoop(
            sources=[src0, src1],
            out_size=(128, 72),
            ziel_fps=30,
        )
        loop.start()
        try:
            # Bis zu 3 s warten bis ein Frame ankommt
            deadline = time.time() + 3.0
            frame = None
            while time.time() < deadline:
                frame = loop.latest_frame()
                if frame is not None:
                    break
                time.sleep(0.05)
        finally:
            loop.stop()

        assert frame is not None, "latest_frame() muss nach Start einen Frame liefern"

    def test_sauberer_stop_kein_orphan_thread(self):
        """stop() wartet auf alle Threads — kein verwaister Thread danach."""
        from video.multi_capture_loop import MultiSourceCaptureLoop

        src0, src1 = _zwei_mock_quellen()
        loop = MultiSourceCaptureLoop(
            sources=[src0, src1],
            out_size=(128, 72),
            ziel_fps=30,
        )
        loop.start()
        time.sleep(0.1)
        loop.stop()

        # Interner Zustand: keine lebenden internen Threads
        lebende = [t for t in loop._alle_threads() if t.is_alive()]
        assert not lebende, f"Verwaiste Threads nach stop(): {lebende}"

    def test_stop_vor_start_kein_absturz(self):
        """stop() vor start() darf keinen Fehler werfen."""
        from video.multi_capture_loop import MultiSourceCaptureLoop

        src0, src1 = _zwei_mock_quellen()
        loop = MultiSourceCaptureLoop(
            sources=[src0, src1],
            out_size=(128, 72),
        )
        loop.stop()  # soll kein Exception werfen

    def test_latest_frame_vor_start_ist_none(self):
        """latest_frame() vor start() liefert None."""
        from video.multi_capture_loop import MultiSourceCaptureLoop

        src0, src1 = _zwei_mock_quellen()
        loop = MultiSourceCaptureLoop(
            sources=[src0, src1],
            out_size=(128, 72),
        )
        assert loop.latest_frame() is None

    def test_partieller_start_rollback_stoppt_kind_loops(self):
        """Wenn Compositor-Thread-Start wirft, werden Kind-Loops gestoppt.

        Belegt Bugsweep-Fix: Früher wurden Kind-Loops ohne Rollback gestartet
        — bei Fehler im Compositor-Thread liefen die Kind-Loops weiter.
        """
        import unittest.mock as mock
        import threading
        from video.multi_capture_loop import MultiSourceCaptureLoop

        src0, src1 = _zwei_mock_quellen()
        loop = MultiSourceCaptureLoop(
            sources=[src0, src1],
            out_size=(128, 72),
        )

        # Ersten Thread-Start (VideoCaptureLoop) durchlassen, Compositor sabotieren
        original_start = threading.Thread.start
        call_count = [0]
        started_threads = []

        def mock_start(self):
            call_count[0] += 1
            if self.name == "MultiSourceCompositor":
                raise RuntimeError("Compositor sabotiert")
            started_threads.append(self)
            return original_start(self)

        with mock.patch.object(threading.Thread, "start", mock_start):
            with pytest.raises(RuntimeError, match="Compositor sabotiert"):
                loop.start()

        # Nach Rollback: _gestartet muss False sein
        assert not loop._gestartet, "_gestartet muss False nach fehlgeschlagenem start() sein"
        assert loop._kind_loops == [], "_kind_loops muss leer sein nach Rollback"
