/**
 * pwa.test.mjs — Automatisierte Node-ESM-Vertragstests für die Klangpult light Planer-PWA.
 *
 * Prüft:
 * 1. Dynamische WebSocket-URL-Auflösung (Desktop Loopback, Studio-LAN-Tablet, IPv6, HTTPS/WSS, ?ws_port=).
 * 2. Sichere Service-Worker-Registrierung (isServiceWorkerSupported & registerPlanerServiceWorker).
 * 3. Manifest- und Icon-Parität zwischen planer/manifest.json, mobile_icons/ und planer/sw.js.
 * 4. Tier-2 6-Sprachen-Fallback-Kette in planer/app/i18n.js.
 */

import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { resolveDefaultWsUrl, RemoteConnection } from "../app/remote.js";
import { isServiceWorkerSupported, registerPlanerServiceWorker } from "../app/pwa.js";
import { SUPPORTED_LANGUAGES, setLanguage, getLanguage, t } from "../app/i18n.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const PLANER_ROOT = path.resolve(__dirname, "..");
const REPO_ROOT = path.resolve(PLANER_ROOT, "..");

test("resolveDefaultWsUrl bewahrt ws://127.0.0.1:8768 als Standard ohne Browser-Kontext", () => {
  assert.equal(resolveDefaultWsUrl(null), "ws://127.0.0.1:8768");
  assert.equal(resolveDefaultWsUrl(undefined), "ws://127.0.0.1:8768");
  assert.equal(
    resolveDefaultWsUrl({ protocol: "file:", hostname: "", search: "" }),
    "ws://127.0.0.1:8768"
  );
});

test("resolveDefaultWsUrl löst Desktop-Loopback, Studio-LAN-Tablet, HTTPS und ?ws_port= korrekt auf", () => {
  assert.equal(
    resolveDefaultWsUrl({ protocol: "http:", hostname: "127.0.0.1", search: "" }),
    "ws://127.0.0.1:8768"
  );
  assert.equal(
    resolveDefaultWsUrl({ protocol: "http:", hostname: "192.168.178.42", search: "" }),
    "ws://192.168.178.42:8768"
  );
  assert.equal(
    resolveDefaultWsUrl({
      protocol: "http:",
      hostname: "192.168.178.42",
      search: "?ws_port=9876",
    }),
    "ws://192.168.178.42:9876"
  );
  assert.equal(
    resolveDefaultWsUrl({
      protocol: "https:",
      hostname: "studio.local",
      search: "?ws_port=9443",
    }),
    "wss://studio.local:9443"
  );
  assert.equal(
    resolveDefaultWsUrl({ protocol: "http:", hostname: "::1", search: "" }),
    "ws://[::1]:8768"
  );
  // Ungültiger ws_port fällt sicher auf 8768 zurück
  assert.equal(
    resolveDefaultWsUrl({
      protocol: "http:",
      hostname: "192.168.1.10",
      search: "?ws_port=99999",
    }),
    "ws://192.168.1.10:8768"
  );
});

test("RemoteConnection übernimmt Location-Origin und kapselt Protokollbefehle sauber", () => {
  const rc = new RemoteConnection({
    protocol: "http:",
    hostname: "10.0.0.25",
    search: "?ws_port=8768",
  });
  assert.equal(rc.url, "ws://10.0.0.25:8768");
  assert.equal(rc.status, "disconnected");
  assert.equal(rc.sendTriggerPad("intro"), false);
});

test("isServiceWorkerSupported & registerPlanerServiceWorker prüfen sichere Kontexte strikt", async () => {
  const fakeSwNav = {
    serviceWorker: {
      async register(url, opts) {
        return { scope: opts.scope, url };
      },
    },
  };

  assert.equal(
    isServiceWorkerSupported(fakeSwNav, { protocol: "http:", hostname: "127.0.0.1" }),
    true
  );
  assert.equal(
    isServiceWorkerSupported(fakeSwNav, { protocol: "http:", hostname: "localhost" }),
    true
  );
  assert.equal(
    isServiceWorkerSupported(fakeSwNav, { protocol: "https:", hostname: "studio.local" }),
    true
  );
  // Unverschlüsselte LAN-IP hat keinen Secure-Context für Service Worker -> sauberer Skip
  assert.equal(
    isServiceWorkerSupported(fakeSwNav, { protocol: "http:", hostname: "192.168.178.42" }),
    false
  );
  assert.equal(isServiceWorkerSupported(null, null), false);

  const okRes = await registerPlanerServiceWorker(fakeSwNav, {
    protocol: "http:",
    hostname: "127.0.0.1",
  });
  assert.equal(okRes.registered, true);
  assert.equal(okRes.reason, "ok");

  const skipRes = await registerPlanerServiceWorker(fakeSwNav, {
    protocol: "http:",
    hostname: "192.168.178.42",
  });
  assert.equal(skipRes.registered, false);
  assert.equal(skipRes.reason, "unsupported_or_insecure_context");
});

test("manifest.json, mobile_icons/ und sw.js App-Shell sind vollständig konsistent", () => {
  const manifestRaw = fs.readFileSync(path.join(PLANER_ROOT, "manifest.json"), "utf8");
  const manifest = JSON.parse(manifestRaw);

  assert.equal(manifest.display, "standalone");
  assert.equal(manifest.start_url, "/");
  assert.equal(manifest.icons.length, 4);

  for (const icon of manifest.icons) {
    const iconPath = path.join(REPO_ROOT, "mobile_icons", icon.src);
    assert.equal(
      fs.existsSync(iconPath),
      true,
      `PWA-Manifest-Icon fehlt in mobile_icons/: ${icon.src}`
    );
    assert.ok(fs.statSync(iconPath).size > 100);
  }

  const swText = fs.readFileSync(path.join(PLANER_ROOT, "sw.js"), "utf8");
  assert.ok(swText.includes("klangpult-planer-shell-"));
  assert.ok(swText.includes('"/manifest.json"'));
  assert.ok(swText.includes('"/app/pwa.js"'));
  assert.ok(swText.includes('"/locales/translations.json"'));
  assert.ok(swText.includes("url.origin !== self.location.origin"));
});

test("Tier-2 6-Sprachen-Wörterbuch in planer/app/i18n.js übersetzt alle 6 Zielsprachen fehlerfrei", () => {
  assert.deepEqual(SUPPORTED_LANGUAGES, ["de", "en", "es", "zh", "ja", "ru"]);

  for (const lang of SUPPORTED_LANGUAGES) {
    assert.equal(setLanguage(lang), true);
    assert.equal(getLanguage(), lang);
    const title = t("planer_title");
    assert.ok(typeof title === "string" && title.length > 5);
    assert.notEqual(title, "planer_title");
  }

  // Zurück auf Standard 'de'
  setLanguage("de");
  assert.equal(t("open_planer"), "🌐 Planer im Browser öffnen");
  assert.equal(t("non_existent_key_xyz"), "non_existent_key_xyz");
});
