/**
 * BITOS Companion — Connection Layer
 *
 * Supports two transports:
 *   1. BLE (Web Bluetooth) — primary, for Chrome/Android/desktop
 *   2. HTTP — WiFi fallback for iOS and browsers without Web Bluetooth
 *
 * Both transports expose the same public API so the UI code is transport-agnostic.
 */

const BITOS_SERVICE = 'b1705000-0000-4000-8000-000000000001';
const CHARS = {
  AUTH_CHALLENGE: 'b1705000-0001-4000-8000-000000000001',
  AUTH_RESPONSE: 'b1705000-0002-4000-8000-000000000001',
  WIFI_CONFIG: 'b1705000-0010-4000-8000-000000000001',
  WIFI_STATUS: 'b1705000-0011-4000-8000-000000000001',
  DEVICE_STATUS: 'b1705000-0030-4000-8000-000000000001',
  DEVICE_INFO: 'b1705000-0099-4000-8000-000000000001',
  KEYBOARD_INPUT: 'b1705000-0020-4000-8000-000000000001',
};

// ── Helpers ──

function isBleAvailable() {
  return typeof navigator !== 'undefined' && !!navigator.bluetooth;
}

// ── BLE Transport (original) ──

class BitosCompanion {
  constructor() {
    this.device = null;
    this.server = null;
    this.service = null;
    this.chars = {};
    this.sessionToken = null;
    this._serial = null;
    this.transport = 'ble';
  }

  get connected() {
    return !!(this.device && this.device.gatt && this.device.gatt.connected);
  }

  async connect(bleAddr) {
    if (!navigator.bluetooth) {
      throw new Error('Web Bluetooth not available. Use Chrome or Safari (iOS 16.4+).');
    }
    if (this.device && this.device.gatt && this.device.gatt.connected) {
      console.warn('[BLE] Already connected, skipping re-connect');
      return;
    }
    this.device = await navigator.bluetooth.requestDevice({
      filters: [{ services: [BITOS_SERVICE] }],
      optionalServices: [BITOS_SERVICE],
    });
    this.device.addEventListener('gattserverdisconnected',
      () => { this.sessionToken = null; this.chars = {}; });
    this.server = await this.device.gatt.connect();
    this.service = await this.server.getPrimaryService(BITOS_SERVICE);
    for (const [name, uuid] of Object.entries(CHARS)) {
      try {
        this.chars[name] = await this.service.getCharacteristic(uuid);
      } catch (_) {}
    }
    // Read device serial for key derivation
    if (this.chars.DEVICE_INFO) {
      try {
        const raw = await this.chars.DEVICE_INFO.readValue();
        const info = JSON.parse(new TextDecoder().decode(raw));
        this._serial = info.serial;
      } catch (_) {}
    }
  }

  async authenticate(pin) {
    if (!this.chars.AUTH_CHALLENGE) throw new Error('Not connected');
    const raw = await this.chars.AUTH_CHALLENGE.readValue();
    const challenge = JSON.parse(new TextDecoder().decode(raw));
    const serial = this._serial || 'DESKTOP-DEV-001';
    const bleSecret = await deriveBleSecret(pin, serial);
    // Store for WiFi encryption
    this._bleSecret = bleSecret;
    const hmac = await computeHMAC(bleSecret, challenge.nonce, challenge.timestamp);
    const authPayload = { response: hmac, nonce: challenge.nonce };
    // Include ephemeral pairing credentials if present (v2 QR flow)
    if (this._pairingSession && this._pairingToken) {
      authPayload.pairing_session = this._pairingSession;
      authPayload.pairing_token = this._pairingToken;
    }
    const payload = JSON.stringify(authPayload);
    await this.chars.AUTH_RESPONSE.writeValue(
      new TextEncoder().encode(payload));
    const resp = await this.chars.AUTH_RESPONSE.readValue();
    const result = JSON.parse(new TextDecoder().decode(resp));
    if (result.error) throw new Error(result.error);
    this.sessionToken = result.session_token;
    // Persist secret for this session
    sessionStorage.setItem('bitos_ble_secret', bleSecret);
    sessionStorage.setItem('bitos_session', this.sessionToken);
  }

  async readDeviceInfo() {
    if (!this.chars.DEVICE_INFO) throw new Error('Not connected');
    const raw = await this.chars.DEVICE_INFO.readValue();
    return JSON.parse(new TextDecoder().decode(raw));
  }

  async readStatus() {
    if (!this.chars.DEVICE_STATUS) throw new Error('Not connected');
    const raw = await this.chars.DEVICE_STATUS.readValue();
    return JSON.parse(new TextDecoder().decode(raw));
  }

  async sendKeyboardInput(text) {
    if (!this.sessionToken) throw new Error('Not authenticated');
    if (!this.chars.KEYBOARD_INPUT) throw new Error('Not connected');
    const payload = JSON.stringify({
      session_token: this.sessionToken,
      text: text,
      target: 'any',
    });
    await this.chars.KEYBOARD_INPUT.writeValue(
      new TextEncoder().encode(payload));
  }

  disconnect() {
    if (this.device && this.device.gatt.connected) {
      this.device.gatt.disconnect();
    }
    this.sessionToken = null;
    this.chars = {};
  }

