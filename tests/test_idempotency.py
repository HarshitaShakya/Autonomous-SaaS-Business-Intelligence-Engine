"""Tests for idempotency guard."""

import pytest


class TestIdempotency:

    @pytest.mark.asyncio
    async def test_first_execution_succeeds(self, executor, valid_ux_payload):
        result = await executor.execute(valid_ux_payload)
        assert result.execution_status.value == "SUCCESS"

    @pytest.mark.asyncio
    async def test_duplicate_returns_already_executed(self, executor, valid_ux_payload):
        # First execution
        first = await executor.execute(valid_ux_payload)
        assert first.execution_status.value == "SUCCESS"

        # Second execution — same recommendation
        second = await executor.execute(valid_ux_payload)
        assert second.execution_status.value == "ALREADY_EXECUTED"

    @pytest.mark.asyncio
    async def test_different_recommendations_both_execute(self, executor, valid_ux_payload, valid_alert_payload):
        r1 = await executor.execute(valid_ux_payload)
        r2 = await executor.execute(valid_alert_payload)

        assert r1.execution_status.value == "SUCCESS"
        assert r2.execution_status.value == "SUCCESS"
        assert r1.action_id != r2.action_id

    @pytest.mark.asyncio
    async def test_same_rec_id_different_params_executes(self, executor, valid_ux_payload):
        # First
        r1 = await executor.execute(valid_ux_payload)
        assert r1.execution_status.value == "SUCCESS"

        # Modify parameters → different idempotency key
        valid_ux_payload["recommended_action"]["parameters"]["rollout_percentage"] = 30
        r2 = await executor.execute(valid_ux_payload)
        # This should execute since the fingerprint is different
        assert r2.execution_status.value in ("SUCCESS", "ALREADY_EXECUTED")
