"""UX / product action handler.

Enables / disables feature flags through the FeatureFlagAdapter.
"""

from __future__ import annotations

from typing import Any

from action_agent.adapters.base import AdapterResult, FeatureFlagAdapter
from action_agent.registry.base import ActionHandler
from action_agent.schemas.action import ActionPlan


class UXActionHandler(ActionHandler):
    """Handles UX_UPDATE actions (feature flags, onboarding changes)."""

    def __init__(self, adapter: FeatureFlagAdapter) -> None:
        self._adapter = adapter

    @property
    def action_type_name(self) -> str:
        return "UXUpdate"

    async def execute(self, plan: ActionPlan) -> AdapterResult:
        flag_key = plan.target
        segment = plan.target_segment
        rollout_pct = plan.parameters.get("rollout_percentage", 100.0)
        return await self._adapter.enable_flag(
            flag_key=flag_key,
            segment=segment,
            rollout_pct=rollout_pct,
        )

    async def rollback(self, rollback_data: dict[str, Any]) -> AdapterResult:
        previous = rollback_data.get("previous_state", {})
        flag_key = previous.get("flag_key", "unknown")
        segment = previous.get("segment", "unknown")
        return await self._adapter.disable_flag(flag_key=flag_key, segment=segment)
