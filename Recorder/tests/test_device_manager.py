"""Tests für audio.device_manager — Mock-Geräteliste und Default-Zuweisung."""
import os
import pytest


@pytest.fixture(autouse=True)
def mock_audio_env(monkeypatch):
    """Alle Tests in dieser Datei laufen mit Mock-Audio."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")


def test_mock_liefert_mindestens_zwei_geraete():
    """Im Mock-Modus gibt list_input_devices ≥2 Geräte zurück."""
    from audio.device_manager import DeviceManager
    dm = DeviceManager()
    geraete = dm.list_input_devices(verify=True)
    assert len(geraete) >= 2


def test_mock_geraete_sind_verifiziert():
    """Mock-Geräte sind als verified=True und is_mock=True markiert."""
    from audio.device_manager import DeviceManager
    dm = DeviceManager()
    geraete = dm.list_input_devices(verify=True)
    for g in geraete:
        assert g.verified is True
        assert g.is_mock is True


def test_mock_geraete_haben_korrekte_felder():
    """AudioDevice-Felder sind korrekt befüllt."""
    from audio.device_manager import DeviceManager, AudioDevice
    dm = DeviceManager()
    geraete = dm.list_input_devices()
    for g in geraete:
        assert isinstance(g, AudioDevice)
        assert g.name  # nicht leer
        assert g.max_input_channels >= 1
        assert g.default_samplerate > 0


def test_suggest_default_assignment_belegt_mic1_und_mic2():
    """suggest_default_assignment liefert mic_1 und mic_2 als AudioDevice."""
    from audio.device_manager import DeviceManager, AudioDevice
    dm = DeviceManager()
    zuweisung = dm.suggest_default_assignment()
    assert "mic_1" in zuweisung
    assert "mic_2" in zuweisung
    assert "system" in zuweisung
    assert zuweisung["mic_1"] is not None
    assert isinstance(zuweisung["mic_1"], AudioDevice)
    assert zuweisung["mic_2"] is not None
    assert isinstance(zuweisung["mic_2"], AudioDevice)
    # 'system' bleibt None wenn kein Loopback erkennbar (Mock-Modus)
    # (None ist erlaubt laut Brief)
