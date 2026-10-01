"""bridge.library_api — HTTP-Dienst für die Aufnahme-Bibliothek.

Stellt folgende Endpunkte bereit (HTTP GET/HEAD/OPTIONS, JSON-Antworten):
    GET /api/library               → Liste aller Aufnahmen mit Branch-Baum
    GET /api/library/<id>          → Metadaten einer einzelnen Aufnahme
    GET /api/library/<id>/audio    → Abspielbare Audio-/Videodatei (Range-Streaming)
    GET /api/health                → {"status": "ok"}
    OPTIONS *                      → 204 No Content mit CORS-Headern
    HEAD *                         → Header-Antworten ohne Body-Stream

Wird in einem eigenen Thread betrieben (ThreadingHTTPServer).
Sauberes Herunterfahren via stop() — kein Orphan-Thread.
"""
from __future__ import annotations

import json
import logging
import os
import re
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Optional
from urllib.parse import unquote, urlparse

_log = logging.getLogger(__name__)

# /api/library/<recording_id>/audio → Audiodatei der Aufnahme streamen
_RE_AUDIO = re.compile(r"^/api/library/([^/]+)/audio$")
# /api/library/<recording_id> → Metadaten einer einzelnen Aufnahme
_RE_RECORDING = re.compile(r"^/api/library/([^/]+)$")


def _parse_byte_range(range_header: str, file_size: int) -> tuple[int, int] | None:
    """Parst einen HTTP-Byte-Range-Header (RFC 7233).

    Returns:
        (start, end) inklusive Byte-Positionen, oder None wenn ungültig/nicht erfüllbar.
    """
    if not range_header or not range_header.startswith("bytes="):
        return None
    val = range_header[len("bytes=") :].strip()
    if not val or "," in val:
        return None
    parts = val.split("-", 1)
    if len(parts) != 2:
        return None
    start_str, end_str = parts[0].strip(), parts[1].strip()
    try:
        if not start_str and end_str:
            suffix = int(end_str)
            if suffix <= 0 or file_size <= 0:
                return None
            start = max(0, file_size - suffix)
            end = file_size - 1
            return (start, end)
        elif start_str and not end_str:
            start = int(start_str)
            if start < 0 or start >= file_size:
                return None
            return (start, file_size - 1)
        elif start_str and end_str:
            start = int(start_str)
            end = int(end_str)
            if start < 0 or start > end or start >= file_size:
                return None
            end = min(end, file_size - 1)
            return (start, end)
    except ValueError:
        return None
    return None


class _ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """ThreadingHTTPServer mit allow_reuse_address für saubere Tests."""

    allow_reuse_address = True
    daemon_threads = True  # Handler-Threads sterben mit dem Server-Thread


