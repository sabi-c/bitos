"""
BITOS Server — Minimal FastAPI Backend
Two endpoints: /health and /chat (streaming).
"""
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import anthropic
import json

from config import ANTHROPIC_API_KEY, MODEL_NAME

app = FastAPI(title="BITOS Server", version="0.1.0")

# Allow CORS for web preview
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "model": MODEL_NAME}


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
