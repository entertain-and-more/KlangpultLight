"""tests.test_engine_system_channel — AudioEngine im Mock-Modus mit System-Kanal.

TDD (Task 3b). Headless, PODCAST_RECORDER_MOCK_AUDIO=1 vorausgesetzt.

Belegt: Wenn ein MixerChannel mit source_id="system" in der Kanalliste ist,
schreibt der Mock-Thread Frames für diesen Kanal, und Peaks / WAV-Datei
sind nach einer Aufnahme > 0.
"""
import os
import time
import tempfile

import pytest


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _mock_engine_mit_system(tmp_dir: str):
    """Baut Engine + 3 Kanäle (mic_1, mic_2, system) im Mock-Modus."""
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    channels = [
        MixerChannel(source_id="mic_1", name="Mikrofon 1"),
        MixerChannel(source_id="mic_2", name="Mikrofon 2"),
        MixerChannel(
            source_id="system",
            name="Systemton",
            device_index=7,
            capture_method="wasapi_loopback",
        ),
    ]
    config = AppConfig(workspace_dir=tmp_dir, mock_audio=True)
    engine = AudioEngine(config=config, channels=channels)
    return engine


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_engine_startet_mit_system_kanal():
    """AudioEngine mit system-Kanal startet und läuft ohne Fehler."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _mock_engine_mit_system(tmp)
        engine.start()
        time.sleep(0.05)
        assert engine.is_running()
        engine.stop()


def test_engine_channel_count_mit_system():
    """channel_count() gibt 3 zurück (mic_1, mic_2, system)."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _mock_engine_mit_system(tmp)
        assert engine.channel_count() == 3


def test_system_kanal_peaks_vorhanden():
    """Nach start() liefert latest_peaks() 3 Werte (inkl. System-Kanal)."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _mock_engine_mit_system(tmp)
        engine.start()
        time.sleep(0.15)  # Mock-Thread braucht Zeit, Frames zu produzieren
        peaks = engine.latest_peaks()
        engine.stop()

        assert len(peaks) == 3, f"Erwartet 3 Peaks, bekam {len(peaks)}"
        # Im Mock produziert der Thread echtes synthetisches Signal → min. ein Peak > 0
        assert any(p > 0 for p in peaks), (
            f"Mindestens ein Peak muss > 0 sein, bekam: {peaks}"
        )


def test_system_kanal_wav_geschrieben():
    """Nach Aufnahme existiert system.wav (Frame-Daten für System-Kanal wurden geschrieben)."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _mock_engine_mit_system(tmp)
        engine.start()

        aufnahme_dir = os.path.join(tmp, "aufnahme_test")
        engine.start_recording(aufnahme_dir)
        time.sleep(0.25)  # Mock-Thread produziert Frames
        ergebnis = engine.stop_recording()

        engine.stop()

        system_wav = os.path.join(aufnahme_dir, "system.wav")
        assert os.path.exists(system_wav), (
            f"system.wav wurde nicht geschrieben: {system_wav}"
        )
        assert os.path.getsize(system_wav) > 0, "system.wav ist leer"


def test_system_kanal_duration_positiv():
    """Aufnahme mit System-Kanal: duration > 0 (Frames wurden produziert)."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _mock_engine_mit_system(tmp)
        engine.start()

        aufnahme_dir = os.path.join(tmp, "aufnahme_dauer")
        engine.start_recording(aufnahme_dir)
        time.sleep(0.25)
        ergebnis = engine.stop_recording()

        engine.stop()

        assert ergebnis["duration"] > 0, (
            f"duration muss > 0 sein, bekam {ergebnis['duration']}"
        )


def test_system_kanal_in_channels_dict():
    """stop_recording() liefert 'system' in den channels-Pfaden."""
    with tempfile.TemporaryDirectory() as tmp:
        engine = _mock_engine_mit_system(tmp)
        engine.start()

        aufnahme_dir = os.path.join(tmp, "aufnahme_channels")
        engine.start_recording(aufnahme_dir)
        time.sleep(0.25)
        ergebnis = engine.stop_recording()

        engine.stop()

        assert "system" in ergebnis["channels"], (
            f"'system' muss in channels-Dict vorhanden sein, bekam: {ergebnis['channels'].keys()}"
        )
