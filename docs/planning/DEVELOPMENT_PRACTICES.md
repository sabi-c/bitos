# BITOS · DEVELOPMENT PRACTICES
## docs/planning/DEVELOPMENT_PRACTICES.md
## v1.0 · March 2026

---

## PURPOSE

These are the engineering practices for this project. They exist
because the device will run for months unattended, Pi Zero 2W
performance is a real constraint, and multiple agents and humans
will contribute over time. The practices below prevent the most
common failure modes.

---

## 1. DEPENDENCY MANAGEMENT

### Pin everything exactly

```
# requirements.txt — CORRECT
anthropic==0.49.0
fastapi==0.115.0
pygame==2.6.1
smbus2==0.5.0

# requirements.txt — WRONG
anthropic>=0.40      # will silently upgrade and break
pygame~=2.6          # still too loose
```

Use `pip-tools` to manage this:

```bash
pip install pip-tools

# Edit requirements.in with loose constraints (human-readable intent)
# Run this to generate the locked requirements.txt:
pip-compile requirements.in --output-file requirements.txt

# To upgrade a single package safely:
pip-compile --upgrade-package anthropic requirements.in
```

The Pi will run this software for months without touching it.
A `pip install` on deploy day must produce an identical environment
to what was tested. Exact pins guarantee this.

### Separate device and server dependencies

```
requirements-device.txt   # pygame, smbus2, pyaudio, bleak, etc.
requirements-server.txt   # fastapi, anthropic, sqlalchemy, etc.
requirements-dev.txt      # pytest, pip-tools, black, mypy
```

The Mac mini never needs `smbus2`. The Pi never needs `fastapi`
to run the device client. Keep them separate.

---

## 2. PERFORMANCE — PI ZERO 2W CONSTRAINTS

The Pi Zero 2W has 512MB RAM and a 1GHz quad-core ARM Cortex-A53.
Python is slow on it. These constraints are real and must be
designed around from the start.

### Frame timing

The render loop targets 30fps (33ms per frame). Anything that takes
longer than 33ms will cause a visible stutter.

**Rule:** No database query, no file I/O, no network call in the
render loop. These run in background threads. The render loop only
reads from in-memory state.

```python
# WRONG — blocks render loop
def render(self, surface, tokens):
    tasks = self.repository.get_tasks()  # DB query in render = stutter
    self._draw_tasks(surface, tasks, tokens)

# CORRECT — background thread updates cache, render reads cache
def render(self, surface, tokens):
    self._draw_tasks(surface, self._cached_tasks, tokens)  # instant

def _refresh_tasks(self):  # called from background thread
    self._cached_tasks = self.repository.get_tasks()
```

### Instrument from day one

Add a debug overlay accessible via long-press during boot screen.
Shows real-time metrics on the device screen:

```
DEBUG OVERLAY (hidden, boot long-press)
  FRAME:  18ms  ← render time last frame
  DB:      3ms  ← last DB query time
  API:  2340ms  ← last API call latency
  RAM:   184MB  ← current memory usage
  CPU:    34%   ← CPU usage
```

Log any frame over 33ms at WARNING level:
```python
if frame_ms > 33:
    logger.warning("slow_frame", extra={"ms": frame_ms, "screen": self.active_screen_name})
```

### Font loading

Press Start 2P at multiple sizes. Pre-load all sizes at startup,
store in `tokens.py` as a fonts dict. Never call `pygame.font.Font()`
inside a render loop.

```python
# tokens.py
FONTS = {}  # populated once at startup

def load_fonts():
    path = "assets/fonts/PressStart2P.ttf"
    for name, size in [("display",22),("header",18),("body",7),
                        ("meta",6),("hint",5),("tiny",4)]:
        FONTS[name] = pygame.font.Font(path, size)
```

### Memory budget

Target peak memory under 256MB (half available RAM, leaves headroom
for OS and audio buffers).

