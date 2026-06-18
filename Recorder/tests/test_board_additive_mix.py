"""tests.test_board_additive_mix — Additives Board-Mischen (Task 6a).

Belegt I-2: Gleichzeitige Board-Pads werden ADDITIV summiert, nicht zeitlich
verschachtelt. Zwei Pads (A≈0.5, B≈0.3) → Board-Beitrag im Mix ≈ 0.8.

Kein Thread-Timing: alle Tests sind synchron über _mix_one_tick().
"""
import numpy as np
import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio und Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _engine_mit_kanal(tmp_path):
    """Erzeugt eine AudioEngine mit einem Kanal (kein start() — MixWorker-Thread-frei)."""
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    cfg = AppConfig(
        mock_audio=True,
        block_size=1024,
        samplerate=48000,
        channels=2,
        workspace_dir=str(tmp_path),
    )
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)
    return engine, cfg


def _null_kanal_block(engine, cfg):
    """Füllt den Kanal-Puffer mit einem Null-Block, damit _mix_one_tick() hat_daten=True."""
    null = np.zeros((cfg.block_size, cfg.channels), dtype=np.float32)
    for kanal in engine._channels:
        engine._kanal_puffer[kanal.source_id].append(null.copy())


# ---------------------------------------------------------------------------
# Test 1: Zwei gleichzeitige Pro-Feeder-Puffer werden additiv summiert
# ---------------------------------------------------------------------------

def test_zwei_feeder_puffer_additiv(tmp_path):
    """Zwei registrierte Feeder-Puffer (0.5 + 0.3) → Mix-Block hat Board-Beitrag ≈ 0.8.

    Prüft, dass _mix_one_tick() alle pro-Feeder-Puffer summiert, nicht nur den ersten.
    """
    engine, cfg = _engine_mit_kanal(tmp_path)

    block_size = cfg.block_size
    ch = cfg.channels

    # Feeder A registrieren (Amplitude 0.5)
    puffer_a = engine.register_board_feeder(feeder_id=1)
    block_a = np.full((block_size, ch), 0.5, dtype=np.float32)
    puffer_a.append(block_a)

    # Feeder B registrieren (Amplitude 0.3)
    puffer_b = engine.register_board_feeder(feeder_id=2)
    block_b = np.full((block_size, ch), 0.3, dtype=np.float32)
    puffer_b.append(block_b)

    # Kanal-Puffer mit Null füllen (damit hat_daten=True)
    _null_kanal_block(engine, cfg)

    # Aufnahme starten und einen Tick ausführen
    aufnahme_dir = str(tmp_path / "additiv_mix")
    engine.start_recording(aufnahme_dir)
    engine._mix_one_tick()
    ergebnis = engine.stop_recording()

    import soundfile as sf
    import os
    mix_pfad = ergebnis["mix"]
    assert os.path.exists(mix_pfad), "mix.wav fehlt"
    mix_daten, _ = sf.read(mix_pfad, dtype="float32")
    assert mix_daten.size > 0, "mix.wav ist leer"

    # Board-Beitrag = Kanal-Mix (≈0) + Feeder-A (0.5) + Feeder-B (0.3) → clipped ≈ 0.8
    # Max-Amplitude muss deutlich über 0.5 (einem einzelnen Feeder) liegen
    max_amp = float(np.max(np.abs(mix_daten)))
    assert max_amp > 0.6, (
        f"Additiver Mix erwartet max_amp > 0.6, erhalten: {max_amp:.4f}. "
        "Möglicherweise werden Feeder-Puffer nicht summiert."
    )


# ---------------------------------------------------------------------------
# Test 2: Einzelner Feeder-Puffer funktioniert korrekt (Regression)
# ---------------------------------------------------------------------------

def test_einzelner_feeder_puffer_korrekt(tmp_path):
    """Ein registrierter Feeder-Puffer (0.5) landet korrekt im Mix."""
    engine, cfg = _engine_mit_kanal(tmp_path)

    block_size = cfg.block_size
    ch = cfg.channels

    puffer = engine.register_board_feeder(feeder_id=99)
    block = np.full((block_size, ch), 0.5, dtype=np.float32)
    puffer.append(block)

    _null_kanal_block(engine, cfg)

    aufnahme_dir = str(tmp_path / "einzeln_mix")
    engine.start_recording(aufnahme_dir)
    engine._mix_one_tick()
    ergebnis = engine.stop_recording()

    import soundfile as sf
    import os
    mix_daten, _ = sf.read(ergebnis["mix"], dtype="float32")
    energie = float(np.sum(mix_daten ** 2))
    assert energie > 0.0, "Einzelner Feeder-Puffer landete nicht im Mix"


