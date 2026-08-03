"""Isolierte Live-Fixture für die manuelle Planer-Browserabnahme.

Startet die produktiven Library-, Projects- und Planer-HTTP-Dienste auf freien
localhost-Ports. Laufzeitdaten bleiben im explizit übergebenen Datenordner.
Der Prozess endet, sobald die Stop-Datei angelegt wird oder Ctrl+C eintrifft.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import wave
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
RECORDER_ROOT = REPO_ROOT / "Recorder"
PLANER_SERVER_ROOT = REPO_ROOT / "planer" / "server"
sys.path.insert(0, str(RECORDER_ROOT))
sys.path.insert(0, str(PLANER_SERVER_ROOT))

from bridge.library_api import LibraryApiServer  # noqa: E402
from bridge.projects_api import ProjectsApiServer  # noqa: E402
from planer_server import PlanerServer  # noqa: E402
from recordings.library import RecordingLibrary  # noqa: E402


def _write_fixture_wave(path: Path) -> None:
    """Schreibt eine kurze, valide stille WAV-Datei für den Browser-Player."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(8_000)
        wav_file.writeframes(b"\x00\x00" * 800)


def _write_ready(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Startet eine isolierte Klangpult-light-Planer-Browser-Fixture."
    )
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--ready-file", type=Path, required=True)
    parser.add_argument("--stop-file", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    data_dir = args.data_dir.resolve()
    ready_file = args.ready_file.resolve()
    stop_file = args.stop_file.resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    stop_file.unlink(missing_ok=True)

    library = RecordingLibrary(workspace_dir=str(data_dir / "workspace"))
    recording = library.create_recording("Browser-Abnahme Aufnahme")
    library.add_branch(recording.recording_id, "Browser-Zweig")
    audio_path = Path(library.recording_dir(recording.recording_id)) / "main" / "mix.wav"
    _write_fixture_wave(audio_path)

    library_server = LibraryApiServer(library=library)
    projects_server = ProjectsApiServer(data_dir=str(data_dir / "projects"))
    planer_server: PlanerServer | None = None

    try:
        library_server.start(host="127.0.0.1", port=0)
        projects_server.start(host="127.0.0.1", port=0)
        if library_server.port is None or projects_server.port is None:
            raise RuntimeError("Backend-Ports wurden nicht gebunden.")

        planer_server = PlanerServer(
            library_port=library_server.port,
            projects_port=projects_server.port,
        )
        planer_server.start(host="127.0.0.1", port=0)
        if planer_server.port is None:
            raise RuntimeError("Planer-Port wurde nicht gebunden.")

        payload = {
            "status": "ready",
            "pid": os.getpid(),
            "url": f"http://127.0.0.1:{planer_server.port}",
            "library_port": library_server.port,
            "projects_port": projects_server.port,
            "planer_port": planer_server.port,
            "recording_id": recording.recording_id,
            "recording_title": recording.title,
            "data_dir": str(data_dir),
        }
        _write_ready(ready_file, payload)
        print(json.dumps(payload, ensure_ascii=False), flush=True)

        while not stop_file.exists():
            time.sleep(0.2)
        return 0
    except KeyboardInterrupt:
        return 130
    finally:
        if planer_server is not None:
            planer_server.stop()
        projects_server.stop()
        library_server.stop()


if __name__ == "__main__":
    raise SystemExit(main())
