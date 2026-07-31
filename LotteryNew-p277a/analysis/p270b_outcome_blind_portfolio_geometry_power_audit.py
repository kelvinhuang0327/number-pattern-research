#!/usr/bin/env python3
"""P270B — Outcome-blind portfolio geometry & power audit.

Read-only, outcome-blind audit of the cross-strategy fixed-N (N=3) ticket
pool geometry in `strategy_prediction_replays`, used to decide whether
Direction A (P270A) has enough geometry/power headroom to proceed to a
P270C backtest design.

CONTRACT (binding, see outputs/research/p270a_* and 00-Plan/roadmap):
  - Reads ONLY: lottery_type, target_draw, strategy_id, bet_index,
    predicted_numbers, history_cutoff_draw, replay_status.
  - NEVER reads: actual_numbers, hit_count, special_hit, or any other
    outcome/derived-outcome column.
  - No DB write. No registry mutation. No backtest. No strategy generation.
  - No hit-rate-improvement claim.
"""

from __future__ import annotations

import itertools
import json
import math
import sqlite3
import statistics
import subprocess
from collections import defaultdict
from datetime import datetime, timezone

DB_PATH = "lottery_api/data/lottery_v2.db"

# --- Outcome-blind data access contract -------------------------------------------------

ALLOWED_COLUMNS = (
    "lottery_type",
    "target_draw",
    "strategy_id",
    "bet_index",
    "predicted_numbers",
    "history_cutoff_draw",
    "replay_status",
)

FORBIDDEN_COLUMNS = (
    "actual_numbers",
    "hit_count",
    "special_hit",
    "predicted_special",
    "actual_special",
    "hit_numbers",
    "controlled_apply_id",
    "truth_level",
)

QUERY = f"""
SELECT {", ".join(ALLOWED_COLUMNS)}
FROM strategy_prediction_replays
WHERE replay_status = 'PREDICTED'
"""

# Static guard: assert no forbidden/outcome column token appears anywhere in the
# SQL text issued against the database. This is the "outcome-forbidden guard"
# required by the P270B governance contract.
for _col in FORBIDDEN_COLUMNS:
    assert _col not in QUERY, f"OUTCOME COLUMN '{_col}' DETECTED IN QUERY — ABORTING"
for _col in ALLOWED_COLUMNS:
    assert _col in QUERY, f"required column '{_col}' missing from query"

# --- Pre-registered constants (P270A binding conclusions) -------------------------------

N = 3
MIN_POOL = 5
ALPHA = 0.0167  # Bonferroni-corrected, family m=3 (one primary test per lottery)
POWER = 0.80
PRIMARY_WINDOW_N = 1000

# P267C exact-hypergeometric 1-bet M3+ baselines (theoretical combinatorial
# constants published in p267c_m3plus_strategy_revalidation_20260610.md;
# these are NOT outcome data — they are closed-form draw-probability constants
# of the lottery number space, independent of any replayed draw result).
THEORETICAL_1BET_M3PLUS_PROB = {
    "DAILY_539": 0.010041,
    "BIG_LOTTO": 0.018638,
    "POWER_LOTTO": 0.038698,
}

# P267C best uncorrected per-lottery single-cell M3+ excess (pp), used as the
# kill-criterion comparator (P270A binding).
P267C_BEST_UNCORRECTED_EXCESS_PP = {
    "DAILY_539": 1.32,
    "BIG_LOTTO": 1.23,
    "POWER_LOTTO": 1.48,
}

# z-scores for two-sided alpha=0.0167 (alpha/2=0.00835) and power=0.80.
# Hardcoded standard-normal quantiles to avoid a scipy dependency.
Z_ALPHA_2 = 2.3934
Z_BETA = 0.8416
Z_SUM = Z_ALPHA_2 + Z_BETA


def git_head() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=".", text=True
        ).strip()
    except Exception:
        return "UNKNOWN"


