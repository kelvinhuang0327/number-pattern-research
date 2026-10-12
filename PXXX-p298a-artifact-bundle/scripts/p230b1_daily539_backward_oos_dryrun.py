#!/usr/bin/env python3
"""
p230b1_daily539_backward_oos_dryrun.py
======================================
P230B1 — DAILY_539 Backward-OOS Code-Only Artifact Dry-Run Generator

Generates backward-OOS replay PREDICTIONS for the single P224 survivor
`midfreq_fourier_2bet / DAILY_539` over older DAILY_539 history that is
strictly earlier than the candidate's existing 1,500-row replay window.

HARD GOVERNANCE RULES (this script):
  - READ-ONLY on the production DB. The DB connection is opened with
    `mode=ro` (SQLite read-only URI) so DB writes are physically impossible.
  - Writes ONLY artifact files (JSON + Markdown) under outputs/research/.
  - Does NOT insert/update/delete `strategy_prediction_replays` rows.
  - Does NOT mutate the registry, production state, or recommendation logic.
  - Reuses the EXISTING `MidfreqFourier2BetAdapter` (P31A wrapper) and the
    P31B causal-slice convention `history = all_draws[:target_idx]`.

LEAKAGE GUARD:
  - DAILY_539 draws are sorted by (date ASC, CAST(draw AS INTEGER) ASC).
  - For each target index `i`, `history = all_draws[:i]` (STRICTLY before).
  - `history_cutoff_draw` is the ORDINAL PREDECESSOR (all_draws[i-1]["draw"]),
    NOT numeric `target_draw - 1` (draw IDs reset at ROC-year boundaries,
    e.g. 110000313 -> 111000001).
  - Deterministic `min_history` warmup: the first 100 draws (insufficient
    history) are skipped, exactly as the adapter would reject them.

BET SEMANTICS:
  - Only bet-1 (bet_index=1) is generated. bet-1 of `midfreq_fourier_2bet`
    is PURE MidFreq (`predict_midfreq`); the Fourier bet-2 was never stored
    and is NOT invented here.

This is a DRY-RUN ARTIFACT ONLY. It is NOT betting advice, NOT a guaranteed
predictive edge, and confers NO promotion / production / P225 authorization.

Usage:
  python3 scripts/p230b1_daily539_backward_oos_dryrun.py
  python3 scripts/p230b1_daily539_backward_oos_dryrun.py --limit 200   # dev subset
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

# ─── Fixed candidate identity (no other strategy / lottery) ───────────────────
STRATEGY_ID = "midfreq_fourier_2bet"
LOTTERY_TYPE = "DAILY_539"
BET_INDEX = 1

# ─── Baselines / reference values (from P224, era-invariant) ──────────────────
# Theoretical random hypergeometric mean = pick(5) * draw(5) / pool(39) = 25/39.
P224_BASELINE = 0.6410256410256411
P224_MEAN = 0.6693333333333333
ALL_HISTORY_REFERENCE_BASELINE = 0.6251612903225806

DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DATE_TAG = "20260603"


# ─── Read-only DB helpers ─────────────────────────────────────────────────────

def _connect_ro(db_path: Path) -> sqlite3.Connection:
    """Open the DB strictly read-only. Any write attempt raises OperationalError."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def load_daily539_draws(db_path: Path) -> List[dict]:
    """Load all DAILY_539 draws, chronologically ascending. READ-ONLY."""
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT draw, date, numbers FROM draws "
            "WHERE lottery_type = 'DAILY_539' "
            "ORDER BY date ASC, CAST(draw AS INTEGER) ASC"
        ).fetchall()
    finally:
        conn.close()

    draws: List[dict] = []
    for row in rows:
        raw = row["numbers"]
        nums = json.loads(raw) if isinstance(raw, str) else raw
        draws.append({
            "draw": str(row["draw"]),
            "date": row["date"],
            "numbers": [int(n) for n in nums],
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
    """
    Produce backward-OOS prediction rows for the candidate.

    A draw is a backward target iff CAST(draw AS INT) < window_min_draw.
    The first `min_history` draws are skipped (deterministic warmup).

    Causal slice: history = all_draws[:i] (strictly before target i).
    Returns (rows, inventory_summary). NO DB writes occur here.
    """
    # Backward target indices: chronologically ordered, strictly earlier than window.
    backward_indices = [
        i for i, d in enumerate(all_draws)
        if int(d["draw"]) < window_min_draw
    ]
    n_backward_total = len(backward_indices)

    # Apply deterministic warmup: a target at ordinal index i needs i prior draws.
    replayable_indices = [i for i in backward_indices if i >= min_history]
    n_warmup_skipped = n_backward_total - len(replayable_indices)
    n_replayable_true = len(replayable_indices)  # true count before any dev limit

    if limit is not None:
        replayable_indices = replayable_indices[:limit]

    rows: List[dict] = []
    now = datetime.now(timezone.utc).isoformat()

    for i in replayable_indices:
        target = all_draws[i]
        history = all_draws[:i]  # strictly before — causal slice (P31B convention)
        # Ordinal predecessor cutoff (NOT numeric target_draw - 1).
        history_cutoff_draw = history[-1]["draw"] if history else None
        prediction_cutoff_date = history[-1]["date"] if history else None

        replay_status = "PREDICTED"
        reject_reason = None
        predicted_numbers = None
        hit_numbers = None
        hit_count = 0
        prov = None

        try:
            numbers, special = adapter.get_one_bet(history, LOTTERY_TYPE)
            predicted_numbers = numbers
            actual = target["numbers"]
            hits = sorted(set(numbers) & set(actual))
            hit_numbers = hits
            hit_count = len(hits)
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
            "predicted_special": None,  # DAILY_539 has no special
            "actual_numbers": target["numbers"],
            "hit_numbers": hit_numbers,
            "hit_count": hit_count,
            "replay_status": replay_status,
            "reject_reason": reject_reason,
            "provenance_hash": prov,
            "dry_run": 1,
            "generated_at": now,
        })

    inventory = {
        "daily539_total_draws": len(all_draws),
        "window_min_draw": window_min_draw,
        "backward_total_draws": n_backward_total,
        "min_history_warmup": min_history,
        "warmup_skipped": n_warmup_skipped,
        "replayable_backward_targets": n_replayable_true,
        "targets_generated": len(replayable_indices),
        "first_backward_replayable": all_draws[replayable_indices[0]]["draw"] if replayable_indices else None,
        "first_backward_replayable_date": all_draws[replayable_indices[0]]["date"] if replayable_indices else None,
        "last_backward_target": all_draws[backward_indices[-1]]["draw"] if backward_indices else None,
        "last_backward_target_date": all_draws[backward_indices[-1]]["date"] if backward_indices else None,
        "limit_applied": limit,
    }
    return rows, inventory


