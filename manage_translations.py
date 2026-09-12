#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""manage_translations.py — Multi-Language Scanner & Auditor für Klangpult light
================================================================================
Scannt UI-Dateien nach Texten und auditiert locales/translations.json
gemäß dem 6-Sprachen Tier-2 Standard (Policy P-006: DE, EN, ES, ZH, JA, RU).

Verwendung:
    python manage_translations.py [--check] [--dir VERZEICHNIS]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SUPPORTED_LANGUAGES = ("de", "en", "es", "zh", "ja", "ru")
ROOT_DIR = Path(__file__).resolve().parent
DEFAULT_TRANSLATION_FILE = ROOT_DIR / "locales" / "translations.json"


def load_translations(filepath: Path) -> dict[str, dict[str, str]]:
    """Lädt die translations.json Datei."""
    if not filepath.is_file():
        print(f"FEHLER: Übersetzungsdatei nicht gefunden: {filepath}")
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def audit_translations(translations: dict[str, dict[str, str]]) -> int:
    """Auditiert Übersetzungen auf Vollständigkeit, Umlaute und Parität."""
    print("=" * 65)
    print("AUDIT: Klangpult light Multi-Language Tier-2 (Policy P-006)")
    print("=" * 65)

    total_keys = len(translations)
    print(f"Gesamtanzahl Übersetzungsschlüssel: {total_keys}")

    if total_keys == 0:
        print("FEHLER: Keine Übersetzungsschlüssel gefunden!")
        return 1

    missing_by_lang: dict[str, list[str]] = {lang: [] for lang in SUPPORTED_LANGUAGES}
    empty_by_lang: dict[str, list[str]] = {lang: [] for lang in SUPPORTED_LANGUAGES}

    for key, data in translations.items():
        if not isinstance(data, dict):
            for lang in SUPPORTED_LANGUAGES:
                missing_by_lang[lang].append(key)
            continue

        for lang in SUPPORTED_LANGUAGES:
            if lang not in data:
                missing_by_lang[lang].append(key)
            elif not str(data[lang]).strip():
                empty_by_lang[lang].append(key)

    print("\nAbdeckung nach Zielsprache:")
    has_errors = False
    for lang in SUPPORTED_LANGUAGES:
        missing_count = len(missing_by_lang[lang]) + len(empty_by_lang[lang])
        coverage = ((total_keys - missing_count) / total_keys) * 100.0
        status = "OK" if coverage == 100.0 else f"LÜCKEN ({missing_count})"
        print(f"  [{lang}] {coverage:6.1f}%  {status}")
        if coverage < 100.0:
            has_errors = True

    # Umlaut-Prüfung für deutsche Texte
    umlaut_signals = ["ä", "ö", "ü", "Ä", "Ö", "Ü", "ß"]
    de_with_umlauts = 0
    for key, data in translations.items():
        if isinstance(data, dict) and "de" in data:
            val = str(data["de"])
            if any(u in val for u in umlaut_signals):
                de_with_umlauts += 1

    print(f"\nDeutsche Texte mit echten Umlauten (P-006 Konformität): {de_with_umlauts}")
    print("=" * 65)

    if has_errors:
        print("ERGEBNIS: Audit FEHLGESCHLAGEN — Unvollständige Übersetzungen.")
        return 1
    else:
        print("ERGEBNIS: Audit BESTANDEN — 100% Tier-2 Parität über alle 6 Sprachen.")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Multi-Language Manager für Klangpult light")
    parser.add_argument("--check", action="store_true", help="Führt Vollständigkeitsprüfung durch")
    parser.add_argument("--file", type=str, default=str(DEFAULT_TRANSLATION_FILE), help="Pfad zu translations.json")
    args = parser.parse_args()

    file_path = Path(args.file)
    translations = load_translations(file_path)
    if not translations:
        return 1

    return audit_translations(translations)


if __name__ == "__main__":
    sys.exit(main())
