"""stt.mock_engine — Deterministischer Mock für Tests und Headless-Selftests.

Immer verfügbar. Liefert synthetische TranscriptChunks.
Keine echten Modelle, kein Netzwerk.
"""
from __future__ import annotations

import numpy as np

from stt.engine_base import LiveSttEngine
from stt.transcript_models import TranscriptChunk


class MockSttEngine(LiveSttEngine):
    """STT-Engine-Mock für Tests.

    Liefert deterministisch nummerierte Segmente der Form ``"Segment <n>"``.
    Zählt, wie oft :py:meth:`transcribe` aufgerufen wurde. Immer verfügbar.
    """

    def __init__(self) -> None:
        self._aufruf_zaehler: int = 0

    # -------------------------------------------------------------------------
    # LiveSttEngine-Interface
    # -------------------------------------------------------------------------

    @property
    def name(self) -> str:
        return "mock"

    def available(self) -> bool:
        return True

    def transcribe(
        self,
        audio: np.ndarray,
        samplerate: int,
        t_start: float,
    ) -> list[TranscriptChunk]:
        """Gibt einen deterministischen Chunk zurück.

        Args:
            audio:      Ignoriert (kein echtes Modell).
            samplerate: Ignoriert.
            t_start:    Wird 1:1 an den Chunk weitergegeben.

        Returns:
            Liste mit genau einem :class:`~stt.transcript_models.TranscriptChunk`.
        """
        self._aufruf_zaehler += 1
        return [
            TranscriptChunk(
                text=f"Segment {self._aufruf_zaehler}",
                is_final=True,
                t_start=t_start,
                engine=self.name,
            )
        ]

    # -------------------------------------------------------------------------
    # Test-Hilfsmethoden
    # -------------------------------------------------------------------------

    @property
    def aufruf_zaehler(self) -> int:
        """Anzahl bisheriger :py:meth:`transcribe`-Aufrufe (für Assertions in Tests)."""
        return self._aufruf_zaehler
