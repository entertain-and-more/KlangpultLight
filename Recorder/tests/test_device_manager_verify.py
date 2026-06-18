"""Tests für audio.device_manager — echte Mic-Verifikation via Stream-Öffnen (Task 6b, TDD / M-2).

Prüft:
  - Im Mock-Modus: verified=True, is_mock=True (unverändert)
  - Realer Pfad: Stream-Öffnen erfolgreich → verified=True
  - Realer Pfad: Stream-Öffnen schlägt fehl → verified=False, kein Crash
  - Fehlertolerant: Exception beim Öffnen → verified=False
"""
import os
import pytest


@pytest.fixture(autouse=True)
def mock_audio_env(monkeypatch):
    """Standard-Mock-Audio-Env — einzelne Tests können das überschreiben."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")


class TestDeviceManagerVerifyMock:
    def test_mock_geraete_sind_verifiziert(self):
        """Im Mock-Modus: Geräte haben verified=True (Mock-Pfad unverändert)."""
        from audio.device_manager import DeviceManager
        dm = DeviceManager()
        geraete = dm.list_input_devices(verify=True)
        assert len(geraete) >= 2
        for g in geraete:
            assert g.verified is True
            assert g.is_mock is True

    def test_mock_verify_false_liefert_kein_crash(self):
        """Im Mock-Modus: verify=False gibt Mock-Geräte zurück, kein Crash."""
        from audio.device_manager import DeviceManager
        dm = DeviceManager()
        geraete = dm.list_input_devices(verify=False)
        assert len(geraete) >= 2


class TestDeviceManagerVerifyReal:
    """Tests für den realen Verifikations-Pfad via sounddevice.InputStream.

    Diese Tests simulieren den realen Pfad durch direktes Patchen von sounddevice,
    ohne echte Hardware zu benötigen.
    """

    def test_stream_oeffnen_erfolgreich_setzt_verified_true(self, monkeypatch):
        """Wenn InputStream erfolgreich öffnet → verified=True."""
        import audio.device_manager as dm_module

        # Mock-Modus deaktivieren
        monkeypatch.delenv("PODCAST_RECORDER_MOCK_AUDIO", raising=False)

        # sounddevice simulieren: query_devices liefert 1 Gerät, InputStream öffnet ok
        class FakeInputStream:
            def __init__(self, *a, **kw):
                pass
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        class FakeSD:
            @staticmethod
            def query_devices():
                return [
                    {
                        "name": "Fake Mic",
                        "max_input_channels": 2,
                        "default_samplerate": 48000.0,
                    }
                ]
            InputStream = FakeInputStream

        import sys
        monkeypatch.setitem(sys.modules, "sounddevice", FakeSD)

        from importlib import reload
        import audio.device_manager
        reload(audio.device_manager)
        from audio.device_manager import DeviceManager

        dm = DeviceManager()
        geraete = dm.list_input_devices(verify=True)

        assert len(geraete) == 1
        assert geraete[0].verified is True
        assert geraete[0].is_mock is False

    def test_stream_oeffnen_schlaegt_fehl_setzt_verified_false(self, monkeypatch):
        """Wenn InputStream fehlschlägt → verified=False, kein Crash."""
        import audio.device_manager as dm_module

        monkeypatch.delenv("PODCAST_RECORDER_MOCK_AUDIO", raising=False)

        class BrokenInputStream:
            def __init__(self, *a, **kw):
                raise OSError("Gerät nicht verfügbar")
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        class FakeSD:
            @staticmethod
            def query_devices():
                return [
                    {
                        "name": "Broken Mic",
                        "max_input_channels": 1,
                        "default_samplerate": 44100.0,
                    }
                ]
            InputStream = BrokenInputStream

        import sys
        monkeypatch.setitem(sys.modules, "sounddevice", FakeSD)

        from importlib import reload
        import audio.device_manager
        reload(audio.device_manager)
        from audio.device_manager import DeviceManager

        dm = DeviceManager()
        # Darf keinen Crash werfen
        geraete = dm.list_input_devices(verify=True)

        assert len(geraete) == 1
        assert geraete[0].verified is False
        assert geraete[0].is_mock is False

    def test_verify_false_setzt_verified_false_kein_stream(self, monkeypatch):
        """verify=False → kein Stream-Öffnen, verified=False (wie bisher)."""
        monkeypatch.delenv("PODCAST_RECORDER_MOCK_AUDIO", raising=False)

        stream_geoeffnet = []

        class TrackingInputStream:
            def __init__(self, *a, **kw):
                stream_geoeffnet.append(True)
            def __enter__(self):
                return self
            def __exit__(self, *a):
                pass

        class FakeSD:
            @staticmethod
            def query_devices():
                return [
                    {
                        "name": "Track Mic",
                        "max_input_channels": 2,
                        "default_samplerate": 48000.0,
                    }
                ]
            InputStream = TrackingInputStream

        import sys
        monkeypatch.setitem(sys.modules, "sounddevice", FakeSD)

        from importlib import reload
        import audio.device_manager
        reload(audio.device_manager)
        from audio.device_manager import DeviceManager

        dm = DeviceManager()
        geraete = dm.list_input_devices(verify=False)

        assert len(stream_geoeffnet) == 0, "Bei verify=False darf kein Stream geöffnet werden"
        assert geraete[0].verified is False
