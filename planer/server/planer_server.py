"""planer.server.planer_server — Statischer Dateiserver mit API-Proxy.

Dient zwei Zwecken:
1. Statische Dateien aus ``planer/`` ausliefern (index.html, app/*.js, styles/*.css).
2. API-Anfragen transparent an die laufenden Recorder-Dienste weiterleiten:
   - /api/library/* → LibraryApiServer  (Standard-Port 8767)
   - /api/projects/* → ProjectsApiServer (Standard-Port 8769)

Dadurch laufen Frontend und API am selben Ursprung — kein CORS nötig.

Starten (direkt):
    python planer/server/planer_server.py

Oder über start.py im Planer-Root:
    python planer/start.py
"""
from __future__ import annotations

import http.client
import json
import logging
import mimetypes
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from socketserver import ThreadingMixIn
from typing import Optional
from urllib.parse import urlparse

_log = logging.getLogger(__name__)

# Standardports (passend zu bridge_service.py)
_LIBRARY_PORT_DEFAULT = 8767
_PROJECTS_PORT_DEFAULT = 8769


def _resolve_static_root() -> Path:
    """Ermittelt den statischen Root-Pfad für den Planer (Entwicklung und Frozen/PyInstaller)."""
    default_root = Path(__file__).parent.parent
    if (default_root / "index.html").is_file():
        return default_root

    # Frozen mode (PyInstaller onefile / onedir)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        cand = Path(meipass) / "planer"
        if (cand / "index.html").is_file():
            return cand

    exe_dir = Path(sys.executable).parent
    for cand in [exe_dir / "planer", exe_dir / "_internal" / "planer"]:
        if (cand / "index.html").is_file():
            return cand

    return default_root


# Statischer Root: planer/
_STATIC_ROOT = _resolve_static_root()

# Erweiterungen, die NIEMALS ausgeliefert werden dürfen (Python-Quellcode / Bytecode)
_BLOCKED_SUFFIXES = {".py", ".pyc", ".pyo", ".pyd"}

# MIME-Typen sicherstellen
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")


