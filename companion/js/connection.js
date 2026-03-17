/**
 * BITOS Companion — Unified Connection Manager
 *
 * Auto-discovers the best connection method:
 *   1. Try HTTP first (faster, works everywhere including iOS)
 *   2. Fall back to BLE if HTTP unreachable and Web Bluetooth available
 *
 * Provides a single interface for all pages to use regardless of transport.
 * Persists connection settings to localStorage.
 */

const CONN_DEFAULTS = {
  deviceIp: 'bitos.local',
  port: 8080,
  preferredMode: 'auto', // 'auto' | 'wifi' | 'ble'
};

class ConnectionManager {
  constructor() {
    this._http = null;       // BitosHttpCompanion instance
    this._ble = null;        // BitosCompanion instance
    this._activeTransport = null; // 'http' | 'ble' | null
    this._logs = [];
    this._maxLogs = 200;
    this._listeners = [];
    this._pollTimer = null;
    this._deviceStatus = {};
    this._deviceInfo = {};

    // Load saved settings
    const saved = localStorage.getItem('bitos_conn_settings');
    if (saved) {
      try {
        this._settings = { ...CONN_DEFAULTS, ...JSON.parse(saved) };
      } catch (_) {
        this._settings = { ...CONN_DEFAULTS };
      }
    } else {
      this._settings = { ...CONN_DEFAULTS };
    }
  }

  // ── Public getters ──

  get connected() {
    return this._activeTransport !== null;
  }

  get transport() {
    return this._activeTransport;
  }

  get settings() {
    return { ...this._settings };
  }

  get deviceStatus() {
    return { ...this._deviceStatus };
  }

  get deviceInfo() {
    return { ...this._deviceInfo };
  }

  get logs() {
    return [...this._logs];
  }

  get companion() {
    if (this._activeTransport === 'http') return this._http;
    if (this._activeTransport === 'ble') return this._ble;
    return this._http || this._ble || null;
  }

  // ── Settings ──

  updateSettings(partial) {
    Object.assign(this._settings, partial);
    localStorage.setItem('bitos_conn_settings', JSON.stringify(this._settings));
    this._emit();
  }

  getHttpBaseUrl() {
    const ip = this._settings.deviceIp || 'bitos.local';
    const port = this._settings.port || 8080;
    return `http://${ip}:${port}`;
  }

  // ── Logging ──

  _log(level, msg) {
    const entry = {
      time: new Date().toISOString(),
      level,
      msg,
    };
    this._logs.push(entry);
    if (this._logs.length > this._maxLogs) {
      this._logs.shift();
    }
    console.log(`[CONN/${level}] ${msg}`);
  }

  // ── Event listeners ──

  onChange(fn) {
    this._listeners.push(fn);
  }

  _emit() {
    for (const fn of this._listeners) {
      try { fn(this); } catch (_) {}
    }
  }

  // ── Auto-discovery ──

  async autoConnect() {
    const mode = this._settings.preferredMode || 'auto';
    this._log('INFO', `Auto-connect starting (mode=${mode})`);

    if (mode === 'ble') {
      return this._connectBLE();
    }

    // Try HTTP first (works on iOS, faster)
    if (mode === 'wifi' || mode === 'auto') {
      const httpOk = await this._tryHTTP();
      if (httpOk) return true;
    }

    // Fall back to BLE if available and mode allows
    if (mode === 'auto' || mode === 'ble') {
      if (isBleAvailable()) {
        this._log('INFO', 'HTTP unreachable, BLE available — manual BLE connect needed');
        // Don't auto-trigger BLE since it requires user gesture
        return false;
      }
    }

    this._log('WARN', 'No connection method succeeded');
    this._activeTransport = null;
    this._emit();
    return false;
  }

  async _tryHTTP() {
    const baseUrl = this.getHttpBaseUrl();
    this._log('INFO', `Trying HTTP at ${baseUrl}`);
    try {
      const http = new BitosHttpCompanion(baseUrl);
      await http.connect();
      this._http = http;
      this._activeTransport = 'http';
      this._log('INFO', 'HTTP connected successfully');

      // Read device info
      try {
        this._deviceInfo = await http.readDeviceInfo();
        this._log('INFO', `Device: ${this._deviceInfo.model || 'BITOS'} (${(this._deviceInfo.serial || '').slice(-6)})`);
      } catch (_) {}

      this._emit();
      return true;
    } catch (e) {
      this._log('WARN', `HTTP failed: ${e.message}`);
      return false;
    }
  }

