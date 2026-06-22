"""
Replay API Routes (Strategy Historical Prediction Replay Store v0.1)

GET  /api/replay/strategies          — 列出所有已登錄策略（可按彩種過濾）
GET  /api/replay/history             — 分頁查詢歷史回放記錄
GET  /api/replay/summary             — 按策略聚合命中率摘要
GET  /api/replay/runs                — 列出 replay_run 記錄
GET  /api/replay/run/{run_id}/status — 查詢單一 replay_run 狀態
GET  /api/replay/history-overview    — P259A 回放總覽（策略層級摘要，預設 bet_index=1）
GET  /api/replay/history-detail      — P259B 回放明細（單策略每期分頁查詢，server-side pagination）
GET  /api/replay/history-detail-grouped — P261A 回放明細（依 target_draw 分組，一列一 draw，內含多注 bets[]）

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
from lottery_api.models.replay_strategy_state_labels import (
    get_full_label_catalog as _p26_get_full_label_catalog,
    get_label_summary as _p26_get_label_summary,
    _load_p24_inventory as _p26_load_p24_inventory,
)

_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

router = APIRouter()
logger = logging.getLogger(__name__)
_FIXTURE_HISTORY_PATH = Path(_api_root).parent / "outputs" / "replay" / "non_online_replay_fixture_20260511.json"
_FIXTURE_SOURCE = "synthetic_fixture"
_EVIDENCE_DASHBOARD_PATH = (
    Path(_api_root).parent
    / "outputs"
    / "research"
    / "p251b_cross_lottery_evidence_dashboard_data_20260606.json"
)
_BEST_STRATEGY_OVERVIEW_PATH = (
    Path(_api_root).parent
    / "outputs"
    / "research"
    / "p257a_best_nbet_strategy_overview_historical_replay_20260608.json"
)
_D3_STRATEGY_STATUS_AUDIT_PATH = (
    Path(_api_root).parent
    / "outputs"
    / "research"
    / "p258n_d3_strategy_status_audit_payload_20260609.json"
)
_BIG649_MEASUREMENT_EXPORT_PATH = (
    Path(_api_root).parent
    / "outputs"
    / "research"
    / "big649_measurement_export_20260621.json"
)

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


def _load_fixture_history_payload() -> dict:
    if not _FIXTURE_HISTORY_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"fixture history artifact not found: {_FIXTURE_HISTORY_PATH}",
        )
    try:
        with _FIXTURE_HISTORY_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"fixture history artifact is invalid JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=500,
            detail="fixture history artifact must be a JSON object",
        )
    return payload


def _fixture_history_record(
    raw_record: dict,
    *,
    fixture_version: str,
    generated_at: Optional[str],
    row_id: int,
) -> dict:
    prediction = raw_record.get("prediction_payload") or {}
    actual = raw_record.get("actual_result_payload") or {}
    comparison = raw_record.get("comparison_result") or {}
    lifecycle_status = raw_record.get("lifecycle_status") or "UNKNOWN"
    fixture_row_id = raw_record.get("fixture_row_id") or f"fixture-row-{row_id}"

    return {
        "id": row_id,
        "lottery": raw_record.get("lottery_type") or "UNKNOWN",
        "lottery_type": raw_record.get("lottery_type") or "UNKNOWN",
        "target_draw": raw_record.get("draw_id") or fixture_row_id,
        "target_date": raw_record.get("draw_date"),
        "strategy_id": raw_record.get("strategy_id") or fixture_row_id,
        "strategy_name": raw_record.get("strategy_id") or fixture_row_id,
        "strategy_version": fixture_version,
        "history_cutoff": None,
        "replay_status": "PREDICTED",
        "reject_reason": None,
        "predicted_numbers": prediction.get("numbers") or [],
        "predicted_special": None,
        "actual_numbers": actual.get("numbers") or [],
        "actual_special": None,
        "hit_numbers": comparison.get("matched_numbers") or [],
        "hit_count": int(comparison.get("hit_count") or 0),
        "special_hit": 0,
        "replay_run_id": fixture_row_id,
        "generated_at": generated_at,
        "truth_level": "FIXTURE_SYNTHETIC",
        "lifecycle_status": lifecycle_status,
        "strategy_lifecycle_status": lifecycle_status,
        "fixture_mode": True,
        "source": _FIXTURE_SOURCE,
        "advisory_only": True,
        "production_db_write": False,
        "synthetic_only": True,
        "fixture_only": True,
        "fixture_source": raw_record.get("fixture_source") or "non_online_lifecycle_fixture",
        "governance_marker": raw_record.get("governance_marker") or "P21_NON_ONLINE_FIXTURE_ROW",
    }


def _fixture_history_response(
    *,
    lifecycle_status: Optional[str],
    strategy_id: Optional[str],
    replay_status: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    page: int,
    page_size: int,
) -> dict:
    payload = _load_fixture_history_payload()
    canonical_lc = _normalise_lifecycle_filter(lifecycle_status)
    fixture_version = str(payload.get("fixture_version") or "fixture")
    generated_at = payload.get("generated_at")

    records = []
    for raw_record in payload.get("records", []):
        record_lc = raw_record.get("lifecycle_status") or "UNKNOWN"
        if canonical_lc and record_lc != canonical_lc:
            continue
        if strategy_id and raw_record.get("strategy_id") != strategy_id:
            continue
        if replay_status and replay_status != "PREDICTED":
            continue
        draw_date = raw_record.get("draw_date") or ""
        if date_from and draw_date < date_from:
            continue
        if date_to and draw_date > date_to:
            continue
        records.append(
            _fixture_history_record(
                raw_record,
                fixture_version=fixture_version,
                generated_at=generated_at,
                row_id=len(records) + 1,
            )
        )

    total = len(records)
    pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    page_records = records[offset: offset + page_size]

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": pages,
        "filter_lifecycle_status": canonical_lc,
        "fixture_mode": True,
        "source": _FIXTURE_SOURCE,
        "advisory_only": True,
        "production_db_write": False,
        "synthetic_only": True,
        "fixture_only": True,
        "fixture_name": payload.get("fixture_name"),
        "fixture_version": fixture_version,
        "generated_at": generated_at,
        "records": page_records,
        "disclaimer": (
            _DISCLAIMER
            + " 此模式回傳合成 fixture，僅供驗收與 UI bridge 驗證，不代表真實預測。"
        ),
    }


# ─── Strategy listing ─────────────────────────────────────────────────────────

_PUBLIC_LIFECYCLE = frozenset({"ONLINE", "OBSERVATION"})


def get_strategies_response(
    lottery_type:     Optional[str] = None,
    lifecycle_status: Optional[str] = None,
    public_only:      bool          = False,
) -> dict:
    """
    Business logic for GET /api/replay/strategies.

    Extracted as a plain sync function so tests can call it directly
    without FastAPI Query-object coercion issues.

    public_only=True restricts to ONLINE/OBSERVATION lifecycle only and
    overrides any lifecycle_status filter.
    READ-ONLY. No DB write.
    """
    # Coerce to real bool — guards against Query(False) objects in direct calls
    _public_only = bool(public_only) if isinstance(public_only, bool) else False

    effective_lifecycle = None if _public_only else lifecycle_status

    strategies = list_strategies(
        lottery_type=lottery_type,
        lifecycle_status=effective_lifecycle,
    )

    if _public_only:
        strategies = [
            s for s in strategies
            if s.get("strategy_lifecycle_status", "") in _PUBLIC_LIFECYCLE
        ]

    return {
        "strategies":              strategies,
        "count":                   len(strategies),
        "filter_lottery_type":     lottery_type,
        "filter_lifecycle_status": lifecycle_status,
        "filter_public_only":      _public_only,
        "filter":                  lottery_type,  # backward-compat alias
    }


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
    public_only: bool = Query(
        False,
        description=(
            "When true, restrict to public-visible strategies only "
            "(lifecycle_status ONLINE or OBSERVATION). "
            "Internal states (REJECTED, RETIRED, OFFLINE) are excluded."
        ),
    ),
):
    """
    Lists registered replay strategies.

    Optional filters:
      lottery_type     — POWER_LOTTO | BIG_LOTTO | DAILY_539
      lifecycle_status — ONLINE | OFFLINE | REJECTED | OBSERVATION | RETIRED
      public_only      — when true, only ONLINE/OBSERVATION strategies returned

    Each entry includes 'strategy_lifecycle_status'.
    READ-ONLY. Does NOT trigger replay generation.
    """
    try:
        return get_strategies_response(
            lottery_type=lottery_type,
            lifecycle_status=lifecycle_status,
            public_only=bool(public_only),
        )
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
        fixture_mode:     bool           = Query(
            False,
            description="Read synthetic fixture replay rows instead of the production DB.",
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
        if fixture_mode:
            return _fixture_history_response(
                lifecycle_status=lifecycle_status,
                strategy_id=strategy_id,
                replay_status=replay_status,
                date_from=date_from,
                date_to=date_to,
                page=page,
                page_size=page_size,
            )

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
                    replay_run_id, generated_at, truth_level,
                    controlled_apply_id, source, provenance_hash, provenance_source,
                    prediction_cutoff_date, prediction_generated_at
                FROM strategy_prediction_replays
                WHERE {where_sql}
                ORDER BY CAST(target_draw AS INTEGER) DESC, strategy_id ASC
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

            records = []
            for r in rows:
                actual_nums = _parse_json(r["actual_numbers"])
                hit_cnt     = r["hit_count"]
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
                    "actual_numbers":           actual_nums,
                    "actual_special":           r["actual_special"],
                    "hit_numbers":              _parse_json(r["hit_numbers"]),
                    "hit_count":                hit_cnt,
                    "special_hit":              r["special_hit"],
                    "replay_run_id":            r["replay_run_id"],
                    "generated_at":             r["generated_at"],
                    "truth_level":              r["truth_level"],
                    "controlled_apply_id":      r["controlled_apply_id"],
                    "source":                   r["source"],
                    "provenance_hash":          r["provenance_hash"],
                    "provenance_source":        r["provenance_source"],
                    "lifecycle_status":         get_strategy_lifecycle_status(r["strategy_id"]),
                    # P0-C: strategy lifecycle status from registry (read-only)
                    "strategy_lifecycle_status": get_strategy_lifecycle_status(r["strategy_id"]),
                    # P5: P3 coverage matrix fields (minimal patch — non-breaking)
                    "visibility_state":         "ROW_BACKED",
                    "display_status":           "SHOW_REPLAY_RESULT",
                    "should_count_as_success":  actual_nums is not None and hit_cnt is not None,
                    "source_trace":             "|".join(filter(None, [
                        r["source"], r["truth_level"], r["provenance_hash"]
                    ])) or None,
                    # P17: prediction timestamp fields (NULL for rows applied before P16A)
                    "prediction_cutoff_date":   r["prediction_cutoff_date"],
                    "prediction_generated_at":  r["prediction_generated_at"],
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


# ─── P28: Strategy Catalog ────────────────────────────────────────────────────

_SAFE_USER_MESSAGES: dict[str, str] = {
    "row-backed":          "Replay rows available in DB — queryable via /api/replay/history.",
    "artifact-only":       "尚無 replay rows / artifact-only — 僅目錄展示。",
    "no-data":             "No replay rows and no recoverable artifact — catalog entry only.",
    "reconstructible":     "Logic recoverable from archive; not yet authorized for reconstruction.",
    "manual-review":       "Requires manual review before display.",
    "unsupported":         "Unsupported: insufficient source to reconstruct or replay.",
    "retired":             "已退役 — lifecycle preserved for reference only.",
    "rejected-registered": "已拒絕 / registered stub — MUST NOT be executed.",
    "observation":         "觀察中 — shadow evaluation, not in active production.",
}


def _build_catalog_entry(label_entry: dict, raw: dict) -> dict:
    """Merge P26 label entry with raw P24 fields for the catalog response."""
    primary = label_entry["primary_label"]
    safe_msg = _SAFE_USER_MESSAGES.get(primary, "Status unknown.")
    return {
        "strategy_id":               label_entry["strategy_id"],
        "display_name":              label_entry["display_name"],
        "lottery_type":              label_entry["lottery_type"],
        "lifecycle_state":           label_entry["lifecycle_state"],
        "replay_visibility_state":   label_entry["replay_visibility_state"],
        "primary_label":             primary,
        "label_display_name":        label_entry["label_display"],
        "label_description":         label_entry["label_description"],
        "row_count":                 label_entry["row_count"],
        "verified_row_count":        int(raw.get("verified_row_count") or 0),
        "is_row_backed":             label_entry["is_row_backed"],
        "is_queryable":              label_entry["queryable"],
        "reconstructible_candidate": label_entry["reconstructible_candidate"],
        "needs_manual_review":       bool(raw.get("needs_manual_review")),
        "unsupported_reason":        raw.get("unsupported_reason"),
        "safe_user_message":         safe_msg,
        "source_artifact":           raw.get("source_artifact"),
        "source_path":               raw.get("source_path"),
    }


@router.get("/api/replay/strategy-catalog")
async def get_replay_strategy_catalog():
    """
    P28: Read-only strategy catalog exposing all 59 P24 strategies with P26 safety labels.

    Each entry shows which strategies are row-backed (queryable) vs
    artifact-only / retired / rejected / observation.

    READ-ONLY: no DB write, no migrations, no strategy execution.
    Label source: lottery_api/models/replay_strategy_state_labels.py (P26 module).
    """
    try:
        label_catalog = _p26_get_full_label_catalog()
        raw_inventory = _p26_load_p24_inventory()
        raw_by_id = {s["strategy_id"]: s for s in raw_inventory}

        strategies = [
            _build_catalog_entry(entry, raw_by_id.get(entry["strategy_id"], {}))
            for entry in label_catalog
        ]

        label_summary = _p26_get_label_summary()

        return {
            "generated_at":     datetime.now(timezone.utc).isoformat(),
            "phase":            "P28",
            "total_strategies": len(strategies),
            "label_summary":    label_summary,
            "row_backed_count": label_summary.get("row-backed", 0),
            "non_row_backed_count": len(strategies) - label_summary.get("row-backed", 0),
            "strategies":       strategies,
            "no_db_write":      True,
            "p26_label_module": "lottery_api/models/replay_strategy_state_labels.py",
            "disclaimer":       _DISCLAIMER,
        }
    except Exception as e:
        logger.exception("get_replay_strategy_catalog failed")
        raise HTTPException(status_code=500, detail=str(e))


def _load_evidence_dashboard_payload() -> dict:
    """Load the published P251B evidence dashboard artifact without mutating state."""
    if not _EVIDENCE_DASHBOARD_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"evidence dashboard artifact not found: {_EVIDENCE_DASHBOARD_PATH}",
        )
    try:
        with _EVIDENCE_DASHBOARD_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"evidence dashboard artifact is invalid JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=500,
            detail="evidence dashboard artifact must be a JSON object",
        )
    return payload


@router.get("/api/replay/evidence-dashboard")
async def get_replay_evidence_dashboard():
    """
    P251D: Read-only evidence dashboard payload.

    Serves the published P251B dashboard artifact using the P251C contract path.
    READ-ONLY: no DB query, no registry mutation, no prediction generation.
    """
    try:
        return _load_evidence_dashboard_payload()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_replay_evidence_dashboard failed")
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


def _load_best_strategy_overview_payload() -> dict:
    """Load the P257A best-strategy overview artifact without mutating state."""
    if not _BEST_STRATEGY_OVERVIEW_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"best strategy overview artifact not found: {_BEST_STRATEGY_OVERVIEW_PATH}",
        )
    try:
        with _BEST_STRATEGY_OVERVIEW_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"best strategy overview artifact is invalid JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=500,
            detail="best strategy overview artifact must be a JSON object",
        )
    return payload


@router.get("/api/replay/best-strategy-overview")
async def get_replay_best_strategy_overview():
    """
    P257B: Read-only best N-bet strategy overview payload.

    Serves the published P257A historical replay artifact.
    Data source: P257A artifact (NOT DB query, NOT registry mutation, NOT prediction generation).

    Returns best N-bet portfolio rankings per lottery, historical high-hit events,
    page contract, and warning copy. All data is historical replay only.

    READ-ONLY: no DB query, no registry mutation, no strategy promotion, no betting advice.
    """
    try:
        payload = _load_best_strategy_overview_payload()
        # Wrap with explicit metadata flags for API consumers
        return {
            **payload,
            "historical_replay_only": True,
            "no_future_guarantee": True,
            "no_betting_advice": True,
            "no_strategy_promotion": True,
            "source_artifact": str(_BEST_STRATEGY_OVERVIEW_PATH.name),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_replay_best_strategy_overview failed")
        raise HTTPException(status_code=500, detail=str(e))


def _load_d3_strategy_status_audit_payload() -> dict:
    """Load the P258N D3 strategy status audit artifact without mutating state."""
    if not _D3_STRATEGY_STATUS_AUDIT_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"D3 strategy status audit artifact not found: {_D3_STRATEGY_STATUS_AUDIT_PATH}",
        )
    try:
        with _D3_STRATEGY_STATUS_AUDIT_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"D3 strategy status audit artifact is invalid JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=500,
            detail="D3 strategy status audit artifact must be a JSON object",
        )
    return payload


@router.get("/api/replay/d3-strategy-status-audit")
async def get_d3_strategy_status_audit():
    """
    P258N: Read-only D3 strategy status / contract audit payload.

    Serves the published P258N artifact payload conforming to the P258M contract.
    Data source: P258N artifact only (NOT DB query, NOT registry mutation, NOT D3 execution).

    Returns a per-strategy index showing lifecycle status, evidence status, and D3
    contract-readiness status. D3 contract status is NOT approval and must not be
    interpreted as strategy promotion, recommendation, or improved prediction accuracy.

    READ-ONLY: no DB query, no registry mutation, no D3 execution, no null generation,
    no p-values, no strategy promotion, no betting advice.
    """
    try:
        return _load_d3_strategy_status_audit_payload()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_d3_strategy_status_audit failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── BIG649 Measurement Export (read-only, artifact-backed) ──────────────────

_BIG649_MEASUREMENT_EXPORT_ROUTE = "/api/replay/big649-measurement-export"
# API window query value -> internal frozen window name.
_BIG649_MEASUREMENT_WINDOWS = {
    "all_reference": "REFERENCE_ALL_ELIGIBLE",
    "recent_750": "RECENT_750",
    "recent_300": "RECENT_300",
    "recent_50": "RECENT_50",
}
# Metric scope query value -> measurement sub-payload key.
_BIG649_MEASUREMENT_SCOPES = {
    "ticket_slot": "per_strategy_ticket_level_distribution",
    "target_level": "per_strategy_target_level_distribution",
    "prize_aware": "per_strategy_prize_aware_distribution",
    "redundancy": "per_strategy_redundancy_diagnostics",
    "pairwise_overlap": "pairwise_ticket_overlap_diagnostics",
}


def _load_big649_measurement_export_payload() -> dict:
    """Load the committed BIG649 measurement-export artifact without mutating state.

    READ-ONLY: reads the committed artifact file only; performs NO DB query.
    """
    if not _BIG649_MEASUREMENT_EXPORT_PATH.exists():
        raise HTTPException(
            status_code=500,
            detail=f"big649 measurement export artifact not found: {_BIG649_MEASUREMENT_EXPORT_PATH}",
        )
    try:
        with _BIG649_MEASUREMENT_EXPORT_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"big649 measurement export artifact is invalid JSON: {exc}",
        ) from exc
    if not isinstance(payload, dict):
        raise HTTPException(
            status_code=500,
            detail="big649 measurement export artifact must be a JSON object",
        )
    if not isinstance(payload.get("payload"), dict):
        raise HTTPException(
            status_code=500,
            detail="big649 measurement export artifact missing 'payload' object",
        )
    return payload


@router.get("/api/replay/big649-measurement-export")
async def get_big649_measurement_export(
    window: str = Query(
        "all_reference",
        description="Measurement window: all_reference | recent_750 | recent_300 | recent_50.",
    ),
    metric_scope: str = Query(
        "ticket_slot",
        description=(
            "Metric scope: ticket_slot | target_level | prize_aware | redundancy "
            "| pairwise_overlap."
        ),
    ),
):
    """
    BIG649 read-only measurement export (artifact-backed).

    Serves a window + metric-scope slice of the committed BIG649 hit-distribution &
    redundancy measurement artifact (frozen contract ``big649_measurement_contract_v1``).
    Data source: the committed artifact ONLY (NOT a DB query, NOT registry mutation,
    NOT prediction generation). Strategy and pair rows are LEXICAL and unranked.

    READ-ONLY and MEASUREMENT-ONLY: this is a local historical measurement. It is NOT
    a ranking, recommendation, candidate classification, random baseline, p-value,
    payout, ROI, or official-prize statement, and it returns none of those.
    """
    if window not in _BIG649_MEASUREMENT_WINDOWS:
        raise HTTPException(
            status_code=400,
            detail=f"invalid window {window!r}; allowed: {sorted(_BIG649_MEASUREMENT_WINDOWS)}",
        )
    if metric_scope not in _BIG649_MEASUREMENT_SCOPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"invalid metric_scope {metric_scope!r}; "
                f"allowed: {sorted(_BIG649_MEASUREMENT_SCOPES)}"
            ),
        )
    try:
        artifact = _load_big649_measurement_export_payload()
        internal_window = _BIG649_MEASUREMENT_WINDOWS[window]
        sub_key = _BIG649_MEASUREMENT_SCOPES[metric_scope]
        sub = artifact["payload"].get(sub_key)
        if not isinstance(sub, dict):
            raise HTTPException(
                status_code=500,
                detail=f"big649 measurement export artifact missing sub-payload {sub_key!r}",
            )

        window_def = (artifact.get("window_definitions") or {}).get(internal_window)
        result = {
            "route_path": _BIG649_MEASUREMENT_EXPORT_ROUTE,
            "schema_version": artifact.get("schema_version"),
            "lottery_type": artifact.get("lottery_type"),
            "measurement_only_notice": artifact.get("measurement_only_notice"),
            "local_historical_measurement_disclaimer": artifact.get(
                "local_historical_measurement_disclaimer"
            ),
            "endpoint_support_status": artifact.get("endpoint_support_status"),
            "safety_limitations": artifact.get("safety_limitations"),
            "coverage_denominators": artifact.get("coverage_denominators"),
            "window_order": artifact.get("window_order"),
            "window": window,
            "window_internal": internal_window,
            "window_definition": window_def,
            "metric_scope": metric_scope,
            "source_artifact": _BIG649_MEASUREMENT_EXPORT_PATH.name,
            "historical_replay_only": True,
            "no_recommendation": True,
            "no_ranking": True,
            "no_betting_advice": True,
        }

        if metric_scope == "pairwise_overlap":
            pairs_out = []
            for row in sub.get("pairs", []):
                cell = (row.get("by_window") or {}).get(internal_window)
                pairs_out.append({"pair_key": row.get("pair_key"), "cell": cell})
            result["level"] = "STRUCTURAL_DIAGNOSTIC_PAIRWISE"
            result["pair_count"] = sub.get("pair_count")
            result["pairs_lexical"] = sub.get("pairs_lexical", [])
            result["pairs"] = pairs_out
            if "note" in sub:
                result["note"] = sub.get("note")
            return result

        # Per-strategy scopes: ticket_slot / target_level / prize_aware / redundancy.
        by_strategy_full = sub.get("by_strategy", {})
        strategy_order = sub.get("strategy_order_lexical", [])
        sliced = {}
        for sid in strategy_order:
            sliced[sid] = (by_strategy_full.get(sid) or {}).get(internal_window)
        result["strategy_order_lexical"] = strategy_order
        result["by_strategy"] = sliced
        if "level" in sub:
            result["level"] = sub.get("level")
        if "denominator_kind" in sub:
            result["denominator_kind"] = sub.get("denominator_kind")
        if metric_scope == "prize_aware" and "endpoint_definitions" in sub:
            result["endpoint_definitions"] = sub.get("endpoint_definitions")
        if metric_scope == "redundancy" and "note" in sub:
            result["note"] = sub.get("note")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_big649_measurement_export failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── P259A: History Replay Overview ─────────────────────────────────────────


def _derive_bet_count(strategy_id: str) -> int:
    """Derive declared bet count from strategy_id naming convention.

    Extracts the numeric suffix before 'bet' (e.g. '_3bet' → 3).
    Falls back to well-known special cases, then defaults to 1.
    """
    import re as _re
    m = _re.search(r'[_-](\d+)bet', strategy_id)
    if m:
        return int(m.group(1))
    if "triple_strike" in strategy_id:
        return 3
    return 1


_REPLAY_STATUS_CATEGORIES = {
    "has_rows":           "有 replay rows",
    "no_production_replay": "無 production replay",
    "artifact_only":      "僅 artifact / rejected artifact",
}

# ── P262B: coverage-remediation helpers (READ-ONLY) ──────────────────────────
# These let the overview surface EVERY known strategy cell — including DB orphan
# strategies (replay rows but unregistered) and registry/lottery mismatches
# (rows under a lottery_type the registry does not list) — and explain WHY a
# cell lacks coverage, without backfilling rows, writing the DB, or touching the
# strategy registry / adapters.

_REGISTRY_STATUS_REGISTERED = "registered"
_REGISTRY_STATUS_ORPHAN     = "unregistered_orphan"
_REGISTRY_STATUS_MISMATCH   = "registry_lottery_mismatch"


def _parse_bet_indices_csv(csv_val) -> list:
    """Parse a GROUP_CONCAT(DISTINCT bet_index) CSV into a sorted int list."""
    if not csv_val:
        return []
    seen = set()
    for tok in str(csv_val).split(","):
        tok = tok.strip()
        if tok.lstrip("-").isdigit():
            seen.add(int(tok))
    return sorted(seen)


def _coverage_missing_reason(registry_status: str, has_rows: bool,
                             lifecycle: str, replay_cat: str):
    """Read-only classification of WHY a coverage cell lacks production replay rows.

    Returns one of: registered_without_rows | artifact_only | observation_no_data
    | no_production_replay, or None when the cell HAS rows (orphan/mismatch cells
    have rows by definition and return None — their gap is registration, surfaced
    via coverage_warning instead).
    """
    if has_rows:
        return None
    if registry_status in (_REGISTRY_STATUS_ORPHAN, _REGISTRY_STATUS_MISMATCH):
        return None
    if lifecycle == "OBSERVATION":
        return "observation_no_data"
    if replay_cat == "artifact_only":
        return "artifact_only"
    if lifecycle in ("REJECTED", "RETIRED", "OFFLINE"):
        return "registered_without_rows"
    return "no_production_replay"


def _build_overview_row(*, lt: str, sid: str, strategy_name, strategy_version,
                        derived_bets: int, lifecycle: str, is_exec: bool,
                        db: Optional[dict], registry_status: str) -> dict:
    """Build one overview row. Existing P259A fields are preserved verbatim; P262B
    coverage fields are added additively. Pure function — no DB / side effects."""
    has_rows = db is not None and db["total_rows"] > 0

    # replay_status_category — identical rule to the original P259A endpoint.
    if has_rows:
        rcat = "has_rows"
    elif lifecycle in ("REJECTED",) and not is_exec:
        rcat = "artifact_only"
    else:
        rcat = "no_production_replay"

    missing_reason = _coverage_missing_reason(registry_status, has_rows, lifecycle, rcat)

    coverage_warning = None
    if registry_status == _REGISTRY_STATUS_ORPHAN:
        coverage_warning = (
            "unregistered_orphan: replay rows exist but this strategy_id is not in "
            "the strategy registry; the registry-only overview walk never surfaces it"
        )
    elif registry_status == _REGISTRY_STATUS_MISMATCH:
        coverage_warning = (
            "registry_lottery_mismatch: replay rows exist under a lottery_type not "
            "listed in the strategy registry supported_lottery_types"
        )

    return {
        # ── existing P259A fields (unchanged contract) ──
        "lottery_type":           lt,
        "strategy_id":            sid,
        "strategy_name":          strategy_name,
        "strategy_version":       strategy_version,
        "derived_bet_count":      derived_bets,
        "lifecycle_status":       lifecycle,
        "is_executable":          is_exec,
        "total_replay_rows":      db["total_rows"] if db else 0,
        "min_target_draw":        db["min_target_draw"] if db else None,
        "max_target_draw":        db["max_target_draw"] if db else None,
        "latest_target_draw":     db["latest_target_draw"] if db else None,
        "replay_status_summary":  db["replay_status_summary"] if db else {},
        "has_production_replay":  has_rows,
        "replay_status_category": rcat,
        # ── P262B additive coverage fields ──
        "has_replay_rows":        has_rows,
        "distinct_draw_count":    db["distinct_draw_count"] if db else 0,
        "max_bet_index":          db["max_bet_index"] if db else 0,
        "available_bet_indices":  db["available_bet_indices"] if db else [],
        "registry_status":        registry_status,
        "can_open_detail":        has_rows,
        "missing_reason":         missing_reason,
        "coverage_warning":       coverage_warning,
    }


@router.get("/api/replay/history-overview")
async def get_history_replay_overview(
    lottery_type:              Optional[str] = Query(
        None,
        description="Filter by lottery type: BIG_LOTTO | POWER_LOTTO | DAILY_539. "
                    "Omit or empty string for all lottery types.",
    ),
    bet_index:                 int           = Query(
        1,
        ge=0,
        le=5,
        description="Filter by derived bet count (1–5). Use 0 for all bet counts. Default 1.",
    ),
    replay_status_category:    Optional[str] = Query(
        None,
        description=(
            "Filter by replay availability category: "
            "has_rows | no_production_replay | artifact_only. "
            "Omit for all."
        ),
    ),
    coverage_mode:             bool          = Query(
        False,
        description=(
            "P262B: when true, the overview surfaces EVERY known strategy cell — "
            "including DB orphan strategies (replay rows but unregistered) and "
            "registry/lottery mismatches (rows under a lottery_type the registry "
            "does not list). Each row carries registry_status / has_replay_rows / "
            "can_open_detail / missing_reason / coverage_warning / "
            "available_bet_indices / max_bet_index / distinct_draw_count. "
            "Pair with bet_index=0 to avoid hiding multi-bet strategies. "
            "Default false preserves the original P259A registry-only behaviour. "
            "READ-ONLY — never writes the DB, backfills rows, or mutates registry."
        ),
    ),
):
    """
    P259A: Read-only History Replay Overview — strategy-level summary.

    Returns one row per (strategy_id × lottery_type) combination showing:
    - Declared bet count (derived from strategy_id naming)
    - Replay row count, target_draw range, latest target_draw
    - Lifecycle status as badge metadata (never used to exclude strategies)
    - Replay status category summary

    All registered strategies are included regardless of lifecycle status.
    Lifecycle is metadata only — it does NOT permanently exclude strategies.

    Per-draw detail data is NOT included. Detail page deferred to P259B.

    READ-ONLY. No DB write. No replay backfill. No strategy adapter execution.
    No migration. No production deployment change.
    """
    try:
        # ── 1. Get all strategies from registry (all lifecycle states) ──────
        all_meta = list_strategy_lifecycle_metadata()
        exec_ids = set(list_executable_strategy_ids())

        # ── 2. Query DB for replay summary per (lottery_type, strategy_id) ──
        conn = _open_conn()
        try:
            db_rows = conn.execute(
                """
                SELECT
                    lottery_type,
                    strategy_id,
                    MAX(strategy_name) AS db_strategy_name,
                    COUNT(*)  AS total_rows,
                    COUNT(DISTINCT target_draw) AS distinct_draw_count,
                    MAX(bet_index) AS max_bet_index,
                    GROUP_CONCAT(DISTINCT bet_index) AS bet_indices_csv,
                    MIN(CAST(target_draw AS INTEGER)) AS min_draw_int,
                    MAX(CAST(target_draw AS INTEGER)) AS max_draw_int,
                    SUM(CASE WHEN replay_status='PREDICTED'            THEN 1 ELSE 0 END) AS predicted_cnt,
                    SUM(CASE WHEN replay_status='REJECTED'             THEN 1 ELSE 0 END) AS rejected_cnt,
                    SUM(CASE WHEN replay_status='INSUFFICIENT_HISTORY' THEN 1 ELSE 0 END) AS insuf_cnt,
                    SUM(CASE WHEN replay_status='REPLAY_ERROR'         THEN 1 ELSE 0 END) AS error_cnt,
                    SUM(CASE WHEN replay_status='STRATEGY_UNAVAILABLE' THEN 1 ELSE 0 END) AS unavail_cnt
                FROM strategy_prediction_replays
                GROUP BY lottery_type, strategy_id
                """,
            ).fetchall()
        finally:
            conn.close()

        # Index DB data by (lottery_type, strategy_id)
        db_index: dict = {}
        for r in db_rows:
            key = (r["lottery_type"], r["strategy_id"])
            db_index[key] = {
                "db_strategy_name": r["db_strategy_name"],
                "total_rows":       r["total_rows"],
                "distinct_draw_count": r["distinct_draw_count"] or 0,
                "max_bet_index":    r["max_bet_index"] or 0,
                "available_bet_indices": _parse_bet_indices_csv(r["bet_indices_csv"]),
                "min_target_draw":  str(r["min_draw_int"]) if r["min_draw_int"] else None,
                "max_target_draw":  str(r["max_draw_int"]) if r["max_draw_int"] else None,
                "latest_target_draw": str(r["max_draw_int"]) if r["max_draw_int"] else None,
                "replay_status_summary": {
                    "PREDICTED":            r["predicted_cnt"] or 0,
                    "REJECTED":             r["rejected_cnt"] or 0,
                    "INSUFFICIENT_HISTORY": r["insuf_cnt"] or 0,
                    "REPLAY_ERROR":         r["error_cnt"] or 0,
                    "STRATEGY_UNAVAILABLE": r["unavail_cnt"] or 0,
                },
            }

        # ── 3. Build overview rows ──────────────────────────────────────────
        # (a) Registry walk — IDENTICAL iteration/filters to the original P259A
        #     endpoint (registered strategies × their supported_lottery_types).
        # (b) P262B coverage_mode ONLY: append leftover DB cells the registry walk
        #     can never reach — orphans (unregistered) and registry/lottery
        #     mismatches — so the overview can show every known strategy cell.
        registry_supported = {
            (lt, m["strategy_id"])
            for m in all_meta
            for lt in m["supported_lottery_types"]
        }

        rows = []

        # (a) registry walk
        for meta in all_meta:
            sid = meta["strategy_id"]
            derived_bets = _derive_bet_count(sid)
            is_exec = sid in exec_ids

            for lt in meta["supported_lottery_types"]:
                # lottery_type filter
                if lottery_type and lt != lottery_type:
                    continue
                # bet_index filter (0 = all)
                if bet_index != 0 and derived_bets != bet_index:
                    continue

                row = _build_overview_row(
                    lt=lt, sid=sid,
                    strategy_name=meta["strategy_name"],
                    strategy_version=meta["strategy_version"],
                    derived_bets=derived_bets,
                    lifecycle=meta["lifecycle_status"],
                    is_exec=is_exec,
                    db=db_index.get((lt, sid)),
                    registry_status=_REGISTRY_STATUS_REGISTERED,
                )
                # replay_status_category filter
                if replay_status_category and row["replay_status_category"] != replay_status_category:
                    continue
                rows.append(row)

        # (b) coverage_mode universe expansion — orphan + registry/lottery mismatch
        if coverage_mode:
            reg_index = {m["strategy_id"]: m for m in all_meta}
            for (lt, sid), db in db_index.items():
                if (lt, sid) in registry_supported:
                    continue  # already produced by the registry walk above
                if lottery_type and lt != lottery_type:
                    continue
                derived_bets = _derive_bet_count(sid)
                if bet_index != 0 and derived_bets != bet_index:
                    continue

                reg_meta = reg_index.get(sid)
                if reg_meta is None:
                    # orphan: replay rows exist but strategy_id is unregistered
                    registry_status = _REGISTRY_STATUS_ORPHAN
                    lifecycle       = "UNREGISTERED"
                    strategy_name   = db.get("db_strategy_name") or sid
                    strategy_version = None
                    is_exec         = False
                else:
                    # registered, but rows exist under a lottery_type the registry
                    # does NOT list for this strategy → coverage mismatch
                    registry_status = _REGISTRY_STATUS_MISMATCH
                    lifecycle       = reg_meta["lifecycle_status"]
                    strategy_name   = reg_meta["strategy_name"]
                    strategy_version = reg_meta["strategy_version"]
                    is_exec         = sid in exec_ids

                row = _build_overview_row(
                    lt=lt, sid=sid,
                    strategy_name=strategy_name,
                    strategy_version=strategy_version,
                    derived_bets=derived_bets,
                    lifecycle=lifecycle,
                    is_exec=is_exec,
                    db=db,
                    registry_status=registry_status,
                )
                if replay_status_category and row["replay_status_category"] != replay_status_category:
                    continue
                rows.append(row)

        # P262B coverage summary (only meaningful counts; harmless in legacy mode)
        distinct_strategy_ids = {r["strategy_id"] for r in rows}
        coverage_summary = {
            "registered":                sum(1 for r in rows if r["registry_status"] == _REGISTRY_STATUS_REGISTERED),
            "unregistered_orphan":       sum(1 for r in rows if r["registry_status"] == _REGISTRY_STATUS_ORPHAN),
            "registry_lottery_mismatch": sum(1 for r in rows if r["registry_status"] == _REGISTRY_STATUS_MISMATCH),
            "with_replay_rows":          sum(1 for r in rows if r["has_replay_rows"]),
            "without_replay_rows":       sum(1 for r in rows if not r["has_replay_rows"]),
            "can_open_detail":           sum(1 for r in rows if r["can_open_detail"]),
        }

        return {
            "default_bet_index":            1,
            "bet_index_filter":             bet_index,
            "lottery_type_filter":          lottery_type or None,
            "replay_status_category_filter": replay_status_category or None,
            "coverage_mode":                coverage_mode,
            "total_rows":                   len(rows),
            "total_known_strategies":       len(distinct_strategy_ids),
            "coverage_summary":             coverage_summary,
            "rows":                         rows,
            "all_strategies_included":      True,
            "lifecycle_as_badge_only":      True,
            "detail_page_note":             (
                "明細頁將於後續 P259B 實作，包含每一期預測比對與分頁查詢。"
            ),
            "disclaimer":                   _DISCLAIMER,
            "no_db_write":                  True,
            "no_replay_backfill":           True,
            "no_strategy_adapter_changes":  True,
            "no_large_per_draw_detail":     True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_history_replay_overview failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── P259B: History Replay Detail (paginated per-draw query) ─────────────────

_DETAIL_SORTS = ("target_draw_desc", "target_draw_asc")
_DETAIL_HIT_FILTERS = ("all", "hit", "miss")


def _parse_numbers_field(raw):
    """Parse a stored numbers TEXT field (e.g. '[1, 7, 15]') into a list of ints.

    Returns [] on null/empty; falls back to the raw string wrapped in a list
    only if it is non-empty and unparseable. Never raises.
    """
    if raw is None or raw == "":
        return []
    if isinstance(raw, list):
        return raw
    try:
        val = json.loads(raw)
        if isinstance(val, list):
            return val
        return [val]
    except (json.JSONDecodeError, TypeError):
        return [str(raw)]


def _detail_result_label(hit_count, special_hit):
    """Derive a factual, advisory-free result label from hit_count / special_hit.

    Purely descriptive of historical replay outcome — NOT a prize tier claim,
    NOT betting advice.
    """
    hc = hit_count or 0
    if hc <= 0:
        base = "未命中"
    else:
        base = f"命中 {hc} 碼"
    if special_hit:
        base += "＋特別號"
    return base


@router.get("/api/replay/history-detail")
async def get_history_replay_detail(
    lottery_type: str = Query(
        ...,
        description="BIG_LOTTO | POWER_LOTTO | DAILY_539",
    ),
    strategy_id: str = Query(..., description="Strategy identifier (exact match)."),
    bet_index: int = Query(
        1,
        ge=1,
        le=5,
        description=(
            "Strategy-level declared bet count (P259A-consistent, derived from "
            "strategy_id naming). Confirmatory only — the replay table has no "
            "per-bet column; rows are scoped by (lottery_type, strategy_id)."
        ),
    ),
    page: int = Query(1, ge=1, description="1-based page number."),
    page_size: int = Query(
        100,
        ge=1,
        le=1500,
        description="Rows per page. Default 100, max 1500. Server-side paginated. P260A: raised from 200 to support quick-range 100/300/500/1500.",
    ),
    sort: str = Query(
        "target_draw_desc",
        description="target_draw_desc (default, latest first) | target_draw_asc",
    ),
    hit_filter: str = Query(
        "all",
        description="all (default) | hit (hit_count>0) | miss (hit_count=0)",
    ),
    target_draw: Optional[str] = Query(
        None,
        description="Exact target_draw match (e.g. '115000037'). Safe parameterized query.",
    ),
):
    """
    P259B: Read-only paginated per-draw replay detail for one strategy.

    Returns each replay draw's predicted vs actual comparison for a specific
    (lottery_type, strategy_id), with server-side pagination (never loads all
    rows at once), sort, hit/miss filter, and exact target_draw search.

    bet_index semantics (P259A-consistent / Option A): the strategy-level declared
    bet count derived from the strategy_id name. The replay table stores no per-bet
    index column, so rows are scoped by (lottery_type, strategy_id). `derived_bet_count`
    and `bet_index_matches_strategy` are returned so callers can verify consistency.

    READ-ONLY. No DB write. No replay backfill/generation. No strategy adapter
    execution. No migration. No betting advice.
    """
    try:
        # ── Validate enum params ────────────────────────────────────────────
        if sort not in _DETAIL_SORTS:
            raise HTTPException(
                status_code=400,
                detail=f"invalid sort {sort!r}; allowed: {list(_DETAIL_SORTS)}",
            )
        if hit_filter not in _DETAIL_HIT_FILTERS:
            raise HTTPException(
                status_code=400,
                detail=f"invalid hit_filter {hit_filter!r}; allowed: {list(_DETAIL_HIT_FILTERS)}",
            )

        derived_bet_count = _derive_bet_count(strategy_id)
        bet_index_matches = (derived_bet_count == bet_index)

        # ── Build WHERE clause (always scoped to lottery_type + strategy_id) ─
        where_parts = ["lottery_type = ?", "strategy_id = ?"]
        params: list = [lottery_type, strategy_id]

        if hit_filter == "hit":
            where_parts.append("hit_count > 0")
        elif hit_filter == "miss":
            where_parts.append("(hit_count = 0 OR hit_count IS NULL)")

        if target_draw:
            where_parts.append("target_draw = ?")
            params.append(target_draw)

        where_sql = " AND ".join(where_parts)
        order_dir = "DESC" if sort == "target_draw_desc" else "ASC"

        conn = _open_conn()
        try:
            # ── Total count for the filtered set (server-side pagination) ────
            total_count = conn.execute(
                f"SELECT COUNT(*) FROM strategy_prediction_replays WHERE {where_sql}",
                params,
            ).fetchone()[0]

            offset = (page - 1) * page_size
            page_rows = conn.execute(
                f"""
                SELECT
                    lottery_type, strategy_id, strategy_name, target_draw, target_date,
                    predicted_numbers, predicted_special, actual_numbers, actual_special,
                    hit_count, hit_numbers, special_hit, generated_at
                FROM strategy_prediction_replays
                WHERE {where_sql}
                ORDER BY CAST(target_draw AS INTEGER) {order_dir}, id {order_dir}
                LIMIT ? OFFSET ?
                """,
                params + [page_size, offset],
            ).fetchall()

            rows = []
            for r in page_rows:
                rows.append({
                    "lottery_type":      r["lottery_type"],
                    "strategy_id":       r["strategy_id"],
                    "strategy_name":     r["strategy_name"],
                    "bet_index":         derived_bet_count,  # P259A-consistent strategy-level value
                    "target_draw":       r["target_draw"],
                    "draw_date":         r["target_date"],
                    "predicted_numbers": _parse_numbers_field(r["predicted_numbers"]),
                    "predicted_special": r["predicted_special"],
                    "actual_numbers":    _parse_numbers_field(r["actual_numbers"]),
                    "actual_special":    r["actual_special"],
                    "hit_count":         r["hit_count"] or 0,
                    "hit_numbers":       _parse_numbers_field(r["hit_numbers"]),
                    "special_hit":       bool(r["special_hit"]),
                    "result_label":      _detail_result_label(r["hit_count"], r["special_hit"]),
                    "replay_created_at": r["generated_at"],
                })

            # ── Summary over the FULL (lottery, strategy) set (unfiltered) ───
            summary_row = conn.execute(
                """
                SELECT
                    COUNT(*) AS total_rows,
                    SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END) AS hit_rows,
                    MIN(CAST(target_draw AS INTEGER)) AS first_draw,
                    MAX(CAST(target_draw AS INTEGER)) AS last_draw
                FROM strategy_prediction_replays
                WHERE lottery_type = ? AND strategy_id = ?
                """,
                [lottery_type, strategy_id],
            ).fetchone()
        finally:
            conn.close()

        total_replay_rows = summary_row["total_rows"] or 0
        total_hit_rows = summary_row["hit_rows"] or 0
        hit_rate = round(total_hit_rows / total_replay_rows, 4) if total_replay_rows else 0.0
        first_draw = str(summary_row["first_draw"]) if summary_row["first_draw"] is not None else None
        last_draw = str(summary_row["last_draw"]) if summary_row["last_draw"] is not None else None

        has_next = (page * page_size) < total_count

        return {
            "lottery_type":      lottery_type,
            "strategy_id":       strategy_id,
            "bet_index":         bet_index,
            "derived_bet_count": derived_bet_count,
            "bet_index_matches_strategy": bet_index_matches,
            "page":              page,
            "page_size":         page_size,
            "total_count":       total_count,
            "has_next":          has_next,
            "sort":              sort,
            "hit_filter":        hit_filter,
            "rows":              rows,
            "summary": {
                "total_replay_rows": total_replay_rows,
                "total_hit_rows":    total_hit_rows,
                "hit_rate":          hit_rate,
                "first_target_draw": first_draw,
                "last_target_draw":  last_draw,
                "latest_target_draw": last_draw,
                "current_filters": {
                    "lottery_type": lottery_type,
                    "strategy_id":  strategy_id,
                    "bet_index":    bet_index,
                    "sort":         sort,
                    "hit_filter":   hit_filter,
                    "target_draw":  target_draw or None,
                },
            },
            "field_notes": {
                "no_bet_index_column": (
                    "replay table has no per-bet index column; bet_index is the "
                    "strategy-level declared bet count (P259A-consistent)."
                ),
                "result_label_derived": "result_label is derived from hit_count / special_hit, not stored.",
            },
            "disclaimer":                  _DISCLAIMER,
            "paginated":                   True,
            "server_side_pagination":      True,
            "no_full_load":                True,
            "no_db_write":                 True,
            "no_replay_backfill":          True,
            "no_strategy_adapter_changes": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_history_replay_detail failed")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/replay/history-detail-grouped")
async def get_history_replay_detail_grouped(
    lottery_type: str = Query(
        ...,
        description="BIG_LOTTO | POWER_LOTTO | DAILY_539",
    ),
    strategy_id: str = Query(..., description="Strategy identifier (exact match)."),
    bet_index: int = Query(
        1,
        ge=1,
        le=5,
        description=(
            "Strategy-level declared bet count (P259A-consistent, derived from "
            "strategy_id naming). CONFIRMATORY ONLY in the grouped view — it does "
            "NOT filter rows; the grouped view always returns ALL bets per draw "
            "in each row's bets[] array. `derived_bet_count` / "
            "`bet_index_matches_strategy` are echoed so callers can verify."
        ),
    ),
    page: int = Query(1, ge=1, description="1-based page number (paginates over distinct draws)."),
    page_size: int = Query(
        100,
        ge=1,
        le=1500,
        description=(
            "Number of DISTINCT DRAWS per page. Default 100, max 1500. "
            "Server-side paginated — never loads all draws at once. "
            "P261A: grouped view paginates over draws, not over bet-rows."
        ),
    ),
    sort: str = Query(
        "target_draw_desc",
        description="target_draw_desc (default, latest first) | target_draw_asc",
    ),
    hit_filter: str = Query(
        "all",
        description=(
            "all (default) | hit (draw with ANY bet hit_count>0) | "
            "miss (draw where ALL bets hit_count=0). Applied at the DRAW level."
        ),
    ),
    target_draw: Optional[str] = Query(
        None,
        description="Exact target_draw match (e.g. '115000037'). Safe parameterized query.",
    ),
):
    """
    P261A: Read-only DRAW-GROUPED replay detail for one strategy.

    Unlike /api/replay/history-detail (which returns one row per bet-row), this
    endpoint groups by distinct target_draw and returns ONE row per draw, with a
    nested `bets[]` array holding every bet's per-bet predicted/actual/hit detail.
    This is the data source for the row-expand UI: the main table shows one clean
    row per draw, and expanding a row reveals each bet (第 1 注 / 第 2 注 / …).

    Server-side pagination is over DISTINCT DRAWS (page_size = draws per page,
    max 1500), so a 5-bet strategy at page_size=100 loads 100 draws × ≤5 bets,
    never the full result set. The existing /history-detail endpoint and its
    contract are unchanged.

    READ-ONLY. No DB write. No replay backfill/generation. No strategy adapter
    execution. No migration. No schema change. No betting advice.
    """
    try:
        # ── Validate enum params ────────────────────────────────────────────
        if sort not in _DETAIL_SORTS:
            raise HTTPException(
                status_code=400,
                detail=f"invalid sort {sort!r}; allowed: {list(_DETAIL_SORTS)}",
            )
        if hit_filter not in _DETAIL_HIT_FILTERS:
            raise HTTPException(
                status_code=400,
                detail=f"invalid hit_filter {hit_filter!r}; allowed: {list(_DETAIL_HIT_FILTERS)}",
            )

        derived_bet_count = _derive_bet_count(strategy_id)
        bet_index_matches = (derived_bet_count == bet_index)

        # ── Base WHERE (scoped to lottery_type + strategy_id) ────────────────
        base_where = ["lottery_type = ?", "strategy_id = ?"]
        base_params: list = [lottery_type, strategy_id]
        if target_draw:
            base_where.append("target_draw = ?")
            base_params.append(target_draw)
        base_where_sql = " AND ".join(base_where)
        order_dir = "DESC" if sort == "target_draw_desc" else "ASC"

        # Draw-level hit_filter applied via HAVING on the per-draw aggregate.
        having_sql = ""
        if hit_filter == "hit":
            having_sql = "HAVING SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END) > 0"
        elif hit_filter == "miss":
            having_sql = "HAVING SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END) = 0"

        conn = _open_conn()
        try:
            # ── Count distinct draws matching the filter ─────────────────────
            total_count = conn.execute(
                f"""
                SELECT COUNT(*) FROM (
                    SELECT target_draw
                    FROM strategy_prediction_replays
                    WHERE {base_where_sql}
                    GROUP BY target_draw
                    {having_sql}
                )
                """,
                base_params,
            ).fetchone()[0]

            # ── Page of distinct draws (with per-draw aggregates) ────────────
            offset = (page - 1) * page_size
            draw_rows = conn.execute(
                f"""
                SELECT
                    target_draw,
                    MAX(target_date)                            AS draw_date,
                    COUNT(*)                                    AS n_bets,
                    SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END) AS hit_bets,
                    MAX(COALESCE(hit_count, 0))                 AS max_hit_count,
                    SUM(COALESCE(hit_count, 0))                 AS total_hit_count
                FROM strategy_prediction_replays
                WHERE {base_where_sql}
                GROUP BY target_draw
                {having_sql}
                ORDER BY CAST(target_draw AS INTEGER) {order_dir}
                LIMIT ? OFFSET ?
                """,
                base_params + [page_size, offset],
            ).fetchall()

            page_draws = [str(d["target_draw"]) for d in draw_rows]

            # ── Fetch every bet row for the paginated draws ──────────────────
            bet_rows_by_draw: dict = {}
            if page_draws:
                placeholders = ",".join("?" for _ in page_draws)
                bet_rows = conn.execute(
                    f"""
                    SELECT
                        target_draw, bet_index, strategy_name, target_date,
                        predicted_numbers, predicted_special,
                        actual_numbers, actual_special,
                        hit_numbers, hit_count, special_hit, replay_status
                    FROM strategy_prediction_replays
                    WHERE lottery_type = ? AND strategy_id = ?
                      AND target_draw IN ({placeholders})
                    ORDER BY CAST(target_draw AS INTEGER) {order_dir}, bet_index ASC
                    """,
                    [lottery_type, strategy_id] + page_draws,
                ).fetchall()
                for br in bet_rows:
                    bet_rows_by_draw.setdefault(str(br["target_draw"]), []).append(br)

            # ── Build one row per draw, with nested bets[] ───────────────────
            rows = []
            for d in draw_rows:
                td = str(d["target_draw"])
                bet_list = bet_rows_by_draw.get(td, [])
                bets = []
                hit_union: set = set()
                actual_numbers = []
                actual_special = None
                strategy_name = None
                for br in bet_list:
                    b_pred = _parse_numbers_field(br["predicted_numbers"])
                    b_actual = _parse_numbers_field(br["actual_numbers"])
                    b_hits = _parse_numbers_field(br["hit_numbers"])
                    if not actual_numbers and b_actual:
                        actual_numbers = b_actual
                    if actual_special is None:
                        actual_special = br["actual_special"]
                    if strategy_name is None:
                        strategy_name = br["strategy_name"]
                    for n in b_hits:
                        try:
                            hit_union.add(int(n))
                        except (TypeError, ValueError):
                            hit_union.add(n)
                    bets.append({
                        "bet_index":         br["bet_index"],
                        "predicted_numbers": b_pred,
                        "predicted_special": br["predicted_special"],
                        "actual_numbers":    b_actual,
                        "actual_special":    br["actual_special"],
                        "hit_numbers":       b_hits,
                        "hit_count":         br["hit_count"] or 0,
                        "special_hit":       bool(br["special_hit"]),
                        "result_label":      _detail_result_label(br["hit_count"], br["special_hit"]),
                        "strategy_name":     br["strategy_name"],
                        "replay_status":     br["replay_status"],
                    })

                max_hit = d["max_hit_count"] or 0
                # Draw-level summary fields (history-detail-compatible names):
                #   predicted_numbers / predicted_special = first bet's prediction
                #   hit_numbers = union of all bets' hit numbers for this draw
                predicted_summary = bets[0]["predicted_numbers"] if bets else []
                predicted_special_summary = bets[0]["predicted_special"] if bets else None
                special_hit_any = any(b["special_hit"] for b in bets)
                rows.append({
                    "lottery_type":      lottery_type,
                    "strategy_id":       strategy_id,
                    "strategy_name":     strategy_name,
                    "target_draw":       td,
                    "draw_date":         d["draw_date"],
                    "n_bets":            d["n_bets"] or len(bets),
                    "actual_numbers":    actual_numbers,
                    "actual_special":    actual_special,
                    # Draw-level summary (one bet's prediction + union of hits):
                    "predicted_numbers": predicted_summary,
                    "predicted_special": predicted_special_summary,
                    "hit_numbers":       sorted(hit_union, key=lambda x: (isinstance(x, str), x)),
                    "max_hit_count":     max_hit,
                    "total_hit_count":   d["total_hit_count"] or 0,
                    "hit_bets":          d["hit_bets"] or 0,
                    "any_hit":           max_hit > 0,
                    "special_hit":       special_hit_any,
                    "bets":              bets,
                })

            # ── Summary over the FULL (lottery, strategy) set (unfiltered) ───
            summary_row = conn.execute(
                """
                SELECT
                    COUNT(*)                                       AS total_rows,
                    COUNT(DISTINCT target_draw)                    AS total_draws,
                    SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END) AS hit_rows,
                    MIN(CAST(target_draw AS INTEGER))              AS first_draw,
                    MAX(CAST(target_draw AS INTEGER))              AS last_draw
                FROM strategy_prediction_replays
                WHERE lottery_type = ? AND strategy_id = ?
                """,
                [lottery_type, strategy_id],
            ).fetchone()

            # Distinct draws that have at least one bet hit (draw-level hit rate).
            hit_draws_row = conn.execute(
                """
                SELECT COUNT(*) FROM (
                    SELECT target_draw
                    FROM strategy_prediction_replays
                    WHERE lottery_type = ? AND strategy_id = ?
                    GROUP BY target_draw
                    HAVING SUM(CASE WHEN hit_count > 0 THEN 1 ELSE 0 END) > 0
                )
                """,
                [lottery_type, strategy_id],
            ).fetchone()
        finally:
            conn.close()

        total_replay_rows = summary_row["total_rows"] or 0
        total_draws = summary_row["total_draws"] or 0
        total_hit_rows = summary_row["hit_rows"] or 0
        total_hit_draws = (hit_draws_row[0] if hit_draws_row else 0) or 0
        draw_hit_rate = round(total_hit_draws / total_draws, 4) if total_draws else 0.0
        row_hit_rate = round(total_hit_rows / total_replay_rows, 4) if total_replay_rows else 0.0
        first_draw = str(summary_row["first_draw"]) if summary_row["first_draw"] is not None else None
        last_draw = str(summary_row["last_draw"]) if summary_row["last_draw"] is not None else None

        has_next = (page * page_size) < total_count

        return {
            "lottery_type":      lottery_type,
            "strategy_id":       strategy_id,
            "bet_index":         bet_index,
            "derived_bet_count": derived_bet_count,
            "bet_index_matches_strategy": bet_index_matches,
            "grouped":           True,
            "page":              page,
            "page_size":         page_size,
            "total_count":       total_count,
            "has_next":          has_next,
            "sort":              sort,
            "hit_filter":        hit_filter,
            "rows":              rows,
            "summary": {
                "total_replay_rows": total_replay_rows,
                "total_draws":       total_draws,
                "total_hit_rows":    total_hit_rows,
                "total_hit_draws":   total_hit_draws,
                "hit_rate":          draw_hit_rate,
                "draw_hit_rate":     draw_hit_rate,
                "row_hit_rate":      row_hit_rate,
                "first_target_draw": first_draw,
                "last_target_draw":  last_draw,
                "latest_target_draw": last_draw,
                "current_filters": {
                    "lottery_type": lottery_type,
                    "strategy_id":  strategy_id,
                    "bet_index":    bet_index,
                    "sort":         sort,
                    "hit_filter":   hit_filter,
                    "target_draw":  target_draw or None,
                },
            },
            "field_notes": {
                "pagination_unit": "distinct target_draw (one row per draw)",
                "bets_array": (
                    "each row carries a bets[] array with every bet's per-bet "
                    "bet_index / predicted_numbers / actual_numbers / hit_numbers / "
                    "hit_count / special_hit; bet_index is the real per-row DB column."
                ),
                "bet_index_param_confirmatory": (
                    "the bet_index query param does NOT filter; the grouped view "
                    "always returns all bets per draw."
                ),
                "result_label_derived": "result_label is derived from hit_count / special_hit, not stored.",
            },
            "disclaimer":                  _DISCLAIMER,
            "paginated":                   True,
            "server_side_pagination":      True,
            "no_full_load":                True,
            "no_db_write":                 True,
            "no_replay_backfill":          True,
            "no_strategy_adapter_changes": True,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_history_replay_detail_grouped failed")
        raise HTTPException(status_code=500, detail=str(e))


# ─── P263B: D3 Strategy Status / Contract Audit — SSOT Coverage ───────────────
# Rebuilds the D3 strategy-status view from the P262B coverage universe
# (registry ∪ replay-store cells ∪ rejected artifacts) so every known strategy
# cell is represented, with per-cell lifecycle (from the registry, no
# contradiction), registry_status, per-cell replay counts (no lottery-level
# transposition), reject reason/source provenance, and read-only success rates.
#
# This is an ADDITIVE, read-only endpoint. It does NOT replace the artifact-backed
# /api/replay/d3-strategy-status-audit route (P258N) — that contract is preserved
# verbatim. This route reads the replay store read-only via _open_conn(); it never
# writes, backfills replay rows, mutates the registry, changes adapters, or runs a
# migration. D3 contract status remains NOT_EVALUATED_BY_D3 for every row — it is
# NOT approval and does NOT imply improved prediction accuracy.

_REJECTED_ARTIFACT_DIR = Path(_api_root).parent / "rejected"

# Success-rate contract (P265A recontract — read-only DISPLAY metric only, NOT a
# promotion gate and NOT a strategy ranking):
#   metric        : M3+ real replay success rate (P265A). In P263B this column was
#                   an any-hit rate (hit_count >= 1 OR special_hit); that overstated
#                   BIG_LOTTO / multi-bet cells (~55% / 90%+). It is now M3+.
#   windows       : the most recent N distinct target_draw per cell, taken by
#                   CAST(target_draw AS INTEGER) DESC (newest first)
#   draw_success  : a draw counts as a success if ANY bet_index for that draw has
#                   hit_count >= 3 (at least 3 main-number hits). special_hit does
#                   NOT make a draw an M3+ success on its own — only hit_count >= 3
#                   counts; a special-only draw with hit_count < 3 is a non-success.
#   denominator   : distinct target_draw in the window (NOT replay row count) —
#                   multi-bet cells collapse to one entry per draw before counting
#   success_rate_N: M3+ successes / available_draws_N over the most recent N draws
#   available_N=0 : success_rate_N is null (rendered N/A)
_D3_SUCCESS_RATE_WINDOWS = [30, 100, 500, 1500]
_D3_SUCCESS_METRIC = "M3_PLUS"
_D3_SUCCESS_METRIC_LABEL = "M3+ 成功率"


def _d3_load_reject_provenance(strategy_id: str) -> dict:
    """Read reject reason/source/date from rejected/{strategy_id}.json (read-only).

    Returns reject_reason / reject_updated_at / reject_source_artifact. Missing
    file → all None. Malformed/incomplete file → 'unknown' (never fabricated).
    """
    path = _REJECTED_ARTIFACT_DIR / f"{strategy_id}.json"
    if not path.exists():
        return {"reject_reason": None, "reject_updated_at": None,
                "reject_source_artifact": None}
    source = f"rejected/{strategy_id}.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except Exception:
        # File present but unreadable/malformed — surface as unknown, never invent.
        return {"reject_reason": "unknown", "reject_updated_at": "unknown",
                "reject_source_artifact": source}
    if not isinstance(data, dict):
        return {"reject_reason": "unknown", "reject_updated_at": "unknown",
                "reject_source_artifact": source}
    return {
        "reject_reason": data.get("failure_reason") or "unknown",
        "reject_updated_at": data.get("rejected_date") or "unknown",
        "reject_source_artifact": source,
    }


def _d3_compute_success_rates(conn) -> dict:
    """Return {(lottery_type, strategy_id): {success_rate_N, available_draws_N}}.

    Read-only single pass over the replay store: collapse to one row per
    (cell, target_draw) with M3+ draw_success, ordered newest-first, then slice
    the declared windows in Python.

    M3+ (P265A): a draw is a success iff ANY bet_index for that (cell, target_draw)
    has hit_count >= 3 (>= 3 main-number hits). special_hit is intentionally NOT
    part of the criterion — a special-only draw with hit_count < 3 is a non-success.
    The GROUP BY collapses multi-bet cells to one entry per distinct target_draw,
    so the denominator is distinct target_draw, never replay row count.
    """
    cur = conn.execute(
        """
        SELECT lottery_type, strategy_id, target_draw,
               MAX(CASE WHEN hit_count >= 3 THEN 1 ELSE 0 END)
                   AS draw_success
        FROM strategy_prediction_replays
        GROUP BY lottery_type, strategy_id, target_draw
        ORDER BY lottery_type, strategy_id, CAST(target_draw AS INTEGER) DESC
        """
    )
    ordered: dict = {}
    for r in cur.fetchall():
        ordered.setdefault((r["lottery_type"], r["strategy_id"]), []).append(
            int(r["draw_success"])
        )
    out: dict = {}
    for key, successes_desc in ordered.items():
        metrics = {}
        for n in _D3_SUCCESS_RATE_WINDOWS:
            window = successes_desc[:n]
            avail = len(window)
            metrics[f"success_rate_{n}"] = (
                round(sum(window) / avail, 4) if avail else None
            )
            metrics[f"available_draws_{n}"] = avail
        out[key] = metrics
    return out


def _d3_empty_success_rates() -> dict:
    metrics = {}
    for n in _D3_SUCCESS_RATE_WINDOWS:
        metrics[f"success_rate_{n}"] = None
        metrics[f"available_draws_{n}"] = 0
    return metrics


_D3_SAFETY_DISCLAIMERS = [
    "D3 is not a prediction model.",
    "Contract validation is not strategy evaluation.",
    "NOT_YET_REJECTED is not approval.",
    "Passing contract validation does not imply improved prediction accuracy.",
    "M3+ success rate = share of draws where any bet hit >= 3 main numbers (hit_count >= 3).",
    "special_hit alone does not count as M3+ success (a draw with hit_count < 3 is a non-success).",
    "M3+ success rate is a read-only historical metric — not approval and not betting advice.",
    "M3+ 成功率 = replay 中每期任一注命中主號 3 顆以上 (hit_count >= 3) 的比例。",
    "special_hit 不單獨計入 M3+ success（hit_count < 3 即非成功）。",
    "M3+ 成功率為歷史唯讀 metric，不代表 D3 核准或投注建議。",
]


def _build_d3_ssot_coverage_payload() -> dict:
    """Build the P263B SSOT D3 coverage payload (read-only)."""
    all_meta = list_strategy_lifecycle_metadata()
    exec_ids = set(list_executable_strategy_ids())
    reg_index = {m["strategy_id"]: m for m in all_meta}
    registry_supported = {
        (lt, m["strategy_id"])
        for m in all_meta
        for lt in m["supported_lottery_types"]
    }

    conn = _open_conn()
    try:
        summary_rows = conn.execute(
            """
            SELECT lottery_type, strategy_id,
                   MAX(strategy_name) AS db_strategy_name,
                   COUNT(*) AS total_rows,
                   COUNT(DISTINCT target_draw) AS distinct_draw_count,
                   MAX(bet_index) AS max_bet_index,
                   GROUP_CONCAT(DISTINCT bet_index) AS bet_indices_csv
            FROM strategy_prediction_replays
            GROUP BY lottery_type, strategy_id
            """
        ).fetchall()
        success = _d3_compute_success_rates(conn)
    finally:
        conn.close()

    cell_index: dict = {}
    for r in summary_rows:
        cell_index[(r["lottery_type"], r["strategy_id"])] = {
            "db_strategy_name": r["db_strategy_name"],
            "total_rows": r["total_rows"],
            "distinct_draw_count": r["distinct_draw_count"] or 0,
            "max_bet_index": r["max_bet_index"] or 0,
            "available_bet_indices": _parse_bet_indices_csv(r["bet_indices_csv"]),
        }

    # Universe = registry-supported cells ∪ replay-store cells.
    universe = sorted(set(registry_supported) | set(cell_index.keys()))

    rows = []
    for (lt, sid) in universe:
        cell = cell_index.get((lt, sid))
        has_rows = cell is not None and cell["total_rows"] > 0

        if (lt, sid) in registry_supported:
            registry_status = _REGISTRY_STATUS_REGISTERED
            meta = reg_index[sid]
            lifecycle = meta["lifecycle_status"]
            strategy_name = meta["strategy_name"]
            strategy_version = meta["strategy_version"]
            status_source = "replay_strategy_registry"
            status_reason = (
                f"lifecycle '{lifecycle}' declared in the strategy registry "
                f"(replay_strategy_registry)"
            )
        elif sid in reg_index:
            registry_status = _REGISTRY_STATUS_MISMATCH
            meta = reg_index[sid]
            lifecycle = meta["lifecycle_status"]
            strategy_name = meta["strategy_name"]
            strategy_version = meta["strategy_version"]
            status_source = "replay_strategy_registry"
            status_reason = (
                "registry_lottery_mismatch: replay rows exist under a lottery_type "
                "not listed in the registry supported_lottery_types for this strategy"
            )
        else:
            registry_status = _REGISTRY_STATUS_ORPHAN
            lifecycle = "UNREGISTERED"
            strategy_name = (cell or {}).get("db_strategy_name") or sid
            strategy_version = None
            status_source = "replay_store_rows"
            status_reason = (
                "unregistered_orphan: replay rows exist but strategy_id is absent "
                "from the strategy registry"
            )

        is_exec = sid in exec_ids
        if has_rows:
            rcat = "has_rows"
        elif lifecycle in ("REJECTED",) and not is_exec:
            rcat = "artifact_only"
        else:
            rcat = "no_production_replay"
        missing_reason = _coverage_missing_reason(registry_status, has_rows, lifecycle, rcat)

        reject = _d3_load_reject_provenance(sid)
        rates = success.get((lt, sid), _d3_empty_success_rates())

        row = {
            # identity
            "lottery_type": lt,
            "strategy_id": sid,
            "strategy_name": strategy_name,
            "strategy_version": strategy_version,
            "derived_bet_count": _derive_bet_count(sid),
            # lifecycle / registry (lifecycle sourced from registry — no contradiction)
            "lifecycle": lifecycle,
            "lifecycle_status": lifecycle,  # alias for UI parity
            "registry_status": registry_status,
            "is_executable": is_exec,
            "status_reason": status_reason,
            "status_updated_at": None,  # registry carries no per-status timestamp
            "status_source": status_source,
            # replay coverage (per-cell — never lottery-level aggregate)
            "replay_row_count": (cell or {}).get("total_rows", 0),
            "distinct_draw_count": (cell or {}).get("distinct_draw_count", 0),
            "max_bet_index": (cell or {}).get("max_bet_index", 0),
            "available_bet_indices": (cell or {}).get("available_bet_indices", []),
            "has_replay_rows": has_rows,
            "can_open_detail": has_rows,
            "missing_reason": missing_reason,
            # reject provenance (from rejected/*.json, else null/unknown)
            "reject_reason": reject["reject_reason"],
            "reject_updated_at": reject["reject_updated_at"],
            "reject_source_artifact": reject["reject_source_artifact"],
            # D3 contract status (NOT approval; identical safety semantics to P258N)
            "d3_contract_status": "NOT_EVALUATED_BY_D3",
            "d3_contract_reason": (
                "No D3 evaluation has been run for this strategy. D3 executable "
                "gate evaluation requires separate explicit authorization."
            ),
            "d3_not_approval_warning": (
                "D3 contract status is NOT approval. NOT_YET_REJECTED is not approval."
            ),
            "no_prediction_claim": (
                "D3 is not a prediction model. Contract validation does not imply "
                "improved prediction accuracy."
            ),
            "no_betting_advice": (
                "Success rate is historical/read-only evidence only. It is not "
                "betting advice."
            ),
        }
        row.update(rates)
        rows.append(row)

    distinct_ids = {r["strategy_id"] for r in rows}
    coverage_summary = {
        "registered": sum(1 for r in rows if r["registry_status"] == _REGISTRY_STATUS_REGISTERED),
        "unregistered_orphan": sum(1 for r in rows if r["registry_status"] == _REGISTRY_STATUS_ORPHAN),
        "registry_lottery_mismatch": sum(1 for r in rows if r["registry_status"] == _REGISTRY_STATUS_MISMATCH),
        "with_replay_rows": sum(1 for r in rows if r["has_replay_rows"]),
        "without_replay_rows": sum(1 for r in rows if not r["has_replay_rows"]),
        "can_open_detail": sum(1 for r in rows if r["can_open_detail"]),
    }
    by_lottery: dict = {}
    for r in rows:
        by_lottery[r["lottery_type"]] = by_lottery.get(r["lottery_type"], 0) + 1

    return {
        "schema_version": "1.0",
        "route_path": "/api/replay/d3-strategy-status-coverage",
        "page_title": "D3 Strategy Status / Contract Audit — SSOT Coverage",
        "source": "ssot_registry_replay_store_rejected_artifacts",
        "summary": {
            "total_cells": len(rows),
            "total_strategies": len(distinct_ids),
            "by_lottery_type": by_lottery,
            "by_d3_contract_status": {"NOT_EVALUATED_BY_D3": len(rows)},
        },
        "coverage_summary": coverage_summary,
        "filters": {
            "lottery_type": ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO", "ALL"],
            "lifecycle": ["ONLINE", "OFFLINE", "RETIRED", "REJECTED", "OBSERVATION",
                          "UNREGISTERED", "ALL"],
            "registry_status": [_REGISTRY_STATUS_REGISTERED, _REGISTRY_STATUS_ORPHAN,
                                _REGISTRY_STATUS_MISMATCH, "ALL"],
            "d3_contract_status": ["NOT_EVALUATED_BY_D3", "CONTRACT_READY",
                                   "CONTRACT_BLOCKED", "NOT_APPLICABLE_HISTORICAL_ARTIFACT",
                                   "NOT_APPLICABLE_NO_REPLAY", "ALL"],
            "has_replay": [True, False],
        },
        "success_rate_contract": {
            "success_metric": _D3_SUCCESS_METRIC,
            "metric_label": _D3_SUCCESS_METRIC_LABEL,
            "windows": _D3_SUCCESS_RATE_WINDOWS,
            "window_basis": "most recent N distinct target_draw by CAST(target_draw AS INTEGER) DESC",
            "draw_success_rule": "any bet_index for the draw has hit_count >= 3 (>= 3 main-number hits)",
            "special_hit_excluded": True,
            "special_hit_note": "special_hit alone does NOT count as M3+ success; only hit_count >= 3 counts",
            "denominator": "distinct target_draw in the window (not replay row count)",
            "scope": "strategy_id + lottery_type",
            "no_threshold_weighting": True,
            "display_metric_only": True,
            "not_a_promotion_gate": True,
            "not_a_strategy_ranking": True,
            "metric_history": "P263B used any-hit (hit_count>=1 OR special_hit); P265A recontracted to M3+ (hit_count>=3)",
        },
        "safety_disclaimers": _D3_SAFETY_DISCLAIMERS,
        "forbidden_actions_confirmed": {
            "no_db_write": True,
            "no_replay_backfill": True,
            "no_registry_mutation": True,
            "no_adapter_change": True,
            "no_migration": True,
            "no_production_change": True,
            "no_betting_advice": True,
            "read_only_query": True,
        },
        "rows": rows,
    }


@router.get("/api/replay/d3-strategy-status-coverage")
async def get_d3_strategy_status_coverage():
    """
    P263B: Read-only D3 strategy-status SSOT coverage.

    Rebuilds the D3 strategy-status view over the full P262B coverage universe
    (registry ∪ replay-store cells ∪ rejected artifacts): every known strategy
    cell, per-cell lifecycle (from the registry), registry_status, per-cell replay
    counts, reject reason/source provenance, and read-only success rates over the
    most recent 30/100/500/1500 draws.

    READ-ONLY: reads the replay store via SELECT only; no write, no replay
    backfill, no registry mutation, no adapter change, no migration, no D3
    execution, no strategy promotion, no betting advice. D3 contract status is
    NOT_EVALUATED_BY_D3 for every row and is NOT approval.
    """
    try:
        return _build_d3_ssot_coverage_payload()
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("get_d3_strategy_status_coverage failed")
        raise HTTPException(status_code=500, detail=str(e))
