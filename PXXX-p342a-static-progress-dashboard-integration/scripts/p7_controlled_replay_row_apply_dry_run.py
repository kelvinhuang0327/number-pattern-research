#!/usr/bin/env python3
"""
p7_controlled_replay_row_apply_dry_run.py
===========================================
P7 Controlled Replay Row Apply — DRY-RUN ONLY.

Reads P6 approved candidates, performs a duplicate check against the live DB
(read-only), and produces a P7 apply plan. Does NOT write to the DB. Does NOT
generate replay rows. Does NOT expose a --apply flag.

Default scope: ONLINE_ONLY
  - ONLINE candidates → PLAN_INSERT (in dry-run only)
  - RETIRED candidates → PLAN_MANUAL_REVIEW_REQUIRED

Optional scope: INCLUDE_RETIRED_WITH_WARNING
  - RETIRED + lifecycle_warning acknowledged → PLAN_INSERT (still dry-run)

Outputs:
  outputs/replay/p7_controlled_apply_dry_run_20260520.json
  docs/replay/p7_controlled_apply_dry_run_20260520.md
"""

from __future__ import annotations

import argparse
import datetime
import json
import pathlib
import sqlite3
import sys
import uuid

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH   = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P6_JSON   = REPO_ROOT / "outputs" / "replay" / "p6_source_promotion_policy_20260520.json"

sys.path.insert(0, str(REPO_ROOT))

from lottery_api.models.replay_p7_apply_plan_contract import (
    P7ApplyDecision,
    P7ApplyScope,
    P7ApplyPlanRow,
    apply_decision_for_candidate,
    make_duplicate_check_key,
    summarize_p7_plan,
)


# ---------------------------------------------------------------------------
# DB helpers (read-only)
# ---------------------------------------------------------------------------

def _open_db_readonly() -> sqlite3.Connection:
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def _verify_db_row_count(conn: sqlite3.Connection, expected: int = 460) -> int:
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    count = cur.fetchone()[0]
    if count != expected:
        raise RuntimeError(
            f"SAFETY STOP: strategy_prediction_replays row count changed! "
            f"Expected {expected}, got {count}."
        )
    return count


