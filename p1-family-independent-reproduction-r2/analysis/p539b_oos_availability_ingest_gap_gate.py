"""P539B — OOS Availability / Ingest-Gap Gate.

Read-only gate over the committed P539A per-draw replay export (and its own
upstream P538A/P537A/P536K/P536C artifacts) plus an optional read-only check
of the live DB's `draws` table, to answer one question: is a real rolling /
out-of-sample evaluator feasible today, and if not, exactly what is missing.

P539A already reports `new_draws_found_since_last_replay_cutoff=false`, but
that finding is scoped to the `strategy_prediction_replays` table alone --
the same table its own recovered cutoffs are derived from. This module adds
one further read-only check against the `draws` table (the raw official
draw-result table) to test whether new official draws already exist that
have simply never been run through the strategy replay/prediction generation
step. That distinction -- "no new draws" vs. "new draws exist but were never
replayed" -- determines what the smallest next task actually is.

This module does not run a rolling/out-of-sample evaluator, does not score or
promote any strategy, and does not write to the DB (`draws` and
`strategy_prediction_replays` are opened read-only, mode=ro + PRAGMA
query_only=ON, matching P539A/P333's own convention).

Historical replay availability gate only; not a prediction, betting edge,
future-winning, or production-readiness claim.
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

TASK_ID = "P539B"
UPSTREAM_TASK_IDS = ("P539A", "P538A", "P537A", "P536K", "P536C", "P333")

DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"

DEFAULT_P539A_PATH = OUTPUT_DIR / "p539a_readonly_per_draw_replay_export_20260709.json"
DEFAULT_P538A_PATH = OUTPUT_DIR / "p538a_strategy_candidate_evaluation_readiness_20260709.json"
DEFAULT_P537A_PATH = OUTPUT_DIR / "p537a_shortlist_robustness_review_20260709.json"
DEFAULT_P536K_PATH = OUTPUT_DIR / "p536k_lift_candidate_shortlist_20260708.json"
DEFAULT_P536C_PATH = OUTPUT_DIR / "p536c_success_matrix_lift_extension_20260708.json"

DISCLAIMER_EN = (
    "Historical replay availability gate only; not a prediction, betting "
    "edge, future-winning, or production-readiness claim."
)

FEASIBILITY_CATEGORIES = (
    "feasible_now",
    "blocked_no_new_draws",
    "blocked_schema_mapping",
    "blocked_missing_temporal_fields",
    "blocked_needs_readonly_ingest_gap_audit",
)


def _load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _file_sha256(path: Path | str) -> str:
    hasher = hashlib.sha256()
    hasher.update(Path(path).read_bytes())
    return hasher.hexdigest()


def _db_file_sha256(db_path: Path | str) -> str:
    return _file_sha256(db_path)


def cutoffs_by_lottery_from_candidate_index(candidate_index: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    """Recovers min/max recovered_latest_target_draw per lottery from P539A's candidate_index.

    stable_review_candidate rows carry recovered_latest_target_draw directly.
    combination_review_candidate rows carry it nested per window in
    per_window_cutoffs; the max across windows is used per combo.
    """
    per_lottery: dict[str, list[int]] = {}
    for cand in candidate_index:
        lt = cand["lottery_type"]
        values: list[int] = []
        direct = cand.get("recovered_latest_target_draw")
        if direct is not None:
            values.append(int(direct))
        for window_rec in (cand.get("per_window_cutoffs") or {}).values():
            v = window_rec.get("recovered_latest_target_draw")
            if v is not None:
                values.append(int(v))
        if values:
            per_lottery.setdefault(lt, []).extend(values)

    return {
        lt: {"min_latest": min(vals), "max_latest": max(vals), "n_candidates_with_recovered_cutoff": len(vals)}
        for lt, vals in per_lottery.items()
    }


def query_draws_table_availability(
    conn: sqlite3.Connection, lottery_type: str, max_latest: int, min_latest: int
) -> dict[str, Any]:
    """Read-only lookup of official draw availability beyond recovered replay cutoffs.

    Distinguishes "beyond every candidate's cutoff" (max_latest) from
    "beyond at least one candidate's cutoff" (min_latest) since candidates
    for the same lottery can have slightly different recovered cutoffs.
    """
    max_draw_row = conn.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type=?", (lottery_type,)
    ).fetchone()
    draws_table_max_draw = max_draw_row[0] if max_draw_row else None

    n_beyond_all = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type=? AND CAST(draw AS INTEGER) > ?",
        (lottery_type, max_latest),
    ).fetchone()[0]
    n_beyond_any = conn.execute(
        "SELECT COUNT(*) FROM draws WHERE lottery_type=? AND CAST(draw AS INTEGER) > ?",
        (lottery_type, min_latest),
    ).fetchone()[0]

    sample_rows = conn.execute(
        """
        SELECT draw, date FROM draws
        WHERE lottery_type=? AND CAST(draw AS INTEGER) > ?
        ORDER BY CAST(draw AS INTEGER) ASC
        """,
        (lottery_type, max_latest),
    ).fetchall()

    return {
        "draws_table_max_draw": draws_table_max_draw,
        "new_official_draws_beyond_all_candidates_cutoff": n_beyond_all,
        "new_official_draws_beyond_any_candidate_cutoff": n_beyond_any,
        "new_official_draws_sample": [{"draw": r["draw"], "date": r["date"]} for r in sample_rows],
    }


def query_replay_table_max_target_draw(conn: sqlite3.Connection, lottery_type: str) -> int | None:
    row = conn.execute(
        "SELECT MAX(CAST(target_draw AS INTEGER)) FROM strategy_prediction_replays WHERE lottery_type=?",
        (lottery_type,),
    ).fetchone()
    return row[0] if row else None


def build_new_draw_availability_by_lottery(
    conn: sqlite3.Connection,
    cutoffs_by_lottery: dict[str, dict[str, int]],
    minimum_support_draws: int,
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for lt, cutoffs in sorted(cutoffs_by_lottery.items()):
        max_latest = cutoffs["max_latest"]
        min_latest = cutoffs["min_latest"]
        availability = query_draws_table_availability(conn, lt, max_latest, min_latest)
        replay_max_target_draw = query_replay_table_max_target_draw(conn, lt)
        n_new = availability["new_official_draws_beyond_all_candidates_cutoff"]
        result[lt] = {
            **availability,
            "replay_table_max_target_draw": replay_max_target_draw,
            "recovered_replay_cutoff_min_latest_across_candidates": min_latest,
            "recovered_replay_cutoff_max_latest_across_candidates": max_latest,
            "n_candidates_with_recovered_cutoff": cutoffs["n_candidates_with_recovered_cutoff"],
            "meets_minimum_support_draws_if_replayed_today": n_new >= minimum_support_draws,
            "additional_official_draws_needed_to_reach_minimum_support_draws": (
                max(0, minimum_support_draws - n_new)
            ),
        }
    return result


def build_oos_feasibility_summary(new_draw_availability_by_lottery: dict[str, Any]) -> dict[str, Any]:
    per_lottery: dict[str, Any] = {}
    any_new_official_draws = False
    any_meets_floor = False

    for lt, info in new_draw_availability_by_lottery.items():
        n_new = info["new_official_draws_beyond_all_candidates_cutoff"]
        meets_floor = info["meets_minimum_support_draws_if_replayed_today"]
        if n_new > 0:
            any_new_official_draws = True
        if meets_floor:
            any_meets_floor = True

        if n_new == 0:
            classification = "blocked_no_new_draws"
            note = "No new official draws exist yet beyond every candidate's recovered replay cutoff."
        elif not meets_floor:
            classification = "blocked_needs_readonly_ingest_gap_audit"
            note = (
                f"{n_new} new official draw(s) already exist beyond the replay cutoff but have "
                "never been run through strategy replay/prediction generation; even after "
                "generation, this is short of P536C's minimum_support_draws floor -- both "
                "replay generation and further new draws are needed."
            )
        else:
            classification = "blocked_needs_readonly_ingest_gap_audit"
            note = (
                f"{n_new} new official draw(s) already exist beyond the replay cutoff and already "
                "meet P536C's minimum_support_draws floor, but none have been run through "
                "strategy replay/prediction generation yet -- the blocker is a replay-generation "
                "gap, not a shortage of new draws."
            )

        per_lottery[lt] = {
            "feasible_now": False,
            "classification": classification,
            "note": note,
        }

    overall_feasible_now = False
    if any_new_official_draws:
        overall_classification = "blocked_needs_readonly_ingest_gap_audit"
        overall_note = (
            "Rolling/OOS evaluation is NOT feasible today for any candidate. New official draws "
            "already exist in the raw draws table beyond every candidate's recovered replay "
            "cutoff for at least one lottery, but zero of those draws have been run through "
            "strategy replay/prediction generation, so P539A's per-draw source table "
            "(strategy_prediction_replays) still has no post-cutoff rows. The primary blocker is "
            "therefore a replay-generation gap between the raw draws table and the "
            "strategy_prediction_replays table, not an absence of new lottery draws."
        )
    else:
        overall_classification = "blocked_no_new_draws"
        overall_note = (
            "Rolling/OOS evaluation is NOT feasible today. No new official draws exist yet "
            "beyond any candidate's recovered replay cutoff, in either the draws table or the "
            "strategy_prediction_replays table."
        )

    return {
        "feasible_now": overall_feasible_now,
        "classification": overall_classification,
        "closest_predefined_category_caveat": (
            "P539A's own readiness.new_draws_found_since_last_replay_cutoff=false is accurate "
            "only for the strategy_prediction_replays table; it should not be read as 'no new "
            "lottery draws have occurred' -- see new_draw_availability_by_lottery for the "
            "draws-table cross-check."
        ),
        "note": overall_note,
        "any_new_official_draws_beyond_cutoff": any_new_official_draws,
        "any_lottery_meets_minimum_support_draws_if_replayed": any_meets_floor,
        "per_lottery": per_lottery,
    }


def build_missing_data_or_ingest_gaps(new_draw_availability_by_lottery: dict[str, Any]) -> list[dict[str, Any]]:
    gaps: list[dict[str, Any]] = []
    for lt, info in sorted(new_draw_availability_by_lottery.items()):
        n_new = info["new_official_draws_beyond_all_candidates_cutoff"]
        if n_new > 0:
            gaps.append(
                {
                    "lottery_type": lt,
                    "gap_type": "replay_generation_gap",
                    "description": (
                        f"{n_new} official draw(s) already ingested into the `draws` table "
                        f"(up to draw {info['draws_table_max_draw']}) beyond every candidate's "
                        f"recovered replay cutoff (max_latest={info['recovered_replay_cutoff_max_latest_across_candidates']}), "
                        f"but strategy_prediction_replays.MAX(target_draw) for this lottery is still "
                        f"{info['replay_table_max_target_draw']}. No strategy replay/prediction row "
                        "has ever been generated for these draws."
                    ),
                    "not_a_raw_ingestion_gap": (
                        "The raw draws table is up to date for this lottery; this is a downstream "
                        "replay/prediction generation gap, not a missing-data-ingestion gap."
                    ),
                }
            )
        else:
            gaps.append(
                {
                    "lottery_type": lt,
                    "gap_type": "no_new_draws_yet",
                    "description": (
                        f"draws table MAX(draw)={info['draws_table_max_draw']} does not exceed the "
                        f"recovered replay cutoff (max_latest="
                        f"{info['recovered_replay_cutoff_max_latest_across_candidates']}) for any "
                        "candidate in this lottery. This is a genuine wait-for-new-draws gap."
                    ),
                    "not_a_raw_ingestion_gap": None,
                }
            )
    return gaps


def build_minimum_data_needed(
    new_draw_availability_by_lottery: dict[str, Any], minimum_support_draws: int
) -> list[dict[str, Any]]:
    needs: list[dict[str, Any]] = []
    for lt, info in sorted(new_draw_availability_by_lottery.items()):
        n_new = info["new_official_draws_beyond_all_candidates_cutoff"]
        additional_needed = info["additional_official_draws_needed_to_reach_minimum_support_draws"]
        steps = []
        if n_new > 0:
            steps.append(
                f"Run strategy replay/prediction generation for the existing {n_new} new official "
                f"draw(s) (target_draw > {info['recovered_replay_cutoff_max_latest_across_candidates']}) "
                "for this lottery's candidate strategies, so strategy_prediction_replays gains "
                "post-cutoff rows -- this is a distinct, separately-authorized task, not part of "
                "this read-only gate."
            )
        if additional_needed > 0:
            steps.append(
                f"Wait for {additional_needed} more official draw(s) to be ingested "
                f"(minimum_support_draws={minimum_support_draws} per P536C's window_policy)."
            )
        if not steps:
            steps.append("No further data needed by draw count; re-run P539A/P539C once replay rows exist.")
        needs.append(
            {
                "lottery_type": lt,
                "minimum_support_draws_floor": minimum_support_draws,
                "new_official_draws_available_now": n_new,
                "additional_official_draws_needed": additional_needed,
                "steps": steps,
            }
        )
    return needs


def run_analysis(
    db_path: Path | str,
    p539a_path: Path | str,
    p538a_path: Path | str,
    p537a_path: Path | str,
    p536k_path: Path | str,
    p536c_path: Path | str,
) -> dict[str, Any]:
    p539a = _load_json(p539a_path)
    p538a = _load_json(p538a_path)
    p536c = _load_json(p536c_path)

    minimum_support_draws = int(p536c.get("window_policy", {}).get("minimum_support_draws", 30))

    cutoffs_by_lottery = cutoffs_by_lottery_from_candidate_index(p539a["candidate_index"])

    db_hash_before = _db_file_sha256(db_path)
    conn = _open_ro(db_path)
    try:
        new_draw_availability_by_lottery = build_new_draw_availability_by_lottery(
            conn, cutoffs_by_lottery, minimum_support_draws
        )
    finally:
        conn.close()
    db_hash_after = _db_file_sha256(db_path)

    oos_feasibility_summary = build_oos_feasibility_summary(new_draw_availability_by_lottery)
    missing_data_or_ingest_gaps = build_missing_data_or_ingest_gaps(new_draw_availability_by_lottery)
    minimum_data_needed = build_minimum_data_needed(new_draw_availability_by_lottery, minimum_support_draws)

    p539a_source_export_findings = {
        "task_id": p539a.get("task_id"),
        "generated_at": p539a.get("generated_at"),
        "classification": p539a.get("classification"),
        "readiness_new_draws_found_since_last_replay_cutoff": p539a.get("readiness", {}).get(
            "new_draws_found_since_last_replay_cutoff"
        ),
        "readiness_p539b_rolling_oos_evaluator_feasible_from_this_export_alone": p539a.get(
            "readiness", {}
        ).get("p539b_rolling_oos_evaluator_feasible_from_this_export_alone"),
        "readiness_db_max_target_draw_by_lottery": p539a.get("readiness", {}).get(
            "db_max_target_draw_by_lottery"
        ),
        "distinct_strategy_ids_covered": p539a.get("readiness", {}).get("distinct_strategy_ids_covered"),
        "rows_exported_by_candidate_group": p539a.get("readiness", {}).get("rows_exported_by_candidate_group"),
        "scope_caveat": (
            "These P539A readiness figures are scoped to the strategy_prediction_replays table "
            "only. See oos_feasibility_summary and new_draw_availability_by_lottery in this "
            "artifact for the draws-table cross-check that refines this finding."
        ),
    }

    recommended_next_single_worker_task = {
        "proposed_task_id": "P539C (proposed, not yet authorized)",
        "title": "Read-write strategy replay/prediction generation for existing new draws",
        "scope": (
            "For each lottery with new_official_draws_beyond_all_candidates_cutoff > 0 (see "
            "new_draw_availability_by_lottery), run the existing replay/prediction generation "
            "pipeline for the shortlisted candidate strategy_ids against the specific new "
            "target_draw values already present in the `draws` table, writing new rows into "
            "strategy_prediction_replays. This is a DB-write task and requires its own explicit "
            "canonical-DB-write authorization; it is proposed here, not executed."
        ),
        "why_smallest_next_step": (
            "This task (P539B) already establishes that the blocker is a replay-generation gap, "
            "not missing official draws, for at least one lottery. Generating replay rows for the "
            "draws that already exist is the smallest step that could make a first OOS window "
            "possible, and is strictly narrower than building a rolling/OOS evaluator."
        ),
        "not_run_in_this_task": True,
        "excluded_from_this_proposed_task": [
            "Any lottery still below minimum_support_draws even after replay generation "
            "(see minimum_data_needed_for_p539c_or_oos_evaluator) -- those still need to wait for "
            "more official draws regardless of replay generation.",
            "cross_lottery_review_candidate / insufficient_context_candidate groups (excluded "
            "upstream by P538A/P539A; unchanged by this gate).",
        ],
    }

    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "upstream_task_ids": list(UPSTREAM_TASK_IDS),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P539B_OOS_AVAILABILITY_INGEST_GAP_GATE_READY",
        "oos_feasibility_summary": oos_feasibility_summary,
        "p539a_source_export_findings": p539a_source_export_findings,
        "new_draw_availability_by_lottery": new_draw_availability_by_lottery,
        "missing_data_or_ingest_gaps": missing_data_or_ingest_gaps,
        "minimum_data_needed_for_p539c_or_oos_evaluator": minimum_data_needed,
        "recommended_next_single_worker_task": recommended_next_single_worker_task,
        "provenance_and_limits": {
            "source_artifacts": {
                "P539A": {"path": str(p539a_path), "file_sha256": _file_sha256(p539a_path), "generated_at": p539a.get("generated_at")},
                "P538A": {"path": str(p538a_path), "file_sha256": _file_sha256(p538a_path), "generated_at": p538a.get("generated_at")},
                "P537A": {"path": str(p537a_path), "file_sha256": _file_sha256(p537a_path)},
                "P536K": {"path": str(p536k_path), "file_sha256": _file_sha256(p536k_path)},
                "P536C": {"path": str(p536c_path), "file_sha256": _file_sha256(p536c_path), "generated_at": p536c.get("generated_at")},
            },
            "db_access": {
                "db_path": str(db_path),
                "tables": ["draws", "strategy_prediction_replays"],
                "db_open_mode": "sqlite3 URI mode=ro + PRAGMA query_only=ON",
                "purpose": (
                    "Read-only availability check only: MAX(draw)/COUNT(*) on `draws`, and "
                    "MAX(target_draw) on `strategy_prediction_replays`, both grouped by "
                    "lottery_type. No row-level prediction data is read or exported by this task."
                ),
                "db_sha256_before": db_hash_before,
                "db_sha256_after": db_hash_after,
                "db_unchanged": db_hash_before == db_hash_after,
            },
            "minimum_support_draws_source": "P536C.window_policy.minimum_support_draws",
            "minimum_support_draws_value": minimum_support_draws,
            "feasibility_categories_reference": list(FEASIBILITY_CATEGORIES),
            "selection_method": (
                "All candidate identity and recovered cutoffs are read verbatim from the "
                "committed P539A artifact (no recomputation of candidate_index). The only new "
                "computation in this task is a read-only COUNT/MAX over the `draws` and "
                "strategy_prediction_replays tables, cross-referenced against those cutoffs."
            ),
            "limitations": [
                "Availability gate only; does not compute any rolling/out-of-sample statistical test.",
                "Does not rank, score, or promote any strategy.",
                "additional_official_draws_needed_to_reach_minimum_support_draws assumes all new "
                "draws would be usable once replayed; does not account for any candidate-specific "
                "exclusion that might apply once replay rows actually exist.",
                "Retrospective availability snapshot as of generated_at; re-run after any new "
                "ingestion or replay-generation run.",
            ],
            "disclaimer_en": DISCLAIMER_EN,
        },
        "disclaimer_en": DISCLAIMER_EN,
    }
    return artifact


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P539B — OOS Availability / Ingest-Gap Gate")
    add("")
    add(f"> {DISCLAIMER_EN}")
    add("")
    add(f"Upstream: {', '.join(result['upstream_task_ids'])}")
    add("")
    add("## OOS Feasibility Summary")
    add("")
    summary = result["oos_feasibility_summary"]
    add(f"- feasible_now: `{summary['feasible_now']}`")
    add(f"- classification: `{summary['classification']}`")
    add(f"- note: {summary['note']}")
    add(f"- caveat: {summary['closest_predefined_category_caveat']}")
    add("")
    for lt, info in sorted(summary["per_lottery"].items()):
        add(f"- **{lt}**: `{info['classification']}` — {info['note']}")
    add("")
    add("## New Draw Availability By Lottery")
    add("")
    for lt, info in sorted(result["new_draw_availability_by_lottery"].items()):
        add(
            f"- **{lt}**: draws.max_draw=`{info['draws_table_max_draw']}`, "
            f"replay.max_target_draw=`{info['replay_table_max_target_draw']}`, "
            f"new_beyond_all_candidates_cutoff=`{info['new_official_draws_beyond_all_candidates_cutoff']}`, "
            f"meets_minimum_support_draws_if_replayed=`{info['meets_minimum_support_draws_if_replayed_today']}`"
        )
    add("")
    add("## Missing Data / Ingest Gaps")
    add("")
    for gap in result["missing_data_or_ingest_gaps"]:
        add(f"- **{gap['lottery_type']}** (`{gap['gap_type']}`): {gap['description']}")
    add("")
    add("## Minimum Data Needed For P539C / OOS Evaluator")
    add("")
    for need in result["minimum_data_needed_for_p539c_or_oos_evaluator"]:
        add(f"- **{need['lottery_type']}**:")
        for step in need["steps"]:
            add(f"  - {step}")
    add("")
    add("## Recommended Next Single-Worker Task")
    add("")
    task = result["recommended_next_single_worker_task"]
    add(f"- proposed_task_id: `{task['proposed_task_id']}`")
    add(f"- title: {task['title']}")
    add(f"- scope: {task['scope']}")
    add("")
    add("## Provenance")
    add("")
    for task_id, meta in result["provenance_and_limits"]["source_artifacts"].items():
        add(f"- {task_id}: `{meta['path']}` (sha256 `{meta['file_sha256'][:16]}...`)")
    db_access = result["provenance_and_limits"]["db_access"]
    add(f"- db_unchanged: `{db_access['db_unchanged']}`")
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
    json_path = OUTPUT_DIR / f"p539b_oos_availability_ingest_gap_gate_{stamp}.json"
    md_path = OUTPUT_DIR / f"p539b_oos_availability_ingest_gap_gate_{stamp}.md"
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(description="Build P539B OOS availability / ingest-gap gate")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--p539a", default=str(DEFAULT_P539A_PATH))
    parser.add_argument("--p538a", default=str(DEFAULT_P538A_PATH))
    parser.add_argument("--p537a", default=str(DEFAULT_P537A_PATH))
    parser.add_argument("--p536k", default=str(DEFAULT_P536K_PATH))
    parser.add_argument("--p536c", default=str(DEFAULT_P536C_PATH))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    result = run_analysis(args.db, args.p539a, args.p538a, args.p537a, args.p536k, args.p536c)
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "oos_feasibility_summary": result["oos_feasibility_summary"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
