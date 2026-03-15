"""BITOS BLE Protocol — JSON over Nordic UART Service (NUS)."""

from __future__ import annotations

import json
import logging
from typing import Optional

logger = logging.getLogger(__name__)

MAX_CHUNK = 180  # Safe BLE payload size before fragmentation.


class BITOSProtocol:
    """Encode/decode BITOS BLE JSON messages with chunking support."""

    @staticmethod
    def encode(msg: dict) -> list[bytes]:
        """Encode a dict to one or more BLE payloads."""
        raw = json.dumps(msg, separators=(",", ":"))
        if len(raw) <= MAX_CHUNK:
            return [raw.encode("utf-8")]

        chunks = [raw[i : i + MAX_CHUNK] for i in range(0, len(raw), MAX_CHUNK)]
        n = len(chunks)
        return [
            json.dumps({"t": "chunk", "i": i, "n": n, "d": chunk}, separators=(",", ":")).encode("utf-8")
            for i, chunk in enumerate(chunks)
        ]

    @staticmethod
    def decode(raw_bytes: bytes) -> Optional[dict]:
        """Decode incoming bytes to a dict. Returns None on error."""
        try:
            return json.loads(raw_bytes.decode("utf-8"))
        except Exception as exc:  # pragma: no cover - defensive for malformed payloads
            logger.debug("BLE decode error: %s | raw: %r", exc, raw_bytes[:50])
            return None


class ChunkAssembler:
    """Reassembles fragmented chunk messages."""

    def __init__(self):
        self._chunks: dict[int, str] = {}
        self._expected: Optional[int] = None

    def feed(self, msg: dict) -> Optional[dict]:
        """Feed decoded message; returns complete message when available."""
        if msg.get("t") != "chunk":
            return msg

        index = msg.get("i", 0)
        total = msg.get("n", 1)
        data = msg.get("d", "")
        self._expected = total
        self._chunks[index] = data

        if len(self._chunks) == self._expected:
            full = "".join(self._chunks[i] for i in range(self._expected))
            self._chunks.clear()
            self._expected = None
            try:
                return json.loads(full)
            except Exception:  # pragma: no cover - defensive for malformed fragments
                return None

        return None
