/**
 * bibliothek.js — Aufnahmen-Bibliothek-View des PodcastPlaners.
 *
 * Zeigt alle Aufnahmen aus /api/library mit Branch-Baum.
 * Beim Klick auf eine Aufnahme öffnet sich das Detail-Panel rechts.
 * Kein Schreiben — die Bibliothek ist read-only (Aufnahmen entstehen im Recorder).
 */

import { listRecordings } from "./api.js";
import { formatDateTime, formatDuration, el } from "./util.js";

// DOM-Referenzen (werden beim Mount gesetzt)
let _container = null;
let _detail = null;
let _currentId = null;

// ---------------------------------------------------------------------------
// Mount
// ---------------------------------------------------------------------------

export function mount(container, detailPanel) {
  _container = container;
  _detail = detailPanel;
  render();
}

export function unmount() {
  if (_detail) _detail.classList.remove("open");
  _currentId = null;
}

// ---------------------------------------------------------------------------
// Hauptrender
// ---------------------------------------------------------------------------

async function render() {
  if (!_container) return;
  _container.innerHTML = "";

  // Lade-Spinner
  const spinner = el("div", { className: "empty-state" }, [
    el("div", { className: "spinner" }),
    el("p", { textContent: "Aufnahmen werden geladen…" }),
  ]);
  _container.appendChild(spinner);

  const result = await listRecordings();

  if (!result.ok) {
    _container.innerHTML = "";
    const banner = el("div", { className: "error-banner" }, [
      `Bibliothek nicht erreichbar: ${result.error}`,
      el("br"),
      el("small", { textContent: "Bitte PodcastRecorder starten (Bridge läuft auf Port 8767)." }),
    ]);
    _container.appendChild(banner);
    return;
  }

  const recordings = result.data.recordings || [];
  _container.innerHTML = "";

  if (recordings.length === 0) {
    _container.appendChild(
      el("div", { className: "empty-state" }, [
        el("div", { className: "empty-icon", textContent: "🎙" }),
        el("p", { textContent: "Noch keine Aufnahmen vorhanden. Starte den PodcastRecorder, um deine erste Aufnahme zu machen." }),
      ])
    );
    return;
  }

  // Header
  const header = el("div", { className: "card-header" }, [
    el("h2", { textContent: "Aufnahmen" }),
    el("span", { className: "badge badge-geplant", textContent: `${recordings.length} Aufnahme(n)` }),
  ]);
  _container.appendChild(header);

  // Liste
  const list = el("div", { className: "item-list" });
  for (const rec of recordings) {
    list.appendChild(_renderRecordingItem(rec));
  }
  _container.appendChild(list);
}

// ---------------------------------------------------------------------------
// Aufnahme-Listeneintrag
// ---------------------------------------------------------------------------

function _renderRecordingItem(rec) {
  const branches = rec.branches || [];
  const original = branches.find(b => b.is_original);
  const dauer = original ? original.duration : rec.duration || 0;

  const meta = [
    formatDateTime(rec.created_at),
    dauer > 0 ? formatDuration(dauer) : null,
    branches.length > 0 ? `${branches.length} Branch(es)` : null,
  ].filter(Boolean).join("  ·  ");

  const item = el("div", { className: "list-item" + (_currentId === rec.recording_id ? " selected" : "") }, [
    el("div", { className: "list-item-main" }, [
      el("div", { className: "list-item-title", textContent: rec.title || "Ohne Titel" }),
      el("div", { className: "list-item-meta", textContent: meta }),
    ]),
  ]);

  item.addEventListener("click", () => {
    // Selektion aktualisieren
    document.querySelectorAll(".view.active .list-item").forEach(i => i.classList.remove("selected"));
    item.classList.add("selected");
    _currentId = rec.recording_id;
    _renderDetail(rec);
  });

  return item;
}

// ---------------------------------------------------------------------------
// Detail-Panel
// ---------------------------------------------------------------------------

function _renderDetail(rec) {
  if (!_detail) return;
  _detail.innerHTML = "";
  _detail.classList.add("open");

  const branches = rec.branches || [];

  _detail.appendChild(el("h2", { textContent: rec.title || "Ohne Titel" }));

  // Metadaten
  _detail.appendChild(_detailSection("Aufnahme-ID", rec.recording_id));
  _detail.appendChild(_detailSection("Erstellt", formatDateTime(rec.created_at)));
  if (rec.description) _detail.appendChild(_detailSection("Beschreibung", rec.description));
  if (rec.tags && rec.tags.length > 0) {
    _detail.appendChild(_detailSection("Tags", rec.tags.join(", ")));
  }

  _detail.appendChild(el("div", { className: "sep" }));

  // Branch-Baum
  _detail.appendChild(el("h3", { textContent: `Branches (${branches.length})` }));
  if (branches.length === 0) {
    _detail.appendChild(el("p", { className: "list-item-meta", textContent: "Keine Branches vorhanden." }));
  } else {
    const branchList = el("div", { className: "branch-list" });
    for (const b of branches) {
      const badge = b.is_original
        ? el("span", { className: "badge badge-original", textContent: "Original" })
        : null;
      const dauer = b.duration > 0 ? el("span", { className: "list-item-meta", textContent: formatDuration(b.duration) }) : null;
      branchList.appendChild(
        el("div", { className: "branch-item" }, [
          el("span", { textContent: b.name }),
          badge,
          dauer,
        ])
      );
    }
    _detail.appendChild(branchList);
  }
}

function _detailSection(label, value) {
  return el("div", { className: "detail-section" }, [
    el("div", { className: "detail-label", textContent: label }),
    el("div", { className: "detail-value", textContent: value }),
  ]);
}

// ---------------------------------------------------------------------------
// Öffentliche Methode zum Neuladen
// ---------------------------------------------------------------------------

export function reload() {
  if (_container) render();
}
