"""stt — Live-STT-Modul für den PodcastRecorder.

Exportiert die wichtigsten Klassen und Hilfsfunktionen:

- :class:`~stt.transcript_models.TranscriptChunk` — Datenmodell
- :class:`~stt.engine_base.LiveSttEngine` — abstrakte Basisklasse
- :class:`~stt.mock_engine.MockSttEngine` — deterministischer Mock
- :class:`~stt.local_engine.LocalWhisperEngine` — lokal (faster-whisper, optional)
- :class:`~stt.cloud_engine.CloudSttEngine` — Cloud (openai, optional)
- :class:`~stt.stt_manager.SttManager` — Audio-Tap → Fenster → Engine → on_chunk
- :func:`~stt.stt_manager.select_engine` — Engine-Auswahllogik
"""
from stt.transcript_models import TranscriptChunk
from stt.engine_base import LiveSttEngine
from stt.mock_engine import MockSttEngine
from stt.local_engine import LocalWhisperEngine
from stt.cloud_engine import CloudSttEngine
from stt.stt_manager import SttManager, select_engine

__all__ = [
    "TranscriptChunk",
    "LiveSttEngine",
    "MockSttEngine",
    "LocalWhisperEngine",
    "CloudSttEngine",
    "SttManager",
    "select_engine",
]
