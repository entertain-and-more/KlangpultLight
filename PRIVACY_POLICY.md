# Privacy Policy / Datenschutzerklärung — Klangpult light

Stand: 2026-11-08  
Verantwortlicher Entwickler: Lukas Geiger (`support@lukasgeiger.com`)

## 1. Grundsatz: 100% Local-First & Zero-Egress

Klangpult light ist als strikt lokale Desktop- und Web-Workstation für Audio-/Videoaufnahmen, Einspieler und Podcast-Planung konzipiert. Die Anwendung verarbeitet sämtliche Daten ausschließlich lokal auf dem Endgerät des Benutzers. Es findet keinerlei unaufgeforderte Datenübertragung an externe Server, Werbenetzwerke oder Tracking-Dienste statt (Zero-Egress-Prinzip).

## 2. Welche Daten lokal verarbeitet und gespeichert werden

- **Audio- und Videoaufnahmen:** Aufgenommene Audiospuren (WAV/MP3), optionale Videospuren (MP4/MKV) und Metadaten werden im vom Benutzer definierten Aufnahmeverzeichnis (`workspace/` bzw. benutzerdefinierter Pfad) gespeichert.
- **Konfigurationsdaten:** Audio- und Video-Geräteeinstellungen, Lautstärke-Fader, Soundboard-Zuordnungen, Themes und Sprachpräferenzen werden lokal in Einstellungsdateien bzw. `QSettings` (Windows Registry / appdata) abgelegt.
- **Planer-Daten & Storylines:** Storylines, Asset-Listen und Teleprompter-Texte des Web-Planers verbleiben in der lokalen Workspace-Datenstruktur.
- **Lokale Schnittstellen & Bridge:** Die interne Bridge (`LibraryApiServer`, `RemoteWsServer`, `ProjectsApiServer` und `PlanerServer`) bindet ausschließlich auf `127.0.0.1` (localhost). Es erfolgt kein Routing ins öffentliche Internet.

## 3. Keine Erfassung personenbezogener Telemetriedaten

Klangpult light erfasst, analysiert und übermittelt keine Telemetrie-, Diagnose-, Nutzungs- oder Verhaltensdaten. Es gibt keine Drittanbieter-SDKs für Analytik, Profiling oder Werbung.

## 4. Berechtigungen unter Windows

Für den ordnungsgemäßen Betrieb benötigt Klangpult light folgende lokale Systemberechtigungen:
- **Mikrofon & Audioaufnahme (`microphone`):** Zum Zugriff auf angeschlossene USB-Mikrofone, Audio-Interfaces und Systemsounds.
- **Dateisystemzugriff:** Zum Speichern von Aufnahmedateien und Laden von Soundboard-Audiodateien.
- **Lokale Netzwerkkommunikation (`internetClient` / Local Loopback):** Zur internen Kommunikation zwischen Recorder-Desktop-App und lokalem Web-Planer auf `127.0.0.1`.

## 5. Rechte der Nutzerinnen und Nutzer

Da keine personenbezogenen Daten auf externen Servern gespeichert oder verarbeitet werden, verbleibt die volle Datenhoheit und Kontrolle zu jedem Zeitpunkt beim Nutzer. Alle lokalen Daten können durch Löschen des Workspace-Ordners oder Deinstallation der App vollständig entfernt werden.

## 6. Kontakt & Support

Bei Fragen zum Datenschutz oder zur Funktionsweise von Klangpult light wenden Sie sich bitte an:
- E-Mail: `support@lukasgeiger.com`
- GitHub Issue-Tracker: `https://github.com/entertain-and-more/KlangpultLight/issues`
