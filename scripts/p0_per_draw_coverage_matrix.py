#!/usr/bin/env python3
"""
p0_per_draw_coverage_matrix.py
===============================
P0 Schema Stabilization — Per-draw coverage matrix (READ-ONLY).

Computes for the most recent 10 draws per lottery type:
  - draw_id
  - total_strategies (canonical count from registry)
  - with_prediction_row (strategies that have at least 1 replay row for this draw)
  - coverage_pct
  - by_truth_level breakdown
  - by_lifecycle breakdown

SAFETY: No writes. No strategy execution. No row creation.

Usage:
    python3 scripts/p0_per_draw_coverage_matrix.py
    python3 scripts/p0_per_draw_coverage_matrix.py --json-out /tmp/matrix.json
"""
from __future__ import annotations

import argparse
import datetime
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = PROJECT_ROOT / "outputs" / "replay"

LOTTERY_TYPES = ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]
DRAWS_PER_TYPE = 10


def _get_registry_strategies() -> dict[str, list[str]]:
    """Return canonical strategies per lottery type from registry."""
    sys.path.insert(0, str(PROJECT_ROOT))
    from lottery_api.models.replay_strategy_registry import list_strategies
    strats = list_strategies()
    result: dict[str, list[str]] = {lt: [] for lt in LOTTERY_TYPES}
    for s in strats:
        for lt in (s.get("supported_lottery_types") or []):
            if lt in result:
                result[lt].append(s["strategy_id"])
    return result


def run_coverage_matrix() -> dict[str, Any]:
    """Compute per-draw coverage matrix (read-only)."""
    ts = datetime.datetime.now(datetime.UTC).isoformat()

    result: dict[str, Any] = {
        "generated_at": ts,
        "mission": "P0 Schema Stabilization — per-draw coverage matrix",
        "db_path": str(DB_PATH),
        "draws_per_type": DRAWS_PER_TYPE,
        "safety": "READ_ONLY — no rows written",
        "by_lottery": {},
    }

    try:
        registry_strats = _get_registry_strategies()
    except Exception as exc:
        result["error"] = f"Registry load failed: {exc}"
        return result

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    try:
        for lt in LOTTERY_TYPES:
            canonical_strategies = registry_strats.get(lt, [])
            total_strategies = len(canonical_strategies)

            # Get last N draws for this lottery type
            cur = conn.execute(
                """
                SELECT draw, date FROM draws
                WHERE lottery_type = ?
                ORDER BY CAST(draw AS INTEGER) DESC
                LIMIT ?
                """,
                (lt, DRAWS_PER_TYPE),
            )
            draws = cur.fetchall()

            draws_data = []
            for row in draws:
                draw_id = row["draw"]
                draw_date = row["date"]

                # Count strategies with at least 1 replay row for this draw
                cur2 = conn.execute(
                    """
                    SELECT strategy_id, COUNT(*) as row_count,
                           GROUP_CONCAT(DISTINCT truth_level) as truth_levels,
                           MIN(generated_at) as first_generated
                    FROM strategy_prediction_replays
                    WHERE lottery_type = ? AND target_draw = ?
                    GROUP BY strategy_id
                    """,
                    (lt, draw_id),
                )
                strategy_rows = cur2.fetchall()

                with_prediction = len(strategy_rows)
                coverage_pct = (with_prediction / total_strategies * 100) if total_strategies > 0 else 0.0

                # Truth level breakdown
                truth_level_counts: dict[str, int] = {}
                for sr in strategy_rows:
                    for tl in (sr["truth_levels"] or "UNKNOWN").split(","):
                        truth_level_counts[tl] = truth_level_counts.get(tl, 0) + 1

                # Lifecycle breakdown (strategies with rows vs without)
                strategies_with_rows = {sr["strategy_id"] for sr in strategy_rows}
                strategies_without = [s for s in canonical_strategies if s not in strategies_with_rows]

                draws_data.append({
                    "draw_id": draw_id,
                    "draw_date": draw_date,
                    "total_strategies_in_registry": total_strategies,
                    "with_prediction_row": with_prediction,
                    "without_prediction_row": total_strategies - with_prediction,
                    "coverage_pct": round(coverage_pct, 1),
                    "by_truth_level": truth_level_counts,
                    "strategies_without_row": strategies_without,
                    "total_replay_rows": sum(sr["row_count"] for sr in strategy_rows),
                })

            result["by_lottery"][lt] = {
                "canonical_strategy_count": total_strategies,
                "canonical_strategies": canonical_strategies,
                "draws": draws_data,
                "summary": {
                    "avg_coverage_pct": round(
                        sum(d["coverage_pct"] for d in draws_data) / len(draws_data), 1
                    ) if draws_data else 0.0,
                    "draws_with_any_row": sum(1 for d in draws_data if d["with_prediction_row"] > 0),
                    "draws_with_full_coverage": sum(
                        1 for d in draws_data
                        if d["with_prediction_row"] >= total_strategies and total_strategies > 0
                    ),
                },
            }

    finally:
        conn.close()

    return result


def main():
    parser = argparse.ArgumentParser(
        description="P0 per-draw coverage matrix (read-only)"
    )
    parser.add_argument("--json-out", help="Output path for JSON result")
    args = parser.parse_args()

    print("=" * 60)
    print("P0 Per-draw Coverage Matrix — READ ONLY")
    print(f"DB: {DB_PATH}")
    print("=" * 60)

    matrix = run_coverage_matrix()

    if "error" in matrix:
        print(f"ERROR: {matrix['error']}", file=sys.stderr)
        sys.exit(1)

    # Print summary
    for lt, data in matrix.get("by_lottery", {}).items():
        print(f"\n{lt} (canonical strategies: {data['canonical_strategy_count']})")
        for d in data["draws"]:
            print(
                f"  {d['draw_id']} ({d['draw_date']}): "
                f"{d['with_prediction_row']}/{d['total_strategies_in_registry']} = "
                f"{d['coverage_pct']}% coverage"
            )

    # Write to outputs/replay/
    log_date = datetime.datetime.now(datetime.UTC).strftime("%Y%m%d")
    default_out = OUTPUT_DIR / f"p0_per_draw_coverage_matrix_{log_date}.json"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(str(default_out), "w") as f:
        json.dump(matrix, f, indent=2, ensure_ascii=False)
    print(f"\nJSON written: {default_out}")

    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(matrix, f, indent=2, ensure_ascii=False)
        print(f"JSON also written: {args.json_out}")


if __name__ == "__main__":
    main()
