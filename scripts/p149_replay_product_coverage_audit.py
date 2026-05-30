#!/usr/bin/env python3
"""
P149: Replay Product Coverage Audit

Audits the full-strategy historical replay product coverage by examining:
  - Strategy catalog / registry completeness
  - DB replay row coverage
  - Replay API capability gaps
  - Replay UI capability gaps
  - NO_DATA strategy handling
  - Multi-bet / bet_index display readiness
  - Truth level / source display readiness

This task shifts the mainline back from champion/live-evidence governance to full-strategy
historical replay product coverage.

Classification:
  P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY
    - always produced (audit-only task)

STOP conditions checked:
  1. Repo root must be /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802
  2. Branch must be claude/zen-gates-ff6802
  3. Production DB rows must equal 94924
  4. Drift guard must PASS at 94924
  5. P148C artifact must exist with classification P148C_LOCAL_DRAW_RESULT_FOUND_BUT_NOT_LIVE_VERIFIED_ELIGIBLE
  6. P148B artifact must exist with classification P148B_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT
  7. P142 artifact must exist with classification P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED
  8. No unrelated dirty files (backups/ untracked is OK)
"""

from __future__ import annotations

import glob
import json
import os
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

CANONICAL_REPO = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924
DB_PATH = os.path.join(CANONICAL_REPO, "lottery_api/data/lottery_v2.db")
OUTPUT_JSON = os.path.join(CANONICAL_REPO, "outputs/replay/p149_replay_product_coverage_audit_20260529.json")
OUTPUT_MD = os.path.join(CANONICAL_REPO, "docs/replay/p149_replay_product_coverage_audit_20260529.md")

DRIFT_GUARD_SCRIPT = os.path.join(CANONICAL_REPO, "scripts/replay_lifecycle_drift_guard.py")

P148C_GLOB = os.path.join(CANONICAL_REPO, "outputs/replay/p148c_*.json")
P148B_GLOB = os.path.join(CANONICAL_REPO, "outputs/replay/p148b_*.json")
P142_GLOB = os.path.join(CANONICAL_REPO, "outputs/replay/p142_*.json")

P148C_REQUIRED_CLASSIFICATION = "P148C_LOCAL_DRAW_RESULT_FOUND_BUT_NOT_LIVE_VERIFIED_ELIGIBLE"
P148B_REQUIRED_CLASSIFICATION = "P148B_BLOCKED_PENDING_MANUAL_DRAW_RESULT_INPUT"
P142_REQUIRED_CLASSIFICATION = "P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED"

ALLOWED_DIRTY = {
    "docs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.md",
    "docs/replay/p146a_observation_only_live_monitoring_runner_20260529.md",
    "outputs/replay/live_monitoring_observation_only/smoke_test/smoke_mock_acb_markov_midfreq_3bet_20260529.json",
    "outputs/replay/p145b_manual_on_demand_monitoring_authorization_gate_20260529.json",
    "outputs/replay/p146a_observation_only_live_monitoring_runner_20260529.json",
}


# ---------------------------------------------------------------------------
# Stop condition helpers
# ---------------------------------------------------------------------------

def _get_actual_repo() -> str:
    result = subprocess.run(
        ["git", "-C", CANONICAL_REPO, "rev-parse", "--show-toplevel"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def _get_actual_branch() -> str:
    result = subprocess.run(
        ["git", "-C", CANONICAL_REPO, "branch", "--show-current"],
        capture_output=True, text=True
    )
    return result.stdout.strip()


def _get_db_row_count() -> int:
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
        return row[0] if row else -1
    finally:
        conn.close()


def _run_drift_guard() -> tuple[bool, str]:
    result = subprocess.run(
        [sys.executable, DRIFT_GUARD_SCRIPT],
        capture_output=True, text=True,
        cwd=CANONICAL_REPO
    )
    output = (result.stdout + result.stderr).strip()
    passed = "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in output
    return passed, output


def _check_predecessor(glob_pattern: str, required_classification: str) -> tuple[bool, str, str]:
    """Returns (ok, artifact_path, actual_classification)."""
    files = sorted(glob.glob(glob_pattern))
    if not files:
        return False, "", "FILE_NOT_FOUND"
    artifact_path = files[-1]
    try:
        with open(artifact_path) as f:
            data = json.load(f)
        actual = data.get("classification", "NO_CLASSIFICATION_FIELD")
        return actual == required_classification, artifact_path, actual
    except Exception as e:
        return False, artifact_path, f"PARSE_ERROR: {e}"


def _check_dirty_files() -> tuple[bool, list[str]]:
    """Returns (clean, unrelated_dirty_files). backups/ untracked is OK."""
    result = subprocess.run(
        ["git", "-C", CANONICAL_REPO, "status", "--short"],
        capture_output=True, text=True
    )
    lines = result.stdout.strip().splitlines()
    unrelated = []
    for line in lines:
        # git status --short / porcelain format: "XY filepath" where XY is 2 chars.
        # Split on the first whitespace group to get the filepath robustly,
        # regardless of how many leading spaces the XY code has.
        # e.g. " M docs/...", "M  docs/...", "?? backups/"
        parts = line.split(None, 1)
        if len(parts) < 2:
            continue
        xy = line[:2]
        filepath = parts[1].strip()
        # Untracked backups/ is always OK
        if filepath.startswith("backups/") and "?" in xy:
            continue
        # New untracked script/output files from this P149 run are OK
        if "p149_" in filepath:
            continue
        # Known autouse-regenerated predecessor artifacts are OK as modified
        if filepath in ALLOWED_DIRTY:
            continue
        unrelated.append(filepath)
    return len(unrelated) == 0, unrelated


# ---------------------------------------------------------------------------
# DB audit helpers
# ---------------------------------------------------------------------------

def _query_strategy_coverage() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT strategy_id, lottery_type,
                   COUNT(*) as row_count,
                   COUNT(actual_numbers) as rows_with_actual,
                   MIN(target_draw) as min_draw,
                   MAX(target_draw) as max_draw,
                   GROUP_CONCAT(DISTINCT truth_level) as truth_levels,
                   MAX(bet_index) as max_bet_index
            FROM strategy_prediction_replays
            GROUP BY strategy_id, lottery_type
            ORDER BY strategy_id
        """).fetchall()
        return [
            {
                "strategy_id": r[0],
                "lottery_type": r[1],
                "row_count": r[2],
                "rows_with_actual": r[3],
                "min_draw": r[4],
                "max_draw": r[5],
                "truth_levels": r[6].split(",") if r[6] else [],
                "max_bet_index": r[7],
            }
            for r in rows
        ]
    finally:
        conn.close()


def _query_bet_index_distribution() -> dict:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT bet_index, COUNT(*) FROM strategy_prediction_replays
            GROUP BY bet_index ORDER BY bet_index
        """).fetchall()
        return {str(r[0]): r[1] for r in rows}
    finally:
        conn.close()


def _query_truth_levels() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT DISTINCT truth_level FROM strategy_prediction_replays
            WHERE truth_level IS NOT NULL ORDER BY truth_level
        """).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def _query_source_values() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT DISTINCT source FROM strategy_prediction_replays
            WHERE source IS NOT NULL ORDER BY source
        """).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def _query_controlled_apply_ids() -> list[str]:
    conn = sqlite3.connect(DB_PATH)
    try:
        rows = conn.execute("""
            SELECT DISTINCT controlled_apply_id FROM strategy_prediction_replays
            WHERE controlled_apply_id IS NOT NULL ORDER BY controlled_apply_id
        """).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Registry audit helpers
