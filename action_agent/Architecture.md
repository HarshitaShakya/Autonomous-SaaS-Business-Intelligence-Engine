# System Architecture: Action Agent Module

This document outlines the high-level architecture, module interactions, data flows, and security boundaries of the **Action Agent** within the Autonomous SaaS Business Intelligence platform.

---

## 1. System Topology & Context

The Action Agent bridges analytical strategy generation and real-world operational execution. It serves as the operational execution engine of the autonomous BI loop:

```mermaid
graph LR
    subgraph Analytics Layer
        SA[Strategy Agent] -->|Structured Recommendation JSON| AA[Action Agent]
    end

    subgraph Action Agent Module
        AA --> PARSE[Parse & Risk Evaluation]
        PARSE --> ROUTER{Risk Router}
        ROUTER -->|Low Risk| EXEC[Execution Engine]
        ROUTER -->|High Risk| HITL[Human-in-the-Loop Gate]
        HITL -->|Approved| EXEC
        HITL -->|Rejected| ABORT[Cancellation Handler]
        EXEC --> AUDIT[(Audit Trail Store)]
        ABORT --> AUDIT
    end

    subgraph External Infrastructure
        EXEC -->|Simulated Webhook| GB[GrowthBook A/B API]
        EXEC -->|Simulated REST| STRIPE[Stripe Billing API]
        EXEC -->|Simulated Dispatch| SLACK[Slack / CRM Webhook]
    end
```

---

## 2. Component Breakdown

The codebase is partitioned into distinct, decoupled modules:

| File | Module Responsibility | Key Classes & Functions |
|---|---|---|
| `config.py` | Environment management, secrets loading, and logging | `Settings`, `setup_logger`, `settings` singleton |
| `schemas.py` | Data validation, Pydantic contracts, and LangGraph TypedDict | `ActionType`, `ActionState`, `ParsedAction`, `StrategyRecommendation`, `AuditRecord` |
| `tools.py` | External API mock integrations decorated with `@tool` | `trigger_a_b_test`, `apply_stripe_discount`, `send_cs_alert`, `execute_tool` |
| `agent.py` | Core LangGraph orchestration, node implementations, and routing logic | `parse_strategy_node`, `human_review_node`, `execute_action_node`, `build_action_graph`, `app` |
| `test_runner.py` | Standalone verification test suite | `run_test_low_risk`, `run_test_high_risk_approved`, `run_test_high_risk_rejected` |

---

## 3. LangGraph Execution Topology

The agent's state machine is modeled as a directed graph using LangGraph's `StateGraph`:

```mermaid
flowchart TD
    START([START]) --> parse_strategy[parse_strategy_node]
    parse_strategy --> route_after_parse{route_after_parse}

    route_after_parse -- "is_high_risk == False" --> execute_action[execute_action_node]
    route_after_parse -- "is_high_risk == True" --> human_review[human_review_node]

    human_review --> execute_action
    execute_action --> END([END])

    style START fill:#4CAF50,stroke:#388E3C,color:#fff
    style END fill:#E53935,stroke:#C62828,color:#fff
    style human_review fill:#FF9800,stroke:#F57C00,color:#fff
    style parse_strategy fill:#2196F3,stroke:#1976D2,color:#fff
    style execute_action fill:#9C27B0,stroke:#7B1FA2,color:#fff
```

### Node Specifications:
1. **`parse_strategy`**:
   - Ingests `recommendation_input` from `ActionState`.
   - Uses `ChatOpenAI(model="gpt-4o")` (or deterministic rule-based fallback) to resolve the action into valid tool arguments and evaluate operational risk.
   - Programmatically guarantees `is_high_risk = True` for financial/pricing operations.

2. **`human_review`**:
   - Engaged exclusively if `is_high_risk == True`.
   - Displays proposed operation details and prompts operator for `(y/n)` terminal confirmation.
   - Updates `human_approved` state key with boolean decision.

3. **`execute_action`**:
   - Inspects `is_high_risk` and `human_approved`.
   - If approved or low-risk, dispatches tool via `execute_tool(action_type, parameters)`.
   - If rejected, generates a structured cancellation result without external network invocation.
   - Appends an entry to the immutable `audit_log.jsonl`.

