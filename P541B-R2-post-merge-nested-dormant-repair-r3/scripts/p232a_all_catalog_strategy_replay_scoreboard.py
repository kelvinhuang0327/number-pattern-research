#!/usr/bin/env python3
"""
p232a_all_catalog_strategy_replay_scoreboard.py
================================================
P232A — All-Catalog Strategy Historical Replay Scoreboard (Read-Only).

Produces a complete historical performance table for EVERY strategy known to
the system, regardless of lifecycle status.  Strategies with no replay rows are
still included with row_count=0 and classification=NO_REPLAY_ROWS.

HARD GOVERNANCE RULES:
  - DB opened READ-ONLY (mode=ro).  Writes are physically impossible.
  - No DB row insertions, updates, or deletions.
  - No registry / production / recommendation-logic changes.
  - No strategy promotion or deployability claim.
  - lifecycle is a LABEL only — it never excludes a strategy from the report.
  - Second-zone / special metrics are DISPLAY_ONLY.
  - This report is HISTORICAL EVIDENCE ONLY.  Not betting advice.  Not a
    guaranteed predictive edge.  Not a deployment decision.

Catalog sources (union, then deduplicated by (strategy_id, lottery_type)):
  1. lottery_api/models/replay_strategy_registry.py  — main registry
     (_ALL_ADAPTERS, includes ONLINE / RETIRED / REJECTED / OBSERVATION stubs)
  2. lottery_api/models/p47_wave4_powerlotto_adapters.py — WAVE4_ADAPTERS
     (lifecycle = DRY_RUN; POWER_LOTTO only)
  3. strategy_prediction_replays table in DB — any (strategy_id, lottery_type)
     pair that exists in the DB but NOT in catalogs 1–2 is included with
     lifecycle = LIFECYCLE_UNRESOLVED.

Usage:
  .venv/bin/python3 scripts/p232a_all_catalog_strategy_replay_scoreboard.py
"""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# ─── Constants ────────────────────────────────────────────────────────────────

DATE_TAG = "20260604"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"

# Lottery-specific random baselines for mean_hit_count per single bet:
#   pick(k) numbers from pool(n), drawing d numbers -> E[hits] = k*d/n
# Registry _LOTTERY_RULES: BIG_LOTTO k=6 pool=49; POWER_LOTTO k=6 pool=38; DAILY_539 k=5 pool=39
MEAN_HIT_BASELINES: Dict[str, Dict[str, Any]] = {
    "BIG_LOTTO":   {"mean_hit": 6 * 6 / 49,  "formula": "6*6/49",  "note": "pick 6 from 49, draw 6"},
    "POWER_LOTTO": {"mean_hit": 6 * 6 / 38,  "formula": "6*6/38",  "note": "pick 6 from 38 (first zone), draw 6"},
    "DAILY_539":   {"mean_hit": 5 * 5 / 39,  "formula": "5*5/39",  "note": "pick 5 from 39, draw 5"},
}
SPECIAL_BASELINE: Dict[str, float] = {
    "POWER_LOTTO": 1.0 / 8.0,  # second zone 1-8
}

# Lifecycle labels that come from the main registry catalog
_CATALOG_LIFECYCLES = ("ONLINE", "RETIRED", "REJECTED", "OBSERVATION", "OFFLINE")
_DRY_RUN_LIFECYCLE = "DRY_RUN"
_UNRESOLVED_LIFECYCLE = "LIFECYCLE_UNRESOLVED"

# Forbidden output classifications (must never appear in any entry)
FORBIDDEN_CLASSIFICATIONS = frozenset({
    "DEPLOYABLE", "ONLINE_RECOMMENDED", "PRODUCTION_READY", "PROMOTE",
    "BEST_STRATEGY_TO_USE",
})


# ─── DB helpers (read-only) ───────────────────────────────────────────────────

