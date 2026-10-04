"""Strategy Agent → Action Agent input contract.

This module defines the exact schema the Strategy Agent must produce.
It is the single most important integration piece between the two agents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class Priority(str, Enum):
    """Urgency level assigned by the Strategy Agent."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class RecommendedAction(BaseModel):
    """What the Strategy Agent wants the Action Agent to do."""

    type: str = Field(
        ...,
        description="Action category, e.g. 'experiment', 'pricing_change', 'ux_update', 'alert', 'retention_intervention'.",
    )
    target: str = Field(
        ...,
        description="The specific entity to act on (feature name, flag key, segment ID, etc.).",
    )
    description: str = Field(
        ...,
        description="Human-readable description of the recommended action.",
    )
    expected_outcome: str = Field(
        default="",
        description="What success looks like, e.g. 'increase_30_day_retention'.",
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Action-specific key-value parameters (rollout_percentage, discount_amount, etc.).",
    )


class ExpectedImpact(BaseModel):
    """Quantified prediction of what this action should achieve."""

    metric: str = Field(..., description="Business metric affected, e.g. 'retention_rate'.")
    direction: str = Field(..., description="'increase' or 'decrease'.")
    estimated_change: float = Field(
        ...,
        description="Estimated absolute change (e.g. 0.08 = +8 percentage points).",
    )


class ActionConstraints(BaseModel):
    """Guardrails set by the Strategy Agent."""

    max_rollout_percentage: float = Field(
        default=100.0,
        ge=0.0,
        le=100.0,
        description="Maximum allowed rollout percentage.",
    )
    requires_approval: bool = Field(
        default=False,
        description="Whether the Strategy Agent explicitly requests human approval.",
    )
    max_budget: float | None = Field(
        default=None,
        description="Optional budget ceiling for this action.",
    )


# ---------------------------------------------------------------------------
# Top-level input contract
# ---------------------------------------------------------------------------

class StrategyRecommendation(BaseModel):
    """Complete recommendation payload from the Strategy Agent.

    This is the primary input schema for the Action Agent.
    All fields use sensible defaults where possible so partial
    payloads from early-stage Strategy Agent implementations
    still parse successfully.
    """

    recommendation_id: str = Field(
        ...,
        min_length=1,
        description="Globally unique ID for this recommendation.",
    )
    customer_segment: str = Field(
        default="all",
        description="Target customer segment identifier.",
    )
    priority: Priority = Field(
        default=Priority.MEDIUM,
        description="Urgency level.",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Strategy Agent's confidence in this recommendation (0–1).",
    )
    reason: str = Field(
        default="",
        description="Human-readable explanation of why this action is recommended.",
    )
    recommended_action: RecommendedAction
    expected_impact: ExpectedImpact | None = Field(
        default=None,
        description="Optional quantified impact prediction.",
    )
    constraints: ActionConstraints = Field(
        default_factory=ActionConstraints,
        description="Guardrails for execution.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="When the recommendation was generated.",
    )
    expires_at: datetime | None = Field(
        default=None,
        description="Optional expiry; the Action Agent rejects stale recommendations.",
    )

    # -- Validators ----------------------------------------------------------

    @field_validator("recommendation_id")
    @classmethod
    def strip_recommendation_id(cls, v: str) -> str:
        return v.strip()