def git_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "branch", "--show-current"], cwd=".", text=True
        ).strip()
    except Exception:
        return "UNKNOWN"


def load_rows():
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    try:
        cur = conn.execute(QUERY)
        rows = cur.fetchall()
        # Assert the cursor description matches exactly the allowed columns
        # (defense in depth against schema drift silently adding outcome cols).
        cols = tuple(d[0] for d in cur.description)
        assert cols == ALLOWED_COLUMNS, f"unexpected column set returned: {cols}"
        return rows
    finally:
        conn.close()


def build_pools(rows):
    """Return pools[lottery][draw] = set of dedup ticket tuples (sorted main numbers).

    Also returns causality records, and the strategy/bet_index roster.
    """
    pools = defaultdict(lambda: defaultdict(set))
    cutoffs = []  # (lottery, draw, history_cutoff_draw)
    roster_bet_index = defaultdict(lambda: defaultdict(set))  # roster[lottery][strategy_id] = {bet_index,...}
    roster_row_count = defaultdict(int)  # (lottery, strategy_id, bet_index) -> row count

    for lottery, draw, strategy_id, bet_index, predicted_numbers, cutoff, status in rows:
        assert status == "PREDICTED"
        nums = tuple(sorted(json.loads(predicted_numbers)))
        pools[lottery][draw].add(nums)
        cutoffs.append((lottery, draw, cutoff))
        roster_bet_index[lottery][strategy_id].add(bet_index)
        roster_row_count[(lottery, strategy_id, bet_index)] += 1

    return pools, cutoffs, roster_bet_index, roster_row_count


def causality_check(cutoffs):
    violations = []
    checked = 0
    for lottery, draw, cutoff in cutoffs:
        if cutoff is None:
            continue
        checked += 1
        try:
            if int(cutoff) >= int(draw):
                violations.append({"lottery_type": lottery, "target_draw": draw, "history_cutoff_draw": cutoff})
        except ValueError:
            violations.append({"lottery_type": lottery, "target_draw": draw, "history_cutoff_draw": cutoff,
                                "reason": "non-integer draw/cutoff"})
    return {
        "rows_checked": checked,
        "violations_found": len(violations),
        "violations": violations[:20],  # cap for artifact size
        "expected": "zero violations",
        "result": "PASS" if not violations else "FAIL",
    }


# --- Geometry helpers ---------------------------------------------------------------------

_TRIPLE_CACHE: dict = {}


def ticket_triples(ticket: tuple) -> frozenset:
    cached = _TRIPLE_CACHE.get(ticket)
    if cached is None:
        cached = frozenset(itertools.combinations(sorted(ticket), 3))
        _TRIPLE_CACHE[ticket] = cached
    return cached


def coverage(tickets: tuple) -> int:
    """T(S): number of distinct 3-number triples covered by union of tickets."""
    union = set()
    for t in tickets:
        union |= ticket_triples(t)
    return len(union)


def jaccard_distance(a: tuple, b: tuple) -> float:
    sa, sb = set(a), set(b)
    union = sa | sb
    if not union:
        return 0.0
    inter = sa & sb
    return 1.0 - (len(inter) / len(union))


def select_g_d(pool_list: list) -> tuple:
    """Outcome-independent triple-coverage-maximal portfolio.

    Tie-break:
      (a) maximize the minimum pairwise Jaccard distance among selected tickets
      (b) lexicographic order of the sorted ticket-tuple combo
    """
    best_t = -1
    candidates = []
    for combo in itertools.combinations(pool_list, N):
        t = coverage(combo)
        if t > best_t:
            best_t = t
            candidates = [combo]
        elif t == best_t:
            candidates.append(combo)

    def tie_key(combo):
        pairs = itertools.combinations(combo, 2)
        min_jacc_dist = min(jaccard_distance(a, b) for a, b in pairs)
        # maximize min_jacc_dist -> negate for ascending sort;
        # lexicographic tiebreak on sorted combo (ascending, smallest wins)
        sorted_combo = tuple(sorted(combo))
        return (-min_jacc_dist, sorted_combo)

    candidates.sort(key=tie_key)
    return candidates[0], best_t


