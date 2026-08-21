"""bridge.projects_api — HTTP-Dienst für die Projektplanung (Planer-Backend).

Stellt folgende Endpunkte bereit (HTTP, JSON-Antworten):
    GET    /api/health                        → {"status": "ok"}
    GET    /api/projects                      → {"projects": [...]}
    POST   /api/projects                      → Projekt anlegen → 201 + Projekt-Objekt
    GET    /api/projects/{id}                 → einzelnes Projekt
    PUT    /api/projects/{id}                 → Projekt aktualisieren
    DELETE /api/projects/{id}                 → Projekt löschen → 204
    GET    /api/projects/{id}/episodes        → {"episodes": [...]}
    POST   /api/projects/{id}/episodes        → Episode anlegen → 201 + Episode-Objekt

Persistenz: JSON-Dateien in ``data_dir/`` (UTF-8 ohne BOM).
    data_dir/projects.json     — alle Projekte
    data_dir/episodes_{id}.json — Episoden je Projekt

Wird in einem eigenen Thread betrieben (ThreadingHTTPServer).
Sauberes Herunterfahren via stop() — kein Orphan-Thread.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional
from urllib.parse import urlparse

_log = logging.getLogger(__name__)

# Regulärer Ausdruck für Projekt-Pfade
_RE_PROJEKT = re.compile(r"^/api/projects/([^/]+)$")
_RE_EPISODEN = re.compile(r"^/api/projects/([^/]+)/episodes$")
_RE_EPISODE = re.compile(r"^/api/projects/([^/]+)/episodes/([^/]+)$")
_RE_PROJEKT_RECORDING = re.compile(r"^/api/projects/([^/]+)/recordings/([^/]+)$")
_RE_ASSETS = re.compile(r"^/api/projects/([^/]+)/assets$")
_RE_ASSET = re.compile(r"^/api/projects/([^/]+)/assets/([^/]+)$")
_RE_LINE = re.compile(r"^/api/projects/([^/]+)/line$")
_RE_WORKSPACE = re.compile(r"^/api/projects/([^/]+)/workspace$")
_RE_WORKSPACE_IMPORT = re.compile(r"^/api/projects/([^/]+)/workspace/import$")
_RE_TELEPROMPTER = re.compile(r"^/api/projects/([^/]+)/teleprompter$")
_RE_MONITOR = re.compile(r"^/api/projects/([^/]+)/monitor$")
_RE_MONITOR_ANALYZE = re.compile(r"^/api/projects/([^/]+)/monitor/analyze$")


# ---------------------------------------------------------------------------
# Dateipersistenz (UTF-8 JSON ohne BOM)
# ---------------------------------------------------------------------------

def _json_lesen(pfad: Path) -> list | dict:
    """Liest JSON aus einer Datei; gibt leere Liste/Dict zurück bei Fehler."""
    try:
        with open(pfad, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _json_schreiben(pfad: Path, daten) -> None:
    """Schreibt daten als UTF-8 JSON ohne BOM (atomic via Temp-Datei + Rename).

    Schreibt zunächst in eine temporäre Datei neben der Zieldatei, dann wird
    per ``os.replace()`` atomar umbenannt. Dadurch bleibt die bestehende Datei
    bei einem vorzeitigen Absturz unverändert (kein truncated JSON).
    """
    pfad.parent.mkdir(parents=True, exist_ok=True)
    tmp_pfad = pfad.with_suffix(pfad.suffix + ".tmp")
    with open(tmp_pfad, "w", encoding="utf-8") as f:
        json.dump(daten, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_pfad, pfad)  # auf POSIX/Windows atomar genug für Einzelprozess


# ---------------------------------------------------------------------------
# Projektverwaltung (threadsicherer Zugriff über Lock)
# ---------------------------------------------------------------------------

class _ProjektStore:
    """Verwaltet Projekte und Episoden auf dem Dateisystem.

    Alle öffentlichen Methoden sind threadsicher (interner Lock).
    Datenformat: Liste von Dicts in JSON-Dateien.
    """

    def __init__(self, data_dir: str) -> None:
        self._dir = Path(data_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._projekte_pfad = self._dir / "projects.json"
        self._lock = threading.Lock()

    # -- Projekte --

    def _projekte_lesen(self) -> list[dict]:
        daten = _json_lesen(self._projekte_pfad)
        if isinstance(daten, list):
            return daten
        return []

    def _projekte_schreiben(self, projekte: list[dict]) -> None:
        _json_schreiben(self._projekte_pfad, projekte)

    def liste_projekte(self) -> list[dict]:
        with self._lock:
            return list(self._projekte_lesen())

    def _projekt_holen_nolock(self, project_id: str) -> Optional[dict]:
        """Gibt das Projekt zurück (ohne Lock — muss innerhalb von with self._lock aufgerufen werden)."""
        for p in self._projekte_lesen():
            if p.get("project_id") == project_id:
                return dict(p)
        return None

    def projekt_anlegen(self, title: str, description: str = "") -> dict:
        jetzt = datetime.now(timezone.utc).isoformat()
        projekt = {
            "project_id": str(uuid.uuid4()),
            "title": title,
            "description": description,
            "created_at": jetzt,
            "updated_at": jetzt,
        }
        with self._lock:
            projekte = self._projekte_lesen()
            projekte.append(projekt)
            self._projekte_schreiben(projekte)
        return projekt

    def projekt_holen(self, project_id: str) -> Optional[dict]:
        with self._lock:
            return self._projekt_holen_nolock(project_id)

    def projekt_aktualisieren(self, project_id: str, title: str, description: str = "") -> Optional[dict]:
        with self._lock:
            projekte = self._projekte_lesen()
            for p in projekte:
                if p.get("project_id") == project_id:
                    p["title"] = title
                    p["description"] = description
                    p["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._projekte_schreiben(projekte)
                    return dict(p)
        return None

    def projekt_loeschen(self, project_id: str) -> bool:
        with self._lock:
            projekte = self._projekte_lesen()
            neu = [p for p in projekte if p.get("project_id") != project_id]
            if len(neu) == len(projekte):
                return False  # nicht gefunden
            self._projekte_schreiben(neu)
            # Zugehörige Dateien ebenfalls löschen
            ep_pfad = self._episoden_pfad(project_id)
            if ep_pfad.exists():
                ep_pfad.unlink()
            assets_pfad = self._assets_pfad(project_id)
            if assets_pfad.exists():
                assets_pfad.unlink()
            line_pfad = self._line_pfad(project_id)
            if line_pfad.exists():
                line_pfad.unlink()
            tp_pfad = self._teleprompter_pfad(project_id)
            if tp_pfad.exists():
                tp_pfad.unlink()
            mon_pfad = self._monitor_pfad(project_id)
            if mon_pfad.exists():
                mon_pfad.unlink()
        return True

    # -- Episoden --

    def _episoden_pfad(self, project_id: str) -> Path:
        return self._dir / f"episodes_{project_id}.json"

    def _episoden_lesen(self, project_id: str) -> list[dict]:
        daten = _json_lesen(self._episoden_pfad(project_id))
        if isinstance(daten, list):
            return daten
        return []

    def liste_episoden(self, project_id: str) -> Optional[list[dict]]:
        """Gibt None zurück wenn das Projekt nicht existiert."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            return list(self._episoden_lesen(project_id))

    def episode_anlegen(
        self,
        project_id: str,
        title: str,
        notes: str = "",
        status: str = "geplant",
    ) -> Optional[dict]:
        """Gibt None zurück wenn das Projekt nicht existiert."""
        jetzt = datetime.now(timezone.utc).isoformat()
        episode = {
            "episode_id": str(uuid.uuid4()),
            "project_id": project_id,
            "title": title,
            "notes": notes,
            "status": status,
            "created_at": jetzt,
        }
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            episoden = self._episoden_lesen(project_id)
            episoden.append(episode)
            _json_schreiben(self._episoden_pfad(project_id), episoden)
        return episode

    def episode_aktualisieren(
        self, project_id: str, episode_id: str, title: str,
        notes: str = "", status: str = "geplant",
    ) -> Optional[dict]:
        """Aktualisiert eine Episode. None, wenn Projekt/Episode fehlt."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            episoden = self._episoden_lesen(project_id)
            for ep in episoden:
                if ep.get("episode_id") == episode_id:
                    ep["title"] = title
                    ep["notes"] = notes
                    ep["status"] = status
                    ep["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _json_schreiben(self._episoden_pfad(project_id), episoden)
                    return ep
            return None

    def episode_loeschen(self, project_id: str, episode_id: str) -> bool:
        """Löscht eine Episode. False, wenn Projekt/Episode fehlt."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return False
            episoden = self._episoden_lesen(project_id)
            neu = [e for e in episoden if e.get("episode_id") != episode_id]
            if len(neu) == len(episoden):
                return False
            _json_schreiben(self._episoden_pfad(project_id), neu)
            return True

    # -- Aufnahmen-Zuordnung (recording_ids je Projekt) --

    def aufnahme_zuordnen(self, project_id: str, recording_id: str) -> Optional[dict]:
        """Ordnet eine Aufnahme einem Projekt zu (idempotent). None wenn Projekt fehlt."""
        with self._lock:
            projekte = self._projekte_lesen()
            for p in projekte:
                if p.get("project_id") == project_id:
                    ids = list(p.get("recording_ids") or [])
                    if recording_id not in ids:
                        ids.append(recording_id)
                    p["recording_ids"] = ids
                    p["updated_at"] = datetime.now(timezone.utc).isoformat()
                    self._projekte_schreiben(projekte)
                    return p
            return None

    def aufnahme_entfernen(self, project_id: str, recording_id: str) -> Optional[dict]:
        """Entfernt die Zuordnung einer Aufnahme. None wenn Projekt fehlt."""
        with self._lock:
            projekte = self._projekte_lesen()
            for p in projekte:
                if p.get("project_id") == project_id:
                    p["recording_ids"] = [
                        r for r in (p.get("recording_ids") or []) if r != recording_id
                    ]
                    self._projekte_schreiben(projekte)
                    return p
            return None

    # -- Assets (Board-Pads) --

    def _assets_pfad(self, project_id: str) -> Path:
        return self._dir / f"assets_{project_id}.json"

    def _assets_lesen(self, project_id: str) -> list[dict]:
        daten = _json_lesen(self._assets_pfad(project_id))
        if isinstance(daten, list):
            return daten
        return []

    def liste_assets(self, project_id: str) -> Optional[list[dict]]:
        """Gibt None zurück, wenn das Projekt nicht existiert."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            return list(self._assets_lesen(project_id))

    def asset_anlegen(
        self,
        project_id: str,
        label: str,
        kind: str = "audio",
        asset_path: str = "",
        color: str = "#3b82f6",
        mode: str = "play_stop",
        hotkey: str = "",
        volume: float = 1.0,
        asset_id: Optional[str] = None,
    ) -> Optional[dict]:
        """Legt ein Asset an oder aktualisiert ein vorhandenes mit gleicher ID. None wenn Projekt fehlt."""
        if kind not in {"audio", "video", "image"}:
            kind = "audio"
        if mode not in {"play_stop", "loop", "overlap"}:
            mode = "play_stop"
        jetzt = datetime.now(timezone.utc).isoformat()
        aid = asset_id if asset_id and str(asset_id).strip() else str(uuid.uuid4())
        asset = {
            "id": aid,
            "project_id": project_id,
            "label": label,
            "kind": kind,
            "asset_path": asset_path,
            "color": color or "#3b82f6",
            "mode": mode,
            "hotkey": hotkey or "",
            "volume": float(volume),
            "created_at": jetzt,
            "updated_at": jetzt,
        }
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            assets = self._assets_lesen(project_id)
            replaced = False
            for i, a in enumerate(assets):
                if a.get("id") == aid:
                    asset["created_at"] = a.get("created_at", jetzt)
                    assets[i] = asset
                    replaced = True
                    break
            if not replaced:
                assets.append(asset)
            _json_schreiben(self._assets_pfad(project_id), assets)
        return asset

    def asset_aktualisieren(
        self,
        project_id: str,
        asset_id: str,
        label: str,
        kind: str = "audio",
        asset_path: str = "",
        color: str = "#3b82f6",
        mode: str = "play_stop",
        hotkey: str = "",
        volume: float = 1.0,
    ) -> Optional[dict]:
        """Aktualisiert ein Asset. None wenn Projekt oder Asset fehlt."""
        if kind not in {"audio", "video", "image"}:
            kind = "audio"
        if mode not in {"play_stop", "loop", "overlap"}:
            mode = "play_stop"
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            assets = self._assets_lesen(project_id)
            for a in assets:
                if a.get("id") == asset_id:
                    a["label"] = label
                    a["kind"] = kind
                    a["asset_path"] = asset_path
                    a["color"] = color or "#3b82f6"
                    a["mode"] = mode
                    a["hotkey"] = hotkey or ""
                    a["volume"] = float(volume)
                    a["updated_at"] = datetime.now(timezone.utc).isoformat()
                    _json_schreiben(self._assets_pfad(project_id), assets)
                    return dict(a)
        return None

    def asset_loeschen(self, project_id: str, asset_id: str) -> bool:
        """Löscht ein Asset und entfernt es aus der Line. False wenn nicht gefunden."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return False
            assets = self._assets_lesen(project_id)
            neu = [a for a in assets if a.get("id") != asset_id]
            if len(neu) == len(assets):
                return False
            _json_schreiben(self._assets_pfad(project_id), neu)

            line = self._line_lesen(project_id)
            if asset_id in line:
                neu_line = [x for x in line if x != asset_id]
                _json_schreiben(self._line_pfad(project_id), neu_line)
        return True

    # -- Line (Einspieler-Reihenfolge) --

    def _line_pfad(self, project_id: str) -> Path:
        return self._dir / f"line_{project_id}.json"

    def _line_lesen(self, project_id: str) -> list[str]:
        daten = _json_lesen(self._line_pfad(project_id))
        if isinstance(daten, list):
            return [str(x) for x in daten if str(x).strip()]
        return []

    def hole_line(self, project_id: str) -> Optional[list[str]]:
        """Gibt die Line-Reihenfolge zurück. None wenn Projekt fehlt."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            return list(self._line_lesen(project_id))

    def speichere_line(self, project_id: str, line: list[str]) -> Optional[list[str]]:
        """Speichert die Line-Reihenfolge. None wenn Projekt fehlt."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            saubere_line = [str(x) for x in line if str(x).strip()]
            _json_schreiben(self._line_pfad(project_id), saubere_line)
            return saubere_line

    # -- Teleprompter --

    def _teleprompter_pfad(self, project_id: str) -> Path:
        return self._dir / f"teleprompter_{project_id}.json"

    def _teleprompter_lesen(self, project_id: str) -> dict:
        daten = _json_lesen(self._teleprompter_pfad(project_id))
        default = {
            "project_id": project_id,
            "text": "",
            "font_size": 24,
            "scroll_speed": 1.0,
            "mode": "manual",
            "current_line": 0,
            "mirror": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(daten, dict):
            default.update(daten)
        return default

    def hole_teleprompter(self, project_id: str) -> Optional[dict]:
        """Gibt Teleprompter-Daten zurück. None wenn Projekt nicht existiert."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            return dict(self._teleprompter_lesen(project_id))

    def speichere_teleprompter(self, project_id: str, daten: dict) -> Optional[dict]:
        """Aktualisiert Teleprompter-Daten. None wenn Projekt nicht existiert."""
        if not isinstance(daten, dict):
            raise ValueError("Daten müssen ein JSON-Objekt sein")
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            aktuell = self._teleprompter_lesen(project_id)
            jetzt = datetime.now(timezone.utc).isoformat()
            if "text" in daten:
                aktuell["text"] = str(daten["text"])
            if "font_size" in daten:
                try:
                    aktuell["font_size"] = max(8, int(daten["font_size"]))
                except (ValueError, TypeError):
                    pass
            if "scroll_speed" in daten:
                try:
                    aktuell["scroll_speed"] = max(0.1, float(daten["scroll_speed"]))
                except (ValueError, TypeError):
                    pass
            if "mode" in daten:
                mode = str(daten["mode"])
                if mode in {"manual", "time", "speech", "hybrid"}:
                    aktuell["mode"] = mode
            if "current_line" in daten:
                try:
                    aktuell["current_line"] = max(0, int(daten["current_line"]))
                except (ValueError, TypeError):
                    pass
            if "mirror" in daten:
                aktuell["mirror"] = bool(daten["mirror"])
            aktuell["updated_at"] = jetzt
            _json_schreiben(self._teleprompter_pfad(project_id), aktuell)
            return dict(aktuell)

    # -- KI-Monitor --

    def _monitor_pfad(self, project_id: str) -> Path:
        return self._dir / f"monitor_{project_id}.json"

    def _monitor_lesen(self, project_id: str) -> dict:
        daten = _json_lesen(self._monitor_pfad(project_id))
        default = {
            "project_id": project_id,
            "briefing": "",
            "keywords": [],
            "cards": [],
            "cloud_opt_in": False,
            "web_search": False,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        if isinstance(daten, dict):
            default.update(daten)
        return default

    def hole_monitor(self, project_id: str) -> Optional[dict]:
        """Gibt KI-Monitor-Daten zurück. None wenn Projekt nicht existiert."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            return dict(self._monitor_lesen(project_id))

    def speichere_monitor(self, project_id: str, daten: dict) -> Optional[dict]:
        """Aktualisiert KI-Monitor-Daten. None wenn Projekt nicht existiert."""
        if not isinstance(daten, dict):
            raise ValueError("Daten müssen ein JSON-Objekt sein")
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            aktuell = self._monitor_lesen(project_id)
            jetzt = datetime.now(timezone.utc).isoformat()
            if "briefing" in daten:
                aktuell["briefing"] = str(daten["briefing"])
            if "keywords" in daten and isinstance(daten["keywords"], list):
                aktuell["keywords"] = [str(k) for k in daten["keywords"] if str(k).strip()]
            if "cards" in daten and isinstance(daten["cards"], list):
                aktuell["cards"] = daten["cards"]
            if "cloud_opt_in" in daten:
                aktuell["cloud_opt_in"] = bool(daten["cloud_opt_in"])
            if "web_search" in daten:
                aktuell["web_search"] = bool(daten["web_search"])
            aktuell["updated_at"] = jetzt
            _json_schreiben(self._monitor_pfad(project_id), aktuell)
            return dict(aktuell)

    def monitor_analysieren(
        self,
        project_id: str,
        transcript_text: str,
        context: Optional[dict] = None,
    ) -> Optional[dict]:
        """Analysiert Live-Transkriptionstext lokal gegen Briefing und Kontext.

        Erzeugt strukturierte Assistenz-Karten (Fakten, Nachfragen, Kapitelmarker, Zusammenfassung).
        Vollständig offline / lokal ohne externe Abhängigkeiten.
        """
        with self._lock:
            projekt = self._projekt_holen_nolock(project_id)
            if projekt is None:
                return None
            monitor = self._monitor_lesen(project_id)

        briefing = monitor.get("briefing", "") or projekt.get("description", "")
        keywords = list(monitor.get("keywords") or [])
        text = str(transcript_text).strip()
        if not text:
            return {
                "status": "empty",
                "cards": [],
                "keywords_detected": [],
                "engine": "local_rules",
            }

        # Lokale Heuristik / Regelanalyse
        detected_keywords = []
        words = re.findall(r"\b[a-zA-ZäöüÄÖÜß]{4,}\b", text)
        for w in words:
            w_lower = w.lower()
            if any(w_lower == k.lower() for k in keywords) and not any(w_lower == d.lower() for d in detected_keywords):
                detected_keywords.append(w)

        cards = []
        jetzt = datetime.now(timezone.utc).isoformat()

        # 1. Fact / Keyword-Card
        if detected_keywords:
            kw_str = ", ".join(detected_keywords[:3])
            briefing_hint = f" ({briefing[:60]}...)" if briefing else ""
            cards.append({
                "id": str(uuid.uuid4()),
                "type": "fact_check",
                "title": f"Schlüsselbegriff: {kw_str}",
                "content": f"Erwähnung im Kontext{briefing_hint}: »{text[:120]}...«",
                "created_at": jetzt,
            })

        # 2. Moderations- / Nachfrage-Impuls
        if len(text.split()) >= 4:
            cards.append({
                "id": str(uuid.uuid4()),
                "type": "followup_question",
                "title": "Nachfrage-Impuls für Moderation",
                "content": f"Wie ordnet sich »{text[:80]}...« in das Thema »{projekt.get('title', '')}« ein?",
                "created_at": jetzt,
            })

        # 3. Kapitelmarker-Vorschlag
        marker_triggers = ["kapitel", "thema", "nächster punkt", "kommen wir zu", "als nächstes", "abschließend", "willkommen"]
        if any(trig in text.lower() for trig in marker_triggers) or len(text) > 80:
            label_candidate = text[:40].strip()
            cards.append({
                "id": str(uuid.uuid4()),
                "type": "chapter_suggestion",
                "title": "Kapitelmarker-Vorschlag",
                "label": label_candidate,
                "content": f"Vorschlag für Marker: »{label_candidate}«",
                "created_at": jetzt,
            })

        # 4. Zusammenfassungs-Stichpunkt
        cards.append({
            "id": str(uuid.uuid4()),
            "type": "summary_bullet",
            "title": "Kernaussage",
            "content": text[:150],
            "created_at": jetzt,
        })

        return {
            "status": "ok",
            "cards": cards,
            "keywords_detected": detected_keywords,
            "engine": "local_rules",
            "cloud_opt_in": monitor.get("cloud_opt_in", False),
            "web_search": monitor.get("web_search", False),
        }

    # -- Workspace-v1 Export / Import --

    def workspace_exportieren(self, project_id: str) -> Optional[dict]:
        """Exportiert Assets, Line und Teleprompter als valides klangpultlight-workspace-v1 Payload."""
        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None
            assets = self._assets_lesen(project_id)
            line = self._line_lesen(project_id)
            teleprompter_data = self._teleprompter_lesen(project_id)
            pads = []
            for a in assets:
                pad = {
                    "id": a.get("id", ""),
                    "label": a.get("label", ""),
                    "color": a.get("color", "#3b82f6"),
                    "kind": a.get("kind", "audio"),
                    "asset_path": a.get("asset_path", ""),
                    "mode": a.get("mode", "play_stop"),
                    "hotkey": a.get("hotkey", ""),
                }
                pads.append(pad)
            return {
                "format": "klangpultlight-workspace-v1",
                "version": 1,
                "board": {"pads": pads},
                "line": line,
                "teleprompter": {
                    "text": teleprompter_data.get("text", ""),
                    "font_size": teleprompter_data.get("font_size", 24),
                    "scroll_speed": teleprompter_data.get("scroll_speed", 1.0),
                    "mode": teleprompter_data.get("mode", "manual"),
                },
            }

    def workspace_importieren(self, project_id: str, payload: dict) -> Optional[dict]:
        """Importiert ein klangpultlight-workspace-v1 Payload in das Projekt."""
        if not isinstance(payload, dict):
            raise ValueError("Payload muss ein JSON-Objekt sein")
        if payload.get("format") != "klangpultlight-workspace-v1":
            raise ValueError(f"Format muss 'klangpultlight-workspace-v1' sein, erhalten: {payload.get('format')!r}")
        version = payload.get("version")
        if not isinstance(version, int) or version < 1:
            raise ValueError(f"Version muss ein Integer >= 1 sein, erhalten: {version!r}")

        with self._lock:
            if self._projekt_holen_nolock(project_id) is None:
                return None

            board_daten = payload.get("board") or {}
            roh_pads = board_daten.get("pads") or []
            jetzt = datetime.now(timezone.utc).isoformat()

            neue_assets = []
            for p in roh_pads:
                if not isinstance(p, dict) or not p.get("id"):
                    continue
                kind = p.get("kind", "audio")
                if kind not in {"audio", "video", "image"}:
                    kind = "audio"
                mode = p.get("mode", "play_stop")
                if mode not in {"play_stop", "loop", "overlap"}:
                    mode = "play_stop"
                neue_assets.append({
                    "id": str(p["id"]),
                    "project_id": project_id,
                    "label": str(p.get("label", "")),
                    "kind": kind,
                    "asset_path": str(p.get("asset_path", "")),
                    "color": str(p.get("color", "#3b82f6")),
                    "mode": mode,
                    "hotkey": str(p.get("hotkey", "")),
                    "volume": float(p.get("volume", 1.0)),
                    "created_at": jetzt,
                    "updated_at": jetzt,
                })
            _json_schreiben(self._assets_pfad(project_id), neue_assets)

            roh_line = payload.get("line") or []
            neue_line = [str(x) for x in roh_line if str(x).strip()]
            _json_schreiben(self._line_pfad(project_id), neue_line)

            tele_payload = payload.get("teleprompter")
            if isinstance(tele_payload, dict):
                aktuell_tele = self._teleprompter_lesen(project_id)
                if "text" in tele_payload:
                    aktuell_tele["text"] = str(tele_payload["text"])
                if "font_size" in tele_payload:
                    try:
                        aktuell_tele["font_size"] = max(8, int(tele_payload["font_size"]))
                    except (ValueError, TypeError):
                        pass
                if "scroll_speed" in tele_payload:
                    try:
                        aktuell_tele["scroll_speed"] = max(0.1, float(tele_payload["scroll_speed"]))
                    except (ValueError, TypeError):
                        pass
                if "mode" in tele_payload and str(tele_payload["mode"]) in {"manual", "time", "speech", "hybrid"}:
                    aktuell_tele["mode"] = str(tele_payload["mode"])
                aktuell_tele["updated_at"] = jetzt
                _json_schreiben(self._teleprompter_pfad(project_id), aktuell_tele)

            return {
                "status": "ok",
                "assets_count": len(neue_assets),
                "line_count": len(neue_line),
            }


# ---------------------------------------------------------------------------
# HTTP-Handler
# ---------------------------------------------------------------------------

class _ProjectsHandler(BaseHTTPRequestHandler):
    """HTTP-Request-Handler für die Projektplanung-API."""

    def _path(self) -> str:
        """Gibt den Pfad ohne Query-String zurück (selbst wenn Proxy Query-String durchreicht)."""
        return urlparse(self.path).path

    def do_GET(self) -> None:  # noqa: N802
        path = self._path()
        if path == "/api/health":
            self._json(200, {"status": "ok"})
        elif path == "/api/projects":
            self._handle_projekte_liste()
        elif m := _RE_PROJEKT.match(path):
            self._handle_projekt_get(m.group(1))
        elif m := _RE_EPISODEN.match(path):
            self._handle_episoden_liste(m.group(1))
        elif m := _RE_ASSETS.match(path):
            self._handle_assets_liste(m.group(1))
        elif m := _RE_LINE.match(path):
            self._handle_line_get(m.group(1))
        elif m := _RE_WORKSPACE.match(path):
            self._handle_workspace_get(m.group(1))
        elif m := _RE_TELEPROMPTER.match(path):
            self._handle_teleprompter_get(m.group(1))
        elif m := _RE_MONITOR.match(path):
            self._handle_monitor_get(m.group(1))
        else:
            self._json(404, {"error": "Nicht gefunden"})

    def do_POST(self) -> None:  # noqa: N802
        path = self._path()
        if path == "/api/projects":
            self._handle_projekt_post()
        elif m := _RE_EPISODEN.match(path):
            self._handle_episode_post(m.group(1))
        elif m := _RE_PROJEKT_RECORDING.match(path):
            self._handle_recording_assign(m.group(1), m.group(2))
        elif m := _RE_ASSETS.match(path):
            self._handle_asset_post(m.group(1))
        elif m := _RE_WORKSPACE_IMPORT.match(path):
            self._handle_workspace_import_post(m.group(1))
        elif m := _RE_MONITOR_ANALYZE.match(path):
            self._handle_monitor_analyze_post(m.group(1))
        else:
            self._json(404, {"error": "Nicht gefunden"})

    def do_PUT(self) -> None:  # noqa: N802
        path = self._path()
        if m := _RE_EPISODE.match(path):
            self._handle_episode_put(m.group(1), m.group(2))
        elif m := _RE_ASSET.match(path):
            self._handle_asset_put(m.group(1), m.group(2))
        elif m := _RE_LINE.match(path):
            self._handle_line_put(m.group(1))
        elif m := _RE_TELEPROMPTER.match(path):
            self._handle_teleprompter_put(m.group(1))
        elif m := _RE_MONITOR.match(path):
            self._handle_monitor_put(m.group(1))
        elif m := _RE_PROJEKT.match(path):
            self._handle_projekt_put(m.group(1))
        else:
            self._json(404, {"error": "Nicht gefunden"})

    def do_DELETE(self) -> None:  # noqa: N802
        path = self._path()
        if m := _RE_EPISODE.match(path):
            self._handle_episode_delete(m.group(1), m.group(2))
        elif m := _RE_ASSET.match(path):
            self._handle_asset_delete(m.group(1), m.group(2))
        elif m := _RE_PROJEKT_RECORDING.match(path):
            self._handle_recording_unassign(m.group(1), m.group(2))
        elif m := _RE_PROJEKT.match(path):
            self._handle_projekt_delete(m.group(1))
        else:
            self._json(404, {"error": "Nicht gefunden"})

    # -- GET-Handler --

    def _handle_projekte_liste(self) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        self._json(200, {"projects": store.liste_projekte()})

    def _handle_projekt_get(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        projekt = store.projekt_holen(project_id)
        if projekt is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, projekt)

    def _handle_episoden_liste(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        episoden = store.liste_episoden(project_id)
        if episoden is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"episodes": episoden})

    def _handle_assets_liste(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        assets = store.liste_assets(project_id)
        if assets is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"assets": assets})

    def _handle_line_get(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        line = store.hole_line(project_id)
        if line is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"line": line})

    def _handle_workspace_get(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        payload = store.workspace_exportieren(project_id)
        if payload is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, payload)

    def _handle_teleprompter_get(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        data = store.hole_teleprompter(project_id)
        if data is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"teleprompter": data})

    def _handle_teleprompter_put(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        try:
            res = store.speichere_teleprompter(project_id, body)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        if res is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"teleprompter": res})

    def _handle_monitor_get(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        data = store.hole_monitor(project_id)
        if data is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"monitor": data})

    def _handle_monitor_put(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        try:
            res = store.speichere_monitor(project_id, body)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        if res is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"monitor": res})

    def _handle_monitor_analyze_post(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        text = str(body.get("text", "")).strip()
        context = body.get("context")
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        res = store.monitor_analysieren(project_id, text, context)
        if res is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, res)

    # -- POST-Handler --

    def _handle_projekt_post(self) -> None:
        body = self._lese_body()
        if body is None:
            return
        title = body.get("title", "").strip()
        if not title:
            self._json(400, {"error": "Pflichtfeld 'title' fehlt oder leer"})
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        projekt = store.projekt_anlegen(
            title=title,
            description=body.get("description", ""),
        )
        self._json(201, projekt)

    def _handle_episode_post(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        title = body.get("title", "").strip()
        if not title:
            self._json(400, {"error": "Pflichtfeld 'title' fehlt oder leer"})
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        episode = store.episode_anlegen(
            project_id=project_id,
            title=title,
            notes=body.get("notes", ""),
            status=body.get("status", "geplant"),
        )
        if episode is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(201, episode)

    def _handle_asset_post(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        label = str(body.get("label", "")).strip()
        if not label:
            self._json(400, {"error": "Pflichtfeld 'label' fehlt oder leer"})
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        asset = store.asset_anlegen(
            project_id=project_id,
            label=label,
            kind=body.get("kind", "audio"),
            asset_path=body.get("asset_path", ""),
            color=body.get("color", "#3b82f6"),
            mode=body.get("mode", "play_stop"),
            hotkey=body.get("hotkey", ""),
            volume=float(body.get("volume", 1.0)),
            asset_id=body.get("id"),
        )
        if asset is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(201, asset)

    def _handle_workspace_import_post(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        try:
            res = store.workspace_importieren(project_id, body)
        except ValueError as exc:
            self._json(400, {"error": str(exc)})
            return
        if res is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, res)

    # -- PUT-Handler --

    def _handle_projekt_put(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        title = body.get("title", "").strip()
        if not title:
            self._json(400, {"error": "Pflichtfeld 'title' fehlt oder leer"})
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        projekt = store.projekt_aktualisieren(
            project_id=project_id,
            title=title,
            description=body.get("description", ""),
        )
        if projekt is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, projekt)

    def _handle_asset_put(self, project_id: str, asset_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        label = str(body.get("label", "")).strip()
        if not label:
            self._json(400, {"error": "Pflichtfeld 'label' fehlt oder leer"})
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        asset = store.asset_aktualisieren(
            project_id=project_id,
            asset_id=asset_id,
            label=label,
            kind=body.get("kind", "audio"),
            asset_path=body.get("asset_path", ""),
            color=body.get("color", "#3b82f6"),
            mode=body.get("mode", "play_stop"),
            hotkey=body.get("hotkey", ""),
            volume=float(body.get("volume", 1.0)),
        )
        if asset is None:
            self._json(404, {"error": "Projekt oder Asset nicht gefunden"})
        else:
            self._json(200, asset)

    def _handle_line_put(self, project_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        raw_line = body.get("line")
        if raw_line is None or not isinstance(raw_line, list):
            self._json(400, {"error": "Pflichtfeld 'line' muss eine Liste sein"})
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        line = store.speichere_line(project_id, raw_line)
        if line is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, {"line": line})

    # -- DELETE-Handler --

    def _handle_projekt_delete(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        ok = store.projekt_loeschen(project_id)
        if ok:
            self.send_response(204)
            self.end_headers()
        else:
            self._json(404, {"error": "Projekt nicht gefunden"})

    def _handle_episode_put(self, project_id: str, episode_id: str) -> None:
        body = self._lese_body()
        if body is None:
            return
        title = body.get("title", "").strip()
        if not title:
            self._json(400, {"error": "Pflichtfeld 'title' fehlt oder leer"})
            return
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        episode = store.episode_aktualisieren(
            project_id=project_id,
            episode_id=episode_id,
            title=title,
            notes=body.get("notes", ""),
            status=body.get("status", "geplant"),
        )
        if episode is None:
            self._json(404, {"error": "Projekt oder Episode nicht gefunden"})
        else:
            self._json(200, episode)

    def _handle_episode_delete(self, project_id: str, episode_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        if store.episode_loeschen(project_id, episode_id):
            self.send_response(204)
            self.end_headers()
        else:
            self._json(404, {"error": "Projekt oder Episode nicht gefunden"})

    def _handle_asset_delete(self, project_id: str, asset_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        if store.asset_loeschen(project_id, asset_id):
            self.send_response(204)
            self.end_headers()
        else:
            self._json(404, {"error": "Projekt oder Asset nicht gefunden"})

    def _handle_recording_assign(self, project_id: str, recording_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        projekt = store.aufnahme_zuordnen(project_id, recording_id)
        if projekt is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, projekt)

    def _handle_recording_unassign(self, project_id: str, recording_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        projekt = store.aufnahme_entfernen(project_id, recording_id)
        if projekt is None:
            self._json(404, {"error": "Projekt nicht gefunden"})
        else:
            self._json(200, projekt)

    # -- Hilfsmethoden --

    def _lese_body(self) -> Optional[dict]:
        """Liest und parsed den JSON-Request-Body. Sendet 400 bei Fehler."""
        try:
            laenge = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(laenge) if laenge > 0 else b"{}"
            return json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": f"Ungültiger JSON-Body: {exc}"})
            return None

    def _json(self, status: int, daten: dict | list) -> None:
        body = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: D102
        _log.debug("ProjectsApiServer: " + fmt, *args)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class ProjectsApiServer:
    """HTTP-Dienst für die Projektplanung des Klangpult light – Planers.

    Läuft in einem eigenen Daemon-Thread. Sauberes stop() wartet auf Shutdown.
    Persistenz via JSON-Dateien in ``data_dir`` (UTF-8 ohne BOM).

    Args:
        data_dir: Verzeichnis für Persistenz-Dateien. Wird angelegt falls nicht vorhanden.
    """

    def __init__(self, data_dir: str) -> None:
        self._store = _ProjektStore(data_dir=data_dir)
        self._server: Optional[_ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> Optional[int]:
        """Tatsächlich gebundener Port (nach start()). Für Tests mit port=0."""
        if self._server is not None:
            return self._server.server_address[1]
        return None

    def start(self, host: str = "127.0.0.1", port: int = 8769) -> None:
        """Startet den HTTP-Server in einem eigenen Thread.

        Args:
            host: Bind-Adresse (Standard: 127.0.0.1).
            port: Port (Standard: 8769). Port 0 = Betriebssystem wählt freien Port.
        """
        if self._server is not None:
            return

        server = _ThreadingHTTPServer((host, port), _ProjectsHandler)
        server.store = self._store  # type: ignore[attr-defined]

        thread = threading.Thread(
            target=server.serve_forever,
            name="ProjectsApiServer",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            server.server_close()
            raise
        # Erst nach erfolgreichem Thread-Start als "laufend" markieren.
        self._server = server
        self._thread = thread
        _log.info(
            "ProjectsApiServer gestartet auf http://%s:%d",
            host,
            server.server_address[1],
        )

    def stop(self) -> None:
        """Fährt den HTTP-Server sauber herunter und wartet auf Thread-Ende."""
        if self._server is None:
            return

        server = self._server
        self._server = None
        server.shutdown()
        server.server_close()

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        _log.info("ProjectsApiServer gestoppt.")
