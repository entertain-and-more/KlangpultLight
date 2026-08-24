# Live-STT End-to-End-Pfad und Degradationsgrenzen

Dieses Dokument belegt den End-to-End-Pfad der Live-Transkription (`TW-KLANGPULTLIGHT-04`), die Degradationsgrenzen und die Opt-in-Sicherheitsregeln für KlangpultLight.

---

## 1. Architektur & End-to-End-Pipeline

Die Live-STT ist als asynchroner, flüchtiger Motor für Teleprompter-Sync und KI-Monitor konzipiert:

```
[AudioEngine] (Audio-Tap / Mix-Stream)
      │
      ▼ feed(block) [non-blocking Puffer]
[SttManager] (Worker-Thread, Fenster-Akkumulation z. B. 4.0s)
      │
      ▼ _engine.transcribe(audio, samplerate, t_start)
[LiveSttEngine] (LocalWhisperEngine | CloudSttEngine | MockSttEngine)
      │
      ▼ on_chunk(TranscriptChunk) Callback
[BridgeService] (RemoteWsServer / WebSocket Port 8768)
      │
      ▼ push_transcript_chunk(text, is_final, t_start, engine)
[Planer / Remote Client] (Teleprompter-Token-Sync & KI-Monitor-Event)
```

---

## 2. Degradationsgrenzen & Fehlertoleranz

| Szenario | Verhalten des Subsystems | Auswirkung auf Aufnahme / GUI |
| :--- | :--- | :--- |
| **Kein faster-whisper installiert** | `LocalWhisperEngine.available() == False`, `transcribe()` gibt sofort `[]` zurück. | 0% Auswirkung: Aufnahme läuft unverändert weiter, kein GUI-Block. |
| **Inferenz-Exception / CUDA OOM** | Try-Catch in `transcribe()` fängt Exception ab, loggt Warning und liefert `[]`. | Worker-Thread bleibt am Leben, nachfolgende Chunks werden weiter verarbeitet. |
| **Kein OPENAI_API_KEY gesetzt** | `CloudSttEngine.available() == False`, Cloud bleibt strikt deaktiviert (Opt-in). | Kein Netzwerkzugriff, keine Credentials im Code. |
| **Netzwerk-Timeout / API-Fehler** | Try-Catch fängt TimeoutError / 401 / 429 ab und liefert `[]`. | Kein Absturz der Bridge oder des Recorders. |
| **Ungültige Audiodaten (NaN / Inf)** | Finite Vektor-Konvertierung in `feed()`; kein Absturz des Audio-Taps. | Audio-Engine wird nicht blockiert. |
| **Beendigung / App-Shutdown** | `SttManager.stop()` beendet Worker-Thread über Event innerhalb von <100ms. | 0 verwaiste Daemon-Threads. |

---

## 3. Engine-Auswahl & Fallback-Hierarchie (`select_engine`)

1. **`prefer="cloud"`**:
   - Wenn Cloud verfügbar (API-Key gesetzt und Lib geladen) → `CloudSttEngine`.
   - Wenn Cloud nicht verfügbar, aber lokal verfügbar → automatischer Fallback auf `LocalWhisperEngine`.
   - Wenn weder Cloud noch lokal verfügbar → Fallback auf `MockSttEngine` (im Test) bzw. inaktive Instanz (im Produktivbetrieb).
2. **`prefer="local"` (Standard)**:
   - Wenn lokal verfügbar → `LocalWhisperEngine`.
   - Wenn lokal nicht verfügbar → Fallback auf `MockSttEngine` (im Test) bzw. inaktive Instanz.
   - Cloud wird **niemals** automatisch ohne `prefer="cloud"` und gesetzten API-Key aktiviert.
3. **Garantie**: `select_engine` gibt **niemals `None`** zurück.

---

## 4. Testabdeckung & Verifikationsnachweis

Die Ende-zu-Ende-Funktion und alle Degradationspfade sind durch eine dedizierte Testsuite abgesichert:

- `Recorder/tests/test_stt_e2e_degradation_contract.py` (11 Tests):
  - `TestSttEndToEndPath`: Audio-Feed → SttManager → BridgeService WebSocket-Nachricht (`transcript_chunk`).
  - `TestLocalWhisperDegradationContract`: Fehlende Bibliothek, Inferenz-Exceptions, Stille.
  - `TestCloudSttDegradationContract`: Opt-in-Zwang, Timeout-Handling, Auth-/RateLimit-Fehler.
  - `TestSelectEngineFallbackHierarchy`: Lückenlose Fallback-Kette.
  - `TestAudioBufferResilience`: NaN/Inf-Toleranz, leere Arrays, Last-Shutdown.
- `Recorder/tests/test_stt_degradation.py` (10 Tests)
- `Recorder/tests/test_stt_manager.py` (8 Tests)
- `Recorder/tests/test_stt_bridge_integration.py` (2 Tests)
- `Recorder/tests/test_stt_select_engine.py` (9 Tests)

Gesamt: **40 STT-spezifische Regressionstests**, 100% grün.
