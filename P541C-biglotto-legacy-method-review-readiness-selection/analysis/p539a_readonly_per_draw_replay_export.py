"""P539A — Read-only per-draw replay export for stable/combination candidate draw-range cutoffs.

Restricted to the strategy_ids/combo_ids already present in the committed P537A
artifact's stable_candidates_for_owner_review and combination_candidates_for_followup
groups (cross_lottery and insufficient_context groups are excluded, matching P538A's
own recommended_next_single_worker_task, which found them not traceable to a single
walk-forward-able series without a further upstream task).

For each candidate, recovers earliest_target_draw/latest_target_draw by joining to the
committed P536C artifact (by lottery_type/strategy_id/window/pick_k for stable
candidates, by lottery_type/combo_id/window for combination candidates), then opens
lottery_api/data/lottery_v2.db read-only (sqlite3 URI mode=ro + PRAGMA query_only=ON)
to check whether any target_draw rows exist strictly after each candidate's recovered
cutoff -- i.e. whether new draws now exist to support even a first out-of-sample window.

This module does not compute rolling/out-of-sample scores, does not rank or promote
any strategy, and does not recompute anything already present in P536C/P537A/P536K.
It only exports (a) a candidate index carrying the recovered draw-range cutoffs and
(b) any genuinely new per-draw source rows found beyond those cutoffs, plus a small
number of illustrative already-replayed rows to document the per-draw row schema.

Historical replay source export only; not a prediction, betting edge, future-winning,
or production-readiness claim.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from analysis.p333_strategy_pick_combination_scoreboard import _open_ro  # noqa: E402

TASK_ID = "P539A"
DERIVED_FROM_TASK_ID = "P538A"
UPSTREAM_TASK_IDS = ("P537A", "P536K", "P536C", "P333")

DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"

DEFAULT_P537A_PATH = OUTPUT_DIR / "p537a_shortlist_robustness_review_20260709.json"
DEFAULT_P536K_PATH = OUTPUT_DIR / "p536k_lift_candidate_shortlist_20260708.json"
DEFAULT_P536C_PATH = OUTPUT_DIR / "p536c_success_matrix_lift_extension_20260708.json"
DEFAULT_P538A_PATH = OUTPUT_DIR / "p538a_strategy_candidate_evaluation_readiness_20260709.json"

DISCLAIMER_EN = (
    "Historical replay source export only; not a prediction, betting edge, "
    "future-winning, or production-readiness claim."
)

SOURCE_ROW_FIELDS = (
    "id", "lottery_type", "target_draw", "target_date", "strategy_id", "bet_index",
    "predicted_numbers", "predicted_special", "actual_numbers", "actual_special",
    "hit_count", "special_hit",
)

_NEW_ROWS_QUERY = f"""
    SELECT {", ".join(SOURCE_ROW_FIELDS)}
    FROM strategy_prediction_replays
    WHERE lottery_type = ? AND strategy_id = ?
      AND replay_status = 'PREDICTED'
      AND dry_run = 0
      AND predicted_numbers IS NOT NULL
      AND actual_numbers IS NOT NULL
      AND CAST(target_draw AS INTEGER) > ?
    ORDER BY CAST(target_draw AS INTEGER) DESC, bet_index
"""

_LATEST_EXISTING_ROW_QUERY = f"""
    SELECT {", ".join(SOURCE_ROW_FIELDS)}
    FROM strategy_prediction_replays
    WHERE lottery_type = ? AND strategy_id = ?
      AND replay_status = 'PREDICTED'
      AND dry_run = 0
      AND predicted_numbers IS NOT NULL
      AND actual_numbers IS NOT NULL
    ORDER BY CAST(target_draw AS INTEGER) DESC, bet_index
    LIMIT 1