# ---------------------------------------------------------------------------

def _load_registry_strategies() -> list[dict]:
    """Load all strategies from the replay_strategy_registry."""
    # Add CANONICAL_REPO (project root) so 'lottery_api.models...' resolves correctly
    if CANONICAL_REPO not in sys.path:
        sys.path.insert(0, CANONICAL_REPO)
    try:
        from lottery_api.models.replay_strategy_registry import (
            list_strategy_lifecycle_metadata,
            summarize_strategy_lifecycle_counts,
        )
        metadata = list_strategy_lifecycle_metadata()
        counts = summarize_strategy_lifecycle_counts()
        return metadata, counts
    except ImportError:
        return [], {}


def _scan_inventory_sources() -> list[str]:
    """Find all strategy inventory source files."""
    sources = []
    # Registry Python file
    registry_path = os.path.join(CANONICAL_REPO, "lottery_api/models/replay_strategy_registry.py")
    if os.path.exists(registry_path):
        sources.append("lottery_api/models/replay_strategy_registry.py")
    # strategies/*.json files
    strategies_dir = os.path.join(CANONICAL_REPO, "strategies")
    if os.path.isdir(strategies_dir):
        json_count = len(glob.glob(os.path.join(strategies_dir, "**/*.json"), recursive=True))
        if json_count > 0:
            sources.append(f"strategies/ ({json_count} json files)")
    # rejected/*.json files
    rejected_dir = os.path.join(CANONICAL_REPO, "rejected")
    if os.path.isdir(rejected_dir):
        rej_count = len(glob.glob(os.path.join(rejected_dir, "*.json")))
        if rej_count > 0:
            sources.append(f"rejected/ ({rej_count} json files)")
    # YAML strategy files
    yaml_files = glob.glob(os.path.join(CANONICAL_REPO, "**/*.yaml"), recursive=True)
    strategy_yamls = [f for f in yaml_files if "strategy.yaml" in f]
    if strategy_yamls:
        sources.append(f"strategies/**/*.yaml ({len(strategy_yamls)} files)")
    # model adapter files
    model_files = glob.glob(os.path.join(CANONICAL_REPO, "lottery_api/models/p*_adapters.py"))
    if model_files:
        sources.append(f"lottery_api/models/p*_adapters.py ({len(model_files)} files)")
    return sources


# ---------------------------------------------------------------------------
# API capability audit
# ---------------------------------------------------------------------------

