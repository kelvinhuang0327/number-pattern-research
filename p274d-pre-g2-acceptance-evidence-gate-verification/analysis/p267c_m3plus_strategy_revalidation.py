#!/usr/bin/env python3
"""
P267C — M3+ Success-Metric Strategy Revalidation
=================================================

Pre-registered re-validation of all replay-backed strategy cells under the
P265A SSOT success metric (M3+): draw-level success = any bet_index within the
same lottery/strategy/target_draw has hit_count >= 3. special_hit is NEVER
counted (P265A contract, all three lotteries).

Governance contracts honoured:
  - L138: Hypothesis Registry entry is written BEFORE any statistic is computed
    (lottery_api/engine/hypothesis_registry.py — repo-canonical append-only JSONL).
  - L96:  null = per-draw Bernoulli(p_i) Monte-Carlo (label-shuffle forbidden).
  - L132/L139: predict-vs-actual only — each prediction is scored exclusively
    against its own target draw; historical-pool max-hit is never computed.
  - L142/L143/L144: classification restricted to a fixed allowed set; any
    corrected-significant cell can only yield CANDIDATE_SIGNAL_REQUIRES_HUMAN_REVIEW.

DB access is strictly read-only (sqlite3 URI mode=ro). No DB write, no replay
mutation, no registry mutation, no production change, no betting advice.

Run:  ./venv/bin/python analysis/p267c_m3plus_strategy_revalidation.py
"""

import json
import math
import os
import sqlite3
import sys
from datetime import datetime

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ----------------------------------------------------------------------------
# Pre-registered constants (declared before any data inspection in this run)
# ----------------------------------------------------------------------------
SEED = 42
M_BASELINE = 10_000        # MC fair draws per target draw (multi-bet conditional baseline)
M_SANITY = 1_000_000       # MC draws for 1-bet exact-vs-MC convergence sanity (per lottery)
SANITY_TOL_PP = 0.05       # 1-bet MC mean must match exact baseline within +/-0.05pp
T_NULL = 10_000            # null iterations for empirical p
WINDOW_PRIMARY = 1500      # primary endpoint: most-recent 1500 distinct target_draw
WINDOWS_STABILITY = (150, 500)  # sign-check only, NOT significance gates
FAMILY_M = 36              # pre-registered primary family size (replay-backed cells)
BONFERRONI_ALPHA = 0.05 / FAMILY_M
BH_Q = 0.10
EXPECTED_REPLAY_ROWS = 94_924

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "lottery_api", "data", "lottery_v2.db")
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "outputs", "research")
STAMP = "20260610"

LOTTERY_RULES = {
    # lottery_type: (pool_size, numbers_drawn)  — main zone only; special excluded
    "DAILY_539": (39, 5),
    "BIG_LOTTO": (49, 6),
    "POWER_LOTTO": (38, 6),
}

ALLOWED_CLASSIFICATIONS = (
    "P267C_M3PLUS_REVALIDATION_COMPLETE_NO_VALIDATED_M3_EDGE",
    "P267C_M3PLUS_REVALIDATION_COMPLETE_CANDIDATE_SIGNAL_REQUIRES_HUMAN_REVIEW",
    "P267C_M3PLUS_REVALIDATION_BLOCKED_DATA_QUALITY",
)

DISCLAIMERS = [
    "本報告不構成投注建議，不保證任何中獎結果。",
    "M3+ 成功率為歷史 walk-forward replay 的描述統計，不代表未來表現。",
    "任何通過校正的訊號僅為 CANDIDATE_SIGNAL，必須經人類審查（L144），不得自動晉級。",
    "special_hit 一律不計入 M3+（P265A SSOT contract）。",
    "This report does not improve win rate and does not authorize betting action.",
]

H6_STRATEGY_ID = "h6_gate_mk20_ew85"


def open_ro():
    uri = "file:" + os.path.abspath(DB_PATH) + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def exact_one_bet_m3plus(pool: int, k: int) -> float:
    """P(>=3 main-number hits for one k-number bet) under a uniform fair draw."""
    total = math.comb(pool, k)
    return sum(math.comb(k, h) * math.comb(pool - k, k - h) for h in range(3, k + 1)) / total


