/**
 * i18n.js — Client-Adapter für Internationalisierung im Klangpult light Planer.
 *
 * Implementiert Tier-2 Mehrsprachigkeit nach Policy P-006:
 * - 6 Zielsprachen: de (Deutsch), en (English), es (Español), zh (简体中文), ja (日本語), ru (Русский)
 * - Deterministische 4-stufige Fallback-Kette: target -> en -> de -> key
 * - Persistenz via localStorage ('klangpult_planer_lang')
 * - Aktualisierung des document.documentElement.lang Attributs
 * - Dynamische Attribut- und Text-Aktualisierung (data-i18n, data-i18n-title, etc.)
 */

export const SUPPORTED_LANGUAGES = ["de", "en", "es", "zh", "ja", "ru"];
export const DEFAULT_LANGUAGE = "de";
export const FALLBACK_CHAIN = ["en", "de"];

export const LANGUAGE_NAMES = {
  de: "Deutsch",
  en: "English",
  es: "Español",
  zh: "简体中文",
  ja: "日本語",
  ru: "Русский",
};

// Eingebettetes Kernwörterbuch als Offline-/Zero-Latency-Fallback
let _translations = {
  "app_title": {
    "de": "Klangpult light – Recorder",
    "en": "Klangpult light – Recorder",
    "es": "Klangpult light – Grabador",
    "zh": "Klangpult light – 录音台",
    "ja": "Klangpult light – レコーダー",
    "ru": "Klangpult light – Рекордер"
  },
  "planer_title": {
    "de": "Klangpult light – Planer",
    "en": "Klangpult light – Planner",
    "es": "Klangpult light – Planificador",
    "zh": "Klangpult light – 策划器",
    "ja": "Klangpult light – プランナー",
    "ru": "Klangpult light – Планировщик"
  },
  "start_recording": {
    "de": "Aufnahme starten",
    "en": "Start Recording",
    "es": "Iniciar grabación",
    "zh": "开始录制",
    "ja": "録音開始",
    "ru": "Начать запись"
  },
  "stop_recording": {
    "de": "Aufnahme stoppen",
    "en": "Stop Recording",
    "es": "Detener grabación",
    "zh": "停止录制",
    "ja": "録音停止",
    "ru": "Остановить запись"
  },
  "sources": {
    "de": "Quellen",
    "en": "Sources",
    "es": "Fuentes",
    "zh": "信号源",
    "ja": "ソース",
    "ru": "Источники"
  },
  "recordings": {
    "de": "Aufnahmen",
    "en": "Recordings",
    "es": "Grabaciones",
    "zh": "录音列表",
    "ja": "録音一覧",
    "ru": "Записи"
  },
  "levels": {
    "de": "Pegel",
    "en": "Levels",
    "es": "Niveles",
    "zh": "电平",
    "ja": "レベル",
    "ru": "Уровни"
  },
  "recording_mode": {
    "de": "Aufnahme-Modus",
    "en": "Recording Mode",
    "es": "Modo de grabación",
    "zh": "录制模式",
    "ja": "録音モード",
    "ru": "Режим записи"
  },
  "recording_mode_tooltip": {
    "de": "Wählt, ob Ton, Video oder beides aufgezeichnet wird.",
    "en": "Selects whether audio, video, or both are recorded.",
    "es": "Selecciona si se graba audio, vídeo o ambos.",
    "zh": "选择录制音频、视频还是两者兼录。",
    "ja": "音声、映像、またはその両方を記録するかを選択します。",
    "ru": "Выбирает, записывать ли звук, видео или то и другое."
  },
  "mode_audio_video": {
    "de": "Ton + Video",
    "en": "Audio + Video",
    "es": "Audio + Vídeo",
    "zh": "音频 + 视频",
    "ja": "音声 + 映像",
    "ru": "Аудио + Видео"
  },
  "mode_audio_only": {
    "de": "Nur Ton",
    "en": "Audio Only",
    "es": "Solo audio",
    "zh": "仅音频",
    "ja": "音声のみ",
    "ru": "Только аудио"
  },
  "mode_video_only": {
    "de": "Nur Video",
    "en": "Video Only",
    "es": "Solo vídeo",
    "zh": "仅视频",
    "ja": "映像のみ",
    "ru": "Только видео"
  },
  "capture_active": {
    "de": "Mitschneiden:",
    "en": "Capture:",
    "es": "Capturar:",
    "zh": "录制:",
    "ja": "キャプチャ:",
    "ru": "Захват:"
  },
  "available_inputs": {
    "de": "Verfügbare Eingänge:",
    "en": "Available Inputs:",
    "es": "Entradas disponibles:",
    "zh": "可用输入:",
    "ja": "利用可能な入力:",
    "ru": "Доступные входы:"
  },
  "video_sources": {
    "de": "Video-Quellen:",
    "en": "Video Sources:",
    "es": "Fuentes de vídeo:",
    "zh": "视频源:",
    "ja": "映像ソース:",
    "ru": "Источники видео:"
  },
  "preview": {
    "de": "Vorschau:",
    "en": "Preview:",
    "es": "Vista previa:",
    "zh": "预览:",
    "ja": "プレビュー:",
    "ru": "Предпросмотр:"
  },
  "open_planer": {
    "de": "🌐 Planer im Browser öffnen",
    "en": "🌐 Open Planner in Browser",
    "es": "🌐 Abrir planificador en el navegador",
    "zh": "🌐 在浏览器中打开策划器",
    "ja": "🌐 ブラウザでプランナーを開く",
    "ru": "🌐 Открыть планировщик в браузере"
  },
  "open_planer_tooltip": {
    "de": "Öffnet die Web-App zur Episoden- und Medienplanung (Standard: http://127.0.0.1:8770) im Browser",
    "en": "Opens the web application for episode and media planning (default: http://127.0.0.1:8770) in browser",
    "es": "Abre la aplicación web de planificación de episodios y medios (predeterminado: http://127.0.0.1:8770) en el navegador",
    "zh": "在浏览器中打开剧集和媒体策划 Web 应用（默认：http://127.0.0.1:8770）",
    "ja": "エピソードおよびメディア計画用 Web アプリ（デフォルト: http://127.0.0.1:8770）をブラウザで開きます",
    "ru": "Открывает веб-приложение планирования эпизодов и медиа (по умолчанию: http://127.0.0.1:8770) в браузере"
  },
  "pads_title": {
    "de": "Einspieler",
    "en": "Soundboard Pads",
    "es": "Efectos y cortes",
    "zh": "音效按键",
    "ja": "サンプラーパッド",
    "ru": "Сэмплерные кнопки"
  },
  "add_pad": {
    "de": "+ Einspieler hinzufügen",
    "en": "+ Add Pad",
    "es": "+ Añadir efecto",
    "zh": "+ 添加按键",
    "ja": "+ パッド追加",
    "ru": "+ Добавить кнопку"
  },
  "no_pads_yet": {
    "de": "Noch keine Einspieler – Button oben nutzen, um Pads anzulegen.",
    "en": "No pads yet – use the button above to add pads.",
    "es": "Todavía no hay efectos: usa el botón superior para crearlos.",
    "zh": "暂无音效按键 – 请使用上方按钮创建。",
    "ja": "パッドがまだありません – 上のボタンから追加してください。",
    "ru": "Кнопок ещё нет – используйте кнопку выше для добавления."
  },
  "no_board_loaded": {
    "de": "Kein Board geladen.",
    "en": "No board loaded.",
    "es": "No hay panel cargado.",
    "zh": "未加载面板。",
    "ja": "ボードが読み込まれていません。",
    "ru": "Панель не загружена."
  },
  "no_devices_found": {
    "de": "Keine Geräte gefunden",
    "en": "No devices found",
    "es": "No se encontraron dispositivos",
    "zh": "未找到设备",
    "ja": "デバイスが見つかりません",
    "ru": "Устройства не найдены"
  },
  "mock_mode_active": {
    "de": "Mock-Modus aktiv (keine reale Audio-Hardware)",
    "en": "Mock mode active (no real audio hardware)",
    "es": "Modo simulado activo (sin hardware de audio real)",
    "zh": "模拟模式激活（无真实音频硬件）",
    "ja": "モックモード有効（実オーディオハードウェアなし）",
    "ru": "Активен демо-режим (нет реального аудиооборудования)"
  },
  "no_loopback_available": {
    "de": "Kein Loopback verfügbar – Checkbox deaktiviert",
    "en": "No loopback available – checkbox disabled",
    "es": "Sin loopback disponible – casilla desactivada",
    "zh": "无可用回环录音 – 复选框已停用",
    "ja": "ループバック利用不可 – チェックボックス無効",
    "ru": "Петлевой захват недоступен – флажок отключен"
  },
  "header_recording_branch": {
    "de": "Aufnahme / Branch",
    "en": "Recording / Branch",
    "es": "Grabación / Rama",
    "zh": "录音 / 分支",
    "ja": "録音 / ブランチ",
    "ru": "Запись / Ветка"
  },
  "header_duration": {
    "de": "Dauer",
    "en": "Duration",
    "es": "Duración",
    "zh": "时长",
    "ja": "再生時間",
    "ru": "Длительность"
  },
  "header_format": {
    "de": "Format",
    "en": "Format",
    "es": "Formato",
    "zh": "格式",
    "ja": "フォーマット",
    "ru": "Формат"
  },
  "status_ready": {
    "de": "Bereit",
    "en": "Ready",
    "es": "Listo",
    "zh": "就绪",
    "ja": "待機中",
    "ru": "Готов"
  },
  "status_recording": {
    "de": "Aufnahme läuft…",
    "en": "Recording…",
    "es": "Grabando…",
    "zh": "正在录制…",
    "ja": "録音中…",
    "ru": "Идёт запись…"
  },
  "status_stopped": {
    "de": "Aufnahme beendet",
    "en": "Recording stopped",
    "es": "Grabación finalizada",
    "zh": "录制已结束",
    "ja": "録音終了",
    "ru": "Запись завершена"
  },
  "delete": {
    "de": "Löschen",
    "en": "Delete",
    "es": "Eliminar",
    "zh": "删除",
    "ja": "削除",
    "ru": "Удалить"
  },
  "rename": {
    "de": "Umbenennen",
    "en": "Rename",
    "es": "Renombrar",
    "zh": "重命名",
    "ja": "名前変更",
    "ru": "Переименовать"
  },
  "play": {
    "de": "Abspielen",
    "en": "Play",
    "es": "Reproducir",
    "zh": "播放",
    "ja": "再生",
    "ru": "Воспроизвести"
  },
  "reveal_in_explorer": {
    "de": "Im Explorer anzeigen",
    "en": "Show in Explorer",
    "es": "Mostrar en el explorador",
    "zh": "在文件资源管理器中显示",
    "ja": "エクスプローラーで表示",
    "ru": "Показать в проводнике"
  },
  "language": {
    "de": "Sprache",
    "en": "Language",
    "es": "Idioma",
    "zh": "语言",
    "ja": "言語",
    "ru": "Язык"
  },
  "settings": {
    "de": "Einstellungen",
    "en": "Settings",
    "es": "Configuración",
    "zh": "设置",
    "ja": "設定",
    "ru": "Настройки"
  },
  "nav_library": {
    "de": "Bibliothek",
    "en": "Library",
    "es": "Biblioteca",
    "zh": "媒体库",
    "ja": "ライブラリ",
    "ru": "Библиотека"
  },
  "nav_projects": {
    "de": "Projekte",
    "en": "Projects",
    "es": "Proyectos",
    "zh": "项目",
    "ja": "プロジェクト",
    "ru": "Проекты"
  },
  "nav_assets": {
    "de": "Assets & Board",
    "en": "Assets & Board",
    "es": "Recursos y panel",
    "zh": "素材与面板",
    "ja": "素材とボード",
    "ru": "Ресурсы и панель"
  },
  "nav_teleprompter": {
    "de": "Teleprompter",
    "en": "Teleprompter",
    "es": "Teleprónter",
    "zh": "提词器",
    "ja": "テレプロンプター",
    "ru": "Телесуфлёр"
  },
  "nav_monitor": {
    "de": "KI-Monitor",
    "en": "AI Monitor",
    "es": "Monitor IA",
    "zh": "AI 监视器",
    "ja": "AI モニター",
    "ru": "ИИ-монитор"
  },
  "checking_connection": {
    "de": "Prüfe Verbindung…",
    "en": "Checking connection…",
    "es": "Comprobando conexión…",
    "zh": "正在检查连接…",
    "ja": "接続確認中…",
    "ru": "Проверка соединения…"
  },
  "reload_view": {
    "de": "Aktuelle Ansicht neu laden",
    "en": "Reload current view",
    "es": "Recargar vista actual",
    "zh": "重新加载当前视图",
    "ja": "現在の表示を再読み込み",
    "ru": "Перезагрузить текущий вид"
  },
  "header_title": {
    "de": "Titel",
    "en": "Title",
    "es": "Título",
    "zh": "标题",
    "ja": "タイトル",
    "ru": "Название"
  },
  "header_created": {
    "de": "Erstellt",
    "en": "Created",
    "es": "Creado",
    "zh": "创建时间",
    "ja": "作成日時",
    "ru": "Создано"
  },
  "title": {
    "de": "Titel",
    "en": "Title",
    "es": "Título",
    "zh": "标题",
    "ja": "タイトル",
    "ru": "Название"
  },
  "title_placeholder": {
    "de": "Aufnahmetitel …",
    "en": "Recording title …",
    "es": "Título de la grabación …",
    "zh": "录音标题 …",
    "ja": "録音タイトル …",
    "ru": "Название записи …"
  },
  "branch_create": {
    "de": "Branch anlegen",
    "en": "Create Branch",
    "es": "Crear rama",
    "zh": "创建分支",
    "ja": "ブランチ作成",
    "ru": "Создать ветку"
  }
};

