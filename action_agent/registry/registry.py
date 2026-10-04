"""Action registry — maps ActionType enums to handler instances.

Follows the open/closed principle: adding a new action type is
simply ``registry.register(ActionType.NEW, NewHandler())``.
"""

from __future__ import annotations

from action_agent.registry.base import ActionHandler
from action_agent.schemas.action import ActionType


class HandlerNotFoundError(Exception):
    """Raised when no handler is registered for the given action type."""


class ActionRegistry:
    """Type → Handler mapping with runtime registration."""

    def __init__(self) -> None:
        self._handlers: dict[ActionType, ActionHandler] = {}

    def register(self, action_type: ActionType, handler: ActionHandler) -> None:
        """Register a handler for an action type."""
        self._handlers[action_type] = handler

    def get_handler(self, action_type: ActionType | str) -> ActionHandler:
        """Look up the handler.  Accepts ActionType enum or raw string."""
        if isinstance(action_type, str):
            try:
                action_type = ActionType(action_type)
            except ValueError:
                raise HandlerNotFoundError(
                    f"Unknown action type: '{action_type}'. "
                    f"Registered: {[t.value for t in self._handlers]}"
                )
        handler = self._handlers.get(action_type)
        if handler is None:
            raise HandlerNotFoundError(
                f"No handler registered for '{action_type.value}'. "
                f"Registered: {[t.value for t in self._handlers]}"
            )
        return handler

    @property
    def registered_types(self) -> list[ActionType]:
        return list(self._handlers.keys())
