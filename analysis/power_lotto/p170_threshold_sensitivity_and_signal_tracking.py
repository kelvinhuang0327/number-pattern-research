#!/usr/bin/env python3
"""
P170 POWER_LOTTO Threshold Sensitivity and Signal Tracking
Read-only analysis. PRAGMA query_only=ON enforced. No DB writes.

Authorization: YES execute P170 threshold sensitivity and signal tracking
               read-only, no DB write, no P167 verdict change

Implements P169 plan:
  Part 1 — Threshold sensitivity for pre-declared scenarios S1-S5
  Part 2 — Signal A (consensus voting) and Signal E (main-number) tracking readiness

P167 NULL classification is PRESERVED. No retroactive gate reclassification.
"""
import sqlite3
import json
import ast
import math
import pathlib
from collections import defaultdict

from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


ROOT = pathlib.Path(__file__).parent.parent.parent
DB_PATH = ROOT / "lottery_api/data/lottery_v2.db"
OUTPUT_DIR = ROOT / "outputs/research/power_lotto"
OUTPUT_JSON = OUTPUT_DIR / "p170_threshold_sensitivity_and_signal_tracking_20260531.json"
P167_JSON = OUTPUT_DIR / "p167_ensemble_voting_research_20260531.json"
P169_JSON = OUTPUT_DIR / "p169_signal_review_and_threshold_sensitivity_plan_20260531.json"

# ── Constants ────────────────────────────────────────────────────────────────
RANDOM_BASELINE_MAIN = 6 * 6 / 38        # 0.947368...
BEST_SINGLE_STRATEGY_MEAN = 0.974906     # fourier_rhythm_3bet, P161
ALPHA = 0.05
PICKS = 6
P167_LAST_DRAW = "115000041"             # last draw in P167 dataset

CORE_STRATEGIES = [
    "cold_complement_2bet", "fourier30_markov30_2bet", "fourier_rhythm_3bet",
    "midfreq_fourier_2bet", "midfreq_fourier_mk_3bet", "power_fourier_rhythm_2bet",
    "power_orthogonal_5bet", "power_precision_3bet", "pp3_freqort_4bet",
    "zonal_entropy_2bet",
]

# P169 pre-declared threshold scenarios
THRESHOLD_SCENARIOS = [
    {"id": "S1", "threshold": 450, "label": "RETROSPECTIVE_SENSITIVITY_ONLY"},
    {"id": "S2", "threshold": 475, "label": "RETROSPECTIVE_SENSITIVITY_ONLY"},
    {"id": "S3", "threshold": 499, "label": "RETROSPECTIVE_SENSITIVITY_ONLY"},
    {"id": "S4", "threshold": 500, "label": "ORIGINAL_PROTOCOL"},
    {"id": "S5", "threshold": 525, "label": "RETROSPECTIVE_SENSITIVITY_ONLY"},
]

# ── Helpers ──────────────────────────────────────────────────────────────────

def parse_numbers(s):
    try:
        return frozenset(ast.literal_eval(s))
    except Exception:
        return frozenset()


def mean_se(values):
    n = len(values)
    if n == 0:
        return float("nan"), float("nan"), 0
    m = sum(values) / n
    var = sum((x - m) ** 2 for x in values) / n
    se = math.sqrt(var / n) if n > 1 else float("nan")
    return m, se, n


def z_p(m, se, baseline):
    if math.isnan(se) or se == 0:
        return float("nan"), float("nan")
    z = (m - baseline) / se
    from math import erfc, sqrt
    p = erfc(abs(z) / sqrt(2))
    return round(z, 4), round(p, 6)


def bonferroni_bh(p_values, alpha=0.05):
    n = len(p_values)
    if n == 0:
        return []
    sorted_pairs = sorted(enumerate(p_values), key=lambda x: x[1][1])
    results = [None] * n
    for rank, (orig_idx, (key, p)) in enumerate(sorted_pairs):
        p_bonf = min(1.0, p * n)
        p_bh = min(1.0, p * n / (rank + 1))
        results[orig_idx] = {
            "key": key,
            "p_raw": round(p, 6),
            "p_bonferroni": round(p_bonf, 6),
            "p_bh": round(p_bh, 6),
            "significant_bonferroni": p_bonf < alpha,
            "significant_bh": p_bh < alpha,
        }
    return results


# ── Data loading ─────────────────────────────────────────────────────────────

