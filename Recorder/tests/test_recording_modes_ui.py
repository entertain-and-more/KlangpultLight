"""Tests für Aufnahme-Modi und Audioquellen-Auswahl in ui.main_window."""
import sys

import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen hardwarefrei im Qt-Offscreen-Modus."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qt_app():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


class FakeRecordingSession:
    """Minimaler RecordingSession-Ersatz für UI-Starttests."""

    last_start = None

    def __init__(self, library, engine, state=None):
        self.library = library
        self.engine = engine
        self.state = state

    def start(self, title, video_source=None, video_sources=None, audio_enabled=True):
        FakeRecordingSession.last_start = {
            "title": title,
            "video_source": video_source,
            "video_sources": video_sources,
            "audio_enabled": audio_enabled,
        }

    def stop(self):
        return None


def _modus_setzen(fenster, modus: str) -> None:
    idx = fenster._aufnahme_modus.findData(modus)
    assert idx >= 0, f"Aufnahme-Modus fehlt: {modus}"
    fenster._aufnahme_modus.setCurrentIndex(idx)


def _fenster(tmp_path, monkeypatch):
    from audio.device_manager import DeviceManager
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.app_state import AppState
    from core.config import AppConfig
    from recordings.library import RecordingLibrary
    from sources.source_config import load_sources_config
    import ui.main_window as main_window_mod

    monkeypatch.setattr(main_window_mod, "RecordingSession", FakeRecordingSession)
    FakeRecordingSession.last_start = None

    cfg = AppConfig(
        mock_audio=True,
        workspace_dir=str(tmp_path),
        block_size=1024,
        samplerate=48000,
        channels=2,
    )
    channels = [
        MixerChannel(source_id="mic_1", name="Mikrofon 1"),
        MixerChannel(source_id="mic_2", name="Mikrofon 2"),
    ]
    state = AppState()
    engine = AudioEngine(cfg, channels, state=state)
    library = RecordingLibrary(str(tmp_path))
    sources = load_sources_config(None)

    fenster = main_window_mod.MainWindow(
        config=cfg,
        device_manager=DeviceManager(),
        engine=engine,
        library=library,
        state=state,
        sources_config=sources,
        sources_config_path=None,
    )
    return fenster, engine


def test_audio_quellen_checkbox_schaltet_engine(tmp_path, qt_app, monkeypatch):
    """Die Audioquellen-Checkbox wirkt direkt auf die laufende Engine."""
    fenster, engine = _fenster(tmp_path, monkeypatch)
    try:
        assert set(engine.active_channel_ids()) == {"mic_1", "mic_2"}

        fenster._capture_umschalten("mic_2", False)

        assert engine.active_channel_ids() == ["mic_1"]
    finally:
        fenster.close()


def test_modus_nur_ton_startet_ohne_videoquellen(tmp_path, qt_app, monkeypatch):
    """Nur Ton übergibt keine Videoquellen an RecordingSession."""
    fenster, _engine = _fenster(tmp_path, monkeypatch)
    try:
        _modus_setzen(fenster, "audio_only")
        fenster._aufnahme_starten()

        assert FakeRecordingSession.last_start is not None
        assert FakeRecordingSession.last_start["audio_enabled"] is True
        assert FakeRecordingSession.last_start["video_sources"] is None
    finally:
        fenster.close()


def test_modus_nur_video_startet_ohne_audio(tmp_path, qt_app, monkeypatch):
    """Nur Video übergibt audio_enabled=False und eine Videoquelle."""
    fenster, _engine = _fenster(tmp_path, monkeypatch)
    try:
        _modus_setzen(fenster, "video_only")
        fenster._aufnahme_starten()

        assert FakeRecordingSession.last_start is not None
        assert FakeRecordingSession.last_start["audio_enabled"] is False
        assert FakeRecordingSession.last_start["video_sources"]
    finally:
        fenster.close()