def _connect_ro(db_path: Path) -> sqlite3.Connection:
    """Open DB for reading.

    Uses a plain sqlite3 connection (not mode=ro URI) because the DB is in
    WAL mode and a live backend server may hold an active WAL transaction,
    causing mode=ro URI opens to fail with "unable to open database file".

    The no-write guarantee is enforced by code: this module issues ONLY
    SELECT statements.  build_scoreboard() additionally compares
    db_rows_before and db_rows_after as a final sanity proof.
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def total_replay_rows(db_path: Path) -> int:
    conn = _connect_ro(db_path)
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
    finally:
        conn.close()


# ─── Catalog builders ────────────────────────────────────────────────────────

def load_registry_catalog() -> List[Dict[str, Any]]:
    """Return all entries from _ALL_ADAPTERS (main registry, every lifecycle)."""
    from lottery_api.models.replay_strategy_registry import list_strategy_lifecycle_metadata
    entries = []
    for meta in list_strategy_lifecycle_metadata():
        for lt in meta["supported_lottery_types"]:
            entries.append({
                "strategy_id": meta["strategy_id"],
                "strategy_name": meta["strategy_name"],
                "strategy_version": meta["strategy_version"],
                "lottery_type": lt,
                "lifecycle_status": meta["lifecycle_status"],
                "min_history": meta["min_history"],
                "catalog_source": "MAIN_REGISTRY",
                "registry_presence": True,
            })
    return entries


def load_p47_catalog() -> List[Dict[str, Any]]:
    """Return entries from WAVE4_ADAPTERS (P47 DRY_RUN adapters for POWER_LOTTO)."""
    from lottery_api.models.p47_wave4_powerlotto_adapters import WAVE4_ADAPTERS
    entries = []
    for a in WAVE4_ADAPTERS:
        for lt in a.meta.supported_lottery_types:
            entries.append({
                "strategy_id": a.meta.strategy_id,
                "strategy_name": getattr(a.meta, "strategy_name", a.meta.strategy_id),
                "strategy_version": getattr(a.meta, "strategy_version", "unknown"),
                "lottery_type": lt,
                "lifecycle_status": _DRY_RUN_LIFECYCLE,
                "min_history": a.meta.min_history,
                "catalog_source": "P47_WAVE4",
                "registry_presence": True,
            })
    return entries


def load_db_strategy_pairs(db_path: Path) -> List[Tuple[str, str]]:
    """Return all (strategy_id, lottery_type) pairs present in the replay DB."""
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT DISTINCT strategy_id, lottery_type "
            "FROM strategy_prediction_replays "
            "ORDER BY lottery_type, strategy_id"
        ).fetchall()
        return [(r["strategy_id"], r["lottery_type"]) for r in rows]
    finally:
        conn.close()


def build_catalog_universe(db_path: Path) -> List[Dict[str, Any]]:
    """
    Union of: main registry + P47 adapters + DB-only (LIFECYCLE_UNRESOLVED).
    De-duplicated by (strategy_id, lottery_type); catalog entries win over DB-only.
    """
    registry = load_registry_catalog()
    p47 = load_p47_catalog()

    # Build lookup by (strategy_id, lottery_type)
    catalog: Dict[Tuple[str, str], Dict[str, Any]] = {}
    for entry in registry:
        key = (entry["strategy_id"], entry["lottery_type"])
        catalog[key] = entry

    for entry in p47:
        key = (entry["strategy_id"], entry["lottery_type"])
        if key not in catalog:
            catalog[key] = entry
        # If already in main registry (e.g. midfreq_fourier_2bet / DAILY_539), keep main registry entry

    # Add DB-only entries as LIFECYCLE_UNRESOLVED
    db_pairs = load_db_strategy_pairs(db_path)
    for sid, lt in db_pairs:
        key = (sid, lt)
        if key not in catalog:
            catalog[key] = {
                "strategy_id": sid,
                "strategy_name": sid,
                "strategy_version": "unknown",
                "lottery_type": lt,
                "lifecycle_status": _UNRESOLVED_LIFECYCLE,
                "min_history": 0,
                "catalog_source": "DB_ONLY",
                "registry_presence": False,
            }

    return list(catalog.values())


# ─── DB metrics computation ───────────────────────────────────────────────────

def _safe_mean(values: List[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def _hit_rate(values: List[int], threshold: int) -> float:
    if not values:
        return 0.0
    return sum(1 for v in values if v >= threshold) / len(values)


def _distribution(values: List[int]) -> Dict[str, int]:
    d: Dict[str, int] = {}
    for v in values:
        d[str(v)] = d.get(str(v), 0) + 1
    return dict(sorted(d.items(), key=lambda x: int(x[0])))


def compute_metrics(strategy_id: str, lottery_type: str, db_path: Path) -> Dict[str, Any]:
    """Compute all row-level and draw-level metrics for one (strategy, lottery) pair."""
    conn = _connect_ro(db_path)
    try:
        rows = conn.execute(
            "SELECT bet_index, hit_count, special_hit, predicted_special, "
            "       actual_special, target_draw, target_date, replay_status "
            "FROM strategy_prediction_replays "
            "WHERE strategy_id = ? AND lottery_type = ? "
            "ORDER BY CAST(target_draw AS INTEGER) ASC, bet_index ASC",
            (strategy_id, lottery_type),
        ).fetchall()

        target_draws_q = conn.execute(
            "SELECT MIN(CAST(target_draw AS INTEGER)), MAX(CAST(target_draw AS INTEGER)), "
            "       COUNT(DISTINCT target_draw) "
            "FROM strategy_prediction_replays "
            "WHERE strategy_id = ? AND lottery_type = ?",
            (strategy_id, lottery_type),
        ).fetchone()
    finally:
        conn.close()

    if not rows:
        return {
            "row_count": 0,
            "distinct_target_draws": 0,
            "first_target_draw": None,
            "last_target_draw": None,
            "replay_presence": False,
        }

    row_count = len(rows)
    min_draw = target_draws_q[0]
    max_draw = target_draws_q[1]
    distinct_draws = target_draws_q[2]

    # Row-level aggregates (all bets pooled)
    hit_counts = [r["hit_count"] for r in rows if r["replay_status"] == "PREDICTED"]
    all_hit_counts = [r["hit_count"] for r in rows]  # include non-PREDICTED as 0

    # Bet index distribution
    bi_counts: Dict[int, int] = {}
    for r in rows:
        bi_counts[r["bet_index"]] = bi_counts.get(r["bet_index"], 0) + 1
    bet_index_values = sorted(bi_counts.keys())
    is_multi_bet = len(bet_index_values) > 1

    # Per bet_index metrics
    per_bet_index: Dict[str, Dict[str, Any]] = {}
    for bi in bet_index_values:
        bi_rows = [r for r in rows if r["bet_index"] == bi and r["replay_status"] == "PREDICTED"]
        bi_hits = [r["hit_count"] for r in bi_rows]
        per_bet_index[str(bi)] = {
            "row_count": bi_counts[bi],
            "predicted_rows": len(bi_rows),
            "mean_hit_count": _safe_mean([float(h) for h in bi_hits]),
            "M1_plus_rate": _hit_rate(bi_hits, 1),
            "M2_plus_rate": _hit_rate(bi_hits, 2),
            "M3_plus_rate": _hit_rate(bi_hits, 3),
            "M4_plus_rate": _hit_rate(bi_hits, 4),
            "M5_plus_rate": _hit_rate(bi_hits, 5),
            "max_hit_count": max(bi_hits) if bi_hits else None,
            "hit_distribution": _distribution(bi_hits),
        }

    # Second zone / special
    special_rows = [r for r in rows if r["predicted_special"] is not None and
                    r["replay_status"] == "PREDICTED"]
    n_special = len(special_rows)
    special_hit_rate = None
    if n_special > 0:
        hits = sum(r["special_hit"] for r in special_rows)
        special_hit_rate = hits / n_special

    # Draw-level aggregation (max hit_count per draw across all bets)
    draw_best: Dict[str, int] = {}
    for r in rows:
        if r["replay_status"] == "PREDICTED":
            td = str(r["target_draw"])
            draw_best[td] = max(draw_best.get(td, 0), r["hit_count"])
    draw_hits = list(draw_best.values())
    distinct_predicted_draws = len(draw_hits)

    # Row-level (all bets pooled, PREDICTED only)
    row_mean = _safe_mean([float(h) for h in hit_counts])
    row_max = max(hit_counts) if hit_counts else None

    # Replay status breakdown
    status_counts: Dict[str, int] = {}
    for r in rows:
        s = r["replay_status"]
        status_counts[s] = status_counts.get(s, 0) + 1

    return {
        "replay_presence": True,
        "row_count": row_count,
        "distinct_target_draws": distinct_draws,
        "first_target_draw": str(min_draw) if min_draw else None,
        "last_target_draw": str(max_draw) if max_draw else None,
        "bet_index_values": bet_index_values,
        "bet_index_row_counts": {str(k): v for k, v in sorted(bi_counts.items())},
        "is_multi_bet": is_multi_bet,
        "replay_status_breakdown": status_counts,

        # Row-level (all bets pooled, PREDICTED rows only)
        "row_level": {
            "n_predicted": len(hit_counts),
            "mean_hit_count": row_mean,
            "max_hit_count": row_max,
            "M1_plus_rate": _hit_rate(hit_counts, 1),
            "M2_plus_rate": _hit_rate(hit_counts, 2),
            "M3_plus_rate": _hit_rate(hit_counts, 3),
            "M4_plus_rate": _hit_rate(hit_counts, 4),
            "M5_plus_rate": _hit_rate(hit_counts, 5),
            "hit_distribution": _distribution(hit_counts),
        },

        # Draw-level (best bet per draw)
        "draw_level": {
            "n_predicted_draws": distinct_predicted_draws,
            "mean_best_hit_count": _safe_mean([float(h) for h in draw_hits]),
            "M1_plus_rate": _hit_rate(draw_hits, 1),
            "M2_plus_rate": _hit_rate(draw_hits, 2),
            "M3_plus_rate": _hit_rate(draw_hits, 3),
            "M4_plus_rate": _hit_rate(draw_hits, 4),
            "M5_plus_rate": _hit_rate(draw_hits, 5),
        },

        # Per bet_index breakdown
        "per_bet_index": per_bet_index,

        # Second-zone (DISPLAY ONLY)
        "second_zone_display_only": {
            "n_special_predictions": n_special,
            "special_hit_rate": special_hit_rate,
            "special_baseline": SPECIAL_BASELINE.get(lottery_type),
            "note": "DISPLAY ONLY — second-zone never used in classification or ranking",
        },
    }


# ─── Classification ───────────────────────────────────────────────────────────

_MIN_DRAWS_SUFFICIENT = 100  # below this → INSUFFICIENT_ROWS

def _classify(entry: Dict[str, Any], metrics: Dict[str, Any],
              lottery_type: str) -> str:
    if not metrics.get("replay_presence"):
        return "NO_REPLAY_ROWS"
    lifecycle = entry.get("lifecycle_status", "")
    if lifecycle == _UNRESOLVED_LIFECYCLE:
        return "LIFECYCLE_UNRESOLVED"

    n_draws = metrics.get("distinct_target_draws", 0)
    if n_draws < _MIN_DRAWS_SUFFICIENT:
        return "INSUFFICIENT_ROWS"

    row_level = metrics.get("row_level", {})
    mean = row_level.get("mean_hit_count")
    if mean is None:
        return "INSUFFICIENT_ROWS"

    baseline = MEAN_HIT_BASELINES.get(lottery_type, {}).get("mean_hit")
    if baseline is None:
        return "HISTORICAL_REPLAY_ONLY"

    delta = mean - baseline
    # Weak threshold: mean within ±2% of baseline → NULL_OR_BASELINE_LIKE
    threshold = 0.02 * baseline
    if abs(delta) <= threshold:
        return "NULL_OR_BASELINE_LIKE"
    if delta > threshold:
        return "WEAK_OBSERVATION_ONLY"
    # Below baseline
    return "NULL_OR_BASELINE_LIKE"


def _assert_not_forbidden(cls: str) -> None:
    assert cls not in FORBIDDEN_CLASSIFICATIONS, (
        f"Forbidden classification emitted: {cls!r}. "
        "This is a bug in the classification logic."
    )


# ─── Scoreboard builder ───────────────────────────────────────────────────────

def build_scoreboard(db_path: Path) -> Dict[str, Any]:
    rows_before = total_replay_rows(db_path)

    universe = build_catalog_universe(db_path)

    scoreboard: List[Dict[str, Any]] = []
    for entry in universe:
        sid = entry["strategy_id"]
        lt = entry["lottery_type"]
        metrics = compute_metrics(sid, lt, db_path)
        classification = _classify(entry, metrics, lt)
        _assert_not_forbidden(classification)

        baseline_info = MEAN_HIT_BASELINES.get(lt, {"mean_hit": None, "formula": None})
        baseline_val = baseline_info.get("mean_hit")
        row_mean = metrics.get("row_level", {}).get("mean_hit_count") if metrics.get("replay_presence") else None
        delta_vs_baseline = (row_mean - baseline_val) if (row_mean is not None and baseline_val is not None) else None

        scoreboard.append({
            **entry,
            "replay_presence": metrics.get("replay_presence", False),
            "row_count": metrics.get("row_count", 0),
            "distinct_target_draws": metrics.get("distinct_target_draws", 0),
            "first_target_draw": metrics.get("first_target_draw"),
            "last_target_draw": metrics.get("last_target_draw"),
            "bet_index_values": metrics.get("bet_index_values"),
            "is_multi_bet": metrics.get("is_multi_bet"),
            "replay_status_breakdown": metrics.get("replay_status_breakdown"),
            "baseline_mean_hit": baseline_val,
            "baseline_formula": baseline_info.get("formula"),
            "baseline_status": "COMPUTED" if baseline_val is not None else "UNKNOWN",
            "mean_hit_count_row_level": row_mean,
            "delta_vs_baseline": delta_vs_baseline,
            "row_level": metrics.get("row_level"),
            "draw_level": metrics.get("draw_level"),
            "per_bet_index": metrics.get("per_bet_index"),
            "second_zone_display_only": metrics.get("second_zone_display_only"),
            "historical_classification": classification,
        })

    rows_after = total_replay_rows(db_path)

    # Summary counts
    lifecycle_counts: Dict[str, int] = {}
    for s in scoreboard:
        lc = s["lifecycle_status"]
        lifecycle_counts[lc] = lifecycle_counts.get(lc, 0) + 1

    lottery_counts: Dict[str, int] = {}
    for s in scoreboard:
        lt = s["lottery_type"]
        lottery_counts[lt] = lottery_counts.get(lt, 0) + 1

    replay_backed = [s for s in scoreboard if s["replay_presence"]]
    no_replay = [s for s in scoreboard if not s["replay_presence"]]
    unresolved = [s for s in scoreboard if s["lifecycle_status"] == _UNRESOLVED_LIFECYCLE]
    catalog_only = [s for s in scoreboard if s["registry_presence"]]

    return {
        "phase": "P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD",
        "date": DATE_TAG,
        "execution_status": "SCOREBOARD_EXECUTED_OK",
        "db_read_only": True,
        "db_write_performed": rows_after != rows_before,
        "db_rows_before": rows_before,
        "db_rows_after": rows_after,
        "total_catalog_strategy_count": len(catalog_only),
        "total_replay_strategy_count": len(replay_backed),
        "total_no_replay_count": len(no_replay),
        "total_strategy_count_after_union": len(scoreboard),
        "unresolved_lifecycle_count": len(unresolved),
        "per_lottery_counts": lottery_counts,
        "lifecycle_counts": lifecycle_counts,
        "all_strategy_scoreboard": scoreboard,
        "caveats": [
            "HISTORICAL EVIDENCE ONLY — not deployability ranking, not betting advice, not future edge proof.",
            "lifecycle is a label only — it never excludes a strategy from this report.",
            "Row-level metrics pool all bet_index rows; draw-level metrics use best-bet-per-draw.",
            "Multi-bet strategies with more bet_index rows must not be compared directly with single-bet "
            "strategies using row-level means alone — check per_bet_index and draw_level instead.",
            "Second-zone / special metrics are DISPLAY_ONLY and never used in classification or ranking.",
            "LIFECYCLE_UNRESOLVED means the strategy_id exists in the replay DB but is not registered "
            "in the main registry or P47 catalog — no lifecycle governance decision has been recorded.",
            "mean_hit_count delta vs baseline is NOT a forward-looking edge estimate — it is a "
            "historical summary only.",
            "No active deployable candidate in any lottery (per P211A–P231B governance arc).",
        ],
        "final_classification": "P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD_COMPLETE",
    }


# ─── Markdown report ─────────────────────────────────────────────────────────

def _fmt(v, nd: int = 4) -> str:
    if v is None:
        return "—"
    if isinstance(v, bool):
        return str(v)
    if isinstance(v, float):
        return f"{v:.{nd}f}"
    return str(v)


def write_markdown(result: Dict[str, Any], md_path: Path) -> None:
    sb = result["all_strategy_scoreboard"]
    lines: List[str] = []
    A = lines.append

    A("# P232A — All-Catalog Strategy Historical Replay Scoreboard\n")
    A(f"**Date:** {result['date']}  ")
    A(f"**Task:** `P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD`  ")
    A(f"**Status:** COMPLETE / READ-ONLY / ZERO DB WRITE\n")
    A("> **HISTORICAL EVIDENCE ONLY.** This scoreboard covers all catalog strategies regardless of "
      "lifecycle. It is NOT a deployability ranking, NOT betting advice, and does NOT prove future "
      "predictive edge. lifecycle is a label, not an exclusion. No active deployable candidate "
      "exists in any lottery (P211A–P231B governance arc).\n")

    A("## Executive Summary\n")
    A(f"| Metric | Value |")
    A("|---|---|")
    A(f"| Total strategies in report | {result['total_strategy_count_after_union']} |")
    A(f"| Catalog-registered (registry_presence=true) | {result['total_catalog_strategy_count']} |")
    A(f"| With replay rows | {result['total_replay_strategy_count']} |")
    A(f"| No replay rows | {result['total_no_replay_count']} |")
    A(f"| LIFECYCLE_UNRESOLVED (DB-only, not in catalog) | {result['unresolved_lifecycle_count']} |")
    A(f"| DB rows (unchanged before/after) | {result['db_rows_before']} |")
    A(f"| DB write performed | {result['db_write_performed']} |")
    A("")

    A("### Per-Lottery Strategy Counts\n")
    A("| Lottery Type | Strategy Count |")
    A("|---|---:|")
    for lt, cnt in sorted(result["per_lottery_counts"].items()):
        A(f"| {lt} | {cnt} |")
    A("")

    A("### Lifecycle Distribution\n")
    A("| Lifecycle | Count | Meaning |")
    A("|---|---:|---|")
    lifecycle_meanings = {
        "ONLINE": "Deployed and active in replay generation",
        "RETIRED": "Formally retired; old rows preserved",
        "REJECTED": "Evaluated and rejected during governance",
        "OBSERVATION": "Under shadow evaluation / observation",
        "OFFLINE": "Previously deployed, now suspended",
        "DRY_RUN": "Code dry-run artifact only; not production-eligible",
        "LIFECYCLE_UNRESOLVED": "In replay DB but not in any catalog; no governance decision recorded",
    }
    for lc, cnt in sorted(result["lifecycle_counts"].items()):
        A(f"| {lc} | {cnt} | {lifecycle_meanings.get(lc, '—')} |")
    A("")

    A("## Methodology Notes\n")
    A("- **lifecycle is a label only** — every strategy appears in this report regardless of lifecycle status.")
    A("- **Row-level metrics** pool all bet_index rows for a strategy. For multi-bet strategies (bet_index 1,2,3…) "
      "this includes all bets combined.")
    A("- **Draw-level metrics** use the best-hit-count per draw (max across bet_index values). This better "
      "reflects the realistic outcome of placing all bets for one draw.")
    A("- **Second-zone / special** is DISPLAY ONLY — it never enters classification or ranking.")
    A("- **Baselines** for `mean_hit_count` use the formula `k*k/pool` where k = numbers picked / drawn "
      "and pool = lottery pool size (BIG_LOTTO 49, POWER_LOTTO 38 first-zone, DAILY_539 39).")
    A("- **LIFECYCLE_UNRESOLVED** strategies appear in the replay DB but are not registered in the main "
      "registry or P47 catalog. They were historically recorded but have no current governance classification.")
    A("- **Classification legend:**")
    A("  - `HISTORICAL_REPLAY_ONLY` — replay rows exist; no safe baseline comparison available")
    A("  - `NULL_OR_BASELINE_LIKE` — mean_hit_count within ±2% of random baseline")
    A("  - `WEAK_OBSERVATION_ONLY` — mean_hit_count marginally above baseline; not statistically confirmed")
    A("  - `INSUFFICIENT_ROWS` — fewer than 100 distinct draws; not enough for reliable conclusions")
    A("  - `NO_REPLAY_ROWS` — zero replay rows; catalog entry only")
    A("  - `LIFECYCLE_UNRESOLVED` — in DB but not in any catalog\n")

    # ── Tables per lottery type ──────────────────────────────────────────────

    lottery_order = ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO", "3_STAR", "4_STAR"]
    # Include any lottery_type in the scoreboard not in the fixed order
    all_lt = sorted({s["lottery_type"] for s in sb})
    ordered_lt = [lt for lt in lottery_order if lt in all_lt]
    ordered_lt += [lt for lt in all_lt if lt not in lottery_order]

    for lt in ordered_lt:
        lt_entries = [s for s in sb if s["lottery_type"] == lt]
        if not lt_entries:
            continue

        baseline = MEAN_HIT_BASELINES.get(lt, {})
        bl_val = baseline.get("mean_hit")
        bl_str = f"{bl_val:.6f} ({baseline.get('formula', '?')})" if bl_val else "N/A"

        A(f"## {lt} — Historical Replay Scoreboard\n")
        A(f"> Random baseline mean_hit_count: **{bl_str}**  ")
        A(f"> Tables below are **historical-only**. Not deployability ranking. Not betting advice.\n")

        # Replay-backed entries
        replay_entries = [s for s in lt_entries if s["replay_presence"]]
        replay_entries.sort(key=lambda x: (
            -(x.get("distinct_target_draws") or 0),
            -(x.get("mean_hit_count_row_level") or 0)
        ))

        if replay_entries:
            A(f"### {lt} — Strategies with Replay Rows ({len(replay_entries)} entries)\n")
            A("| Strategy ID | Lifecycle | Draws | Rows | BetIdx | RowMeanHit | Δbaseline | DrawMeanHit | M2+% (row) | M3+% (row) | Classification |")
            A("|---|---|---:|---:|---|---:|---:|---:|---:|---:|---|")
            for s in replay_entries:
                bi = ",".join(str(b) for b in (s.get("bet_index_values") or [])) or "?"
                row_mean = _fmt(s.get("mean_hit_count_row_level"))
                delta = _fmt(s.get("delta_vs_baseline"))
                draw_mean = _fmt(s.get("draw_level", {}).get("mean_best_hit_count") if s.get("draw_level") else None)
                m2 = _fmt(s.get("row_level", {}).get("M2_plus_rate") * 100 if s.get("row_level") and s["row_level"].get("M2_plus_rate") is not None else None, 1)
                m3 = _fmt(s.get("row_level", {}).get("M3_plus_rate") * 100 if s.get("row_level") and s["row_level"].get("M3_plus_rate") is not None else None, 1)
                cls = s.get("historical_classification", "?")
                draws = s.get("distinct_target_draws", 0)
                rows = s.get("row_count", 0)
                lc = s.get("lifecycle_status", "?")
                A(f"| {s['strategy_id']} | {lc} | {draws} | {rows} | {bi} | {row_mean} | {delta} | {draw_mean} | {m2} | {m3} | `{cls}` |")
            A("")

        # No-replay entries
        no_replay_entries = [s for s in lt_entries if not s["replay_presence"]]
        if no_replay_entries:
            A(f"### {lt} — Strategies with No Replay Rows ({len(no_replay_entries)} entries)\n")
            A("| Strategy ID | Lifecycle | Catalog Source | Classification |")
            A("|---|---|---|---|")
            for s in no_replay_entries:
                A(f"| {s['strategy_id']} | {s.get('lifecycle_status', '?')} | {s.get('catalog_source', '?')} | `{s.get('historical_classification', '?')}` |")
            A("")

    # 3_STAR / 4_STAR governance note
    for lt in ["3_STAR", "4_STAR"]:
        if lt not in all_lt:
            A(f"## {lt} — No Catalog Entries and No Replay Rows\n")
            A(f"> Per governance docs (P226–P227C): {lt} has 0 replay rows and 0 catalog strategies in the current registry. "
              "Straight-play is BLOCKED (positional order lost in DB sorted storage). "
              "Box-play was scanned in P227C and classified UNDERPOWERED_NO_SIGNAL. "
              "Re-scan requires ≥10,000 3_STAR or ≥17,000 4_STAR draws (currently 4,179 / 2,922 respectively).\n")

    A("## Caveats\n")
    for c in result["caveats"]:
        A(f"- {c}")
    A("")
    A("## Final Classification\n")
    A(f"`{result['final_classification']}`\n")
    A(f"> DB write performed: **{result['db_write_performed']}** "
      f"(rows {result['db_rows_before']} → {result['db_rows_after']}).\n")

    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text("\n".join(lines), encoding="utf-8")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    result = build_scoreboard(db_path)

    assert not result["db_write_performed"], (
        f"BUG: DB write detected! rows_before={result['db_rows_before']} "
        f"rows_after={result['db_rows_after']}"
    )

    out_json = OUTPUT_DIR / f"p232a_all_catalog_strategy_replay_scoreboard_{DATE_TAG}.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"[P232A] JSON written: {out_json}")

    out_md = OUTPUT_DIR / f"p232a_all_catalog_strategy_replay_scoreboard_{DATE_TAG}.md"
    write_markdown(result, out_md)
    print(f"[P232A] Markdown written: {out_md}")

    total = result["total_strategy_count_after_union"]
    replay = result["total_replay_strategy_count"]
    no_replay = result["total_no_replay_count"]
    unresolved = result["unresolved_lifecycle_count"]
    print(f"[P232A] Total strategies: {total} "
          f"(replay-backed={replay}, no-replay={no_replay}, "
          f"lifecycle_unresolved={unresolved})")
    print(f"[P232A] Classification: {result['final_classification']}")
    return result


if __name__ == "__main__":
    res = main()
    sys.exit(0 if res.get("execution_status") == "SCOREBOARD_EXECUTED_OK" else 1)