  async sendWifiConfig(ssid, password, security = 'WPA2', priority = 100) {
    if (!this.sessionToken) throw new Error('Not authenticated');
    if (!this.chars.WIFI_CONFIG || !this.chars.WIFI_STATUS) {
      throw new Error('WiFi characteristics unavailable');
    }
    const bleSecret = this._bleSecret ||
      sessionStorage.getItem('bitos_ble_secret');
    const encPw = await encryptWifiPassword(password, this.sessionToken, bleSecret);
    const payload = JSON.stringify({
      session_token: this.sessionToken,
      ssid, password: encPw, security, priority,
    });
    await this.chars.WIFI_CONFIG.writeValueWithoutResponse(
      new TextEncoder().encode(payload));

    // Poll for status instead of relying on notifications.
    for (let i = 0; i < 15; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const raw = await this.chars.WIFI_STATUS.readValue();
      const s = JSON.parse(new TextDecoder().decode(raw));
      if (s.connected) return s;
      if (s.last_error) throw new Error(s.last_error);
    }
    throw new Error('Timeout \u2014 device did not confirm WiFi');
  }
}

// ── HTTP Transport (WiFi fallback) ──

class BitosHttpCompanion {
  constructor(baseUrl) {
    this.baseUrl = (baseUrl || '').replace(/\/+$/, '');
    this.sessionToken = null;
    this._serial = null;
    this._bleSecret = null;
    this._connected = false;
    this.transport = 'http';

    // Pairing credentials (set externally like BLE companion)
    this._pairingSession = null;
    this._pairingToken = null;
  }

  get connected() {
    return this._connected;
  }

  async _fetch(path, opts = {}) {
    const url = this.baseUrl + path;
    const resp = await fetch(url, {
      signal: AbortSignal.timeout(5000),
      ...opts,
      headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    });
    return resp;
  }

  async connect() {
    // Verify the device is reachable over HTTP
    const resp = await this._fetch('/api/health');
    if (!resp.ok) throw new Error('Device not reachable at ' + this.baseUrl);
    this._connected = true;

    // Read device serial
    try {
      const info = await this.readDeviceInfo();
      this._serial = info.serial;
    } catch (_) {}
  }

  async authenticate(pin) {
    if (!this._connected) throw new Error('Not connected');

    // Step 1: Get challenge
    const challengeResp = await this._fetch('/api/ble/challenge');
    if (!challengeResp.ok) throw new Error('Failed to get challenge');
    const challenge = await challengeResp.json();

    // Step 2: Compute HMAC
    const serial = this._serial || 'DESKTOP-DEV-001';
    const bleSecret = await deriveBleSecret(pin, serial);
    this._bleSecret = bleSecret;
    const hmac = await computeHMAC(bleSecret, challenge.nonce, challenge.timestamp);

    // Step 3: Send auth response
    const authPayload = { response: hmac, nonce: challenge.nonce };
    if (this._pairingSession && this._pairingToken) {
      authPayload.pairing_session = this._pairingSession;
      authPayload.pairing_token = this._pairingToken;
    }
    const authResp = await this._fetch('/api/ble/auth', {
      method: 'POST',
      body: JSON.stringify(authPayload),
    });
    const result = await authResp.json();
    if (result.error) throw new Error(result.error);
    this.sessionToken = result.session_token;

    sessionStorage.setItem('bitos_ble_secret', bleSecret);
    sessionStorage.setItem('bitos_session', this.sessionToken);
  }

  async readDeviceInfo() {
    const resp = await this._fetch('/api/device/info');
    if (!resp.ok) throw new Error('Failed to read device info');
    return resp.json();
  }

  async readStatus() {
    const resp = await this._fetch('/api/device/status');
    if (!resp.ok) throw new Error('Failed to read device status');
    return resp.json();
  }

  async sendKeyboardInput(text) {
    if (!this.sessionToken) throw new Error('Not authenticated');
    const resp = await this._fetch('/api/keyboard/input', {
      method: 'POST',
      body: JSON.stringify({
        session_token: this.sessionToken,
        text: text,
        target: 'any',
      }),
    });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error || 'Keyboard input failed');
    }
  }

  disconnect() {
    this._connected = false;
    this.sessionToken = null;
  }

  async sendWifiConfig(ssid, password, security = 'WPA2', priority = 100) {
    if (!this.sessionToken) throw new Error('Not authenticated');
    const bleSecret = this._bleSecret ||
      sessionStorage.getItem('bitos_ble_secret');
    const encPw = await encryptWifiPassword(password, this.sessionToken, bleSecret);

    const resp = await this._fetch('/api/wifi/config', {
      method: 'POST',
      body: JSON.stringify({
        session_token: this.sessionToken,
        ssid, password: encPw, security, priority,
      }),
    });
    const result = await resp.json();
    if (result.error) throw new Error(result.error);

    // Poll for WiFi status
    for (let i = 0; i < 15; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      const statusResp = await this._fetch('/api/wifi/status');
      if (statusResp.ok) {
        const s = await statusResp.json();
        if (s.connected) return s;
        if (s.last_error) throw new Error(s.last_error);
      }
    }
    throw new Error('Timeout \u2014 device did not confirm WiFi');
  }
}
