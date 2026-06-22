"""tests.test_projects_api — Tests für den ProjectsApiServer.

Belegt:
  - GET  /api/projects       → leere oder befüllte Projektliste
  - POST /api/projects        → Projekt anlegen (Titel, Beschreibung)
  - GET  /api/projects/{id}   → einzelnes Projekt abrufen
  - PUT  /api/projects/{id}   → Projekt aktualisieren
  - DELETE /api/projects/{id} → Projekt löschen
  - POST /api/projects/{id}/episodes → Episode anlegen
  - GET  /api/projects/{id}/episodes → Episodenliste abrufen
  - Persistenz: nach Neustart des Servers sind Projekte noch vorhanden
  - 404 bei unbekanntem Projekt-ID
  - Alle Antworten sind UTF-8 JSON (keine BOM, echte Umlaute)
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit deaktivierter Bridge (Auto-Start unterdrücken)."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


def _starte_server(tmp_path):
    """Hilfsfunktion: ProjectsApiServer starten und Port zurückgeben."""
    from bridge.projects_api import ProjectsApiServer

    server = ProjectsApiServer(data_dir=str(tmp_path / "projects"))
    server.start(host="127.0.0.1", port=0)
    return server


def _get(port: int, pfad: str) -> tuple[int, dict]:
    """HTTP GET, gibt (status_code, json_dict) zurück."""
    url = f"http://127.0.0.1:{port}{pfad}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, json.loads(body) if body else {}


def _post(port: int, pfad: str, daten: dict) -> tuple[int, dict]:
    """HTTP POST mit JSON-Body, gibt (status_code, json_dict) zurück."""
    url = f"http://127.0.0.1:{port}{pfad}"
    body = json.dumps(daten, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        return e.code, json.loads(body_bytes.decode("utf-8")) if body_bytes else {}


def _put(port: int, pfad: str, daten: dict) -> tuple[int, dict]:
    """HTTP PUT mit JSON-Body, gibt (status_code, json_dict) zurück."""
    url = f"http://127.0.0.1:{port}{pfad}"
    body = json.dumps(daten, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="PUT",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body_bytes = e.read()
        return e.code, json.loads(body_bytes.decode("utf-8")) if body_bytes else {}


def _delete(port: int, pfad: str) -> int:
    """HTTP DELETE, gibt status_code zurück."""
    url = f"http://127.0.0.1:{port}{pfad}"
    req = urllib.request.Request(url, method="DELETE")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code


# ---------------------------------------------------------------------------
# /api/health
# ---------------------------------------------------------------------------

def test_health_endpoint(tmp_path):
    """GET /api/health liefert HTTP 200 und {"status": "ok"}."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, daten = _get(port, "/api/health")
        assert status == 200
        assert daten == {"status": "ok"}
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# /api/projects — Liste + Anlegen
# ---------------------------------------------------------------------------

def test_projekte_leer_am_anfang(tmp_path):
    """GET /api/projects gibt leere Liste zurück wenn noch kein Projekt existiert."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, daten = _get(port, "/api/projects")
        assert status == 200, f"Erwartet 200, bekam {status}"
        assert "projects" in daten, f"'projects'-Schlüssel fehlt: {daten}"
        assert daten["projects"] == [], f"Erwartet leere Liste: {daten}"
    finally:
        server.stop()


def test_projekt_anlegen(tmp_path):
    """POST /api/projects legt ein neues Projekt an und gibt es zurück."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, daten = _post(port, "/api/projects", {
            "title": "Folge 1 — Einführung",
            "description": "Erste Episode des Podcasts über KI-Themen",
        })
        assert status == 201, f"Erwartet 201, bekam {status}: {daten}"
        assert "project_id" in daten, f"'project_id' fehlt: {daten}"
        assert daten["title"] == "Folge 1 — Einführung"
        assert daten["description"] == "Erste Episode des Podcasts über KI-Themen"
        assert "created_at" in daten
    finally:
        server.stop()