class PlanerHandler(BaseHTTPRequestHandler):
    """HTTP-Handler für den Planer-Server.

    Proxy-Logik: /api/library* → library_port, /api/projects* → projects_port
    Alles andere: statische Dateien aus _STATIC_ROOT.
    """

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path

        if path.startswith("/api/library"):
            self._proxy(self.server.library_port)  # type: ignore[attr-defined]
        elif path.startswith("/api/projects"):
            self._proxy(self.server.projects_port)  # type: ignore[attr-defined]
        else:
            self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/projects"):
            self._proxy(self.server.projects_port)  # type: ignore[attr-defined]
        else:
            self._fehler(405, "Methode nicht erlaubt")

    def do_PUT(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/projects"):
            self._proxy(self.server.projects_port)  # type: ignore[attr-defined]
        else:
            self._fehler(405, "Methode nicht erlaubt")

    def do_DELETE(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path.startswith("/api/projects"):
            self._proxy(self.server.projects_port)  # type: ignore[attr-defined]
        else:
            self._fehler(405, "Methode nicht erlaubt")

    # -------------------------------------------------------------------------
    # Proxy
    # -------------------------------------------------------------------------

    def _proxy(self, backend_port: int) -> None:
        """Leitet die Anfrage an den Backend-Dienst weiter.

        Routing verwendet den geparsten Pfad (ohne Query) zur Bestimmung des Backends,
        aber der vollständige ``self.path`` (mit Query-String) wird an das Backend
        durchgereicht, damit Query-Parameter nicht verloren gehen.
        """
        method = self.command
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        try:
            conn = http.client.HTTPConnection("127.0.0.1", backend_port, timeout=10)
            headers = {"Content-Type": self.headers.get("Content-Type", "application/json")}
            # self.path enthält Query-String (z. B. /api/projects?sort=asc) — vollständig
            # durchreichen, damit Filter/Paginierung beim Backend ankommen.
            conn.request(method, self.path, body=body, headers=headers)
            resp = conn.getresponse()
            resp_body = resp.read()

            self.send_response(resp.status)
            ct = resp.getheader("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Type", ct)
            self.send_header("Content-Length", str(len(resp_body)))
            # CORS-Header für den Fall, dass das Frontend doch direkt geöffnet wird
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(resp_body)
            conn.close()
        except OSError as exc:
            _log.warning("Proxy-Fehler zu Port %d: %s", backend_port, exc)
            self._fehler(
                502,
                f"Backend-Dienst nicht erreichbar (Port {backend_port}). "
                "Bitte Klangpult light – Recorder starten.",
            )

    # -------------------------------------------------------------------------
    # Statische Dateien
    # -------------------------------------------------------------------------

    def _serve_static(self, path: str) -> None:
        """Liefert statische Dateien aus dem Planer-Verzeichnis."""
        # Index-Datei-Fallback
        if path == "/" or path == "":
            path = "/index.html"

        # Sicherheitscheck: kein Path-Traversal
        try:
            abs_path = (_STATIC_ROOT / path.lstrip("/")).resolve()
            abs_path.relative_to(_STATIC_ROOT.resolve())
        except ValueError:
            self._fehler(403, "Zugriff verweigert")
            return

        # Sicherheitscheck: keine Python-Quelldateien oder -Bytecode ausliefern
        if abs_path.suffix.lower() in _BLOCKED_SUFFIXES:
            self._fehler(404, f"Datei nicht gefunden: {path}")
            return

        if not abs_path.exists():
            self._fehler(404, f"Datei nicht gefunden: {path}")
            return

        if abs_path.is_dir():
            # Verzeichnis: index.html versuchen
            index = abs_path / "index.html"
            if index.exists():
                abs_path = index
            else:
                self._fehler(403, "Verzeichnis-Listing nicht erlaubt")
                return

        mime = mimetypes.guess_type(str(abs_path))[0] or "application/octet-stream"
        try:
            data = abs_path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except OSError as exc:
            _log.error("Fehler beim Lesen von %s: %s", abs_path, exc)
            self._fehler(500, "Interner Fehler")

    # -------------------------------------------------------------------------
    # Hilfsmethoden
    # -------------------------------------------------------------------------

    def _fehler(self, status: int, meldung: str) -> None:
        body = json.dumps({"error": meldung}, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: D102
        _log.debug("PlanerServer: " + fmt, *args)


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


class PlanerServer:
    """Planer-Webserver: statische Dateien + Proxy zu Recorder-APIs.

    Args:
        library_port:  Port des LibraryApiServers (Standard: 8767).
        projects_port: Port des ProjectsApiServers (Standard: 8769).
    """

    def __init__(
        self,
        library_port: int = _LIBRARY_PORT_DEFAULT,
        projects_port: int = _PROJECTS_PORT_DEFAULT,
    ) -> None:
        self._library_port = library_port
        self._projects_port = projects_port
        self._server: Optional[_ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> Optional[int]:
        """Gebundener Port nach start(). Für Tests mit port=0."""
        if self._server is not None:
            return self._server.server_address[1]
        return None

    def start(self, host: str = "127.0.0.1", port: int = 8770) -> None:
        """Startet den Server in einem Daemon-Thread.

        Args:
            host: Bind-Adresse (Standard: 127.0.0.1).
            port: Port (Standard: 8770). 0 = freien Port wählen.
        """
        if self._server is not None:
            return

        server = _ThreadingHTTPServer((host, port), PlanerHandler)
        server.library_port = self._library_port  # type: ignore[attr-defined]
        server.projects_port = self._projects_port  # type: ignore[attr-defined]

        thread = threading.Thread(
            target=server.serve_forever,
            name="PlanerServer",
            daemon=True,
        )
        try:
            thread.start()
        except Exception:
            server.server_close()
            raise
        # Erst nach erfolgreichem Thread-Start als "laufend" markieren,
        # damit start() bei einem Fehler nicht idempotent blockiert.
        self._server = server
        self._thread = thread
        _log.info(
            "PlanerServer gestartet auf http://%s:%d "
            "(Library→%d, Projects→%d)",
            host,
            server.server_address[1],
            self._library_port,
            self._projects_port,
        )

    def stop(self) -> None:
        """Fährt den Server sauber herunter."""
        if self._server is None:
            return

        server = self._server
        self._server = None
        server.shutdown()
        server.server_close()

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        _log.info("PlanerServer gestoppt.")


# ---------------------------------------------------------------------------
# Direktstart
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    port = int(os.environ.get("PLANER_PORT", "8770"))
    library_port = int(os.environ.get("LIBRARY_PORT", str(_LIBRARY_PORT_DEFAULT)))
    projects_port = int(os.environ.get("PROJECTS_PORT", str(_PROJECTS_PORT_DEFAULT)))

    srv = PlanerServer(library_port=library_port, projects_port=projects_port)
    srv.start(host="127.0.0.1", port=port)

    print(f"Klangpult light – Planer läuft auf http://127.0.0.1:{srv.port}")
    print("Stoppen mit Ctrl+C")
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        print("\nBeende...")
        srv.stop()
        sys.exit(0)
