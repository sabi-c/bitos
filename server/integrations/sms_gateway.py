"""Unified SMS gateway — routes messages between text channels and BITOS chat.

Supports iMessage (via BlueBubbles) as the primary channel, with the adapter
pattern ready for future channels (Telegram, etc).

Sessions expire after 30 minutes of inactivity. Memory/facts are global and
carry across sessions.
"""
from __future__ import annotations

import logging
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
DB_PATH = DATA_DIR / "sms_sessions.db"
SESSION_TIMEOUT_MINUTES = 30


# ── Database ──────────────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=3000")
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sms_sessions (
            id TEXT PRIMARY KEY,
            channel TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            conversation_id TEXT,
            last_activity TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


# ── Gateway ───────────────────────────────────────────────────────────────

class SMSGateway:
    """Routes messages between text channels (iMessage, etc.) and the BITOS
    chat pipeline. Maintains per-sender sessions with 30-min timeout."""

    def __init__(self):
        # Ensure tables exist on init
        db = _get_db()
        db.close()
        self._adapters: dict[str, Any] = {}

    def register_adapter(self, channel: str, adapter: Any) -> None:
        """Register a channel adapter (e.g. BlueBubblesAdapter for 'imessage')."""
        self._adapters[channel] = adapter
        logger.info("sms_gateway: registered adapter for channel=%s", channel)

    async def handle_incoming(
        self,
        channel: str,
        sender_id: str,
        text: str,
        metadata: dict | None = None,
    ) -> str:
        """Process an incoming text message through the BITOS chat pipeline.

        Returns the agent's response text.
        """
        if not text or not text.strip():
            return ""

        conv_id = self._get_or_create_session(channel, sender_id)
        logger.info(
            "sms_incoming: channel=%s sender=%s conv=%s len=%d",
            channel, sender_id[:20], conv_id, len(text),
        )

        # Run the chat pipeline — reuse the same logic as /chat endpoint
        response = await self._run_chat_pipeline(text, conv_id)

        # Update session activity timestamp
        self._touch_session(channel, sender_id)

        return response

    async def send_outbound(
        self,
        channel: str,
        recipient: str,
        text: str,
    ) -> bool:
        """Send an outbound message via the appropriate channel adapter."""
        adapter = self._adapters.get(channel)
        if not adapter:
            logger.warning("sms_gateway: no adapter for channel=%s", channel)
            return False

        try:
            result = adapter.send_message(recipient, text)
            logger.info(
                "sms_outbound: channel=%s recipient=%s len=%d ok=%s",
                channel, recipient[:20], len(text), result,
            )
            return bool(result)
        except Exception as exc:
            logger.error("sms_outbound_error: channel=%s %s", channel, exc)
            return False

    def _get_or_create_session(self, channel: str, sender_id: str) -> str:
        """Look up or create a session. Returns conversation_id.

        If no session exists or the last activity was more than 30 minutes ago,
        a new conversation is created. Otherwise, the existing conversation_id
        is reused for multi-turn continuity.
        """
        session_id = f"{channel}:{sender_id}"
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=SESSION_TIMEOUT_MINUTES)

        db = _get_db()
        try:
            row = db.execute(
                "SELECT conversation_id, last_activity FROM sms_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()

            if row and row["conversation_id"]:
                last_activity = datetime.fromisoformat(row["last_activity"])
                # Ensure timezone-aware comparison
                if last_activity.tzinfo is None:
                    last_activity = last_activity.replace(tzinfo=timezone.utc)
                if last_activity > cutoff:
                    # Session still active — reuse conversation
                    return row["conversation_id"]

            # Create new conversation
            from conversation_store import create_conversation
            conv_id = create_conversation()

            db.execute(
                """INSERT INTO sms_sessions (id, channel, sender_id, conversation_id, last_activity, created_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       conversation_id = excluded.conversation_id,
                       last_activity = excluded.last_activity""",
                (session_id, channel, sender_id, conv_id, now.isoformat(), now.isoformat()),
            )
            db.commit()
            logger.info(
                "sms_session: new session=%s conv=%s (timeout or first contact)",
                session_id, conv_id,
            )
            return conv_id
        finally:
            db.close()

    def _touch_session(self, channel: str, sender_id: str) -> None:
        """Update the last_activity timestamp for a session."""
        session_id = f"{channel}:{sender_id}"
        now = datetime.now(timezone.utc).isoformat()
        db = _get_db()
        try:
            db.execute(
                "UPDATE sms_sessions SET last_activity = ? WHERE id = ?",
                (now, session_id),
            )
            db.commit()
        finally:
            db.close()

    async def _run_chat_pipeline(self, message: str, conversation_id: str) -> str:
        """Run the BITOS chat pipeline (same logic as /chat endpoint).

        Uses complete_text (non-streaming) since SMS doesn't need streaming.
        Includes memory retrieval and fact extraction, just like /chat.
        """
        import asyncio
        import threading

        from agent_modes import get_system_prompt
        from conversation_store import add_message, get_messages as get_conv_messages
        from memory_store import search_facts

        # Build system prompt with default producer mode
        system_prompt = get_system_prompt("producer")

        # Inject long-term memory facts
        try:
            memory_facts = search_facts(message, limit=10)
            if memory_facts:
                facts_lines = [f"- {f['content']}" for f in memory_facts]
                system_prompt += (
                    "\n\nMEMORY (things I know about you):\n"
                    + "\n".join(facts_lines)
                )
        except Exception as exc:
            logger.warning("sms_memory_retrieval_failed: %s", exc)

        # Add SMS context hint
        system_prompt += (
            "\n\nCONTEXT: This message arrived via iMessage/SMS. "
            "Keep your response concise and text-friendly — no markdown, "
            "no bullet points, just plain conversational text. "
            "2-3 sentences max unless the question requires more."
        )

        # Load conversation history for multi-turn
        history = get_conv_messages(conversation_id)
        history_messages = [
            {"role": m["role"], "content": m["content"]} for m in history
        ]

        # Get the LLM bridge from main module
        try:
            import main as server_main
            bridge = server_main.llm_bridge
        except Exception:
            from llm_bridge import create_llm_bridge
            bridge = create_llm_bridge()

        # Use non-streaming complete_text for SMS
        response_text = ""
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: bridge.complete_text(
                    message,
                    system_prompt=system_prompt,
                ),
            )
            if isinstance(result, tuple):
                response_text = result[0]
            else:
                response_text = str(result)
        except Exception as exc:
            logger.error("sms_chat_pipeline_error: %s", exc)
            response_text = "Sorry, I couldn't process that right now."

        # Save conversation turn
        if response_text.strip():
            add_message(conversation_id, "user", message)
            add_message(conversation_id, "assistant", response_text)

            # Background fact extraction
            try:
                from fact_extractor import extract_and_store_facts
                threading.Thread(
                    target=extract_and_store_facts,
                    args=(message, response_text, conversation_id),
                    daemon=True,
                ).start()
            except Exception:
                pass

        return response_text

    def get_session_info(self, channel: str, sender_id: str) -> dict | None:
        """Return session info for a channel+sender, or None if no session."""
        session_id = f"{channel}:{sender_id}"
        db = _get_db()
        try:
            row = db.execute(
                "SELECT * FROM sms_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    def list_sessions(self, limit: int = 20) -> list[dict]:
        """Return recent SMS sessions."""
        db = _get_db()
        try:
            rows = db.execute(
                "SELECT * FROM sms_sessions ORDER BY last_activity DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            db.close()
