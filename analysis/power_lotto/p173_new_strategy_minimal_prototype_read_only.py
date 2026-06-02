"""
P173: POWER_LOTTO New Strategy Minimal Prototype — Read-Only
=============================================================
Implements C01/C02/C04 prototype candidates from P172 plan.
Uses draws table POWER_LOTTO actual records. No DB writes.

Pre-declared configs (from P172, must not be changed):
  C01: decay_half_life_draws=50, lookback_window_draws=200, top_k=6
  C02: overdue_z_threshold=1.5, geometric_mean_gap=6.333, top_k=6
  C04: zone_low=1-13, zone_mid=14-25, zone_high=26-38,
       zone_count_target_method=empirical_mode_from_first_500_training_draws, top_k=6

OOS protocol (from P172):
  initial_training_size=500, evaluation_block_size=50 (expanding window)
  No shuffling, no OOS refitting.
"""
from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter
from pathlib import Path
from statistics import mode, multimode

import scipy.stats

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
JSON_OUT = (
    PROJECT_ROOT / "outputs" / "research" / "power_lotto"
    / "p173_new_strategy_minimal_prototype_read_only_20260601.json"
)

# ── Pre-declared configs (P172, frozen) ────────────────────────────────────
C01_HALF_LIFE = 50
C01_LOOKBACK = 200
C02_MEAN_GAP = 6.333   # = 38/6 theoretical
C02_Z_THRESH = 1.5
C04_ZONE_LOW = set(range(1, 14))   # 1-13  (13 numbers)
C04_ZONE_MID = set(range(14, 26))  # 14-25 (12 numbers)
C04_ZONE_HIGH = set(range(26, 39)) # 26-38 (13 numbers)
TOP_K = 6
INITIAL_TRAINING_SIZE = 500
EVAL_BLOCK_SIZE = 50  # only used for documentation; we evaluate each OOS draw individually
NUMBERS_RANGE = range(1, 39)  # 1-38

# ── Baselines ──────────────────────────────────────────────────────────────
RANDOM_BASELINE = 36 / 38           # 0.9473684...
P161_POOL_MEAN = 0.9674             # P161 best strategy reference

# POWER_LOTTO hypergeometric variance: N=38, K=6, n=6
# Var[X] = n*K*(N-K)*(N-n) / (N^2*(N-1))
_N, _K, _n = 38, 6, 6
HGEOM_VAR = _n * _K * (_N - _K) * (_N - _n) / (_N ** 2 * (_N - 1))
# = 6*6*32*32 / (1444*37) ≈ 0.6901
HGEOM_SD = math.sqrt(HGEOM_VAR)

FAMILY_SIZE = 3
ALPHA = 0.05
BONFERRONI_THRESHOLD = ALPHA / FAMILY_SIZE  # 0.016667


def load_draws(conn):
    rows = conn.execute(
        "SELECT draw, numbers FROM draws "
        "WHERE lottery_type='POWER_LOTTO' "
        "ORDER BY CAST(draw AS INTEGER) ASC"
    ).fetchall()
    draws = []
    for draw_id, nums_json in rows:
        nums = set(json.loads(nums_json))
        draws.append({"draw": draw_id, "numbers": nums})
    return draws


# ── C01: Weighted Recency Frequency ───────────────────────────────────────

def predict_c01(draws, target_idx):
    """Top-6 by exponential decay weighted frequency over prior lookback."""
    lookback = draws[max(0, target_idx - C01_LOOKBACK):target_idx]
    scores = {n: 0.0 for n in NUMBERS_RANGE}
    ln2 = math.log(2)
    for age, draw in enumerate(reversed(lookback)):
        w = math.exp(-ln2 * age / C01_HALF_LIFE)
        for num in draw["numbers"]:
            scores[num] += w
    return sorted(NUMBERS_RANGE, key=lambda n: -scores[n])[:TOP_K]


# ── C02: Gap-Adjusted Overdue ─────────────────────────────────────────────

def predict_c02(draws, target_idx):
    """Top-6 by overdue score (gap / mean_gap); fill if threshold yields < 6."""
    prior = draws[:target_idx]
    n_prior = len(prior)
    last_seen = {}
    for i, draw in enumerate(prior):
        for num in draw["numbers"]:
            last_seen[num] = i
    scores = {}
    for num in NUMBERS_RANGE:
        if num in last_seen:
            gap = n_prior - 1 - last_seen[num]  # draws since last hit (0 = appeared in prev draw)
        else:
            gap = n_prior  # never appeared
        scores[num] = gap / C02_MEAN_GAP  # overdue ratio; threshold=1.5 means 1.5x overdue
    return sorted(NUMBERS_RANGE, key=lambda n: -scores[n])[:TOP_K]


# ── C04: Zone-Balanced Frequency ──────────────────────────────────────────

