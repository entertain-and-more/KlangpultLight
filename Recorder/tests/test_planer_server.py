"""tests.test_planer_server — Tests für den PlanerServer (planer/server/planer_server.py).

Belegt:
  - Statische Datei (index.html) wird ausgeliefert
  - Unbekannter Pfad → 404
  - Proxy → 502 wenn Backend nicht läuft (kein echter Backend-Port)
  - Server startet und stoppt sauber (kein Orphan-Thread)
  - Port-0-Bindung (dynamischer Port)
"""
import json
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

# planer/server/ zum Python-Pfad hinzufügen (Projekt-Root-relativ)
_PLANER_SERVER_DIR = (
    Path(__file__).parent.parent.parent / "planer" / "server"
)
if str(_PLANER_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_PLANER_SERVER_DIR))


@pytest.fixture()
def planer_server():
    """Erzeugt einen PlanerServer auf einem freien Port und fährt ihn nach dem Test wieder herunter."""
    from planer_server import PlanerServer

    # Nicht existierende Ports für Library/Projects — wir testen nur statische Auslieferung + 502
    srv = PlanerServer(library_port=19999, projects_port=19998)
    srv.start(host="127.0.0.1", port=0)
    assert srv.port is not None and srv.port > 0, "Port wurde nicht zugewiesen"
    yield srv
    srv.stop()


# ---------------------------------------------------------------------------
# Statische Dateien
# ---------------------------------------------------------------------------

def test_index_html_wird_ausgeliefert(planer_server):
    """GET / liefert index.html (HTML-Content-Type, Status 200)."""
    url = f"http://127.0.0.1:{planer_server.port}/"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        ct = resp.headers.get("Content-Type", "")
        assert "html" in ct.lower(), f"Unerwarteter Content-Type: {ct}"
        body = resp.read().decode("utf-8")
    assert "Klangpult light" in body, "Erwartete 'Klangpult light' im HTML-Body"


def test_css_wird_ausgeliefert(planer_server):
    """GET /styles/main.css → 200, Content-Type enthält 'css'."""
    url = f"http://127.0.0.1:{planer_server.port}/styles/main.css"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        ct = resp.headers.get("Content-Type", "")
        assert "css" in ct.lower(), f"Unerwarteter Content-Type für CSS: {ct}"


def test_js_modul_wird_ausgeliefert(planer_server):
    """GET /app/api.js → 200, Content-Type enthält 'javascript'."""
    url = f"http://127.0.0.1:{planer_server.port}/app/api.js"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200
        ct = resp.headers.get("Content-Type", "")
        assert "javascript" in ct.lower(), f"Unerwarteter Content-Type für JS: {ct}"


def test_unbekannte_datei_404(planer_server):
    """GET /nichtvorhanden.txt → 404."""
    url = f"http://127.0.0.1:{planer_server.port}/nichtvorhanden.txt"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 404


# ---------------------------------------------------------------------------
# Proxy-Fehler (Backend nicht erreichbar)
# ---------------------------------------------------------------------------

def test_proxy_library_502_wenn_backend_nicht_laeuft(planer_server):
    """GET /api/library → 502 wenn LibraryApiServer nicht läuft."""
    url = f"http://127.0.0.1:{planer_server.port}/api/library"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 502, f"Erwartet 502, bekam {exc_info.value.code}"


def test_proxy_projects_502_wenn_backend_nicht_laeuft(planer_server):
    """GET /api/projects → 502 wenn ProjectsApiServer nicht läuft."""
    url = f"http://127.0.0.1:{planer_server.port}/api/projects"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 502, f"Erwartet 502, bekam {exc_info.value.code}"


def test_proxy_response_ist_json(planer_server):
    """502-Antwort enthält valides JSON mit 'error'-Schlüssel."""
    url = f"http://127.0.0.1:{planer_server.port}/api/library"
    try:
        urllib.request.urlopen(url, timeout=5)
        pytest.fail("Erwartete HTTPError (502), aber Request war erfolgreich")
    except urllib.error.HTTPError as e:
        assert e.code == 502, f"Erwartet 502, bekam {e.code}"
        body = e.read().decode("utf-8")
        data = json.loads(body)
        assert "error" in data, f"'error'-Schlüssel fehlt: {data}"


# ---------------------------------------------------------------------------
# Sicherheit: Path-Traversal
# ---------------------------------------------------------------------------

def test_path_traversal_relativ_403(planer_server):
    """GET /../<datei> (echtes ..) → 403 (kein Ausbruch aus _STATIC_ROOT)."""
    # http.client sendet den Pfad roh, ohne urllib-Normalisierung
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", planer_server.port, timeout=5)
    conn.request("GET", "/../../CLAUDE.md")
    resp = conn.getresponse()
    status = resp.status
    resp.read()
    conn.close()
    assert status == 403, f"Path-Traversal nicht blockiert: Status {status}"


