#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Platform Source-Mode & Multi-Target Smoke Suite — Klangpult light.

Prüft zustandsisoliert (temporäres Workspace-Verzeichnis + isoliertes QSettings-INI-Backend,
keine Berührung realer Nutzerdaten oder Windows-Registry) alle 7 plattformkritischen
Laufzeit-Gates für Windows, macOS, Linux und die gekoppelte Planer-PWA:

  1. qt_offscreen_mainwindow       — Offscreen-PySide6 MainWindow, Icon-Auflösung & 6-Sprachen-UI
  2. mock_recording_session        — Mock-AudioEngine + RecordingSession -> nicht-leere mix.wav
  3. cross_platform_loopback       — Loopback-Profile & Hinweise für Windows, macOS (BlackHole) & Linux (PipeWire)
  4. i18n_and_frozen_meipass       — 6-Sprachen-Parität & PyInstaller-_MEIPASS-Pfadauflösung
  5. bridge_and_pwa_companion      — BridgeService + PlanerServer (Port 0): Manifest, SW, Allowlist-Icons & API
  6. store_and_wack_preflight      — Windows Store Readiness & WACK Preflight (0 Beanstandungen)
  7. process_priority_cycle        — Unprivilegierter Boost-/Restore-Zyklus (Windows & POSIX)

Aufruf:
    python tests/source_platform_smoke.py [--json]
    pytest -q tests/source_platform_smoke.py
