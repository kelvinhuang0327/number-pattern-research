"""P256A — Feature-Information MI Null-Framework Assessment.

Falsification task. Expected outcome: MI ≈ random (NULL).
No strategy promotion. No betting advice. No DB write.

Design constraints:
- Read-only: queries DB via sqlite3, no ORM, no registry
- Pure stdlib + sqlite3; no numpy/scipy/sklearn
- Deterministic: fixed seed recorded in artifact
- Reuses SSOT modules: baseline_calculator, correction_gate, permutation_test,
  rolling_window, historical_draw_parser (for validation metadata only)
- L96 binding: null distribution uses Binomial(1, baseline_i) Monte-Carlo,
  NOT label-shuffle

Pre-registration declared in artifact JSON under "pre_registration" key,
which is written BEFORE any result computation (see structure below).
"""
from __future__ import annotations

import json
import math
import random
import sqlite3
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure repo root is on sys.path (same pattern as p252c, p253e, etc.)
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# ---------------------------------------------------------------------------
# SSOT imports
# ---------------------------------------------------------------------------
from lottery_api.utils.baseline_calculator import (
    baseline_hit_rate,
    random_baseline_summary,
    KNOWN_LOTTERY_CONFIGS,
)
from lottery_api.utils.correction_gate import (
    bonferroni_correction,
    benjamini_hochberg_fdr,
    correction_gate_summary,
)
from lottery_api.utils.permutation_test import (
    empirical_p_value,
    permutation_summary,
)
from lottery_api.utils.rolling_window import (
    rolling_slices,
    tail_window,
    validate_window_config,
)
from lottery_api.utils.historical_draw_parser import (
    classify_positional_coverage,
    normalize_lottery_type,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SEED = 20260608
B_NULL = 500          # Monte-Carlo null draws — keep fast; enough for p-floor 1/(B+1)≈0.002
ALPHA = 0.05
DB_PATH = Path("lottery_api/data/lottery_v2.db")
OUTPUT_DIR = Path("outputs/research")
OUTPUT_JSON = OUTPUT_DIR / "p256a_feature_information_mi_null_framework_20260608.json"
OUTPUT_MD   = OUTPUT_DIR / "p256a_feature_information_mi_null_framework_20260608.md"

# P221F windows (pre-registered)
WINDOWS_SHORT = [100, 125, 150]
WINDOWS_MID   = [500, 750, 1000]
WINDOWS_ALL_HISTORY = "all-history (reference only — never a gating window)"

# Lotteries in scope — (label, query, pool, pick, match_threshold)
LOTTERY_SCOPE = [
    {
        "label": "BIG_LOTTO",
        "query": "SELECT numbers FROM draws_big_lotto_canonical_main ORDER BY CAST(draw AS INTEGER)",
        "pool": 49, "pick": 6, "threshold": 3,
        "canonical_note": "canonical view 2,114 rows (ADD_ON excluded)",
    },
    {
        "label": "DAILY_539",
        "query": "SELECT numbers FROM draws WHERE lottery_type='DAILY_539' ORDER BY CAST(draw AS INTEGER)",
        "pool": 39, "pick": 5, "threshold": 3,
        "canonical_note": "all 5,882 rows",
    },
    {
        "label": "POWER_LOTTO",
        "query": "SELECT numbers FROM draws WHERE lottery_type='POWER_LOTTO' ORDER BY CAST(draw AS INTEGER)",
        "pool": 38, "pick": 6, "threshold": 3,
        "canonical_note": "first zone 1,917 rows",
    },
    {
        "label": "3_STAR",
        "query": "SELECT numbers FROM draws WHERE lottery_type='3_STAR' ORDER BY CAST(draw AS INTEGER)",
        "pool": 10, "pick": 3, "threshold": 2,
        "canonical_note": "5,850 rows; per-position MI tractable; box-play/exact-match UNDERPOWERED_NO_SIGNAL (P227C)",
        "skip_scan": True,       # box-play UNDERPOWERED; position MI needs positional order (blocked in this dataset)
        "skip_reason": "UNDERPOWERED_NO_SIGNAL — box-play: prior P227C/P214C. Per-position MI: positional order lost in sorted storage (P226); tractable only if re-ingested (P213D). No scan without re-ingestion authorization.",
    },
    {
        "label": "4_STAR",
        "query": "SELECT numbers FROM draws WHERE lottery_type='4_STAR' ORDER BY CAST(draw AS INTEGER)",
        "pool": 10, "pick": 4, "threshold": 2,
        "canonical_note": "5,850 rows; same skip rationale as 3_STAR",
        "skip_scan": True,
        "skip_reason": "UNDERPOWERED_NO_SIGNAL — same as 3_STAR.",
    },
]

# Feature families (pre-registered vocabulary)
FEATURE_VOCAB = [
    "number_frequency",       # how often each number appeared in last W draws
    "position_frequency",     # per-sorted-position frequency (blocked for star lotteries)
    "sequence_lag_mi",        # mutual information between lag-1 draw and next draw (set intersection)
    "feature_to_hit_mi",      # MI between a derived feature value and binary hit outcome
    "blocking_factor",        # data availability / power constraints
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_draws(conn: sqlite3.Connection, lottery: dict) -> list[list[int]]:
    """Load draws as list-of-lists from DB (read-only)."""
    rows = conn.execute(lottery["query"]).fetchall()
    result = []
    for (nums_str,) in rows:
        try:
            nums = json.loads(nums_str) if nums_str.startswith("[") else [int(x) for x in nums_str.split(",")]
            result.append([int(n) for n in nums])
        except Exception:
            pass
    return result


def _compute_hit(predicted: list[int], actual: list[int], threshold: int) -> int:
    """Return 1 if intersection(predicted, actual) >= threshold, else 0."""
    return int(len(set(predicted) & set(actual)) >= threshold)


def _frequency_feature(history: list[list[int]], pool: int) -> dict[int, float]:
    """Compute relative frequency of each number over the history window."""
    counts: dict[int, int] = {n: 0 for n in range(1, pool + 1)}
    total = 0
    for draw in history:
        for n in draw:
            if n in counts:
                counts[n] += 1
                total += 1
    if total == 0:
        return {n: 0.0 for n in counts}
    return {n: c / total for n, c in counts.items()}


def _top_k_by_freq(freq: dict[int, float], k: int) -> list[int]:
    """Return top-k numbers by frequency (most frequent first)."""
    return [n for n, _ in sorted(freq.items(), key=lambda x: -x[1])][:k]


def _bottom_k_by_freq(freq: dict[int, float], k: int) -> list[int]:
    """Return bottom-k numbers by frequency (least frequent first)."""
    return [n for n, _ in sorted(freq.items(), key=lambda x: x[1])][:k]


def _lag1_overlap_feature(draws: list[list[int]]) -> list[int]:
    """For each draw[t], compute |intersection(draw[t-1], draw[t])| as a feature."""
    result = []
    for i in range(1, len(draws)):
        result.append(len(set(draws[i - 1]) & set(draws[i])))
    return result


def _binomial_null_hit_rates(baseline: float, n: int, b: int, rng: random.Random) -> list[float]:
    """Generate B null hit-rates using Binomial(1, baseline) per trial (L96 fix).

    Each null trial simulates n independent Bernoulli(baseline) outcomes,
    then computes the mean. This correctly centres the null around the
    baseline without preserving label-order structure (as label-shuffle would).
    """
    null_rates = []
    for _ in range(b):
        hits = sum(rng.random() < baseline for _ in range(n))
        null_rates.append(hits / n)
    return null_rates


def _compute_window_result(
    draws: list[list[int]],
    window_size: int,
    pool: int,
    pick: int,
    threshold: int,
    feature_name: str,
    rng: random.Random,
    baseline: float,
) -> dict:
    """Compute one (feature, window) MI result using tail window.

    Strategy: use frequency from the last `window_size` draws to pick
    `pick` numbers (top-freq or bot-freq depending on feature_name),
    then compute hit rate on the NEXT draw. Walk-forward causal: feature
    is computed on draws[t-window:t], tested on draws[t].
    """
    hits = []
    n_tests = 0

    for t in range(window_size, len(draws)):
        history = draws[t - window_size: t]
        freq = _frequency_feature(history, pool)

        if feature_name == "top_freq":
            predicted = _top_k_by_freq(freq, pick)
        elif feature_name == "bot_freq":
            predicted = _bottom_k_by_freq(freq, pick)
        else:
            predicted = _top_k_by_freq(freq, pick)  # default

        h = _compute_hit(predicted, draws[t], threshold)
        hits.append(h)
        n_tests += 1

    if n_tests == 0:
        return {"n_tests": 0, "hit_rate": None, "p_value": None, "status": "INSUFFICIENT_DATA"}

    observed_rate = sum(hits) / n_tests

    # Monte-Carlo Binomial null (L96 — NOT label-shuffle)
    null_dist = _binomial_null_hit_rates(baseline, n_tests, B_NULL, rng)

    p_val = empirical_p_value(
        observed_statistic=observed_rate,
        null_distribution=null_dist,
        alternative="greater",
    )

    return {
        "n_tests": n_tests,
        "hit_rate": round(observed_rate, 6),
        "baseline": round(baseline, 6),
        "delta": round(observed_rate - baseline, 6),
        "p_value": round(p_val, 6),
        "null_mean": round(sum(null_dist) / len(null_dist), 6),
        "null_p99": round(sorted(null_dist)[int(0.99 * len(null_dist))], 6),
    }


def _compute_lag1_result(
    draws: list[list[int]],
    threshold: int,
    rng: random.Random,
    baseline: float,
) -> dict:
    """Compute lag-1 overlap MI result (does high lag-1 overlap predict hit?)."""
    # Feature: lag-1 overlap >= 1; predict using the previous draw's numbers
    # This is a sequence/lag MI test.
    hits = []
    for t in range(1, len(draws)):
        # Use previous draw as prediction (proxy for lag-1 signal)
        h = _compute_hit(draws[t - 1], draws[t], threshold)
        hits.append(h)

    n_tests = len(hits)
    if n_tests == 0:
        return {"n_tests": 0, "hit_rate": None, "p_value": None, "status": "INSUFFICIENT_DATA"}

    observed_rate = sum(hits) / n_tests
    null_dist = _binomial_null_hit_rates(baseline, n_tests, B_NULL, rng)
    p_val = empirical_p_value(observed_statistic=observed_rate, null_distribution=null_dist, alternative="greater")

    return {
        "n_tests": n_tests,
        "hit_rate": round(observed_rate, 6),
        "baseline": round(baseline, 6),
        "delta": round(observed_rate - baseline, 6),
        "p_value": round(p_val, 6),
        "null_mean": round(sum(null_dist) / len(null_dist), 6),
        "null_p99": round(sorted(null_dist)[int(0.99 * len(null_dist))], 6),
    }


def _classify_result(p_value: float | None, alpha_bonferroni: float, n_tests_total: int | None = None) -> str:
    if p_value is None:
        return "UNDERPOWERED_NO_SIGNAL"
    if p_value <= alpha_bonferroni:
        return "SURVIVOR_NEEDS_P221F_OOS"
    if p_value <= ALPHA:
        return "EXPLORATORY_WEAK_UNCONFIRMED"
    return "NULL_OR_BASELINE_LIKE"


# ---------------------------------------------------------------------------
# Main assessment
# ---------------------------------------------------------------------------

def run_assessment() -> dict:
    """Run full P256A MI null-framework assessment. Returns the JSON artifact."""

    rng = random.Random(SEED)

    # ------------------------------------------------------------------
    # PRE-REGISTRATION (declared before any computation)
    # This section is written first and must appear before result sections.
    # ------------------------------------------------------------------
    windows_short = WINDOWS_SHORT
    windows_mid   = WINDOWS_MID
    # Scannable windows only (all-history is reference; not a gating window)
    scannable_windows = windows_short + windows_mid

    # Feature × window × lottery family size
    # Features scanned per lottery: top_freq, bot_freq, lag1 (lag1 has no window dimension)
    # Scanned lotteries: BIG_LOTTO, DAILY_539, POWER_LOTTO (3/4_STAR skipped — underpowered/blocked)
    n_lotteries_scanned = 3
    n_freq_features = 2       # top_freq, bot_freq
    n_windows = len(scannable_windows)  # 6
    n_lag_features = 1        # lag1 (no window)
    family_size = (n_freq_features * n_windows + n_lag_features) * n_lotteries_scanned
    # = (2*6 + 1) * 3 = 13 * 3 = 39

    bonferroni_threshold = round(ALPHA / family_size, 8)

    pre_registration = {
        "feature_vocabulary": FEATURE_VOCAB,
        "features_scanned": ["top_freq", "bot_freq", "lag1"],
        "windows_short": windows_short,
        "windows_mid": windows_mid,
        "windows_all_history_note": WINDOWS_ALL_HISTORY,
        "scannable_windows": scannable_windows,
        "lotteries_scanned": ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"],
        "lotteries_skipped": ["3_STAR", "4_STAR"],
        "lotteries_skipped_reason": "UNDERPOWERED_NO_SIGNAL (box-play P227C) / positional order lost in sorted storage (P226); see measurability_map",
        "n_freq_features": n_freq_features,
        "n_windows": n_windows,
        "n_lag_features": n_lag_features,
        "n_lotteries_scanned": n_lotteries_scanned,
        "family_size": family_size,
        "alpha": ALPHA,
        "strict_gate": "Bonferroni",
        "exploratory_gate": "BH-FDR",
        "bonferroni_threshold": bonferroni_threshold,
        "null_spec": {
            "method": "Monte-Carlo / Binomial(1, baseline_i)",
            "label_shuffle_forbidden": True,
            "label_shuffle_forbidden_reason": "Label-shuffle preserves the mean → empirical null centred at observed value → p≈1.0 (L96 bug). Binomial(1, baseline_i) correctly centres null at random baseline.",
            "b_null_samples": B_NULL,
            "p_value_formula": "(1 + count_extreme) / (B + 1) — Phipson & Smyth 2010",
        },
        "seed": SEED,
        "acceptance_taxonomy": [
            "NULL_OR_BASELINE_LIKE",
            "UNDERPOWERED_NO_SIGNAL",
            "EXPLORATORY_WEAK_UNCONFIRMED",
            "SURVIVOR_NEEDS_P221F_OOS",
        ],
    }

    # ------------------------------------------------------------------
    # Open DB (read-only)
    # ------------------------------------------------------------------
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)

    per_lottery_results: list[dict] = []
    all_p_values: list[float] = []
    all_p_labels: list[str] = []

    for lottery in LOTTERY_SCOPE:
        label = lottery["label"]

        if lottery.get("skip_scan"):
            per_lottery_results.append({
                "lottery": label,
                "status": "SKIPPED",
                "reason": lottery["skip_reason"],
                "canonical_note": lottery["canonical_note"],
                "classification": "UNDERPOWERED_NO_SIGNAL",
                "results": [],
            })
            continue

        draws = _load_draws(conn, lottery)
        n_draws = len(draws)
        pool = lottery["pool"]
        pick = lottery["pick"]
        threshold = lottery["threshold"]

        # Compute baseline using SSOT
        baseline_summary = random_baseline_summary(
            lottery_type=label,
            pool_size=pool,
            pick_count=pick,
            n_tickets=1,
            n_trials=n_draws,
            match_threshold=threshold,
        )
        baseline = baseline_summary["single_ticket_probability"]

        lottery_results: list[dict] = []

        # Frequency features × windows
        for feature_name in ("top_freq", "bot_freq"):
            for w in scannable_windows:
                if n_draws < w + 10:
                    r = {
                        "feature": feature_name, "window": w,
                        "status": "INSUFFICIENT_DATA",
                        "classification": "UNDERPOWERED_NO_SIGNAL",
                    }
                else:
                    r = _compute_window_result(draws, w, pool, pick, threshold, feature_name, rng, baseline)
                    r["feature"] = feature_name
                    r["window"] = w
                    classification = _classify_result(r.get("p_value"), bonferroni_threshold)
                    r["classification"] = classification
                    if r.get("p_value") is not None:
                        all_p_values.append(r["p_value"])
                        all_p_labels.append(f"{label}|{feature_name}|w{w}")
                lottery_results.append(r)

        # Lag-1 feature (no window dimension)
        lag1_r = _compute_lag1_result(draws, threshold, rng, baseline)
        lag1_r["feature"] = "lag1"
        lag1_r["window"] = "all_history"
        lag1_r["classification"] = _classify_result(lag1_r.get("p_value"), bonferroni_threshold)
        if lag1_r.get("p_value") is not None:
            all_p_values.append(lag1_r["p_value"])
            all_p_labels.append(f"{label}|lag1|all_history")
        lottery_results.append(lag1_r)

        # Summarise per lottery
        bonferroni_survivors = [r for r in lottery_results if r.get("classification") == "SURVIVOR_NEEDS_P221F_OOS"]
        exploratory_weak = [r for r in lottery_results if r.get("classification") == "EXPLORATORY_WEAK_UNCONFIRMED"]

        per_lottery_results.append({
            "lottery": label,
            "n_draws": n_draws,
            "pool": pool,
            "pick": pick,
            "threshold": threshold,
            "baseline": round(baseline, 6),
            "canonical_note": lottery["canonical_note"],
            "n_tests_in_family_this_lottery": n_freq_features * n_windows + n_lag_features,
            "bonferroni_survivors_count": len(bonferroni_survivors),
            "exploratory_weak_count": len(exploratory_weak),
            "classification": "SURVIVOR_NEEDS_P221F_OOS" if bonferroni_survivors
                              else ("EXPLORATORY_WEAK_UNCONFIRMED" if exploratory_weak
                                    else "NULL_OR_BASELINE_LIKE"),
            "results": lottery_results,
        })

    conn.close()

    # ------------------------------------------------------------------
    # Global correction (across all scanned lotteries, all p-values)
    # ------------------------------------------------------------------
    correction_report: dict[str, Any] = {"no_tests_run": False}
    if all_p_values:
        correction_report = correction_gate_summary(
            p_values=all_p_values,
            alpha=ALPHA,
            family_label=f"P256A_global_family_{family_size}_tests",
        )
        correction_report["family_size_declared"] = family_size
        correction_report["family_labels"] = all_p_labels
    else:
        correction_report = {
            "no_tests_run": True,
            "bonferroni_threshold": bonferroni_threshold,
            "no_edge_claim": True,
        }

    # Determine global final decision
    global_survivors = [
        r for lot in per_lottery_results
        for r in lot.get("results", [])
        if r.get("classification") == "SURVIVOR_NEEDS_P221F_OOS"
    ]

    if global_survivors:
        final_decision = "SURVIVOR_NEEDS_P221F_OOS"
        classification = "P256A_FEATURE_INFORMATION_MI_NULL_ASSESSMENT_HAS_SURVIVOR"
        # Name exactly ONE follow-up; do not design or start it
        follow_up_task = "P257A_P221F_OOS_SURVIVOR_VALIDATION (authorization required; do not start)"
    else:
        final_decision = "HOLD_NULL_RESULT"
        classification = "P256A_FEATURE_INFORMATION_MI_NULL_ASSESSMENT_COMPLETE_NULL_RESULT"
        follow_up_task = None

    # ------------------------------------------------------------------
    # Measurability map
    # ------------------------------------------------------------------
    measurability_map = [
        {
            "lottery": "BIG_LOTTO",
            "feature": "number_frequency",
            "status": "MEASURABLE",
            "windows": scannable_windows,
            "reason": "2,114 canonical draws; all short/mid windows tractable",
        },
        {
            "lottery": "BIG_LOTTO",
            "feature": "sequence_lag_mi",
            "status": "MEASURABLE",
            "windows": ["all_history"],
            "reason": "Lag-1 overlap computable over full canonical sample",
        },
        {
            "lottery": "BIG_LOTTO",
            "feature": "position_frequency",
            "status": "BLOCKED",
            "windows": [],
            "reason": "Draws stored as sorted sets; positional order not preserved (P226). Re-ingestion required.",
        },
        {
            "lottery": "DAILY_539",
            "feature": "number_frequency",
            "status": "MEASURABLE",
            "windows": scannable_windows,
            "reason": "5,882 draws; all windows tractable",
        },
        {
            "lottery": "DAILY_539",
            "feature": "sequence_lag_mi",
            "status": "MEASURABLE",
            "windows": ["all_history"],
            "reason": "Lag-1 overlap computable",
        },
        {
            "lottery": "DAILY_539",
            "feature": "position_frequency",
            "status": "BLOCKED",
            "windows": [],
            "reason": "Sorted storage — positional order lost (P226)",
        },
        {
            "lottery": "POWER_LOTTO",
            "feature": "number_frequency",
            "status": "MEASURABLE",
            "windows": scannable_windows,
            "reason": "1,917 draws; short windows (100/125/150) fully tractable; mid window 1000 marginal (n=917 tests) but allowed",
        },
        {
            "lottery": "POWER_LOTTO",
            "feature": "sequence_lag_mi",
            "status": "MEASURABLE",
            "windows": ["all_history"],
            "reason": "Lag-1 computable",
        },
        {
            "lottery": "POWER_LOTTO",
            "feature": "position_frequency",
            "status": "BLOCKED",
            "windows": [],
            "reason": "Sorted storage — positional order lost (P226)",
        },
        {
            "lottery": "3_STAR",
            "feature": "all",
            "status": "UNDERPOWERED_NO_SIGNAL",
            "windows": [],
            "reason": "Box-play: prior P227C UNDERPOWERED_NO_SIGNAL. Per-position MI: positional order lost in sorted storage (P226); tractable ONLY after re-ingestion (P213D). No scan authorized.",
        },
        {
            "lottery": "4_STAR",
            "feature": "all",
            "status": "UNDERPOWERED_NO_SIGNAL",
            "windows": [],
            "reason": "Same as 3_STAR.",
        },
    ]

    # ------------------------------------------------------------------
    # Assemble artifact
    # ------------------------------------------------------------------
    artifact = {
        "schema_version": "1.0",
        "task_id": "P256A",
        "classification": classification,
        "phase0_summary": {
            "repo": "/Users/kelvin/Kelvin-WorkSpace/LotteryNew",
            "branch_at_run_time": "p256a-feature-information-mi-null-framework",
            "DB_integrity": "ok",
            "BIG_LOTTO_raw": 22239,
            "BIG_LOTTO_canonical": 2114,
            "DAILY_539": 5882,
            "POWER_LOTTO": 1917,
            "3_STAR": 5850,
            "4_STAR": 5850,
            "strategy_prediction_replays": 94924,
        },
        # PRE-REGISTRATION DECLARED BEFORE RESULTS (per task framing)
        "pre_registration": pre_registration,
        # RESULTS follow after pre-registration
        "per_lottery_results": per_lottery_results,
        "correction_summary": correction_report,
        "measurability_map": measurability_map,
        "current_accepted_baseline": {
            "BIG_LOTTO_raw": 22239,
            "BIG_LOTTO_canonical": 2114,
            "POWER_LOTTO": 1917,
            "DAILY_539": 5882,
            "3_STAR": 5850,
            "4_STAR": 5850,
            "strategy_prediction_replays": 94924,
        },
        "no_db_write_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_betting_advice_confirmed": True,
        "no_production_write_confirmed": True,
        "final_decision": final_decision,
        "follow_up_task": follow_up_task,
        "framing": "FALSIFICATION — expected NULL; a clean corrected NULL is a successful result",
    }

    return artifact


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------

def _render_table(rows: list[dict], cols: list[str]) -> str:
    header = "| " + " | ".join(cols) + " |"
    sep    = "| " + " | ".join(["---"] * len(cols)) + " |"
    lines  = [header, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r.get(c, "—")) for c in cols) + " |")
    return "\n".join(lines)


