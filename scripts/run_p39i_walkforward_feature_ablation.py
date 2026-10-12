"""
P39I — Walk-Forward Feature Ablation + Enriched Model Robustness Audit
SCRIPT_VERSION = "p39i_walkforward_feature_ablation_v1"
PAPER_ONLY = True
production_ready = False

Walk-forward OOF ablation over 5 feature groups to assess whether P39G Statcast
rolling features provide robust Brier improvement over the P38A baseline (p_oof).

No odds, no CLV, no production write, no betting recommendation.

Usage (summary-only — no file writes):
  PYTHONPATH=. .venv/bin/python scripts/run_p39i_walkforward_feature_ablation.py \\
    --input-file data/pybaseball/local_only/p39g_enriched_p38a_oof_fullseason.csv

Usage (execute — write JSON + markdown report):
  PYTHONPATH=. .venv/bin/python scripts/run_p39i_walkforward_feature_ablation.py \\
    --input-file data/pybaseball/local_only/p39g_enriched_p38a_oof_fullseason.csv \\
    --out-json outputs/predictions/PAPER/p39i_walkforward_feature_ablation_20260515.json \\
    --out-report 00-BettingPlan/20260513/p39i_walkforward_feature_ablation_report_20260515.md \\
    --n-folds 5 \\
    --min-train-rows 400 \\
    --model logistic \\
    --execute

Acceptance marker: P39I_WALKFORWARD_ABLATION_SCRIPT_READY_20260515
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

SCRIPT_VERSION = "p39i_walkforward_feature_ablation_v1"
PAPER_ONLY = True
PRODUCTION_READY = False

_BRIDGE_DEFAULT = Path("data/mlb_2024/processed/mlb_2024_game_identity_outcomes_joined.csv")

# ── Forbidden columns ──────────────────────────────────────────────────────────
_LEAKAGE_COLUMNS = frozenset([
    "y_true_home_win", "home_win", "winner", "home_score", "away_score",
    "run_diff", "total_runs",
])
_ODDS_COLUMNS_PATTERN = ["odds_", "_ml", "_rl", "_ou", "line_value", "handicap", "clv"]
_META_COLUMNS = frozenset([
    "game_id", "fold_id", "model_version", "source_prediction_ref",
    "generated_without_y_true", "game_date", "home_team", "away_team",
    "bridge_match_status",
])


def _is_odds_column(col: str) -> bool:
    return any(pat in col.lower() for pat in _ODDS_COLUMNS_PATTERN)


def _validate_columns(df: pd.DataFrame) -> None:
    """Raise if leakage or odds columns are present."""
    leakage = set(df.columns) & _LEAKAGE_COLUMNS
    if leakage:
        raise ValueError(f"[LEAKAGE] Forbidden target columns in feature set: {leakage}")
    odds = [c for c in df.columns if _is_odds_column(c)]
    if odds:
        raise ValueError(f"[ODDS] Odds columns must not appear in feature set: {odds}")


# ── Feature group definitions ──────────────────────────────────────────────────

def _diff_feature_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("diff_")]


def _home_away_rolling_cols(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("home_rolling_") or c.startswith("away_rolling_")]


def _full_statcast_cols(df: pd.DataFrame) -> list[str]:
    return sorted(set(_diff_feature_cols(df)) | set(_home_away_rolling_cols(df)))


def get_feature_groups(df: pd.DataFrame) -> dict[str, list[str]]:
    """Return feature group name -> list of column names. Excludes game_date and target."""
    diff_cols = _diff_feature_cols(df)
    home_away_cols = _home_away_rolling_cols(df)
    full_statcast = sorted(set(diff_cols) | set(home_away_cols))
    p_oof_plus_full = sorted({"p_oof"} | set(full_statcast))

    return {
        "baseline_p_oof": [],          # special: use p_oof directly, no model
        "diff_features_only": diff_cols,
        "home_away_rolling_only": home_away_cols,
        "full_statcast_rolling": full_statcast,
        "p_oof_plus_full_statcast": p_oof_plus_full,
    }


# ── Walk-forward fold builder ──────────────────────────────────────────────────

def build_walk_forward_folds(
    df: pd.DataFrame,
    n_folds: int = 5,
    min_train_rows: int = 400,
    min_test_rows: int = 50,
) -> list[dict[str, Any]]:
    """
    Build walk-forward fold definitions.

    Chronological sort, then split into n_folds chunks. Fold k trains on
    chunks 0..k-1 and tests on chunk k. First chunk is never predicted.

    Returns list of fold dicts with keys:
        fold_id, train_idx, test_idx, train_start, train_end,
        test_start, test_end, skipped, skip_reason
    """
    df = df.sort_values("game_date").reset_index(drop=True)
    n = len(df)
    chunk_size = n // n_folds

    folds: list[dict[str, Any]] = []
    for k in range(1, n_folds):           # fold k: train on chunks 0..k-1, test on chunk k
        train_start_idx = 0
        train_end_idx = k * chunk_size   # exclusive
        test_start_idx = k * chunk_size
        test_end_idx = (k + 1) * chunk_size if k < n_folds - 1 else n

        train_idx = list(range(train_start_idx, train_end_idx))
        test_idx = list(range(test_start_idx, test_end_idx))

        train_dates = df.iloc[train_idx]["game_date"]
        test_dates = df.iloc[test_idx]["game_date"]

        skip = False
        skip_reason = ""
        if len(train_idx) < min_train_rows:
            skip = True
            skip_reason = f"train rows {len(train_idx)} < min {min_train_rows}"
        if len(test_idx) < min_test_rows:
            skip = True
            skip_reason += f"; test rows {len(test_idx)} < min {min_test_rows}"

        folds.append({
            "fold_id": k - 1,
            "train_idx": train_idx,
            "test_idx": test_idx,
            "train_n": len(train_idx),
            "test_n": len(test_idx),
            "train_start": str(train_dates.min()),
            "train_end": str(train_dates.max()),
            "test_start": str(test_dates.min()),
            "test_end": str(test_dates.max()),
            "skipped": skip,
            "skip_reason": skip_reason.strip("; "),
        })

    return folds


# ── Model training & evaluation ───────────────────────────────────────────────

def _train_and_eval_fold(
    df: pd.DataFrame,
    y: np.ndarray,
    train_idx: list[int],
    test_idx: list[int],
    feature_cols: list[str],
    model_name: str = "logistic",
) -> dict[str, float]:
    """Train logistic regression on train, evaluate on test. Returns metrics dict."""
    X_train = df.iloc[train_idx][feature_cols].to_numpy(dtype=float).copy()
    X_test = df.iloc[test_idx][feature_cols].to_numpy(dtype=float).copy()
    y_train = y[train_idx]
    y_test = y[test_idx]

    # Fill NaN with column mean of train set (leakage-safe: use train mean only)
    col_means = np.nanmean(X_train, axis=0)
    for j in range(X_train.shape[1]):
        X_train[:, j] = np.where(np.isnan(X_train[:, j]), col_means[j], X_train[:, j])
        X_test[:, j] = np.where(np.isnan(X_test[:, j]), col_means[j], X_test[:, j])

    # Need at least 2 classes in training
    if len(np.unique(y_train)) < 2:
        return {"brier": float("nan"), "log_loss_val": float("nan"), "bss": float("nan")}

    clf = LogisticRegression(C=1.0, max_iter=1000, random_state=42, solver="lbfgs")
    clf.fit(X_train, y_train)
    home_win_idx = list(clf.classes_).index(1)
    p_pred = clf.predict_proba(X_test)[:, home_win_idx]

    base_rate = float(y_test.mean())
    brier = float(brier_score_loss(y_test, p_pred))
    ll = float(log_loss(y_test, p_pred))
    brier_ref = float(brier_score_loss(y_test, np.full_like(p_pred, base_rate)))
    bss = 1.0 - brier / brier_ref if brier_ref > 0 else float("nan")

    return {"brier": brier, "log_loss_val": ll, "bss": bss}


def _eval_baseline_fold(
    df: pd.DataFrame,
    y: np.ndarray,
    test_idx: list[int],
) -> dict[str, float]:
    """Baseline: use p_oof directly on test set. No model training."""
    p_oof = df.iloc[test_idx]["p_oof"].to_numpy(dtype=float)
    y_test = y[test_idx]

    # Handle NaN in p_oof
    valid_mask = ~np.isnan(p_oof)
    if valid_mask.sum() == 0:
        return {"brier": float("nan"), "log_loss_val": float("nan"), "bss": float("nan")}

    p_oof_clean = p_oof[valid_mask]
    y_clean = y_test[valid_mask]

    base_rate = float(y_clean.mean())
    brier = float(brier_score_loss(y_clean, p_oof_clean))
    ll = float(log_loss(y_clean, p_oof_clean))
    brier_ref = float(brier_score_loss(y_clean, np.full_like(p_oof_clean, base_rate)))
    bss = 1.0 - brier / brier_ref if brier_ref > 0 else float("nan")

    return {"brier": brier, "log_loss_val": ll, "bss": bss}


# ── Robust improvement evaluation ─────────────────────────────────────────────

def evaluate_robust_improvement(
    fold_deltas: list[float],
    mean_delta_threshold: float = -0.002,
    pct_improved_threshold: float = 0.60,
    worst_degradation_threshold: float = 0.005,
) -> dict[str, Any]:
    """
    Check all three robust improvement criteria.
    delta = candidate_brier - baseline_brier (negative = improvement).
    """
    valid_deltas = [d for d in fold_deltas if not np.isnan(d)]
    if not valid_deltas:
        return {"classification": "INCONCLUSIVE", "reason": "no valid folds"}

    mean_delta = float(np.mean(valid_deltas))
    pct_improved = sum(d < 0 for d in valid_deltas) / len(valid_deltas)
    worst_degradation = max(valid_deltas)

    criteria = {
        "mean_delta": mean_delta,
        "mean_delta_pass": mean_delta <= mean_delta_threshold,
        "pct_improved": pct_improved,
        "pct_improved_pass": pct_improved >= pct_improved_threshold,
        "worst_degradation": worst_degradation,
        "worst_degradation_pass": worst_degradation <= worst_degradation_threshold,
        "n_folds_evaluated": len(valid_deltas),
    }

    all_pass = criteria["mean_delta_pass"] and criteria["pct_improved_pass"] and criteria["worst_degradation_pass"]

    if all_pass:
        classification = "ROBUST_IMPROVEMENT"
    elif len(valid_deltas) < 2:
        classification = "INCONCLUSIVE"
    else:
        classification = "NO_ROBUST_IMPROVEMENT"

    return {"classification": classification, **criteria}


# ── Main ablation ──────────────────────────────────────────────────────────────

def load_and_join(
    input_file: Path,
    bridge_file: Path = _BRIDGE_DEFAULT,
) -> pd.DataFrame:
    """Load enriched CSV and join y_true_home_win from bridge."""
    df = pd.read_csv(input_file)
    bridge = pd.read_csv(bridge_file, usecols=["game_id", "y_true_home_win"])
    merged = df.merge(bridge, on="game_id", how="left")
    null_y = merged["y_true_home_win"].isnull().sum()
    if null_y > 0:
        raise RuntimeError(
            f"[DATA] {null_y} rows missing y_true_home_win after bridge join. "
            "Check game_id alignment between enriched CSV and bridge."
        )
    merged["game_date"] = pd.to_datetime(merged["game_date"])
    return merged.sort_values("game_date").reset_index(drop=True)


def run_ablation(
    df: pd.DataFrame,
    n_folds: int = 5,
    min_train_rows: int = 400,
    model_name: str = "logistic",
) -> dict[str, Any]:
    """Run full walk-forward ablation across all feature groups."""
    feature_groups = get_feature_groups(df)

    # Guard: validate each candidate feature group
    for group_name, cols in feature_groups.items():
        if group_name == "baseline_p_oof":
            continue
        candidate_df = df[cols] if cols else pd.DataFrame()
        if not candidate_df.empty:
            _validate_columns(candidate_df)
        if "game_date" in cols:
            raise ValueError(f"[LEAKAGE] game_date must not be a feature in group {group_name}")

    folds = build_walk_forward_folds(df, n_folds=n_folds, min_train_rows=min_train_rows)
    y = df["y_true_home_win"].to_numpy(dtype=float)

    results: dict[str, Any] = {
        "script_version": SCRIPT_VERSION,
        "paper_only": PAPER_ONLY,
        "production_ready": PRODUCTION_READY,
        "n_folds_requested": n_folds,
        "n_folds_evaluated": 0,
        "feature_groups": {},
        "fold_definitions": [],
        "robust_improvement_summary": {},
        "classification": "",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }

    # Store fold definitions
    for fold in folds:
        results["fold_definitions"].append({
            k: v for k, v in fold.items()
            if k not in ("train_idx", "test_idx")
        })

    active_folds = [f for f in folds if not f["skipped"]]
    results["n_folds_evaluated"] = len(active_folds)
    results["n_folds_skipped"] = len(folds) - len(active_folds)

    # For each feature group, run each fold
    all_group_results: dict[str, dict] = {}

    for group_name, feature_cols in feature_groups.items():
        fold_results = []

        for fold in folds:
            fold_meta = {
                "fold_id": fold["fold_id"],
                "train_n": fold["train_n"],
                "test_n": fold["test_n"],
                "test_start": fold["test_start"],
                "test_end": fold["test_end"],
                "skipped": fold["skipped"],
                "skip_reason": fold["skip_reason"],
            }

            if fold["skipped"]:
                fold_meta.update({
                    "baseline_brier": None,
                    "candidate_brier": None,
                    "delta_brier": None,
                    "improved": None,
                })
                fold_results.append(fold_meta)
                continue

            train_idx = fold["train_idx"]
            test_idx = fold["test_idx"]

            # Baseline (always p_oof direct)
            baseline_metrics = _eval_baseline_fold(df, y, test_idx)

            # Candidate
            if group_name == "baseline_p_oof":
                candidate_metrics = baseline_metrics
            elif feature_cols:
                candidate_metrics = _train_and_eval_fold(
                    df, y, train_idx, test_idx, feature_cols, model_name
                )
            else:
                candidate_metrics = {"brier": float("nan"), "log_loss_val": float("nan"), "bss": float("nan")}

            delta = (
                candidate_metrics["brier"] - baseline_metrics["brier"]
                if not (np.isnan(candidate_metrics["brier"]) or np.isnan(baseline_metrics["brier"]))
                else float("nan")
            )

            fold_meta.update({
                "baseline_brier": baseline_metrics["brier"],
                "baseline_log_loss": baseline_metrics["log_loss_val"],
                "candidate_brier": candidate_metrics["brier"],
                "candidate_log_loss": candidate_metrics["log_loss_val"],
                "candidate_bss": candidate_metrics["bss"],
                "delta_brier": delta,
                "improved": delta < 0 if not np.isnan(delta) else None,
            })
            fold_results.append(fold_meta)

        # Aggregate
        valid_deltas = [
            f["delta_brier"] for f in fold_results
            if not f["skipped"] and f["delta_brier"] is not None and not np.isnan(f["delta_brier"])
        ]
        robust = evaluate_robust_improvement(valid_deltas)

        all_group_results[group_name] = {
            "feature_cols": feature_cols,
            "n_feature_cols": len(feature_cols),
            "fold_results": fold_results,
            "aggregate": {
                "mean_delta_brier": float(np.mean(valid_deltas)) if valid_deltas else None,
                "median_delta_brier": float(np.median(valid_deltas)) if valid_deltas else None,
                "pct_folds_improved": sum(d < 0 for d in valid_deltas) / len(valid_deltas) if valid_deltas else None,
                "worst_fold_degradation": max(valid_deltas) if valid_deltas else None,
                "best_fold_improvement": min(valid_deltas) if valid_deltas else None,
                "n_valid_folds": len(valid_deltas),
            },
            "robust_improvement": robust,
        }

    results["feature_groups"] = all_group_results

    # Overall classification: take the best-performing candidate group
    best_classification = "NO_ROBUST_IMPROVEMENT"
    for group_name, gdata in all_group_results.items():
        if group_name == "baseline_p_oof":
            continue
        cls = gdata["robust_improvement"]["classification"]
        if cls == "ROBUST_IMPROVEMENT":
            best_classification = "ROBUST_IMPROVEMENT"
            break
        elif cls == "INCONCLUSIVE" and best_classification == "NO_ROBUST_IMPROVEMENT":
            best_classification = "INCONCLUSIVE"

    results["classification"] = best_classification
    results["robust_improvement_summary"] = {
        g: all_group_results[g]["robust_improvement"]["classification"]
        for g in all_group_results
        if g != "baseline_p_oof"
    }

    return results


# ── Report writer ──────────────────────────────────────────────────────────────

def _fmt(v: Any, decimals: int = 4) -> str:
    if v is None:
        return "N/A"
    if isinstance(v, float) and np.isnan(v):
        return "NaN"
    if isinstance(v, float):
        return f"{v:.{decimals}f}"
    return str(v)


def write_markdown_report(results: dict[str, Any], out_path: Path) -> None:
    """Write human-readable markdown report."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cls = results["classification"]

    if cls == "ROBUST_IMPROVEMENT":
        cls_marker = "P39I_WALKFORWARD_ABLATION_ROBUST_IMPROVEMENT_20260515"
    elif cls == "NO_ROBUST_IMPROVEMENT":
        cls_marker = "P39I_WALKFORWARD_ABLATION_NO_ROBUST_IMPROVEMENT_20260515"
    else:
        cls_marker = "P39I_WALKFORWARD_ABLATION_INCONCLUSIVE_20260515"

    lines = [
        "# P39I Walk-Forward Feature Ablation Report",
        f"**Date:** {results['timestamp_utc'][:10]}",
        f"**Classification:** `{cls}`",
        f"**paper_only:** True | **production_ready:** False",
        "",
        "---",
        "",
        "## Fold Definitions",
        "",
        "| Fold | Train N | Test N | Train Start | Train End | Test Start | Test End | Skipped |",
        "|------|---------|--------|-------------|-----------|------------|----------|---------|",
    ]

    for fold in results["fold_definitions"]:
        lines.append(
            f"| {fold['fold_id']} | {fold['train_n']} | {fold['test_n']} | "
            f"{fold['train_start'][:10]} | {fold['train_end'][:10]} | "
            f"{fold['test_start'][:10]} | {fold['test_end'][:10]} | "
            f"{'YES: '+fold['skip_reason'] if fold['skipped'] else 'No'} |"
        )

    lines += ["", "---", "", "## Feature Group Results", ""]

    # Aggregate table
    lines += [
        "### Aggregate Metrics (per feature group)",
        "",
        "| Group | Mean ΔBrier | Median ΔBrier | % Folds Improved | Worst Degradation | Best Improvement | N Folds | Classification |",
        "|-------|------------|---------------|-----------------|-------------------|-----------------|---------|----------------|",
    ]

    for group_name, gdata in results["feature_groups"].items():
        agg = gdata["aggregate"]
        cls_g = gdata["robust_improvement"]["classification"]
        lines.append(
            f"| `{group_name}` | {_fmt(agg['mean_delta_brier'])} | {_fmt(agg['median_delta_brier'])} | "
            f"{_fmt(agg['pct_folds_improved'], 1) if agg['pct_folds_improved'] is not None else 'N/A'} | "
            f"{_fmt(agg['worst_fold_degradation'])} | {_fmt(agg['best_fold_improvement'])} | "
            f"{agg['n_valid_folds']} | `{cls_g}` |"
        )

    lines += ["", "---", "", "## Per-Fold Detail", ""]

    for group_name, gdata in results["feature_groups"].items():
        lines += [f"### {group_name}", ""]
        lines += [
            "| Fold | Train N | Test N | Baseline Brier | Candidate Brier | ΔBrier | Improved |",
            "|------|---------|--------|----------------|-----------------|--------|---------|",
        ]
        for fr in gdata["fold_results"]:
            if fr["skipped"]:
                lines.append(f"| {fr['fold_id']} | {fr['train_n']} | {fr['test_n']} | *skipped* | *skipped* | *skipped* | — |")
            else:
                lines.append(
                    f"| {fr['fold_id']} | {fr['train_n']} | {fr['test_n']} | "
                    f"{_fmt(fr['baseline_brier'])} | {_fmt(fr['candidate_brier'])} | "
                    f"{_fmt(fr['delta_brier'])} | {'✅' if fr['improved'] else '❌'} |"
                )
        lines += [""]

    lines += [
        "---",
        "",
        "## Robust Improvement Summary",
        "",
        "Criteria for ROBUST_IMPROVEMENT (all three must pass):",
        "- mean delta Brier ≤ −0.002",
        "- ≥ 60% folds improved",
        "- worst fold degradation ≤ +0.005",
        "",
        "| Feature Group | Classification |",
        "|---------------|----------------|",
    ]
    for g, c in results["robust_improvement_summary"].items():
        lines.append(f"| `{g}` | `{c}` |")

    lines += [
        "",
        "---",
        "",
        "## Interpretation Guard",
        "",
        "- This is a paper-only research audit. No production edge is claimed.",
        "- No odds, no CLV, no betting recommendation.",
        "- pybaseball rolling features are a baseball stats source, not an odds source.",
        "- P38A baseline remains the operative model until robust improvement is confirmed.",
        "",
        "---",
        "",
        f"## Acceptance Marker",
        "",
        f"`{cls_marker}`",
    ]

    out_path.write_text("\n".join(lines))


