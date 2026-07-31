#!/usr/bin/env python3
"""P13 Walk-Forward Logistic OOF CLI.

Runs walk-forward cross-validated logistic regression on a P12 ablation
variant CSV and produces an OOF report JSON and Markdown sibling file.

Usage:
    python scripts/run_p13_walk_forward_logistic_oof.py \\
        --input outputs/predictions/PAPER/2026-05-11/ablation/variant_no_rest.csv \\
        --output-dir outputs/predictions/PAPER/2026-05-12/p13_walk_forward_logistic \\
        [--features feat1 feat2 ...] \\
        [--folds 5] \\
        [--label home_win]

Notes:
    - paper_only=true is enforced; no production data writes.
    - gate_decision is PASS iff bss_oof > 0 (no forging allowed).
    - home_win is derived from Home Score > Away Score if absent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

# Ensure project root is in path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from wbc_backend.models.walk_forward_logistic import (
    DEFAULT_FEATURES,
    WalkForwardLogisticBaseline,
)

# ---------------------------------------------------------------------------
# P12 reference metrics
# ---------------------------------------------------------------------------
P12_BEST_VARIANT = "no_rest"
P12_BEST_BSS = -0.027537

# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------


def brier_skill_score(y_true: np.ndarray, p_pred: np.ndarray) -> float:
    """Compute Brier Skill Score relative to climatological baseline.

    BSS = 1 - Brier_model / Brier_baseline
    where Brier_baseline uses the mean label rate as constant prediction.
    A positive BSS means the model beats the climatological baseline.
    """
    brier_model = float(brier_score_loss(y_true, p_pred))
    # Baseline: always predict the mean prevalence
    climatology = float(np.mean(y_true))
    brier_baseline = float(brier_score_loss(y_true, np.full_like(p_pred, climatology)))
    if brier_baseline == 0.0:
        return 0.0
    return float(1.0 - brier_model / brier_baseline)


def expected_calibration_error(
    y_true: np.ndarray,
    p_pred: np.ndarray,
    n_bins: int = 10,
) -> float:
    """Compute Expected Calibration Error (ECE) with equal-width bins."""
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    ece = 0.0
    n = len(y_true)
    for lo, hi in zip(bins[:-1], bins[1:]):
        mask = (p_pred >= lo) & (p_pred < hi)
        if mask.sum() == 0:
            continue
        mean_conf = float(p_pred[mask].mean())
        mean_acc = float(y_true[mask].mean())
        ece += (mask.sum() / n) * abs(mean_conf - mean_acc)
    return float(ece)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="P13 Walk-Forward Logistic OOF evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input CSV (P12 ablation variant)",
    )
    parser.add_argument(
        "--output-dir",
        default=(
            f"outputs/predictions/PAPER/"
            f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}/"
            "p13_walk_forward_logistic"
        ),
        help="Directory to write oof_report.json and oof_report.md",
    )
    parser.add_argument(
        "--features",
        nargs="+",
        default=None,
        help=(
            "Feature column names (default: indep_recent_win_rate_delta "
            "indep_starter_era_delta)"
        ),
    )
    parser.add_argument(
        "--folds",
        type=int,
        default=5,
        help="Number of walk-forward folds (default: 5)",
    )
    parser.add_argument(
        "--label",
        default="home_win",
        help="Label column name (default: home_win)",
    )
    return parser.parse_args(argv)


def load_and_prepare(input_path: str, label_col: str) -> pd.DataFrame:
    """Load input CSV and derive label if necessary.

    If 'home_win' column is absent but 'Home Score' and 'Away Score'
    columns are present, derives home_win = (Home Score > Away Score).
    Raises ValueError if derivation is not possible.
    """
    df = pd.read_csv(input_path)

    if label_col not in df.columns:
        if label_col == "home_win" and "Home Score" in df.columns and "Away Score" in df.columns:
            df["home_win"] = (df["Home Score"] > df["Away Score"]).astype(int)
            print(
                f"[INFO] Derived 'home_win' from Home Score > Away Score "
                f"({df['home_win'].sum()} wins / {len(df)} games)",
                file=sys.stderr,
            )
        else:
            raise ValueError(
                f"Label column '{label_col}' not found in input and cannot be derived. "
                f"Available columns: {list(df.columns)}"
            )

    return df


def run_oof(args: argparse.Namespace) -> None:
    """Execute walk-forward OOF and write reports."""
    input_path = os.path.abspath(args.input)
    output_dir = Path(args.output_dir)
    features = args.features or DEFAULT_FEATURES
    label_col = args.label

    print(f"[P13] Input   : {input_path}", file=sys.stderr)
    print(f"[P13] Features: {features}", file=sys.stderr)
    print(f"[P13] Folds   : {args.folds}", file=sys.stderr)
    print(f"[P13] Label   : {label_col}", file=sys.stderr)
    print(f"[P13] Output  : {output_dir}", file=sys.stderr)

    # Load and prepare data
    df = load_and_prepare(input_path, label_col)

    # Fit walk-forward model
    model = WalkForwardLogisticBaseline(
        features=features,
        n_folds=args.folds,
        time_column="Date",
        min_train_size=200,
        regularization=1.0,
    )
    oof = model.fit_predict_oof(df, label_col=label_col)
    fold_meta = model.fold_metadata()

    y_true = oof["y_true"].values.astype(int)
    p_oof = oof["p_oof"].values.astype(float)

    # Compute metrics
    bss = brier_skill_score(y_true, p_oof)
    brier = float(brier_score_loss(y_true, p_oof))
    ece = expected_calibration_error(y_true, p_oof)
    ll = float(log_loss(y_true, p_oof))

    bss_delta = float(bss - P12_BEST_BSS)
    gate_decision = "PASS" if bss > 0 else "FAIL"

    print(f"\n[P13] bss_oof         = {bss:.6f}", file=sys.stderr)
    print(f"[P13] bss_delta_vs_p12 = {bss_delta:+.6f}", file=sys.stderr)
    print(f"[P13] gate_decision    = {gate_decision}", file=sys.stderr)

    # Build report dict
    report: dict = {
        "bss_oof": round(bss, 6),
        "ece_oof": round(ece, 6),
        "brier_oof": round(brier, 6),
        "logloss_oof": round(ll, 6),
        "n_folds": len(fold_meta),
        "n_samples_total": len(oof),
        "n_features": len(features),
        "model_family": "logistic",
        "feature_set": features,
        "compare_to_p12_best_variant": P12_BEST_VARIANT,
        "compare_to_p12_bss": P12_BEST_BSS,
        "bss_delta_vs_p12": round(bss_delta, 6),
        "gate_decision": gate_decision,
        "paper_only": True,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_input": input_path,
        "fold_metadata": fold_meta,
    }

    # Write outputs
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "oof_report.json"
    md_path = output_dir / "oof_report.md"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, default=str)
    print(f"[P13] Written: {json_path}", file=sys.stderr)

    # Predictions CSV (deterministic; no wall-clock timestamps)
    csv_path = output_dir / "oof_predictions.csv"
    oof_out = oof.copy()
    oof_out["source_model"] = "p13_walk_forward_logistic"
    oof_out["source_bss_oof"] = round(bss, 6)
    oof_out["paper_only"] = True
    # Convert datetime columns to ISO strings for CSV portability
    for col in ["train_window_start", "train_window_end", "predict_window_start", "predict_window_end"]:
        if col in oof_out.columns:
            oof_out[col] = oof_out[col].astype(str)
    oof_out.to_csv(csv_path, index=False)
    print(f"[P13] Written: {csv_path}", file=sys.stderr)

    # Markdown report
    fold_rows = "\n".join(
        f"| {m['fold_id']} | {m['train_size']} | {m['predict_size']} "
        f"| {m['train_window_start']} | {m['train_window_end']} "
        f"| {m['predict_window_start']} | {m['predict_window_end']} |"
        for m in fold_meta
    )

    gate_badge = "✅ PASS" if gate_decision == "PASS" else "❌ FAIL"

    md_content = f"""# P13 Walk-Forward Logistic OOF Report

