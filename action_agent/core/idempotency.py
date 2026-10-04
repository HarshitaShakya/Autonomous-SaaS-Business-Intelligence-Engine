"""Idempotency guard.

Prevents the same recommendation from being executed twice by
checking the idempotency key against the action state store.
"""

from __future__ import annotations

import json

from action_agent.persistence.action_repository import ActionRepository
from action_agent.schemas.action import ExecutionResult


class IdempotencyGuard:
    """Checks whether an action has already been executed."""

    def __init__(self, repo: ActionRepository) -> None:
        self._repo = repo

    async def check(self, idempotency_key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if this key was already executed.

        Returns None if the action has not been executed before.
        """
        existing = await self._repo.find_by_idempotency_key(idempotency_key)
        if existing is None:
            return None

        # If found but status is PENDING / APPROVAL_REQUIRED, it hasn't
        # actually been executed yet — allow re-submission.
        status = existing["status"]
        if status in ("PENDING", "APPROVAL_REQUIRED"):
            return None

        # Return the cached result
        result_json = existing.get("result_json")
        if result_json:
            return ExecutionResult.model_validate_json(result_json)

        # No result stored — build a minimal "already executed" response
        return ExecutionResult(
            action_id=existing["action_id"],
            recommendation_id=existing["recommendation_id"],
            action_type=existing["action_type"],
            execution_status="ALREADY_EXECUTED",
            execution_mode=existing["execution_mode"],
            details={"message": "This recommendation has already been executed."},
        )
