"""board.board_model — Board- und Pad-Datenmodell.

Keine GUI-Imports. Nur stdlib + dataclasses.

Kompatibel zu shared/workspace_v1.json (podcastpackages-workspace-v1, Version 1).
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional

# Literal-Konstanten aus workspace_v1.json
WORKSPACE_FORMAT = "podcastpackages-workspace-v1"
WORKSPACE_VERSION = 1


@dataclass
class Pad:
    """Repräsentiert ein einzelnes Board-Pad (Audio, Video oder Bild).

    Felder:
        id:         Eindeutige Pad-ID.
        label:      Anzeigename.
        color:      Hex-Farbe (CSS), Standard: blau.
        kind:       Pad-Typ: "audio" | "video" | "image".
        asset_path: Pfad zur Asset-Datei (WAV, MP4, Bild …).
        mode:       Wiedergabe-Modus: "play_stop" | "loop" | "overlap".
        hotkey:     Tastenkürzel (leer = keins).
        volume:     Lineare Lautstärke (1.0 = 0 dB). Nur für Audio-Pads.
    """
    id: str
    label: str = ""
    color: str = "#3b82f6"
    kind: str = "audio"       # "audio" | "video" | "image"
    asset_path: str = ""
    mode: str = "play_stop"   # "play_stop" | "loop" | "overlap"
    hotkey: str = ""
    volume: float = 1.0

    def to_dict(self) -> dict:
        """Serialisiert das Pad als dict.

        `volume` wird NICHT in den workspace_v1-Export geschrieben
        (Erweiterungsfeld; export_to_workspace filtert es heraus).
        Für load/save (eigenes JSON-Format) bleibt es erhalten.
        """
        return asdict(self)

    @classmethod
    def from_dict(cls, daten: dict) -> "Pad":
        """Erstellt ein Pad aus einem dict.

        Unbekannte Felder werden ignoriert (Vorwärts-Kompatibilität).
        """
        bekannte = set(cls.__dataclass_fields__)
        gefiltert = {k: v for k, v in daten.items() if k in bekannte}
        return cls(**gefiltert)


@dataclass
class Board:
    """Gemeinsames Audio-Videoboard mit gemischten Pad-Typen."""

    pads: list[Pad] = field(default_factory=list)

    def get(self, pad_id: str) -> Optional[Pad]:
        """Gibt ein Pad anhand seiner ID zurück (None wenn nicht gefunden)."""
        for pad in self.pads:
            if pad.id == pad_id:
                return pad
        return None

    def add(self, pad: Pad) -> None:
        """Fügt ein Pad hinzu (ersetzt vorhandenes Pad gleicher ID)."""
        for i, p in enumerate(self.pads):
            if p.id == pad.id:
                self.pads[i] = pad
                return
        self.pads.append(pad)

    def remove(self, pad_id: str) -> None:
        """Entfernt ein Pad anhand seiner ID (still, wenn nicht gefunden)."""
        self.pads = [p for p in self.pads if p.id != pad_id]


# ---------------------------------------------------------------------------
# Datei-I/O (eigenes Board-JSON-Format, nicht workspace_v1)
# ---------------------------------------------------------------------------

def load_board(path: str) -> Board:
    """Lädt ein Board aus einer JSON-Datei (eigenes Format mit 'pads'-Liste).

    Bei fehlender Datei oder Fehler: leeres Board.

    Args:
        path: Pfad zur JSON-Datei.

    Returns:
        Board mit geladenen Pads.
    """
    if not os.path.exists(path):
        return Board()

    try:
        with open(path, encoding="utf-8") as f:
            daten = json.load(f)
        pads = [Pad.from_dict(p) for p in daten.get("pads", [])]
        return Board(pads=pads)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        return Board()


def save_board(board: Board, path: str) -> None:
    """Speichert ein Board als UTF-8 JSON ohne BOM (atomic via Temp-Datei + Rename).

    Schreibt zunächst in eine temporäre Datei neben dem Ziel, dann per
    ``os.replace()`` atomar umbenannt. Verhindert korruptes Board-JSON
    bei einem vorzeitigen Absturz.

    Args:
        board: Zu speicherndes Board.
        path:  Zielpfad.
    """
    verzeichnis = os.path.dirname(path)
    if verzeichnis:
        os.makedirs(verzeichnis, exist_ok=True)

    daten = {"pads": [p.to_dict() for p in board.pads]}
    tmp_pfad = path + ".tmp"
    with open(tmp_pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_pfad, path)


# ---------------------------------------------------------------------------
# workspace_v1-Import/Export
# ---------------------------------------------------------------------------

def import_from_workspace(payload: dict) -> Board:
    """Erstellt ein Board aus einem workspace_v1-Payload.

    Liest ``payload["board"]["pads"]``.
    Felder, die workspace_v1 nicht kennt (z. B. ``volume``), erhalten
    ihre Pad-Standardwerte.

    Args:
        payload: Vollständiger workspace_v1-Payload als dict.

    Returns:
        Board mit den importierten Pads.
    """
    board_daten = payload.get("board") or {}
    roh_pads = board_daten.get("pads") or []
    pads = [Pad.from_dict(p) for p in roh_pads]
    return Board(pads=pads)


def export_to_workspace(board: Board) -> dict:
    """Exportiert ein Board als workspace_v1-konformes dict.

    Das Format entspricht exakt den Pflichtfeldern aus workspace_v1.json:
    ``{format, version, board:{pads}}``.

    ``volume`` (Erweiterungsfeld) wird NICHT in den Pad-Export übernommen,
    damit der Export schema-konform bleibt.

    Args:
        board: Zu exportierendes Board.

    Returns:
        workspace_v1-konformes dict.
    """
    # Nur schema-definierte Pad-Felder exportieren
    _schema_felder = {"id", "label", "color", "kind", "asset_path", "mode", "hotkey"}

    pads_export = []
    for pad in board.pads:
        pad_dict = pad.to_dict()
        pads_export.append({k: v for k, v in pad_dict.items() if k in _schema_felder})

    return {
        "format": WORKSPACE_FORMAT,
        "version": WORKSPACE_VERSION,
        "board": {"pads": pads_export},
    }