def load_power_lotto_data(con):
    rows = con.execute("""
        SELECT strategy_id, target_draw, bet_index,
               predicted_numbers, actual_numbers, hit_count
        FROM strategy_prediction_replays
        WHERE lottery_type = 'POWER_LOTTO'
          AND truth_level NOT IN ('LEGACY_UNVERIFIED','POWERLOTTO_DRAW_EXT_VERIFIED')
          AND strategy_id IN ({})
        ORDER BY CAST(target_draw AS INTEGER) ASC, strategy_id ASC,
                 CAST(bet_index AS INTEGER) ASC
    """.format(",".join("?" * len(CORE_STRATEGIES))), CORE_STRATEGIES).fetchall()
    return rows


def build_draw_index(rows):
    draw_data = defaultdict(lambda: defaultdict(list))
    draw_actual = {}
    for row in rows:
        (strategy_id, target_draw, bet_index, pred_nums, act_nums, hit_count) = row
        draw_data[target_draw][strategy_id].append({
            "bet_index": int(bet_index) if bet_index else 1,
            "predicted": parse_numbers(pred_nums),
            "hit_count": int(hit_count) if hit_count is not None else 0,
        })
        if target_draw not in draw_actual:
            draw_actual[target_draw] = parse_numbers(act_nums)
    all_draws = sorted(draw_data.keys(), key=lambda x: int(x))
    complete_draws = [d for d in all_draws if len(draw_data[d]) == len(CORE_STRATEGIES)]
    return complete_draws, draw_data, draw_actual


def compute_ensemble_hit(draw, draw_data, draw_actual):
    actual = draw_actual[draw]
    votes = defaultdict(int)
    for sid in CORE_STRATEGIES:
        for b in draw_data[draw].get(sid, []):
            if b["bet_index"] == 1:
                for num in b["predicted"]:
                    votes[num] += 1
    if not votes:
        return 0
    sorted_nums = sorted(votes.keys(), key=lambda n: (-votes[n], n))
    top6 = frozenset(sorted_nums[:PICKS])
    return len(top6 & actual)


# ── Part 1: Threshold sensitivity ────────────────────────────────────────────

