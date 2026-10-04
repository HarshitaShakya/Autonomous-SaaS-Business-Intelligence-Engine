"""Rollback manager.

Orchestrates reversal of previously executed actions using the
adapter's stored previous_state.  Irreversible actions (e.g. sent
notifications) are explicitly marked as non-reversible.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from action_agent.adapters.base import AdapterResult
from action_agent.persistence.action_repository import ActionRepository
from action_agent.persistence.audit_repository import AuditRepository
from action_agent.schemas.action import ActionType, ExecutionStatus
from action_agent.schemas.audit import AuditEntry


# Action types that cannot be rolled back
_IRREVERSIBLE_TYPES = {ActionType.ALERT}


class RollbackError(Exception):
    """Raised when a rollback cannot be performed."""


class RollbackManager:
    """Manages action reversal via adapters."""

    def __init__(
        self,
        action_repo: ActionRepository,
        audit_repo: AuditRepository,
    ) -> None:
        self._action_repo = action_repo
        self._audit_repo = audit_repo

    @staticmethod
    def is_reversible(action_type: ActionType) -> bool:
        """Check if an action type supports rollback."""
        return action_type not in _IRREVERSIBLE_TYPES

    async def rollback(
        self,
        action_id: str,
        rollback_fn: Any,  # Callable — adapter-specific rollback coroutine
    ) -> AdapterResult:
        """Perform rollback for a given action.

        Steps:
        1. Load the action and its rollback metadata.
        2. Call the adapter-specific rollback function.
        3. Update action state to ROLLED_BACK.
        4. Write audit entry.
        """
        record = await self._action_repo.get_by_action_id(action_id)
        if record is None:
            raise RollbackError(f"Action '{action_id}' not found")

        if record["status"] == ExecutionStatus.ROLLED_BACK.value:
            raise RollbackError(f"Action '{action_id}' has already been rolled back")

        if record["status"] not in (ExecutionStatus.SUCCESS.value, ExecutionStatus.FAILED.value):
            raise RollbackError(
                f"Action '{action_id}' is in state '{record['status']}' and cannot be rolled back"
            )

        action_type = ActionType(record["action_type"])
        if not self.is_reversible(action_type):
            raise RollbackError(
                f"Action type '{action_type.value}' does not support rollback"
            )

        # Load rollback data
        rollback_data_raw = record.get("rollback_data")
        rollback_data: dict[str, Any] = {}
        if rollback_data_raw:
            rollback_data = json.loads(rollback_data_raw)

        # Execute rollback via adapter
        result = await rollback_fn(rollback_data)

        # Update state
        await self._action_repo.update_status(action_id, ExecutionStatus.ROLLED_BACK.value)

        # Audit
        await self._audit_repo.save(
            AuditEntry(
                action_id=f"{action_id}_rollback",
                recommendation_id=record["recommendation_id"],
                timestamp=datetime.now(timezone.utc),
                action_type=record["action_type"],
                execution_status=ExecutionStatus.ROLLED_BACK.value,
                rollback_status="COMPLETED" if result.success else "FAILED",
                execution_mode=record["execution_mode"],
                result_details=result.details,
                error_info=result.error,
            )
        )

        return result
