"""Policy and risk assessment schemas."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    """Severity classification of an action."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class PolicyDecision(str, Enum):
    """Outcome of the policy engine evaluation."""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


class PolicyEvaluation(BaseModel):
    """Full result of the policy engine's assessment of an action."""

    decision: PolicyDecision
    risk_level: RiskLevel
    requires_approval: bool = False
    reasons: list[str] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)
    checks_passed: dict[str, bool] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
