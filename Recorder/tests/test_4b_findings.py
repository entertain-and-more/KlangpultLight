"""tests.test_4b_findings — Tests für die eingefalteten 4a-Findings (Task 4b).

Belegt:
  - I-3: Shape-Mismatch zwischen Board-Block und Mix-Block wird geloggt (nicht still verworfen).
  - I-4: Verworfene Blöcke bei vollem _board_puffer werden geloggt.
  - M-2: _letzter_amp wird aus der echten Frame-Amplitude abgeleitet (nicht pauschal pad.volume).
  - Selftest-Erweiterung: Board-Audio-Pad während Mock-Aufnahme → Board-Audio im Mix nachweisbar.
"""
import logging
import os
import time

import numpy as np
import pytest
import soundfile as sf


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio und Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _erstelle_test_wav(pfad: str, dauer_frames: int = 4096, samplerate: int = 48000,
                       channels: int = 2, amplitude: float = 0.3) -> str:
    """Erzeugt eine Test-WAV-Datei mit konstantem Signal."""
    daten = np.full((dauer_frames, channels), amplitude, dtype=np.float32)
    sf.write(pfad, daten, samplerate)
    return pfad


def _engine_und_board(tmp_path, pad_liste):
    """Erzeugt Engine + Board für Tests."""
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from board.board_model import Board

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)
    board = Board(pads=pad_liste)
    return engine, board, cfg


# ---------------------------------------------------------------------------
# Test I-3: Shape-Mismatch wird geloggt
# ---------------------------------------------------------------------------

