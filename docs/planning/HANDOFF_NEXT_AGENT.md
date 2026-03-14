# BITOS Handoff Notes (Next Agent)

## What was built
Full pre-hardware sprint complete. All Phase 4-6 core features shipped and tested. CI green. Device arrives today.

## Hardware bring-up sequence
1. Flash SD (Pi OS Lite 64-bit, Pi Imager)
2. `cp scripts/cloud-init/user-data /Volumes/bootfs/user-data`
3. Power on, wait 15 min
4. `ssh pi@bitos`
5. `python scripts/verify_hardware.py`
6. `sudo nano /etc/bitos/secrets` → add `ANTHROPIC_API_KEY`
7. `sudo systemctl start bitos`
8. Hold button, speak, hear response

## If something breaks
- Display blank: `sudo raspi-config nonint do_spi 0 && sudo reboot`
- No audio: `cd ~/whisplay && sudo bash install.sh`
- Button dead: check `GPIO.BOARD` pin 11 reads 0 when pressed
- Claude offline: check `/etc/bitos/secrets` has valid API key

## After hardware confirmed working
Next priorities:
1. UI spec gaps (see `docs/reports/UI_SPEC_GAPS.md`)
   Use Claude Code for surgical screen-by-screen fixes
2. P5-012f — deploy companion to custom domain
3. P7-001 — Piper TTS offline fallback
4. P8-001 — Global workspace (makes Claude feel like it knows you)
