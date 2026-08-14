/**
 * assets.js — Soundboard-Assets & Line-Ablauf-Planer für Klangpult light.
 *
 * Verwaltet Board-Pads (Assets) und Einspieler-Reihenfolge (Line) je Projekt.
 * Volle Kompatibilität zum klangpultlight-workspace-v1 Standard.
 * Reines Vanilla JS ESM — keine externen UI-Frameworks.
 */

import {
  listProjects,
  listAssets,
  createAsset,
  updateAsset,
  deleteAsset,
  getLine,
  updateLine,
  getWorkspace,
  importWorkspace,
} from "./api.js";
import { el, bestätigen } from "./util.js";

let _container = null;
let _detail = null;
let _projects = [];
let _currentProjectId = null;
let _assets = [];
let _line = []; // Array von Asset-IDs

const PRESET_COLORS = [
  "#3b82f6", // Blau
  "#ef4444", // Rot
  "#10b981", // Grün
  "#f59e0b", // Orange/Gelb
  "#8b5cf6", // Lila
  "#ec4899", // Pink
  "#06b6d4", // Cyan
  "#6b7280", // Grau
];

// ---------------------------------------------------------------------------
// Lifecycle: Mount / Unmount / Reload
// ---------------------------------------------------------------------------

export function mount(container, detailPanel) {
  _container = container;
  _detail = detailPanel;
  render();
}

export function unmount() {
  if (_detail) _detail.classList.remove("open");
  _container = null;
  _detail = null;
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

  const spinner = el("div", { className: "empty-state" }, [
    el("div", { className: "spinner" }),
    el("p", { textContent: "Assets & Line-Planung wird geladen…" }),
  ]);
  _container.appendChild(spinner);

  const pRes = await listProjects();
  _container.innerHTML = "";

  if (!pRes.ok) {
    _container.appendChild(
      el("div", { className: "error-banner" }, [
        `Projektdienst nicht erreichbar: ${pRes.error}`,
        el("br"),
        el("small", { textContent: "Bitte Klangpult light – Recorder starten (Bridge auf Port 8769)." }),
      ])
    );
    return;
  }

  _projects = pRes.data.projects || [];

  if (_projects.length === 0) {
    _container.appendChild(
      el("div", { className: "empty-state" }, [
        el("div", { className: "empty-icon", textContent: "🎛️" }),
        el("p", { textContent: "Noch kein Projekt vorhanden. Bitte zuerst unter 'Projekte' ein Projekt erstellen." }),
      ])
    );
    return;
  }

  // Falls keine ID gewählt oder gelöscht: erstes Projekt wählen
  if (!_currentProjectId || !_projects.some((p) => p.project_id === _currentProjectId)) {
    _currentProjectId = _projects[0].project_id;
  }

  // Daten für das gewählte Projekt laden
  await _loadProjectData(_currentProjectId);
  _buildView();
}

async function _loadProjectData(projectId) {
  const [aRes, lRes] = await Promise.all([
    listAssets(projectId),
    getLine(projectId),
  ]);

  _assets = aRes.ok ? (aRes.data.assets || []) : [];
  _line = lRes.ok ? (lRes.data.line || []) : [];
}

