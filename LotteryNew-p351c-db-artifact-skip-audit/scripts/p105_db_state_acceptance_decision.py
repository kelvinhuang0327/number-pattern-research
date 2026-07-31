#!/usr/bin/env python3
"""
P105 DB State Acceptance Decision — Read-Only Helper Script
===========================================================
Prints the P105 decision summary from the governance JSON artifact.
This script is STRICTLY READ-ONLY: it does NOT modify the DB, any file,
or any configuration. It may only read.

Usage:
    python scripts/p105_db_state_acceptance_decision.py
    python scripts/p105_db_state_acceptance_decision.py --json-out /tmp/p105_summary.json
"""

import argparse
import json
import os
import sqlite3
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(REPO_ROOT, "outputs", "replay",
                         "p105_db_state_acceptance_decision_20260527.json")
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")


def load_artifact() -> dict:
    with open(JSON_PATH, encoding="utf-8") as f:
        return json.load(f)


def query_db() -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        replay_rows = conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        per_lottery = {}
        for row in conn.execute(
            "SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER)) "
            "FROM draws "
            "WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO') "
            "GROUP BY lottery_type"
        ).fetchall():
            per_lottery[row[0]] = {"count": row[1], "max_draw": row[2]}
        return {"replay_rows": replay_rows, "per_lottery": per_lottery}
    finally:
        conn.close()


def print_summary(artifact: dict, live_db: dict) -> None:
    sep = "=" * 70
    print(sep)
    print("P105 DB STATE ACCEPTANCE DECISION — SUMMARY")
    print(sep)
    print(f"Classification : {artifact['classification']}")
    print(f"User Input     : {artifact['user_input_verbatim']!r}  →  {artifact['interpretation']}")
    print(f"Selected Option: {artifact['selected_option']}")
    print()

    print("--- Pre-flight snapshot (from artifact) ---")
    pf = artifact["preflight"]
    print(f"  HEAD commit  : {pf['head_commit']}")
    print(f"  Drift guard  : {pf['drift_guard']}")
    print(f"  Gov guard    : {pf['branch_governance_guard']}")
    print(f"  Contamination: {pf['context_contamination_check']}")
    print()

    print("--- Live DB (read-only query now) ---")
    print(f"  Replay rows  : {live_db['replay_rows']}  (expected: 54462)")
    for lt in ["3_STAR", "4_STAR", "POWER_LOTTO"]:
        info = live_db["per_lottery"].get(lt, {})
        print(f"  {lt:12s} : count={info.get('count','?')}, max_draw={info.get('max_draw','?')}")
    print()

    print("--- Authorization table ---")
    auth = artifact["authorize"]
    for k, v in auth.items():
        mark = "✅" if v else "❌"
        print(f"  {mark} {k}: {v}")
    print()

    print("--- Never-Again Governance Clause ---")
    print(artifact["never_again_clause"])
    print()

    print("--- Source-Unknown Caveat ---")
    print(artifact["source_unknown_caveat"])
    print()

    print("--- Next Actions ---")
    for action in artifact.get("next_actions", []):
        print(f"  [{action['phase']}] {action['name']} — {action['description'][:80]}...")
    print()

    print(f"Final Classification: {artifact['classification']}")
    print(sep)


def main() -> None:
    parser = argparse.ArgumentParser(description="P105 DB State Acceptance — read-only summary")
    parser.add_argument("--json-out", metavar="PATH",
                        help="Write the live-query results to this JSON file (optional)")
    args = parser.parse_args()

    if not os.path.isfile(JSON_PATH):
        print(f"ERROR: Artifact not found: {JSON_PATH}", file=sys.stderr)
        sys.exit(1)

    artifact = load_artifact()
    live_db = query_db()
    print_summary(artifact, live_db)

    if args.json_out:
        out = {
            "classification": artifact["classification"],
            "live_db": live_db,
            "artifact_snapshot": {
                "user_input_verbatim": artifact["user_input_verbatim"],
                "interpretation": artifact["interpretation"],
                "selected_option": artifact["selected_option"],
                "authorize": artifact["authorize"],
            }
        }
        with open(args.json_out, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
        print(f"[p105-helper] JSON written to: {args.json_out}")


if __name__ == "__main__":
    main()
