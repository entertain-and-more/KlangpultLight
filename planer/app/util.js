/**
 * util.js — Kleine Hilfsfunktionen für das Planer-Frontend.
 */

/**
 * Formatiert einen ISO-Zeitstempel als lesbares Datum/Uhrzeit (de-DE).
 * @param {string} iso
 * @returns {string}
 */
export function formatDateTime(iso) {
  if (!iso) return "—";
  try {
    return new Intl.DateTimeFormat("de-DE", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/**
 * Formatiert eine Dauer in Sekunden als mm:ss (oder hh:mm:ss wenn ≥ 1 h).
 * @param {number} seconds
 * @returns {string}
 */
export function formatDuration(seconds) {
  if (!seconds || seconds <= 0) return "0:00";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = Math.floor(seconds % 60);
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return `${m}:${String(s).padStart(2, "0")}`;
}

/**
 * Gibt das CSS-Badge-Klasse für einen Episodenstatus zurück.
 * @param {string} status
 * @returns {string}
 */
export function statusBadgeClass(status) {
  const map = { geplant: "badge-geplant", laufend: "badge-laufend", fertig: "badge-fertig" };
  return map[status] || "badge-geplant";
}

/**
 * Erstellt ein DOM-Element und setzt Attribute/Textinhalt.
 * Minimalwrapper — kein Framework.
 * @param {string} tag
 * @param {object} [attrs]
 * @param {string|Node|Array} [children]
 * @returns {HTMLElement}
 */
export function el(tag, attrs = {}, children = []) {
  const elem = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "className") elem.className = v;
    else if (k === "textContent") elem.textContent = v;
    else if (k.startsWith("on") && typeof v === "function") {
      elem.addEventListener(k.slice(2).toLowerCase(), v);
    } else {
      elem.setAttribute(k, v);
    }
  }
  if (!Array.isArray(children)) children = [children];
  for (const child of children) {
    if (child == null) continue;
    if (typeof child === "string") elem.appendChild(document.createTextNode(child));
    else elem.appendChild(child);
  }
  return elem;
}

/**
 * Zeigt ein zugängliches Bestätigungs-Modal (kein window.confirm).
 * @param {string} frage
 * @returns {Promise<boolean>}
 */
export function bestätigen(frage) {
  return new Promise((resolve) => {
    const previousFocus = document.activeElement;

    const overlay = el("div", {
      className: "modal-backdrop open",
      role: "dialog",
      "aria-modal": "true",
      "aria-label": "Bestätigung erforderlich",
    });

    const dialog = el("div", { className: "modal" }, [
      el("div", { className: "modal-header" }, [
        el("h2", { textContent: "Bestätigung" }),
      ]),
      el("div", { className: "modal-body" }, [
        el("p", { textContent: frage }),
      ]),
      el("div", { className: "modal-footer" }, [
        el("button", {
          className: "btn btn-ghost",
          textContent: "Abbrechen",
          onClick: () => cleanup(false),
        }),
        el("button", {
          className: "btn btn-danger",
          textContent: "Bestätigen",
          onClick: () => cleanup(true),
        }),
      ]),
    ]);

    overlay.appendChild(dialog);
    document.body.appendChild(overlay);

    const confirmBtn = dialog.querySelector(".btn-danger");
    if (confirmBtn) confirmBtn.focus();

    function onKeyDown(e) {
      if (e.key === "Escape") {
        e.preventDefault();
        cleanup(false);
      } else if (e.key === "Tab") {
        const focusables = Array.from(dialog.querySelectorAll("button, [tabindex='0']"));
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
    }

    window.addEventListener("keydown", onKeyDown);

    function cleanup(result) {
      window.removeEventListener("keydown", onKeyDown);
      if (overlay.parentNode) {
        overlay.parentNode.removeChild(overlay);
      }
      if (previousFocus && typeof previousFocus.focus === "function") {
        previousFocus.focus();
      }
      resolve(result);
    }
  });
}
