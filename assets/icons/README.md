# Icon-Satz — PodcastPackages

Kohärenter Line-Icon-Satz für Recorder + Planer: **24px viewBox, `stroke="currentColor"`,
2px, runde Enden**. `currentColor` = die Icons erben die Textfarbe (CSS `color` bzw.
PySide-Palette); `record`/`delete` werden per Akzentfarbe rot gesetzt.

**Vorschau:** `index.html` im Browser öffnen (Icons sind inline eingebettet).

## Icons
`mic` · `video` · `soundboard` · `record` · `stop` · `play` · `pause` · `delete` ·
`edit` · `add` · `project` · `episode` · `library` · `assign` · `collapse`

## Verwendung
- **Web (Planer):** inline `<svg>` einbetten oder als CSS-Mask
  (`background:currentColor; mask:url(icons/edit.svg)`), damit `currentColor`/Theme greift.
- **PySide (Recorder):** `QIcon("assets/icons/play.svg")` auf Buttons; für Farbe ein
  themed SVG oder `QPixmap`-Recoloring.

## Neu generieren (Codex)
Erstellt wurden die Icons direkt (Codex' Dateischreiben ist in der aktuellen
gesandboxten Agent-Umgebung blockiert — derselbe Prozess-Spawn-Block wie beim
Codex-Review). Zum Neu-/Umgenerieren mit Codex auf deinem Rechner:

```
node "C:\Users\User\.claude\plugins\cache\openai-codex\codex\1.0.4\scripts\codex-companion.mjs" \
  task --write -C "C:\Users\User\OneDrive\.TOPICS\.SOFTWARE\ENTERTAINMENT\PodcastPackages" \
  "Erzeuge in assets/icons/ einen kohaerenten 24px-Line-Icon-Satz (stroke currentColor, 2px,
   runde Enden) fuer: mic, video, soundboard, record, stop, play, pause, delete, edit, add,
   project, episode, library, assign, collapse. Eine .svg pro Icon."
```
