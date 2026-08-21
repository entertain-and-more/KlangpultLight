/**
 * monitor.js — KI-Monitor-Modul für den Klangpult light – Planer (Phase 8).
 *
 * Stellt ein ruhiges Assistenz-Panel für Aufnahme & Moderation bereit:
 *   - Speist sich aus Live-Transkriptions-Chunks (STT) und Projekt-Briefing
 *   - Erzeugt strukturierte Assistenz-Karten: Fakten, Moderations-Impulse, Kapitelmarker, Zusammenfassungen
 *   - 1-Klick Kapitelmarker-Trigger an den Recorder über remote.js
 *   - 100% lokal & offline-fähig mit opt-in Cloud-/Webrecherche-Schaltern
 *   - Klare Signalisierung von Fehlern und Offline-Zuständen
 */

import * as api from "./api.js";
import { el, formatDuration } from "./util.js";
import { remote } from "./remote.js";

let _container = null;
let _projects = [];
let _activeProjectId = null;
let _monitorData = {
  briefing: "",
  keywords: [],
  cards: [],
  cloud_opt_in: false,
  web_search: false,
};

let _transcriptFeed = [];
let _isFeedPaused = false;
let _speechUnsubscribe = null;
let _connUnsubscribe = null;
let _autoAnalyzeTimer = null;
let _pendingTextBuffer = "";

// ---------------------------------------------------------------------------
// Lifecycle: mount / unmount / reload
// ---------------------------------------------------------------------------

export async function mount(container) {
  _container = container;
  _container.innerHTML = "";

  _speechUnsubscribe = remote.on("transcript_chunk", handleTranscriptChunk);
  _connUnsubscribe = remote.on("connection_change", handleConnectionChange);

  await reload();
}

