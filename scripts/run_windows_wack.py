#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Windows App Certification Kit (WACK) Preflight & Certification Runner — Klangpult light.

Führt eine hermetische, reproduzierbare WACK-Vorprüfung für das Desktop-Bridge-Paket
(Geiger.KlangpultLight, Version 0.1.0.0, x64) durch und unterstützt optional den
kontrollierten Aufruf des offiziellen Windows SDK ``appcert.exe`` gegen ein gebautes
MSIX-Paket (ohne ``shell=True``).

Standardlauf (statisch, CI- & Cross-Platform-tauglich, Read-Only):
    python scripts/run_windows_wack.py [--json]

Optionaler Lauf mit echtem Windows SDK App Certification Kit:
    python scripts/run_windows_wack.py --msix releases/windowsstore/Geiger.KlangpultLight_0.1.0.0_x64.msix --invoke-appcert --report-xml wack_report.xml
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TIER2_MANIFEST_LANGS = ("de-de", "en-us", "es-es", "zh-cn", "ja-jp", "ru-ru")
TIER2_STORE_LANGS = ("de-DE", "en-US", "es-ES", "zh-CN", "ja-JP", "ru-RU")
TIER2_SHORT_LANGS = ("de", "en", "es", "zh", "ja", "ru")

FORBIDDEN_ELEVATION_TOKENS = (
    "requireAdministrator",
    "highestAvailable",
    "allowElevation",
)

FORBIDDEN_BRAND_KEYWORDS = {
    "microsoft",
    "windows",
    "apple",
    "google",
    "android",
    "ios",
    "excel",
    "word",
    "trello",
    "notion",
    "todoist",
    "ticktick",
    "asana",
    "jira",
    "zoom",
    "teams",
}


def find_sdk_appcert() -> Optional[Path]:
    """Sucht ``appcert.exe`` aus dem Windows 10/11 SDK ohne Schreibzugriff."""
    which_hit = shutil.which("appcert") or shutil.which("appcert.exe")
    if which_hit:
        p = Path(which_hit)
        if p.is_file():
            return p

    program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
    candidates = [
        Path(program_files_x86) / "Windows Kits" / "10" / "App Certification Kit" / "appcert.exe",
        Path(program_files) / "Windows Kits" / "10" / "App Certification Kit" / "appcert.exe",
    ]
    for cand in candidates:
        if cand.is_file():
            return cand
    return None


