"""
Data Schemas and TypedDict State Definitions.

Defines Pydantic models for incoming strategy recommendations, tool parameters,
parsing results, and the LangGraph ActionState TypedDict.
"""

from enum import Enum
from typing import Any, Dict, List, Optional, Union
from typing_extensions import TypedDict
from pydantic import BaseModel, Field


class ActionType(str, Enum):
    """Enumeration of supported external automated and HITL action types."""
    A_B_TEST = "trigger_a_b_test"
    STRIPE_DISCOUNT = "apply_stripe_discount"
    CS_ALERT = "send_cs_alert"


class ABTestParameters(BaseModel):
    """Parameters required to trigger an A/B test flag in GrowthBook/feature flagging."""
    segment_id: str = Field(..., description="Target user segment identifier (e.g. 'churn_risk_tier1', 'enterprise_us')")
    experiment_name: str = Field(..., description="Unique experiment or feature flag identifier (e.g. 'onboarding_modal_v2')")


class StripeDiscountParameters(BaseModel):
    """Parameters required to apply a retention discount coupon in Stripe."""
    customer_id: str = Field(..., description="Stripe customer identifier (e.g. 'cus_987654321')")
    coupon_code: str = Field(..., description="Stripe discount coupon code (e.g. 'RETENTION_25', 'SAVE_50')")


class CSAlertParameters(BaseModel):
    """Parameters required to dispatch a customer success alert via Slack/CRM."""
    channel: str = Field(..., description="Slack channel or CRM queue (e.g. '#customer-success-urgent', '#churn-alerts')")
    message: str = Field(..., description="Detailed alert body with context, churn probability, and recommended outreach")


class StrategyRecommendation(BaseModel):
    """Structured recommendation received from upstream Strategy Agent."""
    recommendation_id: str = Field(..., description="Unique ID of the strategy proposal")
    action_type: str = Field(..., description="Suggested action type or target category")
    target_entity: str = Field(..., description="Target customer, segment, or channel")
    description: str = Field(..., description="High-level explanation of the proposed business strategy")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Raw parameters extracted by strategy agent")
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0, description="Confidence score from strategy evaluation")
    justification: Optional[str] = Field(default=None, description="Analytical reasoning justifying the action")


class ParsedAction(BaseModel):
    """Structured LLM output parsing raw strategy input into a verified tool call."""
    action_type: ActionType = Field(..., description="The verified action tool to execute")
    parameters: Dict[str, Any] = Field(..., description="Validated key-value parameters for the corresponding tool")
    is_high_risk: bool = Field(..., description="True if action entails financial, billing, or disruptive operational risk")
    risk_reason: str = Field(..., description="Explanation of why this action is flagged as high-risk or low-risk")
    summary: str = Field(..., description="Human-readable summary of the action intended for review or logging")


class AuditRecord(BaseModel):
    """Structured entry persisted to the immutable audit log."""
    audit_id: str
    timestamp_utc: str
    recommendation_id: Optional[str] = None
    action_type: str
    parameters: Dict[str, Any]
    is_high_risk: bool
    human_approved: Optional[bool]
    status: str
    execution_result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ActionState(TypedDict, total=False):
    """
    LangGraph Workflow State.

    Tracks the execution lifecycle of an action recommendation across all nodes.
    """
    recommendation_input: Union[Dict[str, Any], str]
    action_type: Optional[str]
    parameters: Dict[str, Any]
    is_high_risk: bool
    risk_reason: Optional[str]
    human_approved: Optional[bool]
    execution_result: Optional[Dict[str, Any]]
    audit_id: Optional[str]
    error: Optional[str]
