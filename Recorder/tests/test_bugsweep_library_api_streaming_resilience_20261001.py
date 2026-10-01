"""Regressionstests für den Bugsweep 2026-10-01 (KlangpultLight).

Bereich:
  "Bibliotheks-API & Proxy Streaming: HTTP Range-Requests, CORS/OPTIONS-Support,
   HEAD-Preflight, URL-Decoding und chunked Proxy-Forwarding (Recorder/bridge/library_api.py + planer/server/planer_server.py)"

Belegt vor Fix:
  - OPTIONS auf /api/library oder /api/library/<id>/audio warf HTTP 501
  - Range: bytes=X-Y auf /api/library/<id>/audio wurde ignoriert (200 statt 206 Partial Content)
  - HEAD auf /api/library oder /api/library/<id>/audio warf HTTP 501
  - GET /api/library/<id> (Detailabfrage) warf 404
  - Percent-encoded recording_id in URL wurde nicht dekodiert
  - PlanerHandler._proxy leitete Range nicht weiter und unterstützte weder OPTIONS noch HEAD
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

_PLANER_SERVER_DIR = Path(__file__).parent.parent.parent / "planer" / "server"
if str(_PLANER_SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(_PLANER_SERVER_DIR))

from bridge.library_api import LibraryApiServer  # noqa: E402
from recordings.library import RecordingLibrary  # noqa: E402


@pytest.fixture(autouse=True)
def mock_umgebung(monkeypatch):
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_AUDIO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_MOCK_VIDEO", "1")
    monkeypatch.setenv("PODCAST_RECORDER_BRIDGE", "0")


def _erstelle_test_library(tmp_path):
    library = RecordingLibrary(workspace_dir=str(tmp_path))
    meta = library.create_recording("Runde 1")
    main_dir = os.path.join(library.recording_dir(meta.recording_id), "main")
    os.makedirs(main_dir, exist_ok=True)
    audio_content = b"0123456789ABCDEF"  # 16 Bytes
    with open(os.path.join(main_dir, "mix.wav"), "wb") as f:
        f.write(audio_content)
    return library, meta, audio_content


def test_library_options_cors_preflight(tmp_path):
    library, meta, _ = _erstelle_test_library(tmp_path)
    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        url = f"http://127.0.0.1:{port}/api/library"
        req = urllib.request.Request(url, method="OPTIONS")
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 204
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
            methods = resp.headers.get("Access-Control-Allow-Methods", "")
            assert "GET" in methods and "OPTIONS" in methods and "HEAD" in methods
            assert "Range" in resp.headers.get("Access-Control-Allow-Headers", "")
    finally:
        server.stop()


def test_library_audio_range_request_partial_content(tmp_path):
    library, meta, audio_bytes = _erstelle_test_library(tmp_path)
    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        url = f"http://127.0.0.1:{port}/api/library/{meta.recording_id}/audio"
        # Bytes 0-3 (4 Bytes: b"0123")
        req = urllib.request.Request(url, headers={"Range": "bytes=0-3"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            assert resp.status == 206
            assert resp.headers.get("Content-Range") == "bytes 0-3/16"
            assert resp.headers.get("Content-Length") == "4"
            assert resp.headers.get("Accept-Ranges") == "bytes"
            assert resp.headers.get("Access-Control-Allow-Origin") == "*"
            data = resp.read()
            assert data == b"0123"

        # Open-ended: bytes=10- (6 Bytes: b"ABCDEF")
        req2 = urllib.request.Request(url, headers={"Range": "bytes=10-"})
        with urllib.request.urlopen(req2, timeout=5) as resp2:
            assert resp2.status == 206
            assert resp2.headers.get("Content-Range") == "bytes 10-15/16"
            assert resp2.headers.get("Content-Length") == "6"
            assert resp2.read() == b"ABCDEF"

        # Suffix: bytes=-4 (letzte 4 Bytes: b"CDEF")
        req3 = urllib.request.Request(url, headers={"Range": "bytes=-4"})
        with urllib.request.urlopen(req3, timeout=5) as resp3:
            assert resp3.status == 206
            assert resp3.headers.get("Content-Range") == "bytes 12-15/16"
            assert resp3.headers.get("Content-Length") == "4"
            assert resp3.read() == b"CDEF"
    finally:
        server.stop()


def test_library_audio_range_unsatisfiable_416(tmp_path):
    library, meta, _ = _erstelle_test_library(tmp_path)
    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        url = f"http://127.0.0.1:{port}/api/library/{meta.recording_id}/audio"
        req = urllib.request.Request(url, headers={"Range": "bytes=50-60"})
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=5)
        assert exc_info.value.code == 416
        assert exc_info.value.headers.get("Content-Range") == "bytes */16"
    finally:
        server.stop()


def test_library_head_method_support(tmp_path):
    library, meta, _ = _erstelle_test_library(tmp_path)
    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        # HEAD auf Audio
        url_audio = f"http://127.0.0.1:{port}/api/library/{meta.recording_id}/audio"
        req_audio = urllib.request.Request(url_audio, method="HEAD")
        with urllib.request.urlopen(req_audio, timeout=5) as resp:
            assert resp.status == 200
            assert resp.headers.get("Content-Length") == "16"
            assert resp.headers.get("Accept-Ranges") == "bytes"
            assert resp.headers.get("Content-Type") == "audio/wav"
            assert resp.read() == b""

        # HEAD auf JSON-Library
        url_lib = f"http://127.0.0.1:{port}/api/library"
        req_lib = urllib.request.Request(url_lib, method="HEAD")
        with urllib.request.urlopen(req_lib, timeout=5) as resp:
            assert resp.status == 200
            assert int(resp.headers.get("Content-Length", 0)) > 0
            assert "json" in resp.headers.get("Content-Type", "")
            assert resp.read() == b""
    finally:
        server.stop()


def test_library_single_recording_detail_endpoint(tmp_path):
    library, meta, _ = _erstelle_test_library(tmp_path)
    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        url = f"http://127.0.0.1:{port}/api/library/{meta.recording_id}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            daten = json.loads(resp.read().decode("utf-8"))
            assert "recording" in daten
            assert daten["recording"]["recording_id"] == meta.recording_id
            assert daten["recording"]["title"] == "Runde 1"

        # Unbekannte ID liefert 404
        url_404 = f"http://127.0.0.1:{port}/api/library/nicht-vorhanden"
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(url_404, timeout=5)
        assert exc_info.value.code == 404
    finally:
        server.stop()


def test_library_audio_url_decoding(tmp_path):
    library, meta, audio_bytes = _erstelle_test_library(tmp_path)
    server = LibraryApiServer(library=library)
    server.start(host="127.0.0.1", port=0)
    port = server.port
    try:
        encoded_id = urllib.parse.quote(meta.recording_id)
        url = f"http://127.0.0.1:{port}/api/library/{encoded_id}/audio"
        with urllib.request.urlopen(url, timeout=5) as resp:
            assert resp.status == 200
            assert resp.read() == audio_bytes
    finally:
        server.stop()


def test_planer_server_proxy_options_and_range_streaming(tmp_path):
    from planer_server import PlanerServer

    library, meta, audio_bytes = _erstelle_test_library(tmp_path)
    lib_server = LibraryApiServer(library=library)
    lib_server.start(host="127.0.0.1", port=0)

    planer = PlanerServer(library_port=lib_server.port, projects_port=19999)
    planer.start(host="127.0.0.1", port=0)

    try:
        # 1. OPTIONS durch Proxy
        url_opt = f"http://127.0.0.1:{planer.port}/api/library"
        req_opt = urllib.request.Request(url_opt, method="OPTIONS")
        with urllib.request.urlopen(req_opt, timeout=5) as resp_opt:
            assert resp_opt.status == 204
            assert resp_opt.headers.get("Access-Control-Allow-Origin") == "*"

        # 2. Range-Request durch Proxy
        url_audio = f"http://127.0.0.1:{planer.port}/api/library/{meta.recording_id}/audio"
        req_range = urllib.request.Request(url_audio, headers={"Range": "bytes=2-6"})
        with urllib.request.urlopen(req_range, timeout=5) as resp_range:
            assert resp_range.status == 206
            assert resp_range.headers.get("Content-Range") == "bytes 2-6/16"
            assert resp_range.headers.get("Content-Length") == "5"
            assert resp_range.headers.get("Accept-Ranges") == "bytes"
            assert resp_range.read() == audio_bytes[2:7]

        # 3. HEAD durch Proxy
        req_head = urllib.request.Request(url_audio, method="HEAD")
        with urllib.request.urlopen(req_head, timeout=5) as resp_head:
            assert resp_head.status == 200
            assert resp_head.headers.get("Content-Length") == "16"
            assert resp_head.read() == b""
    finally:
        planer.stop()
        lib_server.stop()