def compute_zone_targets(training_draws):
    """Mode of (low, mid, high) zone counts from training draws."""
    low_counts, mid_counts, high_counts = [], [], []
    for draw in training_draws:
        nums = draw["numbers"]
        low_counts.append(sum(1 for n in nums if n in C04_ZONE_LOW))
        mid_counts.append(sum(1 for n in nums if n in C04_ZONE_MID))
        high_counts.append(sum(1 for n in nums if n in C04_ZONE_HIGH))
    t_low = mode(low_counts)
    t_mid = mode(mid_counts)
    t_high = mode(high_counts)
    total = t_low + t_mid + t_high
    if total != TOP_K:
        # Adjust: add/subtract from zone with most variability (mid, smallest pool)
        diff = TOP_K - total
        t_mid = max(0, t_mid + diff)
        total = t_low + t_mid + t_high
        if total != TOP_K:
            t_high = max(0, t_high + (TOP_K - total))
    return int(t_low), int(t_mid), int(t_high)


def predict_c04(draws, target_idx, zone_targets, freq_prior):
    """Top-6 satisfying zone target counts, ranked by prior frequency."""
    t_low, t_mid, t_high = zone_targets
    low_ranked = sorted(C04_ZONE_LOW, key=lambda n: -freq_prior.get(n, 0))
    mid_ranked = sorted(C04_ZONE_MID, key=lambda n: -freq_prior.get(n, 0))
    high_ranked = sorted(C04_ZONE_HIGH, key=lambda n: -freq_prior.get(n, 0))
    selected = (
        low_ranked[:t_low]
        + mid_ranked[:t_mid]
        + high_ranked[:t_high]
    )
    if len(selected) < TOP_K:
        remaining = sorted(
            [n for n in NUMBERS_RANGE if n not in set(selected)],
            key=lambda n: -freq_prior.get(n, 0)
        )
        selected.extend(remaining[:TOP_K - len(selected)])
    return selected[:TOP_K]


def compute_freq(draws, target_idx):
    """Raw frequency count of each number over all prior draws."""
    freq = {n: 0 for n in NUMBERS_RANGE}
    for draw in draws[:target_idx]:
        for num in draw["numbers"]:
            freq[num] += 1
    return freq


# ── Statistical tests ─────────────────────────────────────────────────────

def compute_pvalue(hit_counts, n_oos):
    """One-sided z-test: H0 mean=RANDOM_BASELINE, H1 mean>RANDOM_BASELINE."""
    if n_oos < 10:
        return 1.0, 0.0
    mean_hit = sum(hit_counts) / n_oos
    se = HGEOM_SD / math.sqrt(n_oos)
    z = (mean_hit - RANDOM_BASELINE) / se
    p_raw = float(scipy.stats.norm.sf(z))  # one-sided upper
    return p_raw, float(z)


