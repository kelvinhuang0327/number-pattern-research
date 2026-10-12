#!/usr/bin/env python3
"""
P125 Adapter Gap Plan From P124 Matrix
======================================
Task: P125_ADAPTER_GAP_PLAN_FROM_P124_MATRIX
Read-only analysis that reads the P124 coverage matrix and produces:
  - ranked controlled_apply-ready list (5 Tier-B candidates)
  - ranked adapter_build_needed list (12 strategies)
  - replay storage design risks
  - blocked/forbidden areas
  - recommended next sequence: P126 / P127 / P128

NO DB writes.  NO scheduler install.  NO strategy promotion.
NO 4_STAR backtest.  NO P108 / P117 / P118 execution.
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
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
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
P124_ARTIFACT = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p124_multi_bet_truth_and_coverage_matrix_20260528.json"
)
OUT_JSON = (
    REPO_ROOT
    / "outputs"
    / "replay"
    / "p125_adapter_gap_plan_from_p124_20260528.json"
)
OUT_MD = (
    REPO_ROOT
    / "docs"
    / "replay"
    / "p125_adapter_gap_plan_from_p124_20260528.md"
)

# ---------------------------------------------------------------------------
# Expected DB invariants (must match before writing output)
# ---------------------------------------------------------------------------
EXPECTED_REPLAY_ROWS = 54462
EXPECTED_3STAR_COUNT = 4179
EXPECTED_3STAR_MAX = "115000106"
EXPECTED_4STAR_COUNT = 2922
EXPECTED_4STAR_MAX = "115000103"
EXPECTED_POWER_COUNT = 1913
EXPECTED_POWER_MAX = "115000041"

# ---------------------------------------------------------------------------
# Quality label priority (higher = more product value)
# ---------------------------------------------------------------------------
QUALITY_PRIORITY = {
    "prediction_helpful": 4,
    "fallback_equivalent": 3,
    "watchlist": 2,
    "sub_baseline": 1,
    "coverage_only": 0,
}

LOTTERY_PRIORITY = {
    "DAILY_539": 3,
    "BIG_LOTTO": 2,
    "POWER_LOTTO": 1,
}

# ---------------------------------------------------------------------------
# Pre-flight: verify P124 artifact exists
# ---------------------------------------------------------------------------
def load_p124_artifact():
    if not P124_ARTIFACT.exists():
        print(
            f"[P125] BLOCKED: P124 artifact not found at {P124_ARTIFACT}",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(P124_ARTIFACT) as f:
        data = json.load(f)
    if data.get("task_id") != "P124":
        print("[P125] BLOCKED: P124 artifact task_id mismatch", file=sys.stderr)
        sys.exit(1)
    if data.get("classification") != "P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY":
        print("[P125] BLOCKED: P124 artifact classification mismatch", file=sys.stderr)
        sys.exit(1)
    print(f"[P125] P124 artifact loaded: {len(data['coverage_matrix'])} rows")
    return data


# ---------------------------------------------------------------------------
# Pre-flight: verify DB invariants (SELECT only)
# ---------------------------------------------------------------------------
def verify_db_invariants():
    _p291u_db_path = _p291u_resolve_db_path()
    if not DB_PATH.exists():
        print(f"[P125] BLOCKED: DB not found at {DB_PATH}", file=sys.stderr)
        sys.exit(1)

    con = _p291u_connect_resolved(_p291u_db_path)
    con.execute("PRAGMA query_only = ON")
    cur = con.cursor()

    replay_rows = cur.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]

    draws_result = cur.execute(
        """
        SELECT lottery_type, COUNT(*), MAX(CAST(draw AS INTEGER))
        FROM draws
        WHERE lottery_type IN ('3_STAR','4_STAR','POWER_LOTTO','BIG_LOTTO','DAILY_539')
        GROUP BY lottery_type
        """
    ).fetchall()
    con.close()

    draws_map = {r[0]: {"count": r[1], "max_draw": str(r[2])} for r in draws_result}

    drift = []
    if replay_rows != EXPECTED_REPLAY_ROWS:
        drift.append(f"replay_rows: got {replay_rows}, expected {EXPECTED_REPLAY_ROWS}")
    if draws_map.get("3_STAR", {}).get("count") != EXPECTED_3STAR_COUNT:
        drift.append(f"3_STAR count: got {draws_map.get('3_STAR', {}).get('count')}")
    if draws_map.get("3_STAR", {}).get("max_draw") != EXPECTED_3STAR_MAX:
        drift.append(f"3_STAR max_draw: got {draws_map.get('3_STAR', {}).get('max_draw')}")
    if draws_map.get("4_STAR", {}).get("count") != EXPECTED_4STAR_COUNT:
        drift.append(f"4_STAR count: got {draws_map.get('4_STAR', {}).get('count')}")
    if draws_map.get("4_STAR", {}).get("max_draw") != EXPECTED_4STAR_MAX:
        drift.append(f"4_STAR max_draw: got {draws_map.get('4_STAR', {}).get('max_draw')}")
    if draws_map.get("POWER_LOTTO", {}).get("count") != EXPECTED_POWER_COUNT:
        drift.append(f"POWER_LOTTO count: got {draws_map.get('POWER_LOTTO', {}).get('count')}")
    if draws_map.get("POWER_LOTTO", {}).get("max_draw") != EXPECTED_POWER_MAX:
        drift.append(f"POWER_LOTTO max_draw: got {draws_map.get('POWER_LOTTO', {}).get('max_draw')}")

    if drift:
        print("[P125] BLOCKED: DB invariant drift detected:", file=sys.stderr)
        for d in drift:
            print(f"  {d}", file=sys.stderr)
        sys.exit(1)

    snapshot = {
        "replay_rows": replay_rows,
        "3_STAR": draws_map.get("3_STAR", {}),
        "4_STAR": draws_map.get("4_STAR", {}),
        "POWER_LOTTO": draws_map.get("POWER_LOTTO", {}),
        "BIG_LOTTO": draws_map.get("BIG_LOTTO", {}),
        "DAILY_539": draws_map.get("DAILY_539", {}),
    }
    print(f"[P125] DB invariants OK: replay_rows={replay_rows}")
    return snapshot


# ---------------------------------------------------------------------------
# Compute ranking score for a coverage matrix row
# ---------------------------------------------------------------------------
def rank_score(row, bonus_for_action=0):
    quality = QUALITY_PRIORITY.get(row.get("quality_label", ""), 0)
    lottery = LOTTERY_PRIORITY.get(row.get("lottery_type", ""), 0)
    # Extract target bet count from strategy_id suffix or native_bet_count
    sid = row.get("strategy_id", "")
    target_bets = row.get("native_bet_count", 1)
    for suffix in ["5bet", "4bet", "3bet", "2bet"]:
        if sid.endswith(suffix) or f"_{suffix}" in sid or f"_{suffix[0]}" in sid:
            try:
                target_bets = int(suffix[0])
            except ValueError:
                pass
            break
    # Score: quality (0-4) * 10 + lottery (0-3) * 5 + bet_count * 2 + bonus
    return quality * 10 + lottery * 5 + target_bets * 2 + bonus_for_action


def extract_target_bet_count(strategy_id, native_bet_count):
    for n in ["5", "4", "3", "2"]:
        if f"_{n}bet" in strategy_id or strategy_id.endswith(f"_{n}bet"):
            return int(n)
    return native_bet_count


def extract_missing_component(row):
    """Determine missing adapter component based on strategy characteristics."""
    sid = row["strategy_id"]
    if "fourier" in sid and "markov" in sid:
        return "fourier_markov_multi_bet_adapter"
    if "fourier" in sid:
        return "fourier_multi_bet_adapter"
    if "markov" in sid:
        return "markov_multi_bet_adapter"
    if "midfreq" in sid:
        return "midfreq_multi_bet_adapter"
    if "zonal" in sid or "zone" in sid:
        return "zonal_multi_bet_adapter"
    if "cold" in sid or "complement" in sid:
        return "cold_complement_multi_bet_adapter"
    if "pp3" in sid or "freqort" in sid:
        return "pp3_freqort_multi_bet_adapter"
    if "orthogonal" in sid:
        return "orthogonal_multi_bet_adapter"
    if "precision" in sid:
        return "precision_multi_bet_adapter"
    return "generic_multi_bet_adapter"


def make_adapter_contract(row):
    sid = row["strategy_id"]
    target_bets = extract_target_bet_count(sid, row.get("native_bet_count", 1))
    lottery = row["lottery_type"]
    return {
        "method": "get_all_bets(draw_context) -> List[List[int]]",
        "expected_outputs": target_bets,
        "lottery_type": lottery,
        "storage_format": "one_row_per_bet OR multi_numbers_per_row (P128 decision pending)",
        "must_not_fabricate": True,
        "must_use_historical_draw_context_only": True,
    }


# ---------------------------------------------------------------------------
# Build controlled_apply_ready list
# ---------------------------------------------------------------------------
def build_controlled_apply_ready(coverage_matrix):
    rows = [r for r in coverage_matrix if r.get("proposed_next_action_type") == "controlled_apply"]

    # Known Tier-B candidates (from P124 mandate)
    KNOWN_TIER_B = {
        "daily539_f4cold_3bet",
        "daily539_f4cold_5bet",
        "biglotto_echo_aware_3bet",
        "biglotto_ts3_markov_4bet_w30",
        "power_fourier_rhythm_2bet",
    }

    result = []
    for row in sorted(rows, key=lambda r: -rank_score(r, bonus_for_action=5)):
        sid = row["strategy_id"]
        lottery = row["lottery_type"]
        target_bets = extract_target_bet_count(sid, row.get("native_bet_count", 1))

        # Estimate expected rows: existing replay_rows / 1 * target_bets
        existing_rows = row.get("replay_rows_total", 0)
        if existing_rows and existing_rows > 0 and target_bets > 1:
            expected = f"~{existing_rows * target_bets} (estimate: {existing_rows} draws × {target_bets} bets)"
        else:
            expected = "unknown"

        result.append({
            "strategy_id": sid,
            "lottery_type": lottery,
            "target_bet_count": target_bets,
            "current_label": row.get("bet_1_label", "first_bet_only_fallback"),
            "proposed_action": "controlled_apply_dry_run_then_apply",
            "tier_b_confirmed": sid in KNOWN_TIER_B,
            "expected_rows_estimate": expected,
            "quality_label": row.get("quality_label", "unknown"),
            "risk_level": "low_to_medium" if row.get("quality_label") in ("prediction_helpful", "fallback_equivalent") else "medium",
            "required_pre_apply_tests": [
                "verify_adapter_get_all_bets_returns_correct_count",
                "verify_no_fabricated_numbers",
                "dry_run_single_draw_sanity_check",
                "confirm_db_row_count_before_apply",
                "confirm_staging_whitelist_clean",
            ],
            "explicit_apply_authorization_required": True,
            "p126_scope": True,
            "rank_score": rank_score(row, bonus_for_action=5),
        })

    return result


# ---------------------------------------------------------------------------
# Build adapter_build_needed list
# ---------------------------------------------------------------------------
def build_adapter_build_needed(coverage_matrix):
    rows = [r for r in coverage_matrix if r.get("proposed_next_action_type") == "adapter_build"]

    result = []
    for row in sorted(rows, key=lambda r: -rank_score(r)):
        sid = row["strategy_id"]
        lottery = row["lottery_type"]
        target_bets = extract_target_bet_count(sid, row.get("native_bet_count", 1))
        missing = extract_missing_component(row)
        contract = make_adapter_contract(row)

        result.append({
            "strategy_id": sid,
            "lottery_type": lottery,
            "desired_bet_count": target_bets,
            "current_label": row.get("bet_1_label", "first_bet_only_fallback"),
            "quality_label": row.get("quality_label", "unknown"),
            "missing_component": missing,
            "proposed_adapter_contract": contract,
            "test_plan": [
                f"unit_test_{missing}_correct_output_count",
                "no_future_data_leak_assertion",
                "single_draw_sanity_check",
                "integration_test_with_historical_draw_context",
            ],
            "risk_level": "medium",
            "no_db_write_in_p125": True,
            "p127_scope": True,
            "rank_score": rank_score(row),
        })

    return result


# ---------------------------------------------------------------------------
# Build relabel list
# ---------------------------------------------------------------------------
def build_relabel_list(coverage_matrix):
    return [
        {
            "strategy_id": r["strategy_id"],
            "lottery_type": r["lottery_type"],
            "current_label": r.get("bet_1_label"),
            "proposed_label": "first_bet_only_fallback_confirmed",
            "action": "metadata_relabel_only",
            "no_db_write_in_p125": True,
        }
        for r in coverage_matrix
        if r.get("proposed_next_action_type") == "relabel_first_bet_only"
    ]


# ---------------------------------------------------------------------------
# Blocked / forbidden
# ---------------------------------------------------------------------------
def build_blocked_or_forbidden(p124_data):
    return {
        "rejected_strategies": {
            "description": "Strategies with lifecycle=REJECTED must remain no_action. Expansion is forbidden.",
            "strategy_ids": [
                r["strategy_id"]
                for r in p124_data["coverage_matrix"]
                if r.get("bet_1_label") == "rejected"
            ],
            "rule": "no_action_forever_unless_explicit_authorization",
        },
        "4_STAR_source_unknown": {
            "description": "4_STAR rows exist in DB but provenance is unknown. No backtest until provenance is accepted.",
            "lottery_type": "4_STAR",
            "status": "source_unknown",
            "excluded_from": ["controlled_apply", "adapter_build", "backtest", "any_replay_expansion"],
            "rule": "provenance_decision_required_before_any_analysis",
        },
        "P108_Special3": {
            "description": "P108 requires 100 prospective Special3 draws. Currently ~63/100.",
            "status": "still_blocked",
            "rule": "do_not_execute_until_100_draws_confirmed",
        },
        "P117_POWER_LOTTO_OOS": {
            "description": "P117 POWER_LOTTO OOS retrigger needs 30-40 more draws after 115000041.",
            "status": "still_blocked",
            "rule": "do_not_execute_until_draw_threshold_met",
        },
        "P118_BIG_LOTTO_quarantine": {
            "description": "P118 BIG_LOTTO actual quarantine requires exact authorization phrase.",
            "status": "still_blocked",
            "rule": "exact_phrase_absent_do_not_apply",
        },
        "fabricated_rows": {
            "description": "Fabricating replay rows is forbidden regardless of coverage gap.",
            "rule": "fabrication_prohibited_all_rows_must_derive_from_historical_draws",
        },
        "native_multi_bet_storage_design": {
            "description": "Current schema stores one predicted_numbers list per row. Schema/format changes require P128 design decision first.",
            "status": "pending_P128_design",
            "rule": "no_schema_change_until_P128_approved",
        },
    }


# ---------------------------------------------------------------------------
# Replay storage design risks
# ---------------------------------------------------------------------------
def build_replay_storage_design_risks():
    return [
        {
            "risk_id": "RSR-1",
            "description": "One predicted_numbers list per replay row",
            "detail": (
                "Current strategy_prediction_replays schema stores a single JSON list "
                "of predicted numbers per row. Multi-bet strategies with N bets require "
                "either: (a) N separate rows per draw, or (b) a JSON array-of-arrays per row. "
                "Neither is formally decided or implemented."
            ),
            "impact": "Blocks native_multi_bet storage for all strategies",
            "mitigation": "P128 must design and approve the storage format before any apply",
            "severity": "high",
        },
        {
            "risk_id": "RSR-2",
            "description": "First-bet-only labeling inconsistency",
            "detail": (
                "19 strategy×lottery pairs have first_bet_only_fallback in P124 matrix "
                "but are stored as if they were full multi-bet strategies. "
                "Row counts may mislead consumers about actual bet diversity."
            ),
            "impact": "User-facing replay may overstate prediction variety",
            "mitigation": "P126/P127 controlled_apply and adapter builds must update labels alongside rows",
            "severity": "medium",
        },
        {
            "risk_id": "RSR-3",
            "description": "No replay row deduplication guard for multi-bet inserts",
            "detail": (
                "If controlled_apply generates rows for bets 2-5 for already-covered draws, "
                "there is no current guard against inserting duplicate bet-1 rows. "
                "P126 must enforce upsert-or-skip logic keyed on (strategy_id, draw, bet_index)."
            ),
            "impact": "Duplicate rows could inflate replay counts and mislead drift guard",
            "mitigation": "P126 dry-run must verify row-count delta matches exactly N_bets × N_draws",
            "severity": "medium",
        },
        {
            "risk_id": "RSR-4",
            "description": "Adapter get_all_bets() not uniformly implemented",
            "detail": (
                "P93/P94 Tier-B adapters implement get_all_bets() for some strategies, "
                "but P124 confirms 12 strategies still lack any multi-bet adapter. "
                "P127 must define and implement the missing adapters before apply."
            ),
            "impact": "Cannot expand replay coverage for 12 strategies until P127 completes",
            "mitigation": "P127 adapter builds with full unit test coverage",
            "severity": "medium",
        },
    ]


# ---------------------------------------------------------------------------
# Recommended sequence
# ---------------------------------------------------------------------------
def build_recommended_sequence():
    return [
        {
            "sequence": 1,
            "phase": "P126",
            "title": "Controlled Apply Dry-Run and Apply for 5 Tier-B Candidates",
            "description": (
                "Run controlled_apply dry-run for each of the 5 Tier-B candidates. "
                "Verify bet-count output, no fabrication, and row-count delta. "
                "If dry-run passes, apply with explicit authorization. "
                "All 5 strategies must have explicit_apply_authorization_required=true."
            ),
            "candidates": [
                "daily539_f4cold_3bet",
                "daily539_f4cold_5bet",
                "biglotto_echo_aware_3bet",
                "biglotto_ts3_markov_4bet_w30",
                "power_fourier_rhythm_2bet",
            ],
            "preconditions": [
                "P128 storage design approved OR apply using current one-row-per-bet convention",
                "Dry-run passes: row-count delta = N_draws × target_bets",
                "No duplicate bet-1 rows",
                "Staging whitelist clean",
            ],
            "no_db_write_in_p125": True,
        },
        {
            "sequence": 2,
            "phase": "P127",
            "title": "Adapter Build for 12 Missing Multi-Bet Adapters",
            "description": (
                "Build get_all_bets() adapters for the 12 strategies currently missing them. "
                "Priority order: prediction_helpful (pp3_freqort_4bet, midfreq_fourier_mk_3bet) first, "
                "then fallback_equivalent, then watchlist. "
                "Each adapter must have unit tests and no-future-data-leak assertions."
            ),
            "priority_order": [
                "pp3_freqort_4bet (POWER_LOTTO / prediction_helpful)",
                "midfreq_fourier_mk_3bet (POWER_LOTTO / prediction_helpful)",
                "zonal_entropy_2bet (POWER_LOTTO / fallback_equivalent)",
                "cold_complement_2bet (POWER_LOTTO / fallback_equivalent)",
                "acb_markov_midfreq_3bet (DAILY_539 / watchlist)",
                "midfreq_acb_2bet (DAILY_539 / watchlist)",
                "midfreq_fourier_2bet (DAILY_539 / watchlist)",
                "power_precision_3bet (POWER_LOTTO / watchlist)",
                "power_orthogonal_5bet (POWER_LOTTO / watchlist)",
                "fourier_rhythm_3bet (POWER_LOTTO / watchlist)",
                "midfreq_fourier_2bet (POWER_LOTTO / watchlist)",
                "fourier30_markov30_2bet (POWER_LOTTO / watchlist)",
            ],
            "no_db_write_in_p125": True,
        },
        {
            "sequence": 3,
            "phase": "P128",
            "title": "Native Multi-Bet Replay Storage Design",
            "description": (
                "Design the storage format for native multi-bet replay rows. "
                "Decide between: (a) one row per bet per draw, or (b) array-of-arrays per row. "
                "Define schema migration plan, drift guard update, and API compatibility rules. "
                "This is a design-only phase; no schema changes in P128 itself."
            ),
            "open_questions": [
                "Row-per-bet: simpler queries but N× row growth",
                "Array-per-row: compact but breaks current replay consumer assumptions",
                "Backward compatibility with existing 54462 rows",
                "Drift guard update to track multi-bet rows separately",
            ],
            "no_db_write_in_p125": True,
        },
    ]


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def build_summary(controlled_apply_ready, adapter_build_needed, relabel_list, blocked):
    return {
        "total_p124_coverage_matrix_rows": 36,
        "controlled_apply_ready_count": len(controlled_apply_ready),
        "adapter_build_needed_count": len(adapter_build_needed),
        "relabel_only_count": len(relabel_list),
        "no_action_kept": 17,
        "rejected_strategies_count": len(blocked["rejected_strategies"]["strategy_ids"]),
        "native_multi_bet_count": 0,
        "db_writes_in_p125": 0,
        "scheduler_installed": False,
        "4_STAR_included": False,
        "P108_executed": False,
        "P117_executed": False,
        "P118_executed": False,
        "fabricated_rows": 0,
    }


# ---------------------------------------------------------------------------
# Build Markdown report
# ---------------------------------------------------------------------------
def build_markdown(
    controlled_apply_ready,
    adapter_build_needed,
    relabel_list,
    replay_storage_risks,
    blocked_or_forbidden,
    recommended_sequence,
    summary,
    db_snapshot,
    generated_at,
):
    lines = []
    lines.append("# P125 Adapter Gap Plan From P124 Matrix")
    lines.append("")
    lines.append(f"**Generated:** {generated_at}")
    lines.append(
        f"**Classification:** `P125_ADAPTER_GAP_PLAN_READY`"
    )
    lines.append(
        "**Task:** P125_ADAPTER_GAP_PLAN_FROM_P124_MATRIX"
    )
    lines.append("")

    # 1. Executive summary
    lines.append("---")
    lines.append("")
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(
        "P125 reads the P124 multi-bet replay truth and coverage matrix and produces a ranked "
        "adapter gap plan. This is a read-only planning artifact. No DB rows are written. "
        "No adapters are built. No strategies are promoted. No scheduler is installed."
    )
    lines.append("")
    lines.append("| Metric | Count |")
    lines.append("|---|---|")
    lines.append(f"| P124 coverage matrix rows | 36 |")
    lines.append(f"| Controlled-apply-ready (Tier-B) | {len(controlled_apply_ready)} |")
    lines.append(f"| Adapter-build-needed | {len(adapter_build_needed)} |")
    lines.append(f"| Relabel-only | {len(relabel_list)} |")
    lines.append(f"| No-action (kept) | 17 |")
    lines.append(f"| Rejected (no-action-forever) | {summary['rejected_strategies_count']} |")
    lines.append(f"| Native multi-bet strategies | **0** |")
    lines.append(f"| DB writes in P125 | **0** |")
    lines.append("")

    # 2. What P124 proved
    lines.append("---")
    lines.append("")
    lines.append("## 2. What P124 Proved")
    lines.append("")
    lines.append(
        "- **Zero native multi-bet storage.** Every one of the 54462 replay rows stores "
        "exactly one `predicted_numbers` list. Even strategies named `_3bet`, `_4bet`, `_5bet` "
        "store only bet-1 in the current DB."
    )
    lines.append(
        "- **All 36 strategy×lottery pairs are first_bet_only_fallback, rejected, or already_covered.** "
        "No pair is genuinely native_multi_bet."
    )
    lines.append(
        "- **5 Tier-B adapter strategies** exist with working `get_all_bets()` implementations "
        "from P93/P94, making them controlled_apply candidates without new adapter code."
    )
    lines.append(
        "- **12 strategies** need new adapters before multi-bet replay rows can be generated."
    )
    lines.append(
        "- **DB invariants confirmed at P125 start:** replay_rows=54462, "
        f"3_STAR={db_snapshot['3_STAR']['count']}/max={db_snapshot['3_STAR']['max_draw']}, "
        f"POWER_LOTTO={db_snapshot['POWER_LOTTO']['count']}/max={db_snapshot['POWER_LOTTO']['max_draw']}."
    )
    lines.append("")

    # 3. Controlled-apply-ready
    lines.append("---")
    lines.append("")
    lines.append("## 3. Controlled-Apply-Ready List (P126 Scope)")
    lines.append("")
    lines.append(
        "These 5 strategies have working Tier-B adapters. They can proceed to P126 "
        "controlled_apply dry-run once P128 storage design is approved or the current "
        "one-row-per-bet convention is explicitly authorized."
    )
    lines.append("")
    lines.append(
        "**Every candidate requires `explicit_apply_authorization_required = true`. "
        "P125 does NOT apply any of these.**"
    )
    lines.append("")
    lines.append("| Rank | Strategy ID | Lottery | Bets | Quality | Risk | Estimated New Rows |")
    lines.append("|---|---|---|---|---|---|---|")
    for i, c in enumerate(controlled_apply_ready, 1):
        lines.append(
            f"| {i} | `{c['strategy_id']}` | {c['lottery_type']} | {c['target_bet_count']} | "
            f"{c['quality_label']} | {c['risk_level']} | {c['expected_rows_estimate']} |"
        )
    lines.append("")

    # 4. Adapter-build-needed
    lines.append("---")
    lines.append("")
    lines.append("## 4. Adapter-Build-Needed List (P127 Scope)")
    lines.append("")
    lines.append(
        "These 12 strategies need a new `get_all_bets()` adapter before controlled_apply "
        "can be attempted. Ranked by product value (quality × lottery priority × bet count)."
    )
    lines.append("")
    lines.append("| Rank | Strategy ID | Lottery | Bets | Quality | Missing Component |")
    lines.append("|---|---|---|---|---|---|")
    for i, a in enumerate(adapter_build_needed, 1):
        lines.append(
            f"| {i} | `{a['strategy_id']}` | {a['lottery_type']} | {a['desired_bet_count']} | "
            f"{a['quality_label']} | {a['missing_component']} |"
        )
    lines.append("")

    # 5. Why native_multi_bet is zero
    lines.append("---")
    lines.append("")
    lines.append("## 5. Why Native Multi-Bet Count Is Zero")
    lines.append("")
    lines.append(
        "The P94 Tier-B controlled apply run stored results using the existing replay insert path, "
        "which writes one `predicted_numbers` list per row. Even though the Tier-B adapters can "
        "produce multiple bets via `get_all_bets()`, only the first bet (or a merged single-bet "
        "representation) was stored. Therefore:"
    )
    lines.append("")
    lines.append("- `strategy_prediction_replays` has exactly 54462 rows — unchanged after P94.")
    lines.append("- All rows contain a single `predicted_numbers` JSON list.")
    lines.append(
        "- Strategies with names like `_3bet`, `_4bet`, `_5bet` were stored as if they were 1-bet strategies."
    )
    lines.append(
        "- This is not incorrect — it is first_bet_only_fallback, not fabrication. "
        "But it means the CEO mandate for 1-5 bet historical replay is **not yet satisfied**."
    )
    lines.append("")

    # 6. Replay storage risk
    lines.append("---")
    lines.append("")
    lines.append("## 6. Replay Storage Risk: One predicted_numbers List Per Row")
    lines.append("")
    lines.append(
        "The current schema forces a single bet per replay row. Before any multi-bet "
        "expansion can happen, a storage format decision must be made in P128:"
    )
    lines.append("")
    for risk in replay_storage_risks:
        lines.append(f"### {risk['risk_id']}: {risk['description']}")
        lines.append("")
        lines.append(f"**Detail:** {risk['detail']}")
        lines.append("")
        lines.append(f"**Impact:** {risk['impact']}")
        lines.append("")
        lines.append(f"**Mitigation:** {risk['mitigation']}")
        lines.append("")
        lines.append(f"**Severity:** {risk['severity']}")
        lines.append("")

    # 7. Recommended sequence
    lines.append("---")
    lines.append("")
    lines.append("## 7. Recommended Next Sequence: P126 / P127 / P128")
    lines.append("")
    for seq in recommended_sequence:
        lines.append(f"### P{seq['phase'][1:]} (Sequence {seq['sequence']}): {seq['title']}")
        lines.append("")
        lines.append(seq["description"])
        lines.append("")
        if "candidates" in seq:
            lines.append("**Candidates:**")
            for c in seq["candidates"]:
                lines.append(f"- `{c}`")
            lines.append("")
        if "priority_order" in seq:
            lines.append("**Priority order:**")
            for p in seq["priority_order"]:
                lines.append(f"- {p}")
            lines.append("")
        if "open_questions" in seq:
            lines.append("**Open design questions:**")
            for q in seq["open_questions"]:
                lines.append(f"- {q}")
            lines.append("")
        if "preconditions" in seq:
            lines.append("**Preconditions:**")
            for p in seq["preconditions"]:
                lines.append(f"- {p}")
            lines.append("")

    # 8. Explicit non-actions
    lines.append("---")
    lines.append("")
    lines.append("## 8. Explicit Non-Actions in P125")
    lines.append("")
    lines.append("| Item | Status |")
    lines.append("|---|---|")
    lines.append("| DB writes | **None** — P125 is read-only planning |")
    lines.append("| Scheduler installation | **None** — no cron / launchd install |")
    lines.append("| 4_STAR backtest | **Blocked** — source_unknown, provenance absent |")
    lines.append("| P108 Special3 | **Blocked** — needs ~37 more draws |")
    lines.append("| P117 POWER_LOTTO OOS | **Blocked** — needs 30-40 more draws |")
    lines.append("| P118 BIG_LOTTO quarantine | **Blocked** — authorization phrase absent |")
    lines.append("| Rejected strategy expansion | **Forbidden** — no_action_forever |")
    lines.append("| Strategy promotion / champion / registry | **None** |")
    lines.append("| Fabricated replay rows | **Forbidden** |")
    lines.append("")

    # 9. Final classification
    lines.append("---")
    lines.append("")
    lines.append("## 9. Final Classification")
    lines.append("")
    lines.append("```")
    lines.append("P125_ADAPTER_GAP_PLAN_READY")
    lines.append("```")
    lines.append("")
    lines.append(
        "Next task: **P126_CONTROLLED_APPLY_PLAN_FOR_TIER_B_MULTI_BET_ADAPTERS** "
        "(requires explicit apply authorization for each of the 5 candidates)."
    )
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    print("[P125] Starting...")
    generated_at = datetime.now(timezone.utc).isoformat()

    # Load P124 artifact and verify DB
    p124_data = load_p124_artifact()
    db_snapshot = verify_db_invariants()

    coverage_matrix = p124_data["coverage_matrix"]

    # Build plan components
    controlled_apply_ready = build_controlled_apply_ready(coverage_matrix)
    adapter_build_needed = build_adapter_build_needed(coverage_matrix)
    relabel_list = build_relabel_list(coverage_matrix)
    replay_storage_risks = build_replay_storage_design_risks()
    blocked_or_forbidden = build_blocked_or_forbidden(p124_data)
    recommended_sequence = build_recommended_sequence()
    summary = build_summary(controlled_apply_ready, adapter_build_needed, relabel_list, blocked_or_forbidden)

    # Build JSON artifact
    artifact = {
        "task_id": "P125",
        "generated_at": generated_at,
        "classification": "P125_ADAPTER_GAP_PLAN_READY",
        "p124_source_artifact": str(P124_ARTIFACT.relative_to(REPO_ROOT)),
        "db_snapshot": db_snapshot,
        "controlled_apply_ready": controlled_apply_ready,
        "adapter_build_needed": adapter_build_needed,
        "relabel_only": relabel_list,
        "replay_storage_design_risks": replay_storage_risks,
        "blocked_or_forbidden": blocked_or_forbidden,
        "recommended_sequence": recommended_sequence,
        "p126_candidate_scope": {
            "description": "Controlled apply dry-run + apply for 5 Tier-B multi-bet strategies",
            "candidates": [c["strategy_id"] for c in controlled_apply_ready],
            "authorization_required": True,
            "no_db_write_in_p125": True,
        },
        "p127_candidate_scope": {
            "description": "Build missing get_all_bets() adapters for 12 strategies",
            "strategies": [a["strategy_id"] for a in adapter_build_needed],
            "no_db_write_in_p125": True,
        },
        "p128_candidate_scope": {
            "description": "Design native multi-bet replay storage format (schema / format decision)",
            "open_questions": [
                "one_row_per_bet vs array_of_arrays_per_row",
                "backward_compatibility_with_54462_existing_rows",
                "drift_guard_update_for_multi_bet_tracking",
                "API_consumer_compatibility",
            ],
            "no_db_write_in_p125": True,
        },
        "summary": summary,
        "governance": {
            "db_writes": 0,
            "scheduler_installed": False,
            "strategy_promoted": False,
            "fabricated_rows": 0,
            "4_STAR_included": False,
            "P108_executed": False,
            "P117_executed": False,
            "P118_executed": False,
        },
    }

    # Write JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w") as f:
        json.dump(artifact, f, indent=2)
    print(f"[P125] JSON written: {OUT_JSON}")

    # Write Markdown
    md_text = build_markdown(
        controlled_apply_ready=controlled_apply_ready,
        adapter_build_needed=adapter_build_needed,
        relabel_list=relabel_list,
        replay_storage_risks=replay_storage_risks,
        blocked_or_forbidden=blocked_or_forbidden,
        recommended_sequence=recommended_sequence,
        summary=summary,
        db_snapshot=db_snapshot,
        generated_at=generated_at,
    )
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_MD, "w") as f:
        f.write(md_text)
    print(f"[P125] MD written: {OUT_MD}")

    print(
        f"[P125] Done. Classification: P125_ADAPTER_GAP_PLAN_READY\n"
        f"  controlled_apply_ready: {len(controlled_apply_ready)}\n"
        f"  adapter_build_needed:   {len(adapter_build_needed)}\n"
        f"  relabel_only:           {len(relabel_list)}\n"
        f"  db_writes:              0"
    )


if __name__ == "__main__":
    main()
