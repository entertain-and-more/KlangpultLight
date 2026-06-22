"""Tests für audio.engine — AudioEngine im Mock-Modus (keine Hardware)."""
import os
import time
import pytest


@pytest.fixture(autouse=True)
def mock_audio_env(monkeypatch):
    """Alle Tests hier laufen mit Mock-Audio."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")


def test_engine_start_stop_ohne_fehler(tmp_path):
    """AudioEngine lässt sich im Mock-Modus starten und stoppen."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(cfg, kanaele)
    engine.start()
    time.sleep(0.05)
    engine.stop()


def test_engine_aufnahme_liefert_mix_wav(tmp_path):
    """start_recording + stop_recording liefert dict mit duration>0 und existierender mix.wav."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [
        MixerChannel(source_id="mic1", name="Mikrofon 1"),
        MixerChannel(source_id="mic2", name="Mikrofon 2"),
    ]
    engine = AudioEngine(cfg, kanaele)
    engine.start()
    time.sleep(0.05)

    aufnahme_dir = str(tmp_path / "aufnahme_01")
    engine.start_recording(aufnahme_dir)
    time.sleep(0.15)  # Kurz aufnehmen — genug für >0 Frames
    ergebnis = engine.stop_recording()

    engine.stop()

    assert "duration" in ergebnis
    assert ergebnis["duration"] > 0.0
    assert "mix" in ergebnis

    import pathlib
    assert pathlib.Path(ergebnis["mix"]).exists()


def test_engine_kanalaufnahmen_vorhanden(tmp_path):
    """stop_recording liefert auch die Einzel-Kanal-Dateien."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [
        MixerChannel(source_id="mic1", name="Mikrofon 1"),
        MixerChannel(source_id="mic2", name="Mikrofon 2"),
    ]
    engine = AudioEngine(cfg, kanaele)
    engine.start()
    time.sleep(0.05)

    aufnahme_dir = str(tmp_path / "aufnahme_02")
    engine.start_recording(aufnahme_dir)
    time.sleep(0.15)
    ergebnis = engine.stop_recording()
    engine.stop()

    import pathlib
    assert "channels" in ergebnis
    for source_id, kanal_pfad in ergebnis["channels"].items():
        assert pathlib.Path(kanal_pfad).exists(), f"Kanal-Datei fehlt: {kanal_pfad}"


def test_engine_latest_peaks_kanallaenge(tmp_path):
    """latest_peaks() liefert eine Liste in Kanal-Länge, nie leer."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [
        MixerChannel(source_id="mic1", name="Mikrofon 1"),
        MixerChannel(source_id="mic2", name="Mikrofon 2"),
    ]
    engine = AudioEngine(cfg, kanaele)
    engine.start()
    time.sleep(0.05)

    peaks = engine.latest_peaks()

    engine.stop()

    assert isinstance(peaks, list)
    assert len(peaks) == len(kanaele)


def test_engine_peaks_ohne_start():
    """latest_peaks() liefert auch ohne start() eine Liste der Kanal-Länge (Nullen)."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True)
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(cfg, kanaele)
    peaks = engine.latest_peaks()
    assert len(peaks) == 1


def test_engine_start_rollback_bei_mock_thread_fehler(tmp_path):
    """Wenn der Mock-Thread nicht gestartet werden kann, bleibt is_running() False.

    Belegt Bugsweep-Fix: Früher wurde der MixWorker gestartet und _laeuft blieb
    False — ein erneutes start() startete einen zweiten MixWorker auf demselben
    _kanal_puffer. Nach dem Fix: bei Fehler wird _stop_event gesetzt und der
    MixWorker gestoppt → sauberer Rollback.
    """
    import threading
    import unittest.mock as mock
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(cfg, kanaele)

    # Zweiten Thread-Start (Mock-Thread) sabotieren, ersten (MixWorker) durchlassen
    original_start = threading.Thread.start
    call_count = [0]

    def selektiver_fehler(self):
        call_count[0] += 1
        if call_count[0] == 2:
            raise RuntimeError("Simulierter Mock-Thread-Start-Fehler")
        return original_start(self)

    with mock.patch.object(threading.Thread, "start", selektiver_fehler):
        with pytest.raises(RuntimeError, match="Simulierter Mock-Thread-Start-Fehler"):
            engine.start()

    # Nach Rollback: is_running() muss False sein
    assert not engine.is_running(), "is_running() muss nach fehlgeschlagenem start() False sein"
    assert engine._mix_worker_thread is None, "_mix_worker_thread muss nach Rollback None sein"

    # Zweites start() muss funktionieren (kein blockierter Zustand)
    engine.start()
    try:
        import time
        time.sleep(0.05)
        assert engine.is_running(), "is_running() muss nach zweitem start() True sein"
    finally:
        engine.stop()
