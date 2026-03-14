"""BITOS Server backend: health, chat, and UI settings catalog endpoints."""
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import json

from config import ANTHROPIC_API_KEY, MODEL_NAME, UI_SETTINGS_FILE
from ui_settings import UISettingsStore, UISettingsValidationError

app = FastAPI(title="BITOS Server", version="0.2.0")
settings_store = UISettingsStore(UI_SETTINGS_FILE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "model": MODEL_NAME,
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


@app.post("/chat")
async def chat(request: Request):
    """Stream a Claude response as SSE."""
    body = await request.json()
    message = body.get("message", "")

    if not message:
        return {"error": "No message provided"}

    if not ANTHROPIC_API_KEY:
        return {"error": "ANTHROPIC_API_KEY not configured"}

    def stream_response():
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

        with client.messages.stream(
            model=MODEL_NAME,
            max_tokens=1024,
            messages=[{"role": "user", "content": message}],
            system="You are BITOS, a helpful pocket AI companion. Keep responses concise — you're rendering on a tiny 240×280 pixel screen. Be direct and useful.",
        ) as stream:
            for text in stream.text_stream:
                yield f"data: {json.dumps({'text': text})}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        stream_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    import uvicorn
    from config import SERVER_HOST, SERVER_PORT
    uvicorn.run(app, host=SERVER_HOST, port=SERVER_PORT)
