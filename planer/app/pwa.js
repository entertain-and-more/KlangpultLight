/**
 * pwa.js — Sichere Service-Worker-Registrierung für den Klangpult light – Planer.
 *
 * Registriert ./sw.js ausschließlich in unterstützten Browser-Kontexten
 * (https: oder lokaler Loopback 127.0.0.1 / localhost / [::1]).
 * In Node-Tests oder file://-Umgebungen erfolgt ein sauberer No-Op ohne Fehler.
 */

const LOOPBACK_HOSTS = new Set(["127.0.0.1", "localhost", "[::1]", "::1"]);

/**
 * Prüft, ob die aktuelle Umgebung Service Worker unterstützt und erlaubt.
 * @param {object|null} [nav]
 * @param {object|null} [loc]
 * @returns {boolean}
 */
export function isServiceWorkerSupported(
  nav = typeof navigator !== "undefined" ? navigator : null,
  loc = typeof window !== "undefined" ? window.location : null
) {
  if (!nav || typeof nav !== "object" || !("serviceWorker" in nav)) {
    return false;
  }
  if (!loc || typeof loc !== "object") {
    return false;
  }
  const protocol = String(loc.protocol || "").toLowerCase();
  const hostname = String(loc.hostname || "").toLowerCase();
  if (protocol === "https:") {
    return true;
  }
  if (protocol === "http:" && LOOPBACK_HOSTS.has(hostname)) {
    return true;
  }
  return false;
}

/**
 * Registriert den lokalen Offline-App-Shell Service Worker.
 * @param {object|null} [nav]
 * @param {object|null} [loc]
 * @param {string} [swUrl="./sw.js"]
 * @returns {Promise<{registered: boolean, reason: string, scope?: string}>}
 */
export async function registerPlanerServiceWorker(
  nav = typeof navigator !== "undefined" ? navigator : null,
  loc = typeof window !== "undefined" ? window.location : null,
  swUrl = "./sw.js"
) {
  if (!isServiceWorkerSupported(nav, loc)) {
    return { registered: false, reason: "unsupported_or_insecure_context" };
  }
  try {
    const reg = await nav.serviceWorker.register(swUrl, { scope: "./" });
    return {
      registered: true,
      reason: "ok",
      scope: reg && reg.scope ? String(reg.scope) : "./",
    };
  } catch (err) {
    return {
      registered: false,
      reason: err && err.message ? String(err.message) : "registration_failed",
    };
  }
}
