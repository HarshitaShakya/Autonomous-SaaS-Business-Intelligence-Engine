"""Mock experiment adapter.

Simulates an A/B testing platform (e.g. Optimizely, GrowthBook).
"""

from __future__ import annotations

import asyncio
from typing import Any

from action_agent.adapters.base import AdapterResult, ExperimentAdapter


class MockExperimentAdapter(ExperimentAdapter):
    """Simulates an experimentation platform."""

    def __init__(self) -> None:
        self._experiments: dict[str, dict[str, Any]] = {}

    async def create_experiment(
        self,
        experiment_key: str,
        segment: str,
        rollout_pct: float,
        parameters: dict[str, Any],
    ) -> AdapterResult:
        await asyncio.sleep(0.05)

        previous = self._experiments.get(experiment_key, {}).copy()
        self._experiments[experiment_key] = {
            "active": True,
            "segment": segment,
            "rollout_pct": rollout_pct,
            "parameters": parameters,
        }
        return AdapterResult(
            success=True,
            adapter_name="MockExperiment",
            action_performed=f"Created experiment '{experiment_key}' targeting '{segment}' at {rollout_pct}%",
            details=self._experiments[experiment_key],
            previous_state=previous,
        )

    async def stop_experiment(self, experiment_key: str) -> AdapterResult:
        await asyncio.sleep(0.05)

        previous = self._experiments.get(experiment_key, {}).copy()
        if experiment_key in self._experiments:
            self._experiments[experiment_key]["active"] = False
        return AdapterResult(
            success=True,
            adapter_name="MockExperiment",
            action_performed=f"Stopped experiment '{experiment_key}'",
            details=self._experiments.get(experiment_key, {}),
            previous_state=previous,
        )

    async def get_experiment_state(self, experiment_key: str) -> dict[str, Any]:
        return self._experiments.get(experiment_key, {"active": False})
