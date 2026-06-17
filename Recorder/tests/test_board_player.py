"""tests.test_board_player — Tests für board.board_player.BoardPlayer.

TDD Task 4a. Headless, kein Audiogerät.

Tests erzeugen kurze WAVs mit soundfile. Engine läuft im Mock-Modus.
Alle Tests verwenden die Engine-Puffer-Mechanik (_board_puffer) als Prüfpunkt.

Belegt:
  - Audio-Pad triggern → _board_puffer erhält Blöcke (Board-Audio im Mix)
  - active_pad_ids() korrekt
  - stop() beendet Feeder
  - Während Audio-Pad spielt → DuckController aktiv (Gain-Faktor < 1.0)
  - Video/Bild-Pad triggert on_visual_pad-Callback, kein Audio
  - mode overlap erlaubt mehrere gleichzeitig
  - mode play_stop togglet
  - mode loop wiederholt (Feeder bleibt alive nach erstem Durchlauf)
  - keine verwaisten Threads nach stop_all
"""
import os
import time
import threading

import numpy as np
import soundfile as sf
import pytest


# ---------------------------------------------------------------------------
# Fixtures / Hilfsfunktionen
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _erstelle_test_wav(pfad: str, dauer_frames: int = 4096, samplerate: int = 48000, channels: int = 2) -> str:
    """Erzeugt eine kurze Test-WAV-Datei.

    Args:
        pfad:          Zielpfad der WAV-Datei.
        dauer_frames:  Anzahl Frames (Standard: 4096 ≈ 85 ms bei 48 kHz).
        samplerate:    Samplerate.
        channels:      Anzahl Kanäle.

    Returns:
        pfad (zur Verwendung als asset_path).
    """
    daten = np.full((dauer_frames, channels), 0.3, dtype=np.float32)
    sf.write(pfad, daten, samplerate)
    return pfad


def _engine_und_board(tmp_path, pad_liste):
    """Erzeugt Engine + Board für Tests (kein start())."""
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from board.board_model import Board, Pad

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    board = Board(pads=pad_liste)
    return engine, board, cfg


