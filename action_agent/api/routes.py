"""FastAPI routes for the Action Agent.

These endpoints expose the Action Agent's capabilities over HTTP
so the Strategy Agent (or any other system) can call them.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from action_agent.core.executor import ActionExecutor
from action_agent.core.parser import ParseError
from action_agent.core.rollback_manager import RollbackError
from action_agent.persistence.audit_repository import AuditRepository

router = APIRouter(prefix="/actions", tags=["actions"])

# These will be set during app startup via dependency injection
_executor: ActionExecutor | None = None
_audit_repo: AuditRepository | None = None


def configure(executor: ActionExecutor, audit_repo: AuditRepository) -> None:
    """Inject dependencies at startup — avoids global state pollution."""
    global _executor, _audit_repo
    _executor = executor
    _audit_repo = audit_repo


def _get_executor() -> ActionExecutor:
    if _executor is None:
        raise RuntimeError("ActionExecutor not configured")
    return _executor


def _get_audit() -> AuditRepository:
    if _audit_repo is None:
        raise RuntimeError("AuditRepository not configured")
    return _audit_repo


# -----------------------------------------------------------------------
# POST /actions/execute
# -----------------------------------------------------------------------

@router.post("/execute", summary="Execute a strategy recommendation")
async def execute_action(payload: dict[str, Any]) -> dict[str, Any]:
    """Receive a StrategyRecommendation and run the full execution pipeline."""
    executor = _get_executor()
    result = await executor.execute(payload)
    return result.model_dump()


# -----------------------------------------------------------------------
# POST /actions/preview
# -----------------------------------------------------------------------

@router.post("/preview", summary="Preview an action without executing")
async def preview_action(payload: dict[str, Any]) -> dict[str, Any]:
    """Analyse a recommendation and return what would happen — no side effects."""
    executor = _get_executor()
    return await executor.preview(payload)


# -----------------------------------------------------------------------
# GET /actions/{action_id}
# -----------------------------------------------------------------------

@router.get("/{action_id}", summary="Get action details")
async def get_action(action_id: str) -> dict[str, Any]:
    """Look up a single action by its ID."""
    audit = _get_audit()
    entry = await audit.get_by_action_id(action_id)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Action '{action_id}' not found")
    return entry.model_dump()


# -----------------------------------------------------------------------
# POST /actions/{action_id}/rollback
# -----------------------------------------------------------------------

@router.post("/{action_id}/rollback", summary="Rollback a completed action")
async def rollback_action(action_id: str) -> dict[str, Any]:
    """Attempt to reverse a previously executed action."""
    executor = _get_executor()
    try:
        return await executor.rollback_action(action_id)
    except RollbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# -----------------------------------------------------------------------
# POST /actions/{action_id}/approve
# -----------------------------------------------------------------------

@router.post("/{action_id}/approve", summary="Approve a pending high-risk action")
async def approve_action(action_id: str) -> dict[str, Any]:
    """Approve and execute an action that requires human approval."""
    executor = _get_executor()
    try:
        result = await executor.approve(action_id)
        return result.model_dump()
    except RollbackError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


# -----------------------------------------------------------------------
# GET /actions/history
# -----------------------------------------------------------------------

@router.get("/", summary="Query action history")
async def get_history(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    action_type: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    """Retrieve filtered audit history."""
    audit = _get_audit()
    entries = await audit.get_history(
        limit=limit, offset=offset,
        action_type=action_type, execution_status=status,
    )
    return [e.model_dump() for e in entries]
