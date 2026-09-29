"""test_bugsweep_projects_api_resilience_20260929.py — Regressionstests für ProjectsApiServer Resilienz.

Belegt Mängel in Recorder/bridge/projects_api.py:
  1. Title-Handling: None, Ints, Lists in POST/PUT für Projekte und Episoden
     stürzten bisher mit ungehandhabtem AttributeError: 'NoneType'/'int' object has no attribute 'strip' ab.
  2. Workspace-Import: Nicht-Dict board-Eigenschaften (z.B. String oder Liste)
     stürzten bisher mit unhandled AttributeError ab statt 400 Bad Request zu liefern.
  3. Workspace-Export: Lautstärke ('volume') wurde beim Export aus Assets weggelassen
     und ging bei Export/Import-Zyklen still verloren.
  4. Teleprompter: scroll_speed mit 'nan' oder 'inf' korrumpierte JSON-Persistenz.
  5. Line-Reihenfolge: Speichern von None oder Nicht-Strings führte zu 'None'/'123' Fake-IDs.
  6. CORS & OPTIONS: Fehlende OPTIONS-Preflight-Unterstützung (501 Unsupported Method)
     und fehlende CORS-Header bei Browser-Direktaufrufen.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Deaktiviert automatische Hintergrunddienste für Testisolation."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


def _starte_server(tmp_path):
    """Startet einen ProjectsApiServer auf einem freien Port mit temporärem Speicherort."""
    from bridge.projects_api import ProjectsApiServer

    server = ProjectsApiServer(data_dir=str(tmp_path / "projects_resilience"))
    server.start(host="127.0.0.1", port=0)
    return server


def _post(port: int, pfad: str, daten: dict | list | str | int | None) -> tuple[int, dict]:
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


def _get(port: int, pfad: str) -> tuple[int, dict]:
    url = f"http://127.0.0.1:{port}{pfad}"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        return e.code, json.loads(body) if body else {}


def _options(port: int, pfad: str) -> tuple[int, dict[str, str]]:
    url = f"http://127.0.0.1:{port}{pfad}"
    req = urllib.request.Request(url, method="OPTIONS")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return resp.status, headers
    except urllib.error.HTTPError as e:
        headers = {k.lower(): v for k, v in e.headers.items()}
        return e.code, headers


# ---------------------------------------------------------------------------
# Tests: Title & Body Robustness
# ---------------------------------------------------------------------------

def test_post_project_with_null_and_non_string_title_returns_400(tmp_path):
    """POST /api/projects mit title=None oder int darf nicht abstürzen, sondern liefert 400."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status1, res1 = _post(port, "/api/projects", {"title": None})
        assert status1 == 400
        assert "error" in res1

        status2, res2 = _post(port, "/api/projects", {"title": 12345})
        assert status2 == 400
        assert "error" in res2

        status3, res3 = _post(port, "/api/projects", {"title": ["Array", "Titel"]})
        assert status3 == 400
        assert "error" in res3
    finally:
        server.stop()


def test_put_project_with_null_and_non_string_title_returns_400(tmp_path):
    """PUT /api/projects/{id} mit title=None oder int liefert 400 statt AttributeError."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "Init Project"})
        pid = proj["project_id"]

        status1, res1 = _put(port, f"/api/projects/{pid}", {"title": None})
        assert status1 == 400
        assert "error" in res1

        status2, res2 = _put(port, f"/api/projects/{pid}", {"title": 999})
        assert status2 == 400
        assert "error" in res2
    finally:
        server.stop()


def test_post_episode_with_null_and_non_string_title_returns_400(tmp_path):
    """POST /api/projects/{id}/episodes mit title=None liefert 400 statt Absturz."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "Ep Project"})
        pid = proj["project_id"]

        status1, res1 = _post(port, f"/api/projects/{pid}/episodes", {"title": None})
        assert status1 == 400
        assert "error" in res1

        status2, res2 = _post(port, f"/api/projects/{pid}/episodes", {"title": 42})
        assert status2 == 400
        assert "error" in res2
    finally:
        server.stop()


