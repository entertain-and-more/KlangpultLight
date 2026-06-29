"""ui.styles — Schlankes Dark-Theme für den Klangpult light – Recorder.

Frisches, ruhiges Design. Kein alter Studio-PySide-Look.
"""

# Farbpalette
FARBE_HINTERGRUND = "#1a1a1f"
FARBE_OBERFLÄCHE = "#252530"
FARBE_OBERFLÄCHE_HOCH = "#2d2d3a"
FARBE_RAND = "#3a3a4a"
FARBE_TEXT_PRIMÄR = "#e8e8f0"
FARBE_TEXT_SEKUNDÄR = "#8888a0"
FARBE_AKZENT = "#5c8af0"
FARBE_AUFNAHME_AKTIV = "#e05050"
FARBE_AUFNAHME_STOP = "#4a8f6a"
FARBE_PEGEL_NIEDRIG = "#4a8f6a"
FARBE_PEGEL_MITTEL = "#d4a030"
FARBE_PEGEL_HOCH = "#e05050"
FARBE_PEGEL_HINTERGRUND = "#1a1a25"

APP_QSS = f"""
/* Basis */
QWidget {{
    background-color: {FARBE_HINTERGRUND};
    color: {FARBE_TEXT_PRIMÄR};
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
    border: none;
    outline: none;
}}

/* Hauptfenster */
QMainWindow {{
    background-color: {FARBE_HINTERGRUND};
}}

/* Trennlinien */
QFrame[frameShape="4"],
QFrame[frameShape="5"] {{
    color: {FARBE_RAND};
    background-color: {FARBE_RAND};
}}

/* Statusleiste */
QStatusBar {{
    background-color: {FARBE_OBERFLÄCHE};
    color: {FARBE_TEXT_SEKUNDÄR};
    font-size: 11px;
    border-top: 1px solid {FARBE_RAND};
    padding: 2px 8px;
}}

/* Aufnahme-Button */
QPushButton#btn_aufnahme {{
    background-color: {FARBE_AKZENT};
    color: {FARBE_TEXT_PRIMÄR};
    border-radius: 8px;
    padding: 14px 32px;
    font-size: 15px;
    font-weight: 600;
    min-width: 160px;
    min-height: 52px;
    border: none;
}}

QPushButton#btn_aufnahme:hover {{
    background-color: #6d9af8;
}}

QPushButton#btn_aufnahme:pressed {{
    background-color: #4070d0;
}}

QPushButton#btn_aufnahme[recording="true"] {{
    background-color: {FARBE_AUFNAHME_AKTIV};
}}

QPushButton#btn_aufnahme[recording="true"]:hover {{
    background-color: #f06060;
}}

/* Allgemeine Buttons */
QPushButton {{
    background-color: {FARBE_OBERFLÄCHE_HOCH};
    color: {FARBE_TEXT_PRIMÄR};
    border-radius: 5px;
    padding: 6px 14px;
    border: 1px solid {FARBE_RAND};
}}

QPushButton:hover {{
    background-color: #363648;
    border-color: {FARBE_AKZENT};
}}

/* Aufnahmeliste */
QTreeWidget {{
    background-color: {FARBE_OBERFLÄCHE};
    border: 1px solid {FARBE_RAND};
    border-radius: 6px;
    alternate-background-color: {FARBE_OBERFLÄCHE_HOCH};
    show-decoration-selected: 1;
}}

QTreeWidget::item {{
    padding: 4px 6px;
    border-radius: 3px;
}}

QTreeWidget::item:selected {{
    background-color: {FARBE_AKZENT};
    color: white;
}}

QTreeWidget::item:hover {{
    background-color: {FARBE_OBERFLÄCHE_HOCH};
}}

QHeaderView::section {{
    background-color: {FARBE_OBERFLÄCHE};
    color: {FARBE_TEXT_SEKUNDÄR};
    border: none;
    border-bottom: 1px solid {FARBE_RAND};
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* Scroll-Bars */
QScrollBar:vertical {{
    background: {FARBE_OBERFLÄCHE};
    width: 8px;
    border-radius: 4px;
}}

QScrollBar::handle:vertical {{
    background: {FARBE_RAND};
    border-radius: 4px;
    min-height: 20px;
}}

QScrollBar::handle:vertical:hover {{
    background: {FARBE_TEXT_SEKUNDÄR};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
}}

/* Beschriftungen */
QLabel {{
    color: {FARBE_TEXT_PRIMÄR};
    background: transparent;
}}

QLabel[role="überschrift"] {{
    color: {FARBE_TEXT_SEKUNDÄR};
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}

QLabel[role="aufnahme_aktiv"] {{
    color: {FARBE_AUFNAHME_AKTIV};
    font-weight: 600;
}}

/* Quellen-Panel */
QGroupBox {{
    border: 1px solid {FARBE_RAND};
    border-radius: 6px;
    margin-top: 10px;
    padding: 8px;
    color: {FARBE_TEXT_SEKUNDÄR};
    font-size: 10px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: {FARBE_TEXT_SEKUNDÄR};
}}

QLineEdit {{
    background-color: {FARBE_OBERFLÄCHE_HOCH};
    border: 1px solid {FARBE_RAND};
    border-radius: 4px;
    padding: 4px 8px;
    color: {FARBE_TEXT_PRIMÄR};
}}

QLineEdit:focus {{
    border-color: {FARBE_AKZENT};
}}
"""
