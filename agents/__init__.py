"""ML Agents package.

Contains the three classical ML/statistical agents that consume
``CanonicalRecord`` instances and produce typed Pydantic outputs:

* **User Behavior Agent** (``user_behavior``) — clustering and drift detection.
* **Churn Prediction Agent** (``churn_prediction``) — survival analysis and
  binary classification.
* **Feature Analysis Agent** (``feature_analysis``) — Double ML causal
  inference.

Each agent is wrapped as a LangChain ``RunnableLambda`` with typed I/O so a
future LLM-based Strategy Agent can invoke them consistently via LCEL.
"""