def _check_duplicate(
    conn: sqlite3.Connection,
    strategy_id: str,
    lottery_type: str,
    target_draw: str,
) -> bool:
    """Read-only: True if a row already exists for this (strategy, draw, lottery)."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id=? AND lottery_type=? AND target_draw=?",
        (strategy_id, lottery_type, target_draw),
    )
    return cur.fetchone()[0] > 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="P7 Controlled Replay Row Apply — DRY-RUN ONLY. No --apply."
    )
    parser.add_argument(
        "--scope",
        choices=[
            P7ApplyScope.ONLINE_ONLY,
            P7ApplyScope.INCLUDE_RETIRED_WITH_WARNING,
            P7ApplyScope.MANUAL_REVIEW_ONLY,
        ],
        default=P7ApplyScope.ONLINE_ONLY,
        help=(
            "Candidate scope. Default: ONLINE_ONLY (safest). "
            "INCLUDE_RETIRED_WITH_WARNING adds 93 RETIRED candidates as dry-run PLAN_INSERT. "
            "No scope writes to DB."
        ),
    )
    parser.add_argument(
        "--json-out",
        default=str(REPO_ROOT / "outputs" / "replay" / "p7_controlled_apply_dry_run_20260520.json"),
    )
    parser.add_argument(
        "--md-out",
        default=str(REPO_ROOT / "docs" / "replay" / "p7_controlled_apply_dry_run_20260520.md"),
    )
    parser.add_argument(
        "--p6-json",
        default=str(P6_JSON),
    )
    parser.add_argument(
        "--expected-rows",
        type=int,
        default=460,
    )
    args = parser.parse_args()

    scope = args.scope

    # ── Safety: DB read-only check ───────────────────────────────────────────
    conn = _open_db_readonly()
    try:
        row_count = _verify_db_row_count(conn, expected=args.expected_rows)
    except RuntimeError as e:
        print(f"STOP: {e}")
        sys.exit(1)
    print(f"DB safety check: strategy_prediction_replays = {row_count} rows (unchanged)")

    # ── Load P6 candidates ────────────────────────────────────────────────────
    p6_path = pathlib.Path(args.p6_json)
    if not p6_path.exists():
        print(f"STOP: P6 JSON not found: {p6_path}")
        sys.exit(1)

    p6_data       = json.loads(p6_path.read_text())
    candidates    = p6_data.get("p7_candidate_rows", [])
    total_p6      = p6_data.get("approved_for_p7_candidate", 0)

    print(f"P6 candidates loaded: {len(candidates)} approved candidates")
    print(f"Scope: {scope}")

    # ── Generate batch IDs ────────────────────────────────────────────────────
    rollback_batch_id = str(uuid.uuid4())
    generated_at      = datetime.datetime.utcnow().isoformat() + "Z"

    # ── Build P7 plan rows ────────────────────────────────────────────────────
    plan_rows: list[P7ApplyPlanRow] = []

    for cand in candidates:
        sid          = cand.get("strategy_id", "")
        lottery_type = cand.get("lottery_type", "")
        draw_id      = cand.get("draw_id", "")   # maps to target_draw in DB
        prov_hash    = cand.get("provenance_hash")
        lc_state     = cand.get("lifecycle_state", "")
        lc_warning   = cand.get("lifecycle_warning")
        run_id       = cand.get("run_id")
        source_tier  = cand.get("source_tier", "")

        # Duplicate check (read-only DB query)
        is_dup = _check_duplicate(conn, sid, lottery_type, draw_id)

        # Policy decision
        decision, reason = apply_decision_for_candidate(
            cand,
            scope=scope,
            is_duplicate=is_dup,
        )

        dup_key = make_duplicate_check_key(sid, lottery_type, draw_id)

        plan_rows.append(P7ApplyPlanRow(
            plan_id=str(uuid.uuid4()),
            strategy_id=sid,
            lottery_type=lottery_type,
            draw_id=draw_id,
            draw_date=cand.get("draw_date"),
            predicted_numbers=None,    # not stored in P6 JSON for brevity
            source_run_id=run_id,
            source_prediction_item_id=None,
            provenance_hash=prov_hash,
            source_tier=source_tier,
            lifecycle_state=lc_state,
            lifecycle_warning=lc_warning,
            p7_candidate_status=cand.get("p7_candidate_status", ""),
            apply_decision=decision,
            apply_decision_reason=reason,
            scope_applied=scope,
            dry_run_only=True,
            p7_can_apply=False,
            truth_level="RECONSTRUCTION_DRY_RUN_PLAN",
            created_by_phase="P7",
            created_at=generated_at,
            duplicate_check_key=dup_key,
            is_duplicate=is_dup,
            rollback_batch_id=rollback_batch_id,
            controlled_apply_id=str(uuid.uuid4()),
        ))

    conn.close()

    # ── Safety invariants ─────────────────────────────────────────────────────
    for r in plan_rows:
        if r.p7_can_apply:
            raise RuntimeError(
                f"SAFETY STOP: p7_can_apply=True for {r.strategy_id}/{r.draw_id}"
            )
        if not r.dry_run_only:
            raise RuntimeError(
                f"SAFETY STOP: dry_run_only=False for {r.strategy_id}/{r.draw_id}"
            )

    # ── Summarize ─────────────────────────────────────────────────────────────
    summary = summarize_p7_plan(
        plan_rows,
        rollback_batch_id=rollback_batch_id,
        scope=scope,
    )

    # ── Build full output ──────────────────────────────────────────────────────
    output = {
        "phase":                      "P7",
        "generated_at":               generated_at,
        "scope":                      scope,
        "rollback_batch_id":          rollback_batch_id,
        "dry_run_only":               True,
        "p7_can_apply":               False,
        "db_row_count_verified":      row_count,
        "p6_source":                  str(p6_path),
        "total_p6_candidates":        len(candidates),
        "plan_insert_count":          summary["plan_insert_count"],
        "manual_review_required_count": summary["manual_review_required_count"],
        "duplicate_skip_count":       summary["duplicate_skip_count"],
        "invalid_candidate_count":    summary["invalid_candidate_count"],
        "online_candidates":          summary["online_candidates"],
        "retired_warning_candidates": summary["retired_warning_candidates"],
        "by_strategy":                summary["by_strategy"],
        "by_lifecycle_state":         summary["by_lifecycle_state"],
        "by_apply_decision":          summary["by_apply_decision"],
        "backup_plan":                summary["backup_plan"],
        "rollback_plan":              summary["rollback_plan"],
        "safety_flags":               summary["safety_flags"],
        "p7_insert_rows":             summary["p7_insert_rows"],
        "all_plan_rows":              [r.to_dict() for r in plan_rows],
    }

    # ── Write outputs ─────────────────────────────────────────────────────────
    json_path = pathlib.Path(args.json_out)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    md_path = pathlib.Path(args.md_out)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    _write_md(output, md_path)

    # ── Print summary ──────────────────────────────────────────────────────────
    print(f"\n=== P7 Dry-run Plan ({scope}) ===")
    print(f"Total P6 candidates:     {len(candidates)}")
    print(f"PLAN_INSERT:             {summary['plan_insert_count']}")
    print(f"MANUAL_REVIEW_REQUIRED:  {summary['manual_review_required_count']}")
    print(f"PLAN_SKIP_DUPLICATE:     {summary['duplicate_skip_count']}")
    print(f"Other skip:              {summary['invalid_candidate_count']}")
    print(f"Rollback batch ID:       {rollback_batch_id}")
    print(f"\nJSON:  {json_path}")
    print(f"MD:    {md_path}")


def _write_md(output: dict, path: pathlib.Path) -> None:
    scope  = output["scope"]
    lines  = [
        f"# P7 Controlled Replay Row Apply — Dry-run Report",
        f"**Date**: {output['generated_at'][:10]}  ",
        f"**Scope**: `{scope}`  ",
        f"**Rollback Batch ID**: `{output['rollback_batch_id']}`  ",
        f"**p7_can_apply**: `False` (dry-run only)  ",
        "",
        "## Summary",
        "",
        f"| Metric | Count |",
        f"|--------|-------|",
        f"| Total P6 candidates | {output['total_p6_candidates']} |",
        f"| ONLINE candidates | {output['online_candidates']} |",
        f"| RETIRED candidates (with lifecycle warning) | {output['retired_warning_candidates']} |",
        f"| **PLAN_INSERT** | **{output['plan_insert_count']}** |",
        f"| PLAN_MANUAL_REVIEW_REQUIRED | {output['manual_review_required_count']} |",
        f"| PLAN_SKIP_DUPLICATE | {output['duplicate_skip_count']} |",
        f"| Other skip | {output['invalid_candidate_count']} |",
        f"| DB rows verified (unchanged) | {output['db_row_count_verified']} |",
        "",
        "## By Strategy",
        "",
        "| Strategy | Lifecycle | PLAN_INSERT | Manual Review | Skip | Total |",
        "|----------|-----------|-------------|---------------|------|-------|",
    ]
    for sid, s in output["by_strategy"].items():
        lines.append(
            f"| {sid} | {s['lifecycle']} | {s['plan_insert']} | "
            f"{s['manual_review']} | {s['skip']} | {s['total']} |"
        )

    bp = output["backup_plan"]
    rp = output["rollback_plan"]
    lines += [
        "",
        "## Backup Plan",
        "",
        f"> {bp['description']}",
        "",
        f"- Snapshot target: `{bp['snapshot_target']}`",
        f"- Backup path: `{bp['backup_path']}`",
        f"- Verified row count before apply: {bp['verified_row_count_before']}",
        f"- Rollback command: `{bp['rollback_command']}`",
        "",
        "## Rollback Plan",
        "",
        f"> {rp['description']}",
        "",
        f"- Rollback batch ID: `{rp['rollback_batch_id']}`",
        f"- Idempotency check: `{rp['idempotency_check']}`",
        "",
        "## Safety Flags",
        "",
        "| Flag | Value |",
        "|------|-------|",
    ]
    for k, v in output["safety_flags"].items():
        lines.append(f"| `{k}` | `{v}` |")

    lines += [
        "",
        "## CEO Authorization Gate",
        "",
        "> P7 actual apply is **NOT** triggered by this script.",
        ">",
        f"> This report covers scope `{scope}`.",
        f"> {output['plan_insert_count']} rows are staged for dry-run insert.",
        "> RETIRED lifecycle warnings must be reviewed before any actual apply.",
        "",
        "若授權實際執行 P7 controlled apply，請回覆：",
        "",
        "> `YES apply P7 controlled replay rows`",
    ]

    path.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