# ----------------------------------------------------------------------------
# Step 0 — Hypothesis Registry pre-registration (L138; before any statistics)
# ----------------------------------------------------------------------------
def preregister():
    from lottery_api.engine import hypothesis_registry as hr

    entries = []
    thresholds = {
        "success_metric": "M3_PLUS_draw_level_any_bet_hit_count_ge_3",
        "special_hit_excluded": True,
        "primary_endpoint": "most_recent_1500_distinct_target_draw",
        "stability_windows_sign_check_only": [150, 500],
        "null": "per_draw_Bernoulli(p_i)_MC_L96",
        "baseline_multi_bet": "per_draw_conditional_MC_M=10000",
        "baseline_one_bet": "exact_hypergeometric",
        "family_m": FAMILY_M,
        "bonferroni_alpha": BONFERRONI_ALPHA,
        "bh_fdr_q": BH_Q,
        "mc_iterations": T_NULL,
        "seed": SEED,
    }
    existing = {(e.get("name"), e.get("lottery")) for e in hr.list_all()}
    plan = [
        ("p267c_m3plus_reval_primary", lot,
         "P265A M3+ 度量重驗證：既有 walk-forward replay 證據對齊使用者目標度量（非新訊號挖掘）",
         "預期 NULL（L131/L133）；任何 corrected-significant 僅 CANDIDATE_SIGNAL")
        for lot in ("DAILY_539", "BIG_LOTTO", "POWER_LOTTO")
    ] + [
        ("p267c_h6_m3plus_decomposition_conditional", "DAILY_539",
         "H6 ew85 M2-only vs M3+ 分層分解（conditional：僅當 per-draw evidence 可重現）",
         "H6 per-draw evidence 不可重現則輸出 H6_EVIDENCE_NOT_REPRODUCIBLE，不引用 wiki 摘要數字"),
    ]
    for name, lot, basis, direction in plan:
        if (name, lot) in existing:
            entries.append({"name": name, "lottery": lot, "status": "ALREADY_REGISTERED"})
            continue
        e = hr.register(
            name=name, lottery=lot, theory_basis=basis, expected_direction=direction,
            test_thresholds=thresholds, seed=SEED, n_periods=WINDOW_PRIMARY,
            notes="P267C pre-registration (HR-P267B-M3PLUS-REVAL-001); read-only revalidation; no DB write",
        )
        entries.append({"hypothesis_id": e["hypothesis_id"], "name": name, "lottery": lot,
                        "status": "REGISTERED"})
    return entries


# ----------------------------------------------------------------------------
# Step 1 — data-quality gates
# ----------------------------------------------------------------------------
def data_quality_gates(conn):
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    total_rows = cur.fetchone()[0]
    cur.execute("""SELECT COUNT(*) FROM strategy_prediction_replays
                   WHERE CAST(history_cutoff_draw AS INTEGER) >= CAST(target_draw AS INTEGER)""")
    causality = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE replay_status != 'PREDICTED'")
    non_predicted = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE dry_run != 0")
    dry = cur.fetchone()[0]
    cur.execute("""SELECT COUNT(*) FROM strategy_prediction_replays
                   WHERE predicted_numbers IS NULL OR actual_numbers IS NULL OR hit_count IS NULL""")
    nulls = cur.fetchone()[0]
    gates = {
        "total_replay_rows": total_rows,
        "expected_replay_rows": EXPECTED_REPLAY_ROWS,
        "causality_violations": causality,
        "non_predicted_rows": non_predicted,
        "dry_run_rows": dry,
        "null_field_rows": nulls,
    }
    ok = (causality == 0 and non_predicted == 0 and dry == 0 and nulls == 0
          and total_rows == EXPECTED_REPLAY_ROWS)
    return ok, gates


