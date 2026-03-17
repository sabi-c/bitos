"""Agent Heartbeat — persistent background loop for proactive agent behaviors.

Runs on the Mac mini server. Devices are just frontends that receive
proactive messages via WebSocket.

Background loop (default 60s tick) checks scheduled actions stored in SQLite:
  - morning_briefing (8:00 AM) — calendar, tasks, unread messages
  - evening_winddown (9:00 PM) — day summary, tomorrow's first event
  - idle_checkin — gentle nudge after 2+ hours of silence (waking hours only)
  - task_reminders — overdue task reminders every 4 hours

Module-level API:
  start_heartbeat(app)   — call from main.py on startup
  stop_heartbeat()       — graceful shutdown
  get_heartbeat_status() — dict with last tick, next actions, etc.
  trigger_action(type)   — manually fire an action (for /heartbeat/trigger)
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import subprocess
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).resolve().parent / "data"
DB_PATH = DATA_DIR / "heartbeat.db"

DEFAULT_TICK_INTERVAL = 60  # seconds
DEFAULT_TIMEZONE = "America/Los_Angeles"
ACTIVE_HOURS_START = 8   # 8 AM
ACTIVE_HOURS_END = 22    # 10 PM
IDLE_THRESHOLD_SECONDS = 2 * 60 * 60  # 2 hours
TASK_REMINDER_INTERVAL = 4 * 60 * 60  # 4 hours
PROACTIVE_COOLDOWN_SECONDS = 15 * 60  # 15 min between proactive messages
HAIKU_MODEL = "claude-haiku-4-5-20251001"

HEARTBEAT_SYSTEM_PROMPT = (
    "You are BITOS, a pocket AI companion running on a small hardware device. "
    "Generate concise proactive messages — you're rendering on a 240x280 pixel screen. "
    "Be direct, warm, and useful. No corporate speak. Keep it to 2-3 sentences max."
)

# ── WebSocket Client Registry ─────────────────────────────────────────────

_proactive_clients: set[Any] = set()


def register_proactive_ws(ws: Any) -> None:
    """Register a WebSocket connection to receive proactive messages."""
    _proactive_clients.add(ws)
    logger.info("proactive_ws_registered: %d total", len(_proactive_clients))


def unregister_proactive_ws(ws: Any) -> None:
    """Remove a WebSocket connection from the proactive registry."""
    _proactive_clients.discard(ws)
    logger.info("proactive_ws_unregistered: %d remaining", len(_proactive_clients))


async def _broadcast_to_devices(payload: dict) -> None:
    """Push a message to all connected proactive WebSocket clients."""
    dead: set[Any] = set()
    for ws in _proactive_clients:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.add(ws)
    _proactive_clients.difference_update(dead)
    if dead:
        logger.info("proactive_ws_pruned: %d dead connections", len(dead))


# ── Database ──────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    """Open a connection to heartbeat.db, creating tables if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scheduled_actions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_type TEXT NOT NULL UNIQUE,
            last_run TEXT,
            interval_seconds INTEGER NOT NULL DEFAULT 0,
            enabled INTEGER NOT NULL DEFAULT 1,
            config TEXT NOT NULL DEFAULT '{}'
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS heartbeat_log (
            id TEXT PRIMARY KEY,
            action_type TEXT NOT NULL,
            message TEXT,
            timestamp TEXT NOT NULL,
            delivered INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.commit()
    return conn


def _seed_defaults(db: sqlite3.Connection) -> None:
    """Insert default scheduled actions if the table is empty."""
    count = db.execute("SELECT COUNT(*) FROM scheduled_actions").fetchone()[0]
    if count > 0:
        return

    defaults = [
        (
            "morning_briefing",
            0,  # not interval-based — time-of-day trigger
            json.dumps({
                "description": "Morning briefing: calendar, tasks, unread messages",
                "hour": 8,
                "minute": 0,
            }),
        ),
        (
            "evening_winddown",
            0,
            json.dumps({
                "description": "Evening wind-down: day summary, tomorrow preview",
                "hour": 21,
                "minute": 0,
            }),
        ),
        (
            "idle_checkin",
            IDLE_THRESHOLD_SECONDS,
            json.dumps({
                "description": "Gentle check-in after 2+ hours idle during waking hours",
                "threshold_seconds": IDLE_THRESHOLD_SECONDS,
            }),
        ),
        (
            "task_reminders",
            TASK_REMINDER_INTERVAL,
            json.dumps({
                "description": "Remind about overdue tasks",
                "interval_hours": 4,
            }),
        ),
    ]
    for action_type, interval, config in defaults:
        db.execute(
            "INSERT INTO scheduled_actions (action_type, interval_seconds, enabled, config) "
            "VALUES (?, ?, 1, ?)",
            (action_type, interval, config),
        )
    db.commit()
    logger.info("heartbeat: seeded %d default actions", len(defaults))


# ── LLM Generation (sync Anthropic client, runs in thread) ───────────────

def _generate_with_haiku(prompt: str) -> str:
    """Call Haiku synchronously. Meant to be run via asyncio.to_thread."""
    if not ANTHROPIC_API_KEY:
        return ""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=256,
        system=HEARTBEAT_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(
        block.text for block in response.content if hasattr(block, "text")
    ).strip()


async def _generate_async(prompt: str) -> str:
    """Run the sync Haiku call in a thread so we don't block the event loop."""
    try:
        return await asyncio.to_thread(_generate_with_haiku, prompt)
    except Exception as exc:
        logger.warning("heartbeat_llm_error: %s", exc)
        return ""


# ── Context Gatherers ─────────────────────────────────────────────────────

async def _gather_calendar_context(now: datetime) -> str:
    """Pull today's events from macOS Calendar via osascript."""
    script = '''
set now to current date
set endDate to now + (1 * days)
tell application "Calendar"
    set output to ""
    set allCals to every calendar
    repeat with cal in allCals
        set evts to (every event of cal whose start date >= now and start date <= endDate)
        repeat with ev in evts
            set output to output & (summary of ev) & " at " & ((start date of ev) as string) & linefeed
        end repeat
    end repeat
    return output
end tell
'''
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().split("\n")[:5]
            return "Calendar today:\n" + "\n".join(f"- {l}" for l in lines)
    except Exception:
        pass
    return ""


async def _gather_task_context() -> str:
    """Pull tasks from Vikunja if available."""
    try:
        from integrations.vikunja_adapter import VikunjaAdapter
        adapter = VikunjaAdapter()
        tasks = adapter.get_today_tasks()
        if tasks:
            items = [f"- {t}" for t in tasks[:5]]
            return "Today's tasks:\n" + "\n".join(items)
    except Exception:
        pass
    return ""


async def _gather_overdue_tasks() -> list[dict]:
    """Return overdue tasks from Vikunja."""
    try:
        from integrations.vikunja_adapter import VikunjaAdapter
        adapter = VikunjaAdapter()
        all_tasks = adapter.list_tasks()
        now_iso = datetime.now().isoformat()
        return [
            t for t in all_tasks
            if t.get("due_date") and t["due_date"] < now_iso and not t.get("done")
        ]
    except Exception:
        return []


async def _gather_unread_context() -> str:
    """Count unread messages and emails."""
    parts = []
    try:
        from integrations.bluebubbles_adapter import BlueBubblesAdapter
        count = BlueBubblesAdapter().get_unread_count()
        if count:
            parts.append(f"{count} unread message{'s' if count != 1 else ''}")
    except Exception:
        pass
    try:
        from integrations.gmail_adapter import GmailAdapter
        count = GmailAdapter().get_unread_count()
        if count:
            parts.append(f"{count} unread email{'s' if count != 1 else ''}")
    except Exception:
        pass
    return "Unread: " + ", ".join(parts) if parts else ""


# ── Action Handlers ───────────────────────────────────────────────────────

async def _handle_morning_briefing(now: datetime) -> str | None:
    """Generate morning briefing content."""
    day_label = now.strftime("%A, %B %d")

    # Gather context in parallel
    cal, tasks, unread = await asyncio.gather(
        _gather_calendar_context(now),
        _gather_task_context(),
        _gather_unread_context(),
    )

    context_parts = [f"Today is {day_label}."]
    if cal:
        context_parts.append(cal)
    if tasks:
        context_parts.append(tasks)
    if unread:
        context_parts.append(unread)

    context = "\n\n".join(context_parts)
    prompt = (
        f"Generate a brief morning briefing for Seb based on this context:\n\n"
        f"{context}\n\n"
        f"Summarize what's on today — calendar, tasks, unread messages. "
        f"Keep it under 3 sentences. No greetings like 'Hey!' — just the info."
    )

    message = await _generate_async(prompt)
    if not message:
        # Fallback: static from gathered context
        message = f"Good morning. {context_parts[0]}"
        if tasks:
            message += f" {tasks.split(chr(10))[0].lstrip('- ')}"
    return message


async def _handle_evening_winddown(now: datetime) -> str | None:
    """Generate evening wind-down content."""
    # Gather what was done today (recent heartbeat log as proxy)
    db = _get_db()
    try:
        today_str = now.strftime("%Y-%m-%d")
        rows = db.execute(
            "SELECT action_type, message FROM heartbeat_log "
            "WHERE timestamp LIKE ? ORDER BY timestamp DESC LIMIT 5",
            (f"{today_str}%",),
        ).fetchall()
    finally:
        db.close()

    day_summary = ""
    if rows:
        day_summary = "Today's proactive actions:\n" + "\n".join(
            f"- {r['action_type']}: {r['message'][:60]}" for r in rows
        )

    # Check tomorrow's first event
    cal_tomorrow = ""
    try:
        tomorrow = now + timedelta(days=1)
        tomorrow_str = tomorrow.strftime("%A")
        cal_tomorrow = f"Tomorrow is {tomorrow_str}."
    except Exception:
        pass

    prompt = (
        f"Generate a brief evening wind-down message for Seb.\n\n"
        f"{day_summary}\n{cal_tomorrow}\n\n"
        f"Summarize what happened today if anything notable, mention tomorrow. "
        f"Suggest winding down. Keep it to 2 sentences. Warm but not cheesy."
    )

    message = await _generate_async(prompt)
    if not message:
        message = "Winding down for the evening. Let me know if you want to set any reminders for tomorrow."
    return message


async def _handle_idle_checkin(idle_seconds: float) -> str | None:
    """Generate a gentle idle check-in."""
    hours = idle_seconds / 3600
    if hours < 3:
        prompt = (
            "Generate a very brief, gentle check-in message. The user has been "
            "away for about 2 hours. Just let them know you're around. One sentence."
        )
    else:
        prompt = (
            f"Generate a brief check-in. The user has been away for about "
            f"{int(hours)} hours. Low-key, no pressure. One sentence."
        )

    message = await _generate_async(prompt)
    if not message:
        if hours < 3:
            message = "Still here if you need anything."
        else:
            message = f"It's been about {int(hours)} hours. No rush — I'm here when you're ready."
    return message


async def _handle_task_reminders() -> str | None:
    """Check for overdue tasks and generate a reminder."""
    overdue = await _gather_overdue_tasks()
    if not overdue:
        return None

    task_names = [t.get("title", "Untitled") for t in overdue[:5]]
    task_list = "\n".join(f"- {n}" for n in task_names)
    extra = f"\n(and {len(overdue) - 5} more)" if len(overdue) > 5 else ""

    prompt = (
        f"Generate a brief reminder about overdue tasks:\n\n{task_list}{extra}\n\n"
        f"Be direct, no lecturing. Mention the key tasks by name. 1-2 sentences."
    )

    message = await _generate_async(prompt)
    if not message:
        names = ", ".join(task_names[:3])
        suffix = f" and {len(overdue) - 3} more" if len(overdue) > 3 else ""
        message = f"You have {len(overdue)} overdue task{'s' if len(overdue) != 1 else ''}: {names}{suffix}."
    return message


# ── Core Heartbeat Engine ─────────────────────────────────────────────────

class _HeartbeatEngine:
    """Internal singleton that runs the background tick loop."""

    def __init__(self):
        self.tz = ZoneInfo(DEFAULT_TIMEZONE)
        self.tick_interval = DEFAULT_TICK_INTERVAL
        self._task: asyncio.Task | None = None
        self._last_tick: datetime | None = None
        self._last_user_activity: datetime = datetime.now(self.tz)
        self._last_proactive_time: datetime | None = None
        self._morning_done_date: str | None = None  # "YYYY-MM-DD"
        self._evening_done_date: str | None = None

        # Ensure DB + defaults
        db = _get_db()
        _seed_defaults(db)
        db.close()

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._task and not self._task.done():
            logger.warning("heartbeat already running")
            return
        self._task = asyncio.create_task(self._loop(), name="heartbeat")
        logger.info(
            "heartbeat_started: tick=%ds tz=%s",
            self.tick_interval, self.tz,
        )

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
            logger.info("heartbeat_stopped")

    # ── User Activity Tracking ────────────────────────────────────────

    def record_activity(self) -> None:
        """Call on every user chat message to reset idle timer."""
        self._last_user_activity = datetime.now(self.tz)

    # ── Main Loop ─────────────────────────────────────────────────────

    async def _loop(self) -> None:
        # Small initial delay so server finishes booting
        await asyncio.sleep(5)
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("heartbeat_tick_error: %s", exc)
            await asyncio.sleep(self.tick_interval)

    async def _tick(self) -> None:
        now = datetime.now(self.tz)
        self._last_tick = now
        today_str = now.strftime("%Y-%m-%d")
        is_waking = ACTIVE_HOURS_START <= now.hour < ACTIVE_HOURS_END

        db = _get_db()
        try:
            actions = db.execute(
                "SELECT * FROM scheduled_actions WHERE enabled = 1"
            ).fetchall()
        finally:
            db.close()

        for action in actions:
            atype = action["action_type"]
            config = json.loads(action["config"]) if action["config"] else {}
            last_run = action["last_run"]

            if atype == "morning_briefing":
                await self._check_time_trigger(
                    now, today_str, atype, config,
                    done_attr="_morning_done_date",
                    handler=_handle_morning_briefing,
                )

            elif atype == "evening_winddown":
                await self._check_time_trigger(
                    now, today_str, atype, config,
                    done_attr="_evening_done_date",
                    handler=_handle_evening_winddown,
                )

            elif atype == "idle_checkin" and is_waking:
                await self._check_idle(now, atype, last_run, config)

            elif atype == "task_reminders" and is_waking:
                await self._check_interval(now, atype, last_run, action["interval_seconds"])

    # ── Trigger Checkers ──────────────────────────────────────────────

    async def _check_time_trigger(
        self,
        now: datetime,
        today_str: str,
        action_type: str,
        config: dict,
        done_attr: str,
        handler,
    ) -> None:
        """Fire a once-per-day action at a specific hour:minute."""
        if getattr(self, done_attr) == today_str:
            return

        hour = config.get("hour", 8 if "morning" in action_type else 21)
        minute = config.get("minute", 0)

        trigger_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        window_end = trigger_time + timedelta(hours=1)

        if not (trigger_time <= now < window_end):
            return

        if not self._cooldown_ok(now):
            return

        message = await handler(now)
        if message:
            await self._deliver(message, action_type, now)
            setattr(self, done_attr, today_str)

    async def _check_idle(
        self,
        now: datetime,
        action_type: str,
        last_run: str | None,
        config: dict,
    ) -> None:
        """Fire if user has been idle for threshold_seconds."""
        threshold = config.get("threshold_seconds", IDLE_THRESHOLD_SECONDS)
        idle_secs = (now - self._last_user_activity).total_seconds()
        if idle_secs < threshold:
            return

        # Don't spam — respect last_run for idle too
        if last_run:
            try:
                last_dt = datetime.fromisoformat(last_run).replace(tzinfo=self.tz)
                if (now - last_dt).total_seconds() < threshold:
                    return
            except (ValueError, TypeError):
                pass

        if not self._cooldown_ok(now):
            return

        message = await _handle_idle_checkin(idle_secs)
        if message:
            await self._deliver(message, action_type, now)

    async def _check_interval(
        self,
        now: datetime,
        action_type: str,
        last_run: str | None,
        interval_seconds: int,
    ) -> None:
        """Fire if interval_seconds have elapsed since last_run."""
        if last_run:
            try:
                last_dt = datetime.fromisoformat(last_run).replace(tzinfo=self.tz)
                if (now - last_dt).total_seconds() < interval_seconds:
                    return
            except (ValueError, TypeError):
                pass

        if not self._cooldown_ok(now):
            return

        if action_type == "task_reminders":
            message = await _handle_task_reminders()
        else:
            return

        if message:
            await self._deliver(message, action_type, now)

    # ── Delivery ──────────────────────────────────────────────────────

    def _cooldown_ok(self, now: datetime) -> bool:
        """Ensure we don't spam the user."""
        if self._last_proactive_time is None:
            return True
        return (now - self._last_proactive_time).total_seconds() >= PROACTIVE_COOLDOWN_SECONDS

    async def _deliver(self, message: str, action_type: str, now: datetime) -> None:
        """Push proactive message to devices and log it.

        If no WebSocket device clients are connected, falls back to sending
        the message via iMessage through the SMS gateway.
        """
        self._last_proactive_time = now
        payload = {
            "type": "proactive_message",
            "action": action_type,
            "message": message,
            "timestamp": now.isoformat(),
        }

        # Push to all connected WebSocket clients
        await _broadcast_to_devices(payload)

        # SMS fallback: if no device clients connected, send via iMessage
        if not _proactive_clients:
            await self._sms_fallback(message, action_type)

        # Log to activity feed
        try:
            from activity_feed import log_activity
            log_activity(
                "heartbeat",
                f"proactive: {action_type}",
                metadata={"message": message[:200], "action": action_type},
                status="done",
            )
        except Exception:
            pass

        # Log to heartbeat_log table
        db = _get_db()
        try:
            db.execute(
                "INSERT INTO heartbeat_log (id, action_type, message, timestamp, delivered) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    f"hbl_{uuid.uuid4().hex[:8]}",
                    action_type,
                    message[:500],
                    now.isoformat(),
                    len(_proactive_clients),
                ),
            )
            # Update last_run for this action
            db.execute(
                "UPDATE scheduled_actions SET last_run = ? WHERE action_type = ?",
                (now.isoformat(), action_type),
            )
            db.commit()
        finally:
            db.close()

        logger.info(
            "heartbeat_proactive [%s] -> %d clients: %s",
            action_type, len(_proactive_clients), message[:120],
        )

    # ── SMS Fallback ─────────────────────────────────────────────────

    async def _sms_fallback(self, message: str, action_type: str) -> None:
        """Send a proactive message via iMessage when no devices are connected."""
        try:
            from integrations.bluebubbles_adapter import BlueBubblesAdapter
            adapter = BlueBubblesAdapter()
            chat_guid = adapter.self_chat_guid
            if not chat_guid:
                logger.debug(
                    "heartbeat_sms_fallback: no BLUEBUBBLES_SELF_CHAT_GUID configured, skipping"
                )
                return

            prefix = f"[{action_type}] " if "manual" not in action_type else ""
            ok = await adapter.send_message_async(chat_guid, f"{prefix}{message}")
            if ok:
                logger.info("heartbeat_sms_fallback: sent via iMessage (%s)", action_type)
            else:
                logger.warning("heartbeat_sms_fallback: send_message returned False")
        except Exception as exc:
            logger.warning("heartbeat_sms_fallback_error: %s", exc)

    # ── Manual Trigger ────────────────────────────────────────────────

    async def trigger(self, action_type: str) -> dict:
        """Manually fire an action. Returns result dict."""
        now = datetime.now(self.tz)

        handlers = {
            "morning_briefing": lambda: _handle_morning_briefing(now),
            "evening_winddown": lambda: _handle_evening_winddown(now),
            "idle_checkin": lambda: _handle_idle_checkin(
                (now - self._last_user_activity).total_seconds()
            ),
            "task_reminders": _handle_task_reminders,
        }

        handler = handlers.get(action_type)
        if not handler:
            return {"action": action_type, "error": "unknown action type", "triggered": False}

        try:
            message = await handler()
            if not message:
                return {"action": action_type, "message": None, "triggered": False, "reason": "no content"}

            # Force-deliver regardless of cooldown
            self._last_proactive_time = None
            await self._deliver(message, f"{action_type} (manual)", now)
            return {"action": action_type, "message": message, "triggered": True}
        except Exception as exc:
            logger.exception("heartbeat_trigger_error: %s", exc)
            return {"action": action_type, "error": str(exc), "triggered": False}

    # ── Status ────────────────────────────────────────────────────────

    def status(self) -> dict:
        now = datetime.now(self.tz)
        idle_secs = (now - self._last_user_activity).total_seconds()

        cooldown_remaining = 0.0
        if self._last_proactive_time:
            elapsed = (now - self._last_proactive_time).total_seconds()
            cooldown_remaining = max(0, PROACTIVE_COOLDOWN_SECONDS - elapsed)

        # Scheduled actions from DB
        actions = []
        recent_log = []
        db = _get_db()
        try:
            for row in db.execute("SELECT * FROM scheduled_actions ORDER BY action_type").fetchall():
                actions.append({
                    "id": row["id"],
                    "action_type": row["action_type"],
                    "last_run": row["last_run"],
                    "interval_seconds": row["interval_seconds"],
                    "enabled": bool(row["enabled"]),
                    "config": json.loads(row["config"]) if row["config"] else {},
                })
            for row in db.execute(
                "SELECT * FROM heartbeat_log ORDER BY timestamp DESC LIMIT 10"
            ).fetchall():
                recent_log.append({
                    "action_type": row["action_type"],
                    "message": row["message"],
                    "timestamp": row["timestamp"],
                    "delivered": row["delivered"],
                })
        finally:
            db.close()

        return {
            "running": self._task is not None and not self._task.done(),
            "tick_interval_seconds": self.tick_interval,
            "timezone": str(self.tz),
            "last_tick": self._last_tick.isoformat() if self._last_tick else None,
            "last_user_activity": self._last_user_activity.isoformat(),
            "idle_seconds": round(idle_secs),
            "idle_human": f"{int(idle_secs // 3600)}h {int((idle_secs % 3600) // 60)}m",
            "last_proactive_time": self._last_proactive_time.isoformat() if self._last_proactive_time else None,
            "cooldown_remaining_seconds": round(cooldown_remaining),
            "connected_clients": len(_proactive_clients),
            "morning_done_today": self._morning_done_date,
            "evening_done_today": self._evening_done_date,
            "scheduled_actions": actions,
            "recent_log": recent_log,
        }


# ── Module Singleton ──────────────────────────────────────────────────────

_engine: _HeartbeatEngine | None = None


def _get_engine() -> _HeartbeatEngine:
    global _engine
    if _engine is None:
        _engine = _HeartbeatEngine()
    return _engine


# ── Public API ────────────────────────────────────────────────────────────

async def start_heartbeat(app: Any = None) -> None:
    """Start the heartbeat background loop. Call from main.py on startup.

    The `app` parameter is accepted for convention (FastAPI app instance)
    but not strictly required — the engine runs as a free asyncio task.
    """
    engine = _get_engine()
    await engine.start()
    logger.info("heartbeat: started via start_heartbeat()")


async def stop_heartbeat() -> None:
    """Gracefully shut down the heartbeat loop."""
    engine = _get_engine()
    await engine.stop()


def get_heartbeat_status() -> dict:
    """Return current heartbeat state — last tick, scheduled actions, recent log."""
    return _get_engine().status()


async def trigger_action(action_type: str) -> dict:
    """Manually trigger a heartbeat action. Returns result dict."""
    return await _get_engine().trigger(action_type)


def record_user_activity() -> None:
    """Call on every user chat message to reset the idle timer."""
    _get_engine().record_activity()
