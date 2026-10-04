"""Tests for the full executor pipeline."""

import pytest


class TestExecutor:
    """Tests for ActionExecutor — full pipeline integration."""

    @pytest.mark.asyncio
    async def test_successful_ux_execution(self, executor, valid_ux_payload):
        result = await executor.execute(valid_ux_payload)

        assert result.execution_status.value == "SUCCESS"
        assert result.verification_status.value == "PASSED"
        assert result.action_type.value == "UX_UPDATE"
        assert result.risk_level == "LOW"
        assert result.rollback_supported is True

    @pytest.mark.asyncio
    async def test_successful_alert_execution(self, executor, valid_alert_payload):
        result = await executor.execute(valid_alert_payload)

        assert result.execution_status.value == "SUCCESS"
        assert result.action_type.value == "ALERT"
        assert result.rollback_supported is False

    @pytest.mark.asyncio
    async def test_successful_experiment_execution(self, executor, valid_experiment_payload):
        result = await executor.execute(valid_experiment_payload)
        assert result.execution_status.value == "SUCCESS"

    @pytest.mark.asyncio
    async def test_successful_retention_execution(self, executor, valid_retention_payload):
        result = await executor.execute(valid_retention_payload)
        assert result.execution_status.value == "SUCCESS"

    @pytest.mark.asyncio
    async def test_low_confidence_rejection(self, executor, valid_ux_payload):
        valid_ux_payload["confidence"] = 0.2
        result = await executor.execute(valid_ux_payload)

        assert result.execution_status.value == "POLICY_REJECTED"

    @pytest.mark.asyncio
    async def test_invalid_input_returns_validation_failed(self, executor):
        result = await executor.execute({"garbage": True})
        assert result.execution_status.value == "VALIDATION_FAILED"

    @pytest.mark.asyncio
    async def test_unsupported_action_type(self, executor):
        payload = {
            "recommendation_id": "rec_bad_type",
            "confidence": 0.9,
            "recommended_action": {
                "type": "time_travel",
                "target": "x",
                "description": "impossible",
                "parameters": {}
            }
        }
        result = await executor.execute(payload)
        assert result.execution_status.value == "VALIDATION_FAILED"
