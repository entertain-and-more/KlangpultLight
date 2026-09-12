"""Recorder.tests.test_i18n — Recorder-interne Tests für das Multi-Language System."""

import sys
from pathlib import Path

# Sicherstellen, dass Recorder im Pfad ist
RECORDER_DIR = Path(__file__).resolve().parent.parent
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

from i18n.translator import (  # noqa: E402
    SUPPORTED_LANGUAGES,
    TranslationSystem,
    get_translator,
)


def test_recorder_supported_languages_tier2():
    """Prüft Tier-2 Sprachkonstanten."""
    assert len(SUPPORTED_LANGUAGES) == 6
    assert set(SUPPORTED_LANGUAGES) == {"de", "en", "es", "zh", "ja", "ru"}


def test_recorder_translator_switching():
    """Prüft Sprachumschaltung und Übersetzung im Recorder-Kontext."""
    tr = TranslationSystem(default_lang="de")
    assert tr.t("app_title") == "Klangpult light – Recorder"

    tr.set_language("en")
    assert tr.t("start_recording") == "Start Recording"

    tr.set_language("es")
    assert tr.t("start_recording") == "Iniciar grabación"


def test_recorder_translations_parity():
    """Prüft Parität der Übersetzungsschlüssel."""
    tr = get_translator()
    cov = tr.check_coverage()
    assert cov["is_complete"] is True
    assert cov["total_keys"] >= 40
