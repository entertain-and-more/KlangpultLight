"""bridge.library_api — HTTP-Dienst für die Aufnahme-Bibliothek.

Stellt folgende Endpunkte bereit (HTTP GET, JSON-Antworten):
    GET /api/library  → Liste aller Aufnahmen mit Branch-Baum
    GET /api/health   → {"status": "ok"}

Wird in einem eigenen Thread betrieben (ThreadingHTTPServer).
Sauberes Herunterfahren via stop() — kein Orphan-Thread.
"""
from __future__ import annotations

import json
import logging
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Optional

_log = logging.getLogger(__name__)


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """ThreadingHTTPServer mit allow_reuse_address für saubere Tests."""
    allow_reuse_address = True
    daemon_threads = True  # Handler-Threads sterben mit dem Server-Thread


class _LibraryHandler(BaseHTTPRequestHandler):
    """HTTP-Request-Handler für die Bibliotheks-API.

    Liest self.server.library aus (wird von LibraryApiServer gesetzt).
    Kein GUI-Zugriff, kein Blocking-I/O.
    """

    def do_GET(self) -> None:  # noqa: N802 — HTTP-Methoden-Konvention
        if self.path == "/api/health":
            self._json_response(200, {"status": "ok"})
        elif self.path == "/api/library":
            self._antwort_library()
        else:
            self._json_response(404, {"error": "Nicht gefunden"})

    def _antwort_library(self) -> None:
        """Liefert alle Aufnahmen mit Branch-Baum als JSON."""
        try:
            library = getattr(self.server, "library", None)
            if library is None:
                self._json_response(503, {"error": "Library nicht verfügbar"})
                return

            aufnahmen = library.list_recordings()
            daten = []
            for meta in aufnahmen:
                eintrag = meta.to_dict()
                daten.append(eintrag)

            self._json_response(200, {"recordings": daten})
        except Exception as exc:
            _log.exception("LibraryApiServer: Fehler bei /api/library: %s", exc)
            self._json_response(500, {"error": "Interner Fehler"})

    def _json_response(self, status: int, daten: dict) -> None:
        body = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: D102
        # Standard-HTTP-Log auf DEBUG reduzieren (kein Spam in Tests)
        _log.debug("LibraryApiServer: " + fmt, *args)


class LibraryApiServer:
    """Kleiner HTTP-Dienst, der die Aufnahme-Bibliothek über REST zugänglich macht.

    Läuft in einem eigenen Daemon-Thread. Sauberes stop() wartet auf Shutdown.

    Args:
        library: RecordingLibrary-Instanz. Wird als Attribut an den HTTPServer
                 gebunden (self.server.library im Handler).
    """

    def __init__(self, library) -> None:
        self._library = library
        self._server: Optional[_ThreadingHTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    @property
    def port(self) -> Optional[int]:
        """Tatsächlich gebundener Port (nach start()). Für Tests mit port=0."""
        if self._server is not None:
            return self._server.server_address[1]
        return None

    def start(self, host: str = "127.0.0.1", port: int = 8767) -> None:
        """Startet den HTTP-Server in einem eigenen Thread.

        Args:
            host: Bind-Adresse (Standard: 127.0.0.1).
            port: Port (Standard: 8767). Port 0 = Betriebssystem wählt freien Port.
        """
        if self._server is not None:
            return  # Bereits gestartet

        server = _ThreadingHTTPServer((host, port), _LibraryHandler)
        server.library = self._library  # type: ignore[attr-defined]
        self._server = server

        self._thread = threading.Thread(
            target=server.serve_forever,
            name="LibraryApiServer",
            daemon=True,
        )
        self._thread.start()
        _log.info(
            "LibraryApiServer gestartet auf http://%s:%d",
            host,
            server.server_address[1],
        )

    def stop(self) -> None:
        """Fährt den HTTP-Server sauber herunter und wartet auf Thread-Ende."""
        if self._server is None:
            return

        server = self._server
        self._server = None
        server.shutdown()   # blockiert bis serve_forever() zurückkehrt
        server.server_close()

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        _log.info("LibraryApiServer gestoppt.")
