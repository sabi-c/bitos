"""Lightweight perception classifier for BITOS chat.

Runs a fast Haiku pre-call to classify user intent before the main model response.
This saves tokens (skip tools when unnecessary) and gives the main model better context.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

import anthropic

from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

CLASSIFIER_PROMPT = """Classify this user message for a pocket AI assistant. Return JSON only.

Fields:
- intent: one of [chat, question, command, settings, task, creative, reflection, messaging]
- needs_tools: boolean — true if the user needs device control, messaging, email, calendar, or contacts
- urgency: one of [low, normal, high]
- response_hint: one of [brief, normal, detailed] — how long the response should be
- topic: short topic label (2-4 words)

Rules:
- "chat" = casual conversation, greetings, banter
- "question" = asking for information or explanation
- "command" = requesting an action (settings change, send message, etc.)
- "settings" = specifically about device settings (volume, voice, model, mode)
- "task" = task/todo/project management
- "creative" = brainstorming, writing, ideation
- "reflection" = deep thinking, meditation, personal growth
- "messaging" = reading/sending messages, emails, checking calendar, looking up contacts
- needs_tools is true for: settings, command, messaging, task intents
- needs_tools is false for: chat, question, creative, reflection
- "send a text to..." or "email..." or "what's on my calendar" = messaging + needs_tools=true
- brief = 1-2 sentences, normal = 2-4 sentences, detailed = paragraph+

Return ONLY valid JSON, no markdown fences."""


@dataclass
class Perception:
    """Result of the perception classifier."""
    intent: str = "chat"
    needs_tools: bool = False
    urgency: str = "normal"
    response_hint: str = "normal"
    topic: str = ""
    raw: dict = field(default_factory=dict)


def classify(message: str, agent_mode: str = "") -> Perception:
    """Run the Haiku classifier on a user message.

    Returns a Perception with intent, tool needs, and response hints.
    Falls back to safe defaults on any error — never blocks the main response.
    """
    if not ANTHROPIC_API_KEY:
        return Perception()

    try:
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        response = client.messages.create(
            model=HAIKU_MODEL,
            max_tokens=150,
            system=[{
                "type": "text",
                "text": CLASSIFIER_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": message}],
        )

        text = "".join(
            block.text for block in response.content if hasattr(block, "text")
        )

        # Parse JSON — strip markdown fences if model adds them
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(text)

        result = Perception(
            intent=data.get("intent", "chat"),
            needs_tools=bool(data.get("needs_tools", False)),
            urgency=data.get("urgency", "normal"),
            response_hint=data.get("response_hint", "normal"),
            topic=data.get("topic", ""),
            raw=data,
        )

        logger.info(
            "perception: intent=%s needs_tools=%s urgency=%s hint=%s topic=%s",
            result.intent, result.needs_tools, result.urgency,
            result.response_hint, result.topic,
        )
        return result

    except Exception as exc:
        logger.warning("perception_failed: %s — using defaults", exc)
        return Perception()