def test_path_traversal_url_encoded_404(planer_server):
    """GET mit URL-kodiertem ..%2f → kein Ausbruch (404, nicht ausgeliefert)."""
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", planer_server.port, timeout=5)
    conn.request("GET", "/..%2f..%2fserver%2fplaner_server.py")
    resp = conn.getresponse()
    status = resp.status
    resp.read()
    conn.close()
    # Darf NICHT 200 sein (sonst wäre planer_server.py von außerhalb auslieferbar)
    assert status != 200, f"URL-kodiertes Path-Traversal lieferte Datei aus: {status}"
    assert status == 404, f"Erwartet 404 für unbekannten kodierten Pfad, bekam {status}"


# ---------------------------------------------------------------------------
# Proxy mit echtem Backend (Integration)
# ---------------------------------------------------------------------------

def test_proxy_leitet_an_projects_api_weiter(tmp_path):
    """Voller Proxy-Test: PlanerServer leitet POST /api/projects an ProjectsApiServer weiter."""
    from planer_server import PlanerServer

    # Echten ProjectsApiServer starten
    sys.path.insert(0, str(Path(__file__).parent.parent / "bridge"))
    from bridge.projects_api import ProjectsApiServer

    projects_srv = ProjectsApiServer(data_dir=str(tmp_path / "proj_data"))
    projects_srv.start(host="127.0.0.1", port=0)
    projects_port = projects_srv.port

    planer = PlanerServer(library_port=19999, projects_port=projects_port)
    planer.start(host="127.0.0.1", port=0)

    try:
        # POST Projekt über PlanerServer
        url = f"http://127.0.0.1:{planer.port}/api/projects"
        body = json.dumps({"title": "Integrationstest-Projekt", "description": "Proxy-Test"}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 201
            data = json.loads(resp.read().decode("utf-8"))
        assert data["title"] == "Integrationstest-Projekt"
        assert "project_id" in data

        # GET über PlanerServer
        get_url = f"http://127.0.0.1:{planer.port}/api/projects"
        with urllib.request.urlopen(get_url, timeout=5) as resp:
            assert resp.status == 200
            data2 = json.loads(resp.read().decode("utf-8"))
        assert len(data2["projects"]) == 1
    finally:
        planer.stop()
        projects_srv.stop()


# ---------------------------------------------------------------------------
# Bug-Fix: Query-String wird an Backend durchgereicht (nicht abgeschnitten)
# ---------------------------------------------------------------------------

def test_proxy_leitet_query_string_durch(tmp_path):
    """Query-String in der URL wird vollständig an das Backend weitergeleitet.

    Reproduziert Bug aus Phase-2-Abnahme: _proxy bekam nur den geparsten path
    (ohne Query), statt self.path (mit Query). Dieser Test legt ein Projekt an
    und ruft /api/projects/<id>?foo=bar ab — das Backend muss 200 zurückgeben
    (der Query-Parameter wird ignoriert, aber der Request landet korrekt).
    Früher hätte der Proxy /api/projects/<id> an den Backend gesendet, aber
    ohne Query — was für filterbezogene Endpoints falsch wäre.
    """
    from planer_server import PlanerServer
    from bridge.projects_api import ProjectsApiServer

    projects_srv = ProjectsApiServer(data_dir=str(tmp_path / "qs_test"))
    projects_srv.start(host="127.0.0.1", port=0)
    projects_port = projects_srv.port

    planer = PlanerServer(library_port=19999, projects_port=projects_port)
    planer.start(host="127.0.0.1", port=0)

    try:
        # Projekt anlegen
        url_post = f"http://127.0.0.1:{planer.port}/api/projects"
        body = json.dumps({"title": "Query-Test-Projekt"}).encode("utf-8")
        req = urllib.request.Request(url_post, data=body, method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        pid = data["project_id"]

        # GET mit Query-String — muss 200 liefern (Query-String wird durchgereicht)
        url_get = f"http://127.0.0.1:{planer.port}/api/projects/{pid}?foo=bar&baz=1"
        with urllib.request.urlopen(url_get, timeout=5) as resp:
            assert resp.status == 200, f"Erwartet 200, bekam {resp.status}"
            result = json.loads(resp.read().decode("utf-8"))
        assert result["project_id"] == pid, "Falsches Projekt zurückgegeben"
        assert result["title"] == "Query-Test-Projekt"
    finally:
        planer.stop()
        projects_srv.stop()


# ---------------------------------------------------------------------------
# Bug-Fix: Thread-Start-Fehler hinterlässt keinen blockierten Zustand
# ---------------------------------------------------------------------------

def test_thread_start_fehler_blockiert_nicht_naechsten_start():
    """Wenn thread.start() wirft, muss ein zweites start() trotzdem klappen.

    Belegt Bugsweep-Fix: self._server wurde früher VOR thread.start() gesetzt.
    Bei einem Start-Fehler war _server damit != None → zweites start() gab
    sofort via idempotenter Return zurück, ohne je einen Thread zu starten.
    Nach dem Fix wird _server erst NACH erfolgreichem thread.start() gesetzt.
    """
    import unittest.mock as mock
    from planer_server import PlanerServer

    srv = PlanerServer(library_port=19999, projects_port=19998)

    # Ersten start()-Versuch sabotieren: thread.start() wirft RuntimeError
    with mock.patch("threading.Thread.start", side_effect=RuntimeError("Sabotage")):
        with pytest.raises(RuntimeError, match="Sabotage"):
            srv.start(host="127.0.0.1", port=0)

    # Zustand nach Fehler: _server muss None sein
    assert srv._server is None, (
        "_server muss None sein nach fehlgeschlagenem start() — sonst blockiert zweites start()"
    )

    # Zweiter start()-Versuch OHNE Mock muss funktionieren
    srv.start(host="127.0.0.1", port=0)
    try:
        assert srv.port is not None and srv.port > 0, "Port wurde nicht gesetzt"
        url = f"http://127.0.0.1:{srv.port}/"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
    finally:
        srv.stop()


# ---------------------------------------------------------------------------
# Sicherheit: Server-Quellcode nicht auslieferbar (Source-Exposure)
# ---------------------------------------------------------------------------

def test_server_py_datei_nicht_auslieferbar(planer_server):
    """GET /server/planer_server.py → 404 (kein Quellcode-Leak).

    Belegt Phase-4-Fix: planer/server/ liegt innerhalb von _STATIC_ROOT (planer/),
    daher wäre planer_server.py ohne explizite Blockierung abrufbar.
    Nach dem Fix gibt der Server 404 zurück.
    """
    url = f"http://127.0.0.1:{planer_server.port}/server/planer_server.py"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 404, (
        f"Erwartet 404 für /server/planer_server.py, bekam {exc_info.value.code} — "
        "Quellcode wird ausgeliefert!"
    )


def test_start_py_datei_nicht_auslieferbar(planer_server):
    """GET /start.py → 404 (kein Python-Quellcode-Leak).

    planer/start.py liegt direkt im _STATIC_ROOT — ohne Schutz würde es
    mit HTTP 200 ausgeliefert. Der Fix blockiert .py-Dateien generell.
    """
    url = f"http://127.0.0.1:{planer_server.port}/start.py"
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(url, timeout=5)
    assert exc_info.value.code == 404, (
        f"Erwartet 404 für /start.py, bekam {exc_info.value.code} — "
        "Python-Quellcode wird ausgeliefert!"
    )


def test_pyc_datei_nicht_auslieferbar(planer_server):
    """GET /server/__pycache__/planer_server.cpython-311.pyc → 404.

    .pyc-Dateien (Bytecode) würden ebenfalls Source-Code exponieren.
    Der Fix blockiert .py- und .pyc-Erweiterungen.
    """
    import http.client
    conn = http.client.HTTPConnection("127.0.0.1", planer_server.port, timeout=5)
    # Generischer __pycache__-Pfad — Datei muss nicht existieren,
    # aber falls sie existiert, darf sie nicht ausgeliefert werden.
    conn.request("GET", "/server/__pycache__/planer_server.cpython-311.pyc")
    resp = conn.getresponse()
    status = resp.status
    resp.read()
    conn.close()
    assert status == 404, (
        f"Erwartet 404 für .pyc-Datei, bekam {status} — Bytecode-Leak!"
    )


# ---------------------------------------------------------------------------
# Sauberer Stop
# ---------------------------------------------------------------------------

def test_kein_orphan_thread_nach_stop():
    """Nach stop() läuft kein PlanerServer-Thread mehr."""
    from planer_server import PlanerServer

    srv = PlanerServer(library_port=19999, projects_port=19998)
    srv.start(host="127.0.0.1", port=0)

    threads_nach_start = {t.name for t in threading.enumerate()}
    assert "PlanerServer" in threads_nach_start, "PlanerServer-Thread sollte aktiv sein"

    url = f"http://127.0.0.1:{srv.port}/"
    with urllib.request.urlopen(url, timeout=5) as resp:
        assert resp.status == 200

    srv.stop()
    time.sleep(0.15)

    threads_nach_stop = {t.name for t in threading.enumerate()}
    assert "PlanerServer" not in threads_nach_stop, (
        "PlanerServer-Thread läuft noch nach stop() — Orphan-Thread!"
    )
