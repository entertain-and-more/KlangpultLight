/**
 * projekte.js — Projektplanung-View des Klangpult light – Planers.
 *
 * CRUD für Projekte und deren Episoden gegen /api/projects (Port 8769).
 * Kein Framework — reines Vanilla JS ESM.
 */

import {
  listProjects, createProject, updateProject, deleteProject,
  listEpisodes, createEpisode, updateEpisode, deleteEpisode,
} from "./api.js";
import { formatDateTime, statusBadgeClass, el, bestätigen } from "./util.js";

let _container = null;
let _detail = null;
let _currentProject = null;  // {project_id, title, description, ...}
let _episodes = [];           // Episoden des aktuellen Projekts

// ---------------------------------------------------------------------------
// Mount / Unmount
// ---------------------------------------------------------------------------

export function mount(container, detailPanel) {
  _container = container;
  _detail = detailPanel;
  render();
}

export function unmount() {
  if (_detail) _detail.classList.remove("open");
  _currentProject = null;
  _episodes = [];
}

export function reload() {
  if (_container) render();
}

// ---------------------------------------------------------------------------
// Hauptrender
// ---------------------------------------------------------------------------

async function render() {
  if (!_container) return;
  _container.innerHTML = "";

  // Lade-Spinner (konsistent mit bibliothek.js)
  const spinner = el("div", { className: "empty-state" }, [
    el("div", { className: "spinner" }),
    el("p", { textContent: "Projekte werden geladen…" }),
  ]);
  _container.appendChild(spinner);

  const result = await listProjects();

  _container.innerHTML = "";  // Spinner entfernen

  if (!result.ok) {
    _container.appendChild(
      el("div", { className: "error-banner" }, [
        `Projektdienst nicht erreichbar: ${result.error}`,
        el("br"),
        el("small", { textContent: "Bitte Klangpult light – Recorder starten (Bridge auf Port 8769)." }),
      ])
    );
    return;
  }

  const projects = result.data.projects || [];

  // Zwei-Spalten-Layout: Liste links, Detail rechts
  const header = el("div", { className: "card-header" }, [
    el("h2", { textContent: "Projekte" }),
    el("button", {
      className: "btn btn-primary",
      textContent: "+ Neues Projekt",
      onClick: _openNeuProjektModal,
    }),
  ]);
  _container.appendChild(header);

  if (projects.length === 0) {
    _container.appendChild(
      el("div", { className: "empty-state" }, [
        el("div", { className: "empty-icon", textContent: "📋" }),
        el("p", { textContent: "Noch kein Projekt angelegt. Erstelle dein erstes Podcast-Projekt!" }),
        el("button", {
          className: "btn btn-primary",
          textContent: "+ Neues Projekt",
          onClick: _openNeuProjektModal,
        }),
      ])
    );
    return;
  }

  const list = el("div", { className: "item-list" });
  for (const p of projects) {
    list.appendChild(_renderProjectItem(p));
  }
  _container.appendChild(list);

  // Falls noch ein Projekt ausgewählt war, Detail neu laden
  if (_currentProject) {
    const found = projects.find(p => p.project_id === _currentProject.project_id);
    if (found) {
      _currentProject = found;
      await _renderDetail(found);
    }
  }
}

// ---------------------------------------------------------------------------
// Projekt-Listeneintrag
// ---------------------------------------------------------------------------