function _buildView() {
  if (!_container) return;
  _container.innerHTML = "";

  const currentProj = _projects.find((p) => p.project_id === _currentProjectId);

  // --- Toolbar: Projektauswahl & Aktionen ---
  const toolbar = el("div", { className: "assets-toolbar" }, [
    el("div", { className: "assets-project-selector" }, [
      el("label", {
        for: "assets-project-select",
        textContent: "Projekt:",
        className: "assets-select-label",
      }),
      (() => {
        const select = el("select", {
          id: "assets-project-select",
          className: "input-field select-field",
          "aria-label": "Projekt für Assets und Line auswählen",
          onChange: async (e) => {
            _currentProjectId = e.target.value;
            await _loadProjectData(_currentProjectId);
            _buildView();
          },
        });
        for (const p of _projects) {
          const opt = el("option", {
            value: p.project_id,
            textContent: p.title || "Unbenanntes Projekt",
          });
          if (p.project_id === _currentProjectId) opt.selected = true;
          select.appendChild(opt);
        }
        return select;
      })(),
    ]),
    el("div", { className: "assets-toolbar-actions" }, [
      el("button", {
        className: "btn btn-primary",
        textContent: "+ Neues Asset",
        "aria-label": "Neues Board-Asset anlegen",
        onClick: () => _openAssetModal(null),
      }),
      el("button", {
        className: "btn btn-ghost",
        textContent: "📦 Workspace JSON",
        "aria-label": "Workspace-v1 JSON anzeigen, exportieren oder importieren",
        onClick: _openWorkspaceModal,
      }),
    ]),
  ]);

  _container.appendChild(toolbar);

  // --- Hauptbereich: 2-Spalten-Layout (Assets links, Line rechts) ---
  const mainGrid = el("div", { className: "assets-line-grid" });

  // 1. Assets Spalte
  const assetsPane = el("div", { className: "assets-pane" }, [
    el("div", { className: "pane-header" }, [
      el("h2", { textContent: "Board-Assets / Pads" }),
      el("span", {
        className: "pane-badge",
        textContent: `${_assets.length} ${plural(_assets.length, "Asset", "Assets")}`,
      }),
    ]),
  ]);

  if (_assets.length === 0) {
    assetsPane.appendChild(
      el("div", { className: "empty-state mini" }, [
        el("div", { className: "empty-icon", textContent: "🎵" }),
        el("p", { textContent: "Keine Assets für dieses Projekt hinterlegt." }),
        el("button", {
          className: "btn btn-primary",
          textContent: "+ Erstes Asset anlegen",
          "aria-label": "Erstes Asset anlegen",
          onClick: () => _openAssetModal(null),
        }),
      ])
    );
  } else {
    const grid = el("div", { className: "assets-cards-grid" });
    for (const asset of _assets) {
      grid.appendChild(_renderAssetCard(asset));
    }
    assetsPane.appendChild(grid);
  }
  mainGrid.appendChild(assetsPane);

  // 2. Line Spalte
  const linePane = el("div", { className: "line-pane" }, [
    el("div", { className: "pane-header" }, [
      el("h2", { textContent: "Line-Ablauf" }),
      el("div", { className: "pane-header-actions" }, [
        el("span", {
          className: "pane-badge",
          textContent: `${_line.length} ${plural(_line.length, "Slot", "Slots")}`,
        }),
        _line.length > 0
          ? el("button", {
              className: "btn btn-ghost btn-sm",
              textContent: "Leeren",
              "aria-label": "Gesamte Line leeren",
              onClick: _clearLine,
            })
          : null,
      ]),
    ]),
  ]);

  if (_line.length === 0) {
    linePane.appendChild(
      el("div", { className: "empty-state mini" }, [
        el("div", { className: "empty-icon", textContent: "📜" }),
        el("p", { textContent: "Die Line ist noch leer." }),
        el("small", {
          textContent: "Klicke bei einem Board-Asset auf '+ Zur Line', um es zur Ablauf-Reihenfolge hinzuzufügen.",
        }),
      ])
    );
  } else {
    const lineList = el("div", { className: "line-slots-list", role: "list" });
    _line.forEach((assetId, index) => {
      const asset = _assets.find((a) => a.id === assetId);
      lineList.appendChild(_renderLineSlot(assetId, asset, index));
    });
    linePane.appendChild(lineList);
  }
  mainGrid.appendChild(linePane);

  _container.appendChild(mainGrid);
}

// ---------------------------------------------------------------------------
// Render: Asset Card
// ---------------------------------------------------------------------------