  async connectHTTP(ip, port) {
    if (ip) this._settings.deviceIp = ip;
    if (port) this._settings.port = port;
    localStorage.setItem('bitos_conn_settings', JSON.stringify(this._settings));

    const baseUrl = this.getHttpBaseUrl();
    this._log('INFO', `Manual HTTP connect to ${baseUrl}`);
    try {
      const http = new BitosHttpCompanion(baseUrl);
      await http.connect();
      this._http = http;
      this._activeTransport = 'http';
      this._log('INFO', 'HTTP connected successfully');

      try {
        this._deviceInfo = await http.readDeviceInfo();
      } catch (_) {}

      this._emit();
      return true;
    } catch (e) {
      this._log('ERROR', `HTTP connect failed: ${e.message}`);
      this._emit();
      throw e;
    }
  }

  async _connectBLE() {
    if (!isBleAvailable()) {
      this._log('ERROR', 'BLE not available in this browser');
      throw new Error('Web Bluetooth not available');
    }
    this._log('INFO', 'Connecting via BLE...');
    try {
      const ble = new BitosCompanion();
      await ble.connect();
      this._ble = ble;
      this._activeTransport = 'ble';
      this._log('INFO', 'BLE connected');

      try {
        this._deviceInfo = await ble.readDeviceInfo();
      } catch (_) {}

      this._emit();
      return true;
    } catch (e) {
      this._log('ERROR', `BLE connect failed: ${e.message}`);
      throw e;
    }
  }

  async connectBLE() {
    return this._connectBLE();
  }

  // ── Authenticate ──

  async authenticate(pin) {
    const c = this.companion;
    if (!c) throw new Error('Not connected');
    this._log('INFO', `Authenticating via ${this._activeTransport}...`);
    await c.authenticate(pin);
    this._log('INFO', 'Authenticated');
    this._emit();
  }

  // ── Device status polling ──

  async pollStatus() {
    let status = {};

    // Try HTTP device status (provisioning server)
    if (this._http && this._http.connected) {
      try {
        const s = await this._http.readStatus();
        Object.assign(status, s);
      } catch (_) {}
    }

    // Try BLE device status
    if (this._ble && this._ble.connected) {
      try {
        const s = await this._ble.readStatus();
        Object.assign(status, s);
      } catch (_) {}
    }

    // Determine overall reachability
    const httpOk = this._http && this._http.connected;
    const bleOk = this._ble && this._ble.connected;

    if (httpOk || bleOk) {
      status._reachable = true;
      status._transport = httpOk ? 'http' : 'ble';
    } else {
      status._reachable = false;
      status._transport = null;
    }

    this._deviceStatus = status;
    this._emit();
    return status;
  }

  startPolling(intervalMs = 5000) {
    this.stopPolling();
    this.pollStatus();
    this._pollTimer = setInterval(() => this.pollStatus(), intervalMs);
  }

  stopPolling() {
    if (this._pollTimer) {
      clearInterval(this._pollTimer);
      this._pollTimer = null;
    }
  }

  // ── WiFi config ──

  async sendWifiConfig(ssid, password, security, priority) {
    const c = this.companion;
    if (!c) throw new Error('Not connected');
    this._log('INFO', `Sending WiFi config for "${ssid}" via ${this._activeTransport}`);
    const result = await c.sendWifiConfig(ssid, password, security, priority);
    this._log('INFO', 'WiFi config sent successfully');
    return result;
  }

  // ── Keyboard input ──

  async sendKeyboardInput(text) {
    const c = this.companion;
    if (!c) throw new Error('Not connected');
    await c.sendKeyboardInput(text);
  }

  // ── Disconnect ──

  disconnect() {
    this._log('INFO', 'Disconnecting...');
    if (this._ble) {
      try { this._ble.disconnect(); } catch (_) {}
      this._ble = null;
    }
    if (this._http) {
      try { this._http.disconnect(); } catch (_) {}
      this._http = null;
    }
    this._activeTransport = null;
    this.stopPolling();
    this._emit();
  }

  // ── Static helpers ──

  static get bleAvailable() {
    return isBleAvailable();
  }
}

// Singleton
const connMgr = new ConnectionManager();
