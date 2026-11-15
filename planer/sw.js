/**
 * sw.js — Offline-App-Shell Service Worker für Klangpult light – Planer.
 *
 * Sicherheits- & Architektur-Invarianten:
 * - 100% Zero-Egress (INV-LOCAL-01): Verarbeitet ausschließlich Same-Origin GET-Anfragen.
 * - Kein Caching mutierender API-Operationen (POST/PUT/DELETE).
 * - Network-First für /api/* mit ehrlichem Offline-JSON-Fallback (Faktentreue §2h).
 * - App-Shell-Caching für statische Assets und 6-Sprachen-Wörterbuch (/locales/translations.json).
 */

const CACHE_PREFIX = "klangpult-planer-shell-";
const CACHE_VERSION = "v0.1.0";
const CACHE_NAME = `${CACHE_PREFIX}${CACHE_VERSION}`;

const APP_SHELL_URLS = [
  "/",
  "/index.html",
  "/manifest.json",
  "/favicon.ico",
  "/favicon.png",
  "/apple-touch-icon.png",
  "/icon-192.png",
  "/icon-512.png",
  "/styles/main.css",
  "/app/main.js",
  "/app/api.js",
  "/app/i18n.js",
  "/app/remote.js",
  "/app/pwa.js",
  "/app/util.js",
  "/app/bibliothek.js",
  "/app/projekte.js",
  "/app/assets.js",
  "/app/teleprompter.js",
  "/app/monitor.js",
  "/locales/translations.json",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE_NAME);
      await Promise.allSettled(
        APP_SHELL_URLS.map((url) =>
          cache.add(new Request(url, { cache: "reload" }))
        )
      );
      await self.skipWaiting();
    })()
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    (async () => {
      const keys = await caches.keys();
      await Promise.all(
        keys
          .filter((key) => key.startsWith(CACHE_PREFIX) && key !== CACHE_NAME)
          .map((oldKey) => caches.delete(oldKey))
      );
      await self.clients.claim();
    })()
  );
});

async function handleApiGet(request, pathname) {
  const cache = await caches.open(CACHE_NAME);

  // Sprachwörterbuch: Network-First mit Offline-Cache-Fallback
  if (pathname === "/api/translations" || pathname === "/api/i18n") {
    try {
      const response = await fetch(request);
      if (response && response.ok) {
        await cache.put(request, response.clone());
      }
      return response;
    } catch (_) {
      const cached =
        (await cache.match(request)) ||
        (await cache.match("/locales/translations.json"));
      if (cached) return cached;
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      });
    }
  }

  // Bridge-Health-Status: Network-First, bei Offline ehrlicher "offline"-Status
  if (pathname === "/api/status") {
    try {
      return await fetch(request);
    } catch (_) {
      return new Response(
        JSON.stringify({
          status: "offline",
          services: {
            library: { ok: false },
            projects: { ok: false },
          },
          offline_cache: true,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json; charset=utf-8" },
        }
      );
    }
  }

  // Übrige GET /api/* Routen: Live vom lokalen Recorder abrufen, kein Stale-Daten-Schwindel
  try {
    return await fetch(request);
  } catch (_) {
    return new Response(
      JSON.stringify({
        error:
          "Offline – Lokaler Planer- oder Recorder-Dienst ist derzeit nicht erreichbar.",
        offline: true,
      }),
      {
        status: 503,
        headers: { "Content-Type": "application/json; charset=utf-8" },
      }
    );
  }
}

async function handleStaticGet(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const networkResponse = await fetch(request);
    if (networkResponse && networkResponse.ok) {
      await cache.put(request, networkResponse.clone());
    }
    return networkResponse;
  } catch (_) {
    const cached = await cache.match(request);
    if (cached) return cached;
    if (request.mode === "navigate") {
      const fallbackDoc =
        (await cache.match("/index.html")) || (await cache.match("/"));
      if (fallbackDoc) return fallbackDoc;
    }
    return new Response("Offline", {
      status: 503,
      headers: { "Content-Type": "text/plain; charset=utf-8" },
    });
  }
}

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  let url;
  try {
    url = new URL(request.url);
  } catch (_) {
    return;
  }

  // Striktes Same-Origin-Prinzip (Zero-Egress)
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(handleApiGet(request, url.pathname));
    return;
  }

  event.respondWith(handleStaticGet(request));
});
