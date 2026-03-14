# BITOS Quick Commands

## From your Mac

### First setup
make flash        prepare SD card cloud-init on macOS

## After first boot

### Daily use
make status       check if services running
make logs         live log stream (Ctrl+C to stop)
make restart      restart everything cleanly

### Development
make deploy       push code changes to Pi
make ship         deploy + restart + logs
make ssh          open SSH session

### Hardware
make verify-hw    run hardware check on Pi
make logs-device  device-only logs
make logs-server  server-only logs

### If things go wrong
ssh pi@bitos
sudo systemctl status bitos-device
journalctl -u bitos-device -n 100 --no-pager

## On the device (SSH)

bash scripts/day_one.sh      # first boot setup
bash scripts/setup/check_secrets.sh  # verify API key set
python scripts/verify_hardware.py    # hardware check
python scripts/smoke_test.py         # end-to-end check

## Button gestures
SHORT PRESS    scroll / advance
LONG PRESS     select / send / hold to speak
DOUBLE PRESS   back
TRIPLE PRESS   quick capture
5x PRESS       power menu (shutdown/reboot)
