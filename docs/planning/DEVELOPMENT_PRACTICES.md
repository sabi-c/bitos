# BITOS · DEVELOPMENT PRACTICES

## 1. Dependency Management
- Pin every package exactly: anthropic==0.49.0 not anthropic>=0.40
- Use pip-tools: requirements.in (loose) → requirements.txt (locked)
- Three separate files: requirements-device.txt / requirements-server.txt / requirements-dev.txt
- Upgrade single package: pip-compile --upgrade-package anthropic requirements.in
- Weekly security scan: pip-audit -r requirements-device.txt

## 2. Performance (Pi Zero 2W: 512MB RAM, 1GHz ARM)
- Rule: NO database queries, file I/O, or network calls in render loop
- Background threads update in-memory cache. Render loop reads cache only.
- Target: 30fps = 33ms per frame. Log any frame >33ms at WARNING level.
- Pre-load all Press Start 2P font sizes at startup in tokens.FONTS dict.
  Never call pygame.font.Font() in a render method.
- RAM budget: peak under 256MB. Profile with memory_profiler.
- Debug overlay (long press during boot): shows frame_ms, db_ms, api_ms,
  RAM usage, CPU%. Add to device/screens/debug_overlay.py.

## 3. Structured Logging
- Never use print(). Use logging module with JSON formatter.
- JsonFormatter outputs: ts, level, module, msg + any extra fields.
- Usage: logger.info("chat.response", extra={"tokens": 847, "ms": 2340})
- Remote streaming: ssh pi@bitos "tail -f /var/log/bitos/app.log | jq ."
- Log levels: DEBUG=dev noise, INFO=normal ops, WARNING=perf/recoverable,
  ERROR=failures, CRITICAL=service-threatening.

## 4. Database Practices
- Test every migration: write a test that starts at schema vN, inserts data,
  migrates to vN+1, and asserts data survives.
- Migrations: ADD COLUMN (with DEFAULT) and ADD TABLE only.
  Never UPDATE/DELETE rows in a migration.
- SQLite pragmas on every connection: WAL mode, NORMAL sync, 16MB cache,
  temp_store=MEMORY, mmap_size=128MB.
- DB file permissions: 600, owner pi:pi.

## 5. Testing Practices
Always test: business logic, data persistence (write+read back),
error states, permission gates, migration correctness.
Don't test: pygame rendering output, exact pixel positions,
font rendering, real network timeouts (mock the client).
Mock hardware: BITOS_DISPLAY=mock, BITOS_AUDIO=mock, BITOS_WIFI=mock.
Use tmp_path fixtures for isolated DB instances.
Suite must run in under 30 seconds.

## 6. Environment Targets
DESKTOP: BITOS_DISPLAY=pygame, BITOS_AUDIO=mock, BITOS_BUTTON=keyboard
  Use for: all development and testing.
PI-DEV:  BITOS_DISPLAY=st7789, BITOS_AUDIO=hw:0, BITOS_BUTTON=gpio
  Use for: hardware verification, display driver testing.
PI-PROD: BITOS_DISPLAY=st7789, BITOS_AUDIO=hw:0, BITOS_BUTTON=gpio
  Use for: daily use.
All three read env vars. No if platform == checks in business logic.

## 7. Deploy Process
Makefile is the single source of truth. Never SSH and run commands manually.
  make push    — rsync device/ and server/ to Pi
  make deploy  — push + restart service
  make ship    — push + deploy + stream logs
  make logs    — tail journalctl for bitos service
  make db-web  — start sqlite-web on Pi at port 8080

## 8. SD Card Protection
tmpfs for /tmp and /var/tmp (in /etc/fstab).
log2ram for /var/log (periodic flush, not constant write).
Hardware watchdog: dtparam=watchdog=on, RuntimeWatchdogSec=15.
Service: MemoryMax=300M, MemorySwapMax=0.

## 9. Crash Recovery
1. Watchdog auto-reboots after 15s hang.
2. After reboot: check journalctl -u bitos --since "1 hour ago"
3. Check dmesg | tail -50 for SD card errors.
4. SD card errors: replace card, restore from nightly backup.
5. OOM: MemoryMax in service file prevents killing other processes.

## 10. Backup Strategy
Nightly cron on Pi: rsync bitos.db to Mac mini via Tailscale.
Retention: 30 days. Before restore: stop service, verify schema version,
restore, restart.