"""

from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RECORDER_ROOT = PROJECT_ROOT / "Recorder"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"

for _p in (str(RECORDER_ROOT), str(SCRIPTS_ROOT), str(PROJECT_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)


def _http_get(url: str, timeout: float = 5.0) -> tuple[int, dict[str, str], bytes]:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        headers = {k.lower(): v for k, v in resp.headers.items()}
        return resp.status, headers, resp.read()


def run_smoke_suite(project_root: Path = PROJECT_ROOT) -> Dict[str, Any]:
    """Führt alle 7 zustandsisolierten Cross-Platform-Smoke-Gates aus."""
    env_keys = ("QT_QPA_PLATFORM", "PODCAST_RECORDER_MOCK_AUDIO", "PODCAST_RECORDER_MOCK_VIDEO")
    saved_env = {k: os.environ.get(k) for k in env_keys}
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    os.environ["PODCAST_RECORDER_MOCK_AUDIO"] = "1"
    os.environ["PODCAST_RECORDER_MOCK_VIDEO"] = "1"

    from PySide6.QtCore import QSettings
    from PySide6.QtWidgets import QApplication

    import check_store_readiness
    import main as recorder_main
    import run_windows_wack
    from audio.device_manager import DeviceManager
    from audio.engine import AudioEngine
    from audio.mixer_channel import MixerChannel
    from bridge.bridge_service import BridgeService
    from core import process_priority
    from core.app_state import AppState
    from core.config import AppConfig
    from i18n.translator import SUPPORTED_LANGUAGES, TranslationSystem, resolve_translations_file
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession
    from sources.loopback_detector import (
        LOOPBACK_HINT,
        LOOPBACK_HINT_LINUX,
        LOOPBACK_HINT_MACOS,
        LoopbackDetector,
        LoopbackRoute,
        get_platform_loopback_hint,
    )
    from sources.source_config import load_sources_config
    from ui.main_window import MainWindow

    gates: Dict[str, Dict[str, Any]] = {}
    errors: List[str] = []

    prev_qsettings_format = QSettings.defaultFormat()

    try:
        with tempfile.TemporaryDirectory(prefix="klangpult_smoke_") as tmp_base:
            tmp_path = Path(tmp_base)
            qsettings_dir = tmp_path / "qsettings"
            workspace_dir = tmp_path / "workspace"
            projects_dir = workspace_dir / "projects"
            qsettings_dir.mkdir(parents=True, exist_ok=True)
            workspace_dir.mkdir(parents=True, exist_ok=True)
            projects_dir.mkdir(parents=True, exist_ok=True)

            # Strikte QSettings-Zustandsisolation (keine Registry-/User-Profile-Schreibzugriffe)
            QSettings.setDefaultFormat(QSettings.Format.IniFormat)
            QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(qsettings_dir))
            QSettings.setPath(QSettings.Format.IniFormat, QSettings.Scope.SystemScope, str(qsettings_dir))

            app = QApplication.instance() or QApplication([])

            config = AppConfig(workspace_dir=str(workspace_dir), mock_audio=True)
            sources_cfg_path = str(workspace_dir / "sources.json")
            sources_cfg = load_sources_config(sources_cfg_path)
            sources_cfg.set_capture("system", True)

            channels = [
                MixerChannel(source_id="mic_1", name="Mikrofon 1"),
                MixerChannel(source_id="system", name="Systemton"),
            ]
            state = AppState()
            engine = AudioEngine(config, channels, state=state)
            library = RecordingLibrary(str(workspace_dir))
            device_manager = DeviceManager()
            mock_route = LoopbackRoute(
                name="Smoke-Mock-Loopback",
                method="wasapi_loopback",
                device_index=0,
                hostapi="Mock",
                score=100,
            )

            fenster = None
            bridge = None
            try:
                engine.start()

                # --- Gate 1: Offscreen MainWindow, Icon & 6-Sprachen-Umschaltung ---
                icon = recorder_main.load_app_icon()
                fenster = MainWindow(
                    config=config,
                    device_manager=device_manager,
                    engine=engine,
                    library=library,
                    state=state,
                    sources_config=sources_cfg,
                    loopback_route=mock_route,
                    sources_config_path=sources_cfg_path,
                    board_player=None,
                )
                for lang in SUPPORTED_LANGUAGES:
                    fenster._translator.set_language(lang)
                    fenster.retranslate_ui()
                fenster._translator.set_language("de")
                fenster.retranslate_ui()
                app.processEvents()

                gate1_ok = not icon.isNull() and fenster.windowTitle() != ""
                if not gate1_ok:
                    errors.append("Gate 1: Offscreen MainWindow oder App-Icon konnte nicht geladen werden")
                gates["qt_offscreen_mainwindow"] = {
                    "passed": gate1_ok,
                    "icon_loaded": not icon.isNull(),
                    "languages_verified": list(SUPPORTED_LANGUAGES),
                }

                # --- Gate 2: Mock-Aufnahme -> nicht-leere mix.wav ---
                session = RecordingSession(library=library, engine=engine, state=state)
                session.start("Cross-Platform-Smoke")
                time.sleep(0.25)
                meta = session.stop()
                orig = next((b for b in meta.branches if b.is_original), None)
                mix_path = getattr(orig, "audio_path", "") or getattr(orig, "mix_path", "") if orig else ""
                mix_size = Path(mix_path).stat().st_size if mix_path and Path(mix_path).is_file() else 0
                gate2_ok = meta.duration > 0 and mix_size > 44
                if not gate2_ok:
                    errors.append(f"Gate 2: Aufnahme unvollständig (duration={meta.duration}, mix_size={mix_size})")
                gates["mock_recording_session"] = {
                    "passed": gate2_ok,
                    "duration_sec": round(float(meta.duration), 3),
                    "mix_wav_bytes": mix_size,
                }

                # --- Gate 3: Cross-Platform Loopback-Profile (Windows / macOS / Linux) ---
                detector = LoopbackDetector()
                win_routes = detector.detect_from(
                    input_devices=[],
                    output_devices=[
                        {
                            "name": "Speakers (USB Audio)",
                            "index": 3,
                            "max_input_channels": 0,
                            "max_output_channels": 2,
                            "hostapi": 0,
                        }
                    ],
                    hostapis=[{"name": "Windows WASAPI"}],
                )
                mac_routes = detector.detect_from(
                    input_devices=[
                        {
                            "name": "BlackHole 2ch",
                            "index": 1,
                            "max_input_channels": 2,
                            "max_output_channels": 0,
                            "hostapi": 0,
                        }
                    ],
                    output_devices=[],
                    hostapis=[{"name": "Core Audio"}],
                )
                linux_routes = detector.detect_from(
                    input_devices=[
                        {
                            "name": "Monitor of Built-in Audio Analog Stereo",
                            "index": 4,
                            "max_input_channels": 2,
                            "max_output_channels": 0,
                            "hostapi": 0,
                        }
                    ],
                    output_devices=[],
                    hostapis=[{"name": "ALSA"}],
                )
                hints_ok = (
                    get_platform_loopback_hint("win32") == LOOPBACK_HINT
                    and get_platform_loopback_hint("darwin") == LOOPBACK_HINT_MACOS
                    and get_platform_loopback_hint("linux") == LOOPBACK_HINT_LINUX
                )
                gate3_ok = (
                    len(win_routes) == 1
                    and win_routes[0].method == "wasapi_loopback"
                    and len(mac_routes) == 1
                    and mac_routes[0].score == 50
                    and len(linux_routes) == 1
                    and linux_routes[0].score == 30
                    and hints_ok
                )
                if not gate3_ok:
                    errors.append("Gate 3: Cross-Platform Loopback-Profile oder Hinweise fehlerhaft")
                gates["cross_platform_loopback"] = {
                    "passed": gate3_ok,
                    "windows_method": win_routes[0].method if win_routes else None,
                    "macos_device": mac_routes[0].name if mac_routes else None,
                    "linux_device": linux_routes[0].name if linux_routes else None,
                }

                # --- Gate 4: Tier-2 I18N & PyInstaller _MEIPASS Auflösung ---
                ts = TranslationSystem()
                cov = ts.check_coverage()
                fake_meipass = tmp_path / "fake_meipass"
                (fake_meipass / "planer" / "locales").mkdir(parents=True, exist_ok=True)
                src_dict = (project_root / "locales" / "translations.json").read_text(encoding="utf-8")
                target_dict = fake_meipass / "planer" / "locales" / "translations.json"
                target_dict.write_text(src_dict, encoding="utf-8")

                old_meipass = getattr(sys, "_MEIPASS", None)
                had_meipass = hasattr(sys, "_MEIPASS")
                try:
                    sys._MEIPASS = str(fake_meipass)  # type: ignore[attr-defined]
                    resolved_meipass = resolve_translations_file()
                finally:
                    if had_meipass:
                        sys._MEIPASS = old_meipass  # type: ignore[attr-defined]
                    elif hasattr(sys, "_MEIPASS"):
                        delattr(sys, "_MEIPASS")

                gate4_ok = bool(cov["is_complete"]) and resolved_meipass == target_dict
                if not gate4_ok:
                    errors.append("Gate 4: Tier-2 I18N-Abdeckung oder _MEIPASS-Pfadauflösung fehlgeschlagen")
                gates["i18n_and_frozen_meipass"] = {
                    "passed": gate4_ok,
                    "total_keys": cov["total_keys"],
                    "meipass_resolved": resolved_meipass == target_dict,
                }

                # --- Gate 5: BridgeService + PlanerServer PWA & Allowlist-Icons ---
                bridge = BridgeService(
                    library=library,
                    engine=engine,
                    state=state,
                    library_port=0,
                    ws_port=0,
                    projects_port=0,
                    projects_data_dir=str(projects_dir),
                    host="127.0.0.1",
                    planer_port=0,
                )
                bridge.start()
                p_port = bridge.planer_port
                if not p_port:
                    errors.append("Gate 5: BridgeService hat PlanerServer nicht gestartet")
                    gates["bridge_and_pwa_companion"] = {"passed": False}
                else:
                    base = f"http://127.0.0.1:{p_port}"
                    st_idx, _, body_idx = _http_get(f"{base}/")
                    st_man, hdr_man, body_man = _http_get(f"{base}/manifest.json")
                    st_sw, hdr_sw, _ = _http_get(f"{base}/sw.js")
                    st_ic1, hdr_ic1, body_ic1 = _http_get(f"{base}/icon-192.png")
                    st_ic2, hdr_ic2, body_ic2 = _http_get(f"{base}/icon-512.png")
                    st_api, _, body_api = _http_get(f"{base}/api/status")
                    st_i18n, _, body_i18n = _http_get(f"{base}/api/translations")

                    api_json = json.loads(body_api.decode("utf-8"))
                    manifest_json = json.loads(body_man.decode("utf-8"))
                    i18n_json = json.loads(body_i18n.decode("utf-8"))

                    gate5_ok = (
                        st_idx == 200
                        and b"manifest.json" in body_idx
                        and st_man == 200
                        and "manifest+json" in hdr_man.get("content-type", "")
                        and len(manifest_json.get("icons", [])) == 4
                        and st_sw == 200
                        and hdr_sw.get("service-worker-allowed") == "/"
                        and st_ic1 == 200
                        and hdr_ic1.get("content-type", "").startswith("image/png")
                        and len(body_ic1) > 100
                        and st_ic2 == 200
                        and hdr_ic2.get("content-type", "").startswith("image/png")
                        and len(body_ic2) > 100
                        and st_api == 200
                        and api_json.get("status") == "online"
                        and st_i18n == 200
                        and "app_title" in i18n_json
                    )
                    if not gate5_ok:
                        errors.append("Gate 5: Planer-PWA-Endpunkte oder Allowlist-Icons fehlerhaft")
                    gates["bridge_and_pwa_companion"] = {
                        "passed": gate5_ok,
                        "bridge_status": api_json.get("status"),
                        "pwa_icons_verified": 2,
                    }

                # --- Gate 6: Store Readiness & WACK Preflight ---
                with contextlib.redirect_stdout(io.StringIO()):
                    store_rc = check_store_readiness.run_all_checks(project_root)
                wack_res = run_windows_wack.run_wack_preflight(project_root)
                gate6_ok = store_rc == 0 and bool(wack_res.get("passed"))
                if not gate6_ok:
                    errors.append(
                        f"Gate 6: Store/WACK Preflight fehlgeschlagen (store_rc={store_rc}, wack={wack_res.get('errors')})"
                    )
                gates["store_and_wack_preflight"] = {
                    "passed": gate6_ok,
                    "store_exit_code": store_rc,
                    "wack_error_count": wack_res.get("error_count", -1),
                }

                # --- Gate 7: Unprivilegierter Prozess-Prioritätszyklus ---
                boosted = process_priority.boost_priority()
                process_priority.restore_priority()
                gate7_ok = isinstance(boosted, bool) and not process_priority._boosted
                if not gate7_ok:
                    errors.append("Gate 7: Prozess-Priorität wurde nicht sauber zurückgesetzt")
                gates["process_priority_cycle"] = {
                    "passed": gate7_ok,
                    "boost_attempted_ok": boosted,
                    "restored_cleanly": not process_priority._boosted,
                }

            finally:
                if bridge is not None:
                    bridge.stop()
                if fenster is not None:
                    fenster.close()
                    fenster.deleteLater()
                engine.stop()
                app.processEvents()

    finally:
        QSettings.setDefaultFormat(prev_qsettings_format)
        for k, prev_val in saved_env.items():
            if prev_val is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = prev_val

    return {
        "project": "KlangpultLight",
        "platform": sys.platform,
        "python": sys.version.split()[0],
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "gates": gates,
    }


def test_source_platform_smoke_suite() -> None:
    """Pytest-Einstiegspunkt für die zustandsisolierte Cross-Platform-Smoke-Suite."""
    result = run_smoke_suite(PROJECT_ROOT)
    assert result["passed"], f"Cross-Platform Smoke Suite fehlgeschlagen: {result['errors']}"


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Cross-Platform Source-Mode Smoke Suite für Klangpult light")
    parser.add_argument("--json", action="store_true", help="Ergebnis als JSON ausgeben")
    args = parser.parse_args(argv)

    result = run_smoke_suite(PROJECT_ROOT)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Cross-Platform Smoke Suite — Klangpult light ({result['platform']}, Python {result['python']})")
        for gate_name, gate_info in result["gates"].items():
            status = "PASS" if gate_info.get("passed") else "FAIL"
            print(f"  [{status}] {gate_name}")
        print("-" * 65)
        if result["passed"]:
            print("SMOKE SUITE PASSED: Alle 7 Plattform- & PWA-Gates grün.")
        else:
            print(f"SMOKE SUITE FAILED: {result['error_count']} Fehler: {result['errors']}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
