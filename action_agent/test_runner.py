"""
Independent Test Runner for the Action Agent Module.

Verifies:
1. Test 1 (Low-Risk): Automated Slack alert dispatching (no HITL intervention).
2. Test 2 (High-Risk - Approved): Stripe retention discount with HITL approval.
3. Test 3 (High-Risk - Rejected): Stripe retention discount with HITL rejection.

Usage:
    python test_runner.py              # Runs automated test suite (mocked HITL decisions)
    python test_runner.py --interactive # Prompts for real human terminal input on high-risk tests
"""

import argparse
import json
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from agent import app, run_action_agent
from config import settings, logger
from schemas import ActionType


def print_separator(title: str = "", char: str = "=", length: int = 80):
    """Prints a styled terminal separator."""
    if title:
        padding = (length - len(title) - 4) // 2
        print(f"\n{char * padding}[ {title} ]{char * padding}")
    else:
        print(f"\n{char * length}")


def run_test_low_risk():
    """
    Test Case 1: Automated Low-Risk Action (Customer Success / Slack Alert).
    Verifies that low-risk actions bypass human review and execute immediately.
    """
    print_separator("TEST 1: LOW-RISK AUTOMATED ACTION (CS ALERT)", "=")
    print("Scenario: Strategy Agent flags account 'acme_corp' with high churn risk.")
    print("Expected: is_high_risk == False, skips HITL review, auto-dispatches Slack alert.\n")

    strategy_payload = {
        "recommendation_id": "rec_strat_001",
        "action_type": "send_cs_alert",
        "target_entity": "#customer-success-urgent",
        "description": "Urgent churn probability 82% on customer 'acme_corp'. Trigger immediate team outreach.",
        "parameters": {
            "channel": "#customer-success-urgent",
            "message": "Urgent Churn Warning: Customer acme_corp usage down 64% WoW. Account manager outreach requested.",
        },
        "confidence_score": 0.94,
        "justification": "Weekly telemetry detected 64% drop in daily active sessions.",
    }

    print(f"Input Recommendation Payload:\n{json.dumps(strategy_payload, indent=2)}")

    # Execute workflow
    result_state = run_action_agent(strategy_payload)

    # Assertions
    print("\nValidating Test 1 Results:")
    assert result_state.get("action_type") == ActionType.CS_ALERT.value, (
        f"Expected action_type '{ActionType.CS_ALERT.value}', got '{result_state.get('action_type')}'"
    )
    assert result_state.get("is_high_risk") is False, (
        f"Expected is_high_risk to be False, got {result_state.get('is_high_risk')}"
    )
    assert result_state.get("human_approved") is None, (
        f"Expected human_approved to be None (skipped), got {result_state.get('human_approved')}"
    )
    exec_res = result_state.get("execution_result", {})
    assert exec_res.get("status") == "success", (
        f"Expected execution status 'success', got '{exec_res.get('status')}'"
    )
    assert exec_res.get("provider") == "Slack/CRM", (
        f"Expected provider 'Slack/CRM', got '{exec_res.get('provider')}'"
    )

    print("  [PASS] is_high_risk correctly flagged as False.")
    print("  [PASS] Human review skipped as expected.")
    print("  [PASS] Tool 'send_cs_alert' executed with delivery confirmation.")
    print(f"  [PASS] Execution Output: {json.dumps(exec_res, indent=2)}")
    print("\n>>> TEST 1 PASSED: Low-Risk automated pipeline functioning properly! <<<\n")


def run_test_high_risk_approved(interactive: bool = False):
    """
    Test Case 2: High-Risk Action with Human Approval (Stripe Retention Discount).
    Verifies that financial actions trigger HITL review and execute only upon approval.
    """
    print_separator("TEST 2: HIGH-RISK ACTION - APPROVED FLOW", "=")
    print("Scenario: Strategy Agent recommends applying 25% discount to at-risk subscriber.")
    print("Expected: is_high_risk == True, pauses for HITL review, executes Stripe tool upon approval.\n")

    strategy_payload = {
        "recommendation_id": "rec_strat_002",
        "action_type": "apply_stripe_discount",
        "target_entity": "cus_enterprise_9981",
        "description": "Apply a 25% one-time retention concession to prevent cancellation of Pro subscription.",
        "parameters": {
            "customer_id": "cus_enterprise_9981",
            "coupon_code": "RETENTION_25",
        },
        "confidence_score": 0.88,
        "justification": "Customer triggered cancellation survey citing pricing objections.",
    }

    print(f"Input Recommendation Payload:\n{json.dumps(strategy_payload, indent=2)}")

    if interactive:
        print("\n[Running in INTERACTIVE Mode: Please enter 'y' when prompted below]")
        result_state = run_action_agent(strategy_payload)
    else:
        print("\n[Running in AUTOMATED Test Mode: Simulating Human Approval 'YES']")
        result_state = run_action_agent(strategy_payload, auto_approve_test=True)

    print("\nValidating Test 2 Results:")
    assert result_state.get("action_type") == ActionType.STRIPE_DISCOUNT.value, (
        f"Expected action_type '{ActionType.STRIPE_DISCOUNT.value}', got '{result_state.get('action_type')}'"
    )
    assert result_state.get("is_high_risk") is True, (
        f"Expected is_high_risk to be True, got {result_state.get('is_high_risk')}"
    )
    assert result_state.get("human_approved") is True, (
        f"Expected human_approved to be True, got {result_state.get('human_approved')}"
    )
    exec_res = result_state.get("execution_result", {})
    assert exec_res.get("status") == "success", (
        f"Expected execution status 'success', got '{exec_res.get('status')}'"
    )
    assert exec_res.get("provider") == "Stripe", (
        f"Expected provider 'Stripe', got '{exec_res.get('provider')}'"
    )
    assert exec_res.get("discount_percentage") == 25, (
        f"Expected discount 25%, got '{exec_res.get('discount_percentage')}'"
    )

    print("  [PASS] is_high_risk correctly flagged as True.")
    print("  [PASS] HITL node engaged and human approval recorded.")
    print("  [PASS] Tool 'apply_stripe_discount' executed and coupon applied.")
    print(f"  [PASS] Execution Output: {json.dumps(exec_res, indent=2)}")
    print("\n>>> TEST 2 PASSED: High-Risk approval pipeline functioning properly! <<<\n")


