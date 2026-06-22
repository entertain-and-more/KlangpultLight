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
