"""Tests für video.video_manager — VideoManager im Mock-Modus."""
import os
import pytest


@pytest.fixture(autouse=True)
def mock_video_env(monkeypatch):
    """Alle Tests hier laufen mit Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def test_available_sources_liefert_mindestens_eine_quelle():
    """Im Mock-Modus liefert available_sources() mindestens 1 Quelle."""
    from video.video_manager import VideoManager

    vm = VideoManager()
    quellen = vm.available_sources()

    assert len(quellen) >= 1


def test_available_sources_mock_korrekt_markiert():
    """Mock-Quellen haben verified=True und is_mock=True."""
    from video.video_manager import VideoManager

    vm = VideoManager()
    quellen = vm.available_sources()

    mock_quellen = [q for q in quellen if q.is_mock]
    assert len(mock_quellen) >= 1

    for q in mock_quellen:
        assert q.verified is True, f"Mock-Quelle {q.source_id} muss verified=True haben"
        assert q.is_mock is True


def test_suggest_default_source_nicht_none():
    """suggest_default_source() gibt im Mock-Modus eine Quelle zurück (nicht None)."""
    from video.video_manager import VideoManager

    vm = VideoManager()
    quelle = vm.suggest_default_source()

    assert quelle is not None


def test_open_source_liefert_lesbare_quelle():
    """open_source() liefert eine VideoSource, aus der Frames gelesen werden können."""
    import numpy as np
    from video.video_manager import VideoManager

    vm = VideoManager()
    quellen = vm.available_sources()
    assert len(quellen) >= 1

    info = quellen[0]
    src = vm.open_source(info)
    src.open()

    frame = src.read_frame()
    assert frame is not None
    assert frame.ndim == 3
    assert frame.shape[2] == 3
    assert frame.dtype == np.uint8

    src.close()


def test_list_camera_sources_gibt_liste():
    """list_camera_sources() gibt eine Liste zurück (kann leer sein im Mock-Env)."""
    from video.video_manager import VideoManager

    vm = VideoManager()
    kamera_quellen = vm.list_camera_sources(verify=False, max_index=2)
    assert isinstance(kamera_quellen, list)


def test_list_screen_sources_gibt_liste():
    """list_screen_sources() gibt eine Liste zurück (kann leer sein im Mock-Env)."""
    from video.video_manager import VideoManager

    vm = VideoManager()
    bildschirm_quellen = vm.list_screen_sources()
    assert isinstance(bildschirm_quellen, list)
