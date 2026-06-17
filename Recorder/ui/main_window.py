"""ui.main_window — Hauptfenster des PodcastRecorders (PySide6).

Thread-Modell: Pegel-Updates nur über QTimer (nie direkt aus Audio-Callbacks).
DriftMonitor-Anbindung: QTimer ruft observe() auf, Statusleiste zeigt Warnung.
"""
import os
from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QLineEdit,
    QFormLayout,
)

from audio.device_manager import DeviceManager
from audio.drift_monitor import DriftMonitor
from audio.engine import AudioEngine
from core.app_state import AppState
from core.config import AppConfig
from recordings.library import RecordingLibrary
from recordings.recording_session import RecordingSession
from ui.level_meter import LevelMeter
from ui.styles import APP_QSS


class MainWindow(QMainWindow):
    """Hauptfenster des PodcastRecorders.

    Layout (schlank):
      Links  — Quellen-Panel (verifizierte Geräte + Default-Belegung)
      Mitte  — Aufnahme-/Stop-Button + LevelMeter je Kanal
      Rechts — Aufnahmeliste (QTreeWidget: Aufnahme → Branches)
    Statusleiste zeigt Mock-Hinweis, Quellenanzahl und Drift-Warnung.
    """

    _TIMER_INTERVAL_MS = 40  # ~25 Hz Pegel-Update

    def __init__(
        self,
        config: AppConfig,
        device_manager: DeviceManager,
        engine: AudioEngine,
        library: RecordingLibrary,
        state: AppState,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._device_manager = device_manager
        self._engine = engine
        self._library = library
        self._state = state
        self._session: Optional[RecordingSession] = None
        self._aufnahme_läuft = False

        # DriftMonitor verdrahten
        self._drift_monitor = DriftMonitor(warn_threshold=8)
        self._drift_warnung = False
        self._drift_monitor.on_warning = self._bei_drift_warnung

        self._setup_ui()
        self._setup_timer()
        self._aktualisiere_status()
        self._lade_aufnahmeliste()

    # -------------------------------------------------------------------------
    # UI-Aufbau
    # -------------------------------------------------------------------------

    def _setup_ui(self) -> None:
        self.setWindowTitle("PodcastRecorder")
        self.setMinimumSize(900, 560)
        self.setStyleSheet(APP_QSS)

        # Zentrales Widget
        zentral = QWidget()
        self.setCentralWidget(zentral)
        haupt_layout = QHBoxLayout(zentral)
        haupt_layout.setContentsMargins(12, 12, 12, 12)
        haupt_layout.setSpacing(12)

        # --- Linkes Panel: Quellen ---
        haupt_layout.addWidget(self._baue_quellen_panel(), stretch=2)

        # --- Mittleres Panel: Aufnahme ---
        haupt_layout.addWidget(self._baue_aufnahme_panel(), stretch=3)

        # --- Rechtes Panel: Aufnahmeliste ---
        haupt_layout.addWidget(self._baue_aufnahmeliste(), stretch=3)

        # Statusleiste
        self._statusleiste = QStatusBar()
        self.setStatusBar(self._statusleiste)

    def _baue_quellen_panel(self) -> QWidget:
        """Quellen-Panel: zeigt verifizierte Geräte und Default-Belegung."""
        box = QGroupBox("Quellen")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        geraete = self._device_manager.list_input_devices(verify=True)
        belegung = self._device_manager.suggest_default_assignment()

        beschriftung = QLabel("Automatisch belegte Eingänge:")
        beschriftung.setProperty("role", "überschrift")
        layout.addWidget(beschriftung)

        form = QFormLayout()
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        form.setSpacing(6)

        for rolle, gerät in belegung.items():
            if gerät is not None:
                wert = QLabel(gerät.name)
            else:
                wert = QLabel("– nicht belegt –")
                wert.setProperty("role", "sekundär")
            form.addRow(QLabel(f"{rolle}:"), wert)

        layout.addLayout(form)
        layout.addSpacing(8)

        trenn = QLabel("Verfügbare Eingänge:")
        trenn.setProperty("role", "überschrift")
        layout.addWidget(trenn)

        if geraete:
            for gerät in geraete:
                mock_hint = " (Mock)" if gerät.is_mock else ""
                verifiziert = " ✓" if gerät.verified else " ✗"
                zeile = QLabel(f"{gerät.name}{mock_hint}{verifiziert}")
                layout.addWidget(zeile)
        else:
            layout.addWidget(QLabel("Keine Geräte gefunden"))

        layout.addStretch()
        return box

    def _baue_aufnahme_panel(self) -> QWidget:
        """Mittelpanel mit Titel-Eingabe, Aufnahme-Button und Pegelmetern."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        layout.setSpacing(16)
        layout.setContentsMargins(8, 8, 8, 8)

        # Titel-Eingabe
        titel_label = QLabel("Titel")
        titel_label.setProperty("role", "überschrift")
        layout.addWidget(titel_label)
        self._titel_eingabe = QLineEdit()
        self._titel_eingabe.setPlaceholderText("Aufnahmetitel …")
        layout.addWidget(self._titel_eingabe)

        layout.addSpacing(12)

        # Aufnahme-Button
        self._btn_aufnahme = QPushButton("Aufnahme starten")
        self._btn_aufnahme.setObjectName("btn_aufnahme")
        self._btn_aufnahme.setCheckable(False)
        self._btn_aufnahme.clicked.connect(self._aufnahme_umschalten)
        layout.addWidget(self._btn_aufnahme, alignment=Qt.AlignmentFlag.AlignHCenter)

        layout.addSpacing(16)

        # Pegelanzeigen je Kanal
        pegel_label = QLabel("Pegel")
        pegel_label.setProperty("role", "überschrift")
        layout.addWidget(pegel_label)

        self._pegel_meter: list[LevelMeter] = []
        # Kanalanzahl aus Engine-Channels ableiten (gleich der channels-Liste der Engine)
        anzahl_kanäle = max(1, self._config.channels)
        for i in range(anzahl_kanäle):
            zeile = QHBoxLayout()
            lbl = QLabel(f"K{i + 1}")
            lbl.setFixedWidth(22)
            meter = LevelMeter()
            self._pegel_meter.append(meter)
            zeile.addWidget(lbl)
            zeile.addWidget(meter)
            layout.addLayout(zeile)

        layout.addStretch()
        return container

    def _baue_aufnahmeliste(self) -> QWidget:
        """Rechtes Panel mit Aufnahme-TreeWidget."""
        box = QGroupBox("Aufnahmen")
        layout = QVBoxLayout(box)

        self._aufnahme_tree = QTreeWidget()
        self._aufnahme_tree.setHeaderLabels(["Titel", "Dauer", "Erstellt"])
        self._aufnahme_tree.setColumnWidth(0, 180)
        self._aufnahme_tree.setColumnWidth(1, 70)
        self._aufnahme_tree.setAlternatingRowColors(True)
        self._aufnahme_tree.setRootIsDecorated(True)
        layout.addWidget(self._aufnahme_tree)

        return box

    # -------------------------------------------------------------------------
    # Timer / Pegel-Polling
    # -------------------------------------------------------------------------

    def _setup_timer(self) -> None:
        self._timer = QTimer(self)
        self._timer.setInterval(self._TIMER_INTERVAL_MS)
        self._timer.timeout.connect(self._timer_tick)
        self._timer.start()

    def _timer_tick(self) -> None:
        """QTimer-Callback: pollt Peaks und aktualisiert DriftMonitor."""
        peaks = self._engine.latest_peaks()
        for i, meter in enumerate(self._pegel_meter):
            pegel = peaks[i] if i < len(peaks) else 0.0
            meter.set_level(pegel)

        # DriftMonitor: deque-Länge als Proxy für Queue-Größe
        queue_len = len(self._engine._peak_deque)
        self._drift_monitor.observe(queue_len)

    # -------------------------------------------------------------------------
    # Aufnahme-Logik
    # -------------------------------------------------------------------------

    def _aufnahme_umschalten(self) -> None:
        """Startet oder stoppt die Aufnahme."""
        if self._aufnahme_läuft:
            self._aufnahme_stoppen()
        else:
            self._aufnahme_starten()

    def _aufnahme_starten(self) -> None:
        """Startet eine neue Aufnahme-Session."""
        if self._session is not None:
            return

        titel = self._titel_eingabe.text().strip() or "Aufnahme"
        self._session = RecordingSession(
            library=self._library,
            engine=self._engine,
            state=self._state,
        )
        self._session.start(titel)
        self._aufnahme_läuft = True
        self._btn_aufnahme.setText("Aufnahme stoppen")
        self._btn_aufnahme.setProperty("recording", "true")
        self._btn_aufnahme.style().unpolish(self._btn_aufnahme)
        self._btn_aufnahme.style().polish(self._btn_aufnahme)
        self._aktualisiere_status()

    def _aufnahme_stoppen(self) -> None:
        """Beendet die laufende Aufnahme und aktualisiert die Liste."""
        if self._session is None:
            return

        self._session.stop()
        self._session = None
        self._aufnahme_läuft = False
        self._btn_aufnahme.setText("Aufnahme starten")
        self._btn_aufnahme.setProperty("recording", "false")
        self._btn_aufnahme.style().unpolish(self._btn_aufnahme)
        self._btn_aufnahme.style().polish(self._btn_aufnahme)
        self._aktualisiere_status()
        self._lade_aufnahmeliste()

    # -------------------------------------------------------------------------
    # Aufnahmeliste
    # -------------------------------------------------------------------------

    def _lade_aufnahmeliste(self) -> None:
        """Liest alle Aufnahmen aus der Library und zeigt sie im Tree."""
        self._aufnahme_tree.clear()
        aufnahmen = self._library.list_recordings()

        for meta in aufnahmen:
            dauer_str = self._formatiere_dauer(meta.duration)
            datum_str = meta.created_at[:16].replace("T", " ") if meta.created_at else ""
            root_item = QTreeWidgetItem([meta.title, dauer_str, datum_str])
            root_item.setData(0, Qt.ItemDataRole.UserRole, meta.recording_id)

            # Branches als Kinder
            for branch in meta.branches:
                branch_dauer = self._formatiere_dauer(branch.duration)
                marker = " (Original)" if branch.is_original else ""
                b_item = QTreeWidgetItem(
                    [f"{branch.name}{marker}", branch_dauer, ""]
                )
                root_item.addChild(b_item)

            self._aufnahme_tree.addTopLevelItem(root_item)
            root_item.setExpanded(True)

    @staticmethod
    def _formatiere_dauer(sekunden: float) -> str:
        """Formatiert Sekunden als mm:ss."""
        if sekunden <= 0:
            return "–"
        minuten = int(sekunden) // 60
        sek = int(sekunden) % 60
        return f"{minuten}:{sek:02d}"

    # -------------------------------------------------------------------------
    # Statusleiste
    # -------------------------------------------------------------------------

    def _aktualisiere_status(self) -> None:
        """Aktualisiert die Statuszeile mit aktuellem Systemzustand."""
        teile = []

        # Mock-Hinweis
        if os.environ.get("PODCAST_RECORDER_MOCK_AUDIO", "").strip() == "1" or self._config.mock_audio:
            teile.append("Mock-Audio aktiv")

        # Anzahl verifizierter Quellen
        geraete = self._device_manager.list_input_devices(verify=False)
        verifiziert = sum(1 for g in geraete if g.verified)
        teile.append(f"{verifiziert} verifizierte Quelle{'n' if verifiziert != 1 else ''}")

        # Aufnahme-Status
        if self._aufnahme_läuft:
            teile.append("● Aufnahme läuft")

        # Drift-Warnung
        if self._drift_warnung:
            teile.append("⚠ Audio-Drift erkannt")

        self._statusleiste.showMessage("   |   ".join(teile))

    def _bei_drift_warnung(self) -> None:
        """Callback des DriftMonitors — im GUI-Thread sicher, da über QTimer."""
        self._drift_warnung = True
        self._aktualisiere_status()

    # -------------------------------------------------------------------------
    # Aufräumen
    # -------------------------------------------------------------------------

    def closeEvent(self, event) -> None:  # noqa: N802
        """Räumt Engine und Timer beim Schließen auf."""
        self._timer.stop()
        if self._aufnahme_läuft and self._session is not None:
            self._session.stop()
        self._engine.stop()
        super().closeEvent(event)
