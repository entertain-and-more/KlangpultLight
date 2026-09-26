"""tests.test_bugsweep_board_model_and_ducking_20260926 — Regressionstests für Bugsweep 2026-09-26.

Belegt funktionale Mängel und Randfälle in:
  1. board.board_model.load_board(): Absturz mit AttributeError bei Nicht-Dict JSON (z.B. [], null, "string").
  2. board.board_model.Pad.from_dict(): Ungeschützte Übernahme von volume=None / ungültigen Typen führt
     im Feeder zu TypeError beim Lautstärke-Scaling. Fehlende Normalisierung von ID, Modus und Typ.
  3. board.board_model.validate_workspace_payload(): Akzeptiert version=True (bool subclass) und validiert
     teleprompter-Eigenschaften (font_size, scroll_speed, text) nicht gegen shared/workspace_v1.json.
  4. board.board_model.export_workspace_full(): Absturz mit TypeError/ValueError bei None/ungültigen
     Teleprompter-Werten und String-Korruption von None zu "None".
  5. board.board_model.save_board(): Leerer Pfad erzeugt verwaiste .tmp-Dateien im CWD.
  6. board.duck_controller.DuckController: Fehlende is_idle()-Methode zur Erkennung des Release-Abschlusses.
  7. audio.engine.AudioEngine._mix_one_tick(): Harter Gain-Sprung auf 1.0 bei vorzeitigem unregister_duck(),
     Release-Rampe des DuckControllers wurde in der Engine abgeschnitten.
  8. board.board_player.BoardPlayer: Restlisten mit leeren Feeder-Listen verbleiben nach Pad-Ende in self._feeder.
"""
import pytest
import numpy as np

from board.board_model import (
    Board,
    Pad,
    load_board,
    save_board,
    validate_workspace_payload,
    export_workspace_full,
    WORKSPACE_FORMAT,
    WORKSPACE_VERSION,
)
from board.duck_controller import DuckController
from audio.engine import AudioEngine
from core.config import AppConfig
from audio.mixer_channel import MixerChannel


class TestLoadBoardNonDictJson:
    """load_board() muss bei allen ungültigen oder Nicht-Dict JSON-Inhalten leere Boards liefern."""

    def test_load_board_array_json_returns_empty_board(self, tmp_path):
        bad_json = tmp_path / "array.json"
        bad_json.write_text("[]", encoding="utf-8")
        board = load_board(str(bad_json))
        assert isinstance(board, Board)
        assert len(board.pads) == 0

    def test_load_board_null_json_returns_empty_board(self, tmp_path):
        bad_json = tmp_path / "null.json"
        bad_json.write_text("null", encoding="utf-8")
        board = load_board(str(bad_json))
        assert isinstance(board, Board)
        assert len(board.pads) == 0

    def test_load_board_primitive_string_returns_empty_board(self, tmp_path):
        bad_json = tmp_path / "str.json"
        bad_json.write_text('"nur ein string"', encoding="utf-8")
        board = load_board(str(bad_json))
        assert isinstance(board, Board)
        assert len(board.pads) == 0

    def test_load_board_primitive_number_returns_empty_board(self, tmp_path):
        bad_json = tmp_path / "num.json"
        bad_json.write_text("12345", encoding="utf-8")
        board = load_board(str(bad_json))
        assert isinstance(board, Board)
        assert len(board.pads) == 0


