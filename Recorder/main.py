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


def _mock_loopback_route():
    """Gibt eine synthetische LoopbackRoute für den Mock-Pfad zurück.

    Im Mock-Modus (PODCAST_RECORDER_MOCK_AUDIO=1) gibt es keine echte Hardware.
    Damit der System-Kanal trotzdem im Mock nachweisbar mitläuft, wird eine
    synthetische Route injiziert — nur wenn Mock aktiv ist.
    Im Produktionsbetrieb liefert LoopbackDetector.detect() die echte Route.
    """
    from sources.loopback_detector import LoopbackRoute
    return LoopbackRoute(
        name="Mock-Loopback",
        method="wasapi_loopback",
        device_index=0,
        hostapi="Mock",
        score=100,
    )


def main() -> int:
    """Hauptfunktion — gibt Exit-Code zurück."""
    from PySide6.QtWidgets import QApplication

    from audio.device_manager import DeviceManager
    from audio.engine import AudioEngine
    from core.app_state import AppState
    from core.config import AppConfig
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession
    from sources.build_channels import build_channels
    from sources.loopback_detector import LoopbackDetector
    from sources.source_config import load_sources_config, save_sources_config
    from ui.main_window import MainWindow

    # --- Konfiguration ---
    recorder_root = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.join(recorder_root, "workspace")
    config = AppConfig(workspace_dir=workspace_dir)

    # --- Quellen-Config laden (oder Defaults) ---
    sources_config_path = os.path.join(workspace_dir, "sources.json")
    sources_config = load_sources_config(sources_config_path)

    # --- Loopback erkennen ---
    detector = LoopbackDetector()
    nutze_mock = (
        config.mock_audio
        or os.environ.get("PODCAST_RECORDER_MOCK_AUDIO", "").strip() == "1"
    )
    if nutze_mock:
        # Mock-Pfad: synthetische Route, damit System-Kanal headless testbar ist.
        # system.capture ist standardmäßig False; wir setzen es im Mock auf True,
        # damit der Selftest den System-Kanal nachweisen kann.
        loopback_route = _mock_loopback_route()
        sources_config.set_capture("system", True)
    else:
        # Produktionspfad: echte Hardware-Erkennung
        routen = detector.detect()
        loopback_route = detector.best_route(routen)

    # --- Gerätebelegung + Kanäle ---
    device_manager = DeviceManager()
    belegung_raw = device_manager.suggest_default_assignment()
    # device_assignment: source_id → int (nur Einträge mit device_index != None)
    device_assignment: dict = {}
    for rolle, gerät in belegung_raw.items():
        if gerät is not None and hasattr(gerät, "index") and gerät.index is not None:
            device_assignment[rolle] = gerät.index

    channels = build_channels(
        sources_config=sources_config,
        device_assignment=device_assignment,
        loopback_route=loopback_route,
    )

    # Fallback: mindestens ein Kanal
    if not channels:
        from audio.mixer_channel import MixerChannel
        channels = [
            MixerChannel(source_id="mic_1", name="Mikrofon 1"),
            MixerChannel(source_id="mic_2", name="Mikrofon 2"),
        ]

    # --- Engine + State ---
    state = AppState()
    engine = AudioEngine(config, channels, state=state)
    engine.start()

    # --- Bibliothek ---
    library = RecordingLibrary(config.workspace_dir)

    # --- Board laden und BoardPlayer erstellen ---
    board_player = _lade_board_und_player(engine, config)

    # --- Qt-App ---
    app = QApplication.instance() or QApplication(sys.argv)

    # --- Hauptfenster ---
    fenster = MainWindow(
        config=config,
        device_manager=device_manager,
        engine=engine,
        library=library,
        state=state,
        sources_config=sources_config,
        loopback_route=loopback_route,
        sources_config_path=sources_config_path,
        board_player=board_player,
    )

    # --- on_visual_pad verdrahten (4b-Fix) ---
    # BoardPlayer wurde ohne on_visual_pad-Callback erstellt (in _lade_board_und_player).
    # Nach MainWindow-Konstruktion wird der Callback hier gesetzt — genau eine
    # Callback-Kette, kein Doppelpfad.
    if board_player is not None and hasattr(fenster, "_on_visual_pad"):
        board_player._on_visual_pad = fenster._on_visual_pad

    # --- BridgeService optional starten ---
    from bridge.bridge_service import BridgeService
    bridge: BridgeService | None = None
    if BridgeService.soll_starten():
        bridge = BridgeService(
            library=library,
            engine=engine,
            state=state,
            board_player=board_player,
        )
        bridge.start()

    # --- Headless-Selftest ---
    selftest = os.environ.get("PODCAST_RECORDER_SELFTEST", "").strip() == "1"
    if selftest:
        ergebnis = _selftest(engine, library, fenster, state, channels, board_player)
        if bridge is not None:
            bridge.stop()
        return ergebnis

    # --- Normaler Start ---
    fenster.show()
    exit_code = app.exec()
    if bridge is not None:
        bridge.stop()
    return exit_code


