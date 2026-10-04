"""Audit log entry schema."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """Immutable record of an action's complete lifecycle."""

    action_id: str
    recommendation_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    action_type: str
    target: str = ""
    target_segment: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    risk_level: str = "UNKNOWN"
    confidence: float = 0.0
    policy_decision: str = "UNKNOWN"
    approval_status: str = "NOT_REQUIRED"
    execution_mode: str = "DRY_RUN"
    execution_status: str = "PENDING"
    verification_status: str = "PENDING"
    rollback_status: str = "NOT_APPLICABLE"
    error_info: str | None = None
    result_details: dict[str, Any] = Field(default_factory=dict)
