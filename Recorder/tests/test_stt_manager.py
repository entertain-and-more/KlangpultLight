"""Tests für stt.stt_manager.SttManager.

Headless, kein echtes Modell, kein Netzwerk.
Prüft: feed() → Fenster-Akkumulation → on_chunk-Feuern, sauberer Stop.
"""
import threading
import time

import numpy as np

from stt.mock_engine import MockSttEngine
from stt.stt_manager import SttManager
from stt.transcript_models import TranscriptChunk


# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------


def _sinus_block(samples: int, samplerate: int = 48_000) -> np.ndarray:
    """Erzeugt einen kurzen Sinus-Block (float32, Mono)."""
    t = np.linspace(0, samples / samplerate, samples, endpoint=False)
    return (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSttManager:
    """SttManager-Tests."""

    def test_feed_genug_audio_feuert_on_chunk(self):
        """feed() mit genug Samples → on_chunk wird mit TranscriptChunk aufgerufen."""
        samplerate = 48_000
        window_seconds = 0.1  # kurzes Fenster für schnellen Test
        engine = MockSttEngine()
        empfangene: list[TranscriptChunk] = []
        chunk_event = threading.Event()

        def on_chunk(chunk: TranscriptChunk) -> None:
            empfangene.append(chunk)
            chunk_event.set()

        manager = SttManager(
            engine=engine,
            on_chunk=on_chunk,
            samplerate=samplerate,
            window_seconds=window_seconds,
        )
        manager.start()

        # Fenster-Größe in Samples + etwas Reserve
        fenster_samples = int(samplerate * window_seconds)
        block = _sinus_block(fenster_samples + 512, samplerate)
        manager.feed(block)

        # Warten bis on_chunk gefeuert wurde (max. 3 Sekunden)
        ausgeloest = chunk_event.wait(timeout=3.0)
        manager.stop()

        assert ausgeloest, "on_chunk wurde nicht innerhalb von 3 Sekunden aufgerufen"
        assert len(empfangene) >= 1
        assert isinstance(empfangene[0], TranscriptChunk)
        assert empfangene[0].text.startswith("Segment")

    def test_feed_zu_wenig_audio_kein_on_chunk(self):
        """feed() mit zu wenig Samples → on_chunk darf NICHT aufgerufen werden."""
        samplerate = 48_000
        window_seconds = 4.0  # langes Fenster
        engine = MockSttEngine()
        empfangene: list[TranscriptChunk] = []

        manager = SttManager(
            engine=engine,
            on_chunk=empfangene.append,
            samplerate=samplerate,
            window_seconds=window_seconds,
        )
        manager.start()

        # Viel zu kurzer Block (z. B. 100 ms)
        kleiner_block = _sinus_block(int(samplerate * 0.1), samplerate)
        manager.feed(kleiner_block)

        # Kurz warten — on_chunk sollte nicht ausgelöst worden sein
        time.sleep(0.3)
        manager.stop()

        assert len(empfangene) == 0, "on_chunk sollte bei zu kurzem Audio nicht gefeuert werden"

    def test_mehrere_feeds_akkumulieren_zu_einem_fenster(self):
        """Mehrere kleine feeds() ergeben zusammen ein Fenster → on_chunk einmal gefeuert."""
        samplerate = 48_000
        window_seconds = 0.1
        engine = MockSttEngine()
        empfangene: list[TranscriptChunk] = []
        chunk_event = threading.Event()

        def on_chunk(chunk: TranscriptChunk) -> None:
            empfangene.append(chunk)
            chunk_event.set()

        manager = SttManager(
            engine=engine,
            on_chunk=on_chunk,
            samplerate=samplerate,
            window_seconds=window_seconds,
        )
        manager.start()

        fenster_samples = int(samplerate * window_seconds)
        block_groesse = 256
        zugeführt = 0

        while zugeführt < fenster_samples + block_groesse:
            manager.feed(_sinus_block(block_groesse, samplerate))
            zugeführt += block_groesse

        ausgeloest = chunk_event.wait(timeout=3.0)
        manager.stop()

        assert ausgeloest, "on_chunk wurde bei akkumulierten Blöcken nicht aufgerufen"
        assert len(empfangene) >= 1

    def test_stop_kein_orphan_thread(self):
        """stop() beendet den Worker-Thread sauber (kein Orphan)."""
        engine = MockSttEngine()
        manager = SttManager(
            engine=engine,
            on_chunk=lambda _: None,
            samplerate=48_000,
            window_seconds=4.0,
        )
        manager.start()

        thread = manager._worker_thread
        assert thread is not None
        assert thread.is_alive()

        manager.stop()

        # Thread muss beendet sein
        assert not thread.is_alive(), "SttWorker-Thread läuft noch nach stop()"
        assert manager._worker_thread is None

    def test_feed_stereo_block_wird_zu_mono_konvertiert(self):
        """feed() mit Stereo-Block → kein Crash, Mono-Konvertierung intern."""
        samplerate = 48_000
        window_seconds = 0.1
        engine = MockSttEngine()
        chunk_event = threading.Event()

        def on_chunk(chunk: TranscriptChunk) -> None:
            chunk_event.set()

        manager = SttManager(
            engine=engine,
            on_chunk=on_chunk,
            samplerate=samplerate,
            window_seconds=window_seconds,
        )
        manager.start()

        fenster_samples = int(samplerate * window_seconds)
        # Stereo-Block (N, 2)
        stereo = np.zeros((fenster_samples + 512, 2), dtype=np.float32)
        manager.feed(stereo)

        ausgeloest = chunk_event.wait(timeout=3.0)
        manager.stop()

        assert ausgeloest, "Stereo-Block hat keinen Chunk ausgelöst"

    def test_chunk_engine_name_korrekt(self):
        """TranscriptChunk.engine entspricht dem Mock-Engine-Namen."""
        samplerate = 48_000
        window_seconds = 0.1
        engine = MockSttEngine()
        empfangene: list[TranscriptChunk] = []
        chunk_event = threading.Event()

        def on_chunk(chunk: TranscriptChunk) -> None:
            empfangene.append(chunk)
            chunk_event.set()

        manager = SttManager(
            engine=engine,
            on_chunk=on_chunk,
            samplerate=samplerate,
            window_seconds=window_seconds,
        )
        manager.start()

        fenster_samples = int(samplerate * window_seconds)
        manager.feed(_sinus_block(fenster_samples + 512, samplerate))
        chunk_event.wait(timeout=3.0)
        manager.stop()

        assert len(empfangene) >= 1
        assert empfangene[0].engine == "mock"

    def test_t_start_wird_weitergegeben(self):
        """t_start im ersten Chunk ist >= 0 und plausibel."""
        samplerate = 48_000
        window_seconds = 0.1
        engine = MockSttEngine()
        empfangene: list[TranscriptChunk] = []
        chunk_event = threading.Event()

        def on_chunk(chunk: TranscriptChunk) -> None:
            empfangene.append(chunk)
            chunk_event.set()

        manager = SttManager(
            engine=engine,
            on_chunk=on_chunk,
            samplerate=samplerate,
            window_seconds=window_seconds,
        )
        manager.start()

        fenster_samples = int(samplerate * window_seconds)
        manager.feed(_sinus_block(fenster_samples + 512, samplerate))
        chunk_event.wait(timeout=3.0)
        manager.stop()

        assert len(empfangene) >= 1
        assert empfangene[0].t_start >= 0.0