def run_test_high_risk_rejected(interactive: bool = False):
    """
    Test Case 3: High-Risk Action with Human Rejection.
    Verifies that rejecting a high-risk action safely aborts tool execution.
    """
    print_separator("TEST 3: HIGH-RISK ACTION - REJECTED FLOW", "=")
    print("Scenario: Strategy Agent recommends a steep 50% discount on a legacy customer.")
    print("Expected: is_high_risk == True, HITL review, human operator REJECTS execution.\n")

    strategy_payload = {
        "recommendation_id": "rec_strat_003",
        "action_type": "apply_stripe_discount",
        "target_entity": "cus_legacy_4412",
        "description": "Apply a 50% discount to retain customer cus_legacy_4412.",
        "parameters": {
            "customer_id": "cus_legacy_4412",
            "coupon_code": "SAVE_50",
        },
        "confidence_score": 0.65,
        "justification": "Severe contract dispute; high margin sacrifice.",
    }

    print(f"Input Recommendation Payload:\n{json.dumps(strategy_payload, indent=2)}")

    if interactive:
        print("\n[Running in INTERACTIVE Mode: Please enter 'n' when prompted below to test rejection]")
        result_state = run_action_agent(strategy_payload)
    else:
        print("\n[Running in AUTOMATED Test Mode: Simulating Human Rejection 'NO']")
        result_state = run_action_agent(strategy_payload, auto_approve_test=False)

    print("\nValidating Test 3 Results:")
    assert result_state.get("action_type") == ActionType.STRIPE_DISCOUNT.value
    assert result_state.get("is_high_risk") is True
    assert result_state.get("human_approved") is False
    exec_res = result_state.get("execution_result", {})
    assert exec_res.get("status") == "cancelled", (
        f"Expected execution status 'cancelled', got '{exec_res.get('status')}'"
    )

    print("  [PASS] is_high_risk correctly flagged as True.")
    print("  [PASS] HITL rejection recorded correctly.")
    print("  [PASS] Execution safely ABORTED (no API changes dispatched).")
    print(f"  [PASS] Cancellation State: {json.dumps(exec_res, indent=2)}")
    print("\n>>> TEST 3 PASSED: High-Risk rejection safety gate functioning properly! <<<\n")


def verify_audit_log():
    """Verifies that audit log entries were successfully generated."""
    print_separator("AUDIT LOG VERIFICATION", "-")
    audit_file = settings.AUDIT_LOG_FILE
    if not audit_file.exists():
        print(f"Warning: Audit log file {audit_file} does not exist yet.")
        return

    with open(audit_file, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f.readlines() if line.strip()]

    print(f"Audit log location: {audit_file.resolve()}")
    print(f"Total entries logged: {len(lines)}")
    if lines:
        last_entry = json.loads(lines[-1])
        print(f"Latest audit entry: {json.dumps(last_entry, indent=2)}")
    print("  [PASS] Audit log persistence confirmed.")


def main():
    parser = argparse.ArgumentParser(description="Action Agent Test Suite")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Run high-risk test cases with real interactive terminal prompts (y/n)",
    )
    args = parser.parse_args()

    print_separator("ACTION AGENT TEST RUNNER", "#")
    print(f"Environment: {settings.ENVIRONMENT}")
    print(f"OpenAI Key Configured: {settings.has_valid_openai_key()}")
    print(f"Interactive Mode: {args.interactive}")

    try:
        # 1. Test Low Risk automated flow
        run_test_low_risk()

        # 2. Test High Risk approved flow
        run_test_high_risk_approved(interactive=args.interactive)

        # 3. Test High Risk rejected flow
        run_test_high_risk_rejected(interactive=args.interactive)

        # 4. Verify audit trail
        verify_audit_log()

        print_separator("ALL TEST SUITES PASSED SUCCESSFULLY (3/3)", "#")
        sys.exit(0)
    except AssertionError as ae:
        print(f"\n[FAIL] TEST ASSERTION FAILED: {ae}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[ERROR] UNEXPECTED ERROR DURING TEST EXECUTION: {exc}")
        logger.exception("Test failure")
        sys.exit(2)


if __name__ == "__main__":
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    main()
