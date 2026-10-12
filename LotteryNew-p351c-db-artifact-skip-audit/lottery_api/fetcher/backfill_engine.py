"""
Backfill engine — safely inserts missing draws into the DB.

Safety guarantees:
  - Idempotent: safe to re-run; existing records are never overwritten
  - No silent conflicts: if fetched data differs from existing data, it is
    logged as CONFLICT and skipped (not overwritten)
  - Dry-run mode: pass dry_run=True to preview without inserting
  - All operations are recorded in ingest_log.jsonl

Typical usage:
  engine = BackfillEngine()

  # Auto-detect and fill missing draws
  result = engine.run("BIG_LOTTO")

  # Fill a specific list of draw numbers
  result = engine.run("DAILY_539", draw_list=["115000070", "115000071"])

  # Preview without writing
  result = engine.run("POWER_LOTTO", dry_run=True)
"""

import logging
import time
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

POLITE_DELAY = 0.8   # seconds between fetch requests (be polite)


class BackfillEngine:
    """Orchestrates fetch → conflict-check → insert for missing draws."""

    def __init__(self):
        pass   # lazy imports inside methods

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        lottery_type: str,
        draw_list: Optional[List[str]] = None,
        dry_run: bool = False,
        max_draws: int = 50,
    ) -> Dict:
        """
        Run the backfill process.

        Args:
            lottery_type : BIG_LOTTO | POWER_LOTTO | DAILY_539
            draw_list    : Explicit list of draw numbers to backfill.
                           If None, auto-detects via MissingIssueDetector.
            dry_run      : If True, fetch and log but do NOT insert.
            max_draws    : Cap on how many draws to process in one run.

        Returns:
          {
            lottery_type : str,
            dry_run      : bool,
            total        : int,
            inserted     : int,
            skipped      : int,   (already existed)
            conflict     : int,   (data mismatch, not inserted)
            failed       : int,   (fetch/parse error)
            details      : list[dict],  per-draw result
          }
        """
        from .taiwan_lottery_fetcher import fetcher
        from .missing_issue_detector import detector
        from .ingest_logger import ingest_logger

        summary = {
            "lottery_type": lottery_type,
            "dry_run":      dry_run,
            "total":        0,
            "inserted":     0,
            "skipped":      0,
            "conflict":     0,
            "failed":       0,
            "details":      [],
        }

        # --- Determine which draws to process ---
        if draw_list is None:
            logger.info(f"🔍 Auto-detecting missing draws for {lottery_type}...")
            scan = detector.scan(lottery_type)
            if scan.get("scan_error"):
                logger.error(f"❌ Scan failed: {scan['scan_error']}")
                summary["error"] = scan["scan_error"]
                ingest_logger.log(
                    action="backfill",
                    lottery_type=lottery_type,
                    status="error",
                    message=f"Scan failed: {scan['scan_error']}",
                )
                return summary
            draw_list = scan["missing_draws"]
            logger.info(f"Found {len(draw_list)} missing draws to backfill")
        else:
            logger.info(f"Explicit draw list provided: {len(draw_list)} draws")

        # Apply cap
        if len(draw_list) > max_draws:
            logger.warning(
                f"⚠️  Capping backfill at {max_draws} draws "
                f"(requested {len(draw_list)})"
            )
            draw_list = draw_list[:max_draws]

        summary["total"] = len(draw_list)

        if not draw_list:
            logger.info("✅ Nothing to backfill — DB is up to date")
            ingest_logger.log(
                action="backfill",
                lottery_type=lottery_type,
                status="ok",
                message="Nothing to backfill — DB is up to date",
            )
            return summary

        # --- Fetch recent official draws for lookup ---
        logger.info(f"🌐 Fetching official draws for {lottery_type}...")
        official_draws = fetcher.fetch_recent(lottery_type, max_draws=max(len(draw_list) + 10, 50))
        official_map = {d["draw"]: d for d in official_draws}

        # --- Process each draw ---
        for draw_num in draw_list:
            detail = self._process_one(
                lottery_type=lottery_type,
                draw_num=draw_num,
                official_map=official_map,
                dry_run=dry_run,
                fetcher=fetcher,
                ingest_logger=ingest_logger,
            )
            summary["details"].append(detail)
            s = detail["status"]
            if s == "inserted":
                summary["inserted"] += 1
            elif s == "skipped":
                summary["skipped"] += 1
            elif s == "conflict":
                summary["conflict"] += 1
            elif s == "failed":
                summary["failed"] += 1
            elif s == "dry_run":
                summary["inserted"] += 1  # count as would-be-inserted

            time.sleep(POLITE_DELAY)

        logger.info(
            f"✅ Backfill complete for {lottery_type}: "
            f"inserted={summary['inserted']}, skipped={summary['skipped']}, "
            f"conflict={summary['conflict']}, failed={summary['failed']}"
        )
        ingest_logger.log(
            action="backfill",
            lottery_type=lottery_type,
            status="ok" if summary["failed"] == 0 else "partial",
            message=(
                f"inserted={summary['inserted']}, skipped={summary['skipped']}, "
                f"conflict={summary['conflict']}, failed={summary['failed']}"
            ),
            data={"dry_run": dry_run, "total": summary["total"]},
        )
        return summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _process_one(
        self,
        lottery_type: str,
        draw_num: str,
        official_map: Dict,
        dry_run: bool,
        fetcher,
        ingest_logger,
    ) -> Dict:
        """
        Process a single draw number: fetch → conflict-check → insert.
        Returns a per-draw result dict.
        """
        import sys
        import os

        # Try to get draw data from official_map first, then re-fetch
        fetched = official_map.get(draw_num)
        if not fetched:
            logger.info(f"  🌐 Re-fetching {draw_num} individually...")
            latest = fetcher.fetch_latest(lottery_type)
            if latest and latest.get("draw") == draw_num:
                fetched = latest
            # TODO: implement single-draw fetch by period if needed
            if not fetched:
                logger.warning(f"  ⚠️  Could not fetch draw {draw_num}")
                ingest_logger.log(
                    action="backfill",
                    lottery_type=lottery_type,
                    draw=draw_num,
                    status="failed",
                    message="Could not fetch from official source",
                )
                return {"draw": draw_num, "status": "failed",
                        "message": "Could not fetch from official source"}

        # Check for existing record in DB
        existing = self._get_existing(lottery_type, draw_num)

        if existing:
            # Compare data
            conflict = self._detect_conflict(existing, fetched)
            if conflict:
                msg = (
                    f"CONFLICT: existing={existing.get('numbers')}/{existing.get('special')}, "
                    f"fetched={fetched.get('numbers')}/{fetched.get('special')}"
                )
                logger.warning(f"  ⚡ {draw_num}: {msg}")
                ingest_logger.log(
                    action="conflict",
                    lottery_type=lottery_type,
                    draw=draw_num,
                    status="conflict",
                    message=msg,
                    data={"existing": existing, "fetched": fetched,
                          "conflict_type": conflict},
                )
                return {"draw": draw_num, "status": "conflict", "message": msg}
            else:
                logger.info(f"  ⏩ {draw_num}: already in DB (exact duplicate, skipping)")
                ingest_logger.log(
                    action="backfill",
                    lottery_type=lottery_type,
                    draw=draw_num,
                    status="skip",
                    message="Already exists in DB",
                )
                return {"draw": draw_num, "status": "skipped",
                        "message": "Already in DB"}

        # Insert
        if dry_run:
            logger.info(f"  🔎 DRY-RUN {draw_num}: would insert {fetched}")
            ingest_logger.log(
                action="backfill",
                lottery_type=lottery_type,
                draw=draw_num,
                status="dry_run",
                message=f"Would insert: numbers={fetched['numbers']}, special={fetched['special']}",
                data=fetched,
            )
            return {"draw": draw_num, "status": "dry_run",
                    "data": fetched}

        # Actual insert
        try:
            inserted, dupes = self._insert(fetched)
            if inserted > 0:
                logger.info(f"  ✅ {draw_num}: inserted")
                ingest_logger.log(
                    action="backfill",
                    lottery_type=lottery_type,
                    draw=draw_num,
                    status="ok",
                    message=f"Inserted: numbers={fetched['numbers']}, special={fetched['special']}",
                    data=fetched,
                )
                return {"draw": draw_num, "status": "inserted", "data": fetched}
            else:
                logger.info(f"  ⏩ {draw_num}: duplicate (skipped by DB constraint)")
                ingest_logger.log(
                    action="backfill",
                    lottery_type=lottery_type,
                    draw=draw_num,
                    status="skip",
                    message="DB constraint: duplicate",
                )
                return {"draw": draw_num, "status": "skipped",
                        "message": "DB duplicate"}
        except Exception as e:
            logger.error(f"  ❌ {draw_num}: insert error: {e}")
            ingest_logger.log(
                action="backfill",
                lottery_type=lottery_type,
                draw=draw_num,
                status="error",
                message=str(e),
            )
            return {"draw": draw_num, "status": "failed", "message": str(e)}

    def _get_existing(self, lottery_type: str, draw_num: str):
        """Return existing DB record or None."""
        import sqlite3
        import json
        import os

        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lottery_v2.db"),
            "lottery_api/data/lottery_v2.db",
            "data/lottery_v2.db",
        ]
        db_path = next((p for p in candidates if os.path.exists(p)), candidates[0])

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT draw, date, lottery_type, numbers, special FROM draws "
                "WHERE lottery_type=? AND draw=?",
                (lottery_type, draw_num),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "draw":        row["draw"],
                "date":        row["date"],
                "lotteryType": row["lottery_type"],
                "numbers":     json.loads(row["numbers"]),
                "special":     row["special"],
            }
        finally:
            conn.close()

    def _detect_conflict(self, existing: Dict, fetched: Dict) -> Optional[str]:
        """
        Compare existing DB record with fetched data.
        Returns conflict type string or None if identical.

        Conflict types:
          "numbers"   : different main numbers
          "special"   : different special number
          "date"      : different draw date
          "no_record" : existing is None (no DB record to compare against)
          "format"    : same numbers, different sort order (acceptable, not a conflict)
        """
        if existing is None:
            return "no_record"
        e_nums = sorted(existing.get("numbers", []))
        f_nums = sorted(fetched.get("numbers", []))
        if e_nums != f_nums:
            return "numbers"

        if existing.get("special", 0) != fetched.get("special", 0):
            return "special"

        # Date difference is informational, not a blocking conflict
        # (manual entry may use different date format)
        return None

    def _insert(self, draw_data: Dict):
        """Insert a single draw into the DB. Returns (inserted, dupes) tuple."""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
        from database import db_manager
        return db_manager.insert_draws([draw_data])


# Module-level singleton
backfill_engine = BackfillEngine()
