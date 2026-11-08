"""
Vertragstests für Tier-2 Windows Store Packaging & 6-Sprachen-Materialien (Policy P-006).

Sichert die Einhaltung der Windows Store Richtlinie 10.1.3, der Sprachabdeckung
(DE, EN, ES, ZH, JA, RU), der AppxManifest-Konformität und des Staging-Verzeichnisses ab.
"""

from __future__ import annotations

import json
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WINDOWS_STORE_DIR = PROJECT_ROOT / "releases" / "windowsstore"
TIER2_LANGS = ("de", "en", "es", "zh", "ja", "ru")
TIER2_STORE_LANGS = ("de-DE", "en-US", "es-ES", "zh-CN", "ja-JP", "ru-RU")


class TestStoreMaterials(unittest.TestCase):

    def setUp(self):
        self.store_pkg_path = PROJECT_ROOT / "store_package.json"
        self.assertTrue(self.store_pkg_path.is_file(), "store_package.json fehlt")
        self.store_pkg = json.loads(self.store_pkg_path.read_text(encoding="utf-8"))

        self.store_settings_path = WINDOWS_STORE_DIR / "store_settings.json"
        self.assertTrue(self.store_settings_path.is_file(), "releases/windowsstore/store_settings.json fehlt")
        self.store_settings = json.loads(self.store_settings_path.read_text(encoding="utf-8"))

    def test_store_package_declares_six_tier2_languages(self):
        langs = self.store_pkg.get("languages", [])
        for expected in TIER2_STORE_LANGS:
            self.assertIn(expected, langs, f"Fehlende Tier-2 Sprache: {expected}")

    def test_store_package_identity_and_version(self):
        self.assertEqual(self.store_pkg["app_name"], "KlangpultLight")
        self.assertEqual(self.store_pkg["identity_name"], "Geiger.KlangpultLight")
        self.assertEqual(self.store_pkg["publisher"], "CN=52596601-BAB4-4F3F-B182-E8F3F273B202")
        self.assertEqual(self.store_pkg["version"], "0.1.0.0")

    def test_store_package_short_descriptions_length(self):
        for lang in TIER2_LANGS:
            key = f"description_{lang}"
            self.assertIn(key, self.store_pkg, f"Fehlende Kurzbeschreibung '{key}'")
            desc = self.store_pkg[key]
            self.assertIsInstance(desc, str)
            self.assertTrue(len(desc) > 0, f"Kurzbeschreibung '{key}' ist leer")
            self.assertLessEqual(len(desc), 100, f"Kurzbeschreibung '{key}' überschreitet 100 Zeichen: {len(desc)}")

    def test_store_package_keywords_policy_compliance(self):
        for lang in TIER2_LANGS:
            key = f"keywords_{lang}"
            self.assertIn(key, self.store_pkg, f"Fehlende Keywords '{key}'")
            kws = self.store_pkg[key]
            self.assertIsInstance(kws, list)
            self.assertEqual(len(kws), 7, f"Keywords '{key}' muss genau 7 Begriffe enthalten (Policy 10.1.3)")
            for kw in kws:
                self.assertLessEqual(len(kw), 30, f"Keyword '{kw}' in '{key}' überschreitet 30 Zeichen")

    def test_store_settings_in_sync_with_store_package(self):
        self.assertEqual(self.store_pkg["app_name"], self.store_settings["app_name"])
        self.assertEqual(self.store_pkg["version"], self.store_settings["version"])
        self.assertEqual(self.store_pkg["publisher"], self.store_settings["publisher"])
        self.assertEqual(self.store_pkg["publisher_display"], self.store_settings["publisher_display"])
        self.assertEqual(self.store_pkg["identity_name"], self.store_settings["identity_name"])
        self.assertEqual(self.store_pkg["privacy_url"], self.store_settings["privacy_url"])
        self.assertEqual(self.store_pkg["support_url"], self.store_settings["support_url"])
        self.assertEqual(self.store_pkg["languages"], self.store_settings["languages"])

    def test_staged_store_listings_exist_and_non_empty(self):
        for lang in TIER2_LANGS:
            listing_file = WINDOWS_STORE_DIR / f"store_listing_{lang}.md"
            self.assertTrue(listing_file.is_file(), f"Staged Listing fehlt: {listing_file.name}")
            content = listing_file.read_text(encoding="utf-8")
            self.assertGreater(len(content.strip()), 100, f"Staged Listing zu kurz: {listing_file.name}")

    def test_store_listing_markdown_contains_all_six_sections(self):
        listing_md = PROJECT_ROOT / "STORE_LISTING.md"
        self.assertTrue(listing_md.is_file(), "STORE_LISTING.md fehlt")
        text = listing_md.read_text(encoding="utf-8")
        for section in ("Deutsch (de-DE)", "English (en-US)", "Español (es-ES)", "简体中文 (zh-CN)", "日本語 (ja-JP)", "Русский (ru-RU)"):
            self.assertIn(f"## {section}", text, f"Abschnitt '## {section}' fehlt in STORE_LISTING.md")

    def test_wack_protocol_and_build_docs_exist(self):
        build_md = WINDOWS_STORE_DIR / "BUILD.md"
        wack_md = WINDOWS_STORE_DIR / "WACK_PROTOCOL.md"
        self.assertTrue(build_md.is_file(), "releases/windowsstore/BUILD.md fehlt")
        self.assertTrue(wack_md.is_file(), "releases/windowsstore/WACK_PROTOCOL.md fehlt")

    def test_privacy_policy_and_windows_store_prep_exist(self):
        pp = PROJECT_ROOT / "PRIVACY_POLICY.md"
        prep = PROJECT_ROOT / "WINDOWS_STORE_PREP.md"
        self.assertTrue(pp.is_file(), "PRIVACY_POLICY.md fehlt")
        self.assertTrue(prep.is_file(), "WINDOWS_STORE_PREP.md fehlt")
        pp_text = pp.read_text(encoding="utf-8")
        self.assertIn("Zero-Egress", pp_text)
        self.assertIn("Local-First", pp_text)

    def test_appx_manifest_structure_and_resources(self):
        manifest_path = PROJECT_ROOT / "store_package" / "KlangpultLight" / "AppxManifest.xml"
        self.assertTrue(manifest_path.is_file(), "AppxManifest.xml fehlt")
        tree = ET.parse(manifest_path)
        root = tree.getroot()

        # Check identity
        identity = root.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Identity")
        self.assertIsNotNone(identity, "Identity Tag fehlt")
        self.assertEqual(identity.attrib.get("Name"), "Geiger.KlangpultLight")
        self.assertEqual(identity.attrib.get("Version"), "0.1.0.0")
        self.assertEqual(identity.attrib.get("Publisher"), "CN=52596601-BAB4-4F3F-B182-E8F3F273B202")

        # Check Resources
        resources = root.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Resources")
        self.assertIsNotNone(resources, "Resources Tag fehlt")
        res_langs = [r.attrib.get("Language").lower() for r in resources.findall("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Resource")]
        for expected in TIER2_STORE_LANGS:
            self.assertIn(expected.lower(), res_langs, f"Ressourcen-Sprache {expected} fehlt im AppxManifest")

        # Check Capability
        caps = root.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Capabilities")
        self.assertIsNotNone(caps, "Capabilities Tag fehlt")
        has_full_trust = any("runFullTrust" in (c.attrib.get("Name") or "") for c in caps)
        self.assertTrue(has_full_trust, "runFullTrust fehlt im AppxManifest")

    def test_store_icons_exist_and_valid_dimensions(self):
        icons_dir = PROJECT_ROOT / "store_assets"
        for icon_name in ("Square44x44Logo.png", "Square150x150Logo.png", "Wide310x150Logo.png", "Square310x310Logo.png", "StoreLogo.png"):
            icon_file = icons_dir / icon_name
            self.assertTrue(icon_file.is_file(), f"Icon {icon_name} fehlt in store_assets")
            self.assertGreater(icon_file.stat().st_size, 100)

    def test_check_store_readiness_script_passes(self):
        sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
        import check_store_readiness
        exit_code = check_store_readiness.run_all_checks(PROJECT_ROOT)
        self.assertEqual(exit_code, 0, "check_store_readiness.run_all_checks() muss 0 zurückgeben")


if __name__ == "__main__":
    unittest.main()