Profile with:
```bash
python -m memory_profiler device/main.py
```

Watch for: large conversation histories loaded into memory at once,
Pygame surfaces that aren't freed, audio buffers accumulating.

---

## 3. STRUCTURED LOGGING

Never use `print()`. Use Python's `logging` module configured to
output JSON lines. Every log entry is machine-readable and can be
searched remotely.

```python
# server/config.py and device/main.py — logging setup
import logging, json

class JsonFormatter(logging.Formatter):
    def format(self, record):
        obj = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%SZ"),
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }
        if hasattr(record, "__dict__"):
            obj.update({k: v for k, v in record.__dict__.items()
                       if k not in logging.LogRecord.__dict__})
        return json.dumps(obj)

handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.root.addHandler(handler)
logging.root.setLevel(logging.INFO)
```

Usage:
```python
logger = logging.getLogger(__name__)

# Simple
logger.info("chat.response_complete")

# With structured fields
logger.info("chat.response", extra={
    "tokens": 847,
    "latency_ms": 2340,
    "session_id": session_id,
    "model": "claude-sonnet-4-6"
})

# Performance warning
logger.warning("slow_frame", extra={"ms": frame_ms})

# Security event
logger.warning("auth.failed", extra={
    "attempts": attempt_count,
    "ip": client_ip
})
```

Remote log streaming:
```bash
ssh pi@bitos "tail -f /var/log/bitos/app.log | jq ."
```

---

## 4. DATABASE PRACTICES

### Migration runner must be tested

The schema migration pattern (version table + guards) is in
`DeviceRepository`. Every migration must have a test:

```python
def test_migration_v1_to_v2_preserves_data():
    """Prove a real migration doesn't destroy existing records."""
    db = DeviceRepository(":memory:")
    db._apply_schema_v1()  # start at old version
    
    # Insert data in old schema
    db.execute("INSERT INTO sessions VALUES ('id1', 'title1', ...)")
    
    # Apply migration
    db._migrate_to_v2()
    
    # Data must survive
    row = db.execute("SELECT * FROM sessions WHERE id='id1'").fetchone()
    assert row is not None
    assert row["title"] == "title1"
```

### Never modify production data in migrations

Migrations add columns (with DEFAULT), add tables, add indexes.
They never UPDATE or DELETE existing rows. If data transformation
is needed, do it in application code after the migration, with
explicit error handling.

### SQLite settings for Pi

```python
# Apply on every connection
connection.execute("PRAGMA journal_mode=WAL")      # better concurrent reads
connection.execute("PRAGMA synchronous=NORMAL")    # faster writes, safe
connection.execute("PRAGMA cache_size=-16000")     # 16MB cache in RAM
connection.execute("PRAGMA temp_store=MEMORY")     # temp tables in RAM
connection.execute("PRAGMA mmap_size=134217728")   # 128MB memory-mapped I/O
```

---

## 5. TESTING PRACTICES

### Test naming convention

```
test_{module}_{behavior}_{condition}.py

# Examples:
test_notification_queue_fires_toast_on_push
test_settings_toggle_persists_to_repository
test_chat_panel_shows_offline_banner_when_health_fails
test_migration_v2_preserves_existing_sessions
```

### What to test (and what not to)

**Always test:**
- Business logic (input handling, state transitions)
- Data persistence (write + read back from DB)
- Error states (what happens when backend is down)
- Permission gates (tier-2 actions require confirmation)
- Migration correctness (old data survives schema changes)

**Don't bother testing:**
- Pygame rendering output (too brittle, too slow)
- Exact pixel positions
- Font rendering
- Network timeouts (mock the client instead)

### Mock the hardware

```python
# conftest.py
@pytest.fixture
def mock_api(mocker):
    """Use this instead of making real API calls in tests."""
    return mocker.patch("device.client.api.BackendClient.health",
                        return_value=True)

@pytest.fixture  
def mock_repository(tmp_path):
    """In-memory DB for fast, isolated tests."""
    return DeviceRepository(str(tmp_path / "test.db"))
```

