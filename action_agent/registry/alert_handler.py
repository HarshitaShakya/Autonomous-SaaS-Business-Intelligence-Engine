"""Alert / notification action handler.

Sends notifications via the NotificationAdapter.
Notifications are irreversible — rollback is not supported.
"""

from __future__ import annotations

from typing import Any

from action_agent.adapters.base import AdapterResult, NotificationAdapter
from action_agent.registry.base import ActionHandler
from action_agent.schemas.action import ActionPlan


class AlertActionHandler(ActionHandler):
    """Handles ALERT actions."""

    def __init__(self, adapter: NotificationAdapter) -> None:
        self._adapter = adapter

    @property
    def action_type_name(self) -> str:
        return "Alert"

    @property
    def rollback_supported(self) -> bool:
        return False  # Cannot un-send a notification

    async def execute(self, plan: ActionPlan) -> AdapterResult:
        channel = plan.parameters.get("channel", "product_team")
        severity = plan.parameters.get("severity", "INFO")
        title = plan.parameters.get("title", plan.description or f"Alert: {plan.target}")
        message = plan.parameters.get(
            "message",
            f"Action Agent alert for segment '{plan.target_segment}': {plan.description}",
        )
        return await self._adapter.send_notification(
            channel=channel,
            title=title,
            message=message,
            severity=severity,
            metadata={"action_id": plan.action_id, "target": plan.target},
        )

    async def rollback(self, rollback_data: dict[str, Any]) -> AdapterResult:
        return AdapterResult(
            success=False,
            adapter_name="Notification",
            error="Notifications cannot be rolled back",
        )
