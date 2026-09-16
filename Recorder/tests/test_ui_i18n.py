"""Recorder.tests.test_ui_i18n — Automatisierte Tests für die dynamische UI-Lokalisierung.

Prüft:
- Initialisierung des Sprachmenüs mit allen 6 Tier-2-Sprachen (DE, EN, ES, ZH, JA, RU)
- Dynamische Aktualisierung aller Oberflächentexte (retranslate_ui)
- Persistenz der Sprachauswahl via QSettings
- Saubere Registrierung und Deregistrierung des Event-Listeners beim Schließen
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

# Recorder-Verzeichnis im Suchpfad sicherstellen
RECORDER_DIR = Path(__file__).resolve().parent.parent
if str(RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(RECORDER_DIR))

from audio.device_manager import AudioDevice  # noqa: E402
from audio.engine import AudioEngine  # noqa: E402
from audio.mixer_channel import MixerChannel  # noqa: E402
from core.app_state import AppState  # noqa: E402
from core.config import AppConfig  # noqa: E402
from i18n.translator import SUPPORTED_LANGUAGES, get_translator  # noqa: E402
from recordings.library import RecordingLibrary  # noqa: E402
from ui.main_window import MainWindow  # noqa: E402


@pytest.fixture(autouse=True)
def headless_umgebung(monkeypatch):
    """Offscreen-Umgebung erzwingen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _erstelle_test_fenster(tmp_path):
    geraet = AudioDevice(
        index=1,
        name="Testmikrofon",
        max_input_channels=2,
        default_samplerate=48000.0,
        verified=True,
        is_mock=True,
    )

    class FakeDeviceManager:
        def list_input_devices(self, verify=True):
            return [geraet]

        def verified_input_devices(self, refresh=False):
            return [geraet]

        def suggest_default_assignment(self):
            return {"mic_1": geraet, "mic_2": None, "system": None}

    config = AppConfig(
        mock_audio=False,
        workspace_dir=str(tmp_path),
        samplerate=48000,
        channels=2,
    )
    engine = AudioEngine(
        config=config,
        channels=[MixerChannel(source_id="mic_1", name="Mikrofon 1")],
    )
    fenster = MainWindow(
        config=config,
        device_manager=FakeDeviceManager(),
        engine=engine,
        library=RecordingLibrary(str(tmp_path)),
        state=AppState(),
    )
    return fenster


def test_sprachmenue_vorhanden_und_vollstaendig(tmp_path, qt_app):
    """Prüft, ob das Menü 'Sprache' alle 6 Sprachen anbietet und exklusiv schaltet."""
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        assert hasattr(fenster, "_sprach_menu")
        assert fenster._sprach_menu is not None
        assert len(fenster._sprach_aktionen) == 6
        for lang in SUPPORTED_LANGUAGES:
            assert lang in fenster._sprach_aktionen
            assert fenster._sprach_aktionen[lang].isCheckable()

        # Genau eine Aktion aktiv
        checked = [k for k, a in fenster._sprach_aktionen.items() if a.isChecked()]
        assert len(checked) == 1
    finally:
        fenster.close()
        qt_app.processEvents()


def test_dynamischer_sprachwechsel_ui_texte(tmp_path, qt_app):
    """Prüft, ob retranslate_ui alle sichtbaren Komponenten für alle 6 Sprachen übersetzt."""
    tr = get_translator()
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        for lang in SUPPORTED_LANGUAGES:
            fenster._sprache_wechseln(lang)
            assert fenster._translator.get_language() == lang
            assert fenster._sprach_aktionen[lang].isChecked()

            # Fenstertitel
            assert fenster.windowTitle() == tr.t("app_title")

            # Buttons & Aktionen
            assert fenster._btn_aufnahme.text() == tr.t("start_recording")
            assert fenster._btn_planer.text() == tr.t("open_planer")

            # Headers
            assert fenster._aufnahme_tree.headerItem().text(0) == tr.t("header_title")
            assert fenster._aufnahme_tree.headerItem().text(1) == tr.t("header_duration")
            assert fenster._aufnahme_tree.headerItem().text(2) == tr.t("header_created")

            # GroupBoxen & Labels
            assert fenster._quellen_box.title() == tr.t("sources")
            assert fenster._modus_label.text() == tr.t("recording_mode")
            assert fenster._aufnahmen_box.title() == tr.t("recordings")
    finally:
        # Zurück auf Deutsch für sauberen Zustand
        fenster._sprache_wechseln("de")
        fenster.close()
        qt_app.processEvents()


def test_qsettings_persistenz(tmp_path, qt_app):
    """Prüft, ob die Sprachwahl in QSettings persistiert und wiederhergestellt wird."""
    settings = QSettings("Klangpult", "KlangpultLight")
    original_lang = settings.value("ui/language", "de")

    fenster = _erstelle_test_fenster(tmp_path)
    try:
        fenster._sprache_wechseln("es")
        assert settings.value("ui/language") == "es"

        fenster._sprache_wechseln("en")
        assert settings.value("ui/language") == "en"
    finally:
        # Wiederherstellen
        settings.setValue("ui/language", original_lang)
        get_translator().set_language("de")
        fenster.close()
        qt_app.processEvents()


def test_listener_deregistrierung_beim_schliessen(tmp_path, qt_app):
    """Prüft, ob der UI-Listener bei Fenster-Schließung sauber deregistriert wird."""
    tr = get_translator()
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        assert fenster.retranslate_ui in tr._listeners
    finally:
        fenster.close()
        qt_app.processEvents()

    assert fenster.retranslate_ui not in tr._listeners
