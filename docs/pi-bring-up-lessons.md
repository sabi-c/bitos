# Pi Zero 2W Bring-Up: Lessons Learned

Everything that went wrong during day-one device bring-up (2026-03-17/18) and how to prevent it.

## Boot Crash #1: Read-Only Filesystem

**Symptom**: `OSError: [Errno 30] Read-only file system: '/var/log/bitos/device.log'`

**Root cause**: `log2ram` makes `/var/log` read-only on boot. `os.makedirs(exist_ok=True)` succeeds because the dir already exists, but file creation fails.

**Fix** (`device/main.py`):
```python
# Test that we can actually WRITE, not just that the dir exists
test_file = os.path.join(log_dir, ".write_test")
open(test_file, "w").close()
os.remove(test_file)
```

**Prevention**: Always test write access, never trust `makedirs` success.

## Boot Crash #2: systemd NAMESPACE Error

**Symptom**: `Failed to set up mount namespacing: /var/log/bitos: No such file or directory`

**Root cause**: `ReadWritePaths=/var/log/bitos` in the service file, but the directory doesn't exist yet. systemd can't mount a non-existent path.

**Fix**: Create the dir in install script AND in ExecStartPre:
```bash
sudo mkdir -p /var/log/bitos
```

**Prevention**: Every path in `ReadWritePaths` must exist before the service starts. Add to install script.

## Boot Crash #3: SDL Video Driver

**Symptom**: `pygame.error: video system not initialized`

**Root cause**: `SDL_VIDEODRIVER=fbcon` but Pi Zero 2W has no framebuffer — the ST7789 display is SPI-only, not a Linux framebuffer device.

**Fix**: `SDL_VIDEODRIVER=dummy` in the service file.

**Prevention**: Pi + SPI display = always use `dummy` SDL driver.

## Boot Crash #4: GPIO Edge Detection

**Symptom**: `RuntimeError` from `GPIO.add_event_detect()` during WhisPlayBoard init.

**Root cause**: GPIO pin 11 (button) may have a stale event callback from a previous crash, or the pin is already in use.

**Fix** (`device/hardware/whisplay_board.py`):
```python
try:
    _instance = WhisPlayBoard()
except RuntimeError as gpio_err:
    if "edge detection" in str(gpio_err).lower():
        GPIO.add_event_detect = lambda *a, **k: None  # monkey-patch
        _instance = WhisPlayBoard()
```

**Prevention**: Always handle GPIO init failures gracefully. The display works even if the button doesn't.

## Bluetooth: No Audio Profiles

**Symptom**: `br-connection-profile-unavailable` — AirPods connect at L2CAP but refuse A2DP.

**Root cause**: WirePlumber's bluez5 SPA monitor never started. On headless Pi, logind reports seat state as `"online"` not `"active"`. The `bluez.lua` script only creates the monitor when seat is `"active"`.

**Fix** (`~/.config/wireplumber/wireplumber.conf.d/bluetooth.conf`):
```
wireplumber.profiles = {
  main = { monitor.bluez.seat-monitoring = disabled }
}
```

**Prevention**: Always disable seat-monitoring for headless deployments.

## Bluetooth: Bond Not Stored

**Symptom**: Pairing succeeds (`Paired: yes`) then immediately drops (`Paired: no, Bonded: no`). No `[LinkKey]` section in BlueZ device info file.

**Root cause**: `bondable` flag not set on the HCI controller. `btmgmt info` showed `bondable` in supported but NOT in current settings.

**Fix** (`/etc/bluetooth/main.conf`):
```ini
[General]
Bondable = true
```

**Prevention**: Always set `Bondable = true` in BlueZ config.

## Bluetooth: AirPods Not Found by Scan

**Symptom**: `bluetoothctl scan on` finds random BLE devices but not AirPods.

**Root cause**: `bluetoothctl scan on` defaults to LE-only scan on Pi. AirPods use BR/EDR classic Bluetooth for audio.

**Fix**: Use `hcitool inq` for BR/EDR classic device discovery:
```bash
sudo hcitool inq --length=8
```

**Prevention**: Always use `hcitool inq` for audio device discovery, not `bluetoothctl scan`.

## Bluetooth: rfkill Blocking

**Symptom**: BT adapter powered off, `rfkill list` shows bluetooth soft-blocked.

**Root cause**: `PowerManager.system_power_save()` ran `rfkill block bluetooth` on boot.

**Fix**: Removed from `device/power/manager.py`.

**Prevention**: Never rfkill block bluetooth if BT audio is needed.

## USB Gadget: Mac Internet Lost

**Symptom**: Mac can't reach internet when Pi is connected via USB.

**Root cause**: Mac's default gateway routes through `en9` (USB gadget) instead of WiFi router.

**Fix**:
```bash
sudo route delete default
sudo route add default <router_ip>
```

**Prevention**: Use WiFi (`192.168.254.200`) as primary Pi access, USB gadget as fallback only.

---

## Day-One Install Script Improvements

The install script (`scripts/install.sh`) should do ALL of the following in one pass:

### Pre-flight
1. Enable I2C and SPI: `sudo raspi-config nonint do_i2c 0 && do_spi 0`
2. Create ALL runtime dirs: `/var/log/bitos`, `device/data`, `device/logs`, `server/data`
3. Set correct permissions: `chown pi:pi` on runtime dirs

### Audio
4. Install WM8960 driver: `cd /home/pi/Whisplay/Driver && sudo bash install_wm8960_drive.sh`
5. Verify ALSA devices exist: `aplay -l | grep wm8960`

### Bluetooth
6. Run `scripts/setup/fix_bt_airpods.sh` — sets up BlueZ config, WirePlumber, PipeWire
7. Enable `loginctl enable-linger` for headless PipeWire
8. Install `expect` and `python3-dbus python3-gi` for pairing automation

### Service Files
9. Copy service files with correct `SDL_VIDEODRIVER=dummy`
10. Ensure `ReadWritePaths` dirs all exist before enabling services
11. Enable and start services: `bitos-server`, `bitos-device`, `bitos-bt-reconnect`

### Secrets
12. Run `scripts/setup/02b_secrets.sh` with `chmod 644` (not 600)
13. Remind user to set real `ANTHROPIC_API_KEY`

### Validation
14. `curl localhost:8000/health` — server is up
15. `sudo systemctl status bitos-device` — no NAMESPACE/crash errors
16. `wpctl status | grep bluez` — BT audio stack ready
17. `bluetoothctl show | grep Bondable` — should say "yes"
