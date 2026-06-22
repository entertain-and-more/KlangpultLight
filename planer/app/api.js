/**
 * api.js — Zentrale API-Schicht des PodcastPlaners.
 *
 * Alle Fetch-Aufrufe laufen über dieses Modul. Die Basis-URLs werden relativ
 * zur aktuellen Origin aufgebaut — der PlanerServer proxyt /api/* transparent.
 *
 * Fehlermodell: jede Funktion gibt Promise<{ok: true, data: ...}> oder
 * Promise<{ok: false, error: string}> zurück (kein throw).
 */

const BASE = "";  // same-origin via Proxy

// ---------------------------------------------------------------------------
// Hilfsfunktionen
// ---------------------------------------------------------------------------

async function _request(method, path, body = null) {
  const opts = {
    method,
    headers: { "Content-Type": "application/json" },
  };
  if (body !== null) {
    opts.body = JSON.stringify(body);
  }
  try {
    const resp = await fetch(BASE + path, opts);
    if (resp.status === 204) return { ok: true, data: null };
    const data = await resp.json();
    if (!resp.ok) {
      return { ok: false, error: data.error || `HTTP ${resp.status}` };
    }
    return { ok: true, data };
  } catch (err) {
    return { ok: false, error: err.message || "Netzwerkfehler" };
  }
}

// ---------------------------------------------------------------------------
// Health / Status
// ---------------------------------------------------------------------------

/** Prüft ob LibraryApiServer erreichbar ist. */
export async function checkLibraryHealth() {
  return _request("GET", "/api/library");
}

/** Prüft ob ProjectsApiServer erreichbar ist. */
export async function checkProjectsHealth() {
  return _request("GET", "/api/projects");
}

// ---------------------------------------------------------------------------
// Bibliothek (LibraryApiServer → Port 8767)
// ---------------------------------------------------------------------------

/**
 * Listet alle Aufnahmen mit Branch-Baum.
 * @returns {Promise<{ok: boolean, data?: {recordings: Array}, error?: string}>}
 */
export async function listRecordings() {
  return _request("GET", "/api/library");
}

// ---------------------------------------------------------------------------
// Projekte (ProjectsApiServer → Port 8769)
// ---------------------------------------------------------------------------

/**
 * Listet alle Projekte.
 * @returns {Promise<{ok: boolean, data?: {projects: Array}, error?: string}>}
 */
export async function listProjects() {
  return _request("GET", "/api/projects");
}

/**
 * Legt ein neues Projekt an.
 * @param {string} title
 * @param {string} [description]
 */
export async function createProject(title, description = "") {
  return _request("POST", "/api/projects", { title, description });
}

/**
 * Ruft ein Projekt ab.
 * @param {string} projectId
 */
export async function getProject(projectId) {
  return _request("GET", `/api/projects/${projectId}`);
}

/**
 * Aktualisiert ein Projekt.
 * @param {string} projectId
 * @param {string} title
 * @param {string} [description]
 */
export async function updateProject(projectId, title, description = "") {
  return _request("PUT", `/api/projects/${projectId}`, { title, description });
}

/**
 * Löscht ein Projekt.
 * @param {string} projectId
 */
export async function deleteProject(projectId) {
  return _request("DELETE", `/api/projects/${projectId}`);
}

/**
 * Listet die Episoden eines Projekts.
 * @param {string} projectId
 */
export async function listEpisodes(projectId) {
  return _request("GET", `/api/projects/${projectId}/episodes`);
}

/**
 * Legt eine neue Episode an.
 * @param {string} projectId
 * @param {string} title
 * @param {string} [notes]
 * @param {string} [status]  "geplant" | "laufend" | "fertig"
 */
export async function createEpisode(projectId, title, notes = "", status = "geplant") {
  return _request("POST", `/api/projects/${projectId}/episodes`, {
    title, notes, status,
  });
}
