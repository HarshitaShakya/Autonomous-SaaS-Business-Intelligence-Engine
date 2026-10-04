"""Action planner.

Converts a validated StrategyRecommendation into an ActionPlan
by classifying the action type and generating a deterministic
idempotency key.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any

from action_agent.config import settings
from action_agent.schemas.action import ActionPlan, ActionType, ExecutionMode
from action_agent.schemas.recommendation import StrategyRecommendation


# ---------------------------------------------------------------------------
# Action type classification map
# ---------------------------------------------------------------------------
# Maps recommendation action.type strings to internal ActionType enums.
# Case-insensitive, supports multiple aliases per type.

_TYPE_MAP: dict[str, ActionType] = {
    "experiment": ActionType.EXPERIMENT,
    "ab_experiment": ActionType.EXPERIMENT,
    "a/b_experiment": ActionType.EXPERIMENT,
    "ab_test": ActionType.EXPERIMENT,
    "pricing_change": ActionType.PRICING_CHANGE,
    "pricing_experiment": ActionType.PRICING_CHANGE,
    "discount": ActionType.PRICING_CHANGE,
    "pricing": ActionType.PRICING_CHANGE,
    "ux_update": ActionType.UX_UPDATE,
    "ux_experiment": ActionType.UX_UPDATE,
    "feature_flag": ActionType.UX_UPDATE,
    "feature_rollout": ActionType.UX_UPDATE,
    "onboarding": ActionType.UX_UPDATE,
    "ux": ActionType.UX_UPDATE,
    "alert": ActionType.ALERT,
    "notification": ActionType.ALERT,
    "notify": ActionType.ALERT,
    "retention_intervention": ActionType.RETENTION_INTERVENTION,
    "retention": ActionType.RETENTION_INTERVENTION,
    "retention_campaign": ActionType.RETENTION_INTERVENTION,
    "retention_offer": ActionType.RETENTION_INTERVENTION,
}


class ClassificationError(Exception):
    """Raised when the recommended action type cannot be mapped."""


class ActionPlanner:
    """Classifies a recommendation and produces an ActionPlan."""

    def classify(self, action_type_str: str) -> ActionType:
        """Map a free-text action type to an enum value.

        Raises ClassificationError if no mapping exists.
        """
        normalised = action_type_str.strip().lower().replace(" ", "_").replace("-", "_")
        action_type = _TYPE_MAP.get(normalised)
        if action_type is None:
            # Try a direct enum match
            try:
                return ActionType(action_type_str.upper())
            except ValueError:
                raise ClassificationError(
                    f"Unsupported action type: '{action_type_str}'. "
                    f"Supported types: {sorted(set(_TYPE_MAP.values()), key=lambda x: x.value)}"
                )
        return action_type

    def create_plan(self, rec: StrategyRecommendation) -> ActionPlan:
        """Convert a recommendation to a fully-formed ActionPlan."""
        action_type = self.classify(rec.recommended_action.type)
        action_id = f"act_{uuid.uuid4().hex[:12]}"
        idemp_key = self._compute_idempotency_key(rec)

        return ActionPlan(
            action_id=action_id,
            recommendation_id=rec.recommendation_id,
            action_type=action_type,
            target=rec.recommended_action.target,
            target_segment=rec.customer_segment,
            description=rec.recommended_action.description,
            parameters=rec.recommended_action.parameters,
            execution_mode=ExecutionMode(settings.execution_mode.value),
            idempotency_key=idemp_key,
        )

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _compute_idempotency_key(rec: StrategyRecommendation) -> str:
        """Deterministic fingerprint: recommendation_id + action_type + sorted params."""
        payload = {
            "recommendation_id": rec.recommendation_id,
            "type": rec.recommended_action.type,
            "target": rec.recommended_action.target,
            "parameters": _sort_dict(rec.recommended_action.parameters),
        }
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()


def _sort_dict(d: dict[str, Any]) -> dict[str, Any]:
    """Recursively sort dict keys for deterministic hashing."""
    return {k: _sort_dict(v) if isinstance(v, dict) else v for k, v in sorted(d.items())}
