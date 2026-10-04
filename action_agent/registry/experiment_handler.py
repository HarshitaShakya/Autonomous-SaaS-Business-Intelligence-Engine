"""Experiment action handler.

Creates / stops A/B experiments via the ExperimentAdapter.
"""

from __future__ import annotations

from typing import Any

from action_agent.adapters.base import AdapterResult, ExperimentAdapter
from action_agent.registry.base import ActionHandler
from action_agent.schemas.action import ActionPlan


class ExperimentActionHandler(ActionHandler):
    """Handles EXPERIMENT actions."""

    def __init__(self, adapter: ExperimentAdapter) -> None:
        self._adapter = adapter

    @property
    def action_type_name(self) -> str:
        return "Experiment"

    async def execute(self, plan: ActionPlan) -> AdapterResult:
        experiment_key = plan.target or plan.parameters.get("experiment_key", "exp_default")
        segment = plan.target_segment
        rollout_pct = plan.parameters.get("rollout_percentage", 10.0)
        return await self._adapter.create_experiment(
            experiment_key=experiment_key,
            segment=segment,
            rollout_pct=rollout_pct,
            parameters=plan.parameters,
        )

    async def rollback(self, rollback_data: dict[str, Any]) -> AdapterResult:
        previous = rollback_data.get("previous_state", {})
        experiment_key = previous.get("experiment_key", "")
        if not experiment_key:
            # If we don't know the key, try the action_performed string
            action_str = rollback_data.get("action_performed", "")
            # Fallback: stop by parsing the key from the original action
            experiment_key = action_str.split("'")[1] if "'" in action_str else "unknown"
        return await self._adapter.stop_experiment(experiment_key)
