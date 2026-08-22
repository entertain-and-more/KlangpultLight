"""tests.test_mix_alignment — MixWorker bleibt ausgerichtet wenn ein Kanal kurz fehlt.

TDD Task 3c. Headless, kein Hardware-Zugriff.

Belegt:
  - Fehlt in einem Kanal kurz ein Block → Mix befüllt diesen Slot mit Zeros,
    kein Crash und kein Hänger.
  - Das Ergebnis bleibt eine gültige WAV mit Dauer > 0.
  - Kein verwaister MixWorker-Thread nach stop().

Die synchronen Tests laufen OHNE Hintergrund-Threads, um Race Conditions zu
vermeiden (gleiche Strategie wie test_mix_loop.py).
"""
import os
import time

import numpy as np
import soundfile as sf



# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _engine_direkt(tmp_path):
    """Baut Engine ohne Hintergrund-Threads (für synchrone Ausrichtungs-Tests)."""
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    channels = [
        MixerChannel(source_id="kanal_a", name="Kanal A"),
        MixerChannel(source_id="kanal_b", name="Kanal B"),
    ]
    cfg = AppConfig(mock_audio=False, workspace_dir=str(tmp_path))
    engine = AudioEngine(config=cfg, channels=channels)
    return engine, cfg


def _starte_aufnahme_direkt(engine, aufnahme_dir: str):
    """Öffnet Recorder ohne engine.start() (Hintergrund-Threads bleiben aus)."""
    import os as _os
    from audio.wav_recorder import WavRecorder

    _os.makedirs(aufnahme_dir, exist_ok=True)
    engine._aufnahme_dir = aufnahme_dir

    sr = engine._config.samplerate
    ch = engine._config.channels

    engine._mix_recorder = WavRecorder(samplerate=sr, channels=ch)
    engine._mix_recorder.open(_os.path.join(aufnahme_dir, "mix.wav"))

    engine._kanal_recorder = {}
    for kanal in engine._channels:
        rec = WavRecorder(samplerate=sr, channels=ch)
        rec.open(_os.path.join(aufnahme_dir, f"{kanal.source_id}.wav"))
        engine._kanal_recorder[kanal.source_id] = rec

    engine._recording = True


def _stoppe_aufnahme_direkt(engine):
    """Schließt Recorder ohne engine.stop()."""
    engine._recording = False
    if engine._mix_recorder is not None:
        engine._mix_recorder.close()
        engine._mix_recorder = None
    for rec in engine._kanal_recorder.values():
        rec.close()
    engine._kanal_recorder = {}


# ---------------------------------------------------------------------------
# Test 1: Zeros-Slot wenn Kanal leer
# ---------------------------------------------------------------------------

def test_zeros_slot_wenn_kanal_leer(tmp_path):
    """Wenn Kanal B keinen Block bereitstellt, füllt MixWorker mit Zeros auf.

    Kein Crash, kein Hänger; mix.wav enthält gültige Samples.
    Synchroner Test via _mix_one_tick().
    """
    engine, cfg = _engine_direkt(tmp_path)

    aufnahme_dir = str(tmp_path / "aufnahme_align")
    _starte_aufnahme_direkt(engine, aufnahme_dir)

    block_size = cfg.block_size
    audio_ch = cfg.channels
    n = 5

    for _ in range(n):
        # Nur Kanal A hat Daten; Kanal B ist leer
        engine._kanal_puffer["kanal_a"].append(
            np.full((block_size, audio_ch), 0.5, dtype=np.float32)
        )
        # _mix_one_tick() soll für Kanal B Zeros verwenden
        engine._mix_one_tick()

    _stoppe_aufnahme_direkt(engine)

    mix_pfad = os.path.join(aufnahme_dir, "mix.wav")
    assert os.path.exists(mix_pfad), f"mix.wav fehlt: {mix_pfad}"

    data_mix, _ = sf.read(mix_pfad, dtype="float32")
    assert data_mix.size > 0, "mix.wav ist leer"
    # Mix ≈ 0.5 (Kanal A) + 0.0 (Kanal B Zeros) = 0.5
    assert np.allclose(data_mix, 0.5, atol=1e-3), (
        f"Zeros-Slot: Mix sollte ≈ 0.5, tatsächlich: "
        f"min={data_mix.min():.4f} max={data_mix.max():.4f}"
    )


# ---------------------------------------------------------------------------
# Test 2: Ungleichmäßige Puffer ohne Crash
# ---------------------------------------------------------------------------

def test_alignment_mix_ohne_crash_nach_fehlenden_blocks(tmp_path):
    """MixWorker läuft durch mehrere ungleichmäßige Puffer ohne Absturz.

    Abwechselnd: 1 Block in A, dann nichts, dann 2 in B, …
    Keine Exception, WAV am Ende vorhanden.
    """
    engine, cfg = _engine_direkt(tmp_path)

    aufnahme_dir = str(tmp_path / "aufnahme_ungleich")
    _starte_aufnahme_direkt(engine, aufnahme_dir)

    block_size = cfg.block_size
    audio_ch = cfg.channels

    block_a = np.full((block_size, audio_ch), 0.4, dtype=np.float32)
    block_b = np.full((block_size, audio_ch), 0.2, dtype=np.float32)

    # Tick 1: nur A (B leer → Zeros)
    engine._kanal_puffer["kanal_a"].append(block_a.copy())
    engine._mix_one_tick()

    # Tick 2: nur B (A leer → Zeros)
    engine._kanal_puffer["kanal_b"].append(block_b.copy())
    engine._mix_one_tick()

    # Tick 3: beide
    engine._kanal_puffer["kanal_a"].append(block_a.copy())
    engine._kanal_puffer["kanal_b"].append(block_b.copy())
    engine._mix_one_tick()

    # Tick 4: keiner (idle → kein Write, kein Frame)
    engine._mix_one_tick()

    _stoppe_aufnahme_direkt(engine)

    mix_pfad = os.path.join(aufnahme_dir, "mix.wav")
    assert os.path.exists(mix_pfad), f"mix.wav fehlt: {mix_pfad}"

    data_mix, _ = sf.read(mix_pfad, dtype="float32")
    # 3 Ticks mit Daten, Tick 4 = idle (alle leer → kein Write)
    assert data_mix.shape[0] == 3 * block_size, (
        f"Erwartet {3 * block_size} Frames, tatsächlich {data_mix.shape[0]}"
    )


# ---------------------------------------------------------------------------
# Test 3: Keine verwaisten Threads
# ---------------------------------------------------------------------------

def test_keine_verwaisten_threads(tmp_path):
    """Kein verwaister Thread nach stop().

    Prüft, dass der MixWorker sauber mit join(timeout) beendet wird.
    """
    import threading
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    channels = [
        MixerChannel(source_id="kanal_a", name="Kanal A"),
        MixerChannel(source_id="kanal_b", name="Kanal B"),
    ]
    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    engine = AudioEngine(config=cfg, channels=channels)

    engine.start()

    # Mindestens ein MixWorker-Thread muss existieren
    threads_waehrend = {t.name for t in threading.enumerate()}
    assert any("MixWorker" in n for n in threads_waehrend), (
        "Kein MixWorker-Thread nach start() gefunden"
    )

    engine.stop()

    # Kurz warten auf join
    time.sleep(0.05)
    threads_nachher = {t.name for t in threading.enumerate()}
    verwaist = {n for n in threads_nachher if "MixWorker" in n}
    assert not verwaist, f"Verwaiste MixWorker-Threads nach stop(): {verwaist}"
