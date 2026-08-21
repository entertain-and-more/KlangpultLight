/**
 * teleprompter.js — Teleprompter-Modul für den Klangpult light – Planer (Phase 8).
 *
 * Unterstützt:
 *   - 4 Betriebsmodi: manuell, nach Zeit (Auto-Scroll), nach Sprache (Speech-Sync via STT), Hybrid
 *   - Live-Kopplung an den Recorder über remote.js (WebSocket remote_protocol_v1)
 *   - Barrierefreie Tastaturbedienung (Space = Start/Pause, Up/Down = Zeilensprung, Esc = Reset)
 *   - Hardware-Spiegelmodus (Flip Horizontal für Teleprompterglas)
 *   - Einstellbare Typografie (Schriftgröße, Zeilenabstand) und Vollbild-Präsentation
 */

import * as api from "./api.js";
import { el } from "./util.js";
import { remote } from "./remote.js";

let _container = null;
let _projects = [];
let _activeProjectId = null;
let _teleprompterData = {
  text: "",
  font_size: 28,
  scroll_speed: 1.0,
  mode: "manual", // manual | time | speech | hybrid
  current_line: 0,
  mirror: false,
};

let _isPlaying = false;
let _lines = [];
let _currentLineIndex = 0;
let _scrollAnimationId = null;
let _speechUnsubscribe = null;
let _stateUnsubscribe = null;
let _connUnsubscribe = null;
let _isFullscreen = false;

// ---------------------------------------------------------------------------
// Lifecycle: mount / unmount / reload
// ---------------------------------------------------------------------------

export async function mount(container) {
  _container = container;
  _container.innerHTML = "";

  // Event-Listener für Live-WebSocket registrieren
  _speechUnsubscribe = remote.on("transcript_chunk", handleTranscriptChunk);
  _stateUnsubscribe = remote.on("state_update", handleStateUpdate);
  _connUnsubscribe = remote.on("connection_change", handleConnectionChange);

  // Tastatursteuerung global für Teleprompter
  window.addEventListener("keydown", handleGlobalKeyDown);

  await reload();
}

export function unmount() {
  stopScrolling();
  if (_speechUnsubscribe) { _speechUnsubscribe(); _speechUnsubscribe = null; }
  if (_stateUnsubscribe) { _stateUnsubscribe(); _stateUnsubscribe = null; }
  if (_connUnsubscribe) { _connUnsubscribe(); _connUnsubscribe = null; }
  window.removeEventListener("keydown", handleGlobalKeyDown);
  _container = null;
}

export async function reload() {
  if (!_container) return;
  const res = await api.listProjects();
  if (res.ok && res.data) {
    _projects = res.data.projects || [];
    if (!_activeProjectId && _projects.length > 0) {
      _activeProjectId = _projects[0].project_id;
    }
  } else {
    _projects = [];
  }

  if (_activeProjectId) {
    const teleRes = await api.getTeleprompter(_activeProjectId);
    if (teleRes.ok && teleRes.data && teleRes.data.teleprompter) {
      _teleprompterData = Object.assign(_teleprompterData, teleRes.data.teleprompter);
      _currentLineIndex = _teleprompterData.current_line || 0;
    }
  }

  _parseLines();
  render();
}

// ---------------------------------------------------------------------------
// Hilfsfunktionen & Textzerlegung
// ---------------------------------------------------------------------------

