"""BITOS Server backend: health, chat, and UI settings catalog endpoints."""
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from integrations.bluebubbles_adapter import BlueBubblesAdapter
from integrations.vikunja_adapter import VikunjaAdapter

from agent_modes import get_system_prompt
from config import UI_SETTINGS_FILE
from llm_bridge import create_llm_bridge, to_sse_data
from ui_settings import UISettingsStore, UISettingsValidationError


class ChatRequest(BaseModel):
    message: str
    session_id: str = ""
    agent_mode: str = "producer"
    tasks_today: list[str] = Field(default_factory=list)
    battery_pct: int | None = None


class MessageSendRequest(BaseModel):
    chat_id: str
    text: str
    confirmed: bool = False


class MessageDraftRequest(BaseModel):
    chat_id: str
    voice_transcript: str


class IntegrationSettingsRequest(BaseModel):
    integration: str
    config: dict = Field(default_factory=dict)


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

logger = logging.getLogger(__name__)

app = FastAPI(title="BITOS Server", version="0.3.0")
settings_store = UISettingsStore(UI_SETTINGS_FILE)
llm_bridge = create_llm_bridge()
_token_warning_logged = False

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
        "provider": llm_bridge.provider,
        "model": llm_bridge.model,
        "settings_file": UI_SETTINGS_FILE,
    }


@app.get("/status/integrations")
async def get_integrations_status():
    return _integration_status_payload()


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
    )

    def stream_response():
        for text in llm_bridge.stream_text(message, system_prompt=system_prompt):
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
