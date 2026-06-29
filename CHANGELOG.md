# Changelog / Änderungsprotokoll

Alle wesentlichen Änderungen an diesem Projekt werden hier dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.1.0/).

## [Rebrand 2026-06-27]

### Geändert
- Produkt umbenannt: PodcastPackages → Klangpult light
- Lizenz: Proprietär/Freeware, Closed-Source
- Sub-Tools: PodcastRecorder → Klangpult light – Recorder; PodcastPlaner → Klangpult light – Planer
- Strategie verankert: kein öffentliches GitHub-Repo; Free/Freeware-Funnel für Klangpult (Vollversion)

## [Unreleased]

### Hinzugefügt / Added
- Projektweite `CHANGELOG.md` als Bootstrap-Baustein angelegt, damit künftige Recorder-/Planer-Änderungen versionierbar dokumentiert werden können.
- Recorder: Aufnahme-Moduswahl `Ton + Video`, `Nur Ton`, `Nur Video`.
- Recorder: auswählbare Audioquellen pro Mic-/Line-Quelle mit persistenter und direkt übernommener Gerätezuweisung.

### Geändert / Changed
- Nichts.

### Behoben / Fixed
- Recorder: Videoaufnahme ist nicht mehr implizit immer aktiv; `Nur Ton` startet ohne Videoquelle.
- Recorder: `Nur Video` erzeugt eine echte Video-only-Aufnahme ohne Audio-WAV-Dummy.
- Recorder: Audioquellen-Checkboxen wirken sofort auf die laufende Engine statt nur in `sources.json`.

## [0.1.0] - 2026-06-17

### Hinzugefügt / Added
- Konzeptprojekt `Klangpult light` als schlanke Aufspaltung von `DEV_USBPodcastStudio` in `Recorder` und `planer` dokumentiert.
- Root-Dokumente `README.md`, `KONZEPT.md` und `TODO.md` als erste Projektbasis angelegt.
