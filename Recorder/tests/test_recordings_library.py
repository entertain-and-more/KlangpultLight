"""Tests für recordings.library — RecordingLibrary.

Headless, kein Hardware-Zugriff. Nutzt tmp_path (pytest-Fixture).
"""
import json
import os
import time

import pytest

from recordings.library import RecordingLibrary


class TestCreateRecording:
    def test_legt_ordner_und_metadata_an(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Testaufnahme")

        rec_dir = lib.recording_dir(meta.recording_id)
        assert os.path.isdir(rec_dir), "Aufnahme-Ordner fehlt"
        assert os.path.isdir(os.path.join(rec_dir, "main")), "main/-Unterordner fehlt"
        assert os.path.isfile(os.path.join(rec_dir, "metadata.json")), "metadata.json fehlt"

    def test_events_jsonl_angelegt(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Testaufnahme")
        rec_dir = lib.recording_dir(meta.recording_id)
        assert os.path.isfile(os.path.join(rec_dir, "events.jsonl")), "events.jsonl fehlt"

    def test_original_branch_gesetzt(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Podcast Episode 1")
        originals = [b for b in meta.branches if b.is_original]
        assert len(originals) == 1, "Genau ein Original-Branch erwartet"
        assert originals[0].name == "Original"

    def test_metadata_json_utf8_ohne_bom(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Äpfel und Öl")
        rec_dir = lib.recording_dir(meta.recording_id)
        meta_pfad = os.path.join(rec_dir, "metadata.json")

        with open(meta_pfad, "rb") as f:
            rohbytes = f.read(3)
        # UTF-8 BOM wäre 0xEF 0xBB 0xBF
        assert rohbytes[:3] != b"\xef\xbb\xbf", "BOM vorhanden — muss ohne BOM sein"

        with open(meta_pfad, encoding="utf-8") as f:
            daten = json.load(f)
        assert daten["title"] == "Äpfel und Öl"

    def test_eindeutige_ids_bei_schnellen_aufrufen(self, tmp_path):
        """Mehrere schnell erstellte Aufnahmen dürfen nicht kollidieren."""
        lib = RecordingLibrary(str(tmp_path))
        ids = set()
        for i in range(5):
            meta = lib.create_recording(f"Aufnahme {i}")
            ids.add(meta.recording_id)
        assert len(ids) == 5, "recording_ids müssen eindeutig sein"


class TestListRecordings:
    def test_findet_erstellte_aufnahmen(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        lib.create_recording("Erste")
        lib.create_recording("Zweite")
        aufnahmen = lib.list_recordings()
        assert len(aufnahmen) == 2

    def test_neueste_zuerst(self, tmp_path):
        """list_recordings gibt neueste zuerst zurück."""
        lib = RecordingLibrary(str(tmp_path))
        m1 = lib.create_recording("Älter")
        time.sleep(0.01)  # Minimalverzögerung für unterschiedliche Zeitstempel
        m2 = lib.create_recording("Neuer")
        aufnahmen = lib.list_recordings()
        # Neueste zuerst
        assert aufnahmen[0].recording_id == m2.recording_id
        assert aufnahmen[1].recording_id == m1.recording_id

    def test_leere_bibliothek(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        assert lib.list_recordings() == []

    def test_ignoriert_ungültige_ordner(self, tmp_path):
        """Ordner ohne metadata.json werden übersprungen."""
        lib = RecordingLibrary(str(tmp_path))
        # Ungültiger Ordner ohne metadata.json
        komisch = os.path.join(str(tmp_path), "recordings", "komischer_ordner")
        os.makedirs(komisch, exist_ok=True)
        lib.create_recording("Valide")
        aufnahmen = lib.list_recordings()
        assert len(aufnahmen) == 1


class TestUpdateMetadata:
    def test_persistiert_änderungen(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Original")
        meta.title = "Geändert"
        meta.duration = 123.4
        lib.update_metadata(meta)

        # Frisch laden
        aufnahmen = lib.list_recordings()
        assert aufnahmen[0].title == "Geändert"
        assert aufnahmen[0].duration == pytest.approx(123.4)

    def test_utf8_ohne_bom_nach_update(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Übergabe")
        meta.description = "Schöne Beschreibung mit ß"
        lib.update_metadata(meta)

        rec_dir = lib.recording_dir(meta.recording_id)
        meta_pfad = os.path.join(rec_dir, "metadata.json")
        with open(meta_pfad, "rb") as f:
            assert f.read(3) != b"\xef\xbb\xbf", "BOM nach update vorhanden"

        with open(meta_pfad, encoding="utf-8") as f:
            daten = json.load(f)
        assert daten["description"] == "Schöne Beschreibung mit ß"

    def test_atomic_write_keine_tmp_datei(self, tmp_path):
        """Nach update_metadata() darf keine metadata.json.tmp übrig bleiben.

        Belegt Bugsweep-Fix: update_metadata() nutzt jetzt Temp-Datei + os.replace()
        statt direktem Überschreiben.
        """
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Atomic-Test")
        meta.title = "Geändert"
        lib.update_metadata(meta)

        rec_dir = lib.recording_dir(meta.recording_id)
        tmp_datei = os.path.join(rec_dir, "metadata.json.tmp")
        assert not os.path.exists(tmp_datei), (
            f"metadata.json.tmp darf nach update_metadata() nicht existieren: {tmp_datei}"
        )
        # Die eigentliche Datei muss da sein
        assert os.path.isfile(os.path.join(rec_dir, "metadata.json"))


class TestRenameRecording:
    def test_umbenennen_aendert_titel_nicht_id(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Alt")
        rid = meta.recording_id
        lib.rename_recording(rid, "Neu")
        liste = lib.list_recordings()
        treffer = next(m for m in liste if m.recording_id == rid)
        assert treffer.title == "Neu"
        assert treffer.recording_id == rid  # ID/Ordner unveraendert

    def test_leerer_titel_wirft(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Alt")
        with pytest.raises(ValueError):
            lib.rename_recording(meta.recording_id, "   ")

    def test_unbekannte_aufnahme_wirft(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        with pytest.raises(ValueError):
            lib.rename_recording("recording_gibt_es_nicht", "X")


class TestDeleteRecording:
    def test_loeschen_entfernt_ordner_und_aus_liste(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Weg damit")
        rid = meta.recording_id
        assert os.path.isdir(lib.recording_dir(rid))
        lib.delete_recording(rid)
        assert not os.path.isdir(lib.recording_dir(rid))
        assert all(m.recording_id != rid for m in lib.list_recordings())

    def test_loeschen_unbekannt_wirft(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        with pytest.raises(ValueError):
            lib.delete_recording("recording_gibt_es_nicht")

    def test_andere_aufnahmen_bleiben(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        a = lib.create_recording("A")
        b = lib.create_recording("B")
        lib.delete_recording(a.recording_id)
        ids = {m.recording_id for m in lib.list_recordings()}
        assert b.recording_id in ids
        assert a.recording_id not in ids

    def test_loeschen_mit_path_traversal_verhindert(self, tmp_path):
        """delete_recording darf bei Traversal-Versuchen niemals Workspace löschen."""
        lib = RecordingLibrary(str(tmp_path))
        lib.create_recording("Wichtig")
        recordings_dir = tmp_path / "recordings"
        assert recordings_dir.exists()

        ungueltige_ids = ["..", ".", "", "   ", "../..", "sub/aufnahme", "..\\aufnahme", "/etc/passwd"]
        for bad_id in ungueltige_ids:
            with pytest.raises(ValueError):
                lib.delete_recording(bad_id)

        # Workspace und Recordings müssen intakt sein
        assert tmp_path.exists(), "Workspace wurde durch Traversal gelöscht!"
        assert recordings_dir.exists(), "Recordings-Ordner wurde gelöscht!"
        assert len(lib.list_recordings()) == 1

    def test_loeschen_ignoriert_ordner_ohne_metadata_json(self, tmp_path):
        """Ordner ohne metadata.json dürfen nicht versehentlich gelöscht werden."""
        lib = RecordingLibrary(str(tmp_path))
        fremd_ordner = tmp_path / "recordings" / "fremde_dateien"
        fremd_ordner.mkdir(parents=True, exist_ok=True)
        (fremd_ordner / "notiz.txt").write_text("Wichtig", encoding="utf-8")

        with pytest.raises(ValueError, match="nicht gefunden"):
            lib.delete_recording("fremde_dateien")

        assert fremd_ordner.exists(), "Fremdordner ohne metadata.json wurde gelöscht!"


class TestRecordingDirValidation:
    def test_recording_dir_absoluter_pfad_und_traversal_schutz(self, tmp_path):
        """recording_dir liefert absoluten Pfad und weist Traversal ab."""
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Valide")
        rec_dir = lib.recording_dir(meta.recording_id)
        assert os.path.isabs(rec_dir), "recording_dir muss absoluten Pfad liefern"

        ungueltige = ["..", ".", "", "  ", "a/b", "a\\b", "/root"]
        for bad in ungueltige:
            with pytest.raises(ValueError):
                lib.recording_dir(bad)


class TestAddBranchValidation:
    def test_add_branch_leerer_name_wirft(self, tmp_path):
        lib = RecordingLibrary(str(tmp_path))
        meta = lib.create_recording("Basis")
        with pytest.raises(ValueError, match="nicht leer"):
            lib.add_branch(meta.recording_id, "   ")