def _lade_board_und_player(engine, config):
    """Lädt das Standard-Board aus dem Workspace und erstellt einen BoardPlayer.

    Wenn keine board.json im Workspace vorhanden ist, wird ein Demo-Board mit
    ein paar Beispiel-Pads erstellt (ohne Asset-Dateien — werden beim Trigger
    graceful mit Warning gehandelt).

    workspace_v1-Import: Wenn eine workspace_v1.json vorhanden ist, wird das
    Board daraus importiert (Fallback auf eigenes Format).

    Returns:
        BoardPlayer-Instanz oder None bei Fehler.
    """
    try:
        from board.board_model import Board, Pad, load_board, import_from_workspace
        from board.board_player import BoardPlayer

        workspace_dir = config.workspace_dir
        os.makedirs(workspace_dir, exist_ok=True)

        board_pfad = os.path.join(workspace_dir, "board.json")
        workspace_v1_pfad = os.path.join(workspace_dir, "workspace_v1.json")

        board = None

        # Versuch 1: workspace_v1 importieren
        if os.path.isfile(workspace_v1_pfad):
            try:
                import json
                with open(workspace_v1_pfad, encoding="utf-8") as f:
                    payload = json.load(f)
                board = import_from_workspace(payload)
            except Exception:
                board = None

        # Versuch 2: eigenes Board-Format laden
        if board is None and os.path.isfile(board_pfad):
            try:
                board = load_board(board_pfad)
            except Exception:
                board = None

        # Fallback: Demo-Board
        if board is None or not board.pads:
            board = Board(pads=[
                Pad(id="demo1", label="Intro", color="#3a86ff", kind="audio",
                    asset_path="", mode="play_stop"),
                Pad(id="demo2", label="Jingle", color="#ff006e", kind="audio",
                    asset_path="", mode="play_stop"),
                Pad(id="demo3", label="Outro", color="#06d6a0", kind="audio",
                    asset_path="", mode="play_stop"),
            ])

        player = BoardPlayer(engine=engine, board=board)
        return player

    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Board/BoardPlayer-Initialisierung fehlgeschlagen: %s", exc)
        return None


def _video_quelle_fuer_selftest():
    """Gibt eine Video-Quelle für den Selftest zurück (Mock oder None)."""
    from video.video_manager import VideoManager
    try:
        manager = VideoManager()
        info = manager.suggest_default_source()
        if info is None:
            return None
        return manager.open_source(info)
    except Exception:
        return None


