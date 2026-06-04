#!/usr/bin/env python3
"""
p231b_powerlotto_first_zone_backward_oos_dryrun.py
==================================================
P231B — POWER_LOTTO First-Zone Backward-OOS Code-Only Artifact Dry-Run.

Backward-OOS falsification of the single P231A POWER_LOTTO first-zone candidate
`midfreq_fourier_mk_3bet / POWER_LOTTO` over older POWER_LOTTO history that is
strictly earlier than the candidate's existing 1,500-draw replay window.

Mirrors the P230B1 (DAILY_539) pattern exactly.

HARD GOVERNANCE RULES (this script):
  - READ-ONLY on the production DB. Connection opened with `mode=ro` (SQLite
    read-only URI) so DB writes are physically impossible.
  - Writes ONLY artifact files (JSON + Markdown) under outputs/research/.
  - Does NOT insert/update/delete `strategy_prediction_replays` rows.
  - Does NOT mutate the registry, production state, or recommendation logic.
  - Reuses the EXISTING `MidFreqFourierMk3BetAdapter` (P47 wrapper) + the causal
    slice convention `history = all_draws[:target_idx]`.

BET SEMANTICS (mirrors P230B1's "do not invent" discipline):
  - Only the deterministic bet-1 (bet_index=1) is generated. bet-1 of
    `midfreq_fourier_mk_3bet` is the composite blend
    (MidFreq×0.3 + Fourier×0.4 + Markov×0.3) returned by the P47 adapter.
  - The in-window DB stores 3 bets (bet_index 1,2,3), but bets 2 & 3 are NOT
    produced by the deterministic adapter and are NOT invented here — exactly as
    P230B1 refused to invent the Fourier bet-2.
  - Primary metric is first-zone hit_count of bet-1 vs the random baseline
    36/38 = 0.947368 (= bet-1 random expectation).

SECOND ZONE (special, 1-8):
  - special_hit is reported SEPARATELY ONLY (display), baseline 1/8 = 0.125.
  - It NEVER enters first-zone scoring or the final classification.

LEAKAGE GUARD:
  - POWER_LOTTO draws sorted by (date ASC, CAST(draw AS INTEGER) ASC).
  - For each target index i, history = all_draws[:i] (STRICTLY before).
  - history_cutoff_draw = ORDINAL PREDECESSOR (all_draws[i-1]["draw"]),
    NOT numeric target_draw-1 (draw IDs reset at ROC-year boundaries).
  - Deterministic min_history warmup (adapter min_history = 30).

This is a DRY-RUN ARTIFACT ONLY. NOT betting advice, NOT a guaranteed predictive
edge, and confers NO promotion / production / DB-write / registry authorization.

Usage:
  .venv/bin/python3 scripts/p231b_powerlotto_first_zone_backward_oos_dryrun.py
  .venv/bin/python3 scripts/p231b_powerlotto_first_zone_backward_oos_dryrun.py --limit 200
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ─── Fixed candidate identity (pre-registered by P231A; no other strategy/lottery) ──
STRATEGY_ID = "midfreq_fourier_mk_3bet"
LOTTERY_TYPE = "POWER_LOTTO"
BET_INDEX = 1  # deterministic bet-1 only; bets 2,3 not in adapter, not invented

# ─── Baselines (era-invariant) ────────────────────────────────────────────────
# First zone: pick(6) over pool(38), draw(6) -> expected hits/bet = 6*6/38 = 36/38.
FIRST_ZONE_BASELINE = 36.0 / 38.0          # 0.9473684210526315
# Second zone (display-only): special is 1 of 8 -> 1/8.
SPECIAL_BASELINE = 1.0 / 8.0               # 0.125

DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DATE_TAG = "20260604"

# Conservative warmup alternative reported alongside adapter-min (informational only).
CONSERVATIVE_WARMUP = 100


# ─── Read-only DB helpers ─────────────────────────────────────────────────────

def _connect_ro(db_path: Path) -> sqlite3.Connection:
    """Open the DB strictly read-only. Any write attempt raises OperationalError."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_power_draws(db_path: Path) -> List[dict]:
    """Load all POWER_LOTTO draws, chronologically ascending. READ-ONLY.

    Includes `special` (second zone 1-8) so the adapter's special predictor and
    the display-only special_hit metric can be computed.
    """
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers, special FROM draws "
            "WHERE lottery_type = 'POWER_LOTTO' "
            "ORDER BY date ASC, CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    draws: List[dict] = []
    for row in rows:
        raw = row["numbers"]
        nums = json.loads(raw) if isinstance(raw, str) else raw
        sp = row["special"]
        draws.append({
            "draw": str(row["draw"]),
            "date": row["date"],
            "numbers": [int(n) for n in nums],
            "special": int(sp) if sp is not None else None,
        })
    return draws


