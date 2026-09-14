# Third-Party Licenses & Transparency Notice

> **Project:** `entertain-and-more/KlangpultLight` (Klangpult light — Desktop & Web Media Workstation)<br>
> **Audited:** 2026-09-14<br>
> **Repository License:** [Freeware / Proprietary License](LICENSE)<br>
> **Architecture & Privacy:** 100% Local-First, Zero-Egress by default, Unprivileged User-Mode (`RunAsInvoker`)

---

## Executive Summary & Compliance Assurance

Klangpult light is a lightweight, local-first audio/video recording workstation and content planning suite. The application distribution is licensed under the [Klangpult light Freeware License Agreement](LICENSE).

All runtime and development dependencies utilized in Klangpult light are distributed under recognized, permissive and free open-source licenses (MIT, BSD-3-Clause, Apache-2.0, PSFL, LGPL-3.0, LGPL-2.1).

- **PySide6 (Qt6 Python bindings)** is licensed under **LGPL-3.0**. PySide6 is utilized exclusively via dynamic linking (standard PyPI distribution / shared objects). No modifications to the Qt or PySide6 libraries are made. In full compliance with **LGPLv3 Section 4**, users and downstream developers are free to inspect, replace, and dynamically relink the Qt/PySide6 binaries.
- **Zero-Copyleft Contagion:** User recordings (WAV, MP4), soundboard audio assets, teleprompter scripts, episode planning databases, and metadata logs remain 100% proprietary to the creator and are never subject to copyleft or relicensing.
- **FFmpeg Subprocess Isolation:** FFmpeg binaries are invoked strictly as external, isolated command-line subprocesses with explicit argument arrays. They are not statically or dynamically linked into the Python process address space.
- **Zero Egress & Unprivileged Execution:** Klangpult light executes with standard user privileges (`RunAsInvoker`) without requiring administrative elevation and performs zero outbound network requests across WAN/LAN.

Furthermore, Klangpult light affirms the ten governance and runtime invariants:
1. **INV-LOCAL-01 (100% Local-First & Zero-Egress):** Audio, video, transcriptions, and planning data remain strictly on the local machine. Zero analytics, telemetry, or outbound network calls.
2. **INV-USER-02 (Unprivileged Execution & Non-Elevation):** Operates under strict `RunAsInvoker` security without requiring administrator privileges or root access.
3. **INV-IPC-03 (Strict Loopback IPC Isolation):** IPC between PySide6 Recorder and HTTP Web Planer is bound exclusively to `127.0.0.1` (ports `8767`, `8769`, `8770`).
4. **INV-SAFE-04 (Safe Subprocess Boundaries):** FFmpeg remuxing and video capture subprocesses use explicit argument vectors (non-shell) and path traversal sanitization.
5. **INV-BUF-05 (Bounded Buffer & Audio Integrity):** Multichannel audio buffers sanitize against NaN/Inf float samples and flush atomically to standard WAV containers.
6. **INV-STT-06 (Offline STT Degradation Boundary):** Local `faster-whisper` transcription operates in an isolated worker thread with graceful fallback if weights are missing; never stalls real-time recording or UI rendering.
7. **INV-STORE-07 (Caller-Controlled Session Storage):** Session folders, event logs (`events.jsonl`), and recordings are owned and retained exclusively by the creator with zero auto-purge.
8. **INV-PLAT-08 (Cross-Platform Operating Parity):** Architecture, protocol schemas (`v1`), and data models run consistently across Windows, Linux, and macOS.
9. **INV-SYNC-09 (Multi-Host & Sync Resilience):** `.gitignore` rigorously ignores conflict copies (`*-conflict-*`, `*.sync-temp-*`) and multi-agent locks (`LOCK.*`, `*.lock`).
10. **INV-SLA-10 (48h Response & 5-Day Triage SLA):** Formal commitment to 48-hour response / 5-day triage SLA, validated by automated GitHub Actions CI matrices across Ubuntu, Windows, and macOS on Python 3.10, 3.11, 3.12, and 3.13.

---

## Runtime Dependency Matrix

