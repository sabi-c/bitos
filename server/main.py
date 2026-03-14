"""BITOS Server backend: health, chat, and UI settings catalog endpoints."""
import logging
import os

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
