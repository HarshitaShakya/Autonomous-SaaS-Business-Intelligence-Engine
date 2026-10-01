"""
Mocked External API Tools for the Action Agent Module.

Implements simulated integrations for:
1. GrowthBook / Feature Flagging: trigger_a_b_test
2. Stripe Billing / Concessions: apply_stripe_discount
3. Slack / CRM Alerts: send_cs_alert
"""

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

try:
    from langchain_core.tools import tool
except ImportError:
    # Graceful fallback decorator if langchain_core is not yet installed in runtime
    def tool(func):
        func.name = func.__name__
        func.description = func.__doc__ or ""
        func.invoke = lambda args: func(**args)
        return func

from config import logger, settings
from schemas import (
    ABTestParameters,
    ActionType,
    CSAlertParameters,
    StripeDiscountParameters,
)


@tool
def trigger_a_b_test(segment_id: str, experiment_name: str) -> str:
    """
    Simulates triggering an A/B test or feature flag via GrowthBook.

    Args:
        segment_id: Target audience or user cohort identifier.
        experiment_name: Unique name or key of the experiment.

    Returns:
        JSON string containing the execution confirmation and experiment metadata.
    """
    logger.info(f"[GrowthBook API] Triggering experiment '{experiment_name}' for segment '{segment_id}'")
    
    # Simulate API latency
    if settings.MOCK_TOOL_DELAY_SECONDS > 0:
        time.sleep(settings.MOCK_TOOL_DELAY_SECONDS)

    payload = {
        "status": "success",
        "provider": "GrowthBook",
        "action": "trigger_a_b_test",
        "experiment_id": f"exp_{uuid.uuid4().hex[:8]}",
        "experiment_name": experiment_name,
        "segment_id": segment_id,
        "state": "active",
        "traffic_allocation": "50/50",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload, indent=2)


@tool
def apply_stripe_discount(customer_id: str, coupon_code: str) -> str:
    """
    Simulates applying a promotional or retention discount coupon in Stripe.

    Args:
        customer_id: Stripe customer identifier (e.g., 'cus_987654321').
        coupon_code: Valid coupon code (e.g., 'RETENTION_25', 'SAVE_50').

    Returns:
        JSON string containing the discount confirmation and updated invoice state.
    """
    logger.info(f"[Stripe API] Applying coupon '{coupon_code}' to customer '{customer_id}'")

    # Simulate API latency
    if settings.MOCK_TOOL_DELAY_SECONDS > 0:
        time.sleep(settings.MOCK_TOOL_DELAY_SECONDS)

    # Derive discount rate from coupon code or default to 20%
    discount_pct = 20
    if "25" in coupon_code:
        discount_pct = 25
    elif "50" in coupon_code:
        discount_pct = 50
    elif "15" in coupon_code:
        discount_pct = 15

    payload = {
        "status": "success",
        "provider": "Stripe",
        "action": "apply_stripe_discount",
        "discount_id": f"di_{uuid.uuid4().hex[:10]}",
        "customer_id": customer_id,
        "coupon_code": coupon_code,
        "discount_percentage": discount_pct,
        "currency": "usd",
        "duration": "once",
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "invoice_preview": {
            "subtotal": 199.00,
            "discount_amount": round(199.00 * (discount_pct / 100.0), 2),
            "new_total": round(199.00 * (1.0 - (discount_pct / 100.0)), 2),
        },
    }
    return json.dumps(payload, indent=2)


@tool
def send_cs_alert(channel: str, message: str) -> str:
    """
    Simulates sending an urgent customer success or churn alert via Slack or CRM.

    Args:
        channel: Target Slack channel or CRM queue (e.g., '#churn-alerts').
        message: Detailed alert message content.

    Returns:
        JSON string confirming message delivery with dispatch metadata.
    """
    logger.info(f"[Slack/CRM API] Dispatching alert to channel '{channel}'")

    # Simulate API latency
    if settings.MOCK_TOOL_DELAY_SECONDS > 0:
        time.sleep(settings.MOCK_TOOL_DELAY_SECONDS)

    payload = {
        "status": "success",
        "provider": "Slack/CRM",
        "action": "send_cs_alert",
        "message_id": f"msg_{uuid.uuid4().hex[:12]}",
        "channel": channel,
        "message_preview": (message[:80] + "...") if len(message) > 80 else message,
        "delivered": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return json.dumps(payload, indent=2)


# Registry mapping action names to their respective LangChain tool functions
TOOL_REGISTRY: Dict[str, Any] = {
    ActionType.A_B_TEST.value: trigger_a_b_test,
    ActionType.STRIPE_DISCOUNT.value: apply_stripe_discount,
    ActionType.CS_ALERT.value: send_cs_alert,
    # Aliases for flexibility
    "trigger_a_b_test": trigger_a_b_test,
    "apply_stripe_discount": apply_stripe_discount,
    "send_cs_alert": send_cs_alert,
}


def execute_tool(action_type: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
    """
    Dispatches execution to the appropriate tool based on action_type and parameters.

    Args:
        action_type: Registered action identifier.
        parameters: Keyword arguments required by the target tool.

    Returns:
        Dict[str, Any]: Parsed JSON payload returned by the tool.

    Raises:
        ValueError: If action_type is unregistered or parameters fail validation.
    """
    tool_func = TOOL_REGISTRY.get(action_type)
    if not tool_func:
        raise ValueError(f"Unsupported action_type: '{action_type}'. Registered tools: {list(TOOL_REGISTRY.keys())}")

    # Validate parameters using target Pydantic schema
    if action_type in (ActionType.A_B_TEST.value, "trigger_a_b_test"):
        validated_args = ABTestParameters(**parameters).model_dump()
    elif action_type in (ActionType.STRIPE_DISCOUNT.value, "apply_stripe_discount"):
        validated_args = StripeDiscountParameters(**parameters).model_dump()
    elif action_type in (ActionType.CS_ALERT.value, "send_cs_alert"):
        validated_args = CSAlertParameters(**parameters).model_dump()
    else:
        validated_args = parameters

    # Invoke tool via LangChain tool API or direct call
    if hasattr(tool_func, "invoke"):
        raw_result = tool_func.invoke(validated_args)
    else:
        raw_result = tool_func(**validated_args)

    if isinstance(raw_result, str):
        try:
            return json.loads(raw_result)
        except json.JSONDecodeError:
            return {"raw_output": raw_result}
    elif isinstance(raw_result, dict):
        return raw_result
    else:
        return {"output": str(raw_result)}
