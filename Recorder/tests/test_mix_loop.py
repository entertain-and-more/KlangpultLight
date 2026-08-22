"""tests.test_mix_loop — Kernnachweis: zentraler MixWorker summiert Kanäle korrekt.

TDD Task 3c. Headless, kein Hardware-Zugriff.

Belegt:
  - Zwei Kanäle mit konstantem Signal A=0.5 und B=0.3 → summierte mix.wav ≈ 0.8
  - Pro-Kanal-WAVs enthalten A=0.5 bzw. B=0.3
  - Solo: nur der Solo-Kanal landet im Mix
  - Mix-Worker ist identisch im Mock- und Echtbetrieb (Korrektheit headless testbar)

Testmuster für deterministische Wert-Tests:
  Die synchronen Tests umgehen die Hintergrund-Threads (Mock + MixWorker)
  und rufen _mix_one_tick() direkt auf. So gibt es keine Race Conditions mit
  dem Mock-Synth-Thread. Die start()/stop()-Lifecycle-Tests belegen separat,
  dass die Mix-WAV Frames > 0 enthält.
"""
import os
import time

import numpy as np
import soundfile as sf



# ---------------------------------------------------------------------------
# Hilfsfunktionen
# ---------------------------------------------------------------------------

def _engine_direkt(tmp_path, channels=None):
    """Baut Engine OHNE Hintergrund-Threads (für synchrone Wert-Tests).

    Öffnet nur Recorder-State; kein start()/stop() nötig.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    if channels is None:
        channels = [
            MixerChannel(source_id="kanal_a", name="Kanal A"),
            MixerChannel(source_id="kanal_b", name="Kanal B"),
        ]
    # mock_audio=False → kein Mock-Thread; aber wir starten gar nicht via start()
    cfg = AppConfig(mock_audio=False, workspace_dir=str(tmp_path))
    engine = AudioEngine(config=cfg, channels=channels)
    return engine, cfg


def _starte_aufnahme_direkt(engine, aufnahme_dir: str):
    """Öffnet Recorder ohne engine.start() (Hintergrund-Threads bleiben aus)."""
    import os as _os
    _os.makedirs(aufnahme_dir, exist_ok=True)
    engine._aufnahme_dir = aufnahme_dir

    sr = engine._config.samplerate
    ch = engine._config.channels

    from audio.wav_recorder import WavRecorder

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


def _engine_mit_zwei_kanaelen(tmp_path):
    """Baut Engine mit zwei Kanälen im Mock-Modus (für Lifecycle-Tests)."""
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    channels = [
        MixerChannel(source_id="kanal_a", name="Kanal A"),
        MixerChannel(source_id="kanal_b", name="Kanal B"),
    ]
    cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    engine = AudioEngine(config=cfg, channels=channels)
    return engine, channels, cfg


class _LockProbeRecorder:
    """Minimaler Recorder-Dummy, der den Lock-Zustand beim write() mitschreibt."""

    def __init__(self, engine):
        self._engine = engine
        self.lock_states: list[bool] = []

    def write(self, block) -> None:
        self.lock_states.append(self._engine._aufnahme_lock.locked())

    def close(self) -> float:
        return 0.0


# ---------------------------------------------------------------------------
# Test 1: Mix-Korrektheit synchron (Kern-Anforderung aus Task 3c)
# ---------------------------------------------------------------------------

def test_mix_loop_synchron(tmp_path):
    """Synchroner Nachweis: konstante Blöcke (A=0.5, B=0.3) → Mix ≈ 0.8.

    Ruft _mix_one_tick() direkt auf (kein Thread-Timing, keine Race Condition).
    Pro-Kanal-WAV und mix.wav werden verglichen.
    PCM_16-Rundungseffekt: atol=1e-3.
    """
    engine, cfg = _engine_direkt(tmp_path)

    aufnahme_dir = str(tmp_path / "aufnahme_sync")
    _starte_aufnahme_direkt(engine, aufnahme_dir)

    block_size = cfg.block_size
    ch = cfg.channels
    val_a, val_b = 0.5, 0.3
    n = 5

    for _ in range(n):
        engine._kanal_puffer["kanal_a"].append(
            np.full((block_size, ch), val_a, dtype=np.float32)
        )
        engine._kanal_puffer["kanal_b"].append(
            np.full((block_size, ch), val_b, dtype=np.float32)
        )
        engine._mix_one_tick()

    _stoppe_aufnahme_direkt(engine)

    # mix.wav prüfen: Samples ≈ 0.8 (= 0.5 + 0.3, kein Clipping nötig)
    mix_pfad = os.path.join(aufnahme_dir, "mix.wav")
    data_mix, _ = sf.read(mix_pfad, dtype="float32")
    assert data_mix.size > 0, "mix.wav ist leer"
    assert np.allclose(data_mix, 0.8, atol=1e-3), (
        f"Erwarteter Mix-Wert ≈ 0.8, tatsächlich: min={data_mix.min():.4f} max={data_mix.max():.4f}"
    )

    # Kanal-A-WAV: ≈ 0.5
    wav_a = os.path.join(aufnahme_dir, "kanal_a.wav")
    data_a, _ = sf.read(wav_a, dtype="float32")
    assert data_a.size > 0, "kanal_a.wav ist leer"
    assert np.allclose(data_a, val_a, atol=1e-3), (
        f"Kanal-A: erwartet ≈ {val_a}, tatsächlich: max={data_a.max():.4f}"
    )

    # Kanal-B-WAV: ≈ 0.3
    wav_b = os.path.join(aufnahme_dir, "kanal_b.wav")
    data_b, _ = sf.read(wav_b, dtype="float32")
    assert data_b.size > 0, "kanal_b.wav ist leer"
    assert np.allclose(data_b, val_b, atol=1e-3), (
        f"Kanal-B: erwartet ≈ {val_b}, tatsächlich: max={data_b.max():.4f}"
    )


def test_mix_frame_count(tmp_path):
    """n synchrone Ticks → genau n * block_size Frames in mix.wav."""
    engine, cfg = _engine_direkt(tmp_path)
    aufnahme_dir = str(tmp_path / "aufnahme_frames")
    _starte_aufnahme_direkt(engine, aufnahme_dir)

    block_size = cfg.block_size
    ch = cfg.channels
    n = 3

    for _ in range(n):
        engine._kanal_puffer["kanal_a"].append(
            np.full((block_size, ch), 0.5, dtype=np.float32)
        )
        engine._kanal_puffer["kanal_b"].append(
            np.full((block_size, ch), 0.3, dtype=np.float32)
        )
        engine._mix_one_tick()

    _stoppe_aufnahme_direkt(engine)

    mix_pfad = os.path.join(aufnahme_dir, "mix.wav")
    data_mix, _ = sf.read(mix_pfad, dtype="float32")
    assert data_mix.shape[0] == n * block_size, (
        f"Erwartet {n * block_size} Frames, tatsächlich {data_mix.shape[0]}"
    )


# ---------------------------------------------------------------------------
# Test 2: Lifecycle — start/stop liefert mix.wav mit Frames > 0
# ---------------------------------------------------------------------------

def test_mix_summe_lifecycle(tmp_path):
    """Lifecycle-Test: start() + start_recording() + stop_recording() + stop().

    Belegt, dass der MixWorker im Hintergrund läuft und mix.wav Frames enthält.
    """
    engine, channels, cfg = _engine_mit_zwei_kanaelen(tmp_path)
    engine.start()

    aufnahme_dir = str(tmp_path / "aufnahme_lifecycle")
    engine.start_recording(aufnahme_dir)
    time.sleep(0.2)  # Mock-Thread + MixWorker produzieren Frames
    ergebnis = engine.stop_recording()
    engine.stop()

    assert ergebnis["duration"] > 0.0, "mix.wav hat keine Dauer"

    mix_pfad = os.path.join(aufnahme_dir, "mix.wav")
    assert os.path.exists(mix_pfad), f"mix.wav fehlt: {mix_pfad}"

    data, _ = sf.read(mix_pfad, dtype="float32")
    assert data.size > 0, "mix.wav ist leer"
    assert np.max(np.abs(data)) > 0.0, "mix.wav enthält nur Nullen"


# ---------------------------------------------------------------------------
# Test 3: Solo — nur Solo-Kanal landet im Mix
# ---------------------------------------------------------------------------

def test_solo_kanal_nur_a_im_mix(tmp_path):
    """Wenn Kanal A solo=True, darf Kanal B NICHT im Mix erscheinen.

    Synchroner Test via _mix_one_tick().
    """
    from audio.mixer_channel import MixerChannel

    ch_a = MixerChannel(source_id="kanal_a", name="Kanal A", solo=True)
    ch_b = MixerChannel(source_id="kanal_b", name="Kanal B")
    engine, cfg = _engine_direkt(tmp_path, channels=[ch_a, ch_b])

    aufnahme_dir = str(tmp_path / "aufnahme_solo")
    _starte_aufnahme_direkt(engine, aufnahme_dir)

    block_size = cfg.block_size
    audio_ch = cfg.channels
    val_a, val_b = 0.5, 0.3
    n = 5

    for _ in range(n):
        engine._kanal_puffer["kanal_a"].append(
            np.full((block_size, audio_ch), val_a, dtype=np.float32)
        )
        engine._kanal_puffer["kanal_b"].append(
            np.full((block_size, audio_ch), val_b, dtype=np.float32)
        )
        engine._mix_one_tick()

    _stoppe_aufnahme_direkt(engine)

    mix_pfad = os.path.join(aufnahme_dir, "mix.wav")
    data_mix, _ = sf.read(mix_pfad, dtype="float32")
    assert data_mix.size > 0, "mix.wav ist leer"

    # Mix ≈ 0.5 (nur Kanal A, Kanal B stummgeschaltet durch Solo-Logik)
    assert np.allclose(data_mix, val_a, atol=1e-3), (
        f"Solo-Test: Mix sollte ≈ {val_a} (nur A), tatsächlich: "
        f"min={data_mix.min():.4f} max={data_mix.max():.4f}"
    )


# ---------------------------------------------------------------------------
# Test 4: Clipping — Summe > 1.0 wird auf 1.0 begrenzt
# ---------------------------------------------------------------------------

def test_clipping_bei_uebersteuerung(tmp_path):
    """Summe 0.8 + 0.8 = 1.6 → Clipping auf 1.0."""
    engine, cfg = _engine_direkt(tmp_path)

    aufnahme_dir = str(tmp_path / "aufnahme_clip")
    _starte_aufnahme_direkt(engine, aufnahme_dir)

    block_size = cfg.block_size
    audio_ch = cfg.channels

    for _ in range(5):
        engine._kanal_puffer["kanal_a"].append(
            np.full((block_size, audio_ch), 0.8, dtype=np.float32)
        )
        engine._kanal_puffer["kanal_b"].append(
            np.full((block_size, audio_ch), 0.8, dtype=np.float32)
        )
        engine._mix_one_tick()

    _stoppe_aufnahme_direkt(engine)

    mix_pfad = os.path.join(aufnahme_dir, "mix.wav")
    data_mix, _ = sf.read(mix_pfad, dtype="float32")
    assert data_mix.size > 0, "mix.wav ist leer"
    assert np.max(data_mix) <= 1.0 + 1e-4, (
        f"Clipping fehlt: max={np.max(data_mix):.4f} > 1.0"
    )
    # Wert muss nah an 1.0 liegen (nicht 0 wegen Rounding)
    assert np.max(data_mix) > 0.9, "Nach Clipping: Wert sollte ≈ 1.0 sein"


def test_wav_write_laueft_nicht_unter_aufnahme_lock(tmp_path):
    """Disk-I/O darf den Aufnahmezustandslock nicht halten.

    Reproduziert den Bugsweep-Befund: _mix_one_tick() soll Recorder.write()
    außerhalb von _aufnahme_lock ausführen, damit langsame Dateisysteme den
    Aufnahmezustand nicht unnötig blockieren.
    """
    engine, cfg = _engine_direkt(tmp_path)
    mix_probe = _LockProbeRecorder(engine)
    kanal_a_probe = _LockProbeRecorder(engine)
    kanal_b_probe = _LockProbeRecorder(engine)

    engine._mix_recorder = mix_probe
    engine._kanal_recorder = {
        "kanal_a": kanal_a_probe,
        "kanal_b": kanal_b_probe,
    }
    engine._recording = True

    block_size = cfg.block_size
    audio_ch = cfg.channels
    engine._kanal_puffer["kanal_a"].append(
        np.full((block_size, audio_ch), 0.4, dtype=np.float32)
    )
    engine._kanal_puffer["kanal_b"].append(
        np.full((block_size, audio_ch), 0.2, dtype=np.float32)
    )

    engine._mix_one_tick()

    assert mix_probe.lock_states == [False]
    assert kanal_a_probe.lock_states == [False]
    assert kanal_b_probe.lock_states == [False]