let _currentLang = DEFAULT_LANGUAGE;
const _listeners = new Set();

/**
 * Ermittelt die bevorzugte Sprache (localStorage -> navigator.language -> DEFAULT_LANGUAGE).
 */
export function detectLanguage() {
  try {
    const saved = localStorage.getItem("klangpult_planer_lang");
    if (saved && SUPPORTED_LANGUAGES.includes(saved)) {
      return saved;
    }
  } catch (_) {
    // localStorage nicht verfügbar
  }

  try {
    const nav = (navigator.language || navigator.userLanguage || "").toLowerCase();
    const code = nav.split("-")[0];
    if (SUPPORTED_LANGUAGES.includes(code)) {
      return code;
    }
  } catch (_) {
    // navigator nicht verfügbar
  }

  return DEFAULT_LANGUAGE;
}

/**
 * Übersetzt einen Schlüssel in die aktive Sprache mit robuster Fallback-Kette.
 *
 * @param {string} key - Übersetzungsschlüssel
 * @param {Record<string, string|number>} [params] - Platzhalter-Parameter
 * @returns {string} Übersetzter Text
 */
export function t(key, params = {}) {
  if (!key) return "";

  const entry = _translations[key];
  let text = null;

  if (entry && typeof entry === "object") {
    // 1. Zielsprache
    if (entry[_currentLang] && typeof entry[_currentLang] === "string" && entry[_currentLang].trim()) {
      text = entry[_currentLang];
    } else {
      // 2. Fallback-Kette (en -> de)
      for (const fb of FALLBACK_CHAIN) {
        if (entry[fb] && typeof entry[fb] === "string" && entry[fb].trim()) {
          text = entry[fb];
          break;
        }
      }
    }
  }

  if (text === null) {
    text = key;
  }

  // Parameter ersetzen: {name}
  if (params && typeof params === "object") {
    for (const [pKey, pVal] of Object.entries(params)) {
      text = text.replace(new RegExp("\\{" + pKey + "\\}", "g"), String(pVal));
    }
  }

  return text;
}

