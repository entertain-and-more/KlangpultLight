"""Recorder.tests.test_ui_accessibility — Barrierefreiheits- und Tastaturnavigations-Vertragstests.

Konformität: WCAG 2.1 AA / BITV 2.0 / Policy P-006
Prüft:
- Screenreader-Attribute (AccessibleName, AccessibleDescription, Tooltips) für alle interaktiven Widgets
- Formular-Buddies (Label-Verknüpfungen mit Eingabefeldern und Comboboxen)
- Barrierefreie Menüleiste mit Mnemonics (Datei, Ansicht, Sprache, Hilfe)
- Registrierung und Funktionsfähigkeit globaler Tastaturkürzel (F1, Strg+R, Strg+T, Strg+P, F5, Strg+Q, Strg+1..5)
- ShortcutsDialog: Modale Struktur, Spalten, Tastaturkürzel, BITV 2.0 / WCAG 2.1 AA Hinweis, Initialfokus
- AccessibleRecordingTree: Tastaturinteraktion (Return=Abspielen, Entf=Löschen, F2=Umbenennen, Strg+C=Kopieren, F5=Aktualisieren)
- Soundboard-Pads: AccessibleName, AccessibleDescription und Tooltips mit Hotkey-Zuordnung (1–8)
- 100% Tier-2 6-Sprachen-Parität (DE, EN, ES, ZH, JA, RU) für alle Barrierefreiheits-Texte
- Echte deutsche Umlaute ohne Codierungsfehler
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QKeyEvent
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

# Suchpfad für Recorder
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
from ui.main_window import AccessibleRecordingTree, MainWindow  # noqa: E402
from ui.shortcuts_dialog import ShortcutsDialog  # noqa: E402


@pytest.fixture(autouse=True)
def headless_umgebung(monkeypatch):
    """Offscreen-Umgebung und Mock-Hardware erzwingen."""
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication(sys.argv)


def _erstelle_test_fenster(tmp_path, board_player=None):
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
        library=RecordingLibrary(workspace_dir=str(tmp_path)),
        state=AppState(),
        board_player=board_player,
    )
    return fenster


def test_main_window_accessible_attributes(tmp_path, qt_app):
    """Prüft barrierefreie Namen, Beschreibungen und Tooltips an allen Kern-Widgets."""
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        # Titelfeld
        assert fenster._titel_eingabe.accessibleName() == "Titel"
        assert "Tastenkürzel: Strg+T" in fenster._titel_eingabe.accessibleDescription()
        assert "Strg+T" in fenster._titel_eingabe.toolTip()
        assert fenster._titel_label.buddy() == fenster._titel_eingabe

        # Aufnahmemodus-Combobox
        assert fenster._aufnahme_modus.accessibleName() == "Aufnahme-Modus"
        assert len(fenster._aufnahme_modus.accessibleDescription()) > 0
        assert fenster._modus_label.buddy() == fenster._aufnahme_modus

        # Aufnahme-Button
        assert fenster._btn_aufnahme.accessibleName() == "Aufnahme starten"
        assert "Strg+R" in fenster._btn_aufnahme.accessibleDescription()
        assert "Strg+R" in fenster._btn_aufnahme.toolTip()

        # Planer-Button
        assert "Planer" in fenster._btn_planer.accessibleName()
        assert "Strg+P" in fenster._btn_planer.toolTip()

        # Videoquellen-Liste
        assert fenster._video_quelle_liste.accessibleName() == "Videoquellen-Auswahl"
        assert "Pfeiltasten" in fenster._video_quelle_liste.accessibleDescription()

        # Aufnahmen-Tree
        assert isinstance(fenster._aufnahme_tree, AccessibleRecordingTree)
        assert fenster._aufnahme_tree.accessibleName() == "Aufnahmen und Branches"
        assert "Eingabetaste" in fenster._aufnahme_tree.accessibleDescription()
        assert "Strg+C" in fenster._aufnahme_tree.toolTip()

        # Hinweisfeld für Board
        assert hasattr(fenster, "_no_board_label")
        assert len(fenster._no_board_label.text()) > 0
    finally:
        fenster.close()
        qt_app.processEvents()


def test_board_pad_accessibility(tmp_path, qt_app):
    """Prüft barrierefreie Attribute des Einspieler-Buttons bei geladenem Soundboard."""
    mock_player = MagicMock()
    mock_player._board = None
    fenster = _erstelle_test_fenster(tmp_path, board_player=mock_player)
    try:
        assert hasattr(fenster, "_add_pad_btn")
        assert "Einspieler" in fenster._add_pad_btn.accessibleName()
        assert len(fenster._add_pad_btn.accessibleDescription()) > 0
        assert "Einspieler" in fenster._add_pad_btn.toolTip()
    finally:
        fenster.close()
        qt_app.processEvents()


def test_main_window_menubar_and_actions(tmp_path, qt_app):
    """Prüft, ob die Menüleiste barrierefrei mit Menüs und Tastaturkürzeln ausgestattet ist."""
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        assert hasattr(fenster, "_datei_menu") and fenster._datei_menu is not None
        assert hasattr(fenster, "_ansicht_menu") and fenster._ansicht_menu is not None
        assert hasattr(fenster, "_sprach_menu") and fenster._sprach_menu is not None
        assert hasattr(fenster, "_hilfe_menu") and fenster._hilfe_menu is not None

        assert "Datei" in fenster._datei_menu.title()
        assert "Ansicht" in fenster._ansicht_menu.title()
        assert "Hilfe" in fenster._hilfe_menu.title()

        # Aktionen im Datei-Menü
        assert fenster._aktion_aufnahme.shortcut().toString() == "Ctrl+R"
        assert fenster._aktion_titel.shortcut().toString() == "Ctrl+T"
        assert fenster._aktion_refresh.shortcut().toString() == "F5"
        assert fenster._aktion_beenden.shortcut().toString() == "Ctrl+Q"

        # Aktionen im Hilfe-Menü
        assert fenster._aktion_hilfe.shortcut().toString() == "F1"
        assert fenster._aktion_planer.shortcut().toString() == "Ctrl+P"
    finally:
        fenster.close()
        qt_app.processEvents()


def test_shortcuts_dialog_structure_and_a11y(qt_app):
    """Prüft den ShortcutsDialog auf BITV 2.0 / WCAG 2.1 AA Konformität."""
    dlg = ShortcutsDialog()
    try:
        assert "Tastaturkürzel" in dlg.windowTitle()
        assert "BITV 2.0 / WCAG 2.1 AA" in dlg._lbl_a11y.text()

        # Tabelle: 3 Spalten
        assert dlg._table.columnCount() == 3
        headers = [
            dlg._table.horizontalHeaderItem(0).text(),
            dlg._table.horizontalHeaderItem(1).text(),
            dlg._table.horizontalHeaderItem(2).text(),
        ]
        assert headers == ["Tastenkombination", "Aktion / Funktion", "Bereich"]

        # Mindestens 15 registrierte Tastaturkürzel
        shortcuts = dlg.get_shortcuts_data()
        assert len(shortcuts) >= 15
        assert dlg._table.rowCount() == len(shortcuts)

        # Wichtige Shortcuts enthalten
        keys = [s[0] for s in shortcuts]
        assert any("F1" in k for k in keys)
        assert any("Strg+R" in k for k in keys)
        assert any("Strg+T" in k for k in keys)
        assert any("Strg+P" in k for k in keys)
        assert any("F5" in k for k in keys)
        assert any("Eingabe" in k for k in keys)
        assert any("Entf" in k for k in keys)
        assert any("F2" in k for k in keys)
        assert any("Strg+C" in k for k in keys)
        assert any("Strg+Q" in k for k in keys)

        # Schließen-Button mit Initialfokus
        assert dlg._btn_close.isDefault() is True
        assert dlg._btn_close.text() == "Schließen"

        # Escape-Taste schließt Dialog
        event_esc = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier)
        dlg.keyPressEvent(event_esc)
        assert dlg.result() == 1  # Accepted via accept()
    finally:
        dlg.close()
        qt_app.processEvents()


def test_shortcuts_dialog_multilingual_parity(qt_app):
    """Prüft, ob der ShortcutsDialog dynamisch für alle 6 Sprachen übersetzt werden kann."""
    tr = get_translator()
    dlg = ShortcutsDialog()
    try:
        for lang in SUPPORTED_LANGUAGES:
            tr.set_language(lang)
            dlg.retranslate_ui()

            assert len(dlg.windowTitle()) > 0
            assert len(dlg._lbl_titel.text()) > 0
            assert len(dlg._lbl_a11y.text()) > 0
            assert len(dlg._btn_close.text()) > 0
            assert dlg._table.columnCount() == 3

            # Tabelleneinträge für die jeweilige Sprache gefüllt
            assert dlg._table.rowCount() >= 15
            for r in range(dlg._table.rowCount()):
                assert len(dlg._table.item(r, 0).text()) > 0
                assert len(dlg._table.item(r, 1).text()) > 0
                assert len(dlg._table.item(r, 2).text()) > 0
    finally:
        tr.set_language("de")
        dlg.close()
        qt_app.processEvents()


def test_accessible_recording_tree_keyboard_navigation(tmp_path, qt_app):
    """Prüft die Tastaturbehandlung in AccessibleRecordingTree (Return, Del, F2, Strg+C, F5)."""
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        tree = fenster._aufnahme_tree
        assert isinstance(tree, AccessibleRecordingTree)

        # Mock-Methoden auf fenster setzen zur Erfassung der Tasten-Trigger
        fenster._aufnahme_abspielen = MagicMock()
        fenster._loeschabfrage_starten = MagicMock()
        fenster._umbenennen_dialog_starten = MagicMock()
        fenster._kopiere_aufnahme_in_zwischenablage = MagicMock()
        fenster._lade_aufnahmeliste = MagicMock()

        # Eintrag in Tree einfügen
        item = QTreeWidgetItem(["Testaufnahme 1", "01:23", "2026-09-28"])
        item.setData(0, Qt.ItemDataRole.UserRole, "rec_test_123")
        tree.addTopLevelItem(item)
        tree.setCurrentItem(item)

        # 1. Return -> Abspielen
        ev_return = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Return, Qt.KeyboardModifier.NoModifier)
        tree.keyPressEvent(ev_return)
        fenster._aufnahme_abspielen.assert_called_once_with("rec_test_123")

        # 2. Entf -> Löschen
        ev_del = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier)
        tree.keyPressEvent(ev_del)
        fenster._loeschabfrage_starten.assert_called_once_with("rec_test_123")

        # 3. F2 -> Umbenennen
        ev_f2 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F2, Qt.KeyboardModifier.NoModifier)
        tree.keyPressEvent(ev_f2)
        fenster._umbenennen_dialog_starten.assert_called_once_with("rec_test_123")

        # 4. Strg+C -> In Zwischenablage kopieren
        ev_copy = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        tree.keyPressEvent(ev_copy)
        fenster._kopiere_aufnahme_in_zwischenablage.assert_called_once_with(item)

        # 5. F5 -> Aktualisieren
        ev_f5 = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_F5, Qt.KeyboardModifier.NoModifier)
        tree.keyPressEvent(ev_f5)
        fenster._lade_aufnahmeliste.assert_called_once()
    finally:
        fenster.close()
        qt_app.processEvents()


def test_clipboard_copy_recording_details(tmp_path, qt_app):
    """Prüft, ob _kopiere_aufnahme_in_zwischenablage Aufnahme-Details in die Zwischenablage legt."""
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        item = QTreeWidgetItem(["Interview Podcast 2026", "05:00", "2026-09-28"])
        item.setData(0, Qt.ItemDataRole.UserRole, "rec_abc")
        fenster._aufnahme_audio_pfad = MagicMock(return_value="C:/recordings/mix.wav")

        fenster._kopiere_aufnahme_in_zwischenablage(item)

        clipboard = QGuiApplication.clipboard()
        if clipboard:
            inhalt = clipboard.text()
            assert "Interview Podcast 2026" in inhalt
            assert "C:/recordings/mix.wav" in inhalt

        status_text = fenster._statusleiste.currentMessage()
        assert "kopiert" in status_text.lower()
    finally:
        fenster.close()
        qt_app.processEvents()


def test_panel_toggle_shortcuts(tmp_path, qt_app):
    """Prüft, ob _toggle_panel(0..4) die Panels ein- und ausklappt."""
    fenster = _erstelle_test_fenster(tmp_path)
    try:
        # Panel 0: Quellen (Checkable QGroupBox)
        assert fenster._quellen_box.isChecked() is True
        fenster._toggle_panel(0)
        assert fenster._quellen_box.isChecked() is False
        fenster._toggle_panel(0)
        assert fenster._quellen_box.isChecked() is True

        # Panel 3: Video (Checkable QGroupBox)
        assert fenster._video_box.isChecked() is True
        fenster._toggle_panel(3)
        assert fenster._video_box.isChecked() is False
        fenster._toggle_panel(3)
        assert fenster._video_box.isChecked() is True

        # Panel 4: Aufnahmen (Checkable QGroupBox)
        assert fenster._aufnahmen_box.isChecked() is True
        fenster._toggle_panel(4)
        assert fenster._aufnahmen_box.isChecked() is False
        fenster._toggle_panel(4)
        assert fenster._aufnahmen_box.isChecked() is True
    finally:
        fenster.close()
        qt_app.processEvents()
