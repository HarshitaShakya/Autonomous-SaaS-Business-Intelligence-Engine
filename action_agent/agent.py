"""
LangGraph Action Agent Workflow.

Implements the multi-stage LangGraph workflow for consuming Strategy Agent
recommendations, evaluating risk levels, gating high-risk actions through
Human-in-the-Loop (HITL) approval, and safely dispatching tool executions.
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

# Optional LangGraph imports with seamless fallback implementation
try:
    from langgraph.graph import StateGraph, START, END
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    START = "__start__"
    END = "__end__"

    class StateGraph:
        """Lightweight fallback compatible with LangGraph StateGraph API."""
        def __init__(self, state_schema):
            self.state_schema = state_schema
            self.nodes = {}
            self.edges = {}
            self.conditional_edges = {}

        def add_node(self, name, func):
            self.nodes[name] = func

        def add_edge(self, start_node, end_node):
            self.edges[start_node] = end_node

        def add_conditional_edges(self, source, router, path_map):
            self.conditional_edges[source] = (router, path_map)

        def compile(self):
            return CompiledGraph(self)

    class CompiledGraph:
        """Compiled runner for fallback StateGraph."""
        def __init__(self, graph: StateGraph):
            self.graph = graph

        def invoke(self, state: Dict[str, Any]) -> Dict[str, Any]:
            current_state = dict(state)
            current_node = self.graph.edges.get(START, "parse_strategy")

            while current_node != END:
                if current_node not in self.graph.nodes:
                    break
                node_func = self.graph.nodes[current_node]
                updates = node_func(current_state)
                if isinstance(updates, dict):
                    current_state.update(updates)

                # Check conditional edge
                if current_node in self.graph.conditional_edges:
                    router, path_map = self.graph.conditional_edges[current_node]
                    next_route_key = router(current_state)
                    current_node = path_map.get(next_route_key, END)
                elif current_node in self.graph.edges:
                    current_node = self.graph.edges[current_node]
                else:
                    break

            return current_state


# Optional LangChain OpenAI import
try:
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import SystemMessage, HumanMessage
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from config import logger, settings
from schemas import (
    ActionState,
    ActionType,
    AuditRecord,
    ParsedAction,
    StrategyRecommendation,
)
from tools import execute_tool


# ============================================================================
# AUDIT LOGGING UTILITY
# ============================================================================

def record_audit_log(state: ActionState) -> str:
    """
    Appends an immutable audit log entry to the configured JSONL file.

    Args:
        state: Final or intermediate ActionState.

    Returns:
        str: Generated audit record ID.
    """
    audit_id = f"aud_{uuid.uuid4().hex[:12]}"
    rec_input = state.get("recommendation_input", {})
    rec_id = None
    if isinstance(rec_input, dict):
        rec_id = rec_input.get("recommendation_id")

    status = "completed"
    exec_res = state.get("execution_result", {})
    if exec_res and isinstance(exec_res, dict):
        status = exec_res.get("status", "completed")

    audit_entry = AuditRecord(
        audit_id=audit_id,
        timestamp_utc=datetime.now(timezone.utc).isoformat(),
        recommendation_id=rec_id,
        action_type=state.get("action_type") or "unknown",
        parameters=state.get("parameters") or {},
        is_high_risk=state.get("is_high_risk", False),
        human_approved=state.get("human_approved"),
        status=status,
        execution_result=state.get("execution_result"),
        error=state.get("error"),
    )

    try:
        with open(settings.AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(audit_entry.model_dump_json() + "\n")
        logger.debug(f"Audit log recorded: {audit_id}")
    except Exception as ex:
        logger.error(f"Failed to write audit log: {ex}")

    return audit_id


# ============================================================================
# NODE 1: PARSE STRATEGY NODE
# ============================================================================

def parse_strategy_node(state: ActionState) -> ActionState:
    """
    Parses upstream recommendation inputs into structured tool invocations.

    Leverages ChatOpenAI(model='gpt-4o') with structured output schemas when
    configured with an API key, or utilizes a deterministic heuristic parser
    for local/offline test execution.

    Enforces critical safety invariant:
    Any action modifying billing, discounts, or Stripe credentials MUST be
    flagged as is_high_risk=True.
    """
    raw_input = state.get("recommendation_input")
    logger.info("Entering [parse_strategy_node]")

    # Normalize raw input into dictionary
    input_data: Dict[str, Any] = {}
    if isinstance(raw_input, str):
        try:
            input_data = json.loads(raw_input)
        except json.JSONDecodeError:
            input_data = {"description": raw_input}
    elif isinstance(raw_input, dict):
        input_data = raw_input
    else:
        input_data = {"raw": str(raw_input)}

    action_type: Optional[str] = None
    parameters: Dict[str, Any] = {}
    is_high_risk: bool = False
    risk_reason: str = ""

    parsed_successfully = False

    # Attempt LLM-based parsing if ChatOpenAI is available and key is configured
    if OPENAI_AVAILABLE and settings.has_valid_openai_key():
        try:
            logger.info(f"Invoking ChatOpenAI({settings.MODEL_NAME}) for structured action parsing...")
            llm = ChatOpenAI(
                model=settings.MODEL_NAME,
                temperature=settings.TEMPERATURE,
                api_key=settings.OPENAI_API_KEY,
            )
            structured_llm = llm.with_structured_output(ParsedAction)

            prompt = (
                "You are the Action Agent in an Autonomous SaaS Business Intelligence platform.\n"
                "Extract the target action and parameters from the following strategy recommendation.\n"
                "Available tools:\n"
                "- 'trigger_a_b_test': GrowthBook/feature experiments (params: segment_id, experiment_name)\n"
                "- 'apply_stripe_discount': Customer discounts/coupons (params: customer_id, coupon_code)\n"
                "- 'send_cs_alert': Slack or CRM team notifications (params: channel, message)\n\n"
                "MANDATORY SAFETY POLICY: Any financial, discount, pricing, or billing modifications "
                "in Stripe MUST be marked as is_high_risk=True.\n\n"
                f"Strategy Recommendation:\n{json.dumps(input_data, indent=2)}"
            )

            result: ParsedAction = structured_llm.invoke([
                SystemMessage(content="You are an autonomous operations compiler."),
                HumanMessage(content=prompt)
            ])

            action_type = result.action_type.value if hasattr(result.action_type, "value") else str(result.action_type)
            parameters = result.parameters
            is_high_risk = result.is_high_risk
            risk_reason = result.risk_reason
            parsed_successfully = True
            logger.info(f"LLM successfully parsed action '{action_type}' (is_high_risk={is_high_risk})")
        except Exception as err:
            logger.warning(f"OpenAI LLM parsing encountered exception: {err}. Falling back to heuristic parser.")
            parsed_successfully = False

    # Heuristic fallback parser (for offline runs, mock testing, or LLM failure)
    if not parsed_successfully:
        logger.info("Executing rule-based deterministic strategy parser...")
        raw_text = (
            str(input_data.get("action_type", "")) + " " +
            str(input_data.get("description", "")) + " " +
            json.dumps(input_data.get("parameters", {})) + " " +
            str(input_data.get("target_entity", ""))
        ).lower()

        extracted_params = input_data.get("parameters", {})

        # Rule 1: Stripe / Discount / Billing operations -> High Risk
        if any(kw in raw_text for kw in ["stripe", "discount", "coupon", "billing", "credit", "price", "refund"]):
            action_type = ActionType.STRIPE_DISCOUNT.value
            is_high_risk = True
            risk_reason = "Financial modification: Applying discounts alters recurring revenue and billing contracts."
            parameters = {
                "customer_id": extracted_params.get("customer_id") or input_data.get("target_entity") or "cus_default",
                "coupon_code": extracted_params.get("coupon_code") or "RETENTION_25",
            }
        # Rule 2: A/B Testing / Feature flag toggles -> Low Risk
        elif any(kw in raw_text for kw in ["a/b", "experiment", "growthbook", "feature_flag", "cohort_test"]):
            action_type = ActionType.A_B_TEST.value
            is_high_risk = False
            risk_reason = "Automated experimentation: GrowthBook feature flag with 50/50 cohort distribution."
            parameters = {
                "segment_id": extracted_params.get("segment_id") or input_data.get("target_entity") or "churn_risk_segment",
                "experiment_name": extracted_params.get("experiment_name") or "retention_onboarding_v1",
            }
        # Rule 3: Customer Success Alerts / Slack / CRM -> Low Risk
        else:
            action_type = ActionType.CS_ALERT.value
            is_high_risk = False
            risk_reason = "Operational notification: Dispatches Slack/CRM alert without modifying production data."
            parameters = {
                "channel": extracted_params.get("channel") or "#churn-alerts",
                "message": extracted_params.get("message") or input_data.get("description") or "Automated BI churn alert.",
            }

    # Strict secondary safety assertion: Stripe actions CANNOT be low risk
    if action_type in (ActionType.STRIPE_DISCOUNT.value, "apply_stripe_discount"):
        is_high_risk = True
        if not risk_reason:
            risk_reason = "Safety Override: Any Stripe pricing or discount action requires human review."

    return {
        "action_type": action_type,
        "parameters": parameters,
        "is_high_risk": is_high_risk,
        "risk_reason": risk_reason,
    }


# ============================================================================
# NODE 2: HUMAN REVIEW NODE (HITL)
# ============================================================================

def human_review_node(state: ActionState) -> ActionState:
    """
    Pauses execution to solicit interactive terminal approval for high-risk actions.

    Displays an inspection card outlining the proposed action, target entity,
    parameters, and risk evaluation. Prompts the operator for explicit (y/n)
    authorization.
    """
    logger.info("Entering [human_review_node] - Action requires Human-in-the-Loop authorization")

    action_type = state.get("action_type", "unknown")
    parameters = state.get("parameters", {})
    risk_reason = state.get("risk_reason", "High-risk operational or financial action.")

    # Ensure stdout handles unicode if possible
    try:
        import sys
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    print("\n" + "=" * 76)
    print(" [!] HUMAN-IN-THE-LOOP (HITL) APPROVAL REQUIRED")
    print("=" * 76)
    print(f" Action Type:     {action_type}")
    print(f" Target Params:   {json.dumps(parameters, indent=18).strip()}")
    print(f" Risk Assessment: {risk_reason}")
    print("=" * 76)

    # Check for programmatic mock override (used during non-interactive unit testing)
    pre_approved = state.get("human_approved")
    auto_approve_test = state.get("auto_approve_test")

    if auto_approve_test is not None:
        approved = bool(auto_approve_test)
        logger.info(f"[Test Mode Mock] Automatic HITL decision resolved to: {approved}")
        print(f" [Test Mode] Programmatic input received: {'YES (Approved)' if approved else 'NO (Rejected)'}")
    elif pre_approved is not None:
        approved = bool(pre_approved)
        logger.info(f"[State Pre-set] Human approval state already populated: {approved}")
        print(f" [Pre-set State] Approval status: {'YES (Approved)' if approved else 'NO (Rejected)'}")
    else:
        # Live interactive prompt
        try:
            choice = input(" >> Authorize execution of this high-risk action? [y/N]: ").strip().lower()
            approved = choice in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            logger.warning("Interactive prompt interrupted or EOF received. Defaulting to REJECT.")
            approved = False

    if approved:
        print(" [APPROVED] Human Operator: Action execution granted.\n")
        logger.info(f"Operator APPROVED execution for action '{action_type}'")
    else:
        print(" [REJECTED] Human Operator: Action execution denied.\n")
        logger.warning(f"Operator REJECTED execution for action '{action_type}'")

    return {"human_approved": approved}


# ============================================================================
# NODE 3: EXECUTE ACTION NODE
# ============================================================================

def execute_action_node(state: ActionState) -> ActionState:
    """
    Executes the designated tool or cancels execution if rejected during HITL review.

    Records the outcome in the state and persists an immutable audit log entry.
    """
    logger.info("Entering [execute_action_node]")

    action_type = state.get("action_type")
    parameters = state.get("parameters", {})
    is_high_risk = state.get("is_high_risk", False)
    human_approved = state.get("human_approved")

    # Safety Gate: Abort if high-risk action was not approved
    if is_high_risk and not human_approved:
        logger.warning(f"Execution cancelled: High-risk action '{action_type}' was REJECTED by human operator.")
        result = {
            "status": "cancelled",
            "reason": "Execution cancelled: Action was rejected by human operator during HITL review.",
            "action_type": action_type,
            "parameters": parameters,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        updated_state = {"execution_result": result}
        audit_id = record_audit_log({**state, **updated_state})
        updated_state["audit_id"] = audit_id
        return updated_state

    # Execute the requested tool
    try:
        logger.info(f"Executing tool '{action_type}' with parameters {parameters}")
        result = execute_tool(action_type, parameters)
        logger.info(f"Tool '{action_type}' executed successfully.")
        updated_state = {"execution_result": result}
    except Exception as exc:
        logger.error(f"Error executing tool '{action_type}': {exc}", exc_info=True)
        result = {
            "status": "error",
            "error_message": str(exc),
            "action_type": action_type,
            "parameters": parameters,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        updated_state = {"execution_result": result, "error": str(exc)}

    # Record immutable audit trail
    audit_id = record_audit_log({**state, **updated_state})
    updated_state["audit_id"] = audit_id
    return updated_state


# ============================================================================
# ROUTER LOGIC & GRAPH ASSEMBLY
# ============================================================================

def route_after_parse(state: ActionState) -> str:
    """
    Conditional router directing high-risk actions to human review and
    low-risk actions directly to execution.

    Args:
        state: ActionState after strategy parsing.

    Returns:
        str: Next node identifier ('human_review' or 'execute_action').
    """
    is_high_risk = state.get("is_high_risk", False)
    if is_high_risk:
        logger.info("Router: High-risk action detected -> Routing to [human_review]")
        return "human_review"
    logger.info("Router: Low-risk action detected -> Routing directly to [execute_action]")
    return "execute_action"


def build_action_graph():
    """
    Constructs and compiles the Action Agent StateGraph.

    Graph Topology:
        START -> parse_strategy -> (conditional branch)
                   ├─ [is_high_risk=True]  -> human_review -> execute_action -> END
                   └─ [is_high_risk=False] ─────────────────> execute_action -> END

    Returns:
        Compiled StateGraph instance.
    """
    workflow = StateGraph(ActionState)

    # Register nodes
    workflow.add_node("parse_strategy", parse_strategy_node)
    workflow.add_node("human_review", human_review_node)
    workflow.add_node("execute_action", execute_action_node)

    # Define execution edges
    workflow.add_edge(START, "parse_strategy")
    workflow.add_conditional_edges(
        "parse_strategy",
        route_after_parse,
        {
            "human_review": "human_review",
            "execute_action": "execute_action",
        }
    )
    workflow.add_edge("human_review", "execute_action")
    workflow.add_edge("execute_action", END)

    return workflow.compile()


# Global compiled workflow runner
app = build_action_graph()


def run_action_agent(recommendation_input: Union[Dict[str, Any], str], **kwargs) -> ActionState:
    """
    Convenience interface to execute the Action Agent workflow for a single input.

    Args:
        recommendation_input: Raw strategy payload or JSON string.
        **kwargs: Optional state seed parameters (e.g. auto_approve_test).

    Returns:
        ActionState: Final state dictionary after workflow execution.
    """
    initial_state: ActionState = {
        "recommendation_input": recommendation_input,
        "action_type": None,
        "parameters": {},
        "is_high_risk": False,
        "human_approved": None,
        "execution_result": None,
        "error": None,
        **kwargs,
    }
    return app.invoke(initial_state)