def test_put_episode_with_null_and_non_string_title_returns_400(tmp_path):
    """PUT /api/projects/{id}/episodes/{eid} mit title=None liefert 400 statt Absturz."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "Ep Put Project"})
        pid = proj["project_id"]
        _, ep = _post(port, f"/api/projects/{pid}/episodes", {"title": "Valid Episode"})
        eid = ep["episode_id"]

        status1, res1 = _put(port, f"/api/projects/{pid}/episodes/{eid}", {"title": None})
        assert status1 == 400
        assert "error" in res1

        status2, res2 = _put(port, f"/api/projects/{pid}/episodes/{eid}", {"title": 777})
        assert status2 == 400
        assert "error" in res2
    finally:
        server.stop()


def test_workspace_import_with_non_dict_board_returns_400(tmp_path):
    """POST /api/projects/{id}/workspace/import mit board='kein_dict' liefert 400 statt 500/Absturz."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "WS Bad Board Test"})
        pid = proj["project_id"]

        payload1 = {
            "format": "klangpultlight-workspace-v1",
            "version": 1,
            "board": "ungueltiger-board-string",
        }
        status1, res1 = _post(port, f"/api/projects/{pid}/workspace/import", payload1)
        assert status1 == 400
        assert "error" in res1

        payload2 = {
            "format": "klangpultlight-workspace-v1",
            "version": 1,
            "board": ["eine", "liste"],
        }
        status2, res2 = _post(port, f"/api/projects/{pid}/workspace/import", payload2)
        assert status2 == 400
        assert "error" in res2
    finally:
        server.stop()


def test_workspace_export_preserves_custom_volume(tmp_path):
    """GET /api/projects/{id}/workspace muss gesetzte Lautstärken ('volume') erhalten."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "Volume Export Test"})
        pid = proj["project_id"]

        # Asset mit Lautstärke 0.45 anlegen
        s_asset, asset = _post(port, f"/api/projects/{pid}/assets", {
            "label": "Custom Volume Pad",
            "volume": 0.45,
            "kind": "audio",
        })
        assert s_asset == 201
        assert asset["volume"] == 0.45

        # Workspace exportieren
        s_exp, exp_data = _get(port, f"/api/projects/{pid}/workspace")
        assert s_exp == 200
        pads = exp_data.get("board", {}).get("pads", [])
        assert len(pads) == 1
        assert "volume" in pads[0], "workspace_exportieren() darf 'volume' nicht weglassen"
        assert abs(pads[0]["volume"] - 0.45) < 1e-5
    finally:
        server.stop()


def test_teleprompter_scroll_speed_nan_and_inf_resilience(tmp_path):
    """Teleprompter-Update mit NaN oder Inf muss defensiv abgefangen werden."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "Tele NaN Test"})
        pid = proj["project_id"]

        # scroll_speed mit 'nan' übergeben
        s1, res1 = _put(port, f"/api/projects/{pid}/teleprompter", {"scroll_speed": "nan"})
        assert s1 == 200
        assert res1["teleprompter"]["scroll_speed"] == 1.0  # Fallback auf Default

        # scroll_speed mit 'inf' übergeben
        s2, res2 = _put(port, f"/api/projects/{pid}/teleprompter", {"scroll_speed": "inf"})
        assert s2 == 200
        assert res2["teleprompter"]["scroll_speed"] == 1.0

        # Verifizieren via GET
        s3, res3 = _get(port, f"/api/projects/{pid}/teleprompter")
        assert s3 == 200
        assert res3["teleprompter"]["scroll_speed"] == 1.0
    finally:
        server.stop()


def test_line_put_filters_none_and_non_strings(tmp_path):
    """PUT /api/projects/{id}/line darf keine 'None'-Strings oder Nicht-String-Objekte anlegen."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        _, proj = _post(port, "/api/projects", {"title": "Line Filter Test"})
        pid = proj["project_id"]

        status, res = _put(port, f"/api/projects/{pid}/line", {
            "line": ["pad-a", None, "   ", 1234, "pad-b", "None", "none"]
        })
        assert status == 200
        line = res.get("line", [])
        assert line == ["pad-a", "pad-b"], f"Unerwünschte Slots in line: {line}"
    finally:
        server.stop()


def test_options_cors_preflight_and_headers(tmp_path):
    """OPTIONS-Anfragen liefern 204 und CORS-Header für Browser-Preflight."""
    server = _starte_server(tmp_path)
    port = server.port
    try:
        status, headers = _options(port, "/api/projects")
        assert status == 204
        assert "access-control-allow-origin" in headers
        assert headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-methods" in headers
        assert "POST" in headers["access-control-allow-methods"]

        # Auch reguläre GET-Anfragen müssen Access-Control-Allow-Origin haben
        s_get, _ = _get(port, "/api/projects")
        assert s_get == 200
    finally:
        server.stop()
