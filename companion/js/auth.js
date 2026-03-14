async function deriveBleSecret(pin, serial) {
  const enc = new TextEncoder();
  const keyMat = await crypto.subtle.importKey(
    'raw', enc.encode(pin),
    { name: 'PBKDF2' }, false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits(
    {
      name: 'PBKDF2', hash: 'SHA-256',
      salt: enc.encode(serial), iterations: 100000,
    },
    keyMat, 256);
  return bytesToHex(new Uint8Array(bits));
}

async function computeHMAC(bleSecretHex, nonceHex, timestamp) {
  const key = await crypto.subtle.importKey(
    'raw', hexToBytes(bleSecretHex),
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign']);
  const nonceBytes = hexToBytes(nonceHex);
  const tsBytes = new Uint8Array(8);
  const view = new DataView(tsBytes.buffer);
  // timestamp is seconds (int), store as big-endian 64-bit
  view.setBigUint64(0, BigInt(Math.floor(timestamp)), false);
  const data = new Uint8Array([...nonceBytes, ...tsBytes]);
  const sig = await crypto.subtle.sign('HMAC', key, data);
  return bytesToHex(new Uint8Array(sig));
}

function hexToBytes(hex) {
  const arr = new Uint8Array(hex.length / 2);
  for (let i = 0; i < arr.length; i++) {
    arr[i] = parseInt(hex.substr(i * 2, 2), 16);
  }
  return arr;
}

function bytesToHex(bytes) {
  return Array.from(bytes).map((b) =>
    b.toString(16).padStart(2, '0')).join('');
}
