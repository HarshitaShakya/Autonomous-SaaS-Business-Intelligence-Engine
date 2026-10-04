"""Retention intervention action handler.

Creates retention-specific experiments / campaigns via the
ExperimentAdapter.  Structurally similar to experiments but
with retention-specific semantics.
"""

from __future__ import annotations

from typing import Any

from action_agent.adapters.base import AdapterResult, ExperimentAdapter
from action_agent.registry.base import ActionHandler
from action_agent.schemas.action import ActionPlan


class RetentionActionHandler(ActionHandler):
    """Handles RETENTION_INTERVENTION actions."""

    def __init__(self, adapter: ExperimentAdapter) -> None:
        self._adapter = adapter

    @property
    def action_type_name(self) -> str:
        return "RetentionIntervention"

    async def execute(self, plan: ActionPlan) -> AdapterResult:
        experiment_key = f"retention_{plan.target}"
        segment = plan.target_segment
        rollout_pct = plan.parameters.get("rollout_percentage", 10.0)
        params = {
            **plan.parameters,
            "intervention_type": "retention",
            "description": plan.description,
        }
        return await self._adapter.create_experiment(
            experiment_key=experiment_key,
            segment=segment,
            rollout_pct=rollout_pct,
            parameters=params,
        )

    async def rollback(self, rollback_data: dict[str, Any]) -> AdapterResult:
        previous = rollback_data.get("previous_state", {})
        experiment_key = previous.get("experiment_key", "")
        if not experiment_key:
            action_str = rollback_data.get("action_performed", "")
            experiment_key = action_str.split("'")[1] if "'" in action_str else "unknown"
        return await self._adapter.stop_experiment(experiment_key)
