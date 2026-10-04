"""Audit log repository — immutable persistence of action lifecycle events."""

from __future__ import annotations

import json
from typing import Any

from action_agent.persistence.database import Database
from action_agent.schemas.audit import AuditEntry


class AuditRepository:
    """CRUD operations on the audit_log table."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def save(self, entry: AuditEntry) -> None:
        """Insert an immutable audit record."""
        await self._db.conn.execute(
            """
            INSERT INTO audit_log (
                action_id, recommendation_id, timestamp, action_type,
                target, target_segment, parameters, risk_level, confidence,
                policy_decision, approval_status, execution_mode,
                execution_status, verification_status, rollback_status,
                error_info, result_details
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.action_id,
                entry.recommendation_id,
                entry.timestamp.isoformat(),
                entry.action_type,
                entry.target,
                entry.target_segment,
                json.dumps(entry.parameters),
                entry.risk_level,
                entry.confidence,
                entry.policy_decision,
                entry.approval_status,
                entry.execution_mode,
                entry.execution_status,
                entry.verification_status,
                entry.rollback_status,
                entry.error_info,
                json.dumps(entry.result_details),
            ),
        )
        await self._db.conn.commit()

    async def get_by_action_id(self, action_id: str) -> AuditEntry | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM audit_log WHERE action_id = ?", (action_id,)
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return self._row_to_entry(row)

    async def get_by_recommendation_id(self, recommendation_id: str) -> list[AuditEntry]:
        cursor = await self._db.conn.execute(
            "SELECT * FROM audit_log WHERE recommendation_id = ? ORDER BY timestamp DESC",
            (recommendation_id,),
        )
        rows = await cursor.fetchall()
        return [self._row_to_entry(r) for r in rows]

    async def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        action_type: str | None = None,
        execution_status: str | None = None,
    ) -> list[AuditEntry]:
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []

        if action_type:
            query += " AND action_type = ?"
            params.append(action_type)
        if execution_status:
            query += " AND execution_status = ?"
            params.append(execution_status)

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = await self._db.conn.execute(query, params)
        rows = await cursor.fetchall()
        return [self._row_to_entry(r) for r in rows]

    # -- Helpers -------------------------------------------------------------

    @staticmethod
    def _row_to_entry(row: Any) -> AuditEntry:
        return AuditEntry(
            action_id=row["action_id"],
            recommendation_id=row["recommendation_id"],
            timestamp=row["timestamp"],
            action_type=row["action_type"],
            target=row["target"],
            target_segment=row["target_segment"],
            parameters=json.loads(row["parameters"]),
            risk_level=row["risk_level"],
            confidence=row["confidence"],
            policy_decision=row["policy_decision"],
            approval_status=row["approval_status"],
            execution_mode=row["execution_mode"],
            execution_status=row["execution_status"],
            verification_status=row["verification_status"],
            rollback_status=row["rollback_status"],
            error_info=row["error_info"],
            result_details=json.loads(row["result_details"]),
        )
