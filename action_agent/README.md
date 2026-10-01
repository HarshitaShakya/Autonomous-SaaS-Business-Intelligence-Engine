# Action Agent Module for Autonomous SaaS Business Intelligence

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/LangGraph-v1.x%2B-purple.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic](https://img.shields.io/badge/Pydantic-v2.0%2B-brightgreen.svg)](https://docs.pydantic.dev/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

A standalone, production-ready **Action Agent** module designed for an **Autonomous SaaS Business Intelligence platform**. Built with **Python** and **LangGraph (v1.x+)**, this agent bridges the gap between high-level analytical strategy recommendations and real-world operational execution.

It consumes structured strategy proposals, parses target tools and parameters, performs automated risk classification, enforces mandatory **Human-in-the-Loop (HITL)** approval for high-risk operations (e.g. Stripe retention discounts), and dispatches automated actions (GrowthBook A/B tests, Slack alerts) with an immutable audit log.

---

## 🚀 Key Features

- **LangGraph State Machine**: Orchestrated via a `StateGraph(ActionState)` with conditional routing between automated paths and interactive human checkpoints.
- **Automated vs. High-Risk Segregation**:
  - **Low-Risk (Automated)**: Instant dispatch for telemetry alerts (Slack/CRM) and feature flags (GrowthBook).
  - **High-Risk (Gated)**: Pauses execution to solicit terminal human review `(y/n)` for billing changes, discount codes, or revenue-impacting actions.
- **LLM + Heuristic Fallback Parsing**: Employs `ChatOpenAI(model="gpt-4o")` with Pydantic structured outputs when configured with an API key, with a zero-dependency deterministic parser for seamless local testing and offline CI pipelines.
- **Extensible Tool Integrations**:
  - `@tool trigger_a_b_test`: Simulates GrowthBook experiment cohort toggles.
  - `@tool apply_stripe_discount`: Simulates Stripe customer retention coupon applications.
  - `@tool send_cs_alert`: Simulates urgent Slack/CRM notification dispatches.
- **Immutable Audit Logging**: Emits structured JSON lines (`audit_log.jsonl`) for SOC2 compliance, accounting reconciliation, and post-mortem analysis.

---

## 📂 Project Structure

```
action_agent_project/
├── config.py             # Environment variables, Pydantic settings, and logging
├── schemas.py            # Pydantic models and TypedDict LangGraph states
├── tools.py              # Mocked API tool integrations (GrowthBook, Stripe, Slack/CRM)
├── agent.py              # LangGraph workflow, nodes, and router logic
├── test_runner.py        # Independent test suite verifying automated vs HITL actions
├── requirements.txt      # Python dependencies
├── README.md             # Project overview and specifications
├── Memory.md             # Agent memory state tracking, context storage, and log schemas
├── Plan.md               # Execution roadmap, agent orchestration steps, and safety rules
└── Architecture.md       # High-level system design, data flows, and module interactions
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- Python 3.10 or higher installed.

### 2. Environment Setup
Clone or navigate to the project directory:

```bash
cd action_agent_project
```

Create and activate a virtual environment:

```bash
# Windows (PowerShell)
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 3. Environment Configuration (`.env`)
Create a `.env` file in `action_agent_project/`:

```env
# OpenAI API Key (Optional for mock test runs, required for live GPT-4o parsing)
OPENAI_API_KEY=your-openai-api-key-here
MODEL_NAME=gpt-4o
TEMPERATURE=0.0

# Runtime Mode
ENVIRONMENT=development
LOG_LEVEL=INFO
ENABLE_HITL=true
AUDIT_LOG_FILE=audit_log.jsonl
TOOL_TIMEOUT_SECONDS=30
MOCK_TOOL_DELAY_SECONDS=0.2
```

> **Note**: If `OPENAI_API_KEY` is not provided or left blank, the agent automatically utilizes its built-in deterministic heuristic parser.

---

## 🧪 Running the Test Suite

The test suite includes 3 comprehensive test cases:
1. **Test 1 (Low-Risk)**: Automated Slack/CRM alert execution (skips human review).
2. **Test 2 (High-Risk - Approved)**: Stripe discount requiring human authorization (verifies execution upon approval).
3. **Test 3 (High-Risk - Rejected)**: Stripe discount with human rejection (verifies cancellation and safety abort).

### Automated Mode (Ideal for CI/CD)
Runs all tests with simulated approval decisions without blocking for user input:

```bash
python test_runner.py
```

### Interactive Mode (Hands-on HITL Demonstration)
Prompts for live operator input `(y/n)` directly in the terminal:

```bash
python test_runner.py --interactive
```

---

## 📖 Architectural Highlights

### LangGraph Topology

```
START 
  │
  ▼
[parse_strategy] 
  │
  ├─► (is_high_risk == False) ─────────────────────────┐
  │                                                    │
  └─► (is_high_risk == True) ──► [human_review] (HITL) │
                                       │               │
                                       ▼               ▼
                               [execute_action] ◄──────┘
                                       │
                                       ▼
                                      END
```

For complete architectural details, sequence diagrams, and memory specifications:
- Read [Architecture.md](file:///c:/Users/khushi/Agent/action_agent_project/Architecture.md)
- Read [Memory.md](file:///c:/Users/khushi/Agent/action_agent_project/Memory.md)
- Read [Plan.md](file:///c:/Users/khushi/Agent/action_agent_project/Plan.md)

---

## 📝 License
MIT License.