def _check_manifest_wack_rules(project_root: Path) -> List[str]:
    """Prüft AppxManifest.xml auf alle WACK-kritischen Desktop-Bridge-Vorgaben."""
    errors: List[str] = []
    pkg_dir = project_root / "store_package" / "KlangpultLight"
    manifest_path = pkg_dir / "AppxManifest.xml"
    if not manifest_path.is_file():
        return [f"AppxManifest.xml fehlt unter {manifest_path}"]

    raw_xml = manifest_path.read_text(encoding="utf-8")
    for tok in FORBIDDEN_ELEVATION_TOKENS:
        if tok.lower() in raw_xml.lower():
            errors.append(f"AppxManifest.xml enthält verbotenes Elevation-Token '{tok}' (WACK Security Gate)")

    try:
        tree = ET.parse(manifest_path)
        root = tree.getroot()
    except Exception as exc:
        return [f"AppxManifest.xml ist kein wohlgeformtes XML: {exc}"]

    ns_f = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10}"
    ns_uap = "{http://schemas.microsoft.com/appx/manifest/uap/windows10}"
    ns_rescap = "{http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities}"

    identity = root.find(f"{ns_f}Identity")
    if identity is None:
        errors.append("WACK-Manifest: <Identity> fehlt")
    else:
        if identity.attrib.get("Name") != "Geiger.KlangpultLight":
            errors.append(f"WACK-Manifest: Unerwarteter Identity Name '{identity.attrib.get('Name')}'")
        if identity.attrib.get("Publisher") != "CN=52596601-BAB4-4F3F-B182-E8F3F273B202":
            errors.append("WACK-Manifest: Publisher-DN stimmt nicht mit Partner-Center-Identität überein")
        if identity.attrib.get("Version") != "0.1.0.0":
            errors.append(f"WACK-Manifest: Version muss 0.1.0.0 (4-teilig) sein, ist '{identity.attrib.get('Version')}'")
        if identity.attrib.get("ProcessorArchitecture") != "x64":
            errors.append(
                f"WACK-Manifest: ProcessorArchitecture muss 'x64' sein (nicht neutral für PyInstaller-PE), "
                f"ist '{identity.attrib.get('ProcessorArchitecture')}'"
            )

    tdf = root.find(f"{ns_f}Dependencies/{ns_f}TargetDeviceFamily")
    if tdf is None:
        errors.append("WACK-Manifest: <TargetDeviceFamily> fehlt")
    else:
        if tdf.attrib.get("Name") != "Windows.Desktop":
            errors.append(f"WACK-Manifest: TargetDeviceFamily muss 'Windows.Desktop' sein, ist '{tdf.attrib.get('Name')}'")
        min_ver = tdf.attrib.get("MinVersion", "")
        max_ver = tdf.attrib.get("MaxVersionTested", "")
        if not min_ver or not max_ver:
            errors.append("WACK-Manifest: MinVersion oder MaxVersionTested fehlt")

    resources = root.find(f"{ns_f}Resources")
    if resources is None:
        errors.append("WACK-Manifest: <Resources> fehlt")
    else:
        declared = [
            (el.attrib.get("Language") or "").strip().lower()
            for el in resources.findall(f"{ns_f}Resource")
        ]
        for lang in TIER2_MANIFEST_LANGS:
            if lang not in declared:
                errors.append(f"WACK-Manifest: Tier-2 Ressourcensprache '{lang}' fehlt")

    caps = root.find(f"{ns_f}Capabilities")
    if caps is None:
        errors.append("WACK-Manifest: <Capabilities> fehlt")
    else:
        res_caps = [c.attrib.get("Name") for c in caps.findall(f"{ns_rescap}Capability")]
        std_caps = [c.attrib.get("Name") for c in caps.findall(f"{ns_f}Capability")]
        dev_caps = [c.attrib.get("Name") for c in caps.findall(f"{ns_f}DeviceCapability")]
        if "runFullTrust" not in res_caps:
            errors.append("WACK-Manifest: rescap:Capability 'runFullTrust' fehlt")
        if "internetClient" not in std_caps:
            errors.append("WACK-Manifest: Capability 'internetClient' fehlt")
        if "microphone" not in dev_caps:
            errors.append("WACK-Manifest: DeviceCapability 'microphone' fehlt")

    app_el = root.find(f"{ns_f}Applications/{ns_f}Application")
    if app_el is None:
        errors.append("WACK-Manifest: <Application> fehlt")
    else:
        if app_el.attrib.get("EntryPoint") != "Windows.FullTrustApplication":
            errors.append("WACK-Manifest: EntryPoint muss 'Windows.FullTrustApplication' lauten")
        if app_el.attrib.get("Executable") != "KlangpultLightRecorder.exe":
            errors.append("WACK-Manifest: Executable muss 'KlangpultLightRecorder.exe' lauten")

        # Prüfe alle im Manifest referenzierten Bilddateien relativ zum Paketordner
        referenced_images: List[str] = []
        logo_el = root.find(f"{ns_f}Properties/{ns_f}Logo")
        if logo_el is not None and logo_el.text:
            referenced_images.append(logo_el.text.strip())

        vis = app_el.find(f"{ns_uap}VisualElements")
        if vis is None:
            errors.append("WACK-Manifest: <uap:VisualElements> fehlt")
        else:
            for attr in ("Square150x150Logo", "Square44x44Logo"):
                val = vis.attrib.get(attr, "").strip()
                if val:
                    referenced_images.append(val)
                else:
                    errors.append(f"WACK-Manifest: Pflichtattribut '{attr}' fehlt in VisualElements")

            dt = vis.find(f"{ns_uap}DefaultTile")
            if dt is not None:
                for attr in ("Wide310x150Logo", "Square310x310Logo", "Square71x71Logo"):
                    val = dt.attrib.get(attr, "").strip()
                    if val:
                        referenced_images.append(val)

            sp = vis.find(f"{ns_uap}SplashScreen")
            if sp is not None and sp.attrib.get("Image"):
                referenced_images.append(sp.attrib["Image"].strip())

        for rel_img in sorted(set(referenced_images)):
            norm_rel = Path(*rel_img.replace("\\", "/").split("/"))
            full_img = pkg_dir / norm_rel
            if not full_img.is_file():
                errors.append(f"WACK-Manifest: Referenzierte Bilddatei existiert nicht: {rel_img}")
            else:
                try:
                    with Image.open(full_img) as img:
                        if img.format != "PNG":
                            errors.append(f"WACK-Asset '{rel_img}' ist kein PNG ({img.format})")
                        if img.mode not in ("RGB", "RGBA"):
                            errors.append(f"WACK-Asset '{rel_img}' nutzt unzulässigen Farbmodus '{img.mode}'")
                except Exception as exc:
                    errors.append(f"WACK-Asset '{rel_img}' konnte nicht gelesen werden: {exc}")

    return errors


