"""Tests für video.video_capture_loop — VideoCaptureLoop."""
import time
import threading
import numpy as np
import pytest


@pytest.fixture(autouse=True)
def mock_video_env(monkeypatch):
    """Alle Tests hier laufen mit Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _mock_source():
    """Erstellt eine MockVideoSource für Tests."""
    from video.video_manager import VideoManager
    manager = VideoManager()
    info = manager.suggest_default_source()
    assert info is not None
    return manager.open_source(info)


def test_capture_loop_liefert_frames_an_callback():
    """Loop ruft on_frame-Callback mit numpy-Frames auf."""
    empfangene: list[np.ndarray] = []

    def callback(frame: np.ndarray) -> None:
        empfangene.append(frame)

    from video.video_capture_loop import VideoCaptureLoop

    source = _mock_source()
    loop = VideoCaptureLoop(source=source, ziel_fps=30, on_frame=callback)

    loop.start()
    time.sleep(0.15)  # ~4-5 Frames bei 30 fps
    loop.stop()

    assert len(empfangene) > 0, "Kein Frame an Callback geliefert"
    for frame in empfangene:
        assert isinstance(frame, np.ndarray)
        assert frame.ndim == 3
        assert frame.shape[2] == 3  # BGR


def test_capture_loop_start_stop_sauber():
    """start()/stop() laufen ohne Exception, is_running ändert sich korrekt."""
    from video.video_capture_loop import VideoCaptureLoop

    source = _mock_source()
    loop = VideoCaptureLoop(source=source, ziel_fps=30)

    assert not loop.is_running
    loop.start()
    assert loop.is_running
    time.sleep(0.05)
    loop.stop()
    assert not loop.is_running


def test_capture_loop_latest_frame_abrufbar():
    """latest_frame() gibt nach kurzer Laufzeit einen Frame zurück."""
    from video.video_capture_loop import VideoCaptureLoop

    source = _mock_source()
    loop = VideoCaptureLoop(source=source, ziel_fps=30)

    loop.start()
    time.sleep(0.1)
    frame = loop.latest_frame()
    loop.stop()

    assert frame is not None, "latest_frame() muss nach 100 ms einen Frame liefern"
    assert isinstance(frame, np.ndarray)
    assert frame.ndim == 3


def test_capture_loop_start_idempotent():
    """Doppelter start()-Aufruf ist ein No-op (kein zweiter Thread)."""
    from video.video_capture_loop import VideoCaptureLoop

    source = _mock_source()
    loop = VideoCaptureLoop(source=source, ziel_fps=30)

    loop.start()
    loop.start()  # zweiter Aufruf — kein Fehler
    assert loop.is_running
    loop.stop()


def test_capture_loop_stop_ohne_start_kein_fehler():
    """stop() ohne vorherigem start() ist ein No-op."""
    from video.video_capture_loop import VideoCaptureLoop

    source = _mock_source()
    loop = VideoCaptureLoop(source=source, ziel_fps=30)

    loop.stop()  # kein Fehler erwartet
    assert not loop.is_running


def test_capture_loop_latest_frame_ist_kopie():
    """latest_frame() gibt eine Kopie zurück — Mutation ändert nicht den internen Zustand."""
    from video.video_capture_loop import VideoCaptureLoop

    source = _mock_source()
    loop = VideoCaptureLoop(source=source, ziel_fps=30)

    loop.start()
    time.sleep(0.1)

    frame1 = loop.latest_frame()
    if frame1 is not None:
        frame1[:] = 0  # mutieren

    frame2 = loop.latest_frame()
    loop.stop()

    # frame2 soll nicht durch frame1-Mutation beeinflusst worden sein
    if frame2 is not None:
        assert not np.all(frame2 == 0), "latest_frame() muss Kopie zurückgeben, nicht Referenz"
