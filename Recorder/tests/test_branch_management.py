"""tests.test_branch_management — Tests für Branch-Verwaltung + on_visual_pad-Fix.

Belegt:
  - add_branch legt neuen Branch an
  - Original-Branch bleibt unverändert (is_original=True)
  - Neuer Branch persistiert (reload aus Disk)
  - Direkter board_player.trigger(video_pad_id) löst on_visual_pad aus (4b-Fix)
"""
import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio und Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


# ---------------------------------------------------------------------------
# Test: add_branch — Grundfunktion
# ---------------------------------------------------------------------------

def test_add_branch_legt_branch_an(tmp_path):
    """add_branch fügt einen neuen Branch zur Aufnahme hinzu."""
    from recordings.library import RecordingLibrary

    library = RecordingLibrary(workspace_dir=str(tmp_path))
    meta = library.create_recording("Podcast Folge 1")

    # Anfangs: nur Original-Branch
    assert len(meta.branches) == 1
    assert meta.branches[0].is_original is True
    assert meta.branches[0].name == "Original"

    # Branch anlegen
    neuer_branch = library.add_branch(meta.recording_id, "Schnitt A")

    assert neuer_branch.recording_id == meta.recording_id
    assert neuer_branch.name == "Schnitt A"
    assert neuer_branch.is_original is False
    assert neuer_branch.branch_id.startswith("branch_")
    assert neuer_branch.created_at != ""


def test_original_bleibt_unveraendert(tmp_path):
    """Original-Branch darf durch add_branch nicht modifiziert werden."""
    from recordings.library import RecordingLibrary

    library = RecordingLibrary(workspace_dir=str(tmp_path))
    meta = library.create_recording("Aufnahme")
    original_id = meta.branches[0].branch_id

    library.add_branch(meta.recording_id, "Variante 1")
    library.add_branch(meta.recording_id, "Variante 2")

    # Neu laden
    aufnahmen = library.list_recordings()
    reloaded = next(m for m in aufnahmen if m.recording_id == meta.recording_id)

    originals = [b for b in reloaded.branches if b.is_original]
    assert len(originals) == 1, f"Genau ein Original erwartet, aber {len(originals)} gefunden"
    assert originals[0].branch_id == original_id, "Original-Branch-ID hat sich verändert"
    assert originals[0].name == "Original"


def test_branch_persistiert_nach_reload(tmp_path):
    """Neuer Branch ist nach Reload aus Disk auffindbar."""
    from recordings.library import RecordingLibrary

    library = RecordingLibrary(workspace_dir=str(tmp_path))
    meta = library.create_recording("Testaufnahme")

    branch = library.add_branch(meta.recording_id, "Remix")
    branch_id = branch.branch_id

    # Neue Library-Instanz (simuliert App-Neustart)
    library2 = RecordingLibrary(workspace_dir=str(tmp_path))
    aufnahmen = library2.list_recordings()
    reloaded = next(m for m in aufnahmen if m.recording_id == meta.recording_id)

    branch_ids = [b.branch_id for b in reloaded.branches]
    assert branch_id in branch_ids, f"Branch '{branch_id}' nicht nach Reload: {branch_ids}"

    remix_branch = next(b for b in reloaded.branches if b.branch_id == branch_id)
    assert remix_branch.name == "Remix"
    assert remix_branch.is_original is False


def test_mehrere_branches_moeglich(tmp_path):
    """Mehrere Branches können zur selben Aufnahme hinzugefügt werden."""
    from recordings.library import RecordingLibrary

    library = RecordingLibrary(workspace_dir=str(tmp_path))
    meta = library.create_recording("Viele Branches")

    library.add_branch(meta.recording_id, "Version A")
    library.add_branch(meta.recording_id, "Version B")
    library.add_branch(meta.recording_id, "Version C")

    aufnahmen = library.list_recordings()
    reloaded = next(m for m in aufnahmen if m.recording_id == meta.recording_id)

    # Original + 3 Branches = 4
    assert len(reloaded.branches) == 4, f"Erwartet 4 Branches, bekam {len(reloaded.branches)}"


def test_add_branch_unbekannte_aufnahme(tmp_path):
    """add_branch mit unbekannter recording_id wirft ValueError."""
    from recordings.library import RecordingLibrary

    library = RecordingLibrary(workspace_dir=str(tmp_path))

    with pytest.raises(ValueError, match="nicht gefunden"):
        library.add_branch("recording_nicht_vorhanden", "Irgendwas")


# ---------------------------------------------------------------------------
# Test: on_visual_pad Fix (4b) — direkter trigger() ruft Callback auf
# ---------------------------------------------------------------------------

