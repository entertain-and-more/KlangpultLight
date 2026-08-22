"""tests.test_board_model — Tests für board.board_model.

TDD Task 4a. Headless, kein Hardware-Zugriff.

Belegt:
  - Pad/Board to_dict/from_dict Roundtrip
  - load_board/save_board (UTF-8 ohne BOM)
  - import_from_workspace/export_to_workspace konsistent mit workspace_v1.json-Format
"""
import os



# ---------------------------------------------------------------------------
# Pad — Roundtrip
# ---------------------------------------------------------------------------

def test_pad_to_dict_from_dict_roundtrip():
    """Pad → to_dict() → from_dict() → identisches Pad."""
    from board.board_model import Pad

    original = Pad(
        id="p1",
        label="Jingle Intro",
        color="#ff0000",
        kind="audio",
        asset_path="/pfad/zur/datei.wav",
        mode="loop",
        hotkey="F1",
        volume=0.8,
    )
    d = original.to_dict()
    wiederhergestellt = Pad.from_dict(d)

    assert wiederhergestellt.id == original.id
    assert wiederhergestellt.label == original.label
    assert wiederhergestellt.color == original.color
    assert wiederhergestellt.kind == original.kind
    assert wiederhergestellt.asset_path == original.asset_path
    assert wiederhergestellt.mode == original.mode
    assert wiederhergestellt.hotkey == original.hotkey
    assert abs(wiederhergestellt.volume - original.volume) < 1e-9


def test_pad_from_dict_ignoriert_unbekannte_felder():
    """from_dict() ignoriert unbekannte Felder ohne Fehler."""
    from board.board_model import Pad

    d = {"id": "p2", "label": "Test", "unbekannt_xyz": 42}
    pad = Pad.from_dict(d)
    assert pad.id == "p2"
    assert pad.label == "Test"


def test_pad_standardwerte():
    """Pad hat sinnvolle Standardwerte bei Minimal-Konstruktion."""
    from board.board_model import Pad

    pad = Pad(id="min")
    assert pad.label == ""
    assert pad.color == "#3b82f6"
    assert pad.kind == "audio"
    assert pad.asset_path == ""
    assert pad.mode == "play_stop"
    assert pad.hotkey == ""
    assert abs(pad.volume - 1.0) < 1e-9


# ---------------------------------------------------------------------------
# Board — Grundoperationen
# ---------------------------------------------------------------------------

def test_board_add_und_get():
    """Pad hinzufügen und per ID abrufen."""
    from board.board_model import Board, Pad

    board = Board()
    pad = Pad(id="a1", label="Applaus")
    board.add(pad)

    gefunden = board.get("a1")
    assert gefunden is not None
    assert gefunden.label == "Applaus"


def test_board_get_nicht_gefunden():
    """get() gibt None zurück wenn ID nicht existiert."""
    from board.board_model import Board

    board = Board()
    assert board.get("existiert_nicht") is None


def test_board_add_ersetzt_vorhandenes():
    """add() ersetzt ein Pad mit gleicher ID."""
    from board.board_model import Board, Pad

    board = Board()
    board.add(Pad(id="a1", label="Alt"))
    board.add(Pad(id="a1", label="Neu"))

    assert len(board.pads) == 1
    assert board.get("a1").label == "Neu"


def test_board_remove():
    """remove() entfernt ein Pad; bei unbekannter ID kein Fehler."""
    from board.board_model import Board, Pad

    board = Board()
    board.add(Pad(id="r1", label="Remove me"))
    board.add(Pad(id="r2", label="Keep me"))

    board.remove("r1")
    assert board.get("r1") is None
    assert board.get("r2") is not None

    # Keine Exception bei nicht vorhandener ID
    board.remove("existiert_nicht")


# ---------------------------------------------------------------------------
# load_board / save_board
# ---------------------------------------------------------------------------

def test_save_und_load_board(tmp_path):
    """save_board + load_board: Roundtrip ohne Datenverlust."""
    from board.board_model import Board, Pad, save_board, load_board

    board = Board(pads=[
        Pad(id="s1", label="Intro-Jingle", kind="audio", volume=0.9),
        Pad(id="s2", label="Übergangs-Bild", kind="image", asset_path="bild.png"),
    ])

    pfad = str(tmp_path / "board.json")
    save_board(board, pfad)

    # Datei existiert
    assert os.path.exists(pfad)

    # UTF-8 ohne BOM prüfen
    with open(pfad, "rb") as f:
        rohbytes = f.read(4)
    assert not rohbytes.startswith(b"\xef\xbb\xbf"), "Datei enthält BOM!"

    # Ladbar
    geladen = load_board(pfad)
    assert len(geladen.pads) == 2
    assert geladen.get("s1").label == "Intro-Jingle"
    assert abs(geladen.get("s1").volume - 0.9) < 1e-9
    assert geladen.get("s2").kind == "image"


def test_load_board_nicht_existierend(tmp_path):
    """load_board gibt leeres Board zurück wenn Datei fehlt."""
    from board.board_model import load_board

    board = load_board(str(tmp_path / "gibts_nicht.json"))
    assert isinstance(board.pads, list)
    assert len(board.pads) == 0