function _renderAssetCard(asset) {
  const kindIcons = { audio: "🎵", video: "🎬", image: "🖼️" };
  const kindNames = { audio: "Audio", video: "Video", image: "Bild" };
  const modeLabels = { play_stop: "Play / Stop", loop: "Loop", overlap: "Overlap" };

  const icon = kindIcons[asset.kind] || "🎵";
  const kindName = kindNames[asset.kind] || asset.kind;
  const modeName = modeLabels[asset.mode] || asset.mode;

  const card = el("div", {
    className: "asset-card",
    style: `border-left: 4px solid ${asset.color || "#3b82f6"}`,
  });

  const cardTop = el("div", { className: "asset-card-top" }, [
    el("div", { className: "asset-title-row" }, [
      el("span", {
        className: "asset-color-dot",
        style: `background-color: ${asset.color || "#3b82f6"}`,
        "aria-hidden": "true",
      }),
      el("h3", { className: "asset-title", textContent: asset.label || "Unbenannt" }),
    ]),
    el("span", {
      className: `asset-kind-pill kind-${asset.kind}`,
      textContent: `${icon} ${kindName}`,
    }),
  ]);
  card.appendChild(cardTop);

  const cardBody = el("div", { className: "asset-card-body" }, [
    el("div", { className: "asset-meta-item" }, [
      el("span", { className: "asset-meta-label", textContent: "Pfad:" }),
      el("span", {
        className: "asset-meta-value code-snippet",
        textContent: asset.asset_path || "—",
        title: asset.asset_path || "",
      }),
    ]),
    el("div", { className: "asset-meta-row" }, [
      el("div", { className: "asset-meta-item" }, [
        el("span", { className: "asset-meta-label", textContent: "Modus:" }),
        el("span", { className: "asset-meta-value", textContent: modeName }),
      ]),
      asset.hotkey
        ? el("div", { className: "asset-meta-item" }, [
            el("span", { className: "asset-meta-label", textContent: "Taste:" }),
            el("span", { className: "asset-hotkey-badge", textContent: asset.hotkey }),
          ])
        : null,
    ]),
  ]);
  card.appendChild(cardBody);

  const cardActions = el("div", { className: "asset-card-actions" }, [
    el("button", {
      className: "btn btn-primary btn-sm",
      textContent: "+ Zur Line",
      "aria-label": `'${asset.label}' zur Line hinzufügen`,
      onClick: () => _addToLine(asset.id),
    }),
    el("button", {
      className: "btn btn-ghost btn-sm",
      textContent: "Bearbeiten",
      "aria-label": `'${asset.label}' bearbeiten`,
      onClick: () => _openAssetModal(asset),
    }),
    el("button", {
      className: "btn btn-danger btn-sm",
      textContent: "Löschen",
      "aria-label": `'${asset.label}' löschen`,
      onClick: () => _deleteAssetConfirm(asset),
    }),
  ]);
  card.appendChild(cardActions);

  return card;
}

// ---------------------------------------------------------------------------
// Render: Line Slot
// ---------------------------------------------------------------------------

function _renderLineSlot(assetId, asset, index) {
  const isFirst = index === 0;
  const isLast = index === _line.length - 1;

  const slot = el("div", {
    className: "line-slot-item",
    role: "listitem",
  });

  const numBadge = el("span", {
    className: "line-slot-number",
    textContent: `${index + 1}.`,
  });

  const infoCol = el("div", { className: "line-slot-info" });
  if (asset) {
    infoCol.appendChild(
      el("div", { className: "line-slot-name-row" }, [
        el("span", {
          className: "asset-color-dot small",
          style: `background-color: ${asset.color || "#3b82f6"}`,
          "aria-hidden": "true",
        }),
        el("strong", { textContent: asset.label || "Unbenannt" }),
        el("span", { className: "line-slot-kind", textContent: `(${asset.kind})` }),
      ])
    );
  } else {
    infoCol.appendChild(
      el("div", { className: "line-slot-name-row missing" }, [
        el("strong", { textContent: `Asset-ID: ${assetId} (nicht gefunden)` }),
      ])
    );
  }

  const controls = el("div", { className: "line-slot-controls" }, [
    el("button", {
      className: "btn-icon",
      textContent: "▲",
      disabled: isFirst,
      "aria-label": `Slot ${index + 1} nach oben verschieben`,
      title: "Nach oben",
      onClick: () => _moveLineSlot(index, index - 1),
    }),
    el("button", {
      className: "btn-icon",
      textContent: "▼",
      disabled: isLast,
      "aria-label": `Slot ${index + 1} nach unten verschieben`,
      title: "Nach unten",
      onClick: () => _moveLineSlot(index, index + 1),
    }),
    el("button", {
      className: "btn-icon btn-danger-icon",
      textContent: "✕",
      "aria-label": `Slot ${index + 1} aus der Line entfernen`,
      title: "Entfernen",
      onClick: () => _removeLineSlot(index),
    }),
  ]);

  slot.appendChild(numBadge);
  slot.appendChild(infoCol);
  slot.appendChild(controls);

  return slot;
}

// ---------------------------------------------------------------------------
// Line Aktionen
// ---------------------------------------------------------------------------