def test_on_visual_pad_wird_aufgerufen_bei_video_pad():
    """Direkter board_player.trigger(video_pad_id) löst on_visual_pad aus.

    Testet den 4b-Fix: BoardPlayer hat on_visual_pad-Callback gesetzt,
    trigger() auf ein Video-Pad ruft den Callback mit dem Pad-Objekt auf.
    """
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from audio.engine import AudioEngine

    aufgerufene_pads = []

    def _on_visual_pad(pad):
        aufgerufene_pads.append(pad)

    # Minimale Engine (nicht gestartet — Video-Pads brauchen sie nicht)
    cfg = AppConfig(mock_audio=True, workspace_dir="/tmp")
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    video_pad = Pad(id="v1", label="Intro-Video", kind="video", asset_path="intro.mp4")
    image_pad = Pad(id="i1", label="Logo", kind="image", asset_path="logo.png")
    audio_pad = Pad(id="a1", label="Jingle", kind="audio", asset_path="")
    board = Board(pads=[video_pad, image_pad, audio_pad])

    player = BoardPlayer(engine=engine, board=board, on_visual_pad=_on_visual_pad)

    # Video-Pad triggern
    player.trigger("v1")
    assert len(aufgerufene_pads) == 1, f"Erwartet 1 Callback-Aufruf, bekam {len(aufgerufene_pads)}"
    assert aufgerufene_pads[0].id == "v1"

    # Bild-Pad triggern
    player.trigger("i1")
    assert len(aufgerufene_pads) == 2
    assert aufgerufene_pads[1].id == "i1"

    # Audio-Pad triggert NICHT den visuellen Callback
    player.trigger("a1")
    assert len(aufgerufene_pads) == 2, "Audio-Pad darf on_visual_pad nicht auslösen"


def test_on_visual_pad_ohne_callback_kein_fehler():
    """trigger() auf Video-Pad ohne Callback löst keinen Fehler aus."""
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from audio.engine import AudioEngine

    cfg = AppConfig(mock_audio=True, workspace_dir="/tmp")
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    video_pad = Pad(id="v2", kind="video", asset_path="")
    board = Board(pads=[video_pad])

    # on_visual_pad=None (Standard)
    player = BoardPlayer(engine=engine, board=board)
    # Darf keinen Fehler werfen
    player.trigger("v2")


def test_on_visual_pad_nachtraeglich_setzen():
    """on_visual_pad kann nachträglich per Attribut-Zuweisung gesetzt werden (main.py-Muster)."""
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer
    from audio.mixer_channel import MixerChannel
    from core.config import AppConfig
    from audio.engine import AudioEngine

    aufgerufene_pads = []

    cfg = AppConfig(mock_audio=True, workspace_dir="/tmp")
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)

    video_pad = Pad(id="v3", kind="video", asset_path="")
    board = Board(pads=[video_pad])

    # BoardPlayer ohne Callback erstellt (wie in _lade_board_und_player)
    player = BoardPlayer(engine=engine, board=board)
    assert player._on_visual_pad is None

    # Callback nachträglich setzen (4b-Fix in main.py)
    player._on_visual_pad = lambda p: aufgerufene_pads.append(p)

    player.trigger("v3")
    assert len(aufgerufene_pads) == 1, "Callback nach nachträglicher Zuweisung soll funktionieren"


# ---------------------------------------------------------------------------
# Test: UI-Aktion „Branch anlegen" (M5, offscreen)
# ---------------------------------------------------------------------------

def _offscreen_verfuegbar() -> bool:
    import os
    return os.environ.get("QT_QPA_PLATFORM", "").strip() == "offscreen"


def test_ui_branch_anlegen_offscreen(tmp_path, monkeypatch):
    """MainWindow._branch_anlegen() legt einen Branch an und refresht die Liste.

    Testet den offscreen-tauglichen Logik-Einstiegspunkt (ohne QMenu/Dialog).
    Wird übersprungen, wenn QT_QPA_PLATFORM=offscreen nicht verfügbar ist.
    """
    import sys
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    if not _offscreen_verfuegbar():
        pytest.skip("QT_QPA_PLATFORM=offscreen nicht verfügbar")

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from audio.device_manager import DeviceManager
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from core.app_state import AppState
    from core.config import AppConfig
    from recordings.library import RecordingLibrary
    from ui.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)

    cfg = AppConfig(mock_audio=True, block_size=1024, samplerate=48000, channels=2,
                    workspace_dir=str(tmp_path))
    kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
    engine = AudioEngine(config=cfg, channels=kanaele)
    state = AppState()
    library = RecordingLibrary(str(tmp_path))
    device_manager = DeviceManager()

    # Eine Aufnahme anlegen, damit die Liste einen Eintrag hat
    meta = library.create_recording("UI-Testaufnahme")

    fenster = MainWindow(
        config=cfg,
        device_manager=device_manager,
        engine=engine,
        library=library,
        state=state,
        board_player=None,
    )

    # Kontextmenü-Policy ist gesetzt
    assert fenster._aufnahme_tree.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu

    # Logik-Einstiegspunkt direkt aufrufen (umgeht QMenu/QInputDialog)
    fenster._branch_anlegen(meta.recording_id, "UI-Branch")

    # Library hat jetzt Original + neuen Branch
    aufnahmen = library.list_recordings()
    reloaded = next(m for m in aufnahmen if m.recording_id == meta.recording_id)
    branch_namen = {b.name for b in reloaded.branches}
    assert "UI-Branch" in branch_namen, f"UI-Branch nicht angelegt: {branch_namen}"
    assert "Original" in branch_namen, "Original muss erhalten bleiben"

    # Tree wurde refresht: Top-Level-Item hat die recording_id, ein Kind heißt „UI-Branch"
    root = fenster._aufnahme_tree.topLevelItem(0)
    assert root is not None
    assert root.data(0, Qt.ItemDataRole.UserRole) == meta.recording_id
    kind_namen = {root.child(i).text(0) for i in range(root.childCount())}
    assert any("UI-Branch" in n for n in kind_namen), f"UI-Branch nicht im Tree: {kind_namen}"

    # recording_id-Ermittlung über ein Branch-Kind liefert die Eltern-ID
    erstes_kind = root.child(0)
    assert fenster._ermittle_recording_id(erstes_kind) == meta.recording_id

    fenster.close()