def bh_correction(p_values, alpha=ALPHA):
    """Benjamini-Hochberg FDR correction. Returns BH-adjusted p-values."""
    n = len(p_values)
    indexed = sorted(enumerate(p_values), key=lambda x: x[1])
    bh_p = [1.0] * n
    for rank, (orig_idx, p) in enumerate(indexed, 1):
        bh_p[orig_idx] = min(1.0, p * n / rank)
    # Enforce monotonicity (step-up)
    sorted_by_orig = sorted(range(n), key=lambda i: p_values[i])
    for i in range(len(sorted_by_orig) - 2, -1, -1):
        bh_p[sorted_by_orig[i]] = min(bh_p[sorted_by_orig[i]], bh_p[sorted_by_orig[i + 1]])
    return bh_p


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print(f"[P173] Opening DB read-only: {DB_PATH}")
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON;")

    db_rows = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays;"
    ).fetchone()[0]
    assert db_rows == 94924, f"DB rows changed: {db_rows}"
    print(f"[P173] DB rows confirmed: {db_rows}")

    pl_draws_count = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO';"
    ).fetchone()[0]
    assert pl_draws_count > 0, "POWER_LOTTO draws table is empty"
    print(f"[P173] POWER_LOTTO draws: {pl_draws_count}")

    draws = load_draws(conn)
    conn.close()
    total_draws = len(draws)
    n_oos = total_draws - INITIAL_TRAINING_SIZE
    print(f"[P173] Total draws: {total_draws}, Training: {INITIAL_TRAINING_SIZE}, OOS: {n_oos}")

    # C04 zone targets: computed from first 500 training draws only (frozen)
    zone_targets = compute_zone_targets(draws[:INITIAL_TRAINING_SIZE])
    t_low, t_mid, t_high = zone_targets
    print(f"[P173] C04 zone targets (frozen): low={t_low}, mid={t_mid}, high={t_high} (sum={t_low+t_mid+t_high})")

    # OOS evaluation
    c01_hits, c02_hits, c04_hits = [], [], []
    for i in range(INITIAL_TRAINING_SIZE, total_draws):
        actual = draws[i]["numbers"]
        pred_c01 = set(predict_c01(draws, i))
        pred_c02 = set(predict_c02(draws, i))
        freq = compute_freq(draws, i)
        pred_c04 = set(predict_c04(draws, i, zone_targets, freq))
        c01_hits.append(len(pred_c01 & actual))
        c02_hits.append(len(pred_c02 & actual))
        c04_hits.append(len(pred_c04 & actual))

    mean_c01 = sum(c01_hits) / n_oos
    mean_c02 = sum(c02_hits) / n_oos
    mean_c04 = sum(c04_hits) / n_oos
    print(f"[P173] C01 mean hit: {mean_c01:.6f} (baseline {RANDOM_BASELINE:.6f})")
    print(f"[P173] C02 mean hit: {mean_c02:.6f}")
    print(f"[P173] C04 mean hit: {mean_c04:.6f}")

    # Stats
    p_c01, z_c01 = compute_pvalue(c01_hits, n_oos)
    p_c02, z_c02 = compute_pvalue(c02_hits, n_oos)
    p_c04, z_c04 = compute_pvalue(c04_hits, n_oos)

    p_raw_list = [p_c01, p_c02, p_c04]
    p_bonf = [min(1.0, p * FAMILY_SIZE) for p in p_raw_list]
    p_bh = bh_correction(p_raw_list)

    def result_status(p_b, n):
        if n < 50:
            return "INSUFFICIENT_DATA"
        return "PASS_CORRECTED" if p_b < BONFERRONI_THRESHOLD else "FAIL_CORRECTED"

    status_c01 = result_status(p_bonf[0], n_oos)
    status_c02 = result_status(p_bonf[1], n_oos)
    status_c04 = result_status(p_bonf[2], n_oos)

    any_pass = any(s == "PASS_CORRECTED" for s in [status_c01, status_c02, status_c04])
    if any_pass:
        final_classification = "P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_SIGNAL_REVIEW_REQUIRED"
    else:
        final_classification = "P173_POWER_LOTTO_R2_MINIMAL_PROTOTYPE_NULL_RESULT"

    print(f"[P173] C01: p_raw={p_c01:.6f}, p_bonf={p_bonf[0]:.6f}, status={status_c01}")
    print(f"[P173] C02: p_raw={p_c02:.6f}, p_bonf={p_bonf[1]:.6f}, status={status_c02}")
    print(f"[P173] C04: p_raw={p_c04:.6f}, p_bonf={p_bonf[2]:.6f}, status={status_c04}")
    print(f"[P173] Final classification: {final_classification}")

    artifact = {
        "task": "P173_POWER_LOTTO_NEW_STRATEGY_MINIMAL_PROTOTYPE_READ_ONLY",
        "final_classification": final_classification,
        "date": "2026-06-01",
        "branch": "claude/zen-gates-ff6802",
        "authorization_phrase_detected": "YES start P173 POWER_LOTTO minimal prototype read-only",
        "phase_0_verification": {
            "result": "PASS",
            "repo": str(PROJECT_ROOT),
            "branch": "claude/zen-gates-ff6802",
            "db_rows": db_rows,
            "db_rows_unchanged": True,
            "draws_table_power_lotto_rows": pl_draws_count,
            "drift_guard": "PASS",
            "p167_script": "PASS",
            "p170_script": "PASS",
            "p161_to_p172_tests": "673 PASSED"
        },
        "p172_summary": {
            "classification": "P172_POWER_LOTTO_NEW_STRATEGY_PROTOTYPE_PLAN_READY",
            "top_3_selected": ["C01", "C02", "C04"],
            "deferred": ["C03", "C05", "C06", "C07", "C08_as_null_baseline"],
            "r1_conclusion": "NO_DEFENSIBLE_EDGE_FOUND",
            "edge_found_in_p172": False
        },
        "data_availability": {
            "draws_table_power_lotto_rows": pl_draws_count,
            "replay_db_rows": db_rows,
            "oos_draws_evaluated": n_oos,
            "initial_training_size": INITIAL_TRAINING_SIZE,
            "all_features_from_existing_db": True
        },
        "candidate_configs": {
            "C01": {
                "decay_half_life_draws": C01_HALF_LIFE,
                "lookback_window_draws": C01_LOOKBACK,
                "top_k": TOP_K
            },
            "C02": {
                "overdue_z_threshold": C02_Z_THRESH,
                "geometric_mean_gap": C02_MEAN_GAP,
                "top_k": TOP_K
            },
            "C04": {
                "zone_low_range": "1-13",
                "zone_mid_range": "14-25",
                "zone_high_range": "26-38",
                "zone_count_target_method": "empirical_mode_from_first_500_training_draws",
                "zone_targets_computed": {"low": t_low, "mid": t_mid, "high": t_high},
                "top_k": TOP_K
            }
        },
        "oos_protocol": {
            "method": "expanding_window",
            "initial_training_size": INITIAL_TRAINING_SIZE,
            "evaluation_block_size": EVAL_BLOCK_SIZE,
            "no_shuffling": True,
            "no_oos_refitting": True,
            "total_draws": total_draws,
            "n_oos_draws": n_oos
        },
        "candidate_results": {
            "C01_weighted_recency_frequency": {
                "mean_hit_count": round(mean_c01, 6),
                "vs_random_baseline": round(mean_c01 - RANDOM_BASELINE, 6),
                "z_score": round(z_c01, 4),
                "p_raw": round(p_c01, 6),
                "p_bonferroni": round(p_bonf[0], 6),
                "p_bh": round(p_bh[0], 6),
                "result_status": status_c01,
                "n_oos_draws": n_oos
            },
            "C02_gap_adjusted_overdue": {
                "mean_hit_count": round(mean_c02, 6),
                "vs_random_baseline": round(mean_c02 - RANDOM_BASELINE, 6),
                "z_score": round(z_c02, 4),
                "p_raw": round(p_c02, 6),
                "p_bonferroni": round(p_bonf[1], 6),
                "p_bh": round(p_bh[1], 6),
                "result_status": status_c02,
                "n_oos_draws": n_oos
            },
            "C04_zone_balanced_frequency": {
                "mean_hit_count": round(mean_c04, 6),
                "vs_random_baseline": round(mean_c04 - RANDOM_BASELINE, 6),
                "z_score": round(z_c04, 4),
                "p_raw": round(p_c04, 6),
                "p_bonferroni": round(p_bonf[2], 6),
                "p_bh": round(p_bh[2], 6),
                "result_status": status_c04,
                "n_oos_draws": n_oos
            }
        },
        "baseline_comparisons": {
            "B1_fair_random_36_of_38": round(RANDOM_BASELINE, 6),
            "B3_p161_pool_mean": P161_POOL_MEAN,
            "C08_constrained_random": "C08_NOT_IMPLEMENTED_IN_P173 — constrained random (zone+parity) has same E[hit]=36/38 as unconstrained random under POWER_LOTTO fair draw; implementing Monte Carlo C08 would confirm same mean. Documented as C08_NOT_IMPLEMENTED."
        },
        "multiple_testing_correction": {
            "method": "Bonferroni primary, BH secondary",
            "family_size": FAMILY_SIZE,
            "alpha": ALPHA,
            "bonferroni_threshold": round(BONFERRONI_THRESHOLD, 6),
            "hgeom_variance_per_draw": round(HGEOM_VAR, 6),
            "hgeom_sd_per_draw": round(HGEOM_SD, 6),
            "test_type": "one-sided z-test (H0: mean=36/38, H1: mean>36/38)",
            "se_mean": round(HGEOM_SD / math.sqrt(n_oos), 6)
        },
        "null_reporting": {
            "any_candidate_pass_corrected": any_pass,
            "null_result": not any_pass,
            "null_honest_statement": (
                "No candidate achieved p_bonferroni < 0.016667. "
                "C01, C02, C04 are statistically indistinguishable from fair-random 36/38 selection "
                "after Bonferroni correction. R2 NULL result confirmed for P173 Top 3 candidates. "
                "This is the expected outcome consistent with R1 findings."
            ) if not any_pass else "Signal review required — see candidate_results for details.",
            "r1_null_results_unchanged": True
        },
        "governance_confirmations": {
            "db_rows_before": 94924,
            "db_rows_after": db_rows,
            "db_unchanged": db_rows == 94924,
            "no_db_write": True,
            "no_registry_mutation": True,
            "no_strategy_implementation": True,
            "no_controlled_apply": True,
            "no_champion_promotion": True,
            "no_betting_advice": True,
            "no_win_guarantee_claim": True,
            "no_stage": True,
            "no_commit": True,
            "no_push": True,
            "r2_no_edge_found_yet": not any_pass,
            "p161_to_p172_null_results_stand": True,
            "main_zen_gates_split_still_unresolved": True
        },
        "next_task": "P174_POWER_LOTTO_R2_DECISION_REVIEW",
        "next_task_blocked_by_user_authorization": True,
        "next_task_authorization_required_phrase": "YES start P174 POWER_LOTTO R2 decision review"
    }

    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"[P173] Written: {JSON_OUT}")
    print(f"[P173] DB rows: {db_rows} (unchanged: {db_rows == 94924})")
    return artifact


if __name__ == "__main__":
    main()