async function _addToLine(assetId) {
  _line.push(assetId);
  const res = await updateLine(_currentProjectId, _line);
  if (res.ok) {
    _line = res.data.line || _line;
    _buildView();
  }
}

async function _moveLineSlot(fromIndex, toIndex) {
  if (toIndex < 0 || toIndex >= _line.length) return;
  const item = _line.splice(fromIndex, 1)[0];
  _line.splice(toIndex, 0, item);

  const res = await updateLine(_currentProjectId, _line);
  if (res.ok) {
    _line = res.data.line || _line;
    _buildView();
  }
}

async function _removeLineSlot(index) {
  _line.splice(index, 1);
  const res = await updateLine(_currentProjectId, _line);
  if (res.ok) {
    _line = res.data.line || _line;
    _buildView();
  }
}

async function _clearLine() {
  const ok = await bestätigen("Möchtest du wirklich alle Einträge aus der Line entfernen?");
  if (!ok) return;

  _line = [];
  const res = await updateLine(_currentProjectId, _line);
  if (res.ok) {
    _line = [];
    _buildView();
  }
}

// ---------------------------------------------------------------------------
// Asset Löschen
// ---------------------------------------------------------------------------

async function _deleteAssetConfirm(asset) {
  const ok = await bestätigen(
    `Möchtest du das Asset "${asset.label || asset.id}" wirklich löschen? Es wird auch aus der Line entfernt.`
  );
  if (!ok) return;

  const res = await deleteAsset(_currentProjectId, asset.id);
  if (res.ok) {
    await _loadProjectData(_currentProjectId);
    _buildView();
  }
}

// ---------------------------------------------------------------------------
// Modal: Asset Anlegen / Bearbeiten (A11y-konform)
// ---------------------------------------------------------------------------

