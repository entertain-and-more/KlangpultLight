"""tests.test_mux_fehler_gemeldet — M-3: FFmpeg-Mux-Fehler werden gemeldet (Task 6a).

Belegt: Wenn mux_audio_video() beim Stop einer Aufnahme fehlschlägt, wird der
Fehler NICHT lautlos verschluckt — stattdessen:
  1. Als Event ("video_error", phase="mux") im EventLog protokolliert.
  2. Via logging.WARNING ausgegeben (Fallback, falls kein EventLog aktiv).

Die Tests patchen mux_audio_video direkt, um echtes FFmpeg nicht vorauszusetzen.
"""
import logging
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    """Alle Tests laufen mit Mock-Audio und Mock-Video."""
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")


def _erstelle_dummy_dateien(tmp_path):
    """Erzeugt kleine Dummy-MP4 und WAV-Dateien für Mux-Tests."""
    video_pfad = str(tmp_path / "program_video.mp4")
    wav_pfad = str(tmp_path / "mix.wav")
    # Minimale WAV (1 Frame)
    sf.write(wav_pfad, np.zeros((1024, 2), dtype=np.float32), 48000)
    # Minimale MP4 (leere Datei genügt für Path-Check in _stoppe_video_und_mux)
    with open(video_pfad, "wb") as f:
        f.write(b"\x00" * 16)
    return video_pfad, wav_pfad


# ---------------------------------------------------------------------------
# Hilfsklasse: minimale RecordingSession mit echtem _stoppe_video_und_mux
# ---------------------------------------------------------------------------

def _session_mit_event_log(tmp_path):
    """Baut eine RecordingSession mit aktivem EventLog."""
    from core.config import AppConfig
    from audio.mixer_channel import MixerChannel
    from audio.engine import AudioEngine
    from recordings.library import RecordingLibrary
    from recordings.recording_session import RecordingSession

    config = AppConfig(mock_audio=True, workspace_dir=str(tmp_path))
    channels = [MixerChannel(source_id="mic_1", name="Mikrofon 1")]
    engine = AudioEngine(config, channels)

    lib = RecordingLibrary(str(tmp_path))
    session = RecordingSession(library=lib, engine=engine)
    return session


# ---------------------------------------------------------------------------
# Test 1: Mux-Fehler wird als video_error-Event geloggt
# ---------------------------------------------------------------------------

