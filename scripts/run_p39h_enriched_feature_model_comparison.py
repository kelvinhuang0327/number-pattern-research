"""
P39H — Time-Aware Enriched Feature Model Comparison
SCRIPT_VERSION = "p39h_enriched_feature_model_comparison_v1"
PAPER_ONLY = True

Compare P38A baseline (p_oof) vs logistic regression trained on P39G Statcast
rolling features using a strict time-aware train/test split.

No odds, no live betting, no production write.

Usage:
  PYTHONPATH=. .venv/bin/python scripts/run_p39h_enriched_feature_model_comparison.py \\
    --input-file data/pybaseball/local_only/p39g_enriched_p38a_oof_fullseason.csv \\
    --out-json outputs/predictions/PAPER/p39h_enriched_feature_model_comparison_20260515.json \\
    --out-report 00-BettingPlan/20260513/p39h_enriched_feature_model_comparison_report_20260515.md \\
    --test-start-date 2024-08-01 \\
    --model logistic \\
    --execute

Acceptance marker: P39H_MODEL_COMPARISON_SCRIPT_READY_20260515
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.preprocessing import StandardScaler

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCRIPT_VERSION = "p39h_enriched_feature_model_comparison_v1"
PAPER_ONLY: bool = True

BRIDGE_FILE = Path(
    "data/mlb_2024/processed/mlb_2024_game_identity_outcomes_joined.csv"
)

# All allowed rolling Statcast features (pregame-safe, no odds, no leakage)
STATCAST_FEATURE_COLS: list[str] = [
    "home_rolling_pa_proxy",
    "home_rolling_avg_launch_speed",
    "home_rolling_hard_hit_rate_proxy",
    "home_rolling_barrel_rate_proxy",
    "away_rolling_pa_proxy",
    "away_rolling_avg_launch_speed",
    "away_rolling_hard_hit_rate_proxy",
    "away_rolling_barrel_rate_proxy",
    "diff_rolling_avg_launch_speed",
    "diff_rolling_hard_hit_rate_proxy",
    "diff_sample_size",
]

# Feature set = Statcast features + baseline p_oof as an input signal
ENRICHED_FEATURE_COLS: list[str] = STATCAST_FEATURE_COLS + ["p_oof"]

# Patterns that indicate odds / sportsbook leakage — never allowed in features
BANNED_FEATURE_PATTERNS: tuple[str, ...] = (
    "odds",
    "moneyline",
    "sportsbook",
    "spread",
    "total",
    "vig",
    "implied",
    "ml_",
    "juice",
    "clv",
    "closing_line",
    "opening_line",
    "bet_size",
    "kelly",
    "edge",
)

# P39H_MODEL_COMPARISON_SCRIPT_READY_20260515


# ---------------------------------------------------------------------------
# Leakage / safety checks
# ---------------------------------------------------------------------------


def check_no_banned_features(feature_cols: list[str]) -> None:
    """Raise ValueError if any feature column matches a banned odds pattern."""
    violations = [
        col
        for col in feature_cols
        if any(pat in col.lower() for pat in BANNED_FEATURE_PATTERNS)
    ]
    if violations:
        raise ValueError(
            f"[LEAKAGE] Banned odds/sportsbook features detected: {violations}. "
            "Remove these before running the comparison."
        )


def check_no_target_in_features(
    feature_cols: list[str], target_col: str = "y_true_home_win"
) -> None:
    """Raise ValueError if the target column appears in the feature list."""
    if target_col in feature_cols:
        raise ValueError(
            f"[LEAKAGE] Target column '{target_col}' must not appear in feature_cols."
        )


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_and_join_data(
    input_file: Path,
    bridge_file: Path = BRIDGE_FILE,
) -> pd.DataFrame:
    """
    Load enriched P39G CSV and join y_true_home_win from the bridge.

    Raises FileNotFoundError if either file is missing.
    Raises RuntimeError if join produces null y_true rows.
    """
    if not input_file.exists():
        raise FileNotFoundError(f"Enriched CSV not found: {input_file}")
    if not bridge_file.exists():
        raise FileNotFoundError(f"Bridge file not found: {bridge_file}")

    df = pd.read_csv(input_file)
    bridge = pd.read_csv(bridge_file, usecols=["game_id", "y_true_home_win"])

    merged = df.merge(bridge, on="game_id", how="left")

    null_y = merged["y_true_home_win"].isnull().sum()
    if null_y > 0:
        raise RuntimeError(
            f"[DATA] {null_y} rows missing y_true_home_win after bridge join. "
            "Cannot compute metrics without ground truth."
        )

    merged["game_date"] = pd.to_datetime(merged["game_date"])
    return merged


# ---------------------------------------------------------------------------
# Time-aware split
# ---------------------------------------------------------------------------


def time_aware_split(
    df: pd.DataFrame,
    test_start_date: str,
    date_col: str = "game_date",
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split DataFrame chronologically at test_start_date.

    Returns (train_df, test_df) with no overlap.
    Raises ValueError if either split is empty.
    """
    cutoff = pd.Timestamp(test_start_date)
    train_df = df[df[date_col] < cutoff].copy()
    test_df = df[df[date_col] >= cutoff].copy()

    if len(train_df) == 0:
        raise ValueError(
            f"[SPLIT] Time-aware split produced empty train set at cutoff={test_start_date}."
        )
    if len(test_df) == 0:
        raise ValueError(
            f"[SPLIT] Time-aware split produced empty test set at cutoff={test_start_date}."
        )

    # Safety: confirm no date overlap
    if train_df[date_col].max() >= cutoff:
        raise RuntimeError(
            "[SPLIT] Train set contains dates >= test_start_date — potential leakage."
        )

    return train_df, test_df


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------


