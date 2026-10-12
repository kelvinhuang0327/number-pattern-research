"""
P38A 2024 OOF Prediction Rebuild — CLI Entry Point.

Usage:
    python scripts/run_p38a_2024_oof_prediction_rebuild.py \\
        --input-csv data/mlb_2024/processed/mlb_2024_game_identity_outcomes_joined.csv \\
        --output-dir outputs/predictions/PAPER/p38a_2024_oof \\
        --paper-only

PAPER_ONLY=True
production_ready=False
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import pandas as pd

# Allow running from repo root
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from wbc_backend.recommendation.p38a_retrosheet_feature_adapter import (
    build_feature_dataframe,
)
from wbc_backend.recommendation.p38a_oof_prediction_builder import build_oof_predictions

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# ── Gate constants ──────────────────────────────────────────────────────────
P38A_2024_OOF_PREDICTION_READY = "P38A_2024_OOF_PREDICTION_READY"
P38A_BLOCKED_FEATURE_COVERAGE_INSUFFICIENT = "P38A_BLOCKED_FEATURE_COVERAGE_INSUFFICIENT"
P38A_BLOCKED_LEAKAGE_RISK = "P38A_BLOCKED_LEAKAGE_RISK"
P38A_FAIL_INPUT_MISSING = "P38A_FAIL_INPUT_MISSING"
P38A_FAIL_NON_DETERMINISTIC = "P38A_FAIL_NON_DETERMINISTIC"

MIN_COVERAGE_PCT = 90.0

PAPER_ONLY: bool = True
PRODUCTION_READY: bool = False


def _run(input_csv: Path, output_dir: Path, paper_only: bool) -> str:
    """Core logic. Returns gate constant string."""

    if not paper_only:
        logger.error("This script must be run with --paper-only. Aborting.")
        return P38A_BLOCKED_LEAKAGE_RISK

    if not input_csv.exists():
        logger.error("Input CSV not found: %s", input_csv)
        return P38A_FAIL_INPUT_MISSING

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── Feature adapter ──────────────────────────────────────────────────
    logger.info("Running feature adapter on %s", input_csv)
    try:
        adapter_result = build_feature_dataframe(input_csv)
    except Exception as exc:
        logger.error("Feature adapter failed: %s", exc)
        return P38A_BLOCKED_LEAKAGE_RISK

    feature_df = adapter_result.feature_df

    # ── Load labels ──────────────────────────────────────────────────────
    raw_df = pd.read_csv(input_csv, dtype={"game_id": str})
    label_map = raw_df.set_index("game_id")["y_true_home_win"].to_dict()

    y_true = feature_df["game_id"].map(label_map)
    missing_labels = y_true.isna().sum()
    if missing_labels > 0:
        logger.warning("%d rows missing y_true labels", missing_labels)

    feature_df_clean = feature_df[~y_true.isna()].reset_index(drop=True)
    y_true_clean = y_true[~y_true.isna()].reset_index(drop=True).astype(int)

    # ── OOF predictions (run twice for determinism check) ────────────────
    logger.info("Building OOF predictions (run 1/2)...")
    result1 = build_oof_predictions(feature_df_clean, y_true_clean)

    logger.info("Building OOF predictions (run 2/2, determinism check)...")
    result2 = build_oof_predictions(feature_df_clean, y_true_clean)

    if result1.output_hash != result2.output_hash:
        logger.error(
            "Non-deterministic output: hash1=%s hash2=%s",
            result1.output_hash,
            result2.output_hash,
        )
        return P38A_FAIL_NON_DETERMINISTIC

    logger.info("Determinism check PASSED (hash=%s)", result1.output_hash[:16])

    # ── Coverage gate ────────────────────────────────────────────────────
    coverage = result1.metrics.coverage_pct
    if coverage < MIN_COVERAGE_PCT:
        logger.error(
            "Coverage %.1f%% < required %.1f%%",
            coverage,
            MIN_COVERAGE_PCT,
        )
        return P38A_BLOCKED_FEATURE_COVERAGE_INSUFFICIENT

    # ── Write outputs ─────────────────────────────────────────────────────
    pred_path = output_dir / "p38a_2024_oof_predictions.csv"
    result1.predictions_df.to_csv(pred_path, index=False)
    logger.info("Predictions written to %s", pred_path)

    metrics_dict = {
        "brier": result1.metrics.brier,
        "log_loss": result1.metrics.log_loss_val,
        "brier_skill_score": result1.metrics.brier_skill_score,
        "base_rate": result1.metrics.base_rate,
        "n_predictions": result1.metrics.n_predictions,
        "coverage_pct": result1.metrics.coverage_pct,
        "total_input_rows": len(feature_df),
        "fold_count": result1.fold_count,
        "output_hash": result1.output_hash,
        "model_version": "p38a_walk_forward_logistic_v1",
        "paper_only": True,
        "production_ready": False,
    }
    metrics_path = output_dir / "p38a_oof_metrics.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics_dict, f, indent=2)
    logger.info("Metrics written to %s", metrics_path)

    gate_result = {
        "gate": P38A_2024_OOF_PREDICTION_READY,
        "coverage_pct": coverage,
        "brier": result1.metrics.brier,
        "deterministic": True,
        "output_hash": result1.output_hash,
        "paper_only": True,
        "production_ready": False,
    }
    gate_path = output_dir / "p38a_gate_result.json"
    with open(gate_path, "w") as f:
        json.dump(gate_result, f, indent=2)
    logger.info("Gate result: %s", P38A_2024_OOF_PREDICTION_READY)

    return P38A_2024_OOF_PREDICTION_READY


def main() -> None:
    parser = argparse.ArgumentParser(description="P38A 2024 OOF Prediction Rebuild")
    parser.add_argument(
        "--input-csv",
        required=True,
        type=Path,
        help="Path to mlb_2024_game_identity_outcomes_joined.csv",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directory for output files",
    )
    parser.add_argument(
        "--paper-only",
        action="store_true",
        default=False,
        help="Required flag; confirms paper-only mode",
    )
    args = parser.parse_args()

    gate = _run(
        input_csv=args.input_csv,
        output_dir=args.output_dir,
        paper_only=args.paper_only,
    )

    print(gate)

    if gate == P38A_2024_OOF_PREDICTION_READY:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