function _openAssetModal(existingAsset = null) {
  const isEdit = existingAsset !== null;
  const titleText = isEdit ? "Asset bearbeiten" : "Neues Board-Asset anlegen";

  let currentColor = (existingAsset && existingAsset.color) || "#3b82f6";

  const overlay = el("div", {
    className: "modal-backdrop open",
    role: "dialog",
    "aria-modal": "true",
    "aria-label": titleText,
  });

  const dialog = el("div", { className: "modal" });

  const header = el("div", { className: "modal-header" }, [
    el("h2", { textContent: titleText }),
    el("button", {
      className: "btn-icon",
      textContent: "✕",
      "aria-label": "Modal schließen",
      onClick: close,
    }),
  ]);

  const body = el("div", { className: "modal-body" });

  // Label Input
  const labelGroup = el("div", { className: "form-group" }, [
    el("label", { for: "asset-input-label", textContent: "Bezeichnung / Label *" }),
    el("input", {
      id: "asset-input-label",
      type: "text",
      className: "input-field",
      placeholder: "z. B. Intro Jingle, Applaus, Bauchbinde",
      value: existingAsset ? existingAsset.label || "" : "",
      required: "true",
    }),
  ]);
  body.appendChild(labelGroup);

  // Kind Select
  const kindGroup = el("div", { className: "form-group" }, [
    el("label", { for: "asset-input-kind", textContent: "Typ *" }),
    (() => {
      const sel = el("select", { id: "asset-input-kind", className: "input-field" });
      const options = [
        { val: "audio", label: "🎵 Audio (Soundeffekt / Musik)" },
        { val: "video", label: "🎬 Video (Einspieler)" },
        { val: "image", label: "🖼️ Bild (Grafik / Logo)" },
      ];
      for (const opt of options) {
        const o = el("option", { value: opt.val, textContent: opt.label });
        if (existingAsset && existingAsset.kind === opt.val) o.selected = true;
        sel.appendChild(o);
      }
      return sel;
    })(),
  ]);
  body.appendChild(kindGroup);

  // Asset Path Input
  const pathGroup = el("div", { className: "form-group" }, [
    el("label", { for: "asset-input-path", textContent: "Dateipfad" }),
    el("input", {
      id: "asset-input-path",
      type: "text",
      className: "input-field",
      placeholder: "z. B. sounds/intro.wav oder C:/Assets/video.mp4",
      value: existingAsset ? existingAsset.asset_path || "" : "",
    }),
  ]);
  body.appendChild(pathGroup);

  // Mode Select
  const modeGroup = el("div", { className: "form-group" }, [
    el("label", { for: "asset-input-mode", textContent: "Wiedergabemodus" }),
    (() => {
      const sel = el("select", { id: "asset-input-mode", className: "input-field" });
      const options = [
        { val: "play_stop", label: "Play / Stop (Klick startet / stoppt)" },
        { val: "loop", label: "Loop (Dauerschleife)" },
        { val: "overlap", label: "Overlap (Mehrfachstarts überlappen)" },
      ];
      for (const opt of options) {
        const o = el("option", { value: opt.val, textContent: opt.label });
        if (existingAsset && existingAsset.mode === opt.val) o.selected = true;
        sel.appendChild(o);
      }
      return sel;
    })(),
  ]);
  body.appendChild(modeGroup);

  // Hotkey Input
  const hotkeyGroup = el("div", { className: "form-group" }, [
    el("label", { for: "asset-input-hotkey", textContent: "Tastenkürzel (Hotkey)" }),
    el("input", {
      id: "asset-input-hotkey",
      type: "text",
      className: "input-field",
      placeholder: "z. B. 1, A, F1, Space",
      maxLength: "10",
      value: existingAsset ? existingAsset.hotkey || "" : "",
    }),
  ]);
  body.appendChild(hotkeyGroup);

  // Color Presets & Hex Picker
  const colorBox = el("div", { className: "form-group" }, [
    el("label", { for: "asset-input-color", textContent: "Pad-Farbe" }),
    (() => {
      const colorContainer = el("div", { className: "color-picker-row" });
      const hexInput = el("input", {
        id: "asset-input-color",
        type: "text",
        className: "input-field color-hex-input",
        value: currentColor,
      });

      const presetRow = el("div", { className: "color-presets" });
      for (const col of PRESET_COLORS) {
        const btn = el("button", {
          type: "button",
          className: "color-preset-btn",
          style: `background-color: ${col}`,
          "aria-label": `Farbe ${col} wählen`,
          onClick: () => {
            currentColor = col;
            hexInput.value = col;
          },
        });
        presetRow.appendChild(btn);
      }

      hexInput.addEventListener("input", (e) => {
        currentColor = e.target.value;
      });

      colorContainer.appendChild(presetRow);
      colorContainer.appendChild(hexInput);
      return colorContainer;
    })(),
  ]);
  body.appendChild(colorBox);

  // Error container
  const errBox = el("div", { className: "modal-error-msg", style: "display: none;" });
  body.appendChild(errBox);

  // Footer Buttons
  const footer = el("div", { className: "modal-footer" }, [
    el("button", {
      type: "button",
      className: "btn btn-ghost",
      textContent: "Abbrechen",
      "aria-label": "Abbrechen und Dialog schließen",
      onClick: close,
    }),
    el("button", {
      type: "button",
      className: "btn btn-primary",
      textContent: isEdit ? "Speichern" : "Anlegen",
      "aria-label": isEdit ? "Asset speichern" : "Asset anlegen",
      onClick: async () => {
        const labelVal = labelGroup.querySelector("input").value.trim();
        const kindVal = kindGroup.querySelector("select").value;
        const pathVal = pathGroup.querySelector("input").value.trim();
        const modeVal = modeGroup.querySelector("select").value;
        const hotkeyVal = hotkeyGroup.querySelector("input").value.trim();
        const colorVal = colorBox.querySelector("#asset-input-color").value.trim() || "#3b82f6";

        if (!labelVal) {
          errBox.textContent = "Bitte gib eine Bezeichnung für das Asset ein.";
          errBox.style.display = "block";
          return;
        }

        const payload = {
          label: labelVal,
          kind: kindVal,
          asset_path: pathVal,
          mode: modeVal,
          hotkey: hotkeyVal,
          color: colorVal,
          volume: existingAsset ? existingAsset.volume || 1.0 : 1.0,
        };

        let res;
        if (isEdit) {
          res = await updateAsset(_currentProjectId, existingAsset.id, payload);
        } else {
          res = await createAsset(_currentProjectId, payload);
        }

        if (!res.ok) {
          errBox.textContent = `Fehler: ${res.error}`;
          errBox.style.display = "block";
          return;
        }

        close();
        await _loadProjectData(_currentProjectId);
        _buildView();
      },
    }),
  ]);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(footer);
  overlay.appendChild(dialog);

  function close() {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
  }

  function onKey(e) {
    if (e.key === "Escape") close();
  }
  document.addEventListener("keydown", onKey);

  document.body.appendChild(overlay);
  labelGroup.querySelector("input").focus();
}