function _parseLines() {
  const raw = _teleprompterData.text || "";
  if (!raw.trim()) {
    _lines = [
      "Willkommen beim Klangpult light Teleprompter.",
      "Lade oder schreibe ein Skript, um zu beginnen.",
      "Modi: Manuell, Nach Zeit, Nach Sprache (Live-STT) oder Hybrid.",
    ];
  } else {
    _lines = raw
      .split("\n")
      .map((l) => l.trim())
      .filter((l) => l.length > 0);
    if (_lines.length === 0) {
      _lines = ["(Kein Text im Skript vorhanden)"];
    }
  }
  if (_currentLineIndex >= _lines.length) {
    _currentLineIndex = 0;
  }
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function render() {
  if (!_container) return;
  _container.innerHTML = "";

  const root = el("div", { className: "prompter-container" });

  // 1. Header Toolbar
  const header = el("div", { className: "prompter-header card" }, [
    el("div", { className: "prompter-header-top" }, [
      el("div", { className: "form-group prompter-project-select-group" }, [
        el("label", { for: "prompter-project-select", textContent: "Projekt auswählen" }),
        (() => {
          const select = el("select", {
            id: "prompter-project-select",
            onChange: async (e) => {
              _activeProjectId = e.target.value;
              await reload();
            },
          });
          for (const p of _projects) {
            const opt = el("option", { value: p.project_id, textContent: p.title });
            if (p.project_id === _activeProjectId) opt.selected = true;
            select.appendChild(opt);
          }
          return select;
        })(),
      ]),

      el("div", { className: "prompter-status-indicators" }, [
        el("div", {
          id: "prompter-ws-status",
          className: `badge ${remote.isConnected ? "badge-fertig" : "badge-geplant"}`,
          textContent: remote.isConnected ? "Recorder verbunden" : "Recorder offline",
        }),
        el("div", {
          id: "prompter-play-status",
          className: `badge ${_isPlaying ? "badge-laufend" : "badge-geplant"}`,
          textContent: _isPlaying ? "Aktiv (Scroll)" : "Pausiert",
        }),
      ]),
    ]),

    // Controls Row
    el("div", { className: "prompter-controls-row" }, [
      el("div", { className: "prompter-control-item" }, [
        el("label", { for: "prompter-mode-select", textContent: "Modus" }),
        el("select", {
          id: "prompter-mode-select",
          onChange: (e) => {
            _teleprompterData.mode = e.target.value;
            _saveData();
            updateControlsUI();
          },
        }, [
          el("option", { value: "manual", textContent: "1. Manuell (Tastatur)", selected: _teleprompterData.mode === "manual" }),
          el("option", { value: "time", textContent: "2. Nach Zeit (Auto-Scroll)", selected: _teleprompterData.mode === "time" }),
          el("option", { value: "speech", textContent: "3. Nach Sprache (STT)", selected: _teleprompterData.mode === "speech" }),
          el("option", { value: "hybrid", textContent: "4. Hybrid (Zeit + STT)", selected: _teleprompterData.mode === "hybrid" }),
        ]),
      ]),

      el("div", { className: "prompter-control-item" }, [
        el("label", { for: "prompter-speed-slider", textContent: `Tempo (${_teleprompterData.scroll_speed}x)` }),
        el("input", {
          id: "prompter-speed-slider",
          type: "range",
          min: "0.2",
          max: "3.0",
          step: "0.1",
          value: String(_teleprompterData.scroll_speed || 1.0),
          onInput: (e) => {
            _teleprompterData.scroll_speed = parseFloat(e.target.value);
            const lbl = document.querySelector("label[for='prompter-speed-slider']");
            if (lbl) lbl.textContent = `Tempo (${_teleprompterData.scroll_speed.toFixed(1)}x)`;
            _saveData();
          },
        }),
      ]),

      el("div", { className: "prompter-control-item" }, [
        el("label", { for: "prompter-font-size-slider", textContent: `Schrift (${_teleprompterData.font_size}px)` }),
        el("input", {
          id: "prompter-font-size-slider",
          type: "range",
          min: "16",
          max: "64",
          step: "2",
          value: String(_teleprompterData.font_size || 28),
          onInput: (e) => {
            _teleprompterData.font_size = parseInt(e.target.value, 10);
            const lbl = document.querySelector("label[for='prompter-font-size-slider']");
            if (lbl) lbl.textContent = `Schrift (${_teleprompterData.font_size}px)`;
            applyTypographyStyles();
            _saveData();
          },
        }),
      ]),

      el("div", { className: "prompter-action-buttons" }, [
        el("button", {
          id: "prompter-play-btn",
          className: `btn ${_isPlaying ? "btn-danger" : "btn-primary"}`,
          textContent: _isPlaying ? "Pause (Space)" : "Start (Space)",
          "aria-label": _isPlaying ? "Teleprompter anhalten" : "Teleprompter starten",
          onClick: togglePlay,
        }),
        el("button", {
          id: "prompter-prev-btn",
          className: "btn btn-ghost",
          textContent: "▲ Zurück",
          "aria-label": "Eine Zeile zurückspringen",
          onClick: () => jumpLine(-1),
        }),
        el("button", {
          id: "prompter-next-btn",
          className: "btn btn-ghost",
          textContent: "▼ Weiter",
          "aria-label": "Eine Zeile weiterspringen",
          onClick: () => jumpLine(1),
        }),
        el("button", {
          id: "prompter-reset-btn",
          className: "btn btn-ghost",
          textContent: "↺ Reset",
          "aria-label": "Teleprompter an den Anfang setzen",
          onClick: resetToStart,
        }),
        el("button", {
          id: "prompter-mirror-toggle",
          className: `btn ${_teleprompterData.mirror ? "btn-primary" : "btn-ghost"}`,
          textContent: "⇋ Spiegeln",
          "aria-label": "Spiegelschrift umschalten",
          onClick: toggleMirror,
        }),
        el("button", {
          id: "prompter-fullscreen-btn",
          className: "btn btn-ghost",
          textContent: "⛶ Vollbild",
          "aria-label": "Vollbildmodus aktivieren",
          onClick: toggleFullscreen,
        }),
      ]),
    ]),
  ]);

  // 2. Main Stage & Editor Split
  const mainStage = el("div", { className: "prompter-main-stage" }, [
    // Prompter Screen / Display Box
    el("div", {
      id: "prompter-screen",
      className: `prompter-screen ${_teleprompterData.mirror ? "mirrored" : ""}`,
      role: "region",
      "aria-label": "Teleprompter-Bühne",
      tabIndex: 0,
    }, [
      el("div", { className: "prompter-cue-marker", "aria-hidden": "true" }),
      el("div", { id: "prompter-text-flow", className: "prompter-text-flow" }),
    ]),

    // Script Editor Panel
    el("div", { className: "prompter-editor-panel card" }, [
      el("div", { className: "card-header" }, [
        el("h3", { textContent: "Skript-Editor" }),
        el("span", {
          id: "prompter-line-count",
          className: "badge badge-geplant",
          textContent: `${_lines.length} Zeilen`,
        }),
      ]),
      el("div", { className: "form-group" }, [
        el("label", { for: "prompter-text-editor", textContent: "Skripttext (zeilenbasiert)" }),
        el("textarea", {
          id: "prompter-text-editor",
          rows: 10,
          value: _teleprompterData.text || "",
          placeholder: "Füge hier deinen Moderationstext ein...\nJede Zeile wird als eigener Leseblock dargestellt.",
          onInput: (e) => {
            _teleprompterData.text = e.target.value;
            _parseLines();
            renderTextFlow();
            const badge = document.getElementById("prompter-line-count");
            if (badge) badge.textContent = `${_lines.length} Zeilen`;
            _saveDataDebounced();
          },
        }),
      ]),
      el("div", { className: "prompter-editor-actions" }, [
        el("button", {
          className: "btn btn-ghost",
          textContent: "Beispiel-Skript laden",
          onClick: () => {
            _teleprompterData.text =
              "Herzlich willkommen zu Klangpult light!\n" +
              "Heute sprechen wir über Audio- und Videorecordings.\n" +
              "Wir zeigen den neuen Planer mit Soundboard und Teleprompter.\n" +
              "Als nächstes werfen wir einen Blick auf die Live-Transkription.\n" +
              "Vielen Dank fürs Zuschauen und bis zur nächsten Episode!";
            const editor = document.getElementById("prompter-text-editor");
            if (editor) editor.value = _teleprompterData.text;
            _parseLines();
            renderTextFlow();
            _saveData();
          },
        }),
        el("button", {
          className: "btn btn-primary",
          textContent: "Skript speichern",
          onClick: async () => {
            await _saveData();
          },
        }),
      ]),
    ]),
  ]);

  root.appendChild(header);
  root.appendChild(mainStage);
  _container.appendChild(root);

  renderTextFlow();
  applyTypographyStyles();
  updateControlsUI();
}

function renderTextFlow() {
  const flow = document.getElementById("prompter-text-flow");
  if (!flow) return;
  flow.innerHTML = "";

  _lines.forEach((lineText, idx) => {
    const lineEl = el("div", {
      className: `prompter-line ${idx === _currentLineIndex ? "active" : ""}`,
      id: `prompter-line-${idx}`,
      role: "button",
      tabIndex: 0,
      "aria-label": `Zeile ${idx + 1}: ${lineText}`,
      onClick: () => {
        _currentLineIndex = idx;
        highlightActiveLine(true);
      },
      onKeyDown: (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          _currentLineIndex = idx;
          highlightActiveLine(true);
        }
      },
    }, [
      el("span", { className: "prompter-line-number", textContent: String(idx + 1) }),
      el("span", { className: "prompter-line-content", textContent: lineText }),
    ]);

    flow.appendChild(lineEl);
  });

  highlightActiveLine(false);
}

