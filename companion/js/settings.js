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

    // Check device provisioning server (port 8080) as additional signal
    let deviceOk = false;
    if (typeof checkDeviceHealth === 'function') {
      try {
        const deviceCheck = await checkDeviceHealth();
        deviceOk = deviceCheck.online;
        if (deviceOk) {
          this.deviceStatus.device_online = true;

          // Try to read settings from device provisioning server
          const deviceUrl = typeof getDeviceUrl === 'function' ? getDeviceUrl() : null;
          if (deviceUrl) {
            try {
              const devSettingsResp = await fetch(`${deviceUrl}/api/settings`, { signal: AbortSignal.timeout(3000) });
              if (devSettingsResp.ok) {
                const devSettings = await devSettingsResp.json();
                // Merge device settings (don't override server settings)
                for (const [k, v] of Object.entries(devSettings)) {
                  if (this.settings[k] === undefined || this.settings[k] === null) {
                    this.settings[k] = v;
                  }
                }
              }
            } catch (_) {}

            // Fetch WiFi status from device
            try {
              const wifiResp = await fetch(`${deviceUrl}/api/wifi/status`, { signal: AbortSignal.timeout(3000) });
              if (wifiResp.ok) {
                const ws = await wifiResp.json();
                if (ws.connected) {
                  this.deviceStatus.wifi_connected = true;
                  this.deviceStatus.wifi_ssid = ws.ssid || this.deviceStatus.wifi_ssid;
                }
              }
            } catch (_) {}
          }

          // Fetch richer status from device if server was unreachable
          if (!httpOk && typeof fetchDeviceStatus === 'function') {
            const devStatus = await fetchDeviceStatus();
            if (devStatus) {
              if (devStatus.battery != null) this.deviceStatus.battery = devStatus.battery;
              if (devStatus.charging != null) this.deviceStatus.charging = devStatus.charging;
              if (devStatus.wifi_ssid) {
                this.deviceStatus.wifi_ssid = devStatus.wifi_ssid;
                this.deviceStatus.wifi_connected = true;
              }
            }
          }
        }
      } catch (_) {}
    }

    // Determine connection mode — device is online if either server or device endpoint responds
    if (bleOk && httpOk) this.connectionMode = 'ble';
    else if (httpOk) this.connectionMode = 'http';
    else if (bleOk) this.connectionMode = 'ble';
    else if (deviceOk) this.connectionMode = 'http';
    else this.connectionMode = 'offline';

    this._emit();
  }

  // ── Write settings ─────────────────────────────────────

  async setSetting(key, value) {
    this.settings[key] = value;
    this._emit();

    // Try the specific device settings endpoint first (main server on port 8000)
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

    // Fallback: try the device provisioning server (port 8080) /api/settings endpoint
    try {
      const deviceUrl = typeof getDeviceUrl === 'function' ? getDeviceUrl() : null;
      if (deviceUrl) {
        const resp = await fetch(`${deviceUrl}/api/settings`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ key, value }),
          signal: AbortSignal.timeout(5000),
        });
        if (resp.ok) return true;
      }
    } catch (_) {}

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
    settings: [
      { key: 'voice_enabled', label: 'Voice output', type: 'toggle', default: false },
      { key: 'voice_mode', label: 'Voice mode', type: 'picker', options: ['off', 'on', 'auto'], default: 'auto' },
      { key: 'volume', label: 'Volume', type: 'slider', min: 0, max: 100, step: 5, default: 70 },
      { key: 'tts_engine', label: 'TTS engine', type: 'picker',
        options: ['auto', 'edge_tts', 'cartesia', 'speechify', 'openai', 'espeak'], default: 'auto' },
      { key: 'voice_id', label: 'Voice', type: 'voice_picker', default: '' },
      { key: 'voice_params', label: 'Voice tuning', type: 'voice_params', default: '{}' },
      { key: '_test_voice', label: 'Preview on device', type: 'action', action: 'test_voice' },
    ],
  },
  {
    id: 'text',
    label: 'TEXT',
    settings: [
      { key: 'text_speed', label: 'Speed preset', type: 'picker', options: ['slow', 'normal', 'fast', 'custom'], default: 'normal' },
      { key: 'tw_base_speed_ms', label: 'Base speed (ms/char)', type: 'slider', min: 10, max: 120, step: 5, default: 45, showWhen: 'custom' },
      { key: 'tw_punctuation', label: 'Punctuation pause', type: 'slider', min: 0.5, max: 3.0, step: 0.1, default: 1.0, showWhen: 'custom' },
      { key: 'tw_jitter', label: 'Jitter amount', type: 'slider', min: 0, max: 0.30, step: 0.01, default: 0.15, showWhen: 'custom' },
      { key: 'tw_common_speed', label: 'Common letter speed', type: 'slider', min: 0.5, max: 1.0, step: 0.05, default: 0.8, showWhen: 'custom' },
      { key: 'tw_rare_speed', label: 'Rare letter speed', type: 'slider', min: 1.0, max: 2.0, step: 0.05, default: 1.3, showWhen: 'custom' },
      { key: '_test_typewriter', label: 'Test on device', type: 'action', action: 'test_typewriter' },
    ],
  },
  {
    id: 'ai',
    label: 'AI',
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
    settings: [
      { key: 'font_family', label: 'Font', type: 'picker', options: ['press_start_2p', 'monocraft'], default: 'monocraft' },
      { key: 'font_scale', label: 'Font size', type: 'slider', min: 0.8, max: 1.5, step: 0.1, default: 1.0 },
    ],
  },
  {
    id: 'wakeword',
    label: 'WAKE WORD',
    settings: [
      { key: 'wake_word_enabled', label: 'Wake word', type: 'toggle', default: false },
      { key: 'wake_word_phrase', label: 'Phrase', type: 'picker', options: ['hey bitos', 'ok bitos', 'bitos'], default: 'hey bitos' },
      { key: 'wake_word_sensitivity', label: 'Sensitivity', type: 'slider', min: 0.1, max: 1.0, step: 0.1, default: 0.5 },
    ],
  },
  {
    id: 'sleep',
    label: 'SLEEP',
    settings: [
      { key: 'sleep_timeout_seconds', label: 'Sleep after', type: 'picker', options: ['30', '60', '120', '300', '600', 'never'], default: '60' },
      { key: 'safe_shutdown_pct', label: 'Auto-shutdown at %', type: 'slider', min: 0, max: 20, step: 1, default: 5 },
    ],
  },
];