def test_projekt_anlegen_umlaute(tmp_path):
    """Projekttitel mit echten Umlauten werden korrekt gespeichert und zurückgegeben."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, daten = _post(port, "/api/projects", {
            "title": "Über KI und Öffentlichkeit",
            "description": "Diskussion über Ängste und Möglichkeiten",
        })
        assert status == 201
        assert daten["title"] == "Über KI und Öffentlichkeit"
        assert daten["description"] == "Diskussion über Ängste und Möglichkeiten"
    finally:
        server.stop()


def test_projekte_liste_nach_anlegen(tmp_path):
    """Angelegte Projekte erscheinen in der Liste."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _post(port, "/api/projects", {"title": "Projekt Alpha"})
        _post(port, "/api/projects", {"title": "Projekt Beta"})

        status, daten = _get(port, "/api/projects")
        assert status == 200
        titel = {p["title"] for p in daten["projects"]}
        assert "Projekt Alpha" in titel
        assert "Projekt Beta" in titel
    finally:
        server.stop()


def test_projekt_anlegen_ohne_pflichtfeld(tmp_path):
    """POST /api/projects ohne 'title' liefert HTTP 400."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, _ = _post(port, "/api/projects", {"description": "Kein Titel"})
        assert status == 400, f"Erwartet 400, bekam {status}"
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# /api/projects/{id} — Einzelabruf + Update + Löschen
# ---------------------------------------------------------------------------

def test_einzelnes_projekt_abrufen(tmp_path):
    """GET /api/projects/{id} gibt das Projekt zurück."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, angelegt = _post(port, "/api/projects", {"title": "Einzelprojekt"})
        pid = angelegt["project_id"]

        status, daten = _get(port, f"/api/projects/{pid}")
        assert status == 200
        assert daten["project_id"] == pid
        assert daten["title"] == "Einzelprojekt"
    finally:
        server.stop()


def test_unbekanntes_projekt_liefert_404(tmp_path):
    """GET /api/projects/unbekannt liefert HTTP 404."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, _ = _get(port, "/api/projects/nicht-vorhanden-id")
        assert status == 404, f"Erwartet 404, bekam {status}"
    finally:
        server.stop()


def test_projekt_aktualisieren(tmp_path):
    """PUT /api/projects/{id} aktualisiert Titel und Beschreibung."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, angelegt = _post(port, "/api/projects", {
            "title": "Alter Titel",
            "description": "Alte Beschreibung",
        })
        pid = angelegt["project_id"]

        status, daten = _put(port, f"/api/projects/{pid}", {
            "title": "Neuer Titel",
            "description": "Neue Beschreibung",
        })
        assert status == 200, f"Erwartet 200, bekam {status}: {daten}"
        assert daten["title"] == "Neuer Titel"
        assert daten["description"] == "Neue Beschreibung"

        # Auch beim erneuten GET vorhanden
        _, abgerufen = _get(port, f"/api/projects/{pid}")
        assert abgerufen["title"] == "Neuer Titel"
    finally:
        server.stop()


def test_projekt_loeschen(tmp_path):
    """DELETE /api/projects/{id} entfernt das Projekt."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, angelegt = _post(port, "/api/projects", {"title": "Zu löschen"})
        pid = angelegt["project_id"]

        status = _delete(port, f"/api/projects/{pid}")
        assert status == 204, f"Erwartet 204, bekam {status}"

        # Danach 404
        status2, _ = _get(port, f"/api/projects/{pid}")
        assert status2 == 404
    finally:
        server.stop()


def test_projekt_loeschen_unbekannt_liefert_404(tmp_path):
    """DELETE /api/projects/unbekannt liefert HTTP 404."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status = _delete(port, "/api/projects/nicht-vorhanden")
        assert status == 404, f"Erwartet 404, bekam {status}"
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# /api/projects/{id}/episodes — Episodenverwaltung
# ---------------------------------------------------------------------------

