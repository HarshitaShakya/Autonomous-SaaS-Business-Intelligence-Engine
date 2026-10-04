"""Abstract base class for action handlers.

Every action type (experiment, pricing, UX, alert, retention)
implements this interface so the registry can dispatch uniformly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from action_agent.adapters.base import AdapterResult
from action_agent.schemas.action import ActionPlan


class ActionHandler(ABC):
    """Interface that every action handler must implement."""

    @property
    @abstractmethod
    def action_type_name(self) -> str:
        """Human-readable name for logging."""
        ...

    @property
    def rollback_supported(self) -> bool:
        """Override to False for irreversible actions."""
        return True

    @abstractmethod
    async def execute(self, plan: ActionPlan) -> AdapterResult:
        """Perform the action and return the adapter result."""
        ...

    @abstractmethod
    async def rollback(self, rollback_data: dict[str, Any]) -> AdapterResult:
        """Reverse a previously executed action using stored rollback data."""
        ...