export function unmount() {
  if (_speechUnsubscribe) { _speechUnsubscribe(); _speechUnsubscribe = null; }
  if (_connUnsubscribe) { _connUnsubscribe(); _connUnsubscribe = null; }
  if (_autoAnalyzeTimer) { clearTimeout(_autoAnalyzeTimer); _autoAnalyzeTimer = null; }
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
    const monRes = await api.getMonitor(_activeProjectId);
    if (monRes.ok && monRes.data && monRes.data.monitor) {
      _monitorData = Object.assign(_monitorData, monRes.data.monitor);
    }
  }

  render();
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function render() {
  if (!_container) return;
  _container.innerHTML = "";

  const root = el("div", { className: "monitor-container" });

  // 1. Header Toolbar
  const header = el("div", { className: "monitor-header card" }, [
    el("div", { className: "monitor-header-top" }, [
      el("div", { className: "form-group monitor-project-select-group" }, [
        el("label", { for: "monitor-project-select", textContent: "Projekt für Assistenz-Kontext" }),
        (() => {
          const select = el("select", {
            id: "monitor-project-select",
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

      el("div", { className: "monitor-status-badges" }, [
        el("div", {
          id: "monitor-stt-status",
          className: `badge ${remote.isConnected ? "badge-fertig" : "badge-geplant"}`,
          textContent: remote.isConnected ? "STT Live verbunden" : "Recorder / STT getrennt",
        }),
        el("div", {
          id: "monitor-engine-badge",
          className: "badge badge-original",
          textContent: "Engine: Whisper (Lokal)",
        }),
      ]),
    ]),

    // Settings & Mode toggles
    el("div", { className: "monitor-settings-row" }, [
      el("div", { className: "monitor-toggle-item" }, [
        el("input", {
          type: "checkbox",
          id: "monitor-cloud-toggle",
          checked: Boolean(_monitorData.cloud_opt_in),
          onChange: (e) => {
            _monitorData.cloud_opt_in = e.target.checked;
            _saveData();
          },
        }),
        el("label", {
          for: "monitor-cloud-toggle",
          textContent: "Cloud-KI opt-in (Standard: Aus / 100% Offline)",
        }),
      ]),

      el("div", { className: "monitor-toggle-item" }, [
        el("input", {
          type: "checkbox",
          id: "monitor-web-toggle",
          checked: Boolean(_monitorData.web_search),
          onChange: (e) => {
            _monitorData.web_search = e.target.checked;
            _saveData();
          },
        }),
        el("label", {
          for: "monitor-web-toggle",
          textContent: "Webrecherche (Standard: Aus)",
        }),
      ]),

      el("div", { className: "monitor-stream-actions" }, [
        el("button", {
          id: "monitor-pause-feed-btn",
          className: `btn ${_isFeedPaused ? "btn-primary" : "btn-ghost"}`,
          textContent: _isFeedPaused ? "▶ Stream fortsetzen" : "⏸ Stream anhalten",
          "aria-label": _isFeedPaused ? "Transkript-Stream fortsetzen" : "Transkript-Stream anhalten",
          onClick: togglePauseFeed,
        }),
        el("button", {
          className: "btn btn-ghost",
          textContent: "Feed leeren",
          "aria-label": "Transkriptionsverlauf leeren",
          onClick: clearTranscriptFeed,
        }),
      ]),
    ]),
  ]);

  // 2. Main Content Split: Live-Transkription (links) vs. Assistenz-Karten & Briefing (rechts)
  const contentRow = el("div", { className: "monitor-content-row" }, [
    // Linke Spalte: Live Transkriptions-Feed
    el("div", { className: "monitor-feed-column card" }, [
      el("div", { className: "card-header" }, [
        el("h3", { textContent: "Live-Transkription (STT-Feed)" }),
        el("span", {
          id: "monitor-feed-count",
          className: "badge badge-geplant",
          textContent: `${_transcriptFeed.length} Chunks`,
        }),
      ]),
      el("div", {
        id: "monitor-feed-list",
        className: "monitor-feed-list",
        role: "log",
        "aria-live": "polite",
        "aria-label": "Echtzeit-Transkriptionsstream",
      }),
    ]),

    // Rechte Spalte: Briefing-Kontext & Assistenz-Karten
    el("div", { className: "monitor-insights-column" }, [
      // Briefing Accordion / Box
      el("div", { className: "monitor-briefing-card card" }, [
        el("div", { className: "card-header" }, [
          el("h3", { textContent: "Themen & Briefing-Leitfaden" }),
          el("button", {
            className: "btn btn-ghost btn-sm",
            textContent: "Speichern",
            onClick: _saveData,
          }),
        ]),
        el("div", { className: "form-group" }, [
          el("label", { for: "monitor-briefing-input", textContent: "Projekt-Briefing / Notizen" }),
          el("textarea", {
            id: "monitor-briefing-input",
            rows: 3,
            value: _monitorData.briefing || "",
            placeholder: "Trage hier zentrale Themen, Fragen oder Schwerpunkte der Episode ein...",
            onInput: (e) => {
              _monitorData.briefing = e.target.value;
              _saveDataDebounced();
            },
          }),
        ]),
        el("div", { className: "form-group" }, [
          el("label", { for: "monitor-keywords-input", textContent: "Schlüsselwörter (kommagetrennt)" }),
          el("input", {
            id: "monitor-keywords-input",
            type: "text",
            value: (_monitorData.keywords || []).join(", "),
            placeholder: "z.B. Audio, Mikrofone, Routing, Latenz, Soundboard",
            onInput: (e) => {
              _monitorData.keywords = e.target.value
                .split(",")
                .map((s) => s.trim())
                .filter((s) => s.length > 0);
              _saveDataDebounced();
            },
          }),
        ]),
      ]),

      // Assistenz-Karten (Fakten, Nachfragen, Kapitelmarker)
      el("div", { className: "monitor-cards-container card" }, [
        el("div", { className: "card-header" }, [
          el("h3", { textContent: "Strukturierte KI-Impulse & Fakten" }),
          el("button", {
            className: "btn btn-ghost btn-sm",
            textContent: "Karten leeren",
            onClick: () => {
              _monitorData.cards = [];
              renderCards();
              _saveData();
            },
          }),
        ]),
        el("div", {
          id: "monitor-cards-list",
          className: "monitor-cards-list",
          role: "region",
          "aria-label": "KI-Assistenzkarten",
        }),
      ]),
    ]),
  ]);

  root.appendChild(header);
  root.appendChild(contentRow);
  _container.appendChild(root);

  renderFeed();
  renderCards();
  updateStatusUI();
}

// ---------------------------------------------------------------------------
// Feed & Cards Rendering
// ---------------------------------------------------------------------------

function renderFeed() {
  const feedList = document.getElementById("monitor-feed-list");
  if (!feedList) return;
  feedList.innerHTML = "";

  if (_transcriptFeed.length === 0) {
    feedList.appendChild(
      el("div", { className: "empty-state" }, [
        el("div", { className: "empty-icon", textContent: "🎙️" }),
        el("p", { textContent: "Warte auf Live-Transkription aus dem Recorder..." }),
        el("small", {
          textContent: "Sobald eine Aufnahme im Recorder läuft, erscheinen hier die Text-Chunks in Echtzeit.",
        }),
      ])
    );
    return;
  }

  _transcriptFeed.forEach((chunk) => {
    const bubble = el("div", {
      className: `monitor-feed-bubble ${chunk.is_final ? "final" : "interim"}`,
    }, [
      el("div", { className: "feed-bubble-meta" }, [
        el("span", { className: "feed-timestamp", textContent: formatDuration(chunk.t_start) }),
        el("span", { className: "badge badge-original", textContent: chunk.engine || "whisper" }),
        chunk.is_final ? null : el("span", { className: "badge badge-geplant", textContent: "vorläufig" }),
      ]),
      el("div", { className: "feed-bubble-text", textContent: chunk.text }),
    ]);

    feedList.appendChild(bubble);
  });

  // Auto-Scroll nach unten
  feedList.scrollTop = feedList.scrollHeight;

  const countBadge = document.getElementById("monitor-feed-count");
  if (countBadge) countBadge.textContent = `${_transcriptFeed.length} Chunks`;
}

function renderCards() {
  const cardsList = document.getElementById("monitor-cards-list");
  if (!cardsList) return;
  cardsList.innerHTML = "";

  const cards = _monitorData.cards || [];
  if (cards.length === 0) {
    cardsList.appendChild(
      el("div", { className: "empty-state" }, [
        el("div", { className: "empty-icon", textContent: "💡" }),
        el("p", { textContent: "Noch keine Assistenz-Impulse generiert." }),
        el("small", {
          textContent: "Strukturierte Fakten, Moderations-Nachfragen und Kapitelmarker erscheinen automatisch.",
        }),
      ])
    );
    return;
  }

  cards.forEach((card, idx) => {
    const cardEl = el("div", {
      className: `monitor-insight-card card-${card.type || "fact_check"}`,
    }, [
      el("div", { className: "insight-card-header" }, [
        el("span", { className: `badge badge-${card.type || "fact"}`, textContent: _cardTypeLabel(card.type) }),
        el("strong", { textContent: card.title || "Hinweis" }),
        el("button", {
          className: "btn-icon-close",
          "aria-label": "Karte verwerfen",
          onClick: () => {
            _monitorData.cards.splice(idx, 1);
            renderCards();
            _saveData();
          },
          textContent: "×",
        }),
      ]),
      el("div", { className: "insight-card-body" }, [
        el("p", { textContent: card.content }),
      ]),
      // Optionale Aktionsbuttons je Kartentyp
      card.type === "chapter_suggestion"
        ? el("div", { className: "insight-card-footer" }, [
            el("button", {
              className: "btn btn-primary btn-sm",
              textContent: "Als Kapitelmarker setzen",
              "aria-label": `Kapitelmarker »${card.label || card.title}« setzen`,
              onClick: () => {
                const label = card.label || card.title || "Neuer Abschnitt";
                remote.sendInsertChapterMarker(label);
                card.applied = true;
                renderCards();
              },
            }),
            card.applied ? el("span", { className: "badge badge-fertig", textContent: "Gesetzt ✔" }) : null,
          ])
        : null,
    ]);

    cardsList.appendChild(cardEl);
  });
}

function _cardTypeLabel(type) {
  const map = {
    fact_check: "Fakt / Begriff",
    followup_question: "Nachfrage-Impuls",
    chapter_suggestion: "Kapitelmarker",
    summary_bullet: "Kernaussage",
  };
  return map[type] || "Hinweis";
}

function updateStatusUI() {
  const sttBadge = document.getElementById("monitor-stt-status");
  if (sttBadge) {
    sttBadge.textContent = remote.isConnected ? "STT Live verbunden" : "Recorder / STT getrennt";
    sttBadge.className = `badge ${remote.isConnected ? "badge-fertig" : "badge-geplant"}`;
  }
}

// ---------------------------------------------------------------------------
// Event Handling & Analyse-Engine
// ---------------------------------------------------------------------------

function handleTranscriptChunk(chunk) {
  if (_isFeedPaused || !chunk || !chunk.text) return;

  _transcriptFeed.push(chunk);
  if (_transcriptFeed.length > 200) {
    _transcriptFeed.shift();
  }
  renderFeed();

  // Transkripttext puffern und zur strukturierten Analyse senden
  if (chunk.is_final) {
    _pendingTextBuffer += " " + chunk.text;
    _scheduleAnalysis();
  }
}

function handleConnectionChange() {
  updateStatusUI();
}

export function togglePauseFeed() {
  _isFeedPaused = !_isFeedPaused;
  const btn = document.getElementById("monitor-pause-feed-btn");
  if (btn) {
    btn.textContent = _isFeedPaused ? "▶ Stream fortsetzen" : "⏸ Stream anhalten";
    btn.className = `btn ${_isFeedPaused ? "btn-primary" : "btn-ghost"}`;
  }
}

export function clearTranscriptFeed() {
  _transcriptFeed = [];
  _pendingTextBuffer = "";
  renderFeed();
}

function _scheduleAnalysis() {
  if (_autoAnalyzeTimer) clearTimeout(_autoAnalyzeTimer);
  _autoAnalyzeTimer = setTimeout(async () => {
    const textToAnalyze = _pendingTextBuffer.trim();
    _pendingTextBuffer = "";
    if (!textToAnalyze || !_activeProjectId) return;

    try {
      const res = await api.analyzeMonitorText(_activeProjectId, textToAnalyze);
      if (res.ok && res.data && Array.isArray(res.data.cards)) {
        // Neue Karten vorne anfügen (max. 15 Karten vorhalten)
        _monitorData.cards = [...res.data.cards, ...(_monitorData.cards || [])].slice(0, 15);
        renderCards();
        _saveData();
      }
    } catch (err) {
      console.warn("Fehler bei der Monitor-Analyse:", err);
    }
  }, 1200);
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
  await api.updateMonitor(_activeProjectId, _monitorData);
}
