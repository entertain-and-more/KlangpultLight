"""Klangpult light - Internationalisierung & Mehrsprachigkeit (Tier-2 nach P-006).

Unterstützte Sprachen:
  - de: Deutsch (Standard / Primärsprache)
  - en: English
  - es: Español
  - zh: 简体中文 (Chinesisch vereinfacht)
  - ja: 日本語 (Japanisch)
  - ru: Русский (Russisch)
"""

from .translator import (
    FALLBACK_CHAIN,
    LANGUAGE_DISPLAY_NAMES,
    LANGUAGE_NAMES,
    SUPPORTED_LANGUAGES,
    TranslationSystem,
    get_translator,
    t,
)

__all__ = [
    "FALLBACK_CHAIN",
    "LANGUAGE_DISPLAY_NAMES",
    "LANGUAGE_NAMES",
    "SUPPORTED_LANGUAGES",
    "TranslationSystem",
    "get_translator",
    "t",
]
