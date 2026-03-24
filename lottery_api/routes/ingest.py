"""
Automated data ingestion API endpoints.

Endpoints:
  GET  /api/ingest/status          — source health check for all games
  POST /api/ingest/fetch-latest    — fetch latest draw from official site
  GET  /api/ingest/scan-missing    — scan DB vs official for missing draws
  POST /api/ingest/backfill        — backfill missing draws
  GET  /api/ingest/log             — view recent ingest log
  POST /api/ingest/log/clear       — clear ingest log

All existing manual upload endpoints (/api/draws, /api/data/upload, etc.)
are unaffected.
"""

import logging
import os
import sys
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

# Ensure parent directory on path for sibling imports
_api_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _api_root not in sys.path:
    sys.path.insert(0, _api_root)

router = APIRouter()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class FetchLatestRequest(BaseModel):
    lottery_type: str   = "BIG_LOTTO"   # BIG_LOTTO | POWER_LOTTO | DAILY_539
    insert_if_new: bool = False          # Auto-insert if draw is missing from DB
    dry_run: bool       = False          # Fetch but do not insert


class BackfillRequest(BaseModel):
    lottery_type: str        = "BIG_LOTTO"
    draw_list: Optional[List[str]] = None   # explicit list; None = auto-detect
    dry_run: bool            = False
    max_draws: int           = Field(default=30, ge=1, le=500)  # safety cap per run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_fetcher():
    from fetcher.taiwan_lottery_fetcher import fetcher
    return fetcher

def _get_detector():
    from fetcher.missing_issue_detector import detector
    return detector

def _get_engine():
    from fetcher.backfill_engine import backfill_engine
    return backfill_engine

def _get_ingest_logger():
    from fetcher.ingest_logger import ingest_logger
    return ingest_logger

def _get_db_manager():
    from database import db_manager
    return db_manager

def _refresh_after_insert():
    """Trigger scheduler + hedge fund refresh after new data inserted."""
    try:
        from utils.scheduler import scheduler
        scheduler.load_data()
    except Exception as e:
        logger.warning(f"scheduler.load_data() failed: {e}")
    try:
        import os as _os
        project_root = _os.path.dirname(_os.path.dirname(_os.path.dirname(
            _os.path.abspath(__file__)
        )))
        from analysis.payout.sync import refresh_hedge_fund_outputs
        refresh_hedge_fund_outputs(project_root)
    except Exception as e:
        logger.warning(f"refresh_hedge_fund_outputs() failed: {e}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/api/ingest/status")
async def ingest_status():
    """
    Check connectivity to official Taiwan Lottery site for all 3 game types.
    Returns source URL, whether it's reachable, and the latest draw found.
    """
    fetcher = _get_fetcher()
    results = {}
    for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
        try:
            check = fetcher.check_source(lt)
            results[lt] = check
        except Exception as e:
            results[lt] = {"ok": False, "error": str(e)}

    all_ok = all(v.get("ok") for v in results.values())
    return {
        "overall_ok": all_ok,
        "sources":    results,
    }


@router.post("/api/ingest/fetch-latest")
async def fetch_latest(req: FetchLatestRequest):
    """
    Fetch the latest available draw from the official Taiwan Lottery site.

    - If insert_if_new=True and the draw is not in DB, it will be inserted.
    - If dry_run=True, the result is shown but nothing is written.
    - If the draw already exists in DB, it is reported as 'already_exists'.
    - Conflicts (data mismatch) are logged and not overwritten.
    """
    fetcher    = _get_fetcher()
    db_manager = _get_db_manager()
    il         = _get_ingest_logger()

    # Fetch from official site
    try:
        draw_data = fetcher.fetch_latest(req.lottery_type)
    except Exception as e:
        logger.error(f"Fetch error: {e}")
        raise HTTPException(status_code=502, detail=f"Fetch failed: {e}")

    if not draw_data:
        raise HTTPException(
            status_code=502,
            detail=(
                "Official site returned no data. "
                "Check source URL or network connectivity."
            )
        )

    draw_num = draw_data["draw"]
    lt       = req.lottery_type

    # Check existence in DB
    existing = db_manager.get_draw(lt, draw_num)

    if existing:
        # Check for conflict
        e_nums = sorted(existing.get("numbers", []))
        f_nums = sorted(draw_data.get("numbers", []))
        if e_nums != f_nums or existing.get("special", 0) != draw_data.get("special", 0):
            il.log("fetch_latest", lt, draw_num, "conflict",
                   f"Data mismatch: DB={e_nums}/{existing.get('special')}, "
                   f"fetched={f_nums}/{draw_data.get('special')}",
                   {"existing": existing, "fetched": draw_data})
            return {
                "success":  False,
                "status":   "conflict",
                "draw":     draw_num,
                "message":  "Fetched data conflicts with existing DB record. "
                            "Review logged conflict before overwriting.",
                "existing": existing,
                "fetched":  draw_data,
            }

        il.log("fetch_latest", lt, draw_num, "skip", "Already in DB")
        return {
            "success":       True,
            "status":        "already_exists",
            "draw":          draw_num,
            "message":       f"Draw {draw_num} already in DB (no change needed)",
            "draw_data":     draw_data,
        }

    # Draw is new
    if req.dry_run:
        il.log("fetch_latest", lt, draw_num, "dry_run",
               f"Would insert: {draw_data}")
        return {
            "success":   True,
            "status":    "dry_run",
            "draw":      draw_num,
            "message":   "DRY-RUN: draw would be inserted (not written)",
            "draw_data": draw_data,
        }

    if req.insert_if_new:
        try:
            inserted, _ = db_manager.insert_draws([draw_data])
            if inserted > 0:
                _refresh_after_insert()
                il.log("fetch_latest", lt, draw_num, "ok",
                       f"Inserted: {draw_data}")
                return {
                    "success":   True,
                    "status":    "inserted",
                    "draw":      draw_num,
                    "message":   f"✅ Draw {draw_num} inserted successfully",
                    "draw_data": draw_data,
                }
            else:
                il.log("fetch_latest", lt, draw_num, "skip", "DB IGNORE (race)")
                return {
                    "success": True,
                    "status":  "skipped",
                    "draw":    draw_num,
                    "message": "Insert skipped (possible race condition)",
                }
        except Exception as e:
            il.log("fetch_latest", lt, draw_num, "error", str(e))
            raise HTTPException(status_code=500, detail=f"Insert failed: {e}")

    # Fetched but not asked to insert
    il.log("fetch_latest", lt, draw_num, "ok",
           "Fetched (insert_if_new=false, not written)")
    return {
        "success":     True,
        "status":      "fetched_only",
        "draw":        draw_num,
        "message":     "Draw fetched. Set insert_if_new=true to write to DB.",
        "draw_data":   draw_data,
    }


