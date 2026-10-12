"""
Missing issue detector.

Compares draw numbers stored in the local DB against a reference set
(fetched from the official site) and identifies gaps.

Detection logic:
  1. Get all draw numbers from DB for a lottery type (sorted ascending)
  2. Fetch recent draws from official site
  3. Find draw numbers in official set that are absent from DB
  4. Also detect internal integer gaps in the DB sequence

Note: draw numbers are NOT guaranteed to be consecutive integers (holidays,
cancellations, year boundaries). We rely on the official site's own listing
as the authoritative sequence, not raw enumeration.
"""

import logging
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)

SUPPORTED = {"BIG_LOTTO", "POWER_LOTTO", "DAILY_539"}


class MissingIssueDetector:
    """
    Detects missing draw records by comparing DB vs official source.

    Usage:
        detector = MissingIssueDetector()
        result   = detector.scan("BIG_LOTTO")
    """

    def __init__(self):
        # Lazy imports to avoid circular deps
        pass

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def scan(self, lottery_type: str,
             max_recent_fetch: int = 50) -> Dict:
        """
        Scan for missing issues for a given lottery type.

        Returns:
          {
            lottery_type      : str,
            db_count          : int,
            db_latest_draw    : str | None,
            db_earliest_draw  : str | None,
            official_count    : int,
            official_latest   : str | None,
            missing_draws     : list[str],   # draw numbers absent in DB
            missing_count     : int,
            internal_gaps     : list[dict],  # gaps within DB sequence
            scan_error        : str | None,
          }
        """
        result = {
            "lottery_type":     lottery_type,
            "db_count":         0,
            "db_latest_draw":   None,
            "db_earliest_draw": None,
            "official_count":   0,
            "official_latest":  None,
            "missing_draws":    [],
            "missing_count":    0,
            "internal_gaps":    [],
            "scan_error":       None,
        }

        if lottery_type not in SUPPORTED:
            result["scan_error"] = f"Unsupported lottery type: {lottery_type}"
            return result

        # --- Step 1: Get DB draws ---
        try:
            db_draws = self._get_db_draw_numbers(lottery_type)
        except Exception as e:
            result["scan_error"] = f"DB query failed: {e}"
            return result

        db_set: Set[str] = set(db_draws)
        result["db_count"]         = len(db_draws)
        result["db_latest_draw"]   = db_draws[-1] if db_draws else None
        result["db_earliest_draw"] = db_draws[0]  if db_draws else None

        # --- Step 2: Detect internal DB gaps ---
        result["internal_gaps"] = self._detect_internal_gaps(db_draws)

        # --- Step 3: Fetch official recent draws ---
        try:
            from .taiwan_lottery_fetcher import fetcher
            official_draws = fetcher.fetch_recent(
                lottery_type, max_draws=max_recent_fetch
            )
        except Exception as e:
            result["scan_error"] = f"Official fetch failed: {e}"
            # Return partial result (DB info still valid)
            return result

        if not official_draws:
            result["scan_error"] = (
                "Official site returned no draws. "
                "Check network or source URL."
            )
            return result

        official_draw_numbers = [d["draw"] for d in official_draws]
        official_set: Set[str] = set(official_draw_numbers)
        official_date_map: Dict[str, str] = {d["draw"]: d.get("date", "") for d in official_draws}

        result["official_count"]       = len(official_draws)
        result["official_latest"]      = official_draw_numbers[0]  # newest first
        result["official_latest_date"] = official_draws[0].get("date", "") if official_draws else ""

        # --- Step 4: Find missing (in official but not in DB) ---
        missing = sorted(
            [d for d in official_draw_numbers if d not in db_set],
            key=lambda x: int(x)
        )
        result["missing_draws"] = missing
        result["missing_count"] = len(missing)
        result["missing_draws_detail"] = [
            {"draw": d, "date": official_date_map.get(d, "")}
            for d in missing
        ]

        logger.info(
            f"✅ Scan {lottery_type}: DB={len(db_draws)}, "
            f"official={len(official_draws)}, missing={len(missing)}"
        )
        return result

    def scan_all(self) -> Dict[str, Dict]:
        """Scan all 3 supported lottery types."""
        return {lt: self.scan(lt) for lt in SUPPORTED}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_db_draw_numbers(self, lottery_type: str) -> List[str]:
        """
        Return all draw numbers for a lottery type from DB,
        sorted ascending by integer value.
        """
        import sqlite3
        import os
        import sys

        # Locate the DB file (works whether called from lottery_api/ or project root)
        candidates = [
            os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "lottery_v2.db"),
            "lottery_api/data/lottery_v2.db",
            "data/lottery_v2.db",
        ]
        db_path = next((p for p in candidates if os.path.exists(p)), candidates[0])

        conn = sqlite3.connect(db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT draw FROM draws
                WHERE lottery_type = ?
                ORDER BY CAST(draw AS INTEGER) ASC
                """,
                (lottery_type,),
            )
            rows = cursor.fetchall()
            return [r[0] for r in rows]
        finally:
            conn.close()

    def _detect_internal_gaps(self, draws: List[str]) -> List[Dict]:
        """
        Find within-year sequence gaps in the DB draw list.

        Draw number format: YYYNNNNNN
          YYY    = ROC year (3 digits, e.g. 115 = 2026)
          NNNNNN = sequential issue within that year (6 digits)

        Year boundaries (e.g. 96000104 → 97000001) are NOT gaps.
        Only consecutive draws within the same year where the
        sequential part skips > 1 are flagged.
        """
        if len(draws) < 2:
            return []

        def _split(draw: str):
            # Draw number = {ROC_year}{6-digit-sequence}
            # Sequence is always the rightmost 6 digits.
            # Year may be 2 or 3 digits (e.g., 96→115).
            seq  = int(draw[-6:])
            year = int(draw[:-6])
            return year, seq

        gaps = []
        for i in range(1, len(draws)):
            prev_year, prev_seq = _split(draws[i - 1])
            curr_year, curr_seq = _split(draws[i])

            if prev_year != curr_year:
                continue      # year boundary — expected jump

            diff = curr_seq - prev_seq
            if diff > 1:
                gaps.append({
                    "from_draw": draws[i - 1],
                    "to_draw":   draws[i],
                    "gap_size":  diff - 1,
                    "note": "Within-year gap: possible cancellation/holiday or missing data",
                })
        return gaps


# Module-level singleton
detector = MissingIssueDetector()
