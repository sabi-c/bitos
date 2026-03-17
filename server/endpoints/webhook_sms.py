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
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["webhooks"])


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
