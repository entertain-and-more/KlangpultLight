# Klangpult light – Planer (Installierbare Local-First Web-App & Companion-PWA)

[English (`README.md`)](./README.md) · [Portierungsplan (`../PORTIERUNGSPLAN.md`)](../PORTIERUNGSPLAN.md)

**Version:** `0.1.0` · **Lizenz:** Freeware (`Proprietary / Freeware`) · **Architektur:** 100 % Local-First & Zero-Egress (`INV-LOCAL-01`)

---

## 1. Überblick & Einsatzzweck

`Klangpult light – Planer` (`planer/`) ist die browserbasierte Planungs-, Bibliotheks-, Einspieler-Line-, Teleprompter- und KI-Monitor-Anwendung zu `Klangpult light – Recorder`.

Der Planer ist als **installierbare Progressive Web App (PWA)** (`manifest.json` + `sw.js`) ausgelegt und deckt zwei zentrale Einsatzszenarien ab:
- **Desktop-App-Fenster** (Edge, Chrome, Chromium, Firefox/Safari unter Windows, macOS und Linux),
- **Tablet- & Smartphone-Companion im Studio-LAN** (iPadOS / iOS „Zum Home-Bildschirm“ sowie Android-PWA-Installation) als kabelloser **Zweitbildschirm-Teleprompter**, **Touch-Soundboard-Fernbedienung** und **Live-Transkriptions-Monitor**.

Gemäß `PUBLICATION-POLICY.md` §2 (`Regel b`, `Regel c`, `Regel e2`, `Regel g`, `Regel h` — Faktentreue statt Scheinfunktionen) trennt der Planer transparent zwischen lokal gecachter App-Shell und aktiver Recorder-Kopplung:

| Funktion | Offline-App-Shell (`sw.js`) | Lokaler Planer-Server (`start.py`) | Gekoppelt mit Desktop-Recorder (`BridgeService`) |
| --- | :---: | :---: | :---: |
| UI-Shell, Dark-Styles & 6-Sprachen-Wörterbuch laden | Ja | Ja | Ja |
| Ehrliche Verbindungsanzeige (`online` / `partial` / `offline`) | Ja | Ja | Ja |
| Aufnahmebibliothek & Branch-Wiedergabe (`/api/library`) | Ehrlicher Offline-Status (`503`) | Proxy bei laufendem Recorder | Ja (Port `8767` auf `127.0.0.1`) |
| Projekte, Episoden, Assets, Line & Workspace-v1 (`/api/projects`) | Ehrlicher Offline-Status (`503`) | Proxy bei laufendem Recorder | Ja (Port `8769` auf `127.0.0.1`) |
| Live-Pegel, Pad-Trigger, Kapitelmarker & STT-Stream (`ws://...:8768`) | Getrennt-Status | Verbindet bei Recorder-Start | Ja (Port `8768`) |

> **Architekturgrenze:** Latenzkritische Mehrkanal-Audio- und Videoaufnahmen (`WASAPI`, `CoreAudio`, `ALSA`/`PipeWire`, `OpenCV`, `mss`, `FFmpeg`) laufen ausschließlich im nativen Desktop-`Recorder`-Prozess und werden niemals im Browser simuliert (`Regel e2`).

---

## 2. Betriebsmodi & Schnellstart

### Modus A — Ein-Klick-Kopplung über den Desktop-Recorder (Standard)

Beim Start von `Klangpult light – Recorder` (`START.bat` oder `python Recorder/main.py`) startet `BridgeService` den `PlanerServer` automatisch auf `http://127.0.0.1:8770` sowie den `RemoteWsServer` auf `ws://127.0.0.1:8768` und leitet `/api/library/*` (`127.0.0.1:8767`) sowie `/api/projects/*` (`127.0.0.1:8769`) am selben Ursprung (Same-Origin ohne CORS-Hürden) weiter.

Klicke im Recorder auf **„🌐 Planer im Browser öffnen“** (`Strg+P`) oder rufe folgende Adresse auf:

```text
http://127.0.0.1:8770
```

### Modus B — Eigenständiger Planer-Server

Für den separaten Start des Planer-Webservers (z. B. zur Vorab-Planung oder während eines Recorder-Neustarts):

```bash
python planer/start.py
```

Optionale Umgebungsvariablen (Standard bleibt strikt auf lokalem Loopback `127.0.0.1`):

| Variable | Standard | Bedeutung |
| --- | --- | --- |
| `PLANER_HOST` | `127.0.0.1` | Bind-Adresse für `PlanerServer` (`8770`) und beim Start über `Recorder/main.py` synchron auch für `RemoteWsServer` (`8768`). Optional separat überschreibbar per `PODCAST_RECORDER_COMPANION_HOST`. Die internen REST-Server (`8767`, `8769`) bleiben stets strikt auf `127.0.0.1` isoliert. |
| `PLANER_PORT` | `8770` | HTTP-Port der Planer-Web-App und des API-Proxys |
| `LIBRARY_PORT` | `8767` | Lokaler Port des `LibraryApiServer` auf `127.0.0.1` |
| `PROJECTS_PORT` | `8769` | Lokaler Port des `ProjectsApiServer` auf `127.0.0.1` |

