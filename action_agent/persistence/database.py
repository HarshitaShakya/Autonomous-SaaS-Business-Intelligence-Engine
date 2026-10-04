"""SQLite database connection and schema management.

Uses aiosqlite for async access.  The schema auto-creates on
first connection so there is zero manual setup.
"""

from __future__ import annotations

import aiosqlite

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS audit_log (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    action_id       TEXT    NOT NULL UNIQUE,
    recommendation_id TEXT  NOT NULL,
    timestamp       TEXT    NOT NULL,
    action_type     TEXT    NOT NULL,
    target          TEXT    DEFAULT '',
    target_segment  TEXT    DEFAULT '',
    parameters      TEXT    DEFAULT '{}',
    risk_level      TEXT    DEFAULT 'UNKNOWN',
    confidence      REAL    DEFAULT 0.0,
    policy_decision TEXT    DEFAULT 'UNKNOWN',
    approval_status TEXT    DEFAULT 'NOT_REQUIRED',
    execution_mode  TEXT    DEFAULT 'DRY_RUN',
    execution_status TEXT   DEFAULT 'PENDING',
    verification_status TEXT DEFAULT 'PENDING',
    rollback_status TEXT    DEFAULT 'NOT_APPLICABLE',
    error_info      TEXT,
    result_details  TEXT    DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS action_state (
    action_id       TEXT    PRIMARY KEY,
    recommendation_id TEXT  NOT NULL,
    idempotency_key TEXT    NOT NULL,
    action_type     TEXT    NOT NULL,
    status          TEXT    NOT NULL DEFAULT 'PENDING',
    execution_mode  TEXT    NOT NULL DEFAULT 'DRY_RUN',
    plan_json       TEXT    NOT NULL DEFAULT '{}',
    result_json     TEXT,
    rollback_data   TEXT,
    created_at      TEXT    NOT NULL,
    updated_at      TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_action_state_idemp
    ON action_state(idempotency_key);
CREATE INDEX IF NOT EXISTS idx_action_state_rec
    ON action_state(recommendation_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_rec
    ON audit_log(recommendation_id);
"""


class Database:
    """Async SQLite wrapper with auto-schema creation."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Open connection and ensure schema exists."""
        self._connection = await aiosqlite.connect(self._db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.executescript(_SCHEMA_SQL)
        await self._connection.commit()

    async def disconnect(self) -> None:
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._connection is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._connection
