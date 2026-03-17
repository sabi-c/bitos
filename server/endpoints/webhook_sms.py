"""BlueBubbles webhook endpoint for incoming iMessages.

BlueBubbles Server sends POST requests to this endpoint when new messages
arrive. The webhook is configured in BlueBubbles Settings > Webhooks.

Expected payload:
    {
        "type": "new-message",
        "data": {
            "text": "hello",
            "isFromMe": false,
            "handle": {"address": "+13105550001"},
            "chats": [{"guid": "iMessage;+;+13105550001"}]
        }
    }

Authentication:
    Set BLUEBUBBLES_PASSWORD env var to match your BlueBubbles server password.
    Requests must include it as ?password= query param or X-BlueBubbles-Password header.
    If the env var is unset, auth is skipped (dev mode) with a warning on first request.
"""
from __future__ import annotations

import hmac
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])

_auth_warning_logged = False


def _verify_webhook_auth(request: Request) -> bool | None:
    """Check BlueBubbles password authentication.

    Returns True if auth passes, False if it fails, None if auth is not configured.
    """
    global _auth_warning_logged
    expected = os.environ.get("BLUEBUBBLES_PASSWORD", "")
    if not expected:
        if not _auth_warning_logged:
            logger.warning(
                "webhook_bluebubbles: BLUEBUBBLES_PASSWORD not set — "
                "webhook authentication is DISABLED (dev mode)"
            )
            _auth_warning_logged = True
        return None

    # BlueBubbles sends the password as a query parameter or we accept it as a header
    provided = (
        request.query_params.get("password", "")
        or request.headers.get("x-bluebubbles-password", "")
    )
    if not provided:
        return False

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected, provided)


def _get_gateway():
    """Lazy import to avoid circular imports at module load time."""
    import main as server_main
    return server_main.sms_gateway


def _get_adapter():
    """Lazy import for BlueBubbles adapter."""
    import main as server_main
    return server_main.bluebubbles


@router.post("/webhook/bluebubbles")
async def webhook_bluebubbles(request: Request):
    """Receive BlueBubbles webhook for incoming iMessages."""
    # ── Authentication ────────────────────────────────────────────
    auth_result = _verify_webhook_auth(request)
    if auth_result is False:
        logger.warning("webhook_bluebubbles: authentication failed from %s", request.client.host if request.client else "unknown")
        return JSONResponse(status_code=401, content={"ok": False, "error": "unauthorized"})

    try:
        body = await request.json()
    except Exception:
        logger.warning("webhook_bluebubbles: invalid JSON body")
        return {"ok": False, "error": "invalid JSON"}

    msg_type = body.get("type", "")

    # Only process new incoming messages
    if msg_type != "new-message":
        logger.debug("webhook_bluebubbles: ignoring type=%s", msg_type)
        return {"ok": True, "skipped": msg_type}

    data = body.get("data", {})

    # Ignore our own outgoing messages
    if data.get("isFromMe", False):
        return {"ok": True, "skipped": "from_me"}

    text = (data.get("text") or "").strip()
    if not text:
        return {"ok": True, "skipped": "empty_text"}

    # Extract sender address
    sender = (data.get("handle") or {}).get("address", "")
    if not sender:
        logger.warning("webhook_bluebubbles: no sender address in payload")
        return {"ok": False, "error": "no sender"}

    # Extract chat GUID for replying
    chats = data.get("chats") or []
    chat_guid = chats[0].get("guid", "") if chats else ""

    logger.info(
        "webhook_bluebubbles: incoming from=%s chat=%s len=%d",
        sender[:20], chat_guid[:30], len(text),
    )

    # Process through SMS gateway
    gateway = _get_gateway()
    response_text = await gateway.handle_incoming(
        channel="imessage",
        sender_id=sender,
        text=text,
        metadata=data,
    )

    # Send reply back via BlueBubbles
    if chat_guid and response_text:
        adapter = _get_adapter()
        try:
            await adapter.send_message_async(chat_guid, response_text)
            logger.info(
                "webhook_bluebubbles: replied to=%s len=%d",
                sender[:20], len(response_text),
            )
        except Exception as exc:
            logger.error("webhook_bluebubbles: reply failed: %s", exc)
            # Fall back to sync send
            try:
                adapter.send_message(chat_guid, response_text)
            except Exception:
                logger.error("webhook_bluebubbles: sync reply also failed")

    return {"ok": True, "responded": bool(response_text)}