Generated: {report['generated_at_utc']}

## Gate Decision: {gate_badge}

| Metric | Value |
|--------|-------|
| BSS (OOF) | {bss:.6f} |
| ECE (OOF) | {ece:.6f} |
| Brier Score (OOF) | {brier:.6f} |
| Log-Loss (OOF) | {ll:.6f} |
| n_folds | {len(fold_meta)} |
| n_samples_total | {len(oof)} |
| n_features | {len(features)} |

## P12 Comparison

| Item | Value |
|------|-------|
| P12 best variant | {P12_BEST_VARIANT} |
| P12 BSS | {P12_BEST_BSS:.6f} |
| P13 BSS | {bss:.6f} |
| Delta | {bss_delta:+.6f} |
| Gate | **{gate_decision}** (BSS {'> 0' if bss > 0 else '<= 0'}) |

## Features Used

```
{chr(10).join(f"- {f}" for f in features)}
```

## Fold Metadata

| Fold | Train Size | Predict Size | Train Start | Train End | Pred Start | Pred End |
|------|-----------|--------------|-------------|-----------|------------|----------|
{fold_rows}

## Source

- Input: `{input_path}`
- paper_only: true
- MLB PAPER_ONLY gate: enforced

## Next Phase

{"→ Proceed to P2 (P14 strategy simulation spine activation): BSS > 0 confirmed." if gate_decision == "PASS" else "→ Proceed to P3 (LightGBM model family comparison): BSS <= 0, logistic baseline insufficient."}
"""

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"[P13] Written: {md_path}", file=sys.stderr)

    # Print final summary to stdout for easy capture
    print(f"bss_oof={bss:.6f}")
    print(f"bss_delta_vs_p12={bss_delta:+.6f}")
    print(f"gate_decision={gate_decision}")


def main() -> None:
    """Entry point."""
    args = parse_args()
    run_oof(args)


if __name__ == "__main__":
    main()
