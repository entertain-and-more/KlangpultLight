"""recordings.models — Datenmodelle für Aufnahmen und Branches.

Passend zu shared/branch.schema.json und shared/recording.schema.json.
Kein GUI-Import. Nur stdlib + dataclasses.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Branch:
    """Ein Branch einer Aufnahme.

    Das Original (is_original=True) wird nie überschrieben.
    Felder passend zu shared/branch.schema.json.
    """
    branch_id: str
    recording_id: str
    name: str
    created_at: str = ""
    audio_path: str = ""
    video_path: str = ""
    duration: float = 0.0
    is_original: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serialisiert den Branch als Dictionary."""
        return {
            "branch_id": self.branch_id,
            "recording_id": self.recording_id,
            "name": self.name,
            "created_at": self.created_at,
            "audio_path": self.audio_path,
            "video_path": self.video_path,
            "duration": self.duration,
            "is_original": self.is_original,
        }

    @classmethod
    def from_dict(cls, daten: dict[str, Any]) -> "Branch":
        """Deserialisiert einen Branch aus einem Dictionary."""
        return cls(
            branch_id=daten["branch_id"],
            recording_id=daten["recording_id"],
            name=daten["name"],
            created_at=daten.get("created_at", ""),
            audio_path=daten.get("audio_path", ""),
            video_path=daten.get("video_path", ""),
            duration=float(daten.get("duration", 0.0)),
            is_original=bool(daten.get("is_original", False)),
        )


@dataclass
class RecordingMetadata:
    """Metadaten einer Aufnahme.

    Das Original ist unveränderlich; Bearbeitungen entstehen als Branches.
    Felder passend zu shared/recording.schema.json.
    """
    recording_id: str
    title: str
    created_at: str
    duration: float = 0.0
    sources: list[dict[str, Any]] = field(default_factory=list)
    branches: list[Branch] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialisiert die Metadaten als Dictionary (JSON-kompatibel)."""
        return {
            "recording_id": self.recording_id,
            "title": self.title,
            "created_at": self.created_at,
            "duration": self.duration,
            "sources": list(self.sources),
            "branches": [b.to_dict() for b in self.branches],
            "tags": list(self.tags),
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, daten: dict[str, Any]) -> "RecordingMetadata":
        """Deserialisiert Metadaten aus einem Dictionary.

        Listenfelder (branches, sources, tags) können in korrupten oder
        extern erzeugten JSON-Dateien als ``null`` vorliegen.
        In diesem Fall wird eine leere Liste als Default verwendet.
        """
        branches_roh = daten.get("branches") or []
        branches = [Branch.from_dict(b) for b in branches_roh]
        return cls(
            recording_id=daten["recording_id"],
            title=daten["title"],
            created_at=daten["created_at"],
            duration=float(daten.get("duration", 0.0)),
            sources=list(daten.get("sources") or []),
            branches=branches,
            tags=list(daten.get("tags") or []),
            description=daten.get("description", ""),
        )