@router.get("/api/ingest/scan-missing")
async def scan_missing(
    lottery_type: Optional[str] = Query(None, description="彩種 (空=掃描全部)"),
    max_recent_fetch: int       = Query(50, ge=5, le=200),
):
    """
    Scan the DB for draws missing compared to the official site.

    Returns per-game:
      - db_count, db_latest_draw
      - official_latest
      - missing_draws list
      - internal_gaps (holes in the DB sequence)
    """
    detector = _get_detector()
    il       = _get_ingest_logger()

    if lottery_type:
        result = detector.scan(lottery_type, max_recent_fetch=max_recent_fetch)
        il.log("scan_missing", lottery_type, status="ok",
               message=f"missing={result['missing_count']}")
        return {"results": {lottery_type: result}}
    else:
        all_results = {}
        total_missing = 0
        for lt in ["BIG_LOTTO", "POWER_LOTTO", "DAILY_539"]:
            r = detector.scan(lt, max_recent_fetch=max_recent_fetch)
            all_results[lt] = r
            total_missing += r.get("missing_count", 0)
            il.log("scan_missing", lt, status="ok",
                   message=f"missing={r['missing_count']}")
        return {
            "results":       all_results,
            "total_missing": total_missing,
        }


@router.post("/api/ingest/backfill")
async def run_backfill(req: BackfillRequest):
    """
    Backfill missing draws for a given lottery type.

    Safety:
      - Existing records are never overwritten
      - Conflicts are logged and skipped
      - Use dry_run=true to preview without writing
      - max_draws caps how many draws are processed per call
    """
    engine = _get_engine()
    il     = _get_ingest_logger()

    try:
        summary = engine.run(
            lottery_type=req.lottery_type,
            draw_list=req.draw_list,
            dry_run=req.dry_run,
            max_draws=req.max_draws,
        )
    except Exception as e:
        logger.error(f"Backfill error: {e}", exc_info=True)
        il.log("backfill", req.lottery_type, status="error", message=str(e))
        raise HTTPException(status_code=500, detail=f"Backfill failed: {e}")

    if summary.get("inserted", 0) > 0 and not req.dry_run:
        _refresh_after_insert()

    return {
        "success": True,
        "summary": summary,
    }


@router.get("/api/ingest/log")
async def get_ingest_log(
    limit: int          = Query(20, ge=1, le=500),
    offset: int         = Query(0, ge=0),
    lottery_type: Optional[str] = Query(None),
):
    """Return ingest log entries, newest first, with pagination support."""
    il = _get_ingest_logger()
    entries = il.get_recent(limit=limit, offset=offset, lottery_type=lottery_type)
    stats   = il.get_stats()
    return {
        "entries": entries,
        "stats":   stats,
        "limit":   limit,
        "offset":  offset,
    }


@router.post("/api/ingest/log/clear")
async def clear_ingest_log():
    """Clear the ingest log file."""
    il = _get_ingest_logger()
    count = il.clear()
    return {
        "success": True,
        "cleared": count,
        "message": f"Cleared {count} log entries",
    }
