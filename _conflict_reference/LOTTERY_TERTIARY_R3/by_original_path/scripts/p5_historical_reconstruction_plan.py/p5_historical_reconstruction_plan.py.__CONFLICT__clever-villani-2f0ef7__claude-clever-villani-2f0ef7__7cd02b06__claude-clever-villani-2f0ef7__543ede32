"""
p5_historical_reconstruction_plan.py
======================================
P5 Historical Reconstruction Dry-run Row Plan.

Builds a per-draw × per-strategy plan of which replay rows COULD be inserted
in a future P7 Controlled Apply phase. Does NOT insert any rows.

HARD CONSTRAINTS:
  - No --apply option; this script is permanently dry-run only
  - No DB writes; no prediction rows; no replay rows
  - No strategy logic execution
  - No invented prediction numbers; only propagated from existing DB payload
  - ARTIFACT_CANDIDATE → SKIP_ARTIFACT_ONLY
  - CODE_SCAN strategies → NEEDS_P6_POLICY
  - NO_DATA → not processed (only RECONSTRUCTIBLE in scope)
  - REGISTERED_WITH_REPLAY_ROWS → SKIP_ALREADY_COVERED
  - Draws already covered in strategy_prediction_replays → SKIP_ALREADY_COVERED
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from lottery_api.services.replay_catalog_source import load_catalog_with_source_info
from scripts.p5_reconstruction_input_inventory import _load_p1_metadata_overlay, _apply_p1_overlay
from lottery_api.models.replay_reconstruction_plan_contract import (
    ReconstructionPlanRow,
    PlannedAction,
    TrustLevel,
    TruthLevel,
    validate_plan_row,
)

DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P2_JSON = REPO_ROOT / "outputs" / "replay" / "p2_catalog_apply_dry_run_20260520.json"
P1_JSON = REPO_ROOT / "outputs" / "replay" / "p1_catalog_visibility_plan_20260519.json"
P4_JSON = REPO_ROOT / "outputs" / "replay" / "p4_coverage_matrix_dry_run_20260520.json"
OUT_DIR = REPO_ROOT / "outputs" / "replay"
DOC_DIR = REPO_ROOT / "docs" / "replay"


def _db_row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]


def _get_existing_replay_draws(conn: sqlite3.Connection, strategy_id: str, lottery_type: str) -> set[str]:
    """Return set of target_draws already in strategy_prediction_replays for this strategy."""
    rows = conn.execute(
        "SELECT target_draw FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type=?",
        (strategy_id, lottery_type),
    ).fetchall()
    return {r[0] for r in rows}


def _get_draw_date(conn: sqlite3.Connection, draw: str, lottery_type: str) -> str | None:
    row = conn.execute(
        "SELECT date FROM draws WHERE draw=? AND lottery_type=? LIMIT 1",
        (draw, lottery_type),
    ).fetchone()
    return row[0] if row else None


def _make_provenance_hash(strategy_id: str, draw: str, run_id: int | None, source: str) -> str:
    """Deterministic hash for plan row provenance. Not a secret."""
    raw = f"P5|{strategy_id}|{draw}|{run_id}|{source}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _get_payload_for_draw(
    conn: sqlite3.Connection,
    strategy_id: str,
    lottery_type: str,
    draw: str,
) -> dict | None:
    """
    Find historical prediction payload for (strategy, draw) from prediction_items/runs.
    Returns {run_id, numbers_list, item_count, source_type} or None.
    Read-only; does NOT execute strategy logic.
    """
    # Inferred: prediction made when latest_known_draw = draw - 1
    inferred_known = str(int(draw) - 1)

    # 1. Direct run (prediction_runs.strategy_name = strategy_id)
    rows = conn.execute(
        """
        SELECT prun.id, pi.numbers, pi.bet_index
          FROM prediction_runs prun
          JOIN prediction_items pi ON pi.run_id = prun.id
         WHERE prun.strategy_name  = ?
           AND prun.lottery_type   = ?
           AND prun.latest_known_draw = ?
         ORDER BY pi.bet_index
        """,
        (strategy_id, lottery_type, inferred_known),
    ).fetchall()
    if rows:
        numbers_list = []
        for r in rows:
            try:
                nums = json.loads(r[1]) if isinstance(r[1], str) else r[1]
                numbers_list.append(nums)
            except Exception:
                pass
        if numbers_list:
            return {
                "run_id":      rows[0][0],
                "numbers_list": numbers_list,
                "item_count":  len(rows),
                "source_type": "DIRECT_RUN",
            }

    # 2. MULTI_STRATEGY sub-item (prediction_items.strategy_name = strategy_id)
    rows2 = conn.execute(
        """
        SELECT prun.id, pi.numbers, pi.bet_index
          FROM prediction_items pi
          JOIN prediction_runs prun ON pi.run_id = prun.id
         WHERE pi.strategy_name    = ?
           AND prun.lottery_type   = ?
           AND prun.latest_known_draw = ?
         ORDER BY pi.bet_index
        """,
        (strategy_id, lottery_type, inferred_known),
    ).fetchall()
    if rows2:
        numbers_list = []
        for r in rows2:
            try:
                nums = json.loads(r[1]) if isinstance(r[1], str) else r[1]
                numbers_list.append(nums)
            except Exception:
                pass
        if numbers_list:
            return {
                "run_id":      rows2[0][0],
                "numbers_list": numbers_list,
                "item_count":  len(rows2),
                "source_type": "MULTI_STRATEGY",
            }

    return None


def build_plan_row(
    conn: sqlite3.Connection,
    strategy_id: str,
    lottery_type: str,
    draw: str,
    entry,
    existing_replay_draws: set[str],
) -> ReconstructionPlanRow:
    """
    Build one plan row for a (strategy, draw) pair. Read-only.
    Determines planned_action based on available evidence.
    """
    draw_date  = _get_draw_date(conn, draw, lottery_type)
    asrc       = entry.artifact_source_type
    plan_id    = f"P5|{strategy_id}|{draw}"

    # Guard: already covered
    if draw in existing_replay_draws:
        return ReconstructionPlanRow(
            plan_id=plan_id, strategy_id=strategy_id, lottery_type=lottery_type,
            draw_id=draw, draw_date=draw_date,
            catalog_visibility_state="RECONSTRUCTIBLE",
            coverage_status_before="RECONSTRUCTIBLE_PENDING",
            planned_action=PlannedAction.SKIP_ALREADY_COVERED,
            skip_reason="replay row already exists in strategy_prediction_replays",
        )

    # CODE_SCAN: blocked — cannot re-execute strategy logic in P5
    if asrc == "CODE_SCAN":
        return ReconstructionPlanRow(
            plan_id=plan_id, strategy_id=strategy_id, lottery_type=lottery_type,
            draw_id=draw, draw_date=draw_date,
            catalog_visibility_state="RECONSTRUCTIBLE",
            coverage_status_before="RECONSTRUCTIBLE_PENDING",
            planned_action=PlannedAction.NEEDS_P6_POLICY,
            source_paths=entry.source_paths or [],
            artifact_source_type=asrc,
            skip_reason=(
                "Only CODE_SCAN source available; re-executing strategy logic is "
                "prohibited in P5. Requires P6 Source Promotion Policy approval."
            ),
            trust_level=TrustLevel.UNKNOWN,
        )

    # REJECTED_JSON: no per-draw prediction payload
    if asrc == "REJECTED_JSON":
        return ReconstructionPlanRow(
            plan_id=plan_id, strategy_id=strategy_id, lottery_type=lottery_type,
            draw_id=draw, draw_date=draw_date,
            catalog_visibility_state="RECONSTRUCTIBLE",
            coverage_status_before="RECONSTRUCTIBLE_PENDING",
            planned_action=PlannedAction.SKIP_SOURCE_MISSING,
            source_paths=entry.source_paths or [],
            artifact_source_type=asrc,
            skip_reason=(
                "REJECTED_JSON artifact contains strategy config only, "
                "not per-draw historical prediction payload."
            ),
        )

    # PREDICTION_LOG: look for actual payload
    if asrc == "PREDICTION_LOG":
        payload = _get_payload_for_draw(conn, strategy_id, lottery_type, draw)
        if payload is None:
            return ReconstructionPlanRow(
                plan_id=plan_id, strategy_id=strategy_id, lottery_type=lottery_type,
                draw_id=draw, draw_date=draw_date,
                catalog_visibility_state="RECONSTRUCTIBLE",
                coverage_status_before="RECONSTRUCTIBLE_PENDING",
                planned_action=PlannedAction.SKIP_NO_HISTORICAL_PAYLOAD,
                source_paths=entry.source_paths or [],
                artifact_source_type=asrc,
                skip_reason=(
                    f"No prediction_items found for draw {draw} "
                    f"(looked for latest_known_draw={int(draw)-1})."
                ),
                trust_level=TrustLevel.ARTIFACT_DERIVED,
            )

        prov_hash = _make_provenance_hash(
            strategy_id, draw, payload["run_id"], payload["source_type"]
        )
        return ReconstructionPlanRow(
            plan_id=plan_id, strategy_id=strategy_id, lottery_type=lottery_type,
            draw_id=draw, draw_date=draw_date,
            catalog_visibility_state="RECONSTRUCTIBLE",
            coverage_status_before="RECONSTRUCTIBLE_PENDING",
            planned_action=PlannedAction.PLAN_INSERT_REPLAY_ROW,
            source_paths=entry.source_paths or [],
            artifact_source_type=asrc,
            provenance_hash=prov_hash,
            provenance_source=(
                f"DB:prediction_items via prediction_runs.id={payload['run_id']} "
                f"[{payload['source_type']}]"
            ),
            reconstruction_reason=(
                f"Historical prediction payload found in prediction_items "
                f"for strategy_name='{strategy_id}' targeting draw {draw}."
            ),
            trust_level=TrustLevel.ARTIFACT_DERIVED,
            predicted_numbers=payload["numbers_list"],
            item_count=payload["item_count"],
            run_id=payload["run_id"],
        )

    # Fallback
    return ReconstructionPlanRow(
        plan_id=plan_id, strategy_id=strategy_id, lottery_type=lottery_type,
        draw_id=draw, draw_date=draw_date,
        catalog_visibility_state="RECONSTRUCTIBLE",
        coverage_status_before="RECONSTRUCTIBLE_PENDING",
        planned_action=PlannedAction.SKIP_SOURCE_MISSING,
        artifact_source_type=asrc,
        skip_reason=f"Unknown artifact_source_type={asrc!r}; cannot reconstruct.",
    )


def run_reconstruction_plan(
    limit: int = 50,
    lottery_type_filter: str = "DAILY_539",
    db_path: Path = DB_PATH,
    p2_json: Path = P2_JSON,
    p1_json: Path = P1_JSON,
    p4_json: Path = P4_JSON,
) -> dict:
    """Build P5 reconstruction plan. Read-only; does not write DB."""
    catalog_info = load_catalog_with_source_info(
        db_path=db_path, p2_json=p2_json, p1_json=p1_json
    )
    entries     = catalog_info["entries"]
    source_used = catalog_info["source_used"]

    # P2 JSON strips artifact metadata; apply P1 overlay for RECONSTRUCTIBLE
    p1_overlay = _load_p1_metadata_overlay(p1_json)
    for e in entries:
        if e.catalog_visibility_state == "RECONSTRUCTIBLE":
            _apply_p1_overlay(e, p1_overlay)

    recon_entries = [
        e for e in entries
        if e.catalog_visibility_state == "RECONSTRUCTIBLE"
        and (lottery_type_filter is None or e.lottery_type == lottery_type_filter)
    ]

    # Load P4 matrix for target draws
    with open(p4_json) as f:
        p4 = json.load(f)

    pending_cells = [
        r for r in p4["matrix"]
        if r["coverage_status"] == "RECONSTRUCTIBLE_PENDING"
        and (lottery_type_filter is None or r["lottery_type"] == lottery_type_filter)
    ]
    target_draws = sorted(
        set(r["draw"] for r in pending_cells), key=lambda x: int(x)
    )[:limit]

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row_count_before = _db_row_count(conn)

    plan_rows: list[ReconstructionPlanRow] = []
    for entry in recon_entries:
        existing = _get_existing_replay_draws(conn, entry.strategy_id, entry.lottery_type)
        lt_draws = [d for d in target_draws
                    if any(c["draw"] == d and c["lottery_type"] == entry.lottery_type
                           for c in pending_cells)]
        for draw in lt_draws:
            row = build_plan_row(conn, entry.strategy_id, entry.lottery_type, draw, entry, existing)
            # Validate
            errors = validate_plan_row(row)
            if errors:
                row.planned_action = PlannedAction.SKIP_UNSAFE
                row.skip_reason = f"Validation errors: {errors}"
            plan_rows.append(row)

    row_count_after = _db_row_count(conn)
    conn.close()

    assert row_count_before == row_count_after, "DB modified during plan!"

    # Summaries
    action_counts = Counter(r.planned_action for r in plan_rows)
    by_strategy: dict[str, dict] = {}
    for r in plan_rows:
        if r.strategy_id not in by_strategy:
            by_strategy[r.strategy_id] = {"strategy_id": r.strategy_id, "total": 0,
                                           "planned": 0, "skipped": 0, "by_action": {}}
        s = by_strategy[r.strategy_id]
        s["total"] += 1
        s["by_action"][r.planned_action] = s["by_action"].get(r.planned_action, 0) + 1
        if r.planned_action == PlannedAction.PLAN_INSERT_REPLAY_ROW:
            s["planned"] += 1
        else:
            s["skipped"] += 1

    skipped_by_reason = {
        k: v for k, v in action_counts.items()
        if k != PlannedAction.PLAN_INSERT_REPLAY_ROW
    }

    provenance_quality = {
        "with_hash":    sum(1 for r in plan_rows if r.provenance_hash),
        "without_hash": sum(1 for r in plan_rows if not r.provenance_hash),
        "artifact_derived": sum(1 for r in plan_rows if r.trust_level == TrustLevel.ARTIFACT_DERIVED),
        "unknown_trust":    sum(1 for r in plan_rows if r.trust_level == TrustLevel.UNKNOWN),
    }

    return {
        "generated_at":              datetime.utcnow().isoformat() + "Z",
        "phase":                     "P5",
        "mode":                      "DRY_RUN",
        "dry_run":                   True,
        "catalog_source":            source_used,
        "catalog_denominator":       len(entries),
        "reconstructible_strategy_count": len(recon_entries),
        "lottery_type_filter":       lottery_type_filter,
        "draw_count":                len(target_draws),
        "draw_range":                f"{target_draws[0]}-{target_draws[-1]}" if target_draws else "",
        "candidate_cells":           len(plan_rows),
        "rows_to_insert_planned":    action_counts.get(PlannedAction.PLAN_INSERT_REPLAY_ROW, 0),
        "skipped_by_reason":         skipped_by_reason,
        "by_strategy":               by_strategy,
        "provenance_summary":        provenance_quality,
        "safety_flags": {
            "no_apply_option":       True,
            "all_dry_run":           all(r.dry_run_only for r in plan_rows),
            "all_can_apply_false":   all(not r.can_apply() for r in plan_rows),
            "no_db_writes":          True,
            "db_row_count_before":   row_count_before,
            "db_row_count_after":    row_count_after,
            "rows_unchanged":        row_count_before == row_count_after,
        },
        "plan_rows":                 [r.to_dict() for r in plan_rows],
    }


def write_outputs(result: dict, json_out: Path, md_out: Path | None) -> None:
    json_out.parent.mkdir(parents=True, exist_ok=True)
    with open(json_out, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"JSON written to: {json_out}")
    if md_out:
        md_out.parent.mkdir(parents=True, exist_ok=True)
        _write_md(result, md_out)
        print(f"MD written to: {md_out}")


def _write_md(r: dict, path: Path) -> None:
    lines = [
        "# P5 Historical Reconstruction Dry-run Row Plan",
        "",
        f"Generated: {r['generated_at']}",
        f"Lottery type filter: `{r['lottery_type_filter']}`  ",
        f"Draw range: `{r['draw_range']}`  ",
        f"Candidate cells: {r['candidate_cells']}  ",
        f"**rows_to_insert_planned: {r['rows_to_insert_planned']}**  ",
        "",
        "## Plan Action Summary",
        "",
        "| Action | Count |",
        "|--------|-------|",
    ]
    all_actions = {PlannedAction.PLAN_INSERT_REPLAY_ROW: r["rows_to_insert_planned"],
                   **r["skipped_by_reason"]}
    for action, count in sorted(all_actions.items(), key=lambda x: -x[1]):
        lines.append(f"| `{action}` | {count} |")

    lines += [
        "",
        "## Per-Strategy Breakdown",
        "",
        "| Strategy | Total | Planned | Skipped |",
        "|---|---|---|---|",
    ]
    for sid, s in r["by_strategy"].items():
        lines.append(f"| {sid} | {s['total']} | {s['planned']} | {s['skipped']} |")

    lines += [
        "",
        "## Provenance Quality",
        "",
        f"- Rows with provenance_hash: {r['provenance_summary']['with_hash']}",
        f"- Rows without provenance_hash: {r['provenance_summary']['without_hash']}",
        f"- ARTIFACT_DERIVED trust: {r['provenance_summary']['artifact_derived']}",
        f"- UNKNOWN trust: {r['provenance_summary']['unknown_trust']}",
        "",
        "## Safety Flags",
        "",
        f"- no_apply_option: {r['safety_flags']['no_apply_option']}",
        f"- all_dry_run: {r['safety_flags']['all_dry_run']}",
        f"- all_can_apply_false: {r['safety_flags']['all_can_apply_false']}",
        f"- db_rows before/after: {r['safety_flags']['db_row_count_before']} / {r['safety_flags']['db_row_count_after']}",
        f"- rows_unchanged: {r['safety_flags']['rows_unchanged']}",
        "",
        "## Notes",
        "",
        "- `PLAN_INSERT_REPLAY_ROW` = has payload from prediction_items; ready for P7 review",
        "- `NEEDS_P6_POLICY` = CODE_SCAN only; P6 must approve re-execution before P7",
        "- `SKIP_SOURCE_MISSING` = REJECTED_JSON has no per-draw payload",
        "- `SKIP_NO_HISTORICAL_PAYLOAD` = PREDICTION_LOG exists but no entry for this draw",
        "- **No rows were inserted in this plan run.**",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="P5 Historical Reconstruction Plan (read-only, no --apply)")
    parser.add_argument("--limit",    type=int, default=50)
    parser.add_argument("--lottery-type", default="DAILY_539")
    parser.add_argument("--json-out", default=str(OUT_DIR / "p5_historical_reconstruction_plan_20260520.json"))
    parser.add_argument("--md-out",   default=str(DOC_DIR / "p5_historical_reconstruction_plan_20260520.md"))
    parser.add_argument("--no-write", action="store_true")
    args = parser.parse_args()

    print(f"P5 Historical Reconstruction Plan — dry-run only, no --apply...")
    result = run_reconstruction_plan(limit=args.limit, lottery_type_filter=args.lottery_type)

    print(f"  catalog denominator:   {result['catalog_denominator']}")
    print(f"  reconstructible:       {result['reconstructible_strategy_count']}")
    print(f"  candidate cells:       {result['candidate_cells']}")
    print(f"  rows_to_insert:        {result['rows_to_insert_planned']}")
    print(f"  skipped_by_reason:     {result['skipped_by_reason']}")
    print(f"  DB rows unchanged:     {result['safety_flags']['rows_unchanged']}")

    if not args.no_write:
        write_outputs(result, Path(args.json_out), Path(args.md_out) if args.md_out else None)

    if not result["safety_flags"]["rows_unchanged"]:
        print("CRITICAL: DB row count changed!", file=sys.stderr)
        sys.exit(1)
    if not result["safety_flags"]["all_can_apply_false"]:
        print("CRITICAL: some plan rows have can_apply=True!", file=sys.stderr)
        sys.exit(1)

    print("Final classification: P5_RECONSTRUCTION_DRY_RUN_PLAN_PASS")


if __name__ == "__main__":
    main()
