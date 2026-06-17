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
# Test I-4: Verworfene Blöcke bei vollem _board_puffer werden geloggt
# ---------------------------------------------------------------------------

def test_i4_verworfene_bloecke_werden_geloggt(tmp_path, caplog):
    """Wenn _board_puffer voll ist und ein Block verworfen wird, soll ein Log erscheinen.

    _PadFeeder schreibt via engine._board_puffer.append() in eine deque mit maxlen=128.
    Wenn sie voll ist, verwirft deque.append() links-seitig OHNE Fehler — das soll geloggt werden.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer

    wav = _erstelle_test_wav(str(tmp_path / "i4_signal.wav"), dauer_frames=4096)
    pad = Pad(id="i4pad", kind="audio", asset_path=wav, mode="overlap")
    pad2 = Pad(id="i4pad2", kind="audio", asset_path=wav, mode="overlap")

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)
    board = Board(pads=[pad, pad2])
    player = BoardPlayer(engine=engine, board=board)

    # _board_puffer bis zur Kapazität füllen
    maxlen = engine._board_puffer.maxlen
    assert maxlen is not None and maxlen > 0
    dummy_block = np.zeros((cfg.block_size, cfg.channels), dtype=np.float32)
    for _ in range(maxlen):
        engine._board_puffer.append(dummy_block)

    assert len(engine._board_puffer) == maxlen, "Puffer sollte voll sein"

    # Jetzt einen weiteren Block direkt anhängen — soll Drop loggen
    with caplog.at_level(logging.WARNING, logger="board.board_player"):
        # _PadFeeder._append_mit_backpressure_check() oder ähnliche Methode aufrufen
        # Da der Feeder thread-intern ist, testen wir BoardPlayer._append_in_puffer()
        # Fallback: direkt append und prüfen ob Log via monkey-patch entsteht
        # Wir simulieren den Drop: der Puffer ist voll, append() wird aufgerufen
        # Dabei soll der Feeder/BoardPlayer loggen
        if hasattr(player, '_append_in_puffer'):
            player._append_in_puffer(dummy_block)
        else:
            # Engine hat keinen Log-Hook → Feeder hat Log-Hook
            # Wir triggern den Feeder kurz und prüfen ob ein Drop-Log erscheint
            # In dieser Situation ist der Puffer voll, jeder neue append() überschreibt links
            # Der Fix muss daher VOR append() prüfen
            engine._board_puffer.append(dummy_block)  # Löst Drop aus

    # Log-Prüfung: WARNING über verworfenen Block oder voller Puffer
    drop_logs = [r for r in caplog.records
                 if any(kw in r.message.lower() for kw in ("drop", "voll", "full", "verworf", "overflow", "überlauf"))]

    if not drop_logs:
        # Akzeptiere auch: BoardPlayer-Trigger mit vollem Puffer erzeugt Log
        # via direktem Trigger-Aufruf
        player.trigger("i4pad")
        time.sleep(0.1)
        drop_logs = [r for r in caplog.records
                     if any(kw in r.message.lower() for kw in ("drop", "voll", "full", "verworf", "overflow", "überlauf"))]

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
    from board.board_player import _PadFeeder, FADE_FRAMES
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
# Test Selftest-Erweiterung: Board-Audio via Feeder-Thread im Mix (Integrationstest)
# ---------------------------------------------------------------------------

def test_board_audio_landet_in_mix_via_feeder(tmp_path):
    """Integrationsnachweis: BoardPlayer-Feeder-Thread schreibt Board-Audio in die Aufnahme.

    Dieser Test belegt Meilenstein M4: Audio-Pads landen in der Aufnahme.
    Das Board-Signal (0.5) ist deutlich über dem Mock-Null-Mix.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer

    wav_pfad = _erstelle_test_wav(str(tmp_path / "board_m4.wav"),
                                   dauer_frames=48000, amplitude=0.5)

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2,
                    workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    pad = Pad(id="m4pad", kind="audio", asset_path=wav_pfad, mode="play_stop")
    board = Board(pads=[pad])
    player = BoardPlayer(engine=engine, board=board)

    aufnahme_dir = str(tmp_path / "aufnahme_m4")
    engine.start()
    time.sleep(0.05)

    engine.start_recording(aufnahme_dir)
    player.trigger("m4pad")
    time.sleep(0.6)  # ausreichend Zeit für Feeder + Mix

    player.stop_all()
    ergebnis = engine.stop_recording()
    engine.stop()

    mix_pfad = ergebnis["mix"]
    assert os.path.exists(mix_pfad), "mix.wav fehlt"
    mix_daten, _ = sf.read(mix_pfad, dtype="float32")
    assert mix_daten.size > 0, "mix.wav ist leer"
    assert np.max(np.abs(mix_daten)) > 0.0, "mix.wav enthält nur Nullen — Board-Audio fehlt"
