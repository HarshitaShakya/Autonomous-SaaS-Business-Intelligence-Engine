"""Mock pricing adapter.

Simulates a billing / pricing service (e.g. Stripe, Chargebee).
Stores discount state per segment for verification and rollback.
"""

from __future__ import annotations

import asyncio
from typing import Any

from action_agent.adapters.base import AdapterResult, PricingAdapter


class MockPricingAdapter(PricingAdapter):
    """Simulates a pricing/billing service."""

    def __init__(self) -> None:
        self._discounts: dict[str, dict[str, Any]] = {}

    async def apply_discount(
        self, segment: str, discount_pct: float, duration_days: int
    ) -> AdapterResult:
        await asyncio.sleep(0.05)

        previous = self._discounts.get(segment, {}).copy()
        self._discounts[segment] = {
            "active": True,
            "discount_pct": discount_pct,
            "duration_days": duration_days,
        }
        return AdapterResult(
            success=True,
            adapter_name="MockPricing",
            action_performed=f"Applied {discount_pct}% discount to segment '{segment}' for {duration_days} days",
            details=self._discounts[segment],
            previous_state=previous,
        )

    async def revert_discount(self, segment: str) -> AdapterResult:
        await asyncio.sleep(0.05)

        previous = self._discounts.get(segment, {}).copy()
        self._discounts[segment] = {"active": False, "discount_pct": 0.0, "duration_days": 0}
        return AdapterResult(
            success=True,
            adapter_name="MockPricing",
            action_performed=f"Reverted discount for segment '{segment}'",
            details=self._discounts[segment],
            previous_state=previous,
        )

    async def get_pricing_state(self, segment: str) -> dict[str, Any]:
        return self._discounts.get(segment, {"active": False, "discount_pct": 0.0, "duration_days": 0})
