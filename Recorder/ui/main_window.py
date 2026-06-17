"""ui.main_window — Hauptfenster des PodcastRecorders (PySide6).

Thread-Modell:
  - Pegel-Updates und Video-Vorschau nur über QTimer (nie direkt aus Audio-/Video-Callbacks).
  - Video-Frames: VideoCaptureLoop schreibt in thread-sicheren Speicher → QTimer liest
    latest_frame() und aktualisiert das Vorschau-Widget.
DriftMonitor-Anbindung: QTimer ruft observe() auf, Statusleiste zeigt Warnung.
"""
import os
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QPixmap
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
    QListWidget,
    QListWidgetItem,
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
from video.video_manager import VideoManager
from video.video_source import VideoSourceInfo


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

        # Video-Manager + verfügbare Quellen
        self._video_manager = VideoManager()
        self._video_quellen: list[VideoSourceInfo] = self._video_manager.available_sources()
        self._gewählte_video_quelle: Optional[VideoSourceInfo] = (
            self._video_manager.suggest_default_source()
        )
        # Vorschau-Capture-Loop (nur für UI-Preview, nicht für Aufnahme)
        self._vorschau_loop = None  # VideoCaptureLoop-Instanz oder None

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

        # --- Linkes Panel: Audio-Quellen ---
        haupt_layout.addWidget(self._baue_quellen_panel(), stretch=2)

        # --- Mittleres Panel: Aufnahme ---
        haupt_layout.addWidget(self._baue_aufnahme_panel(), stretch=3)

        # --- Video-Panel ---
        haupt_layout.addWidget(self._baue_video_panel(), stretch=3)

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
        # Kanalanzahl aus tatsächlichen Engine-Channels ableiten (nicht config.channels!)
        anzahl_kanäle = max(1, self._engine.channel_count())
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

    def _baue_video_panel(self) -> QWidget:
        """Video-Panel: Quellauswahl + Live-Vorschau (bis zu 4 Quellen als Kacheln)."""
        box = QGroupBox("Video")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        # Quell-Liste
        beschriftung = QLabel("Video-Quellen:")
        beschriftung.setProperty("role", "überschrift")
        layout.addWidget(beschriftung)

        self._video_quelle_liste = QListWidget()
        self._video_quelle_liste.setMaximumHeight(100)
        for info in self._video_quellen:
            mock_hint = " (Mock)" if info.is_mock else ""
            verifiziert = " ✓" if info.verified else ""
            item = QListWidgetItem(f"{info.name}{mock_hint}{verifiziert}")
            item.setData(Qt.ItemDataRole.UserRole, info.source_id)
            self._video_quelle_liste.addItem(item)

        # Default-Auswahl vormarkieren
        if self._gewählte_video_quelle is not None:
            for i in range(self._video_quelle_liste.count()):
                item = self._video_quelle_liste.item(i)
                if item and item.data(Qt.ItemDataRole.UserRole) == self._gewählte_video_quelle.source_id:
                    self._video_quelle_liste.setCurrentRow(i)
                    break

        self._video_quelle_liste.currentItemChanged.connect(self._bei_video_auswahl)
        layout.addWidget(self._video_quelle_liste)

        # Vorschau-Kacheln (bis zu 4 Quellen — einfaches Kachel-Layout)
        vorschau_label = QLabel("Vorschau:")
        vorschau_label.setProperty("role", "überschrift")
        layout.addWidget(vorschau_label)

        # Kachel-Grid: 2×2 für bis zu 4 Quellen (aktuell: 1 Vorschau-Label für Default)
        self._vorschau_kacheln: list[QLabel] = []
        kachel_layout = QHBoxLayout()
        anzahl_kacheln = min(4, max(1, len(self._video_quellen)))
        for _ in range(anzahl_kacheln):
            kachel = QLabel("–")
            kachel.setAlignment(Qt.AlignmentFlag.AlignCenter)
            kachel.setMinimumSize(120, 90)
            kachel.setStyleSheet("background: #1a1a1a; color: #555; border: 1px solid #333;")
            kachel.setScaledContents(False)
            self._vorschau_kacheln.append(kachel)
            kachel_layout.addWidget(kachel)
        layout.addLayout(kachel_layout)

        layout.addStretch()
        return box

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
        """QTimer-Callback: pollt Peaks, aktualisiert DriftMonitor und Video-Vorschau."""
        peaks = self._engine.latest_peaks()
        for i, meter in enumerate(self._pegel_meter):
            pegel = peaks[i] if i < len(peaks) else 0.0
            meter.set_level(pegel)

        # DriftMonitor: öffentliche queue_backlog()-Methode (kein Privatzugriff)
        queue_len = self._engine.queue_backlog()
        self._drift_monitor.observe(queue_len)

        # Video-Vorschau: letzten Frame aus dem Capture-Loop lesen und anzeigen
        self._aktualisiere_video_vorschau()

    def _aktualisiere_video_vorschau(self) -> None:
        """Liest letzten Frame aus dem Vorschau-Loop und zeigt ihn in der ersten Kachel.

        No-op im Offscreen-/Selftest-Modus (Kacheln sind nicht sichtbar).
        Kein GUI-Aufruf aus dem Capture-Thread — nur aus QTimer im GUI-Thread.
        """
        if not self._vorschau_kacheln:
            return

        if self._vorschau_loop is None:
            return

        frame = self._vorschau_loop.latest_frame()
        if frame is None:
            return

        # BGR → RGB (QImage erwartet RGB)
        try:
            frame_rgb = frame[:, :, ::-1].astype(np.uint8)
            h, w, ch = frame_rgb.shape
            bytes_per_line = ch * w
            qimg = QImage(frame_rgb.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
            pixmap = QPixmap.fromImage(qimg)
            kachel = self._vorschau_kacheln[0]
            pixmap = pixmap.scaled(
                kachel.width(),
                kachel.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            kachel.setPixmap(pixmap)
        except Exception:
            pass  # Vorschau-Fehler darf die App nicht abstürzen lassen

    def _bei_video_auswahl(self, aktuell, _vorher) -> None:
        """Callback: Video-Quelle wurde in der Liste gewählt."""
        if aktuell is None:
            return
        source_id = aktuell.data(Qt.ItemDataRole.UserRole)
        # Gewählte Quelle aus der Liste suchen
        for info in self._video_quellen:
            if info.source_id == source_id:
                self._gewählte_video_quelle = info
                self._starte_vorschau_loop()
                self._aktualisiere_status()
                break

    def _starte_vorschau_loop(self) -> None:
        """Startet (oder neustartet) den Vorschau-Capture-Loop für die gewählte Quelle."""
        # Alten Loop stoppen
        if self._vorschau_loop is not None:
            try:
                self._vorschau_loop.stop()
            except Exception:
                pass
            self._vorschau_loop = None

        if self._gewählte_video_quelle is None:
            return

        # Während einer laufenden Aufnahme keine Preview-Quelle öffnen
        # (echte Kamera kann nicht doppelt geöffnet werden)
        if self._aufnahme_läuft:
            return

        try:
            from video.video_capture_loop import VideoCaptureLoop
            source = self._video_manager.open_source(self._gewählte_video_quelle)
            self._vorschau_loop = VideoCaptureLoop(source=source, ziel_fps=25)
            self._vorschau_loop.start()
        except Exception:
            self._vorschau_loop = None

    # -------------------------------------------------------------------------
    # Aufnahme-Logik
    # -------------------------------------------------------------------------

    def _aufnahme_umschalten(self) -> None:
        """Startet oder stoppt die Aufnahme — Doppelklick-Schutz via Button-Disable."""
        # Während des Umschaltens deaktivieren, um Doppelklick-Probleme zu vermeiden
        self._btn_aufnahme.setEnabled(False)
        try:
            if self._aufnahme_läuft:
                self._aufnahme_stoppen()
            else:
                self._aufnahme_starten()
        finally:
            self._btn_aufnahme.setEnabled(True)

    def _aufnahme_starten(self) -> None:
        """Startet eine neue Aufnahme-Session mit optionalem Video."""
        if self._session is not None:
            return

        titel = self._titel_eingabe.text().strip() or "Aufnahme"
        self._session = RecordingSession(
            library=self._library,
            engine=self._engine,
            state=self._state,
        )

        # Vorschau-Loop stoppen — echte Kamera kann nicht doppelt geöffnet werden
        if self._vorschau_loop is not None:
            try:
                self._vorschau_loop.stop()
            except Exception:
                pass
            self._vorschau_loop = None

        # Video-Quelle für die Aufnahme öffnen (wenn gewählt)
        video_source = None
        if self._gewählte_video_quelle is not None:
            try:
                video_source = self._video_manager.open_source(self._gewählte_video_quelle)
            except Exception:
                video_source = None

        self._session.start(titel, video_source=video_source)
        self._aufnahme_läuft = True
        self._btn_aufnahme.setText("Aufnahme stoppen")
        self._btn_aufnahme.setProperty("recording", "true")
        self._btn_aufnahme.style().unpolish(self._btn_aufnahme)
        self._btn_aufnahme.style().polish(self._btn_aufnahme)
        self._aktualisiere_status()

    def _aufnahme_stoppen(self) -> None:
        """Beendet die laufende Aufnahme, aktualisiert die Liste und startet Preview neu."""
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

        # Vorschau-Loop nach der Aufnahme wieder starten
        self._starte_vorschau_loop()

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

        # Mock-Hinweis Audio
        if os.environ.get("PODCAST_RECORDER_MOCK_AUDIO", "").strip() == "1" or self._config.mock_audio:
            teile.append("Mock-Audio aktiv")

        # Mock-Hinweis Video — ehrliche Anzeige gemäß Faktentreue-Regel
        if os.environ.get("PODCAST_RECORDER_MOCK_VIDEO", "").strip() == "1":
            teile.append("Mock-Video aktiv")
        elif self._gewählte_video_quelle is not None:
            if self._gewählte_video_quelle.is_mock:
                teile.append("keine Kamera verifiziert — Bildschirm/Mock")
            else:
                teile.append(f"Video: {self._gewählte_video_quelle.name}")

        # Anzahl verifizierter Audio-Quellen
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
        """Räumt Engine, Video-Capture-Loops und Timer beim Schließen auf."""
        self._timer.stop()

        # Vorschau-Loop stoppen
        if self._vorschau_loop is not None:
            try:
                self._vorschau_loop.stop()
            except Exception:
                pass
            self._vorschau_loop = None

        if self._aufnahme_läuft and self._session is not None:
            try:
                self._session.stop()
            except Exception:
                pass  # Aufnahme-Stop darf das Schließen nicht blockieren

        # Engine nur stoppen wenn sie läuft (Guard verhindert doppelten Aufruf)
        if self._engine.is_running():
            self._engine.stop()

        super().closeEvent(event)
