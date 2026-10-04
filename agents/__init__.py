"""ML & Reasoning Agents package.

Contains the three classical ML/statistical agents and the LLM-based
Strategy Agent that consume upstream outputs and produce typed Pydantic
results:

* **User Behavior Agent** (``user_behavior``) — clustering and drift detection.
* **Churn Prediction Agent** (``churn_prediction``) — survival analysis and
  binary classification.
* **Feature Analysis Agent** (``feature_analysis``) — Double ML causal
  inference.
* **Strategy Agent** (``strategy_agent``) — LLM-based reasoning over the
  three upstream outputs to produce ranked business recommendations for the
  Action Agent.

Each agent is wrapped as a LangChain ``RunnableLambda`` with typed I/O so
they compose into the same LangGraph / LCEL pipeline.
"""