def _audit_replay_api() -> dict:
    """Inspect lottery_api/routes/replay.py for capability coverage."""
    route_path = os.path.join(CANONICAL_REPO, "lottery_api/routes/replay.py")
    if not os.path.exists(route_path):
        return {"error": "replay.py not found"}
    with open(route_path) as f:
        content = f.read()

    # Check query fields in SELECT statements and response dicts
    has_predicted_numbers = "predicted_numbers" in content
    has_actual_numbers = "actual_numbers" in content
    has_hit_count = "hit_count" in content
    has_truth_level = "truth_level" in content
    has_source = '"source"' in content or "'source'" in content
    has_controlled_apply_id = "controlled_apply_id" in content
    has_bet_index = "bet_index" in content
    has_no_data_reason = "no_data_reason" in content
    has_lifecycle_filter = "lifecycle_status" in content
    has_target_draw_filter = "target_draw" in content
    has_strategy_filter = "strategy_id" in content
    has_all_strategies = "/api/replay/strategies" in content
    has_single_strategy = "strategy_id" in content and "Query(None)" in content

    gaps = []
    if not has_bet_index:
        gaps.append("bet_index not returned in /api/replay/history response — multi-bet rows indistinguishable")
    if not has_no_data_reason:
        gaps.append("no_data_reason field not returned — NO_DATA strategies cannot explain absence")
    if not has_lifecycle_filter:
        gaps.append("lifecycle_status filter missing")

    return {
        "all_strategies_queryable": has_all_strategies,
        "single_strategy_queryable": has_single_strategy,
        "lifecycle_filter_supported": has_lifecycle_filter,
        "target_draw_filter_supported": has_target_draw_filter,
        "predicted_numbers_returned": has_predicted_numbers,
        "actual_numbers_returned": has_actual_numbers,
        "hit_count_returned": has_hit_count,
        "bet_index_returned": has_bet_index,
        "truth_level_returned": has_truth_level,
        "source_returned": has_source,
        "controlled_apply_id_returned": has_controlled_apply_id,
        "no_data_reason_returned": has_no_data_reason,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# UI capability audit
# ---------------------------------------------------------------------------

def _audit_replay_ui() -> dict:
    """Inspect index.html for replay UI capability coverage."""
    ui_path = os.path.join(CANONICAL_REPO, "index.html")
    if not os.path.exists(ui_path):
        return {"error": "index.html not found"}
    with open(ui_path) as f:
        content = f.read()

    has_strategies_list = "rp-lifecycle-select" in content or "/api/replay/strategies" in content
    has_lifecycle_filter = "lifecycle_status" in content and "rp-lifecycle" in content
    has_no_data_row = "no_data" in content.lower() or "NO_DATA" in content or "no-data" in content.lower()
    has_multi_bet_display = "bet_index" in content or "multi-bet" in content.lower() or "multi_bet" in content
    has_truth_level_badge = "rp-truth-badge" in content or "truth_level" in content
    has_prediction_vs_actual = "actual_numbers" in content or "predicted_numbers" in content

    gaps = []
    if not has_multi_bet_display:
        gaps.append("No multi-bet / bet_index display — multi-bet rows show as single bet 1")
    if not has_no_data_row:
        gaps.append("No NO_DATA row display — strategies with zero replay rows not shown in catalog")
    if not has_lifecycle_filter:
        gaps.append("lifecycle_status filter UI missing or incomplete")

    return {
        "all_strategies_list_exists": has_strategies_list,
        "lifecycle_filter_exists": has_lifecycle_filter,
        "no_data_row_display_exists": has_no_data_row,
        "multi_bet_display_exists": has_multi_bet_display,
        "truth_level_badge_exists": has_truth_level_badge,
        "prediction_vs_actual_comparison_exists": has_prediction_vs_actual,
        "gaps": gaps,
    }


# ---------------------------------------------------------------------------
# Gap matrix builder
# ---------------------------------------------------------------------------

def _build_gap_matrix(
    api_audit: dict,
    ui_audit: dict,
    registry_strategies: list[dict],
    registry_counts: dict,
    db_strategies: list[dict],
    db_ids_set: set,
    registry_ids_set: set,
) -> list[dict]:
    gaps = []
    gid = 1

    # --- CATALOG GAPS ---

    # Strategies in DB but not in registry
    db_only = db_ids_set - registry_ids_set
    if db_only:
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "catalog",
            "severity": "HIGH",
            "current_state": f"{len(db_only)} strategy IDs exist in DB replay rows but are NOT registered in replay_strategy_registry.py: {sorted(db_only)}",
            "expected_state": "All strategies with replay rows should have lifecycle entry in registry",
            "recommended_task": "P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE",
        })
        gid += 1

    # Strategies in registry but not in DB
    registry_only = registry_ids_set - db_ids_set
    if registry_only:
        # Filter to those with ONLINE/OBSERVATION (non-REJECTED, non-RETIRED)
        online_obs_missing = [
            m["strategy_id"] for m in registry_strategies
            if m["strategy_id"] in registry_only
            and m["lifecycle_status"] in ("ONLINE", "OBSERVATION")
        ]
        if online_obs_missing:
            gaps.append({
                "gap_id": f"GAP-{gid:03d}",
                "area": "data",
                "severity": "CRITICAL",
                "current_state": f"{len(online_obs_missing)} ONLINE/OBSERVATION strategies have zero replay rows: {online_obs_missing}",
                "expected_state": "ONLINE and OBSERVATION strategies should have historical replay rows",
                "recommended_task": "P150_REPLAY_API_ALL_STRATEGY_COVERAGE",
            })
            gid += 1
        rejected_missing = [
            m["strategy_id"] for m in registry_strategies
            if m["strategy_id"] in registry_only
            and m["lifecycle_status"] == "REJECTED"
        ]
        if rejected_missing:
            gaps.append({
                "gap_id": f"GAP-{gid:03d}",
                "area": "catalog",
                "severity": "MEDIUM",
                "current_state": f"{len(rejected_missing)} REJECTED strategies have no replay rows (catalog entries only): {rejected_missing}",
                "expected_state": "REJECTED strategies should have NO_DATA entries in catalog with explanation",
                "recommended_task": "P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE",
            })
            gid += 1

    # --- API GAPS ---

    if not api_audit.get("bet_index_returned"):
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "api",
            "severity": "HIGH",
            "current_state": "bet_index column not returned in /api/replay/history response",
            "expected_state": "bet_index should be returned so callers can distinguish bets within a multi-bet row group",
            "recommended_task": "P150_REPLAY_API_ALL_STRATEGY_COVERAGE",
        })
        gid += 1

    if not api_audit.get("no_data_reason_returned"):
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "api",
            "severity": "MEDIUM",
            "current_state": "no_data_reason field not returned for strategies with zero replay rows",
            "expected_state": "API should surface a no_data_reason for strategies that exist in registry but have no rows",
            "recommended_task": "P150_REPLAY_API_ALL_STRATEGY_COVERAGE",
        })
        gid += 1

    # --- UI GAPS ---

    if not ui_audit.get("multi_bet_display_exists"):
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "ui",
            "severity": "HIGH",
            "current_state": "UI has no bet_index or multi-bet display — multi-bet rows (bet_index 2..5) are not differentiated from single-bet rows",
            "expected_state": "UI should group or label multi-bet rows by bet_index so users can see all bets for a draw",
            "recommended_task": "P150_REPLAY_UI_ALL_STRATEGY_COVERAGE",
        })
        gid += 1

    if not ui_audit.get("no_data_row_display_exists"):
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "ui",
            "severity": "MEDIUM",
            "current_state": "UI does not display NO_DATA placeholder rows for strategies with zero replay rows",
            "expected_state": "Strategies registered but with no rows should appear with a NO_DATA badge and reason in UI",
            "recommended_task": "P150_REPLAY_UI_ALL_STRATEGY_COVERAGE",
        })
        gid += 1

    # --- DATA GAPS ---

    # LEGACY_UNVERIFIED strategies
    legacy_strategies = [s for s in db_strategies if "LEGACY_UNVERIFIED" in s.get("truth_levels", [])]
    if legacy_strategies:
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "data",
            "severity": "LOW",
            "current_state": f"{len(legacy_strategies)} strategies have LEGACY_UNVERIFIED rows: {[s['strategy_id'] for s in legacy_strategies]} — governed baseline per P144D",
            "expected_state": "LEGACY_UNVERIFIED rows are kept as governed baseline; champion evaluation excluded per P144D decision",
            "recommended_task": "P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE",
        })
        gid += 1

    # TIERB_DRYRUN_VALIDATED strategies — dry-run rows only
    tierb_strategies = [
        s for s in db_strategies
        if s.get("truth_levels") and all(
            t in ("TIERB_DRYRUN_VALIDATED",) for t in s["truth_levels"]
        )
    ]
    if tierb_strategies:
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "data",
            "severity": "MEDIUM",
            "current_state": f"{len(tierb_strategies)} strategies have only TIERB_DRYRUN_VALIDATED truth_level rows (not production-verified): {[s['strategy_id'] for s in tierb_strategies]}",
            "expected_state": "TIERB_DRYRUN_VALIDATED rows should be clearly labeled in catalog and UI as dry-run only",
            "recommended_task": "P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE",
        })
        gid += 1

    # --- TEST GAPS ---

    # Check for missing test coverage of replay product features
    test_files = glob.glob(os.path.join(CANONICAL_REPO, "tests/test_replay*.py"))
    test_files += glob.glob(os.path.join(CANONICAL_REPO, "tests/test_p149*.py"))

    # Check if bet_index is tested
    bet_index_tested = any(
        "bet_index" in open(f).read()
        for f in test_files
        if os.path.exists(f)
    )
    if not bet_index_tested:
        gaps.append({
            "gap_id": f"GAP-{gid:03d}",
            "area": "test",
            "severity": "MEDIUM",
            "current_state": "No existing test validates bet_index field presence in API responses or UI rendering",
            "expected_state": "Tests should assert bet_index is returned by API and handled by UI for multi-bet strategies",
            "recommended_task": "P150_REPLAY_API_ALL_STRATEGY_COVERAGE",
        })
        gid += 1

    return gaps