def test_save_board_erstellt_verzeichnis(tmp_path):
    """save_board erstellt das Zielverzeichnis wenn nötig."""
    from board.board_model import Board, Pad, save_board

    pfad = str(tmp_path / "unterordner" / "tief" / "board.json")
    save_board(Board(pads=[Pad(id="v1")]), pfad)
    assert os.path.exists(pfad)


def test_save_board_echte_umlaute(tmp_path):
    """save_board schreibt echte Umlaute (kein \\uXXXX)."""
    from board.board_model import Board, Pad, save_board

    pfad = str(tmp_path / "umlaute.json")
    board = Board(pads=[Pad(id="u1", label="Jingle Ä Ö Ü ß")])
    save_board(board, pfad)

    with open(pfad, encoding="utf-8") as f:
        inhalt = f.read()

    assert "Ä" in inhalt and "ß" in inhalt, "Umlaute wurden escaped statt als echte Zeichen gespeichert"


def test_save_board_atomic_keine_tmp_datei(tmp_path):
    """Nach save_board() darf keine .json.tmp-Datei übrig bleiben.

    Belegt Bugsweep-Fix: save_board() nutzt jetzt Temp-Datei + os.replace().
    """
    from board.board_model import Board, Pad, save_board
    import os as _os
    pfad = str(tmp_path / "board.json")
    board = Board(pads=[Pad(id="p1", label="Test")])
    save_board(board, pfad)

    tmp_datei = pfad + ".tmp"
    assert not _os.path.exists(tmp_datei), (
        f".json.tmp darf nach save_board() nicht existieren: {tmp_datei}"
    )
    assert _os.path.isfile(pfad), "board.json muss existieren"


# ---------------------------------------------------------------------------
# import_from_workspace / export_to_workspace
# ---------------------------------------------------------------------------

def test_import_from_workspace_basis():
    """import_from_workspace liest Pads aus einem workspace_v1-Payload."""
    from board.board_model import import_from_workspace

    payload = {
        "format": "klangpultlight-workspace-v1",
        "version": 1,
        "board": {
            "pads": [
                {"id": "wp1", "label": "Intro", "kind": "audio", "mode": "play_stop"},
                {"id": "wp2", "label": "Logo", "kind": "image"},
            ]
        }
    }

    board = import_from_workspace(payload)
    assert len(board.pads) == 2
    assert board.get("wp1").label == "Intro"
    assert board.get("wp1").kind == "audio"
    assert board.get("wp2").kind == "image"


def test_export_to_workspace_format():
    """export_to_workspace erzeugt korrektes format/version/board-dict."""
    from board.board_model import Board, Pad, export_to_workspace, WORKSPACE_FORMAT, WORKSPACE_VERSION

    board = Board(pads=[
        Pad(id="e1", label="Musik", kind="audio", mode="loop", hotkey="F1"),
    ])

    payload = export_to_workspace(board)

    assert payload["format"] == WORKSPACE_FORMAT
    assert payload["version"] == WORKSPACE_VERSION
    assert "board" in payload
    pads = payload["board"]["pads"]
    assert len(pads) == 1
    assert pads[0]["id"] == "e1"
    assert pads[0]["label"] == "Musik"
    assert pads[0]["kind"] == "audio"
    assert pads[0]["mode"] == "loop"
    # volume ist NICHT im workspace_v1-Schema
    assert "volume" not in pads[0]


def test_import_export_roundtrip():
    """import_from_workspace → export_to_workspace → import_from_workspace: konsistent."""
    from board.board_model import import_from_workspace, export_to_workspace

    original_payload = {
        "format": "klangpultlight-workspace-v1",
        "version": 1,
        "board": {
            "pads": [
                {"id": "rt1", "label": "Sound", "kind": "audio", "mode": "overlap", "color": "#ff0000", "asset_path": "x.wav", "hotkey": ""},
                {"id": "rt2", "label": "Video-Einspieler", "kind": "video", "mode": "play_stop", "color": "#00ff00", "asset_path": "v.mp4", "hotkey": "F2"},
            ]
        }
    }

    board = import_from_workspace(original_payload)
    re_payload = export_to_workspace(board)
    board2 = import_from_workspace(re_payload)

    assert len(board2.pads) == 2
    assert board2.get("rt1").kind == "audio"
    assert board2.get("rt2").label == "Video-Einspieler"
    assert board2.get("rt2").hotkey == "F2"


def test_export_to_workspace_ohne_volume():
    """export_to_workspace schreibt 'volume' nicht in die Pads."""
    from board.board_model import Board, Pad, export_to_workspace

    board = Board(pads=[Pad(id="nv1", volume=0.5)])
    payload = export_to_workspace(board)

    for pad_dict in payload["board"]["pads"]:
        assert "volume" not in pad_dict


def test_import_from_workspace_leer_board():
    """import_from_workspace mit fehlendem 'board'-Feld: leeres Board."""
    from board.board_model import import_from_workspace

    board = import_from_workspace({"format": "klangpultlight-workspace-v1", "version": 1})
    assert len(board.pads) == 0
