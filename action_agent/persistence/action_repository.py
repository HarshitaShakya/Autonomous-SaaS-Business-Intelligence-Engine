"""Action state repository — tracks execution lifecycle and idempotency."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from action_agent.persistence.database import Database
from action_agent.schemas.action import ActionPlan, ExecutionResult


class ActionRepository:
    """CRUD for action_state table (idempotency + lifecycle tracking)."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def save_plan(self, plan: ActionPlan) -> None:
        """Persist a new action plan."""
        now = datetime.now(timezone.utc).isoformat()
        await self._db.conn.execute(
            """
            INSERT INTO action_state (
                action_id, recommendation_id, idempotency_key,
                action_type, status, execution_mode, plan_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan.action_id,
                plan.recommendation_id,
                plan.idempotency_key,
                plan.action_type.value,
                plan.status.value,
                plan.execution_mode.value,
                plan.model_dump_json(),
                now,
                now,
            ),
        )
        await self._db.conn.commit()

    async def update_status(self, action_id: str, status: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.conn.execute(
            "UPDATE action_state SET status = ?, updated_at = ? WHERE action_id = ?",
            (status, now, action_id),
        )
        await self._db.conn.commit()

    async def save_result(self, action_id: str, result: ExecutionResult) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.conn.execute(
            "UPDATE action_state SET status = ?, result_json = ?, updated_at = ? WHERE action_id = ?",
            (result.execution_status.value, result.model_dump_json(), now, action_id),
        )
        await self._db.conn.commit()

    async def save_rollback_data(self, action_id: str, rollback_data: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self._db.conn.execute(
            "UPDATE action_state SET rollback_data = ?, updated_at = ? WHERE action_id = ?",
            (json.dumps(rollback_data), now, action_id),
        )
        await self._db.conn.commit()

    async def get_by_action_id(self, action_id: str) -> dict[str, Any] | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM action_state WHERE action_id = ?", (action_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def find_by_idempotency_key(self, key: str) -> dict[str, Any] | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM action_state WHERE idempotency_key = ?", (key,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_dict(row)

    async def get_by_recommendation_id(self, recommendation_id: str) -> list[dict[str, Any]]:
        cursor = await self._db.conn.execute(
            "SELECT * FROM action_state WHERE recommendation_id = ? ORDER BY created_at DESC",
            (recommendation_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_dict(r) for r in rows]

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        return {
            "action_id": row["action_id"],
            "recommendation_id": row["recommendation_id"],
            "idempotency_key": row["idempotency_key"],
            "action_type": row["action_type"],
            "status": row["status"],
            "execution_mode": row["execution_mode"],
            "plan_json": row["plan_json"],
            "result_json": row["result_json"],
            "rollback_data": row["rollback_data"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
