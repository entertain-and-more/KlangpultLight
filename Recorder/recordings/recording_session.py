"""recordings.recording_session — Koordiniert Library, AudioEngine, VideoCapture und EventLog.

Kein GUI-Import. Verbindet Aufnahme-Verwaltung mit der Audio-Engine und optionalem Video.

Video-Integration:
  start(title, video_source=<VideoSource>) → startet parallel zur Audioaufnahme einen
  VideoCaptureLoop + VideoRecorder. Bei stop() wird das stumme Video mit dem Audio-Mix
  via mux_audio_video zu program.mp4 zusammengeführt.
  Audio-only-Pfad (video_source=None) bleibt vollständig rückwärtskompatibel.
"""
import logging
import os
from typing import Optional

from core.app_state import AppState
from core.event_log import EventLog
from recordings.library import RecordingLibrary
from recordings.models import RecordingMetadata

_log = logging.getLogger(__name__)


class RecordingSession:
    """Koordiniert RecordingLibrary, AudioEngine, VideoCaptureLoop und EventLog.

    Verwaltet genau eine aktive Aufnahme pro Session-Instanz.
    Die AudioEngine muss bereits gestartet (engine.start() aufgerufen) sein,
    bevor start() aufgerufen wird — sonst werden keine Audio-Frames geschrieben
    und duration=0.

    Limitierung echte Kamera: Eine Kamera kann nicht gleichzeitig von UI-Preview
    und RecordingSession geöffnet werden. UI-Preview muss vor start() gestoppt werden.
    Diese Einschränkung ist bewusst (schlanke Architektur, kein OBS-Multi-Sink).
    Im Mock- und Selftest-Modus ist das kein Problem.
    """

    def __init__(
        self,
        library: RecordingLibrary,
        engine,  # AudioEngine (kein direkter Import → vermeidet zirkuläre Abhängigkeit)
        state: Optional[AppState] = None,
    ) -> None:
        """Initialisiert die RecordingSession.

        Args:
            library: RecordingLibrary für Metadaten-Verwaltung.
            engine: AudioEngine-Instanz (muss bereits gestartet sein).
            state: Optionaler AppState für Zustandssynchronisation.
        """
        self._library = library
        self._engine = engine
        self._state = state
        self._aktuelle_meta: Optional[RecordingMetadata] = None
        self._event_log: Optional[EventLog] = None

        # Video-Capture (optional)
        self._video_capture = None    # VideoCaptureLoop oder MultiSourceCaptureLoop
        self._video_recorder = None   # VideoRecorder-Instanz
        self._video_pfad: Optional[str] = None  # Pfad zur stummen Video-MP4
        self._audio_enabled = True
        self._last_video_duration = 0.0

    def start(
        self,
        title: str,
        video_source=None,
        video_sources: Optional[list] = None,
        audio_enabled: bool = True,
    ) -> RecordingMetadata:
        """Startet eine neue Aufnahme.

        Legt die Aufnahme in der Library an, startet engine.start_recording()
        und protokolliert das start-Event.

        Video-Modi:
          - video_source=<VideoSource>: Einzelquelle (wie bisher, abwärtskompatibel).
          - video_sources=[src, ...]: Mehrere Quellen (≥2) → MultiSourceCaptureLoop +
            Compositor → komponiertes program_video.mp4.
          - video_sources=[src] (1 Element): wie video_source (Single-Source-Pfad).
          - Beide None: Audio-only.
          - audio_enabled=False + Videoquelle: Video-only, ohne AudioEngine-WAV.

        Args:
            title: Titel der Aufnahme.
            video_source: Optionale einzelne VideoSource-Instanz (Einzelquelle).
            video_sources: Optionale Liste von VideoSource-Instanzen (Multi-Quelle).
                           Überschreibt video_source wenn gesetzt und nicht leer.
            audio_enabled: Wenn False, wird keine Audioaufnahme gestartet. Das ist
                           nur mit mindestens einer Videoquelle gültig.

        Returns:
            RecordingMetadata der gestarteten Aufnahme.

        Raises:
            RuntimeError: Wenn bereits eine Aufnahme läuft.
        """
        if self._aktuelle_meta is not None:
            raise RuntimeError("Aufnahme läuft bereits — zuerst stop() aufrufen.")

        quellen_liste: Optional[list] = None
        if video_sources is not None and len(video_sources) > 0:
            quellen_liste = list(video_sources)
        elif video_source is not None:
            quellen_liste = [video_source]

        if not audio_enabled and not quellen_liste:
            raise ValueError("Video-only erfordert mindestens eine Videoquelle.")

        meta = self._library.create_recording(title)

        # EventLog im Aufnahme-Ordner öffnen
        events_pfad = os.path.join(
            self._library.recording_dir(meta.recording_id), "events.jsonl"
        )
        event_log = EventLog(events_pfad)

        # main/-Unterordner anlegen (Audio + Video landen hier)
        main_dir = os.path.join(
            self._library.recording_dir(meta.recording_id), "main"
        )
        os.makedirs(main_dir, exist_ok=True)

        try:
            self._audio_enabled = audio_enabled
            self._last_video_duration = 0.0

            # Audio-Aufnahme starten
            if audio_enabled:
                self._engine.start_recording(main_dir)

            # Video-Aufnahme starten (optional)
            if quellen_liste is not None:
                dateiname = "program_video.mp4" if audio_enabled else "program.mp4"
                self._video_pfad = os.path.join(main_dir, dateiname)
                if len(quellen_liste) >= 2:
                    self._starte_video_multi(quellen_liste, self._video_pfad)
                else:
                    self._starte_video(quellen_liste[0], self._video_pfad)
        except Exception:
            # Partieller Start fehlgeschlagen — Zustand bereinigen damit
            # ein erneuter start()-Aufruf nicht blockiert wird.
            try:
                event_log.close()
            except Exception:
                pass
            self._video_pfad = None
            self._video_capture = None
            self._video_recorder = None
            if audio_enabled:
                try:
                    self._engine.stop_recording()
                except Exception:
                    pass
            raise

        # Erst nach vollständig erfolgreichem Start den Zustand committen.
        self._aktuelle_meta = meta
        self._event_log = event_log

        # Aufnahme-Schutz: Prozess-Priorität anheben, damit konkurrierende
        # Systemlast den Audio-Callback nicht aushungert (Stille-Aussetzer-Schutz).
        if audio_enabled:
            try:
                from core.process_priority import boost_priority
                boost_priority()
            except Exception:
                pass

        # AppState aktualisieren
        if self._state is not None:
            self._state.recording = True

        self._event_log.log("start", title=title, recording_id=meta.recording_id)
        return meta

    def stop(self) -> RecordingMetadata:
        """Beendet die laufende Aufnahme.

        Ruft engine.stop_recording() auf, stoppt ggf. Video-Capture,
        muxed Audio+Video zu program.mp4, schreibt Dauer, audio_path und
        video_path in den Original-Branch, persistiert die Metadaten und
        protokolliert stop.

        Returns:
            Aktualisierte RecordingMetadata.

        Raises:
            RuntimeError: Wenn keine Aufnahme läuft.
        """
        if self._aktuelle_meta is None:
            raise RuntimeError("Keine Aufnahme aktiv — zuerst start() aufrufen.")

        # Audio stoppen
        if self._audio_enabled:
            ergebnis = self._engine.stop_recording()
            dauer = float(ergebnis.get("duration", 0.0))
            mix_pfad = ergebnis.get("mix", "")
        else:
            dauer = 0.0
            mix_pfad = ""

        # Video stoppen und muxen (wenn aktiv)
        program_mp4 = ""
        if self._video_capture is not None or self._video_recorder is not None:
            program_mp4 = self._stoppe_video_und_mux(mix_pfad, dauer)
            if not self._audio_enabled:
                dauer = self._last_video_duration

        # Original-Branch mit Ergebnis aktualisieren
        meta = self._aktuelle_meta
        for branch in meta.branches:
            if branch.is_original:
                branch.audio_path = mix_pfad
                branch.duration = dauer
                if program_mp4:
                    branch.video_path = program_mp4
                break

        meta.duration = dauer
        self._library.update_metadata(meta)

        # Roh-Capture-Diagnose dieses Takes sichern (WASAPI/Treiber vs. App):
        # capture_metrics.json mit Roh-Null-Anteil je Kanal (vor jeder Verarbeitung).
        if self._audio_enabled:
            try:
                import json as _json
                main_dir = os.path.join(
                    self._library.recording_dir(meta.recording_id), "main"
                )
                metrics = self._engine.capture_metrics()
                with open(os.path.join(main_dir, "capture_metrics.json"),
                          "w", encoding="utf-8") as _fh:
                    _json.dump(metrics, _fh, ensure_ascii=False, indent=2)
            except Exception:
                pass

        # Aufnahme-Schutz aufheben (kein Dauer-CPU-Vorrang im Leerlauf).
        try:
            from core.process_priority import restore_priority
            restore_priority()
        except Exception:
            pass

        # AppState aktualisieren
        if self._state is not None:
            self._state.recording = False

        if self._event_log is not None:
            log_kwargs = dict(
                recording_id=meta.recording_id,
                duration=dauer,
                mix=mix_pfad,
            )
            if program_mp4:
                log_kwargs["video"] = program_mp4
            self._event_log.log("stop", **log_kwargs)
            self._event_log.close()
            self._event_log = None

        self._aktuelle_meta = None
        self._audio_enabled = True
        self._last_video_duration = 0.0
        return meta

    # -------------------------------------------------------------------------
    # Video-Interna
    # -------------------------------------------------------------------------

    def _starte_video(self, video_source, video_pfad: str) -> None:
        """Startet VideoCaptureLoop und VideoRecorder für die Aufnahme.

        Dimension aus dem ersten Frame ableiten — nicht aus source.info, da
        echte Kameras von der deklarierten Auflösung abweichen können.
        """
        import shutil
        from video.video_capture_loop import VideoCaptureLoop
        from video.video_recorder import VideoRecorder

        # Quelle kurz öffnen, ersten Frame lesen, Dimensionen bestimmen
        video_source.open()
        erster_frame = video_source.read_frame()
        if erster_frame is None:
            # Fallback auf deklarierte Dimensionen
            w = video_source.info.width
            h = video_source.info.height
        else:
            h, w = erster_frame.shape[:2]
        video_source.close()

        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"
        self._video_recorder = VideoRecorder(width=w, height=h, fps=30, ffmpeg_bin=ffmpeg_bin)
        self._video_recorder.open(video_pfad)

        # Capture-Loop verdrahten: schreibt Frames an Recorder
        def _frame_an_recorder(frame):
            if self._video_recorder is not None:
                try:
                    self._video_recorder.write_frame(frame)
                except (ValueError, RuntimeError):
                    pass  # Shape-Fehler oder Recorder bereits geschlossen

        self._video_capture = VideoCaptureLoop(
            source=video_source,
            ziel_fps=30,
            on_frame=_frame_an_recorder,
        )
        self._video_capture.start()

    def _starte_video_multi(self, quellen: list, video_pfad: str) -> None:
        """Startet MultiSourceCaptureLoop + VideoRecorder für mehrere Quellen.

        Zielauflösung = COMPOSITOR_STANDARD_AUFLOESUNG (1280×720).
        Der Compositor liefert garantiert Frames dieser Größe — VideoRecorder
        wird direkt damit konfiguriert.

        Args:
            quellen: Liste von VideoSource-Instanzen (≥2, noch nicht geöffnet).
            video_pfad: Pfad zur stummen Video-MP4.
        """
        import shutil
        from video.compositor import COMPOSITOR_STANDARD_AUFLOESUNG
        from video.multi_capture_loop import MultiSourceCaptureLoop
        from video.video_recorder import VideoRecorder

        W, H = COMPOSITOR_STANDARD_AUFLOESUNG
        ffmpeg_bin = shutil.which("ffmpeg") or "ffmpeg"

        self._video_recorder = VideoRecorder(width=W, height=H, fps=30, ffmpeg_bin=ffmpeg_bin)
        self._video_recorder.open(video_pfad)

        def _frame_an_recorder(frame):
            if self._video_recorder is not None:
                try:
                    self._video_recorder.write_frame(frame)
                except (ValueError, RuntimeError):
                    pass

        self._video_capture = MultiSourceCaptureLoop(
            sources=quellen,
            out_size=(W, H),
            ziel_fps=30,
            on_frame=_frame_an_recorder,
        )
        self._video_capture.start()

    def _stoppe_video_und_mux(self, mix_pfad: str, audio_dauer: float) -> str:
        """Stoppt Capture-Loop + Recorder und muxed Audio+Video zu program.mp4.

        Returns:
            Pfad zu program.mp4 (leer wenn kein Video oder Fehler).
        """
        from video.video_recorder import mux_audio_video

        # Capture-Loop stoppen
        if self._video_capture is not None:
            try:
                self._video_capture.stop()
            except Exception:
                pass
            self._video_capture = None

        # VideoRecorder schließen
        if self._video_recorder is None:
            return ""

        video_pfad = self._video_pfad or ""
        try:
            self._last_video_duration = float(self._video_recorder.close())
            diagnostics = self._video_recorder.diagnostics
            if diagnostics["frames_dropped"] and self._event_log is not None:
                self._event_log.log("video_frame_drop", **diagnostics)
        except Exception as exc:
            # 2b-Minor: Fehler nicht verschlucken — im EventLog protokollieren,
            # damit ffmpeg-Fehler nicht lautlos verloren gehen.
            if self._event_log is not None:
                self._event_log.log("video_error", fehler=str(exc))
            else:
                # Task 3c Minor: Fallback-Logging wenn kein EventLog vorhanden —
                # Fehler darf niemals still verschluckt werden.
                _log.warning(
                    "VideoRecorder.close() Fehler (kein EventLog vorhanden): %s", exc
                )
        self._video_recorder = None

        if not video_pfad or not os.path.exists(video_pfad):
            return ""
        if not self._audio_enabled:
            self._video_pfad = None
            return video_pfad
        if not mix_pfad or not os.path.exists(mix_pfad):
            return ""

        # Mux zu program.mp4 im gleichen main/-Verzeichnis
        program_mp4 = os.path.join(os.path.dirname(video_pfad), "program.mp4")
        try:
            mux_audio_video(
                video_path=video_pfad,
                audio_path=mix_pfad,
                out_path=program_mp4,
            )
        except Exception as mux_exc:
            # M-3: Mux-Fehler dürfen NICHT lautlos verschwinden (Task 6a).
            # Als Event protokollieren UND via logging ausgeben.
            fehler_msg = str(mux_exc)
            if self._event_log is not None:
                self._event_log.log("video_error", fehler=fehler_msg, phase="mux")
            _log.warning(
                "FFmpeg-Mux fehlgeschlagen — program.mp4 wurde nicht erstellt: %s",
                fehler_msg,
            )
            return ""

        self._video_pfad = None
        return program_mp4
