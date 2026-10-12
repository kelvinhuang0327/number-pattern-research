"""
P86 Live Monitoring / Source Decision Guard
Classification: P86_LIVE_MONITORING_SOURCE_DECISION_GUARD_READY

Read-only script. Never writes to DB, never inserts replay rows,
never calls official API for writes, never creates tables.

Usage:
  python scripts/p86_live_monitoring_source_decision_guard.py
  python scripts/p86_live_monitoring_source_decision_guard.py --source-snapshot path/to/snapshot.json
  python scripts/p86_live_monitoring_source_decision_guard.py --allow-network-read

Classifications:
  STABLE_NO_NEW_DRAW          source max draw == DB max draw
  SOURCE_DECISION_REQUIRED    source max draw > DB max draw (new draws exist)
  SOURCE_STALE                source max draw < DB max draw (source behind DB)
  SOURCE_UNAVAILABLE          no source provided and network not allowed/failed
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from typing import Optional

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")
OUTPUT_PATH = os.path.join(
    REPO_ROOT, "outputs", "replay", "p86_live_monitoring_source_decision_guard_20260526.json"
)

POLICY_VERSION = "p86-v1"
PHASE = "P86"
CLASSIFICATION_STABLE = "STABLE_NO_NEW_DRAW"
CLASSIFICATION_DECISION_REQUIRED = "SOURCE_DECISION_REQUIRED"
CLASSIFICATION_STALE = "SOURCE_STALE"
CLASSIFICATION_UNAVAILABLE = "SOURCE_UNAVAILABLE"


def get_db_max_draw(db_path: str, lottery_type: str = "POWER_LOTTO") -> int:
    """Read current max draw from DB. Read-only — no writes."""
    if not os.path.isfile(db_path):
        raise FileNotFoundError(f"DB not found: {db_path}")
    # Read-only by design: no write statements are issued
    con = sqlite3.connect(db_path)
    try:
        cur = con.cursor()
        cur.execute(
            "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type=?",
            (lottery_type,),
        )
        result = cur.fetchone()[0]
        return int(result) if result is not None else 0
    finally:
        con.close()


def get_db_replay_row_count() -> int:
    """Read replay row count. Read-only."""
    # Read-only by design: no write statements are issued
    con = sqlite3.connect(DB_PATH)
    try:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
        return cur.fetchone()[0]
    finally:
        con.close()


def load_source_snapshot(path: str) -> dict:
    """
    Load a source snapshot JSON file.

    Expected format:
      {
        "lottery_type": "POWER_LOTTO",
        "max_draw": 115000042,
        "source": "operator_upload",
        "as_of": "2026-05-27"
      }
    """
    with open(path) as f:
        data = json.load(f)
    required = {"lottery_type", "max_draw", "source"}
    missing = required - data.keys()
    if missing:
        raise ValueError(f"Source snapshot missing fields: {missing}")
    return data


def try_network_read(lottery_type: str = "POWER_LOTTO") -> Optional[dict]:
    """
    Attempt a read-only query to official API.
    Only called when --allow-network-read is passed.
    Never writes. Returns None on failure.
    """
    try:
        import urllib.request

        # Read-only endpoint — no authentication, no write params
        url = f"http://127.0.0.1:8002/api/draws/latest?lottery_type={lottery_type}"
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8")
            data = json.loads(body)
            return {
                "lottery_type": lottery_type,
                "max_draw": int(data.get("draw", 0)),
                "source": "network_read_local_api",
                "as_of": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as exc:
        return {"error": str(exc), "source": "network_read_failed"}


def classify(db_max: int, source_max: Optional[int]) -> str:
    if source_max is None:
        return CLASSIFICATION_UNAVAILABLE
    if source_max == db_max:
        return CLASSIFICATION_STABLE
    if source_max > db_max:
        return CLASSIFICATION_DECISION_REQUIRED
    return CLASSIFICATION_STALE


def source_decision_policy(classification: str, source_max: Optional[int], db_max: int) -> dict:
    """
    Return the source decision policy block for the current classification.
    No side effects — read-only.
    """
    base = {
        "classification": classification,
        "db_max_draw": db_max,
        "source_max_draw": source_max,
        "forbidden_automatic_behavior": [
            "auto_db_insert",
            "auto_replay_apply",
            "fallback_to_official_api_without_explicit_decision",
            "new_staging_table_creation",
        ],
    }

    if classification == CLASSIFICATION_STABLE:
        base["action"] = "no_action_required"
        base["message"] = (
            f"DB and source agree on max draw {db_max}. "
            "System is current. No new draws to process."
        )
        base["allowed_next_steps"] = ["continue_monitoring", "run_freshness_guard"]

    elif classification == CLASSIFICATION_DECISION_REQUIRED:
        base["action"] = "SOURCE_DECISION_REQUIRED"
        base["message"] = (
            f"Source reports max draw {source_max}, DB has {db_max}. "
            f"{source_max - db_max} new draw(s) detected. "
            "Operator must make an explicit source decision before any ingestion or replay apply."
        )
        base["allowed_source_decisions"] = [
            "uploaded_source_provided_by_operator",
            "official_api_explicitly_authorized",
            "hold_no_action",
            "manual_verification_required",
        ]
        base["blocked_until"] = "explicit_operator_authorization"

    elif classification == CLASSIFICATION_STALE:
        base["action"] = "investigate_source"
        base["message"] = (
            f"Source reports max draw {source_max}, but DB has {db_max}. "
            "Source is behind the DB. Verify source freshness."
        )
        base["allowed_next_steps"] = [
            "check_source_provider",
            "verify_source_file_date",
            "run_freshness_guard",
        ]

    elif classification == CLASSIFICATION_UNAVAILABLE:
        base["action"] = "source_unavailable"
        base["message"] = (
            "No source provided and network read not authorized or failed. "
            "Run with --source-snapshot <path> or --allow-network-read to compare against a source."
        )
        base["allowed_next_steps"] = [
            "provide_source_snapshot",
            "pass_allow_network_read_flag",
        ]

    return base


def run(source_snapshot_path: Optional[str] = None, allow_network_read: bool = False) -> dict:
    """
    Main monitoring run. Read-only throughout.
    Returns the full result dict without writing to DB.
    """
    ts = datetime.now(timezone.utc).isoformat()
    db_max = get_db_max_draw(DB_PATH)
    replay_rows = get_db_replay_row_count()

    source_data: Optional[dict] = None
    source_max: Optional[int] = None
    source_method = "none"

    if source_snapshot_path:
        source_data = load_source_snapshot(source_snapshot_path)
        source_max = int(source_data["max_draw"])
        source_method = "snapshot_file"
    elif allow_network_read:
        source_data = try_network_read()
        if source_data and "error" not in source_data:
            source_max = int(source_data["max_draw"])
            source_method = "network_read"
        else:
            source_method = "network_read_failed"

    classification = classify(db_max, source_max)
    policy = source_decision_policy(classification, source_max, db_max)

    result = {
        "phase": PHASE,
        "policy_version": POLICY_VERSION,
        "classification": classification,
        "as_of": ts,
        "db": {
            "path": DB_PATH,
            "lottery_type": "POWER_LOTTO",
            "max_draw": db_max,
            "replay_rows": replay_rows,
            "db_writes": False,
            "replay_rows_inserted": 0,
        },
        "source": {
            "method": source_method,
            "max_draw": source_max,
            "data": source_data,
        },
        "policy": policy,
        "governance": {
            "no_db_writes": True,
            "no_replay_inserts": True,
            "no_official_api_writes": True,
            "no_new_tables": True,
            "no_ingestion": True,
            "read_only": True,
        },
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="P86 Live Monitoring / Source Decision Guard (read-only)"
    )
    parser.add_argument("--source-snapshot", type=str, default=None,
                        help="Path to source snapshot JSON file")
    parser.add_argument("--allow-network-read", action="store_true", default=False,
                        help="Allow a read-only network call to the local API")
    parser.add_argument("--output", type=str, default=OUTPUT_PATH,
                        help="Output JSON path (default: outputs/replay/p86_...json)")
    args = parser.parse_args()

    result = run(
        source_snapshot_path=args.source_snapshot,
        allow_network_read=args.allow_network_read,
    )

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w") as f:
        json.dump(result, f, indent=2)

    print(f"classification : {result['classification']}")
    print(f"db_max_draw    : {result['db']['max_draw']}")
    print(f"source_max_draw: {result['source']['max_draw']}")
    print(f"replay_rows    : {result['db']['replay_rows']}")
    print(f"db_writes      : {result['db']['db_writes']}")
    print(f"output         : {args.output}")

    # Exit non-zero only for SOURCE_DECISION_REQUIRED so CI can catch it
    if result["classification"] == CLASSIFICATION_DECISION_REQUIRED:
        sys.exit(2)


if __name__ == "__main__":
    main()