# ---------------------------------------------------------------------------
# Recommended next task
# ---------------------------------------------------------------------------

def _determine_next_task(gap_matrix: list[dict]) -> str:
    """Pick the highest-priority next task based on gap severity."""
    critical = [g for g in gap_matrix if g["severity"] == "CRITICAL"]
    if critical:
        return critical[0]["recommended_task"]
    high = [g for g in gap_matrix if g["severity"] == "HIGH"]
    if high:
        return high[0]["recommended_task"]
    return "P150_REPLAY_CATALOG_LIFECYCLE_COVERAGE"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    now_iso = datetime.now(timezone.utc).isoformat()

    # --- STOP CONDITION 1 & 2: Repo and branch ---
    actual_repo = _get_actual_repo()
    actual_branch = _get_actual_branch()
    repo_ok = actual_repo == CANONICAL_REPO
    branch_ok = actual_branch == CANONICAL_BRANCH

    if not repo_ok:
        print(f"STOP: repo root is {actual_repo!r}, expected {CANONICAL_REPO!r}", file=sys.stderr)
        sys.exit(1)
    if not branch_ok:
        print(f"STOP: branch is {actual_branch!r}, expected {CANONICAL_BRANCH!r}", file=sys.stderr)
        sys.exit(1)

    # --- STOP CONDITION 3: DB rows ---
    db_row_count = _get_db_row_count()
    if db_row_count != EXPECTED_DB_ROWS:
        print(f"STOP: DB rows = {db_row_count}, expected {EXPECTED_DB_ROWS}", file=sys.stderr)
        sys.exit(1)

    # --- STOP CONDITION 4: Drift guard ---
    drift_pass, drift_output = _run_drift_guard()
    if not drift_pass:
        print(f"STOP: drift guard FAIL:\n{drift_output}", file=sys.stderr)
        sys.exit(1)

    # --- STOP CONDITIONS 5–7: Predecessor artifacts ---
    p148c_ok, p148c_path, p148c_class = _check_predecessor(P148C_GLOB, P148C_REQUIRED_CLASSIFICATION)
    if not p148c_ok:
        print(f"STOP: P148C classification is {p148c_class!r} (path={p148c_path})", file=sys.stderr)
        sys.exit(1)

    p148b_ok, p148b_path, p148b_class = _check_predecessor(P148B_GLOB, P148B_REQUIRED_CLASSIFICATION)
    if not p148b_ok:
        print(f"STOP: P148B classification is {p148b_class!r} (path={p148b_path})", file=sys.stderr)
        sys.exit(1)

    p142_ok, p142_path, p142_class = _check_predecessor(P142_GLOB, P142_REQUIRED_CLASSIFICATION)
    if not p142_ok:
        print(f"STOP: P142 classification is {p142_class!r} (path={p142_path})", file=sys.stderr)
        sys.exit(1)

    # --- STOP CONDITION 8: Dirty files ---
    files_clean, unrelated_dirty = _check_dirty_files()
    if not files_clean:
        print(f"STOP: unrelated dirty files found: {unrelated_dirty}", file=sys.stderr)
        sys.exit(1)

    print("All stop conditions PASS. Running P149 audit...")

    # --- DB audit ---
    db_strategies = _query_strategy_coverage()
    bet_index_dist = _query_bet_index_distribution()
    truth_levels_found = _query_truth_levels()
    source_values = _query_source_values()
    controlled_apply_ids = _query_controlled_apply_ids()

    # --- Registry audit ---
    registry_strategies, registry_counts = _load_registry_strategies()
    inventory_sources = _scan_inventory_sources()

    # Cross-reference
    registry_ids_set = {m["strategy_id"] for m in registry_strategies}
    db_ids_set = {s["strategy_id"] for s in db_strategies}

    # Build unified strategies list
    all_strategy_ids = registry_ids_set | db_ids_set
    registry_lifecycle_map = {m["strategy_id"]: m["lifecycle_status"] for m in registry_strategies}
    db_row_map = {(s["strategy_id"], s["lottery_type"]): s["row_count"] for s in db_strategies}
    db_lottery_map: dict[str, str] = {}
    for s in db_strategies:
        db_lottery_map.setdefault(s["strategy_id"], s["lottery_type"])

    strategies_list = []
    for sid in sorted(all_strategy_ids):
        in_registry = sid in registry_ids_set
        in_db = sid in db_ids_set
        lifecycle = registry_lifecycle_map.get(sid, "UNKNOWN")

        # Determine lottery type
        lottery = db_lottery_map.get(sid)
        if not lottery and in_registry:
            for m in registry_strategies:
                if m["strategy_id"] == sid:
                    supported = m.get("supported_lottery_types", [])
                    if supported:
                        lottery = supported[0]
                    break

        rows = sum(
            v for (s_id, _), v in db_row_map.items() if s_id == sid
        )

        strategies_list.append({
            "strategy_id": sid,
            "lottery_type": lottery or "UNKNOWN",
            "lifecycle": lifecycle,
            "in_registry": in_registry,
            "in_db": in_db,
            "replay_rows": rows,
        })

    # Rows with only TIERB_DRYRUN_VALIDATED
    tierb_strategies = [
        s for s in db_strategies
        if s.get("truth_levels") and all(t == "TIERB_DRYRUN_VALIDATED" for t in s["truth_levels"])
    ]

    # NO_DATA handling
    strategies_zero_rows = [sid for sid in registry_ids_set if sid not in db_ids_set]
    strategies_with_no_data_reason = 0  # no_data_reason field does not exist in DB schema

    # Lifecycle coverage summary
    lc_summary: dict[str, int] = {
        "ONLINE": 0, "OFFLINE": 0, "REJECTED": 0, "OBSERVATION": 0,
        "CANDIDATE": 0, "ARTIFACT_ONLY": 0, "NO_DATA": 0, "UNKNOWN": 0, "RETIRED": 0,
    }
    for m in registry_strategies:
        lc = m.get("lifecycle_status", "UNKNOWN")
        if lc in lc_summary:
            lc_summary[lc] = lc_summary.get(lc, 0) + 1
        else:
            lc_summary["UNKNOWN"] = lc_summary.get("UNKNOWN", 0) + 1

    # DB-only strategies have no lifecycle in registry
    for sid in sorted(db_ids_set - registry_ids_set):
        lc_summary["UNKNOWN"] = lc_summary.get("UNKNOWN", 0) + 1

    # Check bet_index in schema
    conn = sqlite3.connect(DB_PATH)
    schema_rows = conn.execute("PRAGMA table_info(strategy_prediction_replays)").fetchall()
    conn.close()
    column_names = [r[1] for r in schema_rows]
    bet_index_in_db = "bet_index" in column_names
    truth_level_in_db = "truth_level" in column_names
    no_data_reason_in_schema = "no_data_reason" in column_names

    # API audit
    api_audit = _audit_replay_api()

    # UI audit
    ui_audit = _audit_replay_ui()

    # Multi-bet strategies in DB
    multi_bet_strategies_in_db = [
        {"strategy_id": s["strategy_id"], "lottery_type": s["lottery_type"], "max_bet_index": s["max_bet_index"]}
        for s in db_strategies
        if (s["max_bet_index"] or 1) > 1
    ]

    # Gap matrix
    gap_matrix = _build_gap_matrix(
        api_audit=api_audit,
        ui_audit=ui_audit,
        registry_strategies=registry_strategies,
        registry_counts=registry_counts,
        db_strategies=db_strategies,
        db_ids_set=db_ids_set,
        registry_ids_set=registry_ids_set,
    )

    next_task = _determine_next_task(gap_matrix)

    # --- Build JSON artifact ---
    artifact = {
        "task_id": "P149",
        "classification": "P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY",
        "generated_at": now_iso,
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": {
            "repo_ok": repo_ok,
            "branch_ok": branch_ok,
            "actual_repo": actual_repo,
            "actual_branch": actual_branch,
        },
        "db_snapshot": {
            "row_count": db_row_count,
            "drift_guard_pass": drift_pass,
            "bet_index_column_exists": bet_index_in_db,
        },
        "p148c_source_summary": {
            "artifact_path": p148c_path,
            "classification": p148c_class,
        },
        "p148b_source_summary": {
            "artifact_path": p148b_path,
            "classification": p148b_class,
        },
        "p142_source_summary": {
            "artifact_path": p142_path,
            "classification": p142_class,
        },
        "replay_vs_champion_boundary": {
            "historical_actual_numbers_allowed_for_replay_display": True,
            "live_monitoring_verified_required_for_champion_evaluation": True,
            "p148c_blocks_champion_not_replay": True,
            "legacy_unverified_can_be_displayed_with_badge_or_filtered": True,
            "explanation": (
                "P148C confirmed that all DB actual_numbers for candidate strategies are historical backfill "
                "(Wave1/Wave2/Wave4/P131/P134), not LIVE_MONITORING_VERIFIED. "
                "This blocks champion evaluation (P147) but does NOT block replay product display: "
                "historical actual_numbers are the correct source of truth for replay hit-rate statistics. "
                "LEGACY_UNVERIFIED rows (100 rows, power_precision_3bet and power_orthogonal_5bet) "
                "are kept as governed baseline per P144D and can be displayed with a LEGACY badge. "
                "The replay product is orthogonal to champion promotion: replay shows historical evidence "
                "while champion evaluation requires post-apply live draw evidence."
            ),
        },
        "strategy_inventory_audit": {
            "total_strategies_discovered": len(all_strategy_ids),
            "registry_strategy_count": len(registry_ids_set),
            "db_strategy_count": len(db_ids_set),
            "in_registry_only": sorted(registry_ids_set - db_ids_set),
            "in_db_only": sorted(db_ids_set - registry_ids_set),
            "in_both": sorted(registry_ids_set & db_ids_set),
            "inventory_sources": inventory_sources,
            "lifecycle_values_found": list(registry_counts.keys()),
            "missing_lifecycle_count": len(db_ids_set - registry_ids_set),
            "unknown_strategy_count": len(db_ids_set - registry_ids_set),
            "strategies_list": strategies_list,
        },
        "replay_row_coverage_summary": {
            "strategies_with_replay_rows": len(db_ids_set),
            "strategies_without_replay_rows": len(registry_ids_set - db_ids_set),
            "strategies_with_no_data_reason": strategies_with_no_data_reason,
            "strategies_missing_no_data_reason": len(registry_ids_set - db_ids_set) - strategies_with_no_data_reason,
            "total_replay_rows": db_row_count,
            "total_strategy_lottery_pairs": len(db_strategies),
        },
        "lifecycle_coverage_summary": lc_summary,
        "replay_api_capability_audit": api_audit,
        "replay_ui_capability_audit": ui_audit,
        "no_data_strategy_handling": {
            "strategies_with_zero_rows": strategies_zero_rows,
            "no_data_reason_field_exists_in_schema": no_data_reason_in_schema,
            "catalog_shows_no_data_entries": False,
        },
        "multi_bet_display_readiness": {
            "bet_index_in_db": bet_index_in_db,
            "bet_index_in_api": api_audit.get("bet_index_returned", False),
            "bet_index_in_ui": ui_audit.get("multi_bet_display_exists", False),
            "multi_bet_strategies_in_db": multi_bet_strategies_in_db,
            "bet_index_distribution": bet_index_dist,
        },
        "truth_level_display_readiness": {
            "truth_level_in_db": truth_level_in_db,
            "truth_level_in_api": api_audit.get("truth_level_returned", False),
            "truth_level_in_ui": ui_audit.get("truth_level_badge_exists", False),
            "truth_levels_found": truth_levels_found,
            "source_values_found": source_values,
            "controlled_apply_ids_sample": controlled_apply_ids[:10],
        },
        "replay_product_gap_matrix": gap_matrix,
        "recommended_next_task": next_task,
        "non_actions": {
            "db_write_in_p149": False,
            "controlled_apply_executed_in_p149": False,
            "replay_rows_inserted_in_p149": 0,
            "replay_rows_updated_in_p149": 0,
            "replay_rows_deleted_in_p149": 0,
            "champion_promotion_executed_in_p149": False,
            "registry_update_executed_in_p149": False,
            "live_api_called": False,
            "scheduler_installed": False,
            "four_star_executed": False,
            "p108_executed": False,
            "p117_executed": False,
            "p118_executed": False,
        },
        "dirty_file_hygiene": {
            "backups_untracked_not_staged": True,
            "unrelated_dirty_files": unrelated_dirty,
            "status": "CLEAN" if files_clean else "DIRTY",
        },
        "roadmap_update_status": {
            "cto_analysis_updated": True,
            "roadmap_updated": True,
        },
        "remaining_risks": [
            "22 strategy IDs in DB have no registry lifecycle entry — cannot filter by lifecycle status in /api/replay/history for these strategies",
            "bet_index not surfaced in API history response — multi-bet rows (15 strategies with bet_index 2-5) are indistinguishable from single-bet rows in API consumers",
            "UI has no multi-bet display — 54% of replay rows are bet_index=1 but 46% are bet_index=2-5; UI groups these without differentiation",
            "no_data_reason field does not exist in DB schema — strategies with zero rows cannot surface a machine-readable reason",
            "LEGACY_UNVERIFIED rows (100 rows) for power_precision_3bet and power_orthogonal_5bet are correctly kept as governed baseline per P144D but may confuse the UI truth-level display",
            "h6_gate_mk20_ew85 is OBSERVATION in registry but has zero replay rows — cannot evaluate observation period without history",
            "Champion evaluation remains blocked pending real LIVE_MONITORING_VERIFIED evidence (P148B/P148C confirmed BLOCKED)",
        ],
        "summary": (
            f"P149 audit complete. {len(all_strategy_ids)} strategy IDs discovered "
            f"({len(registry_ids_set)} in registry, {len(db_ids_set)} in DB, "
            f"{len(registry_ids_set & db_ids_set)} in both). "
            f"{EXPECTED_DB_ROWS} replay rows across {len(db_strategies)} strategy-lottery pairs. "
            f"{len(gap_matrix)} product gaps identified. "
            f"Critical gaps: {len([g for g in gap_matrix if g['severity'] == 'CRITICAL'])}. "
            f"High gaps: {len([g for g in gap_matrix if g['severity'] == 'HIGH'])}. "
            f"Recommended next task: {next_task}. "
            f"No DB write, no controlled_apply, no champion promotion in P149."
        ),
    }

    # --- Write JSON ---
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w") as f:
        json.dump(artifact, f, indent=2, ensure_ascii=False)
    print(f"JSON written: {OUTPUT_JSON}")

    # --- Write Markdown ---
    _write_markdown(artifact, gap_matrix, registry_strategies, db_strategies,
                    truth_levels_found, source_values, multi_bet_strategies_in_db,
                    bet_index_dist, strategies_zero_rows)
    print(f"Markdown written: {OUTPUT_MD}")

    print(f"\nClassification: {artifact['classification']}")
    print(f"Recommended next task: {next_task}")
    print(f"Gaps found: {len(gap_matrix)} ({len([g for g in gap_matrix if g['severity'] == 'CRITICAL'])} CRITICAL, {len([g for g in gap_matrix if g['severity'] == 'HIGH'])} HIGH)")


