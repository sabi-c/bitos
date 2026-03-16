"""BITOS Server backend: health, chat, and UI settings catalog endpoints."""
import asyncio
import logging
import os
import sqlite3
import subprocess
import sys
import threading
import uuid

try:
    import psutil
except Exception:  # pragma: no cover - fallback for environments missing psutil
    class _Mem:
        used = 0
        total = 0
        percent = 0

    class _Disk:
        percent = 0

    class _PsutilFallback:
        @staticmethod
        def cpu_percent(interval=0):
            return 0

        @staticmethod
        def virtual_memory():
            return _Mem()

        @staticmethod
        def disk_usage(_path):
            return _Disk()

    psutil = _PsutilFallback()
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

SERVER_DIR = Path(__file__).resolve().parent
INTEGRATIONS_DIR = SERVER_DIR / "integrations"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
if str(INTEGRATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_DIR))

from bluebubbles_adapter import BlueBubblesAdapter
from vikunja_adapter import VikunjaAdapter
from gmail_adapter import GmailAdapter

from agent_modes import get_system_prompt
from config import UI_SETTINGS_FILE
from llm_bridge import create_llm_bridge, to_sse_data
from ui_settings import UISettingsStore, UISettingsValidationError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from version import __version__, __build__


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    agent_mode: str = "producer"
    tasks_today: list[str] = Field(default_factory=list)
    battery_pct: int | None = None
    web_search: bool = True
    memory: bool = True
    model: str = ""


class MessageSendRequest(BaseModel):
    chat_id: str
    text: str
    confirmed: bool = False


class MessageDraftRequest(BaseModel):
    chat_id: str
    voice_transcript: str


class MailDraftRequest(BaseModel):
    thread_id: str
    voice_transcript: str


class MailCreateDraftRequest(BaseModel):
    thread_id: str
    body: str
    confirmed: bool = False


class IntegrationSettingsRequest(BaseModel):
    integration: str
    config: dict = Field(default_factory=dict)


class DeviceUpdateRequest(BaseModel):
    target: str = "both"
    confirmed: bool = False


class SubtaskRequest(BaseModel):
    name: str
    prompt: str


def _is_real_anthropic_key(value: str) -> bool:
    key = value.strip()
    return key.startswith("sk-ant-")


def _integration_status_payload() -> dict:
    imessage = BlueBubblesAdapter()
    vikunja = VikunjaAdapter()

    imessage_status = "mock" if imessage.is_mock else "offline"
    if not imessage.is_mock:
        try:
            imessage.ping()
            imessage_status = "online"
        except Exception:
            imessage_status = "offline"

    vikunja_status = "mock" if vikunja.is_mock else "offline"
    task_count = 0
    if not vikunja.is_mock:
        try:
            task_count = len(vikunja.get_today_tasks())
            vikunja_status = "online"
        except Exception:
            vikunja_status = "offline"

    anthropic = os.environ.get("ANTHROPIC_API_KEY", "")
    ai_status = "online" if _is_real_anthropic_key(anthropic) else "offline"

    return {
        "imessage": {
            "status": imessage_status,
            "unread": imessage.get_unread_count() if imessage_status in {"online", "mock"} else 0,
            "server_url": imessage.base_url,
            "last_checked": "just now",
        },
        "vikunja": {
            "status": vikunja_status,
            "task_count": task_count,
            "last_checked": "just now" if vikunja_status in {"online", "mock"} else "never",
        },
        "ai": {
            "status": ai_status,
            "provider": "anthropic",
            "model": llm_bridge.model,
        },
    }


def _write_dev_env(updates: dict[str, str]) -> None:
    env_path = os.path.join(os.getcwd(), ".env")
    existing: dict[str, str] = {}
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" not in line or line.strip().startswith("#"):
                    continue
                k, v = line.strip().split("=", 1)
                existing[k] = v
    existing.update(updates)
    with open(env_path, "w", encoding="utf-8") as f:
        for key in sorted(existing.keys()):
            f.write(f"{key}={existing[key]}\n")


