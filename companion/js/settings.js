/**
 * BITOS Device Settings Manager
 *
 * Reads settings from HTTP server and BLE device status.
 * Writes setting changes via HTTP PUT.
 * Auto-refreshes every 5 seconds.
 */

class BitosSettings {
  constructor(serverUrl) {
    this.server = serverUrl;
    this.ble = null; // BitosCompanion instance (optional)
    this.settings = {};
    this.deviceStatus = {};
    this.connectionMode = 'offline'; // 'ble' | 'http' | 'offline'
    this._refreshTimer = null;
    this._listeners = [];
  }

  onChange(fn) {
    this._listeners.push(fn);
  }

  _emit() {
    for (const fn of this._listeners) fn(this.settings, this.deviceStatus);
  }

  // ── Read settings ──────────────────────────────────────

  async refresh() {
    let httpOk = false;
    let bleOk = false;

    // Try HTTP first
    try {
      const [settingsResp, healthResp] = await Promise.all([
        fetch(`${this.server}/settings/device`, { signal: AbortSignal.timeout(3000) }).catch(() => null),
        fetch(`${this.server}/health`, { signal: AbortSignal.timeout(3000) }).catch(() => null),
      ]);

      if (healthResp && healthResp.ok) {
        const health = await healthResp.json();
        this.deviceStatus.version = health.version || 'unknown';
        this.deviceStatus.commit = health.commit || 'unknown';
        this.deviceStatus.server_online = true;
        httpOk = true;
      }

      if (settingsResp && settingsResp.ok) {
        const data = await settingsResp.json();
        // Merge server settings
        Object.assign(this.settings, data);
      }

      // Also try /settings/ui for font settings
      try {
        const uiResp = await fetch(`${this.server}/settings/ui`, { signal: AbortSignal.timeout(3000) });
        if (uiResp.ok) {
          const ui = await uiResp.json();
          if (ui.font_family) this.settings.font_family = ui.font_family;
          if (ui.text_speed) this.settings.text_speed = ui.text_speed;
          if (ui.font_scale != null) this.settings.font_scale = ui.font_scale;
        }
      } catch (_) {}

      // Try /device/version for firmware info
      try {
        const verResp = await fetch(`${this.server}/device/version`, { signal: AbortSignal.timeout(3000) });
        if (verResp.ok) {
          const ver = await verResp.json();
          this.deviceStatus.firmware_version = ver.version || ver.firmware_version || 'unknown';
          this.deviceStatus.commit = ver.commit || this.deviceStatus.commit;
          this.deviceStatus.update_available = ver.update_available || false;
          this.deviceStatus.behind = ver.behind || 0;
        }
      } catch (_) {}

    } catch (_) {
      this.deviceStatus.server_online = false;
    }

    // Try BLE device status
    if (this.ble && this.ble.device && this.ble.device.gatt && this.ble.device.gatt.connected) {
      try {
        const status = await this.ble.readStatus();
        this.deviceStatus.battery = status.battery;
        this.deviceStatus.wifi_ssid = status.wifi_ssid || status.ssid;
        this.deviceStatus.wifi_connected = status.wifi_connected || status.connected;
        bleOk = true;
      } catch (_) {}
    }

    // HTTP fallback for battery when BLE unavailable
    if (!bleOk && httpOk) {
      try {
        const battResp = await fetch(`${this.server}/device/battery`, { signal: AbortSignal.timeout(3000) });
        if (battResp && battResp.ok) {
          const batt = await battResp.json();
          if (batt.present) {
            this.deviceStatus.battery = batt.pct;
            this.deviceStatus.charging = batt.charging;
          }
        }
      } catch (_) {}
    }

    // Determine connection mode
    if (bleOk && httpOk) this.connectionMode = 'ble';
    else if (httpOk) this.connectionMode = 'http';
    else if (bleOk) this.connectionMode = 'ble';
    else this.connectionMode = 'offline';

    this._emit();
  }

  // ── Write settings ─────────────────────────────────────

  async setSetting(key, value) {
    this.settings[key] = value;
    this._emit();

    // Try the specific device settings endpoint first
    // Server expects { key: "setting_name", value: <val> }
    try {
      const resp = await fetch(`${this.server}/settings/device`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
        signal: AbortSignal.timeout(5000),
      });
      if (resp.ok) return true;
      // Log validation errors so they aren't silently swallowed
      if (resp.status === 422 || resp.status === 400) {
        const err = await resp.json().catch(() => ({}));
        console.warn('[settings] server rejected', key, ':', err.detail || resp.statusText);
      }
    } catch (_) {}

    // Fallback: try /settings/ui for display settings
    if (key === 'font_family' || key === 'text_speed' || key === 'font_scale') {
      try {
        const resp = await fetch(`${this.server}/settings/ui`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ [key]: value }),
          signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) return true;
      } catch (_) {}
    }

    return false;
  }

  // ── Auto-refresh ───────────────────────────────────────

  startAutoRefresh(intervalMs = 5000) {
    this.stopAutoRefresh();
    this.refresh();
    this._refreshTimer = setInterval(() => this.refresh(), intervalMs);
  }

  stopAutoRefresh() {
    if (this._refreshTimer) {
      clearInterval(this._refreshTimer);
      this._refreshTimer = null;
    }
  }
}

// ── Setting definitions ────────────────────────────────────

const SETTING_GROUPS = [
  {
    id: 'voice',
    label: 'VOICE',
    icon: '🔊',
    settings: [
      { key: 'voice_mode', label: 'Voice mode', type: 'picker', options: ['off', 'on', 'auto'], default: 'auto' },
      { key: 'volume', label: 'Volume', type: 'slider', min: 0, max: 100, step: 5, default: 70 },
      { key: 'tts_engine', label: 'TTS engine', type: 'picker', options: ['auto', 'speechify', 'chatterbox', 'piper', 'openai', 'espeak'], default: 'auto' },
    ],
  },
  {
    id: 'ai',
    label: 'AI',
    icon: '◎',
    settings: [
      { key: 'agent_mode', label: 'Agent mode', type: 'picker', options: ['producer', 'hacker', 'clown', 'monk', 'storyteller', 'director'], default: 'producer' },
      { key: 'ai_model', label: 'AI model', type: 'picker', options: ['default', 'haiku', 'sonnet', 'opus'], default: 'default' },
      { key: 'extended_thinking', label: 'Extended thinking', type: 'toggle', default: false },
      { key: 'web_search', label: 'Web search', type: 'toggle', default: true },
      { key: 'memory', label: 'Memory', type: 'toggle', default: true },
    ],
  },
  {
    id: 'display',
    label: 'DISPLAY',
    icon: '▦',
    settings: [
      { key: 'text_speed', label: 'Text speed', type: 'picker', options: ['slow', 'normal', 'fast'], default: 'normal' },
      { key: 'font_family', label: 'Font', type: 'picker', options: ['press_start_2p', 'monocraft'], default: 'monocraft' },
      { key: 'font_scale', label: 'Font size', type: 'slider', min: 0.8, max: 1.5, step: 0.1, default: 1.0 },
    ],
  },
];