| Package | Version Range | Role / Functional Scope | License | Project Repository / Upstream | Compliance Mechanism |
|:---|:---|:---|:---|:---|:---|
| **Python Standard Library** | 3.10+ | Core desktop application, dataclass models, JSON serialization, SQLite persistence, HTTP server | [PSFL-2.0](https://docs.python.org/3/license.html) | [python/cpython](https://github.com/python/cpython) | Standard library distribution |
| **PySide6** | >=6.6 | Desktop GUI framework (Qt6), widgets, media player, multi-monitor display | [LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.html) | [Qt Project / PySide6](https://code.qt.io/cgit/pyside/pyside-setup.git/) | Dynamic linking (LGPLv3 §4), unprivileged user-mode |
| **sounddevice** | >=0.4.6 | Low-latency audio input/output streaming, WASAPI loopback capture | [MIT](https://github.com/spatialaudio/python-sounddevice/blob/master/LICENSE) | [spatialaudio/python-sounddevice](https://github.com/spatialaudio/python-sounddevice) | Dynamic linking via PortAudio |
| **numpy** | >=1.26 | Fast numerical vector buffers, volume metering, audio sanitization | [BSD-3-Clause](https://github.com/numpy/numpy/blob/main/LICENSE.txt) | [numpy/numpy](https://github.com/numpy/numpy) | Standard package import |
| **soundfile** | >=0.12 | Audio file decoding and encoding (libsndfile wrapper) | [BSD-3-Clause](https://github.com/bastibe/python-soundfile/blob/master/LICENSE) | [bastibe/python-soundfile](https://github.com/bastibe/python-soundfile) | Dynamic linking via libsndfile |
| **opencv-python** | >=4.9 | Optional camera frame acquisition and video stream decoding | [Apache-2.0](https://github.com/opencv/opencv-python/blob/master/LICENSE.txt) | [opencv/opencv-python](https://github.com/opencv/opencv-python) | Dynamic import |
| **mss** | >=9.0 | Ultra-fast screen capture for video recording | [MIT](https://github.com/BoboTiG/python-mss/blob/master/LICENSE.txt) | [BoboTiG/python-mss](https://github.com/BoboTiG/python-mss) | Standard package import |
| **websockets** | >=12.0 | Local loopback WebSocket communication for live audio and state streaming | [BSD-3-Clause](https://github.com/python-websockets/websockets/blob/main/LICENSE) | [python-websockets/websockets](https://github.com/python-websockets/websockets) | Standard package import |
| **jsonschema** | >=4.21 | Schema validation for events, config files, and API contracts | [MIT](https://github.com/python-jsonschema/jsonschema/blob/main/COPYING) | [python-jsonschema/jsonschema](https://github.com/python-jsonschema/jsonschema) | Standard package import |
| **faster-whisper** | Optional | Optional local speech-to-text transcription engine | [MIT](https://github.com/SYSTRAN/faster-whisper/blob/master/LICENSE) | [SYSTRAN/faster-whisper](https://github.com/SYSTRAN/faster-whisper) | Optional offline STT worker |
| **FFmpeg** | Binary CLI | External muxer for video/audio remuxing to standard MP4 | [LGPL-2.1+ / GPL-2.0+](https://ffmpeg.org/legal.html) | [FFmpeg/FFmpeg](https://ffmpeg.org/) | Isolated command-line subprocess boundary |

---

## Development & Quality Assurance Tooling

| Package | Usage & Purpose | License | Source / Upstream |
|:---|:---|:---|:---|
| **pytest** | Automated test runner, contract verification suites, mock fixtures | [MIT](https://github.com/pytest-dev/pytest/blob/main/LICENSE) | [pytest-dev/pytest](https://github.com/pytest-dev/pytest) |
| **ruff** | High-performance Python linter and code formatting enforcement | [MIT / Apache-2.0](https://github.com/astral-sh/ruff/blob/main/LICENSE-MIT) | [astral-sh/ruff](https://github.com/astral-sh/ruff) |
| **setuptools** | Standard package build backend (PEP 517 / PEP 621 compliant) | [MIT](https://github.com/pypa/setuptools/blob/main/LICENSE) | [pypa/setuptools](https://github.com/pypa/setuptools) |
| **PyInstaller** | Executable packaging (`KlangpultLightRecorder.spec`, `KlangpultLightRecorderOnedir.spec`) | [GPL-2.0 with Bootloader Exception](https://pyinstaller.org/) | [pyinstaller/pyinstaller](https://github.com/pyinstaller/pyinstaller) |

---

## LGPL Dynamic Linking Compliance Statement

PySide6 is distributed under the GNU Lesser General Public License Version 3 (LGPL-3.0). Klangpult light complies with LGPLv3 Section 4:
1. Klangpult light links dynamically to unmodified PySide6 shared libraries distributed by the official Python Package Index (PyPI).
2. Users are entitled to inspect, modify, and replace the PySide6 shared libraries in their Python virtual environment or system installation.
3. No proprietary modifications to Qt/PySide6 are included or distributed by this repository.

---

## Full License Texts (Excerpts & Notices)

### 1. Python Software Foundation License Version 2 (PSFL-2.0)
Python standard library modules are used under the PSF License Agreement.  
Copyright (c) 2001-2026 Python Software Foundation. All rights reserved.

### 2. MIT License (MIT)
Used for `sounddevice`, `mss`, `jsonschema`, `faster-whisper`, `pytest`, `ruff`, and `setuptools`.

> Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:  
>  
> The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.  
>  
> THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### 3. BSD 3-Clause License (BSD-3-Clause)
Used for `numpy`, `soundfile`, and `websockets`.

> Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:  
> 1. Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer.  
> 2. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.  
> 3. Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission.

### 4. GNU Lesser General Public License Version 3 (LGPL-3.0)
Applies to PySide6.  
Complete terms: https://www.gnu.org/licenses/lgpl-3.0.html

### 5. Apache License Version 2.0 (Apache-2.0)
Applies to `opencv-python` and co-licensed by `ruff`.  
Complete terms: https://www.apache.org/licenses/LICENSE-2.0
