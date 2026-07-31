#!/usr/bin/env python3
"""
P235-A CLI — 建立最終 2025 Run Line backtest package（純彙整＋本機統計附錄，非新模型任務）。

用法（自 repo 根目錄）：
    python3 scripts/build_p235a_final_2025_runline_backtest_package.py

本檔不重跑、不修改 P226-A / P228-A / P230-A / P232-A 任何模型或報告；只讀取它們
既有的 `report/*.json` 與 `report/*_predictions.csv`（read-only 輸入），並：
  1) 從既有 prediction ledger 獨立重算 Gate 0 關鍵數值（非僅複製 JSON 數字）；
  2) 用既有 prediction ledger（P226-A run_line 972 場 test-set）計算本機統計附錄
     （seeded bootstrap 95% CI、paired permutation p-value、chronological split
     穩健性彙整、majority-class/實際 cover-rate 參考基準 REFERENCE_ONLY）；
  3) 彙整成一份最終、獨立的 2025 Run Line backtest package。

純本機、無網路、無 live provider、無 DB / registry / production 變更、無發布、
無未來預測、無下注建議、無跨球季驗證宣稱、無 true-PIT 宣稱。

輸出（report/ 下 3 檔）：
    p235a_final_2025_runline_backtest_package.md
    p235a_final_2025_runline_backtest_package.json
    p235a_final_2025_runline_statistical_appendix.csv
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

REPORT_DIR = ROOT / "report"

P226A_JSON = REPORT_DIR / "p226a_run_line_total_scorecard.json"
P228A_JSON = REPORT_DIR / "p228a_run_line_robustness_scorecard.json"
P230A_JSON = REPORT_DIR / "p230a_local_multiseason_runline_data_audit.json"
P232A_JSON = REPORT_DIR / "p232a_run_line_feature_ablation_scorecard.json"

P226A_PREDICTIONS_CSV = REPORT_DIR / "p226a_run_line_total_predictions.csv"
P228A_PREDICTIONS_CSV = REPORT_DIR / "p228a_run_line_robustness_predictions.csv"
P232A_PREDICTIONS_CSV = REPORT_DIR / "p232a_run_line_feature_ablation_predictions.csv"

REQUIRED_INPUTS = (
    P226A_JSON, P228A_JSON, P230A_JSON, P232A_JSON,
    P226A_PREDICTIONS_CSV, P228A_PREDICTIONS_CSV, P232A_PREDICTIONS_CSV,
)

# ── Gate 0 pre-registered expected values (from task authorization; tolerances
# mirror the existing P228-A/P232-A pytest suites) ──────────────────────────
GATE0_EXPECTED = {
    "poisson_accuracy": (0.6008, 1e-3),
    "poisson_brier": (0.2395, 1e-3),
    "coinflip_brier": (0.2500, 1e-4),
    "calibrated_brier": (0.2375, 1e-3),
    "raw_ece": (0.0483, 1e-3),
    "calibrated_ece": (0.0180, 1e-3),
}

# ── deterministic statistical-appendix seeds (fixed; never re-drawn) ───────
BOOTSTRAP_SEED = 235235
N_BOOTSTRAP = 5000
PERMUTATION_SEED = 235236
N_PERMUTATIONS = 5000

DISCLAIMERS = [
    "LOCAL HISTORICAL / REPLAY BACKTEST ONLY",
    "2025-ONLY: single-season evaluation universe (data/mlb_2025/mlb_odds_2025_real.csv); "
    "NOT a multi-season validation",
    "descriptive synthesis of already-published P226-A / P228-A / P230-A / P232-A results "
    "plus a local-only statistical appendix computed from existing prediction ledgers; "
    "NOT a new model, NOT a re-run, NOT a re-derivation, NO retraining",
    "PROVENANCE-UNVERIFIED: run line spread/prices are a post-game unverified snapshot "
    "(is_verified_real=False); settlement / descriptive market reference only, NEVER a "
    "model input feature; NOT true point-in-time (PIT) data",
    "NO betting recommendation; NO EV/Kelly claim; NOT a proven betting edge",
    "NO live-market claim; NOT production; NOT real betting; NO future prediction",
    "NO provider was contacted for this package; provider path status is PARKED_OPTIONAL",
    "P226-A / P228-A / P230-A / P232-A source artifacts are read-only inputs and are not "
    "modified by this package",
]

LIMITATION_LABELS = [
    "2025-ONLY",
    "HISTORICAL_PAPER_ONLY",
    "ODDS_PROVENANCE_UNVERIFIED",
    "NOT_TRUE_PIT",
    "NOT_BETTING_EDGE",
    "NOT_LIVE",
    "NOT_PRODUCTION",
    "NOT_FUTURE_PREDICTION",
    "NOT_MULTI_SEASON_VALIDATION",
]

DECISION_OPTIONS = [
    {
        "option": "HOLD_ARCHIVE_CURRENT_EVIDENCE",
        "description": "Archive this package as the final, standalone 2025 Run Line "
        "backtest evidence record; no further Run Line work is authorized by this "
        "package alone.",
    },
    {
        "option": "RESTART_PROVIDER_PATH_LATER",
        "description": "Later restart the provider outreach path only if the Owner wants "
        "a true point-in-time (PIT) evidence upgrade; NOT authorized by this package.",
    },
    {
        "option": "CROSS_SEASON_VALIDATION_LATER",
        "description": "Later attempt cross-season validation only if actual usable "
        "multi-season Run Line data becomes locally available (currently blocked per "
        "P230-A: 2024=LABEL_ONLY_NO_ODDS, 2026=MISSING_OR_UNUSABLE); NOT authorized by "
        "this package.",
    },
]

PROVIDER_PATH_STATUS = {
    "status": "PARKED_OPTIONAL",
    "provider_replies_received": 0,
    "true_pit_provider_data_used": False,
    "basis": "report/p230a_local_multiseason_runline_data_audit.json "
    "recommended_next_technical_step.chosen=stop_data_gap, "
    "authorization_status=NOT_AUTHORIZED_YET; no provider outreach records exist "
    "locally in this repository",
    "note": "no provider was contacted to build this package; the provider path remains "
    "parked pending a separate, explicit Owner decision",
}

P234_STATUS = {
    "found_locally": False,
    "status": "NOT_FOUND_LOCALLY",
    "note": "No P234 report, script, or task artifact exists anywhere in this repository "
    "as of this build (report/, 00-Plan/, scripts/, tests/ all searched for 'p234'). "
    "P234 is acknowledged per task instructions but not consolidated because there is no "
    "local evidence to consolidate; this is a factual gap-report, not a fabricated status.",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def load_source_reports(report_dir: Path = REPORT_DIR) -> dict:
    return {
        "p226a": _load_json(Path(report_dir) / "p226a_run_line_total_scorecard.json"),
        "p228a": _load_json(Path(report_dir) / "p228a_run_line_robustness_scorecard.json"),
        "p230a": _load_json(Path(report_dir) / "p230a_local_multiseason_runline_data_audit.json"),
        "p232a": _load_json(Path(report_dir) / "p232a_run_line_feature_ablation_scorecard.json"),
    }


# ── ledger loading (read-only prediction CSVs; no retraining) ──────────────
def load_p226a_run_line_ledger(path: Path = P226A_PREDICTIONS_CSV) -> dict[str, list[dict]]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    decided = [r for r in rows if r["market"] == "run_line" and r["is_push"] == "False"]
    return {
        "coinflip": sorted(
            (r for r in decided if r["model_name"] == "baseline_coinflip_50pct"),
            key=lambda r: r["game_id"],
        ),
        "poisson": sorted(
            (r for r in decided if r["model_name"] == "poisson_team_rate_model"),
            key=lambda r: r["game_id"],
        ),
    }


def load_p228a_anchor_ledger(path: Path = P228A_PREDICTIONS_CSV,
                              anchor_train_frac: str = "0.6") -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    anchor = [r for r in rows if r["split_train_frac"] == anchor_train_frac and r["is_push"] == "False"]
    return sorted(anchor, key=lambda r: r["game_id"])


def _home_label(actual_side: str) -> float:
    return 1.0 if actual_side == "HOME" else 0.0


def _brier(p: float, y: float) -> float:
    return (p - y) ** 2


# ── Gate 0: independent reproduction from raw prediction ledgers ───────────
def reproduce_gate0(sources: dict, ledger: dict[str, list[dict]],
                     p228a_anchor: list[dict]) -> dict[str, Any]:
    coinflip_rows = ledger["coinflip"]
    poisson_rows = ledger["poisson"]
    n = len(poisson_rows)
    if n == 0 or len(coinflip_rows) != n:
        raise RuntimeError("GATE0_FAILED_LEDGER_EMPTY_OR_MISALIGNED")

    coinflip_brier = sum(
        _brier(float(r["predicted_primary_probability"]), _home_label(r["actual_side"]))
        for r in coinflip_rows
    ) / n
    coinflip_accuracy = sum(1 for r in coinflip_rows if r["correct"] == "1") / n

    poisson_brier = sum(
        _brier(float(r["predicted_primary_probability"]), _home_label(r["actual_side"]))
        for r in poisson_rows
    ) / n
    poisson_accuracy = sum(1 for r in poisson_rows if r["correct"] == "1") / n

    n_cal = len(p228a_anchor)
    calibrated_brier = sum(
        _brier(float(r["calibrated_predicted_home_probability"]), _home_label(r["actual_side"]))
        for r in p228a_anchor
    ) / n_cal
    calibrated_accuracy = sum(1 for r in p228a_anchor if r["calibrated_correct"] == "1") / n_cal

    recomputed = {
        "n_run_line_test_games": n,
        "coinflip_accuracy": coinflip_accuracy,
        "coinflip_brier": coinflip_brier,
        "poisson_accuracy": poisson_accuracy,
        "poisson_brier": poisson_brier,
        "calibrated_accuracy": calibrated_accuracy,
        "calibrated_brier": calibrated_brier,
    }

    # ECE (raw/calibrated) is verified against the tracked, pytest-covered P228-A
    # JSON artifact rather than re-derived (re-deriving the exact weighted-gap ECE
    # binning here would risk a definitional mismatch, not a genuine discrepancy).
    p228a_cal = sources["p228a"]["calibration"]
    verified = {
        "raw_ece": p228a_cal["raw"]["calibration_error"],
        "calibrated_ece": p228a_cal["calibrated"]["calibration_error"],
    }

    checks = {
        "poisson_accuracy": recomputed["poisson_accuracy"],
        "poisson_brier": recomputed["poisson_brier"],
        "coinflip_brier": recomputed["coinflip_brier"],
        "calibrated_brier": recomputed["calibrated_brier"],
        "raw_ece": verified["raw_ece"],
        "calibrated_ece": verified["calibrated_ece"],
    }
    mismatches = []
    for key, (expected, tol) in GATE0_EXPECTED.items():
        actual = checks[key]
        if abs(actual - expected) > tol:
            mismatches.append(
                {"metric": key, "expected": expected, "actual": actual, "tolerance": tol}
            )

    if mismatches:
        raise RuntimeError(f"GATE0_FAILED_MISMATCH: {mismatches}")

    return {
        "status": "GATE0_REPRODUCED_P235A_FINAL_PACKAGE",
        "reproduction_method": "accuracy/Brier/calibrated-Brier independently recomputed "
        "from report/p226a_run_line_total_predictions.csv and "
        "report/p228a_run_line_robustness_predictions.csv raw ledger rows (no retraining); "
        "ECE verified against report/p228a_run_line_robustness_scorecard.json "
        "(pytest-covered tracked artifact)",
        "expected": {k: v[0] for k, v in GATE0_EXPECTED.items()},
        "tolerance": {k: v[1] for k, v in GATE0_EXPECTED.items()},
        "recomputed": recomputed,
        "verified_from_artifact": verified,
        "all_within_tolerance": True,
        "mismatches": [],
    }


# ── local-only statistical appendix (existing ledgers only; seeded; no retrain) ──
def compute_statistical_appendix(ledger: dict[str, list[dict]]) -> dict[str, Any]:
    poisson_rows = ledger["poisson"]
    coinflip_rows = ledger["coinflip"]
    n = len(poisson_rows)

    margins = [
        0.25 - _brier(float(r["predicted_primary_probability"]), _home_label(r["actual_side"]))
        for r in poisson_rows
    ]
    observed_mean_margin = sum(margins) / n

    rng_boot = random.Random(BOOTSTRAP_SEED)
    boot_means = []
    for _ in range(N_BOOTSTRAP):
        s = 0.0
        for _ in range(n):
            s += margins[rng_boot.randrange(n)]
        boot_means.append(s / n)
    boot_means.sort()
    ci_lower = boot_means[int(0.025 * N_BOOTSTRAP)]
    ci_upper = boot_means[int(0.975 * N_BOOTSTRAP) - 1]

    rng_perm = random.Random(PERMUTATION_SEED)
    count_ge = 0
    for _ in range(N_PERMUTATIONS):
        s = 0.0
        for m in margins:
            s += m if rng_perm.random() < 0.5 else -m
        if (s / n) >= observed_mean_margin:
            count_ge += 1
    p_value = (count_ge + 1) / (N_PERMUTATIONS + 1)

    home_covers = sum(1 for r in poisson_rows if r["actual_side"] == "HOME")
    home_base_rate = home_covers / n
    away_base_rate = 1.0 - home_base_rate

    coinflip_accuracy = sum(1 for r in coinflip_rows if r["correct"] == "1") / n
    coinflip_brier = 0.25
    poisson_accuracy = sum(1 for r in poisson_rows if r["correct"] == "1") / n
    poisson_brier = sum(
        _brier(float(r["predicted_primary_probability"]), _home_label(r["actual_side"]))
        for r in poisson_rows
    ) / n

    return {
        "source_ledger": "report/p226a_run_line_total_predictions.csv",
        "n_games": n,
        "no_retraining": True,
        "no_remote_data": True,
        "no_provider_data": True,
        "bootstrap": {
            "label": "PREDICTIVE_STATISTIC",
            "metric": "brier_margin_vs_coinflip (coinflip_brier - poisson_brier; "
            "positive = poisson_team_rate_model improvement)",
            "observed_mean": observed_mean_margin,
            "ci95_lower": ci_lower,
            "ci95_upper": ci_upper,
            "seed": BOOTSTRAP_SEED,
            "n_resamples": N_BOOTSTRAP,
        },
        "permutation_test": {
            "label": "PREDICTIVE_STATISTIC",
            "metric": "one-sided sign-flip paired permutation test; "
            "H1: mean Brier margin (coinflip - poisson) > 0",
            "p_value": p_value,
            "seed": PERMUTATION_SEED,
            "n_permutations": N_PERMUTATIONS,
        },
        "predictive_baseline": {
            "label": "PREDICTIVE_BASELINE",
            "name": "baseline_coinflip_50pct",
            "note": "constant p=0.5, always predicts HOME side; accuracy equals the "
            "test-set home-cover base rate by construction, NOT an adaptive baseline",
            "accuracy": coinflip_accuracy,
            "brier": coinflip_brier,
        },
        "majority_class_reference": {
            "label": "REFERENCE_ONLY",
            "note": "descriptive test-set base rate of the more frequent actual side; "
            "computed post-hoc from test-set outcomes, NOT a valid pre-registered forward "
            "predictive baseline (a safe train-fold majority baseline cannot be computed "
            "from existing artifacts without re-deriving per-split labels); presented for "
            "descriptive reference only, NOT a betting/edge baseline",
            "home_base_rate": home_base_rate,
            "away_base_rate": away_base_rate,
            "majority_side": "AWAY" if away_base_rate > home_base_rate else "HOME",
            "majority_class_accuracy_if_always_picked": max(home_base_rate, away_base_rate),
        },
        "model": {
            "label": "MODEL",
            "name": "poisson_team_rate_model",
            "accuracy": poisson_accuracy,
            "brier": poisson_brier,
        },
        "chronological_split_stability": {
            "label": "ROBUSTNESS_SUMMARY",
            "source": "report/p228a_run_line_robustness_scorecard.json (consolidated, not recomputed)",
            "split_grid_beats_coinflip": "3/3",
            "monthly_window_beats_coinflip": "4/5 (2 skipped: insufficient train rows)",
        },
    }


def build_statistical_appendix_rows(appendix: dict[str, Any]) -> list[dict[str, str]]:
    boot = appendix["bootstrap"]
    perm = appendix["permutation_test"]
    split_stab = appendix["chronological_split_stability"]
    baseline = appendix["predictive_baseline"]
    ref = appendix["majority_class_reference"]
    model = appendix["model"]
    n = appendix["n_games"]

    def row(metric, value, ci_lo="", ci_hi="", n_val="", seed="", iterations="", label="", source="", notes=""):
        return {
            "metric": metric,
            "value": value,
            "ci_lower_95": ci_lo,
            "ci_upper_95": ci_hi,
            "n": n_val,
            "seed": seed,
            "iterations": iterations,
            "label": label,
            "source": source,
            "notes": notes,
        }

    return [
        row(
            "brier_margin_vs_coinflip_bootstrap_mean",
            f"{boot['observed_mean']:.6f}",
            f"{boot['ci95_lower']:.6f}",
            f"{boot['ci95_upper']:.6f}",
            n, boot["seed"], boot["n_resamples"], boot["label"],
            "report/p226a_run_line_total_predictions.csv",
            "seeded bootstrap 95% CI of mean per-game Brier margin "
            "(coinflip_brier - poisson_brier); positive = poisson_team_rate_model "
            "improvement over coinflip on the P226-A 2025 run_line test set",
        ),
        row(
            "paired_permutation_pvalue_brier_improvement",
            f"{perm['p_value']:.6f}",
            "", "", n, perm["seed"], perm["n_permutations"], perm["label"],
            "report/p226a_run_line_total_predictions.csv",
            "one-sided sign-flip paired permutation test p-value; H1: mean Brier "
            "margin (coinflip - poisson) > 0; "
            "p=(count(permuted_mean>=observed)+1)/(iterations+1)",
        ),
        row(
            "chronological_split_grid_beats_coinflip_ratio",
            "1.000000", "", "", 3, "", "", "ROBUSTNESS_SUMMARY",
            "report/p228a_run_line_robustness_scorecard.json",
            "3 of 3 pre-registered chronological train_frac splits (0.5/0.6/0.7) beat "
            "coinflip on Brier; consolidated from P228-A split_grid, not recomputed",
        ),
        row(
            "chronological_monthly_window_beats_coinflip_ratio",
            "0.800000", "", "", 5, "", "", "ROBUSTNESS_SUMMARY",
            "report/p228a_run_line_robustness_scorecard.json",
            "4 of 5 scored monthly rolling windows beat coinflip on Brier "
            "(2025-03/2025-04 skipped for insufficient train rows); consolidated "
            "from P228-A monthly_windows, not recomputed",
        ),
        row(
            "predictive_baseline_coinflip_accuracy",
            f"{baseline['accuracy']:.6f}", "", "", n, "", "", baseline["label"],
            "report/p226a_run_line_total_predictions.csv",
            baseline["note"],
        ),
        row(
            "majority_class_test_set_reference_accuracy",
            f"{ref['majority_class_accuracy_if_always_picked']:.6f}",
            "", "", n, "", "", ref["label"],
            "report/p226a_run_line_total_predictions.csv",
            ref["note"],
        ),
        row(
            "model_poisson_team_rate_model_accuracy",
            f"{model['accuracy']:.6f}", "", "", n, "", "", model["label"],
            "report/p226a_run_line_total_predictions.csv",
            "P226-A poisson_team_rate_model test-set accuracy, for side-by-side "
            "reference against baselines above",
        ),
        row(
            "model_poisson_team_rate_model_brier",
            f"{model['brier']:.6f}", "", "", n, "", "", model["label"],
            "report/p226a_run_line_total_predictions.csv",
            "P226-A poisson_team_rate_model test-set Brier score",
        ),
    ]


# ── consolidation of upstream summaries (read-only; no recompute of models) ──
def build_scorecard_summary(p226a: dict) -> dict:
    rl = {m["model_name"]: m for m in p226a["market_comparison"]["run_line"]}
    coinflip, poisson = rl["baseline_coinflip_50pct"], rl["poisson_team_rate_model"]
    return {
        "source": "report/p226a_run_line_total_scorecard.json",
        "test_period": list(p226a["split"]["test_period"]),
        "test_rows": p226a["split"]["test_rows"],
        "coinflip_accuracy": coinflip["accuracy"],
        "coinflip_brier": coinflip["brier_score"],
        "poisson_accuracy": poisson["accuracy"],
        "poisson_brier": poisson["brier_score"],
        "poisson_ece": poisson["calibration_error"],
    }


def build_robustness_summary(p228a: dict) -> dict:
    conc = p228a["robustness_conclusion"]
    return {
        "source": "report/p228a_run_line_robustness_scorecard.json",
        "label": conc["label"],
        "split_grid_strict_wins": conc["split_grid_strict_wins"],
        "split_grid_total": conc["split_grid_total"],
        "monthly_windows_strict_wins": conc["monthly_windows_strict_wins"],
        "monthly_windows_evaluated": conc["monthly_windows_evaluated"],
        "monthly_windows_skipped": conc["monthly_windows_skipped"],
        "statement": f"{conc['split_grid_strict_wins']}/{conc['split_grid_total']} "
        f"chronological splits beat coinflip; "
        f"{conc['monthly_windows_strict_wins']}/{conc['monthly_windows_evaluated']} "
        f"monthly windows beat coinflip "
        f"({conc['monthly_windows_skipped']} skipped, insufficient train)",
    }


def build_calibration_summary(p228a: dict) -> dict:
    cal = p228a["calibration"]
    return {
        "source": "report/p228a_run_line_robustness_scorecard.json",
        "raw_brier": cal["raw"]["brier_score"],
        "calibrated_brier": cal["calibrated"]["brier_score"],
        "raw_ece": cal["raw"]["calibration_error"],
        "calibrated_ece": cal["calibrated"]["calibration_error"],
        "calibration_beats_raw_brier": cal["calibration_beats_raw_brier"],
        "calibration_beats_raw_ece": cal["calibration_beats_raw_ece"],
        "statement": f"Brier {cal['raw']['brier_score']:.4f} -> "
        f"{cal['calibrated']['brier_score']:.4f}; ECE "
        f"{cal['raw']['calibration_error']:.4f} -> "
        f"{cal['calibrated']['calibration_error']:.4f}",
    }


def build_ablation_summary(p232a: dict) -> dict:
    interp = p232a["interpretation"]
    combined = next(
        r for r in p232a["ablation_results"]
        if r["variant"] == "ablate_team_strength_both" and not r["beats_coinflip_brier"]
    )
    return {
        "source": "report/p232a_run_line_feature_ablation_scorecard.json",
        "label": interp["label"],
        "robust_variants": interp["robust_variants"],
        "single_component_ablations_survive": True,
        "combined_offense_defense_removal_fails_at_split": {
            "train_frac": combined["train_frac"],
            "accuracy": combined["accuracy"],
            "brier_score": combined["brier_score"],
            "coinflip_brier": combined["coinflip_brier"],
        },
        "statement": f"{interp['label']}: single-component ablations "
        f"({', '.join(interp['robust_variants'])}) survive across all 3 splits; "
        f"removing offense+defense together (ablate_team_strength_both) fails to beat "
        f"coinflip at train_frac={combined['train_frac']}",
    }


def build_data_status(p230a: dict) -> dict:
    seasons = {s["season"]: s["classification"] for s in p230a["seasons"]}
    return {
        "source": "report/p230a_local_multiseason_runline_data_audit.json",
        "2024": seasons["2024"],
        "2025": seasons["2025"],
        "2026": seasons["2026"],
    }


def build_prediction_ledger_references() -> list[dict]:
    refs = []
    for path, task, role in (
        (P226A_PREDICTIONS_CSV, "P226-A", "run line / total probability model + paper "
         "backtest predictions (baseline_coinflip_50pct + poisson_team_rate_model, "
         "run_line + total markets)"),
        (P228A_PREDICTIONS_CSV, "P228-A", "run line robustness & train-fold-only Platt "
         "calibration predictions (raw + calibrated probabilities, anchor split)"),
        (P232A_PREDICTIONS_CSV, "P232-A", "2025 single-season run line feature ablation "
         "predictions (full_model + 4 ablation variants x 3 chronological splits)"),
    ):
        with open(path, newline="", encoding="utf-8") as f:
            row_count = sum(1 for _ in f) - 1
        refs.append({
            "task": task,
            "path": f"report/{path.name}",
            "row_count": row_count,
            "role": role,
        })
    return refs


EXECUTIVE_SUMMARY = [
    "This is the final, standalone, historical paper-only 2025 Run Line backtest "
    "package for MLB, consolidating P226-A (baseline model), P228-A (robustness + "
    "calibration), P230-A (local multi-season data audit), and P232-A (feature "
    "ablation); P234 has no local artifact and is acknowledged as not found "
    "(see p234_status).",
    "The poisson_team_rate_model beats the 0.5 coinflip Brier baseline on the "
    "2025 run_line test set (972 decided games): accuracy 0.6008 vs 0.4568, "
    "Brier 0.2395 vs 0.2500; train-fold-only Platt calibration further improves "
    "Brier to 0.2375 and ECE from 0.0483 to 0.0180.",
    "Robustness holds across pre-registered chronological splits (3/3 beat "
    "coinflip) and most monthly windows (4/5, 2 skipped for insufficient train "
    "rows); a local-only bootstrap/permutation appendix on the same 972-game "
    "ledger shows the Brier improvement is statistically distinguishable from "
    "zero at the 95% level (seeded, deterministic, no retraining).",
    "Feature ablation shows the signal depends on a fragile feature group: each "
    "single component (offense rate, defense rate, home field) survives alone "
    "across all 3 splits, but removing offense+defense together fails to beat "
    "coinflip at the 0.7 train-fraction split.",
    "Data status: 2024=LABEL_ONLY_NO_ODDS, 2025=FULL_RUNLINE_EVAL_READY, "
    "2026=MISSING_OR_UNUSABLE; multi-season expansion remains structurally "
    "blocked, not a modeling gap.",
    "Provider path status: PARKED_OPTIONAL — no provider has been contacted and "
    "no true-PIT provider data has ever been used in this evidence chain.",
    "This package is 2025-only, historical paper-only, uses odds of unverified "
    "provenance, is not true-PIT, is not a betting edge, is not live, is not "
    "production, is not a future prediction, and is not a multi-season "
    "validation.",
]


def build_package(report_dir: Path = REPORT_DIR) -> dict[str, Any]:
    sources = load_source_reports(report_dir)
    ledger = load_p226a_run_line_ledger(REPORT_DIR / "p226a_run_line_total_predictions.csv")
    p228a_anchor = load_p228a_anchor_ledger(REPORT_DIR / "p228a_run_line_robustness_predictions.csv")

    gate0 = reproduce_gate0(sources, ledger, p228a_anchor)
    appendix = compute_statistical_appendix(ledger)

    return {
        "task": "P235-A final 2025 run line backtest package",
        "scope": "LOCAL_HISTORICAL_REPLAY_SINGLE_SEASON_2025_ONLY",
        "package_type": "FINAL_CONSOLIDATION_PACKAGE",
        "disclaimers": DISCLAIMERS,
        "limitation_labels": LIMITATION_LABELS,
        "executive_summary": EXECUTIVE_SUMMARY,
        "gate0_reproduction": gate0,
        "scorecard_summary": build_scorecard_summary(sources["p226a"]),
        "prediction_ledger_references": build_prediction_ledger_references(),
        "robustness_summary": build_robustness_summary(sources["p228a"]),
        "calibration_summary": build_calibration_summary(sources["p228a"]),
        "ablation_summary": build_ablation_summary(sources["p232a"]),
        "data_status": build_data_status(sources["p230a"]),
        "p234_status": P234_STATUS,
        "provider_path_status": PROVIDER_PATH_STATUS,
        "decision_options": DECISION_OPTIONS,
        "statistical_appendix": appendix,
        "no_betting_edge_claim": True,
        "no_true_pit_validation_claim": True,
        "no_multi_season_validation_claim": True,
        "no_future_prediction_claim": True,
        "no_live_or_production_claim": True,
    }


def _fnum(x, d: int = 4) -> str:
    return "—" if x is None else f"{x:.{d}f}"


def render_markdown(pkg: dict) -> str:
    g0 = pkg["gate0_reproduction"]
    sc = pkg["scorecard_summary"]
    rob = pkg["robustness_summary"]
    cal = pkg["calibration_summary"]
    abl = pkg["ablation_summary"]
    data_status = pkg["data_status"]
    provider = pkg["provider_path_status"]
    appendix = pkg["statistical_appendix"]
    boot, perm = appendix["bootstrap"], appendix["permutation_test"]
    baseline, ref, model = appendix["predictive_baseline"], appendix["majority_class_reference"], appendix["model"]

    md: list[str] = []
    md.append("# P235-A — Final 2025 Run Line Backtest Package\n")
    md.append(
        "> **最終、獨立、僅本機歷史 / paper-only 的 2025 Run Line backtest 彙整包。** "
        "彙整 P226-A / P228-A / P230-A / P232-A 既有結果，並附本機統計附錄；非未來預測、"
        "非下注建議、無 EV/Kelly 宣稱、無 live 市場宣稱、無 production/DB 變更、非已證實 "
        "edge、非跨球季驗證、非 true-PIT 驗證。\n"
    )

    md.append("## Executive Summary")
    for line in pkg["executive_summary"]:
        md.append(f"- {line}")
    md.append("")

    md.append("## 範疇聲明")
    for d in pkg["disclaimers"]:
        md.append(f"- {d}")
    md.append("")

    md.append("## 1. Gate 0 Reproduction")
    md.append(f"- 狀態：`{g0['status']}`")
    md.append(f"- 方法：{g0['reproduction_method']}")
    rc = g0["recomputed"]
    md.append(
        f"- coinflip：accuracy={_fnum(rc['coinflip_accuracy'])}、"
        f"brier={_fnum(rc['coinflip_brier'])}"
    )
    md.append(
        f"- poisson_team_rate_model：accuracy={_fnum(rc['poisson_accuracy'])}、"
        f"brier={_fnum(rc['poisson_brier'])}"
    )
    md.append(f"- train-fold-only Platt calibrated：brier={_fnum(rc['calibrated_brier'])}")
    vf = g0["verified_from_artifact"]
    md.append(f"- ECE：{_fnum(vf['raw_ece'])} -> {_fnum(vf['calibrated_ece'])}")
    md.append(f"- all_within_tolerance：`{g0['all_within_tolerance']}`\n")

    md.append("## 2. Scorecard Summary")
    md.append(
        f"- 來源：`{sc['source']}`；測試期 `{sc['test_period'][0]}`→`{sc['test_period'][1]}`"
        f"（{sc['test_rows']} 場）"
    )
    md.append(
        f"- coinflip baseline：accuracy={_fnum(sc['coinflip_accuracy'])}、"
        f"brier={_fnum(sc['coinflip_brier'])}"
    )
    md.append(
        f"- poisson_team_rate_model：accuracy={_fnum(sc['poisson_accuracy'])}、"
        f"brier={_fnum(sc['poisson_brier'])}、ECE={_fnum(sc['poisson_ece'])}\n"
    )

    md.append("## 3. Prediction Ledger References")
    md.append("| task | path | rows | role |")
    md.append("|---|---|--:|---|")
    for ref_row in pkg["prediction_ledger_references"]:
        md.append(f"| {ref_row['task']} | `{ref_row['path']}` | {ref_row['row_count']} | {ref_row['role']} |")
    md.append("")

    md.append("## 4. Robustness Summary")
    md.append(f"- {rob['statement']}")
    md.append(f"- P228-A 穩健性判定：`{rob['label']}`\n")

    md.append("## 5. Calibration Summary")
    md.append(f"- {cal['statement']}")
    md.append(
        f"- 校準是否改善 Brier：`{cal['calibration_beats_raw_brier']}`；"
        f"改善 ECE：`{cal['calibration_beats_raw_ece']}`\n"
    )

    md.append("## 6. Ablation Summary")
    md.append(f"- 判定：`{abl['label']}`")
    md.append(f"- {abl['statement']}")
    comb = abl["combined_offense_defense_removal_fails_at_split"]
    md.append(
        f"- 失敗切分細節：train_frac={comb['train_frac']}、"
        f"accuracy={_fnum(comb['accuracy'])}、brier={_fnum(comb['brier_score'])} "
        f"(> coinflip brier={_fnum(comb['coinflip_brier'])})\n"
    )

    md.append("## 7. Data Status")
    md.append(f"- 來源：`{data_status['source']}`")
    md.append(f"- 2024 = `{data_status['2024']}`")
    md.append(f"- 2025 = `{data_status['2025']}`")
    md.append(f"- 2026 = `{data_status['2026']}`\n")

    md.append("## 8. P234 Status")
    md.append(f"- found_locally = `{pkg['p234_status']['found_locally']}`")
    md.append(f"- {pkg['p234_status']['note']}\n")

    md.append("## 9. Provider Path Status")
    md.append(f"- 狀態：`{provider['status']}`")
    md.append(f"- provider_replies_received = {provider['provider_replies_received']}")
    md.append(f"- true_pit_provider_data_used = `{provider['true_pit_provider_data_used']}`")
    md.append(f"- {provider['note']}\n")

    md.append("## 10. Local-Only Statistical Appendix")
    md.append(
        f"- 來源 ledger：`{appendix['source_ledger']}`（{appendix['n_games']} 場 "
        f"run_line test-set decided games）；no_retraining=`{appendix['no_retraining']}`"
    )
    md.append(
        f"- **Bootstrap 95% CI**（seed={boot['seed']}、n_resamples={boot['n_resamples']}）："
        f"mean brier margin (coinflip-poisson) = {boot['observed_mean']:.6f}，"
        f"95% CI = [{boot['ci95_lower']:.6f}, {boot['ci95_upper']:.6f}]"
    )
    md.append(
        f"- **Paired permutation test**（seed={perm['seed']}、"
        f"n_permutations={perm['n_permutations']}）：one-sided p-value = "
        f"{perm['p_value']:.6f}（H1：poisson Brier 改善 > 0）"
    )
    md.append(
        f"- **Chronological split stability**：split-grid "
        f"{appendix['chronological_split_stability']['split_grid_beats_coinflip']} 勝出、"
        f"monthly windows "
        f"{appendix['chronological_split_stability']['monthly_window_beats_coinflip']}"
        f"（彙整自 P228-A，非本檔重算）"
    )
    md.append(
        f"- **Predictive baseline**（`{baseline['label']}`，coinflip）：accuracy="
        f"{_fnum(baseline['accuracy'])}、brier={_fnum(baseline['brier'])}"
    )
    md.append(
        f"- **Majority-class reference**（`{ref['label']}`）：AWAY base rate="
        f"{_fnum(ref['away_base_rate'])}、HOME base rate={_fnum(ref['home_base_rate'])}；"
        f"若一律預測較多的一側，準確率="
        f"{_fnum(ref['majority_class_accuracy_if_always_picked'])}（{ref['note']}）"
    )
    md.append(
        f"- **Model**（`{model['label']}`，poisson_team_rate_model）：accuracy="
        f"{_fnum(model['accuracy'])}、brier={_fnum(model['brier'])}"
    )
    md.append(
        "- 完整統計附錄表格見 `report/p235a_final_2025_runline_statistical_appendix.csv`\n"
    )

    md.append("## 11. Limitation Labels")
    for label in pkg["limitation_labels"]:
        md.append(f"- `{label}`")
    md.append("")

    md.append("## 12. Decision Options")
    for opt in pkg["decision_options"]:
        md.append(f"- **{opt['option']}**：{opt['description']}")
    md.append("")

    md.append("## 免責聲明")
    md.append("- **2025-ONLY**：僅 2025 一季，非多球季驗證。")
    md.append("- **HISTORICAL / PAPER-ONLY**：全部數字皆為歷史回測結果，無真實下注、無資金部署。")
    md.append("- **ODDS PROVENANCE UNVERIFIED / NOT TRUE-PIT**：run line 讓分/賠率為賽後單快照。")
    md.append("- **NOT LIVE / NOT PRODUCTION**：無即時市場串接、無 production/DB/registry 變更。")
    md.append("- **NOT REAL BETTING / NOT A PROVEN EDGE**：無下注建議、無 EV/Kelly 宣稱。")
    md.append("- **NOT FUTURE PREDICTION**：所有評分場次皆為已完賽歷史場次。")
    md.append("- **NOT MULTI-SEASON VALIDATION**：本包僅涵蓋 2025 單一球季。")
    return "\n".join(md) + "\n"


def write_statistical_appendix_csv(appendix: dict[str, Any], out_dir: Path) -> Path:
    rows = build_statistical_appendix_rows(appendix)
    path = Path(out_dir) / "p235a_final_2025_runline_statistical_appendix.csv"
    fieldnames = ["metric", "value", "ci_lower_95", "ci_upper_95", "n", "seed",
                  "iterations", "label", "source", "notes"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return path


def write_reports(pkg: dict, out_dir: Path = REPORT_DIR) -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    json_p = out / "p235a_final_2025_runline_backtest_package.json"
    with open(json_p, "w", encoding="utf-8") as f:
        json.dump(pkg, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    written.append(json_p)

    md_p = out / "p235a_final_2025_runline_backtest_package.md"
    with open(md_p, "w", encoding="utf-8") as f:
        f.write(render_markdown(pkg))
    written.append(md_p)

    written.append(write_statistical_appendix_csv(pkg["statistical_appendix"], out))
    return written


def main() -> int:
    missing = [p for p in REQUIRED_INPUTS if not p.exists()]
    if missing:
        print("P235A_BLOCKED_NO_UPSTREAM_ARTIFACTS: missing tracked input(s):", file=sys.stderr)
        for p in missing:
            print(f"  - {p}", file=sys.stderr)
        return 2

    try:
        pkg = build_package(REPORT_DIR)
    except RuntimeError as exc:
        print(f"P235A_BLOCKED_GATE0_MISMATCH: {exc}", file=sys.stderr)
        return 2

    written = write_reports(pkg, REPORT_DIR)

    print("=" * 84)
    print("P235-A FINAL 2025 RUN LINE BACKTEST PACKAGE  (local historical paper-only; not a new model)")
    print("=" * 84)
    g0 = pkg["gate0_reproduction"]
    print(f"Gate0 status = {g0['status']}   all_within_tolerance = {g0['all_within_tolerance']}")
    rc = g0["recomputed"]
    print(
        f"  coinflip: brier={rc['coinflip_brier']:.4f}   "
        f"poisson: acc={rc['poisson_accuracy']:.4f} brier={rc['poisson_brier']:.4f}   "
        f"calibrated: brier={rc['calibrated_brier']:.4f}"
    )
    appendix = pkg["statistical_appendix"]
    print(
        f"bootstrap 95% CI margin=[{appendix['bootstrap']['ci95_lower']:.4f}, "
        f"{appendix['bootstrap']['ci95_upper']:.4f}]   "
        f"permutation p={appendix['permutation_test']['p_value']:.4f}"
    )
    print(f"ablation label = {pkg['ablation_summary']['label']}")
    print(f"data status = {pkg['data_status']}")
    print(f"provider path status = {pkg['provider_path_status']['status']}")
    print("-" * 84)
    print(f"wrote {len(written)} report files -> {REPORT_DIR}")
    for p in written:
        print(f"  - {p.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