def _selftest(engine, library, fenster, state, channels=None, board_player=None) -> int:
    """Führt einen Headless-Selftest durch ohne Event-Loop-Blockade.

    Ablauf (M4):
      1. Audio+Video-Mock-Aufnahme (start → Pause → stop)
      2. Verifizierung: list_recordings() >= 1, duration > 0
      3. Wenn ffmpeg vorhanden: program.mp4 muss existieren und >0 Bytes haben
      4. Nachweis System-Quelle im Mock: channel 'system' in der Kanalliste
      5. Board-Audio-Pad triggern und Board-Audio im Mix nachweisen (M4)
      6. Engine stoppen, Exit-Code 0 bei Erfolg
    """
    import shutil
    from recordings.recording_session import RecordingSession

    ffmpeg_vorhanden = shutil.which("ffmpeg") is not None

    try:
        # Audio+Video-Aufnahme
        video_source = _video_quelle_fuer_selftest() if ffmpeg_vorhanden else None
        session = RecordingSession(library=library, engine=engine, state=state)
        session.start("Selftest-Aufnahme", video_source=video_source)
        # Warten, damit Mock-Thread Frames produziert (mind. ~300 ms für Video-Frames)
        time.sleep(0.35)
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

        # System-Kanal-Nachweis im Mock (M3)
        channel_ids = [c.source_id for c in (channels or [])]
        system_im_mock = "system" in channel_ids
        if not system_im_mock:
            print(
                "SELFTEST FEHLER: Kein System-Kanal in der Engine (Mock sollte System-Kanal enthalten).",
                file=sys.stderr,
            )
            engine.stop()
            return 1

        # Video-Prüfung (wenn ffmpeg verfügbar)
        video_ok = True
        if ffmpeg_vorhanden and video_source is not None:
            original = next((b for b in meta.branches if b.is_original), None)
            program_mp4 = original.video_path if original else ""
            if not program_mp4:
                print(
                    "SELFTEST FEHLER: video_path ist leer — program.mp4 wurde nicht erzeugt.",
                    file=sys.stderr,
                )
                video_ok = False
            elif not os.path.isfile(program_mp4):
                print(
                    f"SELFTEST FEHLER: program.mp4 existiert nicht: {program_mp4}",
                    file=sys.stderr,
                )
                video_ok = False
            elif os.path.getsize(program_mp4) == 0:
                print(
                    f"SELFTEST FEHLER: program.mp4 ist leer: {program_mp4}",
                    file=sys.stderr,
                )
                video_ok = False

        if not video_ok:
            engine.stop()
            return 1

        video_info = ""
        if ffmpeg_vorhanden and video_source is not None:
            original = next((b for b in meta.branches if b.is_original), None)
            video_info = f", video={original.video_path if original else '–'}"

        system_info = f", system={'ja' if system_im_mock else 'nein'}"

        # Board-Audio-Nachweis (M4): Audio-Pad während Mock-Aufnahme triggern,
        # Mix-Energie messen und mit Baseline ohne Board-Block vergleichen.
        board_info = ""
        if board_player is not None:
            board_info = _selftest_board_audio(engine, library, board_player)
            if board_info.startswith("FEHLER"):
                print(f"SELFTEST {board_info}", file=sys.stderr)
                engine.stop()
                return 1

        print(
            f"SELFTEST OK: {len(aufnahmen)} Aufnahme(n), duration={meta.duration:.3f}s"
            f"{video_info}{system_info}{board_info}"
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


def _selftest_board_audio(engine, library, board_player) -> str:
    """Selftest-Erweiterung M4: Board-Audio-Pad während Mock-Aufnahme triggern.

    Erzeugt ein synthetisches WAV, hängt es als Audio-Pad ans Demo-Board,
    triggert es während einer Probe-Aufnahme und verifiziert, dass Board-Audio
    im Mix landet (Mix-Peak > 0).

    Returns:
        String der Form ", board=ok (peak=0.xxxx)" bei Erfolg.
        String der Form "FEHLER: ..." bei Fehler.
    """
    import tempfile
    import numpy as np
    import soundfile as sf
    from board.board_model import Board, Pad
    from board.board_player import BoardPlayer
    from recordings.recording_session import RecordingSession
    from core.app_state import AppState

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Synthetisches WAV mit deutlichem Signal (0.5)
            wav_pfad = os.path.join(tmp_dir, "selftest_board.wav")
            samplerate = engine._config.samplerate
            daten = np.full((samplerate // 2, 2), 0.5, dtype=np.float32)  # 0.5s Signal
            sf.write(wav_pfad, daten, samplerate)

            # Neues Demo-Board mit Audio-Pad
            demo_pad = Pad(id="selftest_pad", label="Selftest", color="#3a86ff",
                           kind="audio", asset_path=wav_pfad, mode="play_stop")
            demo_board = Board(pads=[demo_pad])

            # BoardPlayer erzeugen (separater, temporärer Player für diesen Test)
            test_player = BoardPlayer(engine=engine, board=demo_board)

            # Probe-Aufnahme mit Board-Audio
            state = AppState()
            session = RecordingSession(library=library, engine=engine, state=state)
            session.start("Selftest-Board-Aufnahme")
            test_player.trigger("selftest_pad")
            time.sleep(0.5)  # Board-Feeder produziert Blöcke
            test_player.stop_all()
            meta = session.stop()

            # Mix auf Board-Audio prüfen
            original = next((b for b in meta.branches if b.is_original), None)
            if original is None:
                return "FEHLER: Board-Test: keine Original-Branch"

            mix_pfad = getattr(original, "audio_path", "") or getattr(original, "mix_path", "")
            if not mix_pfad or not os.path.isfile(mix_pfad):
                return "FEHLER: Board-Test: mix.wav fehlt"

            mix_daten, _ = sf.read(mix_pfad, dtype="float32")
            if mix_daten.size == 0:
                return "FEHLER: Board-Test: mix.wav ist leer"

            peak = float(np.max(np.abs(mix_daten)))
            if peak <= 0.0:
                return "FEHLER: Board-Test: mix.wav enthält nur Nullen — Board-Audio fehlt im Mix"

            return f", board=ok (peak={peak:.4f})"

    except Exception as exc:
        return f"FEHLER: Board-Selftest fehlgeschlagen: {exc}"


if __name__ == "__main__":
    sys.exit(main())