# ----------------------------------------------------------------------------
# Step 2 — universe construction
# ----------------------------------------------------------------------------
def build_universe(conn):
    cur = conn.cursor()
    cur.execute("""SELECT lottery_type, strategy_id, COUNT(DISTINCT target_draw), MAX(bet_index)
                   FROM strategy_prediction_replays
                   WHERE replay_status='PREDICTED'
                   GROUP BY lottery_type, strategy_id""")
    cells = [{"lottery_type": r[0], "strategy_id": r[1],
              "distinct_draws": r[2], "max_bet_index": r[3]} for r in cur.fetchall()]

    from lottery_api.models import replay_strategy_registry as reg
    meta = reg.list_strategy_lifecycle_metadata()
    registry_cells, online_ids = set(), set()
    for m in meta:
        sid = m.get("strategy_id")
        status = reg.normalise_lifecycle_status(m.get("lifecycle_status", ""))
        if status == "ONLINE":
            online_ids.add(sid)
        for lot in (m.get("supported_lottery_types") or []):
            registry_cells.add((lot, sid))
    db_cells = {(c["lottery_type"], c["strategy_id"]) for c in cells}
    no_data = sorted(registry_cells - db_cells)
    orphans = sorted(db_cells - registry_cells)
    return cells, no_data, orphans, online_ids


# ----------------------------------------------------------------------------
# Step 3 — per-cell computation
# ----------------------------------------------------------------------------
def load_cell_draws(conn, lottery, sid):
    cur = conn.cursor()
    cur.execute("""SELECT DISTINCT target_draw FROM strategy_prediction_replays
                   WHERE lottery_type=? AND strategy_id=? AND replay_status='PREDICTED'
                   ORDER BY CAST(target_draw AS INTEGER) DESC LIMIT ?""",
                (lottery, sid, WINDOW_PRIMARY))
    draws = [r[0] for r in cur.fetchall()][::-1]  # ascending
    qmarks = ",".join("?" * len(draws))
    cur.execute(f"""SELECT target_draw, bet_index, predicted_numbers, actual_numbers, hit_count
                    FROM strategy_prediction_replays
                    WHERE lottery_type=? AND strategy_id=? AND replay_status='PREDICTED'
                      AND target_draw IN ({qmarks})""",
                [lottery, sid] + draws)
    per_draw = {d: [] for d in draws}
    integrity_mismatch = 0
    for td, bi, pred, act, hc in cur.fetchall():
        p = json.loads(pred)
        a = json.loads(act)
        if len(set(p) & set(a)) != hc:
            integrity_mismatch += 1
        per_draw[td].append((bi, sorted(set(p)), hc))
    for d in per_draw:
        per_draw[d].sort(key=lambda x: x[0])
    return draws, per_draw, integrity_mismatch


def conditional_mc_baseline(bets_by_draw, pool, k, rng):
    """Per-draw P(any bet hits >=3 | uniform fair draw), conditioning on the
    actual stored bet sets for that draw. Vectorized MC, M_BASELINE draws each."""
    p_list = np.empty(len(bets_by_draw))
    for i, bets in enumerate(bets_by_draw):
        mask = np.zeros((len(bets), pool), dtype=np.float32)
        for j, b in enumerate(bets):
            mask[j, np.asarray(b) - 1] = 1.0
        r = rng.random((M_BASELINE, pool), dtype=np.float32)
        idx = np.argpartition(r, k, axis=1)[:, :k]
        onehot = np.zeros((M_BASELINE, pool), dtype=np.float32)
        np.put_along_axis(onehot, idx, 1.0, axis=1)
        hits = onehot @ mask.T
        p_list[i] = float(((hits >= 3.0).any(axis=1)).mean())
    return p_list


def one_bet_mc_sanity(pool, k, rng):
    """Large-M MC of the 1-bet M3+ probability (symmetric in the chosen set)."""
    bet = np.arange(k)  # any fixed set; probability is set-independent by symmetry
    r = rng.random((M_SANITY, pool), dtype=np.float32)
    idx = np.argpartition(r, k, axis=1)[:, :k]
    hits = np.isin(idx, bet).sum(axis=1)
    return float((hits >= 3).mean())


