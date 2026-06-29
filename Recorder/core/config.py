"""core.config — Anwendungskonfiguration (AppConfig, load_config, save_config).

Keine GUI-Imports. Nur stdlib + dataclasses.
"""
import json
import os
from dataclasses import dataclass, asdict


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

    Wenn die Datei nicht existiert oder der Pfad None ist, werden
    die Standardwerte von AppConfig zurückgegeben.

    Args:
        path: Pfad zur JSON-Konfigurationsdatei. None → Defaults.

    Returns:
        AppConfig mit den geladenen oder Standard-Werten.
    """
    if path is None or not os.path.exists(path):
        return AppConfig()

    try:
        with open(path, encoding="utf-8") as f:
            daten = json.load(f)
        # Nur bekannte Felder übernehmen (zukünftige Felder ignorieren)
        bekannte_felder = {k for k in AppConfig.__dataclass_fields__}
        gefiltert = {k: v for k, v in daten.items() if k in bekannte_felder}
        return AppConfig(**gefiltert)
    except (json.JSONDecodeError, TypeError, ValueError):
        # Fehlerhafte Datei → Defaults
        return AppConfig()


def save_config(cfg: AppConfig, path: str) -> None:
    """Speichert AppConfig als UTF-8 JSON ohne BOM (atomic via Temp-Datei + Rename).

    Schreibt zunächst in eine temporäre Datei neben dem Ziel, dann per
    ``os.replace()`` atomar umbenannt. Verhindert korrupte Konfiguration
    bei einem vorzeitigen Absturz.

    Args:
        cfg: Zu speichernde Konfiguration.
        path: Zielpfad der JSON-Datei.
    """
    verzeichnis = os.path.dirname(path)
    if verzeichnis:
        os.makedirs(verzeichnis, exist_ok=True)

    tmp_pfad = path + ".tmp"
    with open(tmp_pfad, "w", encoding="utf-8") as f:
        json.dump(asdict(cfg), f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_pfad, path)
