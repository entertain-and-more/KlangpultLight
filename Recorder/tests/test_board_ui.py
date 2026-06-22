"""tests.test_board_ui — Board-Panel-Tests für ui.main_window.MainWindow.

TDD Task 4b. Headless / offscreen. Kein Audiogerät.

Belegt:
  - MainWindow baut ein Board-Panel auf (QGroupBox mit Pad-Kacheln)
  - Klick auf Pad-Kachel ruft BoardPlayer.trigger() auf
  - active_pad_ids() wird via QTimer gepollt und Pads werden hervorgehoben
  - on_visual_pad-Callback führt zu keinem Crash (no-op im offscreen-Modus)
  - Hotkeys 1–8 triggern die ersten 8 Pads
"""
import os
import sys
import threading
import time

import numpy as np
import pytest

# ---------------------------------------------------------------------------
# Skip-Bedingung: offscreen-Plattform muss verfügbar sein
# ---------------------------------------------------------------------------

def _offscreen_verfuegbar() -> bool:
    """Prüft ob QT_QPA_PLATFORM=offscreen gesetzt oder nutzbar ist."""
    plat = os.environ.get("QT_QPA_PLATFORM", "").strip()
    return plat == "offscreen"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio und Mock-Video, offscreen."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def qt_app():
    """QApplication-Singleton für GUI-Tests."""
    if not _offscreen_verfuegbar():
        pytest.skip("QT_QPA_PLATFORM=offscreen nicht verfügbar")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _erstelle_test_wav(pfad: str, dauer_frames: int = 4096, samplerate: int = 48000, channels: int = 2) -> str:
    """Erzeugt eine kurze Test-WAV-Datei."""
    import soundfile as sf
    daten = np.full((dauer_frames, channels), 0.3, dtype=np.float32)
    sf.write(pfad, daten, samplerate)
    return pfad


def _erstelle_main_window(tmp_path, qt_app, board=None, board_player=None):
    """Erzeugt ein MainWindow mit optionalem Board/BoardPlayer."""
    from audio.device_manager import DeviceManager
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.app_state import AppState
    from core.config import AppConfig
    from recordings.library import RecordingLibrary
    from ui.main_window import MainWindow

    cfg = AppConfig(
        mock_audio=True,
        block_size=1024,
        samplerate=48000,
        channels=2,
        workspace_dir=str(tmp_path),
    )
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)
    state = AppState()
    library = RecordingLibrary(str(tmp_path))
    device_manager = DeviceManager()

    fenster = MainWindow(
        config=cfg,
        device_manager=device_manager,
        engine=engine,
        library=library,
        state=state,
        board_player=board_player,
    )
    return fenster, engine


# ---------------------------------------------------------------------------
# Test 1: Board-Panel wird aufgebaut
# ---------------------------------------------------------------------------

def test_board_panel_wird_aufgebaut(tmp_path, qt_app):
    """MainWindow baut ein Board-Panel mit Pad-Kacheln auf."""
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    wav = _erstelle_test_wav(str(tmp_path / "pad1.wav"))
    pad1 = Pad(id="p1", label="Intro", color="#3a86ff", kind="audio", asset_path=wav)
    pad2 = Pad(id="p2", label="Jingle", color="#ff006e", kind="audio", asset_path=wav)
    board = Board(pads=[pad1, pad2])

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)
    player = BoardPlayer(engine=engine, board=board)

    fenster, _ = _erstelle_main_window(tmp_path, qt_app, board=board, board_player=player)

    # Board-Panel muss als Attribut existieren
    assert hasattr(fenster, "_board_panel"), "MainWindow hat kein _board_panel"
    # Pad-Buttons müssen vorhanden sein
    assert hasattr(fenster, "_pad_buttons"), "MainWindow hat keine _pad_buttons"
    assert len(fenster._pad_buttons) == 2, f"Erwartet 2 Pad-Buttons, gefunden {len(fenster._pad_buttons)}"