def test_i3_shape_mismatch_wird_geloggt(tmp_path, caplog):
    """Shape-Mismatch zwischen Board-Block und Mix-Block wird mindestens einmal geloggt.

    Setup: _board_puffer mit einem Block falscher Shape befüllen,
    dann _mix_one_tick() aufrufen — soll warning loggen statt still verwerfen.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    # Block mit falscher Shape in _board_puffer laden
    # Erwartete Shape: (1024, 2) — wir geben (512, 2) statt
    falscher_block = np.zeros((512, 2), dtype=np.float32)
    engine._board_puffer.append(falscher_block)

    # Kanalpuffer mit echten Daten füllen (für mix_one_tick)
    block_size = cfg.block_size
    ch = cfg.channels
    echter_block = np.zeros((block_size, ch), dtype=np.float32)
    for kanal in kanaele:
        engine._kanal_puffer[kanal.source_id].append(echter_block.copy())

    with caplog.at_level(logging.WARNING, logger="audio.engine"):
        engine._mix_one_tick()

    # Mindestens eine Warnung über Shape-Mismatch muss im Log sein
    mismatch_logs = [r for r in caplog.records if "shape" in r.message.lower() or "mismatch" in r.message.lower()]
    assert mismatch_logs, (
        f"Kein Shape-Mismatch-Log gefunden. Alle WARNING-Logs: {[r.message for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Test I-4: Verworfene Blöcke bei vollem Feeder-Puffer werden geloggt
# ---------------------------------------------------------------------------

def test_i4_verworfene_bloecke_werden_geloggt(tmp_path, caplog):
    """Wenn der pro-Feeder-Puffer voll ist und ein Block verworfen wird, soll ein Log erscheinen.

    Task 6a: Feeder schreiben in ihren eigenen pro-Feeder-Puffer (nicht mehr in den
    gemeinsamen _board_puffer). Der Overflow-Check prüft daher self._puffer.
    Test: Feeder-Puffer direkt bis maxlen füllen, dann _feed_loop synchron
    aufrufen — beim ersten append() muss der Feeder einen WARNING loggen.
    """
    from board.board_model import Pad
    from board.board_player import _PadFeeder
    import threading
    from collections import deque

    wav = _erstelle_test_wav(str(tmp_path / "i4_signal.wav"), dauer_frames=4096)
    pad = Pad(id="i4pad", kind="audio", asset_path=wav, mode="play_stop")

    # Stub-Engine mit minimaler API
    class StubEngine:
        class _config:
            block_size = 1024
            samplerate = 48000
            channels = 2
        _board_puffer = deque(maxlen=128)

    engine = StubEngine()
    stop_event = threading.Event()

    feeder = _PadFeeder(
        pad=pad,
        engine=engine,
        block_size=1024,
        samplerate=48000,
        audio_channels=2,
        duck=None,
        on_finish=lambda: None,
        stop_event=stop_event,
    )
    # Feeder manuell einen vollständig gefüllten eigenen Puffer geben
    voll_puffer: deque = deque(maxlen=128)
    dummy_block = np.zeros((1024, 2), dtype=np.float32)
    for _ in range(128):
        voll_puffer.append(dummy_block)
    feeder._puffer = voll_puffer

    assert len(feeder._puffer) == 128, "Puffer sollte voll sein"

    # _feed_loop aufrufen — beim ersten Block-Append muss ein WARNING kommen
    with caplog.at_level(logging.WARNING, logger="board.board_player"):
        feeder._feed_loop(block_size=1024, sr=48000, ch=2, loop=False)

    # Log-Prüfung: WARNING über vollen Puffer / verworfenen Block
    drop_logs = [r for r in caplog.records
                 if any(kw in r.message.lower() for kw in ("voll", "full", "verworf", "overflow", "überlauf", "drop"))]

    assert drop_logs, (
        f"Kein Drop/Overflow-Log gefunden. Alle Logs (WARNING+): "
        f"{[(r.levelname, r.message) for r in caplog.records if r.levelno >= logging.WARNING]}"
    )


# ---------------------------------------------------------------------------
# Test M-2: _letzter_amp aus echter Frame-Amplitude (nicht pad.volume)
# ---------------------------------------------------------------------------

def test_m2_letzter_amp_aus_echter_amplitude(tmp_path):
    """_letzter_amp muss aus der echten Frame-Amplitude kommen, nicht aus pad.volume.

    Szenario: Kurzes Asset (kürzer als FADE_FRAMES) → der Block nach Fade-in
    hat eine viel niedrigere Amplitude als pad.volume. _letzter_amp muss das
    korrekt widerspiegeln, damit der Fade-out nicht zu hoch startet.
    """
    from board.board_model import Pad
    from board.board_player import _PadFeeder
    import threading

    # Sehr kurzes Asset: nur 10 Frames — weit kürzer als FADE_FRAMES (512)
    sehr_kurz_frames = 10
    wav_pfad = str(tmp_path / "sehr_kurz.wav")
    amplitude = 0.8
    daten = np.full((sehr_kurz_frames, 2), amplitude, dtype=np.float32)
    sf.write(wav_pfad, daten, 48000)

    pad = Pad(id="m2pad", kind="audio", asset_path=wav_pfad, mode="play_stop", volume=0.9)

    # Dummy-Engine mit _board_puffer
    class DummyEngine:
        class _cfg:
            block_size = 1024
            samplerate = 48000
            channels = 2
        _board_puffer = __import__('collections').deque(maxlen=128)

    engine = DummyEngine()
    stop_event = threading.Event()
    finish_aufgerufen = []

    feeder = _PadFeeder(
        pad=pad,
        engine=engine,
        block_size=1024,
        samplerate=48000,
        audio_channels=2,
        duck=None,
        on_finish=lambda: finish_aufgerufen.append(True),
        stop_event=stop_event,
    )

    # Feed-Loop ausführen (synchron, kein Thread)
    feeder._feed_loop(block_size=1024, sr=48000, ch=2, loop=False)

    # _letzter_amp muss die tatsächliche (von Fade-in reduzierte) Amplitude sein
    # Das Asset hat 10 Frames, alle innerhalb der Fade-in-Rampe von 512 Frames
    # Die letzten paar Frames des Fade-in haben Amplitude ≈ (10/512) * 0.8 * 0.9 ≈ 0.014
    # Sicherheitsbereich: _letzter_amp darf NICHT pad.volume sein (0.9)
    assert feeder._letzter_amp < float(pad.volume), (
        f"_letzter_amp={feeder._letzter_amp:.4f} ist nicht kleiner als pad.volume={pad.volume} "
        f"— kurzes Asset sollte aufgrund Fade-in eine niedrigere Amplitude haben"
    )
    # Und es muss > 0 sein (Puffer hatte mindestens einen Block)
    assert feeder._letzter_amp >= 0.0, "_letzter_amp darf nicht negativ sein"


# ---------------------------------------------------------------------------
# Test Selftest-Erweiterung: Board-Audio im Mix nachweisbar (deterministisch)
# ---------------------------------------------------------------------------

def test_board_audio_landet_in_mix_deterministisch(tmp_path):
    """Deterministischer Nachweis: Board-Block im _board_puffer landet im Mix.

    Kein Thread, kein Timing. Direkt: Board-Block in Puffer legen, _mix_one_tick()
    synchron aufrufen (ohne engine.start()), Mix-Energie messen.

    Der WavRecorder wird manuell geöffnet, damit stop_recording() eine Datei findet.
    Engine läuft NICHT — kein MixWorker-Thread, der den Board-Block wegkonkurriert.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    block_size = cfg.block_size
    ch = cfg.channels
    null_block = np.zeros((block_size, ch), dtype=np.float32)

    # Board-Signal mit deutlichem Pegel
    board_signal = np.full((block_size, ch), 0.5, dtype=np.float32)
    engine._board_puffer.append(board_signal)

    # Aufnahme direkt starten (ohne engine.start() — kein MixWorker)
    aufnahme_dir = str(tmp_path / "det_board")
    engine.start_recording(aufnahme_dir)

    # Kanalpuffer mit Null-Block füllen, damit _mix_one_tick() hat_daten=True setzt
    for kanal in kanaele:
        engine._kanal_puffer[kanal.source_id].append(null_block.copy())

    # Synchronen Mix-Tick ausführen — Board-Block wird in mix.wav geschrieben
    engine._mix_one_tick()

    ergebnis = engine.stop_recording()

    # Mix auf Board-Audio prüfen
    mix_pfad = ergebnis["mix"]
    assert os.path.exists(mix_pfad), f"mix.wav fehlt: {mix_pfad}"
    mix_daten, _ = sf.read(mix_pfad, dtype="float32")
    assert mix_daten.size > 0, "mix.wav ist leer"
    energie = float(np.sum(mix_daten ** 2))
    assert energie > 0.0, (
        f"Mix-Energie ist 0 — Board-Audio landete nicht im Mix (energie={energie})"
    )