def _check_frozen_packaging_and_security(project_root: Path) -> List[str]:
    """Prüft PyInstaller-Specs (RunAsInvoker, keine UAC-Elevation, gebündelte Datenbäume)."""
    errors: List[str] = []
    for spec_name in ("KlangpultLightRecorder.spec", "KlangpultLightRecorderOnedir.spec"):
        spec_path = project_root / spec_name
        if not spec_path.is_file():
            errors.append(f"PyInstaller-Spec fehlt: {spec_name}")
            continue
        spec_text = spec_path.read_text(encoding="utf-8")
        if "uac_admin=True" in spec_text or "uac_uiaccess=True" in spec_text:
            errors.append(f"{spec_name} aktiviert UAC-Elevation (verletzt RunAsInvoker & WACK)")
        for required_bundle in (
            '("shared", "shared")',
            '("planer", "planer")',
            '("assets", "assets")',
            '("mobile_icons", "mobile_icons")',
            '("locales", "locales")',
        ):
            if required_bundle not in spec_text:
                errors.append(f"{spec_name} bündelt erforderlichen Datenbaum nicht: {required_bundle}")

    # Prüfe Local-Loopback-Default im BridgeService und PlanerServer
    bridge_py = project_root / "Recorder" / "bridge" / "bridge_service.py"
    planer_py = project_root / "planer" / "server" / "planer_server.py"
    for py_path in (bridge_py, planer_py):
        if not py_path.is_file():
            errors.append(f"Sicherheitsrelevante Serverdatei fehlt: {py_path.relative_to(project_root)}")
        else:
            text = py_path.read_text(encoding="utf-8")
            if '"127.0.0.1"' not in text:
                errors.append(f"{py_path.name} definiert keinen expliziten 127.0.0.1 Loopback-Default")

    return errors


def _check_partner_center_policy_10_1_3(project_root: Path) -> List[str]:
    """Prüft Synchronität und Richtlinie 10.1.3 zwischen store_package.json und store_settings.json."""
    errors: List[str] = []
    pkg_json_path = project_root / "store_package.json"
    stg_json_path = project_root / "releases" / "windowsstore" / "store_settings.json"
    if not pkg_json_path.is_file() or not stg_json_path.is_file():
        return ["store_package.json oder releases/windowsstore/store_settings.json fehlt"]

    pkg = json.loads(pkg_json_path.read_text(encoding="utf-8"))
    stg = json.loads(stg_json_path.read_text(encoding="utf-8"))

    for key in ("app_name", "identity_name", "publisher", "publisher_display", "version", "languages", "license"):
        if pkg.get(key) != stg.get(key):
            errors.append(f"Metadaten-Drift bei '{key}': store_package.json != store_settings.json")

    if "Freeware" not in str(pkg.get("license", "")):
        errors.append("store_package.json muss Klangpult light klar als Freeware ausweisen")

    for short_lang, store_lang in zip(TIER2_SHORT_LANGS, TIER2_STORE_LANGS):
        kws = pkg.get(f"keywords_{short_lang}")
        kws_map = pkg.get("keywords", {}).get(store_lang)
        if not isinstance(kws, list) or len(kws) != 7:
            errors.append(f"Policy 10.1.3: 'keywords_{short_lang}' muss exakt 7 Begriffe enthalten")
        elif kws != kws_map:
            errors.append(f"Policy 10.1.3: 'keywords_{short_lang}' weicht von 'keywords[{store_lang}]' ab")
        else:
            for kw in kws:
                if len(kw) > 30:
                    errors.append(f"Policy 10.1.3: Keyword '{kw}' ({short_lang}) überschreitet 30 Zeichen")
                if kw.strip().lower() in FORBIDDEN_BRAND_KEYWORDS:
                    errors.append(f"Policy 10.1.3: Verbotene Fremdmarke '{kw}' in '{short_lang}'")

        listing_md = project_root / "releases" / "windowsstore" / f"store_listing_{short_lang}.md"
        if not listing_md.is_file() or listing_md.stat().st_size < 100:
            errors.append(f"Staged Store-Listing unvollständig oder fehlend: {listing_md.name}")

    return errors