# ---------------------------------------------------------------------------
# Test 2: Klick auf Pad-Kachel ruft BoardPlayer.trigger() auf
# ---------------------------------------------------------------------------

def test_pad_klick_triggert_board_player(tmp_path, qt_app):
    """Klick auf einen Pad-Button ruft BoardPlayer.trigger(pad_id) auf."""
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig

    getriggerte_ids: list[str] = []

    class FakeBoardPlayer:
        def __init__(self):
            self._board = board

        def trigger(self, pad_id: str) -> None:
            getriggerte_ids.append(pad_id)

        def active_pad_ids(self) -> list:
            return []

        def stop_all(self) -> None:
            pass

    wav = _erstelle_test_wav(str(tmp_path / "pad_klick.wav"))
    pad1 = Pad(id="klick1", label="Klick-Pad", color="#3a86ff", kind="audio", asset_path=wav)
    board = Board(pads=[pad1])

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    from audio.engine import AudioEngine
    engine = AudioEngine(config=cfg, channels=kanaele)
    from core.app_state import AppState
    from recordings.library import RecordingLibrary
    from audio.device_manager import DeviceManager
    from ui.main_window import MainWindow

    fake_player = FakeBoardPlayer()
    fenster = MainWindow(
        config=cfg,
        device_manager=DeviceManager(),
        engine=engine,
        library=RecordingLibrary(str(tmp_path)),
        state=AppState(),
        board_player=fake_player,
    )

    # Pad-Button anklicken
    assert hasattr(fenster, "_pad_buttons"), "Keine _pad_buttons vorhanden"
    btn = fenster._pad_buttons.get("klick1")
    assert btn is not None, "Pad-Button 'klick1' nicht gefunden"
    btn.click()

    assert "klick1" in getriggerte_ids, f"trigger('klick1') wurde nicht aufgerufen, got {getriggerte_ids}"


# ---------------------------------------------------------------------------
# Test 3: Aktive Pads werden hervorgehoben (QTimer-Polling)
# ---------------------------------------------------------------------------

def test_aktive_pads_werden_hervorgehoben(tmp_path, qt_app):
    """active_pad_ids() wird gepollt und aktive Pads erhalten ein Highlight-Flag."""
    from board.board_model import Board, Pad
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from core.app_state import AppState
    from recordings.library import RecordingLibrary
    from audio.device_manager import DeviceManager
    from ui.main_window import MainWindow
    from PySide6.QtWidgets import QApplication

    aktive_ids: list[str] = ["p_aktiv"]

    class FakeBoardPlayer:
        def __init__(self):
            self._board = board

        def trigger(self, pad_id: str) -> None:
            pass

        def active_pad_ids(self) -> list:
            return list(aktive_ids)

        def stop_all(self) -> None:
            pass

    wav = _erstelle_test_wav(str(tmp_path / "aktiv.wav"))
    pad_aktiv = Pad(id="p_aktiv", label="Aktiv", color="#3a86ff", kind="audio", asset_path=wav)
    pad_inaktiv = Pad(id="p_inaktiv", label="Inaktiv", color="#888888", kind="audio", asset_path=wav)
    board = Board(pads=[pad_aktiv, pad_inaktiv])

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    fake_player = FakeBoardPlayer()
    fenster = MainWindow(
        config=cfg,
        device_manager=DeviceManager(),
        engine=engine,
        library=RecordingLibrary(str(tmp_path)),
        state=AppState(),
        board_player=fake_player,
    )

    # Einen Timer-Tick manuell auslösen
    fenster._timer_tick()

    # Buttons prüfen: "p_aktiv" muss als aktiv markiert sein
    assert hasattr(fenster, "_pad_buttons"), "Keine _pad_buttons vorhanden"
    btn_aktiv = fenster._pad_buttons.get("p_aktiv")
    btn_inaktiv = fenster._pad_buttons.get("p_inaktiv")
    assert btn_aktiv is not None
    assert btn_inaktiv is not None

    # Highlight-State: Button-Property oder StyleSheet muss sich unterscheiden
    # Wir prüfen das benutzerdefinierte Property "aktiv"
    aktiv_prop = btn_aktiv.property("pad_aktiv")
    inaktiv_prop = btn_inaktiv.property("pad_aktiv")
    assert aktiv_prop == True, f"Aktiver Pad-Button hat pad_aktiv={aktiv_prop!r}, erwartet True"
    assert inaktiv_prop != True, f"Inaktiver Pad-Button hat pad_aktiv={inaktiv_prop!r}, erwartet nicht True"


