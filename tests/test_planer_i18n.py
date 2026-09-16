"""tests.test_planer_i18n — Tests für Tier-2 Internationalisierung im Planer-Web-Companion.

Prüft:
- Vorhandensein und Validität von planer/app/i18n.js
- Vorhandensein und Synchronizität von planer/locales/translations.json
- Planer-Server-Endpunkt /api/translations und /api/i18n
- HTML-Sprachauswahl im Kopfbereich von planer/index.html
- Vollständigkeit und Struktur-Parität von README.es.md mit README.md
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import urlopen

from planer.server.planer_server import PlanerServer

REPO_ROOT = Path(__file__).resolve().parent.parent
PLANER_DIR = REPO_ROOT / "planer"
LOCALES_FILE = REPO_ROOT / "locales" / "translations.json"
PLANER_LOCALES_FILE = PLANER_DIR / "locales" / "translations.json"
I18N_JS_FILE = PLANER_DIR / "app" / "i18n.js"
INDEX_HTML_FILE = PLANER_DIR / "index.html"
README_ES_FILE = REPO_ROOT / "README.es.md"
README_EN_FILE = REPO_ROOT / "README.md"


def test_i18n_js_file_contract():
    """Prüft, ob i18n.js existiert und die wesentlichen Modulschnittstellen exportiert."""
    assert I18N_JS_FILE.is_file(), f"{I18N_JS_FILE} fehlt!"
    content = I18N_JS_FILE.read_text(encoding="utf-8")

    assert "export const SUPPORTED_LANGUAGES" in content
    assert "export const DEFAULT_LANGUAGE" in content
    assert "export function t(" in content
    assert "export function setLanguage(" in content
    assert "export function getLanguage(" in content
    assert "export function applyTranslations(" in content
    assert "export async function initI18n(" in content
    assert "export function onLanguageChange(" in content

    # Alle 6 Sprachen definiert
    for lang in ("de", "en", "es", "zh", "ja", "ru"):
        assert f'"{lang}"' in content or f"'{lang}'" in content


def test_translations_json_sync():
    """Prüft, ob planer/locales/translations.json mit dem Root-Wörterbuch synchron ist."""
    assert PLANER_LOCALES_FILE.is_file(), f"{PLANER_LOCALES_FILE} fehlt!"
    assert LOCALES_FILE.is_file(), f"{LOCALES_FILE} fehlt!"

    with open(LOCALES_FILE, "r", encoding="utf-8") as f:
        root_dict = json.load(f)

    with open(PLANER_LOCALES_FILE, "r", encoding="utf-8") as f:
        planer_dict = json.load(f)

    assert root_dict == planer_dict
    assert len(root_dict) >= 49


def test_planer_server_translations_endpoint():
    """Startet PlanerServer auf einem dynamischen Port (port=0) und ruft /api/translations ab."""
    server = PlanerServer(library_port=8767, projects_port=8769)
    server.start(host="127.0.0.1", port=0)
    bound_port = server.port
    assert bound_port is not None and bound_port > 0

    try:
        # Test 1: /api/translations
        url = f"http://127.0.0.1:{bound_port}/api/translations"
        with urlopen(url, timeout=3.0) as resp:
            assert resp.status == 200
            assert "application/json" in resp.headers.get("Content-Type", "")
            data = json.loads(resp.read().decode("utf-8"))
            assert isinstance(data, dict)
            assert "app_title" in data
            assert "planer_title" in data
            assert data["app_title"]["es"] == "Klangpult light – Grabador"
            assert data["planer_title"]["es"] == "Klangpult light – Planificador"

        # Test 2: Alias /api/i18n
        url_alias = f"http://127.0.0.1:{bound_port}/api/i18n"
        with urlopen(url_alias, timeout=3.0) as resp:
            assert resp.status == 200
            data_alias = json.loads(resp.read().decode("utf-8"))
            assert data_alias == data
    finally:
        server.stop()


def test_index_html_has_lang_selector_and_i18n():
    """Prüft, ob index.html den Sprachauswahl-Selector und data-i18n Attribute enthält."""
    assert INDEX_HTML_FILE.is_file()
    html = INDEX_HTML_FILE.read_text(encoding="utf-8")

    assert 'id="lang-select"' in html
    assert 'class="lang-selector"' in html
    assert 'data-i18n="planer_title"' in html
    assert 'data-i18n-title="reload_view"' in html
    for lang in ("de", "en", "es", "zh", "ja", "ru"):
        assert f'value="{lang}"' in html


def test_readme_es_parity_and_structure():
    """Prüft, ob README.es.md existiert und alle 17 Abschnitte der Quick Navigation enthält."""
    assert README_ES_FILE.is_file(), f"{README_ES_FILE} fehlt!"
    content_es = README_ES_FILE.read_text(encoding="utf-8")
    content_en = README_EN_FILE.read_text(encoding="utf-8")

    # Mindestens 20 KB
    assert len(content_es) > 20000

    # Navigationspunkte
    assert "## Navegación Rápida" in content_es
    for i in range(1, 18):
        assert f"{i}. [" in content_es

    # Wichtige Schlüsselwörter
    assert "Zero-Egress" in content_es
    assert "RunAsInvoker" in content_es
    assert "WASAPI" in content_es
    assert "Teleprónter" in content_es or "teleprónter" in content_es
    assert "```mermaid" in content_es

    # Sprachverlinkung in allen Versionen
    assert "[🇪🇸 Versión en español](README.es.md)" in content_en
    assert "[🇪🇸 Versión en español](README.es.md)" in content_es
