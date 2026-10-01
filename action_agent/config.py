"""
Configuration Module for the Autonomous SaaS Action Agent.

Loads environment variables, manages runtime operational modes,
and defines system-wide settings for LLMs, logging, and security.
"""

import os
import logging
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Base project directory
BASE_DIR = Path(__file__).resolve().parent

# Load environment variables from .env file
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)


class Settings:
    """System configuration parameters and runtime settings."""

    # OpenAI API Configurations
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY", None)
    MODEL_NAME: str = os.getenv("MODEL_NAME", "gpt-4o")
    TEMPERATURE: float = float(os.getenv("TEMPERATURE", "0.0"))

    # Environment and Execution Settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development").lower()
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    ENABLE_HITL: bool = os.getenv("ENABLE_HITL", "true").lower() in ("true", "1", "yes")
    AUDIT_LOG_FILE: Path = BASE_DIR / os.getenv("AUDIT_LOG_FILE", "audit_log.jsonl")

    # Tool Execution Settings
    TOOL_TIMEOUT_SECONDS: int = int(os.getenv("TOOL_TIMEOUT_SECONDS", "30"))
    MOCK_TOOL_DELAY_SECONDS: float = float(os.getenv("MOCK_TOOL_DELAY_SECONDS", "0.2"))

    # Human-in-the-Loop Settings
    HITL_INPUT_TIMEOUT_SECONDS: int = int(os.getenv("HITL_INPUT_TIMEOUT_SECONDS", "120"))

    @classmethod
    def is_production(cls) -> bool:
        """Check whether the agent is running in production mode."""
        return cls.ENVIRONMENT == "production"

    @classmethod
    def has_valid_openai_key(cls) -> bool:
        """Check whether a non-empty OpenAI API key is configured."""
        return bool(cls.OPENAI_API_KEY and cls.OPENAI_API_KEY.strip() and not cls.OPENAI_API_KEY.startswith("your-"))


# Instantiate global settings singleton
settings = Settings()


def setup_logger(name: str = "ActionAgent") -> logging.Logger:
    """
    Configures and returns a standardized logger instance.
    
    Args:
        name: Name of the logger component.
        
    Returns:
        logging.Logger: Configured logger with console formatting.
    """
    logger = logging.getLogger(name)
    level = getattr(logging, settings.LOG_LEVEL, logging.INFO)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


# Global default logger
logger = setup_logger("ActionAgent.Core")