"""


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _file_sha256(path: Path | str) -> str:
    hasher = hashlib.sha256()
    hasher.update(Path(path).read_bytes())
    return hasher.hexdigest()


def _parse_combo_id(combo_id: str) -> list[tuple[str, int]]:
    members: list[tuple[str, int]] = []
    for part in combo_id.split(" + "):
        sid, quota = part.rsplit(":", 1)
        members.append((sid, int(quota)))
    return members


def _index_matrix_by_strategy_window(p536c: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, Any]]:
    index: dict[tuple[str, str, int], dict[str, Any]] = {}
    for rec in p536c["strategy_pick_matrix_lift_extension"]:
        key = (rec["lottery_type"], rec["strategy_id"], int(rec["window"]))
        index.setdefault(key, rec)
    return index


def _index_leaderboard_by_combo_window(p536c: dict[str, Any]) -> dict[tuple[str, str, int], dict[str, Any]]:
    index: dict[tuple[str, str, int], dict[str, Any]] = {}
    for rec in p536c["combination_leaderboard_with_lift"]:
        key = (rec["lottery_type"], rec["combo_id"], int(rec["window"]))
        index.setdefault(key, rec)
    return index


def build_candidate_index(
    p537a: dict[str, Any], p536c: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[tuple[str, str], int], dict[tuple[str, str], int]]:
    """Returns (candidate_index, earliest_by_strategy[max-window], latest_by_strategy[max-window]).

    earliest/latest are the recovered draw-range cutoffs at each distinct
    (lottery_type, strategy_id)'s own widest referenced window, used only to
    check for genuinely new draws beyond the already-replayed range -- not to
    recompute any rate/lift/edge already present in P536C.
    """
    by_strategy_window = _index_matrix_by_strategy_window(p536c)
    by_combo_window = _index_leaderboard_by_combo_window(p536c)

    candidate_index: list[dict[str, Any]] = []
    max_window_by_strategy: dict[tuple[str, str], int] = {}

    for row in p537a["stable_candidates_for_owner_review"]:
        lt, sid, window, pick_k = row["lottery_type"], row["strategy_id"], int(row["window"]), int(row["pick_k"])
        key = (lt, sid)
        max_window_by_strategy[key] = max(max_window_by_strategy.get(key, 0), window)
        matrix_rec = by_strategy_window.get((lt, sid, window))
        candidate_index.append(
            {
                "candidate_group": "stable_review_candidate",
                "candidate_id": f"stable|{lt}|{sid}|w{window}|k{pick_k}",
                "lottery_type": lt,
                "strategy_id": sid,
                "feature_family": row.get("feature_family"),
                "pick_k": pick_k,
                "window": window,
                "recovery_status": "RECOVERED_FROM_P536C" if matrix_rec else "NOT_FOUND_IN_P536C",
                "recovered_earliest_target_draw": matrix_rec.get("earliest_target_draw") if matrix_rec else None,
                "recovered_latest_target_draw": matrix_rec.get("latest_target_draw") if matrix_rec else None,
                "derived_from_p537a_section": "stable_candidates_for_owner_review",
            }
        )

    for row in p537a["combination_candidates_for_followup"]:
        lt, combo_id = row["lottery_type"], row["combo_id"]
        windows_present = [int(w) for w in row["windows_present"]]
        members = _parse_combo_id(combo_id)
        for sid, _quota in members:
            key = (lt, sid)
            max_window_by_strategy[key] = max(max_window_by_strategy.get(key, 0), max(windows_present))

        per_window_cutoffs: dict[str, Any] = {}
        for window in windows_present:
            lb_rec = by_combo_window.get((lt, combo_id, window))
            per_window_cutoffs[str(window)] = {
                "recovery_status": "RECOVERED_FROM_P536C" if lb_rec else "NOT_FOUND_IN_P536C",
                "recovered_earliest_target_draw": lb_rec.get("earliest_target_draw") if lb_rec else None,
                "recovered_latest_target_draw": lb_rec.get("latest_target_draw") if lb_rec else None,
            }

        candidate_index.append(
            {
                "candidate_group": "combination_review_candidate",
                "candidate_id": f"combo|{lt}|{combo_id}",
                "lottery_type": lt,
                "combo_id": combo_id,
                "member_strategies": [{"strategy_id": sid, "quota": quota} for sid, quota in members],
                "requested_budget": row.get("requested_budget"),
                "windows_present": windows_present,
                "per_window_cutoffs": per_window_cutoffs,
                "derived_from_p537a_section": "combination_candidates_for_followup",
            }
        )

    earliest_by_strategy: dict[tuple[str, str], int] = {}
    latest_by_strategy: dict[tuple[str, str], int] = {}
    for key, window in max_window_by_strategy.items():
        rec = by_strategy_window.get((key[0], key[1], window))
        if rec and rec.get("earliest_target_draw") is not None:
            earliest_by_strategy[key] = int(rec["earliest_target_draw"])
        if rec and rec.get("latest_target_draw") is not None:
            latest_by_strategy[key] = int(rec["latest_target_draw"])

    return candidate_index, earliest_by_strategy, latest_by_strategy


def export_new_rows_since_cutoff(
    conn: sqlite3.Connection, latest_by_strategy: dict[tuple[str, str], int]
) -> list[dict[str, Any]]:
    rows_out: list[dict[str, Any]] = []
    for (lottery_type, strategy_id), latest in sorted(latest_by_strategy.items()):
        cur = conn.execute(_NEW_ROWS_QUERY, (lottery_type, strategy_id, latest))
        for row in cur.fetchall():
            rec = {field: row[field] for field in SOURCE_ROW_FIELDS}
            rec["row_role"] = "post_cutoff_new_draw"
            rec["source_table"] = "strategy_prediction_replays"
            rows_out.append(rec)
    return rows_out


def build_schema_sample_rows(
    conn: sqlite3.Connection, latest_by_strategy: dict[tuple[str, str], int]
) -> list[dict[str, Any]]:
    """One already-replayed row per lottery_type, for schema documentation only.

    These rows are already fully covered by P536C's replayed window; they are
    included only so a consumer can see the per-draw row shape without waiting
    for new draws to be ingested. Not new information.
    """
    seen_lotteries: set[str] = set()
    samples: list[dict[str, Any]] = []
    for (lottery_type, strategy_id) in sorted(latest_by_strategy):
        if lottery_type in seen_lotteries:
            continue
        cur = conn.execute(_LATEST_EXISTING_ROW_QUERY, (lottery_type, strategy_id))
        row = cur.fetchone()
        if row is None:
            continue
        rec = {field: row[field] for field in SOURCE_ROW_FIELDS}
        rec["row_role"] = "illustrative_already_replayed_sample"
        rec["source_table"] = "strategy_prediction_replays"
        samples.append(rec)
        seen_lotteries.add(lottery_type)
    return samples


def _data_hash(rows: list[dict[str, Any]]) -> str:
    hasher = hashlib.sha256()
    for rec in rows:
        parts = [
            str(rec.get("lottery_type")), str(rec.get("strategy_id")), str(rec.get("target_draw")),
            str(rec.get("bet_index")), str(rec.get("predicted_numbers")), str(rec.get("predicted_special")),
            str(rec.get("actual_numbers")), str(rec.get("actual_special")),
        ]
        hasher.update("|".join(parts).encode("utf-8"))
        hasher.update(b"\n")
    return hasher.hexdigest()


def run_analysis(
    db_path: Path | str,
    p537a_path: Path | str,
    p536k_path: Path | str,
    p536c_path: Path | str,
    p538a_path: Path | str,
) -> dict[str, Any]:
    p537a = _load_json(p537a_path)
    p536c = _load_json(p536c_path)

    candidate_index, earliest_by_strategy, latest_by_strategy = build_candidate_index(p537a, p536c)

    conn = _open_ro(db_path)
    try:
        new_rows = export_new_rows_since_cutoff(conn, latest_by_strategy)
        schema_sample_rows = build_schema_sample_rows(conn, latest_by_strategy)
        db_max_target_draw_by_lottery = {
            lt: row[0]
            for lt, row in (
                (lt, conn.execute(
                    "SELECT MAX(CAST(target_draw AS INTEGER)) FROM strategy_prediction_replays WHERE lottery_type=?",
                    (lt,),
                ).fetchone())
                for lt in sorted({lt for lt, _sid in latest_by_strategy})
            )
        }
    finally:
        conn.close()

    rows_by_lottery: dict[str, int] = {}
    for rec in new_rows:
        rows_by_lottery[rec["lottery_type"]] = rows_by_lottery.get(rec["lottery_type"], 0) + 1

    stable_count = sum(1 for c in candidate_index if c["candidate_group"] == "stable_review_candidate")
    combo_count = sum(1 for c in candidate_index if c["candidate_group"] == "combination_review_candidate")
    not_found = [c["candidate_id"] for c in candidate_index if c.get("recovery_status") == "NOT_FOUND_IN_P536C"]

    strategies_with_new_rows = sorted({rec["strategy_id"] for rec in new_rows})
    p538a = _load_json(p538a_path)

    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "derived_from_task_id": DERIVED_FROM_TASK_ID,
        "upstream_task_ids": list(UPSTREAM_TASK_IDS),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P539A_READONLY_PER_DRAW_REPLAY_EXPORT_READY",
        "candidate_scope": {
            "included_candidate_groups": ["stable_review_candidate", "combination_review_candidate"],
            "excluded_candidate_groups": {
                "cross_lottery_review_candidate": (
                    "Excluded per P538A's own rolling_or_out_of_sample_feasibility finding: "
                    "cross_lottery_normalized_lift rows lose strategy_id and target_draw range "
                    "during upstream aggregation and are not traceable to a single "
                    "walk-forward-able series without a separate aggregation-identity task."
                ),
                "insufficient_context_candidate": (
                    "Excluded per P538A's own finding: these rows are excluded upstream because "
                    "avg_prize_signal_lift_across_present_windows is null in the P536K source; "
                    "not a DB-export-resolvable gap."
                ),
            },
        },
        "candidate_index": candidate_index,
        "per_draw_source_rows_new_since_cutoff": new_rows,
        "schema_sample_rows_illustrative_only": schema_sample_rows,
        "readiness": {
            "rows_exported_by_lottery": rows_by_lottery,
            "rows_exported_by_candidate_group": {
                "stable_review_candidate": stable_count,
                "combination_review_candidate": combo_count,
            },
            "distinct_strategy_ids_covered": len(latest_by_strategy),
            "distinct_strategies_with_new_rows": strategies_with_new_rows,
            "db_max_target_draw_by_lottery": db_max_target_draw_by_lottery,
            "candidates_with_recovery_status_not_found": not_found,
            "temporal_fields_available": [
                "recovered_earliest_target_draw (via join to P536C strategy_pick_matrix_lift_extension / combination_leaderboard_with_lift)",
                "recovered_latest_target_draw (via join to P536C, same source)",
                "target_draw (raw DB column, per new/sample row)",
                "target_date (raw DB column, per new/sample row)",
            ],
            "fields_missing_for_next_stage": [
                "No committed artifact (P537A/P536K/P536C) carries a pick_k-specific hit/miss "
                "outcome per target_draw; hit_count/special_hit in this export's per-draw rows "
                "are the raw ingestion-time DB values computed over that bet row's full "
                "predicted_numbers list, not a pick_k-limited recomputation -- recomputing a "
                "pick_k-limited outcome is a scoring step out of scope for this read-only export.",
                "cross_lottery_review_candidate strategy identity (see candidate_scope.excluded_candidate_groups).",
                "insufficient_context_candidate upstream metric gap (see candidate_scope.excluded_candidate_groups).",
            ],
            "new_draws_found_since_last_replay_cutoff": bool(new_rows),
            "p539b_rolling_oos_evaluator_feasible_from_this_export_alone": bool(new_rows),
            "p539b_feasibility_note": (
                "New per-draw rows found beyond the recovered replay cutoff; a first "
                "out-of-sample window may be attemptable, subject to P536C's own "
                "minimum_support_draws=30 floor per candidate."
                if new_rows
                else "Zero rows found with target_draw strictly after each candidate strategy's "
                "own recovered latest_target_draw (checked against the live DB's own max "
                "target_draw per lottery, which is <= the recovered cutoff for every included "
                "candidate strategy). No new out-of-sample window is possible yet; re-run this "
                "export after new draws are ingested."
            ),
        },
        "provenance_and_limits": {
            "source_artifacts": {
                "P538A": {"path": str(p538a_path), "file_sha256": _file_sha256(p538a_path), "generated_at": p538a.get("generated_at")},
                "P537A": {"path": str(p537a_path), "file_sha256": _file_sha256(p537a_path), "generated_at": p537a.get("generated_at")},
                "P536K": {"path": str(p536k_path), "file_sha256": _file_sha256(p536k_path)},
                "P536C": {"path": str(p536c_path), "file_sha256": _file_sha256(p536c_path), "generated_at": p536c.get("generated_at")},
            },
            "db_access": {
                "db_path": str(db_path),
                "tables": ["strategy_prediction_replays"],
                "db_open_mode": "sqlite3 URI mode=ro + PRAGMA query_only=ON",
                "filters": {
                    "replay_status": "PREDICTED",
                    "dry_run": 0,
                    "predicted_numbers": "IS NOT NULL",
                    "actual_numbers": "IS NOT NULL",
                    "target_draw": "> recovered_latest_target_draw (per strategy) for per_draw_source_rows_new_since_cutoff",
                },
            },
            "new_rows_data_hash_sha256": _data_hash(new_rows),
            "new_rows_data_hash_fields": [
                "lottery_type", "strategy_id", "target_draw", "bet_index",
                "predicted_numbers", "predicted_special", "actual_numbers", "actual_special",
            ],
            "selection_method": (
                "Candidate identity and draw-range cutoffs are read verbatim from committed "
                "P537A/P536C artifacts (join, not recomputation). Per-draw rows are raw DB rows "
                "matching the same filter P333/P536C already use, restricted to target_draw > "
                "each candidate strategy's own recovered latest_target_draw. No rate, lift, "
                "edge, rank, or promotion is computed in this task."
            ),
            "limitations": [
                "Retrospective replay source export only; does not imply future performance.",
                "Does not compute any rolling/out-of-sample statistical test itself.",
                "hit_count/special_hit on exported rows reflect each bet row's full "
                "predicted_numbers list at ingestion time, not a pick_k-limited selection.",
                "schema_sample_rows_illustrative_only rows are already covered by P536C's "
                "committed replayed window and carry no new temporal information.",
            ],
            "disclaimer_en": DISCLAIMER_EN,
        },
        "disclaimer_en": DISCLAIMER_EN,
    }
    return artifact


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P539A — Read-Only Per-Draw Replay Export")
    add("")
    add(f"> {DISCLAIMER_EN}")
    add("")
    add(f"Derived from: **{result['derived_from_task_id']}**; upstream: {', '.join(result['upstream_task_ids'])}")
    add("")
    add("## Candidate Scope")
    add("")
    add(f"- included: {', '.join(result['candidate_scope']['included_candidate_groups'])}")
    for group, reason in result["candidate_scope"]["excluded_candidate_groups"].items():
        add(f"- excluded `{group}`: {reason}")
    add("")
    add("## Readiness")
    add("")
    readiness = result["readiness"]
    for key in (
        "rows_exported_by_lottery",
        "rows_exported_by_candidate_group",
        "distinct_strategy_ids_covered",
        "db_max_target_draw_by_lottery",
        "new_draws_found_since_last_replay_cutoff",
        "p539b_rolling_oos_evaluator_feasible_from_this_export_alone",
    ):
        add(f"- {key}: `{readiness[key]}`")
    add("")
    add(f"**Feasibility note:** {readiness['p539b_feasibility_note']}")
    add("")
    if readiness["candidates_with_recovery_status_not_found"]:
        add(f"- candidates with recovery NOT_FOUND: `{readiness['candidates_with_recovery_status_not_found']}`")
        add("")
    add("## Provenance")
    add("")
    for task_id, meta in result["provenance_and_limits"]["source_artifacts"].items():
        add(f"- {task_id}: `{meta['path']}` (sha256 `{meta['file_sha256'][:16]}...`)")
    add(f"- new_rows_data_hash_sha256: `{result['provenance_and_limits']['new_rows_data_hash_sha256']}`")
    add("")
    add("## Limitations")
    add("")
    for item in result["provenance_and_limits"]["limitations"]:
        add(f"- {item}")
    add("")
    return "\n".join(lines)


def write_artifacts(result: dict[str, Any], out_json: Path, out_md: Path) -> None:
    if out_json.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_json}")
    if out_md.exists():
        raise FileExistsError(f"refusing to overwrite existing artifact: {out_md}")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown(result) + "\n", encoding="utf-8")


def _default_dated_paths() -> tuple[Path, Path]:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = OUTPUT_DIR / f"p539a_readonly_per_draw_replay_export_{stamp}.json"
    md_path = OUTPUT_DIR / f"p539a_readonly_per_draw_replay_export_{stamp}.md"
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(description="Build P539A read-only per-draw replay export")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--p537a", default=str(DEFAULT_P537A_PATH))
    parser.add_argument("--p536k", default=str(DEFAULT_P536K_PATH))
    parser.add_argument("--p536c", default=str(DEFAULT_P536C_PATH))
    parser.add_argument("--p538a", default=str(DEFAULT_P538A_PATH))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    result = run_analysis(args.db, args.p537a, args.p536k, args.p536c, args.p538a)
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "readiness": result["readiness"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
