"""Tests für video.video_source — MockVideoSource, ohne Hardware."""
import numpy as np
import pytest


@pytest.fixture(autouse=True)
def mock_video_env(monkeypatch):
    """Alle Tests hier laufen mit Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def test_mock_video_source_liefert_frame_korrekte_shape():
    """MockVideoSource liefert Frames mit Shape (H, W, 3) und dtype uint8."""
    from video.video_source import MockVideoSource, VideoSourceInfo

    info = VideoSourceInfo(
        source_id="mock_0",
        name="Mock-Quelle",
        kind="mock",
        verified=True,
        is_mock=True,
        width=640,
        height=480,
    )
    src = MockVideoSource(info)
    src.open()

    frame = src.read_frame()
    assert frame is not None
    assert frame.shape == (480, 640, 3)
    assert frame.dtype == np.uint8

    src.close()


def test_mock_video_source_frames_deterministisch():
    """MockVideoSource liefert für gleichen Frame-Zähler das gleiche Bild."""
    from video.video_source import MockVideoSource, VideoSourceInfo

    info = VideoSourceInfo(
        source_id="mock_0",
        name="Mock-Quelle",
        kind="mock",
        verified=True,
        is_mock=True,
    )
    src = MockVideoSource(info)
    src.open()

    frame_a = src.read_frame()
    src.close()

    # Neu öffnen — Frame-Zähler startet von 0
    src.open()
    frame_b = src.read_frame()
    src.close()

    assert frame_a is not None
    assert frame_b is not None
    assert np.array_equal(frame_a, frame_b), "Frames bei gleichem Zählerstand müssen identisch sein"


def test_mock_video_source_frame_zaehler_steigt():
    """Aufeinanderfolgende Frames unterscheiden sich (Zähler-Einbettung)."""
    from video.video_source import MockVideoSource, VideoSourceInfo

    info = VideoSourceInfo(
        source_id="mock_0",
        name="Mock-Quelle",
        kind="mock",
        verified=True,
        is_mock=True,
    )
    src = MockVideoSource(info)
    src.open()

    frame1 = src.read_frame()
    frame2 = src.read_frame()

    src.close()

    assert frame1 is not None
    assert frame2 is not None
    assert not np.array_equal(frame1, frame2), "Aufeinanderfolgende Frames müssen verschieden sein"


def test_mock_video_source_open_close_idempotent():
    """open() und close() sind idempotent (mehrfach aufrufbar ohne Fehler)."""
    from video.video_source import MockVideoSource, VideoSourceInfo

    info = VideoSourceInfo(
        source_id="mock_0",
        name="Mock-Quelle",
        kind="mock",
        verified=True,
        is_mock=True,
    )
    src = MockVideoSource(info)

    # open() mehrfach
    src.open()
    src.open()

    frame = src.read_frame()
    assert frame is not None

    # close() mehrfach
    src.close()
    src.close()


def test_mock_video_source_read_frame_vor_open_gibt_none():
    """read_frame() vor open() gibt None zurück (kein Absturz)."""
    from video.video_source import MockVideoSource, VideoSourceInfo

    info = VideoSourceInfo(
        source_id="mock_0",
        name="Mock-Quelle",
        kind="mock",
        verified=True,
        is_mock=True,
    )
    src = MockVideoSource(info)
    frame = src.read_frame()
    assert frame is None


def test_mock_video_source_info_property():
    """info-Property gibt das übergebene VideoSourceInfo-Objekt zurück."""
    from video.video_source import MockVideoSource, VideoSourceInfo

    info = VideoSourceInfo(
        source_id="mock_42",
        name="Test-Mock",
        kind="mock",
        verified=True,
        is_mock=True,
        width=320,
        height=240,
    )
    src = MockVideoSource(info)
    assert src.info is info
    assert src.info.source_id == "mock_42"
    assert src.info.is_mock is True
