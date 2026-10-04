"""End-to-end pipeline for the Autonomous SaaS BI Engine.

Loads data through the appropriate adapter, runs all three ML agents
sequentially, and outputs structured JSON that a future LLM-based
Strategy Agent would consume.

Usage
-----
    python pipeline.py                          # defaults to data/raw/
    python pipeline.py --data-dir path/to/data  # custom data path
    python pipeline.py --adapter telco_churn    # explicit adapter

The pipeline auto-detects the adapter if not specified.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from loguru import logger

# Configure loguru
logger.remove()  # Remove default handler
logger.add(
    sys.stderr,
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
        "<level>{message}</level>"
    ),
    level="INFO",
)
logger.add(
    "logs/pipeline_{time:YYYY-MM-DD}.log",
    rotation="10 MB",
    retention="7 days",
    level="DEBUG",
)


def _detect_adapter_and_path(
    data_dir: str | Path,
) -> tuple[str, Path]:
    """Auto-detect which adapter to use based on files in the data directory.

    Returns (adapter_name, csv_path).
    """
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"Data directory not found: {data_dir}")

    # Check for known datasets
    for f in data_dir.iterdir():
        name_lower = f.name.lower()
        if "telco" in name_lower or "churn" in name_lower:
            return "telco_churn", f

    # Fallback: use first CSV
    csvs = list(data_dir.glob("*.csv"))
    if csvs:
        logger.warning(
            f"Could not auto-detect adapter — using first CSV: {csvs[0].name}"
        )
        return "telco_churn", csvs[0]

    raise FileNotFoundError(f"No CSV files found in {data_dir}")


def main() -> None:
    """Run the full BI pipeline."""
    parser = argparse.ArgumentParser(
        description="Autonomous SaaS BI Engine — ML Pipeline"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="data/raw",
        help="Directory containing raw data files (default: data/raw/)",
    )
    parser.add_argument(
        "--adapter",
        type=str,
        default=None,
        help="Adapter name (auto-detected if not specified)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output JSON file path (default: print to stdout)",
    )
    args = parser.parse_args()

    t0 = time.time()

    # ── Step 0: Detect adapter and load data ─────────────────────────
    logger.info("=" * 60)
    logger.info("Autonomous SaaS BI Engine — Pipeline Start")
    logger.info("=" * 60)

    adapter_name = args.adapter
    if adapter_name:
        data_path = Path(args.data_dir) / next(
            Path(args.data_dir).iterdir()
        ).name
    else:
        adapter_name, data_path = _detect_adapter_and_path(args.data_dir)

    logger.info(f"Adapter: {adapter_name}")
    logger.info(f"Data path: {data_path}")

    # Import adapter
    import adapters
    load_fn = adapters.get_adapter(adapter_name)

    records = load_fn(data_path)
    logger.info(f"Loaded {len(records)} canonical records")

    churned = sum(1 for r in records if r.churn_flag)
    logger.info(f"Churn rate: {churned}/{len(records)} ({100*churned/len(records):.1f}%)")

    # ── Step 1: User Behavior Agent ──────────────────────────────────
    logger.info("-" * 60)
    logger.info("Running Agent 1: User Behavior Agent")
    logger.info("-" * 60)

    from agents.user_behavior import run as run_behavior
    t1 = time.time()
    behavior_result = run_behavior(records)
    t1_elapsed = time.time() - t1

    logger.info(f"Agent 1 complete in {t1_elapsed:.1f}s")
    logger.info(
        f"  Clusters: {len(behavior_result.cluster_profiles)}, "
        f"Anomalous: {len(behavior_result.anomalous_clusters)}, "
        f"Method: {behavior_result.method_used}"
    )

    # ── Step 2: Churn Prediction Agent ───────────────────────────────
    logger.info("-" * 60)
    logger.info("Running Agent 2: Churn Prediction Agent")
    logger.info("-" * 60)

    from agents.churn_prediction import run as run_churn
    t2 = time.time()
    churn_result = run_churn(records)
    t2_elapsed = time.time() - t2

    logger.info(f"Agent 2 complete in {t2_elapsed:.1f}s")
    logger.info(
        f"  Concordance: {churn_result.survival_model_concordance}, "
        f"AUC: {churn_result.classifier_metrics.get('auc_roc', 'N/A')}"
    )

    # ── Step 3: Feature Analysis Agent ───────────────────────────────
    logger.info("-" * 60)
    logger.info("Running Agent 3: Feature Analysis Agent")
    logger.info("-" * 60)

    from agents.feature_analysis import run as run_features
    t3 = time.time()
    feature_result = run_features(records)
    t3_elapsed = time.time() - t3

    logger.info(f"Agent 3 complete in {t3_elapsed:.1f}s")
    logger.info(
        f"  Features analysed: {len(feature_result.effects)}, "
        f"Significant: {sum(1 for e in feature_result.effects if e.is_significant)}"
    )

    # ── Assemble combined output ─────────────────────────────────────
    total_elapsed = time.time() - t0

    combined_output = {
        "pipeline_metadata": {
            "adapter": adapter_name,
            "data_path": str(data_path),
            "n_records": len(records),
            "churn_rate": round(churned / len(records), 4),
            "total_time_seconds": round(total_elapsed, 2),
            "agent_times_seconds": {
                "user_behavior": round(t1_elapsed, 2),
                "churn_prediction": round(t2_elapsed, 2),
                "feature_analysis": round(t3_elapsed, 2),
            },
        },
        "user_behavior": behavior_result.model_dump(),
        "churn_prediction": churn_result.model_dump(),
        "feature_analysis": feature_result.model_dump(),
    }

    # ── Output ───────────────────────────────────────────────────────
    output_json = json.dumps(combined_output, indent=2, default=str)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_json, encoding="utf-8")
        logger.info(f"Output written to {output_path}")
    else:
        # Print summary to stdout (full JSON is too large)
        print("\n" + "=" * 60)
        print("PIPELINE OUTPUT SUMMARY")
        print("=" * 60)

        print(f"\n[DATA] Dataset: {adapter_name} ({len(records)} customers)")
        print(f"[TIME] Total time: {total_elapsed:.1f}s")

        print(f"\n[AGENT 1] User Behavior:")
        print(f"   Clusters: {len(behavior_result.cluster_profiles)}")
        for cp in behavior_result.cluster_profiles:
            flag = " ** ANOMALOUS **" if cp.is_anomalous else ""
            print(f"   - Cluster {cp.cluster_id}: {cp.size} customers -- {cp.label}{flag}")
        print(f"   Anomalous clusters: {behavior_result.anomalous_clusters}")

        print(f"\n[AGENT 2] Churn Prediction:")
        print(f"   Cox PH Concordance (C-index): {churn_result.survival_model_concordance}")
        print(f"   Classifier metrics: {churn_result.classifier_metrics}")
        print(f"   Top feature importances:")
        sorted_imp = sorted(
            churn_result.feature_importances.items(),
            key=lambda x: x[1], reverse=True
        )[:5]
        for feat, imp in sorted_imp:
            print(f"   - {feat}: {imp:.4f}")

        # Churn reason distribution
        reason_counts: dict[str, int] = {}
        for p in churn_result.predictions:
            reason_counts[p.churn_reason] = reason_counts.get(p.churn_reason, 0) + 1
        print(f"   Churn reason distribution: {reason_counts}")

        print(f"\n[AGENT 3] Feature Analysis (Causal):")
        print(f"   Method: {feature_result.method}")
        print(f"   Features analysed: {len(feature_result.effects)}")
        for eff in feature_result.effects:
            sig = "[SIG]" if eff.is_significant else "[ns] "
            print(
                f"   {sig} {eff.feature_name}: ATE={eff.ate:.4f} "
                f"[{eff.ci_lower:.4f}, {eff.ci_upper:.4f}]"
            )

        print("\n" + "=" * 60)
        print("Pipeline complete. Full JSON available with --output flag.")
        print("=" * 60)

        # Also write to default location
        default_output = Path("data/pipeline_output.json")
        default_output.parent.mkdir(parents=True, exist_ok=True)
        default_output.write_text(output_json, encoding="utf-8")
        logger.info(f"Full JSON output saved to {default_output}")


if __name__ == "__main__":
    main()