def test_mux_fehler_wird_als_event_geloggt(tmp_path):
    """Wenn mux_audio_video() fehlschlägt, muss ein video_error-Event im EventLog stehen.

    Szenario: Dummy-Dateien existieren (path-checks bestehen), aber mux wirft RuntimeError.
    """
    from core.event_log import EventLog

    session = _session_mit_event_log(tmp_path)

    # EventLog manuell aufsetzen (wird sonst von start() erzeugt)
    events_pfad = str(tmp_path / "events.jsonl")
    event_log = EventLog(events_pfad)
    session._event_log = event_log

    video_pfad, mix_pfad = _erstelle_dummy_dateien(tmp_path)
    session._video_pfad = video_pfad

    # VideoRecorder-Stub: close() tut nichts (kein echter Prozess)
    class StubVideoRecorder:
        def close(self):
            pass

    session._video_recorder = StubVideoRecorder()

    # Mux fehlschlägt simulieren
    # mux_audio_video wird per lokalem Import in der Methode eingebunden →
    # Patch an der Originalquelle (video.video_recorder) wirkt auf den Import.
    with patch(
        "video.video_recorder.mux_audio_video",
        side_effect=RuntimeError("FFmpeg Mux fehlgeschlagen — Testfehler"),
    ):
        ergebnis = session._stoppe_video_und_mux(mix_pfad=mix_pfad, audio_dauer=1.0)

    # Rückgabewert: leerer String bei Fehler
    assert ergebnis == "", f"Bei Mux-Fehler muss '' zurückgegeben werden, nicht: {ergebnis!r}"

    # EventLog schließen und auslesen
    event_log.close()

    import json
    eintraege = []
    with open(events_pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if zeile:
                eintraege.append(json.loads(zeile))

    # EventLog speichert den event_type unter dem Schlüssel "type"
    video_error_events = [e for e in eintraege if e.get("type") == "video_error"]
    assert video_error_events, (
        f"Kein video_error-Event im EventLog. Alle Events: {eintraege}"
    )

    # Mux-spezifisches Event muss phase='mux' enthalten
    mux_events = [e for e in video_error_events if e.get("phase") == "mux"]
    assert mux_events, (
        f"video_error-Event ohne phase='mux'. video_error-Events: {video_error_events}"
    )


# ---------------------------------------------------------------------------
# Test 2: Mux-Fehler wird via logging gemeldet (auch ohne EventLog)
# ---------------------------------------------------------------------------

def test_mux_fehler_via_logging_ohne_event_log(tmp_path, caplog):
    """Wenn kein EventLog aktiv ist, muss der Mux-Fehler via logging.WARNING gemeldet werden."""

    session = _session_mit_event_log(tmp_path)
    session._event_log = None  # Kein EventLog

    video_pfad, mix_pfad = _erstelle_dummy_dateien(tmp_path)
    session._video_pfad = video_pfad

    class StubVideoRecorder:
        def close(self):
            pass

    session._video_recorder = StubVideoRecorder()

    with caplog.at_level(logging.WARNING, logger="recordings.recording_session"):
        with patch(
            "video.video_recorder.mux_audio_video",
            side_effect=RuntimeError("Mux-Test ohne EventLog"),
        ):
            ergebnis = session._stoppe_video_und_mux(mix_pfad=mix_pfad, audio_dauer=1.0)

    assert ergebnis == "", "Bei Mux-Fehler muss '' zurückgegeben werden"

    mux_logs = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "mux" in r.message.lower()
    ]
    assert mux_logs, (
        f"Kein Mux-WARNING-Log gefunden. Alle Logs: "
        f"{[(r.levelname, r.message) for r in caplog.records]}"
    )


# ---------------------------------------------------------------------------
# Test 3: Mux-Fehler mit aktivem EventLog loggt AUCH via logging
# ---------------------------------------------------------------------------

def test_mux_fehler_loggt_sowohl_event_als_auch_warning(tmp_path, caplog):
    """Mit EventLog: Mux-Fehler erzeugt sowohl Event als auch logging.WARNING.

    M-3 verlangt: Event-Log UND logging-Ausgabe (beide, nicht nur eines).
    """
    from core.event_log import EventLog

    session = _session_mit_event_log(tmp_path)
    events_pfad = str(tmp_path / "events2.jsonl")
    event_log = EventLog(events_pfad)
    session._event_log = event_log

    video_pfad, mix_pfad = _erstelle_dummy_dateien(tmp_path)
    session._video_pfad = video_pfad

    class StubVideoRecorder:
        def close(self):
            pass

    session._video_recorder = StubVideoRecorder()

    with caplog.at_level(logging.WARNING, logger="recordings.recording_session"):
        with patch(
            "video.video_recorder.mux_audio_video",
            side_effect=RuntimeError("Mux-Test beide Kanäle"),
        ):
            session._stoppe_video_und_mux(mix_pfad=mix_pfad, audio_dauer=1.0)

    event_log.close()

    # WARNING-Log muss vorhanden sein
    mux_logs = [
        r for r in caplog.records
        if r.levelno >= logging.WARNING and "mux" in r.message.lower()
    ]
    assert mux_logs, (
        f"Kein Mux-WARNING-Log. Alle Logs: "
        f"{[(r.levelname, r.message) for r in caplog.records]}"
    )

    # Event muss auch vorhanden sein
    import json
    eintraege = []
    with open(events_pfad, encoding="utf-8") as f:
        for zeile in f:
            zeile = zeile.strip()
            if zeile:
                eintraege.append(json.loads(zeile))

    # EventLog speichert den event_type unter dem Schlüssel "type"
    assert any(e.get("type") == "video_error" for e in eintraege), (
        f"Kein video_error-Event trotz aktivem EventLog. Alle Events: {eintraege}"
    )
