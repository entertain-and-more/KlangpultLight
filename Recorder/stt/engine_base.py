"""stt.engine_base — Abstrakte Basisklasse für STT-Engines.

Keine GUI-Importe. Keine optionalen Abhängigkeiten.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np

from stt.transcript_models import TranscriptChunk


class LiveSttEngine(ABC):
    """Abstrakte Schnittstelle für eine Live-STT-Engine.

    Jede konkrete Implementierung (lokal, Cloud, Mock) erbt von dieser Klasse
    und implementiert die Methoden :py:meth:`transcribe`, :py:meth:`available`
    sowie die :py:attr:`name`-Eigenschaft.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Maschinenlesbarer Name der Engine (z. B. ``"local"`` oder ``"cloud"``)."""

    @abstractmethod
    def available(self) -> bool:
        """Gibt zurück, ob diese Engine einsatzbereit ist.

        Prüft beim ersten Aufruf lazy, ob die erforderliche Bibliothek
        und/oder ein API-Schlüssel vorhanden sind.

        Returns:
            True wenn einsatzbereit, False sonst (kein Crash).
        """

    @abstractmethod
    def transcribe(
        self,
        audio: np.ndarray,
        samplerate: int,
        t_start: float,
    ) -> list[TranscriptChunk]:
        """Transkribiert einen Audioblock.

        Wird im Worker-Thread des :class:`~stt.stt_manager.SttManager` aufgerufen.
        Darf I/O oder Netzwerk blockieren — der Aufruf-Thread ist dafür gedacht.
        Darf NIEMALS die GUI aufrufen.

        Args:
            audio:      Mono-Audioblock als ``float32``-Array, Shape ``(N,)`` oder ``(N, 1)``.
            samplerate: Samplerate in Hz.
            t_start:    Startzeit des Blocks in Sekunden (relativ zur Aufnahme).

        Returns:
            Liste von :class:`~stt.transcript_models.TranscriptChunk`-Objekten
            (kann leer sein, wenn kein Text erkannt wurde).
        """