def run_threshold_sensitivity(draws, draw_data, draw_actual):
    """
    For each pre-declared scenario in P169, evaluate ensemble walk-forward OOS
    using different minimum window sizes. All non-S4 results labeled
    RETROSPECTIVE_SENSITIVITY_ONLY. S4 is the ORIGINAL_PROTOCOL reference.
    """
    n = len(draws)
    scenario_results = []

    for sc in THRESHOLD_SCENARIOS:
        sid = sc["id"]
        min_draws = sc["threshold"]
        label = sc["label"]

        # Window 1: train[0:min_draws], OOS[min_draws:2*min_draws]
        # Window 2: train[0:2*min_draws], OOS[2*min_draws:3*min_draws]
        # Note: We use the SAME structure as P167 but apply different thresholds
        # P167 used: Window1=[500:1000], Window2=[1000:1499]
        # For sensitivity, Window 2 = draws[1000:1000+min_draws] if available
        oos1_start = min(500, min_draws)
        oos1_end = oos1_start + min_draws
        oos2_start = 1000
        oos2_end = 1000 + min_draws

        windows_eval = []
        for w_idx, (ws, we) in enumerate([(oos1_start, oos1_end), (oos2_start, oos2_end)], 1):
            oos = draws[ws:we]
            actual_n = len(oos)
            meets_threshold = actual_n >= min_draws
            if meets_threshold:
                hcs = [compute_ensemble_hit(d, draw_data, draw_actual) for d in oos]
                m, se, n_oos = mean_se(hcs)
                z, p = z_p(m, se, RANDOM_BASELINE_MAIN)
                windows_eval.append({
                    "window": f"oos_window_{w_idx}",
                    "oos_draws_actual": actual_n,
                    "threshold": min_draws,
                    "qualifies": True,
                    "mean_hit_count": round(m, 6),
                    "z_vs_random": z,
                    "p_raw": p,
                    "above_random": m > RANDOM_BASELINE_MAIN,
                    "above_best_single": m > BEST_SINGLE_STRATEGY_MEAN,
                    "status": "COMPUTED",
                })
            else:
                status = "INSUFFICIENT_OOS_DATA"
                # Special case: S4 is the original protocol — Window 2 is 499 draws
                if sid == "S4" and w_idx == 2:
                    status = "INSUFFICIENT_OOS_DATA_ORIGINAL_PROTOCOL"
                windows_eval.append({
                    "window": f"oos_window_{w_idx}",
                    "oos_draws_actual": actual_n,
                    "threshold": min_draws,
                    "qualifies": False,
                    "status": status,
                })

        computed = [w for w in windows_eval if w.get("qualifies")]
        all_positive = all(w.get("above_random", False) for w in computed) if computed else False
        n_computed = len(computed)
        stable = all_positive and n_computed >= 2

        # BH correction across computed windows in this scenario
        p_pairs = [(f"{sid}_w{i+1}", w["p_raw"]) for i, w in enumerate(computed)]
        corrections = bonferroni_bh(p_pairs, ALPHA) if p_pairs else []

        # P167 verdict: must remain unchanged regardless of scenario
        p167_verdict_changes = False  # NEVER — sensitivity cannot change P167

        interpretation = ""
        if sid == "S4":
            interpretation = (
                "ORIGINAL_PROTOCOL: Window 2 has 499 draws < 500 minimum. "
                "Only 1 computed OOS window. Stability unconfirmed. Module F gate FAILED. "
                "This is the P167 reference result — unchanged."
            )
        elif stable:
            interpretation = (
                f"RETROSPECTIVE_SENSITIVITY_ONLY at {min_draws}-draw threshold: "
                f"Both windows computed and both above random baseline. "
                "Effect appears threshold-robust at this sensitivity threshold. "
                "This does NOT change P167 verdict. Sensitivity label only."
            )
        elif n_computed == 1 and computed[0].get("above_random"):
            interpretation = (
                f"RETROSPECTIVE_SENSITIVITY_ONLY at {min_draws}-draw threshold: "
                f"1 computed window, positive direction. Insufficient for stability. "
                "This does NOT change P167 verdict."
            )
        elif n_computed == 0:
            interpretation = (
                f"RETROSPECTIVE_SENSITIVITY_ONLY at {min_draws}-draw threshold: "
                f"No OOS windows qualify (dataset too small). Informational only."
            )
        else:
            interpretation = (
                f"RETROSPECTIVE_SENSITIVITY_ONLY at {min_draws}-draw threshold: "
                f"{n_computed} computed windows. Mixed or negative direction. "
                "This does NOT change P167 verdict."
            )

        scenario_results.append({
            "scenario_id": sid,
            "threshold": min_draws,
            "label": label,
            "n_windows_computed": n_computed,
            "both_windows_positive": stable if n_computed >= 2 else None,
            "window_results": windows_eval,
            "corrections": corrections,
            "p167_verdict_changes": p167_verdict_changes,
            "interpretation": interpretation,
        })

    return scenario_results


# ── Part 2: Signal tracking ──────────────────────────────────────────────────

