"""BITOS Server backend: health, chat, and UI settings catalog endpoints."""
import asyncio
import json
import logging
import logging.handlers
import os
import sqlite3
import subprocess
import sys
import threading
import traceback
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

from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

SERVER_DIR = Path(__file__).resolve().parent
INTEGRATIONS_DIR = SERVER_DIR / "integrations"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))
if str(INTEGRATIONS_DIR) not in sys.path:
    sys.path.insert(0, str(INTEGRATIONS_DIR))

from integrations.bluebubbles_adapter import BlueBubblesAdapter
from integrations.vikunja_adapter import VikunjaAdapter
from integrations.gmail_adapter import GmailAdapter

from notifications.dispatcher import NotificationDispatcher
from notifications.integration_bridge import IntegrationBridge
from notifications.queue_store import QueueStore
from notifications.router import DeliveryRouter
from notifications.voice_summary import build_summary, build_detail
from notifications.ws_handler import DeviceWSHandler

from agent_modes import get_system_prompt
from config import UI_SETTINGS_FILE
from conversation_store import (
    create_conversation,
    add_message,
    get_messages as get_conv_messages,
    list_conversations,
    get_conversation,
)
from fact_extractor import extract_and_store_facts
from memory_store import (
    add_fact,
    search_facts,
    get_recent_facts,
    get_facts_by_category,
    deactivate_fact,
)
from memory.memory_store import MemoryStore
from memory.fact_extractor import FactExtractor
from memory.retriever import MemoryRetriever
from llm_bridge import create_llm_bridge, to_sse_data
from perception import classify as classify_perception
from ui_settings import UISettingsStore, UISettingsValidationError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from version import __version__, __build__