function highlightActiveLine(smoothScroll = true) {
  const lines = document.querySelectorAll(".prompter-line");
  lines.forEach((l, idx) => {
    if (idx === _currentLineIndex) {
      l.classList.add("active");
    } else {
      l.classList.remove("active");
    }
  });

  const activeEl = document.getElementById(`prompter-line-${_currentLineIndex}`);
  const screen = document.getElementById("prompter-screen");
  if (activeEl && screen) {
    const targetScroll = activeEl.offsetTop - (screen.clientHeight / 2) + (activeEl.clientHeight / 2);
    screen.scrollTo({
      top: Math.max(0, targetScroll),
      behavior: smoothScroll ? "smooth" : "auto",
    });
  }

  // Live-Sync an Recorder übermitteln
  if (remote.isConnected) {
    remote.sendScrollTeleprompter(_currentLineIndex);
  }
}

function applyTypographyStyles() {
  const flow = document.getElementById("prompter-text-flow");
  if (flow) {
    flow.style.fontSize = `${_teleprompterData.font_size || 28}px`;
    flow.style.lineHeight = "1.7";
  }
}

function updateControlsUI() {
  const playBtn = document.getElementById("prompter-play-btn");
  if (playBtn) {
    playBtn.textContent = _isPlaying ? "Pause (Space)" : "Start (Space)";
    playBtn.className = `btn ${_isPlaying ? "btn-danger" : "btn-primary"}`;
  }

  const playStatus = document.getElementById("prompter-play-status");
  if (playStatus) {
    playStatus.textContent = _isPlaying ? "Aktiv (Scroll)" : "Pausiert";
    playStatus.className = `badge ${_isPlaying ? "badge-laufend" : "badge-geplant"}`;
  }

  const wsStatus = document.getElementById("prompter-ws-status");
  if (wsStatus) {
    wsStatus.textContent = remote.isConnected ? "Recorder verbunden" : "Recorder offline";
    wsStatus.className = `badge ${remote.isConnected ? "badge-fertig" : "badge-geplant"}`;
  }
}

