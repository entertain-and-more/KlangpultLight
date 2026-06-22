/**
 * main.js — Einstiegspunkt des PodcastPlaners.
 *
 * Verwaltet Tab-Navigation und Recorder-Verbindungsstatus.
 * Mounted die einzelnen Views (Bibliothek, Projekte) on demand.
 */

import { checkLibraryHealth, checkProjectsHealth } from "./api.js";
import { mount as mountBibliothek, unmount as unmountBibliothek, reload as reloadBibliothek } from "./bibliothek.js";
import { mount as mountProjekte, unmount as unmountProjekte, reload as reloadProjekte } from "./projekte.js";

// ---------------------------------------------------------------------------
// Tabs
// ---------------------------------------------------------------------------

const TABS = {
  bibliothek: {
    label: "Bibliothek",
    mount: (c, d) => mountBibliothek(c, d),
    unmount: unmountBibliothek,
  },
  projekte: {
    label: "Projekte",
    mount: (c, d) => mountProjekte(c, d),
    unmount: unmountProjekte,
  },
};

let _currentTab = null;

// ---------------------------------------------------------------------------
// DOM-Refs
// ---------------------------------------------------------------------------

const navTabs = document.getElementById("nav-tabs");
const statusDot = document.getElementById("status-dot");
const statusText = document.getElementById("status-text");
const mainEl = document.getElementById("app-main");
const detailPanel = document.getElementById("detail-panel");

// Für jeden Tab ein View-Div + Nav-Button anlegen
const viewEls = {};
for (const [id, tab] of Object.entries(TABS)) {
  // View-Element
  const view = document.createElement("div");
  view.id = `view-${id}`;
  view.className = "view";
  mainEl.insertBefore(view, detailPanel);
  viewEls[id] = view;

  // Nav-Button
  const btn = document.createElement("button");
  btn.className = "nav-tab";
  btn.textContent = tab.label;
  btn.dataset.tab = id;
  btn.addEventListener("click", () => switchTab(id));
  navTabs.appendChild(btn);
}

// ---------------------------------------------------------------------------
// Tab-Wechsel
// ---------------------------------------------------------------------------

function switchTab(id) {
  if (_currentTab === id) return;

  // Vorigen unmounten
  if (_currentTab && TABS[_currentTab]) {
    TABS[_currentTab].unmount();
    viewEls[_currentTab].classList.remove("active");
    navTabs.querySelector(`[data-tab="${_currentTab}"]`)?.classList.remove("active");
  }

  // Detail-Panel leeren
  detailPanel.innerHTML = "";
  detailPanel.classList.remove("open");

  _currentTab = id;
  viewEls[id].classList.add("active");
  navTabs.querySelector(`[data-tab="${id}"]`)?.classList.add("active");

  // Neuen View mounten
  viewEls[id].innerHTML = "";
  TABS[id].mount(viewEls[id], detailPanel);
}

// ---------------------------------------------------------------------------
// Status-Check (Recorder-Verbindung)
// ---------------------------------------------------------------------------

async function checkStatus() {
  const [lib, proj] = await Promise.all([
    checkLibraryHealth(),
    checkProjectsHealth(),
  ]);

  const online = lib.ok || proj.ok;

  statusDot.className = "status-dot " + (online ? "online" : "offline");
  statusText.textContent = online
    ? "Recorder verbunden"
    : "Recorder nicht erreichbar";
}

// Alle 10 Sekunden Status prüfen
checkStatus();
setInterval(checkStatus, 10_000);

// ---------------------------------------------------------------------------
// Reload-Button (Bibliothek)
// ---------------------------------------------------------------------------

const reloadBtn = document.getElementById("btn-reload");
if (reloadBtn) {
  reloadBtn.addEventListener("click", () => {
    if (_currentTab === "bibliothek") reloadBibliothek();
    else if (_currentTab === "projekte") reloadProjekte();
    else switchTab(_currentTab);
  });
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

switchTab("bibliothek");