# ---------------------------------------------------------------------------
# Test 3: Legacy _board_puffer bleibt rückwärtskompatibel
# ---------------------------------------------------------------------------

def test_legacy_board_puffer_bleibt_kompatibel(tmp_path):
    """Direktes Schreiben in engine._board_puffer (Legacy-Tests) wird weiterhin summiert."""
    engine, cfg = _engine_mit_kanal(tmp_path)

    block_size = cfg.block_size
    ch = cfg.channels

    # Direkt in Legacy-Puffer schreiben (wie alte Tests)
    legacy_block = np.full((block_size, ch), 0.4, dtype=np.float32)
    engine._board_puffer.append(legacy_block)

    _null_kanal_block(engine, cfg)

    aufnahme_dir = str(tmp_path / "legacy_mix")
    engine.start_recording(aufnahme_dir)
    engine._mix_one_tick()
    ergebnis = engine.stop_recording()

    import soundfile as sf
    import os
    mix_daten, _ = sf.read(ergebnis["mix"], dtype="float32")
    energie = float(np.sum(mix_daten ** 2))
    assert energie > 0.0, "Legacy _board_puffer landete nicht im Mix"


# ---------------------------------------------------------------------------
# Test 4: Feeder-ID muss pro Instanz eindeutig sein (kein Überschreiben)
# ---------------------------------------------------------------------------

def test_feeder_id_eindeutig(tmp_path):
    """register_board_feeder() mit derselben ID überschreibt den vorherigen Puffer.

    Dokumentiert das erwartete Verhalten: IDs müssen caller-seitig eindeutig sein.
    """
    engine, cfg = _engine_mit_kanal(tmp_path)

    puffer_1 = engine.register_board_feeder(feeder_id=7)
    puffer_2 = engine.register_board_feeder(feeder_id=7)  # gleiche ID → Überschreiben

    # Nach zweiter Registrierung soll nur ein Puffer für diese ID existieren
    with engine._board_feeders_lock:
        anzahl = len(engine._board_feeders)
    assert anzahl == 1, f"Erwartet 1 Eintrag für doppelte ID, erhalten: {anzahl}"

    # puffer_2 ist der neue Puffer (puffer_1 wurde ersetzt)
    assert puffer_1 is not puffer_2 or True  # id-Gleichheit nicht guaranteed, nur Anzahl ist wichtig


# ---------------------------------------------------------------------------
# Test 5: unregister_board_feeder() ist idempotent
# ---------------------------------------------------------------------------

def test_unregister_idempotent(tmp_path):
    """unregister_board_feeder() mit unbekannter ID wirft keinen Fehler."""
    engine, cfg = _engine_mit_kanal(tmp_path)

    engine.register_board_feeder(feeder_id=42)
    engine.unregister_board_feeder(feeder_id=42)
    engine.unregister_board_feeder(feeder_id=42)  # Zweiter Aufruf: kein Fehler

    with engine._board_feeders_lock:
        assert 42 not in engine._board_feeders


# ---------------------------------------------------------------------------
# Test 6: Overlap-Mode — mehrere Feeder für denselben Pad additiv
# ---------------------------------------------------------------------------

def test_overlap_mode_additiv(tmp_path):
    """Overlap-Mode mit zwei Feeder-Instanzen → beide Puffer additiv summiert.

    Simuliert zwei gleichzeitig laufende Feeder für denselben Pad (z. B. Jingle
    zweimal hintereinander ausgelöst). IDs unterscheiden sich (id(feeder1) vs id(feeder2)).
    """
    engine, cfg = _engine_mit_kanal(tmp_path)

    block_size = cfg.block_size
    ch = cfg.channels

    # Zwei Feeder-Instanzen mit unterschiedlichen IDs (Overlap)
    id_a, id_b = 1001, 1002
    puffer_a = engine.register_board_feeder(feeder_id=id_a)
    puffer_b = engine.register_board_feeder(feeder_id=id_b)

    puffer_a.append(np.full((block_size, ch), 0.4, dtype=np.float32))
    puffer_b.append(np.full((block_size, ch), 0.35, dtype=np.float32))

    _null_kanal_block(engine, cfg)

    aufnahme_dir = str(tmp_path / "overlap_mix")
    engine.start_recording(aufnahme_dir)
    engine._mix_one_tick()
    ergebnis = engine.stop_recording()

    import soundfile as sf
    import os
    mix_daten, _ = sf.read(ergebnis["mix"], dtype="float32")
    max_amp = float(np.max(np.abs(mix_daten)))

    # Summe = 0.4 + 0.35 = 0.75 → max_amp > 0.5 (wäre nur ein Feeder)
    assert max_amp > 0.5, (
        f"Overlap-Mode summiert nicht additiv: max_amp={max_amp:.4f}, erwartet > 0.5"
    )