// ---------------------------------------------------------------------------
// Teleprompter Steuerung & Animation
// ---------------------------------------------------------------------------

export function togglePlay() {
  if (_isPlaying) {
    stopScrolling();
  } else {
    startScrolling();
  }
}

export function startScrolling() {
  if (_isPlaying) return;
  _isPlaying = true;
  updateControlsUI();

  if (_teleprompterData.mode === "time" || _teleprompterData.mode === "hybrid") {
    _startAutoScrollLoop();
  }
}

export function stopScrolling() {
  _isPlaying = false;
  if (_scrollAnimationId) {
    cancelAnimationFrame(_scrollAnimationId);
    _scrollAnimationId = null;
  }
  updateControlsUI();
}

function _startAutoScrollLoop() {
  let lastTimestamp = performance.now();
  const screen = document.getElementById("prompter-screen");

  function step(now) {
    if (!_isPlaying) return;
    const deltaMs = now - lastTimestamp;
    lastTimestamp = now;

    if (screen) {
      // Berechne Pixelvorschub basierend auf scroll_speed
      const pixelsPerSec = 35 * (_teleprompterData.scroll_speed || 1.0);
      const move = (pixelsPerSec * deltaMs) / 1000;
      screen.scrollTop += move;

      // Ermittle welche Zeile gerade im Fokusbereich ist
      const middleY = screen.scrollTop + (screen.clientHeight / 2);
      const lines = document.querySelectorAll(".prompter-line");
      for (let i = 0; i < lines.length; i++) {
        const top = lines[i].offsetTop;
        const bottom = top + lines[i].clientHeight;
        if (middleY >= top && middleY <= bottom) {
          if (_currentLineIndex !== i) {
            _currentLineIndex = i;
            lines.forEach((l, idx) => l.classList.toggle("active", idx === i));
          }
          break;
        }
      }
    }

    _scrollAnimationId = requestAnimationFrame(step);
  }

  _scrollAnimationId = requestAnimationFrame(step);
}

export function jumpLine(delta) {
  _currentLineIndex = Math.max(0, Math.min(_lines.length - 1, _currentLineIndex + delta));
  highlightActiveLine(true);
}

