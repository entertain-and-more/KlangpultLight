# Security Policy / Sicherheitsrichtlinie

[English](#english) | [Deutsch](#deutsch)

---

<a name="english"></a>
## English

### Overview

**Klangpult light** is a lightweight desktop and web application (Recorder + Planer) for audio/video recording, live transcription, soundboard triggering, and local media planning. We prioritize data privacy, local-first computing, zero-egress security invariants, and unprivileged user execution.

### Security Guarantees & Invariants

1. **Local-First & Zero-Egress Architecture**:
   - All audio/video recordings, project workspaces, teleprompter scripts, and transcription caches reside strictly on the local machine.
   - The application does not send telemetry, user content, recorded audio, video streams, or project data to external cloud servers.

2. **IPC & Network Loopback Isolation**:
   - Inter-process communication between the PySide6 Desktop Recorder and the Web Planer operates exclusively via local loopback sockets (`127.0.0.1:8767`, `127.0.0.1:8769`, `127.0.0.1:8770`).
   - Web server endpoints are bound to localhost by default, preventing unintended exposure across local area networks (LAN).

3. **Unprivileged Execution (User Mode)**:
   - Klangpult light runs entirely in unprivileged user space without requiring administrator rights or elevated system privileges.
   - Audio and video device access occurs through standard operating system multimedia APIs (WASAPI/MME on Windows, PySide6/FFmpeg pipelines).

4. **Safe Media Processing & Subprocess Boundaries**:
   - Subprocess invocations (e.g., FFmpeg remuxing and video writing) use sanitized arguments, strict pipe timeouts, and dedicated error-handling boundaries to prevent command injection and resource exhaustion.

### Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

### Reporting a Vulnerability

If you discover a security vulnerability, please **do not open a public GitHub issue**. Instead, report it privately:

- **Security Team Email**: [security@ellmos.ai](mailto:security@ellmos.ai)
- **Umbrella Security**: [security@open-bricks.org](mailto:security@open-bricks.org)
- **Maintainer Support**: [support@lukasgeiger.com](mailto:support@lukasgeiger.com) / [lukas@open-bricks.org](mailto:lukas@open-bricks.org)
- **GitHub Security Advisories**: You can also report vulnerabilities via [GitHub Security Advisories](https://github.com/entertain-and-more/KlangpultLight/security/advisories/new).

We will acknowledge receipt within 48 hours and provide updates on resolution and remediation.

---

<a name="deutsch"></a>
## Deutsch

### Übersicht

**Klangpult light** ist eine leichtgewichtige Desktop- und Web-Anwendung (Recorder + Planer) für Audio-/Videoaufnahmen, Live-Transkription, Soundboard-Einspieler und lokale Medienplanung. Höchste Priorität haben Datenschutz, Local-First-Architektur, Zero-Egress-Sicherheitsgarantien und unprivilegierter Betrieb.

### Sicherheitsgarantien & Invarianten

1. **Local-First & Zero-Egress Architektur**:
   - Alle Audio-/Videoaufnahmen, Projekt-Workspaces, Teleprompter-Skripte und Transkriptionsdaten verbleiben ausschließlich auf dem lokalen Rechner.
   - Die Anwendung überträgt keinerlei Telemetrie, Nutzerinhalte, Audiosignale, Videostreams oder Projektdaten an externe Server.

2. **IPC- & Netzwerk-Loopback-Isolation**:
   - Die Interprozesskommunikation zwischen der PySide6-Desktop-App (Recorder) und dem Web-Planer läuft ausschließlich über lokale Loopback-Verbindungen (`127.0.0.1:8767`, `127.0.0.1:8769`, `127.0.0.1:8770`).
   - Die Web-Endpunkte sind standardmäßig an localhost gebunden, um Zugriffe über das lokale Netzwerk (LAN) zu verhindern.

3. **Unprivilegierter Betrieb (User Mode)**:
   - Klangpult light arbeitet vollständig im regulären Benutzermodus ohne Notwendigkeit von Administrator- oder Root-Rechten.
   - Der Zugriff auf Aufnahme- und Wiedergabegeräte erfolgt über standardisierte Betriebssystem-Schnittstellen.

4. **Sichere Medienverarbeitung & Subprozess-Grenzen**:
   - Subprozesse (z. B. FFmpeg-Muxing) werden mit isolierten Argumenten, strikten Pipe-Timeouts und kontrollierten Fehlerbehandlungen ausgeführt.

### Unterstützte Versionen

| Version | Unterstützt        |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |
| < 0.1   | :x:                |

### Schwachstelle melden

Bitte eröffnen Sie bei Sicherheitsbedenken **kein öffentliches GitHub-Issue**, sondern kontaktieren Sie uns vertraulich:

- **Sicherheitsteam E-Mail**: [security@ellmos.ai](mailto:security@ellmos.ai)
- **Dachorganisation Security**: [security@open-bricks.org](mailto:security@open-bricks.org)
- **Maintainer Support**: [support@lukasgeiger.com](mailto:support@lukasgeiger.com) / [lukas@open-bricks.org](mailto:lukas@open-bricks.org)
- **GitHub Security Advisories**: [Schwachstelle privat melden](https://github.com/entertain-and-more/KlangpultLight/security/advisories/new)

Wir bestätigen den Eingang jeder Meldung innerhalb von 48 Stunden und informieren transparent über Schutzmaßnahmen und Updates.
