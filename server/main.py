"""BITOS Server backend: health, chat, and UI settings catalog endpoints."""
import logging
import os
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

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


class MailDraftRequest(BaseModel):
    thread_id: str
    voice_transcript: str


class MailCreateDraftRequest(BaseModel):
    thread_id: str
    body: str
    confirmed: bool = False


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
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from vikunja_adapter import VikunjaAdapter
    adapter = VikunjaAdapter()
    tasks = adapter.get_today_tasks()
    return {"tasks": tasks, "count": len(tasks)}


@app.get("/messages")
async def get_messages_conversations():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from bluebubbles_adapter import BlueBubblesAdapter

    adapter = BlueBubblesAdapter()
    return {
        "conversations": adapter.get_conversations(),
        "unread_total": adapter.get_unread_count(),
    }


@app.get("/mail")
async def get_mail_threads():
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from gmail_adapter import GmailAdapter

    adapter = GmailAdapter()
    return {
        "threads": adapter.get_inbox(limit=10),
        "unread_total": adapter.get_unread_count(),
    }


@app.get("/mail/{thread_id:path}")
async def get_mail_thread(thread_id: str):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from gmail_adapter import GmailAdapter

    adapter = GmailAdapter()
    return {
        "messages": adapter.get_thread(thread_id),
        "thread_id": thread_id,
    }


@app.post("/mail/draft")
async def draft_mail(payload: MailDraftRequest):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from gmail_adapter import GmailAdapter

    adapter = GmailAdapter()
    draft = adapter.draft_reply(payload.thread_id, payload.voice_transcript)
    return {"draft": draft}


@app.post("/mail/create-draft")
async def create_mail_draft(payload: MailCreateDraftRequest):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from gmail_adapter import GmailAdapter

    if not payload.confirmed:
        raise HTTPException(status_code=403, detail="requires confirmed=true")

    adapter = GmailAdapter()
    draft_id = adapter.create_draft(payload.thread_id, payload.body)
    return {"draft_id": draft_id, "ok": bool(draft_id)}


@app.get("/messages/{chat_id:path}")
async def get_messages_for_chat(chat_id: str):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from bluebubbles_adapter import BlueBubblesAdapter

    adapter = BlueBubblesAdapter()
    return {
        "messages": adapter.get_messages(chat_id),
        "chat_id": chat_id,
    }


@app.post("/messages/send")
async def send_message(payload: MessageSendRequest):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from bluebubbles_adapter import BlueBubblesAdapter

    if not payload.confirmed:
        raise HTTPException(status_code=403, detail="requires confirmed=true")

    adapter = BlueBubblesAdapter()
    ok = adapter.send_message(payload.chat_id, payload.text)
    return {"sent": ok}


@app.post("/messages/draft")
async def draft_message(payload: MessageDraftRequest):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from bluebubbles_adapter import BlueBubblesAdapter

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
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent / "integrations"))
    from bluebubbles_adapter import BlueBubblesAdapter
    from gmail_adapter import GmailAdapter

    now = datetime.now(timezone.utc).isoformat()
    msg_adapter = BlueBubblesAdapter()
    gmail_adapter = GmailAdapter()

    return {
        "bluebubbles": {
            "status": "mock" if msg_adapter._mock else "online",
            "unread": msg_adapter.get_unread_count(),
            "last_checked": now,
        },
        "gmail": {
            "status": gmail_adapter.integration_status(),
            "unread": gmail_adapter.get_unread_count(),
            "last_checked": now,
        },
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
