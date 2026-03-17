"""Fact extraction: use Haiku to extract personal facts from conversation turns.

Runs as a background task after each chat response — never blocks the SSE stream.
"""

import json
import logging
import re

import anthropic

from config import ANTHROPIC_API_KEY
from memory_store import add_fact, log_extraction

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

EXTRACTION_PROMPT = """Extract any new facts worth remembering from this exchange.
Facts should be about the user — their preferences, personal info, projects,
schedules, relationships, habits, or decisions.

Do NOT extract:
- Generic knowledge or things the assistant said about itself
- Conversation filler or greetings
- Facts that are vague or not useful long-term

Categories: preference, personal, work, relationship, habit, health, location, other

Return JSON only:
{"facts": [{"content": "...", "confidence": 0.0-1.0, "category": "..."}]}
or {"facts": []} if nothing new."""


def _parse_json(text: str) -> dict | None:
    """Best-effort JSON extraction from LLM output."""
    # Try direct parse first
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find JSON block in markdown code fence
    match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try to find {...} block
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def extract_and_store_facts(
    user_message: str,
    assistant_response: str,
    conversation_id: str,
) -> None:
    """Extract facts from a conversation turn and store them.

    This runs synchronously but is meant to be called from a background thread
    (via asyncio.to_thread or run_in_executor). It uses the synchronous
    Anthropic client.
    """
    # Skip very short messages — unlikely to contain extractable facts
    if len(user_message.strip()) < 10:
        return

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=300,
            system=EXTRACTION_PROMPT,
            messages=[{
                "role": "user",
                "content": f"User said: {user_message}\nAssistant replied: {assistant_response}",
            }],
        )

        text = response.content[0].text.strip()
        data = _parse_json(text)

        if not data or not data.get("facts"):
            logger.debug("No facts extracted from conversation %s", conversation_id)
            return

        extracted = []
        for fact in data["facts"]:
            content = fact.get("content", "").strip() if isinstance(fact, dict) else str(fact).strip()
            if not content or len(content) < 5:
                continue

            confidence = fact.get("confidence", 0.8) if isinstance(fact, dict) else 0.8
            category = fact.get("category", "other") if isinstance(fact, dict) else "other"

            add_fact(
                content=content,
                source=conversation_id or "chat",
                confidence=float(confidence),
                category=category,
            )
            extracted.append({"content": content, "confidence": confidence, "category": category})

        # Log the extraction for debugging
        if extracted:
            log_extraction(conversation_id or "", user_message, extracted)
            logger.info("Extracted %d facts from conversation %s", len(extracted), conversation_id)

    except Exception as e:
        logger.warning("Fact extraction failed (non-critical): %s", e)
