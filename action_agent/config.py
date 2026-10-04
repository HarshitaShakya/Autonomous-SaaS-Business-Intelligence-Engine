"""Centralised, typed configuration loaded from environment variables.

All policy thresholds, execution mode, and infrastructure settings
are managed here — nothing is hardcoded in business logic.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from action_agent.schemas.action import ExecutionMode


class Settings(BaseSettings):
    """Application settings — populated from ``.env`` or environment vars."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -- Execution -----------------------------------------------------------
    execution_mode: ExecutionMode = Field(
        default=ExecutionMode.DRY_RUN,
        description="DRY_RUN (safe default) or LIVE.",
    )

    # -- Database ------------------------------------------------------------
    database_path: str = Field(
        default="action_agent.db",
        description="SQLite database file path.",
    )

    # -- Server --------------------------------------------------------------
    host: str = "0.0.0.0"
    port: int = 8000

    # -- Policy: confidence thresholds --------------------------------------
    min_confidence_low_risk: float = 0.5
    min_confidence_medium_risk: float = 0.7
    min_confidence_high_risk: float = 0.85

    # -- Policy: rollout caps ------------------------------------------------
    max_rollout_low_risk: float = 100.0
    max_rollout_medium_risk: float = 50.0
    max_rollout_high_risk: float = 20.0

    # -- Policy: general -----------------------------------------------------
    recommendation_ttl_hours: int = 24
    auto_approve_low_risk: bool = True
    auto_approve_medium_risk: bool = True
    auto_approve_high_risk: bool = False

    # -- Logging -------------------------------------------------------------
    log_level: str = "INFO"


# Singleton — import ``settings`` everywhere.
settings = Settings()