def test_episoden_liste_leer(tmp_path):
    """GET /api/projects/{id}/episodes gibt leere Liste zurück bei neuem Projekt."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, p = _post(port, "/api/projects", {"title": "Podcast X"})
        pid = p["project_id"]

        status, daten = _get(port, f"/api/projects/{pid}/episodes")
        assert status == 200
        assert "episodes" in daten
        assert daten["episodes"] == []
    finally:
        server.stop()


def test_episode_anlegen(tmp_path):
    """POST /api/projects/{id}/episodes legt eine Episode an."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, p = _post(port, "/api/projects", {"title": "Podcast Y"})
        pid = p["project_id"]

        status, daten = _post(port, f"/api/projects/{pid}/episodes", {
            "title": "Episode 1: Pilot",
            "notes": "Einführungsfolge über das Format",
            "status": "geplant",
        })
        assert status == 201, f"Erwartet 201, bekam {status}: {daten}"
        assert "episode_id" in daten
        assert daten["title"] == "Episode 1: Pilot"
        assert daten["notes"] == "Einführungsfolge über das Format"
        assert daten["status"] == "geplant"
    finally:
        server.stop()


def test_episoden_liste_nach_anlegen(tmp_path):
    """Angelegte Episoden erscheinen in der Episodenliste."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, p = _post(port, "/api/projects", {"title": "Podcast Z"})
        pid = p["project_id"]

        _post(port, f"/api/projects/{pid}/episodes", {"title": "Episode 1"})
        _post(port, f"/api/projects/{pid}/episodes", {"title": "Episode 2"})

        status, daten = _get(port, f"/api/projects/{pid}/episodes")
        assert status == 200
        titel = {e["title"] for e in daten["episodes"]}
        assert "Episode 1" in titel
        assert "Episode 2" in titel
    finally:
        server.stop()


def test_episoden_fremdes_projekt_liefert_404(tmp_path):
    """GET /api/projects/unbekannt/episodes liefert HTTP 404."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, _ = _get(port, "/api/projects/nicht-vorhanden/episodes")
        assert status == 404
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Persistenz: Daten überleben Server-Neustart
# ---------------------------------------------------------------------------

def test_persistenz_nach_neustart(tmp_path):
    """Angelegte Projekte und Episoden sind nach Server-Neustart noch vorhanden."""
    from bridge.projects_api import ProjectsApiServer

    data_dir = str(tmp_path / "projects")

    # Erster Server: Projekt + Episode anlegen
    server1 = ProjectsApiServer(data_dir=data_dir)
    server1.start(host="127.0.0.1", port=0)
    port1 = server1.port
    try:
        _, p = _post(port1, "/api/projects", {"title": "Persistenz-Test"})
        pid = p["project_id"]
        _post(port1, f"/api/projects/{pid}/episodes", {"title": "Episode persistent"})
    finally:
        server1.stop()

    # Zweiter Server: gleicher data_dir
    server2 = ProjectsApiServer(data_dir=data_dir)
    server2.start(host="127.0.0.1", port=0)
    port2 = server2.port
    try:
        status, daten = _get(port2, "/api/projects")
        assert status == 200
        titel = {p["title"] for p in daten["projects"]}
        assert "Persistenz-Test" in titel, f"Projekt fehlt nach Neustart: {titel}"

        # Episoden prüfen
        status_ep, ep_daten = _get(port2, f"/api/projects/{pid}/episodes")
        assert status_ep == 200
        ep_titel = {e["title"] for e in ep_daten["episodes"]}
        assert "Episode persistent" in ep_titel, f"Episode fehlt nach Neustart: {ep_titel}"
    finally:
        server2.stop()


# ---------------------------------------------------------------------------
# Atomic-Write: keine .tmp-Datei verbleibt nach erfolgreichem Schreiben
# ---------------------------------------------------------------------------

def test_atomic_write_keine_tmp_datei(tmp_path):
    """Nach einem Schreibvorgang darf keine .json.tmp-Datei übrig bleiben.

    Belegt Bugsweep-Fix: _json_schreiben() nutzt jetzt Temp-Datei + os.replace()
    statt direktem Überschreiben — die .tmp-Datei muss atomar umbenannt werden.
    """
    from bridge.projects_api import ProjectsApiServer
    from pathlib import Path

    data_dir = tmp_path / "atomic_data"
    server = ProjectsApiServer(data_dir=str(data_dir))
    server.start(host="127.0.0.1", port=0)
    port = server.port

    try:
        _post(port, "/api/projects", {"title": "Atomic-Write-Test"})
    finally:
        server.stop()

    # Nach dem Stop dürfen keine .tmp-Dateien verbleiben
    tmp_dateien = list(Path(data_dir).glob("*.tmp"))
    assert tmp_dateien == [], f"Verbleibende .tmp-Dateien: {tmp_dateien}"

    # projects.json muss vorhanden sein
    projekte_datei = data_dir / "projects.json"
    assert projekte_datei.exists(), "projects.json wurde nicht geschrieben"