export function resetToStart() {
  _currentLineIndex = 0;
  highlightActiveLine(false);
  if (document.getElementById("prompter-screen")) {
    document.getElementById("prompter-screen").scrollTop = 0;
  }
}

export function toggleMirror() {
  _teleprompterData.mirror = !_teleprompterData.mirror;
  const screen = document.getElementById("prompter-screen");
  const btn = document.getElementById("prompter-mirror-toggle");
  if (screen) {
    screen.classList.toggle("mirrored", _teleprompterData.mirror);
  }
  if (btn) {
    btn.className = `btn ${_teleprompterData.mirror ? "btn-primary" : "btn-ghost"}`;
  }
  _saveData();
}

export function toggleFullscreen() {
  const root = document.querySelector(".prompter-container");
  if (!root) return;

  if (!_isFullscreen) {
    if (root.requestFullscreen) {
      root.requestFullscreen();
    }
    root.classList.add("fullscreen");
    _isFullscreen = true;
  } else {
    if (document.exitFullscreen) {
      document.exitFullscreen();
    }
    root.classList.remove("fullscreen");
    _isFullscreen = false;
  }
}

// ---------------------------------------------------------------------------
// Speech-Sync & WebSocket Event Handlers
// ---------------------------------------------------------------------------

function handleTranscriptChunk(chunk) {
  // Wenn STT-Modus oder Hybrid aktiv ist: Text vergleichen und Zeile anpassen
  if (_teleprompterData.mode !== "speech" && _teleprompterData.mode !== "hybrid") {
    return;
  }
  if (!chunk || !chunk.text) return;

  const rawChunkText = chunk.text.toLowerCase().trim();
  const chunkWords = rawChunkText.split(/\s+/).filter((w) => w.length > 2);
  if (chunkWords.length === 0) return;

  // Suche vorzugsweise in der Nähe der aktuellen Zeile [_currentLineIndex, _currentLineIndex + 4]
  let bestIdx = -1;
  let bestScore = 0;

  const lookAhead = Math.min(_lines.length, _currentLineIndex + 6);
  for (let i = Math.max(0, _currentLineIndex - 1); i < lookAhead; i++) {
    const lineLower = _lines[i].toLowerCase();
    let matches = 0;
    for (const w of chunkWords) {
      if (lineLower.includes(w)) {
        matches++;
      }
    }
    const score = matches / Math.max(1, chunkWords.length);
    if (score > bestScore && score >= 0.35) {
      bestScore = score;
      bestIdx = i;
    }
  }

  if (bestIdx !== -1 && bestIdx !== _currentLineIndex) {
    _currentLineIndex = bestIdx;
    highlightActiveLine(true);
  }
}

function handleStateUpdate(state) {
  if (state && typeof state.prompter_line === "number" && state.prompter_line >= 0) {
    // Wenn Recorder einen Zeilensprung meldet (z. B. Companion-Pedal)
    if (_teleprompterData.mode === "manual" && state.prompter_line !== _currentLineIndex) {
      _currentLineIndex = Math.min(_lines.length - 1, state.prompter_line);
      highlightActiveLine(true);
    }
  }
}

function handleConnectionChange() {
  updateControlsUI();
}

function handleGlobalKeyDown(e) {
  if (e.target.tagName === "TEXTAREA" || e.target.tagName === "INPUT") {
    return; // Im Editor tippen nicht als Hotkey abfangen
  }

  if (e.code === "Space") {
    e.preventDefault();
    togglePlay();
  } else if (e.key === "ArrowDown" || e.key === "PageDown") {
    e.preventDefault();
    jumpLine(1);
  } else if (e.key === "ArrowUp" || e.key === "PageUp") {
    e.preventDefault();
    jumpLine(-1);
  } else if (e.key === "Escape") {
    e.preventDefault();
    resetToStart();
  }
}

// ---------------------------------------------------------------------------
// Persistenz
// ---------------------------------------------------------------------------

let _saveTimeout = null;
function _saveDataDebounced() {
  if (_saveTimeout) clearTimeout(_saveTimeout);
  _saveTimeout = setTimeout(() => {
    _saveData();
  }, 1000);
}

async function _saveData() {
  if (!_activeProjectId) return;
  _teleprompterData.current_line = _currentLineIndex;
  await api.updateTeleprompter(_activeProjectId, _teleprompterData);
}
