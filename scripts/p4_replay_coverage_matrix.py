"""
p4_replay_coverage_matrix.py
==============================
P4 Read-only Coverage Matrix Planner.

Computes per-draw × per-strategy coverage status for the N most recent draws.

HARD CONSTRAINTS:
  - read-only; no DB writes, no row generation, no backfill
  - catalog denominator = all catalog-visible entries (fallback P2/P1 JSON if no live table)
  - draw denominator = most recent N draws from draws table
  - coverage_status is purely observational — does NOT improve coverage
  - ARTIFACT_CANDIDATE / RECONSTRUCTIBLE / NO_DATA are NOT "COVERED"

Coverage status values:
  COVERED                — replay row exists for this draw × strategy
  MISSING_REPLAY_ROW     — strategy is REGISTERED_WITH_REPLAY_ROWS but no row for this draw
  RECONSTRUCTIBLE_PENDING— strategy is RECONSTRUCTIBLE (rows not yet backfilled)
  NO_DATA                — REGISTERED_NO_DATA or UNSUPPORTED
  ARTIFACT_ONLY          — ARTIFACT_CANDIDATE (not in runtime registry)
  UNSUPPORTED            — lifecycle state is UNSUPPORTED
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.services.replay_catalog_source import load_catalog_with_source_info

DB_PATH  = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON  = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON  = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
OUT_DIR  = REPO_ROOT / "outputs" / "replay"
DOC_DIR  = REPO_ROOT / "docs" / "replay"

# Coverage status constants
COVERED               = "COVERED"
MISSING_REPLAY_ROW    = "MISSING_REPLAY_ROW"
RECONSTRUCTIBLE_PENDING = "RECONSTRUCTIBLE_PENDING"
NO_DATA               = "NO_DATA"
ARTIFACT_ONLY         = "ARTIFACT_ONLY"
UNSUPPORTED_STATUS    = "UNSUPPORTED"


def _classify_coverage(
    visibility_state: str,
    has_row: bool,
) -> str:
    """
    Determine coverage status for a draw × strategy pair.
    - Only REGISTERED_WITH_REPLAY_ROWS + has_row=True → COVERED
    - RECONSTRUCTIBLE → RECONSTRUCTIBLE_PENDING (never COVERED)
    - NO_DATA / UNSUPPORTED → NO_DATA
    - ARTIFACT_CANDIDATE → ARTIFACT_ONLY
    """
    if visibility_state == "REGISTERED_WITH_REPLAY_ROWS":
        return COVERED if has_row else MISSING_REPLAY_ROW
    if visibility_state == "RECONSTRUCTIBLE":
        return RECONSTRUCTIBLE_PENDING
    if visibility_state in ("REGISTERED_NO_DATA", "UNSUPPORTED"):
        return NO_DATA
    if visibility_state == "ARTIFACT_CANDIDATE":
        return ARTIFACT_ONLY
    return UNSUPPORTED_STATUS


def _get_recent_draws(conn: sqlite3.Connection, limit: int) -> list[dict]:
    """Return most recent N draws (all lottery types) ordered DESC by draw number."""
    rows = conn.execute(
        """
        SELECT draw, lottery_type, date
          FROM draws
         ORDER BY CAST(draw AS INTEGER) DESC
         LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [{"draw": r[0], "lottery_type": r[1], "date": r[2]} for r in rows]


def _get_replay_row_set(conn: sqlite3.Connection) -> set[tuple[str, str, str]]:
    """Return set of (lottery_type, target_draw, strategy_id) for all existing replay rows."""
    rows = conn.execute(
        "SELECT lottery_type, target_draw, strategy_id FROM strategy_prediction_replays"
    ).fetchall()
    return {(r[0], r[1], r[2]) for r in rows}


