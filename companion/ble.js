class BitosCompanion {
  constructor() {
    this.device = null;
    this.server = null;
    this.sessionToken = null;
    this.chars = {
      DEVICE_INFO: null,
      KEYBOARD_INPUT: null,
    };
  }

  async connect() {
    this.device = await navigator.bluetooth.requestDevice({
      acceptAllDevices: true,
      optionalServices: [],
    });
    this.server = await this.device.gatt.connect();
    return true;
  }

  async readDeviceInfo() {
    if (!this.chars.DEVICE_INFO) {
      return { serial: 'unknown', model: 'BITOS', protocol: 'v1' };
    }
    const value = await this.chars.DEVICE_INFO.readValue();
    const text = new TextDecoder().decode(value);
    return JSON.parse(text);
  }

  async authenticate(pin) {
    if (!pin) throw new Error('PIN required');
    this.sessionToken = `demo-${Date.now()}`;
    return this.sessionToken;
  }

  async readStatus() {
    return { battery: 100, wifi: 'connected', ai: 'online' };
  }

  async sendKeyboardInput(text, target = 'any') {
    if (!this.sessionToken) throw new Error('Not authenticated');
    const payload = JSON.stringify({
      session_token: this.sessionToken,
      target,
      text,
      cursor_pos: -1,
    });
    if (this.chars.KEYBOARD_INPUT) {
      await this.chars.KEYBOARD_INPUT.writeValueWithoutResponse(
        new TextEncoder().encode(payload)
      );
      return;
    }
    console.log('[Companion][mock] KEYBOARD_INPUT', payload);
  }

  disconnect() {
    if (this.device?.gatt?.connected) this.device.gatt.disconnect();
    this.sessionToken = null;
  }
}

window.BitosCompanion = BitosCompanion;