def _bss(brier: float, base_rate: float) -> float:
    """Brier Skill Score vs naive base-rate forecast."""
    naive_brier = base_rate * (1.0 - base_rate)
    if naive_brier == 0.0:
        return 0.0
    return float(1.0 - brier / naive_brier)


def compute_baseline_metrics(test_df: pd.DataFrame) -> dict[str, Any]:
    """
    Compute metrics for the P38A baseline (p_oof used directly as probability).
    """
    y_true = test_df["y_true_home_win"].to_numpy(dtype=float)
    p_oof = test_df["p_oof"].to_numpy(dtype=float)
    base_rate = float(y_true.mean())

    brier = float(brier_score_loss(y_true, p_oof))
    ll = float(log_loss(y_true, p_oof))
    bss = _bss(brier, base_rate)

    return {
        "model": "p38a_baseline_p_oof",
        "brier": round(brier, 6),
        "log_loss": round(ll, 6),
        "bss_vs_base_rate": round(bss, 6),
        "base_rate": round(base_rate, 4),
        "n_test": int(len(y_true)),
    }


def compute_enriched_metrics(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    feature_cols: list[str],
    model_type: str = "logistic",
) -> dict[str, Any]:
    """
    Train a model on train_df, evaluate on test_df.

    Returns metrics dict. Raises ValueError if feature cols are missing.
    """
    missing = [c for c in feature_cols if c not in train_df.columns]
    if missing:
        raise ValueError(f"[FEATURES] Required feature columns not found: {missing}")

    X_train = train_df[feature_cols].to_numpy(dtype=float)
    y_train = train_df["y_true_home_win"].to_numpy(dtype=float)
    X_test = test_df[feature_cols].to_numpy(dtype=float)
    y_test = test_df["y_true_home_win"].to_numpy(dtype=float)

    # Constant target guard
    if len(np.unique(y_train)) < 2:
        return {
            "model": model_type,
            "error": "CONSTANT_TARGET_TRAIN",
            "brier": None,
            "log_loss": None,
            "bss_vs_base_rate": None,
            "n_train": int(len(y_train)),
            "n_test": int(len(y_test)),
        }

    # Scale features (fit on train only)
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    if model_type == "logistic":
        model = LogisticRegression(
            C=1.0,
            max_iter=1000,
            solver="lbfgs",
            random_state=42,
        )
        model.fit(X_train_scaled, y_train)
        y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]

        # Coefficients for interpretability
        coefs = dict(zip(feature_cols, model.coef_[0].tolist()))
    else:
        raise ValueError(f"Unsupported model type: {model_type}")

    base_rate = float(y_test.mean())
    brier = float(brier_score_loss(y_test, y_pred_proba))
    ll = float(log_loss(y_test, y_pred_proba))
    bss = _bss(brier, base_rate)

    return {
        "model": model_type,
        "feature_cols": feature_cols,
        "n_train": int(len(y_train)),
        "n_test": int(len(y_test)),
        "brier": round(brier, 6),
        "log_loss": round(ll, 6),
        "bss_vs_base_rate": round(bss, 6),
        "base_rate": round(base_rate, 4),
        "coef": {k: round(v, 6) for k, v in coefs.items()},
    }


