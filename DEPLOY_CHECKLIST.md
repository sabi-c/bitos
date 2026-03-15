## Pre-deploy (from Mac)
make deploy  (or: git push origin main)

## On Pi via SSH
cd ~/bitos
git pull origin main
bash scripts/setup/02b_secrets.sh
sudo cp docs/pi_config/bitos-device.service /etc/systemd/system/bitos-device.service
sudo systemctl daemon-reload
sudo systemctl restart bitos-server
sleep 5
sudo systemctl restart bitos-device
sleep 10
systemctl is-active bitos-device
journalctl -u bitos-device -n 30 --no-pager

## Expected healthy boot log lines (in order):
1. "piper not available — TTS disabled" (WARNING — expected, not a failure)
2. "[BITOS] Starting device..."
3. "pisugar safe shutdown configured"
4. "audio_input_device=0 name=wm8960-soundcard"
5. "button_init ... on_pi=True ... board=<WhisPlay"
6. "[BITOS] Backend connected ✓"
7. "[BLE] BLE service starting"
8. "CPU:XX% RAM:XXX MB" (system monitor — confirms main loop is running)

## Confirm display is working:
- Boot animation (orbs rotating around BITOS text) shows for ~8 seconds
- Lock screen appears with clock and "PRESS TO UNLOCK"
- Single button press advances to home menu
- Home menu shows: CHAT, FOCUS, TASKS, CAPTURES, MESSAGES, MAIL, NOTIFS, SETTINGS
