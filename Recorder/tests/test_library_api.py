"""tests.test_library_api — Tests für den LibraryApiServer.

Belegt:
  - GET /api/health liefert {"status": "ok"} mit HTTP 200
  - GET /api/library liefert korrektes JSON mit Aufnahmen + Branch-Baum
  - Server startet und stoppt sauber (kein Orphan-Thread)
  - Testports werden dynamisch gebunden (port=0), kein hardcodierter Port
"""
import json
import threading
import time
import urllib.request

import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio und Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")  # Bridge in Tests nicht auto-starten


def _erstelle_mock_library(tmp_path):
    """Erzeugt eine RecordingLibrary mit einer Test-Aufnahme und einem Branch."""
    from recordings.library import RecordingLibrary
    library = RecordingLibrary(workspace_dir=str(tmp_path))
    meta = library.create_recording("Testrunde 1")
    library.add_branch(meta.recording_id, "Schnitt A")
    return library, meta


# ---------------------------------------------------------------------------
# Test: /api/health
# ---------------------------------------------------------------------------

def test_health_endpoint(tmp_path):
    """GET /api/health liefert HTTP 200 und {"status": "ok"}."""
    from bridge.library_api import LibraryApiServer
    library, _ = _erstelle_mock_library(tmp_path)

    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    assert port is not None and port > 0, "Port wurde nicht gesetzt"

    try:
        url = f"http://127.0.0.1:{port}/api/health"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            daten = json.loads(resp.read().decode("utf-8"))
        assert daten == {"status": "ok"}, f"Unerwartete Antwort: {daten}"
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Test: /api/library
# ---------------------------------------------------------------------------

def test_library_endpoint_liefert_aufnahmen(tmp_path):
    """GET /api/library liefert mindestens eine Aufnahme mit Branch-Baum."""
    from bridge.library_api import LibraryApiServer
    library, meta = _erstelle_mock_library(tmp_path)

    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port

    try:
        url = f"http://127.0.0.1:{port}/api/library"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            daten = json.loads(resp.read().decode("utf-8"))
    finally:
        server.stop()

    assert "recordings" in daten, f"'recordings'-Schlüssel fehlt: {daten}"
    aufnahmen = daten["recordings"]
    assert len(aufnahmen) >= 1, "Keine Aufnahmen in der Antwort"

    # Erste Aufnahme prüfen
    erste = aufnahmen[0]
    assert erste["recording_id"] == meta.recording_id
    assert erste["title"] == "Testrunde 1"

    # Branch-Baum prüfen
    branches = erste.get("branches", [])
    assert len(branches) >= 2, f"Erwartet >= 2 Branches (Original + Schnitt A): {branches}"

    branch_namen = {b["name"] for b in branches}
    assert "Original" in branch_namen, f"Original-Branch fehlt: {branch_namen}"
    assert "Schnitt A" in branch_namen, f"'Schnitt A'-Branch fehlt: {branch_namen}"

    # Original-Branch muss is_original=True haben
    original = next(b for b in branches if b["name"] == "Original")
    assert original["is_original"] is True, "Original-Branch muss is_original=True haben"


def test_library_endpoint_ohne_aufnahmen(tmp_path):
    """GET /api/library gibt leere Liste zurück wenn keine Aufnahmen vorhanden."""
    from recordings.library import RecordingLibrary
    from bridge.library_api import LibraryApiServer

    # Leere Library (keine create_recording)
    leere_library = RecordingLibrary(workspace_dir=str(tmp_path / "leer"))
    server = LibraryApiServer(library=leere_library)
    server.start(host="127.0.0.1", port=0)
    port = server.port

    try:
        url = f"http://127.0.0.1:{port}/api/library"
        with urllib.request.urlopen(url, timeout=5) as resp:
            daten = json.loads(resp.read().decode("utf-8"))
    finally:
        server.stop()

    assert daten["recordings"] == [], f"Erwartet leere Liste: {daten}"


def test_health_endpoint_mit_query_string(tmp_path):
    """GET /api/health?x=1 liefert HTTP 200 — Query-String darf Routing nicht brechen.

    Belegt library_api.py-Fix: urlparse(self.path).path strippt den Query-String,
    sodass der Pfad-Vergleich auch bei ?-Suffix korrekt matcht.
    """
    from bridge.library_api import LibraryApiServer
    library, _ = _erstelle_mock_library(tmp_path)

    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port

    try:
        url = f"http://127.0.0.1:{port}/api/health?x=1&debug=true"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            daten = json.loads(resp.read().decode("utf-8"))
        assert daten == {"status": "ok"}, f"Unerwartete Antwort: {daten}"
    finally:
        server.stop()


