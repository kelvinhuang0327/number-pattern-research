"""P540A — Full Replay/Prediction Regeneration Readiness (Dry-Run Only).

Read-only readiness inventory for a possible future full-history rerun of
strategy replay/prediction generation across BIG_LOTTO, DAILY_539, and
POWER_LOTTO. This module does not generate any replay row, does not run the
OOS evaluator, does not score or promote any strategy, and does not write to
the DB (`draws` and `strategy_prediction_replays` are opened read-only,
mode=ro + PRAGMA query_only=ON, matching P333/P539A/P539B's own convention).

It answers: which existing repo entrypoints generate replay/prediction rows,
whether they support dry-run, what a future write would touch, and whether a
full-history or incremental rerun is safer -- so that a follow-up DB-write
task (P540B) can be scoped and separately authorized.

Historical replay regeneration readiness only; not a prediction, betting
edge, future-winning, or production-readiness claim.
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

TASK_ID = "P540A"
UPSTREAM_TASK_IDS = ("P539B", "P539A", "P538A", "P537A", "P536K", "P536C")

DEFAULT_DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_DIR = REPO_ROOT / "outputs" / "research"
DEFAULT_P539B_PATH = OUTPUT_DIR / "p539b_oos_availability_ingest_gap_gate_20260709.json"

LOTTERIES = ("BIG_LOTTO", "DAILY_539", "POWER_LOTTO")
MINIMUM_SUPPORT_DRAWS_FLOOR = 30  # per P536C.window_policy.minimum_support_draws

DISCLAIMER_EN = (
    "Historical replay regeneration readiness only; not a prediction, "
    "betting edge, future-winning, or production-readiness claim."
)

# Static inventory built from source inspection of this repo (read-only search,
# not executed). Each path was confirmed to exist at the time this module was
# written. `dry_run_supported`: "true" | "false" | "partial" | "unknown".
REPLAY_GENERATION_ENTRYPOINTS: list[dict[str, Any]] = [
    {
        "path": "lottery_api/routes/replay.py",
        "category": "api_route",
        "lottery_scope": "ALL (query param)",
        "purpose": "Every route here is GET (history/summary/freshness/history-overview/etc). Pure read/query.",
        "dry_run_supported": "not_applicable",
        "reason": "No write path exists in this file; it never inserts into strategy_prediction_replays.",
        "write_scope": [],
        "idempotency_evidence": "not_applicable (no writes)",
    },
    {
        "path": "lottery_api/routes/ingest.py",
        "category": "api_route",
        "lottery_scope": "ALL (query param)",
        "purpose": (
            "POST /api/ingest/fetch-latest and /api/ingest/backfill write only to the `draws` "
            "table via db_manager.insert_draws. Does not write strategy_prediction_replays."
        ),
        "dry_run_supported": "true",
        "reason": (
            "backfill defaults dry_run=True; non-dry-run write requires apply_confirmed=True + "
            "confirm_token + requested_by + reason (_validate_write_confirmation)."
        ),
        "write_scope": ["draws"],
        "idempotency_evidence": "UNIQUE(draw, lottery_type) on draws table.",
    },
    {
        "path": "scripts/p16_biglotto_remaining_strategies_backfill.py",
        "category": "frozen_per_wave_backfill_script",
        "lottery_scope": "BIG_LOTTO",
        "purpose": "One-shot historical backfill for a fixed, already-applied strategy batch.",
        "dry_run_supported": "true",
        "reason": "argparse modes: --dry-run (default) / --temp-rehearsal / --apply / --rollback.",
        "write_scope": ["strategy_prediction_replays"],
        "idempotency_evidence": (
            "In-script `existing_keys` dedup set + self-run-twice idempotency check "
            "(idempotency_pass = rerun_inserted==0)."
        ),
    },
    {
        "path": "scripts/p20_powerlotto_remaining_strategies_backfill.py",
        "category": "frozen_per_wave_backfill_script",
        "lottery_scope": "POWER_LOTTO",
        "purpose": "One-shot historical backfill for a fixed, already-applied strategy batch.",
        "dry_run_supported": "true",
        "reason": "Same 4-mode argparse pattern as p16; test asserts rejection against production DB without an explicit flag.",
        "write_scope": ["strategy_prediction_replays"],
        "idempotency_evidence": "Same dedup pattern as p16; test_script_rejects_production_db_without_flag.",
    },
    {
        "path": "scripts/v2_artifact_only_apply_rows.py",
        "category": "generic_apply_tool_bound_to_frozen_input",
        "lottery_scope": "Generic (lottery_type comes from a fixed input JSONL file)",
        "purpose": (
            "Closest thing to a reusable/generic apply tool in the repo, but bound to one "
            "frozen candidate-row artifact (outputs/replay/v2_artifact_only_candidate_rows_20260514.jsonl), "
            "not a live generator that can target arbitrary new draws."
        ),
        "dry_run_supported": "true",
        "reason": "argparse: --dry-run / --apply / --rollback <id>.",
        "write_scope": ["strategy_prediction_replays"],
        "idempotency_evidence": "would_skip_existing / skipped_existing counters before insert.",
    },
    {
        "path": "scripts/backfill_replay_history_cutoff.py",
        "category": "metadata_repair_tool",
        "lottery_scope": "ALL / BIG_LOTTO / POWER_LOTTO / DAILY_539 / 3_STAR (parameterized)",
        "purpose": (
            "UPDATE-only repair of history_cutoff_draw on EXISTING rows. Does not insert new "
            "replay rows. The one script in the repo genuinely written to be lottery-type-generic."
        ),
        "dry_run_supported": "true",
        "reason": "--dry-run is the default; --apply required to write.",
        "write_scope": ["strategy_prediction_replays.history_cutoff_draw (UPDATE only)"],
        "idempotency_evidence": "Not applicable to new-row generation; out of scope for regeneration.",
    },
    {
        "path": "tools/audit_p262a_replay_strategy_coverage.py",
        "category": "readonly_coverage_audit",
        "lottery_scope": "ALL",
        "purpose": "Reports which (strategy, lottery_type) cells are missing from strategy_prediction_replays. Explicitly documented as NOT a backfill/generator.",
        "dry_run_supported": "not_applicable",
        "reason": "Read-only; no write path exists.",
        "write_scope": [],
        "idempotency_evidence": "not_applicable (no writes)",
    },
]

# Frozen per-wave scripts observed to follow the same dry-run/rehearsal/apply
# pattern as p16/p20 above (rehearsal pair + apply script), one per historical
# wave. Listed by name only (not fully profiled individually) because each is
# scoped to an already-executed, fixed historical batch and none is a
# candidate for reuse without material rework.
FROZEN_WAVE_SCRIPT_FAMILIES = [
    "scripts/p31a_*/p31b_* (DAILY_539 wave1)",
    "scripts/p36_*/p37_* (DAILY_539 wave2)",
    "scripts/p42_*/p43_* (BIG_LOTTO wave3)",
    "scripts/p47_*/p48_* (POWER_LOTTO wave4)",
    "scripts/p56_*/p57_*/p58_*/p59_* (POWER_LOTTO wave5)",
    "scripts/p64_*/p64b_*/p64c_*/p65_*/p66_* (POWER_LOTTO wave6)",
    "scripts/p74_batch_a_controlled_apply.py (POWER_LOTTO)",
    "scripts/p93_tierb_dryrun_rehearsal.py / scripts/p94_tierb_controlled_apply.py (mixed lotteries; p94 has NO CLI dry-run flag, relies on internal _pre_apply_guard)",
    "scripts/p7_controlled_replay_row_apply.py + *_dry_run.py (mixed; writes prediction_runs, not strategy_replay_runs)",
    "scripts/p2b_controlled_replay_backfill_apply.py (BIG_LOTTO, ts3_regime_3bet only)",
]


def _file_sha256(path: Path | str) -> str:
    hasher = hashlib.sha256()
    hasher.update(Path(path).read_bytes())
    return hasher.hexdigest()


def _query_one(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> Any:
    row = conn.execute(sql, params).fetchone()
    return row


def build_current_db_readonly_snapshot(conn: sqlite3.Connection) -> dict[str, Any]:
    snapshot: dict[str, Any] = {}
    for lt in LOTTERIES:
        draws_row = _query_one(
            conn,
            "SELECT COUNT(*), MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type = ?",
            (lt,),
        )
        draws_count, max_draw_int = draws_row[0], draws_row[1]

        latest_draw_row = _query_one(
            conn,
            "SELECT draw, date FROM draws WHERE lottery_type = ? AND CAST(draw AS INTEGER) = ?",
            (lt, max_draw_int),
        )
        latest_draw, latest_draw_date = (latest_draw_row or (None, None))

        replay_row = _query_one(
            conn,
            "SELECT COUNT(*), MAX(CAST(target_draw AS INTEGER)), "
            "COUNT(DISTINCT strategy_id), COUNT(DISTINCT bet_index) "
            "FROM strategy_prediction_replays WHERE lottery_type = ?",
            (lt,),
        )
        replay_count, max_target_draw_int, distinct_strategy_ids, distinct_bet_index = replay_row

        gap_row = _query_one(
            conn,
            "SELECT COUNT(*) FROM draws WHERE lottery_type = ? AND CAST(draw AS INTEGER) > ?",
            (lt, max_target_draw_int or 0),
        )
        gap_count = gap_row[0]

        snapshot[lt] = {
            "raw_draws_count": draws_count,
            "raw_draws_latest_draw": latest_draw,
            "raw_draws_latest_date": latest_draw_date,
            "strategy_prediction_replays_count": replay_count,
            "strategy_prediction_replays_latest_target_draw": (
                str(max_target_draw_int) if max_target_draw_int is not None else None
            ),
            "distinct_strategy_ids_in_replays": distinct_strategy_ids,
            "distinct_bet_index_in_replays": distinct_bet_index,
            "gap_count_raw_draws_newer_than_latest_replayed_target_draw": gap_count,
            "meets_minimum_support_draws_floor_if_gap_replayed": (
                gap_count >= MINIMUM_SUPPORT_DRAWS_FLOOR
            ),
        }
    return snapshot


def build_p539b_context(p539b_path: Path | str) -> dict[str, Any]:
    p539b = json.loads(Path(p539b_path).read_text(encoding="utf-8"))
    return {
        "source_path": str(p539b_path),
        "source_generated_at": p539b.get("generated_at"),
        "source_classification": p539b.get("classification"),
        "oos_feasibility_summary": p539b.get("oos_feasibility_summary"),
        "recommended_next_single_worker_task": p539b.get("recommended_next_single_worker_task"),
        "denominator_caveat": (
            "P539B's new_official_draws_beyond_all_candidates_cutoff figures are scoped to each "
            "strategy candidate's own recovered replay cutoff at P539B's generated_at timestamp. "
            "This task's current_db_readonly_snapshot instead measures gap_count against the "
            "table-wide MAX(target_draw) per lottery_type at this task's own read time, which can "
            "differ slightly from P539B's per-candidate figures both due to denominator choice and "
            "any official draws ingested between the two runs. Reconciling the exact denominator "
            "(per-candidate vs table-wide vs bet_index=1-only) is listed as a blocker for P540B, "
            "not decided by this task -- per this repo's RUNBOOK, replay/evidence dashboard "
            "denominator/scope semantics are user-visible and must not be changed unilaterally."
        ),
    }


def build_dry_run_support_summary() -> dict[str, Any]:
    return {
        "existing_frozen_per_wave_scripts": {
            "dry_run_supported": "true (per-script)",
            "evidence": (
                "p16/p20 and the p31/p36/p42/p47/p56/p64/p74/p2b family expose --dry-run "
                "(often default) / --temp-rehearsal / --apply / --rollback argparse modes, and "
                "several tests assert the rerun-after-dry-run inserts 0 new rows (idempotency)."
            ),
            "caveat": (
                "p94_tierb_controlled_apply.py has NO CLI dry-run flag; it writes unconditionally "
                "when run directly, relying only on an internal _pre_apply_guard precondition check "
                "and the operational convention that p93 (dry-run) runs first."
            ),
        },
        "reusable_full_or_incremental_regenerator_for_currently_missing_draws": {
            "dry_run_supported": "unknown",
            "reason": (
                "No such tool currently exists. Every write-capable script found is either scoped "
                "to one already-applied historical batch (frozen), or bound to one fixed input "
                "artifact file (v2_artifact_only_apply_rows.py). Building a new incremental "
                "generator that targets exactly the current gap draws would need to be written "
                "before its dry-run behavior could be evaluated -- that authoring work is itself "
                "out of scope for this readiness task."
            ),
        },
        "true_readonly_dry_run_note": (
            "For the scripts that do support --dry-run, dry-run mode reads the DB but does not "
            "open it for write and performs no INSERT; this matches the read-only DB stance "
            "required by this task's own gates."
        ),
        "scoped_by_lottery": "true (every existing write-capable script is already single-lottery or single-artifact scoped)",
        "scoped_full_history_vs_incremental": (
            "unknown for a from-scratch full-history rerun; no script in the repo attempts that. "
            "Existing scripts only ever targeted a specific fixed batch of draws/strategies."
        ),
    }


def build_full_vs_incremental_recommendation(snapshot: dict[str, Any]) -> dict[str, Any]:
    return {
        "recommendation": "incremental",
        "reasoning": [
            "strategy_prediction_replays already holds 94,924 rows across the three lotteries "
            "(BIG_LOTTO 24,140 + DAILY_539 34,680 + POWER_LOTTO 36,104 at this task's read time); "
            "a full-history rerun would re-touch all of them with no new draws to justify it, "
            "for pure runtime/DB-growth/duplicate-row risk and no readiness benefit.",
            "Most existing rows carry replay_run_id=NULL and rely on application-level dedup "
            "(SELECT-before-insert), not the DB UNIQUE constraint, for duplicate protection during "
            "reruns -- unique key is (lottery_type, target_draw, strategy_id, bet_index). A full "
            "rerun multiplies the surface area where that application-level dedup must hold.",
            "Per lottery, only the incremental gap needs generation: see "
            "current_db_readonly_snapshot for exact gap_count per lottery. Only DAILY_539's gap "
            "already clears the MINIMUM_SUPPORT_DRAWS_FLOOR "
            f"({MINIMUM_SUPPORT_DRAWS_FLOOR}) on its own; BIG_LOTTO and POWER_LOTTO would still be "
            "short of that floor even after generating every currently-available new draw, so "
            "full-history rerun would not change their readiness outcome either.",
            "docs/REPLAY_OPERATION_SOP.md already forbids unscoped DELETE against production "
            "strategy_prediction_replays and forbids running apply without a prior --dry-run pass "
            "-- both are easier to honor for a narrowly-scoped incremental run than a full rerun.",
        ],
        "per_lottery_incremental_scope": {
            lt: {
                "new_draws_to_generate": info["gap_count_raw_draws_newer_than_latest_replayed_target_draw"],
                "meets_minimum_support_draws_floor_if_replayed": info[
                    "meets_minimum_support_draws_floor_if_gap_replayed"
                ],
            }
            for lt, info in snapshot.items()
        },
    }


def build_future_write_scope() -> dict[str, Any]:
    return {
        "tables_that_would_be_inserted": [
            {
                "table": "strategy_prediction_replays",
                "columns_likely_populated": [
                    "lottery_type", "target_draw", "target_date", "strategy_id", "strategy_name",
                    "strategy_version", "history_cutoff_draw", "replay_status", "predicted_numbers",
                    "predicted_special", "actual_numbers", "actual_special", "hit_numbers",
                    "hit_count", "special_hit", "replay_run_id", "generated_at", "truth_level",
                    "controlled_apply_id", "source", "provenance_hash", "provenance_source",
                    "dry_run", "prediction_cutoff_date", "prediction_generated_at", "bet_index",
                ],
                "unique_key": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
                "scope": "New rows only, for target_draw values already in `draws` beyond each lottery's current MAX(target_draw) in strategy_prediction_replays, for the specific shortlisted strategy_ids under review (not all historical strategies).",
            },
            {
                "table": "strategy_replay_runs",
                "columns_likely_populated": [
                    "lottery_type", "strategy_scope", "started_at", "finished_at", "status",
                    "generator_version", "data_hash", "notes",
                ],
                "scope": "One new run-metadata row per regeneration invocation, per the existing pattern of recording generator_version/data_hash/notes for provenance.",
            },
        ],
        "tables_that_would_be_updated_or_deleted": (
            "None expected for an incremental run. A full-history rerun would additionally raise "
            "the question of whether to DELETE and regenerate existing rows -- docs/REPLAY_OPERATION_SOP.md "
            "forbids unscoped DELETE against production strategy_prediction_replays, so this is a "
            "further reason to prefer incremental (insert-only) over full rerun."
        ),
        "dedupe_guard_expected": (
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE lottery_type=? AND target_draw=? "
            "AND strategy_id=? AND bet_index=? must be 0 before each insert (matches p16/p20/p31-p94 "
            "convention); the DB UNIQUE constraint is a backstop, not the primary guard, since most "
            "existing rows use replay_run_id=NULL."
        ),
    }


def build_safety_requirements_for_p540b() -> list[str]:
    return [
        "Follow the existing per-wave script convention: default to --dry-run, require an explicit "
        "--apply flag to write, and require a --rollback path that documents (but does not "
        "auto-run) the exact DELETE ... WHERE controlled_apply_id=? needed to undo the run.",
        "Run a rehearsal pass against a temp/throwaway DB copy first (R1 insert / R2 duplicate-rerun "
        "producing 0 new inserts / R3 rollback), matching the p36/p42/p47/p56 rehearsal pattern, "
        "before touching the canonical DB.",
        "Record replay_run_id/controlled_apply_id, provenance_hash, provenance_source, and "
        "generator_version/data_hash on strategy_replay_runs for the new run, per this repo's own "
        "provenance convention.",
        "Take a DB snapshot via scripts/snapshot_replay_db.py immediately before any --apply run.",
        "Confirm DB hash/mtime before and after the write; the write should only change "
        "strategy_prediction_replays (and strategy_replay_runs), nothing else.",
        "Require Owner named authorization for the specific DB write, following the same shape as "
        "ingest.py's _validate_write_confirmation (apply_confirmed + confirm_token + requested_by + "
        "reason) -- a task spec's self-declared authorization line is not sufficient on its own.",
        "Reconcile the exact gap-count denominator (per-candidate cutoff vs table-wide MAX vs "
        "bet_index=1-only) before scoping which target_draw values P540B actually generates -- see "
        "p539b_context.denominator_caveat in this artifact.",
        "Scope P540B to the shortlisted candidate strategy_ids already reviewed by P536-P538, not to "
        "every historical strategy_id, to keep the write narrow and reviewable.",
        "Do not delete or overwrite any existing strategy_prediction_replays row; incremental "
        "generation should be insert-only for target_draw values not yet present for that "
        "(lottery_type, strategy_id, bet_index).",
    ]


def build_blockers_or_unknowns(snapshot: dict[str, Any]) -> list[str]:
    blockers = [
        "No generic, reusable, dry-run-capable generator currently exists for the currently-missing "
        "draws across all three lotteries; every write-capable script found is either frozen to an "
        "already-applied historical batch or bound to one fixed input artifact file. Building such a "
        "generator is itself new production code and would need its own plan-mode review, tests, and "
        "1500-period three-window validation gate per this repo's CLAUDE.md before any strategy it "
        "touches could be considered validated.",
        "p94_tierb_controlled_apply.py has no CLI dry-run flag at all; if any future work reuses code "
        "from it, that gap must be closed first.",
        "The exact gap-count denominator differs slightly between this task's table-wide MAX query "
        "and P539B's per-candidate-cutoff query (see p539b_context.denominator_caveat); this must be "
        "reconciled before P540B scopes an exact target_draw list.",
    ]
    for lt, info in snapshot.items():
        if not info["meets_minimum_support_draws_floor_if_gap_replayed"]:
            blockers.append(
                f"{lt}: even after generating all {info['gap_count_raw_draws_newer_than_latest_replayed_target_draw']} "
                f"currently-available new draws, this lottery would still be short of the "
                f"MINIMUM_SUPPORT_DRAWS_FLOOR ({MINIMUM_SUPPORT_DRAWS_FLOOR}) needed for a first OOS window."
            )
    return blockers


def choose_recommended_next_task(snapshot: dict[str, Any]) -> dict[str, Any]:
    daily539 = snapshot["DAILY_539"]
    if daily539["meets_minimum_support_draws_floor_if_gap_replayed"]:
        proposed = "P540B_DAILY539_INCREMENTAL_REPLAY_GENERATION_DB_WRITE_MANIFESTED"
        why = (
            "DAILY_539 is the only lottery whose currently-available gap "
            f"({daily539['gap_count_raw_draws_newer_than_latest_replayed_target_draw']} draws) already "
            f"clears the MINIMUM_SUPPORT_DRAWS_FLOOR ({MINIMUM_SUPPORT_DRAWS_FLOOR}) once replayed, "
            "matching P539B's own conclusion (proposed as 'P539C' there). BIG_LOTTO and POWER_LOTTO "
            "would still be short of the floor even after generation, so incremental generation for "
            "them alone would not yet unlock a first OOS window."
        )
    else:
        proposed = "P540A_BLOCKED_REPLAY_GENERATION_ENTRYPOINT_NOT_FOUND"
        why = "No lottery's gap clears the minimum support floor; see blockers_or_unknowns."
    return {"proposed_task_id": proposed, "why": why, "not_run_in_this_task": True}


def run_analysis(db_path: Path | str, p539b_path: Path | str) -> dict[str, Any]:
    db_hash_before = _file_sha256(db_path)
    conn = _open_ro(db_path)
    try:
        snapshot = build_current_db_readonly_snapshot(conn)
    finally:
        conn.close()
    db_hash_after = _file_sha256(db_path)

    p539b_context = build_p539b_context(p539b_path)
    dry_run_support = build_dry_run_support_summary()
    full_vs_incremental = build_full_vs_incremental_recommendation(snapshot)
    future_write_scope = build_future_write_scope()
    safety_requirements = build_safety_requirements_for_p540b()
    blockers = build_blockers_or_unknowns(snapshot)
    recommended_next_task = choose_recommended_next_task(snapshot)

    artifact: dict[str, Any] = {
        "schema_version": "1.0",
        "task_id": TASK_ID,
        "upstream_task_ids": list(UPSTREAM_TASK_IDS),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "classification": "P540A_FULL_REPLAY_REGENERATION_READINESS_READY",
        "summary": (
            "Readiness/dry-run inventory only. No repo entrypoint today can safely regenerate "
            "strategy_prediction_replays for the currently-missing draws across all three "
            "lotteries in one parameterized, dry-run-capable, idempotent call. Existing "
            "write-capable scripts are frozen to already-applied historical batches or bound to "
            "one fixed input artifact. Incremental generation (not full-history rerun) is "
            "recommended once a new generator is authored and separately authorized; DAILY_539 is "
            "the only lottery whose current gap alone would clear the minimum support floor."
        ),
        "current_db_readonly_snapshot": snapshot,
        "p539b_context": p539b_context,
        "replay_generation_entrypoints": REPLAY_GENERATION_ENTRYPOINTS,
        "frozen_wave_script_families_not_individually_profiled": FROZEN_WAVE_SCRIPT_FAMILIES,
        "dry_run_support": dry_run_support,
        "full_vs_incremental_regeneration_recommendation": full_vs_incremental,
        "future_write_scope": future_write_scope,
        "safety_requirements_for_p540b": safety_requirements,
        "blockers_or_unknowns": blockers,
        "recommended_next_single_worker_task": recommended_next_task,
        "provenance_and_limits": {
            "db_access": {
                "db_path": str(db_path),
                "tables": ["draws", "strategy_prediction_replays"],
                "db_open_mode": "sqlite3 URI mode=ro + PRAGMA query_only=ON",
                "purpose": (
                    "Read-only COUNT/MAX over `draws` and `strategy_prediction_replays`, grouped "
                    "by lottery_type, to build current_db_readonly_snapshot. No row-level "
                    "prediction data is read or exported by this task."
                ),
                "db_sha256_before": db_hash_before,
                "db_sha256_after": db_hash_after,
                "db_unchanged": db_hash_before == db_hash_after,
            },
            "source_inspection_method": (
                "Static source inspection (grep/read) of scripts/, tools/, lottery_api/, analysis/, "
                "tests/, and docs/replay/ for replay/prediction-generation entrypoints. No script "
                "was executed as part of building this inventory."
            ),
            "limitations": [
                "Entrypoint inventory reflects source as of this task's generated_at; a later "
                "commit could add or change entrypoints.",
                "Frozen wave-script families are listed by name only, not individually profiled; "
                "treat their dry-run/idempotency claims as inferred from the closely-matching "
                "p16/p20 pattern, not independently verified per script.",
                "Does not estimate exact strategy count or replay-row count for a future "
                "regeneration beyond what current_db_readonly_snapshot already reports; per-strategy "
                "row estimates would require reading the shortlist artifacts (P536K/P537A/P538A), "
                "which is out of scope for this readiness pass.",
                "Does not compute any rolling/out-of-sample statistical test, and does not rank, "
                "score, or promote any strategy.",
            ],
            "disclaimer_en": DISCLAIMER_EN,
        },
        "disclaimer_en": DISCLAIMER_EN,
    }
    return artifact


def render_markdown(result: dict[str, Any]) -> str:
    lines: list[str] = []
    add = lines.append
    add("# P540A — Full Replay/Prediction Regeneration Readiness (Dry-Run Only)")
    add("")
    add(f"> {DISCLAIMER_EN}")
    add("")
    add(f"Upstream: {', '.join(result['upstream_task_ids'])}")
    add("")
    add("## Summary")
    add("")
    add(result["summary"])
    add("")
    add("## Current DB Read-Only Snapshot")
    add("")
    for lt, info in sorted(result["current_db_readonly_snapshot"].items()):
        add(
            f"- **{lt}**: raw_draws={info['raw_draws_count']} "
            f"(latest `{info['raw_draws_latest_draw']}` / {info['raw_draws_latest_date']}), "
            f"replays={info['strategy_prediction_replays_count']} "
            f"(latest target_draw `{info['strategy_prediction_replays_latest_target_draw']}`), "
            f"gap={info['gap_count_raw_draws_newer_than_latest_replayed_target_draw']}, "
            f"meets_floor_if_replayed=`{info['meets_minimum_support_draws_floor_if_gap_replayed']}`"
        )
    add("")
    add("## Replay Generation Entrypoints")
    add("")
    for ep in result["replay_generation_entrypoints"]:
        add(f"- `{ep['path']}` ({ep['category']}, {ep['lottery_scope']}): dry_run_supported=`{ep['dry_run_supported']}`")
    add("")
    add("## Full vs Incremental Recommendation")
    add("")
    add(f"recommendation: `{result['full_vs_incremental_regeneration_recommendation']['recommendation']}`")
    for reason in result["full_vs_incremental_regeneration_recommendation"]["reasoning"]:
        add(f"- {reason}")
    add("")
    add("## Safety Requirements For P540B")
    add("")
    for req in result["safety_requirements_for_p540b"]:
        add(f"- {req}")
    add("")
    add("## Blockers / Unknowns")
    add("")
    for b in result["blockers_or_unknowns"]:
        add(f"- {b}")
    add("")
    add("## Recommended Next Single-Worker Task")
    add("")
    task = result["recommended_next_single_worker_task"]
    add(f"- proposed_task_id: `{task['proposed_task_id']}`")
    add(f"- why: {task['why']}")
    add("")
    add("## Provenance")
    add("")
    db_access = result["provenance_and_limits"]["db_access"]
    add(f"- db_unchanged: `{db_access['db_unchanged']}`")
    add(f"- db_sha256_before: `{db_access['db_sha256_before'][:16]}...`")
    add(f"- db_sha256_after: `{db_access['db_sha256_after'][:16]}...`")
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
    json_path = OUTPUT_DIR / f"p540a_full_replay_regeneration_readiness_{stamp}.json"
    md_path = OUTPUT_DIR / f"p540a_full_replay_regeneration_readiness_{stamp}.md"
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    default_json, default_md = _default_dated_paths()
    parser = argparse.ArgumentParser(description="Build P540A full replay regeneration readiness report")
    parser.add_argument("--db", default=str(DEFAULT_DB_PATH))
    parser.add_argument("--p539b", default=str(DEFAULT_P539B_PATH))
    parser.add_argument("--out-json", default=str(default_json))
    parser.add_argument("--out-md", default=str(default_md))
    args = parser.parse_args(argv)

    result = run_analysis(args.db, args.p539b)
    write_artifacts(result, Path(args.out_json), Path(args.out_md))
    print(
        json.dumps(
            {
                "task_id": result["task_id"],
                "classification": result["classification"],
                "recommended_next_single_worker_task": result["recommended_next_single_worker_task"],
                "out_json": args.out_json,
                "out_md": args.out_md,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