function _renderProjectItem(project) {
  const isSelected = _currentProject && _currentProject.project_id === project.project_id;
  const item = el("div", {
    className: "list-item" + (isSelected ? " selected" : ""),
    tabIndex: 0,
    role: "button",
    "aria-selected": isSelected ? "true" : "false",
    "aria-label": `Projekt ${project.title}`,
  }, [
    el("div", { className: "list-item-main" }, [
      el("div", { className: "list-item-title", textContent: project.title }),
      el("div", {
        className: "list-item-meta",
        textContent: `Erstellt: ${formatDateTime(project.created_at)}` +
          (project.description ? `  ·  ${project.description.slice(0, 50)}` : ""),
      }),
    ]),
    el("div", { className: "list-item-actions" }, [
      el("button", {
        className: "btn btn-ghost",
        title: "Projekt bearbeiten",
        "aria-label": `Projekt ${project.title} bearbeiten`,
        textContent: "✏",
        onClick: (e) => { e.stopPropagation(); _openBearbeitenModal(project); },
      }),
      el("button", {
        className: "btn btn-danger",
        title: "Projekt löschen",
        "aria-label": `Projekt ${project.title} löschen`,
        textContent: "🗑",
        onClick: (e) => { e.stopPropagation(); _deleteProject(project); },
      }),
    ]),
  ]);

  const selectHandler = async () => {
    document.querySelectorAll(".view.active .list-item").forEach(i => {
      i.classList.remove("selected");
      i.setAttribute("aria-selected", "false");
    });
    item.classList.add("selected");
    item.setAttribute("aria-selected", "true");
    _currentProject = project;
    await _renderDetail(project);
  };

  item.addEventListener("click", selectHandler);
  item.addEventListener("keydown", (e) => {
    if (e.key === "Enter" || e.key === " " || e.code === "Space") {
      e.preventDefault();
      selectHandler();
    }
  });

  return item;
}

// ---------------------------------------------------------------------------
// Detail-Panel (Episoden)
// ---------------------------------------------------------------------------

async function _renderDetail(project) {
  if (!_detail) return;
  _detail.innerHTML = "";
  _detail.classList.add("open");

  // Projekt-Info
  _detail.appendChild(el("h2", { textContent: project.title }));
  if (project.description) {
    _detail.appendChild(el("p", { className: "detail-value", textContent: project.description }));
  }
  _detail.appendChild(el("div", {
    className: "detail-section",
  }, [
    el("div", { className: "detail-label", textContent: "Erstellt" }),
    el("div", { className: "detail-value", textContent: formatDateTime(project.created_at) }),
  ]));
  _detail.appendChild(el("div", { className: "sep" }));

  // Episoden-Header
  _detail.appendChild(
    el("div", { className: "card-header" }, [
      el("h3", { textContent: "Episoden" }),
      el("button", {
        className: "btn btn-primary",
        textContent: "+ Episode",
        onClick: () => _openNeuEpisodeModal(project),
      }),
    ])
  );

  // Episoden laden
  const epResult = await listEpisodes(project.project_id);
  if (!epResult.ok) {
    _detail.appendChild(
      el("div", { className: "error-banner", textContent: `Fehler: ${epResult.error}` })
    );
    return;
  }

  _episodes = epResult.data.episodes || [];

  if (_episodes.length === 0) {
    _detail.appendChild(
      el("div", { className: "empty-state" }, [
        el("p", { textContent: "Noch keine Episoden. Lege die erste Episode dieses Projekts an." }),
      ])
    );
    return;
  }

  const epList = el("div", { className: "item-list" });
  for (const ep of _episodes) {
    epList.appendChild(_renderEpisodeItem(ep, project));
  }
  _detail.appendChild(epList);
}

function _renderEpisodeItem(episode, project) {
  const badgeClass = statusBadgeClass(episode.status || "geplant");
  return el("div", { className: "list-item" }, [
    el("div", { className: "list-item-main" }, [
      el("div", { className: "list-item-title", textContent: episode.title }),
      el("div", { className: "list-item-meta" }, [
        el("span", { className: `badge ${badgeClass}`, textContent: episode.status || "geplant" }),
        episode.notes
          ? el("span", { textContent: `  ·  ${episode.notes.slice(0, 60)}` })
          : null,
      ]),
    ]),
    el("div", { className: "list-item-actions" }, [
      el("button", {
        className: "btn btn-ghost",
        textContent: "✏",
        title: "Episode bearbeiten",
        "aria-label": `Episode ${episode.title} bearbeiten`,
        onClick: (e) => { e.stopPropagation(); _openEpisodeModal(project, episode); },
      }),
      el("button", {
        className: "btn btn-danger",
        textContent: "🗑",
        title: "Episode löschen",
        "aria-label": `Episode ${episode.title} löschen`,
        onClick: (e) => { e.stopPropagation(); _deleteEpisode(project, episode); },
      }),
    ]),
  ]);
}

