"""tests.test_i18n — Tests für das Multi-Language System (Tier-2 nach P-006).

Prüft:
- Verfügbarkeit aller 6 Tier-2-Sprachen (DE, EN, ES, ZH, JA, RU)
- Vollständige Übersetzungsschlüssel-Parität
- Deterministische Fallback-Hierarchie (target -> en -> de -> key)
- Echte deutsche Umlaute (ä, ö, ü, Ä, Ö, Ü, ß)
- Parametrisierte String-Formatierung
- Callback-Benachrichtigung bei Sprachwechsel
- Resilienz bei fehlenden Dateien und Pfadauflösung
"""

import json
import sys
from pathlib import Path

# Pfad zu Recorder/i18n bereitstellen
RECORDER_DIR = Path(__file__).resolve().parent.parent / "Recorder"
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

from i18n.translator import (  # noqa: E402
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    TranslationSystem,
    get_translator,
)


def test_supported_languages_tier2():
    """Prüft, ob alle 6 Sprachen gemäß Tier-2 definiert sind."""
    expected = ("de", "en", "es", "zh", "ja", "ru")
    assert SUPPORTED_LANGUAGES == expected
    for code in expected:
        assert code in LANGUAGE_NAMES
        assert len(LANGUAGE_NAMES[code]) > 0


def test_translator_default_and_switching():
    """Prüft Initialisierung und Sprachumschaltung."""
    tr = TranslationSystem(default_lang="de")
    assert tr.get_language() == "de"
    assert tr.t("app_title") == "Klangpult light – Recorder"

    # Umschaltung auf Englisch
    assert tr.set_language("en") is True
    assert tr.get_language() == "en"
    assert tr.t("start_recording") == "Start Recording"

    # Umschaltung auf Spanisch
    assert tr.set_language("es") is True
    assert tr.t("start_recording") == "Iniciar grabación"

    # Umschaltung auf Chinesisch
    assert tr.set_language("zh") is True
    assert tr.t("start_recording") == "开始录制"

    # Umschaltung auf Japanisch
    assert tr.set_language("ja") is True
    assert tr.t("start_recording") == "録音開始"

    # Umschaltung auf Russisch
    assert tr.set_language("ru") is True
    assert tr.t("start_recording") == "Начать запись"

    # Ungültige Sprache wird ignoriert
    assert tr.set_language("invalid_xx") is False
    assert tr.get_language() == "ru"


def test_fallback_chain(tmp_path: Path):
    """Prüft die 4-stufige Fallback-Kette: target -> en -> de -> key."""
    custom_json = tmp_path / "translations.json"
    data = {
        "full_key": {
            "de": "Vollständiger Text",
            "en": "Full Text",
            "es": "Texto completo",
            "zh": "完整文本",
            "ja": "完全なテキスト",
            "ru": "Полный текст",
        },
        "only_de_and_en": {
            "de": "Deutscher Text",
            "en": "English Fallback",
        },
        "only_de": {
            "de": "Nur Deutscher Text",
        },
    }
    custom_json.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

    tr = TranslationSystem(default_lang="es", translations_file=custom_json)

    # 1. Direkter Treffer in Spanisch
    assert tr.t("full_key") == "Texto completo"

    # 2. Fallback auf Englisch
    assert tr.t("only_de_and_en") == "English Fallback"

    # 3. Fallback auf Deutsch
    assert tr.t("only_de") == "Nur Deutscher Text"

    # 4. Fallback auf den Key selbst
    assert tr.t("unknown_key") == "unknown_key"


def test_german_umlauts_authenticity():
    """Prüft, ob in deutschen Texten echte Umlaute verwendet werden (P-006)."""
    tr = get_translator()
    tr.set_language("de")

    # Beispiele mit Umlauten
    assert "Wählt" in tr.t("recording_mode_tooltip")
    assert "Öffnet" in tr.t("open_planer_tooltip")
    assert "öffnen" in tr.t("open_planer")
    assert "hinzufügen" in tr.t("add_pad")
    assert "Verfügbare" in tr.t("available_inputs")
    assert "Eingänge" in tr.t("available_inputs")
    assert "Löschen" in tr.t("delete")
    assert "Prüfe" in tr.t("checking_connection")


def test_coverage_and_parity():
    """Prüft 100% Parität über alle 6 Sprachen in translations.json."""
    tr = get_translator()
    coverage = tr.check_coverage()

    assert coverage["total_keys"] >= 40
    assert coverage["is_complete"] is True
    for lang in SUPPORTED_LANGUAGES:
        assert coverage["coverage_percent"][lang] == 100.0
        assert len(coverage["missing_keys"][lang]) == 0


def test_listener_callback():
    """Prüft Callback-Benachrichtigung bei Sprachwechsel."""
    tr = TranslationSystem(default_lang="de")
    called_with = []

    def on_lang_change(lang: str):
        called_with.append(lang)

    tr.register_listener(on_lang_change)
    tr.set_language("en")
    tr.set_language("es")
    tr.set_language("es")  # Keine erneute Benachrichtigung bei gleicher Sprache

    assert called_with == ["en", "es"]

    tr.unregister_listener(on_lang_change)
    tr.set_language("zh")
    assert called_with == ["en", "es"]


def test_missing_or_corrupt_file(tmp_path: Path):
    """Prüft Resilienz bei fehlender oder ungültiger JSON-Datei."""
    non_existent = tmp_path / "does_not_exist.json"
    tr_missing = TranslationSystem(default_lang="en", translations_file=non_existent)
    assert tr_missing.t("any_key") == "any_key"

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{corrupt: json}", encoding="utf-8")
    tr_corrupt = TranslationSystem(default_lang="en", translations_file=corrupt)
    assert tr_corrupt.t("any_key") == "any_key"
