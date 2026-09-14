/**
 * main.js — Einstiegspunkt des Klangpult light – Planers.
 *
 * Verwaltet Tab-Navigation und Recorder-Verbindungsstatus.
 * Mounted die einzelnen Views (Bibliothek, Projekte) on demand.
 */

import { getBridgeStatus } from "./api.js";
import { mount as mountBibliothek, unmount as unmountBibliothek, reload as reloadBibliothek } from "./bibliothek.js";
import { mount as mountProjekte, unmount as unmountProjekte, reload as reloadProjekte } from "./projekte.js";
import { mount as mountAssets, unmount as unmountAssets, reload as reloadAssets } from "./assets.js";
import { mount as mountTeleprompter, unmount as unmountTeleprompter, reload as reloadTeleprompter } from "./teleprompter.js";
import { mount as mountMonitor, unmount as unmountMonitor, reload as reloadMonitor } from "./monitor.js";
import { remote } from "./remote.js";

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
  assets: {
    label: "Assets & Line",
    mount: (c, d) => mountAssets(c, d),
    unmount: unmountAssets,
  },
  teleprompter: {
    label: "Teleprompter",
    mount: (c, d) => mountTeleprompter(c, d),
    unmount: unmountTeleprompter,
  },
  monitor: {
    label: "KI-Monitor",
    mount: (c, d) => mountMonitor(c, d),
    unmount: unmountMonitor,
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
const tabIds = Object.keys(TABS);
navTabs.setAttribute("role", "tablist");
for (const [id, tab] of Object.entries(TABS)) {
  // View-Element
  const view = document.createElement("div");
  view.id = `view-${id}`;
  view.className = "view";
  view.setAttribute("role", "tabpanel");
  view.setAttribute("aria-labelledby", `tab-${id}`);
  mainEl.insertBefore(view, detailPanel);
  viewEls[id] = view;

  // Nav-Button
  const btn = document.createElement("button");
  btn.className = "nav-tab";
  btn.textContent = tab.label;
  btn.dataset.tab = id;
  btn.type = "button";
  btn.id = `tab-${id}`;
  btn.setAttribute("role", "tab");
  btn.setAttribute("aria-controls", `view-${id}`);
  btn.setAttribute("aria-selected", "false");
  btn.tabIndex = -1;
  btn.addEventListener("click", () => switchTab(id));
  btn.addEventListener("keydown", (event) => {
    const currentIndex = tabIds.indexOf(id);
    let targetIndex = null;
    if (event.key === "ArrowRight") targetIndex = (currentIndex + 1) % tabIds.length;
    if (event.key === "ArrowLeft") targetIndex = (currentIndex - 1 + tabIds.length) % tabIds.length;
    if (event.key === "Home") targetIndex = 0;
    if (event.key === "End") targetIndex = tabIds.length - 1;
    if (targetIndex === null) return;

    event.preventDefault();
    const targetId = tabIds[targetIndex];
    switchTab(targetId);
    navTabs.querySelector(`[data-tab="${targetId}"]`)?.focus();
  });
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
    const previousButton = navTabs.querySelector(`[data-tab="${_currentTab}"]`);
    previousButton?.classList.remove("active");
    previousButton?.setAttribute("aria-selected", "false");
    if (previousButton) previousButton.tabIndex = -1;
  }

  // Detail-Panel leeren
  detailPanel.innerHTML = "";
  detailPanel.classList.remove("open");

  _currentTab = id;
  viewEls[id].classList.add("active");
  const activeButton = navTabs.querySelector(`[data-tab="${id}"]`);
  activeButton?.classList.add("active");
  activeButton?.setAttribute("aria-selected", "true");
  if (activeButton) activeButton.tabIndex = 0;

  // Neuen View mounten
  viewEls[id].innerHTML = "";
  TABS[id].mount(viewEls[id], detailPanel);
}

// ---------------------------------------------------------------------------
// Status-Check (Recorder-Verbindung)
// ---------------------------------------------------------------------------

async function checkStatus() {
  const result = await getBridgeStatus();
  const status = result.ok ? result.data.status : "offline";
  const labels = {
    online: "Recorder verbunden",
    partial: "Recorder teilweise erreichbar",
    offline: "Recorder nicht erreichbar",
  };
  statusDot.className = "status-dot " + (labels[status] ? status : "offline");
  statusText.textContent = labels[status] || labels.offline;
}

// Alle 10 Sekunden Status prüfen
checkStatus();
setInterval(checkStatus, 10_000);

// ---------------------------------------------------------------------------
// Reload-Button (Bibliothek / Projekte / Assets / Teleprompter / Monitor)
// ---------------------------------------------------------------------------

const reloadBtn = document.getElementById("btn-reload");
if (reloadBtn) {
  reloadBtn.addEventListener("click", () => {
    if (_currentTab === "bibliothek") reloadBibliothek();
    else if (_currentTab === "projekte") reloadProjekte();
    else if (_currentTab === "assets") reloadAssets();
    else if (_currentTab === "teleprompter") reloadTeleprompter();
    else if (_currentTab === "monitor") reloadMonitor();
    else switchTab(_currentTab);
  });
}

// ---------------------------------------------------------------------------
// Start
// ---------------------------------------------------------------------------

remote.connect();
switchTab("bibliothek");
