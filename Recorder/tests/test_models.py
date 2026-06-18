"""Tests für recordings.models — Branch und RecordingMetadata Roundtrips.

Headless, kein Hardware-Zugriff.
"""
import pytest

from recordings.models import Branch, RecordingMetadata


class TestBranch:
    def test_roundtrip_minimal(self):
        """Mindestfelder Roundtrip."""
        branch = Branch(
            branch_id="b1",
            recording_id="r1",
            name="Original",
        )
        d = branch.to_dict()
        wieder = Branch.from_dict(d)
        assert wieder.branch_id == "b1"
        assert wieder.recording_id == "r1"
        assert wieder.name == "Original"

    def test_roundtrip_vollständig(self):
        """Alle Felder Roundtrip."""
        branch = Branch(
            branch_id="b2",
            recording_id="r2",
            name="Bearbeitet",
            created_at="2024-01-01T00:00:00+00:00",
            audio_path="/pfad/mix.wav",
            video_path="/pfad/video.mp4",
            duration=42.5,
            is_original=True,
        )
        d = branch.to_dict()
        wieder = Branch.from_dict(d)
        assert wieder.branch_id == "b2"
        assert wieder.name == "Bearbeitet"
        assert wieder.audio_path == "/pfad/mix.wav"
        assert wieder.video_path == "/pfad/video.mp4"
        assert wieder.duration == pytest.approx(42.5)
        assert wieder.is_original is True

    def test_to_dict_enthält_alle_schema_felder(self):
        """to_dict liefert alle Felder aus branch.schema.json."""
        branch = Branch(branch_id="b", recording_id="r", name="x")
        d = branch.to_dict()
        assert "branch_id" in d
        assert "recording_id" in d
        assert "name" in d
        assert "created_at" in d
        assert "audio_path" in d
        assert "video_path" in d
        assert "duration" in d
        assert "is_original" in d

    def test_from_dict_fehlende_optionale_felder(self):
        """from_dict toleriert fehlende optionale Felder mit Defaults."""
        d = {"branch_id": "b", "recording_id": "r", "name": "x"}
        branch = Branch.from_dict(d)
        assert branch.duration == 0.0
        assert branch.is_original is False
        assert branch.audio_path == ""


class TestRecordingMetadata:
    def test_roundtrip_minimal(self):
        """Mindestfelder Roundtrip."""
        meta = RecordingMetadata(
            recording_id="rec1",
            title="Meine Aufnahme",
            created_at="2024-06-01T12:00:00+00:00",
        )
        d = meta.to_dict()
        wieder = RecordingMetadata.from_dict(d)
        assert wieder.recording_id == "rec1"
        assert wieder.title == "Meine Aufnahme"
        assert wieder.created_at == "2024-06-01T12:00:00+00:00"

    def test_roundtrip_mit_branches(self):
        """Branches werden korrekt serialisiert und deserialisiert."""
        branch = Branch(
            branch_id="b1",
            recording_id="rec1",
            name="Original",
            is_original=True,
            duration=10.0,
        )
        meta = RecordingMetadata(
            recording_id="rec1",
            title="Test",
            created_at="2024-06-01T12:00:00+00:00",
            duration=10.0,
            branches=[branch],
            tags=["podcast", "test"],
            description="Beschreibung mit Ümlauten",
        )
        d = meta.to_dict()
        wieder = RecordingMetadata.from_dict(d)
        assert len(wieder.branches) == 1
        assert wieder.branches[0].is_original is True
        assert wieder.branches[0].duration == pytest.approx(10.0)
        assert wieder.tags == ["podcast", "test"]
        assert wieder.description == "Beschreibung mit Ümlauten"

    def test_to_dict_enthält_alle_schema_felder(self):
        """to_dict liefert alle Felder aus recording.schema.json."""
        meta = RecordingMetadata(
            recording_id="r", title="t", created_at="2024-01-01T00:00:00+00:00"
        )
        d = meta.to_dict()
        assert "recording_id" in d
        assert "title" in d
        assert "created_at" in d
        assert "duration" in d
        assert "sources" in d
        assert "branches" in d
        assert "tags" in d
        assert "description" in d

    def test_umlaute_in_title_erhalten(self):
        """Echte Umlaute in Titeln werden nicht escaped."""
        meta = RecordingMetadata(
            recording_id="r",
            title="Übung macht den Meister — Sonderzeichen äöü",
            created_at="2024-01-01T00:00:00+00:00",
        )
        d = meta.to_dict()
        wieder = RecordingMetadata.from_dict(d)
        assert wieder.title == "Übung macht den Meister — Sonderzeichen äöü"