def _get_row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def run_coverage_matrix(
    limit: int = 50,
    db_path: Path = DB_PATH,
    p2_json: Path = P2_JSON,
    p1_json: Path = P1_JSON,
) -> dict:
    """
    Build coverage matrix. Returns a results dict; does not write anything.
    """
    # ── Load catalog ────────────────────────────────────────────────────────
    catalog_info = load_catalog_with_source_info(
        db_path=db_path, p2_json=p2_json, p1_json=p1_json
    )
    entries      = catalog_info["entries"]
    source_used  = catalog_info["source_used"]

    # Index catalog by (lottery_type, strategy_id)
    catalog_by_key: dict[tuple, object] = {}
    for e in entries:
        catalog_by_key[(e.lottery_type, e.strategy_id)] = e

    # Catalog by lottery_type
    strats_by_lt: dict[str, list] = defaultdict(list)
    for e in entries:
        strats_by_lt[e.lottery_type].append(e)

    # ── Load DB data (read-only) ─────────────────────────────────────────────
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row_count_before = _get_row_count(conn)
        recent_draws     = _get_recent_draws(conn, limit)
        replay_row_set   = _get_replay_row_set(conn)
        row_count_after  = _get_row_count(conn)
    finally:
        conn.close()

    assert row_count_before == row_count_after, "DB was modified during matrix computation!"

    # ── Build matrix ─────────────────────────────────────────────────────────
    # Per draw, per strategy (only strategies matching the draw's lottery_type)
    matrix_rows = []
    all_statuses: list[str] = []

    for draw_info in recent_draws:
        draw_no  = draw_info["draw"]
        lt       = draw_info["lottery_type"]
        strats   = strats_by_lt.get(lt, [])

        for e in strats:
            has_row = (lt, draw_no, e.strategy_id) in replay_row_set
            status  = _classify_coverage(e.catalog_visibility_state, has_row)
            all_statuses.append(status)
            matrix_rows.append({
                "draw":                    draw_no,
                "lottery_type":            lt,
                "draw_date":               draw_info["date"],
                "strategy_id":             e.strategy_id,
                "visibility_state":        e.catalog_visibility_state,
                "lifecycle_state":         e.lifecycle_state,
                "has_prediction_row":      has_row,
                "has_result_row":          True,  # draw is in draws table
                "coverage_status":         status,
            })

    # ── Summary ───────────────────────────────────────────────────────────────
    status_counts  = dict(Counter(all_statuses))
    total_cells    = len(matrix_rows)
    covered_cells  = status_counts.get(COVERED, 0)
    coverage_pct   = round(covered_cells / total_cells * 100, 2) if total_cells > 0 else 0.0

    # Per-lottery breakdown
    lt_summary: dict[str, dict] = {}
    for lt, strats in strats_by_lt.items():
        lt_draws = [d for d in recent_draws if d["lottery_type"] == lt]
        lt_cells  = len(lt_draws) * len(strats)
        lt_covered = sum(
            1 for r in matrix_rows
            if r["lottery_type"] == lt and r["coverage_status"] == COVERED
        )
        lt_summary[lt] = {
            "strategy_count":  len(strats),
            "draw_count":      len(lt_draws),
            "total_cells":     lt_cells,
            "covered":         lt_covered,
            "coverage_pct":    round(lt_covered / lt_cells * 100, 2) if lt_cells > 0 else 0.0,
        }

    return {
        "generated_at":        datetime.utcnow().isoformat() + "Z",
        "phase":               "P4",
        "mode":                "DRY_RUN",
        "dry_run":             True,
        "catalog_source":      source_used,
        "catalog_total":       len(entries),
        "draw_limit":          limit,
        "draws_evaluated":     len(recent_draws),
        "total_cells":         total_cells,
        "covered_cells":       covered_cells,
        "coverage_pct":        coverage_pct,
        "status_counts":       status_counts,
        "by_lottery_type":     lt_summary,
        "db_row_count_before": row_count_before,
        "db_row_count_after":  row_count_after,
        "matrix":              matrix_rows,
    }