def poisson_binomial_pvalues(p_arr, observed):
    """Exact Poisson-binomial two-sided p (cross-check for the empirical MC p)."""
    n = len(p_arr)
    dist = np.zeros(n + 1)
    dist[0] = 1.0
    for p in p_arr:
        dist[1:] = dist[1:] * (1 - p) + dist[:-1] * p
        dist[0] *= (1 - p)
    hi = float(dist[observed:].sum())
    lo = float(dist[:observed + 1].sum())
    return min(1.0, 2 * min(hi, lo))


def empirical_null_pvalues(p_arr, observed, rng):
    u = rng.random((T_NULL, len(p_arr)))
    s = (u < p_arr[None, :]).sum(axis=1)
    p_hi = (int((s >= observed).sum()) + 1) / (T_NULL + 1)
    p_lo = (int((s <= observed).sum()) + 1) / (T_NULL + 1)
    return min(1.0, 2 * min(p_hi, p_lo)), p_hi, p_lo


def analyse_cell(conn, cell, rng_parent):
    lottery, sid = cell["lottery_type"], cell["strategy_id"]
    pool, k = LOTTERY_RULES[lottery]
    draws, per_draw, integrity_mismatch = load_cell_draws(conn, lottery, sid)
    n = len(draws)
    success = np.array([1 if any(hc >= 3 for _, _, hc in per_draw[d]) else 0 for d in draws])
    bets_by_draw = [[b for _, b, _ in per_draw[d]] for d in draws]
    max_bets = max(len(b) for b in bets_by_draw)

    rng = np.random.default_rng(rng_parent.spawn(1)[0])
    exact_1bet = exact_one_bet_m3plus(pool, k)
    if max_bets == 1:
        p_arr = np.full(n, exact_1bet)
        baseline_mode = "exact_hypergeometric_1bet"
    else:
        p_arr = conditional_mc_baseline(bets_by_draw, pool, k, rng)
        baseline_mode = f"per_draw_conditional_MC_M={M_BASELINE}"

    observed = int(success.sum())
    obs_rate = observed / n
    base_mean = float(p_arr.mean())
    excess_pp = (obs_rate - base_mean) * 100

    p_emp, p_hi, p_lo = empirical_null_pvalues(p_arr, observed, rng)
    p_exact = poisson_binomial_pvalues(p_arr, observed)

    # stability sign checks (most recent 150 / 500 inside the same window)
    stability = {}
    for w in WINDOWS_STABILITY:
        sw, pw = success[-w:], p_arr[-w:]
        ex_w = (sw.mean() - pw.mean()) * 100
        stability[f"excess_{w}p_pp"] = round(float(ex_w), 4)
        stability[f"sign_consistent_{w}p"] = bool(np.sign(ex_w) == np.sign(excess_pp)) if excess_pp != 0 else None

    # robustness: 3 consecutive 500-blocks + leave-one-out most surprising success
    blocks = [(success[i:i + 500].mean() - p_arr[i:i + 500].mean()) * 100
              for i in range(0, n - 499, 500)][:3]
    succ_idx = np.where(success == 1)[0]
    p_loo = None
    if len(succ_idx) > 0:
        drop = succ_idx[np.argmin(p_arr[succ_idx])]  # most surprising success
        keep = np.ones(n, dtype=bool)
        keep[drop] = False
        p_loo = poisson_binomial_pvalues(p_arr[keep], observed - 1)

    flags = []
    if integrity_mismatch:
        flags.append(f"HIT_COUNT_INTEGRITY_MISMATCH={integrity_mismatch}")
    declared = sid  # declared bet count inferred from name is unreliable; use stored
    if any(tok in sid for tok in ("2bet", "3bet", "4bet", "5bet")):
        for nb, tok in ((2, "2bet"), (3, "3bet"), (4, "4bet"), (5, "5bet")):
            if tok in sid and max_bets != nb:
                flags.append(f"BET_AVAILABILITY_MISMATCH(name~{nb},stored={max_bets})")

    return {
        "lottery_type": lottery, "strategy_id": sid, "n_draws": n,
        "stored_max_bets": max_bets, "baseline_mode": baseline_mode,
        "exact_1bet_baseline": round(exact_1bet, 6),
        "observed_m3plus_draws": observed,
        "observed_m3plus_rate": round(obs_rate, 6),
        "mc_baseline_mean": round(base_mean, 6),
        "excess_pp": round(excess_pp, 4),
        "p_empirical_two_sided": round(p_emp, 6),
        "p_exact_poisson_binomial": round(p_exact, 6),
        "stability": stability,
        "block_excess_pp_500x3": [round(float(b), 4) for b in blocks],
        "p_leave_one_out": round(p_loo, 6) if p_loo is not None else None,
        "integrity_mismatch_rows": integrity_mismatch,
        "data_quality_flags": flags,
    }, success, draws