/**
 * Setzt die aktive Sprache, aktualisiert html[lang] und benachrichtigt Listener.
 *
 * @param {string} lang - Neuer Sprachcode
 * @returns {boolean} true wenn erfolgreich gesetzt
 */
export function setLanguage(lang) {
  if (!SUPPORTED_LANGUAGES.includes(lang)) {
    return false;
  }

  const changed = _currentLang !== lang;
  _currentLang = lang;

  try {
    localStorage.setItem("klangpult_planer_lang", lang);
  } catch (_) {}

  if (typeof document !== "undefined" && document.documentElement) {
    document.documentElement.lang = lang;
  }

  applyTranslations();

  if (changed) {
    for (const cb of _listeners) {
      try {
        cb(lang);
      } catch (err) {
        console.error("[i18n] Fehler im Listener-Callback:", err);
      }
    }
  }

  return true;
}

/**
 * Liefert den aktuellen Sprachcode.
 */
export function getLanguage() {
  return _currentLang;
}

/**
 * Liefert alle unterstützten Sprachcodes.
 */
export function getSupportedLanguages() {
  return [...SUPPORTED_LANGUAGES];
}

/**
 * Registriert einen Listener für Sprachwechsel.
 */
export function onLanguageChange(callback) {
  if (typeof callback === "function") {
    _listeners.add(callback);
  }
}

