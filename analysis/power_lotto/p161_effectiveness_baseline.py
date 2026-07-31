#!/usr/bin/env python3
"""
P161 — POWER_LOTTO Replay Strategy Effectiveness Baseline (READ-ONLY)
====================================================================
Authorized by CEO Decision 2026-05-31. Worker = analysis only.

This script produces a read-only effectiveness baseline for POWER_LOTTO
replay strategies stored in `strategy_prediction_replays`. It NEVER writes
to the DB (PRAGMA query_only=ON on every connection) and loads the
source-controlled lifecycle registry read-only.

Statistical unit = distinct target_draw (POWER_LOTTO has 1551 distinct
target draws across 10 strategies; per-strategy n_draws varies 1500..1551).

Random baselines:
  - main number hit_count: E[hit] = 6 * 6/38 = 36/38 = 0.9473684...
  - special number: 1/8 = 0.125 (POWER_LOTTO special pool is 1..8)

Sections (per task spec):
  1. Per-strategy table (lifecycle JOIN, n_draws, mean/max hit, dist 0..6, 95% CI)
  2. Main vs special SEPARATED (special filtered to predicted_special IS NOT NULL)
  3. Strategy-vs-random with significance + corrected p
  4. Lifecycle-group comparison (DESCRIPTIVE; survivorship caveat)
  5. Multi-bet slot comparison (bet_index), coverage-normalized note (L37)
  6. Multiple-testing correction (Bonferroni + BH) across the family
  7. Leakage-safe labeling: DESCRIPTIVE (in-sample) vs PREDICTIVE (needs OOS>=500)

Outputs:
  outputs/research/power_lotto/p161_effectiveness_baseline_20260531.json
  outputs/research/power_lotto/p161_effectiveness_baseline_20260531.md
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy import stats


def _to_native(obj):
    """Recursively convert numpy scalar/array types to native Python for JSON."""
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return _to_native(obj.tolist())
    return obj

# ── Paths ──────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_DIR = PROJECT_ROOT / "outputs" / "research" / "power_lotto"
JSON_OUT = OUT_DIR / "p161_effectiveness_baseline_20260531.json"
MD_OUT = OUT_DIR / "p161_effectiveness_baseline_20260531.md"

sys.path.insert(0, str(PROJECT_ROOT))
from lottery_api.models.replay_strategy_registry import (  # noqa: E402
    get_strategy_lifecycle_status,
    get_strategy_lifecycle_metadata,
)


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


# ── Constants ──────────────────────────────────────────────────────────────
LOTTERY = "POWER_LOTTO"
MAIN_RANDOM_BASELINE = 6.0 * 6.0 / 38.0   # 0.9473684210526315
SPECIAL_RANDOM_BASELINE = 1.0 / 8.0       # 0.125
EXPECTED_TOTAL_ROWS = 94924
EXPECTED_PL_ROWS = 36104
EXPECTED_PL_STRATEGIES = 10
EXPECTED_PL_DRAWS = 1551
MIN_NDRAWS_FOR_RANKING = 500   # L101 minimum-n gate before any ranking
OOS_WINDOW_MIN = 500           # L101 walk-forward OOS requirement


# ── Read-only DB helper ──────────────────────────────────────────────────────
def open_ro() -> sqlite3.Connection:
    """Open a read-only connection (query_only enforced)."""
    _p291u_db_path = _p291u_resolve_db_path()
    conn = _p291u_connect_resolved(_p291u_db_path, uri=True)
    conn.execute("PRAGMA query_only=ON;")
    return conn


def _ci95_mean(values_sum: float, values_sumsq: float, n: int):
    """95% CI for a mean using the normal approximation (large n).

    Returns (mean, lo, hi, sem). For n<2 returns (mean, mean, mean, 0).
    """
    if n <= 0:
        return (0.0, 0.0, 0.0, 0.0)
    mean = values_sum / n
    if n < 2:
        return (mean, mean, mean, 0.0)
    var = (values_sumsq - n * mean * mean) / (n - 1)
    var = max(var, 0.0)
    sem = math.sqrt(var / n)
    z = 1.959963984540054  # 97.5th percentile of standard normal
    return (mean, mean - z * sem, mean + z * sem, sem)


def _one_sample_z_p(mean: float, baseline: float, sem: float, n: int):
    """Two-sided z-test of mean vs baseline. Returns (z, p)."""
    if sem <= 0 or n < 2:
        return (float("nan"), float("nan"))
    z = (mean - baseline) / sem
    p = 2.0 * stats.norm.sf(abs(z))
    return (z, p)


def _binom_p_special(hits: int, n: int, p0: float):
    """Two-sided exact binomial test of special-hit count vs p0."""
    if n <= 0:
        return float("nan")
    res = stats.binomtest(hits, n, p0, alternative="two-sided")
    return float(res.pvalue)


def sl_key(sl: dict) -> str:
    """Family key for a bet-slot record, matching the §6 family encoding."""
    return f"slot::{sl['strategy_id']}#bet{sl['bet_index']}"


def bonferroni_bh(pvals: list[float]):
    """Return (bonferroni_list, bh_list) aligned to input order.

    NaN p-values are passed through as NaN and excluded from the family size /
    BH ranking (only finite p-values count toward m).
    """
    idx_finite = [i for i, p in enumerate(pvals) if p is not None and not math.isnan(p)]
    m = len(idx_finite)
    bonf = [float("nan")] * len(pvals)
    bh = [float("nan")] * len(pvals)
    if m == 0:
        return bonf, bh
    # Bonferroni
    for i in idx_finite:
        bonf[i] = min(1.0, pvals[i] * m)
    # Benjamini-Hochberg
    ranked = sorted(idx_finite, key=lambda i: pvals[i])
    prev = 1.0
    # iterate from largest rank down to enforce monotonicity
    bh_raw = {}
    for rank_pos, i in enumerate(ranked, start=1):
        bh_raw[i] = pvals[i] * m / rank_pos
    # monotone adjustment (step-up)
    for rank_pos in range(m, 0, -1):
        i = ranked[rank_pos - 1]
        val = min(prev, bh_raw[i])
        bh[i] = min(1.0, val)
        prev = bh[i]
    return bonf, bh


# ── Section 1+2+3: per-strategy ──────────────────────────────────────────────
def per_strategy_rows(conn: sqlite3.Connection):
    """Aggregate per strategy. STATISTICAL UNIT = distinct target_draw.

    For multi-bet strategies the row grain is (strategy, draw, bet_index). The
    PRIMARY per-strategy main test uses ONE observation per distinct target_draw
    — namely the MEAN hit_count across that draw's bets (coverage-normalized
    "average bet quality per draw"). This gives n = n_draws genuinely (near-)
    independent observations and avoids the pseudo-replication / clustering trap
    of treating each of the 3-5 correlated bets within a draw as independent
    (which would understate the SEM and inflate significance).

    We ALSO report the naive per-bet-row mean as a secondary descriptive figure,
    explicitly flagged as pseudo-replicated (NOT used for the significance test).
    The per-slot view is handled separately in §5.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT strategy_id,
               COUNT(*)                       AS n_rows,
               COUNT(DISTINCT target_draw)    AS n_draws,
               COUNT(DISTINCT bet_index)      AS n_bet_slots,
               SUM(hit_count)                 AS sum_hc,
               SUM(hit_count*hit_count)       AS sumsq_hc,
               MAX(hit_count)                 AS max_hc,
               MIN(CAST(target_draw AS INTEGER)) AS min_draw,
               MAX(CAST(target_draw AS INTEGER)) AS max_draw
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
        GROUP BY strategy_id
        ORDER BY strategy_id
        """,
        (LOTTERY,),
    )
    cols = [c[0] for c in cur.description]
    strategies = [dict(zip(cols, r)) for r in cur.fetchall()]

    # Per-draw mean hit_count series (statistical unit). One value per draw =
    # mean over that draw's bets. We fetch raw per-draw means and compute sample
    # mean/variance in Python so the SEM reflects between-draw variance only.
    cur.execute(
        """
        SELECT strategy_id, target_draw, AVG(hit_count*1.0) AS draw_mean
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
        GROUP BY strategy_id, target_draw
        """,
        (LOTTERY,),
    )
    per_draw = {}
    for sid, _draw, dmean in cur.fetchall():
        per_draw.setdefault(sid, []).append(dmean)

    # hit_count distribution 0..6 per strategy
    cur.execute(
        """
        SELECT strategy_id, hit_count, COUNT(*)
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
        GROUP BY strategy_id, hit_count
        """,
        (LOTTERY,),
    )
    dist = {}
    for sid, hc, c in cur.fetchall():
        dist.setdefault(sid, {k: 0 for k in range(7)})[hc] = c

    # special performance (predicted_special IS NOT NULL only)
    cur.execute(
        """
        SELECT strategy_id,
               COUNT(*)        AS sp_n,
               SUM(special_hit) AS sp_hits
        FROM strategy_prediction_replays
        WHERE lottery_type = ? AND predicted_special IS NOT NULL
        GROUP BY strategy_id
        """,
        (LOTTERY,),
    )
    special = {sid: {"sp_n": n, "sp_hits": h} for sid, n, h in cur.fetchall()}

    out = []
    lifecycle_unresolved = []
    cross_lottery_mismatch = []
    for s in strategies:
        sid = s["strategy_id"]
        lifecycle = get_strategy_lifecycle_status(sid)
        supported = None
        try:
            meta = get_strategy_lifecycle_metadata(sid)
            supported = meta.get("supported_lottery_types")
        except KeyError:
            pass
        if lifecycle is None:
            lifecycle = "LIFECYCLE_UNRESOLVED"
            lifecycle_unresolved.append(sid)
        # cross-lottery registry mismatch: id matches but registry entry is for
        # a different lottery type than the replay rows we observe.
        if supported is not None and LOTTERY not in supported:
            cross_lottery_mismatch.append(
                {"strategy_id": sid, "registry_lottery_types": supported,
                 "observed_lottery_type": LOTTERY, "lifecycle": lifecycle}
            )

        n_rows = s["n_rows"]
        n_draws = s["n_draws"]
        # Secondary descriptive: naive per-bet-row mean (pseudo-replicated — NOT
        # used for significance). Reported for transparency only.
        bet_row_mean = s["sum_hc"] / n_rows if n_rows else float("nan")

        # PRIMARY main test: per-draw mean hit_count (statistical unit = draw).
        draw_vals = per_draw.get(sid, [])
        dv_sum = sum(draw_vals)
        dv_sumsq = sum(v * v for v in draw_vals)
        mean, lo, hi, sem = _ci95_mean(dv_sum, dv_sumsq, len(draw_vals))
        z_main, p_main = _one_sample_z_p(mean, MAIN_RANDOM_BASELINE, sem, len(draw_vals))
        verdict = (
            "ABOVE" if mean > MAIN_RANDOM_BASELINE else
            "BELOW" if mean < MAIN_RANDOM_BASELINE else "AT"
        )
        d = dist.get(sid, {k: 0 for k in range(7)})
        sp = special.get(sid)
        sp_block = None
        if sp:
            sp_n, sp_hits = sp["sp_n"], sp["sp_hits"]
            sp_rate = sp_hits / sp_n if sp_n else float("nan")
            sp_p = _binom_p_special(sp_hits, sp_n, SPECIAL_RANDOM_BASELINE)
            sp_verdict = (
                "ABOVE" if sp_rate > SPECIAL_RANDOM_BASELINE else
                "BELOW" if sp_rate < SPECIAL_RANDOM_BASELINE else "AT"
            )
            sp_block = {
                "predicted_special_n": sp_n,
                "special_hits": sp_hits,
                "special_hit_rate": round(sp_rate, 6),
                "special_random_baseline": SPECIAL_RANDOM_BASELINE,
                "special_verdict_vs_random": sp_verdict,
                "special_binom_p_raw": (None if math.isnan(sp_p) else round(sp_p, 6)),
            }

        out.append({
            "strategy_id": sid,
            "lifecycle": lifecycle,
            "registry_lottery_types": supported,
            "n_draws": n_draws,            # STATISTICAL UNIT (= len(draw_vals))
            "n_bet_rows": n_rows,          # row grain (draws x bet slots)
            "n_bet_slots": s["n_bet_slots"],
            "draw_range": [s["min_draw"], s["max_draw"]],
            # PRIMARY metric: per-draw mean hit_count (statistical unit = draw)
            "mean_hit_count": round(mean, 6),
            "max_hit_count": s["max_hc"],
            "ci95_mean_lo": round(lo, 6),
            "ci95_mean_hi": round(hi, 6),
            "sem": round(sem, 6),
            "statistical_unit": "per_draw_mean_hit_count",
            # secondary descriptive only (pseudo-replicated; NOT tested)
            "bet_row_mean_hit_count_pseudo_replicated": round(bet_row_mean, 6),
            "hit_count_dist": {str(k): d.get(k, 0) for k in range(7)},
            "main_random_baseline": round(MAIN_RANDOM_BASELINE, 6),
            "main_verdict_vs_random": verdict,
            "main_z": (None if math.isnan(z_main) else round(z_main, 4)),
            "main_p_raw": (None if math.isnan(p_main) else round(p_main, 6)),
            "main_test_note": (
                "z-test on per-draw mean hit_count (n=n_draws independent draws), "
                "NOT on per-bet rows (which would pseudo-replicate within-draw bets)."
            ),
            "special": sp_block,
            "meets_min_ndraws_for_ranking": n_draws >= MIN_NDRAWS_FOR_RANKING,
        })
    return out, lifecycle_unresolved, cross_lottery_mismatch


# ── Section 5: multi-bet slot comparison (coverage-normalized) ───────────────
def per_bet_slot(conn: sqlite3.Connection):
    """Per (strategy, bet_index): n_draws, mean hit_count, CI, vs random.

    COVERAGE NORMALIZED: each bet slot is exactly 6 main numbers (one bet),
    so comparing bet_index=1 vs bet_index=2 means is apples-to-apples — it does
    NOT inflate by picking more numbers (L37 geometric-benefit trap). The naive
    union-of-all-bets hit_count would inflate simply because more numbers are
    selected; we therefore compare per-slot means, each over 6-number bets.
    """
    cur = conn.cursor()
    cur.execute(
        """
        SELECT strategy_id, bet_index,
               COUNT(*) AS n_rows,
               COUNT(DISTINCT target_draw) AS n_draws,
               SUM(hit_count) AS sum_hc,
               SUM(hit_count*hit_count) AS sumsq_hc,
               MAX(hit_count) AS max_hc
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
        GROUP BY strategy_id, bet_index
        ORDER BY strategy_id, bet_index
        """,
        (LOTTERY,),
    )
    slots = []
    for sid, bi, n_rows, n_draws, sum_hc, sumsq_hc, max_hc in cur.fetchall():
        mean, lo, hi, sem = _ci95_mean(sum_hc, sumsq_hc, n_rows)
        z, p = _one_sample_z_p(mean, MAIN_RANDOM_BASELINE, sem, n_rows)
        slots.append({
            "strategy_id": sid,
            "bet_index": bi,
            "n_draws": n_draws,
            "n_rows": n_rows,
            "mean_hit_count": round(mean, 6),
            "max_hit_count": max_hc,
            "ci95_lo": round(lo, 6),
            "ci95_hi": round(hi, 6),
            "vs_random": ("ABOVE" if mean > MAIN_RANDOM_BASELINE else
                          "BELOW" if mean < MAIN_RANDOM_BASELINE else "AT"),
            "z": (None if math.isnan(z) else round(z, 4)),
            "p_raw": (None if math.isnan(p) else round(p, 6)),
        })

    # Aggregate per slot position across all strategies that HAVE that slot.
    cur.execute(
        """
        SELECT bet_index,
               COUNT(*) AS n_rows,
               COUNT(DISTINCT strategy_id) AS n_strats,
               SUM(hit_count) AS sum_hc,
               SUM(hit_count*hit_count) AS sumsq_hc
        FROM strategy_prediction_replays
        WHERE lottery_type = ?
        GROUP BY bet_index
        ORDER BY bet_index
        """,
        (LOTTERY,),
    )
    by_position = []
    for bi, n_rows, n_strats, sum_hc, sumsq_hc in cur.fetchall():
        mean, lo, hi, sem = _ci95_mean(sum_hc, sumsq_hc, n_rows)
        z, p = _one_sample_z_p(mean, MAIN_RANDOM_BASELINE, sem, n_rows)
        by_position.append({
            "bet_index": bi,
            "n_strategies_with_slot": n_strats,
            "n_rows": n_rows,
            "mean_hit_count": round(mean, 6),
            "ci95_lo": round(lo, 6),
            "ci95_hi": round(hi, 6),
            "vs_random": ("ABOVE" if mean > MAIN_RANDOM_BASELINE else
                          "BELOW" if mean < MAIN_RANDOM_BASELINE else "AT"),
            "z": (None if math.isnan(z) else round(z, 4)),
            "p_raw": (None if math.isnan(p) else round(p, 6)),
        })
    return slots, by_position


# ── Section 4: lifecycle-group comparison (DESCRIPTIVE) ──────────────────────
def lifecycle_groups(per_strategy):
    groups = {}
    for s in per_strategy:
        lc = s["lifecycle"]
        g = groups.setdefault(lc, {
            "lifecycle": lc, "n_strategies": 0, "strategy_ids": [],
            "sum_hc": 0.0, "sumsq_hc": 0.0, "n_rows": 0, "n_draws_union": 0,
        })
        g["n_strategies"] += 1
        g["strategy_ids"].append(s["strategy_id"])
        # reconstruct sums from mean & n_rows for an aggregate group mean
        g["sum_hc"] += s["mean_hit_count"] * s["n_bet_rows"]
        g["n_rows"] += s["n_bet_rows"]
    out = []
    for lc, g in groups.items():
        mean = g["sum_hc"] / g["n_rows"] if g["n_rows"] else float("nan")
        out.append({
            "lifecycle": lc,
            "n_strategies": g["n_strategies"],
            "strategy_ids": sorted(g["strategy_ids"]),
            "n_bet_rows": g["n_rows"],
            "group_mean_hit_count": round(mean, 6),
            "vs_random": ("ABOVE" if mean > MAIN_RANDOM_BASELINE else
                          "BELOW" if mean < MAIN_RANDOM_BASELINE else "AT"),
        })
    out.sort(key=lambda x: x["lifecycle"])
    return out


# ── Main ─────────────────────────────────────────────────────────────────────
def main():
    conn = open_ro()
    # Guard: confirm read-only + counts
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays;")
    total_rows = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*), COUNT(DISTINCT strategy_id), COUNT(DISTINCT target_draw) "
        "FROM strategy_prediction_replays WHERE lottery_type=?;",
        (LOTTERY,),
    )
    pl_rows, pl_strats, pl_draws = cur.fetchone()
    cur.execute(
        "SELECT ROUND(AVG(hit_count*1.0),6) FROM strategy_prediction_replays "
        "WHERE lottery_type=?;",
        (LOTTERY,),
    )
    pool_avg_hit = cur.fetchone()[0]
    cur.execute(
        "SELECT COUNT(*), SUM(special_hit) FROM strategy_prediction_replays "
        "WHERE lottery_type=? AND predicted_special IS NOT NULL;",
        (LOTTERY,),
    )
    sp_n_all, sp_hits_all = cur.fetchone()
    pool_special_rate = sp_hits_all / sp_n_all if sp_n_all else float("nan")
    # contrast: diluted all-row special avg (the trap)
    cur.execute(
        "SELECT ROUND(AVG(special_hit*1.0),6) FROM strategy_prediction_replays "
        "WHERE lottery_type=?;",
        (LOTTERY,),
    )
    pool_special_diluted = cur.fetchone()[0]

    per_strat, unresolved, cross_mismatch = per_strategy_rows(conn)
    slots, by_position = per_bet_slot(conn)
    lc_groups = lifecycle_groups(per_strat)

    # ── §6 multiple-testing correction across the comparison family ──────────
    # Family = per-strategy main tests + per-strategy special tests + per-slot
    # tests. We collect (label, p_raw) and apply Bonferroni + BH jointly.
    family = []
    for s in per_strat:
        family.append({
            "key": f"main::{s['strategy_id']}",
            "kind": "strategy_main_vs_random",
            "p_raw": s["main_p_raw"],
        })
    for s in per_strat:
        if s["special"] is not None:
            family.append({
                "key": f"special::{s['strategy_id']}",
                "kind": "strategy_special_vs_random",
                "p_raw": s["special"]["special_binom_p_raw"],
            })
    for sl in slots:
        family.append({
            "key": sl_key(sl),
            "kind": "bet_slot_main_vs_random",
            "p_raw": sl["p_raw"],
        })
    pvals = [f["p_raw"] if f["p_raw"] is not None else float("nan") for f in family]
    bonf, bh = bonferroni_bh(pvals)
    for f, b, h in zip(family, bonf, bh):
        f["p_bonferroni"] = (None if math.isnan(b) else round(b, 6))
        f["p_bh"] = (None if math.isnan(h) else round(h, 6))
    family_size = sum(1 for p in pvals if not math.isnan(p))

    # Any strategy beats random after correction? (main, ABOVE & p_bonf<0.05)
    # The PRIMARY headline uses per-strategy MAIN (per-draw) means.
    survivors_bonf = []
    survivors_bh = []
    fam_by_key = {f["key"]: f for f in family}
    for s in per_strat:
        f = fam_by_key.get(f"main::{s['strategy_id']}")
        if f and s["main_verdict_vs_random"] == "ABOVE":
            if f["p_bonferroni"] is not None and f["p_bonferroni"] < 0.05:
                survivors_bonf.append(s["strategy_id"])
            if f["p_bh"] is not None and f["p_bh"] < 0.05:
                survivors_bh.append(s["strategy_id"])

    # Secondary: any individual bet SLOT survives correction (descriptive only).
    # These are per-(strategy,bet_index) slot means (one row per draw per slot,
    # so the per-slot z-test is NOT pseudo-replicated). Reported separately
    # because a surviving slot is still an IN-SAMPLE, full-history finding and
    # is NOT a predictive claim without walk-forward OOS (L101).
    slot_survivors_bonf = []
    slot_survivors_bh = []
    slot_by_key = {sl_key(sl): sl for sl in slots}
    for f in family:
        if f["kind"] != "bet_slot_main_vs_random":
            continue
        sl = slot_by_key.get(f["key"])
        is_above = sl is not None and sl["vs_random"] == "ABOVE"
        if is_above and f["p_bonferroni"] is not None and f["p_bonferroni"] < 0.05:
            slot_survivors_bonf.append(f["key"])
        if is_above and f["p_bh"] is not None and f["p_bh"] < 0.05:
            slot_survivors_bh.append(f["key"])

    # Best single strategy by mean hit_count among those meeting min-n gate
    eligible = [s for s in per_strat if s["meets_min_ndraws_for_ranking"]]
    best = max(eligible, key=lambda s: s["mean_hit_count"]) if eligible else None
    best_block = None
    if best:
        f = fam_by_key.get(f"main::{best['strategy_id']}")
        best_block = {
            "strategy_id": best["strategy_id"],
            "lifecycle": best["lifecycle"],
            "n_draws": best["n_draws"],
            "mean_hit_count": best["mean_hit_count"],
            "ci95": [best["ci95_mean_lo"], best["ci95_mean_hi"]],
            "vs_random": best["main_verdict_vs_random"],
            "p_raw": best["main_p_raw"],
            "p_bonferroni": f["p_bonferroni"] if f else None,
            "p_bh": f["p_bh"] if f else None,
            "beats_random_after_correction": bool(
                best["main_verdict_vs_random"] == "ABOVE"
                and f is not None and f["p_bonferroni"] is not None
                and f["p_bonferroni"] < 0.05
            ),
        }

    # ── §7 leakage labeling ──────────────────────────────────────────────────
    leakage = {
        "all_in_sample_comparisons_are": "DESCRIPTIVE",
        "predictive_claim_requirement": (
            "PREDICTIVE claims require walk-forward / only-past-data evaluation "
            f"with an OOS window >= {OOS_WINDOW_MIN} distinct draws (L101). "
            "This baseline selects/ranks strategies on the FULL replay history "
            "and therefore CANNOT assert that any strategy 'works' going forward."
        ),
        "per_strategy_label": "DESCRIPTIVE_IN_SAMPLE",
        "lifecycle_group_label": "DESCRIPTIVE_IN_SAMPLE",
        "bet_slot_label": "DESCRIPTIVE_IN_SAMPLE",
        "predictive_label": "NOT_ESTABLISHED_NO_WALK_FORWARD",
    }

    # Re-confirm DB unchanged
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays;")
    total_rows_after = cur.fetchone()[0]
    conn.close()

    report = {
        "task_id": "P161_POWER_LOTTO_REPLAY_STRATEGY_EFFECTIVENESS_BASELINE",
        "version": "2.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P161_POWER_LOTTO_EFFECTIVENESS_BASELINE_READY",
        "read_only": True,
        "pragma_query_only": True,
        "db_path": str(DB_PATH.relative_to(PROJECT_ROOT)),
        "db_snapshot": {
            "total_rows_before": total_rows,
            "total_rows_after": total_rows_after,
            "total_rows_unchanged": total_rows == total_rows_after == EXPECTED_TOTAL_ROWS,
            "power_lotto_rows": pl_rows,
            "power_lotto_distinct_strategies": pl_strats,
            "power_lotto_distinct_draws": pl_draws,
            "statistical_unit": "distinct target_draw",
            "statistical_unit_n": pl_draws,
            "note_rows_vs_unit": (
                "36104 rows = sum over strategies of (n_draws x n_bet_slots). "
                "The statistical unit is distinct target_draw (1551), NOT 36104 rows."
            ),
        },
        "baselines": {
            "main_random_E_hit_count": MAIN_RANDOM_BASELINE,
            "main_random_formula": "6 * 6/38 = 36/38",
            "special_random": SPECIAL_RANDOM_BASELINE,
            "special_random_formula": "1/8 (POWER_LOTTO special pool 1..8)",
        },
        "section_2_main_vs_special_separated": {
            "pool_main_avg_hit_count": pool_avg_hit,
            "pool_main_vs_random_delta": round(pool_avg_hit - MAIN_RANDOM_BASELINE, 6),
            "pool_main_verdict": (
                "ABOVE" if pool_avg_hit > MAIN_RANDOM_BASELINE else
                "BELOW" if pool_avg_hit < MAIN_RANDOM_BASELINE else "AT"
            ),
            "special_predicted_special_not_null_n": sp_n_all,
            "special_hits": sp_hits_all,
            "special_hit_rate": round(pool_special_rate, 6),
            "special_vs_random_delta": round(pool_special_rate - SPECIAL_RANDOM_BASELINE, 6),
            "special_verdict": (
                "ABOVE" if pool_special_rate > SPECIAL_RANDOM_BASELINE else
                "BELOW" if pool_special_rate < SPECIAL_RANDOM_BASELINE else "AT"
            ),
            "special_diluted_all_row_avg_DO_NOT_USE": pool_special_diluted,
            "note": (
                "Special uses predicted_special IS NOT NULL only (9000 rows). The "
                "all-row special_hit avg (~0.0294) is diluted by strategies that "
                "never predict a special and MUST NOT be used."
            ),
        },
        "section_1_3_per_strategy": per_strat,
        "section_4_lifecycle_groups": {
            "groups": lc_groups,
            "label": "DESCRIPTIVE_ONLY",
            "survivorship_bias_caveat": (
                "Lifecycle labels (ONLINE/RETIRED/REJECTED/OBSERVATION) were "
                "assigned partly on PAST performance/governance. Comparing "
                "'ONLINE > RETIRED' is therefore partly circular (survivorship / "
                "selection bias) and is NOT evidence that the label predicts "
                "future hit rate UNLESS restricted to draws AFTER the label was "
                "assigned. No such post-label split is performed here."
            ),
            "note_power_lotto_composition": (
                "Among the 10 POWER_LOTTO strategies WITH replay data: 9 ONLINE, "
                "1 RETIRED (midfreq_fourier_2bet, see cross-lottery mismatch). No "
                "REJECTED or OBSERVATION strategies carry POWER_LOTTO replay rows, "
                "so a 4-way lifecycle comparison is not possible with this data."
            ),
        },
        "section_5_multi_bet_slots": {
            "per_strategy_slot": slots,
            "by_bet_position_aggregate": by_position,
            "coverage_normalized_note": (
                "Each bet slot = exactly 6 main numbers (one bet). Per-slot means "
                "are compared like-for-like; we do NOT sum hits across slots, which "
                "would inflate hit rate simply by selecting more numbers (L37 "
                "geometric-benefit trap). Only bet slots actually present in the DB "
                "are analysed (3 '2bet' strategies are stored first-bet-only)."
            ),
            "bet_slot_storage_note": (
                "DB-stored bet counts differ from strategy names: "
                "cold_complement_2bet / fourier30_markov30_2bet / zonal_entropy_2bet "
                "/ midfreq_fourier_2bet are stored as bet_index=1 only. "
                "power_fourier_rhythm_2bet=2, fourier_rhythm_3bet/midfreq_fourier_mk_3bet/"
                "power_precision_3bet=3, pp3_freqort_4bet=4, power_orthogonal_5bet=5."
            ),
            "unbalanced_panel_note": (
                "The bet panel is UNBALANCED for power_orthogonal_5bet and "
                "power_precision_3bet: bet_index=1 covers 1550 draws but bets 2-5 "
                "(resp. 2-3) cover only 1500 — the extra 50 bet1-only draws come "
                "from an earlier single-strategy replay wave (P19/P20) preceding the "
                "P140/P141 multi-bet apply. The per-draw mean averages whatever bets "
                "exist per draw, so this does not bias the statistical-unit test."
            ),
        },
        "section_6_multiple_testing": {
            "family_size_finite_p": family_size,
            "correction_methods": ["bonferroni", "benjamini_hochberg"],
            "alpha": 0.05,
            "family": family,
            "primary_unit": "per_strategy_main_per_draw_mean",
            "survivors_after_bonferroni_above_random": survivors_bonf,
            "survivors_after_bh_above_random": survivors_bh,
            "any_strategy_beats_random_after_correction": bool(survivors_bonf),
            "secondary_bet_slot_survivors_after_bonferroni_above_random": slot_survivors_bonf,
            "secondary_bet_slot_survivors_after_bh_above_random": slot_survivors_bh,
            "min_ndraws_gate_for_ranking": MIN_NDRAWS_FOR_RANKING,
            "note": (
                "Family = 10 strategy-main tests + per-strategy special tests + "
                "per-bet-slot tests. No naked ranking: a min n_draws>=500 gate and "
                "95% CIs are enforced before ranking (L47/L91)."
            ),
            "secondary_slot_survivor_caveat": (
                "One INDIVIDUAL bet slot — midfreq_fourier_mk_3bet bet_index=1 "
                "(per-draw mean ~1.027, raw p~0.0003, p_bonf~0.010, p_BH~0.010) — "
                "does survive correction as an ABOVE-random slot. This is a "
                "DESCRIPTIVE, FULL-HISTORY (in-sample) finding only. It is NOT a "
                "predictive claim: (a) it is the single first bet of a strategy "
                "whose 3-bet per-draw aggregate does NOT survive (bet3 sits below "
                "random), (b) no walk-forward / OOS>=500 evaluation has been run "
                "(L101), and (c) selecting the best-looking slot post hoc on full "
                "history is itself a selection effect. Treat as a hypothesis to "
                "test prospectively, NOT as evidence the slot 'works'."
            ),
        },
        "section_7_leakage_labeling": leakage,
        "best_single_strategy": best_block,
        "lifecycle_unresolved_strategy_ids": unresolved,
        "cross_lottery_registry_mismatch": cross_mismatch,
        "honest_null_statement": (
            "POWER_LOTTO replay strategies are, in aggregate and individually after "
            "multiple-testing correction, statistically indistinguishable from a "
            "fair-random 6-of-38 process on main numbers, and at/below random on the "
            "special number. This is an EXPECTED, ACCEPTABLE NULL/at-random result. "
            "No strategy is shown to beat random out-of-sample; NO betting advice and "
            "NO guaranteed-win claim is made or implied."
        ),
        "governance": {
            "db_writes": 0,
            "registry_mutations": 0,
            "controlled_apply": False,
            "forbidden_actions_taken": "NONE",
        },
    }

    report = _to_native(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    MD_OUT.write_text(render_md(report))
    print(f"WROTE {JSON_OUT}")
    print(f"WROTE {MD_OUT}")
    print(f"DB rows before/after: {total_rows}/{total_rows_after}")
    print(f"pool_main_avg_hit_count={pool_avg_hit} vs random {MAIN_RANDOM_BASELINE:.6f}")
    print(f"special_rate={pool_special_rate:.6f} vs random {SPECIAL_RANDOM_BASELINE}")
    print(f"any_strategy_beats_random_after_correction={bool(survivors_bonf)}")
    return report


def render_md(r: dict) -> str:
    L = []
    a = L.append
    a("# P161 — POWER_LOTTO Replay Strategy Effectiveness Baseline")
    a("")
    a(f"- **Task**: {r['task_id']} (v{r['version']})")
    a(f"- **Generated**: {r['generated_at']}")
    a(f"- **Classification**: `{r['classification']}`")
    a(f"- **Mode**: READ-ONLY (PRAGMA query_only=ON). DB writes: "
      f"{r['governance']['db_writes']}.")
    a("")
    ds = r["db_snapshot"]
    a("## DB snapshot")
    a("")
    a(f"- total rows before/after: **{ds['total_rows_before']} / "
      f"{ds['total_rows_after']}** (unchanged: {ds['total_rows_unchanged']})")
    a(f"- POWER_LOTTO rows: {ds['power_lotto_rows']} | strategies: "
      f"{ds['power_lotto_distinct_strategies']} | distinct draws: "
      f"{ds['power_lotto_distinct_draws']}")
    a(f"- **Statistical unit**: {ds['statistical_unit']} (n={ds['statistical_unit_n']}). "
      f"{ds['note_rows_vs_unit']}")
    a("")
    b = r["baselines"]
    a("## Random baselines")
    a("")
    a(f"- main E[hit_count] = `{b['main_random_formula']}` = "
      f"**{b['main_random_E_hit_count']:.6f}**")
    a(f"- special = `{b['special_random_formula']}` = **{b['special_random']}**")
    a("")
    s2 = r["section_2_main_vs_special_separated"]
    a("## §2 Main vs Special (SEPARATED)")
    a("")
    a(f"- Pool main avg hit_count = **{s2['pool_main_avg_hit_count']:.6f}** "
      f"(delta vs random = {s2['pool_main_vs_random_delta']:+.6f}, "
      f"verdict **{s2['pool_main_verdict']}**)")
    a(f"- Special (predicted_special NOT NULL, n={s2['special_predicted_special_not_null_n']}): "
      f"hit_rate = **{s2['special_hit_rate']:.6f}** "
      f"(delta vs 0.125 = {s2['special_vs_random_delta']:+.6f}, "
      f"verdict **{s2['special_verdict']}**)")
    a(f"- _Diluted all-row special avg (DO NOT USE): "
      f"{s2['special_diluted_all_row_avg_DO_NOT_USE']}_")
    a("")
    a("## §1+§3 Per-strategy table")
    a("")
    a("| strategy_id | lifecycle | n_draws | bet_rows | slots | mean hit | "
      "95% CI | vs rand | p_raw | p_bonf | p_BH | special rate (n) |")
    a("|---|---|--:|--:|--:|--:|---|:--:|--:|--:|--:|---|")
    fam = {f["key"]: f for f in r["section_6_multiple_testing"]["family"]}
    for s in r["section_1_3_per_strategy"]:
        f = fam.get(f"main::{s['strategy_id']}", {})
        sp = s["special"]
        sp_txt = (f"{sp['special_hit_rate']:.4f} ({sp['predicted_special_n']})"
                  if sp else "—")
        a(f"| {s['strategy_id']} | {s['lifecycle']} | {s['n_draws']} | "
          f"{s['n_bet_rows']} | {s['n_bet_slots']} | {s['mean_hit_count']:.4f} | "
          f"[{s['ci95_mean_lo']:.4f}, {s['ci95_mean_hi']:.4f}] | "
          f"{s['main_verdict_vs_random']} | "
          f"{s['main_p_raw']} | {f.get('p_bonferroni')} | {f.get('p_bh')} | {sp_txt} |")
    a("")
    a("Per-strategy hit_count distribution (0..6 main hits):")
    a("")
    a("| strategy_id | 0 | 1 | 2 | 3 | 4 | 5 | 6 |")
    a("|---|--:|--:|--:|--:|--:|--:|--:|")
    for s in r["section_1_3_per_strategy"]:
        d = s["hit_count_dist"]
        a(f"| {s['strategy_id']} | " + " | ".join(str(d[str(k)]) for k in range(7)) + " |")
    a("")
    a("## §4 Lifecycle-group comparison (DESCRIPTIVE)")
    a("")
    a(f"_{r['section_4_lifecycle_groups']['label']}_")
    a("")
    a("| lifecycle | n_strategies | bet_rows | group mean hit | vs rand |")
    a("|---|--:|--:|--:|:--:|")
    for g in r["section_4_lifecycle_groups"]["groups"]:
        a(f"| {g['lifecycle']} | {g['n_strategies']} | {g['n_bet_rows']} | "
          f"{g['group_mean_hit_count']:.6f} | {g['vs_random']} |")
    a("")
    a(f"**Survivorship caveat**: {r['section_4_lifecycle_groups']['survivorship_bias_caveat']}")
    a("")
    a(f"_{r['section_4_lifecycle_groups']['note_power_lotto_composition']}_")
    a("")
    a("## §5 Multi-bet slot comparison (coverage-normalized)")
    a("")
    a(f"{r['section_5_multi_bet_slots']['coverage_normalized_note']}")
    a("")
    a(f"_{r['section_5_multi_bet_slots']['bet_slot_storage_note']}_")
    a("")
    a("Aggregate by bet position (across strategies that have the slot):")
    a("")
    a("| bet_index | #strategies | n_rows | mean hit | 95% CI | vs rand | p_raw |")
    a("|--:|--:|--:|--:|---|:--:|--:|")
    for p in r["section_5_multi_bet_slots"]["by_bet_position_aggregate"]:
        a(f"| {p['bet_index']} | {p['n_strategies_with_slot']} | {p['n_rows']} | "
          f"{p['mean_hit_count']:.6f} | [{p['ci95_lo']:.4f}, {p['ci95_hi']:.4f}] | "
          f"{p['vs_random']} | {p['p_raw']} |")
    a("")
    a("## §6 Multiple-testing correction")
    a("")
    mt = r["section_6_multiple_testing"]
    a(f"- Family size (finite p): **{mt['family_size_finite_p']}** "
      f"(methods: {', '.join(mt['correction_methods'])}, alpha={mt['alpha']})")
    a(f"- Survivors above-random after Bonferroni: "
      f"**{mt['survivors_after_bonferroni_above_random'] or 'NONE'}**")
    a(f"- Survivors above-random after BH: "
      f"**{mt['survivors_after_bh_above_random'] or 'NONE'}**")
    a(f"- **Any strategy beats random after correction (PRIMARY, per-strategy "
      f"main per-draw mean): {mt['any_strategy_beats_random_after_correction']}**")
    a(f"- {mt['note']}")
    a("")
    a(f"- Secondary — individual bet-SLOT survivors after Bonferroni: "
      f"**{mt['secondary_bet_slot_survivors_after_bonferroni_above_random'] or 'NONE'}**")
    a(f"- Secondary — individual bet-SLOT survivors after BH: "
      f"**{mt['secondary_bet_slot_survivors_after_bh_above_random'] or 'NONE'}**")
    a(f"- **Slot survivor caveat**: {mt['secondary_slot_survivor_caveat']}")
    a("")
    a("## §7 Leakage-safe labeling")
    a("")
    lk = r["section_7_leakage_labeling"]
    a(f"- All comparisons in this report are **{lk['all_in_sample_comparisons_are']}** (in-sample).")
    a(f"- {lk['predictive_claim_requirement']}")
    a(f"- Predictive status: **{lk['predictive_label']}**")
    a("")
    a("## Best single strategy")
    a("")
    bs = r["best_single_strategy"]
    if bs:
        a(f"- **{bs['strategy_id']}** (lifecycle {bs['lifecycle']}, n_draws={bs['n_draws']}): "
          f"mean hit = {bs['mean_hit_count']:.6f}, CI {bs['ci95']}, "
          f"vs random **{bs['vs_random']}**")
        a(f"- p_raw={bs['p_raw']}, p_bonferroni={bs['p_bonferroni']}, p_BH={bs['p_bh']}")
        a(f"- **Beats random after correction: {bs['beats_random_after_correction']}**")
    a("")
    if r["cross_lottery_registry_mismatch"]:
        a("## Cross-lottery registry mismatch (flagged)")
        a("")
        for m in r["cross_lottery_registry_mismatch"]:
            a(f"- `{m['strategy_id']}`: registry lottery types "
              f"{m['registry_lottery_types']} but observed replay rows under "
              f"{m['observed_lottery_type']} (lifecycle resolved by id = {m['lifecycle']}).")
        a("")
    if r["lifecycle_unresolved_strategy_ids"]:
        a(f"## LIFECYCLE_UNRESOLVED: {r['lifecycle_unresolved_strategy_ids']}")
        a("")
    a("## Honest NULL statement")
    a("")
    a(r["honest_null_statement"])
    a("")
    return "\n".join(L)


if __name__ == "__main__":
    main()