# ----------------------------------------------------------------------------
# Step 5 — corrections
# ----------------------------------------------------------------------------
def apply_corrections(results):
    ps = [(i, r["p_empirical_two_sided"]) for i, r in enumerate(results)]
    m = len(ps)
    for i, p in ps:
        results[i]["bonferroni_significant"] = bool(p < BONFERRONI_ALPHA)
    ranked = sorted(ps, key=lambda t: t[1])
    bh_cut = 0
    for rank, (_, p) in enumerate(ranked, start=1):
        if p <= BH_Q * rank / m:
            bh_cut = rank
    bh_set = {i for (i, _) in ranked[:bh_cut]}
    for i, _ in ps:
        results[i]["bh_fdr_flag"] = bool(i in bh_set)


# ----------------------------------------------------------------------------
# Step 8 — McNemar (secondary, exploratory; unique-ONLINE-incumbent rule)
# ----------------------------------------------------------------------------
def mcnemar_tests(results, success_by_cell, draws_by_cell, online_ids):
    groups = {}
    for r in results:
        groups.setdefault((r["lottery_type"], r["stored_max_bets"]), []).append(r)
    out = []
    for (lot, nb), members in sorted(groups.items(), key=str):
        incumbents = [m for m in members if m["strategy_id"] in online_ids]
        if len(incumbents) != 1:
            out.append({"group": f"{lot}/N={nb}", "status": "NOT_RUN",
                        "reason": f"non-unique ONLINE incumbent (count={len(incumbents)})"})
            continue
        inc = incumbents[0]
        challengers = [m for m in members if m is not inc]
        if not challengers:
            out.append({"group": f"{lot}/N={nb}", "status": "NOT_RUN",
                        "reason": "no challenger cell in group"})
            continue
        ch = max(challengers, key=lambda m: m["excess_pp"])
        key_i = (inc["lottery_type"], inc["strategy_id"])
        key_c = (ch["lottery_type"], ch["strategy_id"])
        di = dict(zip(draws_by_cell[key_i], success_by_cell[key_i]))
        dc = dict(zip(draws_by_cell[key_c], success_by_cell[key_c]))
        common = sorted(set(di) & set(dc), key=int)
        b = sum(1 for d in common if dc[d] == 1 and di[d] == 0)
        c = sum(1 for d in common if dc[d] == 0 and di[d] == 1)
        nd = b + c
        if nd == 0:
            p = 1.0
        else:
            tail = sum(math.comb(nd, x) for x in range(min(b, c) + 1)) / 2 ** nd
            p = min(1.0, 2 * tail)
        out.append({
            "group": f"{lot}/N={nb}", "status": "RUN_EXPLORATORY",
            "incumbent": inc["strategy_id"], "challenger": ch["strategy_id"],
            "common_draws": len(common), "b_challenger_only": b, "c_incumbent_only": c,
            "p_exact_two_sided": round(p, 6),
            "caveat": "challenger selected by observed excess on the same data — exploratory only",
        })
    return out


