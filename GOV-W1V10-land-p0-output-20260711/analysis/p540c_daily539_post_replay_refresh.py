"""P540C DAILY_539 post-replay refresh (read-only verification artifact).

Verifies -- strictly read-only -- that the P540B incremental replay rows
(controlled_apply_id = P540B_DAILY539_INCREMENTAL_20260709) are present and
queryable in the canonical DB, that they match the committed P540B manifest
exactly, that they are scoped to DAILY_539 only, and that BIG_LOTTO /
POWER_LOTTO remain at the P540B post-write invariant. Emits dated JSON/MD
refresh artifacts under outputs/research/.

This module never writes the DB: connections are opened with the SQLite URI
mode=ro and PRAGMA query_only=ON, and the DB file sha256/mtime are captured
before and after the inspection session.

Historical post-replay refresh only; not a prediction, betting edge,
future-winning, or production-readiness claim.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DEFAULT_P540B_JSON = (
    OUTPUT_DIR / "p540b_daily539_incremental_replay_generation_20260709.json"
)

TASK_ID = "P540C"
REPLAY_TABLE = "strategy_prediction_replays"
TARGET_LOTTERY = "DAILY_539"
OTHER_LOTTERIES = ("BIG_LOTTO", "POWER_LOTTO")
P540B_APPLY_ID = "P540B_DAILY539_INCREMENTAL_20260709"

# Spec-pinned expectations (P540C task spec; must agree with the committed
# P540B manifest -- any disagreement is itself reported as a failed check).
SPEC_EXPECTED_ROWS = 528
SPEC_EXPECTED_DRAW_COUNT = 44
SPEC_EXPECTED_STRATEGY_COUNT = 12
# P540B manifest bet_index_scope: "1 only, for every in-scope strategy_id".
EXPECTED_BET_INDICES = [1]

CLASSIFICATION_READY = "P540C_DAILY539_POST_REPLAY_REFRESH_READY"
CLASSIFICATION_NOT_QUERYABLE = "P540C_BLOCKED_P540B_ROWS_NOT_QUERYABLE"
CLASSIFICATION_MISMATCH = "P540C_BLOCKED_P540B_MANIFEST_MISMATCH"

NEXT_TASK_READY = "P540D_DAILY539_POST_REPLAY_SUCCESS_MATRIX_REFRESH_NO_DB_WRITE"

DISCLAIMER_EN = (
    "Historical post-replay refresh only; not a prediction, betting edge, "
    "future-winning, or production-readiness claim."
)


def _open_ro(db_path: Path | str) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    conn.execute("PRAGMA query_only=ON")
    return conn


def _file_sha256(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_mtime_epoch(path: Path | str) -> int:
    return int(Path(path).stat().st_mtime)


def load_p540b_expectations(p540b_json_path: Path | str) -> dict[str, Any]:
    """Extract the fields P540C verifies against from the committed P540B artifact."""
    with open(p540b_json_path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    manifest = doc["manifest"]
    post = doc["post_write_snapshot"]
    return {
        "source_path": str(p540b_json_path),
        "controlled_apply_id": manifest["controlled_apply_id"],
        "target_lottery": manifest["target_lottery"],
        "expected_inserted_rows": manifest["expected_inserted_rows"],
        "target_draw_ids": sorted(manifest["target_draw_ids"], key=int),
        "target_draw_count": manifest["target_draw_count"],
        "in_scope_strategy_ids": sorted(manifest["in_scope_strategy_ids"]),
        "in_scope_strategy_id_count": manifest["in_scope_strategy_id_count"],
        "excluded_strategy_ids": manifest.get("excluded_strategy_ids", {}),
        "excluded_bet_indices": manifest.get("excluded_bet_indices", {}),
        "inserted_rows_by_draw": doc.get("inserted_rows_by_draw", {}),
        "post_write_counts_by_lottery": post[
            "strategy_prediction_replays_count_by_lottery"
        ],
        "post_write_total": post["strategy_prediction_replays_total"],
        "p540b_db_sha256_after": doc.get("db_access", {}).get("db_sha256_after"),
        "p540b_classification": doc.get("classification"),
    }


def collect_observed(conn: sqlite3.Connection, apply_id: str) -> dict[str, Any]:
    """Read-only observation of the P540B-scoped rows and table-level totals."""

    def one(sql: str, params: tuple = ()) -> Any:
        return conn.execute(sql, params).fetchone()[0]

    def pairs(sql: str, params: tuple = ()) -> dict:
        return {str(k): v for k, v in conn.execute(sql, params).fetchall()}

    table_exists = bool(
        one(
            "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?",
            (REPLAY_TABLE,),
        )
    )
    if not table_exists:
        return {"table_exists": False}

    scope = f"FROM {REPLAY_TABLE} WHERE controlled_apply_id = ?"
    observed: dict[str, Any] = {
        "table_exists": True,
        "apply_id_total_rows": one(f"SELECT count(*) {scope}", (apply_id,)),
        "apply_id_rows_by_lottery": pairs(
            f"SELECT lottery_type, count(*) {scope} GROUP BY lottery_type",
            (apply_id,),
        ),
        "distinct_target_draws": [
            r[0]
            for r in conn.execute(
                f"SELECT DISTINCT target_draw {scope} "
                "ORDER BY CAST(target_draw AS INTEGER)",
                (apply_id,),
            ).fetchall()
        ],
        "rows_by_target_draw": pairs(
            f"SELECT target_draw, count(*) {scope} "
            "GROUP BY target_draw ORDER BY CAST(target_draw AS INTEGER)",
            (apply_id,),
        ),
        "rows_by_strategy": pairs(
            f"SELECT strategy_id, count(*) {scope} GROUP BY strategy_id "
            "ORDER BY strategy_id",
            (apply_id,),
        ),
        "bet_index_counts": {
            str(k): v
            for k, v in conn.execute(
                f"SELECT bet_index, count(*) {scope} GROUP BY bet_index "
                "ORDER BY bet_index",
                (apply_id,),
            ).fetchall()
        },
        "duplicate_identity_groups": one(
            f"SELECT count(*) FROM (SELECT 1 {scope} "
            "GROUP BY target_draw, strategy_id, bet_index HAVING count(*) > 1)",
            (apply_id,),
        ),
        "replay_status_counts": pairs(
            f"SELECT replay_status, count(*) {scope} GROUP BY replay_status "
            "ORDER BY replay_status",
            (apply_id,),
        ),
        "hit_count_distribution": pairs(
            f"SELECT hit_count, count(*) {scope} GROUP BY hit_count "
            "ORDER BY hit_count",
            (apply_id,),
        ),
        "special_hit_distribution": pairs(
            f"SELECT special_hit, count(*) {scope} GROUP BY special_hit "
            "ORDER BY special_hit",
            (apply_id,),
        ),
        "predicted_special_null_rows": one(
            f"SELECT count(*) {scope} AND predicted_special IS NULL", (apply_id,)
        ),
        "dry_run_counts": pairs(
            f"SELECT dry_run, count(*) {scope} GROUP BY dry_run", (apply_id,)
        ),
        "source_values": pairs(
            f"SELECT COALESCE(source,'<NULL>'), count(*) {scope} GROUP BY source",
            (apply_id,),
        ),
        "truth_level_values": pairs(
            f"SELECT COALESCE(truth_level,'<NULL>'), count(*) {scope} "
            "GROUP BY truth_level",
            (apply_id,),
        ),
        "provenance_hash_populated_rows": one(
            f"SELECT count(*) {scope} AND provenance_hash IS NOT NULL "
            "AND provenance_hash != ''",
            (apply_id,),
        ),
        "table_totals_by_lottery": pairs(
            f"SELECT lottery_type, count(*) FROM {REPLAY_TABLE} GROUP BY lottery_type"
        ),
        "table_total_rows": one(f"SELECT count(*) FROM {REPLAY_TABLE}"),
    }
    return observed


def _check(name: str, expected: Any, observed: Any) -> dict[str, Any]:
    return {
        "check": name,
        "expected": expected,
        "observed": observed,
        "match": expected == observed,
    }


def compare_with_manifest(
    expected: dict[str, Any], observed: dict[str, Any]
) -> dict[str, Any]:
    """Compare observed DB state against the P540B manifest expectations."""
    apply_id = expected["controlled_apply_id"]
    checks = []
    if apply_id == P540B_APPLY_ID:
        # The P540C task spec pins these values for the real P540B batch; a
        # committed manifest that disagrees with the spec is itself a failure.
        checks.extend(
            [
                _check(
                    "spec_pin_expected_rows_agrees_with_p540b_manifest",
                    SPEC_EXPECTED_ROWS,
                    expected["expected_inserted_rows"],
                ),
                _check(
                    "spec_pin_draw_count_agrees_with_p540b_manifest",
                    SPEC_EXPECTED_DRAW_COUNT,
                    expected["target_draw_count"],
                ),
                _check(
                    "spec_pin_strategy_count_agrees_with_p540b_manifest",
                    SPEC_EXPECTED_STRATEGY_COUNT,
                    expected["in_scope_strategy_id_count"],
                ),
            ]
        )
    checks += [
        _check(
            "apply_id_total_rows",
            expected["expected_inserted_rows"],
            observed["apply_id_total_rows"],
        ),
        _check(
            "apply_id_rows_daily539_only",
            {expected["target_lottery"]: expected["expected_inserted_rows"]},
            observed["apply_id_rows_by_lottery"],
        ),
        _check(
            "apply_id_rows_in_big_lotto_or_power_lotto",
            0,
            sum(
                observed["apply_id_rows_by_lottery"].get(lt, 0)
                for lt in OTHER_LOTTERIES
            ),
        ),
        _check(
            "distinct_target_draw_count",
            expected["target_draw_count"],
            len(observed["distinct_target_draws"]),
        ),
        _check(
            "target_draw_ids_exact_set",
            expected["target_draw_ids"],
            observed["distinct_target_draws"],
        ),
        _check(
            "rows_by_target_draw_match_p540b_inserted_rows_by_draw",
            {
                k: v
                for k, v in sorted(
                    expected["inserted_rows_by_draw"].items(), key=lambda kv: int(kv[0])
                )
            },
            observed["rows_by_target_draw"],
        ),
        _check(
            "strategy_id_exact_set",
            expected["in_scope_strategy_ids"],
            sorted(observed["rows_by_strategy"].keys()),
        ),
        _check(
            "rows_per_strategy_uniform",
            {
                sid: expected["target_draw_count"]
                for sid in expected["in_scope_strategy_ids"]
            },
            observed["rows_by_strategy"],
        ),
        _check(
            "bet_index_scope",
            {str(b): expected["expected_inserted_rows"] for b in EXPECTED_BET_INDICES},
            observed["bet_index_counts"],
        ),
        _check(
            "duplicate_target_draw_strategy_bet_index_groups",
            0,
            observed["duplicate_identity_groups"],
        ),
        _check(
            "table_totals_match_p540b_post_write_snapshot",
            {
                k: v
                for k, v in sorted(expected["post_write_counts_by_lottery"].items())
            },
            {k: v for k, v in sorted(observed["table_totals_by_lottery"].items())},
        ),
        _check(
            "table_total_matches_p540b_post_write_total",
            expected["post_write_total"],
            observed["table_total_rows"],
        ),
    ]
    return {
        "controlled_apply_id": apply_id,
        "checks": checks,
        "all_checks_pass": all(c["match"] for c in checks),
        "failed_checks": [c["check"] for c in checks if not c["match"]],
    }


def build_artifact(
    db_path: Path | str,
    expected: dict[str, Any],
    observed: dict[str, Any],
    manifest_match: dict[str, Any],
    db_before: dict[str, Any],
    db_after: dict[str, Any],
) -> dict[str, Any]:
    queryable = observed.get("table_exists", False) and isinstance(
        observed.get("apply_id_total_rows"), int
    )
    rows_present = queryable and observed["apply_id_total_rows"] > 0
    all_pass = bool(rows_present and manifest_match["all_checks_pass"])
    db_unchanged = (
        db_before["sha256"] == db_after["sha256"]
        and db_before["mtime_epoch"] == db_after["mtime_epoch"]
    )

    if not rows_present:
        classification = CLASSIFICATION_NOT_QUERYABLE
        next_task = CLASSIFICATION_NOT_QUERYABLE
    elif not all_pass:
        classification = CLASSIFICATION_MISMATCH
        next_task = CLASSIFICATION_MISMATCH
    else:
        classification = CLASSIFICATION_READY
        next_task = NEXT_TASK_READY

    draws = observed.get("distinct_target_draws", [])
    uniform_12 = bool(
        draws
        and all(
            v == expected["in_scope_strategy_id_count"]
            for v in observed.get("rows_by_target_draw", {}).values()
        )
    )

    artifact: dict[str, Any] = {
        "task_id": TASK_ID,
        "schema_version": "p540c.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": classification,
        "summary": {
            "purpose": (
                "Read-only verification that the P540B DAILY_539 incremental "
                "replay rows are present, queryable, manifest-exact, and "
                "DAILY_539-scoped in the canonical DB, with BIG_LOTTO / "
                "POWER_LOTTO at the P540B post-write invariant."
            ),
            "p540b_rows_queryable": rows_present,
            "p540b_manifest_exact_match": manifest_match["all_checks_pass"],
            "daily539_scope_only": observed.get("apply_id_rows_by_lottery", {})
            == {TARGET_LOTTERY: expected["expected_inserted_rows"]},
            "big_lotto_power_lotto_unchanged_from_p540b_invariant": all(
                observed.get("table_totals_by_lottery", {}).get(lt)
                == expected["post_write_counts_by_lottery"].get(lt)
                for lt in OTHER_LOTTERIES
            ),
            "db_unchanged_during_task": db_unchanged,
            "verdict": classification,
        },
        "p540b_manifest_match": manifest_match,
        "readonly_db_snapshot": {
            "db_path": str(db_path),
            "access_mode": "sqlite URI mode=ro + PRAGMA query_only=ON",
            "before": db_before,
            "after": db_after,
            "db_unchanged_during_task": db_unchanged,
            "db_sha256_matches_p540b_recorded_post_write_hash": (
                db_before["sha256"] == expected["p540b_db_sha256_after"]
            ),
            "note": (
                "Hash equality with the P540B post-write hash is informational "
                "provenance (a later authorized write elsewhere in the DB would "
                "break it without touching P540B rows); the manifest checks "
                "above are the gating evidence."
            ),
        },
        "daily539_post_replay_coverage": {
            "controlled_apply_id": expected["controlled_apply_id"],
            "target_draw_range": {
                "min": draws[0] if draws else None,
                "max": draws[-1] if draws else None,
            },
            "target_draw_count": len(draws),
            "strategy_ids_included": sorted(
                observed.get("rows_by_strategy", {}).keys()
            ),
            "strategies_excluded_by_p540b_with_reasons": expected[
                "excluded_strategy_ids"
            ],
            "bet_index_carveouts_documented_by_p540b": expected[
                "excluded_bet_indices"
            ],
            "rows_by_target_draw_uniform_12": uniform_12,
            "rows_by_target_draw": observed.get("rows_by_target_draw", {}),
            "rows_by_strategy": observed.get("rows_by_strategy", {}),
            "bet_index_counts": observed.get("bet_index_counts", {}),
            "replay_status_counts": observed.get("replay_status_counts", {}),
            "hit_count_distribution": observed.get("hit_count_distribution", {}),
            "special_fields": {
                "note": (
                    "DAILY_539 has no special-number zone; special columns are "
                    "expected to be inert on these rows."
                ),
                "special_hit_distribution": observed.get(
                    "special_hit_distribution", {}
                ),
                "predicted_special_null_rows": observed.get(
                    "predicted_special_null_rows"
                ),
            },
            "provenance_fields": {
                "source_values": observed.get("source_values", {}),
                "truth_level_values": observed.get("truth_level_values", {}),
                "dry_run_counts": observed.get("dry_run_counts", {}),
                "provenance_hash_populated_rows": observed.get(
                    "provenance_hash_populated_rows"
                ),
            },
            "daily539_table_total_rows": observed.get(
                "table_totals_by_lottery", {}
            ).get(TARGET_LOTTERY),
        },
        "downstream_feasibility": {
            "success_matrix_refresh": (
                "FEASIBLE read-only: the P536B/P536C success-matrix methodology "
                "can now be refreshed over DAILY_539 replay coverage extended "
                "through draw "
                f"{draws[-1] if draws else 'N/A'} (528 new rows, 12 strategies, "
                "bet_index 1). Comparisons must scope to the 12 in-scope "
                "strategy_ids at bet_index 1; the 3 P540B-excluded strategy_ids "
                "and 2 bet-index carve-outs remain absent for the new draws."
            ),
            "oos_first_window_data_availability": (
                "The 44 newly replayed draws meet the MINIMUM_SUPPORT_DRAWS_FLOOR "
                "(30) that P539B/P540A identified for a first DAILY_539 OOS "
                "window in terms of data availability only. Running any OOS "
                "evaluator or strategy scoring remains out of scope here and "
                "needs its own authorized task."
            ),
            "per_draw_export_refresh": (
                "FEASIBLE read-only: the P539A per-draw export shape can be "
                "regenerated to include the 44 new target draws if a future "
                "task is authorized to do so (P539A artifacts themselves are "
                "not recomputed by P540C)."
            ),
            "big_lotto_power_lotto": (
                "NOT unlocked by P540B/P540C: both remain short of the minimum "
                "support floor per P540A and received no new replay rows."
            ),
        },
        "excluded_scope": {
            "not_performed_by_this_task": [
                "DB writes of any kind (verified by before/after sha256+mtime)",
                "replay row generation (DAILY_539, BIG_LOTTO, or POWER_LOTTO)",
                "OOS evaluator runs, strategy scoring, or promotion gating",
                "recomputation or overwrite of P536/P537/P538/P539/P540A/P540B artifacts",
                "route/API/UI changes",
                "full-history replay rerun",
            ],
            "not_yet_validated": [
                "hit-rate/lift semantics of the 528 new rows (descriptive "
                "distribution reported only; no statistical claim)",
                "the 3 P540B-excluded strategy_ids (daily539_f4cold_3bet, "
                "daily539_f4cold_5bet, daily539_markov_cold) for the new draws",
                "bet_index 2-3 carve-outs (acb_markov_midfreq_3bet, "
                "daily539_f4cold) for the new draws",
                "any predictive value of any strategy (explicitly out of scope)",
            ],
        },
        "recommended_next_single_worker_task": {
            "proposed_task_id": next_task,
            "why": (
                "Success-matrix refresh is the smallest genuinely new read-only "
                "step that consumes the now-verified rows: it extends the "
                "already-merged P536B/P536C descriptive methodology over the 44 "
                "new draws without touching the DB or any evaluator. The "
                "alternative (P540D_DAILY539_OOS_READINESS_GATE_NO_DB_WRITE) is "
                "largely redundant with this artifact, which already documents "
                "post-replay availability (missing draws = 0; 44 >= 30 floor)."
                if classification == CLASSIFICATION_READY
                else "Blocked; see classification."
            ),
            "not_run_in_this_task": True,
        },
        "provenance_and_limits": {
            "upstream_artifacts_read": [
                "outputs/research/p540b_daily539_incremental_replay_generation_20260709.json",
                "outputs/research/p540a_full_replay_regeneration_readiness_20260709.json",
                "outputs/research/p539b_oos_availability_ingest_gap_gate_20260709.json",
                "outputs/research/p539a_readonly_per_draw_replay_export_20260709.json",
                "outputs/research/p536c_success_matrix_lift_extension_20260708.json",
            ],
            "p540b_manifest_source": expected["source_path"],
            "p540b_classification": expected["p540b_classification"],
            "replay_table": REPLAY_TABLE,
            "python_version": sys.version.split()[0],
            "limits": [
                "Read-only descriptive verification; no statistical inference, "
                "no ROI/edge computation, no strategy comparison.",
                "Draw ordering uses CAST(target_draw AS INTEGER) per repo DB "
                "conventions (draw columns are TEXT).",
                "hit_count distribution covers bet_index 1 rows of the 12 "
                "in-scope strategies only.",
                "An external writer changing the DB mid-task would surface as a "
                "before/after hash mismatch and void this artifact.",
            ],
        },
        "disclaimer_en": DISCLAIMER_EN,
    }
    return artifact


def render_markdown(artifact: dict[str, Any]) -> str:
    s = artifact["summary"]
    mm = artifact["p540b_manifest_match"]
    snap = artifact["readonly_db_snapshot"]
    cov = artifact["daily539_post_replay_coverage"]
    lines: list[str] = []
    add = lines.append
    add("# P540C — DAILY_539 Post-Replay Refresh (Read-Only)")
    add("")
    add(f"> {artifact['disclaimer_en']}")
    add("")
    add(f"- Classification: **{artifact['classification']}**")
    add(f"- Generated at: {artifact['generated_at']}")
    add("")
    add("## Summary")
    add("")
    for key in (
        "p540b_rows_queryable",
        "p540b_manifest_exact_match",
        "daily539_scope_only",
        "big_lotto_power_lotto_unchanged_from_p540b_invariant",
        "db_unchanged_during_task",
    ):
        add(f"- {key}: **{s[key]}**")
    add("")
    add("## P540B Manifest Match")
    add("")
    add(f"- controlled_apply_id: `{mm['controlled_apply_id']}`")
    add(f"- all_checks_pass: **{mm['all_checks_pass']}**")
    if mm["failed_checks"]:
        add(f"- failed_checks: {', '.join(mm['failed_checks'])}")
    add("")
    add("| check | expected | observed | match |")
    add("|---|---|---|---|")
    for c in mm["checks"]:
        exp = json.dumps(c["expected"], ensure_ascii=False)
        obs = json.dumps(c["observed"], ensure_ascii=False)
        if len(exp) > 60:
            exp = exp[:57] + "..."
        if len(obs) > 60:
            obs = obs[:57] + "..."
        add(f"| {c['check']} | {exp} | {obs} | {'PASS' if c['match'] else 'FAIL'} |")
    add("")
    add("## Read-Only DB Snapshot")
    add("")
    add(f"- db_path: `{snap['db_path']}`")
    add(f"- access_mode: {snap['access_mode']}")
    add(
        f"- before: sha256 `{snap['before']['sha256']}`, "
        f"mtime_epoch {snap['before']['mtime_epoch']}, "
        f"size {snap['before']['size_bytes']}"
    )
    add(
        f"- after: sha256 `{snap['after']['sha256']}`, "
        f"mtime_epoch {snap['after']['mtime_epoch']}, "
        f"size {snap['after']['size_bytes']}"
    )
    add(f"- db_unchanged_during_task: **{snap['db_unchanged_during_task']}**")
    add(
        "- db_sha256_matches_p540b_recorded_post_write_hash: "
        f"**{snap['db_sha256_matches_p540b_recorded_post_write_hash']}**"
    )
    add("")
    add("## DAILY_539 Post-Replay Coverage")
    add("")
    add(f"- controlled_apply_id: `{cov['controlled_apply_id']}`")
    add(
        f"- target draw range: {cov['target_draw_range']['min']} .. "
        f"{cov['target_draw_range']['max']} ({cov['target_draw_count']} draws)"
    )
    add(
        f"- rows uniform at 12 per draw: **{cov['rows_by_target_draw_uniform_12']}**"
        " (full per-draw map in the JSON artifact)"
    )
    add(f"- bet_index counts: {json.dumps(cov['bet_index_counts'])}")
    add(f"- replay_status counts: {json.dumps(cov['replay_status_counts'])}")
    add(
        f"- DAILY_539 table total rows: {cov['daily539_table_total_rows']}"
    )
    add("")
    add("### Strategies included (rows each)")
    add("")
    add("| strategy_id | rows |")
    add("|---|---|")
    for sid, n in cov["rows_by_strategy"].items():
        add(f"| {sid} | {n} |")
    add("")
    add("### Strategies excluded by P540B (reasons documented in P540B)")
    add("")
    for sid in sorted(cov["strategies_excluded_by_p540b_with_reasons"]):
        add(f"- `{sid}` (see P540B artifact for the full reason text)")
    for sid in sorted(cov["bet_index_carveouts_documented_by_p540b"]):
        add(f"- `{sid}`: bet_index 2-3 carve-out (bet 1 replayed only)")
    add("")
    add("### hit_count distribution (descriptive only)")
    add("")
    add("| hit_count | rows |")
    add("|---|---|")
    for k, v in cov["hit_count_distribution"].items():
        add(f"| {k} | {v} |")
    add("")
    add("### Special fields")
    add("")
    add(f"- {cov['special_fields']['note']}")
    add(
        "- special_hit_distribution: "
        f"{json.dumps(cov['special_fields']['special_hit_distribution'])}"
    )
    add(
        "- predicted_special_null_rows: "
        f"{cov['special_fields']['predicted_special_null_rows']}"
    )
    add("")
    add("### Provenance fields")
    add("")
    for k, v in cov["provenance_fields"].items():
        add(f"- {k}: {json.dumps(v, ensure_ascii=False)}")
    add("")
    add("## Downstream Feasibility")
    add("")
    for k, v in artifact["downstream_feasibility"].items():
        add(f"- **{k}**: {v}")
    add("")
    add("## Excluded Scope")
    add("")
    add("Not performed by this task:")
    add("")
    for item in artifact["excluded_scope"]["not_performed_by_this_task"]:
        add(f"- {item}")
    add("")
    add("Not yet validated:")
    add("")
    for item in artifact["excluded_scope"]["not_yet_validated"]:
        add(f"- {item}")
    add("")
    add("## Recommended Next Single Worker Task")
    add("")
    rec = artifact["recommended_next_single_worker_task"]
    add(f"- proposed_task_id: **{rec['proposed_task_id']}**")
    add(f"- why: {rec['why']}")
    add("")
    add("## Provenance and Limits")
    add("")
    prov = artifact["provenance_and_limits"]
    add(f"- p540b_manifest_source: `{prov['p540b_manifest_source']}`")
    add(f"- replay_table: `{prov['replay_table']}`")
    add(f"- python_version: {prov['python_version']}")
    add("- upstream artifacts read:")
    for p in prov["upstream_artifacts_read"]:
        add(f"  - `{p}`")
    add("- limits:")
    for lim in prov["limits"]:
        add(f"  - {lim}")
    add("")
    add(f"> {artifact['disclaimer_en']}")
    add("")
    return "\n".join(lines)


def write_artifacts(artifact: dict[str, Any], out_json: Path, out_md: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(artifact, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    with open(out_md, "w", encoding="utf-8") as fh:
        fh.write(render_markdown(artifact))


def run(
    db_path: Path | str,
    p540b_json_path: Path | str,
) -> dict[str, Any]:
    expected = load_p540b_expectations(p540b_json_path)
    db_before = {
        "sha256": _file_sha256(db_path),
        "mtime_epoch": _file_mtime_epoch(db_path),
        "size_bytes": Path(db_path).stat().st_size,
    }
    conn = _open_ro(db_path)
    try:
        observed = collect_observed(conn, expected["controlled_apply_id"])
    finally:
        conn.close()
    db_after = {
        "sha256": _file_sha256(db_path),
        "mtime_epoch": _file_mtime_epoch(db_path),
        "size_bytes": Path(db_path).stat().st_size,
    }
    if not observed.get("table_exists", False):
        manifest_match = {
            "controlled_apply_id": expected["controlled_apply_id"],
            "checks": [],
            "all_checks_pass": False,
            "failed_checks": [f"{REPLAY_TABLE} table not found"],
        }
        observed.setdefault("apply_id_total_rows", 0)
    else:
        manifest_match = compare_with_manifest(expected, observed)
    return build_artifact(
        db_path, expected, observed, manifest_match, db_before, db_after
    )


def _default_dated_paths() -> tuple[Path, Path]:
    stamp = date.today().strftime("%Y%m%d")
    return (
        OUTPUT_DIR / f"p540c_daily539_post_replay_refresh_{stamp}.json",
        OUTPUT_DIR / f"p540c_daily539_post_replay_refresh_{stamp}.md",
    )


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(
        description="P540C DAILY_539 post-replay refresh (read-only)"
    )
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--p540b-json", default=str(DEFAULT_P540B_JSON))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    artifact = run(args.db, args.p540b_json)
    write_artifacts(artifact, Path(args.out_json), Path(args.out_md))
    print(f"classification: {artifact['classification']}")
    print(f"json: {args.out_json}")
    print(f"md: {args.out_md}")
    return 0 if artifact["classification"] == CLASSIFICATION_READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