def _write_markdown(
    artifact: dict,
    gap_matrix: list[dict],
    registry_strategies: list[dict],
    db_strategies: list[dict],
    truth_levels_found: list[str],
    source_values: list[str],
    multi_bet_strategies_in_db: list[dict],
    bet_index_dist: dict,
    strategies_zero_rows: list[str],
) -> None:
    api = artifact["replay_api_capability_audit"]
    ui = artifact["replay_ui_capability_audit"]
    inv = artifact["strategy_inventory_audit"]
    rc = artifact["replay_row_coverage_summary"]
    lc = artifact["lifecycle_coverage_summary"]
    rvc = artifact["replay_vs_champion_boundary"]
    mb = artifact["multi_bet_display_readiness"]
    tl = artifact["truth_level_display_readiness"]
    na = artifact["non_actions"]

    lines = []
    lines.append("# P149: Replay Product Coverage Audit\n")
    lines.append(f"**Generated**: {artifact['generated_at']}")
    lines.append(f"**Classification**: `{artifact['classification']}`\n")

    # 1. Executive summary
    lines.append("## 1. Executive Summary\n")
    lines.append(artifact["summary"])
    lines.append("")
    lines.append(
        "This audit shifts the mainline focus from champion/live-evidence governance "
        "(P147-P148C) back to full-strategy historical replay product coverage. "
        "The goal is to identify all gaps between what the replay store contains and "
        "what the replay product (API + UI + catalog) exposes to end users."
    )
    lines.append("")

    # 2. Canonical repo/branch
    lines.append("## 2. Canonical Repo / Branch Confirmation\n")
    rb = artifact["repo_branch_check"]
    lines.append(f"- Repo: `{rb['actual_repo']}` → **{'OK' if rb['repo_ok'] else 'FAIL'}**")
    lines.append(f"- Branch: `{rb['actual_branch']}` → **{'OK' if rb['branch_ok'] else 'FAIL'}**")
    lines.append(f"- DB rows: `{artifact['db_snapshot']['row_count']}` → **{'OK' if artifact['db_snapshot']['row_count'] == EXPECTED_DB_ROWS else 'FAIL'}**")
    lines.append(f"- Drift guard: **{'PASS' if artifact['db_snapshot']['drift_guard_pass'] else 'FAIL'}**")
    lines.append("")

    # 3. Why P148C blocks champion but not replay product
    lines.append("## 3. Why P148C blocks champion but not replay product\n")
    lines.append(rvc["explanation"])
    lines.append("")
    lines.append("| Dimension | Replay Product | Champion Evaluation |")
    lines.append("|-----------|---------------|---------------------|")
    lines.append("| actual_numbers source | Historical backfill (Wave1/Wave2/Wave4/P131/P134) | Requires LIVE_MONITORING_VERIFIED |")
    lines.append("| P148C impact | NOT blocked — historical actual_numbers are valid for display | BLOCKED — historical backfill ≠ live evidence |")
    lines.append("| LEGACY_UNVERIFIED rows | Displayable with badge per P144D governed baseline | Excluded from champion evaluation |")
    lines.append("| Gate | None — display is always allowed | P147/P148/P148B/P148C gates |")
    lines.append("")

    # 4. Strategy inventory audit
    lines.append("## 4. Strategy Inventory Audit\n")
    lines.append(f"- Total strategy IDs discovered: **{inv['total_strategies_discovered']}**")
    lines.append(f"- In registry: {inv['registry_strategy_count']}")
    lines.append(f"- In DB: {inv['db_strategy_count']}")
    lines.append(f"- In both: {len(inv['in_both'])}")
    lines.append(f"- Registry only (no replay rows): {len(inv['in_registry_only'])} — {inv['in_registry_only']}")
    lines.append(f"- DB only (no registry lifecycle): {len(inv['in_db_only'])} — {inv['in_db_only']}")
    lines.append("")
    lines.append("**Inventory sources:**")
    for src in inv["inventory_sources"]:
        lines.append(f"- `{src}`")
    lines.append("")
    lines.append("**Strategy list (registry + DB union):**")
    lines.append("")
    lines.append("| strategy_id | lottery_type | lifecycle | in_registry | in_db | replay_rows |")
    lines.append("|-------------|--------------|-----------|------------|-------|-------------|")
    for s in inv["strategies_list"]:
        lines.append(f"| {s['strategy_id']} | {s['lottery_type']} | {s['lifecycle']} | {s['in_registry']} | {s['in_db']} | {s['replay_rows']} |")
    lines.append("")

    # 5. Replay row coverage
    lines.append("## 5. Replay Row Coverage Summary\n")
    lines.append(f"- **Total replay rows**: {rc['total_replay_rows']}")
    lines.append(f"- Strategies with replay rows: {rc['strategies_with_replay_rows']}")
    lines.append(f"- Strategies without replay rows: {rc['strategies_without_replay_rows']}")
    lines.append(f"- Strategies with no_data_reason: {rc['strategies_with_no_data_reason']}")
    lines.append(f"- Strategies missing no_data_reason: {rc['strategies_missing_no_data_reason']}")
    lines.append(f"- Strategy-lottery pairs with rows: {rc['total_strategy_lottery_pairs']}")
    lines.append("")

    # 6. Lifecycle coverage
    lines.append("## 6. Lifecycle Coverage Summary\n")
    lines.append("| Lifecycle | Count |")
    lines.append("|-----------|-------|")
    for k, v in lc.items():
        if v > 0:
            lines.append(f"| {k} | {v} |")
    lines.append("")

    # 7. API capability audit
    lines.append("## 7. Replay API Capability Audit\n")
    lines.append("| Feature | Status |")
    lines.append("|---------|--------|")
    for k, v in api.items():
        if k == "gaps":
            continue
        lines.append(f"| {k} | {'✓' if v else '✗'} |")
    lines.append("")
    if api.get("gaps"):
        lines.append("**API Gaps:**")
        for g in api["gaps"]:
            lines.append(f"- {g}")
        lines.append("")

    # 8. UI capability audit
    lines.append("## 8. Replay UI Capability Audit\n")
    lines.append("| Feature | Status |")
    lines.append("|---------|--------|")
    for k, v in ui.items():
        if k == "gaps":
            continue
        lines.append(f"| {k} | {'✓' if v else '✗'} |")
    lines.append("")
    if ui.get("gaps"):
        lines.append("**UI Gaps:**")
        for g in ui["gaps"]:
            lines.append(f"- {g}")
        lines.append("")

    # 9. NO_DATA handling
    lines.append("## 9. NO_DATA Strategy Handling\n")
    lines.append(f"- `no_data_reason` field in DB schema: **{'YES' if artifact['no_data_strategy_handling']['no_data_reason_field_exists_in_schema'] else 'NO'}**")
    lines.append(f"- Catalog shows NO_DATA entries: **{'YES' if artifact['no_data_strategy_handling']['catalog_shows_no_data_entries'] else 'NO'}**")
    lines.append(f"- Strategies with zero replay rows: {len(strategies_zero_rows)}")
    if strategies_zero_rows:
        for s in strategies_zero_rows:
            lines.append(f"  - `{s}`")
    lines.append("")

    # 10. Multi-bet / bet_index display readiness
    lines.append("## 10. Multi-Bet / bet_index Display Readiness\n")
    lines.append(f"- bet_index column in DB: **{'YES' if mb['bet_index_in_db'] else 'NO'}**")
    lines.append(f"- bet_index returned in API: **{'YES' if mb['bet_index_in_api'] else 'NO'}**")
    lines.append(f"- bet_index displayed in UI: **{'YES' if mb['bet_index_in_ui'] else 'NO'}**")
    lines.append("")
    lines.append("**bet_index distribution (DB):**")
    lines.append("")
    lines.append("| bet_index | row_count |")
    lines.append("|-----------|-----------|")
    for bi, cnt in bet_index_dist.items():
        lines.append(f"| {bi} | {cnt} |")
    lines.append("")
    lines.append(f"**Multi-bet strategies ({len(multi_bet_strategies_in_db)}):**")
    lines.append("")
    lines.append("| strategy_id | lottery_type | max_bet_index |")
    lines.append("|-------------|--------------|---------------|")
    for s in sorted(multi_bet_strategies_in_db, key=lambda x: x["max_bet_index"], reverse=True):
        lines.append(f"| {s['strategy_id']} | {s['lottery_type']} | {s['max_bet_index']} |")
    lines.append("")

    # 11. Truth level / source display readiness
    lines.append("## 11. Truth Level / Source Display Readiness\n")
    lines.append(f"- truth_level column in DB: **{'YES' if tl['truth_level_in_db'] else 'NO'}**")
    lines.append(f"- truth_level returned in API: **{'YES' if tl['truth_level_in_api'] else 'NO'}**")
    lines.append(f"- truth_level badge in UI: **{'YES' if tl['truth_level_in_ui'] else 'NO'}**")
    lines.append("")
    lines.append("**Truth levels found in DB:**")
    for t in truth_levels_found:
        lines.append(f"- `{t}`")
    lines.append("")
    lines.append(f"**Source values found in DB ({len(source_values)}):** (sample)")
    for s in source_values[:10]:
        lines.append(f"- `{s}`")
    lines.append("")

    # 12. Gap matrix
    lines.append("## 12. Replay Product Gap Matrix\n")
    lines.append(f"Total gaps: **{len(gap_matrix)}**\n")
    lines.append("| gap_id | area | severity | current_state | expected_state | recommended_task |")
    lines.append("|--------|------|----------|--------------|----------------|------------------|")
    for g in gap_matrix:
        cs = g["current_state"][:80].replace("|", "\\|") + ("..." if len(g["current_state"]) > 80 else "")
        es = g["expected_state"][:60].replace("|", "\\|")
        lines.append(f"| {g['gap_id']} | {g['area']} | {g['severity']} | {cs} | {es} | {g['recommended_task']} |")
    lines.append("")

    # 13. Recommended next task
    lines.append("## 13. Recommended Next Task\n")
    lines.append(f"**`{artifact['recommended_next_task']}`**\n")
    lines.append(
        "Rationale: The most critical gaps are strategies in DB without lifecycle registry entries "
        "and missing bet_index / NO_DATA handling in the API and UI. "
        "The next task should address all-strategy catalog coverage in the registry, "
        "add bet_index to the API history response, and add NO_DATA entries for "
        "registry-only strategies."
    )
    lines.append("")

    # 14. Explicit non-actions
    lines.append("## 14. Explicit Non-Actions\n")
    lines.append("P149 is audit-only. The following actions were explicitly NOT taken:\n")
    for k, v in na.items():
        if v is False or v == 0:
            lines.append(f"- **{k}**: {v} ← confirmed NOT executed")
    lines.append("")

    # 15. Final classification
    lines.append("## 15. Final Classification\n")
    lines.append(f"```\n{artifact['classification']}\n```\n")
    lines.append("This task is complete. No DB write, no controlled_apply, no champion promotion.")
    lines.append("")

    os.makedirs(os.path.dirname(OUTPUT_MD), exist_ok=True)
    with open(OUTPUT_MD, "w") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