# ---------------------------------------------------------------------------
# Test Selftest-Erweiterung: Board-Audio via Feeder-Thread im Mix (gehärtet, Task 6a)
# ---------------------------------------------------------------------------

def _warte_auf_mix_ticks(engine, min_ticks: int = 20, timeout: float = 5.0) -> bool:
    """Pollt bis der MixWorker min_ticks Board-Ticks produziert hat.

    Liest engine._produced (Gesamttick-Zähler). Deterministisch: kein blindes Sleep.
    """
    deadline = time.monotonic() + timeout
    start = engine._produced
    while time.monotonic() < deadline:
        if engine._produced - start >= min_ticks:
            return True
        time.sleep(0.005)
    return False


def test_board_audio_landet_in_mix_via_feeder(tmp_path):
    """Integrationsnachweis: BoardPlayer-Feeder-Thread schreibt Board-Audio in die Aufnahme.

    Task 6a — gehärtet gegen Flakes:
    - Kein blindes sleep(0.6) mehr: deterministisches Polling auf engine._produced.
    - Diskriminierende Assertion: Baseline-Aufnahme (ohne Board) vs. Board-Aufnahme.
      Board-Signal (Amplitude 0.5) muss klar mehr Energie liefern als Mock-Null-Mix.
    - Test schlägt fehl, wenn Board-Audio NICHT im Mix landet (war bisher nicht der Fall).
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer

    # --- Baseline: Aufnahme OHNE Board-Audio ---
    baseline_dir = str(tmp_path / "baseline")
    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2,
                    workspace_dir=str(tmp_path))
    kanaele_b = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine_b = AudioEngine(config=cfg, channels=kanaele_b)
    engine_b.start()
    engine_b.start_recording(baseline_dir)
    # Mindestens 30 Ticks produzieren lassen
    assert _warte_auf_mix_ticks(engine_b, min_ticks=30), "Baseline: MixWorker produzierte keine Ticks"
    ergebnis_b = engine_b.stop_recording()
    engine_b.stop()

    baseline_daten, _ = sf.read(ergebnis_b["mix"], dtype="float32")
    baseline_energie = float(np.sum(baseline_daten ** 2))

    # --- Board-Aufnahme: mit Audio-Pad (Amplitude 0.5) ---
    wav_pfad = _erstelle_test_wav(str(tmp_path / "board_m4.wav"),
                                   dauer_frames=48000, amplitude=0.5)
    aufnahme_dir = str(tmp_path / "aufnahme_m4")
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    pad = Pad(id="m4pad", kind="audio", asset_path=wav_pfad, mode="play_stop")
    board = Board(pads=[pad])
    player = BoardPlayer(engine=engine, board=board)

    engine.start()
    engine.start_recording(aufnahme_dir)
    player.trigger("m4pad")

    # Warte deterministisch: mindestens 30 Board-Ticks produziert
    assert _warte_auf_mix_ticks(engine, min_ticks=30), "Board-Aufnahme: MixWorker produzierte keine Ticks"

    player.stop_all()
    ergebnis = engine.stop_recording()
    engine.stop()

    mix_pfad = ergebnis["mix"]
    assert os.path.exists(mix_pfad), "mix.wav fehlt"
    mix_daten, _ = sf.read(mix_pfad, dtype="float32")
    assert mix_daten.size > 0, "mix.wav ist leer"

    board_energie = float(np.sum(mix_daten ** 2))

    # Diskriminierende Assertion: Board-Aufnahme muss messbar mehr Energie haben als Baseline.
    # Amplitude 0.5 über 48 000 Frames entspricht hoher Energie — deutlich über Mock-Null-Mix.
    assert board_energie > baseline_energie, (
        f"Board-Audio nicht im Mix nachweisbar: "
        f"board_energie={board_energie:.4f}, baseline_energie={baseline_energie:.4f}"
    )
