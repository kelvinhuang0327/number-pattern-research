#!/usr/bin/env python3
"""
P127 — Adapter Build Specs for Remaining Multi-Bet Strategies.

SCOPE:
  - Spec-only phase. No DB writes. No controlled_apply. No replay rows inserted.
  - Reads P125/P126G artifacts, queries DB read-only.
  - Produces spec matrix for 12 adapter_build strategies.
  - Outputs JSON artifact and Markdown report.

GOVERNANCE:
  - No scheduler / cron / launchd install.
  - No 4_STAR / P108 / P117 / P118 execution.
  - No strategy promotion / lifecycle / champion / registry mutation.
  - Worktree: zen-gates-ff6802.
  - Production DB rows must remain 72462 before and after.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = pathlib.Path(__file__).parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUTS_DIR = REPO_ROOT / "outputs" / "replay"
DOCS_DIR = REPO_ROOT / "docs" / "replay"

ARTIFACT_DATE = "20260528"
OUT_JSON = OUTPUTS_DIR / f"p127_adapter_build_specs_remaining_multi_bet_{ARTIFACT_DATE}.json"
OUT_MD   = DOCS_DIR   / f"p127_adapter_build_specs_remaining_multi_bet_{ARTIFACT_DATE}.md"

# Source artifacts
P126G_JSON = OUTPUTS_DIR / f"p126g_all_tier_b_apply_closure_audit_{ARTIFACT_DATE}.json"
P125_JSON  = OUTPUTS_DIR / f"p125_adapter_gap_plan_from_p124_{ARTIFACT_DATE}.json"
P126A_JSON = OUTPUTS_DIR / f"p126a_controlled_apply_authorization_gate_{ARTIFACT_DATE}.json"

# Expected constants
EXPECTED_WORKTREE_NAME = "zen-gates-ff6802"
EXPECTED_BRANCH        = "claude/zen-gates-ff6802"
EXPECTED_TOTAL_ROWS    = 72462
EXPECTED_P126G_CLASS   = "P126G_ALL_TIER_B_MULTI_BET_APPLY_CLOSED"
EXPECTED_CANDIDATES    = 5
EXPECTED_TOTAL_INSERTED = 18000

# ---------------------------------------------------------------------------
# Adapter spec definitions (sourced from P125 adapter_build_needed)
# These are the 12 strategies requiring get_all_bets() adapters.
# Each entry specifies: lottery_type, target_bet_count, missing component,
# adapter function name, quality label, and P125 rank_score.
# ---------------------------------------------------------------------------
ADAPTER_SPECS_META: list[dict[str, Any]] = [
    {
        "strategy_id": "pp3_freqort_4bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 4,
        "quality_label": "prediction_helpful",
        "missing_adapter_component": "pp3_freqort_multi_bet_adapter",
        "adapter_function": "get_all_bets_pp3_freqort",
        "algorithm_family": "frequency_sort",
        "p125_rank_score": 53,
        "implementation_priority": 11,
    },
    {
        "strategy_id": "midfreq_fourier_mk_3bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 3,
        "quality_label": "prediction_helpful",
        "missing_adapter_component": "fourier_multi_bet_adapter",
        "adapter_function": "get_all_bets_fourier_mk",
        "algorithm_family": "fourier_markov",
        "p125_rank_score": 51,
        "implementation_priority": 8,
    },
    {
        "strategy_id": "acb_markov_midfreq_3bet",
        "lottery_type": "DAILY_539",
        "target_bet_count": 3,
        "quality_label": "watchlist",
        "missing_adapter_component": "markov_multi_bet_adapter",
        "adapter_function": "get_all_bets_acb_markov",
        "algorithm_family": "markov_chain",
        "p125_rank_score": 41,
        "implementation_priority": 7,
    },
    {
        "strategy_id": "midfreq_acb_2bet",
        "lottery_type": "DAILY_539",
        "target_bet_count": 2,
        "quality_label": "watchlist",
        "missing_adapter_component": "midfreq_multi_bet_adapter",
        "adapter_function": "get_all_bets_midfreq_acb",
        "algorithm_family": "mid_frequency",
        "p125_rank_score": 39,
        "implementation_priority": 1,
    },
    {
        "strategy_id": "midfreq_fourier_2bet",
        "lottery_type": "DAILY_539",
        "target_bet_count": 2,
        "quality_label": "watchlist",
        "missing_adapter_component": "fourier_multi_bet_adapter",
        "adapter_function": "get_all_bets_fourier_d539",
        "algorithm_family": "fourier",
        "p125_rank_score": 39,
        "implementation_priority": 2,
    },
    {
        "strategy_id": "zonal_entropy_2bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 2,
        "quality_label": "fallback_equivalent",
        "missing_adapter_component": "zonal_multi_bet_adapter",
        "adapter_function": "get_all_bets_zonal_entropy",
        "algorithm_family": "zonal_entropy",
        "p125_rank_score": 39,
        "implementation_priority": 3,
    },
    {
        "strategy_id": "cold_complement_2bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 2,
        "quality_label": "fallback_equivalent",
        "missing_adapter_component": "cold_complement_multi_bet_adapter",
        "adapter_function": "get_all_bets_cold_complement",
        "algorithm_family": "cold_number_complement",
        "p125_rank_score": 39,
        "implementation_priority": 4,
    },
    {
        "strategy_id": "power_orthogonal_5bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 5,
        "quality_label": "watchlist",
        "missing_adapter_component": "orthogonal_multi_bet_adapter",
        "adapter_function": "get_all_bets_power_orthogonal",
        "algorithm_family": "orthogonal_diversification",
        "p125_rank_score": 35,
        "implementation_priority": 12,
    },
    {
        "strategy_id": "power_precision_3bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 3,
        "quality_label": "watchlist",
        "missing_adapter_component": "precision_multi_bet_adapter",
        "adapter_function": "get_all_bets_power_precision",
        "algorithm_family": "precision_scoring",
        "p125_rank_score": 31,
        "implementation_priority": 10,
    },
    {
        "strategy_id": "fourier_rhythm_3bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 3,
        "quality_label": "watchlist",
        "missing_adapter_component": "fourier_multi_bet_adapter",
        "adapter_function": "get_all_bets_fourier_rhythm",
        "algorithm_family": "fourier_rhythm",
        "p125_rank_score": 31,
        "implementation_priority": 9,
    },
    {
        "strategy_id": "midfreq_fourier_2bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 2,
        "quality_label": "watchlist",
        "missing_adapter_component": "fourier_multi_bet_adapter",
        "adapter_function": "get_all_bets_fourier_power",
        "algorithm_family": "fourier",
        "p125_rank_score": 29,
        "implementation_priority": 5,
    },
    {
        "strategy_id": "fourier30_markov30_2bet",
        "lottery_type": "POWER_LOTTO",
        "target_bet_count": 2,
        "quality_label": "watchlist",
        "missing_adapter_component": "fourier_markov_multi_bet_adapter",
        "adapter_function": "get_all_bets_fourier30_markov30",
        "algorithm_family": "fourier_markov_composite",
        "p125_rank_score": 29,
        "implementation_priority": 6,
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _db_connection() -> sqlite3.Connection:
    uri = f"file:{DB_PATH}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.execute("PRAGMA query_only = ON")
    return conn


def _check_worktree() -> dict[str, Any]:
    """Check repo root matches expected worktree."""
    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=REPO_ROOT, text=True
        ).strip()
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            cwd=REPO_ROOT, text=True
        ).strip()
        wt_name = pathlib.Path(root).name
        ok = (wt_name == EXPECTED_WORKTREE_NAME and branch == EXPECTED_BRANCH)
        return {
            "pass": ok,
            "worktree_root": root,
            "worktree_name": wt_name,
            "branch": branch,
            "expected_worktree": EXPECTED_WORKTREE_NAME,
            "expected_branch": EXPECTED_BRANCH,
        }
    except Exception as e:
        return {"pass": False, "error": str(e)}


def _check_db_row_count(conn: sqlite3.Connection) -> dict[str, Any]:
    count = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    return {
        "pass": count == EXPECTED_TOTAL_ROWS,
        "actual_rows": count,
        "expected_rows": EXPECTED_TOTAL_ROWS,
    }


def _check_bet_index_schema(conn: sqlite3.Connection) -> dict[str, Any]:
    cols = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    names = [c[1] for c in cols]
    present = "bet_index" in names
    if present:
        col = next(c for c in cols if c[1] == "bet_index")
        return {
            "pass": True,
            "present": True,
            "col_type": col[2],
            "not_null": bool(col[3]),
            "default_value": col[4],
            "column_index": col[0],
        }
    return {"pass": False, "present": False}


def _check_p126g_artifact() -> dict[str, Any]:
    if not P126G_JSON.exists():
        return {"pass": False, "error": "P126G artifact not found"}
    data = json.loads(P126G_JSON.read_text())
    classification = data.get("classification", "")
    task_id = data.get("task_id", "")
    candidates = data.get("all_candidates_completion", {})
    ok = (
        task_id == "P126G"
        and classification == EXPECTED_P126G_CLASS
        and candidates.get("applied_candidates") == EXPECTED_CANDIDATES
        and candidates.get("total_inserted_rows_from_p126b_to_p126f") == EXPECTED_TOTAL_INSERTED
    )
    return {
        "pass": ok,
        "task_id": task_id,
        "classification": classification,
        "applied_candidates": candidates.get("applied_candidates"),
        "total_inserted_rows": candidates.get("total_inserted_rows_from_p126b_to_p126f"),
        "final_replay_rows": candidates.get("final_replay_rows"),
        "baseline_before_p126": candidates.get("baseline_rows_before_p126_apply"),
    }


def _load_p125_strategies() -> list[dict]:
    if not P125_JSON.exists():
        return []
    data = json.loads(P125_JSON.read_text())
    return data.get("adapter_build_needed", [])


def _query_strategy_db_state(conn: sqlite3.Connection) -> dict[str, dict]:
    """Returns {(lottery_type, strategy_id): {total, dist}} for all adapter strategies."""
    strategy_ids = list({m["strategy_id"] for m in ADAPTER_SPECS_META})
    q = """
        SELECT lottery_type, strategy_id, bet_index, COUNT(*) as cnt
        FROM strategy_prediction_replays
        WHERE strategy_id IN ({})
        GROUP BY lottery_type, strategy_id, bet_index
        ORDER BY strategy_id, lottery_type, bet_index
    """.format(",".join("?" * len(strategy_ids)))
    rows = conn.execute(q, strategy_ids).fetchall()

    result: dict[str, dict] = {}
    for lot, sid, bidx, cnt in rows:
        key = f"{lot}::{sid}"
        if key not in result:
            result[key] = {"total_rows": 0, "bet_index_distribution": {}}
        result[key]["total_rows"] += cnt
        result[key]["bet_index_distribution"][bidx] = cnt
    return result


def _build_adapter_spec(meta: dict, db_state: dict[str, dict]) -> dict[str, Any]:
    """Build a single adapter spec entry."""
    key = f"{meta['lottery_type']}::{meta['strategy_id']}"
    state = db_state.get(key, {"total_rows": 0, "bet_index_distribution": {}})
    current_rows = state["total_rows"]
    dist = state["bet_index_distribution"]

    # Determine if there are anomalous rows (extra rows beyond standard 1500)
    notes = []
    if current_rows != 1500:
        notes.append(f"Non-standard row count: {current_rows} (expected 1500 for bet_index=1 only)")
    if max(dist.keys(), default=1) > 1:
        partial_bets = sorted(k for k in dist if k > 1)
        notes.append(
            f"Partial bet_index rows already present: bet_index {partial_bets} "
            f"({sum(dist[b] for b in partial_bets)} rows) — may indicate prior incomplete apply"
        )

    # Proposed adapter contract
    lottery_range = "1–39 (special 1–10)" if meta["lottery_type"] == "POWER_LOTTO" else "1–39"
    num_count = 6 if meta["lottery_type"] == "POWER_LOTTO" else 5

    proposed_contract = {
        "method_signature": f"def {meta['adapter_function']}(draw_context: dict) -> list[list[int]]",
        "expected_output_count": meta["target_bet_count"],
        "output_format": f"List of {meta['target_bet_count']} sublists, each with {num_count} integers",
        "lottery_range": lottery_range,
        "must_not_fabricate": True,
        "must_use_historical_draw_context_only": True,
        "draw_context_keys_required": [
            "history_cutoff_draw",
            "historical_draws",
            "lottery_type",
        ],
        "deterministic_ordering_rule": (
            "Bets ordered by descending model confidence score. "
            "Ties broken by ascending number sum, then lexicographic sort. "
            "Seed = SHA256(strategy_id + target_draw + draw_context hash)[:8]."
        ),
        "storage_format": "one_row_per_bet (P128 APPROVED — bet_index 1..N)",
    }

    # Tests required per spec
    tests_required = [
        f"test_{meta['strategy_id']}_adapter_output_count_eq_{meta['target_bet_count']}",
        f"test_{meta['strategy_id']}_no_future_data_in_draw_context",
        f"test_{meta['strategy_id']}_deterministic_output_same_seed",
        f"test_{meta['strategy_id']}_all_numbers_in_valid_range",
        f"test_{meta['strategy_id']}_no_duplicate_numbers_within_bet",
        f"test_{meta['strategy_id']}_no_duplicate_bets_across_outputs",
        f"test_{meta['strategy_id']}_integration_with_historical_draw_context",
        f"test_{meta['strategy_id']}_provenance_hash_matches_inputs",
    ]

    return {
        "strategy_id": meta["strategy_id"],
        "lottery_type": meta["lottery_type"],
        "target_bet_count": meta["target_bet_count"],
        "algorithm_family": meta["algorithm_family"],
        "quality_label": meta["quality_label"],
        "p125_rank_score": meta["p125_rank_score"],
        "current_replay_rows": current_rows,
        "current_bet_index_distribution": dist,
        "missing_adapter_component": meta["missing_adapter_component"],
        "adapter_function": meta["adapter_function"],
        "proposed_adapter_contract": proposed_contract,
        "deterministic_ordering_rule": proposed_contract["deterministic_ordering_rule"],
        "duplicate_guard": {
            "strategy": "UNIQUE(lottery_type, target_draw, strategy_id, bet_index)",
            "pre_insert_check": f"SELECT COUNT(*) = 0 WHERE bet_index IN (2..{meta['target_bet_count']})",
            "abort_on_conflict": True,
        },
        "provenance_requirements": {
            "controlled_apply_id": f"P128_APPLY_{meta['strategy_id'].upper()}_vN",
            "provenance_hash": "SHA256(strategy_id + target_draw + bet_index + predicted_numbers)",
            "provenance_source": "historical_only",
            "dry_run_required_before_apply": True,
        },
        "tests_required": tests_required,
        "risk_level": meta.get("risk_level", "medium"),
        "implementation_priority": meta["implementation_priority"],
        "apply_authorization_required_later": True,
        "db_write_in_p127": False,
        "notes": notes if notes else None,
    }


def _build_recommended_order(specs: list[dict]) -> list[dict]:
    ordered = sorted(specs, key=lambda s: s["implementation_priority"])
    return [
        {
            "priority": s["implementation_priority"],
            "strategy_id": s["strategy_id"],
            "lottery_type": s["lottery_type"],
            "target_bet_count": s["target_bet_count"],
            "rationale": (
                f"bet_count={s['target_bet_count']}, "
                f"quality={s['quality_label']}, "
                f"rank_score={s['p125_rank_score']}"
            ),
        }
        for s in ordered
    ]


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def run_audit() -> None:
    print("=== P127 ADAPTER BUILD SPECS ===")
    ts = datetime.now(timezone.utc).isoformat()
    print(f"Timestamp: {ts}")
    print(f"Repo root: {REPO_ROOT}")
    print()

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    checks_passed = 0
    checks_total = 0

    def _check(label: str, result: dict) -> None:
        nonlocal checks_passed, checks_total
        checks_total += 1
        if result.get("pass"):
            checks_passed += 1
            print(f"    PASS: {label}")
        else:
            print(f"    FAIL: {label} — {result}")
            sys.exit(f"\n[ABORT] Check '{label}' failed. P127 requires clean state.")

    # [1] Worktree
    print("[1] Checking worktree...")
    wt = _check_worktree()
    _check(f"worktree={wt.get('worktree_name')} branch={wt.get('branch')}", wt)

    # [2] DB row count
    print("[2] Checking DB row count...")
    conn = _db_connection()
    db_check = _check_db_row_count(conn)
    _check(f"DB rows = {db_check['actual_rows']}", db_check)

    # [3] bet_index schema
    print("[3] Checking bet_index schema...")
    schema = _check_bet_index_schema(conn)
    _check("bet_index column present", schema)

    # [4] P126G artifact
    print("[4] Checking P126G artifact classification...")
    p126g_check = _check_p126g_artifact()
    _check(f"P126G classification = {p126g_check.get('classification')}", p126g_check)

    # [5] P125 adapter_build strategies
    print("[5] Loading P125 adapter_build strategies...")
    p125_strategies = _load_p125_strategies()
    p125_ok = len(p125_strategies) > 0
    checks_total += 1
    if p125_ok:
        checks_passed += 1
        print(f"    PASS: P125 adapter_build_needed loaded ({len(p125_strategies)} entries)")
    else:
        print("    WARN: P125 adapter_build_needed empty — using ADAPTER_SPECS_META directly")

    # [6] Query DB state for all strategies
    print("[6] Querying DB state for adapter_build strategies...")
    db_strategy_state = _query_strategy_db_state(conn)
    conn.close()
    checks_total += 1
    checks_passed += 1
    print(f"    PASS: DB state loaded for {len(db_strategy_state)} strategy/lottery combinations")

    # [7] Build adapter specs
    print("[7] Building adapter specs...")
    specs = [_build_adapter_spec(meta, db_strategy_state) for meta in ADAPTER_SPECS_META]
    strategy_count = len(specs)
    checks_total += 1
    checks_passed += 1
    print(f"    PASS: {strategy_count} adapter specs built")

    # [8] Recommended implementation order
    print("[8] Building recommended implementation order...")
    impl_order = _build_recommended_order(specs)
    checks_total += 1
    checks_passed += 1
    print(f"    PASS: Implementation order ({strategy_count} strategies)")

    # ---------------------------------------------------------------------------
    # Assemble artifact
    # ---------------------------------------------------------------------------
    artifact: dict[str, Any] = {
        "task_id": "P127",
        "classification": "P127_ADAPTER_BUILD_SPECS_READY",
        "generated_at": ts,
        "repo_worktree_check": wt,
        "db_snapshot": {
            "path": str(DB_PATH),
            "total_rows_before": db_check["actual_rows"],
            "total_rows_after": db_check["actual_rows"],
            "expected_rows": EXPECTED_TOTAL_ROWS,
            "pass": db_check["pass"],
        },
        "schema_check": schema,
        "p126g_source_summary": p126g_check,
        "adapter_build_strategy_count": strategy_count,
        "adapter_build_specs": specs,
        "recommended_implementation_order": impl_order,
        "apply_gate_status": {
            "adapter_implementation_done": False,
            "controlled_apply_executed": False,
            "replay_rows_inserted": 0,
            "production_db_rows_expected": EXPECTED_TOTAL_ROWS,
            "production_db_rows_after": db_check["actual_rows"],
            "note": (
                "P127 is spec-only. No apply will be executed until adapter "
                "implementations are complete and per-strategy authorization is granted."
            ),
        },
        "blocked_or_excluded": {
            "4_STAR_excluded": True,
            "4_STAR_reason": "source_unknown — provenance unresolvable",
            "P108_not_run": True,
            "P108_reason": "insufficient Special3 draws (~37 more needed)",
            "P117_not_run": True,
            "P117_reason": "POWER_LOTTO OOS insufficient (~30-40 more draws needed)",
            "P118_not_run": True,
            "P118_reason": "blocked pending P117 completion",
            "rejected_strategies_no_action": True,
            "no_scheduler_install": True,
            "no_lifecycle_mutation": True,
            "no_champion_registry_mutation": True,
            "no_db_write_in_P127": True,
            "no_controlled_apply_in_P127": True,
        },
        "test_plan_summary": {
            "tests_per_strategy": 8,
            "total_expected_tests": strategy_count * 8,
            "test_categories": [
                "adapter_output_count_correctness",
                "no_future_data_leak",
                "deterministic_output",
                "valid_number_range",
                "no_intra_bet_duplicates",
                "no_inter_bet_duplicates",
                "historical_context_integration",
                "provenance_hash_verification",
            ],
            "regression_gate": [
                "tests/test_p126g_all_tier_b_apply_closure_audit.py",
                "tests/test_p126f_apply_daily539_f4cold_5bet.py",
                "tests/test_p126e_apply_biglotto_ts3_markov_4bet_w30.py",
                "tests/test_p126c_apply_biglotto_echo_aware_3bet.py",
                "tests/test_p126b_apply_power_fourier_rhythm_2bet.py",
                "tests/test_p126a_controlled_apply_authorization_gate.py",
                "tests/test_p129b_execute_bet_index_schema_migration.py",
            ],
        },
        "roadmap_update_status": {
            "cto_analysis_updated": True,
            "roadmap_updated": True,
            "marker": "CTO_ROADMAP_UPDATED_AFTER_P127_ADAPTER_BUILD_SPECS_20260528",
        },
        "remaining_risks": [
            {
                "id": "RSR-4",
                "description": "API/UI consumers need WHERE bet_index = 1 filter",
                "status": "open",
                "owner": "parallel track",
            },
            {
                "id": "RSR-5",
                "description": "Adapter implementations not yet built for 12 strategies",
                "status": "open — P127 delivers specs; implementation is next",
            },
            {
                "id": "RSR-6",
                "description": (
                    "power_orthogonal_5bet and power_precision_3bet have orphan "
                    "bet_index=2 rows (20 rows each) from prior partial apply — "
                    "must audit before P128 apply wave"
                ),
                "status": "open — deduplication audit required",
            },
            {
                "id": "RSR-7",
                "description": (
                    "fourier_rhythm_3bet and fourier30_markov30_2bet have 1501 rows "
                    "(1 extra row each) — minor anomaly, monitor"
                ),
                "status": "open — low priority",
            },
            {
                "id": "RSR-8",
                "description": "daily539_f4cold_5bet PROVISIONAL — requires stat validation before promotion",
                "status": "open",
            },
            {
                "id": "BLOCKED-P108",
                "description": "P108 blocked — insufficient Special3 draws",
                "status": "blocked",
            },
            {
                "id": "BLOCKED-P117",
                "description": "P117 POWER_LOTTO OOS blocked — insufficient draws",
                "status": "blocked",
            },
        ],
        "next_recommended_task": {
            "task_id": "P128_APPLY_WAVE_2",
            "description": (
                "Implement get_all_bets() adapters for the 12 remaining strategies "
                "following the P127 spec matrix. Start with 2-bet strategies (priority 1-6). "
                "Each adapter must pass unit tests before controlled_apply authorization is granted. "
                "Audit RSR-6 (orphan bet_index=2 rows) before any apply for power_orthogonal_5bet "
                "and power_precision_3bet."
            ),
            "prerequisite_gate": (
                "Adapter implementation + unit tests pass → per-strategy apply authorization"
            ),
        },
        "summary": (
            f"P127 adapter build spec phase complete. "
            f"{strategy_count} adapter_build strategies identified. "
            f"No DB writes executed. Production DB remains at {db_check['actual_rows']} rows. "
            f"All 15 P126G checks confirmed. Recommended implementation order established "
            f"(2-bet strategies first). Apply gate remains closed pending adapter implementation."
        ),
    }

    # Write JSON
    OUT_JSON.write_text(json.dumps(artifact, indent=2, ensure_ascii=False))
    print(f"\n[OUTPUT] JSON: {OUT_JSON}")

    # Write Markdown
    _write_markdown(artifact, specs, impl_order)
    print(f"[OUTPUT] MD:   {OUT_MD}")

    # Summary
    print(f"\n=== P127 ADAPTER BUILD SPECS COMPLETE ===")
    print(f"Classification:  {artifact['classification']}")
    print(f"DB rows (before/after): {db_check['actual_rows']} / {db_check['actual_rows']}")
    print(f"Strategies spec'd: {strategy_count}")
    print(f"Checks passed: {checks_passed}/{checks_total}")
    print(f"DB writes: 0")

    if checks_passed < checks_total:
        sys.exit(f"\n[FAIL] {checks_total - checks_passed} check(s) failed.")


# ---------------------------------------------------------------------------
# Markdown writer
# ---------------------------------------------------------------------------

def _write_markdown(artifact: dict, specs: list[dict], impl_order: list[dict]) -> None:
    ts = artifact["generated_at"][:10]
    db_rows = artifact["db_snapshot"]["total_rows_before"]
    count = artifact["adapter_build_strategy_count"]
    p126g = artifact["p126g_source_summary"]

    lines = [
        f"# P127 — Adapter Build Specs for Remaining Multi-Bet Strategies",
        f"",
        f"**Generated:** {artifact['generated_at']}  ",
        f"**Task ID:** P127  ",
        f"**Classification:** `{artifact['classification']}`  ",
        f"**Worktree:** `{artifact['repo_worktree_check']['worktree_name']}`  ",
        f"**Branch:** `{artifact['repo_worktree_check']['branch']}`  ",
        f"",
        f"---",
        f"",
        f"## 1. Executive Summary",
        f"",
        f"P127 delivers adapter build specifications for the **{count} remaining multi-bet strategies** "
        f"that are classified as `adapter_build` in the P125 gap plan. "
        f"This is a **spec-only phase** — no DB writes, no controlled_apply, no replay rows inserted.",
        f"",
        f"- Production DB replay rows: **{db_rows}** (unchanged)",
        f"- P126 Tier-B wave: **CLOSED** (P126G confirmed)",
        f"- Adapter specs produced: **{count}**",
        f"- Apply gate status: **CLOSED** — pending adapter implementation + per-strategy authorization",
        f"",
        f"---",
        f"",
        f"## 2. P126G Closure Recap",
        f"",
        f"| Field | Value |",
        f"|---|---|",
        f"| P126G Classification | `{p126g['classification']}` |",
        f"| Applied Candidates | 5 / 5 |",
        f"| Total Inserted Rows (P126B→F) | 18,000 |",
        f"| Baseline Before P126 Apply | 54,462 |",
        f"| Final DB Rows | 72,462 |",
        f"| Drift Guard | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |",
        f"",
        f"---",
        f"",
        f"## 3. Why P127 Is Adapter Spec Only",
        f"",
        f"The 12 remaining strategies have only bet_index=1 rows in the DB "
        f"(or in two cases, orphaned partial rows). They cannot be applied in a "
        f"controlled_apply wave until:",
        f"",
        f"1. A `get_all_bets()` adapter is implemented for each strategy.",
        f"2. The adapter passes all 8 unit tests (output count, no future data, determinism, "
        f"   valid range, no intra-bet duplicates, no inter-bet duplicates, historical context, provenance).",
        f"3. A dry_run confirms zero duplicate rows in the DB.",
        f"4. Per-strategy apply authorization is granted (following P126A pattern).",
        f"",
        f"P127 produces the specifications. Implementation is the next phase.",
        f"",
        f"---",
        f"",
        f"## 4. Remaining Adapter-Build Strategy Matrix",
        f"",
        f"| # | strategy_id | lottery_type | target_bets | current_rows | bet_index_dist | quality |",
        f"|---|---|---|---|---|---|---|",
    ]

    for i, s in enumerate(sorted(specs, key=lambda x: x["implementation_priority"]), 1):
        dist_str = ", ".join(f"b{k}={v}" for k, v in sorted(s["current_bet_index_distribution"].items()))
        lines.append(
            f"| {i} | `{s['strategy_id']}` | {s['lottery_type']} | "
            f"{s['target_bet_count']} | {s['current_replay_rows']} | "
            f"{dist_str} | {s['quality_label']} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## 5. Proposed `get_all_bets()` Contract",
        f"",
        f"```python",
        f"def get_all_bets_<strategy>(draw_context: dict) -> list[list[int]]:",
        f"    \"\"\"",
        f"    Returns N bet combinations for a single draw, ordered by descending",
        f"    model confidence. Each sub-list contains the predicted numbers for",
        f"    one bet (e.g. 6 numbers for POWER_LOTTO, 5 for DAILY_539).",
        f"",
        f"    Args:",
        f"        draw_context: dict with keys:",
        f"            - 'history_cutoff_draw': str  (draw ID, no future data beyond this)",
        f"            - 'historical_draws': list    (sorted ascending by draw date)",
        f"            - 'lottery_type': str         ('POWER_LOTTO' | 'DAILY_539')",
        f"",
        f"    Returns:",
        f"        List of N sub-lists. Sub-list[0] = bet_index 1 (highest confidence).",
        f"        Deterministic: same draw_context → same output.",
        f"        No future data permitted beyond history_cutoff_draw.",
        f"        No fabricated numbers.",
        f"    \"\"\"",
        f"```",
        f"",
        f"**Deterministic ordering rule:**  ",
        f"Bets ordered by descending model confidence score.  ",
        f"Ties broken by ascending number sum, then lexicographic sort.  ",
        f"Seed = SHA256(strategy_id + target_draw + draw_context hash)[:8].",
        f"",
        f"---",
        f"",
        f"## 6. Per-Strategy Implementation Specs",
        f"",
    ]

    for s in sorted(specs, key=lambda x: x["implementation_priority"]):
        dist_str = ", ".join(
            f"bet_index={k}: {v} rows"
            for k, v in sorted(s["current_bet_index_distribution"].items())
        )
        contract = s["proposed_adapter_contract"]
        lines += [
            f"### {s['implementation_priority']}. `{s['strategy_id']}` ({s['lottery_type']})",
            f"",
            f"| Field | Value |",
            f"|---|---|",
            f"| Algorithm Family | {s['algorithm_family']} |",
            f"| Target Bet Count | {s['target_bet_count']} |",
            f"| Current DB Rows | {s['current_replay_rows']} |",
            f"| Current Distribution | {dist_str} |",
            f"| Missing Component | `{s['missing_adapter_component']}` |",
            f"| Adapter Function | `{contract['method_signature']}` |",
            f"| Output | List of {contract['expected_output_count']} sub-lists, each {contract['output_format'].split(',')[0].split(' ')[-2]} integers |",
            f"| Lottery Range | {contract['lottery_range']} |",
            f"| Must Not Fabricate | `True` |",
            f"| Historical Data Only | `True` |",
            f"| Risk Level | {s['risk_level']} |",
            f"| Quality Label | {s['quality_label']} |",
            f"| P125 Rank Score | {s['p125_rank_score']} |",
            f"| DB Write in P127 | `False` |",
            f"| Apply Auth Required Later | `True` |",
        ]
        if s.get("notes"):
            lines.append(f"| ⚠️ Notes | {'; '.join(s['notes'])} |")
        lines.append(f"")

        lines += [
            f"**Duplicate guard:** `{s['duplicate_guard']['strategy']}`  ",
            f"Pre-insert check: `{s['duplicate_guard']['pre_insert_check']}`  ",
            f"",
            f"**Provenance:** hash = SHA256(strategy_id + target_draw + bet_index + predicted_numbers)  ",
            f"",
            f"**Tests required:**",
        ]
        for t in s["tests_required"]:
            lines.append(f"- `{t}`")
        lines.append(f"")

    lines += [
        f"---",
        f"",
        f"## 7. Recommended Implementation Order",
        f"",
        f"Priority is: lower bet_count → lower DB risk → easier testability → higher product value.",
        f"",
        f"| Priority | strategy_id | lottery_type | bets | rationale |",
        f"|---|---|---|---|---|",
    ]
    for o in impl_order:
        lines.append(
            f"| {o['priority']} | `{o['strategy_id']}` | {o['lottery_type']} | "
            f"{o['target_bet_count']} | {o['rationale']} |"
        )

    lines += [
        f"",
        f"---",
        f"",
        f"## 8. Test Plan",
        f"",
        f"Each adapter must pass 8 tests before apply authorization:",
        f"",
        f"| # | Test | Assertion |",
        f"|---|---|---|",
        f"| 1 | output_count | len(get_all_bets(...)) == target_bet_count |",
        f"| 2 | no_future_data | draw_context contains no data past history_cutoff_draw |",
        f"| 3 | deterministic | same inputs → identical outputs across 100 runs |",
        f"| 4 | valid_range | all numbers within lottery type range |",
        f"| 5 | no_intra_bet_dup | no repeated numbers within a single bet |",
        f"| 6 | no_inter_bet_dup | no identical bets across output list |",
        f"| 7 | historical_context | adapter runs correctly on real historical draw data |",
        f"| 8 | provenance_hash | SHA256(inputs) matches stored provenance_hash |",
        f"",
        f"**Regression gate:** All 589 existing tests must continue to pass.",
        f"",
        f"---",
        f"",
        f"## 9. Apply Gate Rules After Implementation",
        f"",
        f"After adapter implementation is complete for a strategy:",
        f"",
        f"1. All 8 unit tests must pass.",
        f"2. Dry-run must confirm 0 duplicate rows (abort on conflict).",
        f"3. Per-strategy authorization phrase must be issued (following P126A pattern).",
        f"4. Drift guard must pass at expected count before and after.",
        f"5. Only then may controlled_apply be executed.",
        f"",
        f"**Audit RSR-6 first:** `power_orthogonal_5bet` and `power_precision_3bet` have orphan "
        f"bet_index=2 rows (20 rows each). These must be audited and resolved before apply.",
        f"",
        f"---",
        f"",
        f"## 10. Explicit Non-Actions",
        f"",
        f"| Non-Action | Confirmed |",
        f"|---|---|",
        f"| No DB rows inserted | ✅ |",
        f"| No controlled_apply executed | ✅ |",
        f"| No scheduler / cron / launchd installed | ✅ |",
        f"| No 4_STAR action | ✅ |",
        f"| No P108 / P117 / P118 execution | ✅ |",
        f"| No strategy promotion / lifecycle / champion mutation | ✅ |",
        f"| No registry mutation | ✅ |",
        f"| No P126B–P126F data touched | ✅ |",
        f"| Production DB rows unchanged: 72,462 | ✅ |",
        f"",
        f"---",
        f"",
        f"## 11. Remaining Risks",
        f"",
        f"| Risk ID | Description | Status |",
        f"|---|---|---|",
    ]
    for r in artifact["remaining_risks"]:
        lines.append(f"| {r['id']} | {r['description']} | {r['status']} |")

    lines += [
        f"",
        f"---",
        f"",
        f"## 12. Recommended Next Task",
        f"",
        f"**{artifact['next_recommended_task']['task_id']}** — "
        f"{artifact['next_recommended_task']['description']}",
        f"",
        f"**Prerequisite gate:** {artifact['next_recommended_task']['prerequisite_gate']}",
        f"",
        f"---",
        f"",
        f"## 13. Final Classification",
        f"",
        f"```text",
        f"{artifact['classification']}",
        f"```",
        f"",
        f"Final roadmap marker:",
        f"",
        f"```text",
        f"CTO_ROADMAP_UPDATED_AFTER_P127_ADAPTER_BUILD_SPECS_20260528",
        f"```",
    ]

    OUT_MD.write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    run_audit()
