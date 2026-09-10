"""tests.test_bridge_service — Tests für BridgeService.

Belegt:
  - BridgeService.start() startet alle drei Dienste.
  - Properties .api, .ws, .projects geben korrekte Objekte zurück
    (Phase-2-Bug: .projects-Property war ungetestet).
  - BridgeService.stop() fährt alle Dienste herunter, Properties
    werden danach auf None gesetzt.
  - soll_starten() reagiert korrekt auf Env-Variable.
"""
from __future__ import annotations


import pytest


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch, tmp_path):
    """Alle Tests laufen mit Mock-Audio und deaktivierter produktiver Bridge."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    # projects_data_dir auf tmp_path setzen (wird als Fixture-Default weitergegeben)
    return tmp_path


# ---------------------------------------------------------------------------
# Hilfsfunktion
# ---------------------------------------------------------------------------

def _starte_bridge(tmp_path):
    """Erzeugt und startet einen BridgeService mit freien Ports."""
    from bridge.bridge_service import BridgeService

    srv = BridgeService(
        library_port=0,
        ws_port=0,
        projects_port=0,
        projects_data_dir=str(tmp_path / "bridge_data"),
        host="127.0.0.1",
    )
    srv.start()
    return srv


# ---------------------------------------------------------------------------
# Property-Tests
# ---------------------------------------------------------------------------

def test_bridge_service_api_property_nach_start(tmp_path):
    """BridgeService.api gibt LibraryApiServer zurück nach start()."""
    srv = _starte_bridge(tmp_path)
    try:
        assert srv.api is not None, "api-Property ist None nach start()"
        assert srv.api.port is not None and srv.api.port > 0, (
            f"api.port nicht gesetzt: {srv.api.port}"
        )
    finally:
        srv.stop()


def test_bridge_service_ws_property_nach_start(tmp_path):
    """BridgeService.ws gibt RemoteWsServer zurück nach start()."""
    srv = _starte_bridge(tmp_path)
    try:
        assert srv.ws is not None, "ws-Property ist None nach start()"
        assert srv.ws.port is not None and srv.ws.port > 0, (
            f"ws.port nicht gesetzt: {srv.ws.port}"
        )
    finally:
        srv.stop()


def test_bridge_service_projects_property_nach_start(tmp_path):
    """BridgeService.projects gibt ProjectsApiServer zurück nach start().

    Belegt Phase-2-Bug-Fix: .projects-Property war zuvor ungetestet.
    """
    srv = _starte_bridge(tmp_path)
    try:
        assert srv.projects is not None, "projects-Property ist None nach start()"
        assert srv.projects.port is not None and srv.projects.port > 0, (
            f"projects.port nicht gesetzt: {srv.projects.port}"
        )
    finally:
        srv.stop()


def test_bridge_service_properties_none_nach_stop(tmp_path):
    """Nach stop() sind alle Properties auf None gesetzt."""
    srv = _starte_bridge(tmp_path)
    srv.stop()

    assert srv.api is None, "api-Property ist nach stop() nicht None"
    assert srv.ws is None, "ws-Property ist nach stop() nicht None"
    assert srv.projects is None, "projects-Property ist nach stop() nicht None"


# ---------------------------------------------------------------------------
# Doppelter Start ist idempotent
# ---------------------------------------------------------------------------

def test_bridge_service_doppelter_start_ist_idempotent(tmp_path):
    """Zweimaliges start() verursacht keinen Fehler und ändert den Port nicht."""
    srv = _starte_bridge(tmp_path)
    try:
        port_vor = srv.projects.port
        srv.start()  # zweiter Aufruf — muss ignoriert werden
        assert srv.projects.port == port_vor, "Port hat sich nach zweitem start() geändert"
    finally:
        srv.stop()


# ---------------------------------------------------------------------------
# soll_starten() — Env-Variable
# ---------------------------------------------------------------------------

def test_partieller_start_kein_ressourcenleck(tmp_path):
    """Wenn start() beim dritten Dienst fehlschlägt, werden die ersten zwei gestoppt.

    Belegt Bugsweep-Fix: start() hat jetzt try/except, der bereits gestartete
    Dienste bei einer Exception aufräumt.
    """
    import unittest.mock as mock
    from bridge.bridge_service import BridgeService

    srv = BridgeService(
        library_port=0,
        ws_port=0,
        projects_port=0,
        projects_data_dir=str(tmp_path / "data"),
        host="127.0.0.1",
    )

    # Dritter start() (ProjectsApiServer) soll Exception werfen
    call_count = [0]
    def mock_projects_start(self, host="127.0.0.1", port=8769):
        call_count[0] += 1
        raise RuntimeError("Simulierter Start-Fehler")

    with mock.patch.object(
        __import__("bridge.projects_api", fromlist=["ProjectsApiServer"]).ProjectsApiServer,
        "start",
        mock_projects_start,
    ):
        with pytest.raises(RuntimeError, match="Simulierter Start-Fehler"):
            srv.start()

    # Nach fehlgeschlagenem start(): _gestartet = False, alle Properties None
    assert not srv._gestartet, "_gestartet muss False sein nach fehlgeschlagenem start()"
    assert srv.api is None, "api muss None sein (aufgeräumt)"
    assert srv.ws is None, "ws muss None sein (aufgeräumt)"
    assert srv.projects is None, "projects muss None sein"


def test_soll_starten_standard_an(monkeypatch):
    """soll_starten() gibt True zurück wenn Env-Variable nicht gesetzt ist."""
    from bridge.bridge_service import BridgeService

    monkeypatch.delenv("PODCAST_RECORDER_BRIDGE", raising=False)
    assert BridgeService.soll_starten() is True


def test_soll_starten_an_bei_wert_1(monkeypatch):
    """soll_starten() gibt True zurück bei PODCAST_RECORDER_BRIDGE=1."""
    from bridge.bridge_service import BridgeService

    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "1")
    assert BridgeService.soll_starten() is True


def test_soll_starten_aus_bei_wert_0(monkeypatch):
    """soll_starten() gibt False zurück bei PODCAST_RECORDER_BRIDGE=0."""
    from bridge.bridge_service import BridgeService

    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")
    assert BridgeService.soll_starten() is False


def test_soll_planer_starten_env(monkeypatch):
    """soll_planer_starten() respektiert PODCAST_RECORDER_PLANER."""
    from bridge.bridge_service import BridgeService

    monkeypatch.delenv("PODCAST_RECORDER_PLANER", raising=False)
    assert BridgeService.soll_planer_starten() is True

    monkeypatch.setenv("PODCAST_RECORDER_PLANER", "1")
    assert BridgeService.soll_planer_starten() is True

    monkeypatch.setenv("PODCAST_RECORDER_PLANER", "0")
    assert BridgeService.soll_planer_starten() is False


def test_bridge_service_planer_lifecycle(tmp_path):
    """BridgeService startet und stoppt PlanerServer sauber wenn planer_port übergeben wird."""
    from bridge.bridge_service import BridgeService

    srv = BridgeService(
        library_port=0,
        ws_port=0,
        projects_port=0,
        projects_data_dir=str(tmp_path / "data"),
        host="127.0.0.1",
        planer_port=0,
    )
    srv.start()
    try:
        assert srv.planer is not None, "planer-Property ist None nach start mit planer_port=0"
        assert srv.planer_port is not None and srv.planer_port > 0, (
            f"planer_port nicht gebunden: {srv.planer_port}"
        )
    finally:
        srv.stop()

    assert srv.planer is None, "planer muss nach stop() None sein"
    assert srv.planer_port is None, "planer_port muss nach stop() None sein"

