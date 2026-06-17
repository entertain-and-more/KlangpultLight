"""main.py — Entrypoint des PodcastRecorders.

Start aus Recorder/ heraus: python main.py
Kein `python -m`, Imports relativ zum Recorder/-Root.

Headless-Selftest:
  PODCAST_RECORDER_SELFTEST=1 + QT_QPA_PLATFORM=offscreen + PODCAST_RECORDER_MOCK_AUDIO=1
  → startet App + MainWindow offscreen, führt eine Probe-Aufnahme durch,
    verifiziert list_recordings() >= 1 mit duration > 0, beendet mit Exit-Code 0.
  → Bei Fehler: Exit-Code 1.
"""
import os
import sys
import time


def _setup_sys_path() -> None:
    """Stellt sicher, dass Recorder/ im sys.path liegt."""
    recorder_root = os.path.dirname(os.path.abspath(__file__))
    if recorder_root not in sys.path:
        sys.path.insert(0, recorder_root)


_setup_sys_path()


def _baue_mock_channels():
    """Baut Mock-MixerChannels für den Fall, dass keine Geräte verfügbar sind."""
    from audio.mixer_channel import MixerChannel
    return [
        MixerChannel(source_id="mic_1", name="Mikrofon 1"),
        MixerChannel(source_id="mic_2", name="Mikrofon 2"),
    ]


def _baue_channels_aus_belegung(belegung: dict):
    """Erzeugt MixerChannels aus der suggest_default_assignment()-Belegung."""
    from audio.mixer_channel import MixerChannel
    channels = []
    rollen = [("mic_1", "Mikrofon 1"), ("mic_2", "Mikrofon 2"), ("system", "System")]
    for rolle, anzeigename in rollen:
        gerät = belegung.get(rolle)
        if gerät is not None:
            channels.append(MixerChannel(source_id=rolle, name=gerät.name))
    # Fallback: mindestens ein Kanal
    if not channels:
        channels = _baue_mock_channels()
    return channels


def main() -> int:
    """Hauptfunktion — gibt Exit-Code zurück."""
    from PySide6.QtWidgets import QApplication

    from audio.device_manager import DeviceManager
    from audio.engine import AudioEngine
    from core.app_state import AppState
    from core.config import AppConfig
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession
    from ui.main_window import MainWindow

    # --- Konfiguration ---
    config = AppConfig(
        workspace_dir=os.path.join(os.path.dirname(os.path.abspath(__file__)), "workspace")
    )

    # --- Geräte ---
    device_manager = DeviceManager()
    belegung = device_manager.suggest_default_assignment()
    channels = _baue_channels_aus_belegung(belegung)

    # --- Engine + State ---
    state = AppState()
    engine = AudioEngine(config, channels, state=state)
    engine.start()

    # --- Bibliothek ---
    library = RecordingLibrary(config.workspace_dir)

    # --- Qt-App ---
    app = QApplication.instance() or QApplication(sys.argv)

    # --- Hauptfenster ---
    fenster = MainWindow(
        config=config,
        device_manager=device_manager,
        engine=engine,
        library=library,
        state=state,
    )

    # --- Headless-Selftest ---
    selftest = os.environ.get("PODCAST_RECORDER_SELFTEST", "").strip() == "1"
    if selftest:
        return _selftest(engine, library, fenster, state)

    # --- Normaler Start ---
    fenster.show()
    return app.exec()


def _selftest(engine, library, fenster, state) -> int:
    """Führt einen Headless-Selftest durch ohne Event-Loop-Blockade.

    Ablauf:
      1. Probe-Aufnahme über RecordingSession (start → Pause → stop)
      2. Verifizierung: list_recordings() >= 1, duration > 0
      3. Engine stoppen, Exit-Code 0 bei Erfolg
    """
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession

    try:
        session = RecordingSession(library=library, engine=engine, state=state)
        session.start("Selftest-Aufnahme")
        # Warten, damit Mock-Thread Frames produziert (mind. ~150 ms)
        time.sleep(0.2)
        meta = session.stop()

        aufnahmen = library.list_recordings()
        if len(aufnahmen) < 1:
            print("SELFTEST FEHLER: Keine Aufnahmen in der Library.", file=sys.stderr)
            engine.stop()
            return 1

        if meta.duration <= 0:
            print(
                f"SELFTEST FEHLER: duration={meta.duration} — keine Frames geschrieben.",
                file=sys.stderr,
            )
            engine.stop()
            return 1

        print(
            f"SELFTEST OK: {len(aufnahmen)} Aufnahme(n), duration={meta.duration:.3f}s"
        )
        engine.stop()
        return 0

    except Exception as e:
        print(f"SELFTEST FEHLER: {e}", file=sys.stderr)
        try:
            engine.stop()
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    sys.exit(main())
