"""ui.main_window — Hauptfenster des Klangpult light – Recorders (PySide6).

Thread-Modell:
  - Pegel-Updates und Video-Vorschau nur über QTimer (nie direkt aus Audio-/Video-Callbacks).
  - Video-Frames: VideoCaptureLoop schreibt in thread-sicheren Speicher → QTimer liest
    latest_frame() und aktualisiert das Vorschau-Widget.
  - Board-Pad-Highlighting: QTimer pollt BoardPlayer.active_pad_ids() — kein GUI-Aufruf
    aus Feeder-Threads.
DriftMonitor-Anbindung: QTimer ruft observe() auf, Statusleiste zeigt Warnung.
"""
import os
from typing import Optional

import numpy as np
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QGridLayout,
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
    QComboBox,
    QScrollArea,
    QMenu,
    QInputDialog,
)

from audio.device_manager import DeviceManager
from audio.drift_monitor import DriftMonitor
from audio.engine import AudioEngine
from core.app_state import AppState
from core.config import AppConfig
from recordings.library import RecordingLibrary
from recordings.recording_session import RecordingSession
from sources.source_config import SourcesConfig, save_sources_config
from sources.loopback_detector import LoopbackRoute, LOOPBACK_HINT
from ui.level_meter import LevelMeter
from ui.styles import APP_QSS
from video.video_manager import VideoManager
from video.video_source import VideoSourceInfo


class _FloatPanelWindow(QWidget):
    """Frei schwebendes Fenster für ein abgelöstes Panel.

    Schließt der User das Fenster (X), wird das Panel automatisch wieder
    angedockt (redock_callback). Reines GUI, kein Hardware-Zugriff.
    """

    def __init__(self, box, redock_callback, parent=None) -> None:
        super().__init__(parent, Qt.WindowType.Window)
        self._box = box
        self._redock = redock_callback
        lay = QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        box.setParent(self)
        lay.addWidget(box)
        box.show()

    def closeEvent(self, event) -> None:  # noqa: N802 — Qt-Konvention
        try:
            self._redock(self._box)
        finally:
            event.accept()