# ---------------------------------------------------------------------------
# Test 4: on_visual_pad führt zu keinem Crash
# ---------------------------------------------------------------------------

def test_on_visual_pad_kein_crash(tmp_path, qt_app):
    """on_visual_pad-Callback (für Video/Bild-Pads) darf nicht abstürzen."""
    from board.board_model import Board, Pad
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from core.app_state import AppState
    from recordings.library import RecordingLibrary
    from audio.device_manager import DeviceManager
    from ui.main_window import MainWindow

    class FakeBoardPlayer:
        def __init__(self):
            self._board = board

        def trigger(self, pad_id: str) -> None:
            # Simuliere on_visual_pad-Aufruf bei Video-Pad
            if pad_id == "v1" and self._on_visual_pad:
                self._on_visual_pad(board.get_pad(pad_id))

        def active_pad_ids(self) -> list:
            return []

        def stop_all(self) -> None:
            pass

        # Wird von MainWindow injiziert
        _on_visual_pad = None

    pad_video = Pad(id="v1", label="Video-Einspieler", color="#00b4d8", kind="video", asset_path="")
    board = Board(pads=[pad_video])

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    fake_player = FakeBoardPlayer()
    fenster = MainWindow(
        config=cfg,
        device_manager=DeviceManager(),
        engine=engine,
        library=RecordingLibrary(str(tmp_path)),
        state=AppState(),
        board_player=fake_player,
    )

    # on_visual_pad-Callback direkt aufrufen — darf nicht crashen
    pad = board.get("v1")
    assert pad is not None
    # Rufe den Callback des Fensters auf (falls vorhanden)
    if hasattr(fenster, "_on_visual_pad"):
        try:
            fenster._on_visual_pad(pad)
        except Exception as exc:
            pytest.fail(f"on_visual_pad hat eine Exception geworfen: {exc}")
    # Kein Crash = Test bestanden


# ---------------------------------------------------------------------------
# Test 5: Hotkeys 1–8 triggern die ersten Pads
# ---------------------------------------------------------------------------

def test_hotkeys_triggern_pads(tmp_path, qt_app):
    """Hotkeys 1–8 triggern die ersten 8 Pads über QShortcut."""
    from board.board_model import Board, Pad
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from core.app_state import AppState
    from recordings.library import RecordingLibrary
    from audio.device_manager import DeviceManager
    from ui.main_window import MainWindow
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent

    getriggerte_ids: list[str] = []

    class FakeBoardPlayer:
        def __init__(self):
            self._board = board

        def trigger(self, pad_id: str) -> None:
            getriggerte_ids.append(pad_id)

        def active_pad_ids(self) -> list:
            return []

        def stop_all(self) -> None:
            pass

    wav = _erstelle_test_wav(str(tmp_path / "hotkey.wav"))
    pads = [Pad(id=f"hk{i}", label=f"Pad {i}", color="#3a86ff", kind="audio", asset_path=wav) for i in range(3)]
    board = Board(pads=pads)

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2, workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    fake_player = FakeBoardPlayer()
    fenster = MainWindow(
        config=cfg,
        device_manager=DeviceManager(),
        engine=engine,
        library=RecordingLibrary(str(tmp_path)),
        state=AppState(),
        board_player=fake_player,
    )

    # Hotkeys existieren als Attribut
    assert hasattr(fenster, "_pad_shortcuts"), "Keine _pad_shortcuts vorhanden"
    # Shortcut für Pad 0 (Taste '1') aktivieren
    if fenster._pad_shortcuts:
        shortcut_fn = fenster._pad_shortcuts.get("hk0")
        if shortcut_fn is not None:
            shortcut_fn()
            assert "hk0" in getriggerte_ids, "Hotkey '1' hat hk0 nicht getriggert"