async function _deleteEpisode(project, episode) {
  const ok = await bestätigen(`Episode „${episode.title}" wirklich löschen?`);
  if (!ok) return;
  const result = await deleteEpisode(project.project_id, episode.episode_id);
  if (!result.ok) {
    if (_detail) {
      const banner = el("div", {
        className: "error-banner",
        textContent: `Fehler beim Löschen: ${result.error}`,
      });
      _detail.prepend(banner);
      setTimeout(() => banner.remove(), 5000);
    }
    return;
  }
  await _renderDetail(project);
}

// ---------------------------------------------------------------------------
// Modal: Neues Projekt
// ---------------------------------------------------------------------------

function _openNeuProjektModal() {
  _openProjektModal(null);
}

function _openBearbeitenModal(project) {
  _openProjektModal(project);
}

function _openProjektModal(project) {
  const isNeu = !project;
  const titel = isNeu ? "Neues Projekt" : "Projekt bearbeiten";

  const titelInput = el("input", { id: "projekt-titel", type: "text", placeholder: "Titel des Projekts", value: project?.title || "" });
  const beschrInput = el("textarea", { id: "projekt-beschreibung", placeholder: "Beschreibung (optional)" });
  if (project?.description) beschrInput.value = project.description;

  const errorBanner = el("div", { className: "error-banner", style: "display:none" });

  const modal = _createModal(titel, [
    errorBanner,
    el("div", { className: "form-group" }, [
      el("label", { for: "projekt-titel", textContent: "Titel *" }),
      titelInput,
    ]),
    el("div", { className: "form-group" }, [
      el("label", { for: "projekt-beschreibung", textContent: "Beschreibung" }),
      beschrInput,
    ]),
  ], async () => {
    const title = titelInput.value.trim();
    if (!title) { titelInput.focus(); return; }

    let result;
    if (isNeu) {
      result = await createProject(title, beschrInput.value.trim());
    } else {
      result = await updateProject(project.project_id, title, beschrInput.value.trim());
    }

    if (!result.ok) {
      errorBanner.textContent = `Fehler: ${result.error}`;
      errorBanner.style.display = "";
      return;
    }
    _closeModal(modal);
    await render();
  });

  // Auto-Fokus
  setTimeout(() => titelInput.focus(), 50);
}

// ---------------------------------------------------------------------------
// Modal: Neue Episode
// ---------------------------------------------------------------------------

function _openNeuEpisodeModal(project) {
  _openEpisodeModal(project, null);
}

