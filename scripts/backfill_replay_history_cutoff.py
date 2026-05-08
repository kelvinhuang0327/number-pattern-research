#!/usr/bin/env python3
"""
P0-2 Contingency backfill tool for strategy_prediction_replays.history_cutoff_draw.

Default mode is --dry-run (no DB writes). Use --apply only with explicit
--confirm-cutoff-backfill confirmation.

Safe Backfill Rules enforced (roadmap §4):
1) Backfill only when target_draw is parseable
2) Backfill only when draw sequence is available and ordered
3) New cutoff is immediately previous draw in sequence
4) New cutoff < target_draw
5) Never use target_draw itself
6) Never use later draw
7) If previous draw undeterminable: keep NULL and record reason
8) If ordering not trusted: keep NULL and record reason
9) Dry-run writes nothing
10) Apply never mutates predicted/actual/hit/status/run-status fields
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).parent.parent
DEFAULT_DB = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUT_DIR = PROJECT_ROOT / "outputs" / "replay"

CONFIRM_TOKEN = "CONFIRM_CUTOFF_BACKFILL"
ALLOWED_LOTTERIES = {"ALL", "BIG_LOTTO", "POWER_LOTTO", "DAILY_539", "3_STAR"}


@dataclass
class DrawIndex:
    trusted_order: bool
    reason: str | None
    prev_map: dict[int, int | None]


def _connect(db_path: Path, read_only: bool) -> sqlite3.Connection:
    if read_only:
        uri = f"file:{db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True)
    else:
        conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def _build_draw_index(conn: sqlite3.Connection, lottery_type: str) -> DrawIndex:
    rows = conn.execute(
        """
        SELECT draw
        FROM draws
        WHERE lottery_type = ?
        """,
        (lottery_type,),
    ).fetchall()

    if not rows:
        return DrawIndex(False, "draw_sequence_unavailable", {})

    parsed: list[int] = []
    for r in rows:
        raw = str(r["draw"]).strip()
        try:
            parsed.append(int(raw))
        except ValueError:
            return DrawIndex(False, f"draw_not_parseable:{raw}", {})

    unique = sorted(set(parsed))
    if len(unique) != len(parsed):
        return DrawIndex(False, "draw_sequence_has_duplicates", {})

    prev_map: dict[int, int | None] = {}
    for idx, cur in enumerate(unique):
        prev_map[cur] = unique[idx - 1] if idx > 0 else None

    return DrawIndex(True, None, prev_map)


def _collect_missing_rows(
    conn: sqlite3.Connection,
    lottery: str,
    run_id: int | None,
) -> list[sqlite3.Row]:
    where = ["(r.history_cutoff_draw IS NULL OR TRIM(CAST(r.history_cutoff_draw AS TEXT)) = '')"]
    params: list[Any] = []

    if lottery != "ALL":
        where.append("r.lottery_type = ?")
        params.append(lottery)
    if run_id is not None:
        where.append("r.replay_run_id = ?")
        params.append(run_id)

    q = f"""
        SELECT
            r.id,
            r.lottery_type,
            r.target_draw,
            r.replay_status,
            r.replay_run_id,
            COALESCE(run.status, '') AS run_status,
            COALESCE(run.notes, '') AS run_notes,
            r.predicted_numbers,
            r.actual_numbers,
            r.hit_numbers,
            r.hit_count,
            r.predicted_special,
            r.actual_special,
            r.special_hit
        FROM strategy_prediction_replays r
        LEFT JOIN strategy_replay_runs run
            ON run.id = r.replay_run_id
        WHERE {' AND '.join(where)}
        ORDER BY r.id
    """
    return conn.execute(q, params).fetchall()


def _collect_causal_violations(conn: sqlite3.Connection, lottery: str, run_id: int | None) -> list[sqlite3.Row]:
    where = [
        "r.history_cutoff_draw IS NOT NULL",
        "TRIM(CAST(r.history_cutoff_draw AS TEXT)) != ''",
        "CAST(r.history_cutoff_draw AS INTEGER) >= CAST(r.target_draw AS INTEGER)",
    ]
    params: list[Any] = []
    if lottery != "ALL":
        where.append("r.lottery_type = ?")
        params.append(lottery)
    if run_id is not None:
        where.append("r.replay_run_id = ?")
        params.append(run_id)

    q = f"""
        SELECT id, lottery_type, target_draw, history_cutoff_draw, replay_status, replay_run_id
        FROM strategy_prediction_replays r
        WHERE {' AND '.join(where)}
        ORDER BY id
    """
    return conn.execute(q, params).fetchall()


def run_audit(
    db_path: Path,
    lottery: str,
    run_id: int | None,
    apply: bool,
) -> dict[str, Any]:
    read_only = not apply
    conn = _connect(db_path, read_only=read_only)
    try:
        missing_rows = _collect_missing_rows(conn, lottery, run_id)

        draw_indexes: dict[str, DrawIndex] = {}
        evaluations: list[dict[str, Any]] = []
        backfillable: list[dict[str, Any]] = []

        for row in missing_rows:
            row_d = dict(row)
            lt = row_d["lottery_type"]

            # FAILED_LEGACY + notes rows are exempt from mandatory cutoff rule.
            if row_d["run_status"] == "FAILED_LEGACY" and str(row_d["run_notes"]).strip() != "":
                evaluations.append(
                    {
                        "id": row_d["id"],
                        "lottery_type": lt,
                        "target_draw": row_d["target_draw"],
                        "replay_run_id": row_d["replay_run_id"],
                        "decision": "exempt_failed_legacy_with_notes",
                        "reason": "failed_legacy_with_notes",
                        "new_cutoff": None,
                    }
                )
                continue

            if lt not in draw_indexes:
                draw_indexes[lt] = _build_draw_index(conn, lt)
            idx = draw_indexes[lt]

            target_raw = str(row_d["target_draw"]).strip()
            try:
                target = int(target_raw)
            except ValueError:
                evaluations.append(
                    {
                        "id": row_d["id"],
                        "lottery_type": lt,
                        "target_draw": row_d["target_draw"],
                        "replay_run_id": row_d["replay_run_id"],
                        "decision": "not_backfillable",
                        "reason": "target_draw_not_parseable",
                        "new_cutoff": None,
                    }
                )
                continue

            if not idx.trusted_order:
                evaluations.append(
                    {
                        "id": row_d["id"],
                        "lottery_type": lt,
                        "target_draw": row_d["target_draw"],
                        "replay_run_id": row_d["replay_run_id"],
                        "decision": "not_backfillable",
                        "reason": idx.reason,
                        "new_cutoff": None,
                    }
                )
                continue

            if target not in idx.prev_map:
                evaluations.append(
                    {
                        "id": row_d["id"],
                        "lottery_type": lt,
                        "target_draw": row_d["target_draw"],
                        "replay_run_id": row_d["replay_run_id"],
                        "decision": "not_backfillable",
                        "reason": "target_draw_not_in_sequence",
                        "new_cutoff": None,
                    }
                )
                continue

            prev_draw = idx.prev_map[target]
            if prev_draw is None:
                evaluations.append(
                    {
                        "id": row_d["id"],
                        "lottery_type": lt,
                        "target_draw": row_d["target_draw"],
                        "replay_run_id": row_d["replay_run_id"],
                        "decision": "not_backfillable",
                        "reason": "previous_draw_undeterminable",
                        "new_cutoff": None,
                    }
                )
                continue

            if prev_draw >= target:
                evaluations.append(
                    {
                        "id": row_d["id"],
                        "lottery_type": lt,
                        "target_draw": row_d["target_draw"],
                        "replay_run_id": row_d["replay_run_id"],
                        "decision": "not_backfillable",
                        "reason": "unsafe_previous_draw_not_before_target",
                        "new_cutoff": None,
                    }
                )
                continue

            candidate = {
                "id": row_d["id"],
                "lottery_type": lt,
                "target_draw": row_d["target_draw"],
                "replay_run_id": row_d["replay_run_id"],
                "decision": "backfillable",
                "reason": "safe_immediate_previous_draw",
                "new_cutoff": str(prev_draw),
            }
            evaluations.append(candidate)
            backfillable.append(candidate)

        before_missing = len(missing_rows)
        backfilled_count = 0

        protected_mismatch: list[int] = []
        if apply and backfillable:
            protected_before: dict[int, tuple[Any, ...]] = {}
            for r in missing_rows:
                protected_before[r["id"]] = (
                    r["predicted_numbers"],
                    r["actual_numbers"],
                    r["hit_numbers"],
                    r["hit_count"],
                    r["predicted_special"],
                    r["actual_special"],
                    r["special_hit"],
                    r["replay_status"],
                    r["run_status"],
                )

            conn.execute("BEGIN")
            for c in backfillable:
                conn.execute(
                    """
                    UPDATE strategy_prediction_replays
                    SET history_cutoff_draw = ?
                    WHERE id = ?
                      AND (history_cutoff_draw IS NULL OR TRIM(CAST(history_cutoff_draw AS TEXT)) = '')
                    """,
                    (c["new_cutoff"], c["id"]),
                )

            backfilled_count = len(backfillable)

            for c in backfillable:
                post = conn.execute(
                    """
                    SELECT
                        r.predicted_numbers,
                        r.actual_numbers,
                        r.hit_numbers,
                        r.hit_count,
                        r.predicted_special,
                        r.actual_special,
                        r.special_hit,
                        r.replay_status,
                        COALESCE(run.status, '') AS run_status
                    FROM strategy_prediction_replays r
                    LEFT JOIN strategy_replay_runs run
                        ON run.id = r.replay_run_id
                    WHERE r.id = ?
                    """,
                    (c["id"],),
                ).fetchone()
                if post is None:
                    protected_mismatch.append(c["id"])
                    continue

                after_tuple = (
                    post["predicted_numbers"],
                    post["actual_numbers"],
                    post["hit_numbers"],
                    post["hit_count"],
                    post["predicted_special"],
                    post["actual_special"],
                    post["special_hit"],
                    post["replay_status"],
                    post["run_status"],
                )
                if after_tuple != protected_before[c["id"]]:
                    protected_mismatch.append(c["id"])

            if protected_mismatch:
                conn.rollback()
                raise RuntimeError(
                    "Protected field mutation detected during apply on row IDs: "
                    + ", ".join(map(str, protected_mismatch))
                )

            conn.commit()

        after_missing = conn.execute(
            """
            SELECT COUNT(*)
            FROM strategy_prediction_replays r
            WHERE (r.history_cutoff_draw IS NULL OR TRIM(CAST(r.history_cutoff_draw AS TEXT)) = '')
            """
        ).fetchone()[0]

        violations = _collect_causal_violations(conn, lottery, run_id)

    finally:
        conn.close()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if apply else "dry-run",
        "db_path": str(db_path),
        "filters": {
            "lottery": lottery,
            "run_id": run_id,
        },
        "safe_backfill_rules_version": "roadmap_20260508_section4",
        "missing_before": before_missing,
        "backfillable_count": len(backfillable),
        "backfilled_count": backfilled_count,
        "missing_after": after_missing,
        "causal_violation_count": len(violations),
        "violations": [dict(v) for v in violations],
        "evaluation_rows": evaluations,
        "protected_field_mismatch_row_ids": protected_mismatch,
    }
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    lines = []
    lines.append("# Replay History Cutoff Audit")
    lines.append("")
    lines.append(f"- Generated at: {report['generated_at']}")
    lines.append(f"- Mode: {report['mode']}")
    lines.append(f"- DB: {report['db_path']}")
    lines.append(f"- Filter lottery: {report['filters']['lottery']}")
    lines.append(f"- Filter run_id: {report['filters']['run_id']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- missing_before: {report['missing_before']}")
    lines.append(f"- backfillable_count: {report['backfillable_count']}")
    lines.append(f"- backfilled_count: {report['backfilled_count']}")
    lines.append(f"- missing_after: {report['missing_after']}")
    lines.append(f"- causal_violation_count: {report['causal_violation_count']}")
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Artifact only: this report is not API/UI source-of-truth.")
    lines.append("- Replay DB remains source-of-truth.")
    lines.append("- Dry-run mode writes nothing.")

    if report["violations"]:
        lines.append("")
        lines.append("## Causal Violations")
        lines.append("")
        for v in report["violations"][:50]:
            lines.append(
                f"- row_id={v['id']} lottery={v['lottery_type']} target={v['target_draw']} cutoff={v['history_cutoff_draw']} status={v['replay_status']} run_id={v['replay_run_id']}"
            )

    return "\n".join(lines) + "\n"


def _default_outputs(date_tag: str) -> tuple[Path, Path]:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUT_DIR / f"replay_history_cutoff_audit_{date_tag}.json"
    md_path = OUT_DIR / f"replay_history_cutoff_audit_{date_tag}.md"
    return json_path, md_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Replay history_cutoff backfill audit tool")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to lottery_v2.db")
    parser.add_argument("--lottery", default="ALL", help="Lottery filter: ALL/BIG_LOTTO/POWER_LOTTO/DAILY_539/3_STAR")
    parser.add_argument("--run-id", type=int, default=None, help="Optional replay_run_id filter")

    parser.add_argument("--dry-run", action="store_true", help="Dry-run mode (default behavior)")
    parser.add_argument("--apply", action="store_true", help="Apply backfill updates")
    parser.add_argument(
        "--confirm-cutoff-backfill",
        default=None,
        help=f"Required with --apply. Must equal '{CONFIRM_TOKEN}'.",
    )

    parser.add_argument("--date-tag", default=datetime.now().strftime("%Y%m%d"), help="Date tag for default report names")
    parser.add_argument("--output-json", default=None, help="Output JSON path")
    parser.add_argument("--output-md", default=None, help="Output markdown path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    lottery = str(args.lottery).upper().strip()
    if lottery not in ALLOWED_LOTTERIES:
        raise SystemExit(f"Unsupported --lottery value: {lottery}")

    apply_mode = bool(args.apply)
    if apply_mode:
        if args.confirm_cutoff_backfill != CONFIRM_TOKEN:
            raise SystemExit(
                "--apply requires --confirm-cutoff-backfill "
                f"{CONFIRM_TOKEN}"
            )

    db_path = Path(args.db)
    report = run_audit(
        db_path=db_path,
        lottery=lottery,
        run_id=args.run_id,
        apply=apply_mode,
    )

    default_json, default_md = _default_outputs(args.date_tag)
    out_json = Path(args.output_json) if args.output_json else default_json
    out_md = Path(args.output_md) if args.output_md else default_md

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_md.parent.mkdir(parents=True, exist_ok=True)

    out_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out_md.write_text(_render_markdown(report), encoding="utf-8")

    print(f"[cutoff-audit] mode={report['mode']}")
    print(f"[cutoff-audit] missing_before={report['missing_before']}")
    print(f"[cutoff-audit] backfillable_count={report['backfillable_count']}")
    print(f"[cutoff-audit] backfilled_count={report['backfilled_count']}")
    print(f"[cutoff-audit] missing_after={report['missing_after']}")
    print(f"[cutoff-audit] causal_violation_count={report['causal_violation_count']}")
    print(f"[cutoff-audit] json={out_json}")
    print(f"[cutoff-audit] md={out_md}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