// ---------------------------------------------------------------------------
// Modal: Workspace-v1 JSON Export / Import
// ---------------------------------------------------------------------------

async function _openWorkspaceModal() {
  const res = await getWorkspace(_currentProjectId);
  const currentWorkspace = res.ok ? res.data : { format: "klangpultlight-workspace-v1", version: 1, board: { pads: [] }, line: [] };
  const jsonStr = JSON.stringify(currentWorkspace, null, 2);

  const overlay = el("div", {
    className: "modal-backdrop open",
    role: "dialog",
    "aria-modal": "true",
    "aria-label": "Workspace JSON Export und Import",
  });

  const dialog = el("div", { className: "modal modal-large" });

  const header = el("div", { className: "modal-header" }, [
    el("h2", { textContent: "Workspace-v1 JSON (Export & Import)" }),
    el("button", {
      className: "btn-icon",
      textContent: "✕",
      "aria-label": "Modal schließen",
      onClick: close,
    }),
  ]);

  const body = el("div", { className: "modal-body" }, [
    el("p", {
      textContent:
        "Dieses Format entspricht der Spezifikation klangpultlight-workspace-v1. Du kannst die Konfiguration kopieren oder eine neue JSON-Struktur importieren.",
    }),
    el("div", { className: "form-group" }, [
      el("label", { for: "workspace-json-textarea", textContent: "Workspace JSON-Code" }),
      el("textarea", {
        id: "workspace-json-textarea",
        className: "input-field code-textarea",
        rows: "12",
        value: jsonStr,
      }),
    ]),
  ]);

  const errBox = el("div", { className: "modal-error-msg", style: "display: none;" });
  body.appendChild(errBox);

  const statusBox = el("div", { className: "modal-success-msg", style: "display: none;" });
  body.appendChild(statusBox);

  const footer = el("div", { className: "modal-footer" }, [
    el("button", {
      type: "button",
      className: "btn btn-ghost",
      textContent: "In Zwischenablage kopieren",
      "aria-label": "Workspace JSON in Zwischenablage kopieren",
      onClick: async () => {
        const txt = body.querySelector("textarea").value;
        try {
          await navigator.clipboard.writeText(txt);
          statusBox.textContent = "In die Zwischenablage kopiert!";
          statusBox.style.display = "block";
          errBox.style.display = "none";
        } catch {
          errBox.textContent = "Kopieren fehlgeschlagen — bitte manuell markieren.";
          errBox.style.display = "block";
        }
      },
    }),
    el("button", {
      type: "button",
      className: "btn btn-primary",
      textContent: "Workspace importieren",
      "aria-label": "Angezeigtes JSON als Workspace importieren",
      onClick: async () => {
        errBox.style.display = "none";
        statusBox.style.display = "none";
        const txt = body.querySelector("textarea").value.trim();
        let parsed;
        try {
          parsed = JSON.parse(txt);
        } catch (e) {
          errBox.textContent = `JSON-Syntaxfehler: ${e.message}`;
          errBox.style.display = "block";
          return;
        }

        const importRes = await importWorkspace(_currentProjectId, parsed);
        if (!importRes.ok) {
          errBox.textContent = `Importfehler: ${importRes.error}`;
          errBox.style.display = "block";
          return;
        }

        statusBox.textContent = `Erfolgreich importiert: ${importRes.data.assets_count} Assets, ${importRes.data.line_count} Line-Slots.`;
        statusBox.style.display = "block";

        await _loadProjectData(_currentProjectId);
        _buildView();
      },
    }),
    el("button", {
      type: "button",
      className: "btn btn-ghost",
      textContent: "Schließen",
      "aria-label": "Dialog schließen",
      onClick: close,
    }),
  ]);

  dialog.appendChild(header);
  dialog.appendChild(body);
  dialog.appendChild(footer);
  overlay.appendChild(dialog);

  function close() {
    overlay.remove();
    document.removeEventListener("keydown", onKey);
  }

  function onKey(e) {
    if (e.key === "Escape") close();
  }
  document.addEventListener("keydown", onKey);

  document.body.appendChild(overlay);
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function plural(count, singular, pluralForm) {
  return count === 1 ? singular : pluralForm;
}