def candidate_window_min_draw(db_path: Path) -> Optional[int]:
    """Min existing replay target_draw for the candidate (defines backward boundary)."""
    conn = _connect_ro(db_path)
    try:
        val = conn.execute(
            "SELECT MIN(CAST(target_draw AS INTEGER)) FROM strategy_prediction_replays "
            "WHERE lottery_type = ? AND strategy_id = ?",
            (LOTTERY_TYPE, STRATEGY_ID),
        ).fetchone()[0]
    finally:
        conn.close()
    return int(val) if val is not None else None


def in_window_reference(db_path: Path) -> dict:
    """Read-only in-window reference means for context (NOT used as the gate)."""
    conn = _connect_ro(db_path)
    try:
        strat = conn.execute(
            "SELECT COUNT(*) n, AVG(hit_count) m, AVG(special_hit) s "
            "FROM strategy_prediction_replays WHERE lottery_type=? AND strategy_id=?",
            (LOTTERY_TYPE, STRATEGY_ID),
        ).fetchone()
        bet1 = conn.execute(
            "SELECT COUNT(*) n, AVG(hit_count) m, AVG(special_hit) s "
            "FROM strategy_prediction_replays WHERE lottery_type=? AND strategy_id=? AND bet_index=1",
            (LOTTERY_TYPE, STRATEGY_ID),
        ).fetchone()
    finally:
        conn.close()
    return {
        "strategy_level_pooled": {"n": strat["n"], "mean_hit_count": strat["m"], "mean_special_hit": strat["s"]},
        "bet1_only": {"n": bet1["n"], "mean_hit_count": bet1["m"], "mean_special_hit": bet1["s"]},
    }


def total_replay_rows(db_path: Path) -> int:
    conn = _connect_ro(db_path)
    try:
        return conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    finally:
        conn.close()


# ─── Provenance ───────────────────────────────────────────────────────────────

def provenance_hash(strategy_id: str, target_draw: str, numbers: List[int]) -> str:
    payload = f"{strategy_id}|{target_draw}|{sorted(numbers)}"
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


# ─── Backward-OOS generation (artifact rows only — NO DB write) ───────────────

