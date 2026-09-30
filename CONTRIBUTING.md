# Contributing to Klangpult light

Thank you for your interest in contributing to **Klangpult light** (`entertain-and-more/KlangpultLight`), a lightweight, local-first audio/video recording workstation and media planning suite built with Python, PySide6, and modern loopback web standards.

## Principles & Invariants

All contributions must strictly adhere to our core architectural invariants:
1. **100% Local-First & Zero Egress (`INV-LOCAL-01`)**: All audio, video, transcripts, and session plans remain strictly on the creator's local system. Zero telemetry, zero analytics, zero external network calls.
2. **Unprivileged Execution (`INV-USER-02`)**: Operates under strict `RunAsInvoker` security without requiring administrator privileges or root access.
3. **Strict Loopback IPC Isolation (`INV-IPC-03`)**: Inter-process communication between Recorder and Web Planer is bound strictly to `127.0.0.1` (ports `8767`, `8769`, `8770`).
4. **Safe Subprocess Boundaries (`INV-SAFE-04`)**: FFmpeg remuxing and video capture use explicit argument vectors (non-shell) and strict path sanitization.
5. **Bounded Buffer & Audio Integrity (`INV-BUF-05`)**: Multichannel audio buffers sanitize against NaN/Inf float samples and flush atomically to standard WAV containers.
6. **Offline STT Degradation Boundary (`INV-STT-06`)**: Local `faster-whisper` transcription operates in an isolated worker thread; missing weights or compute errors never stall recording or UI rendering.
7. **Creator Data Sovereignty (`INV-STORE-07`)**: Session folders, event logs (`events.jsonl`), and recordings are retained indefinitely without automated deletion or cloud sync.
8. **Cross-Platform Operating Parity (`INV-PLAT-08`)**: Clean support across Windows, Linux, and macOS.
9. **Multi-Host & Sync Defense (`INV-SYNC-09`)**: `.gitignore` strictly ignores cloud sync conflict copies and multi-agent locks.
10. **Security Response SLA (`INV-SLA-10`)**: Commitment to 48-hour response and 5-day triage SLA under `SECURITY.md`.
11. **Quality Gates**: All tests must pass with 100% green status (`pytest`), `ruff check .` must be clean (0 errors), `python -m compileall -q .` must succeed (0 bytecode errors), and `git diff --check` must be free of whitespace errors.
12. **Strict Version Freeze**: Under governance rule `T-20260920-167562623`, the project version (`0.1.0`) remains strictly pinned across routine maintenance PRs.

## Local Development Setup

```bash
# Clone repository
git clone https://github.com/entertain-and-more/KlangpultLight.git
cd KlangpultLight

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install dependencies and test tooling
pip install -r requirements.txt
pip install -e ".[test]"

# Run full test suite
pytest

# Run metadata contract tests
pytest tests/test_metadata.py

# Run static quality checks
ruff check .
python -m compileall -q .
```

## Pull Request Guidelines

- Ensure your branch is rebased on `main`.
- Add or update contract tests in `tests/` for any new functionality or bug fixes.
- Document all changes under `## [Unreleased]` in `CHANGELOG.md`.
- Adhere strictly to PEP 8 / PEP 621 conventions and Ruff linting standards.
- Never introduce hardcoded user profile paths or external network dependencies.
