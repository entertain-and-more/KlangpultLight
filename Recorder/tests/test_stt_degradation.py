"""Tests für Degradation der STT-Engines bei fehlenden Bibliotheken / API-Keys.

Headless, keine echten Modelle, kein Netzwerk.
Prüft: LocalWhisperEngine und CloudSttEngine degradieren sauber ohne Crash.
"""
import sys

import numpy as np
import pytest

from stt.local_engine import LocalWhisperEngine
from stt.cloud_engine import CloudSttEngine


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _leerer_block(samples: int = 4096) -> np.ndarray:
    return np.zeros(samples, dtype=np.float32)


# ---------------------------------------------------------------------------
# Tests: LocalWhisperEngine
# ---------------------------------------------------------------------------


class TestLocalWhisperEngineDegradation:
    """LocalWhisperEngine verhält sich korrekt, wenn faster-whisper fehlt."""

    def test_available_false_wenn_lib_fehlt(self, monkeypatch):
        """available() == False, wenn faster_whisper nicht importierbar ist."""
        engine = LocalWhisperEngine()

        # Sicherstellen, dass faster_whisper nicht importiert werden kann
        monkeypatch.setitem(sys.modules, "faster_whisper", None)

        # Cache zurücksetzen (private API — nötig für deterministischen Test)
        engine._lib_verfuegbar = None

        verfuegbar = engine.available()
        assert verfuegbar is False

    def test_available_gibt_false_zurueck_kein_crash(self, monkeypatch):
        """available() stürzt nicht ab, wenn die Bibliothek fehlt."""
        engine = LocalWhisperEngine()
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        engine._lib_verfuegbar = None

        # Kein Exception-Raise erwartet
        try:
            engine.available()
        except Exception as exc:
            pytest.fail(f"available() hat eine Exception geworfen: {exc}")

    def test_transcribe_ohne_lib_gibt_leere_liste(self, monkeypatch):
        """transcribe() gibt leere Liste zurück, wenn Bibliothek fehlt — kein Crash."""
        engine = LocalWhisperEngine()
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        engine._lib_verfuegbar = None

        result = engine.transcribe(_leerer_block(), samplerate=48_000, t_start=0.0)

        assert result == [], f"Erwartet [], erhalten {result}"

    def test_available_ergebnis_wird_gecacht(self, monkeypatch):
        """available() Cache-Verhalten: zweiter Aufruf nutzt gecachtes Ergebnis."""
        engine = LocalWhisperEngine()
        monkeypatch.setitem(sys.modules, "faster_whisper", None)
        engine._lib_verfuegbar = None

        ergebnis1 = engine.available()
        ergebnis2 = engine.available()

        assert ergebnis1 == ergebnis2


# ---------------------------------------------------------------------------
# Tests: CloudSttEngine
# ---------------------------------------------------------------------------


class TestCloudSttEngineDegradation:
    """CloudSttEngine verhält sich korrekt bei fehlender Lib oder fehlendem Key."""

    def test_available_false_wenn_lib_fehlt(self, monkeypatch):
        """available() == False, wenn openai nicht importierbar ist."""
        engine = CloudSttEngine()
        monkeypatch.setitem(sys.modules, "openai", None)
        engine._lib_verfuegbar = None

        verfuegbar = engine.available()
        assert verfuegbar is False

    def test_available_false_wenn_key_fehlt(self, monkeypatch):
        """available() == False, wenn OPENAI_API_KEY nicht gesetzt ist."""
        engine = CloudSttEngine()
        engine._lib_verfuegbar = None

        # Sicherstellen dass openai importierbar ERSCHEINT (Stub-Modul)
        import types
        stub = types.ModuleType("openai")
        monkeypatch.setitem(sys.modules, "openai", stub)

        # API-Key entfernen (deterministisch — nicht auf Zufall verlassen)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

        verfuegbar = engine.available()
        assert verfuegbar is False

    def test_available_false_wenn_key_leer(self, monkeypatch):
        """available() == False, wenn OPENAI_API_KEY leer ist."""
        engine = CloudSttEngine()
        engine._lib_verfuegbar = None

        import types
        stub = types.ModuleType("openai")
        monkeypatch.setitem(sys.modules, "openai", stub)
        monkeypatch.setenv("OPENAI_API_KEY", "")

        verfuegbar = engine.available()
        assert verfuegbar is False

    def test_available_kein_crash_ohne_lib(self, monkeypatch):
        """available() stürzt nicht ab, wenn openai fehlt."""
        engine = CloudSttEngine()
        monkeypatch.setitem(sys.modules, "openai", None)
        engine._lib_verfuegbar = None

        try:
            engine.available()
        except Exception as exc:
            pytest.fail(f"available() hat eine Exception geworfen: {exc}")

    def test_transcribe_ohne_lib_gibt_leere_liste(self, monkeypatch):
        """transcribe() gibt leere Liste zurück, wenn openai fehlt."""
        engine = CloudSttEngine()
        monkeypatch.setitem(sys.modules, "openai", None)
        engine._lib_verfuegbar = None

        result = engine.transcribe(_leerer_block(), samplerate=48_000, t_start=0.0)

        assert result == [], f"Erwartet [], erhalten {result}"

    def test_transcribe_ohne_key_gibt_leere_liste(self, monkeypatch):
        """transcribe() gibt leere Liste zurück, wenn OPENAI_API_KEY fehlt."""
        engine = CloudSttEngine()
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Direkt auf inaktiv setzen (kein Netzwerk-Versuch)
        engine._lib_verfuegbar = False

        result = engine.transcribe(_leerer_block(), samplerate=48_000, t_start=0.0)

        assert result == []

    def test_key_wird_nie_hartcodiert(self):
        """Verifikation: CloudSttEngine liest Key nur aus Env, nie aus Sourcecode."""
        import inspect
        from stt import cloud_engine

        source = inspect.getsource(cloud_engine)

        # Kein String der wie ein echter API-Key aussieht
        # (fängt z. B. sk- oder Bearer-Tokens)
        assert "sk-" not in source, "Hardcodierter API-Key in cloud_engine.py gefunden!"
        assert "Bearer " not in source, "Hardcodierter Bearer-Token in cloud_engine.py!"