/**
 * Entfernt einen registrierten Listener.
 */
export function offLanguageChange(callback) {
  _listeners.delete(callback);
}

/**
 * Durchsucht den DOM nach Elementen mit data-i18n-* Attributen und wendet Übersetzungen an.
 *
 * @param {HTMLElement|Document} [root=document]
 */
export function applyTranslations(root = (typeof document !== "undefined" ? document : null)) {
  if (!root) return;

  // Textinhalt: data-i18n="key"
  const textElements = root.querySelectorAll("[data-i18n]");
  for (const el of textElements) {
    const key = el.getAttribute("data-i18n");
    if (key) {
      el.textContent = t(key);
    }
  }

  // Title / Tooltip: data-i18n-title="key"
  const titleElements = root.querySelectorAll("[data-i18n-title]");
  for (const el of titleElements) {
    const key = el.getAttribute("data-i18n-title");
    if (key) {
      el.title = t(key);
    }
  }

  // ARIA-Label: data-i18n-aria-label="key"
  const ariaElements = root.querySelectorAll("[data-i18n-aria-label]");
  for (const el of ariaElements) {
    const key = el.getAttribute("data-i18n-aria-label");
    if (key) {
      el.setAttribute("aria-label", t(key));
    }
  }

  // Placeholder: data-i18n-placeholder="key"
  const placeholderElements = root.querySelectorAll("[data-i18n-placeholder]");
  for (const el of placeholderElements) {
    const key = el.getAttribute("data-i18n-placeholder");
    if (key) {
      el.placeholder = t(key);
    }
  }
}

/**
 * Initialisiert das I18N-System für den Planer.
 */
export async function initI18n() {
  // 1. Gespeicherte / erkannte Sprache einstellen
  const initialLang = detectLanguage();
  _currentLang = initialLang;
  if (typeof document !== "undefined" && document.documentElement) {
    document.documentElement.lang = initialLang;
  }

  // 2. Übersetzungen asynchron vom Server nachladen (falls neue Keys existieren)
  try {
    const resp = await fetch("/api/translations");
    if (resp.ok) {
      const liveData = await resp.json();
      if (liveData && typeof liveData === "object") {
        _translations = { ..._translations, ...liveData };
      }
    }
  } catch (_) {
    // Offline oder Server antwortet nicht: eingebettetes Wörterbuch bleibt aktiv
  }

  // 3. UI übersetzen
  applyTranslations();

  return _currentLang;
}