# ----------------------------------------------------------------------------
# Step 9 — H6 evidence verification (no wiki summary numbers may be used)
# ----------------------------------------------------------------------------
def h6_evidence_check(conn):
    checks = {}
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=?",
                (H6_STRATEGY_ID,))
    checks["replay_rows"] = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM prediction_runs WHERE strategy_name LIKE '%h6%' OR strategy_name LIKE '%ew85%'")
    checks["prediction_runs_rows"] = cur.fetchone()[0]
    try:
        cur.execute("SELECT COUNT(*) FROM shadow_experiments")
        checks["shadow_experiments_rows"] = cur.fetchone()[0]
    except sqlite3.OperationalError:
        checks["shadow_experiments_rows"] = None
    root = os.path.join(os.path.dirname(__file__), "..")
    for rel in ("docs/H6_PRODUCTION_GO_LIVE_SUMMARY.md",
                "strategies/H6_gate_mk20_ew85_spec.md",
                "lottery_api/engine/h6_alert_engine.py"):
        checks[rel] = os.path.exists(os.path.join(root, rel))
    reproducible = (checks["replay_rows"] > 0 or checks["prediction_runs_rows"] > 0)
    status = "H6_PER_DRAW_EVIDENCE_FOUND" if reproducible else "H6_EVIDENCE_NOT_REPRODUCIBLE"
    return {"status": status, "checks": checks,
            "note": ("git history contains only a 7-line spec, strategy-state JSON and a "
                     "leakage transcript (commits 515f9a4/4356b95/79e15ec); no per-draw OOS "
                     "records exist on main or in history; wiki summary claims (+4.00pp/3000p) "
                     "are therefore unverifiable and are NOT used in any computation here "
                     "(CLAUDE.md traceability rule: non-reproducible results are invalid).")}


# ----------------------------------------------------------------------------
def main():
    started = datetime.now().isoformat()
    prereg_entries = preregister()  # MUST precede all statistics (L138)

    conn = open_ro()
    ok, gates = data_quality_gates(conn)
    if not ok:
        emit(classification="P267C_M3PLUS_REVALIDATION_BLOCKED_DATA_QUALITY",
             prereg=prereg_entries, gates=gates, cells=[], mcnemar=[], h6={},
             sanity={}, no_data=[], orphans=[], started=started)
        print("BLOCKED_DATA_QUALITY", gates)
        return 1

    cells, no_data, orphans, online_ids = build_universe(conn)
    if len(cells) != FAMILY_M:
        emit(classification="P267C_M3PLUS_REVALIDATION_BLOCKED_DATA_QUALITY",
             prereg=prereg_entries, gates=gates, cells=[], mcnemar=[], h6={},
             sanity={}, no_data=no_data, orphans=orphans, started=started,
             extra={"universe_size_found": len(cells)})
        print(f"BLOCKED: universe size {len(cells)} != pre-registered {FAMILY_M}")
        return 1

    ss = np.random.SeedSequence(SEED)
    rng_sanity = np.random.default_rng(ss.spawn(1)[0])
    sanity = {}
    for lot, (pool, k) in LOTTERY_RULES.items():
        exact = exact_one_bet_m3plus(pool, k)
        mc = one_bet_mc_sanity(pool, k, rng_sanity)
        diff_pp = abs(mc - exact) * 100
        sanity[lot] = {"exact": round(exact, 6), "mc": round(mc, 6),
                       "abs_diff_pp": round(diff_pp, 4), "tolerance_pp": SANITY_TOL_PP,
                       "pass": bool(diff_pp <= SANITY_TOL_PP)}
    if not all(v["pass"] for v in sanity.values()):
        emit(classification="P267C_M3PLUS_REVALIDATION_BLOCKED_DATA_QUALITY",
             prereg=prereg_entries, gates=gates, cells=[], mcnemar=[], h6={},
             sanity=sanity, no_data=no_data, orphans=orphans, started=started)
        print("BLOCKED: 1-bet MC baseline failed convergence sanity", sanity)
        return 1

    results, success_by_cell, draws_by_cell = [], {}, {}
    cell_seeds = ss.spawn(len(cells))
    for cell, cseed in zip(sorted(cells, key=lambda c: (c["lottery_type"], c["strategy_id"])),
                           cell_seeds):
        res, succ, draws = analyse_cell(conn, cell, cseed)
        results.append(res)
        key = (res["lottery_type"], res["strategy_id"])
        success_by_cell[key], draws_by_cell[key] = succ, draws
        print(f"  done {key[0]}/{key[1]}: excess={res['excess_pp']:+.2f}pp p={res['p_empirical_two_sided']:.4f}")

    apply_corrections(results)
    mcn = mcnemar_tests(results, success_by_cell, draws_by_cell, online_ids)
    h6 = h6_evidence_check(conn)
    conn.close()

    n_bonf = sum(1 for r in results if r["bonferroni_significant"])
    n_bh = sum(1 for r in results if r["bh_fdr_flag"])
    candidate_cells = [
        r for r in results
        if r["bonferroni_significant"]
        and all(r["stability"].get(f"sign_consistent_{w}p") in (True, None) for w in WINDOWS_STABILITY)
        and (r["p_leave_one_out"] is None or r["p_leave_one_out"] < BONFERRONI_ALPHA)
    ]
    classification = ("P267C_M3PLUS_REVALIDATION_COMPLETE_CANDIDATE_SIGNAL_REQUIRES_HUMAN_REVIEW"
                      if candidate_cells else
                      "P267C_M3PLUS_REVALIDATION_COMPLETE_NO_VALIDATED_M3_EDGE")
    assert classification in ALLOWED_CLASSIFICATIONS

    emit(classification=classification, prereg=prereg_entries, gates=gates, cells=results,
         mcnemar=mcn, h6=h6, sanity=sanity, no_data=no_data, orphans=orphans, started=started,
         extra={"bonferroni_significant_cells": n_bonf, "bh_fdr_flagged_cells": n_bh,
                "candidate_cells": [f"{r['lottery_type']}/{r['strategy_id']}" for r in candidate_cells]})
    print(f"\nClassification: {classification}")
    print(f"Bonferroni-significant: {n_bonf}/36; BH-FDR flagged: {n_bh}/36")
    return 0


