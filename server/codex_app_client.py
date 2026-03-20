"""Codex App Server client abstractions and a deterministic in-memory mock transport.

This module intentionally starts with a mock implementation so the remote-control
API surface can be validated in tests before wiring real stdio/websocket transport.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid


@dataclass
class CodexTurnResult:
    turn_id: str
    status: str
    pending_approval_id: str | None = None


@dataclass
class CodexApprovalResult:
    approval_id: str
    decision: str
    status: str


class InMemoryCodexAppClient:
    """Deterministic mock of Codex App Server semantics for local vertical slices."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict] = {}
        self.approvals: dict[str, dict] = {}

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def create_session(self) -> dict:
        session_id = f"cs_{uuid.uuid4().hex[:12]}"
        self.sessions[session_id] = {
            "created_at": self._now(),
            "events": [],
        }
        return {
            "session_id": session_id,
            "created_at": self.sessions[session_id]["created_at"],
        }

    def submit_turn(self, session_id: str, message: str, require_approval: bool = False) -> CodexTurnResult:
        if session_id not in self.sessions:
            raise KeyError("session_not_found")

        turn_id = f"turn_{uuid.uuid4().hex[:10]}"
        self.sessions[session_id]["events"].append(
            {
                "type": "user_message",
                "turn_id": turn_id,
                "content": message,
                "ts": self._now(),
            }
        )

        if require_approval:
            approval_id = f"apr_{uuid.uuid4().hex[:10]}"
            self.approvals[approval_id] = {
                "session_id": session_id,
                "turn_id": turn_id,
                "status": "pending",
            }
            self.sessions[session_id]["events"].append(
                {
                    "type": "approval_requested",
                    "turn_id": turn_id,
                    "approval_id": approval_id,
                    "ts": self._now(),
                }
            )
            return CodexTurnResult(turn_id=turn_id, status="awaiting_approval", pending_approval_id=approval_id)

        self.sessions[session_id]["events"].append(
            {
                "type": "assistant_message",
                "turn_id": turn_id,
                "content": f"[mock] acknowledged: {message}",
                "ts": self._now(),
            }
        )
        return CodexTurnResult(turn_id=turn_id, status="completed")

    def list_events(self, session_id: str) -> list[dict]:
        if session_id not in self.sessions:
            raise KeyError("session_not_found")
        return list(self.sessions[session_id]["events"])

    def resolve_approval(self, approval_id: str, decision: str) -> CodexApprovalResult:
        approval = self.approvals.get(approval_id)
        if approval is None:
            raise KeyError("approval_not_found")
        if approval["status"] != "pending":
            raise ValueError("approval_already_resolved")
        if decision not in {"allow", "deny"}:
            raise ValueError("invalid_decision")

        approval["status"] = "approved" if decision == "allow" else "denied"
        session_id = approval["session_id"]
        turn_id = approval["turn_id"]

        self.sessions[session_id]["events"].append(
            {
                "type": "approval_resolved",
                "turn_id": turn_id,
                "approval_id": approval_id,
                "decision": decision,
                "status": approval["status"],
                "ts": self._now(),
            }
        )

        if decision == "allow":
            self.sessions[session_id]["events"].append(
                {
                    "type": "assistant_message",
                    "turn_id": turn_id,
                    "content": "[mock] approval granted; action executed",
                    "ts": self._now(),
                }
            )

        return CodexApprovalResult(approval_id=approval_id, decision=decision, status=approval["status"])
