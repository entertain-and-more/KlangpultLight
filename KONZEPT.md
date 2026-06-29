# KONZEPT.md — Klangpult light

**Version:** 0.1.0 (Konzept) · **Datum:** 2026-06-17 · **Autor:** Lukas Geiger (+ Claude)

> **Klangpult light** ist die kostenlose Freeware-Version (Funnel). Gegenstück: Klangpult (proprietäre Vollversion, kostenpflichtig).
> Lizenz: Proprietär/Freeware, Closed-Source. Kein öffentliches GitHub-Repo.

> **Kurzfassung:** Das `DEV_USBPodcastStudio` ist mächtig, aber komplex geworden und wird oft nur
> in Teilen gebraucht. `Klangpult light` zerlegt es in **zwei schlanke, eigenständige Tools**, die
> je einen klaren Zweck erfüllen und unabhängig voneinander gestartet werden können:
>
> 1. **Klangpult light – Recorder** — Desktop-App: aufnehmen (Audio + Video + gemeinsames Board, Aufnahmen mit Branches).
> 2. **Klangpult light – Planer** — Web-App: planen (Bibliothek, Projektplanung, Assets/Line, KI-Monitor, Teleprompter).
>
> **Bewusst weggelassen:** Postproduction, Cutter, Transkription (siehe „Abgrenzung").

---

## 1. Warum zwei getrennte Tools?

Das Studio bündelt 9+ Tabs (Mixer, Boards, Video, Aufnahmen, Cutter, Export, Transkripte, KI-Monitor,
Teleprompter, Theme-Editor …) in einer einzigen App. Das ist viel Oberfläche für Sessions, in denen
man eigentlich nur **aufnehmen** oder nur **planen** will.

Die Trennung folgt dem natürlichen Arbeitsablauf:

| Phase | Tool | Wann |
|---|---|---|
| **Vorbereitung** | Klangpult light – Planer (Web) | vor der Aufnahme — Themen, Ablauf, Assets, Teleprompter-Text, Monitor-Briefing |
| **Aufnahme** | Klangpult light – Recorder (Desktop) | während der Aufnahme — Quellen mischen, Board spielen, mitschneiden |
| **Live-Unterstützung** | Planer ↔ Recorder gekoppelt | Teleprompter & KI-Monitor laufen im Planer (Web), gesteuert/gespeist vom Recorder |

Jedes Tool ist **alleine lauffähig**. Die Kopplung ist optional und additiv.

---

## 2. Architektur-Entscheidungen (festgelegt)

### 2.1 Recorder = Desktop-App, Planer = Web-App

**Begründung (technische Realität, nicht Geschmack):**

- **Recorder bleibt Desktop (Python/PySide6).** Mehr-Geräte-Aufnahme (zwei+ USB-Mikrofone gleichzeitig),
  System-/Loopback-Mitschnitt und niedrige Latenz beim Mischen sind im Browser **nicht zuverlässig**
  möglich. Eine Web-Variante würde die Kernfunktion verschlechtern → bleibt App.
- **Planer wird Web-App.** Bibliothek, Projektplanung, Asset-/Line-Listen, Teleprompter-Text und
  KI-Monitor sind daten- und textlastig — genau hier gewinnt modernes Web-Design (Responsiveness,
  Touch, schnelleres UI-Tuning, vom Sofa/Tablet aus nutzbar).

### 2.2 Eigenständig, kein gemeinsamer Studio-Core

Beide Tools sind **unabhängig vom Studio**. Es wird **kein** gemeinsamer Kern aus `DEV_USBPodcastStudio`
herausrefaktoriert (das Studio bleibt unangetastet). Stattdessen: **pragmatisch das Bewährte kopieren**
(z. B. die `sounddevice`-Aufnahme-Engine, `device_manager`, das Recordings-/Branch-Datenmodell) und
**neu schreiben, wo es schlanker geht** (UI, Board, Web-Frontend). Maßgabe: **die Features der genannten
Studio-Tabs sind die Zielmarke und müssen erreicht werden** (siehe Feature-Mapping, Abschnitt 6).

### 2.3 Kopplung: lokaler Dienst + gemeinsamer Workspace

Der Planer ist **kein reines Static-Frontend**. Damit die Bibliothek alle Aufnahmen + Branch-Baum
**automatisch** listen kann und Pläne persistiert werden, spricht der Planer einen **lokalen Dienst** an —
am sinnvollsten denselben, den der Recorder ohnehin für die Live-Bridge exponiert.

- **Gemeinsamer Workspace-Ordner** (lokal, konfigurierbar): Recorder schreibt Aufnahmen/Metadaten hinein,
  Planer liest/listet sie und legt Pläne/Teleprompter-Texte daneben.
- **Austauschformate (aus dem Studio übernommen, da bereits spezifiziert):**
  - `klangpultlight-workspace-v1` (JSON-Payload) — **Plan → Recorder** (Soundboard-Pads, Teleprompter-Text).
  - `remote_protocol_v1` (WebSocket) — **Live**, Recorder ↔ Planer (Pegel, Prompter-Zeile, Pad-Trigger,
    Aufnahme-Status, Kapitelmarker, **Live-Transkriptions-Chunks**). Das Protokoll wird um einen
    `transcript_chunk`-Nachrichtentyp erweitert.
- **Line/Assets-Übergang:** Der Planer **plant** Line-Slots und Assets (ohne Erkennung), der Recorder
  **führt das Board live aus** — über dasselbe Payload. So bleibt „Planung" und „Ausführung" sauber getrennt.

---

## 3. Klangpult light – Recorder (Desktop-App)

**Zweck:** Aufnehmen. Nichts weiter. Maximal automatisiert, minimal zu konfigurieren.

### 3.1 Funktionen (Zielmarke = Studio-Tabs Audio + Video + Boards + Aufnahmen)

- **Audio-Aufnahme:** Mehrkanal-Mixer für USB-Mikrofone + weitere Quellen (Fader, Mute, Solo, Pegel).
  Voice-FX (Gate/Comp/Limiter/EQ) optional, schlank gehalten.
- **Videoaufnahme:** Webcam, Bildschirm/Fenster, mehrere Quellen, Default-Quelle, einfacher Split.
- **Gemeinsames Audio-Videoboard:** **EIN** Board mit **gemischten Pad-Typen** (Audio-Jingle *und*
  Video-/Bild-Einspieler in derselben Pad-Fläche) — nicht zwei getrennte Boards. Hotkeys, Play/Stop/Loop.
  Eingespielte Pads werden mitgeschnitten (Fade + Mikro-Ducking).
- **Aufnahmenansicht mit Branches:** Aufnahmen als Baum (Original unveränderlich, Branches als Kinder).
  Original wird **nie** überschrieben. (Branches hier nur als *Ansicht/Verwaltung* — das Schneiden
  selbst gehört zur weggelassenen Postproduction.)

### 3.2 Automatik (Kernanspruch „möglichst viel automatisch")

- **Quellen-Auto-Erkennung mit Verifikation:** Beim Start ermittelt der Recorder, welche Mikrofone und
  Quellen **wirklich verfügbar und öffenbar** sind (nicht nur `query_devices()` auflisten, sondern testweise
  öffnen), und schlägt eine sinnvolle Standardbelegung vor (Mic 1, Mic 2, System, Kamera).
- **„Aufnehmen, was am PC läuft" — ehrlich umgesetzt:** Wird etwas am PC abgespielt (Video, Musik, Browser),
  schneidet der Recorder es **gemäß Quelleneinstellungen** mit.
  - **Ehrliche Einschränkung (Faktentreue):** Direkter Systemton-Mitschnitt braucht ein **WASAPI-Loopback-
    Gerät** bzw. eine virtuelle Soundkarte (Windows). Ohne das ist es technisch nicht möglich.
  - **Automatik-Kompensation:** Der Recorder erkennt ein vorhandenes Loopback-/Monitor-Gerät automatisch
    und nutzt es. Fehlt es, **führt** die App klar (Statusleiste + Ein-Klick-Hinweis), statt „läuft einfach"
    zu suggerieren.
  - **Quellen-Config-Modell:** Pro Quelle ist explizit hinterlegt, **ob** und **wie** sie mitgeschnitten wird
    (z. B. „Systemton: ein, über Loopback-Gerät X"). Das ist die Bedeutung von „nach Quelleneinstellungen".

### 3.3 Bewusst NICHT im Recorder

Cutter/Schnitt, Export-Render-Pipeline, Transkription, OCR, Upload (YouTube/Spotify) — alles Postproduction
und gehört nicht in das Aufnahme-Tool. Die rohen Aufnahmen liegen im Workspace; Weiterverarbeitung bleibt
dem Studio (falls gewünscht) oder externen Tools überlassen.

---

## 4. Klangpult light – Planer (Web-App)

**Zweck:** Planen und live unterstützen. Daten/Text/Listen — keine Audio-Engine.

### 4.1 Funktionen (Zielmarke = Studio-Features Bibliothek + Projektplanung + Assets + Line + Monitor + Teleprompter)

- **Bibliothek:** listet automatisch alle Aufnahmen + Branch-Bäume aus dem Workspace (read-only Übersicht,
  Metadaten, Notizen). Keine Wiedergabe-Engine nötig — Verlinkung/Öffnen genügt.
- **Projektplanung:** Projekte/Episoden anlegen, Themen, Ablauf/Rundown, Gäste, Notizen, Statusboard.
- **Assets — nur Planung, keine Erkennung:** Asset-Liste pflegen (Jingles, Bilder, Clips als Plan-Einträge).
  Es wird **nichts** automatisch erkannt/klassifiziert — der Mensch listet, was er einsetzen will.
- **Line — nur Planung, keine Erkennung:** Line-Slots/Einspieler-Reihenfolge planen. Die geplante Line geht
  per `workspace-v1`-Payload an den Recorder, der sie live ausführt.
- **KI-Monitor (Premium-tauglich):** ruhiges Assistenz-Panel mit Fakten/Quellen/Nachfragen.
  - **Motor = Live-Transkription (vom User bestätigt):** Der Monitor speist sich aus **Live-Transkriptions-
    Chunks** (Recorder → STT → Bridge) **plus** Projektplan/Notizen. Webrecherche optional/konfigurierbar.
    Das LLM liefert strukturierte Kommandos und manipuliert die UI nicht direkt.
- **Teleprompter:** Text schreiben/laden, Auto-Scroll. Modi **manuell / nach Zeit / nach Sprache / Hybrid**.
  - **Modus „nach Sprache" ist drin:** Live-STT erkennt gesprochene Passagen und scrollt automatisch weiter
    (gespeist über dieselbe Live-Transkription wie der Monitor).

### 4.2 Live-Kopplung zum Recorder

Während einer Aufnahme verbindet sich der Planer (z. B. auf Tablet) per WebSocket mit dem Recorder:
Teleprompter-Zeile syncen, Pegel sehen, Pads/Marker fernauslösen (`remote_protocol_v1`). Ohne laufenden
Recorder funktioniert der Planer weiterhin als reines Planungstool.

### 4.3 Tech (Vorschlag, schlank)

Vanilla JS ESM oder leichtes Framework, **kein schwerer Build-Step nötig**; lokaler Python-Dienst
(FastAPI/uvicorn oder der Recorder-interne Server) für Bibliothek-Listing + Persistenz. Wiederverwendung
des bereits vorhandenen PWA-Companion-Scaffolds aus dem Studio (`web_companion/`) als Startpunkt.

---

## 5. Abgrenzung — was bewusst wegfällt

| Weggelassen | Begründung |
|---|---|
| **Postproduction / Export-Render** | Nicht Teil von Aufnahme oder Planung. |
| **Cutter (EDL/Timeline)** | Schnitt = Postproduction. Branches bleiben als *Ansicht*, nicht als Editor. |
| **Transkription als Datei-Feature (Batch SRT/TXT-Export)** | Postproduction-Komplexität, die Lukas loswerden will. |
| **OCR** | Erkennungs-Engine, raus. |
| **Upload (YouTube/Spotify)** | Distribution, nicht Aufnahme/Planung. |
| **Asset-/Line-Erkennung** | Explizit nur Planungstool, keine Auto-Klassifikation. |

**Wichtige Unterscheidung (vom User entschieden):** „Transkription weggelassen" meint das **Postproduction-
Feature** (Aufnahme nachträglich in SRT/TXT-Dateien verschriften). **Live-Transkription (Live-STT) ist
ausdrücklich DRIN** — sie ist der Motor für KI-Monitor (Live-Fakten/Nachfragen) und Teleprompter
(Modus „nach Sprache"). Es werden also Live-Chunks erkannt und an die Assistenz weitergereicht, aber kein
Transkript-Dokument als Ergebnis erzeugt/exportiert.

---

## 6. Feature-Mapping: Studio-Tab → neues Tool (Abhak-Zielmarke)

| Studio-Tab / Feature | → Klangpult light – Recorder | → Klangpult light – Planer | Status-Ziel |
|---|:--:|:--:|---|
| Mixer (USB-Mics, Fader/Mute/Solo/Pegel) | ✅ | — | muss erreicht |
| Voice-FX (Gate/Comp/Limiter/EQ) | ❌ | — | bewusst NICHT enthalten (Postproduction/Komplexität vermieden) |
| Videoquellen (Webcam/Screen/Split) | ✅ | — | erreicht |
| Soundboards | ✅ (Teil des gem. Boards) | plant Pads | muss |
| Videoboards/Einspieler | ✅ (Teil des gem. Boards) | plant | muss |
| Gemeinsames Audio-Videoboard (1 Board, gemischte Pads) | ✅ | plant | muss erreicht |
| „Aufnehmen was läuft" / Systemton-Loopback | ✅ (mit Auto-Detect + ehrl. Hinweis) | — | muss |
| Quellen-Auto-Erkennung + Verifikation | ✅ | — | muss erreicht |
| Aufnahmen + Branches (Ansicht) | ✅ | listet (Bibliothek) | muss erreicht |
| Bibliothek | — | ✅ | muss erreicht |
| Projektplanung / Rundown | — | ✅ | muss erreicht |
| Assets (nur Planung) | konsumiert | ✅ | muss erreicht |
| Line / Einspieler-Slots (nur Planung) | führt aus | ✅ | muss erreicht |
| Live-Transkription (Live-STT, als Motor) | ✅ (erzeugt Chunks) | konsumiert | muss erreicht |
| KI-Monitor | speist Live-Chunks + Status | ✅ (Live-STT + Plan) | muss erreicht |
| Teleprompter | Live-Sync + STT-Scroll | ✅ (manuell/Zeit/Sprache/Hybrid) | muss erreicht |
| Cutter / Export / **Batch**-Transkription (SRT/TXT) / OCR / Upload | ❌ | ❌ | bewusst raus |

---

## 7. Ordnerstruktur (Vorschlag)

```
Klangpult light/
├── KONZEPT.md              # dieses Dokument
├── TODO.md                 # Umsetzungsplan
├── README.md               # (später) Kurzüberblick + Quickstart
├── recorder/               # Klangpult light – Recorder — Desktop-App (Python/PySide6)
│   ├── main.py
│   ├── audio/              # DeviceManager (+ Verifikation), Mixer, Loopback-Erkennung
│   ├── video/              # Kamera/Screen-Quellen
│   ├── board/              # gemeinsames Audio-Videoboard
│   ├── recordings/         # Metadaten, Branch-Verwaltung (Ansicht)
│   ├── sources/            # Quellen-Config-Modell (was wird wie mitgeschnitten)
│   ├── bridge/             # lokaler Dienst (WebSocket + Bibliothek-API)
│   └── ui/                 # neues, schlankes Design
├── planer/                 # Klangpult light – Planer — Web-App
│   ├── index.html
│   ├── app/                # JS-Module (Bibliothek, Projekt, Assets, Line, Monitor, Prompter)
│   ├── styles/
│   └── server/             # (optional) lokaler Python-Dienst falls nicht im Recorder gebündelt
├── shared/                 # Austauschformate/Schemas (workspace-v1, remote_protocol_v1)
└── workspace/              # (Laufzeit, gitignored) Aufnahmen + Pläne — gemeinsamer Ordner
```

---

## 8. Designleitlinien

- **„Verbessertes Design" gilt für BEIDE Tools** — auch der Recorder bekommt ein frisches, ruhiges UI,
  nicht den alten Studio-PySide-Look 1:1.
- **Automation-first:** sinnvolle Defaults, Auto-Erkennung, möglichst wenig Pflicht-Klicks bis zur ersten
  Aufnahme.
- **Ehrlichkeit statt Magie:** Einschränkungen (Loopback, USB-Drift) klar in der UI benennen.
- **Datenschutz:** alles lokal; Cloud-KI nur opt-in mit Key (wie im Studio).

---

## 9. Offene Punkte / Annahmen zum Bestätigen

1. **Live-STT:** ✅ entschieden — DRIN als Motor für Monitor/Teleprompter. Engine läuft im **Recorder**
   (hat den Audiostream), schiebt `transcript_chunk` über die Bridge an den Planer. Nur Batch-Export raus.
   **Beide Wege parallel (vom User entschieden):** Engine-Abstraktion mit zwei gleichberechtigten Adaptern —
   **lokal** (faster-whisper, datenschutzfreundlich, offline) **und Cloud** (z. B. OpenAI/Deepgram, höhere
   Genauigkeit/Latenz). In den Einstellungen umschaltbar; Cloud nur opt-in mit Key. Standardvorauswahl: lokal,
   wenn kein Key konfiguriert ist.
2. **Planer-Backend / Start-Strategie (Phase-4-Entscheidung, 2026-06-20):** Das Ziel „eine zu startende
   Sache" ist umgesetzt durch `START.bat` im Projektroot: startet Recorder+Bridge im Hintergrund,
   wartet kurz, dann Planer. Die bestehenden Einzel-BATs (`START_RECORDER.bat`, `START_PLANER.bat`)
   bleiben erhalten — sie ermöglichen unabhängigen Start beider Tools (KONZEPT §1: „jedes Tool alleine
   lauffähig"). Die Einzel-BATs sind kein Widerspruch, sondern das Entwickler-/Debug-Interface.
   Ein echtes Single-Prozess-Bundling (Recorder integriert den Planer-Dienst direkt) wäre Architektur-
   Umbau und bleibt offen für später.
3. **Workspace-Ort:** gemeinsamer lokaler Ordner, konfigurierbar (nicht in OneDrive wegen Locks/Größe).
```

