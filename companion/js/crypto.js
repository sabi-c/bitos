async function encryptWifiPassword(password, sessionToken, bleSecretHex) {
  const enc = new TextEncoder();
  const sessionBytes = enc.encode(sessionToken);
  const secretBytes = hexToBytes(bleSecretHex);
  // Combine for HKDF input keying material
  const ikm = new Uint8Array([...sessionBytes, ...secretBytes]);
  const rawKey = await crypto.subtle.importKey(
    'raw', ikm, { name: 'HKDF' }, false, ['deriveKey']);
  const aesKey = await crypto.subtle.deriveKey(
    {
      name: 'HKDF', hash: 'SHA-256',
      salt: new Uint8Array(0),
      info: enc.encode('wifi-key'),
    },
    rawKey,
    { name: 'AES-GCM', length: 128 }, false, ['encrypt']);
  const nonce = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv: nonce },
    aesKey, enc.encode(password));
  const combined = new Uint8Array([...nonce, ...new Uint8Array(ct)]);
  return btoa(String.fromCharCode(...combined));
}
