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
            # Episoden-Datei ebenfalls löschen
            ep_pfad = self._episoden_pfad(project_id)
            if ep_pfad.exists():
                ep_pfad.unlink()
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
        else:
            self._json(404, {"error": "Nicht gefunden"})

    def do_POST(self) -> None:  # noqa: N802
        path = self._path()
        if path == "/api/projects":
            self._handle_projekt_post()
        elif m := _RE_EPISODEN.match(path):
            self._handle_episode_post(m.group(1))
        else:
            self._json(404, {"error": "Nicht gefunden"})

    def do_PUT(self) -> None:  # noqa: N802
        path = self._path()
        if m := _RE_PROJEKT.match(path):
            self._handle_projekt_put(m.group(1))
        else:
            self._json(404, {"error": "Nicht gefunden"})

    def do_DELETE(self) -> None:  # noqa: N802
        path = self._path()
        if m := _RE_PROJEKT.match(path):
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

    # -- DELETE-Handler --

    def _handle_projekt_delete(self, project_id: str) -> None:
        store: _ProjektStore = self.server.store  # type: ignore[attr-defined]
        ok = store.projekt_loeschen(project_id)
        if ok:
            # 204 No Content — kein Body
            self.send_response(204)
            self.end_headers()
        else:
            self._json(404, {"error": "Projekt nicht gefunden"})

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
    """HTTP-Dienst für die Projektplanung des PodcastPlaners.

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
