# Planer-Browser-Abnahme

Dieses Runbook belegt den echten Browserpfad aus `TW-KLANGPULTLIGHT-05`, ohne
Aufnahmen, Projekte oder Ports eines laufenden Nutzerprofils zu berühren.

## Isolierte Fixture starten

```powershell
$env:PYTHONIOENCODING = "utf-8"
python scripts\planer_browser_fixture.py `
  --data-dir C:\_Local_DEV\scratch\klangpultlight-planer-browser `
  --ready-file output\playwright\fixture-ready.json `
  --stop-file output\playwright\fixture-stop
```

Die Ready-Datei enthält ausschließlich localhost-Ports, Fixture-ID und den
temporären Datenpfad. Danach wird die dort ausgegebene URL in einem echten
Browser geöffnet.

## Abnahmeschritte

1. Status zeigt `Recorder verbunden`.
2. Bibliothek listet `Browser-Abnahme Aufnahme` mit Branch-Readback und einem
   nativen Audio-Player.
3. Im Tab `Projekte` ein Projekt anlegen, umbenennen und eine Episode anlegen.
4. Projekt und Episode löschen; Bestätigungsdialoge per Tastatur bedienen.
5. Bibliothek neu laden und damit den Library-Bridge-Pfad erneut auslösen.
6. Browser-Konsole und fehlgeschlagene Netzwerkrequests prüfen.

Die Fixture wird durch Anlegen der angegebenen Stop-Datei sauber beendet.

## Aktueller Abnahmestand

**Bestanden am 2026-08-03, 22:50 Uhr Europe/Berlin.**

- Echter Chromium-Browser über Playwright CLI; isolierte Fixture mit den
  produktiven `LibraryApiServer`, `ProjectsApiServer` und `PlanerServer`.
- Status: `Recorder verbunden`.
- Bibliothek: eine Fixture-Aufnahme, zwei Branches und nativer Audio-Player
  sichtbar; Reload löste den Library-Readback erneut aus.
- Projekte: anlegen, umbenennen, Episode anlegen, Aufnahme zuordnen, Episode
  löschen und Projekt löschen bestanden. Beide Bestätigungsdialoge wurden über
  den fokussierten `Bestätigen`-Button mit Enter bedient.
- Netzwerk: Projekt-POST `201`, Projekt-PUT `200`, Episoden-POST `201`,
  Zuordnung `200`, beide DELETEs `204`; Library-/Projects-Readbacks `200`.
- Erstbefund: impliziter `GET /favicon.ico` lieferte `404` und erzeugte einen
  Konsolenfehler. Nach dem Fix in `planer/index.html` zeigte eine frische
  Browser-Session **0 Fehler und 0 Warnungen**.
- Lokales, gitignoriertes Screenshot-Artefakt:
  `output/playwright/browser-final.png`.

Dieser Lauf belegt Browser, localhost-HTTP-Dienste und den isolierten
Bridge-Vertrag. Er ist keine Audio-/Video-Hardwareabnahme; diese bleibt in
`TW-KLANGPULTLIGHT-11` getrennt offen.