def generate_backward_rows(
    all_draws: List[dict],
    window_min_draw: int,
    adapter,
    min_history: int,
    limit: Optional[int] = None,
) -> Tuple[List[dict], dict]:
    """Produce backward-OOS bet-1 prediction rows for the candidate.

    A draw is a backward target iff CAST(draw AS INT) < window_min_draw.
    The first `min_history` draws are skipped (deterministic warmup).
    Causal slice: history = all_draws[:i] (strictly before target i).
    Returns (rows, inventory_summary). NO DB writes occur here.
    """
    backward_indices = [
        i for i, d in enumerate(all_draws) if int(d["draw"]) < window_min_draw
    ]
    n_backward_total = len(backward_indices)

    replayable_indices = [i for i in backward_indices if i >= min_history]
    n_warmup_skipped = n_backward_total - len(replayable_indices)
    n_replayable_true = len(replayable_indices)

    # Informational: how many remain under a conservative 100-draw warmup.
    n_replayable_conservative = len([i for i in backward_indices if i >= CONSERVATIVE_WARMUP])

    if limit is not None:
        replayable_indices = replayable_indices[:limit]

    rows: List[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for i in replayable_indices:
        target = all_draws[i]
        history = all_draws[:i]  # strictly before — causal slice
        history_cutoff_draw = history[-1]["draw"] if history else None
        prediction_cutoff_date = history[-1]["date"] if history else None

        replay_status = "PREDICTED"
        reject_reason = None
        predicted_numbers = None
        predicted_special = None
        hit_numbers = None
        hit_count = 0
        special_hit = 0
        prov = None

        try:
            numbers, special = adapter.get_one_bet(history, LOTTERY_TYPE)
            predicted_numbers = numbers
            predicted_special = special
            actual = target["numbers"]
            hits = sorted(set(numbers) & set(actual))
            hit_numbers = hits
            hit_count = len(hits)  # FIRST ZONE ONLY
            actual_sp = target.get("special")
            if actual_sp is not None and special is not None:
                special_hit = 1 if special == actual_sp else 0
            prov = provenance_hash(STRATEGY_ID, target["draw"], numbers)
        except ValueError as exc:
            replay_status = "INSUFFICIENT_HISTORY"
            reject_reason = str(exc)
        except AssertionError as exc:
            replay_status = "INVALID_OUTPUT"
            reject_reason = str(exc)

        rows.append({
            "lottery_type": LOTTERY_TYPE,
            "target_draw": target["draw"],
            "target_date": target["date"],
            "strategy_id": STRATEGY_ID,
            "bet_index": BET_INDEX,
            "history_cutoff_draw": history_cutoff_draw,
            "prediction_cutoff_date": prediction_cutoff_date,
            "predicted_numbers": predicted_numbers,
            "predicted_special": predicted_special,
            "actual_numbers": target["numbers"],
            "actual_special": target.get("special"),
            "hit_numbers": hit_numbers,
            "hit_count": hit_count,          # first-zone only
            "special_hit": special_hit,      # second zone — display only
            "replay_status": replay_status,
            "reject_reason": reject_reason,
            "provenance_hash": prov,
            "dry_run": 1,
            "generated_at": now,
        })

    inventory = {
        "power_total_draws": len(all_draws),
        "window_min_draw": window_min_draw,
        "backward_total_draws": n_backward_total,
        "min_history_warmup": min_history,
        "warmup_skipped": n_warmup_skipped,
        "replayable_backward_targets": n_replayable_true,
        "replayable_under_conservative_100_warmup": n_replayable_conservative,
        "targets_generated": len(replayable_indices),
        "first_backward_replayable": all_draws[replayable_indices[0]]["draw"] if replayable_indices else None,
        "first_backward_replayable_date": all_draws[replayable_indices[0]]["date"] if replayable_indices else None,
        "last_backward_target": all_draws[backward_indices[-1]]["draw"] if backward_indices else None,
        "last_backward_target_date": all_draws[backward_indices[-1]]["date"] if backward_indices else None,
        "limit_applied": limit,
    }
    return rows, inventory


# ─── Statistics (pure-Python; replicates P230B1 methodology) ──────────────────

def _norm_sf(z: float) -> float:
    """One-sided upper-tail p-value of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _pop_std(xs: List[float], mean: float) -> float:
    if not xs:
        return 0.0
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    return math.sqrt(var)


def summarize(values: List[int], baseline: float) -> dict:
    """Mean / CI / one-sided p vs baseline for a set of integer counts."""
    n = len(values)
    if n == 0:
        return {"n": 0}
    mean = _mean([float(v) for v in values])
    std = _pop_std([float(v) for v in values], mean)
    se = std / math.sqrt(n) if n > 0 else 0.0
    z = (mean - baseline) / se if se > 0 else 0.0
    p_one_sided = _norm_sf(z) if se > 0 else None
    return {
        "n": n,
        "mean": mean,
        "std": std,
        "se": se,
        "ci95": [mean - 1.96 * se, mean + 1.96 * se],
        "ci_crosses_baseline": (mean - 1.96 * se) <= baseline <= (mean + 1.96 * se),
        "z_vs_baseline": z,
        "p_one_sided_vs_baseline": p_one_sided,
        "direction": "above" if mean > baseline else ("below" if mean < baseline else "equal"),
        "distribution": {str(k): sum(1 for v in values if v == k) for k in range(0, max(values) + 1)},
        "max": max(values),
    }


def block_stability(hit_counts: List[int], baseline: float, block_size: int) -> dict:
    blocks = []
    for start in range(0, len(hit_counts), block_size):
        chunk = hit_counts[start:start + block_size]
        m = _mean([float(h) for h in chunk])
        blocks.append({"index": len(blocks) + 1, "n": len(chunk), "mean": m,
                       "direction": "above" if m > baseline else "below"})
    means = [b["mean"] for b in blocks]
    above = sum(1 for b in blocks if b["mean"] > baseline)
    return {
        "block_size": block_size,
        "n_blocks": len(blocks),
        "blocks_above_baseline": above,
        "majority_above_baseline": above > len(blocks) / 2,
        "block_mean_sd": _pop_std(means, _mean(means)) if means else 0.0,
        "worst_block_mean": min(means) if means else None,
        "best_block_mean": max(means) if means else None,
        "blocks": blocks,
    }


def robustness(hit_counts: List[int], baseline: float, block_size: int = 100) -> dict:
    """Exclude high-hit (>=3) rows, and exclude the strongest full block."""
    excl_hi = [h for h in hit_counts if h < 3]
    mean_excl_hi = _mean([float(h) for h in excl_hi]) if excl_hi else 0.0

    full_blocks = [hit_counts[s:s + block_size] for s in range(0, len(hit_counts), block_size)
                   if len(hit_counts[s:s + block_size]) == block_size]
    if full_blocks:
        block_means = [_mean([float(h) for h in b]) for b in full_blocks]
        strongest_idx = block_means.index(max(block_means))
        remaining = [h for j, b in enumerate(full_blocks) if j != strongest_idx for h in b]
        mean_excl_strongest = _mean([float(h) for h in remaining]) if remaining else 0.0
    else:
        strongest_idx = None
        mean_excl_strongest = None

    return {
        "exclude_hit_ge3": {
            "n_removed": len(hit_counts) - len(excl_hi),
            "n": len(excl_hi),
            "mean": mean_excl_hi,
            "at_or_above_baseline": mean_excl_hi >= baseline,
        },
        "exclude_strongest_block": {
            "block_size": block_size,
            "strongest_block_index_1based": (strongest_idx + 1) if strongest_idx is not None else None,
            "mean": mean_excl_strongest,
            "at_or_above_baseline": (mean_excl_strongest >= baseline) if mean_excl_strongest is not None else None,
        },
    }


def year_splits(rows: List[dict], baseline: float) -> dict:
    """Per-calendar-year first-zone stability (backward window is 2008-2011)."""
    by_year: Dict[str, List[int]] = {}
    for r in rows:
        if r["replay_status"] != "PREDICTED":
            continue
        year = r["target_date"].split("/")[0]
        by_year.setdefault(year, []).append(r["hit_count"])
    return {y: summarize(v, baseline) for y, v in sorted(by_year.items())}


# ─── Classification (reflects ACTUAL result; never presumes success) ──────────

def classify(overall: dict, blocks: dict, robust: dict, baseline: float) -> Tuple[str, str]:
    """Map the first-zone outcome to a P231B final classification + rationale.

    Decision order (honest, falsification-oriented):
      1. mean < baseline                       -> BELOW_BASELINE
      2. CI crosses baseline & not significant -> NULL
      3. mean > baseline & all gates clean     -> NEEDS_MORE_OOS (backward cannot confirm deployment)
      4. mean > baseline & a gate fails        -> WEAK_OBSERVATION_ONLY
    """
    mean = overall["mean"]
    p = overall["p_one_sided_vs_baseline"]
    significant = (p is not None) and (p < 0.05)

    if mean < baseline:
        return ("P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_BELOW_BASELINE",
                f"backward-OOS first-zone mean {mean:.6f} < baseline {baseline:.6f} -> historical-artifact direction")

    if overall["ci_crosses_baseline"] and not significant:
        return ("P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL",
                f"backward-OOS mean {mean:.6f} ~ baseline {baseline:.6f} (CI crosses, one-sided p="
                f"{p:.4f} not significant) -> NULL")

    primary_block = blocks.get("100", next(iter(blocks.values())))
    clean = (
        not overall["ci_crosses_baseline"]
        and significant
        and primary_block["majority_above_baseline"]
        and robust["exclude_hit_ge3"]["at_or_above_baseline"]
        and bool(robust["exclude_strongest_block"]["at_or_above_baseline"])
    )
    if clean:
        return ("P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NEEDS_MORE_OOS",
                f"backward-OOS mean {mean:.6f} > baseline, block-stable & robust, but backward history "
                f"cannot confirm future deployment -> NEEDS_MORE_OOS")
    return ("P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_WEAK_OBSERVATION_ONLY",
            f"backward-OOS mean {mean:.6f} >= baseline but weak (CI crosses / not significant / a block or "
            f"robustness check fails) -> WEAK_OBSERVATION_ONLY")


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run(db_path: Path, limit: Optional[int] = None) -> dict:
    """Full read-only dry-run. Returns the result dict. NO DB writes."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTER_MAP

    adapter = WAVE4_ADAPTER_MAP[STRATEGY_ID]
    min_history = adapter.meta.min_history

    rows_before = total_replay_rows(db_path)
    all_draws = load_power_draws(db_path)
    window_min = candidate_window_min_draw(db_path)
    if window_min is None:
        return {"final_classification": "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_BLOCKED_ACTUAL_STATE_MISMATCH",
                "blocked_reason": "no existing candidate replay rows; backward boundary undefined"}

    ref = in_window_reference(db_path)
    rows, inventory = generate_backward_rows(all_draws, window_min, adapter, min_history, limit=limit)

    predicted = [r for r in rows if r["replay_status"] == "PREDICTED"]
    hit_counts = [r["hit_count"] for r in predicted]
    special_hits = [r["special_hit"] for r in predicted]

    rows_after = total_replay_rows(db_path)  # must equal rows_before (read-only proof)

    if not hit_counts:
        return {
            "final_classification": "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_BLOCKED_ACTUAL_STATE_MISMATCH",
            "blocked_reason": "no PREDICTED backward rows produced",
            "inventory": inventory,
            "db_rows_before": rows_before,
            "db_rows_after": rows_after,
        }

    baseline = FIRST_ZONE_BASELINE
    overall = summarize(hit_counts, baseline)
    blocks = {str(bs): block_stability(hit_counts, baseline, bs) for bs in (50, 100, 150)}
    robust = robustness(hit_counts, baseline, block_size=100)
    years = year_splits(predicted, baseline)
    classification, rationale = classify(overall, blocks, robust, baseline)

    # Second zone (special) — DISPLAY ONLY, never in classification.
    special_overall = summarize(special_hits, SPECIAL_BASELINE)

    return {
        "phase": "P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN",
        "date": "2026-06-04",
        "execution_status": "DRYRUN_EXECUTED_OK",
        "db_write_performed": rows_after != rows_before,
        "db_rows_before": rows_before,
        "db_rows_after": rows_after,
        "candidate": {
            "strategy_id": STRATEGY_ID, "lottery_type": LOTTERY_TYPE, "bet_index": BET_INDEX,
            "zone": "first_zone (1-38, pick 6)", "prior_status": "CANDIDATE_NEEDS_MORE_OOS (P223B)",
            "recorded_bet_semantics": (
                "deterministic bet-1 = composite blend MidFreq*0.3 + Fourier*0.4 + Markov*0.3 (P47 adapter); "
                "in-window bets 2,3 are NOT in the deterministic adapter and are NOT invented (P230B1 discipline)"),
        },
        "determinism": "adapter has no RNG (numpy argsort); fully reproducible, no seed required",
        "inventory": inventory,
        "first_zone_baseline": baseline,
        "first_zone_baseline_derivation": "pick(6)*draw(6)/pool(38) = 36/38 (era-invariant; bet-1 random expectation)",
        "in_window_reference": ref,
        "overall_first_zone": overall,
        "block_stability": blocks,
        "robustness": robust,
        "year_splits": years,
        "second_zone_display_only": {
            "note": "DISPLAY ONLY — special_hit never enters first-zone scoring or final classification",
            "baseline": SPECIAL_BASELINE,
            "summary": special_overall,
        },
        "interpretation_caveat": (
            "Backward-OOS is older-regime (2008-2011) robustness/falsification, NOT true future OOS. It can "
            "FALSIFY a candidate if below baseline, but cannot confirm deployment. The independent older slice "
            "(~312-382) is far smaller than DAILY_539's 4,265, so power is limited. Only deterministic bet-1 is "
            "tested. NOT betting advice, NOT a guaranteed edge."),
        "final_classification": classification,
        "classification_rationale": rationale,
        "authorization": {
            "db_write_backfill": "NOT AUTHORIZED (separate explicit DB-write authorization required)",
            "registry_production_recommendation": "NOT AUTHORIZED / unchanged",
            "second_zone_promotion": "NOT AUTHORIZED (display-only per P211A)",
            "strategy_promotion": "NOT AUTHORIZED regardless of outcome",
        },
    }


def _fmt(x, nd=6):
    if x is None:
        return "n/a"
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def write_markdown(result: dict, md_path: Path) -> None:
    o = result["overall_first_zone"]
    inv = result["inventory"]
    b = result["first_zone_baseline"]
    ref = result["in_window_reference"]
    sp = result["second_zone_display_only"]
    lines: List[str] = []
    A = lines.append
    A("# P231B — POWER_LOTTO First-Zone Backward-OOS Code-Only Dry-Run\n")
    A("**Date:** 2026-06-04 (Asia/Taipei)  ")
    A("**Task:** `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN`  ")
    A(f"**Classification:** `{result['final_classification']}`  ")
    A("**Status:** COMPLETE / CODE-ONLY / ZERO DB WRITE\n")
    A("> **Dry-run artifact only.** No DB write, no replay rows created, no registry/production/recommendation "
      "change, no promotion. Not betting advice and not a guaranteed predictive edge. Backward-OOS is older-regime "
      "robustness, **not** true future OOS, and cannot confirm deployment. Second zone is display-only (P211A).\n")

    A("## Methodology\n")
    A(f"- Candidate: `{STRATEGY_ID} / {LOTTERY_TYPE}`, **first zone**, deterministic **bet-1** "
      "(composite MidFreq×0.3 + Fourier×0.4 + Markov×0.3).")
    A("- In-window bets 2,3 are NOT in the deterministic P47 adapter and are **not invented** (P230B1 discipline).")
    A(f"- Reused `MidFreqFourierMk3BetAdapter` (`min_history={inv['min_history_warmup']}`) + causal slice "
      "`history = all_draws[:i]`.")
    A("- DB opened **read-only** (`mode=ro`); writes physically impossible. Artifacts only.")
    A("- Leakage guard: `history_cutoff_draw` = ordinal predecessor (`all_draws[i-1]`), not numeric `target_draw-1`.")
    A(f"- First-zone baseline = `{b:.6f}` (= 36/38). Second-zone baseline = `{sp['baseline']}` (= 1/8), display-only.")
    A(f"- Determinism: {result['determinism']}.\n")

    A("## Backward-OOS Inventory\n")
    A("| Field | Value |")
    A("|---|---|")
    A(f"| POWER_LOTTO total draws | {inv['power_total_draws']} |")
    A(f"| Candidate window min target_draw | {inv['window_min_draw']} |")
    A(f"| Backward total (strictly earlier) | {inv['backward_total_draws']} |")
    A(f"| Warmup skipped (min_history={inv['min_history_warmup']}) | {inv['warmup_skipped']} |")
    A(f"| **Replayable backward targets (adapter-min)** | **{inv['replayable_backward_targets']}** |")
    A(f"| Replayable under conservative 100-warmup | {inv['replayable_under_conservative_100_warmup']} |")
    A(f"| First replayable | {inv['first_backward_replayable']} @ {inv['first_backward_replayable_date']} |")
    A(f"| Last backward target | {inv['last_backward_target']} @ {inv['last_backward_target_date']} |")
    if inv.get("limit_applied") is not None:
        A(f"| ⚠ limit applied (dev subset) | {inv['limit_applied']} |")
    A("")

    A("## Overall First-Zone Result\n")
    A("| Metric | Backward-OOS (bet-1) | In-window bet-1 | In-window strategy-level (3-bet pooled) |")
    A("|---|---:|---:|---:|")
    A(f"| n | {o['n']} | {ref['bet1_only']['n']} | {ref['strategy_level_pooled']['n']} |")
    A(f"| mean first-zone hit | {_fmt(o['mean'])} | {_fmt(ref['bet1_only']['mean_hit_count'])} | "
      f"{_fmt(ref['strategy_level_pooled']['mean_hit_count'])} |")
    A(f"| baseline (36/38) | {_fmt(b)} | {_fmt(b)} | {_fmt(b)} |")
    A(f"| 95% CI | [{_fmt(o['ci95'][0])}, {_fmt(o['ci95'][1])}] | — | — |")
    A(f"| CI crosses baseline | {o['ci_crosses_baseline']} | — | — |")
    A(f"| z vs baseline | {_fmt(o['z_vs_baseline'])} | — | — |")
    A(f"| one-sided p vs baseline | {_fmt(o['p_one_sided_vs_baseline'])} | — | — |")
    A(f"| direction | {o['direction']} | above | above |")
    A(f"| hit distribution | `{o['distribution']}` | — | — |")
    A("")

    A("## Block Stability\n")
    A("| Block size | n blocks | above baseline | majority | block mean SD | worst | best |")
    A("|---|---:|---:|---|---:|---:|---:|")
    for bs in ("50", "100", "150"):
        bl = result["block_stability"][bs]
        A(f"| {bs} | {bl['n_blocks']} | {bl['blocks_above_baseline']} | {bl['majority_above_baseline']} | "
          f"{_fmt(bl['block_mean_sd'])} | {_fmt(bl['worst_block_mean'])} | {_fmt(bl['best_block_mean'])} |")
    A("")

    A("## Robustness\n")
    rob = result["robustness"]
    A("| Check | n | mean | at/above baseline |")
    A("|---|---:|---:|---|")
    eh = rob["exclude_hit_ge3"]
    A(f"| Exclude hit_count≥3 ({eh['n_removed']} removed) | {eh['n']} | {_fmt(eh['mean'])} | {eh['at_or_above_baseline']} |")
    es = rob["exclude_strongest_block"]
    A(f"| Exclude strongest {es['block_size']}-block (#{es['strongest_block_index_1based']}) | — | "
      f"{_fmt(es['mean'])} | {es['at_or_above_baseline']} |")
    A("")

    A("## Year Splits (backward window 2008-2011)\n")
    A("| Year | n | mean | direction | one-sided p |")
    A("|---|---:|---:|---|---:|")
    for y, e in result["year_splits"].items():
        A(f"| {y} | {e['n']} | {_fmt(e['mean'])} | {e['direction']} | {_fmt(e['p_one_sided_vs_baseline'])} |")
    A("")

    A("## Second Zone (special) — DISPLAY ONLY\n")
    so = sp["summary"]
    A("> Reported separately; **never** used in first-zone scoring or the final classification.\n")
    A("| Metric | Backward-OOS special |")
    A("|---|---:|")
    A(f"| n | {so['n']} |")
    A(f"| special_hit rate | {_fmt(so['mean'])} |")
    A(f"| baseline (1/8) | {_fmt(sp['baseline'])} |")
    A(f"| direction | {so['direction']} |")
    A(f"| one-sided p vs baseline | {_fmt(so['p_one_sided_vs_baseline'])} |")
    A("")

    A("## Decision\n")
    A(f"- **Final classification:** `{result['final_classification']}`")
    A(f"- **Rationale:** {result['classification_rationale']}")
    A(f"- DB write performed: **{result['db_write_performed']}** (rows {result['db_rows_before']} → {result['db_rows_after']}).")
    A(f"- Caveat: {result['interpretation_caveat']}")
    A("- DB-write/backfill, registry, production, recommendation change, second-zone promotion, and strategy "
      "promotion remain **NOT AUTHORIZED** regardless of outcome.\n")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> dict:
    parser = argparse.ArgumentParser(description="P231B POWER_LOTTO first-zone backward-OOS code-only dry-run")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--json-out", default=str(OUTPUT_DIR / f"p231b_powerlotto_first_zone_backward_oos_dryrun_{DATE_TAG}.json"))
    parser.add_argument("--md-out", default=str(OUTPUT_DIR / f"p231b_powerlotto_first_zone_backward_oos_dryrun_{DATE_TAG}.md"))
    parser.add_argument("--limit", type=int, default=None, help="dev subset: cap replayable backward targets")
    args = parser.parse_args(argv)

    result = run(Path(args.db_path), limit=args.limit)

    out_json = Path(args.json_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[P231B] JSON written: {out_json}")

    if result.get("execution_status") == "DRYRUN_EXECUTED_OK":
        write_markdown(result, Path(args.md_out))
        print(f"[P231B] Markdown written: {args.md_out}")

    print(f"[P231B] Classification: {result['final_classification']}")
    return result


if __name__ == "__main__":
    res = main()
    sys.exit(0 if res.get("execution_status") == "DRYRUN_EXECUTED_OK"
             or "BLOCKED" in res.get("final_classification", "") else 1)
