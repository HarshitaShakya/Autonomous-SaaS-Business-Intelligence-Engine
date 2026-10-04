"""Mock notification adapter.

Simulates alert delivery (Slack, PagerDuty, email, etc.).
Stores sent notifications so tests can assert on them.
"""

from __future__ import annotations

import asyncio
from typing import Any

from action_agent.adapters.base import AdapterResult, NotificationAdapter


class MockNotificationAdapter(NotificationAdapter):
    """Simulates a notification/alerting service."""

    def __init__(self) -> None:
        self._sent: list[dict[str, Any]] = []

    @property
    def sent_notifications(self) -> list[dict[str, Any]]:
        """Access to all notifications sent (for testing / verification)."""
        return list(self._sent)

    async def send_notification(
        self,
        channel: str,
        title: str,
        message: str,
        severity: str,
        metadata: dict[str, Any] | None = None,
    ) -> AdapterResult:
        await asyncio.sleep(0.02)

        entry = {
            "channel": channel,
            "title": title,
            "message": message,
            "severity": severity,
            "metadata": metadata or {},
        }
        self._sent.append(entry)

        return AdapterResult(
            success=True,
            adapter_name="MockNotification",
            action_performed=f"Sent '{severity}' notification to '{channel}': {title}",
            details=entry,
            # Notifications are not reversible — no previous_state
        )