def interpret_comparison(
    baseline: dict[str, Any],
    enriched: dict[str, Any],
) -> dict[str, Any]:
    """
    Compare baseline vs enriched metrics and produce interpretation.

    Returns delta_brier, delta_log_loss, interpretation label.
    """
    b_brier = baseline["brier"]
    e_brier = enriched.get("brier")

    if e_brier is None:
        return {
            "delta_brier": None,
            "delta_log_loss": None,
            "interpretation": "FAILED",
            "marker": "P39H_ENRICHED_MODEL_COMPARISON_FAILED_20260515",
            "note": enriched.get("error", "unknown"),
        }

    delta_brier = round(float(e_brier) - float(b_brier), 6)
    delta_ll = round(
        float(enriched.get("log_loss", 0)) - float(baseline.get("log_loss", 0)), 6
    )

    # Interpretation thresholds (conservative for PAPER_ONLY)
    if delta_brier < -0.001:
        interp = "IMPROVED"
        marker = "P39H_ENRICHED_MODEL_COMPARISON_PASS_20260515"
    elif delta_brier > 0.001:
        interp = "DEGRADED"
        marker = "P39H_ENRICHED_MODEL_COMPARISON_NO_IMPROVEMENT_20260515"
    else:
        interp = "INCONCLUSIVE"
        marker = "P39H_ENRICHED_MODEL_COMPARISON_NO_IMPROVEMENT_20260515"

    return {
        "delta_brier": delta_brier,
        "delta_log_loss": delta_ll,
        "interpretation": interp,
        "marker": marker,
        "note": (
            "delta_brier < 0 means enriched model is better (lower Brier is better). "
            "No production edge claim. Paper-only research comparison."
        ),
    }


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------


def build_full_metrics(
    baseline: dict[str, Any],
    enriched: dict[str, Any],
    comparison: dict[str, Any],
    test_start_date: str,
    run_at: str,
) -> dict[str, Any]:
    return {
        "script_version": SCRIPT_VERSION,
        "paper_only": PAPER_ONLY,
        "generated_at": run_at,
        "split": {
            "type": "TIME_AWARE",
            "test_start_date": test_start_date,
            "train_rows": enriched.get("n_train"),
            "test_rows": enriched.get("n_test"),
        },
        "baseline": baseline,
        "enriched": enriched,
        "comparison": comparison,
        "guards": {
            "odds_features": "NONE",
            "leakage_violations": 0,
            "random_split": False,
            "production_edge_claim": False,
        },
    }


def write_json_report(metrics: dict[str, Any], out_json: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, default=str)
    print(f"[P39H] JSON written: {out_json}")