# ─── Statistics (pure-Python; replicates P224 methodology) ────────────────────

def _norm_sf(z: float) -> float:
    """One-sided upper-tail p-value of the standard normal."""
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def _pop_std(xs: List[float], mean: float) -> float:
    """Population std (ddof=0) — matches P224 SE convention."""
    if not xs:
        return 0.0
    var = sum((x - mean) ** 2 for x in xs) / len(xs)
    return math.sqrt(var)


def summarize(hit_counts: List[int], baseline: float) -> dict:
    """Mean / M-rates / CI / one-sided p vs baseline for a set of hit_counts."""
    n = len(hit_counts)
    if n == 0:
        return {"n": 0}
    mean = _mean([float(h) for h in hit_counts])
    std = _pop_std([float(h) for h in hit_counts], mean)
    se = std / math.sqrt(n) if n > 0 else 0.0
    z = (mean - baseline) / se if se > 0 else 0.0
    p_one_sided = _norm_sf(z) if se > 0 else None
    return {
        "n": n,
        "mean_hit_count": mean,
        "std": std,
        "se": se,
        "ci95": [mean - 1.96 * se, mean + 1.96 * se],
        "ci_crosses_baseline": (mean - 1.96 * se) <= baseline <= (mean + 1.96 * se),
        "M1plus": sum(1 for h in hit_counts if h >= 1) / n,
        "M2plus": sum(1 for h in hit_counts if h >= 2) / n,
        "M3plus": sum(1 for h in hit_counts if h >= 3) / n,
        "z_vs_baseline": z,
        "p_one_sided_vs_baseline": p_one_sided,
        "direction": "above" if mean > baseline else ("below" if mean < baseline else "equal"),
        "hit_distribution": {str(k): sum(1 for h in hit_counts if h == k) for k in range(0, max(hit_counts) + 1)},
        "max_hit_count": max(hit_counts),
    }


def block_stability(hit_counts: List[int], baseline: float, block_size: int) -> dict:
    """Non-overlapping blocks (chronological). Trailing partial block included, n labeled."""
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


