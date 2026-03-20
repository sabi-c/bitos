"""Remote-control endpoints for Codex App Server style session/turn/approval flows."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from codex_app_client import InMemoryCodexAppClient


router = APIRouter(tags=["codex-remote"])
client = InMemoryCodexAppClient()


class CreateTurnRequest(BaseModel):
    message: str
    require_approval: bool = False


class ApprovalRequest(BaseModel):
    decision: str


@router.post("/api/codex/sessions")
def create_session() -> dict:
    return client.create_session()


@router.post("/api/codex/sessions/{session_id}/turns")
def create_turn(session_id: str, payload: CreateTurnRequest) -> dict:
    try:
        result = client.submit_turn(
            session_id=session_id,
            message=payload.message,
            require_approval=payload.require_approval,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="session_not_found")

    return {
        "session_id": session_id,
        "turn_id": result.turn_id,
        "status": result.status,
        "pending_approval_id": result.pending_approval_id,
    }


@router.get("/api/codex/sessions/{session_id}/events")
def list_events(session_id: str) -> dict:
    try:
        events = client.list_events(session_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="session_not_found")
    return {"session_id": session_id, "events": events}


@router.post("/api/codex/approvals/{approval_id}")
def resolve_approval(approval_id: str, payload: ApprovalRequest) -> dict:
    try:
        result = client.resolve_approval(approval_id=approval_id, decision=payload.decision)
    except KeyError:
        raise HTTPException(status_code=404, detail="approval_not_found")
    except ValueError as exc:
        detail = str(exc)
        if detail == "approval_already_resolved":
            raise HTTPException(status_code=409, detail=detail)
        raise HTTPException(status_code=400, detail=detail)

    return {
        "approval_id": result.approval_id,
        "decision": result.decision,
        "status": result.status,
    }