class _LibraryHandler(BaseHTTPRequestHandler):
    """HTTP-Request-Handler für die Bibliotheks-API.

    Liest self.server.library aus (wird von LibraryApiServer gesetzt).
    Kein GUI-Zugriff, kein Blocking-I/O.
    """

    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Content-Type, Authorization, Range, X-Requested-With",
        )
        self.send_header(
            "Access-Control-Expose-Headers",
            "Content-Range, Accept-Ranges, Content-Length",
        )

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._set_cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self._dispatch(is_head=True)

    def do_GET(self) -> None:  # noqa: N802 — HTTP-Methoden-Konvention
        self._dispatch(is_head=False)

    def _dispatch(self, is_head: bool = False) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._json_response(200, {"status": "ok"}, is_head=is_head)
        elif path == "/api/library":
            self._antwort_library(is_head=is_head)
        elif m := _RE_AUDIO.match(path):
            self._antwort_audio(m.group(1), is_head=is_head)
        elif m := _RE_RECORDING.match(path):
            self._antwort_recording(m.group(1), is_head=is_head)
        else:
            self._json_response(404, {"error": "Nicht gefunden"}, is_head=is_head)

    def _antwort_audio(self, raw_recording_id: str, is_head: bool = False) -> None:
        """Streamt die abspielbare Datei der Aufnahme (main/mix.wav, sonst program.mp4) mit Range-Support."""
        library = getattr(self.server, "library", None)
        if library is None:
            self._json_response(503, {"error": "Library nicht verfügbar"}, is_head=is_head)
            return
        recording_id = unquote(raw_recording_id).strip()
        try:
            ordner = library.recording_dir(recording_id)
        except Exception:
            self._json_response(404, {"error": "Aufnahme nicht gefunden"}, is_head=is_head)
            return
        kandidaten = [
            (os.path.join(ordner, "main", "mix.wav"), "audio/wav"),
            (os.path.join(ordner, "main", "program.mp4"), "video/mp4"),
        ]
        pfad, ctype = next(((p, c) for p, c in kandidaten if os.path.isfile(p)), (None, None))
        if pfad is None:
            self._json_response(404, {"error": "Keine abspielbare Datei"}, is_head=is_head)
            return
        try:
            groesse = os.path.getsize(pfad)
            range_hdr = self.headers.get("Range")
            if range_hdr is not None and range_hdr.startswith("bytes="):
                byte_range = _parse_byte_range(range_hdr, groesse)
                if byte_range is None:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{groesse}")
                    self.send_header("Content-Length", "0")
                    self._set_cors_headers()
                    self.end_headers()
                    return
                start, end = byte_range
                length = end - start + 1
                self.send_response(206)
                self.send_header("Content-Type", ctype)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Range", f"bytes {start}-{end}/{groesse}")
                self.send_header("Content-Length", str(length))
                self._set_cors_headers()
                self.end_headers()
                if not is_head:
                    with open(pfad, "rb") as f:
                        f.seek(start)
                        remaining = length
                        while remaining > 0:
                            chunk = f.read(min(65536, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            remaining -= len(chunk)
                return

            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(groesse))
            self._set_cors_headers()
            self.end_headers()
            if not is_head:
                with open(pfad, "rb") as f:
                    while True:
                        chunk = f.read(65536)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
        except (OSError, BrokenPipeError) as exc:
            _log.debug("Audio-Stream abgebrochen (%s): %s", recording_id, exc)

    def _antwort_recording(self, raw_recording_id: str, is_head: bool = False) -> None:
        """Liefert Metadaten einer einzelnen Aufnahme als JSON."""
        library = getattr(self.server, "library", None)
        if library is None:
            self._json_response(503, {"error": "Library nicht verfügbar"}, is_head=is_head)
            return
        recording_id = unquote(raw_recording_id).strip()
        aufnahmen = library.list_recordings()
        meta = next((m for m in aufnahmen if m.recording_id == recording_id), None)
        if meta is None:
            self._json_response(404, {"error": "Aufnahme nicht gefunden"}, is_head=is_head)
            return
        self._json_response(200, {"recording": meta.to_dict()}, is_head=is_head)

    def _antwort_library(self, is_head: bool = False) -> None:
        """Liefert alle Aufnahmen mit Branch-Baum als JSON."""
        try:
            library = getattr(self.server, "library", None)
            if library is None:
                self._json_response(503, {"error": "Library nicht verfügbar"}, is_head=is_head)
                return

            aufnahmen = library.list_recordings()
            daten = []
            for meta in aufnahmen:
                eintrag = meta.to_dict()
                daten.append(eintrag)

            self._json_response(200, {"recordings": daten}, is_head=is_head)
        except Exception as exc:
            _log.exception("LibraryApiServer: Fehler bei /api/library: %s", exc)
            self._json_response(500, {"error": "Interner Fehler"}, is_head=is_head)

    def _json_response(self, status: int, daten: dict, is_head: bool = False) -> None:
        body = json.dumps(daten, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        if not is_head:
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

        thread = threading.Thread(
            target=server.serve_forever,
            name="LibraryApiServer",
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
        server.shutdown()  # blockiert bis serve_forever() zurückkehrt
        server.server_close()

        if self._thread is not None:
            self._thread.join(timeout=5.0)
            self._thread = None

        _log.info("LibraryApiServer gestoppt.")
