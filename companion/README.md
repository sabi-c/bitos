# BITOS Companion PWA

Hosted at: https://bitos-companion.onrender.com
(or GitHub Pages — see deployment notes)

## Local dev
cd companion && python3 -m http.server 8080
Open Chrome: http://localhost:8080/setup.html?ble=TEST

## Deploy to Render
New Static Site → root: companion → no build command

## Platform notes
- iPhone: Safari ONLY (enable Web Bluetooth in Experimental Features)
- Android: Chrome works out of the box
- Mac: Chrome works (for testing)