def robustness(hit_counts: List[int], baseline: float) -> dict:
    """Exclude high-hit (>=3) rows, and exclude the strongest 150-block."""
    # Exclude hit_count >= 3 (removes rare high-payoff rows the edge may rest on).
    excl_hi = [h for h in hit_counts if h < 3]
    mean_excl_hi = _mean([float(h) for h in excl_hi]) if excl_hi else 0.0

    # Exclude strongest full 150-block.
    bs = 150
    full_blocks = [hit_counts[s:s + bs] for s in range(0, len(hit_counts), bs) if len(hit_counts[s:s + bs]) == bs]
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
            "mean_hit_count": mean_excl_hi,
            "at_or_above_baseline": mean_excl_hi >= baseline,
        },
        "exclude_strongest_150block": {
            "strongest_block_index_1based": (strongest_idx + 1) if strongest_idx is not None else None,
            "mean_hit_count": mean_excl_strongest,
            "at_or_above_baseline": (mean_excl_strongest >= baseline) if mean_excl_strongest is not None else None,
        },
    }


def era_splits(rows: List[dict], baseline: float) -> dict:
    """Split by calendar era: early (<=2011), middle (2012-2016), late (>=2017)."""
    eras = {"early_2007_2011": [], "middle_2012_2016": [], "late_2017_2021": []}
    for r in rows:
        if r["replay_status"] != "PREDICTED":
            continue
        year = int(r["target_date"].split("/")[0])
        if year <= 2011:
            eras["early_2007_2011"].append(r["hit_count"])
        elif year <= 2016:
            eras["middle_2012_2016"].append(r["hit_count"])
        else:
            eras["late_2017_2021"].append(r["hit_count"])
    return {k: summarize(v, baseline) for k, v in eras.items() if v}


# ─── Classification ───────────────────────────────────────────────────────────

def classify(overall: dict, blocks150: dict, robust: dict, baseline: float) -> Tuple[str, str]:
    """Map the outcome to a P230B1 final classification + one-line rationale."""
    mean = overall["mean_hit_count"]
    if mean < baseline:
        return ("P230B1_BACKWARD_OOS_DRYRUN_BELOW_BASELINE",
                f"backward-OOS mean {mean:.6f} < baseline {baseline:.6f} -> historical-artifact direction")

    clean = (
        not overall["ci_crosses_baseline"]
        and blocks150["majority_above_baseline"]
        and robust["exclude_hit_ge3"]["at_or_above_baseline"]
        and bool(robust["exclude_strongest_150block"]["at_or_above_baseline"])
    )
    if clean:
        return ("P230B1_BACKWARD_OOS_DRYRUN_COMPLETE",
                "backward-OOS above baseline, block-stable, robust to hit>=3 and strongest-block removal")
    return ("P230B1_BACKWARD_OOS_DRYRUN_MIXED",
            "backward-OOS at/above baseline but weak (CI crosses / mixed blocks / fails a robustness check)")


# ─── Orchestrator ─────────────────────────────────────────────────────────────

def run(db_path: Path, limit: Optional[int] = None) -> dict:
    """Full read-only dry-run. Returns the result dict. NO DB writes."""
    from lottery_api.models.p31a_wave1_retired_adapters import WAVE1_ADAPTER_MAP

    adapter = WAVE1_ADAPTER_MAP[STRATEGY_ID]
    min_history = adapter.meta.min_history

    rows_before = total_replay_rows(db_path)
    all_draws = load_daily539_draws(db_path)
    window_min = candidate_window_min_draw(db_path)
    if window_min is None:
        return {"final_classification": "P230B1_BACKWARD_OOS_DRYRUN_BLOCKED",
                "blocked_reason": "no existing candidate replay rows; backward boundary undefined"}

    rows, inventory = generate_backward_rows(all_draws, window_min, adapter, min_history, limit=limit)

    predicted = [r for r in rows if r["replay_status"] == "PREDICTED"]
    hit_counts = [r["hit_count"] for r in predicted]

    rows_after = total_replay_rows(db_path)  # must equal rows_before (read-only proof)

    if not hit_counts:
        return {
            "final_classification": "P230B1_BACKWARD_OOS_DRYRUN_BLOCKED",
            "blocked_reason": "no PREDICTED backward rows produced",
            "inventory": inventory,
            "db_rows_before": rows_before,
            "db_rows_after": rows_after,
        }

    baseline = P224_BASELINE
    overall = summarize(hit_counts, baseline)
    blocks = {str(bs): block_stability(hit_counts, baseline, bs) for bs in (100, 150, 300)}
    robust = robustness(hit_counts, baseline)
    eras = era_splits(predicted, baseline)
    classification, rationale = classify(overall, blocks["150"], robust, baseline)

    return {
        "phase": "P230B1_DAILY539_BACKWARD_OOS_DRYRUN",
        "date": "2026-06-03",
        "execution_status": "DRYRUN_EXECUTED_OK",
        "db_write_performed": rows_after != rows_before,
        "db_rows_before": rows_before,
        "db_rows_after": rows_after,
        "candidate": {"strategy_id": STRATEGY_ID, "lottery_type": LOTTERY_TYPE,
                      "bet_index": BET_INDEX, "status": "WAIT_FOR_OOS",
                      "recorded_bet_semantics": "bet-1 pure MidFreq (predict_midfreq); Fourier bet-2 not stored/invented"},
        "inventory": inventory,
        "baseline_used": baseline,
        "baseline_derivation": "pick(5)*draw(5)/pool(39) = 25/39 (era-invariant)",
        "p224_in_window_reference": {"mean_hit_count": P224_MEAN, "baseline": P224_BASELINE,
                                     "one_sided_p": 0.0673719479414372, "status": "WAIT_FOR_OOS / NEEDS_MORE_OOS"},
        "overall": overall,
        "block_stability": blocks,
        "robustness": robust,
        "era_splits": eras,
        "interpretation_caveat": (
            "Backward-OOS is older-regime robustness, NOT true future OOS. It cannot replace the "
            "P224B future 300/500 new-draw monitoring gate. No promotion / production / P225 authority."
        ),
        "final_classification": classification,
        "classification_rationale": rationale,
        "authorization": {
            "p230b2_db_write_backfill": "NOT AUTHORIZED (separate explicit DB-write authorization required)",
            "p230c_validation": "separately authorized only",
            "p225_model_design": "NOT AUTHORIZED",
            "production_registry_recommendation": "NOT AUTHORIZED / unchanged",
        },
    }


