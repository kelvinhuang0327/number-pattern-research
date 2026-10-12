"""
Audit logger for all automated ingest operations.
Writes to lottery_api/data/ingest_log.jsonl (one JSON object per line).

Schema per entry:
  timestamp   : ISO-8601 UTC
  action      : fetch_latest | scan_missing | backfill | conflict
  lottery_type: BIG_LOTTO | POWER_LOTTO | DAILY_539
  draw        : "115000037" or null
  status      : ok | skip | error | conflict | dry_run
  message     : human-readable summary
  data        : optional extra payload (dict)
"""

import json
import os
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any

logger = logging.getLogger(__name__)

# Default log file location (relative to lottery_api/)
_DEFAULT_LOG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),  # lottery_api/
    "data", "ingest_log.jsonl"
)


class IngestLogger:
    def __init__(self, log_path: str = _DEFAULT_LOG_PATH):
        self.log_path = log_path
        os.makedirs(os.path.dirname(log_path), exist_ok=True)

    def log(
        self,
        action: str,
        lottery_type: str,
        draw: Optional[str] = None,
        status: str = "ok",
        message: str = "",
        data: Optional[Dict[str, Any]] = None,
    ) -> Dict:
        entry = {
            "timestamp":    datetime.now(timezone.utc).isoformat(),
            "action":       action,
            "lottery_type": lottery_type,
            "draw":         draw,
            "status":       status,
            "message":      message,
            "data":         data or {},
        }
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"❌ IngestLogger write failed: {e}")
        return entry

    def get_recent(self, limit: int = 100, offset: int = 0,
                   lottery_type: Optional[str] = None) -> List[Dict]:
        """Return log entries newest first, with optional offset for pagination."""
        if not os.path.exists(self.log_path):
            return []
        entries = []
        try:
            with open(self.log_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        e = json.loads(line)
                        if lottery_type and e.get("lottery_type") != lottery_type:
                            continue
                        entries.append(e)
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.error(f"❌ IngestLogger read failed: {e}")
        all_newest_first = list(reversed(entries))
        return all_newest_first[offset: offset + limit]

    def get_stats(self) -> Dict:
        """Return summary counts by status."""
        entries = self.get_recent(limit=10000)
        stats: Dict[str, int] = {}
        for e in entries:
            s = e.get("status", "unknown")
            stats[s] = stats.get(s, 0) + 1
        return {"total": len(entries), "by_status": stats}

    def clear(self) -> int:
        """Truncate the log file. Returns number of lines cleared."""
        if not os.path.exists(self.log_path):
            return 0
        with open(self.log_path, "r", encoding="utf-8") as f:
            count = sum(1 for line in f if line.strip())
        open(self.log_path, "w").close()
        logger.info(f"✅ Ingest log cleared ({count} entries)")
        return count


# Module-level singleton
ingest_logger = IngestLogger()