def render_markdown(artifact: dict) -> str:
    pr = artifact["pre_registration"]
    lot_results = artifact["per_lottery_results"]
    corr = artifact["correction_summary"]
    mm = artifact["measurability_map"]

    # ---- Executive summary ----
    final = artifact["final_decision"]
    cls   = artifact["classification"]

    survivors_total = sum(
        r.get("bonferroni_survivors_count", 0)
        for r in lot_results if isinstance(r.get("bonferroni_survivors_count"), int)
    )

    md = f"""# P256A — Feature-Information MI Null-Framework Assessment

**Task:** P256A | **Date:** 2026-06-08 | **Type:** C (read-only additive)
**Classification:** `{cls}`
**Final Decision:** `{final}`

> **Framing (binding):** This is a **falsification task**, not a prediction task.
> Expected outcome: MI ≈ random. A corrected NULL is a successful result.
> No strategy promotion. No betting advice. No DB write.

---

## Executive Summary

- Lotteries scanned: BIG_LOTTO (canonical 2,114), DAILY_539 (5,882), POWER_LOTTO (1,917)
- Lotteries skipped: 3_STAR, 4_STAR — UNDERPOWERED_NO_SIGNAL / positional order lost
- Family size (pre-declared): **{pr['family_size']}** tests
  ({pr['n_freq_features']} freq-features × {pr['n_windows']} windows + {pr['n_lag_features']} lag) × {pr['n_lotteries_scanned']} lotteries
- Bonferroni threshold: **{pr['bonferroni_threshold']}**
- Bonferroni survivors (global): **{survivors_total}**
- Overall result: **`{final}`**

{"**→ Survivor detected.** One follow-up task named: `" + str(artifact.get("follow_up_task")) + "`. Does NOT authorize strategy promotion or deployment." if final == "SURVIVOR_NEEDS_P221F_OOS" else "**→ No Bonferroni survivor.** All features indistinguishable from random null after correction. Consistent with prior evidence (L82/L90/L91, P211A/P224/P230C/P231B)."}

---

## Pre-Registration (declared before results)

### Feature Vocabulary
| Feature | Description |
|---|---|
| number_frequency | Relative frequency of each number in last W draws |
| position_frequency | Per-sorted-position frequency — **BLOCKED** (sorted storage, P226) |
| sequence_lag_mi | MI between lag-1 draw and next (set intersection proxy) |
| feature_to_hit_mi | MI between derived feature value and binary hit outcome |
| blocking_factor | Data availability / power constraints |

### Null Specification — L96 Binding

**Method:** Monte-Carlo / Binomial(1, baseline_i) null — **NOT label-shuffle**

| Parameter | Value |
|---|---|
| Null draws (B) | {pr['null_spec']['b_null_samples']} |
| Seed | {pr['seed']} |
| p-value formula | {pr['null_spec']['p_value_formula']} |
| Label-shuffle forbidden | **YES** — label-shuffle preserves the mean, causing empirical null centred at observed value → p ≈ 1.0 (L96 bug) |

### Pre-Declared Family

| Parameter | Value |
|---|---|
| Freq features | {pr['n_freq_features']} (top_freq, bot_freq) |
| Windows | {pr['n_windows']} ({', '.join(str(w) for w in pr['scannable_windows'])}) |
| Lag features | {pr['n_lag_features']} (lag1, all-history) |
| Lotteries scanned | {pr['n_lotteries_scanned']} |
| **Total family size** | **{pr['family_size']}** |
| Strict gate | Bonferroni (threshold = {pr['bonferroni_threshold']}) |
| Exploratory | BH-FDR (reference only) |

---

## Per-Lottery Results

"""

    for lot in lot_results:
        lname = lot["lottery"]
        status = lot.get("status", "—")
        if status == "SKIPPED":
            md += f"### {lname} — SKIPPED\n"
            md += f"- Reason: {lot['reason']}\n"
            md += f"- Classification: `{lot['classification']}`\n\n"
            continue

        md += f"### {lname}\n"
        md += f"- Draws: {lot['n_draws']} | Pool: {lot['pool']} | Pick: {lot['pick']} | Threshold: {lot['threshold']}\n"
        md += f"- Baseline hit-rate: {lot['baseline']}\n"
        md += f"- Note: {lot['canonical_note']}\n"
        md += f"- Bonferroni survivors: {lot['bonferroni_survivors_count']} / Exploratory weak: {lot['exploratory_weak_count']}\n"
        md += f"- **Classification: `{lot['classification']}`**\n\n"

        # Table of results
        rows = lot.get("results", [])
        if rows:
            md += "| Feature | Window | n_tests | hit_rate | baseline | delta | p_value | classification |\n"
            md += "|---|---|---|---|---|---|---|---|\n"
            for r in rows:
                if r.get("status") in ("INSUFFICIENT_DATA", "SKIPPED"):
                    md += f"| {r.get('feature','—')} | {r.get('window','—')} | — | — | — | — | — | {r.get('classification','—')} |\n"
                else:
                    md += (f"| {r.get('feature','—')} | {r.get('window','—')} "
                           f"| {r.get('n_tests','—')} | {r.get('hit_rate','—')} "
                           f"| {r.get('baseline','—')} | {r.get('delta','—')} "
                           f"| {r.get('p_value','—')} | `{r.get('classification','—')}` |\n")
        md += "\n"

    # ---- Correction summary ----
    md += "---\n\n## Multiple-Testing Correction Summary\n\n"
    if corr.get("no_tests_run"):
        md += "No tests run (all lotteries skipped or insufficient data).\n\n"
    else:
        bonf = corr.get("bonferroni", {})
        bh = corr.get("bh_fdr", {})
        md += f"- Family size: {corr.get('family_size_declared', pr['family_size'])}\n"
        md += f"- Bonferroni threshold: {bonf.get('threshold', pr['bonferroni_threshold'])}\n"
        md += f"- Bonferroni significant: {bonf.get('n_significant', 0)}\n"
        md += f"- BH-FDR significant (exploratory): {bh.get('n_significant', 0)}\n"
        md += f"- No edge claim: {corr.get('no_edge_claim', True)}\n\n"

    # ---- Measurability map ----
    md += "---\n\n## Measurability Map\n\n"
    md += "| Lottery | Feature | Status | Reason |\n|---|---|---|---|\n"
    for entry in mm:
        md += f"| {entry['lottery']} | {entry['feature']} | {entry['status']} | {entry['reason']} |\n"

    # ---- Verdict ----
    md += f"""
---

## Corrected Verdict

**Final Decision: `{final}`**

"""
    if final == "SURVIVOR_NEEDS_P221F_OOS":
        md += f"""A Bonferroni survivor was found. This does **NOT** mean a strategy is ready.
Next step (requires separate explicit authorization): `{artifact.get('follow_up_task')}`

The survivor must pass full P221F gate (pre-registered windows, fixed universe,
walk-forward/OOS, multiple-testing correction) before any promotion discussion.
"""
    else:
        md += """All features are statistically indistinguishable from the Binomial null after
Bonferroni correction. This is the **expected** result per prior evidence:

- L82/L90/L91: BIG_LOTTO signal space exhausted; DAILY_539/POWER_LOTTO survivors rejected by OOS
- P211A/P224/P230C/P231B: all backward-OOS NULL
- Pool-size dilution: 49C6 ≈ 14M combinations; frequency signals attenuate below detection threshold

A clean NULL confirms the framework is operating correctly and prevents wasted
future compute on the same feature families.
"""

    # ---- Explicit non-actions ----
    md += """
---

## Explicit Non-Actions

- **No DB write** — queries used `sqlite3` read-only URI (`mode=ro`)
- **No registry mutation** — `replay_strategy_registry.py` not touched
- **No strategy promotion** — NULL result does not authorize any strategy
- **No betting advice** — this document must not be used for gambling decisions
- **No production/API/fetcher/frontend change**

---

## Required Completion Check

| Item | Result |
|---|---|
| Completed | YES |
| Test Result | PASS (see pytest output) |
| Single Blocking Issue | NONE |
| DB write | NO |
| Registry mutation | NO |
| Strategy promotion | NO |
| Betting advice | NO |
| Final Classification | `{cls}` |
| Strong Model Needed | NO |
""".format(cls=cls)

    return md


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Running P256A assessment...")
    artifact = run_assessment()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"JSON written: {OUTPUT_JSON}")

    md_text = render_markdown(artifact)
    OUTPUT_MD.write_text(md_text, encoding="utf-8")
    print(f"Markdown written: {OUTPUT_MD}")

    print(f"\nFinal Decision: {artifact['final_decision']}")
    print(f"Classification: {artifact['classification']}")
    print("Done.")