# ---------------------------------------------------------------------------
# Bug-Fix: Thread-Start-Fehler blockiert nicht den nächsten start()
# ---------------------------------------------------------------------------

def test_thread_start_fehler_blockiert_nicht_naechsten_start(tmp_path):
    """Wenn thread.start() wirft, muss _server None bleiben.

    Belegt Bugsweep-Fix: self._server wurde vor thread.start() gesetzt.
    Bei Fehler war _server != None → zweites start() gab sofort zurück.
    """
    import unittest.mock as mock
    from bridge.projects_api import ProjectsApiServer

    server = ProjectsApiServer(data_dir=str(tmp_path / "thread_err"))

    with mock.patch("threading.Thread.start", side_effect=RuntimeError("Sabotage")):
        with pytest.raises(RuntimeError, match="Sabotage"):
            server.start(host="127.0.0.1", port=0)

    assert server._server is None, "_server muss None sein nach fehlgeschlagenem start()"

    # Zweites start() muss klappen
    server.start(host="127.0.0.1", port=0)
    try:
        assert server.port is not None and server.port > 0
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# 404 für unbekannte Pfade
# ---------------------------------------------------------------------------

def test_unbekannter_pfad_liefert_404(tmp_path):
    """GET /api/unbekannt liefert HTTP 404."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, _ = _get(port, "/api/unbekannt")
        assert status == 404
    finally:
        server.stop()


# ---------------------------------------------------------------------------
# Episoden-Edit/Delete + Aufnahme-Zuordnung (P1)
# ---------------------------------------------------------------------------

def test_episode_aktualisieren_und_loeschen(tmp_path):
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "P"})
        pid = proj["project_id"]
        s, ep = _post(port, f"/api/projects/{pid}/episodes", {"title": "Folge 1"})
        assert s == 201
        eid = ep["episode_id"]

        s, ep2 = _put(
            port, f"/api/projects/{pid}/episodes/{eid}",
            {"title": "Folge 1 (neu)", "status": "fertig"},
        )
        assert s == 200
        assert ep2["title"] == "Folge 1 (neu)"
        assert ep2["status"] == "fertig"

        s, liste = _get(port, f"/api/projects/{pid}/episodes")
        assert liste["episodes"][0]["title"] == "Folge 1 (neu)"

        assert _delete(port, f"/api/projects/{pid}/episodes/{eid}") == 204
        s, liste = _get(port, f"/api/projects/{pid}/episodes")
        assert liste["episodes"] == []
    finally:
        server.stop()


def test_episode_aktualisieren_unbekannt_404(tmp_path):
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "P"})
        pid = proj["project_id"]
        s, _ = _put(port, f"/api/projects/{pid}/episodes/gibtsnicht", {"title": "X"})
        assert s == 404
    finally:
        server.stop()


def test_aufnahme_zuordnen_idempotent_und_entfernen(tmp_path):
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "P"})
        pid = proj["project_id"]

        s, p2 = _post(port, f"/api/projects/{pid}/recordings/rec_123", {})
        assert s == 200
        assert "rec_123" in p2["recording_ids"]

        # idempotent — kein Duplikat
        _, p3 = _post(port, f"/api/projects/{pid}/recordings/rec_123", {})
        assert p3["recording_ids"].count("rec_123") == 1

        assert _delete(port, f"/api/projects/{pid}/recordings/rec_123") == 200
        _, p4 = _get(port, f"/api/projects/{pid}")
        assert "rec_123" not in (p4.get("recording_ids") or [])
    finally:
        server.stop()


def test_aufnahme_zuordnen_unbekanntes_projekt_404(tmp_path):
    server = _starte_server(tmp_path)
    port = server.port
    try:
        s, _ = _post(port, "/api/projects/gibtsnicht/recordings/rec_1", {})
        assert s == 404
    finally:
        server.stop()