def test_library_endpoint_mit_query_string(tmp_path):
    """GET /api/library?refresh=1 liefert HTTP 200 — Query-String darf Routing nicht brechen.

    Belegt library_api.py-Fix (Query-Strip via urlparse) für den /api/library-Pfad.
    """
    from bridge.library_api import LibraryApiServer
    library, _ = _erstelle_mock_library(tmp_path)

    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port

    try:
        url = f"http://127.0.0.1:{port}/api/library?refresh=1"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            daten = json.loads(resp.read().decode("utf-8"))
        assert "recordings" in daten, f"'recordings'-Schlüssel fehlt: {daten}"
    finally:
        server.stop()


def test_unbekannter_pfad_liefert_404(tmp_path):
    """GET /nichtvorhanden liefert HTTP 404."""
    from bridge.library_api import LibraryApiServer
    library, _ = _erstelle_mock_library(tmp_path)

    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port

    try:
        url = f"http://127.0.0.1:{port}/nichtvorhanden"
        try:
            urllib.request.urlopen(url, timeout=5)
            pytest.fail("Erwartet HTTP 404, aber keine Exception")
        except urllib.error.HTTPError as e:
            assert e.code == 404, f"Erwartet 404, bekam {e.code}"
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Test: Sauberer Stop — kein Orphan-Thread
# ---------------------------------------------------------------------------

def test_thread_start_fehler_blockiert_nicht_naechsten_start(tmp_path):
    """Wenn thread.start() wirft, muss _server None bleiben.

    Belegt Bugsweep-Fix: self._server wurde vor thread.start() gesetzt.
    Bei Fehler war _server != None → zweites start() gab sofort zurück.
    """
    import unittest.mock as mock
    from bridge.library_api import LibraryApiServer
    library, _ = _erstelle_mock_library(tmp_path)

    server_obj = LibraryApiServer(library=library)

    with mock.patch("threading.Thread.start", side_effect=RuntimeError("Sabotage")):
        with pytest.raises(RuntimeError, match="Sabotage"):
            server_obj.start(host="127.0.0.1", port=0)

    assert server_obj._server is None, "_server muss None sein nach fehlgeschlagenem start()"

    # Zweites start() muss klappen
    server_obj.start(host="127.0.0.1", port=0)
    try:
        assert server_obj.port is not None and server_obj.port > 0
    finally:
        server_obj.stop()


def test_kein_orphan_thread_nach_stop(tmp_path):
    """Nach stop() läuft kein LibraryApiServer-Thread mehr."""
    from bridge.library_api import LibraryApiServer
    library, _ = _erstelle_mock_library(tmp_path)

    threads_vorher = {t.name for t in threading.enumerate()}

    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port

    # Server-Thread ist aktiv
    threads_nach_start = {t.name for t in threading.enumerate()}
    assert "LibraryApiServer" in threads_nach_start, "Server-Thread sollte aktiv sein"

    # Server ist erreichbar
    url = f"http://127.0.0.1:{port}/api/health"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200

    server.stop()

    # Kurz warten, bis Thread-Ende registriert ist
    time.sleep(0.1)

    threads_nach_stop = {t.name for t in threading.enumerate()}
    assert "LibraryApiServer" not in threads_nach_stop, (
        "LibraryApiServer-Thread läuft noch nach stop() — Orphan-Thread!"
    )


# ---------------------------------------------------------------------------
# Test: /api/library/<id>/audio  (P2 Browser-Player)
# ---------------------------------------------------------------------------

def test_audio_endpoint_streamt_datei(tmp_path):
    """GET /api/library/<id>/audio liefert die mix.wav mit Content-Type audio/wav."""
    import os
    import urllib.error  # noqa: F401
    from bridge.library_api import LibraryApiServer
    library, meta = _erstelle_mock_library(tmp_path)
    main_dir = os.path.join(library.recording_dir(meta.recording_id), "main")
    os.makedirs(main_dir, exist_ok=True)
    inhalt = b"RIFF\x00\x00\x00\x00WAVEfake-audio-bytes"
    with open(os.path.join(main_dir, "mix.wav"), "wb") as f:
        f.write(inhalt)

    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        url = f"http://127.0.0.1:{port}/api/library/{meta.recording_id}/audio"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Type") == "audio/wav"
            body = resp.read()
        assert body == inhalt
    finally:
        server.stop()


def test_audio_endpoint_unbekannt_404(tmp_path):
    import urllib.error
    from bridge.library_api import LibraryApiServer
    library, _ = _erstelle_mock_library(tmp_path)
    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        url = f"http://127.0.0.1:{port}/api/library/gibtsnicht/audio"
        try:
            urllib.request.urlopen(url, timeout=5)
            assert False, "404 erwartet"
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.stop()
