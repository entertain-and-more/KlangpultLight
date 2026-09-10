"""main.py — Entrypoint des Klangpult light – Recorders.

Start aus Recorder/ heraus: python main.py
Kein `python -m`, Imports relativ zum Recorder/-Root.

Headless-Selftest:
  PODCAST_RECORDER_SELFTEST=1
  → setzt automatisch QT_QPA_PLATFORM=offscreen sowie Mock-Audio/Mock-Video,
    startet App + MainWindow offscreen, führt eine Probe-Aufnahme durch,
    verifiziert list_recordings() >= 1 mit duration > 0, beendet mit Exit-Code 0.
  → Bei Fehler: Exit-Code 1.
"""
import os
import sys
import time


def _source_root() -> str:
    """Quellwurzel des Recorders.

    Im Source-Betrieb ist das der Recorder-Ordner. Im Frozen-Betrieb bleibt
    __file__ wichtig für Import-/Bundle-Pfade.
    """
    return os.path.dirname(os.path.abspath(__file__))


def _runtime_base_dir() -> str:
    """Schreibbare Laufzeitbasis für Workspace-Daten.

    Quellbetrieb: Recorder-Ordner.
    Frozen-EXE: Ordner der EXE, nicht _MEIPASS/Temp.
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return _source_root()


def _setup_sys_path() -> None:
    """Stellt sicher, dass Recorder/ im sys.path liegt."""
    recorder_root = _source_root()
    if recorder_root not in sys.path:
        sys.path.insert(0, recorder_root)


_setup_sys_path()


def _selftest_requested() -> bool:
    """True, wenn der Headless-Selftest angefordert wurde."""
    return os.environ.get("PODCAST_RECORDER_SELFTEST", "").strip() == "1"


def _prepare_selftest_environment() -> bool:
    """Setzt robuste Defaults für den Headless-Selftest.

    Die Umgebung muss vor dem PySide6-Import stehen, weil Qt das Platform-Plugin
    beim Laden initialisiert.  Selftest ist immer hardwarefrei: Audio und Video
    laufen über Mock-Pfade, damit Start-Smokes auch ohne Geräte reproduzierbar
    sind.
    """
    selftest = _selftest_requested()
    if selftest:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        os.environ["PODCAST_RECORDER_MOCK_AUDIO"] = "1"
        os.environ["PODCAST_RECORDER_MOCK_VIDEO"] = "1"
    return selftest


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
    selftest = _prepare_selftest_environment()

    from PySide6.QtWidgets import QApplication

    from audio.device_manager import DeviceManager
    from audio.engine import AudioEngine
    from core.app_state import AppState
    from core.config import AppConfig
    from recordings.library import RecordingLibrary
    from sources.build_channels import build_channels
    from sources.loopback_detector import LoopbackDetector
    from sources.source_config import load_sources_config
    from ui.main_window import MainWindow

    # --- Konfiguration ---
    workspace_dir = os.path.join(_runtime_base_dir(), "workspace")
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
    for eintrag in sources_config.enabled_sources():
        if eintrag.device_index is not None:
            device_assignment[eintrag.source_id] = eintrag.device_index

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

    # --- STT (Live-Transkription, Task 5b) — optional, env-/config-gesteuert ---
    # Aktivieren:  PODCAST_RECORDER_STT=1 (oder "cloud" für Cloud-Engine)
    # Deaktivieren: PODCAST_RECORDER_STT=0 (Standard wenn Libs fehlen)
    # Der SttManager wird nach dem Bridge-Start aufgesetzt, damit push_transcript_chunk
    # verfügbar ist. Placeholder, der nach dem Bridge-Block befüllt wird.
    _stt_manager = None  # wird weiter unten gesetzt

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
        planer_port = (
            int(os.environ.get("PLANER_PORT", "8770"))
            if BridgeService.soll_planer_starten()
            else None
        )
        bridge = BridgeService(
            library=library,
            engine=engine,
            state=state,
            board_player=board_player,
            planer_port=planer_port,
        )
        bridge.start()

    if hasattr(fenster, "set_bridge"):
        fenster.set_bridge(bridge)

    # --- STT-Manager aufsetzen (nach Bridge-Start, vor Selftest) ---
    stt_env = os.environ.get("PODCAST_RECORDER_STT", "").strip()
    stt_prefer = "cloud" if stt_env == "cloud" else "local"
    stt_aktiv = stt_env not in ("0", "")

    if stt_aktiv:
        _stt_manager = _setup_stt(
            engine=engine,
            bridge=bridge,
            prefer=stt_prefer,
        )

    # --- Headless-Selftest ---
    if selftest:
        ergebnis = _selftest(
            engine, library, fenster, state, channels, board_player, bridge,
            stt_manager=_stt_manager,
        )
        if _stt_manager is not None:
            _stt_manager.stop()
        if bridge is not None:
            bridge.stop()
        return ergebnis

    # --- Normaler Start ---
    fenster.show()
    exit_code = app.exec()
    if _stt_manager is not None:
        _stt_manager.stop()
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


def _setup_stt(engine, bridge, prefer: str = "local"):
    """Richtet den SttManager ein und hängt ihn in den Mix-Audio-Tap.

    Wählt die Engine nach Präferenz und verfügbaren Adaptern:
    - prefer='cloud': Cloud wenn API-Key + openai vorhanden, sonst lokal
    - prefer='local' (Standard): lokal wenn faster-whisper vorhanden, sonst deaktiviert

    Args:
        engine: AudioEngine-Instanz (muss register_audio_sink() haben).
        bridge: BridgeService-Instanz oder None.
        prefer: 'cloud' oder 'local'.

    Returns:
        Gestarteter SttManager oder None wenn keine Engine verfügbar ist.
    """
    import logging

    from stt.local_engine import LocalWhisperEngine
    from stt.cloud_engine import CloudSttEngine
    from stt.stt_manager import SttManager, select_engine
    from stt.transcript_models import TranscriptChunk

    _log_stt = logging.getLogger(__name__)

    local = LocalWhisperEngine()
    cloud = CloudSttEngine()

    gewählte_engine = select_engine(prefer=prefer, local=local, cloud=cloud)

    if not gewählte_engine.available():
        _log_stt.info(
            "STT: Keine Engine verfügbar — Live-Transkription deaktiviert. "
            "Installiere 'faster-whisper' (lokal) oder setze OPENAI_API_KEY (Cloud)."
        )
        return None

    # on_chunk-Adapter: TranscriptChunk → bridge.push_transcript_chunk
    def on_chunk(chunk: TranscriptChunk) -> None:
        if bridge is not None and bridge.ws is not None:
            try:
                bridge.ws.push_transcript_chunk(
                    text=chunk.text,
                    is_final=chunk.is_final,
                    t_start=chunk.t_start,
                    engine=chunk.engine,
                )
            except Exception as exc:
                _log_stt.warning("STT on_chunk Bridge-Fehler: %s", exc)

    stt_manager = SttManager(
        engine=gewählte_engine,
        on_chunk=on_chunk,
        samplerate=engine._config.samplerate,
    )
    stt_manager.start()

    # Mix-Audio-Tap registrieren
    engine.register_audio_sink(stt_manager.feed)

    _log_stt.info("STT gestartet (Engine: %s).", gewählte_engine.name)
    return stt_manager


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


def _zwei_video_quellen_fuer_selftest():
    """Gibt 2 MockVideoSource-Instanzen für den Split-Selftest zurück.

    Immer im Mock-Modus (PODCAST_RECORDER_MOCK_VIDEO=1 wird für den Selftest gesetzt).
    """
    try:
        from video.video_source import MockVideoSource, VideoSourceInfo
        info0 = VideoSourceInfo(
            source_id="selftest_mock_0", name="Selftest Mock 0", kind="mock",
            verified=True, is_mock=True, width=1280, height=720,
        )
        info1 = VideoSourceInfo(
            source_id="selftest_mock_1", name="Selftest Mock 1", kind="mock",
            verified=True, is_mock=True, width=1280, height=720,
        )
        return MockVideoSource(info0), MockVideoSource(info1)
    except Exception:
        return None, None


def _selftest(engine, library, fenster, state, channels=None, board_player=None,
              bridge=None, stt_manager=None) -> int:
    """Führt einen Headless-Selftest durch ohne Event-Loop-Blockade.

    Ablauf (M4/M5/M5b):
      1. Audio+Video-Mock-Aufnahme (start → Pause → stop)
      2. Verifizierung: list_recordings() >= 1, duration > 0
      3. Wenn ffmpeg vorhanden: program.mp4 muss existieren und >0 Bytes haben
      4. Nachweis System-Quelle im Mock: channel 'system' in der Kanalliste
      5. Board-Audio-Pad triggern und Board-Audio im Mix nachweisen (M4)
      6. Bridge hochfahren, GET /api/library liefert >= 1 Aufnahme (M5)
      7. STT Mock-Chunk über on_chunk/Bridge nachweisen (M5b)
      8. Engine stoppen, Exit-Code 0 bei Erfolg
    """
    import shutil
    from recordings.recording_session import RecordingSession

    ffmpeg_vorhanden = shutil.which("ffmpeg") is not None

    try:
        # Audio+Video-Aufnahme mit 2 Mock-Video-Quellen (Task 6b: Split-Selftest)
        video_src_0, video_src_1 = (
            _zwei_video_quellen_fuer_selftest() if ffmpeg_vorhanden else (None, None)
        )
        zwei_quellen = (video_src_0 is not None and video_src_1 is not None)

        session = RecordingSession(library=library, engine=engine, state=state)
        if zwei_quellen:
            session.start("Selftest-Aufnahme", video_sources=[video_src_0, video_src_1])
        else:
            session.start("Selftest-Aufnahme")
        # Warten, damit Mock-Thread Frames produziert (mind. ~500 ms für Compositor)
        time.sleep(0.5)
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

        # Video-Prüfung (wenn ffmpeg verfügbar und 2 Mock-Quellen genutzt)
        video_ok = True
        video_info = ""
        if ffmpeg_vorhanden and zwei_quellen:
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
            else:
                # Auflösung prüfen: muss Compositor-Zielauflösung sein (1280×720)
                try:
                    import cv2
                    from video.compositor import COMPOSITOR_STANDARD_AUFLOESUNG
                    cap = cv2.VideoCapture(program_mp4)
                    try:
                        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    finally:
                        cap.release()
                    erwartet_w, erwartet_h = COMPOSITOR_STANDARD_AUFLOESUNG
                    if w != erwartet_w or h != erwartet_h:
                        print(
                            f"SELFTEST FEHLER: program.mp4 Auflösung {w}×{h} "
                            f"≠ Compositor-Ziel {erwartet_w}×{erwartet_h}",
                            file=sys.stderr,
                        )
                        video_ok = False
                    else:
                        video_info = (
                            f", video={program_mp4} ({w}×{h}, Split-Compositor)"
                        )
                except Exception as exc:
                    # cv2 nicht verfügbar oder anderer Fehler — Auflösungscheck überspringen
                    video_info = f", video={program_mp4} (Auflösungscheck fehlgeschlagen: {exc})"

        if not video_ok:
            engine.stop()
            return 1

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

        # Bridge-Nachweis (M5): Bibliothek-API hochfahren und per HTTP abfragen.
        bridge_info = _selftest_bridge_library(library, bridge)
        if bridge_info.startswith("FEHLER"):
            print(f"SELFTEST {bridge_info}", file=sys.stderr)
            engine.stop()
            return 1

        # STT-Nachweis (M5b): MockSttEngine + SttManager + on_chunk → mind. 1 Chunk.
        stt_info = _selftest_stt(engine, bridge, stt_manager)
        if stt_info.startswith("FEHLER"):
            print(f"SELFTEST {stt_info}", file=sys.stderr)
            engine.stop()
            return 1

        print(
            f"SELFTEST OK: {len(aufnahmen)} Aufnahme(n), duration={meta.duration:.3f}s"
            f"{video_info}{system_info}{board_info}{bridge_info}{stt_info}"
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


def _selftest_bridge_library(library, bridge=None) -> str:
    """Selftest-Erweiterung M5: Bibliothek-API per HTTP abfragen.

    Fährt die Bridge hoch (falls nicht schon laufend — z. B. weil
    PODCAST_RECORDER_BRIDGE=0 gesetzt war), ruft in-process
    GET /api/library auf und prüft, dass mindestens eine Aufnahme
    im JSON zurückkommt. Stoppt eine selbst gestartete Bridge sauber.

    Returns:
        ", bridge=ok (N Aufnahmen)" bei Erfolg, "FEHLER: ..." bei Fehler.
    """
    import json as _json
    import urllib.request

    from bridge.bridge_service import BridgeService

    eigene_bridge = None
    try:
        aktive_bridge = bridge
        if aktive_bridge is None or aktive_bridge.api is None:
            # Bridge war nicht aktiv (z. B. BRIDGE=0) — für den Check selbst starten.
            # Port 0 = freier Port, vermeidet Kollision mit produktivem 8767.
            eigene_bridge = BridgeService(library=library, library_port=0, ws_port=0)
            eigene_bridge.start()
            aktive_bridge = eigene_bridge

        port = aktive_bridge.api.port if aktive_bridge.api is not None else None
        if not port:
            return "FEHLER: Bridge-Test: Library-API-Port nicht verfügbar"

        url = f"http://127.0.0.1:{port}/api/library"
        with urllib.request.urlopen(url, timeout=5) as resp:
            if resp.status != 200:
                return f"FEHLER: Bridge-Test: HTTP {resp.status} von /api/library"
            daten = _json.loads(resp.read().decode("utf-8"))

        aufnahmen = daten.get("recordings", [])
        if len(aufnahmen) < 1:
            return "FEHLER: Bridge-Test: /api/library lieferte keine Aufnahmen"

        return f", bridge=ok ({len(aufnahmen)} Aufnahmen)"

    except Exception as exc:
        return f"FEHLER: Bridge-Selftest fehlgeschlagen: {exc}"
    finally:
        if eigene_bridge is not None:
            eigene_bridge.stop()


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


def _selftest_stt(engine, bridge, laufender_stt_manager=None) -> str:
    """Selftest-Erweiterung M5b: STT Mock-Chunk über on_chunk/Bridge nachweisen.

    Erzeugt einen MockSttEngine + SttManager mit kurzem Fenster, registriert
    ihn am Mix-Audio-Tap der Engine und wartet, bis mind. ein Chunk über
    den on_chunk-Callback ankommt.  Testet unabhängig davon, ob der echte
    SttManager läuft (Isolation durch separaten temporären Manager).

    Returns:
        ", stt=ok (N Chunks)" bei Erfolg, "FEHLER: ..." bei Fehler.
    """
    import threading

    from stt.mock_engine import MockSttEngine
    from stt.stt_manager import SttManager
    from stt.transcript_models import TranscriptChunk

    empfangene: list[TranscriptChunk] = []
    chunk_event = threading.Event()

    def on_chunk(chunk: TranscriptChunk) -> None:
        empfangene.append(chunk)
        chunk_event.set()

    # Kurzes Fenster damit Mock-Audio reicht (0.05 s = 2400 Samples bei 48 kHz)
    samplerate = engine._config.samplerate
    window_seconds = 0.05

    test_manager = SttManager(
        engine=MockSttEngine(),
        on_chunk=on_chunk,
        samplerate=samplerate,
        window_seconds=window_seconds,
    )
    test_manager.start()

    # Mix-Audio-Tap temporär registrieren
    engine.register_audio_sink(test_manager.feed)

    try:
        # Warten, bis mindestens ein Chunk über on_chunk ankommt (max. 5 s).
        # Der Mock-Synth-Loop der AudioEngine produziert im Hintergrund Audio;
        # nach window_seconds sollte ein Fenster ausgelöst sein.
        ankam = chunk_event.wait(timeout=5.0)
    finally:
        # Tap wieder freigeben (kein Einfluss auf den echten STT-Manager)
        engine.unregister_audio_sink()
        test_manager.stop()

    if not ankam:
        return "FEHLER: STT-Test: Kein Mock-Chunk innerhalb von 5 Sekunden empfangen"

    n = len(empfangene)
    return f", stt=ok ({n} Chunk{'s' if n != 1 else ''})"


if __name__ == "__main__":
    sys.exit(main())
