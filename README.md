![Klangpult light Banner](docs/assets/banner.svg)

# Klangpult light

**Status: Public Alpha** — lightweight, local-first desktop and web workstation for podcasting, multimedia recording, and content planning.

[![Status](https://img.shields.io/badge/Status-Alpha-orange.svg)](#)
[![Version](https://img.shields.io/badge/Version-v0.1.1-blue.svg)](./CHANGELOG.md)
[![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://www.python.org/)
[![Pytest](https://img.shields.io/badge/Pytest-450%20tests%20(449%20passed)-success.svg)](https://docs.pytest.org/)
[![CI](https://img.shields.io/badge/CI-Multi--OS%20Matrix-blue.svg)](https://github.com/entertain-and-more/KlangpultLight/actions/workflows/ci.yml)
[![Platforms](https://img.shields.io/badge/Platforms-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)](#)
[![License](https://img.shields.io/badge/License-Freeware-informational.svg)](./LICENSE)
[![Local-First](https://img.shields.io/badge/Architecture-Local--First%20%7C%20Zero--Egress-orange.svg)](./SECURITY.md)
[![Security](https://img.shields.io/badge/Security-Unprivileged%20(RunAsInvoker)-green.svg)](./SECURITY.md)
[![Security SLA](https://img.shields.io/badge/Security%20SLA-48h%20response%20%7C%205d%20triage-blue.svg)](./SECURITY.md)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Ecosystem](https://img.shields.io/badge/Ecosystem-entertain--and--more-blueviolet.svg)](https://github.com/entertain-and-more)
[![Umbrella](https://img.shields.io/badge/Umbrella-open--bricks-blue.svg)](https://github.com/open-bricks/open-bricks)
[![LLM-Ready](https://img.shields.io/badge/LLM--Ready-llms.txt-purple.svg)](./llms.txt)

[🇬🇧 English Version](README.md) | [🇩🇪 Deutsche Version](README_de.md)

> **Klangpult light** is the complimentary freeware edition (funnel).<br>
> Full commercial counterpart: **Klangpult** (proprietary full edition with automated multichannel cutting, batch export, and OCR).<br>
> License: Freeware / Proprietary, Closed-Source.

> [!NOTE]
> For AI agents and automated tools: See [llms.txt](./llms.txt) (Last checked: 2026-09-09) for machine-readable repository overview and test contracts. Detailed marketing, SEO, and visual asset telemetry is tracked in [MARKETING-LOG.txt](./MARKETING-LOG.txt).

---

## Quick Navigation

1. [Overview & Key Capabilities](#overview--key-capabilities)
2. [System Architecture Flowchart](#system-architecture-flowchart)
3. [Media & Recording Lifecycle Sequence](#media--recording-lifecycle-sequence)
4. [Governance & Runtime Invariants](#governance--runtime-invariants)
5. [Key Features](#key-features)
6. [UI Preview & Screenshots](#ui-preview--screenshots)
7. [Klangpult light – Planer Quickstart](#klangpult-light--planer-quickstart)
8. [Klangpult light – Recorder Quickstart](#klangpult-light--recorder-quickstart)
9. [Build Standalone Executable](#build-standalone-executable)
10. [Sibling Tools & Ecosystem Matrix](#sibling-tools--ecosystem-matrix)
11. [Feature Comparison: Light vs. Full Edition](#feature-comparison-light-vs-full-edition)
12. [Validation & Verification Gates](#validation--verification-gates)
13. [Security Policy & Triage SLA](#security-policy--triage-sla)
14. [License & Author](#license--author)

---

<a id="overview--key-capabilities"></a>
## Overview & Key Capabilities

Klangpult light decouples recording operations from project planning into two tightly integrated tools:

- **`Recorder/`** — **Klangpult light – Recorder**, Desktop App (Python / PySide6): High-fidelity multichannel audio recording, WASAPI/MME loopback capture, video capture with FFmpeg remuxing, live soundboard pads, and live speech-to-text transcription.
- **`planer/`** — **Klangpult light – Planer**, Web App (Python HTTP / Vanilla JS): Episode management, asset tracking, project timelines, teleprompter engine, and AI monitor view.

Both tools communicate via local loopback IPC sockets (`127.0.0.1:8767` and `127.0.0.1:8769`), guaranteeing 100% offline isolation without cloud egress.

---

<a id="system-architecture-flowchart"></a>
## System Architecture Flowchart

```mermaid
graph TD
    A[Klangpult light Engine] --> B[Recorder Desktop App - PySide6]
    A --> C[Planer Web App - Python/HTTP]
    B --> D[System Audio & Video Capture]
    B --> E[Live Transcription Engine]
    B --> I[Soundboard & Visual Pads]
    C --> F[Episode & Asset Planner]
    C --> G[Teleprompter & AI Monitor]
    B <-->|IPC Bridge Ports 8767 / 8769| C
    A --> H[Shared Models & Local Storage]
```

---

<a id="media--recording-lifecycle-sequence"></a>
## Media & Recording Lifecycle Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Creator as Creator / Producer
    participant Planer as Planer Web App (:8770)
    participant Bridge as IPC Bridge (:8767 / :8769)
    participant Recorder as Recorder Desktop (PySide6)
    participant AudioCore as Audio Engine & Devices
    participant Disk as Local Storage (Zero-Egress)

    Creator->>Planer: Open Episode Planning & Teleprompter
    Planer->>Bridge: Query Library & Active Recording State
    Bridge->>Recorder: Fetch AppState & Audio Levels
    Recorder-->>Bridge: Return Channels, Devices & Live State
    Bridge-->>Planer: Render Dynamic Media Dashboard

    Creator->>Recorder: Trigger Record Session
    Recorder->>AudioCore: Start Audio/Video Capture & Live STT
    AudioCore->>Disk: Stream multi-track WAV & MP4
    Recorder->>Bridge: Broadcast State Update (WebSocket)
    Bridge->>Planer: Sync Teleprompter & Live AI Monitor

    Creator->>Recorder: Stop Recording & Remux
    Recorder->>Disk: Finalize Session Metadata & Events (events.jsonl)
    Recorder-->>Creator: Ready for Playback & Planning
```

---

<a id="governance--runtime-invariants"></a>
## Governance & Runtime Invariants

Klangpult light adheres to 10 strict architectural and runtime invariants to guarantee system stability, user privacy, and cross-platform reliability:

| # | Invariant | Scope | Technical Enforcement | Verification Guarantee |
|---|---|---|---|---|
| 1 | **100% Local-First & Zero-Egress** | Network & Privacy | Audio, video, transcriptions, and planning data remain strictly on the local machine. Zero analytics, telemetry, or outbound network calls. | Audited via static code inspection and local loopback binding assertions. |
| 2 | **Unprivileged Execution (RunAsInvoker)** | Process & OS Security | Runs entirely in standard user space without requiring Administrator or root elevation. | No UAC prompts; standard user directory workspace ownership. |
| 3 | **Strict Loopback IPC Isolation** | Interprocess Communication | IPC between PySide6 Recorder and HTTP Web Planer is bound exclusively to `127.0.0.1` (`:8767`, `:8769`, `:8770`). | Local socket binding contracts prevent LAN/WAN exposure. |
| 4 | **Safe Subprocess Boundaries** | Process Isolation | FFmpeg remuxing and video capture subprocesses use explicit argument vectors (non-shell) and path traversal sanitization. | Guarded execution prevents arbitrary command injection. |
| 5 | **Bounded Buffer & Audio Integrity** | Audio Core | Multichannel audio buffers sanitize against NaN/Inf float samples and flush atomically to standard WAV containers. | Zero crash on audio device disconnect; atomic file flush. |
| 6 | **Offline STT Degradation Boundary** | Speech-to-Text | Local `faster-whisper` transcription operates in an isolated worker thread with graceful fallback if weights are missing. | Transcription errors never stall real-time recording or UI rendering. |
| 7 | **Caller-Controlled Session Storage** | Storage & Retention | Session folders, event logs (`events.jsonl`), and recordings are owned and retained exclusively by the creator with zero auto-purge. | Deterministic directory layout under creator workspace. |
| 8 | **Cross-Platform Operating Parity** | Platform Portability | Architecture, protocol schemas (`v1`), and data models run consistently across Windows, Linux, and macOS. | CI multi-OS matrix validation across Ubuntu, Windows, and macOS. |
| 9 | **Multi-Host & Sync Resilience** | File & Lock Hygiene | `.gitignore` rigorously ignores conflict copies (`*-conflict-*`, `*.sync-temp-*`) and multi-agent locks (`LOCK.*`, `*.lock`). | Zero git pollution or corrupted cloud sync state across devices. |
| 10 | **48h Response & 5-Day Triage SLA** | Security Governance | Coordinated vulnerability disclosure with guaranteed acknowledgement within 48h and formal triage within 5 business days. | Published in `SECURITY.md` with official contacts `security@open-bricks.org` and `security@ellmos.ai`. |

---

<a id="key-features"></a>
## Key Features

- 🎙️ **Multichannel Audio Recording**: Dedicated channels for microphone input, system audio capture, and soundboard clips.
- 📹 **Synchronized Video Capture**: Video stream recorded alongside audio and muxed into standard MP4 via FFmpeg.
- ⚡ **Live Soundboard & Visual Pads**: Trigger audio clips and background music on the fly during recording sessions.
- 📝 **Live Speech-to-Text Transcription**: Real-time STT engine for transcription monitoring without cloud dependencies.
- 📜 **Integrated Teleprompter**: Clean, adjustable teleprompter built directly into the web planner.
- 🔒 **100% Local-First & Zero-Egress**: Your voice, video, and planning notes never leave your personal machine.

---

<a id="ui-preview--screenshots"></a>
## UI Preview & Screenshots

![Klangpult light – Recorder](README/screenshots/main.png)

---

<a id="klangpult-light--planer-quickstart"></a>
## Klangpult light – Planer Quickstart

```powershell
# Simplest launch (Klangpult light – Recorder should be running)
.\START_PLANER.bat

# Or manual execution:
$env:PYTHONIOENCODING = "utf-8"
python planer/start.py

# Browser opens automatically on http://127.0.0.1:8770
# Configurable ports via environment variables:
#   PLANER_PORT=8770  LIBRARY_PORT=8767  PROJECTS_PORT=8769
```

The Planer connects to the running Recorder via the IPC Bridge on ports `8767` and `8769`.
If the Recorder is not running, the Planer functions in standalone mode for offline project and episode management.

---

<a id="klangpult-light--recorder-quickstart"></a>
## Klangpult light – Recorder Quickstart

```powershell
# Simplest launch
.\START_RECORDER.bat

# If prebuilt standalone executable exists:
.\KlangpultLightRecorder.exe

# Setup virtual environment:
python -m venv C:\_Local_DEV\venvs\podcast_packages
C:\_Local_DEV\venvs\podcast_packages\Scripts\activate
pip install -r Recorder\requirements.txt

# Start Desktop Application:
cd Recorder
$env:PYTHONIOENCODING = "utf-8"
python main.py

# Headless Self-Test (no GUI window):
$env:PODCAST_RECORDER_SELFTEST = "1"
$env:PYTHONIOENCODING = "utf-8"
python main.py

# Run Test Suite:
$env:PYTHONIOENCODING = "utf-8"
pytest
```

---

<a id="build-standalone-executable"></a>
## Build Standalone Executable

```powershell
$env:PYTHONIOENCODING = "utf-8"
.\build_exe.bat
```

The build script packages a single-file executable at the project root (`KlangpultLightRecorder.exe`), a build copy in `Recorder\dist\`, and a versioned release artifact under `releases\v0.1.0\`.

---

<a id="sibling-tools--ecosystem-matrix"></a>
## Sibling Tools & Ecosystem Matrix

Klangpult light is an integral member of the **entertain-and-more** suite and the broader **open-bricks** developer network:

| Project | Organization | Focus / Category | Status |
|---|---|---|---|
| [BattleStage](https://github.com/entertain-and-more/BattleStage) | entertain-and-more | Server-Authoritative 2D/3D Platform Fighter | Active |
| [ChainReaction](https://github.com/entertain-and-more/ChainReaction) | entertain-and-more | Dynamic Puzzle & Physics Reaction Game | Active |
| [StreetRacer](https://github.com/entertain-and-more/StreetRacer) | entertain-and-more | High-Speed Arcade Racing Game | Active |
| [RealmWars](https://github.com/entertain-and-more/RealmWars) | entertain-and-more | Tactical Strategy & Kingdom Defense | Active |
| [GhostTrain](https://github.com/entertain-and-more/GhostTrain) | entertain-and-more | Atmospheric Adventure & Mystery | Active |
| [RescueMe](https://github.com/entertain-and-more/RescueMe) | entertain-and-more | Fast-Paced Emergency Simulation | Active |
| [HauntedHouse](https://github.com/entertain-and-more/HauntedHouse) | entertain-and-more | Interactive Horror & Exploration | Active |
| [MafiaCastle](https://github.com/entertain-and-more/MafiaCastle) | entertain-and-more | Multiplayer Social Deduction | Active |
| [CuteStrike](https://github.com/entertain-and-more/CuteStrike) | entertain-and-more | Whimsical Family Action Arena | Active |
| [BattleChess3D](https://github.com/entertain-and-more/BattleChess3D) | entertain-and-more | Animated 3D Chess Tactics | Active |
| [system-auditor](https://github.com/ellmos-ai/system-auditor) | ellmos-ai | Local-first System Audit & Health Verifier | Active |
| [automation-master](https://github.com/dev-bricks/automation-master) | dev-bricks | Event-Sourced Automation Governance | Active |
| [ExplorerPro](https://github.com/file-bricks/ExplorerPro) | file-bricks | High-Performance Native File Explorer | Active |
| [CleanMarkdown](https://github.com/doc-bricks/CleanMarkdown) | doc-bricks | Deterministic Markdown Sanitization | Active |
| [ellmos-voice-io](https://github.com/ellmos-ai/ellmos-voice-io) | ellmos-ai | Zero-Egress Audio & Speech Engine Foundation | Active |
| [WikiStub-Seed](https://github.com/dev-bricks/WikiStub-Seed) | dev-bricks | Multilingual Offline Knowledge Seeds | Active |
| [open-bricks](https://github.com/open-bricks/open-bricks) | open-bricks | Umbrella Open Architecture Hub | Active |

---

<a id="feature-comparison-light-vs-full-edition"></a>
## Feature Comparison: Light vs. Full Edition

| Feature | Klangpult light (Freeware) | Klangpult (Full Suite) |
|---|:---:|:---:|
| Multichannel Audio Recording | ✅ | ✅ |
| System Loopback Audio Capture | ✅ | ✅ |
| Synchronized Video Capture | ✅ | ✅ |
| Soundboard & Visual Media Pads | ✅ | ✅ |
| Live Speech-to-Text Monitor | ✅ | ✅ |
| Web Planer & Teleprompter | ✅ | ✅ |
| Automated Multichannel Cutter | ❌ | ✅ |
| Batch Transcription Export (SRT/TXT) | ❌ | ✅ |
| Automated OCR Video Scanner | ❌ | ✅ |
| Advanced Postproduction Mastering | ❌ | ✅ |

Concept: [KONZEPT.md](./KONZEPT.md) · Roadmap: [TODO.md](./TODO.md) · Changelog: [CHANGELOG.md](./CHANGELOG.md)

---

<a id="validation--verification-gates"></a>
## Validation & Verification Gates

Quality, performance, and contract compliance are enforced through automated verification gates:

```powershell
# 1. Metadata and Structural Contract Verification
$env:PYTHONIOENCODING = "utf-8"
pytest tests/test_metadata.py

# 2. Planer Static and Accessibility Verification
pytest tests/test_planer_accessibility_static.py

# 3. Core Engine and Desktop Recorder Test Suite (440 tests)
pytest Recorder/tests/

# 4. Full Pytest Suite (450 tests: 449 passed, 1 skipped)
pytest

# 5. Code Style and Linter Check
ruff check .

# 6. Bytecode Compilation Gate
python -m compileall -q .

# 7. Headless Desktop Recorder Self-Test
$env:PODCAST_RECORDER_SELFTEST = "1"
python Recorder/main.py

# 8. Git Diff & Whitespace Verification
git diff --check
```

---

<a id="security-policy--triage-sla"></a>
## Security Policy & Triage SLA

We maintain strict security guarantees:

- **Zero Cloud Egress**: Recordings and project data are never uploaded to any remote service.
- **Loopback Isolation**: Local network communication is strictly bound to `127.0.0.1`.
- **48-Hour Response SLA**: Receipt confirmed within 48 hours for all vulnerability reports.
- **5-Business-Day Triage SLA**: Formal triage evaluation delivered within 5 business days.
- **Security Contacts**: [security@open-bricks.org](mailto:security@open-bricks.org), [security@ellmos.ai](mailto:security@ellmos.ai), and [support@lukasgeiger.com](mailto:support@lukasgeiger.com).
- **GitHub Security Advisories**: Report privately via [GitHub Security Advisories](https://github.com/entertain-and-more/KlangpultLight/security/advisories/new).
- **Bilingual Security Policy**: Review [SECURITY.md](./SECURITY.md) for full disclosure procedures.

---

<a id="license--author"></a>
## License & Author

Klangpult light is released as **Freeware / Closed-Source Proprietary**. See [LICENSE](./LICENSE) for full terms.<br>
Copyright (c) 2026 Lukas Geiger. All rights reserved.
