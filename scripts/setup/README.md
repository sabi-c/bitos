# BITOS Pi Setup

Run these scripts IN ORDER on a fresh Pi OS Lite (64-bit) install.
Each script is idempotent — safe to re-run.

## Prerequisites
- Pi Zero 2W with Whisplay HAT + PiSugar 3
- Pi OS Lite 64-bit (Bookworm)
- SSH access from Mac
- Python 3.11+

## Sequence

0. Clone the repo:
   git clone https://github.com/[you]/bitos ~/bitos
   cd ~/bitos && pip install -r requirements-device.txt --break-system-packages

1. bash scripts/setup/01_tailscale.sh
   → Authorize in Tailscale admin panel

2. bash scripts/setup/02_security.sh
   → Copies your SSH public key first:
      ssh-copy-id pi@[pi-ip]  (do this from Mac before running)

3. bash scripts/setup/02b_secrets.sh
   → Edit /etc/bitos/secrets with real values

4. bash scripts/setup/03_resilience.sh
   → Reboot after this step: sudo reboot

5. bash scripts/setup/04_bitos_service.sh
   → sudo systemctl start bitos
   → sudo systemctl status bitos

## Verify everything works

From your Mac:
  ssh pi@bitos                    # Tailscale SSH
  make logs                       # stream device logs
  make db-web                     # browse conversation DB
  curl http://bitos:8000/health   # check backend
