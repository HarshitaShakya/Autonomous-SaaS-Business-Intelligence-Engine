"""Pricing action handler.

Applies / reverts pricing changes through the PricingAdapter.
Always treated as HIGH risk — the policy engine enforces this.
"""

from __future__ import annotations

from typing import Any

from action_agent.adapters.base import AdapterResult, PricingAdapter
from action_agent.registry.base import ActionHandler
from action_agent.schemas.action import ActionPlan


class PricingActionHandler(ActionHandler):
    """Handles PRICING_CHANGE actions."""

    def __init__(self, adapter: PricingAdapter) -> None:
        self._adapter = adapter

    @property
    def action_type_name(self) -> str:
        return "PricingChange"

    async def execute(self, plan: ActionPlan) -> AdapterResult:
        segment = plan.target_segment
        discount_pct = plan.parameters.get("discount_percentage", 0.0)
        duration = plan.parameters.get("duration_days", 30)
        return await self._adapter.apply_discount(
            segment=segment,
            discount_pct=discount_pct,
            duration_days=duration,
        )

    async def rollback(self, rollback_data: dict[str, Any]) -> AdapterResult:
        previous = rollback_data.get("previous_state", {})
        segment = previous.get("segment", "unknown")
        return await self._adapter.revert_discount(segment=segment)
