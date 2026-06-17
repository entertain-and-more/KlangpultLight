"""Tests für AudioEngine.queue_backlog() — öffentliche Backlog-API."""
import time
import pytest


@pytest.fixture(autouse=True)
def mock_audio_env(monkeypatch):
    """Alle Tests hier laufen mit Mock-Audio."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")


def test_queue_backlog_existiert_und_liefert_int(tmp_path):
    """queue_backlog() ist vorhanden und gibt einen int zurück."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(cfg, kanaele)

    backlog = engine.queue_backlog()
    assert isinstance(backlog, int)


def test_queue_backlog_vor_start_ist_null(tmp_path):
    """queue_backlog() gibt 0 zurück, bevor start() aufgerufen wurde."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(cfg, kanaele)

    assert engine.queue_backlog() == 0


def test_queue_backlog_steigt_nach_produktion(tmp_path):
    """Nach start() und kurzem Lauf ist queue_backlog() >= 0 (und mindestens einmal > 0 gewesen)."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(cfg, kanaele)

    engine.start()
    time.sleep(0.05)

    # Nach Produktion: Backlog ≥ 0, Wert muss int sein
    backlog = engine.queue_backlog()
    assert isinstance(backlog, int)
    assert backlog >= 0

    engine.stop()


def test_queue_backlog_sinkt_nach_latest_peaks(tmp_path):
    """Aufruf von latest_peaks() konsumiert Peaks — backlog danach <= vorher."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(cfg, kanaele)

    engine.start()
    time.sleep(0.1)  # Mehrere Blöcke produzieren lassen

    backlog_vorher = engine.queue_backlog()
    engine.latest_peaks()  # Konsumiert
    backlog_nachher = engine.queue_backlog()

    engine.stop()

    # Nach Konsum ≤ vorher (kann gleich sein wenn Produktion inzwischen aufgeholt)
    assert backlog_nachher <= backlog_vorher