def build_appcert_command(appcert_exe: Path, msix_path: Path, report_xml: Path) -> List[str]:
    """Erstellt die sichere Argumentliste (ohne ``shell=True``) für ``appcert.exe``."""
    return [
        str(appcert_exe),
        "test",
        "-apptype",
        "desktop",
        "-appxpackagepath",
        str(msix_path),
        "-reportoutputfilepath",
        str(report_xml),
    ]


def run_wack_preflight(
    project_root: Path = PROJECT_ROOT,
    msix_path: Optional[Path] = None,
    invoke_appcert: bool = False,
    report_xml: Optional[Path] = None,
) -> Dict[str, Any]:
    """Führt alle statischen WACK-Gates und optional ``appcert.exe`` aus."""
    checks = {
        "manifest_wack_rules": _check_manifest_wack_rules(project_root),
        "frozen_packaging_and_security": _check_frozen_packaging_and_security(project_root),
        "partner_center_policy_10_1_3": _check_partner_center_policy_10_1_3(project_root),
    }

    errors: List[str] = []
    for section_errs in checks.values():
        errors.extend(section_errs)

    sdk_appcert = find_sdk_appcert()
    appcert_result: Optional[Dict[str, Any]] = None

    if invoke_appcert:
        if msix_path is None or not msix_path.is_file():
            errors.append(f"--invoke-appcert angefordert, aber MSIX-Datei existiert nicht: {msix_path}")
        elif sdk_appcert is None:
            errors.append("--invoke-appcert angefordert, aber Windows SDK appcert.exe wurde nicht gefunden")
        else:
            out_xml = report_xml or (project_root / "releases" / "windowsstore" / "wack_report.xml")
            cmd = build_appcert_command(sdk_appcert, msix_path, out_xml)
            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            appcert_result = {
                "command": cmd,
                "returncode": proc.returncode,
                "report_xml": str(out_xml),
            }
            if proc.returncode != 0:
                errors.append(f"Windows SDK appcert.exe meldete Exit-Code {proc.returncode}")

    return {
        "project": "KlangpultLight",
        "package_identity": "Geiger.KlangpultLight",
        "version": "0.1.0.0",
        "passed": len(errors) == 0,
        "error_count": len(errors),
        "errors": errors,
        "sections": {k: {"passed": len(v) == 0, "errors": v} for k, v in checks.items()},
        "sdk_appcert_available": sdk_appcert is not None,
        "sdk_appcert_path": str(sdk_appcert) if sdk_appcert else None,
        "appcert_execution": appcert_result,
    }


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="WACK Preflight & Certification Runner für Klangpult light")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT, help="Pfad zum Repository-Root")
    parser.add_argument("--msix", type=Path, default=None, help="Optionaler Pfad zu einem gebauten .msix-Paket")
    parser.add_argument(
        "--invoke-appcert",
        action="store_true",
        help="Führt zusätzlich Windows SDK appcert.exe gegen --msix aus",
    )
    parser.add_argument("--report-xml", type=Path, default=None, help="Zielpfad für den appcert-XML-Bericht")
    parser.add_argument("--json", action="store_true", help="Gibt das Ergebnis als JSON auf stdout aus")
    args = parser.parse_args(argv)

    result = run_wack_preflight(
        project_root=args.project_root.resolve(),
        msix_path=args.msix.resolve() if args.msix else None,
        invoke_appcert=args.invoke_appcert,
        report_xml=args.report_xml.resolve() if args.report_xml else None,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Running WACK Preflight for {result['package_identity']} ({result['version']})")
        for sec_name, sec_data in result["sections"].items():
            tag = "PASS" if sec_data["passed"] else "FAIL"
            print(f"  [{tag}] {sec_name}")
            for err in sec_data["errors"]:
                print(f"         - {err}")
        sdk_note = result["sdk_appcert_path"] or "nicht installiert (statischer Preflight aktiv)"
        print(f"  [INFO] Windows SDK appcert.exe: {sdk_note}")
        print("-" * 65)
        if result["passed"]:
            print("WACK PREFLIGHT PASSED: 0 Beanstandungen.")
        else:
            print(f"WACK PREFLIGHT FAILED: {result['error_count']} Beanstandungen.")

    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