def _warte_auf_puffer(engine, timeout: float = 2.0) -> bool:
    """Wartet bis _board_puffer mindestens einen Block enthält."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if len(engine._board_puffer) > 0:
            return True
        time.sleep(0.01)
    return False


# ---------------------------------------------------------------------------
# Test 1: Audio-Pad triggern → Engine-Puffer erhält Blöcke
# ---------------------------------------------------------------------------

def test_audio_pad_füllt_board_puffer(tmp_path):
    """Audio-Pad trigger → _board_puffer der Engine erhält mindestens einen Block."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    wav_pfad = _erstelle_test_wav(str(tmp_path / "jingle.wav"))
    pad = Pad(id="audio1", kind="audio", asset_path=wav_pfad, mode="play_stop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    player = BoardPlayer(engine=engine, board=board)

    player.trigger("audio1")

    hat_daten = _warte_auf_puffer(engine, timeout=2.0)
    player.stop_all()

    assert hat_daten, "_board_puffer blieb leer — Board-Audio wurde nicht eingereiht"


def test_active_pad_ids_korrekt(tmp_path):
    """active_pad_ids() enthält laufende Pad-IDs."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    wav_pfad = _erstelle_test_wav(str(tmp_path / "jingle.wav"), dauer_frames=48000)  # 1 s
    pad = Pad(id="a1", kind="audio", asset_path=wav_pfad, mode="play_stop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    player = BoardPlayer(engine=engine, board=board)

    player.trigger("a1")
    time.sleep(0.05)  # Kurz warten bis Feeder-Thread läuft

    ids = player.active_pad_ids()
    player.stop_all()

    assert "a1" in ids, f"active_pad_ids() enthielt 'a1' nicht: {ids}"


def test_stop_beendet_feeder(tmp_path):
    """stop() beendet den Feeder; active_pad_ids() ist danach leer."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    wav_pfad = _erstelle_test_wav(str(tmp_path / "jingle.wav"), dauer_frames=96000)  # 2 s
    pad = Pad(id="b1", kind="audio", asset_path=wav_pfad, mode="play_stop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    player = BoardPlayer(engine=engine, board=board)

    player.trigger("b1")
    time.sleep(0.05)

    player.stop("b1")
    time.sleep(0.1)  # Thread-Join

    assert "b1" not in player.active_pad_ids(), "Feeder noch aktiv nach stop()"


# ---------------------------------------------------------------------------
# Test 2: Board-Audio taucht im MixWorker auf — synchroner Nachweis
# ---------------------------------------------------------------------------

def test_board_audio_summiert_auf_mix(tmp_path):
    """Synchroner Nachweis: Board-Puffer-Block wird im Mix sichtbar.

    Methode (proof-guard): Mic-Kanäle werden mit Null-Blöcken gefüllt;
    Board-Puffer erhält einen bekannten Block (Amplitude 0.5).
    _mix_one_tick() muss den Board-Block auf den Mix summieren →
    mix_block darf nicht Null sein. Wenn die Summierung entfernt wird,
    fällt dieser Test.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from audio.wav_recorder import WavRecorder

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    # Mic-Kanal mit NULLEN füllen (kein Mock-Synth-Thread!)
    null_block = np.zeros((1024, 2), dtype=np.float32)
    engine._kanal_puffer["mic1"].append(null_block)

    # Board-Puffer mit bekanntem Signal füllen (Amplitude 0.5)
    board_block = np.full((1024, 2), 0.5, dtype=np.float32)
    engine._board_puffer.append(board_block)

    # Aufnahme starten und genau einen Tick ausführen
    aufnahme_dir = str(tmp_path / "sync_test")
    engine.start_recording(aufnahme_dir)
    hatte_daten = engine._mix_one_tick()
    ergebnis = engine.stop_recording()

    assert hatte_daten, "_mix_one_tick() meldet keinen Daten-Tick"

    mix_pfad = ergebnis["mix"]
    assert os.path.exists(mix_pfad), "mix.wav fehlt"

    mix_daten, _ = sf.read(mix_pfad, dtype="float32")
    assert mix_daten.size > 0, "mix.wav ist leer"
    assert np.max(np.abs(mix_daten)) > 0.1, (
        f"Board-Block (0.5) fehlt im Mix — max={np.max(np.abs(mix_daten)):.4f}. "
        "Summierung in _mix_one_tick() ist nicht aktiv."
    )


def test_board_audio_landet_in_mix_integriert(tmp_path):
    """Integrierter Test: Board-Audio über echten BoardPlayer sichtbar in mix.wav.

    Ergänzt den synchronen Nachweis — prüft den echten Feeder-Pfad.
    Mic läuft im Mock-Modus, Board-Signal liegt bei 0.3.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    wav_pfad = _erstelle_test_wav(str(tmp_path / "board_signal.wav"), dauer_frames=24000)
    pad = Pad(id="bm1", kind="audio", asset_path=wav_pfad, mode="play_stop")
    board = Board(pads=[pad])
    player = BoardPlayer(engine=engine, board=board)

    aufnahme_dir = str(tmp_path / "aufnahme_board")
    engine.start()
    time.sleep(0.05)

    engine.start_recording(aufnahme_dir)
    player.trigger("bm1")
    time.sleep(0.5)

    player.stop_all()
    ergebnis = engine.stop_recording()
    engine.stop()

    mix_pfad = ergebnis["mix"]
    assert os.path.exists(mix_pfad), "mix.wav fehlt"
    mix_daten, _ = sf.read(mix_pfad, dtype="float32")
    assert mix_daten.size > 0, "mix.wav ist leer"
    assert np.max(np.abs(mix_daten)) > 0.0, "mix.wav enthält nur Nullen"


# ---------------------------------------------------------------------------
# Test 3: Ducking — DuckController aktiv während Audio-Pad spielt
# ---------------------------------------------------------------------------

def test_ducking_aktiv_waehrend_pad_spielt(tmp_path):
    """Während ein Audio-Pad spielt, sinkt current_gain_factor() unter 1.0."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer
    from board.duck_controller import DuckController

    wav_pfad = _erstelle_test_wav(str(tmp_path / "duck_signal.wav"), dauer_frames=48000)
    pad = Pad(id="d1", kind="audio", asset_path=wav_pfad, mode="play_stop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    duck = DuckController(duck_db=-12.0, attack=0.001, release=0.3)
    player = BoardPlayer(engine=engine, board=board, duck=duck)

    player.trigger("d1")

    # Warten bis Ducking einsetzt (MixWorker nicht aktiv — Ticks manuell)
    deadline = time.monotonic() + 2.0
    faktor_unter_eins = False
    while time.monotonic() < deadline:
        duck.tick(0.01)  # Simuliere MixWorker-Ticks
        if duck.current_gain_factor() < 0.99:
            faktor_unter_eins = True
            break
        time.sleep(0.01)

    player.stop_all()

    assert faktor_unter_eins, (
        f"DuckController wurde nicht aktiviert — Faktor blieb bei {duck.current_gain_factor():.3f}"
    )


def test_ducking_skaliert_mic_im_mix(tmp_path):
    """Synchroner Nachweis: Mic-Block wird durch Ducking abgeschwächt.

    Methode: Mic-Kanal erhält Block mit Amplitude 1.0; Duck-Faktor -12 dB ≈ 0.25.
    Nach register_duck + start_duck + _mix_one_tick() muss mix-Amplitude < 0.5.
    Fällt aus wenn duck_faktor in _mix_one_tick() nicht angewendet wird.
    """
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from board.duck_controller import DuckController
    from audio.wav_recorder import WavRecorder

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    duck = DuckController(duck_db=-12.0, attack=1e-9, release=1.0)
    duck.start_duck()
    # Vorab ticken damit Faktor am Ziel (attack=1e-9 → sofort)
    duck.tick(1.0)
    erwartet_faktor = duck.current_gain_factor()
    assert erwartet_faktor < 0.5, f"Duck-Faktor zu hoch: {erwartet_faktor}"

    # Duck in Engine registrieren
    engine.register_duck(duck)

    # Mic-Block mit voller Amplitude
    mic_block = np.ones((1024, 2), dtype=np.float32)
    engine._kanal_puffer["mic1"].append(mic_block)

    aufnahme_dir = str(tmp_path / "duck_mic_test")
    engine.start_recording(aufnahme_dir)
    engine._mix_one_tick()
    ergebnis = engine.stop_recording()

    mix_daten, _ = sf.read(ergebnis["mix"], dtype="float32")
    max_amp = float(np.max(np.abs(mix_daten)))
    assert max_amp < 0.5, (
        f"Mic wurde NICHT abgeschwächt — Amplitude {max_amp:.4f} ≥ 0.5. "
        f"Duck-Faktor {erwartet_faktor:.4f} wurde nicht angewendet."
    )


def test_ducking_zurück_nach_pad_ende(tmp_path):
    """Nach stop() des Pads rampt DuckController zurück auf 1.0."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer
    from board.duck_controller import DuckController

    # Sehr kurze WAV — endet schnell
    wav_pfad = _erstelle_test_wav(str(tmp_path / "kurz.wav"), dauer_frames=512)
    pad = Pad(id="d2", kind="audio", asset_path=wav_pfad, mode="play_stop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    duck = DuckController(duck_db=-12.0, attack=0.001, release=0.001)
    player = BoardPlayer(engine=engine, board=board, duck=duck)

    player.trigger("d2")
    # Ducken
    for _ in range(100):
        duck.tick(0.01)

    # Auf Pad-Ende warten
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline and "d2" in player.active_pad_ids():
        time.sleep(0.02)

    player.stop_all()

    # Release-Rampe simulieren
    for _ in range(1000):
        duck.tick(0.01)

    assert abs(duck.current_gain_factor() - 1.0) < 1e-3, (
        f"DuckController nicht zurück auf 1.0: {duck.current_gain_factor():.4f}"
    )


# ---------------------------------------------------------------------------
# Test 4: Video/Bild-Pad → Callback, kein Audio
# ---------------------------------------------------------------------------

def test_video_pad_callback_kein_audio(tmp_path):
    """Video-Pad triggert on_visual_pad-Callback und schreibt NICHTS in den Board-Puffer."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    pad = Pad(id="v1", kind="video", asset_path="promo.mp4", mode="play_stop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])

    callback_pads = []
    player = BoardPlayer(
        engine=engine,
        board=board,
        on_visual_pad=lambda p: callback_pads.append(p.id),
    )

    initial_puffer_groesse = len(engine._board_puffer)
    player.trigger("v1")
    time.sleep(0.05)

    assert "v1" in callback_pads, "on_visual_pad-Callback wurde nicht aufgerufen"
    assert len(engine._board_puffer) == initial_puffer_groesse, (
        "Video-Pad hat fälschlicherweise Blöcke in den Board-Puffer geschrieben"
    )


def test_bild_pad_callback(tmp_path):
    """Image-Pad triggert ebenfalls on_visual_pad-Callback."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    pad = Pad(id="img1", kind="image", asset_path="logo.png")

    engine, board, _ = _engine_und_board(tmp_path, [pad])

    aufgerufen = []
    player = BoardPlayer(
        engine=engine,
        board=board,
        on_visual_pad=lambda p: aufgerufen.append(p),
    )

    player.trigger("img1")
    time.sleep(0.05)

    assert len(aufgerufen) == 1
    assert aufgerufen[0].id == "img1"


# ---------------------------------------------------------------------------
# Test 5: Mode overlap — mehrere gleichzeitige Feeder
# ---------------------------------------------------------------------------

def test_overlap_erlaubt_mehrere_feeder(tmp_path):
    """Mode=overlap: mehrfaches trigger() startet mehrere Feeder gleichzeitig."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    wav_pfad = _erstelle_test_wav(str(tmp_path / "overlap.wav"), dauer_frames=96000)  # 2 s
    pad = Pad(id="ov1", kind="audio", asset_path=wav_pfad, mode="overlap")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    player = BoardPlayer(engine=engine, board=board)

    player.trigger("ov1")
    time.sleep(0.05)
    player.trigger("ov1")
    time.sleep(0.05)

    # Beide Feeder müssen laufen
    with player._lock:
        feeder_liste = player._feeder.get("ov1", [])
        aktive = [f for f in feeder_liste if f.is_alive()]

    player.stop_all()

    assert len(aktive) >= 2, f"Overlap: erwartet ≥2 aktive Feeder, gefunden: {len(aktive)}"


# ---------------------------------------------------------------------------
# Test 6: Mode play_stop — toggle
# ---------------------------------------------------------------------------

def test_play_stop_toggle(tmp_path):
    """Mode=play_stop: zweites trigger() stoppt den laufenden Pad."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    wav_pfad = _erstelle_test_wav(str(tmp_path / "toggle.wav"), dauer_frames=96000)
    pad = Pad(id="ps1", kind="audio", asset_path=wav_pfad, mode="play_stop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    player = BoardPlayer(engine=engine, board=board)

    # Start
    player.trigger("ps1")
    time.sleep(0.05)
    assert "ps1" in player.active_pad_ids(), "Pad nach erstem trigger() nicht aktiv"

    # Toggle: Stop
    player.trigger("ps1")
    time.sleep(0.15)  # Join-Zeit
    assert "ps1" not in player.active_pad_ids(), "Pad nach zweitem trigger() immer noch aktiv"

    player.stop_all()


# ---------------------------------------------------------------------------
# Test 7: mode loop — Feeder bleibt alive nach erstem WAV-Durchlauf
# ---------------------------------------------------------------------------

def test_loop_mode_feeder_lebt_nach_erstem_durchlauf(tmp_path):
    """Mode=loop: Feeder bleibt alive nachdem das Asset einmal durchgespielt wurde."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    # Sehr kurze WAV (512 Frames ≈ 10 ms) — damit loop-Verhalten schnell sichtbar
    wav_pfad = _erstelle_test_wav(str(tmp_path / "loop_kurz.wav"), dauer_frames=512)
    pad = Pad(id="lp1", kind="audio", asset_path=wav_pfad, mode="loop")

    engine, board, _ = _engine_und_board(tmp_path, [pad])
    player = BoardPlayer(engine=engine, board=board)

    player.trigger("lp1")
    time.sleep(0.1)  # Mehr als ein WAV-Durchlauf bei 10-ms-Asset

    alive = "lp1" in player.active_pad_ids()
    player.stop_all()

    assert alive, "Loop-Feeder ist nach erstem Durchlauf gestorben — loop-Modus funktioniert nicht"


# ---------------------------------------------------------------------------
# Test 8: stop_all — keine verwaisten Threads
# ---------------------------------------------------------------------------

def test_stop_all_keine_verwaisten_threads(tmp_path):
    """stop_all() wartet auf alle Feeder — keine verwaisten Threads danach."""
    from board.board_model import Pad
    from board.board_player import BoardPlayer

    wav_pfad = _erstelle_test_wav(str(tmp_path / "viele.wav"), dauer_frames=96000)
    pads = [
        Pad(id=f"t{i}", kind="audio", asset_path=wav_pfad, mode="play_stop")
        for i in range(3)
    ]

    engine, board, _ = _engine_und_board(tmp_path, pads)
    player = BoardPlayer(engine=engine, board=board)

    # Mehrere Pads starten
    for pad in pads:
        player.trigger(pad.id)

    time.sleep(0.05)

    # Alle stoppen
    player.stop_all()

    # Kurz warten für Thread-Joins (stop_all hat internes join(timeout=2.0))
    time.sleep(0.1)

    # Keine aktiven Pad-IDs mehr
    assert player.active_pad_ids() == [], (
        f"Noch aktive Pads nach stop_all(): {player.active_pad_ids()}"
    )

    # Kein laufender BoardFeeder-Thread
    laufende_threads = [
        t.name for t in threading.enumerate()
        if t.name.startswith("BoardFeeder-")
    ]
    assert laufende_threads == [], (
        f"Verwaiste BoardFeeder-Threads nach stop_all(): {laufende_threads}"
    )


# ---------------------------------------------------------------------------
# Test: Fade-out ist eine echte Rampe, nicht nur Stille
# ---------------------------------------------------------------------------

def test_fade_out_ist_rampe(tmp_path):
    """_PadFeeder._fade_out_in_puffer erzeugt eine absteigende Rampe (keine bloße Stille).

    Prüft, dass das erste Frame des Fade-out-Blocks > 0 ist (Rampe startet
    bei _letzter_amp), das letzte Frame-Segment ≤ 0 ist, und der Block
    streng monoton abnehmend beginnt.
    """
    from board.board_player import _PadFeeder, FADE_FRAMES
    from board.board_model import Pad

    class _FakeEngine:
        def __init__(self):
            from collections import deque
            self._board_puffer = deque(maxlen=128)

    pad = Pad(id="fo1", kind="audio", asset_path="", mode="play_stop")
    engine = _FakeEngine()

    import threading
    feeder = _PadFeeder(
        pad=pad,
        engine=engine,
        block_size=1024,
        samplerate=48000,
        audio_channels=2,
        duck=None,
        on_finish=lambda: None,
        stop_event=threading.Event(),
    )
    feeder._letzter_amp = 0.8  # Simuliert Amplitude nach letztem Feed-Block

    feeder._fade_out_in_puffer(1024, 2)

    assert len(engine._board_puffer) == 1, "Kein Fade-out-Block in Puffer"
    block = engine._board_puffer[0]

    assert block.shape == (1024, 2), f"Falsches Shape: {block.shape}"

    # Erstes Frame sollte nahe _letzter_amp sein (Rampe beginnt dort)
    assert block[0, 0] > 0.5, f"Fade-out startet nicht bei Amplitude: {block[0, 0]:.4f}"

    # Letztes FADE_FRAMES-Frame sollte nahe 0 sein
    assert block[min(FADE_FRAMES - 1, 1023), 0] < 0.1, (
        f"Fade-out endet nicht bei Null: {block[FADE_FRAMES - 1, 0]:.4f}"
    )

    # Rest (nach Fade) sollte Stille sein
    if FADE_FRAMES < 1024:
        assert np.max(np.abs(block[FADE_FRAMES:])) < 1e-6, "Nach Fade-out keine Stille"


# ---------------------------------------------------------------------------
# Test 9: unbekannte Pad-ID — kein Absturz
# ---------------------------------------------------------------------------

def test_trigger_unbekannte_id(tmp_path):
    """trigger() mit unbekannter Pad-ID löst keinen Fehler aus."""
    from board.board_model import Board
    from board.board_player import BoardPlayer

    engine, board, _ = _engine_und_board(tmp_path, [])
    player = BoardPlayer(engine=engine, board=board)

    # Kein AssertionError, kein Exception
    player.trigger("existiert_nicht")
    player.stop("existiert_nicht")
    player.stop_all()