def emit(classification, prereg, gates, cells, mcnemar, h6, sanity, no_data, orphans,
         started, extra=None):
    pre_registration = {
        "registry_id": "HR-P267B-M3PLUS-REVAL-001",
        "registry_path": "lottery_api/data/hypothesis_registry.jsonl",
        "registered_entries": prereg,
        "primary_hypothesis": ("H-P267B-1: at least one replay-backed cell's draw-level M3+ rate "
                               "differs from its strategy-specific conditional fair-draw baseline "
                               "(two-sided, full-family corrected); expected outcome NULL"),
        "secondary_hypotheses": [
            "H-P267B-2: descriptive excess ranking (observed - MC baseline), no promotion claims",
            "H-P267B-3: same-lottery same-N McNemar vs unique ONLINE incumbent (exploratory)",
            "H-P267B-4: H6 M2-only vs M3+ decomposition, CONDITIONAL on reproducible evidence",
        ],
        "success_metric": "draw_success = any bet_index with hit_count >= 3; denominator = distinct target_draw",
        "special_hit_excluded": True,
        "family_m": FAMILY_M,
        "bonferroni_alpha": BONFERRONI_ALPHA,
        "bh_fdr_q": BH_Q,
        "primary_endpoint": f"most-recent {WINDOW_PRIMARY} distinct target_draw",
        "stability_windows_sign_check_only": list(WINDOWS_STABILITY),
        "null_design": "per-draw Bernoulli(p_i) MC (L96); label-shuffle forbidden",
        "circular_match_guard": "predict-vs-actual only (L132/L139); historical-pool max-hit never computed",
        "seed": SEED,
        "mc_baseline_M": M_BASELINE,
        "null_iterations_T": T_NULL,
        "feasibility_look_disclosure": ("P267B design round inspected cell-level aggregate M3+ rates; "
                                        "mitigation: family = exhaustive 36-cell universe (no observation-"
                                        "driven selection), two-sided tests, full-family correction, and "
                                        "this run recomputes everything from raw rows with fixed seed."),
        "power_statement": ("n=1500, p0=1.0% (DAILY_539 1-bet): Bonferroni-corrected minimum detectable "
                            "excess ~ +0.98pp at 80% power; short windows are sign-checks only because "
                            "they are structurally underpowered."),
    }
    payload = {
        "task": "P267C_M3PLUS_SUCCESS_METRIC_STRATEGY_REVALIDATION",
        "generated_at": datetime.now().isoformat(),
        "started_at": started,
        "db_read_only_mode": "sqlite3 URI mode=ro",
        "pre_registration": pre_registration,
        "data_quality_gates": gates,
        "one_bet_baseline_sanity": sanity,
        "no_data_cells": [f"{l}:{s}" for (l, s) in no_data],
        "orphan_cells": [f"{l}:{s}" for (l, s) in orphans],
        "results": cells,
        "mcnemar": mcnemar,
        "h6_evidence": h6,
        "summary": extra or {},
        "disclaimers": DISCLAIMERS,
        "classification": classification,
    }
    os.makedirs(OUT_DIR, exist_ok=True)
    jpath = os.path.join(OUT_DIR, f"p267c_m3plus_strategy_revalidation_{STAMP}.json")
    with open(jpath, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    md = ["# P267C — M3+ Success-Metric Strategy Revalidation", "",
          f"Generated: {payload['generated_at']}  |  DB access: read-only (mode=ro)", "",
          "## Pre-Registration (declared before results)", "",
          "```json", json.dumps(pre_registration, ensure_ascii=False, indent=2), "```", "",
          "## Data-Quality Gates", "",
          "```json", json.dumps(gates, ensure_ascii=False, indent=2), "```", "",
          "## 1-Bet Baseline Sanity (exact vs MC)", "",
          "```json", json.dumps(sanity, ensure_ascii=False, indent=2), "```", "",
          "## Results (36 replay-backed cells)", "",
          "| Lottery | Strategy | N | Bets | Observed M3+ | MC baseline | Excess (pp) | p (emp) | p (exact PB) | Bonf | BH | Flags |",
          "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(cells, key=lambda x: x["p_empirical_two_sided"]):
        md.append("| {l} | {s} | {n} | {b} | {o:.2%} | {m:.2%} | {e:+.2f} | {p:.4f} | {pe:.4f} | {bf} | {bh} | {fl} |".format(
            l=r["lottery_type"], s=r["strategy_id"], n=r["n_draws"], b=r["stored_max_bets"],
            o=r["observed_m3plus_rate"], m=r["mc_baseline_mean"], e=r["excess_pp"],
            p=r["p_empirical_two_sided"], pe=r["p_exact_poisson_binomial"],
            bf="YES" if r.get("bonferroni_significant") else "no",
            bh="YES" if r.get("bh_fdr_flag") else "no",
            fl=";".join(r["data_quality_flags"]) or "—"))
    md += ["", "## McNemar (secondary, exploratory)", "",
           "```json", json.dumps(mcnemar, ensure_ascii=False, indent=2), "```", "",
           "## H6 Evidence Verification", "",
           "```json", json.dumps(h6, ensure_ascii=False, indent=2), "```", "",
           "## NO_DATA / Orphan Cells", "",
           f"- NO_DATA (registered, no replay rows): {payload['no_data_cells']}",
           f"- Orphans (rows, not registered): {payload['orphan_cells']}", "",
           "## Summary", "",
           "```json", json.dumps(payload["summary"], ensure_ascii=False, indent=2), "```", "",
           "## Disclaimers", ""]
    md += [f"- {d}" for d in DISCLAIMERS]
    md += ["", f"## Final Classification", "", f"`{classification}`", ""]
    mpath = os.path.join(OUT_DIR, f"p267c_m3plus_strategy_revalidation_{STAMP}.md")
    with open(mpath, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print(f"artifacts: {jpath}\n           {mpath}")


if __name__ == "__main__":
    sys.exit(main())