### Modus C — Tablet- / Smartphone-Companion im Studio-LAN (Opt-in)

1. Starte im vertrauenswürdigen lokalen Studio-Netzwerk den Desktop-Recorder mit gesetzter `PLANER_HOST`-Adresse (z. B. `PLANER_HOST=192.168.178.25 python Recorder/main.py` bzw. in PowerShell `$env:PLANER_HOST='192.168.178.25'; python Recorder/main.py`).
2. `BridgeService` bindet dadurch sowohl `PlanerServer` (`http://192.168.178.25:8770`) als auch `RemoteWsServer` (`ws://192.168.178.25:8768`) an die Studio-LAN-Schnittstelle, während `LibraryApiServer` (`8767`) und `ProjectsApiServer` (`8769`) geschützt auf `127.0.0.1` hinter dem Same-Origin-Proxy bleiben.
3. Öffne auf dem Tablet oder Smartphone `http://<STUDIO-LAN-IP>:8770` (optional mit `?ws_port=8768`). `planer/app/remote.js` (`resolveDefaultWsUrl`) verbindet automatisch zu `ws://<STUDIO-LAN-IP>:8768`, während auf dem Desktop unverändert `ws://127.0.0.1:8768` genutzt wird.
4. Optional: Über „App installieren“ bzw. „Zum Home-Bildschirm hinzufügen“ als rahmenlose Vollbild-App für den Teleprompter- und Soundboard-Pad-Einsatz ablegen.

> **Hinweis zu Browser-Sicherheitskontexten:** Browser aktivieren Service Worker (`sw.js`) unter `http://127.0.0.1`, `http://localhost` und `https://`. Bei unverschlüsseltem `http://<LAN-IP>` überspringt `planer/app/pwa.js` die Service-Worker-Registrierung kontrolliert ohne Konsolenfehler; Live-WebSocket und REST-API arbeiten uneingeschränkt.

---

## 3. PWA-Manifest, Allowlist-Icons & Zero-Egress-Caching

- **Web-App-Manifest (`planer/manifest.json`):** Deklariert `display: "standalone"`, das dunkle Studio-Theme `#2b3142` sowie Standard- und Maskable-Icons (`192x192` und `512x512`).
- **Duplikatfreie Icon-Auslieferung:** `PlanerServer` liefert `/icon-192.png`, `/icon-512.png`, `/icon-maskable-192.png`, `/icon-maskable-512.png` und `/apple-touch-icon-180.png` schreibgeschützt aus dem kanonischen Verzeichnis `mobile_icons/` über eine strikte Dateinamen-Allowlist aus (kein Path-Traversal, keine kopierten Binärdateien).
- **Offline-Service-Worker (`planer/sw.js`):**
  - Strikt Same-Origin (`url.origin === self.location.origin`) und ausschließlich `GET` — keinerlei externe Netzwerkaufrufe (`INV-LOCAL-01`).
  - Hält die statische App-Shell (`index.html`, `styles/main.css`, `app/*.js`, Icons und `/locales/translations.json`) im lokalen Cache bereit.
  - Nutzt **Network-First** für `/api/*`, damit niemals veraltete Bibliotheks- oder Projektdaten vorgetäuscht werden; bei gestopptem Backend antwortet der Worker ehrlich mit strukturiertem Offline-JSON (`status: "offline"` bzw. HTTP `503`).

---

## 4. Tier-2-Mehrsprachigkeit (Policy P-006)

Der Planer unterstützt ab Werk alle **6 Tier-2-Sprachen** inklusive Live-Umschaltung (`localStorage`-Schlüssel `klangpult_planer_lang`), Synchronisierung von `<html lang="...">` und deterministischer Fallback-Kette (`target -> en -> de -> key`):

- `de` — Deutsch
- `en` — English
- `es` — Español
- `zh` — 简体中文
- `ja` — 日本語
- `ru` — Русский

---

## 5. Verifikation & Tests

Node.js-ESM-Tests für PWA-Registrierung, LAN-WebSocket-Auflösung, Manifest-Parität und I18N ausführen:

```bash
node --test planer/tests/pwa.test.mjs
```

Python-Vertragstests für Server-Routing, Allowlist-Icons, Barrierefreiheit und Multi-Target-Gates ausführen:

```bash
python -m pytest -q tests/test_multitarget_porting_and_pwa.py tests/test_planer_i18n.py Recorder/tests/test_planer_a11y.py
```
