"""Fact extraction via Haiku sub-agent.

Takes conversation messages, extracts structured facts as JSON,
deduplicates against existing facts, and stores new ones.
Designed to run every 8 turns (batch mode), not per-message.
"""

import json
import logging
import re
from typing import Optional

import anthropic

from config import ANTHROPIC_API_KEY
from memory.memory_store import MemoryStore

logger = logging.getLogger(__name__)

HAIKU_MODEL = "claude-haiku-4-5-20251001"

EXTRACTION_PROMPT = """You are a fact extraction agent for a personal AI companion called BITOS.

Extract atomic facts from this conversation between the user and the AI assistant.
Only extract NEW information not already in the existing memories.

Already known facts:
{existing_memories}

Conversation (last several turns):
{conversation}

Return a JSON array of extracted facts. Each item:
{{
  "content": "atomic fact in third person (e.g., 'Seb prefers dark mode')",
  "category": "preference|biographical|relationship|habit|opinion|knowledge",
  "confidence": 0.0 to 1.0
}}

Categories:
- preference: likes, dislikes, preferred tools/settings
- biographical: name, age, location, occupation, education
- relationship: people they know, family, colleagues
- habit: routines, regular activities, workflows
- opinion: views on topics, beliefs
- knowledge: skills, expertise, things they know about

Rules:
- Return [] if no new facts worth remembering
- Be selective — only meaningful, reusable information
- Skip greetings, filler, and generic knowledge
- Skip things the AI said about itself
- Each fact should be a standalone sentence
- Confidence 0.9+ for explicitly stated facts, 0.5-0.8 for inferred"""


class FactExtractor:
    """Extract structured facts from conversation turns using Haiku."""

    def __init__(self, store: MemoryStore, api_key: Optional[str] = None):
        self._store = store
        self._api_key = api_key or ANTHROPIC_API_KEY
        self._turn_count = 0
        self._batch_threshold = 8
        self._pending_messages: list[dict] = []

    @property
    def turn_count(self) -> int:
        return self._turn_count

    def add_turn(self, user_message: str, assistant_response: str) -> None:
        """Buffer a conversation turn. Call extract_if_ready() after."""
        self._pending_messages.append({
            "user": user_message,
            "assistant": assistant_response,
        })
        self._turn_count += 1

    def should_extract(self) -> bool:
        """True if we've accumulated enough turns for batch extraction."""
        return self._turn_count >= self._batch_threshold

    def extract_if_ready(self, conversation_id: str = "") -> list[dict]:
        """Run extraction if batch threshold reached. Returns new facts."""
        if not self.should_extract():
            return []
        return self.extract_now(conversation_id)

    def extract_now(self, conversation_id: str = "") -> list[dict]:
        """Force extraction on buffered messages. Returns list of new facts."""
        if not self._pending_messages:
            return []

        messages = self._pending_messages.copy()
        self._pending_messages.clear()
        self._turn_count = 0

        return self._extract_from_messages(messages, conversation_id)

    def extract_from_turn(
        self,
        user_message: str,
        assistant_response: str,
        conversation_id: str = "",
    ) -> list[dict]:
        """Extract facts from a single turn (immediate, no batching)."""
        if len(user_message.strip()) < 10:
            return []

        messages = [{"user": user_message, "assistant": assistant_response}]
        return self._extract_from_messages(messages, conversation_id)

    def _extract_from_messages(
        self,
        messages: list[dict],
        conversation_id: str,
    ) -> list[dict]:
        """Core extraction: call Haiku, parse JSON, dedup, store."""
        # Format conversation for the prompt
        conv_text = ""
        for msg in messages:
            conv_text += f"User: {msg['user']}\nAssistant: {msg['assistant']}\n\n"

        # Get existing memories for dedup context
        # Use words from the conversation to find relevant existing facts
        all_words = " ".join(msg["user"] for msg in messages)
        existing = self._store.search_facts(all_words[:200], limit=20)
        existing_text = "\n".join(f"- {f['content']}" for f in existing) if existing else "(none yet)"

        prompt = EXTRACTION_PROMPT.format(
            existing_memories=existing_text,
            conversation=conv_text.strip(),
        )

        try:
            client = anthropic.Anthropic(api_key=self._api_key)
            response = client.messages.create(
                model=HAIKU_MODEL,
                max_tokens=500,
                system="You extract facts from conversations. Return valid JSON only.",
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()
            data = self._parse_json(text)

            if not data:
                logger.debug("No facts extracted from conversation %s", conversation_id)
                return []

            # Handle both array and {"facts": [...]} formats
            facts_list = data if isinstance(data, list) else data.get("facts", [])

            new_facts = []
            for fact in facts_list:
                if not isinstance(fact, dict):
                    continue
                content = fact.get("content", "").strip()
                if not content or len(content) < 5:
                    continue

                category = fact.get("category", "general")
                confidence = float(fact.get("confidence", 0.8))

                fact_id = self._store.add_fact(
                    content=content,
                    category=category,
                    source=conversation_id or "extraction",
                    confidence=confidence,
                )

                if fact_id:
                    new_facts.append({
                        "id": fact_id,
                        "content": content,
                        "category": category,
                        "confidence": confidence,
                    })

            # Log the extraction
            if new_facts:
                self._store.log_extraction(
                    conversation_id or "",
                    all_words[:500],
                    new_facts,
                )
                logger.info(
                    "Extracted %d facts from %d turns (conv %s)",
                    len(new_facts), len(messages), conversation_id,
                )

            return new_facts

        except Exception as e:
            logger.warning("Fact extraction failed (non-critical): %s", e)
            return []

    @staticmethod
    def _parse_json(text: str) -> Optional[list | dict]:
        """Best-effort JSON extraction from LLM output."""
        text = text.strip()

        # Direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Code fence
        match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Find array or object
        for pattern in [r'\[.*\]', r'\{.*\}']:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass

        return None
