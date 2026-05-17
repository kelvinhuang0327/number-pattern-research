#!/usr/bin/env python3
"""Read-only RSM refresh diagnostic.

This script inspects the current replay/strategy state without invoking any
mutating RSM bootstrap path. It is safe to run against the live SQLite database
opened in read-only mode.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
RSM_BOOTSTRAP_PATH = PROJECT_ROOT / "tools" / "rsm_bootstrap.py"
RSM_ENGINE_PATH = PROJECT_ROOT / "lottery_api" / "engine" / "rolling_strategy_monitor.py"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def detect_rsm_behavior() -> dict:
    bootstrap_text = read_text(RSM_BOOTSTRAP_PATH)
    engine_text = read_text(RSM_ENGINE_PATH)

    has_dry_run_flag = bool(re.search(r"--dry-run\b", bootstrap_text))
    has_json_out_flag = bool(re.search(r"--json-out\b", bootstrap_text))
    calls_save = "tracker.save()" in engine_text
    uses_tracker_save = bool(re.search(r"\.save\(\)", engine_text))

    return {
        "bootstrap_path": str(RSM_BOOTSTRAP_PATH),
        "engine_path": str(RSM_ENGINE_PATH),
        "dry_run_available": has_dry_run_flag,
        "json_out_available": has_json_out_flag,
        "bootstrap_calls_tracker_save": calls_save,
        "engine_uses_save": uses_tracker_save,
        "write_mode_reason": (
            "bootstrap() persists via tracker.save()" if calls_save else "no explicit save call detected"
        ),
    }


def audit_db() -> dict:
    conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        result = {
            "generated_at": dt.datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "database": str(DB_PATH),
            "prediction_item_status_counts": [
                dict(row)
                for row in cur.execute(
                    """
                    SELECT status, COUNT(*) AS count
                    FROM prediction_items
                    GROUP BY status
                    ORDER BY status
                    """
                )
            ],
            "replay_total": cur.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays"
            ).fetchone()[0],
            "controlled_apply_counts": [
                dict(row)
                for row in cur.execute(
                    """
                    SELECT controlled_apply_id, COUNT(*) AS count
                    FROM strategy_prediction_replays
                    WHERE controlled_apply_id IS NOT NULL
                    GROUP BY controlled_apply_id
                    ORDER BY controlled_apply_id
                    """
                )
            ],
            "latest_draws": [
                dict(row)
                for row in cur.execute(
                    """
                    SELECT lottery_type, MAX(CAST(draw AS INTEGER)) AS latest_draw
                    FROM draws
                    GROUP BY lottery_type
                    ORDER BY lottery_type
                    """
                )
            ],
        }
        return result
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only RSM refresh diagnostic")
    parser.add_argument("--json-out", required=True, help="Output path for JSON status")
    args = parser.parse_args()

    payload = {
        "classification": "P4A_RSM_REFRESH_BLOCKED_NEEDS_WRITE_MODE_APPROVAL",
        "rsm_behavior": detect_rsm_behavior(),
        "db_audit": audit_db(),
    }

    json_out = Path(args.json_out)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