class TestPadFromDictHardening:
    """Pad.from_dict() muss Werte defensiv validieren und Feeder-Crashes verhindern."""

    def test_pad_volume_none_defaults_to_one(self):
        pad = Pad.from_dict({"id": "p1", "volume": None})
        assert isinstance(pad.volume, float)
        assert pad.volume == 1.0
        # Darf bei Multiplikation nicht crashen
        arr = np.ones((10, 2), dtype=np.float32)
        res = arr * float(pad.volume)
        assert res.shape == (10, 2)

    def test_pad_volume_string_parsed_or_defaulted(self):
        pad1 = Pad.from_dict({"id": "p1", "volume": "0.75"})
        assert abs(pad1.volume - 0.75) < 1e-6

        pad2 = Pad.from_dict({"id": "p2", "volume": "ungueltig"})
        assert pad2.volume == 1.0

    def test_pad_volume_clamped_to_valid_range(self):
        pad_high = Pad.from_dict({"id": "p1", "volume": 10.0})
        assert pad_high.volume == 4.0

        pad_low = Pad.from_dict({"id": "p2", "volume": -2.0})
        assert pad_low.volume == 0.0

    def test_pad_id_normalized_to_string(self):
        pad = Pad.from_dict({"id": 42})
        assert pad.id == "42"
        assert isinstance(pad.id, str)

    def test_pad_kind_and_mode_fallback(self):
        pad = Pad.from_dict({"id": "p1", "kind": "fantasie", "mode": "unbekannt"})
        assert pad.kind == "audio"
        assert pad.mode == "play_stop"


class TestValidateWorkspacePayloadSchema:
    """validate_workspace_payload() muss Schema-Konformität zu shared/workspace_v1.json erzwingen."""

    def test_version_must_be_strictly_int_not_bool(self):
        ok, err = validate_workspace_payload({
            "format": WORKSPACE_FORMAT,
            "version": True,
        })
        assert not ok
        assert "Version muss ein Integer" in err

    def test_teleprompter_properties_validated(self):
        # text muss string sein
        ok1, err1 = validate_workspace_payload({
            "format": WORKSPACE_FORMAT,
            "version": 1,
            "teleprompter": {"text": 12345},
        })
        assert not ok1
        assert "text" in err1

        # font_size muss integer >= 8 sein
        ok2, err2 = validate_workspace_payload({
            "format": WORKSPACE_FORMAT,
            "version": 1,
            "teleprompter": {"font_size": 4},
        })
        assert not ok2
        assert "font_size" in err2

        ok2b, err2b = validate_workspace_payload({
            "format": WORKSPACE_FORMAT,
            "version": 1,
            "teleprompter": {"font_size": "24"},
        })
        assert not ok2b
        assert "font_size" in err2b

        # scroll_speed muss zahl >= 0 sein
        ok3, err3 = validate_workspace_payload({
            "format": WORKSPACE_FORMAT,
            "version": 1,
            "teleprompter": {"scroll_speed": -0.5},
        })
        assert not ok3
        assert "scroll_speed" in err3

        # Gültiges Teleprompter-Objekt
        ok4, err4 = validate_workspace_payload({
            "format": WORKSPACE_FORMAT,
            "version": 1,
            "teleprompter": {"text": "Hallo Podcast", "font_size": 24, "scroll_speed": 1.2},
        })
        assert ok4
        assert err4 == ""


class TestExportWorkspaceFullRobustness:
    """export_workspace_full() darf bei None oder ungültigen Werten nicht mit TypeError/ValueError crashen."""

    def test_export_handles_none_values_in_teleprompter(self):
        b = Board(pads=[Pad(id="p1")])
        tp = {"text": None, "font_size": None, "scroll_speed": None}
        exported = export_workspace_full(b, line=["p1"], teleprompter=tp)
        assert exported["format"] == WORKSPACE_FORMAT
        assert exported["version"] == WORKSPACE_VERSION
        assert exported["line"] == ["p1"]
        # Keine korrupten "None"-Strings oder Crashes
        if "teleprompter" in exported:
            assert exported["teleprompter"].get("text") != "None"

    def test_export_handles_invalid_string_numbers_in_teleprompter(self):
        b = Board()
        tp = {"font_size": "ungueltig", "scroll_speed": "auch_ungueltig"}
        exported = export_workspace_full(b, teleprompter=tp)
        assert isinstance(exported, dict)
        if "teleprompter" in exported:
            assert "font_size" not in exported["teleprompter"]
            assert "scroll_speed" not in exported["teleprompter"]


