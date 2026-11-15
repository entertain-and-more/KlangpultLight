# Klangpult light – Planner (Installable Local-First Web-App & Companion PWA)

[Deutsch (`README_de.md`)](./README_de.md) · [Porting Plan (`../PORTIERUNGSPLAN.md`)](../PORTIERUNGSPLAN.md)

**Version:** `0.1.0` · **License:** Freeware (`Proprietary / Freeware`) · **Architecture:** 100% Local-First & Zero-Egress (`INV-LOCAL-01`)

---

## 1. Overview & Purpose

`Klangpult light – Planner` (`planer/`) is the browser-based planning, library, soundboard-line, teleprompter, and live AI-monitor companion for `Klangpult light – Recorder`.

It is packaged as an **installable Progressive Web App (PWA)** (`manifest.json` + `sw.js`) so creators can install it onto:
- **Desktop browsers** (Edge, Chrome, Chromium, Firefox/Safari web views on Windows, macOS, and Linux),
- **Tablets and smartphones** (iPadOS / iOS "Add to Home Screen", Android Chrome PWA install) as a second-screen **Teleprompter**, **Soundboard Pad Remote**, and **Live Transcript Monitor** on the local studio network.

In strict conformance with `PUBLICATION-POLICY.md` §2 (`Regel b`, `Regel c`, `Regel e2`, `Regel g`, `Regel h`), the Planner communicates honestly about what works standalone offline versus what requires a running desktop Recorder instance:

| Capability | Offline App-Shell (`sw.js`) | Local Planner Server (`start.py`) | Coupled with Desktop Recorder (`BridgeService`) |
| --- | :---: | :---: | :---: |
| Load UI shell, CSS, and 6-language i18n dictionary | Yes | Yes | Yes |
| Honest connection badge (`online` / `partial` / `offline`) | Yes | Yes | Yes |
| Recording Library & Branch Playback (`/api/library`) | Offline notice (`503`) | Proxied when Recorder runs | Yes (Port `8767` on `127.0.0.1`) |
| Projects, Episodes, Assets, Line & Workspace-v1 (`/api/projects`) | Offline notice (`503`) | Proxied when Recorder runs | Yes (Port `8769` on `127.0.0.1`) |
| Live Peaks, Pad Trigger, Chapter Markers & STT Stream (`ws://...:8768`) | Disconnected state | Connects when Recorder runs | Yes (Port `8768`) |

> **Scope Boundary:** Low-latency multi-channel hardware audio/video capture (`WASAPI`, `CoreAudio`, `ALSA`/`PipeWire`, `OpenCV`, `mss`, `FFmpeg`) runs exclusively in the desktop `Recorder` process — never inside browser tabs (`Regel e2`).

---

## 2. Operating Modes & Quickstart

### Mode A — One-Click Coupled Start via Desktop Recorder (Default)

When `Klangpult light – Recorder` starts (`START.bat` or `python Recorder/main.py`), `BridgeService` automatically launches `PlanerServer` on `http://127.0.0.1:8770` and `RemoteWsServer` on `ws://127.0.0.1:8768`, while proxying `/api/library/*` (`127.0.0.1:8767`) and `/api/projects/*` (`127.0.0.1:8769`) on the same origin.

Click **"Open Planner in Browser"** (`Ctrl+P`) inside the Recorder or open:

```text
http://127.0.0.1:8770
```

### Mode B — Standalone Planner Server

To start the Planner HTTP server independently (for UI inspection or while restarting the Recorder):

```bash
python planer/start.py
```

Environment variables (all optional, defaults preserve strict `127.0.0.1` loopback):