---

## 4. End-to-End Sequence Flows

### Scenario A: Low-Risk Flow (Automated Slack Churn Alert)

```mermaid
sequenceDiagram
    autonumber
    participant SA as Strategy Agent
    participant AA as LangGraph (Action Agent)
    participant PS as parse_strategy_node
    participant EA as execute_action_node
    participant SL as Slack API Tool
    participant LOG as Audit Log

    SA->>AA: Ingest recommendation payload
    AA->>PS: Execute parse_strategy_node
    PS->>PS: Identify action = 'send_cs_alert' (is_high_risk=False)
    PS->>AA: Return state {action_type, parameters, is_high_risk: False}
    Note over AA: route_after_parse routes directly to execute_action
    AA->>EA: Execute execute_action_node
    EA->>SL: send_cs_alert(channel, message)
    SL-->>EA: Return {status: 'success', message_id: 'msg_...'}
    EA->>LOG: Write AuditRecord(status='success')
    EA-->>AA: Return execution_result
    AA-->>SA: Complete Action State
```

---

### Scenario B: High-Risk Flow (Stripe Retention Discount with HITL Approval)

```mermaid
sequenceDiagram
    autonumber
    participant SA as Strategy Agent
    participant AA as LangGraph (Action Agent)
    participant PS as parse_strategy_node
    participant HR as human_review_node (HITL)
    participant OP as Human Operator
    participant EA as execute_action_node
    participant ST as Stripe API Tool
    participant LOG as Audit Log

    SA->>AA: Ingest recommendation payload
    AA->>PS: Execute parse_strategy_node
    PS->>PS: Identify action = 'apply_stripe_discount' (is_high_risk=True)
    PS->>AA: Return state {is_high_risk: True}
    Note over AA: route_after_parse routes to human_review
    AA->>HR: Execute human_review_node
    HR->>OP: Display Authorization Card & prompt [y/N]
    OP-->>HR: Input 'y' (Approved)
    HR->>AA: Return state {human_approved: True}
    AA->>EA: Execute execute_action_node
    EA->>EA: Verify human_approved == True
    EA->>ST: apply_stripe_discount(customer_id, coupon_code)
    ST-->>EA: Return {status: 'success', discount_id: 'di_...'}
    EA->>LOG: Write AuditRecord(status='success', human_approved=True)
    EA-->>AA: Return execution_result
```

---

### Scenario C: High-Risk Flow (Stripe Retention Discount with HITL Rejection)

```mermaid
sequenceDiagram
    autonumber
    participant SA as Strategy Agent
    participant AA as LangGraph (Action Agent)
    participant PS as parse_strategy_node
    participant HR as human_review_node (HITL)
    participant OP as Human Operator
    participant EA as execute_action_node
    participant ST as Stripe API Tool
    participant LOG as Audit Log

    SA->>AA: Ingest recommendation payload
    AA->>PS: Execute parse_strategy_node
    PS->>AA: Return state {is_high_risk: True}
    AA->>HR: Execute human_review_node
    HR->>OP: Display Authorization Card & prompt [y/N]
    OP-->>HR: Input 'n' (Rejected)
    HR->>AA: Return state {human_approved: False}
    AA->>EA: Execute execute_action_node
    EA->>EA: Detect human_approved == False -> Abort tool invocation
    Note over EA,ST: Stripe API Tool is NEVER called
    EA->>LOG: Write AuditRecord(status='cancelled', human_approved=False)
    EA-->>AA: Return execution_result {status: 'cancelled'}
```

---

## 5. Security and Guardrails

1. **Deterministic Override**: In `parse_strategy_node`, rule-based safety overrides run after LLM processing to prevent adversarial prompt injections from classifying discount/pricing tools as low-risk.
2. **Defensive Parameter Boundaries**: Pydantic models validate data types and prevent arbitrary code execution or invalid parameter injection.
3. **Audit Immutability**: Logs are append-only to satisfy regulatory tracking standards.