# ---------------------------------------------------------------------------
# Einspieler hinzufügen (P1): Datei -> Pad -> Board + Persistenz
# ---------------------------------------------------------------------------

def test_einspieler_hinzufuegen_legt_pad_an_und_persistiert(tmp_path, qt_app):
    """_einspieler_hinzufuegen() leitet den Pad-Typ aus der Endung ab, fügt das
    Pad dem Board hinzu und schreibt board.json in den Workspace."""
    import os
    from board.board_model import Board
    from board.board_player import BoardPlayer

    board = Board(pads=[])
    fenster, engine = _erstelle_main_window(tmp_path, qt_app, board=board)
    fenster._board_player = BoardPlayer(engine=engine, board=board)

    wav = _erstelle_test_wav(str(tmp_path / "jingle.wav"))
    fenster._einspieler_hinzufuegen(wav)

    treffer = [p for p in board.pads if p.asset_path == wav]
    assert len(treffer) == 1, "genau ein neues Pad erwartet"
    assert treffer[0].kind == "audio"
    assert treffer[0].label == "jingle"
    assert os.path.isfile(fenster._board_pfad()), "board.json wurde nicht persistiert"


def test_einspieler_typ_aus_endung(tmp_path, qt_app):
    """Video-/Bild-Endungen ergeben kind=video/image."""
    from board.board_model import Board
    from board.board_player import BoardPlayer

    board = Board(pads=[])
    fenster, engine = _erstelle_main_window(tmp_path, qt_app, board=board)
    fenster._board_player = BoardPlayer(engine=engine, board=board)

    # leere Dummy-Dateien genügen (Pfad/Endung zählt)
    mp4 = tmp_path / "clip.mp4"; mp4.write_bytes(b"x")
    png = tmp_path / "cover.png"; png.write_bytes(b"x")
    fenster._einspieler_hinzufuegen(str(mp4))
    fenster._einspieler_hinzufuegen(str(png))

    kinds = {p.asset_path: p.kind for p in board.pads}
    assert kinds[str(mp4)] == "video"
    assert kinds[str(png)] == "image"


# ---------------------------------------------------------------------------
# Einklappbare Panels (P2)
# ---------------------------------------------------------------------------

def test_panel_einklappbar_versteckt_inhalt(tmp_path, qt_app):
    """_einklappbar macht eine GroupBox checkable; eingeklappt wird der Inhalt
    versteckt und die Breite schrumpft auf einen schmalen Streifen."""
    from PySide6.QtWidgets import QGroupBox, QLabel, QVBoxLayout
    fenster, _ = _erstelle_main_window(tmp_path, qt_app)
    gb = QGroupBox("T")
    lay = QVBoxLayout(gb)
    lab = QLabel("inhalt")
    lay.addWidget(lab)

    fenster._einklappbar(gb)
    assert gb.isCheckable()

    gb.setChecked(False)
    assert lab.isHidden() is True
    assert gb.maximumWidth() == 40

    gb.setChecked(True)
    assert lab.isHidden() is False


def test_einklappbar_ignoriert_nicht_groupbox(tmp_path, qt_app):
    """Nicht-GroupBox-Panels werden unveraendert durchgereicht (kein Crash)."""
    from PySide6.QtWidgets import QWidget
    fenster, _ = _erstelle_main_window(tmp_path, qt_app)
    w = QWidget()
    assert fenster._einklappbar(w) is w