### CI discipline

All tests must pass before any task is marked done.
The test suite must run in under 30 seconds (target: under 10s).
If a test is slow, it's probably doing real I/O — mock it.

---

## 6. ENVIRONMENT TARGETS

Three environments, each with a clear contract:

```
DESKTOP (Mac)
  BITOS_DISPLAY=pygame
  BITOS_AUDIO=mock        # no WM8960
  BITOS_BUTTON=keyboard   # space/enter/backspace
  Database: ~/.bitos/dev.db
  Backend: localhost:8000
  Use for: all development, all testing

PI-DEV (Pi, development build)
  BITOS_DISPLAY=st7789    # real display
  BITOS_AUDIO=hw:0        # real WM8960
  BITOS_BUTTON=gpio       # real button
  Database: ~/bitos/dev.db
  Backend: mac-mini.local:8000 or tailscale address
  Use for: hardware testing, display driver verification

PI-PROD (Pi, production)
  BITOS_DISPLAY=st7789
  BITOS_AUDIO=hw:0
  BITOS_BUTTON=gpio
  Database: /home/pi/bitos/bitos.db
  Backend: localhost:8000  (server runs on Mac mini, Pi tunnels via Tailscale)
  Use for: daily use
```

The display driver, audio pipeline, and button handler all check
`BITOS_DISPLAY`, `BITOS_AUDIO`, `BITOS_BUTTON` env vars and
instantiate the appropriate implementation. No `if platform ==`
checks scattered through business logic.

---

## 7. DEPLOY PROCESS

```bash
# From Mac, push new device code to Pi
make deploy-device
# Runs: rsync -av device/ pi@bitos:~/bitos/device/ --exclude __pycache__

# Restart the service
make restart
# Runs: ssh pi@bitos "sudo systemctl restart bitos"

# Stream logs after deploy
make logs
# Runs: ssh pi@bitos "journalctl -u bitos -f"

# Full deploy + restart + logs in one command
make ship
```

The Makefile is the single source of truth for operational commands.
Never SSH in and run commands by hand — always via make targets so
the process is documented and repeatable.

---

## 8. DEPENDENCY SECURITY SCANNING

Run weekly (or before any deploy after a dependency update):

```bash
pip install pip-audit
pip-audit -r requirements-device.txt
pip-audit -r requirements-server.txt
```

Any HIGH or CRITICAL CVE blocks the deploy until resolved.
MEDIUM CVEs get a 7-day remediation window.

---

## 9. WHAT TO DO WHEN THE PI CRASHES

The hardware watchdog (configured in SD-series tasks) will
auto-reboot after 15 seconds. After reboot:

1. Check `/var/log/bitos/app.log` for the last entries before crash
2. Check `journalctl -u bitos --since "1 hour ago"` for systemd logs
3. Check `dmesg | tail -50` for kernel-level issues (SD card errors,
   memory issues)
4. If SD card errors: replace card, restore from backup
5. If OOM: check what was in memory at crash time via logs, add limits

```bash
# Set memory limit on the bitos service to prevent OOM killing other processes
# /etc/systemd/system/bitos.service
[Service]
MemoryMax=300M
MemorySwapMax=0
```

---

## 10. BACKUP STRATEGY

```bash
# On Pi: nightly backup of the conversation DB to Mac mini
# /etc/cron.d/bitos-backup
0 3 * * * pi rsync -az /home/pi/bitos/server/bitos.db \
    mac-mini.local:/backups/bitos/bitos-$(date +\%Y\%m\%d).db

# Keep 30 days of backups
find /backups/bitos/ -name "*.db" -mtime +30 -delete
```

Never restore a backup to a running device — stop the service first,
restore, verify schema version matches, then restart.