def _write_pi_secrets(updates: dict[str, str]) -> None:
    secrets_path = "/etc/bitos/secrets"
    existing: dict[str, str] = {}
    if os.path.exists(secrets_path):
        with open(secrets_path, "r", encoding="utf-8") as f:
            for line in f:
                if "=" not in line or line.strip().startswith("#"):
                    continue
                k, v = line.strip().split("=", 1)
                existing[k] = v
    existing.update(updates)
    os.makedirs(os.path.dirname(secrets_path), exist_ok=True)
    with open(secrets_path, "w", encoding="utf-8") as f:
        for key in sorted(existing.keys()):
            f.write(f"{key}={existing[key]}\n")


def _persist_integration_settings(updates: dict[str, str]) -> str:
    for key, value in updates.items():
        os.environ[key] = value
    if os.path.exists("/etc/bitos"):
        _write_pi_secrets(updates)
        return "pi"
    _write_dev_env(updates)
    return "dev"


def _test_integration_connection(integration: str, config: dict) -> tuple[bool, str]:
    if integration == "imessage":
        adapter = BlueBubblesAdapter()
        if not config.get("password", "").strip():
            return False, "BlueBubbles password required"
        try:
            adapter.ping()
            return True, ""
        except Exception as exc:
            return False, str(exc)

    if integration == "vikunja":
        token = str(config.get("token", "")).strip()
        if not token:
            return False, "Vikunja token required"
        base_url = str(config.get("url", "")).rstrip("/")
        import httpx

        try:
            resp = httpx.get(
                f"{base_url}/user",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            resp.raise_for_status()
            return True, ""
        except Exception as exc:
            return False, str(exc)

    return False, "Unknown integration"


REPO_DIR = ROOT_DIR
_last_version_check: datetime | None = None


def get_git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_DIR,
            timeout=3,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _git_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_DIR,
            timeout=3,
            check=False,
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _commits_behind_origin_main() -> int:
    global _last_version_check
    _last_version_check = datetime.now(timezone.utc)
    try:
        subprocess.run(["git", "fetch", "--quiet"], cwd=REPO_DIR, timeout=5, check=False)
        result = subprocess.run(
            ["git", "rev-list", "HEAD..origin/main", "--count"],
            capture_output=True,
            text=True,
            cwd=REPO_DIR,
            timeout=3,
            check=False,
        )
        return int((result.stdout or "0").strip() or "0")
    except Exception:
        return 0


def _run_ota_update(target: str) -> dict:
    allowed = {"device", "server", "both"}
    normalized = target if target in allowed else "both"
    script = REPO_DIR / "scripts" / "ota_update.sh"
    env = os.environ.copy()
    env["OTA_TARGET"] = normalized

    if script.exists():
        subprocess.run(["bash", str(script)], cwd=REPO_DIR, env=env, timeout=180, check=False)
    else:
        subprocess.run(["git", "pull", "origin", "main"], cwd=REPO_DIR, timeout=30, check=False)
        subprocess.run(["pip", "install", "-r", "requirements.txt", "-q"], cwd=REPO_DIR, timeout=60, check=False)

    # Best-effort health probe after restart/update
    try:
        import httpx

        httpx.get("http://localhost:8000/health", timeout=5)
    except Exception:
        pass

    return {"ok": True, "new_commit": get_git_commit(), "target": normalized}


logger = logging.getLogger(__name__)

app = FastAPI(title="BITOS Server", version=__version__)
settings_store = UISettingsStore(UI_SETTINGS_FILE)
llm_bridge = create_llm_bridge()
_token_warning_logged = False

# ── Agent subtask database ──
_SUBTASK_DB_PATH = os.environ.get("DATABASE_PATH", str(SERVER_DIR / "data" / "subtasks.db"))


def _subtask_db() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_SUBTASK_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_SUBTASK_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_subtask_table():
    with _subtask_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agent_subtasks (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                prompt TEXT NOT NULL,
                result TEXT,
                error TEXT,
                input_tokens INTEGER DEFAULT 0,
                output_tokens INTEGER DEFAULT 0,
                cost_usd REAL DEFAULT 0.0,
                created_at TEXT DEFAULT (datetime('now')),
                started_at TEXT,
                completed_at TEXT
            )
        """)
        conn.commit()


_init_subtask_table()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_device_token(request: Request, call_next):
    global _token_warning_logged

    if request.method == "GET" and request.url.path == "/health":
        return await call_next(request)

    # SD-004: Static device-token middleware enforces device identity on non-health endpoints.
    expected = os.environ.get("BITOS_DEVICE_TOKEN", "")
    provided = request.headers.get("X-Device-Token", "")

    if not expected:
        if not _token_warning_logged:
            logger.warning("[BITOS] BITOS_DEVICE_TOKEN is not set; allowing all requests (dev mode)")
            _token_warning_logged = True
        return await call_next(request)

    if provided != expected:
        return JSONResponse(status_code=401, content={"detail": "Unauthorized device"})

    return await call_next(request)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "version": __version__,
        "build": __build__,
        "commit": get_git_commit(),
        "provider": llm_bridge.provider,
        "model": llm_bridge.model,
        "settings_file": UI_SETTINGS_FILE,
    }


@app.get("/device/version")
async def device_version():
    behind = _commits_behind_origin_main()
    return {
        "version": __version__,
        "commit": get_git_commit(),
        "branch": _git_branch(),
        "behind": behind,
        "update_available": behind > 0,
        "last_checked": (_last_version_check or datetime.now(timezone.utc)).isoformat(),
    }


@app.post("/device/update")
async def device_update(payload: DeviceUpdateRequest):
    if not payload.confirmed:
        raise HTTPException(status_code=403, detail="requires confirmed=true")

    result: dict[str, object] = {"ok": False, "new_commit": get_git_commit()}

    def runner():
        nonlocal result
        result = _run_ota_update(payload.target)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    thread.join(timeout=25)

    if thread.is_alive():
        return {"ok": True, "new_commit": get_git_commit(), "message": "update started"}
    return result


@app.post("/settings/integrations")
async def update_integrations_settings(payload: IntegrationSettingsRequest):
    integration = payload.integration.strip().lower()
    config = payload.config or {}

    updates: dict[str, str]
    if integration == "imessage":
        updates = {
            "BLUEBUBBLES_BASE_URL": str(config.get("url", "")).strip(),
            "BLUEBUBBLES_PASSWORD": str(config.get("password", "")).strip(),
        }
    elif integration == "vikunja":
        updates = {
            "VIKUNJA_BASE_URL": str(config.get("url", "")).strip(),
            "VIKUNJA_API_TOKEN": str(config.get("token", "")).strip(),
        }
    else:
        raise HTTPException(status_code=400, detail="Unknown integration")

    _persist_integration_settings(updates)
    ok, error = _test_integration_connection(integration, config)
    if not ok:
        return {"ok": False, "error": error}
    return {"ok": True}


@app.get("/settings/catalog")
async def settings_catalog():
    """Return catalog metadata for editable UI settings."""
    return settings_store.catalog()


@app.get("/settings/ui")
async def get_ui_settings():
    """Return current persisted UI settings."""
    return settings_store.get()


@app.put("/settings/ui")
async def update_ui_settings(request: Request):
    """Persist a partial UI settings update after validation."""
    patch = await request.json()
    if not isinstance(patch, dict):
        raise HTTPException(status_code=400, detail="Settings patch must be an object")

    try:
        return settings_store.update(patch)
    except UISettingsValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc




@app.get("/tasks/today")
async def get_today_tasks():
    adapter = VikunjaAdapter()
    tasks = adapter.get_today_tasks()
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/messages")
async def get_messages_conversations():
    adapter = BlueBubblesAdapter()
    return {
        "conversations": adapter.get_conversations(),
        "unread_total": adapter.get_unread_count(),
    }


@app.get("/mail")
async def get_mail_threads():
    adapter = GmailAdapter()
    return {
        "threads": adapter.get_inbox(limit=10),
        "unread_total": adapter.get_unread_count(),
    }


@app.get("/mail/{thread_id:path}")
async def get_mail_thread(thread_id: str):
    adapter = GmailAdapter()
    return {
        "messages": adapter.get_thread(thread_id),
        "thread_id": thread_id,
    }


@app.post("/mail/draft")
async def draft_mail(payload: MailDraftRequest):
    adapter = GmailAdapter()
    draft = adapter.draft_reply(payload.thread_id, payload.voice_transcript)
    return {"draft": draft}


@app.post("/mail/create-draft")
async def create_mail_draft(payload: MailCreateDraftRequest):
    if not payload.confirmed:
        raise HTTPException(status_code=403, detail="requires confirmed=true")

    adapter = GmailAdapter()
    draft_id = adapter.create_draft(payload.thread_id, payload.body)
    return {"draft_id": draft_id, "ok": bool(draft_id)}


@app.get("/messages/{chat_id:path}")
async def get_messages_for_chat(chat_id: str):
    adapter = BlueBubblesAdapter()
    return {
        "messages": adapter.get_messages(chat_id),
        "chat_id": chat_id,
    }


@app.post("/messages/send")
async def send_message(payload: MessageSendRequest):
    if not payload.confirmed:
        raise HTTPException(status_code=403, detail="requires confirmed=true")

    adapter = BlueBubblesAdapter()
    ok = adapter.send_message(payload.chat_id, payload.text)
    return {"sent": ok}


@app.post("/messages/draft")
async def draft_message(payload: MessageDraftRequest):
    adapter = BlueBubblesAdapter()
    messages = adapter.get_messages(payload.chat_id, limit=3)
    context = "\n".join(
        f"{'You' if message['from_me'] else 'Them'}: {message['text']}"
        for message in messages
    )
    prompt = f"""Draft a reply to this iMessage conversation.

Context:
{context}

The person wants to say:
{payload.voice_transcript}

Write ONLY the reply message text.
Match the conversational tone. Be concise and natural."""
    complete_text = getattr(llm_bridge, "complete_text", None)
    if callable(complete_text):
        draft = complete_text(prompt)
    else:
        draft = "".join(llm_bridge.stream_text(prompt))
    return {"draft": draft}


@app.post("/webhooks/imessage")
async def imessage_webhook(request: Request):
    body = await request.json()
    event = body.get("event", "")
    if event != "new-message":
        return {"ok": True}
    data = body.get("data", {})
    logger.info("imessage_webhook sender=%s", data.get("handle", {}).get("address", ""))
    return {"ok": True}


@app.get("/status/integrations")
async def integrations_status():
    now = datetime.now(timezone.utc).isoformat()
    msg_adapter = BlueBubblesAdapter()
    gmail_adapter = GmailAdapter()

    payload = _integration_status_payload()
    payload.update(
        {
            "bluebubbles": {
                "status": "mock" if msg_adapter.is_mock else "online",
                "unread": msg_adapter.get_unread_count(),
                "last_checked": now,
            },
            "gmail": {
                "status": gmail_adapter.integration_status(),
                "unread": gmail_adapter.get_unread_count(),
                "last_checked": now,
            },
        }
    )
    return payload




@app.get("/device/stats")
async def get_device_stats():
    mem = psutil.virtual_memory()
    pct = 0
    charging = False
    try:
        from device.storage.repository import DeviceRepository

        repo = DeviceRepository()
        pct = int(repo.get_setting("battery_pct", 0) or 0)
        charging = str(repo.get_setting("charging", "false")).lower() == "true"
    except Exception:
        pass
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "ram_used_mb": mem.used // 1024 // 1024,
        "ram_total_mb": mem.total // 1024 // 1024,
        "ram_percent": mem.percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "battery": {
            "pct": pct,
            "charging": charging,
            "present": pct > 0,
        },
    }


@app.get("/device/battery")
async def get_battery():
    """Read battery state cached by device poller."""
    try:
        from device.storage.repository import DeviceRepository

        repo = DeviceRepository()
        pct = int(repo.get_setting("battery_pct", 0) or 0)
        charging = str(repo.get_setting("charging", "false")).lower() == "true"
        return {"pct": pct, "charging": charging, "present": pct > 0}
    except Exception:
        return {"pct": 0, "charging": False, "present": False}

@app.get("/dashboard")
async def get_dashboard():
    """Aggregated snapshot for device home screen: time, tasks, messages, mail, system."""
    now = datetime.now(timezone.utc)

    # Tasks
    vikunja = VikunjaAdapter()
    try:
        tasks = vikunja.get_today_tasks()
    except Exception:
        tasks = []

    # Messages
    msg_adapter = BlueBubblesAdapter()
    try:
        msg_unread = msg_adapter.get_unread_count()
    except Exception:
        msg_unread = 0

    # Mail
    gmail = GmailAdapter()
    try:
        mail_unread = gmail.get_unread_count()
    except Exception:
        mail_unread = 0

    # System
    mem = psutil.virtual_memory()
    battery_pct = 0
    charging = False
    try:
        from device.storage.repository import DeviceRepository
        repo = DeviceRepository()
        battery_pct = int(repo.get_setting("battery_pct", 0) or 0)
        charging = str(repo.get_setting("charging", "false")).lower() == "true"
    except Exception:
        pass

    return {
        "timestamp": now.isoformat(),
        "tasks": {"items": tasks[:5], "total": len(tasks)},
        "messages": {"unread": msg_unread},
        "mail": {"unread": mail_unread},
        "system": {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "ram_percent": mem.percent,
            "battery": {"pct": battery_pct, "charging": charging},
        },
        "ai": {
            "provider": llm_bridge.provider,
            "model": llm_bridge.model,
        },
    }


@app.get("/brief")
async def get_brief():
    """Morning-brief summary: tasks, unread counts, weather-ready structure."""
    vikunja = VikunjaAdapter()
    try:
        tasks = vikunja.get_today_tasks()
    except Exception:
        tasks = []

    msg_adapter = BlueBubblesAdapter()
    try:
        msg_unread = msg_adapter.get_unread_count()
    except Exception:
        msg_unread = 0

    gmail = GmailAdapter()
    try:
        mail_unread = gmail.get_unread_count()
        mail_threads = gmail.get_inbox(limit=3)
    except Exception:
        mail_unread = 0
        mail_threads = []

    now = datetime.now()
    hour = now.hour
    if hour < 12:
        greeting = "Good morning"
    elif hour < 17:
        greeting = "Good afternoon"
    else:
        greeting = "Good evening"

    task_names = [t.get("title", t.get("text", "")) for t in tasks[:5]]

    return {
        "greeting": greeting,
        "date": now.strftime("%A, %B %-d"),
        "tasks": {"items": task_names, "total": len(tasks)},
        "messages": {"unread": msg_unread},
        "mail": {"unread": mail_unread, "recent": mail_threads[:3]},
    }

<<<<<<< HEAD
def _calculate_cost(input_tokens: int, output_tokens: int, model: str = "") -> float:
    """Calculate USD cost based on token usage and model."""
    model_lower = (model or llm_bridge.model).lower()
    if "haiku" in model_lower:
        return input_tokens * 0.001 / 1000 + output_tokens * 0.005 / 1000
    # Default: Sonnet pricing
    return input_tokens * 0.003 / 1000 + output_tokens * 0.015 / 1000


async def _run_subtask(task_id: str, prompt: str):
    """Background coroutine that executes a subtask via the LLM bridge."""
    try:
        with _subtask_db() as conn:
            conn.execute(
                "UPDATE agent_subtasks SET status = 'running', started_at = datetime('now') WHERE id = ?",
                (task_id,),
            )
            conn.commit()

        loop = asyncio.get_event_loop()
        result_text, input_tokens, output_tokens = await loop.run_in_executor(
            None, lambda: llm_bridge.complete_text(prompt)
        )
        cost = _calculate_cost(input_tokens, output_tokens)

        with _subtask_db() as conn:
            conn.execute(
                """UPDATE agent_subtasks
                   SET status = 'complete', result = ?, input_tokens = ?, output_tokens = ?,
                       cost_usd = ?, completed_at = datetime('now')
                   WHERE id = ?""",
                (result_text, input_tokens, output_tokens, cost, task_id),
            )
            conn.commit()
    except Exception as exc:
        logger.error("subtask_failed task_id=%s error=%s", task_id, exc)
        with _subtask_db() as conn:
            conn.execute(
                "UPDATE agent_subtasks SET status = 'failed', error = ?, completed_at = datetime('now') WHERE id = ?",
                (str(exc), task_id),
            )
            conn.commit()


@app.post("/agent/subtasks")
async def create_subtask(payload: SubtaskRequest):
    task_id = uuid.uuid4().hex[:12]
    with _subtask_db() as conn:
        conn.execute(
            "INSERT INTO agent_subtasks (id, name, status, prompt) VALUES (?, ?, 'pending', ?)",
            (task_id, payload.name, payload.prompt),
        )
        conn.commit()
    asyncio.create_task(_run_subtask(task_id, payload.prompt))
    return {"task_id": task_id, "status": "pending"}


@app.get("/agent/subtasks")
async def list_subtasks(status: str | None = None):
    with _subtask_db() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM agent_subtasks WHERE status = ? ORDER BY created_at DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM agent_subtasks ORDER BY created_at DESC"
            ).fetchall()
    return {"subtasks": [dict(row) for row in rows]}


@app.get("/agent/subtasks/{task_id}")
async def get_subtask(task_id: str):
    with _subtask_db() as conn:
        row = conn.execute("SELECT * FROM agent_subtasks WHERE id = ?", (task_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Subtask not found")
    return dict(row)


@app.post("/agent/subtasks/test")
async def create_test_subtask():
    """Create a test subtask as proof-of-concept."""
    sample_text = (
        "Artificial intelligence has rapidly evolved from a theoretical concept to a practical tool "
        "that impacts nearly every aspect of modern life. Machine learning models can now understand "
        "natural language, generate images, write code, and even compose music. The field continues "
        "to advance at an extraordinary pace, with new breakthroughs announced almost weekly. "
        "However, this progress also raises important questions about safety, ethics, and the "
        "future of human work. Researchers and policymakers are working to establish frameworks "
        "that ensure AI development benefits humanity while minimizing potential risks."
    )
    prompt = (
        "Summarize the following text into 4 short paragraphs of ~60 words each, "
        f"suitable for a tiny screen:\n\n{sample_text}"
    )
    task_id = uuid.uuid4().hex[:12]
    with _subtask_db() as conn:
        conn.execute(
            "INSERT INTO agent_subtasks (id, name, status, prompt) VALUES (?, ?, 'pending', ?)",
            (task_id, "markdown-parse", prompt),
        )
        conn.commit()
    asyncio.create_task(_run_subtask(task_id, prompt))
    return {"task_id": task_id, "status": "pending", "name": "markdown-parse"}


# ── File Viewer Endpoints ──────────────────────────────────────────────
import base64
from pathlib import PurePosixPath

BITOS_FILES_DIR = Path(os.environ.get("BITOS_FILES_DIR", str(ROOT_DIR / "files")))
_ALLOWED_EXTENSIONS = {".md", ".txt"}


def _file_id_encode(relative_path: str) -> str:
    """Base64-encode a relative path for use as a URL-safe file ID."""
    return base64.urlsafe_b64encode(relative_path.encode()).decode().rstrip("=")


def _file_id_decode(file_id: str) -> str:
    """Decode a base64 file ID back to a relative path."""
    padded = file_id + "=" * (-len(file_id) % 4)
    return base64.urlsafe_b64decode(padded.encode()).decode()


def _is_safe_path(base: Path, target: Path) -> bool:
    """Ensure target is within base directory (no traversal)."""
    try:
        target.resolve().relative_to(base.resolve())
        return True
    except ValueError:
        return False


@app.get("/files")
async def list_files(path: str = "", limit: int = 20):
    """List files in the curated file system."""
    scan_dir = BITOS_FILES_DIR / path
    if not _is_safe_path(BITOS_FILES_DIR, scan_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not scan_dir.is_dir():
        return {"files": []}

    files = []
    for entry in sorted(scan_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in _ALLOWED_EXTENSIONS:
            continue
        rel = entry.relative_to(BITOS_FILES_DIR)
        file_type = "markdown" if entry.suffix.lower() == ".md" else "text"
        files.append({
            "id": _file_id_encode(str(rel)),
            "name": entry.stem,
            "path": str(rel),
            "size": entry.stat().st_size,
            "type": file_type,
        })
        if len(files) >= limit:
            break

    return {"files": files}


@app.get("/files/{file_id}")
async def get_file(file_id: str):
    """Get file content."""
    try:
        rel_path = _file_id_decode(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    file_path = BITOS_FILES_DIR / rel_path
    if not _is_safe_path(BITOS_FILES_DIR, file_path):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content = file_path.read_text(encoding="utf-8")
    return {
        "id": file_id,
        "name": file_path.stem,
        "content": content,
        "size": file_path.stat().st_size,
    }


@app.post("/files/{file_id}/parse")
async def parse_file(file_id: str):
    """Parse a file into device-friendly 4-page summary using LLM."""
    try:
        rel_path = _file_id_decode(file_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file ID")

    file_path = BITOS_FILES_DIR / rel_path
    if not _is_safe_path(BITOS_FILES_DIR, file_path):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")

    content = file_path.read_text(encoding="utf-8")
    title = file_path.stem.replace("-", " ").replace("_", " ").title()

    prompt = (
        f"Summarize the following document into exactly 4 short sections. "
        f"Each section should be under 200 characters. "
        f"Return ONLY the 4 sections separated by '---' on its own line. "
        f"No headers, no numbering.\n\n{content[:3000]}"
    )

    try:
        complete_text = getattr(llm_bridge, "complete_text", None)
        if callable(complete_text):
            raw = complete_text(prompt)
        else:
            raw = "".join(llm_bridge.stream_text(prompt))

        pages = [p.strip() for p in raw.split("---") if p.strip()]
        # Ensure exactly 4 pages max
        pages = pages[:4]
        if not pages:
            pages = [content[:200]]
    except Exception as exc:
        logger.warning("file_parse_llm_failed: %s", exc)
        # Fallback: split content into chunks
        chunk_size = 200
        pages = []
        for i in range(0, min(len(content), 800), chunk_size):
            pages.append(content[i:i + chunk_size].strip())
        pages = [p for p in pages if p][:4]
        if not pages:
            pages = [content[:200] or "(empty file)"]

    return {
        "pages": pages,
        "page_count": len(pages),
        "title": title,
    }


@app.post("/shutdown")
async def shutdown():
    """Graceful shutdown hook for device power gesture flow."""
    logging.info("[BITOS] shutdown requested")
    return {"status": "ok"}


@app.post("/chat")
async def chat(payload: ChatRequest):
    """Stream model response from the active LLM bridge as SSE."""
    message = payload.message
    if not message:
        return {"error": "No message provided"}

    agent_mode = payload.agent_mode or "producer"
    system_prompt = get_system_prompt(
        agent_mode,
        tasks_today=payload.tasks_today,
        battery_pct=payload.battery_pct,
        web_search=payload.web_search,
        memory=payload.memory,
    )

    model_override = payload.model if payload.model else None

    def stream_response():
        for text in llm_bridge.stream_text(message, system_prompt=system_prompt, model_override=model_override):
            yield to_sse_data(text)

        yield "data: [DONE]\n\n"

    try:
        return StreamingResponse(
            stream_response(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
    except Exception as exc:
        logger.error("[BITOS] Chat stream failed: %s", exc)
        return {"error": str(exc)}


if __name__ == "__main__":
    import uvicorn
    from config import SERVER_HOST, SERVER_PORT

    logger.info("[BITOS] Starting server on %s:%s", SERVER_HOST, SERVER_PORT)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
