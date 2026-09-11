# -*- coding: utf-8 -*-
"""Tests fuer Onedir-Packaging, Desktop-Shortcut und Frozen-Pfadaufloesung.

Absicherung von TW-KLANGPULTLIGHT-12.
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "Recorder"))
sys.path.insert(0, str(PROJECT_ROOT))

from bridge.bridge_service import _get_planer_server_cls  # noqa: E402
from planer.server.planer_server import _resolve_static_root  # noqa: E402
from scripts.create_desktop_shortcut import (  # noqa: E402
    create_shortcut,
    get_desktop_dir,
    resolve_default_target,
)


class TestOnedirPackagingAndShortcut(unittest.TestCase):
    """Prueft die Packaging-Spezifikationen, Desktop-Shortcut und Frozen-Pfade."""

    def test_onefile_spec_contains_planer_and_shared(self):
        """KlangpultLightRecorder.spec muss shared und planer in datas einbinden."""
        spec_file = PROJECT_ROOT / "KlangpultLightRecorder.spec"
        self.assertTrue(spec_file.is_file(), "Onefile Spec muss existieren")
        text = spec_file.read_text(encoding="utf-8")
        self.assertIn('("shared", "shared")', text)
        self.assertIn('("planer", "planer")', text)
        self.assertIn("DesktopIcon.ico", text)

    def test_onedir_spec_structure(self):
        """KlangpultLightRecorderOnedir.spec muss COLLECT und beide Datenbaeume enthalten."""
        spec_file = PROJECT_ROOT / "KlangpultLightRecorderOnedir.spec"
        self.assertTrue(spec_file.is_file(), "Onedir Spec muss existieren")
        text = spec_file.read_text(encoding="utf-8")
        self.assertIn('("shared", "shared")', text)
        self.assertIn('("planer", "planer")', text)
        self.assertIn("exclude_binaries=True", text)
        self.assertIn("COLLECT(", text)
        self.assertIn("DesktopIcon.ico", text)

    def test_build_onedir_bat_present_and_valid(self):
        """build_onedir.bat muss vorhanden sein und Onedir-Ziele ansteuern."""
        bat_file = PROJECT_ROOT / "build_onedir.bat"
        self.assertTrue(bat_file.is_file(), "build_onedir.bat muss existieren")
        text = bat_file.read_text(encoding="utf-8")
        self.assertIn("KlangpultLightRecorderOnedir.spec", text)
        self.assertIn("dist\\KlangpultLightRecorder", text)
        self.assertIn("releases\\v0.1.0\\onedir", text)
        self.assertIn("SHA256SUMS.txt", text)

    def test_create_desktop_shortcut_bat_present(self):
        """CREATE_DESKTOP_SHORTCUT.bat muss vorhanden sein."""
        bat_file = PROJECT_ROOT / "CREATE_DESKTOP_SHORTCUT.bat"
        self.assertTrue(bat_file.is_file(), "CREATE_DESKTOP_SHORTCUT.bat muss existieren")
        text = bat_file.read_text(encoding="utf-8")
        self.assertIn("scripts\\create_desktop_shortcut.py", text)

    def test_shortcut_helper_dry_run(self):
        """create_shortcut im Dry-Run-Modus muss erfolgreich durchlaufen."""
        desktop = get_desktop_dir()
        self.assertTrue(desktop.is_dir() or str(desktop) != "")
        target = resolve_default_target(PROJECT_ROOT)
        self.assertTrue(str(target) != "")

        ok = create_shortcut(
            target=target,
            name="TestKlangpultShortcut",
            dry_run=True,
        )
        self.assertTrue(ok, "Dry-run Verknuepfungserstellung muss True liefern")

    def test_bridge_service_resolves_planer_class(self):
        """_get_planer_server_cls liefert PlanerServer-Klasse."""
        cls = _get_planer_server_cls()
        self.assertIsNotNone(cls)
        self.assertEqual(cls.__name__, "PlanerServer")

    def test_bridge_service_frozen_resolution_simulated(self):
        """_get_planer_server_cls loest ueber _MEIPASS auf wenn frozen gesetzt ist."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", str(PROJECT_ROOT), create=True):
            cls = _get_planer_server_cls()
            self.assertIsNotNone(cls)
            self.assertEqual(cls.__name__, "PlanerServer")

    def test_planer_server_static_root_resolution(self):
        """_resolve_static_root findet den gueltigen planer-Ordner mit index.html."""
        root = _resolve_static_root()
        self.assertTrue((root / "index.html").is_file())

    def test_planer_server_static_root_frozen_simulated(self):
        """_resolve_static_root findet static root unter simuliertem _MEIPASS."""
        with patch.object(sys, "frozen", True, create=True), \
             patch.object(sys, "_MEIPASS", str(PROJECT_ROOT), create=True):
            root = _resolve_static_root()
            self.assertTrue((root / "index.html").is_file())


if __name__ == "__main__":
    unittest.main()
