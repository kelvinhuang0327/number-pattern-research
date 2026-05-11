"""
Replay API Routes (Strategy Historical Prediction Replay Store v0.1)

GET  /api/replay/strategies          — 列出所有已登錄策略（可按彩種過濾）
GET  /api/replay/history             — 分頁查詢歷史回放記錄
GET  /api/replay/summary             — 按策略聚合命中率摘要
GET  /api/replay/runs                — 列出 replay_run 記錄
GET  /api/replay/run/{run_id}/status — 查詢單一 replay_run 狀態

IMPORTANT: These endpoints are READ-ONLY audit endpoints.
  - They MUST NOT trigger any prediction generation.
  - They MUST NOT be used for strategy promotion decisions.
    - Results are for historical audit only; they do NOT represent a validated result.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

try:
    from database import DatabaseManager
except ImportError:
    from lottery_api.database import DatabaseManager

from lottery_api.models.replay_strategy_registry import (
    get_strategy_lifecycle_status,
    list_strategies,
    list_strategy_lifecycle_metadata,
    list_executable_strategy_ids,
    list_non_executable_strategy_ids,
    summarize_strategy_lifecycle_counts,
    normalise_lifecycle_status,
)

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

router = APIRouter()
logger = logging.getLogger(__name__)

# Conservative disclaimer used by all replay endpoints
_DISCLAIMER = (
    "本資料為歷史預測回放資料，用於查詢與稽核；"
    "不代表提高中獎率，也不保證任何回放結果。"
)

# ─── DB access ────────────────────────────────────────────────────────────────

def _get_db():
    """Returns a DatabaseManager instance."""
    return DatabaseManager()


def _open_conn():
    """Returns a raw sqlite3 connection to the lottery DB."""
    db_path = Path(_api_root) / "data" / "lottery_v2.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _normalise_lifecycle_filter(lifecycle_status: Optional[str]) -> Optional[str]:
    """Return a canonical lifecycle filter or None when no filter was supplied."""
    if not isinstance(lifecycle_status, str) or not lifecycle_status:
        return None
    return normalise_lifecycle_status(lifecycle_status.upper())


def _strategy_ids_for_lifecycle(
    lottery_type: str,
    lifecycle_status: Optional[str],
) -> tuple[Optional[str], Optional[frozenset[str]]]:
    """Resolve a lifecycle filter to canonical status + matching strategy ids."""
    canonical_lc = _normalise_lifecycle_filter(lifecycle_status)
    if not canonical_lc:
        return None, None
    matched = list_strategies(
        lottery_type=lottery_type,
        lifecycle_status=canonical_lc,
    )
    return canonical_lc, frozenset(s["strategy_id"] for s in matched)


# ─── Strategy listing ─────────────────────────────────────────────────────────

@router.get("/api/replay/strategies")
async def list_replay_strategies(
    lottery_type:     Optional[str] = Query(None),
    lifecycle_status: Optional[str] = Query(
        None,
        description=(
            "Filter by lifecycle status: "
            "ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED. "
            "If omitted, ALL lifecycle states are returned."
        ),
    ),
):
    """
    Lists ALL registered replay strategies across all lifecycle states (P0-A).

    Optional filters:
      lottery_type     — POWER_LOTTO | BIG_LOTTO | DAILY_539
      lifecycle_status — ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED

    Each entry includes 'strategy_lifecycle_status'.
    READ-ONLY. Does NOT trigger replay generation.
    """
    try:
        strategies = list_strategies(
            lottery_type=lottery_type,
            lifecycle_status=lifecycle_status,
        )
        return {
            "strategies":              strategies,
            "count":                   len(strategies),
            "filter_lottery_type":     lottery_type,
            "filter_lifecycle_status": lifecycle_status,
            # backward-compat alias
            "filter":                  lottery_type,
        }
    except Exception as e:
        logger.exception("list_replay_strategies failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Lifecycle metadata (P7 read-only) ───────────────────────────────────────

@router.get("/api/replay/strategy-lifecycle")
async def get_strategy_lifecycle():
    """
    Returns the full strategy lifecycle registry as a read-only snapshot.

    All data is sourced from the in-memory registry.
    No sqlite3 connection is opened. No file is written.
    No replay execution is performed.

    READ-ONLY. Does NOT trigger any prediction or replay generation.
    Non-ONLINE strategies are listed but cannot be used for replay execution.
    """
    try:
        metadata = list_strategy_lifecycle_metadata()
        counts = summarize_strategy_lifecycle_counts()
        exec_ids = list_executable_strategy_ids()
        non_exec_ids = list_non_executable_strategy_ids()

        strategies = [
            {
                "strategy_id":             m["strategy_id"],
                "strategy_name":           m.get("strategy_name", ""),
                "strategy_version":        m.get("strategy_version", ""),
                "supported_lottery_types": m.get("supported_lottery_types", []),
                "min_history":             m.get("min_history"),
                "lifecycle_status":        m["lifecycle_status"],
                "is_executable":           m["strategy_id"] in set(exec_ids),
            }
            for m in metadata
        ]

        return {
            "total":                     len(metadata),
            "lifecycle_counts":          counts,
            "executable_strategy_ids":   exec_ids,
            "non_executable_strategy_ids": non_exec_ids,
            "strategies":                strategies,
            "no_db_write":               True,
            "no_db_write_note": (
                "All data sourced from in-memory registry. "
                "No sqlite3 connection opened. No replay execution performed."
            ),
            "marker": "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY",
            "disclaimer": _DISCLAIMER,
        }
    except Exception as e:
        logger.exception("get_strategy_lifecycle failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── History query ────────────────────────────────────────────────────────────

@router.get("/api/replay/history")
async def get_replay_history(
    lottery_type:     str            = Query(..., description="POWER_LOTTO | BIG_LOTTO | DAILY_539"),
    strategy_id:      Optional[str]  = Query(None),
    replay_status:    Optional[str]  = Query(None),
    lifecycle_status: Optional[str]  = Query(
        None,
        description=(
            "Filter by strategy lifecycle status: "
            "ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED. "
            "If omitted, all lifecycle states are included."
        ),
    ),
    date_from:        Optional[str]  = Query(None),
    date_to:          Optional[str]  = Query(None),
    page:             int            = Query(1, ge=1),
    page_size:        int            = Query(50, ge=1, le=200),
):
    """
    Paginated query of historical replay records for a given lottery type.

    Optional filters:
      - strategy_id      — e.g. "power_precision_3bet"
      - replay_status    — PREDICTED | REJECTED | INSUFFICIENT_HISTORY | …
      - lifecycle_status — ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED (P0-C)
      - date_from        — target_date >= date_from (YYYY-MM-DD)
      - date_to          — target_date <= date_to   (YYYY-MM-DD)

    Each record includes 'strategy_lifecycle_status' (P0-C).
    READ-ONLY. Does NOT trigger replay generation.
    """
    try:
        # Resolve lifecycle_status filter → strategy_id set (P0-C)
        _lc_filter, lifecycle_strategy_ids = _strategy_ids_for_lifecycle(
            lottery_type=lottery_type,
            lifecycle_status=lifecycle_status,
        )

        # Build lifecycle lookup for response enrichment (strategy_id → lifecycle_status)
        conn = _open_conn()
        try:
            where_parts = ["lottery_type = ?"]
            params: list = [lottery_type]

            if strategy_id:
                where_parts.append("strategy_id = ?")
                params.append(strategy_id)
            if replay_status:
                where_parts.append("replay_status = ?")
                params.append(replay_status)
            # lifecycle_status filter applied via strategy_id IN (...) clause
            if lifecycle_strategy_ids is not None:
                if not lifecycle_strategy_ids:
                    # No strategies match; return empty result set
                    return {
                        "total":                   0,
                        "page":                    page,
                        "page_size":               page_size,
                        "pages":                   1,
                        "filter_lifecycle_status": _lc_filter,
                        "records":                 [],
                    }
                placeholders = ",".join("?" * len(lifecycle_strategy_ids))
                where_parts.append(f"strategy_id IN ({placeholders})")
                params.extend(sorted(lifecycle_strategy_ids))
            if date_from:
                where_parts.append("target_date >= ?")
                params.append(date_from)
            if date_to:
                where_parts.append("target_date <= ?")
                params.append(date_to)

            where_sql = " AND ".join(where_parts)

            # total count
            count_row = conn.execute(
                f"SELECT COUNT(*) FROM strategy_prediction_replays WHERE {where_sql}",
                params,
            ).fetchone()
            total = count_row[0] if count_row else 0

            # paginated data
            offset = (page - 1) * page_size
            rows = conn.execute(
                f"""
                SELECT
                    id, lottery_type, target_draw, target_date,
                    strategy_id, strategy_name, strategy_version,
                    history_cutoff_draw, replay_status, reject_reason,
                    predicted_numbers, predicted_special,
                    actual_numbers, actual_special,
                    hit_numbers, hit_count, special_hit,
                    replay_run_id, generated_at
                FROM strategy_prediction_replays
                WHERE {where_sql}
                ORDER BY target_draw DESC, strategy_id ASC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

            records = []
            for r in rows:
                records.append({
                    "id":                       r["id"],
                    "lottery":                  r["lottery_type"],
                    "lottery_type":             r["lottery_type"],
                    "target_draw":              r["target_draw"],
                    "target_date":              r["target_date"],
                    "strategy_id":              r["strategy_id"],
                    "strategy_name":            r["strategy_name"],
                    "strategy_version":         r["strategy_version"],
                    "history_cutoff":           r["history_cutoff_draw"],
                    "replay_status":            r["replay_status"],
                    "reject_reason":            r["reject_reason"],
                    "predicted_numbers":        _parse_json(r["predicted_numbers"]),
                    "predicted_special":        r["predicted_special"],
                    "actual_numbers":           _parse_json(r["actual_numbers"]),
                    "actual_special":           r["actual_special"],
                    "hit_numbers":              _parse_json(r["hit_numbers"]),
                    "hit_count":                r["hit_count"],
                    "special_hit":              r["special_hit"],
                    "replay_run_id":            r["replay_run_id"],
                    "generated_at":             r["generated_at"],
                    "lifecycle_status":         get_strategy_lifecycle_status(r["strategy_id"]),
                    # P0-C: strategy lifecycle status from registry (read-only)
                    "strategy_lifecycle_status": get_strategy_lifecycle_status(r["strategy_id"]),
                })

            return {
                "total":                   total,
                "page":                    page,
                "page_size":               page_size,
                "pages":                   max(1, (total + page_size - 1) // page_size),
                "filter_lifecycle_status": _lc_filter,
                "records":                 records,
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_replay_history failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Summary / hit-rate aggregation ──────────────────────────────────────────

@router.get("/api/replay/summary")
async def get_replay_summary(
    lottery_type: str           = Query(...),
    strategy_id:  Optional[str] = Query(None),
    lifecycle_status: Optional[str] = Query(
        None,
        description=(
            "Filter by strategy lifecycle status: "
            "ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED. "
            "If omitted, all lifecycle states are included."
        ),
    ),
    date_from:    Optional[str] = Query(None),
    date_to:      Optional[str] = Query(None),
):
    """
    Aggregated hit-rate summary per strategy for a lottery type.

    Returns per-strategy stats:
      - total_draws        — number of draws with PREDICTED status
      - avg_hit_count      — mean number of main-number hits per draw
      - hit_3plus_count    — draws where hit_count >= 3
      - special_hit_count  — draws where special_hit = 1
      - non_predicted      — draws with status != PREDICTED (with breakdown)

    DISCLAIMER: These are historical replay statistics only.
    They do NOT constitute a validated result claim.
    """
    try:
        conn = _open_conn()
        try:
            _lc_filter, lifecycle_strategy_ids = _strategy_ids_for_lifecycle(
                lottery_type=lottery_type,
                lifecycle_status=lifecycle_status,
            )

            where_parts = ["lottery_type = ?"]
            params: list = [lottery_type]
            if strategy_id:
                where_parts.append("strategy_id = ?")
                params.append(strategy_id)
            if lifecycle_strategy_ids is not None:
                if not lifecycle_strategy_ids:
                    return {
                        "lottery_type": lottery_type,
                        "filter":       {"strategy_id": strategy_id, "date_from": date_from, "date_to": date_to},
                        "filter_lifecycle_status": _lc_filter,
                        "summaries":    [],
                        "disclaimer":   (
                            "本摘要為歷史預測回放統計，只用於查詢與稽核；"
                            "不代表提高中獎率，也不保證任何回放結果。"
                        ),
                        "data_scope":         "ALL_REPLAY_ROWS",
                        "legacy_error_count": 0,
                        "has_legacy_errors":  False,
                        "scope_note":         None,
                    }
                placeholders = ",".join("?" * len(lifecycle_strategy_ids))
                where_parts.append(f"strategy_id IN ({placeholders})")
                params.extend(sorted(lifecycle_strategy_ids))
            if date_from:
                where_parts.append("target_date >= ?")
                params.append(date_from)
            if date_to:
                where_parts.append("target_date <= ?")
                params.append(date_to)
            where_sql = " AND ".join(where_parts)

            # Per-strategy summary — only PREDICTED rows for hit stats
            agg_rows = conn.execute(
                f"""
                SELECT
                    strategy_id,
                    strategy_name,
                    COUNT(*) as total,
                    SUM(CASE WHEN replay_status='PREDICTED' THEN 1 ELSE 0 END) as predicted_count,
                    AVG(CASE WHEN replay_status='PREDICTED' THEN hit_count ELSE NULL END) as avg_hit,
                    SUM(CASE WHEN replay_status='PREDICTED' AND hit_count >= 3 THEN 1 ELSE 0 END) as hit3plus,
                    SUM(CASE WHEN replay_status='PREDICTED' AND special_hit=1 THEN 1 ELSE 0 END) as spec_hit,
                    SUM(CASE WHEN replay_status='REJECTED' THEN 1 ELSE 0 END) as rejected_count,
                    SUM(CASE WHEN replay_status='INSUFFICIENT_HISTORY' THEN 1 ELSE 0 END) as insuf_count,
                    SUM(CASE WHEN replay_status='REPLAY_ERROR' THEN 1 ELSE 0 END) as error_count
                FROM strategy_prediction_replays
                WHERE {where_sql}
                GROUP BY strategy_id, strategy_name
                ORDER BY strategy_id
                """,
                params,
            ).fetchall()

            summaries = []
            for r in agg_rows:
                predicted = r["predicted_count"] or 0
                avg_hit   = round(r["avg_hit"], 3) if r["avg_hit"] is not None else None
                summaries.append({
                    "strategy_id":        r["strategy_id"],
                    "strategy_name":      r["strategy_name"],
                    "total_rows":         r["total"],
                    "predicted_count":    predicted,
                    "avg_hit_count":      avg_hit,
                    "hit_3plus_count":    r["hit3plus"] or 0,
                    "special_hit_count":  r["spec_hit"] or 0,
                    "rejected_count":     r["rejected_count"] or 0,
                    "insufficient_count": r["insuf_count"] or 0,
                    "error_count":        r["error_count"] or 0,
                })

            disclaimer = (
                "本摘要為歷史預測回放統計，只用於查詢與稽核；"
                "不代表提高中獎率，也不保證任何回放結果。"
            )

            # Count legacy errors for this lottery type (from FAILED_LEGACY runs only)
            legacy_err_for_type = conn.execute(
                """
                SELECT COUNT(*) FROM strategy_prediction_replays spr
                JOIN strategy_replay_runs srr ON spr.replay_run_id = srr.id
                WHERE spr.lottery_type = ?
                  AND spr.replay_status = 'REPLAY_ERROR'
                  AND srr.status = 'FAILED_LEGACY'
                """,
                (lottery_type,),
            ).fetchone()[0]

            scope_note = (
                "本摘要包含所有歷史 replay runs，含已標記為 FAILED_LEGACY 的舊版 run。"
                "舊版 error rows 已保留供稽核，不代表最新 coverage run 出現錯誤。"
            ) if legacy_err_for_type > 0 else None

            return {
                "lottery_type": lottery_type,
                "filter":       {"strategy_id": strategy_id, "date_from": date_from, "date_to": date_to},
                "filter_lifecycle_status": _lc_filter,
                "summaries":    summaries,
                "disclaimer":   disclaimer,
                "data_scope":         "ALL_REPLAY_ROWS",
                "legacy_error_count": legacy_err_for_type,
                "has_legacy_errors":  legacy_err_for_type > 0,
                "scope_note":         scope_note,
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_replay_summary failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Replay runs list ─────────────────────────────────────────────────────────

@router.get("/api/replay/runs")
async def list_replay_runs(
    lottery_type: Optional[str] = Query(None),
    page:      int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Lists all replay_run records, newest first."""
    try:
        conn = _open_conn()
        try:
            where_parts = []
            params: list = []
            if lottery_type:
                where_parts.append("lottery_type = ?")
                params.append(lottery_type)
            where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

            total = conn.execute(
                f"SELECT COUNT(*) FROM strategy_replay_runs {where_sql}", params
            ).fetchone()[0]

            offset = (page - 1) * page_size
            rows = conn.execute(
                f"""
                SELECT id, lottery_type, strategy_scope, started_at, finished_at,
                       status, generator_version, data_hash, notes, created_at
                FROM strategy_replay_runs
                {where_sql}
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

            runs = [dict(r) for r in rows]
            return {"total": total, "page": page, "page_size": page_size, "runs": runs}
        finally:
            conn.close()
    except Exception as e:
        logger.exception("list_replay_runs failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/replay/run/{run_id}/status")
async def get_replay_run_status(run_id: int):
    """Returns the status and row counts for a single replay run."""
    try:
        conn = _open_conn()
        try:
            row = conn.execute(
                "SELECT * FROM strategy_replay_runs WHERE id = ?", (run_id,)
            ).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"run_id={run_id} not found")

            counts = conn.execute(
                """
                SELECT replay_status, COUNT(*) as cnt
                FROM strategy_prediction_replays
                WHERE replay_run_id = ?
                GROUP BY replay_status
                """,
                (run_id,),
            ).fetchall()

            return {
                "run":           dict(row),
                "status_counts": {r["replay_status"]: r["cnt"] for r in counts},
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_replay_run_status failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Freshness / Coverage Status ─────────────────────────────────────────────

def _detect_coverage_mode(notes: Optional[str]) -> str:
    """
    Parse run notes to determine coverage mode.

    Expected format: 'draws=<N>, window=[<start>..<end>]'
    - If window covers ALL draws (start <= 1 and window_size >= total_draws): FULL
    - Otherwise: LIMITED
    - If notes are absent or unparseable: UNKNOWN
    """
    if not notes:
        return "UNKNOWN"
    m = re.search(r'draws=(\d+)[,\s]+window=\[(\d+)\.\.(\d+)\]', notes)
    if not m:
        return "UNKNOWN"
    total_draws  = int(m.group(1))
    window_start = int(m.group(2))
    window_end   = int(m.group(3))
    window_size  = window_end - window_start + 1
    if window_start <= 1 and window_size >= total_draws:
        return "FULL"
    return "LIMITED"


@router.get("/api/replay/freshness")
async def get_replay_freshness(
    lifecycle_status: Optional[str] = Query(
        None,
        description=(
            "Filter by strategy lifecycle status: "
            "ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED. "
            "If omitted, all lifecycle states are included."
        ),
    ),
):
    """
    Returns data freshness / coverage status for the replay store.

    Reads from DB only — NOT from outputs/.
    Does NOT emit SIGNAL / NO_SIGNAL / NO_VALIDATED_EDGE.
    Use this endpoint to build the UI freshness badge and coverage advisory.
    """
    try:
        conn = _open_conn()
        try:
            # ── Global counts ──────────────────────────────────────────────
            total_rows = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0]
            total_predicted = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE replay_status = 'PREDICTED'"
            ).fetchone()[0]
            total_replay_error = conn.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE replay_status = 'REPLAY_ERROR'"
            ).fetchone()[0]

            # Legacy errors = REPLAY_ERROR rows from FAILED_LEGACY runs only
            legacy_error_count = conn.execute(
                """
                SELECT COUNT(*) FROM strategy_prediction_replays spr
                JOIN strategy_replay_runs srr ON spr.replay_run_id = srr.id
                WHERE spr.replay_status = 'REPLAY_ERROR'
                  AND srr.status = 'FAILED_LEGACY'
                """
            ).fetchone()[0]

            # ── Lottery types present ──────────────────────────────────────
            lt_rows = conn.execute(
                "SELECT DISTINCT lottery_type FROM strategy_replay_runs ORDER BY lottery_type"
            ).fetchall()
            lottery_types = [r[0] for r in lt_rows]

            # ── Per-lottery latest run (excluding FAILED_LEGACY) ───────────
            per_lottery: list = []
            per_cov_modes: list = []

            for lt in lottery_types:
                latest = conn.execute(
                    """
                    SELECT * FROM strategy_replay_runs
                    WHERE lottery_type = ? AND status != 'FAILED_LEGACY'
                    ORDER BY id DESC LIMIT 1
                    """,
                    (lt,),
                ).fetchone()

                if not latest:
                    per_lottery.append({
                        "lottery_type":    lt,
                        "replay_run_id":   None,
                        "status":          "NO_VALID_RUN",
                        "started_at":      None,
                        "finished_at":     None,
                        "notes":           None,
                        "row_count":       0,
                        "predicted_count": 0,
                        "error_count":     0,
                        "coverage_mode":   "UNKNOWN",
                    })
                    per_cov_modes.append("UNKNOWN")
                    continue

                run_id = latest["id"]
                row_count = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays WHERE replay_run_id = ?",
                    (run_id,),
                ).fetchone()[0]
                predicted_count = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays WHERE replay_run_id = ? AND replay_status = 'PREDICTED'",
                    (run_id,),
                ).fetchone()[0]
                error_count = conn.execute(
                    "SELECT COUNT(*) FROM strategy_prediction_replays WHERE replay_run_id = ? AND replay_status = 'REPLAY_ERROR'",
                    (run_id,),
                ).fetchone()[0]

                cov_mode = _detect_coverage_mode(latest["notes"])
                per_cov_modes.append(cov_mode)

                per_lottery.append({
                    "lottery_type":    lt,
                    "replay_run_id":   run_id,
                    "status":          latest["status"],
                    "started_at":      latest["started_at"],
                    "finished_at":     latest["finished_at"],
                    "notes":           latest["notes"],
                    "row_count":       row_count,
                    "predicted_count": predicted_count,
                    "error_count":     error_count,
                    "coverage_mode":   cov_mode,
                })

            # ── Global coverage mode ───────────────────────────────────────
            if not per_cov_modes:
                global_cov_mode = "UNKNOWN"
            elif all(m == "FULL" for m in per_cov_modes):
                global_cov_mode = "FULL"
            elif any(m == "LIMITED" for m in per_cov_modes):
                global_cov_mode = "LIMITED"
            else:
                global_cov_mode = "UNKNOWN"

            # ── Overall latest valid run ───────────────────────────────────
            latest_overall = conn.execute(
                "SELECT * FROM strategy_replay_runs WHERE status != 'FAILED_LEGACY' ORDER BY id DESC LIMIT 1"
            ).fetchone()

            return {
                "generated_at":          datetime.now(timezone.utc).isoformat(),
                "coverage_mode":         global_cov_mode,
                "filter_lifecycle_status": _normalise_lifecycle_filter(lifecycle_status),
                "total_rows":            total_rows,
                "total_predicted":       total_predicted,
                "total_replay_error":    total_replay_error,
                "legacy_error_count":    legacy_error_count,
                "has_legacy_errors":     legacy_error_count > 0,
                "lottery_types":         lottery_types,
                "latest_run_id":         latest_overall["id"] if latest_overall else None,
                "latest_run_status":     latest_overall["status"] if latest_overall else None,
                "latest_run_started_at": latest_overall["started_at"] if latest_overall else None,
                "latest_run_finished_at": latest_overall["finished_at"] if latest_overall else None,
                "per_lottery_latest_run": per_lottery,
                "disclaimer": _DISCLAIMER,
            }
        finally:
            conn.close()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_replay_freshness failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _parse_json(val):
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return val
    try:
        return json.loads(val)
    except Exception:
        return val
