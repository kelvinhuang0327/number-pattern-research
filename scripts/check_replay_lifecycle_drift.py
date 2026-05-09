"""
Read-only lifecycle drift guard for Replay Lifecycle UI.

This script traces replay rows back to the registry lifecycle source of truth
and emits a JSON summary. It does not write to production data.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parent.parent
LOTTERY_API = REPO_ROOT / "lottery_api"
DB_PATH = LOTTERY_API / "data" / "lottery_v2.db"


def _resolve_db_path(explicit: Path | None = None) -> Path:
    """Resolve the replay DB path, honoring the test fixture override."""
    if explicit is not None:
        return explicit
    env_override = os.environ.get("LOTTERY_TEST_DB_PATH")
    if env_override:
        return Path(env_override)
    return DB_PATH

if str(LOTTERY_API) not in sys.path:
    sys.path.insert(0, str(LOTTERY_API))

from models.replay_strategy_registry import (  # noqa: E402
    LIFECYCLE_STATUSES,
    get_strategy_lifecycle_status,
    list_strategies,
)


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def collect_drift_report(db_path: Path | None = None) -> dict[str, Any]:
    """Collect a read-only lifecycle drift report from the replay DB."""
    db_path = _resolve_db_path(db_path)
    if not db_path.exists():
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "db_path": str(db_path),
            "status": "SKIPPED_ENV_UNAVAILABLE",
            "reason": "Replay DB not found",
            "registry_total_strategies": len(list_strategies()),
            "registry_by_lifecycle": {},
            "registry_strategy_ids": [],
            "replay_row_count": 0,
            "replay_rows_by_strategy": {},
            "replay_rows_by_lifecycle": {},
            "traceable_row_count": 0,
            "traceable_strategy_ids": [],
            "unknown_strategy_ids": [],
            "missing_lifecycle_status_strategy_ids": [],
        }

    registry_entries = list_strategies()
    registry_by_id = {
        entry["strategy_id"]: entry["strategy_lifecycle_status"]
        for entry in registry_entries
    }
    registry_by_lifecycle = Counter(entry["strategy_lifecycle_status"] for entry in registry_entries)

    with _connect_ro(db_path) as conn:
        row_counts = conn.execute(
            """
            SELECT strategy_id, COUNT(*) AS row_count
            FROM strategy_prediction_replays
            GROUP BY strategy_id
            ORDER BY strategy_id
            """
        ).fetchall()

    replay_rows_by_strategy = {row["strategy_id"]: int(row["row_count"]) for row in row_counts}
    unknown_strategy_ids = sorted(set(replay_rows_by_strategy) - set(registry_by_id))
    missing_lifecycle_status_strategy_ids = sorted(
        strategy_id for strategy_id, lifecycle in registry_by_id.items()
        if lifecycle not in LIFECYCLE_STATUSES
    )

    replay_rows_by_lifecycle = Counter()
    traceable_row_count = 0
    traceable_strategy_ids = []
    for strategy_id, row_count in replay_rows_by_strategy.items():
        lifecycle = get_strategy_lifecycle_status(strategy_id)
        if lifecycle:
            replay_rows_by_lifecycle[lifecycle] += row_count
            traceable_row_count += row_count
            traceable_strategy_ids.append(strategy_id)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "db_path": str(db_path),
        "status": "PASS",
        "registry_total_strategies": len(registry_entries),
        "registry_by_lifecycle": dict(registry_by_lifecycle),
        "registry_strategy_ids": sorted(registry_by_id),
        "replay_row_count": sum(replay_rows_by_strategy.values()),
        "replay_rows_by_strategy": replay_rows_by_strategy,
        "replay_rows_by_lifecycle": dict(replay_rows_by_lifecycle),
        "traceable_row_count": traceable_row_count,
        "traceable_strategy_ids": sorted(traceable_strategy_ids),
        "unknown_strategy_ids": unknown_strategy_ids,
        "missing_lifecycle_status_strategy_ids": missing_lifecycle_status_strategy_ids,
    }

    if unknown_strategy_ids or missing_lifecycle_status_strategy_ids:
        report["status"] = "BLOCKED"

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay lifecycle drift guard")
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    report = collect_drift_report(args.db_path)
    payload = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())