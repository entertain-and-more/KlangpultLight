# TODO.md — PodcastPackages Umsetzungsplan

**Stand:** 2026-06-17 · Konzept: [KONZEPT.md](./KONZEPT.md)

> **Leitprinzip:** Anlass ist „Studio zu komplex". Also **lean, gestaffelt, lauffähige Scheiben zuerst** —
> kein Wiederaufbau eines Mini-Studios. Erst eine durchgehende dünne Aufnahme-Scheibe, dann verbreitern.
> Quelle: pragmatisch aus `DEV_USBPodcastStudio` kopieren, wo bewährt; neu schreiben, wo schlanker.

**Konventionen:** Python 3.11+, `PYTHONIOENCODING=utf-8`, venv NICHT in OneDrive
(`C:\_Local_DEV\venvs\podcast_packages\`), echte Umlaute, keine Credentials committen.

---

## Phase 0 — Setup & Gerüst

- [ ] `PodcastPackages` als `.SOFTWARE`-Projekt registrieren (releases.json / PROJECT_STATUS.md)
- [ ] Ordnerstruktur anlegen (siehe KONZEPT §7): `recorder/`, `planer/`, `shared/`, `workspace/`
- [ ] `.gitignore` SOFORT: `workspace/`, `*.env`, `venv/`, Build-Artefakte, große Medien
- [ ] Minimale `AGENTS.md` als Redirect auf CLAUDE.md (User-Standard) + Projekt-`README.md` (Stub)
- [ ] venv + `requirements.txt` (sounddevice, numpy, soundfile, opencv-python, mss, PySide6)
- [ ] `shared/`: `workspace_v1.json` + `remote_protocol_v1.json` aus Studio übernehmen/anpassen
- [ ] Quell-Inventar des Studios mit FileCommander erstellen (`fc_list_directory`/`fc_search_files`),
      Copy-vs-Rewrite je Modul entscheiden (Glob scheitert auf OneDrive — bekannt)

---

## Phase 1 — Recorder: erste lauffähige Scheibe (Audio)

> Ziel: **Mics erkennen → Audio aufnehmen → Aufnahme in der Liste sehen.** Das muss als Erstes laufen.

- [ ] `recorder/audio/device_manager.py`: Geräte auflisten **+ Verifikation** (testweise öffnen, nur
      wirklich nutzbare Quellen anbieten); Mock-Fallback ohne Hardware
- [ ] Auto-Standardbelegung vorschlagen (Mic 1 / Mic 2 / System / Kamera) aus verifizierten Geräten
- [ ] `recorder/audio/`: MixerChannel (Fader/Mute/Solo/Pegel), MasterBus, Wav-Recorder
- [ ] Thread-Modell sauber: Audio-Callback → `deque`, GUI liest per QTimer (kein GUI-Call im Callback)
- [ ] `recorder/recordings/`: Aufnahme starten/stoppen → Ordner + `metadata.json` + `events.jsonl`
- [ ] `recorder/ui/`: **neues schlankes Design** — Quellen-Panel + Aufnahme-Button + Pegel + Aufnahmeliste
- [ ] Headless-Selftest (`QT_QPA_PLATFORM=offscreen`) + erste pytest-Tests (DeviceManager, Recorder)
- [ ] **Meilenstein M1:** eine Audio-Session aufnehmen und in der Liste wiederfinden ✔

---

## Phase 2 — Recorder: Video

- [ ] `recorder/video/`: Kamera (OpenCV) + Bildschirm/Fenster (mss), Quellen-Verifikation wie bei Audio
- [ ] Mehrere Quellen, Default-Quelle, einfacher Split (kein OBS-Anspruch)
- [ ] VideoRecorder (FFmpeg-Pipe), Audio+Video gemeinsam → `program.mp4` + `mix.wav`
- [ ] FFmpeg-Check mit klarer Meldung bei Fehlen
- [ ] **Meilenstein M2:** Audio+Video-Session aufnehmen ✔

---

## Phase 3 — Recorder: „Aufnehmen was läuft" + Quellen-Config

- [ ] `recorder/sources/`: Quellen-Config-Modell — pro Quelle „ob/wie mitschneiden"
- [ ] **Loopback-Auto-Erkennung** (WASAPI-Loopback / virtuelles Gerät) → automatisch nutzen
- [ ] Fehlt Loopback: klare UI-Führung (Statusleiste + Ein-Klick-Hinweis), **nicht** „läuft einfach"
      vortäuschen (Faktentreue)
- [ ] Test: am PC abgespieltes Audio/Video wird gemäß Config mitgeschnitten
- [ ] **Meilenstein M3:** Systemton/Playback-Mitschnitt nach Quelleneinstellungen ✔

---

## Phase 4 — Recorder: Gemeinsames Audio-Videoboard

- [ ] `recorder/board/`: **EIN** Board mit **gemischten Pad-Typen** (Audio-Jingle UND Video-/Bild-Einspieler)
- [ ] Pad-Eigenschaften: Name, Icon, Farbe, Lautstärke, Modus (Play/Stop/Loop/Overlap), Hotkey
- [ ] Eingespielte Pads werden mitgeschnitten (Fade + Mikro-Ducking)
- [ ] Board-Belegung aus `workspace-v1`-Payload importierbar (vom Planer)
- [ ] **Meilenstein M4:** Board live spielen, Einspieler landen in der Aufnahme ✔

---

## Phase 5 — Recorder: Branch-Ansicht + lokaler Dienst

- [ ] `recorder/recordings/`: Branch-Datenmodell + Baum-Ansicht (Original unveränderlich)
      — nur Ansicht/Verwaltung, KEIN Editor
- [ ] `recorder/bridge/`: lokaler Dienst startet mit Recorder
  - [ ] Bibliothek-API (Aufnahmen + Branch-Baum als JSON listen)
  - [ ] WebSocket nach `remote_protocol_v1` (Pegel, Prompter-Zeile, Pad-Trigger, Status, Marker)
- [ ] **Meilenstein M5:** Recorder eigenständig vollständig (alle Recorder-Zielmarken erreicht) ✔

---

## Phase 5b — Recorder: Live-Transkription (Motor für Monitor/Teleprompter)

> Vom User entschieden: Live-STT ist DRIN (nur Batch-Export raus). Läuft im Recorder, da dort der Audiostream liegt.

- [ ] `recorder/stt/`: Engine-Abstraktion (`engine_base.py`) — **zwei Adapter parallel**:
  - [ ] **lokal:** faster-whisper (Streaming/Chunking, offline, datenschutzfreundlich)
  - [ ] **Cloud:** Adapter (z. B. OpenAI/Deepgram), nur opt-in mit Key
  - [ ] Umschaltung in den Einstellungen; Auto-Default lokal, wenn kein Key konfiguriert
- [ ] STT speist sich aus dem laufenden Mix/Mic-Stream (eigener Worker-Thread, kein GUI-Block)
- [ ] `remote_protocol_v1` um `transcript_chunk`-Nachrichtentyp erweitern (`shared/`)
- [ ] Recorder pusht erkannte Chunks über die Bridge (kein Transkript-Datei-Export!)
- [ ] **Meilenstein M5b:** Live-Chunks erscheinen beim verbundenen Planer ✔

---

## Phase 6 — Planer: erste lauffähige Scheibe (Bibliothek + Projekt)

> Startpunkt: vorhandenes `web_companion/`-PWA-Scaffold aus dem Studio übernehmen.

- [ ] `planer/`: Scaffold (index.html, app/, styles/) — schlankes, responsives Dark-Design
- [ ] **Bibliothek:** Aufnahmen + Branch-Baum automatisch über Recorder-Dienst/Workspace listen
      (Fallback: manueller Datei-Import, wenn Dienst aus)
- [ ] **Projektplanung:** Projekte/Episoden, Themen, Rundown, Gäste, Notizen, Statusboard (lokal persistiert)
- [ ] Persistenz über lokalen Dienst (im Recorder gebündelt) oder `planer/server/`
- [ ] **Meilenstein M6:** Planer zeigt Bibliothek + speichert ein Projekt ✔

---

## Phase 7 — Planer: Assets + Line (nur Planung)

- [ ] **Assets:** Liste pflegen (Jingles/Bilder/Clips als Plan-Einträge) — KEINE Erkennung/Klassifikation
- [ ] **Line:** Einspieler-Slots/Reihenfolge planen
- [ ] Export als `workspace-v1`-Payload → vom Recorder-Board konsumierbar (Planung → Ausführung)
- [ ] **Meilenstein M7:** geplante Line/Assets erscheinen als Board-Belegung im Recorder ✔

---

## Phase 8 — Planer: Teleprompter + KI-Monitor

- [ ] **Teleprompter:** Text schreiben/laden, Auto-Scroll, Modi **manuell / nach Zeit / nach Sprache / Hybrid**
- [ ] **Modus „nach Sprache":** Auto-Scroll anhand der Live-STT-Chunks aus dem Recorder (Phase 5b)
- [ ] **Live-Sync:** Prompter-Zeile mit Recorder über WebSocket koppeln
- [ ] **KI-Monitor:** Panel mit Fakten/Quellen/Nachfragen, gespeist aus **Live-Transkriptions-Chunks
      (Phase 5b) + Projektplan/Notizen**; LLM liefert strukturierte Kommandos, manipuliert UI nicht direkt
- [ ] Webrecherche-Adapter optional/konfigurierbar; Cloud-KI nur opt-in mit Key
- [ ] **Meilenstein M8:** Teleprompter & Monitor laufen im Planer, live an Recorder gekoppelt ✔

---

## Phase 9 — Abschluss & Härtung

- [ ] End-to-End-Durchlauf mit **frischen Subagenten** (unbelastet) gegen die Feature-Mapping-Tabelle (KONZEPT §6)
- [ ] README + Quickstart je Tool, Datenschutz-Hinweise
- [ ] Recorder: PyInstaller-EXE-Build (onedir + onefile), Desktop-Verknüpfung
- [ ] Planer: lokaler Start dokumentiert (eine zu startende Sache, idealerweise vom Recorder mitgestartet)
- [ ] Eintrag in `.SOFTWARE`-Registry aktualisieren; Memory/Hub-Index ergänzen

---

## Risiken / Wachpunkte

- **Loopback-Realität:** Systemton-Mitschnitt ohne virtuelles Gerät nicht möglich → ehrlich kommunizieren,
  Auto-Detect + Führung statt Versprechen.
- **Zwei Tech-Stacks** (Python-Desktop + JS-Web): bewusste Entscheidung; Kopplung nur über klar
  definierte Schemas (`workspace-v1`, `remote_protocol_v1`), nicht über geteilten Code.
- **Scope-Creep:** Versuchung, Cutter/Export/**Batch**-Transkription „nur ein bisschen" zurückzuholen —
  widerstehen. (Live-STT ist drin, aber **nur als flüchtiger Motor** — kein Transkript-Datei-Export!)
- **Live-STT-Last:** STT braucht CPU/GPU parallel zur Aufnahme — Modellgröße konservativ wählen,
  optional zuschaltbar, damit schwache Rechner die Aufnahme nicht gefährden.
- **USB-Drift:** wie im Studio nur überwachen + warnen, kein Hard-Sync versprechen.

## OFFENE BUGS (siehe BUGS.md) — ergänzt 2026-06-22

Behoben: kombinierter START.bat-Fix (Recorder startete nicht), Recorder-Startfix (Kamera-Probing), Audio-Overflow-Logging.
Offen (Details in BUGS.md):
[ ] P3  WAV-Write hält Aufnahme-Lock während Platten-Write (Recorder/audio/engine.py).
[ ] P3  Video: FFmpeg-stdin-Write blockiert im Capture-Thread, kein Drop-Logging (Recorder/video/video_recorder.py).

## User-Test-Feedback 2026-06-22 (Task 11) — offene Funktionen

Aus User-Tests (Lukas). Reihenfolge = Priorität; Funktionen vor Politur (Premium zuletzt).

### Planer (Web)
- [x] P1  Episoden **editieren UND löschen** — Backend (PUT/DELETE) + Frontend-Buttons. Commits 21ba558/28a8657. (Browser-Klicktest offen.)
- [~] P1  **Projektzuordnung von Aufnahmen** — Backend fertig (POST/DELETE /recordings/{id}, 21ba558); **Frontend-UI (bibliothek.js) noch offen**.
- [ ] P2  Aufnahme **abspielen** — browser-interner Player (Library-Audio-Endpunkt + `<audio>`) oder Start im externen Player.

### Recorder (Desktop)
- [x] P1  **Einspieler hinzufügbar** — Datei-Dialog → Pad → board.json. Commit bbe8d12.
- [x] P1  Aufnahmen in der GUI **löschen/umbenennen/abspielen** (Kontextmenü + Doppelklick). Commit ac43edd.
- [ ] P2  Bereiche **ein-/ausklappbar**; der freiwerdende Platz wird dynamisch genutzt.
- [ ] P3  **Schöne Symbole** verwenden (von Codex generieren lassen).
- [ ] P3  Premium (zuletzt): Fenster-im-Fenster **ablösbar** + wieder **andockbar** — Funktionen gehen vor.
