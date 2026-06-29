#!/usr/bin/env python3
"""
p6_source_promotion_policy.py
================================
P6 Source Promotion Policy Planner — READ-ONLY.

Reads the P5 historical reconstruction plan, applies the P6 source
promotion policy to each plan cell, and produces a P7 candidate list.

Constraints:
  - No DB write
  - No --apply flag
  - No replay row generation
  - No lifecycle_state mutation
  - ARTIFACT_CANDIDATE never becomes P7 candidate
  - p5_can_apply remains False — P6 never flips it

Outputs:
  outputs/replay/p6_source_promotion_policy_20260520.json
  docs/replay/p6_source_promotion_policy_20260520.md
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys

REPO_ROOT  = pathlib.Path(__file__).resolve().parent.parent
DB_PATH    = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P5_PLAN    = REPO_ROOT / "outputs" / "replay" / "p5_historical_reconstruction_plan_20260520.json"
P5_INV     = REPO_ROOT / "outputs" / "replay" / "p5_reconstruction_input_inventory_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_source_promotion_policy import (
    evaluate_promotion_policy,
    summarize_promotion_results,
    SourcePromotionDecision,
    P7CandidateStatus,
)

from pathlib import Path


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))



# ---------------------------------------------------------------------------
# Safety: no DB write allowed
# ---------------------------------------------------------------------------

def _open_db_readonly() -> sqlite3.Connection:
    _p291u_db_path = _p291u_resolve_db_path()
    return _p291u_connect_resolved(_p291u_db_path, uri=True)


def _verify_db_unchanged(conn: sqlite3.Connection, expected: int = 460) -> int:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    if count != expected:
        raise RuntimeError(
            f"SAFETY STOP: strategy_prediction_replays row count changed! "
            f"Expected {expected}, got {count}. Aborting P6."
        )
    return count


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P6 Source Promotion Policy — READ-ONLY, no --apply"
    )
    parser.add_argument(
        "--json-out",
        default=str(REPO_ROOT / "outputs" / "replay" / "p6_source_promotion_policy_20260520.json"),
    )
    parser.add_argument(
        "--md-out",
        default=str(REPO_ROOT / "docs" / "replay" / "p6_source_promotion_policy_20260520.md"),
    )
    parser.add_argument(
        "--p5-plan",
        default=str(P5_PLAN),
        help="Path to P5 historical reconstruction plan JSON",
    )
    parser.add_argument(
        "--expected-rows",
        type=int,
        default=460,
        help="Expected strategy_prediction_replays row count (safety check)",
    )
    args = parser.parse_args()

    # ── Safety: verify DB unchanged ──────────────────────────────────────────
    conn = _open_db_readonly()
    try:
        row_count = _verify_db_unchanged(conn, expected=args.expected_rows)
    finally:
        conn.close()
    print(f"DB safety check: strategy_prediction_replays = {row_count} rows (unchanged)")

    # ── Load P5 plan ─────────────────────────────────────────────────────────
    p5_path = pathlib.Path(args.p5_plan)
    if not p5_path.exists():
        print(f"ERROR: P5 plan not found: {p5_path}")
        print("Run scripts/p5_historical_reconstruction_plan.py first.")
        sys.exit(1)

    p5_data   = json.loads(p5_path.read_text())
    plan_cells = p5_data.get("plan_cells", [])
    print(f"P5 plan loaded: {len(plan_cells)} cells "
          f"({p5_data.get('plan_insert_rows', '?')} PLAN_INSERT, "
          f"{p5_data.get('skipped_rows', '?')} SKIP)")

    # ── Apply P6 policy to every cell ────────────────────────────────────────
    results = [evaluate_promotion_policy(cell) for cell in plan_cells]

    # ── Summarize ─────────────────────────────────────────────────────────────
    summary = summarize_promotion_results(results)

    # ── Safety invariants ─────────────────────────────────────────────────────
    for r in results:
        if r.p6_can_apply:
            raise RuntimeError(
                f"SAFETY STOP: P6 set p6_can_apply=True for "
                f"{r.strategy_id}/{r.draw_id} — invariant violation"
            )
        if r.p5_can_apply:
            print(f"WARNING: p5_can_apply=True seen for {r.strategy_id}/{r.draw_id} "
                  f"(invariant violation in P5 — flagged as MANUAL_REVIEW)")

    # ── Build full output ─────────────────────────────────────────────────────
    generated_at = datetime.datetime.utcnow().isoformat() + "Z"

    output = {
        "phase":                      "P6",
        "generated_at":               generated_at,
        "p5_source":                  str(p5_path),
        "dry_run_only":               True,
        "db_row_count_verified":      row_count,
        "p5_total_plan_rows":         len(plan_cells),
        "p5_plan_insert_rows":        p5_data.get("plan_insert_rows", 0),
        "p5_skipped_rows":            p5_data.get("skipped_rows", 0),
        "total_plan_rows":            summary["total_plan_rows"],
        "plan_insert_rows":           summary["plan_insert_rows"],
        "approved_for_p7_candidate":  summary["approved_for_p7_candidate"],
        "rejected_count":             summary["rejected_count"],
        "manual_review_required":     summary["manual_review_required"],
        "rejected_by_reason":         summary["rejected_by_reason"],
        "by_strategy":                summary["by_strategy"],
        "by_lifecycle_state":         summary["by_lifecycle_state"],
        "by_source_tier":             summary["by_source_tier"],
        "lifecycle_warnings":         summary["lifecycle_warnings"],
        "p7_candidate_rows":          summary["p7_candidate_rows"],
        "all_results":                [r.to_dict() for r in results],
    }

    # ── Write JSON output ──────────────────────────────────────────────────────
    json_path = pathlib.Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    # ── Write MD report ───────────────────────────────────────────────────────
    md_path = pathlib.Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    _write_md_report(output, md_path)

    # ── Print summary ──────────────────────────────────────────────────────────
    print(f"\n=== P6 Source Promotion Policy Results ===")
    print(f"Total plan rows:         {output['total_plan_rows']}")
    print(f"PLAN_INSERT rows:        {output['plan_insert_rows']}")
    print(f"Approved for P7:         {output['approved_for_p7_candidate']}")
    print(f"Rejected:                {output['rejected_count']}")
    print(f"Manual review required:  {output['manual_review_required']}")
    print()
    print("By strategy:")
    for sid, s in output["by_strategy"].items():
        print(f"  {sid}: approved={s['approved_for_p7']} "
              f"rejected={s['rejected']} lc={s['lifecycle_state']}")
    print()
    print(f"JSON written to:  {json_path}")
    print(f"MD written to:    {md_path}")

    if output["approved_for_p7_candidate"] == 0:
        print("\nWARNING: 0 candidates approved for P7. Check rejection reasons.")

    lifecycle_warnings = output.get("lifecycle_warnings", [])
    if lifecycle_warnings:
        print(f"\nLifecycle warnings ({len(lifecycle_warnings)} rows with non-ONLINE lifecycle):")
        warned_strats = set(w["strategy_id"] for w in lifecycle_warnings)
        for sid in warned_strats:
            lc = next(w["lifecycle_state"] for w in lifecycle_warnings if w["strategy_id"] == sid)
            cnt = sum(1 for w in lifecycle_warnings if w["strategy_id"] == sid)
            print(f"  {sid} ({lc}): {cnt} rows — human review required before P7")


def _write_md_report(output: dict, path: pathlib.Path) -> None:
    lines = [
        "# P6 Source Promotion Policy Report",
        f"**Date**: {output['generated_at'][:10]}  ",
        f"**Phase**: P6 (read-only, no DB write)  ",
        f"**P5 Source**: `{pathlib.Path(output['p5_source']).name}`  ",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total plan rows | {output['total_plan_rows']} |",
        f"| PLAN_INSERT_REPLAY_ROW | {output['plan_insert_rows']} |",
        f"| Approved for P7 candidate | **{output['approved_for_p7_candidate']}** |",
        f"| Rejected (NOT_P7_CANDIDATE) | {output['rejected_count']} |",
        f"| Manual review required | {output['manual_review_required']} |",
        f"| DB rows verified (unchanged) | {output['db_row_count_verified']} |",
        "",
        "## By Strategy",
        "",
        "| Strategy | Lifecycle | Approved | Rejected | Manual | Total |",
        "|----------|-----------|----------|----------|--------|-------|",
    ]
    for sid, s in output["by_strategy"].items():
        lines.append(
            f"| {sid} | {s['lifecycle_state']} | "
            f"{s['approved_for_p7']} | {s['rejected']} | "
            f"{s['manual_review_required']} | {s['total_plan_cells']} |"
        )

    lines += [
        "",
        "## Rejection Reasons",
        "",
    ]
    for reason, cnt in output["rejected_by_reason"].items():
        lines.append(f"- `{reason}`: {cnt}")

    lc_warnings = output.get("lifecycle_warnings", [])
    if lc_warnings:
        warned = set(w["strategy_id"] for w in lc_warnings)
        lines += [
            "",
            "## Lifecycle Warnings",
            "",
            f"{len(lc_warnings)} candidate rows involve non-ONLINE strategies. "
            "These require human review before P7 apply.",
            "",
        ]
        for sid in sorted(warned):
            lc  = next(w["lifecycle_state"] for w in lc_warnings if w["strategy_id"] == sid)
            cnt = sum(1 for w in lc_warnings if w["strategy_id"] == sid)
            lines.append(f"- `{sid}` ({lc}): {cnt} rows")

    lines += [
        "",
        "## Safety Confirmation",
        "",
        f"- `strategy_prediction_replays` rows: **{output['db_row_count_verified']}** (verified unchanged)",
        "- No DB write performed",
        "- No replay rows generated",
        "- No lifecycle_state mutations",
        "- All results have `p6_can_apply = False`",
        "",
        "## P7 Authorization Gate",
        "",
        "P7 controlled replay row apply is **NOT** triggered by this script.",
        "",
        "To authorize P7 dry-run preparation, a human operator must respond:",
        "",
        "> `YES prepare P7 dry-run`",
        "",
        "P7 prerequisites:",
        "- [ ] P6 committed and verified",
        "- [ ] UI visibility recovery committed (`a89a7ca`)",
        "- [ ] Drift guard PASS",
        "- [ ] DB rows unchanged (460)",
        "- [ ] Lifecycle warnings reviewed by human",
        "- [ ] Backup/rollback design complete",
    ]

    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
