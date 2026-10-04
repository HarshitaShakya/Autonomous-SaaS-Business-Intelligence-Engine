"""Action plan and execution result schemas.

These types represent the internal state of an action as it moves
through the execution pipeline.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ActionType(str, Enum):
    """Supported action categories."""
    EXPERIMENT = "EXPERIMENT"
    PRICING_CHANGE = "PRICING_CHANGE"
    UX_UPDATE = "UX_UPDATE"
    ALERT = "ALERT"
    RETENTION_INTERVENTION = "RETENTION_INTERVENTION"


class ExecutionMode(str, Enum):
    """Whether actions modify real systems."""
    DRY_RUN = "DRY_RUN"
    LIVE = "LIVE"


class ExecutionStatus(str, Enum):
    """Lifecycle state of an action."""
    PENDING = "PENDING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    EXECUTING = "EXECUTING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    ROLLED_BACK = "ROLLED_BACK"
    ALREADY_EXECUTED = "ALREADY_EXECUTED"
    POLICY_REJECTED = "POLICY_REJECTED"
    EXPIRED = "EXPIRED"


class VerificationStatus(str, Enum):
    """Outcome of post-execution verification."""
    PENDING = "PENDING"
    PASSED = "PASSED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


# ---------------------------------------------------------------------------
# Action plan (internal representation)
# ---------------------------------------------------------------------------

class ActionPlan(BaseModel):
    """An executable action derived from a StrategyRecommendation."""

    action_id: str = Field(..., description="Unique ID for this action instance.")
    recommendation_id: str = Field(..., description="Source recommendation ID.")
    action_type: ActionType
    target: str = Field(..., description="What is being acted on.")
    target_segment: str = Field(default="all")
    description: str = Field(default="")
    parameters: dict[str, Any] = Field(default_factory=dict)
    execution_mode: ExecutionMode = Field(default=ExecutionMode.DRY_RUN)
    status: ExecutionStatus = Field(default=ExecutionStatus.PENDING)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Fingerprint for idempotency (set by the planner)
    idempotency_key: str = Field(default="")


# ---------------------------------------------------------------------------
# Execution result (output)
# ---------------------------------------------------------------------------

class ExecutionResult(BaseModel):
    """Structured result returned after action execution."""

    action_id: str
    recommendation_id: str
    action_type: ActionType | str
    execution_status: ExecutionStatus
    verification_status: VerificationStatus = VerificationStatus.PENDING
    execution_mode: ExecutionMode | str
    risk_level: str = "UNKNOWN"
    policy_decision: str = "UNKNOWN"
    requires_approval: bool = False
    rollback_supported: bool = False
    rollback_id: str | None = None
    target: str = ""
    target_segment: str = ""
    parameters: dict[str, Any] = Field(default_factory=dict)
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