def write_markdown_report(metrics: dict[str, Any], out_report: Path) -> None:
    out_report.parent.mkdir(parents=True, exist_ok=True)
    sp = metrics["split"]
    bl = metrics["baseline"]
    en = metrics["enriched"]
    cp = metrics["comparison"]

    interp = cp.get("interpretation", "UNKNOWN")
    marker = cp.get("marker", "")

    lines = [
        "# P39H — Time-Aware Enriched Feature Model Comparison Report",
        f"**Date**: {metrics['generated_at'][:10]}  ",
        f"**Script**: `{metrics['script_version']}`  ",
        f"**PAPER_ONLY**: {metrics['paper_only']}  ",
        "",
        "---",
        "",
        "## 1. Split Summary",
        "",
        f"| Field | Value |",
        f"|-------|-------|",
        f"| Split type | TIME_AWARE (chronological) |",
        f"| Test start date | {sp['test_start_date']} |",
        f"| Train rows | {sp['train_rows']} |",
        f"| Test rows | {sp['test_rows']} |",
        f"| Random split | NO |",
        "",
        "---",
        "",
        "## 2. Feature Set",
        "",
    ]
    feat_cols = en.get("feature_cols", ENRICHED_FEATURE_COLS)
    for fc in feat_cols:
        lines.append(f"- `{fc}`")

    lines += [
        "",
        "---",
        "",
        "## 3. Metrics",
        "",
        "| Metric | Baseline (p_oof) | Enriched Model | Delta |",
        "|--------|-----------------|---------------|-------|",
        f"| Brier score | {bl['brier']:.6f} | {en.get('brier', 'N/A')} | {cp.get('delta_brier', 'N/A')} |",
        f"| Log-loss | {bl['log_loss']:.6f} | {en.get('log_loss', 'N/A')} | {cp.get('delta_log_loss', 'N/A')} |",
        f"| BSS vs base-rate | {bl['bss_vs_base_rate']:.6f} | {en.get('bss_vs_base_rate', 'N/A')} | — |",
        f"| Base rate | {bl['base_rate']:.4f} | {en.get('base_rate', 'N/A')} | — |",
        "",
        "---",
        "",
        "## 4. Interpretation",
        "",
        f"**Result**: {interp}  ",
        f"**Delta Brier**: {cp.get('delta_brier', 'N/A')} (negative = enriched model is better)  ",
        "",
        f"> {cp.get('note', '')}",
        "",
        "---",
        "",
    ]

    if "coef" in en:
        lines += [
            "## 5. Feature Coefficients (Logistic Regression)",
            "",
            "| Feature | Coefficient |",
            "|---------|------------|",
        ]
        for feat, coef in sorted(
            en["coef"].items(), key=lambda x: abs(x[1]), reverse=True
        ):
            lines.append(f"| `{feat}` | {coef:.6f} |")
        lines += ["", "---", ""]

    lines += [
        "## 6. Guards",
        "",
        "| Guard | Status |",
        "|-------|--------|",
        "| Odds features | NONE |",
        "| Leakage violations | 0 |",
        "| Random split | NO |",
        "| Production edge claim | NO |",
        "| Push | NOT AUTHORIZED |",
        "",
        "---",
        "",
        f"`{marker}`  ",
        "`PAPER_ONLY=True | pybaseball != odds source | no push`",
    ]

    out_report.write_text("\n".join(lines), encoding="utf-8")
    print(f"[P39H] Report written: {out_report}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="P39H: Time-aware enriched feature model comparison (paper-only)"
    )
    p.add_argument(
        "--input-file",
        type=Path,
        default=Path(
            "data/pybaseball/local_only/p39g_enriched_p38a_oof_fullseason.csv"
        ),
        help="Path to P39G enriched OOF CSV",
    )
    p.add_argument(
        "--bridge-file",
        type=Path,
        default=BRIDGE_FILE,
        help="Path to identity bridge CSV (provides y_true_home_win)",
    )
    p.add_argument(
        "--out-json",
        type=Path,
        default=Path(
            "outputs/predictions/PAPER/"
            "p39h_enriched_feature_model_comparison_20260515.json"
        ),
    )
    p.add_argument(
        "--out-report",
        type=Path,
        default=Path(
            "00-BettingPlan/20260513/"
            "p39h_enriched_feature_model_comparison_report_20260515.md"
        ),
    )
    p.add_argument(
        "--test-start-date",
        default="2024-08-01",
        help="First date of test set (YYYY-MM-DD). All earlier dates = train.",
    )
    p.add_argument(
        "--min-train-date",
        default=None,
        help="Optional: exclude rows before this date from training.",
    )
    p.add_argument(
        "--model",
        default="logistic",
        choices=["logistic"],
        help="Model type to train",
    )
    p.add_argument(
        "--execute",
        action="store_true",
        default=False,
        help="Write output JSON and report. Default: summary-only (no file writes).",
    )
    p.add_argument(
        "--summary-only",
        action="store_true",
        default=False,
        help="Print summary and exit without writing files (default behaviour).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()

    print(f"[P39H] SCRIPT_VERSION={SCRIPT_VERSION}")
    print(f"[P39H] PAPER_ONLY={PAPER_ONLY}")
    print(f"[P39H] input={args.input_file}")
    print(f"[P39H] test_start_date={args.test_start_date}")
    print(f"[P39H] model={args.model}")
    print(f"[P39H] execute={args.execute}")

    # --- Safety checks ---
    check_no_banned_features(ENRICHED_FEATURE_COLS)
    check_no_target_in_features(ENRICHED_FEATURE_COLS)

    # --- Load data ---
    df = load_and_join_data(args.input_file, args.bridge_file)
    print(f"[P39H] Loaded {len(df)} rows. date range: {df['game_date'].min().date()} -> {df['game_date'].max().date()}")

    # --- Optional min_train_date filter ---
    if args.min_train_date:
        cutoff = pd.Timestamp(args.min_train_date)
        df = df[df["game_date"] >= cutoff].copy()
        print(f"[P39H] After min_train_date filter: {len(df)} rows")

    # --- Time-aware split ---
    train_df, test_df = time_aware_split(df, args.test_start_date)
    print(f"[P39H] Train rows: {len(train_df)} | Test rows: {len(test_df)}")

    # --- Baseline metrics ---
    baseline = compute_baseline_metrics(test_df)
    print(
        f"[P39H] Baseline Brier={baseline['brier']:.6f} | "
        f"log-loss={baseline['log_loss']:.6f} | "
        f"BSS={baseline['bss_vs_base_rate']:.6f}"
    )

    # --- Enriched model ---
    enriched = compute_enriched_metrics(
        train_df, test_df, ENRICHED_FEATURE_COLS, args.model
    )
    if "error" in enriched:
        print(f"[P39H] Enriched model ERROR: {enriched['error']}")
    else:
        print(
            f"[P39H] Enriched Brier={enriched['brier']:.6f} | "
            f"log-loss={enriched['log_loss']:.6f} | "
            f"BSS={enriched['bss_vs_base_rate']:.6f}"
        )

    # --- Comparison ---
    comparison = interpret_comparison(baseline, enriched)
    print(
        f"[P39H] delta_brier={comparison['delta_brier']} | "
        f"interpretation={comparison['interpretation']}"
    )
    print(f"[P39H] Marker: {comparison['marker']}")

    # --- Build full metrics ---
    run_at = datetime.now(timezone.utc).isoformat()
    metrics = build_full_metrics(baseline, enriched, comparison, args.test_start_date, run_at)

    if args.execute:
        write_json_report(metrics, args.out_json)
        write_markdown_report(metrics, args.out_report)
    else:
        print("[P39H] summary-only mode — no files written. Pass --execute to write outputs.")

    # Exit non-zero if comparison failed
    if comparison.get("interpretation") == "FAILED":
        sys.exit(1)

    print(f"[P39H] DONE. classification={comparison['marker']}")


if __name__ == "__main__":
    main()