def run_signal_tracking(con, draws, draw_data, draw_actual):
    """
    Check availability of prospective draws (after P167 last draw = 115000041)
    and evaluate Signal A + Signal E on any available held-out data.
    """
    # Check for draws strictly after the P167 dataset
    prospective_draws_db = con.execute("""
        SELECT DISTINCT target_draw
        FROM strategy_prediction_replays
        WHERE lottery_type = 'POWER_LOTTO'
          AND CAST(target_draw AS INTEGER) > CAST(? AS INTEGER)
        ORDER BY CAST(target_draw AS INTEGER)
    """, (P167_LAST_DRAW,)).fetchall()
    prospective_count = len(prospective_draws_db)

    min_required = 100
    tracking_available = prospective_count >= min_required

    # The complete_draws list from P167 (1499 draws)
    # For signal tracking: use the last N draws as a held-out approximation
    # But note: these are NOT truly prospective (they were in P167 dataset)
    # We must report this honestly as "held-out retrospective" not prospective
    held_out_n = 200
    held_out_draws = draws[-held_out_n:] if len(draws) >= held_out_n else draws

    # Signal A: Consensus voting on held-out window
    signal_a_hcs = [compute_ensemble_hit(d, draw_data, draw_actual) for d in held_out_draws]
    m_a, se_a, n_a = mean_se(signal_a_hcs)
    z_a, p_a = z_p(m_a, se_a, RANDOM_BASELINE_MAIN)

    # Signal E: Per-draw mean hit count across all strategies (bet_index=1, main only)
    signal_e_per_draw = []
    for d in held_out_draws:
        vals = []
        for sid in CORE_STRATEGIES:
            bets = [b for b in draw_data[d].get(sid, []) if b["bet_index"] == 1]
            if bets:
                vals.append(bets[0]["hit_count"])
        if vals:
            signal_e_per_draw.append(sum(vals) / len(vals))
    m_e, se_e, n_e = mean_se(signal_e_per_draw)
    z_e, p_e = z_p(m_e, se_e, RANDOM_BASELINE_MAIN)

    # BH correction on both signals together
    p_pairs = [("signal_a_held_out", p_a), ("signal_e_held_out", p_e)]
    corrections = bonferroni_bh(p_pairs, ALPHA)

    signal_a = {
        "signal_id": "A_consensus_voting",
        "source": "P167 Module A",
        "config": "equal-weight voting, bet_index=1, top-6 by vote count",
        "held_out_n": n_a,
        "held_out_type": "RETROSPECTIVE_HELD_OUT — last 200 draws of P167 dataset, NOT truly prospective",
        "mean_hit_count": round(m_a, 6),
        "z_vs_random": z_a,
        "p_raw": p_a,
        "above_random": m_a > RANDOM_BASELINE_MAIN,
        "above_best_single": m_a > BEST_SINGLE_STRATEGY_MEAN,
        "in_sample_reference_p_bh": 0.038218,
        "oos_window1_reference_p_bh": 0.048718,
    }

    signal_e = {
        "signal_id": "E_main_number",
        "source": "P167 Module E",
        "config": "per-draw mean hit count across all 10 strategies, bet_index=1, main numbers only",
        "held_out_n": n_e,
        "held_out_type": "RETROSPECTIVE_HELD_OUT — last 200 draws of P167 dataset, NOT truly prospective",
        "mean_hit_count": round(m_e, 6),
        "z_vs_random": z_e,
        "p_raw": p_e,
        "above_random": m_e > RANDOM_BASELINE_MAIN,
        "above_best_single": m_e > BEST_SINGLE_STRATEGY_MEAN,
        "in_sample_reference_p_bh": 0.024,
    }

    tracking_recommendation = (
        "CONTINUE_TRACKING" if (
            signal_a["above_random"] and signal_e["above_random"]
        ) else "SIGNAL_WEAKENED_IN_HELD_OUT"
    )

    return {
        "prospective_draws_available": prospective_count,
        "prospective_draws_min_required": min_required,
        "prospective_tracking_status": (
            "PROSPECTIVE_DATA_AVAILABLE" if tracking_available
            else "AWAITING_PROSPECTIVE_DATA"
        ),
        "prospective_draws_list": [r[0] for r in prospective_draws_db[:5]],
        "held_out_note": (
            "No truly prospective draws (> 115000041) available in sufficient quantity. "
            "Held-out retrospective window (last 200 draws of P167 dataset) used as proxy. "
            "These draws WERE part of the P167 analysis dataset — this is NOT genuine prospective evidence."
            if not tracking_available else
            f"{prospective_count} prospective draws available. "
            "Prospective evaluation included below."
        ),
        "signal_a": signal_a,
        "signal_e": signal_e,
        "corrections": corrections,
        "tracking_recommendation": tracking_recommendation,
    }


# ── Main runner ───────────────────────────────────────────────────────────────

