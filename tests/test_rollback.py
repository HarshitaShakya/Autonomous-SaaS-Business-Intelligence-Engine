"""Tests for rollback manager."""

import pytest

from action_agent.core.rollback_manager import RollbackError, RollbackManager
from action_agent.schemas.action import ActionType


class TestRollbackManager:

    def test_alert_not_reversible(self):
        assert RollbackManager.is_reversible(ActionType.ALERT) is False

    def test_ux_is_reversible(self):
        assert RollbackManager.is_reversible(ActionType.UX_UPDATE) is True

    def test_experiment_is_reversible(self):
        assert RollbackManager.is_reversible(ActionType.EXPERIMENT) is True

    @pytest.mark.asyncio
    async def test_rollback_nonexistent_action(self, rollback_manager):
        with pytest.raises(RollbackError, match="not found"):
            await rollback_manager.rollback("nonexistent_id", lambda d: None)

    @pytest.mark.asyncio
    async def test_rollback_after_successful_execution(self, executor, valid_ux_payload):
        # Execute first
        result = await executor.execute(valid_ux_payload)
        assert result.execution_status.value == "SUCCESS"
        assert result.rollback_supported is True

        # Rollback
        rb = await executor.rollback_action(result.action_id)
        assert rb["rollback_status"] == "COMPLETED"
