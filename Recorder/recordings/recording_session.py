"""recordings.recording_session — Koordiniert Library, AudioEngine, VideoCapture und EventLog.

Kein GUI-Import. Verbindet Aufnahme-Verwaltung mit der Audio-Engine und optionalem Video.

Video-Integration:
  start(title, video_source=<VideoSource>) → startet parallel zur Audioaufnahme einen
  VideoCaptureLoop + VideoRecorder. Bei stop() wird das stumme Video mit dem Audio-Mix
  via mux_audio_video zu program.mp4 zusammengeführt.
  Audio-only-Pfad (video_source=None) bleibt vollständig rückwärtskompatibel.
"""
import os
from typing import Optional

from core.app_state import AppState
from core.event_log import EventLog
from recordings.library import RecordingLibrary
from recordings.models import RecordingMetadata


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
        self._video_capture = None    # VideoCaptureLoop-Instanz
        self._video_recorder = None   # VideoRecorder-Instanz
        self._video_pfad: Optional[str] = None  # Pfad zur stummen Video-MP4

    def start(self, title: str, video_source=None) -> RecordingMetadata:
        """Startet eine neue Aufnahme.

        Legt die Aufnahme in der Library an, startet engine.start_recording()
        und protokolliert das start-Event. Mit video_source wird zusätzlich
        ein VideoCaptureLoop + VideoRecorder gestartet.

        Args:
            title: Titel der Aufnahme.
            video_source: Optionale VideoSource-Instanz. Wenn angegeben, wird parallel
                          zum Audio ein stummes Video in main/program_video.mp4 aufgezeichnet.
                          Die Quelle darf noch nicht geöffnet sein — start() öffnet sie.

        Returns:
            RecordingMetadata der gestarteten Aufnahme.

        Raises:
            RuntimeError: Wenn bereits eine Aufnahme läuft.
        """
        if self._aktuelle_meta is not None:
            raise RuntimeError("Aufnahme läuft bereits — zuerst stop() aufrufen.")

        meta = self._library.create_recording(title)
        self._aktuelle_meta = meta

        # EventLog im Aufnahme-Ordner öffnen
        events_pfad = os.path.join(
            self._library.recording_dir(meta.recording_id), "events.jsonl"
        )
        self._event_log = EventLog(events_pfad)

        # main/-Unterordner anlegen (Audio + Video landen hier)
        main_dir = os.path.join(
            self._library.recording_dir(meta.recording_id), "main"
        )
        os.makedirs(main_dir, exist_ok=True)

        # Audio-Aufnahme starten
        self._engine.start_recording(main_dir)

        # Video-Aufnahme starten (optional)
        if video_source is not None:
            self._video_pfad = os.path.join(main_dir, "program_video.mp4")
            self._starte_video(video_source, self._video_pfad)

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
        ergebnis = self._engine.stop_recording()
        dauer = float(ergebnis.get("duration", 0.0))
        mix_pfad = ergebnis.get("mix", "")

        # Video stoppen und muxen (wenn aktiv)
        program_mp4 = ""
        if self._video_capture is not None or self._video_recorder is not None:
            program_mp4 = self._stoppe_video_und_mux(mix_pfad, dauer)

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
            self._video_recorder.close()
        except Exception:
            pass
        self._video_recorder = None

        if not video_pfad or not os.path.exists(video_pfad):
            return ""
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
        except Exception:
            return ""

        self._video_pfad = None
        return program_mp4