| Variable | Default | Purpose |
| --- | --- | --- |
| `PLANER_HOST` | `127.0.0.1` | Bind address for `PlanerServer` (`8770`) and, when starting `Recorder/main.py`, also for `RemoteWsServer` (`8768`). Override via `PODCAST_RECORDER_COMPANION_HOST` if needed. Internal REST servers (`8767`, `8769`) always remain bound strictly to `127.0.0.1`. |
| `PLANER_PORT` | `8770` | HTTP port for static PWA shell and same-origin API proxy |
| `LIBRARY_PORT` | `8767` | Upstream `LibraryApiServer` port on `127.0.0.1` |
| `PROJECTS_PORT` | `8769` | Upstream `ProjectsApiServer` port on `127.0.0.1` |

### Mode C — Tablet / Mobile Studio-LAN Companion (Opt-In)

1. Inside a trusted local studio network, start the Desktop Recorder with `PLANER_HOST` set to your studio machine's LAN IP (for example `PLANER_HOST=192.168.178.25 python Recorder/main.py`, or `PODCAST_RECORDER_COMPANION_HOST=192.168.178.25`).
2. `BridgeService` binds both `PlanerServer` (`http://192.168.178.25:8770`) and `RemoteWsServer` (`ws://192.168.178.25:8768`) to that interface, while keeping `LibraryApiServer` (`8767`) and `ProjectsApiServer` (`8769`) isolated on `127.0.0.1` behind the same-origin HTTP proxy.
3. Open `http://<STUDIO-LAN-IP>:8770` (or `http://<STUDIO-LAN-IP>:8770/?ws_port=8768`) on your tablet or smartphone. `planer/app/remote.js` (`resolveDefaultWsUrl`) automatically connects to `ws://<STUDIO-LAN-IP>:8768`, while keeping `ws://127.0.0.1:8768` as the default on desktop loopback.
4. Optional: Install as a standalone home-screen app for full-screen teleprompter and touch soundboard pad operation.

> **Browser Security Note for Service Workers:** Browsers activate Service Workers (`sw.js`) on `http://127.0.0.1`, `http://localhost`, and `https://` origins. Over plain `http://<LAN-IP>`, `planer/app/pwa.js` cleanly skips Service Worker registration without errors while keeping full live WebSocket and REST functionality active.

---

## 3. PWA Manifest, Allowlisted Icons & Zero-Egress Caching

- **Web App Manifest (`planer/manifest.json`):** Declares `display: "standalone"`, dark studio theme `#2b3142`, and standard + maskable icons (`192x192` and `512x512`).
- **Single-Source Icon Serving:** `PlanerServer` serves `/icon-192.png`, `/icon-512.png`, `/icon-maskable-192.png`, `/icon-maskable-512.png`, and `/apple-touch-icon-180.png` read-only from the repository's canonical `mobile_icons/` directory via a strict filename allowlist (no path traversal, no duplicated icon binaries).
- **Offline Service Worker (`planer/sw.js`):**
  - Strictly same-origin (`url.origin === self.location.origin`) and `GET`-only — zero external network calls (`INV-LOCAL-01`).
  - Pre-caches the static App-Shell (`index.html`, `styles/main.css`, `app/*.js`, icons, and `/locales/translations.json`).
  - Uses **Network-First** for `/api/*` so live recordings and project edits are never masked by stale cache entries; returns structured offline JSON (`status: "offline"` / HTTP `503`) if the local server is stopped.

---

## 4. Tier-2 Multilingual Support (Policy P-006)

The Planner supports all **6 Tier-2 languages** out of the box with live switching (`localStorage` key `klangpult_planer_lang`), `<html lang="...">` synchronization, and deterministic fallback (`target -> en -> de -> key`):

- `de` — Deutsch
- `en` — English
- `es` — Español
- `zh` — 简体中文
- `ja` — 日本語
- `ru` — Русский

---

## 5. Verification & Tests

Run the Node.js ESM PWA & companion unit tests:

```bash
node --test planer/tests/pwa.test.mjs
```

Run the Python server, i18n, A11y, and multi-target contract tests:

```bash
python -m pytest -q tests/test_multitarget_porting_and_pwa.py tests/test_planer_i18n.py Recorder/tests/test_planer_a11y.py
```