class MainWindow(QMainWindow):
    """Hauptfenster des Klangpult light – Recorders.

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
        sources_config: Optional[SourcesConfig] = None,
        loopback_route: Optional[LoopbackRoute] = None,
        sources_config_path: Optional[str] = None,
        board_player=None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._config = config
        self._device_manager = device_manager
        self._engine = engine
        self._library = library
        self._state = state
        self._sources_config: Optional[SourcesConfig] = sources_config
        self._loopback_route: Optional[LoopbackRoute] = loopback_route
        self._sources_config_path: Optional[str] = sources_config_path
        self._session: Optional[RecordingSession] = None
        self._aufnahme_läuft = False

        # Board-Player (optional; injiziert von main.py)
        self._board_player = board_player
        # pad_id → QPushButton (Board-Kacheln)
        self._pad_buttons: dict[str, QPushButton] = {}
        # pad_id → Callable (Hotkey-Funktionen, testbar ohne echte QShortcut-Auslösung)
        self._pad_shortcuts: dict[str, object] = {}

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
        self.setWindowTitle("Klangpult light – Recorder")
        self.setMinimumSize(900, 560)
        self.setStyleSheet(APP_QSS)

        # Zentrales Widget
        zentral = QWidget()
        self.setCentralWidget(zentral)
        haupt_layout = QHBoxLayout(zentral)
        haupt_layout.setContentsMargins(12, 12, 12, 12)
        haupt_layout.setSpacing(12)
        self._haupt_layout = haupt_layout
        # Ablösbare Panels: id(box) -> (Float-Fenster, urspruenglicher Index, stretch)
        self._float_panels: dict = {}

        # Alle Panels sind ein-/ausklappbar (Checkbox im Titel) — eingeklappt
        # schrumpfen sie zu einem schmalen Streifen, der frei werdende Platz geht
        # an die Nachbar-Panels (stretch).
        # --- Linkes Panel: Audio-Quellen ---
        haupt_layout.addWidget(self._einklappbar(self._baue_quellen_panel()), stretch=2)

        # --- Mittleres Panel: Aufnahme ---
        haupt_layout.addWidget(self._einklappbar(self._baue_aufnahme_panel()), stretch=3)

        # --- Board-Panel (Einspieler) ---
        self._board_panel = self._einklappbar(self._baue_board_panel())
        haupt_layout.addWidget(self._board_panel, stretch=3)

        # --- Video-Panel ---
        haupt_layout.addWidget(self._einklappbar(self._baue_video_panel()), stretch=3)

        # --- Rechtes Panel: Aufnahmeliste ---
        haupt_layout.addWidget(self._einklappbar(self._baue_aufnahmeliste()), stretch=3)

        # Statusleiste
        self._statusleiste = QStatusBar()
        self.setStatusBar(self._statusleiste)

    def _einklappbar(self, box: "QGroupBox") -> "QGroupBox":
        """Macht ein Panel ein-/ausklappbar: die GroupBox bekommt eine Checkbox im
        Titel. Eingeklappt (unchecked) wird der Inhalt versteckt und das Panel
        schrumpft auf einen schmalen Streifen — der frei werdende Platz geht über
        die Layout-Stretch-Faktoren automatisch an die Nachbar-Panels.

        Offscreen-/Headless-sicher (rein deklarativ, kein Hardware-Zugriff)."""
        if not isinstance(box, QGroupBox):
            return box  # nur QGroupBox-Panels tragen die Collapse-Checkbox
        box.setCheckable(True)
        box.setChecked(True)

        def _toggle(checked: bool, b=box) -> None:
            for w in b.findChildren(QWidget):
                w.setVisible(checked)
            # 40 px = nur noch Titel/Checkbox sichtbar (schmaler Streifen)
            b.setMaximumWidth(16777215 if checked else 40)

        box.toggled.connect(_toggle)

        # Ablös-/Andock-Button (⧉) oben im Panel.
        lay = box.layout()
        if lay is not None:
            panel_titel = (box.title() or "Panel").strip() or "Panel"
            aktion = f'Panel „{panel_titel}“ ablösen'
            detach_btn = QPushButton("⧉")
            detach_btn.setToolTip(f"{aktion} oder wieder andocken")
            detach_btn.setAccessibleName(aktion)
            detach_btn.setAccessibleDescription(
                f'Löst das Panel „{panel_titel}“ in ein eigenes Fenster aus oder dockt es wieder an.'
            )
            detach_btn.setProperty("panel_title", panel_titel)
            detach_btn.setMaximumWidth(30)
            detach_btn.clicked.connect(lambda _checked=False, b=box: self._panel_abloesen(b))
            lay.insertWidget(0, detach_btn)
        return box

    def _panel_abloesen(self, box) -> None:
        """Löst ein Panel in ein eigenes schwebendes Fenster ab — oder dockt es
        wieder an, wenn es bereits schwebt (Toggle)."""
        if id(box) in self._float_panels:
            self._panel_andocken(box)
            return
        haupt = getattr(self, "_haupt_layout", None)
        if haupt is None:
            return
        idx = haupt.indexOf(box)
        if idx < 0:
            return
        stretch = haupt.stretch(idx)
        haupt.removeWidget(box)
        win = _FloatPanelWindow(box, self._panel_andocken, self)
        win.setWindowTitle(box.title() or "Panel")
        win.resize(380, 500)
        self._float_panels[id(box)] = (win, idx, stretch)
        win.show()

    def _panel_andocken(self, box) -> None:
        """Dockt ein zuvor abgelöstes Panel wieder an seiner Ursprungsposition an."""
        state = self._float_panels.pop(id(box), None)
        if state is None:
            return
        win, idx, stretch = state
        wlay = win.layout()
        if wlay is not None:
            wlay.removeWidget(box)
        ziel = min(idx, self._haupt_layout.count())
        box.setParent(None)
        self._haupt_layout.insertWidget(ziel, box, stretch)
        box.show()
        win.hide()
        win.deleteLater()

    def _baue_quellen_panel(self) -> QWidget:
        """Quellen-Panel: Capture-Umschalter je Quelle (SourcesConfig) + LOOPBACK_HINT."""
        box = QGroupBox("Quellen")
        outer_layout = QVBoxLayout(box)
        outer_layout.setSpacing(8)

        geraete = self._device_manager.list_input_devices(verify=True)

        if self._sources_config is not None:
            # --- SourcesConfig-Checkboxen: pro Quelle ein Capture-Umschalter ---
            capture_label = QLabel("Mitschneiden:")
            capture_label.setProperty("role", "überschrift")
            outer_layout.addWidget(capture_label)

            self._capture_checkboxen: dict[str, QCheckBox] = {}
            belegung = self._device_manager.suggest_default_assignment()

            for eintrag in self._sources_config.enabled_sources():
                zeile = QHBoxLayout()

                cb = QCheckBox(eintrag.name)
                cb.setChecked(eintrag.capture)

                # System-Quelle: nur aktivierbar wenn Loopback vorhanden
                if eintrag.kind == "system":
                    if self._loopback_route is not None:
                        methode = self._loopback_route.method
                        gerät_name = self._loopback_route.name
                        cb.setToolTip(f"Loopback: {gerät_name} ({methode})")
                    else:
                        cb.setEnabled(False)
                        cb.setChecked(False)
                        cb.setToolTip("Kein Loopback verfügbar — Checkbox deaktiviert")

                source_id = eintrag.source_id
                cb.toggled.connect(
                    lambda checked, sid=source_id: self._capture_umschalten(sid, checked)
                )
                self._capture_checkboxen[source_id] = cb
                zeile.addWidget(cb)

                # Gebundenes Gerät anzeigen
                if eintrag.kind == "system" and self._loopback_route is not None:
                    gerät_lbl = QLabel(f"  [{self._loopback_route.name}]")
                    gerät_lbl.setProperty("role", "sekundär")
                    zeile.addWidget(gerät_lbl)
                else:
                    combo = QComboBox()
                    combo.setObjectName(f"audio_device_{source_id}")
                    combo.setMinimumWidth(180)
                    combo.addItem("Automatisch", None)
                    for gerät in geraete:
                        if not gerät.verified:
                            continue
                        mock_hint = " (Mock)" if gerät.is_mock else ""
                        combo.addItem(f"{gerät.name}{mock_hint}", gerät.index)

                    vorauswahl = eintrag.device_index
                    if vorauswahl is None:
                        gerät_info = belegung.get(source_id)
                        if gerät_info is not None:
                            vorauswahl = gerät_info.index
                    combo.blockSignals(True)
                    for idx in range(combo.count()):
                        if combo.itemData(idx) == vorauswahl:
                            combo.setCurrentIndex(idx)
                            break
                    combo.blockSignals(False)
                    combo.currentIndexChanged.connect(
                        lambda _idx, sid=source_id, feld=combo: self._audio_geraet_waehlen(
                            sid, feld.currentData()
                        )
                    )
                    zeile.addWidget(combo)

                zeile.addStretch()
                outer_layout.addLayout(zeile)

            # LOOPBACK_HINT — sichtbar wenn kein Loopback vorhanden
            if self._loopback_route is None:
                hint_lbl = QLabel(LOOPBACK_HINT)
                hint_lbl.setWordWrap(True)
                hint_lbl.setProperty("role", "sekundär")
                hint_lbl.setObjectName("loopback_hint")
                outer_layout.addSpacing(4)
                outer_layout.addWidget(hint_lbl)

            outer_layout.addSpacing(8)

        # --- Verfügbare Hardware-Eingänge (Info, immer sichtbar) ---
        trenn = QLabel("Verfügbare Eingänge:")
        trenn.setProperty("role", "überschrift")
        outer_layout.addWidget(trenn)

        if geraete:
            for gerät in geraete:
                mock_hint = " (Mock)" if gerät.is_mock else ""
                verifiziert = " ✓" if gerät.verified else " ✗"
                zeile_lbl = QLabel(f"{gerät.name}{mock_hint}{verifiziert}")
                outer_layout.addWidget(zeile_lbl)
        else:
            outer_layout.addWidget(QLabel("Keine Geräte gefunden"))

        outer_layout.addStretch()
        return box

    def _capture_umschalten(self, source_id: str, checked: bool) -> None:
        """Setzt capture-Flag in SourcesConfig und persistiert wenn Pfad bekannt."""
        if self._sources_config is None:
            return
        self._sources_config.set_capture(source_id, checked)
        if hasattr(self._engine, "set_channel_capture_enabled"):
            self._engine.set_channel_capture_enabled(source_id, checked)
        self._aktualisiere_status()
        self._speichere_sources_config()

    def _audio_geraet_waehlen(self, source_id: str, device_index) -> None:
        """Persistiert die Geräteauswahl einer Quelle."""
        if self._sources_config is None:
            return
        if device_index is not None:
            device_index = int(device_index)
        self._sources_config.set_device_index(source_id, device_index)
        self._speichere_sources_config()
        sofort_angewendet = False
        if not self._aufnahme_läuft and hasattr(self._engine, "set_channel_device_index"):
            sofort_angewendet = bool(
                self._engine.set_channel_device_index(source_id, device_index)
            )
        if getattr(self, "_statusleiste", None) is not None:
            if sofort_angewendet:
                text = "Audioquelle ausgewählt und für die laufende Engine übernommen."
            else:
                text = "Audioquelle gespeichert. Gerätewechsel wirkt nach der laufenden Aufnahme oder beim nächsten Start."
            self._statusleiste.showMessage(text, 5000)

    def _speichere_sources_config(self) -> None:
        """Speichert SourcesConfig, ohne die UI bei Dateifehlern abstürzen zu lassen."""
        if self._sources_config_path is not None:
            try:
                save_sources_config(self._sources_config, self._sources_config_path)
            except Exception:
                pass  # Persist-Fehler darf die UI nicht abstürzen lassen

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

        modus_label = QLabel("Aufnahme-Modus")
        modus_label.setProperty("role", "überschrift")
        layout.addWidget(modus_label)
        self._aufnahme_modus = QComboBox()
        self._aufnahme_modus.setObjectName("aufnahme_modus")
        self._aufnahme_modus.addItem("Ton + Video", "audio_video")
        self._aufnahme_modus.addItem("Nur Ton", "audio_only")
        self._aufnahme_modus.addItem("Nur Video", "video_only")
        self._aufnahme_modus.setToolTip("Wählt, ob Ton, Video oder beides aufgezeichnet wird.")
        self._aufnahme_modus.currentIndexChanged.connect(lambda _idx: self._aktualisiere_status())
        layout.addWidget(self._aufnahme_modus)

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

        # 2b-Minor: Vorschau-Loop für die Default-Quelle direkt beim Aufbau starten,
        # nicht erst beim ersten User-Klick. _starte_vorschau_loop() ist idempotent.
        self._starte_vorschau_loop()

        return box

    def _baue_board_panel(self) -> QWidget:
        """Board-Panel: Pad-Kacheln mit Label, Farbe, Klick-Trigger und Hotkeys 1–8.

        Kein Abspiel-Audio direkt hier — ruft nur BoardPlayer.trigger(pad_id) auf.
        QTimer pollt active_pad_ids() und setzt pad_aktiv-Property für Highlighting.
        Video/Bild-Pads rufen _on_visual_pad() auf (no-op im offscreen-Modus).
        """
        box = QGroupBox("Einspieler")
        layout = QVBoxLayout(box)
        layout.setSpacing(8)

        if self._board_player is None:
            hinweis = QLabel("Kein Board geladen.")
            hinweis.setProperty("role", "sekundär")
            layout.addWidget(hinweis)
            layout.addStretch()
            return box

        # „+ Einspieler"-Button immer sichtbar (auch bei leerem Board).
        add_btn = QPushButton("+ Einspieler hinzufügen")
        add_btn.clicked.connect(self._neues_einspieler_pad)
        layout.addWidget(add_btn)

        # Refreshbarer Container für die Pad-Kacheln.
        self._board_pads_container = QWidget()
        self._board_pads_vbox = QVBoxLayout(self._board_pads_container)
        self._board_pads_vbox.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._board_pads_container)
        layout.addStretch()

        self._fuelle_board_pads()
        return box

    def _fuelle_board_pads(self) -> None:
        """(Re)rendert die Pad-Kacheln in den refreshbaren Container.

        Wird beim Aufbau und nach jedem Hinzufügen/Entfernen aufgerufen.
        Verwaltet Hotkeys sauber (alte QShortcuts entfernen, neue setzen),
        damit ein Refresh keine doppelten Trigger erzeugt."""
        vbox = getattr(self, "_board_pads_vbox", None)
        if vbox is None:
            return
        # Alte Pad-Widgets entfernen
        while vbox.count():
            item = vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._pad_buttons.clear()
        # Alte Hotkey-Objekte entfernen (sonst doppelte Trigger nach Refresh)
        for sc in getattr(self, "_pad_shortcut_objs", []):
            try:
                sc.setParent(None)
                sc.deleteLater()
            except Exception:
                pass
        self._pad_shortcut_objs = []

        board = getattr(self._board_player, "_board", None)
        pads = board.pads if board is not None else []

        if not pads:
            hinweis = QLabel("Noch keine Einspieler — Button oben nutzen, um Pads anzulegen.")
            hinweis.setProperty("role", "sekundär")
            vbox.addWidget(hinweis)
            return

        grid_host = QWidget()
        grid = QGridLayout(grid_host)
        grid.setSpacing(6)
        spalten = 4

        for idx, pad in enumerate(pads):
            zeile = idx // spalten
            spalte = idx % spalten

            btn = QPushButton(pad.label or pad.id)
            btn.setMinimumSize(80, 56)
            btn.setMaximumSize(120, 72)
            farbe = pad.color or "#444444"
            btn.setStyleSheet(
                f"QPushButton {{ background-color: {farbe}; color: #ffffff; "
                f"border: 2px solid transparent; border-radius: 4px; font-weight: bold; }}"
                f"QPushButton[pad_aktiv='true'] {{ border: 2px solid #ffffff; }}"
            )
            btn.setProperty("pad_aktiv", False)
            pad_id = pad.id

            def _mache_trigger(pid=pad_id, p=pad):
                def _on_click():
                    if self._board_player is not None:
                        self._board_player.trigger(pid)
                    if p.kind in ("video", "image"):
                        self._on_visual_pad(p)
                return _on_click

            btn.clicked.connect(_mache_trigger())
            self._pad_buttons[pad_id] = btn
            grid.addWidget(btn, zeile, spalte)

            # Hotkeys 1–8 für die ersten 8 Pads
            if idx < 8:
                shortcut = QShortcut(QKeySequence(str(idx + 1)), self)
                trigger_fn = _mache_trigger()
                shortcut.activated.connect(trigger_fn)
                self._pad_shortcuts[pad_id] = trigger_fn
                self._pad_shortcut_objs.append(shortcut)

        vbox.addWidget(grid_host)

    def _board_pfad(self) -> str:
        """Pfad der Board-Datei (workspace/board.json) — zum Persistieren."""
        import os
        return os.path.join(self._library._workspace, "board.json")

    def _neues_einspieler_pad(self) -> None:
        """Öffnet einen Datei-Dialog und legt daraus ein neues Einspieler-Pad an."""
        from PySide6.QtWidgets import QFileDialog
        pfad, _ = QFileDialog.getOpenFileName(
            self,
            "Einspieler wählen",
            "",
            "Medien (*.wav *.mp3 *.ogg *.flac *.m4a *.mp4 *.mov *.mkv *.avi "
            "*.png *.jpg *.jpeg *.gif *.bmp);;Alle Dateien (*)",
        )
        if pfad:
            self._einspieler_hinzufuegen(pfad)

    def _einspieler_hinzufuegen(self, asset_path: str) -> None:
        """Testbarer Kern: legt aus einer Datei ein Pad an, persistiert + rendert neu.

        Der Pad-Typ wird aus der Dateiendung abgeleitet (audio/video/image)."""
        import os
        import uuid
        from board.board_model import Pad, save_board

        board = getattr(self._board_player, "_board", None)
        if board is None:
            return
        name = os.path.splitext(os.path.basename(asset_path))[0]
        ext = os.path.splitext(asset_path)[1].lower()
        if ext in (".mp4", ".mov", ".mkv", ".avi"):
            kind = "video"
        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".bmp"):
            kind = "image"
        else:
            kind = "audio"
        pad = Pad(
            id=f"pad_{uuid.uuid4().hex[:8]}",
            label=name,
            kind=kind,
            asset_path=asset_path,
        )
        board.add(pad)
        try:
            save_board(board, self._board_pfad())
        except OSError:
            pass  # Persistenz best-effort — UI trotzdem aktualisieren
        self._fuelle_board_pads()

    def _on_visual_pad(self, pad) -> None:
        """Callback für Video/Bild-Pads: zeigt das Asset in der Vorschau-Kachel.

        No-op im offscreen-/Headless-Modus (Kacheln sind nicht sichtbar).
        Wird aus dem GUI-Thread (Klick-Handler oder QTimer) aufgerufen — thread-safe.
        """
        if not self._vorschau_kacheln:
            return
        # Nur Bild-Pads: asset_path als Pixmap laden
        if pad.kind == "image" and pad.asset_path:
            try:
                pixmap = QPixmap(pad.asset_path)
                if not pixmap.isNull():
                    kachel = self._vorschau_kacheln[0]
                    pixmap = pixmap.scaled(
                        kachel.width(),
                        kachel.height(),
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.FastTransformation,
                    )
                    kachel.setPixmap(pixmap)
            except Exception:
                pass  # Vorschau-Fehler darf App nicht abstürzen lassen
        # Video-Pads: no-op (Video läuft über eigene VideoCaptureLoop-Infrastruktur)

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

        # Kontextmenü „Branch anlegen" (M5). Original bleibt unveränderlich —
        # add_branch fügt nur einen neuen Kind-Eintrag hinzu, kein Schnitt.
        self._aufnahme_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._aufnahme_tree.customContextMenuRequested.connect(
            self._zeige_aufnahme_kontextmenu
        )
        # Doppelklick auf eine Aufnahme öffnet sie im externen Standard-Player.
        self._aufnahme_tree.itemDoubleClicked.connect(self._on_aufnahme_doppelklick)

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
        """QTimer-Callback: pollt Peaks, aktualisiert DriftMonitor und Video-Vorschau.

        Pollt außerdem BoardPlayer.active_pad_ids() und aktualisiert das
        pad_aktiv-Property der Pad-Buttons für visuelles Feedback.
        Kein GUI-Aufruf aus Audio-/Feeder-Threads — alles hier im GUI-Thread.
        """
        peaks = self._engine.latest_peaks()
        for i, meter in enumerate(self._pegel_meter):
            pegel = peaks[i] if i < len(peaks) else 0.0
            meter.set_level(pegel)

        # DriftMonitor: öffentliche queue_backlog()-Methode (kein Privatzugriff)
        queue_len = self._engine.queue_backlog()
        self._drift_monitor.observe(queue_len)

        # Board-Pad-Highlighting: aktive Pads hervorheben
        self._aktualisiere_board_highlighting()

        # Video-Vorschau: letzten Frame aus dem Capture-Loop lesen und anzeigen
        self._aktualisiere_video_vorschau()

    def _aktualisiere_board_highlighting(self) -> None:
        """Pollt active_pad_ids() und aktualisiert pad_aktiv-Property der Buttons.

        Nur im GUI-Thread via QTimer aufgerufen — nie aus Feeder-Threads.
        """
        if self._board_player is None or not self._pad_buttons:
            return
        try:
            aktive_ids: set = set(self._board_player.active_pad_ids())
        except Exception:
            return

        for pad_id, btn in self._pad_buttons.items():
            ist_aktiv = pad_id in aktive_ids
            if btn.property("pad_aktiv") != ist_aktiv:
                btn.setProperty("pad_aktiv", ist_aktiv)
                # Style neu anwenden damit [pad_aktiv='true']-Selektor greift
                btn.style().unpolish(btn)
                btn.style().polish(btn)
                btn.update()

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
            # 2b-Minor: C-Contiguität sicherstellen — vermeidet verzerrtes Bild bei
            # nicht-contiguous Slices (z. B. nach Kanal-Umkehrung oder Resize).
            frame_rgb = np.ascontiguousarray(frame_rgb)
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

    def _aufnahme_modus_wert(self) -> str:
        """Gibt den aktuell gewählten Aufnahme-Modus zurück."""
        combo = getattr(self, "_aufnahme_modus", None)
        if combo is None:
            return "audio_video"
        wert = combo.currentData()
        return str(wert or "audio_video")

    def _aktive_audio_source_ids(self) -> list[str]:
        """Liest die aktuell ausgewählten Audioquellen aus SourcesConfig."""
        if self._sources_config is None:
            if hasattr(self._engine, "active_channel_ids"):
                return list(self._engine.active_channel_ids())
            return []
        ids: list[str] = []
        for eintrag in self._sources_config.capture_sources():
            if eintrag.kind != "video":
                ids.append(eintrag.source_id)
        return ids

    def _wende_audio_auswahl_an(self) -> list[str]:
        """Überträgt die UI-Audioauswahl auf die laufende Engine."""
        ids = self._aktive_audio_source_ids()
        if hasattr(self._engine, "set_active_capture_source_ids"):
            self._engine.set_active_capture_source_ids(ids)
            if hasattr(self._engine, "active_channel_ids"):
                return list(self._engine.active_channel_ids())
        return ids

    def _aufnahme_starten(self) -> None:
        """Startet eine neue Aufnahme-Session im gewählten Modus."""
        if self._session is not None:
            return

        titel = self._titel_eingabe.text().strip() or "Aufnahme"
        modus = self._aufnahme_modus_wert()
        audio_enabled = modus in ("audio_video", "audio_only")
        video_enabled = modus in ("audio_video", "video_only")

        if audio_enabled:
            aktive_audio_ids = self._wende_audio_auswahl_an()
            if not aktive_audio_ids:
                self._statusleiste.showMessage(
                    "Keine Audioquelle aktiv — bitte mindestens eine Tonquelle auswählen.",
                    6000,
                )
                return

        # Vorschau-Loop nur stoppen, wenn Video wirklich aufgezeichnet wird.
        # Echte Kamera kann nicht gleichzeitig Preview und Aufnahme bedienen.
        if video_enabled and self._vorschau_loop is not None:
            try:
                self._vorschau_loop.stop()
            except Exception:
                pass
            self._vorschau_loop = None

        # Video-Quellen für die Aufnahme sammeln und als Liste übergeben.
        # Aktuell kann in der UI genau eine Quelle gewählt werden;
        # die Liste ist der Erweiterungspunkt für spätere Mehrfachauswahl.
        video_quellen: list = []
        if video_enabled and self._gewählte_video_quelle is not None:
            try:
                quelle = self._video_manager.open_source(self._gewählte_video_quelle)
                video_quellen.append(quelle)
            except Exception:
                self._statusleiste.showMessage(
                    "Videoquelle konnte nicht geöffnet werden — Aufnahme nicht gestartet.",
                    6000,
                )
                self._starte_vorschau_loop()
                return

        if video_enabled and not video_quellen:
            self._statusleiste.showMessage(
                "Keine Videoquelle aktiv — wähle eine Videoquelle oder den Modus Nur Ton.",
                6000,
            )
            self._starte_vorschau_loop()
            return

        session = RecordingSession(
            library=self._library,
            engine=self._engine,
            state=self._state,
        )
        try:
            if video_quellen:
                session.start(
                    titel,
                    video_sources=video_quellen,
                    audio_enabled=audio_enabled,
                )
            else:
                session.start(titel, audio_enabled=audio_enabled)
        except Exception as exc:
            self._statusleiste.showMessage(f"Aufnahme konnte nicht starten: {exc}", 6000)
            self._starte_vorschau_loop()
            return

        self._session = session
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

    def _ermittle_recording_id(self, item) -> Optional[str]:
        """Ermittelt die recording_id zu einem Tree-Item (auch wenn ein Branch-Kind gewählt ist).

        Branch-Kinder tragen keine recording_id — dann wird das Eltern-Item gelesen.
        """
        if item is None:
            return None
        rid = item.data(0, Qt.ItemDataRole.UserRole)
        if rid:
            return rid
        eltern = item.parent()
        if eltern is not None:
            return eltern.data(0, Qt.ItemDataRole.UserRole)
        return None

    def _zeige_aufnahme_kontextmenu(self, pos) -> None:
        """Kontextmenü auf der Aufnahmeliste: „Branch anlegen".

        Nur im GUI-Thread aufgerufen (Signal customContextMenuRequested).
        """
        item = self._aufnahme_tree.itemAt(pos)
        recording_id = self._ermittle_recording_id(item)
        if not recording_id:
            return

        menu = QMenu(self._aufnahme_tree)
        aktion_abspielen = menu.addAction("Abspielen")
        aktion_umbenennen = menu.addAction("Umbenennen…")
        aktion_branch = menu.addAction("Branch anlegen")
        menu.addSeparator()
        aktion_loeschen = menu.addAction("Löschen…")
        gewaehlt = menu.exec(self._aufnahme_tree.viewport().mapToGlobal(pos))

        if gewaehlt == aktion_branch:
            name, ok = QInputDialog.getText(
                self,
                "Branch anlegen",
                "Name des neuen Branches:",
                text="Neuer Branch",
            )
            if ok:
                final_name = name.strip() or "Neuer Branch"
                self._branch_anlegen(recording_id, final_name)
        elif gewaehlt == aktion_abspielen:
            self._aufnahme_abspielen(recording_id)
        elif gewaehlt == aktion_umbenennen:
            aktuell = next(
                (m.title for m in self._library.list_recordings()
                 if m.recording_id == recording_id),
                "",
            )
            neuer, ok = QInputDialog.getText(
                self, "Aufnahme umbenennen", "Neuer Titel:", text=aktuell
            )
            if ok and neuer.strip():
                self._aufnahme_umbenennen(recording_id, neuer.strip())
        elif gewaehlt == aktion_loeschen:
            from PySide6.QtWidgets import QMessageBox
            antwort = QMessageBox.question(
                self,
                "Aufnahme löschen",
                "Diese Aufnahme endgültig löschen (inkl. Audio/Video)?\n\n"
                f"{recording_id}",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if antwort == QMessageBox.StandardButton.Yes:
                self._aufnahme_loeschen(recording_id)

    def _branch_anlegen(self, recording_id: str, name: str) -> None:
        """Legt einen Branch über die Library an und aktualisiert die Liste.

        Original bleibt unveränderlich (library.add_branch fügt nur ein Kind hinzu).
        Separater, offscreen-testbarer Einstiegspunkt (ohne QMenu/Dialog).
        """
        try:
            self._library.add_branch(recording_id, name)
        except ValueError:
            # Aufnahme nicht gefunden — still ignorieren (Liste ggf. veraltet)
            return
        self._lade_aufnahmeliste()

    def _aufnahme_umbenennen(self, recording_id: str, neuer_titel: str) -> None:
        """Benennt eine Aufnahme um (über die Library) und aktualisiert die Liste.

        Separater, offscreen-testbarer Einstiegspunkt (ohne Dialog)."""
        try:
            self._library.rename_recording(recording_id, neuer_titel)
        except ValueError:
            return
        self._lade_aufnahmeliste()

    def _aufnahme_loeschen(self, recording_id: str) -> None:
        """Löscht eine Aufnahme (über die Library) und aktualisiert die Liste.

        Separater, offscreen-testbarer Einstiegspunkt (ohne Bestätigungsdialog)."""
        try:
            self._library.delete_recording(recording_id)
        except (ValueError, OSError):
            return
        self._lade_aufnahmeliste()

    def _aufnahme_audio_pfad(self, recording_id: str) -> Optional[str]:
        """Pfad zur abspielbaren Datei der Aufnahme (Original: main/mix.wav,
        sonst main/program.mp4). None, wenn nichts (mehr) vorhanden ist."""
        import os
        ordner = self._library.recording_dir(recording_id)
        for rel in (("main", "mix.wav"), ("main", "program.mp4")):
            pfad = os.path.join(ordner, *rel)
            if os.path.isfile(pfad):
                return pfad
        return None

    def _aufnahme_abspielen(self, recording_id: str) -> None:
        """Öffnet die Aufnahme im externen Standard-Player des Systems."""
        pfad = self._aufnahme_audio_pfad(recording_id)
        if not pfad:
            return
        import os
        import sys
        import subprocess
        try:
            if sys.platform == "win32":
                os.startfile(pfad)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", pfad])
            else:
                subprocess.Popen(["xdg-open", pfad])
        except OSError:
            pass  # Kein Player verfügbar — UI nicht blockieren

    def _on_aufnahme_doppelklick(self, item, _spalte: int) -> None:
        """Doppelklick auf eine Aufnahme/einen Branch → externen Player öffnen."""
        recording_id = self._ermittle_recording_id(item)
        if recording_id:
            self._aufnahme_abspielen(recording_id)

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

        modus_text = {
            "audio_video": "Ton + Video",
            "audio_only": "Nur Ton",
            "video_only": "Nur Video",
        }.get(self._aufnahme_modus_wert(), "Ton + Video")
        teile.append(f"Modus: {modus_text}")

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