# ── Structured logging setup ─────────────────────────────────────────────
def _configure_logging():
    """Set up structured logging with file rotation for remote debugging."""
    log_dir = os.environ.get("BITOS_LOG_DIR", str(ROOT_DIR / "logs"))
    os.makedirs(log_dir, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    # Console handler (always)
    console = logging.StreamHandler(sys.stderr)
    console.setFormatter(fmt)

    # Rotating file handler: 5MB x 3 files — survives reboots, stays small on Pi
    file_handler = logging.handlers.RotatingFileHandler(
        os.path.join(log_dir, "server.log"),
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(file_handler)

    # Quiet noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


_configure_logging()


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    agent_mode: str = "producer"
    tasks_today: list[str] = Field(default_factory=list)
    battery_pct: int | None = None
    web_search: bool = True
    memory: bool = True
    model: str = ""
    location: dict | None = None
    volume: int = 100
    voice_enabled: bool = False
    voice_mode: str = "auto"
    extended_thinking: bool = False
    response_format_hint: str = ""
    meta_prompt: str | None = None
    conversation_id: str | None = None


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

    # Task store (BITOS-owned SQLite)
    task_store_status = "offline"
    task_count = 0
    try:
        import task_store
        task_count = len(task_store.get_today_tasks())
        task_store_status = "online"
    except Exception:
        task_store_status = "offline"

    # Legacy Vikunja status (kept for reference)
    vikunja_status = "mock" if vikunja.is_mock else "offline"

    anthropic = os.environ.get("ANTHROPIC_API_KEY", "")
    ai_status = "online" if _is_real_anthropic_key(anthropic) else "offline"

    return {
        "imessage": {
            "status": imessage_status,
            "unread": imessage.get_unread_count() if imessage_status in {"online", "mock"} else 0,
            "server_url": imessage.base_url,
            "last_checked": "just now",
        },
        "tasks": {
            "status": task_store_status,
            "task_count": task_count,
            "backend": "bitos_sqlite",
        },
        "vikunja": {
            "status": vikunja_status,
            "note": "legacy, being retired",
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

    if integration == "anthropic":
        api_key = str(config.get("api_key", "")).strip()
        if not _is_real_anthropic_key(api_key):
            return False, "Invalid key format (expected sk-ant-...)"
        return True, ""

    if integration == "gmail":
        # Gmail is toggle-only; no connection test needed
        return True, ""

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

# ── 01-compatible WebSocket endpoint ──
from endpoints.ws_01_compat import router as ws_01_router
from endpoints.spotify_auth import router as spotify_router
from endpoints.codex_remote import router as codex_remote_router
app.include_router(ws_01_router)
app.include_router(spotify_router)
app.include_router(codex_remote_router)

# ── Antigravity voice/text pipeline ──
from ag_voice_handler import router as ag_voice_router
app.include_router(ag_voice_router)

# ── SMS/iMessage webhook endpoint ──
from endpoints.webhook_sms import router as webhook_sms_router
app.include_router(webhook_sms_router)

settings_store = UISettingsStore(UI_SETTINGS_FILE)
llm_bridge = create_llm_bridge()
_token_warning_logged = False

# ── Memory system (v2 — structured facts + retrieval) ──
_memory_store = MemoryStore()
_fact_extractor = FactExtractor(_memory_store)
_memory_retriever = MemoryRetriever(_memory_store)

# ── Notification stack ──
_notif_db_path = str(SERVER_DIR / "data" / "notifications.db")
os.makedirs(os.path.dirname(_notif_db_path), exist_ok=True)
_notif_store = QueueStore(_notif_db_path)
_notif_dispatcher = NotificationDispatcher(_notif_store)
_delivery_router = DeliveryRouter()
_device_ws = DeviceWSHandler(_notif_dispatcher)

# ── Heartbeat (proactive agent) ──
from heartbeat import (
    start_heartbeat, stop_heartbeat, get_heartbeat_status,
    trigger_action as heartbeat_trigger_action, record_user_activity,
    register_proactive_ws, unregister_proactive_ws,
)

# ── Integration bridge (polls adapters → dispatcher) ──
bluebubbles = BlueBubblesAdapter()
_integration_bridge = IntegrationBridge(
    _notif_dispatcher,
    adapters={
        "bluebubbles": bluebubbles,
        "gmail": GmailAdapter(),
        "vikunja": VikunjaAdapter(),
    },
)

# ── SMS Gateway (iMessage via BlueBubbles) ──
from integrations.sms_gateway import SMSGateway
sms_gateway = SMSGateway()
sms_gateway.register_adapter("imessage", bluebubbles)


async def _integration_poll_loop():
    """Background loop: poll integrations every 30s."""
    while True:
        try:
            await _integration_bridge.poll_once()
        except Exception:
            logging.getLogger(__name__).exception("integration poll error")
        await asyncio.sleep(30)


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

_cors_origins = [
    "http://localhost:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "https://bitos-p8xw.onrender.com",  # companion app
]
_extra_origins = os.environ.get("BITOS_CORS_ORIGINS", "")
if _extra_origins:
    _cors_origins.extend([o.strip() for o in _extra_origins.split(",") if o.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all: log full traceback, return consistent JSON error to device."""
    logger.error(
        "unhandled_exception path=%s method=%s error=%s",
        request.url.path, request.method, exc,
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": str(exc)[:200]},
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


_integration_poll_task = None


@app.on_event("startup")
async def _start_integration_poll():
    global _integration_poll_task
    _integration_poll_task = asyncio.create_task(_integration_poll_loop())
    logger.info("integration_bridge: background poll started (30s interval)")


@app.on_event("startup")
async def _start_heartbeat():
    await start_heartbeat(app)


@app.on_event("shutdown")
async def _stop_heartbeat():
    await stop_heartbeat()


@app.get("/health")
async def health():
    # Check critical components
    checks = {}

    # LLM bridge configured?
    checks["llm"] = bool(llm_bridge and llm_bridge.provider != "echo")

    # Database accessible?
    try:
        with _subtask_db() as conn:
            conn.execute("SELECT 1")
        checks["database"] = True
    except Exception:
        checks["database"] = False

    # API key present?
    checks["api_key"] = _is_real_anthropic_key(os.environ.get("ANTHROPIC_API_KEY", ""))

    overall = "ok" if all(checks.values()) else "degraded"

    return {
        "status": overall,
        "version": __version__,
        "build": __build__,
        "commit": get_git_commit(),
        "provider": llm_bridge.provider,
        "model": llm_bridge.model,
        "settings_file": UI_SETTINGS_FILE,
        "checks": checks,
    }


@app.get("/health/deep")
async def health_deep():
    """Deep health check: probe every integration and subsystem.

    Intended for companion app diagnostics. Not called on every request.
    """
    results = {}

    # LLM provider
    try:
        if hasattr(llm_bridge, "complete_text"):
            llm_bridge.complete_text("Say OK", system_prompt="Reply with exactly: OK")
            results["llm"] = {"ok": True, "provider": llm_bridge.provider, "model": llm_bridge.model}
        else:
            text = "".join(llm_bridge.stream_text("Say OK", system_prompt="Reply with exactly: OK"))
            results["llm"] = {"ok": bool(text), "provider": llm_bridge.provider}
    except Exception as exc:
        results["llm"] = {"ok": False, "error": str(exc)[:100]}

    # Integrations
    for name, AdapterCls in [("imessage", BlueBubblesAdapter), ("vikunja", VikunjaAdapter), ("gmail", GmailAdapter)]:
        try:
            adapter = AdapterCls()
            if hasattr(adapter, "is_mock") and adapter.is_mock:
                results[name] = {"ok": True, "mode": "mock"}
            elif hasattr(adapter, "ping"):
                adapter.ping()
                results[name] = {"ok": True}
            else:
                results[name] = {"ok": True, "mode": "available"}
        except Exception as exc:
            results[name] = {"ok": False, "error": str(exc)[:100]}

    # Database
    try:
        with _subtask_db() as conn:
            count = conn.execute("SELECT COUNT(*) FROM agent_subtasks").fetchone()[0]
        results["database"] = {"ok": True, "subtask_count": count}
    except Exception as exc:
        results["database"] = {"ok": False, "error": str(exc)[:100]}

    overall = "ok" if all(r.get("ok", False) for r in results.values()) else "degraded"
    return {"status": overall, "checks": results, "version": __version__}


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
    elif integration == "anthropic":
        api_key = str(config.get("api_key", "")).strip()
        if not api_key:
            return {"ok": False, "error": "API key required"}
        updates = {"ANTHROPIC_API_KEY": api_key}
    elif integration == "gmail":
        enabled = config.get("enabled")
        updates = {"GMAIL_ENABLED": "true" if enabled else "false"}
    else:
        raise HTTPException(status_code=400, detail="Unknown integration")

    _persist_integration_settings(updates)
    ok, error = _test_integration_connection(integration, config)
    if not ok:
        return {"ok": False, "error": error}
    return {"ok": True}


# ── Device settings (synced from device via chat requests) ──────────────
_device_settings_cache: dict = {}
_device_settings_lock = threading.Lock()


def _update_device_settings_cache(settings: dict) -> None:
    """Update cached device settings from the latest chat request."""
    with _device_settings_lock:
        _device_settings_cache.update(settings)


@app.get("/settings/device")
async def get_device_settings():
    """Return last-known device settings (synced from device via chat requests)."""
    with _device_settings_lock:
        return dict(_device_settings_cache)


@app.put("/settings/device")
async def update_device_settings(request: Request):
    """Queue a device setting change. Applied when device next connects."""
    patch = await request.json()
    if not isinstance(patch, dict) or "key" not in patch or "value" not in patch:
        raise HTTPException(status_code=400, detail="Requires {key, value}")

    from agent_tools import validate_setting
    ok, error, coerced = validate_setting(patch["key"], patch["value"])
    if not ok:
        raise HTTPException(status_code=422, detail=error)

    # Store in pending queue for device to pick up
    with _device_settings_lock:
        if "_pending_changes" not in _device_settings_cache:
            _device_settings_cache["_pending_changes"] = []
        _device_settings_cache["_pending_changes"].append({"key": patch["key"], "value": coerced})
        _device_settings_cache[patch["key"]] = coerced

    return {"ok": True, "key": patch["key"], "value": coerced}


@app.get("/settings/device/pending")
async def get_pending_device_settings():
    """Return and clear pending setting changes for the device to apply."""
    with _device_settings_lock:
        pending = _device_settings_cache.pop("_pending_changes", [])
    return {"changes": pending}


@app.get("/settings/voices")
async def get_voice_catalog():
    """Return available TTS voices and per-engine parameters."""
    from voice_catalog import build_catalog
    with _device_settings_lock:
        engine = _device_settings_cache.get("tts_engine", "auto")
        voice_id = _device_settings_cache.get("voice_id", "")
        params_raw = _device_settings_cache.get("voice_params", "{}")
    import json
    try:
        params = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
    except (json.JSONDecodeError, TypeError):
        params = {}
    return build_catalog(current_engine=engine, current_voice_id=voice_id, current_params=params)


@app.post("/settings/device/test-voice")
async def test_voice_on_device(request: Request):
    """Queue a voice test command for the device to play."""
    body = await request.json()
    text = body.get("text", "Hello! This is how I sound.")
    engine = body.get("engine", "auto")
    voice_id = body.get("voice_id", "")
    params = body.get("params", {})
    import json

    with _device_settings_lock:
        if "_pending_changes" not in _device_settings_cache:
            _device_settings_cache["_pending_changes"] = []
        _device_settings_cache["_pending_changes"].append({
            "key": "_test_voice",
            "value": json.dumps({"text": text, "engine": engine, "voice_id": voice_id, "params": params}),
        })
    return {"ok": True, "queued": "test_voice"}


@app.post("/settings/device/test-typewriter")
async def test_typewriter_on_device(request: Request):
    """Queue a typewriter test command for the device to render."""
    body = await request.json()
    text = body.get("text", "The quick brown fox jumps over the lazy dog.")
    config = body.get("config", {})
    import json

    with _device_settings_lock:
        if "_pending_changes" not in _device_settings_cache:
            _device_settings_cache["_pending_changes"] = []
        _device_settings_cache["_pending_changes"].append({
            "key": "_test_typewriter",
            "value": json.dumps({"text": text, "config": config}),
        })
    return {"ok": True, "queued": "test_typewriter"}


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




@app.get("/calendar")
async def get_calendar_events_endpoint(days: int = 7):
    """Return upcoming calendar events from macOS Calendar via AppleScript."""
    days = min(max(1, days), 14)

    script = f'''
set now to current date
set endDate to now + ({days} * days)
tell application "Calendar"
    set output to ""
    set allCals to every calendar
    repeat with cal in allCals
        set calName to name of cal
        try
            set eventList to (every event of cal whose start date >= now and start date <= endDate)
            repeat with ev in eventList
                set output to output & "---" & linefeed
                set output to output & "calendar: " & calName & linefeed
                set output to output & "title: " & (summary of ev) & linefeed
                set output to output & "start: " & ((start date of ev) as string) & linefeed
                set output to output & "end: " & ((end date of ev) as string) & linefeed
                set evLoc to location of ev
                if evLoc is not missing value then
                    set output to output & "location: " & evLoc & linefeed
                end if
                set evNotes to description of ev
                if evNotes is not missing value then
                    if length of evNotes > 100 then
                        set evNotes to text 1 thru 100 of evNotes
                    end if
                    set output to output & "notes: " & evNotes & linefeed
                end if
            end repeat
        end try
    end repeat
    return output
end tell
'''
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return JSONResponse(
                status_code=502,
                content={"error": f"Calendar read failed: {result.stderr.strip()[:100]}"},
            )

        events = []
        for block in result.stdout.split("---"):
            block = block.strip()
            if not block:
                continue
            event = {}
            for line in block.split("\n"):
                if ": " in line:
                    key, val = line.split(": ", 1)
                    event[key.strip()] = val.strip()
            if event and event.get("title"):
                events.append(event)

        # Sort by start time
        events.sort(key=lambda e: e.get("start", ""))
        return {"events": events, "count": len(events), "days": days}
    except Exception as exc:
        logger.error("calendar_endpoint_failed: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": f"Calendar unavailable: {str(exc)[:100]}"},
        )


@app.get("/tasks/today")
async def get_today_tasks():
    """Get tasks due today or overdue (backward-compatible endpoint)."""
    try:
        import task_store
        tasks = task_store.get_today_tasks()
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as exc:
        logger.error("tasks_today_failed: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": "Tasks unavailable", "detail": str(exc)[:100]},
        )


@app.get("/tasks/overdue")
async def get_overdue_tasks_endpoint():
    try:
        import task_store
        tasks = task_store.get_overdue_tasks()
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as exc:
        logger.error("tasks_overdue_failed: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": "Tasks unavailable", "detail": str(exc)[:100]},
        )


@app.get("/tasks/{task_id}")
async def get_task_endpoint(task_id: str):
    try:
        import task_store
        task = task_store.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task_get_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


@app.get("/tasks")
async def list_tasks_endpoint(
    request: Request,
    status: str | None = None,
    project: str | None = None,
    due_before: str | None = None,
    due_after: str | None = None,
    q: str | None = None,
    parent_id: str | None = None,
    limit: int = 50,
):
    try:
        import task_store
        pid = parent_id if parent_id is not None else "TOP_LEVEL"
        tasks = task_store.list_tasks(
            status=status,
            project=project,
            due_before=due_before,
            due_after=due_after,
            query=q,
            parent_id=pid,
            limit=min(limit, 100),
        )
        return {"tasks": tasks, "count": len(tasks)}
    except Exception as exc:
        logger.error("tasks_list_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


class TaskCreateRequest(BaseModel):
    title: str
    notes: str = ""
    priority: int = 3
    due_date: str | None = None
    due_time: str | None = None
    reminder_at: str | None = None
    project: str = "INBOX"
    tags: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    source: str = "companion"


@app.post("/tasks")
async def create_task_endpoint(body: TaskCreateRequest):
    try:
        import task_store
        task = task_store.create_task(
            title=body.title,
            notes=body.notes,
            priority=body.priority,
            due_date=body.due_date,
            due_time=body.due_time,
            reminder_at=body.reminder_at,
            project=body.project,
            tags=body.tags,
            parent_id=body.parent_id,
            source=body.source,
        )
        return task
    except Exception as exc:
        logger.error("task_create_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    notes: str | None = None
    priority: int | None = None
    status: str | None = None
    due_date: str | None = None
    due_time: str | None = None
    reminder_at: str | None = None
    project: str | None = None
    tags: list[str] | None = None


@app.put("/tasks/{task_id}")
async def update_task_endpoint(task_id: str, body: TaskUpdateRequest):
    try:
        import task_store
        fields = {k: v for k, v in body.model_dump().items() if v is not None}
        task = task_store.update_task(task_id, **fields)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task_update_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


@app.delete("/tasks/{task_id}")
async def delete_task_endpoint(task_id: str):
    try:
        import task_store
        ok = task_store.delete_task(task_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"ok": True, "task_id": task_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task_delete_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


@app.post("/tasks/{task_id}/complete")
async def complete_task_endpoint(task_id: str):
    try:
        import task_store
        task = task_store.complete_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        return task
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("task_complete_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


@app.get("/living-doc")
async def get_living_doc_endpoint():
    try:
        import task_store
        doc = task_store.get_living_doc()
        if not doc:
            return {"document": None}
        return {"document": doc}
    except Exception as exc:
        logger.error("living_doc_get_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


class LivingDocRequest(BaseModel):
    content: str
    title: str = "Weekly Plan"


@app.put("/living-doc")
async def update_living_doc_endpoint(body: LivingDocRequest):
    try:
        import task_store
        doc = task_store.update_living_doc(content=body.content, title=body.title)
        return {"document": doc}
    except Exception as exc:
        logger.error("living_doc_update_failed: %s", exc)
        return JSONResponse(status_code=500, content={"error": str(exc)[:100]})


@app.get("/messages")
async def get_messages_conversations():
    try:
        adapter = BlueBubblesAdapter()
        return {
            "conversations": adapter.get_conversations(),
            "unread_total": adapter.get_unread_count(),
        }
    except Exception as exc:
        logger.error("messages_conversations_failed: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": "Messages unavailable", "detail": str(exc)[:100]},
        )


@app.get("/mail")
async def get_mail_threads():
    try:
        adapter = GmailAdapter()
        return {
            "threads": adapter.get_inbox(limit=10),
            "unread_total": adapter.get_unread_count(),
        }
    except Exception as exc:
        logger.error("mail_threads_failed: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"error": "Mail unavailable", "detail": str(exc)[:100]},
        )


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
        raw = repo.get_setting("battery_pct", None)
        if raw is not None and str(raw) not in ("-1", ""):
            pct = max(0, min(100, int(raw)))
            present = True
        else:
            pct = None
            present = False
        charging = str(repo.get_setting("charging", "false")).lower() == "true"
        return {"pct": pct, "charging": charging, "present": present}
    except Exception:
        return {"pct": None, "charging": False, "present": False}

@app.get("/dashboard")
async def get_dashboard():
    """Aggregated snapshot for device home screen: time, tasks, messages, mail, system."""
    now = datetime.now(timezone.utc)

    # Tasks
    try:
        import task_store
        tasks = task_store.get_today_tasks()
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
    battery_pct = None
    charging = False
    try:
        from device.storage.repository import DeviceRepository
        repo = DeviceRepository()
        raw = repo.get_setting("battery_pct", None)
        if raw is not None and str(raw) not in ("-1", ""):
            battery_pct = max(0, min(100, int(raw)))
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


@app.get("/notifications/summary")
async def get_notifications_summary():
    """'What did I miss?' — voice-friendly summary of pending notifications.

    Returns a summary string suitable for TTS readout plus per-item details.
    """
    pending = _notif_store.get_pending()
    summary = build_summary(pending)
    details = build_detail(pending, max_items=5)
    return {
        "count": len(pending),
        "summary": summary,
        "details": details,
    }


@app.get("/activity/notifications")
async def get_activity_notifications():
    """Unified notification feed: recent messages, emails, tasks, events — for device notification view."""
    items: list[dict] = []

    # Recent iMessages
    try:
        bb = BlueBubblesAdapter()
        conversations = bb.get_conversations(limit=5)
        for conv in conversations:
            if conv.get("unread", 0) > 0:
                items.append({
                    "type": "SMS",
                    "source": conv.get("title", "Unknown"),
                    "preview": conv.get("snippet", "")[:60],
                    "time": conv.get("timestamp", ""),
                    "unread": True,
                    "source_id": conv.get("chat_id", ""),
                })
    except Exception:
        pass

    # Recent emails
    try:
        gmail = GmailAdapter()
        inbox = gmail.get_inbox(limit=5)
        for email in inbox:
            if email.get("unread"):
                items.append({
                    "type": "MAIL",
                    "source": email.get("sender", "Unknown"),
                    "preview": email.get("subject", "")[:60],
                    "time": email.get("timestamp", ""),
                    "unread": True,
                    "source_id": email.get("thread_id", ""),
                })
    except Exception:
        pass

    # Today's tasks
    try:
        import task_store
        tasks = task_store.get_today_tasks()
        for task in tasks[:3]:
            items.append({
                "type": "TASK",
                "source": str(task.get("project", "INBOX")),
                "preview": str(task.get("title", ""))[:60],
                "time": "today",
                "unread": not task.get("done", False),
                "source_id": str(task.get("id", "")),
            })
    except Exception:
        pass

    # Upcoming calendar events (via AppleScript on server mac)
    try:
        import subprocess
        script = '''
set now to current date
set endDate to now + (1 * days)
tell application "Calendar"
    set output to ""
    set eventList to (every event whose start date >= now and start date <= endDate)
    set maxCount to count of eventList
    if maxCount > 5 then set maxCount to 5
    repeat with i from 1 to maxCount
        set ev to item i of eventList
        set output to output & (summary of ev) & "|" & ((start date of ev) as string) & linefeed
    end repeat
    return output
end tell
'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                if "|" in line:
                    title, start = line.split("|", 1)
                    items.append({
                        "type": "CALENDAR",
                        "source": "Calendar",
                        "preview": title.strip()[:60],
                        "time": start.strip(),
                        "unread": True,
                        "source_id": "",
                    })
    except Exception:
        pass

    return {"items": items, "count": len(items)}


# ── Live Context Endpoint ────────────────────────────────────────────────

def _fetch_weather(location: str = "Los+Angeles") -> str:
    """Fetch current weather from wttr.in (no API key needed).

    Returns a string like '+72°F Sunny' or empty string on failure.
    """
    import httpx as _httpx
    try:
        resp = _httpx.get(
            f"https://wttr.in/{location}?format=%t+%C",
            timeout=5.0,
            headers={"User-Agent": "bitos/1.0"},
        )
        if resp.status_code == 200:
            text = resp.text.strip()
            # wttr.in returns e.g. "+72°F Sunny" — strip leading +
            if text.startswith("+"):
                text = text[1:]
            return text
    except Exception as exc:
        logger.debug("weather_fetch_failed: %s", exc)
    return ""


def _fetch_next_event() -> str:
    """Get the next upcoming calendar event via AppleScript (macOS only).

    Returns e.g. '10:30 AM Meeting with John' or empty string.
    """
    try:
        script = '''
set now to current date
set endDate to now + (1 * days)
tell application "Calendar"
    set eventList to (every event whose start date >= now and start date <= endDate)
    if (count of eventList) = 0 then return ""
    -- Find earliest
    set earliest to item 1 of eventList
    repeat with ev in eventList
        if (start date of ev) < (start date of earliest) then
            set earliest to ev
        end if
    end repeat
    set t to time string of (start date of earliest)
    return t & " " & (summary of earliest)
end tell
'''
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            raw = result.stdout.strip()
            # Shorten "10:30:00 AM" → "10:30a"
            parts = raw.split(" ", 2)
            if len(parts) >= 3:
                time_part = parts[0].rsplit(":", 1)[0]  # drop seconds
                ampm = parts[1].lower().rstrip("m")  # AM→a, PM→p
                title = parts[2]
                return f"{time_part}{ampm} {title}"
            return raw
    except Exception as exc:
        logger.debug("next_event_fetch_failed: %s", exc)
    return ""


def _fetch_headlines() -> list[str]:
    """Fetch a few top headlines from an RSS feed (BBC World, no key needed).

    Returns up to 3 short headline strings.
    """
    import httpx as _httpx
    try:
        resp = _httpx.get(
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            timeout=5.0,
            headers={"User-Agent": "bitos/1.0"},
        )
        if resp.status_code != 200:
            return []
        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.text)
        titles: list[str] = []
        for item in root.iter("item"):
            title_el = item.find("title")
            if title_el is not None and title_el.text:
                titles.append(title_el.text.strip())
            if len(titles) >= 3:
                break
        return titles
    except Exception as exc:
        logger.debug("headlines_fetch_failed: %s", exc)
    return []


@app.get("/context")
async def get_live_context():
    """Aggregated live context for the device home screen ticker.

    Returns weather, headlines, next calendar event, task count,
    and unread message/email counts — all best-effort with fallbacks.
    """
    import concurrent.futures

    weather = ""
    headlines: list[str] = []
    next_event = ""
    tasks_today = 0
    unread_msgs = 0
    unread_mail = 0

    # Fetch weather, headlines, and next event in parallel threads
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        weather_future = pool.submit(_fetch_weather)
        headlines_future = pool.submit(_fetch_headlines)
        event_future = pool.submit(_fetch_next_event)

        try:
            weather = weather_future.result(timeout=8)
        except Exception:
            pass
        try:
            headlines = headlines_future.result(timeout=8)
        except Exception:
            pass
        try:
            next_event = event_future.result(timeout=12)
        except Exception:
            pass

    # Task count from task store
    try:
        import task_store
        tasks = task_store.get_today_tasks()
        tasks_today = len(tasks)
    except Exception:
        pass

    # Unread messages from BlueBubbles
    try:
        bb = BlueBubblesAdapter()
        unread_msgs = bb.get_unread_count()
    except Exception:
        pass

    # Unread emails from Gmail
    try:
        gmail = GmailAdapter()
        unread_mail = gmail.get_unread_count()
    except Exception:
        pass

    return {
        "weather": weather,
        "headlines": headlines,
        "next_event": next_event,
        "tasks_today": tasks_today,
        "unread_msgs": unread_msgs,
        "unread_mail": unread_mail,
    }


@app.get("/brief")
async def get_brief():
    """Morning-brief summary: tasks, unread counts, weather-ready structure."""
    try:
        import task_store
        tasks = task_store.get_today_tasks()
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


# ── Agent Subtask Endpoints ──────────────────────────────────────────────
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
async def list_files(path: str = "", limit: int = 50):
    """List directories and files in the curated file system.

    Directories are listed first (type="dir" with item_count),
    then files sorted alphabetically by name.
    """
    scan_dir = BITOS_FILES_DIR / path
    if not _is_safe_path(BITOS_FILES_DIR, scan_dir):
        raise HTTPException(status_code=400, detail="Invalid path")
    if not scan_dir.is_dir():
        return {"files": [], "path": path}

    dirs: list[dict] = []
    files: list[dict] = []
    for entry in sorted(scan_dir.iterdir(), key=lambda p: p.name.lower()):
        if entry.name.startswith("."):
            continue
        if entry.is_dir():
            # Count visible items inside
            try:
                item_count = sum(
                    1 for child in entry.iterdir()
                    if not child.name.startswith(".")
                    and (child.is_dir() or child.suffix.lower() in _ALLOWED_EXTENSIONS)
                )
            except OSError:
                item_count = 0
            rel = entry.relative_to(BITOS_FILES_DIR)
            dirs.append({
                "id": _file_id_encode(str(rel)),
                "name": entry.name,
                "path": str(rel),
                "type": "dir",
                "item_count": item_count,
            })
        elif entry.is_file() and entry.suffix.lower() in _ALLOWED_EXTENSIONS:
            rel = entry.relative_to(BITOS_FILES_DIR)
            file_type = "markdown" if entry.suffix.lower() == ".md" else "text"
            files.append({
                "id": _file_id_encode(str(rel)),
                "name": entry.stem,
                "path": str(rel),
                "size": entry.stat().st_size,
                "type": file_type,
            })

    combined = dirs + files
    return {"files": combined[:limit], "path": path}


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


class FileQueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


@app.post("/files/{file_id}/query")
async def query_file(file_id: str, req: FileQueryRequest):
    """Answer a question about a file using LLM context."""
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
        f"Document: {title}\n\n{content[:4000]}\n\n"
        f"Question: {req.question}\n\n"
        f"Answer concisely in 2-3 sentences (under 300 characters). "
        f"This will be displayed on a tiny OLED screen."
    )

    try:
        complete_text = getattr(llm_bridge, "complete_text", None)
        if callable(complete_text):
            answer = complete_text(prompt)
        else:
            answer = "".join(llm_bridge.stream_text(prompt))
        answer = answer.strip()
    except Exception as exc:
        logger.warning("file_query_llm_failed: %s", exc)
        raise HTTPException(status_code=502, detail="LLM query failed")

    return {"answer": answer, "file_id": file_id, "question": req.question}


# ── Heartbeat Endpoints ─────────────────────────────────────────────


@app.get("/heartbeat/status")
async def heartbeat_status():
    """Current heartbeat state, scheduled actions, and recent log."""
    return get_heartbeat_status()


@app.post("/heartbeat/trigger/{action}")
async def heartbeat_trigger(action: str):
    """Manually trigger a heartbeat action for testing."""
    result = await heartbeat_trigger_action(action)
    return result


@app.post("/shutdown")
async def shutdown():
    """Graceful shutdown hook for device power gesture flow."""
    logging.info("[BITOS] shutdown requested")
    return {"status": "ok"}


class ApprovalResponse(BaseModel):
    request_id: str
    choice: str


@app.post("/chat/approval")
async def submit_approval(payload: ApprovalResponse):
    """Device submits user's choice for a blocking approval request."""
    from agent_tools import resolve_approval
    ok = resolve_approval(payload.request_id, payload.choice)
    if not ok:
        raise HTTPException(status_code=404, detail="No pending approval with that ID")
    return {"ok": True, "request_id": payload.request_id, "choice": payload.choice}


@app.post("/chat")
async def chat(payload: ChatRequest):
    """Stream model response from the active LLM bridge as SSE."""
    message = payload.message
    if not message:
        raise HTTPException(status_code=400, detail="No message provided")

    agent_mode = payload.agent_mode or "producer"

    # Record user activity for heartbeat idle tracking
    record_user_activity()

    # Fetch lightweight activity counts for agent notification awareness
    activity_summary = None
    try:
        bb = BlueBubblesAdapter()
        gmail = GmailAdapter()
        activity_summary = {
            "messages_unread": bb.get_unread_count(),
            "emails_unread": gmail.get_unread_count(),
        }
    except Exception:
        pass

    system_prompt = get_system_prompt(
        agent_mode,
        tasks_today=payload.tasks_today,
        battery_pct=payload.battery_pct,
        web_search=payload.web_search,
        memory=payload.memory,
        location=payload.location,
        response_format_hint=payload.response_format_hint,
        activity_summary=activity_summary,
        meta_prompt=payload.meta_prompt,
    )

    # ── Inject long-term memory facts into system prompt ──
    if payload.memory:
        try:
            # Use new ranked retriever (falls back to FTS5 search)
            ranked_facts = _memory_retriever.retrieve_for_context(message, limit=10)
            if ranked_facts:
                facts_lines = [f"- {f}" for f in ranked_facts]
                system_prompt += (
                    "\n\nMEMORY (things I know about you):\n"
                    + "\n".join(facts_lines)
                )
            else:
                # Fallback to legacy store if retriever returns nothing
                memory_facts = search_facts(message, limit=10)
                if memory_facts:
                    facts_lines = [f"- {f['content']}" for f in memory_facts]
                    system_prompt += (
                        "\n\nMEMORY (things I know about you):\n"
                        + "\n".join(facts_lines)
                    )
        except Exception as mem_exc:
            logger.warning("Memory retrieval failed (non-critical): %s", mem_exc)

    # ── Inject now-playing music context ──
    try:
        from integrations.spotify_adapter import get_spotify
        _sp = get_spotify()
        if _sp.available:
            _np = _sp.get_now_playing()
            if _np and _np.get("is_playing"):
                _prog = _np["progress_ms"] // 1000
                _dur = _np["duration_ms"] // 1000
                system_prompt += (
                    f"\n\n[NOW PLAYING] {_np['track']} by {_np['artist']} "
                    f"({_np['album']}) "
                    f"— {_prog // 60}:{_prog % 60:02d}/{_dur // 60}:{_dur % 60:02d}"
                )
    except Exception:
        pass  # Spotify context is optional, never block chat

    # Map short model names to full Anthropic model IDs
    _MODEL_MAP = {
        "haiku": "claude-haiku-4-5-20251001",
        "sonnet": "claude-sonnet-4-6",
        "opus": "claude-opus-4-6",
    }
    raw_model = (payload.model or "").strip().lower()
    model_override = _MODEL_MAP.get(raw_model, payload.model) if raw_model and raw_model != "default" else None

    # Build device settings snapshot for agent tools
    device_settings = {
        "volume": payload.volume,
        "voice_enabled": payload.voice_enabled,
        "voice_mode": payload.voice_mode,
        "web_search": payload.web_search,
        "memory": payload.memory,
        "extended_thinking": payload.extended_thinking,
        "agent_mode": agent_mode,
        "ai_model": payload.model or "default",
    }

    # Sync device settings to server cache (for companion app)
    _update_device_settings_cache(device_settings)

    # ── Perception classifier (Haiku pre-call) ──
    loop = asyncio.get_event_loop()
    perception = await loop.run_in_executor(
        None, lambda: classify_perception(message, agent_mode=agent_mode)
    )

    # Add response hint from perception to system prompt
    _hint_map = {"brief": "Keep your response to 1-2 sentences.", "detailed": "Give a thorough response."}
    if perception.response_hint in _hint_map:
        system_prompt += f"\n\n{_hint_map[perception.response_hint]}"

    # Only include tools when perception says they're needed
    use_tools = perception.needs_tools

    # ── Conversation history ──
    conv_id = payload.conversation_id
    if conv_id:
        history = get_conv_messages(conv_id)
    else:
        history = []

    # Build message list with history for multi-turn
    history_messages = [{"role": m["role"], "content": m["content"]} for m in history]

    def stream_response():
        from agent_tools import DEVICE_TOOLS

        # Filter tools based on user settings
        active_tools = DEVICE_TOOLS
        if not payload.web_search:
            active_tools = [t for t in active_tools if t["name"] != "web_search"]
        if not payload.memory:
            active_tools = [
                t for t in active_tools
                if t["name"] not in ("remember_fact", "recall_facts")
            ]

        full_response_parts: list[str] = []

        # Use tool-aware streaming for Anthropic provider
        if hasattr(llm_bridge, "stream_with_tools") and use_tools:
            setting_changes: list[dict] = []

            gen = llm_bridge.stream_with_tools(
                message,
                tools=active_tools,
                tool_handler=None,  # handled internally
                device_settings=device_settings,
                system_prompt=system_prompt,
                model_override=model_override,
                extended_thinking=payload.extended_thinking,
                messages=history_messages if history_messages else None,
            )

            # Consume generator — yields text (str) or SSE event dicts
            try:
                while True:
                    chunk = next(gen)
                    if isinstance(chunk, dict):
                        # Special SSE event (e.g., approval_request)
                        yield f"data: {json.dumps(chunk)}\n\n"
                    else:
                        full_response_parts.append(chunk)
                        yield to_sse_data(chunk)
            except StopIteration as e:
                setting_changes = e.value or []
            except Exception as tool_exc:
                logger.error("[BITOS] Tool-use chat failed: %s", tool_exc)
                from security import sanitize_tool_error
                yield to_sse_data(f"[Error: {sanitize_tool_error(tool_exc)}]")

            # Emit setting changes as SSE events for the device to apply
            for change in setting_changes:
                yield f"data: {json.dumps({'setting_change': change})}\n\n"
        else:
            # No tools needed — use faster streaming path
            for text in llm_bridge.stream_text(
                message,
                system_prompt=system_prompt,
                model_override=model_override,
                extended_thinking=payload.extended_thinking,
                messages=history_messages if history_messages else None,
            ):
                full_response_parts.append(text)
                yield to_sse_data(text)

        # ── Save conversation turn ──
        nonlocal conv_id
        full_response = "".join(full_response_parts)
        if full_response.strip():
            if not conv_id:
                conv_id = create_conversation()
            add_message(conv_id, "user", message)
            add_message(conv_id, "assistant", full_response)

            # ── Background fact extraction (non-blocking) ──
            if payload.memory:
                try:
                    _msg, _resp, _cid = message, full_response, conv_id
                    # Legacy extractor (per-turn)
                    threading.Thread(
                        target=extract_and_store_facts,
                        args=(_msg, _resp, _cid),
                        daemon=True,
                    ).start()
                    # New batch extractor — buffer turn, extract every 8 turns
                    _fact_extractor.add_turn(_msg, _resp)
                    if _fact_extractor.should_extract():
                        threading.Thread(
                            target=_fact_extractor.extract_now,
                            args=(_cid,),
                            daemon=True,
                        ).start()
                except Exception:
                    pass  # Never let extraction failure affect chat

        # Emit conversation_id so client can continue the conversation
        if conv_id:
            yield f"data: {json.dumps({'conversation_id': conv_id})}\n\n"

        # Emit perception metadata for device-side use
        yield f"data: {json.dumps({'perception': perception.raw})}\n\n"
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
        logger.error("[BITOS] Chat stream failed: %s", exc, exc_info=True)
        return JSONResponse(
            status_code=502,
            content={"error": "Chat failed", "detail": str(exc)[:200]},
        )


# ── Conversation history endpoints ────────────────────────────────────


@app.get("/conversations")
async def conversations_list(limit: int = 20):
    """Return recent conversations with message count and preview."""
    return {"conversations": list_conversations(limit=min(limit, 100))}


@app.get("/conversations/{conv_id}")
async def conversation_detail(conv_id: str):
    """Return full message history for a conversation."""
    conv = get_conversation(conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conv


# ── Memory endpoints ─────────────────────────────────────────────────────


class ManualFactRequest(BaseModel):
    content: str
    category: str = "general"
    confidence: float = 0.8


@app.get("/memory")
async def memory_list(category: str = "", limit: int = 20):
    """List recent memory facts, optionally filtered by category."""
    if category:
        facts = get_facts_by_category(category)
    else:
        facts = get_recent_facts(limit=min(limit, 100))
    return {"facts": facts, "count": len(facts)}


@app.get("/memory/search")
async def memory_search(q: str = "", limit: int = 10):
    """Search memory facts by keyword."""
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    results = search_facts(q, limit=min(limit, 50))
    return {"facts": results, "count": len(results), "query": q}


@app.delete("/memory/{fact_id}")
async def memory_delete(fact_id: int):
    """Soft-delete (deactivate) a memory fact."""
    ok = deactivate_fact(fact_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Fact not found")
    return {"success": True, "id": fact_id}


@app.post("/memory")
async def memory_add(payload: ManualFactRequest):
    """Manually add a fact to long-term memory."""
    if not payload.content.strip():
        raise HTTPException(status_code=400, detail="Content is required")
    fact_id = add_fact(
        content=payload.content,
        source="manual",
        confidence=payload.confidence,
        category=payload.category,
    )
    return {"success": True, "id": fact_id}


# ── Memory v2 endpoints (structured store + retriever) ────────────────


@app.get("/memory/v2")
async def memory_v2_list(category: str = "", limit: int = 20):
    """List memory facts from the structured store, optionally by category."""
    if category:
        facts = _memory_store.get_facts_by_category(category)
    else:
        facts = _memory_store.get_recent_facts(limit=min(limit, 100))
    return {"facts": facts, "count": len(facts), "version": 2}


@app.get("/memory/v2/search")
async def memory_v2_search(q: str = "", limit: int = 10):
    """Ranked memory search using retriever (FTS5 + recency + frequency)."""
    if not q:
        raise HTTPException(status_code=400, detail="Query parameter 'q' is required")
    results = _memory_retriever.retrieve(q, limit=min(limit, 50))
    return {"facts": results, "count": len(results), "query": q, "version": 2}


@app.get("/memory/v2/stats")
async def memory_v2_stats():
    """Memory system statistics."""
    return {
        "total_facts": _memory_store.count_facts(active_only=True),
        "total_all": _memory_store.count_facts(active_only=False),
        "episodes": len(_memory_store.get_episodes(limit=1000)),
        "has_vector_search": _memory_store.has_vector_search,
        "extractor_buffered_turns": _fact_extractor.turn_count,
    }


@app.get("/logs")
async def get_logs(lines: int = 100, level: str = ""):
    """Return recent log lines for remote debugging.

    Query params:
      lines: number of lines to return (default 100, max 500)
      level: optional filter — "ERROR", "WARNING", etc.
    """
    lines = min(max(1, lines), 500)
    log_dir = os.environ.get("BITOS_LOG_DIR", str(ROOT_DIR / "logs"))
    log_path = os.path.join(log_dir, "server.log")

    if not os.path.exists(log_path):
        return {"lines": [], "path": log_path, "exists": False}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        # Filter by level if requested
        if level:
            level_upper = level.upper()
            all_lines = [ln for ln in all_lines if level_upper in ln]

        recent = all_lines[-lines:]
        return {
            "lines": [ln.rstrip() for ln in recent],
            "total_lines": len(all_lines),
            "path": log_path,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Cannot read logs: {exc}"},
        )


@app.get("/logs/device")
async def get_device_logs(lines: int = 100, level: str = ""):
    """Return recent device log lines (if server and device share filesystem)."""
    lines = min(max(1, lines), 500)
    log_path = "/var/log/bitos/device.log"

    if not os.path.exists(log_path):
        return {"lines": [], "path": log_path, "exists": False}

    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()

        if level:
            level_upper = level.upper()
            all_lines = [ln for ln in all_lines if level_upper in ln]

        recent = all_lines[-lines:]
        return {
            "lines": [ln.rstrip() for ln in recent],
            "total_lines": len(all_lines),
            "path": log_path,
        }
    except Exception as exc:
        return JSONResponse(
            status_code=500,
            content={"error": f"Cannot read device logs: {exc}"},
        )


# ── WebSocket: device notification push ──────────────────────────────

@app.websocket("/ws/device")
async def ws_device(ws: WebSocket, device_id: str = "default"):
    """Real-time notification push to BITOS hardware devices."""
    # Check device token for WebSocket connections
    expected_token = os.environ.get("BITOS_DEVICE_TOKEN", "")
    if expected_token:
        # WebSocket clients send token as query param: ?token=xxx
        provided = ws.query_params.get("token", "")
        if provided != expected_token:
            await ws.close(code=1008)  # Policy Violation
            return
    await ws.accept()
    _device_ws.register(ws, device_id)
    logger.info("[WS] Device %s connected to /ws/device", device_id)
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "reconnect":
                last_ts = data.get("last_event_ts", 0.0)
                _device_ws.handle_reconnect(ws, last_ts=last_ts)
            else:
                _device_ws.handle_message(data)
    except WebSocketDisconnect:
        logger.info("[WS] Device %s disconnected", device_id)
    except Exception as exc:
        logger.warning("[WS] Device %s error: %s", device_id, exc)
    finally:
        _device_ws.unregister(device_id)


# ── Quick Actions ────────────────────────────────────────────────────
from activity_feed import (
    log_activity,
    update_activity,
    get_recent as get_recent_activities,
    get_by_type as get_activities_by_type,
    get_by_id as get_activity_by_id,
    register_ws as register_activity_ws,
    unregister_ws as unregister_activity_ws,
)

QUICK_ACTIONS = {
    "check_messages": {"tool": "read_imessages", "input": {"limit": 5}, "label": "Check Messages"},
    "check_email": {"tool": "read_emails", "input": {"limit": 5, "unread_only": True}, "label": "Check Email"},
    "today_tasks": {"tool": "get_tasks", "input": {"filter": "today"}, "label": "Today's Tasks"},
    "today_calendar": {"tool": "get_calendar_events", "input": {"days_ahead": 1}, "label": "Today's Calendar"},
    "battery_status": {"tool": "get_device_settings", "input": {}, "label": "Device Status"},
    "send_daily_summary": {
        "label": "Daily Summary",
        "type": "llm_prompt",
        "prompt": "Give me a brief daily summary: tasks, unread messages, calendar events for today.",
    },
}


class QuickActionRequest(BaseModel):
    action: str = Field(..., description="Quick action name to execute")


@app.get("/actions")
async def list_quick_actions():
    """List all available quick actions."""
    actions = []
    for key, config in QUICK_ACTIONS.items():
        actions.append({
            "name": key,
            "label": config.get("label", key),
            "type": config.get("type", "tool"),
        })
    return {"actions": actions, "count": len(actions)}


@app.post("/actions/run")
async def run_quick_action(payload: QuickActionRequest):
    """Execute a quick action by name, log to activity feed."""
    action_name = payload.action
    config = QUICK_ACTIONS.get(action_name)
    if not config:
        raise HTTPException(status_code=404, detail=f"Unknown action: {action_name}")

    # Create activity entry
    activity_id = log_activity(
        "quick_action",
        config.get("label", action_name),
        metadata={"action": action_name, "config": config},
    )
    update_activity(activity_id, "running")

    try:
        if config.get("type") == "llm_prompt":
            # Run through LLM
            prompt = config["prompt"]
            text = ""
            for chunk in llm_bridge.stream_text(prompt):
                text += chunk
            result = {"type": "llm_response", "text": text}
        else:
            # Run as tool call
            from agent_tools import _handle_tool_call_inner
            tool_name = config["tool"]
            tool_input = config.get("input", {})

            # Build minimal device settings from cache
            device_settings = dict(_device_settings_cache)
            setting_changes: list[dict] = []

            raw = _handle_tool_call_inner(
                tool_name, tool_input, device_settings, setting_changes
            )
            result = {"type": "tool_result", "tool": tool_name, "data": json.loads(raw)}

        update_activity(activity_id, "done", result=json.dumps(result)[:500])
        return {"ok": True, "action": action_name, "activity_id": activity_id, "result": result}

    except Exception as exc:
        update_activity(activity_id, "failed", result=str(exc)[:500])
        logger.error("quick_action_failed: %s error=%s", action_name, exc)
        raise HTTPException(status_code=500, detail=f"Action failed: {exc}")


# ── Activity Feed Endpoints ──────────────────────────────────────────

@app.get("/activity")
async def get_activity_feed(type: str = "", limit: int = 50):
    """Recent agent activity log with optional type filter."""
    if type:
        items = get_activities_by_type(type, limit=limit)
    else:
        items = get_recent_activities(limit=limit)
    return {"activities": items, "count": len(items)}


@app.get("/activity/{activity_id}")
async def get_activity_detail(activity_id: str):
    """Get a single activity by ID."""
    item = get_activity_by_id(activity_id)
    if not item:
        raise HTTPException(status_code=404, detail="Activity not found")
    return item


@app.websocket("/ws/activity")
async def ws_activity(ws: WebSocket):
    """Live activity feed updates for companion app."""
    # Check device token for WebSocket connections
    expected_token = os.environ.get("BITOS_DEVICE_TOKEN", "")
    if expected_token:
        provided = ws.query_params.get("token", "")
        if provided != expected_token:
            await ws.close(code=1008)  # Policy Violation
            return
    await ws.accept()
    register_activity_ws(ws)
    logger.info("[WS] Activity feed client connected")
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("[WS] Activity feed client disconnected")
    except Exception as exc:
        logger.warning("[WS] Activity feed error: %s", exc)
    finally:
        unregister_activity_ws(ws)


@app.websocket("/ws/proactive")
async def ws_proactive(ws: WebSocket):
    """WebSocket endpoint for proactive heartbeat messages to devices."""
    # Check device token for WebSocket connections
    expected_token = os.environ.get("BITOS_DEVICE_TOKEN", "")
    if expected_token:
        provided = ws.query_params.get("token", "")
        if provided != expected_token:
            await ws.close(code=1008)  # Policy Violation
            return
    await ws.accept()
    register_proactive_ws(ws)
    logger.info("[WS] Proactive client connected")
    try:
        while True:
            data = await ws.receive_json()
            msg_type = data.get("type")
            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        logger.info("[WS] Proactive client disconnected")
    except Exception as exc:
        logger.warning("[WS] Proactive error: %s", exc)
    finally:
        unregister_proactive_ws(ws)


if __name__ == "__main__":
    import uvicorn
    from config import SERVER_HOST, SERVER_PORT

    logger.info("[BITOS] Starting server on %s:%s", SERVER_HOST, SERVER_PORT)
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
