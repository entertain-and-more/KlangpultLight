"""core.config — Anwendungskonfiguration (AppConfig, load_config, save_config).

Keine GUI-Imports. Nur stdlib + dataclasses.
"""
from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass


@dataclass
class AppConfig:
    """Zentrale Konfiguration des Klangpult light – Recorders.

    Alle Felder haben sinnvolle Standardwerte, sodass die App sofort
    ohne Konfigurationsdatei startet.
    """
    samplerate: int = 48000
    """Audio-Samplerate in Hz (Standard: 48 kHz)."""
    block_size: int = 1024
    """Anzahl Frames pro Audio-Block."""
    channels: int = 2
    """Anzahl Ausgangskanäle (Stereo = 2)."""
    workspace_dir: str = "./workspace"
    """Verzeichnis für Aufnahmen relativ zum Recorder-Root."""
    mock_audio: bool = False
    """Wenn True, wird synthetisches Audio statt Hardware verwendet."""


def load_config(path: str | None = None) -> AppConfig:
    """Lädt AppConfig aus einer JSON-Datei.

    Wenn die Datei nicht existiert, ein Verzeichnis ist oder der Pfad None ist, werden
    die Standardwerte von AppConfig zurückgegeben.

    Args:
        path: Pfad zur JSON-Konfigurationsdatei. None → Defaults.

    Returns:
        AppConfig mit den geladenen oder Standard-Werten.
    """
    if path is None or not os.path.isfile(path):
        return AppConfig()

    try:
        with open(path, encoding="utf-8") as f:
            daten = json.load(f)
        if not isinstance(daten, dict):
            return AppConfig()
        # Nur bekannte Felder übernehmen (zukünftige Felder ignorieren)
        bekannte_felder = {k for k in AppConfig.__dataclass_fields__}
        gefiltert = {k: v for k, v in daten.items() if k in bekannte_felder}
        return AppConfig(**gefiltert)
    except (json.JSONDecodeError, TypeError, ValueError, AttributeError, OSError):
        # Fehlerhafte Datei oder Schema-Drift → Defaults
        return AppConfig()


def save_config(cfg: AppConfig, path: str) -> None:
    """Speichert AppConfig als UTF-8 JSON ohne BOM (atomic via Temp-Datei + Rename).

    Schreibt zunächst in eine temporäre Datei mit PID-Suffix neben dem Ziel,
    hebt bei bestehenden schreibgeschützten Zieldateien unter Windows vorübergehend
    den Schreibschutz auf und benennt per ``os.replace()`` atomar um.

    Args:
        cfg: Zu speichernde Konfiguration.
        path: Zielpfad der JSON-Datei.
    """
    if os.path.isdir(path):
        raise IsADirectoryError(f"Zielpfad ist ein Verzeichnis: {path}")

    verzeichnis = os.path.dirname(path)
    if verzeichnis:
        os.makedirs(verzeichnis, exist_ok=True)

    tmp_pfad = f"{path}.tmp.{os.getpid()}"
    try:
        with open(tmp_pfad, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())

        # Windows-Schreibschutz-Resilienz (ReadOnly-Overwrite Schutz)
        if os.path.exists(path):
            try:
                os.chmod(path, stat.S_IWRITE)
            except OSError:
                pass

        os.replace(tmp_pfad, path)
    except Exception:
        if os.path.exists(tmp_pfad):
            try:
                os.unlink(tmp_pfad)
            except OSError:
                pass
        raise