def _fmt(x, nd=6):
    return f"{x:.{nd}f}" if isinstance(x, float) else str(x)


def write_markdown(result: dict, md_path: Path) -> None:
    o = result["overall"]
    inv = result["inventory"]
    b = result["baseline_used"]
    lines: List[str] = []
    A = lines.append
    A("# P230B1 — DAILY_539 Backward-OOS Code-Only Dry-Run\n")
    A("**Date:** 2026-06-03 (Asia/Taipei)  ")
    A("**Task:** `P230B1_DAILY539_BACKWARD_OOS_CODE_ONLY_ARTIFACT_DRYRUN`  ")
    A(f"**Classification:** `{result['final_classification']}`  ")
    A("**Status:** COMPLETE / CODE-ONLY / ZERO DB WRITE\n")
    A("> **Dry-run artifact only.** No DB write, no replay rows created, no registry/production/recommendation "
      "change, no P225. Not betting advice and not a guaranteed predictive edge. Backward-OOS is older-regime "
      "robustness, **not** true future OOS, and cannot replace the P224B future 300/500-draw gate.\n")

    A("## Methodology\n")
    A(f"- Candidate: `{STRATEGY_ID} / {LOTTERY_TYPE}`, bet_index=1 (pure MidFreq bet-1; Fourier bet-2 not stored/invented).")
    A(f"- Reused `MidfreqFourier2BetAdapter` (`min_history={inv['min_history_warmup']}`) + P31B causal slice `history = all_draws[:i]`.")
    A("- DB opened **read-only** (`mode=ro`); writes physically impossible. Artifacts only.")
    A("- Leakage guard: `history_cutoff_draw` = ordinal predecessor (`all_draws[i-1]`), not numeric `target_draw-1`.")
    A(f"- Baseline = `{b}` (= 25/39, era-invariant). Stats replicate P224 (sample SD, 1.96·SE CI, one-sided z).\n")

    A("## Backward-OOS Inventory\n")
    A("| Field | Value |")
    A("|---|---|")
    A(f"| DAILY_539 total draws | {inv['daily539_total_draws']} |")
    A(f"| Candidate window min target_draw | {inv['window_min_draw']} |")
    A(f"| Backward total (strictly earlier) | {inv['backward_total_draws']} |")
    A(f"| Warmup skipped (min_history={inv['min_history_warmup']}) | {inv['warmup_skipped']} |")
    A(f"| **Replayable backward targets** | **{inv['replayable_backward_targets']}** |")
    A(f"| First replayable | {inv['first_backward_replayable']} @ {inv['first_backward_replayable_date']} |")
    A(f"| Last backward target | {inv['last_backward_target']} @ {inv['last_backward_target_date']} |")
    if inv.get("limit_applied") is not None:
        A(f"| ⚠ limit applied (dev subset) | {inv['limit_applied']} |")
    A("")

    A("## Overall Result\n")
    A("| Metric | Backward-OOS | P224 in-window |")
    A("|---|---:|---:|")
    A(f"| n | {o['n']} | 1500 |")
    A(f"| mean hit_count | {_fmt(o['mean_hit_count'])} | {_fmt(result['p224_in_window_reference']['mean_hit_count'])} |")
    A(f"| baseline | {_fmt(b)} | {_fmt(b)} |")
    A(f"| 95% CI | [{_fmt(o['ci95'][0])}, {_fmt(o['ci95'][1])}] | [0.632237, 0.706430] |")
    A(f"| CI crosses baseline | {o['ci_crosses_baseline']} | True |")
    A(f"| one-sided p vs baseline | {_fmt(o['p_one_sided_vs_baseline']) if o['p_one_sided_vs_baseline'] is not None else 'n/a'} | 0.067372 |")
    A(f"| M1+ / M2+ / M3+ | {_fmt(o['M1plus'],4)} / {_fmt(o['M2plus'],4)} / {_fmt(o['M3plus'],4)} | 0.524 / 0.1327 / 0.0127 |")
    A(f"| direction | {o['direction']} | above |")
    A("")

    A("## Block Stability\n")
    A("| Block size | n blocks | above baseline | majority | block mean SD | worst | best |")
    A("|---|---:|---:|---|---:|---:|---:|")
    for bs in ("100", "150", "300"):
        bl = result["block_stability"][bs]
        A(f"| {bs} | {bl['n_blocks']} | {bl['blocks_above_baseline']} | {bl['majority_above_baseline']} | "
          f"{_fmt(bl['block_mean_sd'])} | {_fmt(bl['worst_block_mean'])} | {_fmt(bl['best_block_mean'])} |")
    A("")

    A("## Robustness\n")
    rob = result["robustness"]
    A("| Check | n | mean | at/above baseline |")
    A("|---|---:|---:|---|")
    eh = rob["exclude_hit_ge3"]
    A(f"| Exclude hit_count≥3 ({eh['n_removed']} removed) | {eh['n']} | {_fmt(eh['mean_hit_count'])} | {eh['at_or_above_baseline']} |")
    es = rob["exclude_strongest_150block"]
    A(f"| Exclude strongest 150-block (#{es['strongest_block_index_1based']}) | — | {_fmt(es['mean_hit_count'])} | {es['at_or_above_baseline']} |")
    A("")

    A("## Era Splits\n")
    A("| Era | n | mean | direction | one-sided p |")
    A("|---|---:|---:|---|---:|")
    for name, e in result["era_splits"].items():
        A(f"| {name} | {e['n']} | {_fmt(e['mean_hit_count'])} | {e['direction']} | "
          f"{_fmt(e['p_one_sided_vs_baseline']) if e.get('p_one_sided_vs_baseline') is not None else 'n/a'} |")
    A("")

    A("## Decision\n")
    A(f"- **Final classification:** `{result['final_classification']}`")
    A(f"- **Rationale:** {result['classification_rationale']}")
    A(f"- DB write performed: **{result['db_write_performed']}** (rows {result['db_rows_before']} → {result['db_rows_after']}).")
    A("- P230B2 (DB write/backfill), P230C (validation), and P225 (model design) remain **separately authorized only**. "
      "No production / registry / recommendation change. No promotion regardless of outcome.\n")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main(argv: Optional[List[str]] = None) -> dict:
    parser = argparse.ArgumentParser(description="P230B1 DAILY_539 backward-OOS code-only dry-run")
    parser.add_argument("--db-path", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--json-out", default=str(OUTPUT_DIR / f"p230b1_daily539_backward_oos_dryrun_{DATE_TAG}.json"))
    parser.add_argument("--md-out", default=str(OUTPUT_DIR / f"p230b1_daily539_backward_oos_dryrun_{DATE_TAG}.md"))
    parser.add_argument("--limit", type=int, default=None, help="dev subset: cap replayable backward targets")
    args = parser.parse_args(argv)

    result = run(Path(args.db_path), limit=args.limit)

    out_json = Path(args.json_out)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[P230B1] JSON written: {out_json}")

    if result.get("execution_status") == "DRYRUN_EXECUTED_OK":
        write_markdown(result, Path(args.md_out))
        print(f"[P230B1] Markdown written: {args.md_out}")

    print(f"[P230B1] Classification: {result['final_classification']}")
    return result


if __name__ == "__main__":
    res = main()
    sys.exit(0 if res.get("execution_status") == "DRYRUN_EXECUTED_OK" or "BLOCKED" in res.get("final_classification", "") else 1)
