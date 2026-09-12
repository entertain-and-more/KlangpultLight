"""translator.py — Multi-Language Support System für Klangpult light
===================================================================
Version: 2.1.0 (Tier-2 6-Sprachen-Ausbau nach Policy P-006)
Unterstützt: Deutsch (de), English (en), Español (es), 简体中文 (zh), 日本語 (ja), Русский (ru).

Eigenschaften:
- Deterministische 4-stufige Fallback-Kette: target -> en -> de -> key
- Vollständige Typsicherheit, Formatierungs-Platzhalter {name}
- Robust gegen fehlende Dateien und defektes JSON
- Erkennt Quell-, Entwicklungs- und PyInstaller-Umgebungen (Onefile / Onedir)
"""

from __future__ import annotations

import json
import locale
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

SUPPORTED_LANGUAGES: Tuple[str, ...] = ("de", "en", "es", "zh", "ja", "ru")
DEFAULT_LANGUAGE: str = "de"
FALLBACK_CHAIN: Tuple[str, ...] = ("en", "de")

LANGUAGE_NAMES: Dict[str, str] = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "zh": "简体中文",
    "ja": "日本語",
    "ru": "Русский",
}

LANGUAGE_DISPLAY_NAMES: Dict[str, str] = {
    "de": "Deutsch (de)",
    "en": "English (en)",
    "es": "Español (es)",
    "zh": "简体中文 (zh)",
    "ja": "日本語 (ja)",
    "ru": "Русский (ru)",
}


def detect_system_language() -> str:
    """Ermittelt die Systemsprache, Fallback auf 'de'."""
    try:
        loc = locale.getlocale()[0]
        if loc:
            code = loc.split("_")[0].lower()
            if code in SUPPORTED_LANGUAGES:
                return code
    except Exception:
        pass
    return DEFAULT_LANGUAGE


def resolve_translations_file(custom_path: Optional[Path] = None) -> Path:
    """Sucht die Datei locales/translations.json in verschiedenen Laufzeitumgebungen."""
    if custom_path is not None:
        p = Path(custom_path)
        if p.is_file():
            return p
        if (p / "locales" / "translations.json").is_file():
            return p / "locales" / "translations.json"
        if (p / "translations.json").is_file():
            return p / "translations.json"

    # PyInstaller _MEIPASS
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        p = Path(meipass) / "locales" / "translations.json"
        if p.is_file():
            return p
        p_shared = Path(meipass) / "shared" / "locales" / "translations.json"
        if p_shared.is_file():
            return p_shared

    # PyInstaller onedir (neben exe)
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        for cand in [
            exe_dir / "locales" / "translations.json",
            exe_dir / "_internal" / "locales" / "translations.json",
            exe_dir / "Recorder" / "locales" / "translations.json",
        ]:
            if cand.is_file():
                return cand

    # Quellumgebung: relative Pfade ausgehend von dieser Datei
    here = Path(__file__).resolve().parent  # Recorder/i18n
    candidates = [
        here.parent / "locales" / "translations.json",        # Recorder/locales/
        here.parent.parent / "locales" / "translations.json", # Repo-Root/locales/
        here.parent.parent / "shared" / "translations.json",  # shared/
    ]
    for cand in candidates:
        if cand.is_file():
            return cand

    # Fallback: Standard-Pfad im Root
    return here.parent.parent / "locales" / "translations.json"


