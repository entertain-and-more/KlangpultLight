"""Tests für stt.stt_manager.select_engine — Engine-Auswahllogik.

Headless, kein echtes Modell, kein Netzwerk.
"""
import pytest
import numpy as np

from stt.mock_engine import MockSttEngine
from stt.engine_base import LiveSttEngine
from stt.transcript_models import TranscriptChunk
from stt.stt_manager import select_engine


# ---------------------------------------------------------------------------
# Hilfs-Stubs
# ---------------------------------------------------------------------------


class VerfuegbareEngine(LiveSttEngine):
    """Stub-Engine, die immer available() == True meldet."""

    def __init__(self, engine_name: str) -> None:
        self._name = engine_name

    @property
    def name(self) -> str:
        return self._name

    def available(self) -> bool:
        return True

    def transcribe(self, audio: np.ndarray, samplerate: int, t_start: float) -> list[TranscriptChunk]:
        return []


class NichtVerfuegbareEngine(LiveSttEngine):
    """Stub-Engine, die immer available() == False meldet."""

    def __init__(self, engine_name: str) -> None:
        self._name = engine_name

    @property
    def name(self) -> str:
        return self._name

    def available(self) -> bool:
        return False

    def transcribe(self, audio: np.ndarray, samplerate: int, t_start: float) -> list[TranscriptChunk]:
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSelectEngine:
    """Auswahllogik-Tests für select_engine."""

    def test_prefer_cloud_cloud_verfuegbar(self):
        """prefer='cloud' + Cloud verfügbar → Cloud wird gewählt."""
        local = VerfuegbareEngine("local")
        cloud = VerfuegbareEngine("cloud")

        gewählt = select_engine(prefer="cloud", local=local, cloud=cloud)

        assert gewählt is cloud

    def test_prefer_cloud_cloud_nicht_verfuegbar_lokal_verfuegbar(self):
        """prefer='cloud' + Cloud nicht verfügbar + Lokal verfügbar → Lokal."""
        local = VerfuegbareEngine("local")
        cloud = NichtVerfuegbareEngine("cloud")

        gewählt = select_engine(prefer="cloud", local=local, cloud=cloud)

        assert gewählt is local

    def test_prefer_cloud_keiner_verfuegbar_mit_mock(self):
        """prefer='cloud' + weder Cloud noch Lokal + Mock → Mock wird gewählt."""
        local = NichtVerfuegbareEngine("local")
        cloud = NichtVerfuegbareEngine("cloud")
        mock = MockSttEngine()

        gewählt = select_engine(prefer="cloud", local=local, cloud=cloud, mock=mock)

        assert gewählt is mock

    def test_prefer_cloud_keiner_verfuegbar_ohne_mock(self):
        """prefer='cloud' + nichts verfügbar + kein Mock → lokal (inaktiv) zurückgeben."""
        local = NichtVerfuegbareEngine("local")
        cloud = NichtVerfuegbareEngine("cloud")

        gewählt = select_engine(prefer="cloud", local=local, cloud=cloud)

        # Kein Crash; lokal wird als inaktive Instanz zurückgegeben
        assert gewählt is local

    def test_prefer_local_lokal_verfuegbar(self):
        """prefer='local' + Lokal verfügbar → Lokal wird gewählt."""
        local = VerfuegbareEngine("local")
        cloud = VerfuegbareEngine("cloud")  # würde nie gewählt

        gewählt = select_engine(prefer="local", local=local, cloud=cloud)

        assert gewählt is local

    def test_prefer_local_lokal_nicht_verfuegbar_mit_mock(self):
        """prefer='local' + Lokal nicht verfügbar + Mock → Mock."""
        local = NichtVerfuegbareEngine("local")
        cloud = VerfuegbareEngine("cloud")
        mock = MockSttEngine()

        gewählt = select_engine(prefer="local", local=local, cloud=cloud, mock=mock)

        assert gewählt is mock

    def test_prefer_local_keiner_verfuegbar_kein_mock(self):
        """prefer='local' + nichts verfügbar + kein Mock → lokal (inaktiv)."""
        local = NichtVerfuegbareEngine("local")
        cloud = NichtVerfuegbareEngine("cloud")

        gewählt = select_engine(prefer="local", local=local, cloud=cloud)

        assert gewählt is local
        # Kein Crash
        assert isinstance(gewählt, LiveSttEngine)

    def test_default_prefer_lokal_wenn_cloud_nicht_verfuegbar(self):
        """Default (kein prefer='cloud') → lokal bevorzugt, auch wenn Cloud verfügbar."""
        local = VerfuegbareEngine("local")
        cloud = VerfuegbareEngine("cloud")

        # prefer="local" ist der Standardmodus
        gewählt = select_engine(prefer="local", local=local, cloud=cloud)

        assert gewählt is local

    def test_gibt_nie_none_zurueck(self):
        """select_engine darf niemals None zurückgeben."""
        local = NichtVerfuegbareEngine("local")
        cloud = NichtVerfuegbareEngine("cloud")

        gewählt = select_engine(prefer="cloud", local=local, cloud=cloud)

        assert gewählt is not None
