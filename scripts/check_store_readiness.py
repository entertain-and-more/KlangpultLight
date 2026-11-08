#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Store Readiness Preflight Check for Klangpult light.

Validates that all necessary metadata, documentation files, licenses,
icon assets, AppxManifest, and staged 6-language Store listings required for Windows Store
release are present, valid, and policy-compliant (Policy P-006 / Tier-2 / Microsoft Partner Center Policy 10.1.3).
"""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIER2_LANGUAGES = ("de-DE", "en-US", "es-ES", "zh-CN", "ja-JP", "ru-RU")
TIER2_LANG_CODES = ("de", "en", "es", "zh", "ja", "ru")

FORBIDDEN_BRAND_KEYWORDS = {
    "microsoft", "windows", "apple", "google", "android", "ios", "excel", "word",
    "trello", "notion", "todoist", "ticktick", "asana", "jira", "zoom", "teams"
}

EXPECTED_ICON_DIMENSIONS = {
    "StoreLogo.png": (50, 50),
    "icon_44x44.png": (44, 44),
    "icon_50x50.png": (50, 50),
    "icon_150x150.png": (150, 150),
    "icon_310x150.png": (310, 150),
    "icon_310x310.png": (310, 310),
}


def check_store_package_json(project_root: Path) -> List[str]:
    errors = []
    file_path = project_root / "store_package.json"
    if not file_path.exists():
        errors.append("store_package.json is missing.")
        return errors

    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except Exception as e:
        errors.append(f"store_package.json is invalid JSON: {e}")
        return errors

    required_fields = [
        "app_name",
        "publisher",
        "publisher_display",
        "identity_name",
        "version",
        "description",
        "executable",
        "capabilities",
        "category",
        "age_rating",
        "privacy_url",
        "support_url",
        "languages",
    ]
    for field in required_fields:
        val = data.get(field)
        if not val or (isinstance(val, str) and not val.strip()):
            errors.append(f"store_package.json field '{field}' is missing or empty.")
        elif field == "publisher" and (val.startswith("CN=YOUR-PUBLISHER-ID") or "YOUR-PUBLISHER" in val):
            errors.append("store_package.json publisher is still placeholder.")

    if data.get("app_name") != "KlangpultLight":
        errors.append(f"store_package.json app_name expected 'KlangpultLight', got '{data.get('app_name')}'")

    if data.get("identity_name") != "Geiger.KlangpultLight":
        errors.append(f"store_package.json identity_name expected 'Geiger.KlangpultLight', got '{data.get('identity_name')}'")

    if data.get("publisher") != "CN=52596601-BAB4-4F3F-B182-E8F3F273B202":
        errors.append(f"store_package.json publisher CN unexpected: {data.get('publisher')}")

    if data.get("version") != "0.1.0.0":
        errors.append(f"store_package.json version expected '0.1.0.0', got '{data.get('version')}'")

    langs = data.get("languages", [])
    for lang in TIER2_LANGUAGES:
        if lang not in langs:
            errors.append(f"store_package.json missing Tier-2 language: '{lang}'")

    descriptions_map = data.get("descriptions", {})
    keywords_map = data.get("keywords", {})

    for lang_code in TIER2_LANG_CODES:
        # Check descriptions
        desc_key = f"description_{lang_code}"
        desc_val = data.get(desc_key) or descriptions_map.get(lang_code)
        if not desc_val:
            # check full tag e.g. de-DE
            full_tag = next((lang_tag for lang_tag in TIER2_LANGUAGES if lang_tag.lower().startswith(lang_code)), None)
            if full_tag:
                desc_val = descriptions_map.get(full_tag)
        if not desc_val:
            errors.append(f"store_package.json missing short description for '{lang_code}'")
        elif len(desc_val) > 100:
            errors.append(f"store_package.json description for '{lang_code}' exceeds 100 chars ({len(desc_val)})")

        # Check keywords
        kw_key = f"keywords_{lang_code}"
        kw_val = data.get(kw_key) or keywords_map.get(lang_code)
        if not kw_val:
            full_tag = next((lang_tag for lang_tag in TIER2_LANGUAGES if lang_tag.lower().startswith(lang_code)), None)
            if full_tag:
                kw_val = keywords_map.get(full_tag)
        if not kw_val or not isinstance(kw_val, list):
            errors.append(f"store_package.json missing keyword list for '{lang_code}'")
        elif len(kw_val) != 7:
            errors.append(f"store_package.json '{kw_key}' has {len(kw_val)} keywords (exactly 7 required)")
        else:
            for kw in kw_val:
                if len(kw) > 30:
                    errors.append(f"store_package.json keyword '{kw}' in '{kw_key}' exceeds 30 chars ({len(kw)})")
                if kw.lower().strip() in FORBIDDEN_BRAND_KEYWORDS:
                    errors.append(f"store_package.json keyword '{kw}' in '{kw_key}' contains forbidden brand name (Policy 10.1.3)")

    return errors


def check_appx_manifest(project_root: Path) -> List[str]:
    errors = []
    manifest_path = project_root / "store_package" / "KlangpultLight" / "AppxManifest.xml"

    if not manifest_path.exists():
        errors.append(f"AppxManifest.xml is missing at {manifest_path}")
        return errors

    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
        ns = {
            "m": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
            "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
        }

        # Check identity
        identity = root.find("m:Identity", ns)
        if identity is None:
            identity = root.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Identity")
        if identity is not None:
            name = identity.attrib.get("Name")
            pub = identity.attrib.get("Publisher")
            ver = identity.attrib.get("Version")
            arch = identity.attrib.get("ProcessorArchitecture")
            if name != "Geiger.KlangpultLight":
                errors.append(f"AppxManifest.xml Identity Name expected 'Geiger.KlangpultLight', got '{name}'")
            if pub != "CN=52596601-BAB4-4F3F-B182-E8F3F273B202":
                errors.append(f"AppxManifest.xml Identity Publisher expected CN=52596601-BAB4-4F3F-B182-E8F3F273B202, got '{pub}'")
            if ver != "0.1.0.0":
                errors.append(f"AppxManifest.xml Identity Version expected '0.1.0.0', got '{ver}'")
            if arch != "x64":
                errors.append(f"AppxManifest.xml Identity ProcessorArchitecture expected 'x64', got '{arch}'")
        else:
            errors.append("AppxManifest.xml missing <Identity> element")

        # Check Resources
        resources = root.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Resources")
        if resources is not None:
            res_langs = [r.attrib.get("Language").lower() for r in resources.findall("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Resource")]
            for expected_lang in TIER2_LANGUAGES:
                if expected_lang.lower() not in res_langs:
                    errors.append(f"AppxManifest.xml missing resource language '{expected_lang}'")
        else:
            errors.append("AppxManifest.xml missing <Resources> element")

        # Check Capabilities
        caps = root.find("{http://schemas.microsoft.com/appx/manifest/foundation/windows10}Capabilities")
        if caps is not None:
            has_full_trust = any("runFullTrust" in el.attrib.get("Name", "") for el in caps)
            if not has_full_trust:
                errors.append("AppxManifest.xml missing runFullTrust capability")
        else:
            errors.append("AppxManifest.xml missing <Capabilities> element")

    except Exception as e:
        errors.append(f"AppxManifest.xml parse failed: {e}")

    return errors


def check_icon_assets(project_root: Path) -> List[str]:
    errors = []
    asset_dirs = [
        project_root / "store_assets",
        project_root / "store_package" / "KlangpultLight" / "icons",
        project_root / "releases" / "windowsstore" / "icons",
    ]

    for ad in asset_dirs:
        if not ad.exists():
            errors.append(f"Icon asset directory missing: {ad}")
            continue

        for filename, (exp_w, exp_h) in EXPECTED_ICON_DIMENSIONS.items():
            img_path = ad / filename
            if not img_path.exists():
                errors.append(f"Missing icon asset '{filename}' in {ad.relative_to(project_root)}")
            else:
                try:
                    with Image.open(img_path) as img:
                        if img.size != (exp_w, exp_h):
                            errors.append(
                                f"Icon '{filename}' in {ad.relative_to(project_root)} has dimensions {img.size}, expected ({exp_w}, {exp_h})"
                            )
                        if img.mode not in ("RGB", "RGBA"):
                            errors.append(
                                f"Icon '{filename}' in {ad.relative_to(project_root)} has invalid color mode {img.mode}"
                            )
                except Exception as e:
                    errors.append(f"Error reading image {img_path}: {e}")

    # Check root StoreLogo in releases/windowsstore/StoreLogo.png
    ws_logo = project_root / "releases" / "windowsstore" / "StoreLogo.png"
    if not ws_logo.exists():
        errors.append("Missing releases/windowsstore/StoreLogo.png")
    else:
        try:
            with Image.open(ws_logo) as img:
                if img.size != (50, 50):
                    errors.append(f"releases/windowsstore/StoreLogo.png has dimensions {img.size}, expected (50, 50)")
        except Exception as e:
            errors.append(f"Error reading {ws_logo}: {e}")

    return errors


def check_store_listings(project_root: Path) -> List[str]:
    errors = []
    main_listing = project_root / "STORE_LISTING.md"
    if not main_listing.exists():
        errors.append("STORE_LISTING.md is missing in project root.")
    else:
        content = main_listing.read_text(encoding="utf-8")
        for lang_name in ["Deutsch (de-DE)", "English (en-US)", "Español (es-ES)", "简体中文 (zh-CN)", "日本語 (ja-JP)", "Русский (ru-RU)"]:
            if lang_name not in content:
                errors.append(f"STORE_LISTING.md missing section for '{lang_name}'")

    staging_dir = project_root / "releases" / "windowsstore"
    if not staging_dir.exists():
        errors.append("Staging directory 'releases/windowsstore' is missing.")
        return errors

    staging_files = [
        "BUILD.md",
        "WACK_PROTOCOL.md",
        "store_settings.json",
        "store_listing_de.md",
        "store_listing_en.md",
        "store_listing_es.md",
        "store_listing_zh.md",
        "store_listing_ja.md",
        "store_listing_ru.md",
    ]
    for sf in staging_files:
        p = staging_dir / sf
        if not p.exists():
            errors.append(f"Missing staging file 'releases/windowsstore/{sf}'")
        elif p.stat().st_size == 0:
            errors.append(f"Staging file 'releases/windowsstore/{sf}' is empty.")

    return errors


def check_documentation_and_privacy(project_root: Path) -> List[str]:
    errors = []
    for doc in ["PRIVACY_POLICY.md", "WINDOWS_STORE_PREP.md", "LICENSE"]:
        p = project_root / doc
        if not p.exists():
            errors.append(f"Required document '{doc}' is missing in project root.")
        elif p.stat().st_size == 0:
            errors.append(f"Document '{doc}' is empty.")

    pp = project_root / "PRIVACY_POLICY.md"
    if pp.exists():
        text = pp.read_text(encoding="utf-8")
        if "Zero-Egress" not in text and "Local-First" not in text:
            errors.append("PRIVACY_POLICY.md missing Local-First / Zero-Egress reassurance statement.")

    return errors


def run_all_checks(project_root: Path = PROJECT_ROOT) -> int:
    print(f"Running Store Readiness Preflight Checks for Klangpult light in: {project_root}")
    all_errors: List[str] = []

    sections = [
        ("Store Package JSON (store_package.json)", check_store_package_json),
        ("Windows Desktop AppxManifest", check_appx_manifest),
        ("Icon & Tile Assets (50x50, 44x44, 150x150, 310x150, 310x310)", check_icon_assets),
        ("Store Listings & Staging (6 Tier-2 Languages)", check_store_listings),
        ("Documentation & Privacy Policy", check_documentation_and_privacy),
    ]

    total_checks = 0
    for section_name, check_fn in sections:
        errs = check_fn(project_root)
        total_checks += 1
        if errs:
            print(f"  [FAIL] {section_name}")
            for err in errs:
                print(f"         - {err}")
            all_errors.extend(errs)
        else:
            print(f"  [PASS] {section_name}")

    print("-" * 65)
    if all_errors:
        print(f"STORE READINESS CHECK FAILED: {len(all_errors)} issues found.")
        return 1

    print("STORE READINESS CHECK PASSED: All checks passed with 0 findings.")
    return 0


if __name__ == "__main__":
    sys.exit(run_all_checks())