# ── CLI ────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="P39I Walk-Forward Feature Ablation")
    parser.add_argument("--input-file", required=True, type=Path)
    parser.add_argument("--bridge-file", default=str(_BRIDGE_DEFAULT), type=Path)
    parser.add_argument("--out-json", type=Path, default=None)
    parser.add_argument("--out-report", type=Path, default=None)
    parser.add_argument("--n-folds", type=int, default=5)
    parser.add_argument("--min-train-rows", type=int, default=400)
    parser.add_argument("--model", default="logistic", choices=["logistic"])
    parser.add_argument("--summary-only", action="store_true", default=False,
                        help="Print summary to stdout; do not write files (default if --execute not set)")
    parser.add_argument("--execute", action="store_true", default=False,
                        help="Write JSON + markdown report to disk")
    args = parser.parse_args()

    if not args.input_file.exists():
        print(f"[ERROR] Input file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    if not args.bridge_file.exists():
        print(f"[ERROR] Bridge file not found: {args.bridge_file}", file=sys.stderr)
        sys.exit(1)

    df = load_and_join(args.input_file, args.bridge_file)

    results = run_ablation(
        df=df,
        n_folds=args.n_folds,
        min_train_rows=args.min_train_rows,
        model_name=args.model,
    )

    cls = results["classification"]
    print(f"[P39I] Classification: {cls}")
    print(f"[P39I] Folds evaluated: {results['n_folds_evaluated']}")
    for g, c in results["robust_improvement_summary"].items():
        agg = results["feature_groups"][g]["aggregate"]
        mean_d = _fmt(agg["mean_delta_brier"])
        pct = _fmt(agg["pct_folds_improved"], 1) if agg["pct_folds_improved"] is not None else "N/A"
        print(f"  {g}: {c} | mean_delta={mean_d} | pct_improved={pct}")

    if args.execute:
        if args.out_json is None or args.out_report is None:
            print("[ERROR] --execute requires --out-json and --out-report", file=sys.stderr)
            sys.exit(1)

        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.out_json, "w") as f:
            json.dump(results, f, indent=2, default=str)
        print(f"[P39I] JSON written: {args.out_json}")

        write_markdown_report(results, args.out_report)
        print(f"[P39I] Report written: {args.out_report}")

    if cls == "ROBUST_IMPROVEMENT":
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
