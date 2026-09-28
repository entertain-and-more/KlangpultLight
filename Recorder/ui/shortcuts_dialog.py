"""Recorder.ui.shortcuts_dialog — Barrierefreier Dialog für Tastaturkürzel.

Konformität: WCAG 2.1 AA / BITV 2.0
Features:
- Modaler Dialog mit strukturierter tabellarischer Übersicht (3 Spalten: Tastenkombination, Aktion, Bereich)
- Vollständige Tastaturbedienbarkeit (Escape schließt den Dialog, Tab-Navigation)
- Initialer Tastaturfokus auf der Schließen-Schaltfläche
- Barrierefreier Konformitätshinweis für Screenreader
- Vollständig offscreen-sicher (ohne modal-blockierende Schleifen in Tests)
- Vollständige Lokalisierung über den Translator (de, en, es, zh, ja, ru)
"""

from __future__ import annotations

from typing import List, Tuple
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from i18n.translator import get_translator, t


class ShortcutsDialog(QDialog):
    """Barrierefreier Hilfedialog mit allen Tastaturkürzeln nach WCAG 2.1 AA / BITV 2.0."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._translator = get_translator()
        self.setModal(True)
        self.setMinimumSize(640, 520)
        self.resize(700, 560)

        self._setup_ui()
        self.retranslate_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Titel & Überschrift
        self._lbl_titel = QLabel()
        self._lbl_titel.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        self._lbl_titel.setAccessibleName("Titel Tastaturkürzel und Barrierefreiheit")
        layout.addWidget(self._lbl_titel)

        # A11y / BITV 2.0 Hinweis
        self._lbl_a11y = QLabel()
        self._lbl_a11y.setWordWrap(True)
        self._lbl_a11y.setStyleSheet("color: #aaaaaa; font-size: 12px; line-height: 1.4;")
        self._lbl_a11y.setAccessibleName("Hinweis zur Barrierefreiheit")
        layout.addWidget(self._lbl_a11y)

        # Tabelle
        self._table = QTableWidget(self)
        self._table.setColumnCount(3)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self._table.setAlternatingRowColors(True)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(False)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setStyleSheet(
            "QTableWidget { background-color: #1e1e1e; color: #e0e0e0; gridline-color: #333333; }"
            "QTableWidget::item { padding: 6px; }"
            "QTableWidget::item:selected { background-color: #2a4d69; color: #ffffff; }"
            "QHeaderView::section { background-color: #252525; color: #ffffff; padding: 6px; font-weight: bold; }"
        )
        layout.addWidget(self._table)

        # Untere Leiste mit Schließen-Button
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()

        self._btn_close = QPushButton()
        self._btn_close.setDefault(True)
        self._btn_close.setMinimumWidth(110)
        self._btn_close.setStyleSheet(
            "QPushButton { background-color: #007acc; color: #ffffff; padding: 6px 16px; border-radius: 4px; font-weight: bold; }"
            "QPushButton:hover { background-color: #0098ff; }"
            "QPushButton:focus { outline: 2px solid #ffffff; }"
        )
        self._btn_close.clicked.connect(self.accept)
        bottom_layout.addWidget(self._btn_close)

        layout.addLayout(bottom_layout)

        # Initialer Fokus auf den Schließen-Button (WCAG 2.1 AA Fokusführung)
        self._btn_close.setFocus()

    def get_shortcuts_data(self) -> List[Tuple[str, str, str]]:
        """Gibt alle registrierten Tastenkombinationen als Tupel (Kürzel, Aktion, Bereich) zurück."""
        bereich_allgemein = "Allgemein"
        bereich_aufnahme = t("recording_mode")
        bereich_aufnahmen = t("recordings")
        bereich_planer = t("planer_title")
        bereich_soundboard = t("pads_title")
        bereich_ansicht = t("menu_view").replace("&", "").strip()
        bereich_datei = t("menu_file").replace("&", "").strip()
        bereich_hilfe = t("menu_help").replace("&", "").strip()

        return [
            ("F1", t("action_shortcuts").replace("…", "").strip(), bereich_hilfe),
            ("Strg+R / Leertaste", t("start_recording_tooltip").replace("(Strg+R)", "").strip(), bereich_aufnahme),
            ("Strg+T", t("action_focus_title"), bereich_aufnahme),
            ("Strg+P", t("open_planer"), bereich_planer),
            ("F5", t("action_refresh"), bereich_aufnahmen),
            ("Eingabe / Return", t("play"), bereich_aufnahmen),
            ("Entf / Backspace", t("delete"), bereich_aufnahmen),
            ("F2", t("rename"), bereich_aufnahmen),
            ("Strg+C", t("recording_copied_to_clipboard"), bereich_aufnahmen),
            ("1 – 8", t("pad_accessible_name").replace("{label}", "1–8"), bereich_soundboard),
            ("Strg+1", t("action_toggle_sources"), bereich_ansicht),
            ("Strg+2", t("action_toggle_recording"), bereich_ansicht),
            ("Strg+3", t("action_toggle_pads"), bereich_ansicht),
            ("Strg+4", t("action_toggle_video"), bereich_ansicht),
            ("Strg+5", t("action_toggle_recordings"), bereich_ansicht),
            ("Alt+D, Alt+A, Alt+S, Alt+H", "Menüleiste tastaturgeführt bedienen", "Menü"),
            ("Strg+Q", t("action_quit"), bereich_datei),
            ("Esc", "Fenster oder Dialog schließen", bereich_allgemein),
        ]

    def retranslate_ui(self) -> None:
        """Aktualisiert alle UI-Texte und Tabelleneinträge gemäß der aktiven Sprache."""
        self.setWindowTitle(t("shortcuts_title"))
        self._lbl_titel.setText(t("shortcuts_title"))
        self._lbl_a11y.setText(t("shortcuts_a11y_note"))

        # Tabellen-Header
        self._table.setHorizontalHeaderLabels([
            t("shortcuts_header_shortcut"),
            t("shortcuts_header_action"),
            t("shortcuts_header_section"),
        ])
        self._table.setAccessibleName(t("shortcuts_title"))
        self._table.setAccessibleDescription(
            "Tabelle aller Tastaturkürzel mit Tastenkombination, Aktion und Programmbereich."
        )

        # Tabelleneinträge füllen
        shortcuts = self.get_shortcuts_data()
        self._table.setRowCount(len(shortcuts))

        for row, (taste, aktion, bereich) in enumerate(shortcuts):
            item_taste = QTableWidgetItem(taste)
            item_taste.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item_taste.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            item_aktion = QTableWidgetItem(aktion)
            item_aktion.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item_aktion.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            item_bereich = QTableWidgetItem(bereich)
            item_bereich.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            item_bereich.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)

            self._table.setItem(row, 0, item_taste)
            self._table.setItem(row, 1, item_aktion)
            self._table.setItem(row, 2, item_bereich)

        # Schließen-Button
        self._btn_close.setText(t("btn_close"))
        self._btn_close.setAccessibleName(t("btn_close"))
        self._btn_close.setAccessibleDescription(
            "Schließt das Hilfefenster für Tastaturkürzel (Taste: Escape)."
        )

    def keyPressEvent(self, event) -> None:  # noqa: N802 — Qt-Konvention
        """Ermöglicht das Schließen des Dialogs über die Escape-Taste."""
        if event.key() == Qt.Key.Key_Escape:
            self.accept()
            return
        super().keyPressEvent(event)
