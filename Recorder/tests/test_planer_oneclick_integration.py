"""tests.test_planer_oneclick_integration — Tests für One-Click Planer-Integration (TW-KLANGPULTLIGHT-10).

Belegt:
  - MainWindow besitzt _btn_planer mit korrekten Accessibility- und Tooltip-Werten
  - _oeffne_planer() ermittelt die richtige URL (via Bridge oder Fallback) und meldet sie in der Statusleiste
  - Vollständiger 4-Dienste-Verbund: BridgeService startet Library, WS, Projects und PlanerServer
  - Webbrowser-Aufruf erfolgt ohne Fehler
"""
import urllib.request
import pytest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication

from audio.device_manager import DeviceManager
from audio.engine import AudioEngine
from core.app_state import AppState
from core.config import AppConfig
from recordings.library import RecordingLibrary
from ui.main_window import MainWindow
from bridge.bridge_service import BridgeService


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def main_window(qt_app, tmp_path):
    cfg = AppConfig(workspace_dir=str(tmp_path / "ws"))
    dm = DeviceManager()
    eng = AudioEngine(cfg, channels=[])
    lib = RecordingLibrary(str(tmp_path / "ws"))
    st = AppState()
    win = MainWindow(
        config=cfg,
        device_manager=dm,
        engine=eng,
        library=lib,
        state=st,
    )
    yield win
    try:
        win.close()
    except Exception:
        pass


def test_main_window_planer_button_properties(main_window):
    """MainWindow besitzt den Planer-Button mit A11y- und Tooltip-Properties."""
    btn = getattr(main_window, "_btn_planer", None)
    assert btn is not None, "_btn_planer wurde nicht initialisiert"
    assert "Planer" in btn.text()
    assert "Planer" in btn.accessibleName()
    assert "http" in btn.toolTip()


def test_main_window_oeffne_planer_dispatch(main_window):
    """_oeffne_planer öffnet den Browser mit der Ziel-URL und aktualisiert die Statusleiste."""
    opened_urls = []

    with patch("webbrowser.open", side_effect=lambda url: opened_urls.append(url)):
        url = main_window._oeffne_planer()

    assert url == "http://127.0.0.1:8770/"
    assert opened_urls == ["http://127.0.0.1:8770/"]
    assert "Planer im Browser geöffnet" in main_window._statusleiste.currentMessage()


def test_main_window_oeffne_planer_mit_aktiver_bridge(main_window, tmp_path):
    """_oeffne_planer übernimmt dynamischen Port aus aktiver BridgeService-Instanz."""
    srv = BridgeService(
        library_port=0,
        ws_port=0,
        projects_port=0,
        planer_port=0,
        projects_data_dir=str(tmp_path / "data"),
    )
    srv.start()
    try:
        main_window.set_bridge(srv)
        opened_urls = []
        with patch("webbrowser.open", side_effect=lambda url: opened_urls.append(url)):
            url = main_window._oeffne_planer()

        assert srv.planer_port is not None and srv.planer_port > 0
        assert url == f"http://127.0.0.1:{srv.planer_port}/"
        assert opened_urls == [url]
    finally:
        srv.stop()


def test_bridge_service_und_planer_http_request(tmp_path):
    """Verifiziert, dass über den kombinierten BridgeService statische Planer-Seiten erreichbar sind."""
    srv = BridgeService(
        library_port=0,
        ws_port=0,
        projects_port=0,
        planer_port=0,
        projects_data_dir=str(tmp_path / "data"),
    )
    srv.start()
    try:
        url = f"http://127.0.0.1:{srv.planer_port}/"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            content = resp.read().decode("utf-8")
            assert "Klangpult light" in content
    finally:
        srv.stop()