class TestSaveBoardValidation:
    """save_board() muss leere Pfade abweisen."""

    def test_save_board_rejects_empty_path(self):
        b = Board()
        with pytest.raises(ValueError, match="Pfad darf nicht leer sein"):
            save_board(b, "")

        with pytest.raises(ValueError, match="Pfad darf nicht leer sein"):
            save_board(b, "   ")


class TestDuckControllerIsIdle:
    """DuckController.is_idle() gibt zuverlässig an, ob Ducking vollständig abgeschlossen ist."""

    def test_duck_controller_lifecycle_and_idle(self):
        duck = DuckController(duck_db=-12.0, attack=0.01, release=0.05)
        # Initial idle (Gain = 1.0)
        assert duck.is_idle()

        # Start ducking
        duck.start_duck()
        assert not duck.is_idle()

        # Ticke nach unten
        duck.tick(0.02)
        assert abs(duck.current_gain_factor() - duck.duck_target_factor()) < 1e-3
        assert not duck.is_idle()

        # Stoppe ducking -> Release-Phase beginnt
        duck.stop_duck()
        assert not duck.is_idle()

        # Ticke Release teilweise
        duck.tick(0.02)
        assert duck.current_gain_factor() < 0.99
        assert not duck.is_idle()

        # Ticke Release fertig
        duck.tick(0.04)
        assert abs(duck.current_gain_factor() - 1.0) < 1e-4
        assert duck.is_idle()


class TestEngineDuckingReleaseSmoothness:
    """AudioEngine._mix_one_tick() führt die Release-Rampe des DuckControllers sauber aus."""

    def test_mix_one_tick_ramps_duck_smoothly_and_auto_unregisters(self, tmp_path):
        cfg = AppConfig(mock_audio=True, samplerate=48000, block_size=1024, workspace_dir=str(tmp_path))
        kanaele = [MixerChannel(source_id="mic1", name="Mikrofon 1")]
        engine = AudioEngine(config=cfg, channels=kanaele)

        # Release über mehrere Mix-Ticks (dt = 1024 / 48000 ≈ 0.0213 s)
        duck = DuckController(duck_db=-12.0, attack=0.01, release=0.06)
        engine.register_duck(duck)

        # Duck aktivieren und nach unten ticken
        duck.start_duck()
        for _ in range(5):
            engine._mix_one_tick()

        factor_ducked = duck.current_gain_factor()
        assert factor_ducked < 0.35

        # Pad stoppt -> Ducking soll sanft releasen
        duck.stop_duck()

        # Im nächsten Mix-Tick darf die Engine den Faktor NICHT schlagartig auf 1.0 springen lassen
        engine._mix_one_tick()
        factor_tick1 = duck.current_gain_factor()
        assert factor_tick1 < 0.8, f"Faktor sprang sofort zu hoch: {factor_tick1}"
        assert factor_tick1 > factor_ducked, "Faktor stieg nicht an"

        # Ticke bis Release abgeschlossen ist
        for _ in range(10):
            engine._mix_one_tick()

        assert duck.is_idle()
        # Engine hat den inaktiven DuckController sauber abgemeldet
        assert engine._duck is None


class TestBoardPlayerFeederCleanup:
    """BoardPlayer muss self._feeder nach Beendigung von Pads sauber aufräumen."""

    def test_feeder_dict_does_not_leak_empty_lists(self, tmp_path):
        from board.board_player import BoardPlayer
        import soundfile as sf

        wav_pfad = str(tmp_path / "kurz.wav")
        daten = np.full((512, 2), 0.2, dtype=np.float32)
        sf.write(wav_pfad, daten, 48000)

        pad = Pad(id="clean1", asset_path=wav_pfad, mode="play_stop")
        board = Board(pads=[pad])
        cfg = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
        engine = AudioEngine(cfg, channels=[MixerChannel(source_id="m1", name="Mikrofon 1")])

        player = BoardPlayer(engine, board)
        player.trigger("clean1")
        assert "clean1" in player._feeder

        # Stoppen
        player.stop("clean1")

        # Prüfe, dass kein verwaister leerer Eintrag in self._feeder verbleibt
        assert "clean1" not in player._feeder
