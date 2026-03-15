# BITOS Companion PWA

Hosted at: https://bitos-companion.onrender.com
(or GitHub Pages — see deployment notes)

## Source of truth files
- Real BLE implementation: `companion/js/ble.js`
- Real auth implementation: `companion/js/auth.js`
- Real crypto helpers: `companion/js/crypto.js`
- Legacy mock stub (kept for compatibility): `companion/ble.js`

## Local testing
1. Start a static server from the repository root:
   - `python3 -m http.server 8080 --directory companion`
2. Open companion pages in browser:
   - Pairing flow: `http://localhost:8080/pair.html`
   - Setup flow: `http://localhost:8080/setup.html`
   - Crypto vector check: `http://localhost:8080/test_crypto.html`

## Server override
You can pass the backend server from the launcher/URL:
- `settings.html?server=http://192.168.x.x:8000`

## Platform notes
- iPhone/iOS: Safari only, with Web Bluetooth Experimental Features enabled.
- Android: Chrome works out of the box.
- Mac: Chrome works for testing.

## Deploy to Render
New Static Site → root: companion → no build command