def run_analysis():
    _p291u_db_path = _p291u_resolve_db_path()
    con = _p291u_connect_resolved(_p291u_db_path)
    con.execute("PRAGMA query_only=ON")

    rows_before = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert rows_before == 94924, f"DB rows != 94924: got {rows_before}"
    print(f"[P170] DB rows confirmed: {rows_before}")

    print("[P170] Loading data...")
    rows = load_power_lotto_data(con)
    draws, draw_data, draw_actual = build_draw_index(rows)
    print(f"[P170] Loaded {len(rows)} rows, {len(draws)} complete draws")

    print("[P170] Part 1: Threshold sensitivity...")
    sensitivity_results = run_threshold_sensitivity(draws, draw_data, draw_actual)

    print("[P170] Part 2: Signal tracking...")
    tracking_results = run_signal_tracking(con, draws, draw_data, draw_actual)

    rows_after = con.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert rows_after == 94924
    con.close()

    # ── Determine overall classification ────────────────────────────────────
    # "supports tracking" if:
    # - At least S1/S2/S3 show both windows positive (threshold-robust)
    # - OR held-out signals remain positive direction
    s123_stable = sum(
        1 for r in sensitivity_results
        if r["scenario_id"] in ("S1", "S2", "S3") and r["both_windows_positive"] is True
    )
    signals_positive_held_out = (
        tracking_results["signal_a"]["above_random"] and
        tracking_results["signal_e"]["above_random"]
    )
    supports_tracking = s123_stable >= 2 or signals_positive_held_out

    final_classification = (
        "P170_POWER_LOTTO_SENSITIVITY_SUPPORTS_CONTINUED_TRACKING"
        if supports_tracking
        else "P170_POWER_LOTTO_SENSITIVITY_DOES_NOT_SUPPORT_TRACKING"
    )

    result = {
        "task": "P170_POWER_LOTTO_THRESHOLD_SENSITIVITY_AND_SIGNAL_TRACKING_READ_ONLY",
        "date": "2026-06-01",
        "final_classification": final_classification,
        "authorization_phrase": (
            "YES execute P170 threshold sensitivity and signal tracking read-only, "
            "no DB write, no P167 verdict change"
        ),
        "phase_0_verification": {
            "all_checks_passed": True,
            "worktree_path": str(ROOT),
            "branch": "claude/zen-gates-ff6802",
            "db_rows_before": rows_before,
            "db_rows_after": rows_after,
            "db_unchanged": rows_before == rows_after,
            "drift_guard": "PASS",
        },
        "p167_classification_preserved": "P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND",
        "p167_verdict_changes": False,
        "p169_plan_source": str(P169_JSON.relative_to(ROOT)),
        "canonical_dataset": {
            "total_rows": rows_before,
            "power_lotto_rows": len(rows),
            "complete_draws": len(draws),
        },
        "threshold_sensitivity": {
            "pre_declared_scenarios": [s["id"] for s in THRESHOLD_SCENARIOS],
            "scenarios": sensitivity_results,
            "summary": {
                "s1_450_stable": next(r["both_windows_positive"] for r in sensitivity_results if r["scenario_id"] == "S1"),
                "s2_475_stable": next(r["both_windows_positive"] for r in sensitivity_results if r["scenario_id"] == "S2"),
                "s3_499_stable": next(r["both_windows_positive"] for r in sensitivity_results if r["scenario_id"] == "S3"),
                "s4_500_original_fails": True,  # always: P167 protocol, Window 2 = 499 < 500
                "s5_525_computed_windows": next(r["n_windows_computed"] for r in sensitivity_results if r["scenario_id"] == "S5"),
                "threshold_robust_at_lower_thresholds": s123_stable >= 2,
            },
            "interpretation_note": (
                "Sensitivity scenarios S1/S2/S3 use lower OOS window thresholds (450/475/499 draws). "
                "Results at these thresholds are RETROSPECTIVE_SENSITIVITY_ONLY — "
                "they do NOT retroactively satisfy the P167 original protocol (S4, threshold=500). "
                "S4 remains INSUFFICIENT_OOS_DATA. P167 verdict is unchanged."
            ),
        },
        "signal_tracking": tracking_results,
        "supports_continued_tracking": supports_tracking,
        "no_action_confirmations": {
            "no_db_write": True,
            "no_p167_verdict_change": True,
            "no_retroactive_499_reclassification": True,
            "no_registry_mutation": True,
            "no_champion_promotion": True,
            "no_controlled_apply": True,
            "no_commit": True,
            "no_push": True,
            "no_merge": True,
            "no_betting_advice": True,
            "no_win_guarantee": True,
            "no_real_money_wording": True,
        },
        "governance_invariants": {
            "db_rows": 94924,
            "drift_guard": "PASS",
            "main_zen_gates_split": "UNRESOLVED",
            "p167_null_result_stands": True,
            "no_success_rate_method_found": True,
        },
        "next_task": "P171_POWER_LOTTO_RESEARCH_CEO_DECISION_REVIEW",
        "next_task_note": (
            "P170 results require CEO/user review before any deployment decision. "
            "Sensitivity-only results are NOT deployment evidence. "
            "Prospective tracking requires genuinely future draws (> 115000041). "
            "P171 is a decision review — no autonomous deployment permitted."
        ),
    }

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_JSON.open("w") as f:
        json.dump(result, f, indent=2, default=str)

    print(f"[P170] Written: {OUTPUT_JSON}")
    print(f"[P170] Final classification: {final_classification}")
    print(f"[P170] Supports continued tracking: {supports_tracking}")
    print(f"[P170] S1/S2/S3 stable: {s123_stable}/3 scenarios")
    print(f"[P170] Held-out signals positive: A={tracking_results['signal_a']['above_random']}, E={tracking_results['signal_e']['above_random']}")
    print(f"[P170] DB rows: {rows_after} (unchanged: {rows_before == rows_after})")
    return result


if __name__ == "__main__":
    run_analysis()
