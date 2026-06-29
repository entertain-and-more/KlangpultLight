"""sources.source_config — Quellen-Config-Modell (SourceEntry, SourcesConfig, load/save).

Keine GUI-Imports. Nur stdlib + dataclasses.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class SourceEntry:
    """Eine einzelne Aufnahmequelle (Mikrofon, Systemton, Line-In, Video).

    Felder:
        source_id:      Eindeutiger Bezeichner (z. B. "mic_1", "system").
        name:           Anzeigename in der UI.
        kind:           Art der Quelle: "mic" | "system" | "line" | "video".
        enabled:        Quelle ist sichtbar und nutzbar.
        capture:        Quelle wird mitgeschnitten.
        device_index:   Gebundener sounddevice-Index (None = automatisch).
        gain:           Eingangsverstärkung (1.0 = 0 dB).
        capture_method: Aufnahmeverfahren bei Systemton
                        ("wasapi_loopback" | "input_device" | None).
        notes:          Freitext-Notizen (z. B. Konfigurationshinweise).
    """
    source_id: str
    name: str
    kind: str  # "mic" | "system" | "line" | "video"
    enabled: bool = True
    capture: bool = True
    device_index: Optional[int] = None
    gain: float = 1.0
    capture_method: Optional[str] = None
    notes: str = ""

    def to_dict(self) -> dict:
        """Serialisiert den Eintrag als dict (für JSON-Persistenz)."""
        return asdict(self)

    @classmethod
    def from_dict(cls, daten: dict) -> "SourceEntry":
        """Erstellt einen SourceEntry aus einem dict.

        Unbekannte Felder werden ignoriert (Vorwärts-Kompatibilität).
        """
        bekannte = {f for f in cls.__dataclass_fields__}
        gefiltert = {k: v for k, v in daten.items() if k in bekannte}
        return cls(**gefiltert)


@dataclass
class SourcesConfig:
    """Gesamte Quellen-Konfiguration einer Session.

    Enthält eine geordnete Liste aller SourceEntry-Objekte.
    """
    sources: list[SourceEntry] = field(default_factory=list)

    def enabled_sources(self) -> list[SourceEntry]:
        """Gibt alle Quellen zurück, die aktiviert sind (enabled=True)."""
        return [e for e in self.sources if e.enabled]

    def capture_sources(self) -> list[SourceEntry]:
        """Gibt alle Quellen zurück, die enabled=True UND capture=True sind."""
        return [e for e in self.sources if e.enabled and e.capture]

    def get(self, source_id: str) -> Optional[SourceEntry]:
        """Sucht einen Eintrag anhand der source_id.

        Returns:
            SourceEntry wenn gefunden, sonst None.
        """
        for eintrag in self.sources:
            if eintrag.source_id == source_id:
                return eintrag
        return None

    def set_capture(self, source_id: str, value: bool) -> None:
        """Setzt das capture-Flag einer Quelle.

        Unbekannte source_id wird still ignoriert.
        """
        eintrag = self.get(source_id)
        if eintrag is not None:
            eintrag.capture = value

    def set_device_index(self, source_id: str, device_index: Optional[int]) -> None:
        """Setzt das gebundene Audio-Gerät einer Quelle.

        ``None`` bedeutet automatische Belegung durch DeviceManager.
        Unbekannte source_id wird still ignoriert.
        """
        eintrag = self.get(source_id)
        if eintrag is not None:
            eintrag.device_index = device_index

    def to_dict(self) -> dict:
        """Serialisiert die gesamte Konfiguration als dict."""
        return {"sources": [e.to_dict() for e in self.sources]}

    @classmethod
    def from_dict(cls, daten: dict) -> "SourcesConfig":
        """Erstellt SourcesConfig aus einem dict.

        Unbekannte Felder auf SourceEntry-Ebene werden ignoriert.
        """
        eintraege = [
            SourceEntry.from_dict(e) for e in daten.get("sources", [])
        ]
        return cls(sources=eintraege)


def _default_sources_config() -> SourcesConfig:
    """Erzeugt eine sinnvolle Standard-Konfiguration ohne Datei."""
    return SourcesConfig(sources=[
        SourceEntry(
            source_id="mic_1",
            name="Mikrofon 1",
            kind="mic",
            enabled=True,
            capture=True,
            notes="",
        ),
        SourceEntry(
            source_id="mic_2",
            name="Mikrofon 2",
            kind="mic",
            enabled=True,
            capture=True,
            notes="",
        ),
        SourceEntry(
            source_id="system",
            name="Systemton",
            kind="system",
            enabled=True,
            # capture=False bis ein Loopback-Weg bestätigt wurde (Faktentreue-Regel)
            capture=False,
            notes="Loopback noch nicht konfiguriert.",
        ),
    ])


def load_sources_config(path: Optional[str]) -> SourcesConfig:
    """Lädt SourcesConfig aus einer JSON-Datei.

    Wenn path None ist oder die Datei nicht existiert, werden sinnvolle
    Standardwerte zurückgegeben (mic_1/mic_2 capture=True, system capture=False).

    Args:
        path: Pfad zur JSON-Datei oder None.

    Returns:
        SourcesConfig mit geladenen oder Standard-Werten.
    """
    if path is None or not os.path.exists(path):
        return _default_sources_config()

    try:
        with open(path, encoding="utf-8") as f:
            daten = json.load(f)
        return SourcesConfig.from_dict(daten)
    except (json.JSONDecodeError, TypeError, ValueError, KeyError):
        # Fehlerhafte Datei → Defaults
        return _default_sources_config()


def save_sources_config(cfg: SourcesConfig, path: str) -> None:
    """Speichert SourcesConfig als UTF-8 JSON ohne BOM (atomic via Temp-Datei + Rename).

    Schreibt zunächst in eine temporäre Datei neben dem Ziel, dann per
    ``os.replace()`` atomar umbenannt. Dadurch bleibt die bestehende Datei
    bei einem vorzeitigen Absturz unverändert (kein truncated JSON).

    Args:
        cfg:  Zu speichernde Konfiguration.
        path: Zielpfad der JSON-Datei.
    """
    verzeichnis = os.path.dirname(path)
    if verzeichnis:
        os.makedirs(verzeichnis, exist_ok=True)

    tmp_pfad = path + ".tmp"
    with open(tmp_pfad, "w", encoding="utf-8") as f:
        json.dump(cfg.to_dict(), f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_pfad, path)
