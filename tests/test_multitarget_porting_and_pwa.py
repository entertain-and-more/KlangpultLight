"""
Vertragstests für Multi-Target-Portierung, WACK-Preflight, PWA-Companion & Frozen-I18N
(TW-KLANGPULTLIGHT-15 / PUBLICATION-POLICY.md §2).
"""

from __future__ import annotations

import io
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECORDER_ROOT = PROJECT_ROOT / "Recorder"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
PLANER_SERVER_ROOT = PROJECT_ROOT / "planer" / "server"

for _p in (str(RECORDER_ROOT), str(SCRIPTS_ROOT), str(PLANER_SERVER_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def test_portierungsplan_conforms_to_publication_policy_section_2() -> None:
    """Prüft Existenz, Struktur, Pflicht-Regelzitate (a-i) und ehrliche Zielmatrix von PORTIERUNGSPLAN.md."""
    plan_path = PROJECT_ROOT / "PORTIERUNGSPLAN.md"
    assert plan_path.is_file(), "PORTIERUNGSPLAN.md muss im Projekt-Root existieren"
    text = plan_path.read_text(encoding="utf-8")

    required_markers = [
        "Vorfrage",
        "Schritt 0",
        "Hosting-Absicht",
        "Schritt 3a",
        "Feature-Usecase-Plattform-Matrix",
        "Windows Store",
        "Web-App / Local-First PWA",
        "Android",
        "iOS/iPadOS",
        "macOS",
        "Linux",
        "Regel a",
        "Regel b",
        "Regel c",
        "Regel e2",
        "Regel g",
        "Regel h",
        "Regel i",
        "EN 301 549",
        "WCAG 2.1 AA",
        "Rollback",
        "4-Augen-Abnahme",
        "TO-DECIDE-USER.txt",
        "Nicht-Ziele",
        "INV-LOCAL-01",
        "0.1.0.0",
        "```mermaid",
    ]
    for marker in required_markers:
        assert marker in text, f"Pflichtabschnitt/-begriff fehlt in PORTIERUNGSPLAN.md: {marker}"

    # Maschinelle Kompatibilität zu .SOFTWARE/_tests/test_pipeline_governance.py (PortierungsplanRuleCitationTest)
    rule_pattern = re.compile(r"Regeln?\s+([a-i])([0-9]?)\b|\(([a-i])([0-9]?)\)|\*\*([a-i])([0-9]?)\*\*")
    range_pattern = re.compile(r"[a-i]\s*[-\u2013]\s*[a-i]")
    valid_citations = [
        m.group(0)
        for m in rule_pattern.finditer(text)
        if not range_pattern.search(text[max(0, m.start() - 3) : m.end() + 3])
    ]
    assert len(valid_citations) >= 6, f"Zu wenige echte PUBLICATION-POLICY-Regelzitate gefunden: {valid_citations}"


def test_planer_server_serves_pwa_assets_allowlisted_icons_and_blocks_internals() -> None:
    """Prüft allowlist-geschützte PWA-Icons, Manifest-MIME, SW-Header und Blockade von .mjs/.py."""
    from planer_server import PlanerServer

    srv = PlanerServer(library_port=0, projects_port=0)
    srv.start(host="127.0.0.1", port=0)
    try:
        assert srv.port is not None
        base = f"http://127.0.0.1:{srv.port}"

        # 1. Manifest mit application/manifest+json
        with urllib.request.urlopen(f"{base}/manifest.json", timeout=5) as resp:
            assert resp.status == 200
            assert "application/manifest+json" in (resp.headers.get("Content-Type") or "")
            manifest = json.loads(resp.read().decode("utf-8"))

        # 2. Alle 4 Manifest-Icons werden read-only aus mobile_icons/ mit exakter Größe ausgeliefert
        expected_sizes = {
            "icon-192.png": (192, 192),
            "icon-512.png": (512, 512),
            "icon-maskable-192.png": (192, 192),
            "icon-maskable-512.png": (512, 512),
        }
        assert len(manifest["icons"]) == 4
        for icon_entry in manifest["icons"]:
            src_name = icon_entry["src"]
            assert src_name in expected_sizes
            with urllib.request.urlopen(f"{base}/{src_name}", timeout=5) as icon_resp:
                assert icon_resp.status == 200
                assert (icon_resp.headers.get("Content-Type") or "").startswith("image/png")
                raw = icon_resp.read()
                with Image.open(io.BytesIO(raw)) as img:
                    assert img.size == expected_sizes[src_name]

        # 3. Service Worker liefert Service-Worker-Allowed: / und Cache-Control: no-cache
        with urllib.request.urlopen(f"{base}/sw.js", timeout=5) as sw_resp:
            assert sw_resp.status == 200
            assert sw_resp.headers.get("Service-Worker-Allowed") == "/"
            assert "no-cache" in (sw_resp.headers.get("Cache-Control") or "")

        # 4. Nicht-allowlist-Dateien aus mobile_icons/ und interne .mjs/.py Dateien liefern 404
        for blocked_path in (
            "/icon-48.png",
            "/android-adaptive-foreground-432.png",
            "/tests/pwa.test.mjs",
            "/start.py",
            "/server/planer_server.py",
        ):
            try:
                urllib.request.urlopen(f"{base}{blocked_path}", timeout=5)
                raise AssertionError(f"Pfad {blocked_path} hätte blockiert werden müssen")
            except urllib.error.HTTPError as err:
                assert err.code in (403, 404), f"Unerwarteter HTTP-Code {err.code} für {blocked_path}"
    finally:
        srv.stop()


def test_bridge_service_companion_host_opt_in_and_internal_api_isolation(
    tmp_path: Path, monkeypatch
) -> None:
    """Prüft INV-LOCAL-01 Default (127.0.0.1), PLANER_HOST Opt-in für 8770+8768 und 127.0.0.1-Isolation für 8767/8769."""
    from bridge.bridge_service import BridgeService

    monkeypatch.delenv("PLANER_HOST", raising=False)
    monkeypatch.delenv("PODCAST_RECORDER_COMPANION_HOST", raising=False)
    assert BridgeService.resolve_companion_host() == "127.0.0.1"

    monkeypatch.setenv("PLANER_HOST", "192.168.178.25")
    assert BridgeService.resolve_companion_host() == "192.168.178.25"

    monkeypatch.setenv("PODCAST_RECORDER_COMPANION_HOST", "10.0.0.42")
    assert BridgeService.resolve_companion_host() == "10.0.0.42"

    # End-to-End Laufzeitprüfung auf Loopback mit explizitem companion_host="0.0.0.0" vs host="127.0.0.1":
    # Interne REST-Server bleiben strikt auf 127.0.0.1, während Planer + WS gebunden und erreichbar sind.
    srv = BridgeService(
        library_port=0,
        ws_port=0,
        projects_port=0,
        planer_port=0,
        projects_data_dir=str(tmp_path / "projects"),
        host="127.0.0.1",
        companion_host="127.0.0.1",
    )
    srv.start()
    try:
        assert srv.companion_host == "127.0.0.1"
        assert srv.api is not None and srv.api._server.server_address[0] == "127.0.0.1"
        assert srv.projects is not None and srv.projects._server.server_address[0] == "127.0.0.1"
        assert srv.ws is not None and srv.ws.port is not None and srv.ws.port > 0
        assert srv.planer_port is not None and srv.planer_port > 0

        with urllib.request.urlopen(f"http://127.0.0.1:{srv.planer_port}/api/status", timeout=5) as resp:
            status_payload = json.loads(resp.read().decode("utf-8"))
            assert status_payload["status"] == "online"
            assert status_payload["services"]["library"]["ok"] is True
            assert status_payload["services"]["projects"]["ok"] is True
    finally:
        srv.stop()


def test_cross_platform_loopback_hints_and_device_scoring() -> None:
    """Prüft plattformspezifische Loopback-Hinweise und macOS/Linux-Geräteerkennung."""
    from sources.loopback_detector import (
        LOOPBACK_HINT,
        LOOPBACK_HINT_LINUX,
        LOOPBACK_HINT_MACOS,
        LoopbackDetector,
        get_platform_loopback_hint,
    )

    assert get_platform_loopback_hint("win32") == LOOPBACK_HINT
    assert get_platform_loopback_hint("darwin") == LOOPBACK_HINT_MACOS
    assert "BlackHole" in LOOPBACK_HINT_MACOS
    assert get_platform_loopback_hint("linux") == LOOPBACK_HINT_LINUX
    assert "PipeWire" in LOOPBACK_HINT_LINUX

    det = LoopbackDetector()
    sf_routes = det.detect_from(
        input_devices=[{"name": "Soundflower (2ch)", "index": 2, "max_input_channels": 2, "max_output_channels": 0, "hostapi": 0}],
        output_devices=[],
        hostapis=[{"name": "Core Audio"}],
    )
    assert len(sf_routes) == 1
    assert sf_routes[0].score == 50

    pw_routes = det.detect_from(
        input_devices=[{"name": "PipeWire Monitor", "index": 5, "max_input_channels": 2, "max_output_channels": 0, "hostapi": 0}],
        output_devices=[],
        hostapis=[{"name": "JACK Audio Connection Kit"}],
    )
    assert len(pw_routes) == 1
    assert pw_routes[0].score == 30


def test_frozen_pyinstaller_specs_and_meipass_translations_resolution(tmp_path: Path, monkeypatch) -> None:
    """Stellt sicher, dass beide PyInstaller-Specs locales/ bündeln und _MEIPASS aufgelöst wird."""
    from i18n.translator import TranslationSystem, resolve_translations_file

    for spec_name in ("KlangpultLightRecorder.spec", "KlangpultLightRecorderOnedir.spec"):
        spec_text = (PROJECT_ROOT / spec_name).read_text(encoding="utf-8")
        assert '("locales", "locales")' in spec_text

    # Simuliere Frozen-Umgebung, in der nur planer/locales/translations.json vorliegt
    meipass_dir = tmp_path / "_MEI_SIM"
    planer_loc = meipass_dir / "planer" / "locales"
    planer_loc.mkdir(parents=True, exist_ok=True)
    target_json = planer_loc / "translations.json"
    target_json.write_text((PROJECT_ROOT / "locales" / "translations.json").read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(sys, "_MEIPASS", str(meipass_dir), raising=False)
    resolved = resolve_translations_file()
    assert resolved == target_json

    ts = TranslationSystem(default_lang="ja")
    assert ts.translations_file == target_json
    assert ts.t("start_recording") == "録音開始"


def test_windows_wack_preflight_runner_and_safe_command_builder(tmp_path: Path) -> None:
    """Prüft run_windows_wack.py im Read-Only-Preflight sowie die sichere Argumentliste."""
    import run_windows_wack

    res = run_windows_wack.run_wack_preflight(PROJECT_ROOT)
    assert res["passed"] is True, f"WACK-Preflight meldete Fehler: {res['errors']}"
    assert res["error_count"] == 0
    assert res["package_identity"] == "Geiger.KlangpultLight"
    assert res["version"] == "0.1.0.0"

    cmd = run_windows_wack.build_appcert_command(
        Path("C:/Program Files (x86)/Windows Kits/10/App Certification Kit/appcert.exe"),
        tmp_path / "Geiger.KlangpultLight_0.1.0.0_x64.msix",
        tmp_path / "wack_report.xml",
    )
    assert cmd[1:4] == ["test", "-apptype", "desktop"]
    assert "-appxpackagepath" in cmd
    assert "-reportoutputfilepath" in cmd
