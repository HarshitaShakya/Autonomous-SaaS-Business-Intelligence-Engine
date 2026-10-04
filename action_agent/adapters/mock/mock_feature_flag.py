"""Mock feature-flag adapter.

Maintains in-memory state so verification can check flag status
after execution — exactly like a real feature-flag service would behave.
"""

from __future__ import annotations

import asyncio
from typing import Any

from action_agent.adapters.base import AdapterResult, FeatureFlagAdapter


class MockFeatureFlagAdapter(FeatureFlagAdapter):
    """Simulates a feature-flag service (e.g. LaunchDarkly)."""

    def __init__(self) -> None:
        # In-memory flag state: {flag_key: {enabled, segment, rollout_pct}}
        self._flags: dict[str, dict[str, Any]] = {}

    async def enable_flag(
        self, flag_key: str, segment: str, rollout_pct: float
    ) -> AdapterResult:
        await asyncio.sleep(0.05)  # simulate latency

        previous = self._flags.get(flag_key, {}).copy()
        self._flags[flag_key] = {
            "enabled": True,
            "segment": segment,
            "rollout_pct": rollout_pct,
        }
        return AdapterResult(
            success=True,
            adapter_name="MockFeatureFlag",
            action_performed=f"Enabled flag '{flag_key}' for segment '{segment}' at {rollout_pct}%",
            details=self._flags[flag_key],
            previous_state=previous,
        )

    async def disable_flag(self, flag_key: str, segment: str) -> AdapterResult:
        await asyncio.sleep(0.05)

        previous = self._flags.get(flag_key, {}).copy()
        self._flags[flag_key] = {
            "enabled": False,
            "segment": segment,
            "rollout_pct": 0.0,
        }
        return AdapterResult(
            success=True,
            adapter_name="MockFeatureFlag",
            action_performed=f"Disabled flag '{flag_key}' for segment '{segment}'",
            details=self._flags[flag_key],
            previous_state=previous,
        )

    async def get_flag_state(self, flag_key: str) -> dict[str, Any]:
        return self._flags.get(flag_key, {"enabled": False, "segment": "", "rollout_pct": 0.0})
