/**
 * remote.js — WebSocket-Client für die Live-Kopplung an den Klangpult light – Recorder.
 *
 * Verbindet sich nach remote_protocol_v1 mit dem Recorder (Port 8768) und verteilt:
 *   - state_update (Peaks, Recording-Status, Active Pads, Prompter-Line)
 *   - transcript_chunk (Live-STT Chunks von Whisper / STT)
 *
 * Sendet Befehle an den Recorder:
 *   - scroll_teleprompter (delta)
 *   - insert_chapter_marker (label)
 *   - trigger_pad (pad_id)
 *   - toggle_mute (source_id)
 */

class RemoteConnection {
  constructor() {
    this.ws = null;
    this.url = "ws://127.0.0.1:8768";
    this.listeners = new Map();
    this.reconnectTimer = null;
    this.isConnected = false;
    this.status = "disconnected"; // disconnected | connecting | connected
    this.autoReconnect = true;
    this.latestState = {
      channel_peaks: [],
      recording: false,
      active_pad_ids: [],
      prompter_line: 0,
    };
  }

  /**
   * Registriert einen Event-Listener.
   * @param {string} event 'state_update' | 'transcript_chunk' | 'connection_change'
   * @param {Function} callback
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set());
    }
    this.listeners.get(event).add(callback);
    return () => this.off(event, callback);
  }

  /**
   * Entfernt einen Event-Listener.
   * @param {string} event
   * @param {Function} callback
   */
  off(event, callback) {
    if (this.listeners.has(event)) {
      this.listeners.get(event).delete(callback);
    }
  }

  /**
   * Sendet ein Event an alle registrierten Listener.
   * @private
   */
  _emit(event, data) {
    if (this.listeners.has(event)) {
      for (const cb of this.listeners.get(event)) {
        try {
          cb(data);
        } catch (err) {
          console.error(`Fehler im Remote-Listener für '${event}':`, err);
        }
      }
    }
  }

  /**
   * Ändert den Verbindungsstatus und benachrichtigt Listener.
   * @private
   */
  _setStatus(status) {
    this.status = status;
    this.isConnected = status === "connected";
    this._emit("connection_change", { status, isConnected: this.isConnected });
  }

  /**
   * Startet die WebSocket-Verbindung.
   * @param {string} [customUrl]
   */
  connect(customUrl) {
    if (customUrl) this.url = customUrl;
    if (typeof WebSocket === "undefined") {
      this._setStatus("disconnected");
      return;
    }
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
      return;
    }

    this._setStatus("connecting");

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this._setStatus("connected");
        if (this.reconnectTimer) {
          clearTimeout(this.reconnectTimer);
          this.reconnectTimer = null;
        }
      };

      this.ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data);
          if (msg.type === "state_update") {
            this.latestState = {
              channel_peaks: msg.channel_peaks || [],
              recording: Boolean(msg.recording),
              active_pad_ids: msg.active_pad_ids || [],
              prompter_line: Number(msg.prompter_line || 0),
            };
            this._emit("state_update", this.latestState);
          } else if (msg.type === "transcript_chunk") {
            this._emit("transcript_chunk", {
              text: msg.text || "",
              is_final: Boolean(msg.is_final),
              t_start: Number(msg.t_start || 0),
              engine: msg.engine || "unbekannt",
            });
          }
        } catch (err) {
          console.warn("RemoteConnection: Fehler beim Parsen der WebSocket-Nachricht:", err);
        }
      };

      this.ws.onclose = () => {
        this._setStatus("disconnected");
        this._scheduleReconnect();
      };

      this.ws.onerror = () => {
        this._setStatus("disconnected");
      };
    } catch {
      this._setStatus("disconnected");
      this._scheduleReconnect();
    }
  }

  /**
   * Plant eine Wiederverbindung nach Verbindungsverlust.
   * @private
   */
  _scheduleReconnect() {
    if (!this.autoReconnect) return;
    if (this.reconnectTimer) return;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      this.connect();
    }, 3000);
  }

  /**
   * Trennt die WebSocket-Verbindung manuell.
   */
  disconnect() {
    this.autoReconnect = false;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.close();
      } catch {
        // Ignorieren
      }
      this.ws = null;
    }
    this._setStatus("disconnected");
  }

  /**
   * Sendet eine Nachricht an den Recorder.
   * @param {object} payload
   * @returns {boolean} True wenn erfolgreich versendet
   */
  send(payload) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      try {
        this.ws.send(JSON.stringify(payload));
        return true;
      } catch (err) {
        console.error("RemoteConnection: Fehler beim Senden:", err);
      }
    }
    return false;
  }

  /**
   * Sendet einen Teleprompter-Scrollbefehl.
   * @param {number} delta Zeilenversatz (z. B. +1, -1)
   */
  sendScrollTeleprompter(delta) {
    return this.send({
      type: "scroll_teleprompter",
      delta: Number(delta),
    });
  }

  /**
   * Sendet einen Kapitelmarker-Befehl.
   * @param {string} label Name des Kapitelmarkers
   */
  sendInsertChapterMarker(label) {
    return this.send({
      type: "insert_chapter_marker",
      label: String(label || "").trim(),
    });
  }

  /**
   * Triggert ein Soundboard-Pad.
   * @param {string} padId
   */
  sendTriggerPad(padId) {
    return this.send({
      type: "trigger_pad",
      pad_id: String(padId),
    });
  }

  /**
   * Schaltet einen Audio-Kanal stumm / aktiv.
   * @param {string} sourceId
   */
  sendToggleMute(sourceId) {
    return this.send({
      type: "toggle_mute",
      source_id: String(sourceId),
    });
  }
}

// Singleton-Export
export const remote = new RemoteConnection();