class TranslationSystem:
    """Multi-Language Support System mit 6-Sprachen Tier-2 Standard nach P-006."""

    def __init__(
        self,
        default_lang: str = DEFAULT_LANGUAGE,
        translations_file: Optional[Path | str] = None,
    ) -> None:
        self.current_lang = default_lang if default_lang in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
        self.translations_file = resolve_translations_file(
            Path(translations_file) if translations_file else None
        )
        self.translations: Dict[str, Dict[str, str]] = {}
        self._listeners: List[Callable[[str], None]] = []
        self._load_translations()

    def _load_translations(self) -> None:
        """Lädt Übersetzungen aus der JSON-Datei."""
        if self.translations_file.is_file():
            try:
                with open(self.translations_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self.translations = data
                    else:
                        self.translations = {}
            except Exception:
                self.translations = {}
        else:
            self.translations = {}

    def t(self, key: str, **kwargs: Any) -> str:
        """Übersetzt einen Key in die aktive Sprache mit robuster Fallback-Kette.

        Kette: current_lang -> en -> de -> key selbst.
        Erlaubt Format-Platzhalter, z. B. t("recording_time", duration="00:15:30")
        """
        if not key:
            return ""

        entry = self.translations.get(key)
        text: Optional[str] = None

        if isinstance(entry, dict):
            # 1. Gewählte Zielsprache
            val = entry.get(self.current_lang)
            if isinstance(val, str) and val.strip():
                text = val
            else:
                # 2. Fallbacks (en -> de)
                for fb in FALLBACK_CHAIN:
                    val = entry.get(fb)
                    if isinstance(val, str) and val.strip():
                        text = val
                        break

        if text is None:
            text = key

        if kwargs:
            try:
                return text.format(**kwargs)
            except Exception:
                return text
        return text

    def set_language(self, lang: str) -> bool:
        """Setzt die aktive Zielsprache und benachrichtigt registrierte Listener."""
        if lang in SUPPORTED_LANGUAGES and lang != self.current_lang:
            self.current_lang = lang
            self._notify_listeners()
            return True
        elif lang in SUPPORTED_LANGUAGES:
            return True
        return False

    def get_language(self) -> str:
        """Liefert den aktuellen Sprachcode."""
        return self.current_lang

    def register_listener(self, callback: Callable[[str], None]) -> None:
        """Registriert einen Callback für Sprachwechsel (z. B. UI-Retranslation)."""
        if callback not in self._listeners:
            self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[str], None]) -> None:
        """Entfernt einen registrierten Callback."""
        if callback in self._listeners:
            self._listeners.remove(callback)

    def _notify_listeners(self) -> None:
        """Ruft alle registrierten Listener mit der neuen Sprache auf."""
        for cb in list(self._listeners):
            try:
                cb(self.current_lang)
            except Exception:
                pass

    @classmethod
    def get_supported_languages(cls) -> List[str]:
        """Liefert die Liste aller 6 unterstützten Sprachcodes."""
        return list(SUPPORTED_LANGUAGES)

    @classmethod
    def get_language_names(cls) -> Dict[str, str]:
        """Liefert Mapping von Sprachcode auf nativer Sprachname."""
        return dict(LANGUAGE_NAMES)

    @classmethod
    def get_language_display_names(cls) -> Dict[str, str]:
        """Liefert Mapping von Sprachcode auf UI-Display-Name."""
        return dict(LANGUAGE_DISPLAY_NAMES)

    def check_coverage(self) -> Dict[str, Any]:
        """Prüft Vollständigkeit der Übersetzungen über alle 6 Sprachen."""
        total_keys = len(self.translations)
        missing: Dict[str, List[str]] = {lang: [] for lang in SUPPORTED_LANGUAGES}

        for key, entry in self.translations.items():
            if not isinstance(entry, dict):
                for lang in SUPPORTED_LANGUAGES:
                    missing[lang].append(key)
                continue
            for lang in SUPPORTED_LANGUAGES:
                val = entry.get(lang)
                if not val or not str(val).strip():
                    missing[lang].append(key)

        coverage: Dict[str, float] = {}
        for lang in SUPPORTED_LANGUAGES:
            cov = ((total_keys - len(missing[lang])) / total_keys * 100.0) if total_keys > 0 else 0.0
            coverage[lang] = round(cov, 1)

        return {
            "total_keys": total_keys,
            "coverage_percent": coverage,
            "missing_keys": missing,
            "is_complete": all(len(missing[lang]) == 0 for lang in SUPPORTED_LANGUAGES),
        }


# Globaler Singleton
_translator: Optional[TranslationSystem] = None


def get_translator() -> TranslationSystem:
    """Liefert die globale TranslationSystem-Instanz (Lazy-Init)."""
    global _translator
    if _translator is None:
        _translator = TranslationSystem()
    return _translator


def t(key: str, **kwargs: Any) -> str:
    """Globale Hilfsfunktion zur Übersetzung."""
    return get_translator().t(key, **kwargs)