# --- Per-lottery analysis -------------------------------------------------------------------

def analyze_lottery(lottery: str, draw_pools: dict):
    """draw_pools: {target_draw(str): set(ticket tuples)}"""
    draws_sorted = sorted(draw_pools.keys(), key=lambda d: int(d))

    pool_sizes = {d: len(draw_pools[d]) for d in draws_sorted}
    eligible_draws = [d for d in draws_sorted if pool_sizes[d] >= MIN_POOL]
    ineligible_draws = [d for d in draws_sorted if pool_sizes[d] < MIN_POOL]

    # pool-size histogram
    hist = defaultdict(int)
    for d in draws_sorted:
        hist[pool_sizes[d]] += 1
    pool_size_histogram = dict(sorted(hist.items()))

    # time trend: split ascending draws into thirds
    n_draws = len(draws_sorted)
    third = max(1, n_draws // 3)
    segments = {
        "early": draws_sorted[:third],
        "mid": draws_sorted[third:2 * third],
        "late": draws_sorted[2 * third:],
    }
    time_trend = {}
    for seg_name, seg_draws in segments.items():
        sizes = [pool_sizes[d] for d in seg_draws]
        time_trend[seg_name] = {
            "n_draws": len(seg_draws),
            "mean_pool_size": round(statistics.mean(sizes), 3) if sizes else None,
            "min_pool_size": min(sizes) if sizes else None,
            "max_pool_size": max(sizes) if sizes else None,
            "draw_range": [seg_draws[0], seg_draws[-1]] if seg_draws else None,
        }

    # early thin-pool boundary: longest *prefix* (from earliest draw) of
    # consecutive ineligible draws
    boundary_count = 0
    for d in draws_sorted:
        if pool_sizes[d] < MIN_POOL:
            boundary_count += 1
        else:
            break

    # --- coverage band, G_d, pairwise overlap (per eligible draw) ---
    coverage_band_per_draw = []
    g_d_records = []
    overlap_jaccards = []
    overlap_shared_counts = []

    # discordance bound accumulators
    p_ticket = THEORETICAL_1BET_M3PLUS_PROB[lottery]
    discordance_bounds_per_draw_mean = []
    discordance_bounds_per_draw_max = []  # sym_diff=6 case (fully disjoint alt portfolio)
    discordance_bounds_per_draw_min = []  # sym_diff=2 case (closest alt portfolio)

    n_portfolios_total = 0

    for d in eligible_draws:
        pool_list = sorted(draw_pools[d])  # deterministic order
        n_pool = len(pool_list)

        # pairwise overlap within pool
        for a, b in itertools.combinations(pool_list, 2):
            sa, sb = set(a), set(b)
            shared = len(sa & sb)
            union = len(sa | sb)
            jacc = shared / union if union else 0.0
            overlap_shared_counts.append(shared)
            overlap_jaccards.append(jacc)

        # all size-N portfolios and their coverage
        combos = list(itertools.combinations(pool_list, N))
        n_portfolios_total += len(combos)
        t_values = [coverage(c) for c in combos]

        coverage_band_per_draw.append({
            "target_draw": d,
            "pool_size": n_pool,
            "n_portfolios": len(combos),
            "min_T": min(t_values),
            "median_T": statistics.median(t_values),
            "mean_T": round(statistics.mean(t_values), 4),
            "max_T": max(t_values),
        })

        g_d, t_gd = select_g_d(pool_list)
        g_d_records.append({
            "target_draw": d,
            "T_Gd": t_gd,
            "min_T": min(t_values),
            "median_T": statistics.median(t_values),
            "Gd_minus_median": round(t_gd - statistics.median(t_values), 4),
            "Gd_minus_min": t_gd - min(t_values),
        })

        # Discordance bound: for every alternative combo S != G_d, sym diff
        # in ticket-set membership vs G_d is in {2,4,6} (3 - shared_tickets)*2.
        g_d_set = set(g_d)
        sym_diffs = []
        for c in combos:
            if c == g_d:
                continue
            shared_tickets = len(g_d_set & set(c))
            sym_diff = 2 * (N - shared_tickets)
            sym_diffs.append(sym_diff)

        if sym_diffs:
            mean_sym_diff = statistics.mean(sym_diffs)
            max_sym_diff = max(sym_diffs)
            min_sym_diff = min(sym_diffs)
        else:
            # only one portfolio possible (pool_size == N); no alternative exists
            mean_sym_diff = 0
            max_sym_diff = 0
            min_sym_diff = 0

        discordance_bounds_per_draw_mean.append(mean_sym_diff * p_ticket)
        discordance_bounds_per_draw_max.append(max_sym_diff * p_ticket)
        discordance_bounds_per_draw_min.append(min_sym_diff * p_ticket)

    # roster summary computed by caller (needs full roster dict)

    def _agg(values):
        if not values:
            return None
        return {
            "mean": round(statistics.mean(values), 6),
            "median": round(statistics.median(values), 6),
            "min": round(min(values), 6),
            "max": round(max(values), 6),
        }

    pi_disc_mean = statistics.mean(discordance_bounds_per_draw_mean) if discordance_bounds_per_draw_mean else 0.0
    pi_disc_best_case = statistics.mean(discordance_bounds_per_draw_max) if discordance_bounds_per_draw_max else 0.0
    pi_disc_worst_case = statistics.mean(discordance_bounds_per_draw_min) if discordance_bounds_per_draw_min else 0.0

    def mde_from_pi(pi_disc):
        if pi_disc <= 0:
            return None, None
        n_disc = PRIMARY_WINDOW_N * pi_disc
        if n_disc <= 0:
            return None, None
        delta_split = Z_SUM / math.sqrt(n_disc)
        mde_pp = pi_disc * delta_split * 100.0
        required_split = 0.5 + delta_split / 2.0
        return round(mde_pp, 4), round(required_split, 4)

    mde_central_pp, required_split_central = mde_from_pi(pi_disc_mean)
    mde_best_case_pp, required_split_best = mde_from_pi(pi_disc_best_case)
    mde_worst_case_pp, required_split_worst = mde_from_pi(pi_disc_worst_case)

    return {
        "lottery_type": lottery,
        "n_draws_total": n_draws,
        "n_eligible_draws": len(eligible_draws),
        "n_ineligible_draws": len(ineligible_draws),
        "ineligible_draw_examples": ineligible_draws[:10],
        "pool_size_histogram": pool_size_histogram,
        "pool_size_time_trend": time_trend,
        "early_thin_pool_boundary_consecutive_ineligible_from_start": boundary_count,
        "pairwise_overlap_summary": {
            "shared_number_count": _agg(overlap_shared_counts),
            "jaccard_similarity": _agg(overlap_jaccards),
        },
        "coverage_band_summary": {
            "n_portfolios_total": n_portfolios_total,
            "min_T_overall": _agg([r["min_T"] for r in coverage_band_per_draw]),
            "median_T_overall": _agg([r["median_T"] for r in coverage_band_per_draw]),
            "mean_T_overall": _agg([r["mean_T"] for r in coverage_band_per_draw]),
            "max_T_overall": _agg([r["max_T"] for r in coverage_band_per_draw]),
        },
        "g_d_enumeration_summary": {
            "n_draws": len(g_d_records),
            "T_Gd_stats": _agg([r["T_Gd"] for r in g_d_records]),
            "Gd_minus_median_stats": _agg([r["Gd_minus_median"] for r in g_d_records]),
            "Gd_minus_min_stats": _agg([r["Gd_minus_min"] for r in g_d_records]),
        },
        "projected_discordance": {
            "method": "union-bound on theoretical 1-bet M3+ probability times ticket-set "
                      "symmetric-difference size between G_d and every alternative "
                      "size-3 portfolio in the pool (per-draw mean / max / min sym-diff "
                      "case, averaged over eligible draws). rule-R cannot be computed "
                      "without outcome history.",
            "p_ticket_theoretical_1bet_M3plus": p_ticket,
            "pi_disc_central_meanSymDiff": round(pi_disc_mean, 6),
            "pi_disc_best_case_maxSymDiff6": round(pi_disc_best_case, 6),
            "pi_disc_worst_case_minSymDiff2": round(pi_disc_worst_case, 6),
            "rule_R_exact": "NOT_RUN_OUTCOME_FORBIDDEN",
        },
        "mde_summary": {
            "n": PRIMARY_WINDOW_N,
            "alpha": ALPHA,
            "power": POWER,
            "z_alpha_2": Z_ALPHA_2,
            "z_beta": Z_BETA,
            "mde_increment_pp_central": mde_central_pp,
            "mde_increment_pp_best_case": mde_best_case_pp,
            "mde_increment_pp_worst_case": mde_worst_case_pp,
            "required_discordant_split_central": required_split_central,
            "required_discordant_split_best_case": required_split_best,
            "required_discordant_split_worst_case": required_split_worst,
            "p267c_best_uncorrected_excess_pp": P267C_BEST_UNCORRECTED_EXCESS_PP[lottery],
        },
    }


def roster_summary(lottery, roster_bet_index, roster_row_count):
    strategy_ids = sorted(roster_bet_index[lottery].keys())
    cells = []
    bet_index_only_1 = []
    for sid in strategy_ids:
        for bidx in sorted(roster_bet_index[lottery][sid]):
            row_count = roster_row_count[(lottery, sid, bidx)]
            cells.append({"strategy_id": sid, "bet_index": bidx, "row_count": row_count})
        if roster_bet_index[lottery][sid] == {1}:
            bet_index_only_1.append(sid)
    return {
        "n_distinct_strategy_id": len(strategy_ids),
        "n_distinct_strategy_bet_index_cells": len(cells),
        "cells_with_observed_rows": len(cells),
        "strategies_with_only_bet_index_1": bet_index_only_1,
        "n_strategies_with_only_bet_index_1": len(bet_index_only_1),
    }


def main():
    generated_at = datetime.now(timezone.utc).isoformat()
    repo_head = git_head()
    branch = git_branch()

    rows = load_rows()
    pools, cutoffs, roster_bet_index, roster_row_count = build_pools(rows)

    causality = causality_check(cutoffs)

    lotteries = sorted(pools.keys())
    lottery_results = {}
    for lottery in lotteries:
        result = analyze_lottery(lottery, pools[lottery])
        result["pool_membership_roster"] = roster_summary(lottery, roster_bet_index, roster_row_count)
        lottery_results[lottery] = result

    # --- kill criterion (binding, P270A) -----------------------------------------------
    # Use the BEST-CASE (most favorable to GO, i.e. smallest MDE / largest discordance
    # bound via sym_diff=6) MDE per lottery as the comparator, to give Direction A the
    # most generous possible reading before declaring NO_GO.
    criterion_1_per_lottery = {}
    criterion_2_per_lottery = {}
    for lottery in lotteries:
        r = lottery_results[lottery]
        mde_best = r["mde_summary"]["mde_increment_pp_best_case"]
        excess = P267C_BEST_UNCORRECTED_EXCESS_PP[lottery]
        criterion_1_per_lottery[lottery] = {
            "mde_increment_pp_best_case": mde_best,
            "p267c_best_uncorrected_excess_pp": excess,
            "mde_exceeds_excess": (mde_best is not None and mde_best > excess),
        }
        pi_disc_best = r["projected_discordance"]["pi_disc_best_case_maxSymDiff6"]
        criterion_2_per_lottery[lottery] = {
            "pi_disc_best_case": pi_disc_best,
            "below_1pct": pi_disc_best < 0.01,
        }

    criterion_1_triggered_all = all(
        v["mde_exceeds_excess"] for v in criterion_1_per_lottery.values()
    )
    criterion_2_triggered_any = any(
        v["below_1pct"] for v in criterion_2_per_lottery.values()
    )

    kill_criterion_result = {
        "criterion_1_mde_exceeds_p267c_excess_in_all_lotteries": {
            "triggered": criterion_1_triggered_all,
            "per_lottery": criterion_1_per_lottery,
        },
        "criterion_2_projected_discordance_below_1pct_degenerate": {
            "triggered_any_lottery": criterion_2_triggered_any,
            "per_lottery": criterion_2_per_lottery,
        },
        "kill_triggered": bool(criterion_1_triggered_all or criterion_2_triggered_any),
    }

    if causality["result"] != "PASS":
        final_classification = "P270B_BLOCKED_SCHEMA_MISMATCH"
    elif kill_criterion_result["kill_triggered"]:
        final_classification = "P270B_GEOMETRY_POWER_INSUFFICIENT_NO_GO"
    else:
        final_classification = "P270B_GEOMETRY_POWER_SUFFICIENT_GO_DESIGN"

    artifact = {
        "task_id": "P270B_OUTCOME_BLIND_PORTFOLIO_GEOMETRY_POWER_AUDIT",
        "generated_at": generated_at,
        "repo_head": repo_head,
        "branch": branch,
        "mode": "outcome_blind_geometry_power_audit",
        "outcome_columns_read": False,
        "db_write": False,
        "registry_write": False,
        "strategy_generated": False,
        "backtest_run": False,
        "n_fixed": N,
        "min_pool_size": MIN_POOL,
        "lotteries_analyzed": lotteries,
        "eligible_draw_counts": {l: lottery_results[l]["n_eligible_draws"] for l in lotteries},
        "ineligible_draw_counts": {l: lottery_results[l]["n_ineligible_draws"] for l in lotteries},
        "pool_size_histograms": {l: lottery_results[l]["pool_size_histogram"] for l in lotteries},
        "pool_size_time_trends": {l: lottery_results[l]["pool_size_time_trend"] for l in lotteries},
        "early_thin_pool_boundary": {
            l: lottery_results[l]["early_thin_pool_boundary_consecutive_ineligible_from_start"]
            for l in lotteries
        },
        "pairwise_overlap_summary": {l: lottery_results[l]["pairwise_overlap_summary"] for l in lotteries},
        "coverage_band_summary": {l: lottery_results[l]["coverage_band_summary"] for l in lotteries},
        "g_d_enumeration_summary": {l: lottery_results[l]["g_d_enumeration_summary"] for l in lotteries},
        "pool_membership_roster": {l: lottery_results[l]["pool_membership_roster"] for l in lotteries},
        "causality_check": causality,
        "projected_discordance_summary": {l: lottery_results[l]["projected_discordance"] for l in lotteries},
        "mde_summary": {l: lottery_results[l]["mde_summary"] for l in lotteries},
        "kill_criterion_result": kill_criterion_result,
        "final_classification": final_classification,
        "limitations": [
            "Outcome-blind by construction: actual_numbers, hit_count, special_hit, and "
            "all derived outcome fields were never read or loaded.",
            "rule-R (trailing per-strategy M3+ rate selector) cannot be computed without "
            "outcome history; reported as NOT_RUN_OUTCOME_FORBIDDEN in projected_discordance.",
            "Discordance bounds use a union-bound on the THEORETICAL (closed-form "
            "hypergeometric) 1-bet M3+ probability per lottery, not an empirical estimate; "
            "they ignore positive correlation between tickets sharing numbers, which would "
            "tend to make the true discordance probability lower (i.e. MDE higher) than "
            "the union bound suggests. The bound is therefore optimistic for Direction A.",
            "Best-case (sym_diff=6, fully-disjoint alternative portfolio) was used for the "
            "kill-criterion comparison to give Direction A the most favorable possible "
            "reading; even this optimistic bound is reported in mde_summary alongside the "
            "central and worst-case estimates.",
            "G_d tie-breaking (max-min pairwise Jaccard distance, then lexicographic order) "
            "is deterministic and outcome-independent.",
            "No claim of hit-rate improvement, no betting action, no strategy is implied "
            "or generated by this artifact.",
        ],
    }

    md = render_markdown(artifact, lottery_results)

    with open(
        "outputs/research/p270b_outcome_blind_portfolio_geometry_power_audit_20260611.json",
        "w", encoding="utf-8",
    ) as f:
        json.dump(artifact, f, ensure_ascii=False, indent=2)

    with open(
        "outputs/research/p270b_outcome_blind_portfolio_geometry_power_audit_20260611.md",
        "w", encoding="utf-8",
    ) as f:
        f.write(md)

    print(f"final_classification = {final_classification}")


def render_markdown(artifact, lottery_results) -> str:
    lines = []
    a = artifact
    lines.append("# P270B — Outcome-Blind Portfolio Geometry & Power Audit\n")
    lines.append(f"Generated: {a['generated_at']}  |  repo_head: `{a['repo_head']}`  |  branch: `{a['branch']}`\n")
    lines.append("## Outcome-Blind Contract\n")
    lines.append("- This audit is **outcome-blind**: `actual_numbers`, `hit_count`, "
                  "`special_hit`, and all derived outcome columns were **never read or loaded**.")
    lines.append("- **No backtest was run.**")
    lines.append("- **No DB write happened.**")
    lines.append("- **No registry mutation happened.**")
    lines.append("- **No strategy was generated.**")
    lines.append("- **No hit-rate improvement is claimed.**\n")

    lines.append("## Pre-Registered Parameters\n")
    lines.append(f"- N (fixed) = {a['n_fixed']}")
    lines.append(f"- Eligibility: pool size |P_d| >= {a['min_pool_size']}")
    lines.append(f"- Primary window n = {PRIMARY_WINDOW_N}, alpha = {ALPHA} (Bonferroni, m=3), power = {POWER}")
    lines.append("- Kill criterion 1: best-case MDE-increment exceeds the largest P267C "
                  "uncorrected per-lottery single-cell excess in ALL three lotteries "
                  f"({P267C_BEST_UNCORRECTED_EXCESS_PP})")
    lines.append("- Kill criterion 2: best-case projected discordance < 1% in any lottery "
                  "(degenerate / untestable)\n")

    lines.append("## Per-Lottery Summary\n")
    for lottery in a["lotteries_analyzed"]:
        r = lottery_results[lottery]
        lines.append(f"### {lottery}\n")
        lines.append(f"- Eligible draws (|P_d|>={a['min_pool_size']}): {r['n_eligible_draws']} "
                      f"/ {r['n_draws_total']} (ineligible: {r['n_ineligible_draws']}, "
                      f"leading-prefix ineligible run: {r['early_thin_pool_boundary_consecutive_ineligible_from_start']})")
        cb = r["coverage_band_summary"]
        lines.append(f"- Coverage band T(S): min(mean)={cb['min_T_overall']['mean']}, "
                      f"median(mean)={cb['median_T_overall']['mean']}, "
                      f"max(mean)={cb['max_T_overall']['mean']}, "
                      f"portfolios enumerated={cb['n_portfolios_total']}")
        gd = r["g_d_enumeration_summary"]
        lines.append(f"- G_d coverage T(G_d): mean={gd['T_Gd_stats']['mean']}; "
                      f"G_d - median(mean)={gd['Gd_minus_median_stats']['mean']}")
        ov = r["pairwise_overlap_summary"]
        lines.append(f"- Pairwise ticket overlap: mean Jaccard similarity="
                      f"{ov['jaccard_similarity']['mean']}, mean shared-number count="
                      f"{ov['shared_number_count']['mean']}")
        pd_ = r["projected_discordance"]
        lines.append(f"- Projected discordance (union bound, p_ticket={pd_['p_ticket_theoretical_1bet_M3plus']}): "
                      f"central={pd_['pi_disc_central_meanSymDiff']}, "
                      f"best-case={pd_['pi_disc_best_case_maxSymDiff6']}, "
                      f"worst-case={pd_['pi_disc_worst_case_minSymDiff2']}; "
                      f"rule-R = {pd_['rule_R_exact']}")
        mde = r["mde_summary"]
        lines.append(f"- MDE-increment (n={mde['n']}, alpha={mde['alpha']}, power={mde['power']}): "
                      f"central={mde['mde_increment_pp_central']}pp, "
                      f"best-case={mde['mde_increment_pp_best_case']}pp, "
                      f"worst-case={mde['mde_increment_pp_worst_case']}pp "
                      f"vs P267C uncorrected excess={mde['p267c_best_uncorrected_excess_pp']}pp")
        roster = r["pool_membership_roster"]
        lines.append(f"- Roster: {roster['n_distinct_strategy_id']} strategies, "
                      f"{roster['n_distinct_strategy_bet_index_cells']} (strategy,bet_index) cells, "
                      f"{roster['n_strategies_with_only_bet_index_1']} strategies with only bet_index=1")
        lines.append("")

    lines.append("## Causality Check\n")
    cc = a["causality_check"]
    lines.append(f"- rows checked: {cc['rows_checked']}, violations found: {cc['violations_found']}, "
                  f"result: **{cc['result']}**\n")

    lines.append("## Kill Criterion Result\n")
    kc = a["kill_criterion_result"]
    lines.append("### Criterion 1 — best-case MDE exceeds P267C uncorrected excess in ALL lotteries\n")
    lines.append(f"Triggered: **{kc['criterion_1_mde_exceeds_p267c_excess_in_all_lotteries']['triggered']}**\n")
    for lottery, v in kc["criterion_1_mde_exceeds_p267c_excess_in_all_lotteries"]["per_lottery"].items():
        lines.append(f"- {lottery}: MDE_best={v['mde_increment_pp_best_case']}pp vs "
                      f"P267C excess={v['p267c_best_uncorrected_excess_pp']}pp -> "
                      f"exceeds={v['mde_exceeds_excess']}")
    lines.append("")
    lines.append("### Criterion 2 — best-case projected discordance < 1% (degenerate) in any lottery\n")
    lines.append(f"Triggered (any): **{kc['criterion_2_projected_discordance_below_1pct_degenerate']['triggered_any_lottery']}**\n")
    for lottery, v in kc["criterion_2_projected_discordance_below_1pct_degenerate"]["per_lottery"].items():
        lines.append(f"- {lottery}: pi_disc_best_case={v['pi_disc_best_case']} -> below_1pct={v['below_1pct']}")
    lines.append("")

    lines.append("## Final Classification\n")
    lines.append(f"`{a['final_classification']}`\n")

    if a["final_classification"] == "P270B_GEOMETRY_POWER_SUFFICIENT_GO_DESIGN":
        lines.append("**P270C is ALLOWED**, conditional on user authorization and registration "
                      "of H-P270-1 in `hypothesis_registry.jsonl` (not performed in this task).\n")
    else:
        lines.append("**P270C is NOT allowed.** Direction A (cross-strategy fixed-N M3+ portfolio) "
                      "closes per the pre-registered kill criterion. State set to HOLD pending "
                      "user authorization for any next direction.\n")

    lines.append("## Limitations\n")
    for lim in a["limitations"]:
        lines.append(f"- {lim}")
    lines.append("")

    lines.append("## Disclaimers\n")
    lines.append("- This report does not improve win rate and does not authorize betting action.")
    lines.append("- 本報告為幾何/檢定力審計，不構成投注建議，不保證任何中獎結果。")
    lines.append("- No DB write, no registry mutation, no strategy generation occurred in this task.")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