function _openEpisodeModal(project, episode = null) {
  const isNeu = !episode;
  const titelInput = el("input", { id: "episoden-titel", type: "text", placeholder: "Episodentitel", value: episode?.title || "" });
  const notesInput = el("textarea", { id: "episoden-notizen", placeholder: "Notizen (optional)" });
  if (episode?.notes) notesInput.value = episode.notes;
  const statusSelect = el("select", { id: "episoden-status" }, [
    el("option", { value: "geplant", textContent: "Geplant" }),
    el("option", { value: "laufend", textContent: "Laufend" }),
    el("option", { value: "fertig", textContent: "Fertig" }),
  ]);
  if (episode?.status) statusSelect.value = episode.status;

  const episodeErrorBanner = el("div", { className: "error-banner", style: "display:none" });

  const modal = _createModal(isNeu ? "Neue Episode" : "Episode bearbeiten", [
    episodeErrorBanner,
    el("div", { className: "form-group" }, [
      el("label", { for: "episoden-titel", textContent: "Titel *" }),
      titelInput,
    ]),
    el("div", { className: "form-group" }, [
      el("label", { for: "episoden-status", textContent: "Status" }),
      statusSelect,
    ]),
    el("div", { className: "form-group" }, [
      el("label", { for: "episoden-notizen", textContent: "Notizen" }),
      notesInput,
    ]),
  ], async () => {
    const title = titelInput.value.trim();
    if (!title) { titelInput.focus(); return; }

    const result = isNeu
      ? await createEpisode(project.project_id, title, notesInput.value.trim(), statusSelect.value)
      : await updateEpisode(project.project_id, episode.episode_id, title, notesInput.value.trim(), statusSelect.value);

    if (!result.ok) {
      episodeErrorBanner.textContent = `Fehler: ${result.error}`;
      episodeErrorBanner.style.display = "";
      return;
    }
    _closeModal(modal);
    await _renderDetail(project);
  });

  setTimeout(() => titelInput.focus(), 50);
}

// ---------------------------------------------------------------------------
// Löschen
// ---------------------------------------------------------------------------

async function _deleteProject(project) {
  const ok = await bestätigen(
    `Projekt „${project.title}" wirklich löschen?\nAlle Episoden dieses Projekts werden ebenfalls gelöscht.`
  );
  if (!ok) return;

  const result = await deleteProject(project.project_id);
  if (!result.ok) {
    // Kein nativer Dialog — Fehler wird im View-Bereich angezeigt
    const banner = el("div", {
      className: "error-banner",
      textContent: `Fehler beim Löschen: ${result.error}`,
    });
    _container.prepend(banner);
    setTimeout(() => banner.remove(), 5000);
    return;
  }

  if (_currentProject?.project_id === project.project_id) {
    _currentProject = null;
    if (_detail) _detail.classList.remove("open");
  }
  await render();
}

// ---------------------------------------------------------------------------
// Modal-Helfer
// ---------------------------------------------------------------------------

function _createModal(title, bodyElements, onConfirm) {
  const backdrop = el("div", { className: "modal-backdrop" });
  const modal = el("div", {
    className: "modal",
    role: "dialog",
    "aria-modal": "true",
    "aria-label": title,
  }, [
    el("div", { className: "modal-header" }, [
      el("h2", { textContent: title }),
      el("button", {
        className: "btn btn-ghost",
        textContent: "✕",
        title: "Schließen",
        "aria-label": "Schließen",
        onClick: () => _closeModal(backdrop),
      }),
    ]),
    el("div", { className: "modal-body" }, bodyElements),
    el("div", { className: "modal-footer" }, [
      el("button", {
        className: "btn btn-ghost",
        textContent: "Abbrechen",
        onClick: () => _closeModal(backdrop),
      }),
      el("button", {
        className: "btn btn-primary",
        textContent: "Speichern",
        onClick: onConfirm,
      }),
    ]),
  ]);
  backdrop.appendChild(modal);

  // Klick auf Hintergrund schließt Modal
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) _closeModal(backdrop);
  });

  // Tastatursteuerung & Fokus-Falle
  modal.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && e.target.tagName !== "TEXTAREA") {
      e.preventDefault();
      onConfirm();
    } else if (e.key === "Escape") {
      e.preventDefault();
      _closeModal(backdrop);
    } else if (e.key === "Tab") {
      const focusables = Array.from(modal.querySelectorAll("button, input, textarea, select, [tabindex='0']"));
      if (focusables.length === 0) return;
      const first = focusables[0];
      const last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  });

  document.body.appendChild(backdrop);
  return backdrop;
}

function _closeModal(backdrop) {
  if (backdrop && backdrop.parentNode) {
    backdrop.parentNode.removeChild(backdrop);
  }
}