def write_outputs(result: dict, json_out: Path, md_out: Path) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"JSON written to: {json_out}")

    md_out.parent.mkdir(parents=True, exist_ok=True)
    _write_md_report(result, md_out)
    print(f"MD written to: {md_out}")


def _write_md_report(r: dict, path: Path) -> None:
    lines = [
        "# P4 Replay Coverage Matrix — Dry-Run Report",
        "",
        f"Generated: {r['generated_at']}",
        f"Catalog source: `{r['catalog_source']}`  ",
        f"Catalog entries (denominator): {r['catalog_total']}  ",
        f"Draws evaluated: {r['draws_evaluated']} (most recent {r['draw_limit']})  ",
        f"Total cells: {r['total_cells']}  ",
        f"Covered cells: {r['covered_cells']} ({r['coverage_pct']}%)  ",
        "",
        "## Coverage Status Summary",
        "",
        "| Status | Count |",
        "|--------|-------|",
    ]
    for status, count in sorted(r["status_counts"].items()):
        lines.append(f"| `{status}` | {count} |")

    lines += [
        "",
        "## Per Lottery Type",
        "",
        "| Lottery Type | Strategies | Draws | Cells | Covered | Coverage% |",
        "|---|---|---|---|---|---|",
    ]
    for lt, s in r["by_lottery_type"].items():
        lines.append(
            f"| {lt} | {s['strategy_count']} | {s['draw_count']} "
            f"| {s['total_cells']} | {s['covered']} | {s['coverage_pct']}% |"
        )

    lines += [
        "",
        "## Safety Confirmation",
        "",
        f"- DB `strategy_prediction_replays` rows before: {r['db_row_count_before']}",
        f"- DB `strategy_prediction_replays` rows after: {r['db_row_count_after']}",
        f"- **Rows unchanged**: {r['db_row_count_before'] == r['db_row_count_after']}",
        "",
        "## Notes",
        "",
        "- `COVERED` = replay row exists for this draw × strategy",
        "- `MISSING_REPLAY_ROW` = REGISTERED_WITH_REPLAY_ROWS but no row yet",
        "- `RECONSTRUCTIBLE_PENDING` = has artifact, rows not yet backfilled (P5-P7 needed)",
        "- `NO_DATA` = no artifact, no rows, no reconstruction path",
        "- `ARTIFACT_ONLY` = ARTIFACT_CANDIDATE, not in runtime registry",
        "- This report is **read-only measurement only**. No rows were generated.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="P4 Replay Coverage Matrix (read-only)")
    parser.add_argument("--limit", type=int, default=50, help="Number of recent draws to evaluate")
    parser.add_argument(
        "--json-out", default=str(OUT_DIR / "p4_coverage_matrix_dry_run_20260520.json")
    )
    parser.add_argument(
        "--md-out", default=str(DOC_DIR / "p4_coverage_matrix_dry_run_20260520.md")
    )
    parser.add_argument("--no-write", action="store_true", help="Skip file writes (stdout summary only)")
    args = parser.parse_args()

    print(f"P4 Coverage Matrix — evaluating {args.limit} most recent draws...")
    result = run_coverage_matrix(limit=args.limit)

    print(f"  catalog entries: {result['catalog_total']}")
    print(f"  draws evaluated: {result['draws_evaluated']}")
    print(f"  total cells:     {result['total_cells']}")
    print(f"  covered:         {result['covered_cells']} ({result['coverage_pct']}%)")
    print(f"  status breakdown: {result['status_counts']}")
    print(f"  DB rows unchanged: {result['db_row_count_before']} → {result['db_row_count_after']}")

    if not args.no_write:
        write_outputs(result, Path(args.json_out), Path(args.md_out))
    else:
        print(json.dumps(result["status_counts"], indent=2))

    if result["db_row_count_before"] != result["db_row_count_after"]:
        print("CRITICAL: DB row count changed!", file=sys.stderr)
        sys.exit(1)

    print("Final classification: P4_COVERAGE_MATRIX_DRY_RUN_PASS")


if __name__ == "__main__":
    main()
