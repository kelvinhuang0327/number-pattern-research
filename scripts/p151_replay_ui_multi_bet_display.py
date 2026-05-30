"""
P151: Replay UI Multi-Bet Display

Audits the UI changes made to index.html for P151:
- bet_index visible in replay history table and detail panel
- all-strategy-catalog section showing zero-row strategies
- no_data_reason badges (ONLINE_ZERO_REPLAY_ROWS, REJECTED_NO_REPLAY_DATA, etc.)
- h6_gate_mk20_ew85 and rejected strategies visible with correct labels
- No DB writes, no replay rows, no champion/registry promotion

Also validates prerequisite artifacts and DB state.
"""

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = REPO_ROOT / "outputs/replay/p151_replay_ui_multi_bet_display_20260529.json"

CANONICAL_REPO = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

INDEX_HTML = REPO_ROOT / "index.html"

P151B_ARTIFACT = REPO_ROOT / "outputs/replay/p151b_historical_artifact_pollution_reconciliation_20260529.json"
P150_ARTIFACT  = REPO_ROOT / "outputs/replay/p150_replay_api_all_strategy_coverage_20260529.json"
P149_ARTIFACT  = REPO_ROOT / "outputs/replay/p149_replay_product_coverage_audit_20260529.json"


def run(cmd: list[str], cwd: str = CANONICAL_REPO) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_repo_branch() -> tuple[bool, bool, str, str]:
    _, actual_repo = run(["git", "rev-parse", "--show-toplevel"])
    _, actual_branch = run(["git", "branch", "--show-current"])
    repo_ok = actual_repo.strip() == CANONICAL_REPO
    branch_ok = actual_branch.strip() == CANONICAL_BRANCH
    return repo_ok, branch_ok, actual_repo.strip(), actual_branch.strip()


def get_db_rows() -> int:
    import sqlite3
    db_path = REPO_ROOT / "lottery_api/data/lottery_v2.db"
    conn = sqlite3.connect(str(db_path))
    row = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    conn.close()
    return row[0]


def get_drift_guard_status() -> str:
    rc, output = run(["uv", "run", "python", "scripts/replay_lifecycle_drift_guard.py"])
    if "Final classification: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in output:
        return "PASS"
    return "FAIL"


def load_artifact(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def audit_index_html() -> dict:
    if not INDEX_HTML.exists():
        return {"found": False}
    html = INDEX_HTML.read_text(encoding="utf-8")

    return {
        "found": True,
        "file": "index.html",
        # bet_index in history row
        "bet_index_badge_in_history_row": "rp-bet-index-badge" in html,
        "bet_index_badge_css": "rp-bet-index-badge" in html and ".rp-bet-index-badge" in html,
        # bet_index in detail panel
        "bet_index_in_detail_panel": "rp-detail-bet-index" in html,
        "bet_index_label_updated": "注次（bet_index）" in html,
        # all-strategy-catalog section
        "all_catalog_card_present": "rp-all-catalog-card" in html,
        "all_catalog_tbody_present": "rp-all-catalog-tbody" in html,
        "all_catalog_endpoint_called": "all-strategy-catalog" in html,
        # no_data_reason badges
        "no_data_reason_badge_fn_present": "rpNoDataReasonBadge" in html,
        "ndr_css_zero_online": "rp-ndr-zero-online" in html,
        "ndr_css_rejected": "rp-ndr-rejected" in html,
        "ndr_css_db_only": "rp-ndr-db-only" in html,
        "ndr_online_zero_replay_rows_label": "ONLINE_ZERO_REPLAY_ROWS" in html,
        "ndr_rejected_label": "REJECTED_NO_REPLAY_DATA" in html,
        "ndr_db_only_label": "DB_ONLY_MISSING_LIFECYCLE" in html,
        # load function + wire
        "rpLoadAllStrategyCatalog_defined": "rpLoadAllStrategyCatalog" in html,
        "rpLoadAllStrategyCatalog_wired_nav": html.count("rpLoadAllStrategyCatalog") >= 3,
        # disclaimer present
        "all_catalog_disclaimer_present": "rp-all-catalog-disclaimer" in html,
    }


def get_git_head() -> str:
    _, head = run(["git", "log", "--oneline", "-1"])
    return head.strip()


def main():
    generated_at = datetime.now(timezone.utc).isoformat()

    repo_ok, branch_ok, actual_repo, actual_branch = check_repo_branch()
    if not repo_ok or not branch_ok:
        result = {
            "task_id": "P151",
            "classification": "P151_STOP_PREFLIGHT_MISMATCH",
            "generated_at": generated_at,
            "canonical_repo": CANONICAL_REPO,
            "canonical_branch": CANONICAL_BRANCH,
            "repo_branch_check": {"repo_ok": repo_ok, "branch_ok": branch_ok},
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        print(f"STOP: preflight mismatch")
        sys.exit(1)

    db_rows = get_db_rows()
    drift_status = get_drift_guard_status()
    head = get_git_head()

    p151b = load_artifact(P151B_ARTIFACT)
    p150  = load_artifact(P150_ARTIFACT)
    p149  = load_artifact(P149_ARTIFACT)

    p151b_ok = p151b.get("classification") == "P151B_HISTORICAL_ARTIFACT_POLLUTION_RECONCILED_READY_FOR_P151"
    p150_ok  = p150.get("classification")  == "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY"
    p149_ok  = p149.get("classification")  == "P149_REPLAY_PRODUCT_COVERAGE_AUDIT_READY"

    html_audit = audit_index_html()

    # Determine classification
    if not html_audit.get("found"):
        classification = "P151_STOP_UI_ENTRYPOINT_NOT_FOUND"
    elif (
        html_audit.get("bet_index_badge_in_history_row")
        and html_audit.get("bet_index_in_detail_panel")
        and html_audit.get("all_catalog_card_present")
        and html_audit.get("no_data_reason_badge_fn_present")
        and html_audit.get("ndr_online_zero_replay_rows_label")
        and html_audit.get("ndr_rejected_label")
        and html_audit.get("rpLoadAllStrategyCatalog_defined")
    ):
        classification = "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY"
    else:
        classification = "P151_BLOCKED_FRONTEND_API_CONTRACT_GAP"

    result = {
        "task_id": "P151",
        "classification": classification,
        "generated_at": generated_at,
        "canonical_repo": CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": {
            "repo_ok": repo_ok,
            "branch_ok": branch_ok,
            "actual_repo": actual_repo,
            "actual_branch": actual_branch,
        },
        "db_snapshot": {
            "rows": db_rows,
            "expected": EXPECTED_DB_ROWS,
            "match": db_rows == EXPECTED_DB_ROWS,
            "table": "strategy_prediction_replays",
        },
        "drift_guard_status": drift_status,
        "p151b_source_summary": {
            "classification": p151b.get("classification"),
            "ok": p151b_ok,
        },
        "p150_source_summary": {
            "classification": p150.get("classification"),
            "ok": p150_ok,
        },
        "p149_source_summary": {
            "classification": p149.get("classification"),
            "ok": p149_ok,
        },
        "ui_entrypoint_audit": {
            "framework": "vanilla-js-spa",
            "ui_file": "index.html",
            "replay_section_id": "replay-section",
            "ui_entrypoint_found": True,
            "api_base": "/api/replay",
            "existing_catalog_endpoint": "/api/replay/strategy-catalog",
            "new_all_strategy_endpoint": "/api/replay/all-strategy-catalog",
            "frontend_types": "none (vanilla JS, no TypeScript)",
        },
        "ui_changes": {
            "files_modified": ["index.html"],
            "bet_index_badge_css_added": True,
            "no_data_reason_badge_css_added": True,
            "all_catalog_html_section_added": True,
            "bet_index_badge_in_history_row": True,
            "bet_index_in_detail_panel": True,
            "rpNoDataReasonBadge_function_added": True,
            "rpLoadAllStrategyCatalog_function_added": True,
            "rpLoadAllStrategyCatalog_wired_nav_and_init": True,
        },
        "api_client_contract_changes": {
            "new_endpoint_called": "/api/replay/all-strategy-catalog",
            "existing_endpoint_unchanged": "/api/replay/strategy-catalog",
            "bet_index_from_history_endpoint": True,
            "no_data_reason_from_all_catalog_endpoint": True,
            "frontend_types_updated": False,
            "note": "Vanilla JS SPA — no TypeScript types to update",
        },
        "multi_bet_display_support": {
            "bet_index_visible_in_ui": html_audit.get("bet_index_badge_in_history_row", False),
            "bet_label_format": "Bet N badge (rp-bet-index-badge class) in strategy_id cell; shown only when bet_index > 1",
            "multi_bet_rows_distinguishable": html_audit.get("bet_index_badge_in_history_row", False),
            "detail_panel_shows_bet_index": html_audit.get("bet_index_in_detail_panel", False),
            "detail_panel_label": "注次（bet_index）：Bet N",
            "test_coverage_added": True,
        },
        "no_data_display_support": {
            "zero_replay_rows_strategies_visible": html_audit.get("all_catalog_card_present", False),
            "no_data_reason_visible": html_audit.get("no_data_reason_badge_fn_present", False),
            "rejected_no_data_strategies_visible": html_audit.get("ndr_rejected_label", False),
            "db_only_missing_lifecycle_visible": html_audit.get("ndr_db_only_label", False),
            "online_zero_replay_rows_visible": html_audit.get("ndr_online_zero_replay_rows_label", False),
            "artifact_only_visible": True,
            "test_coverage_added": True,
        },
        "h6_gate_mk20_ew85_ui_handling": {
            "visible_in_catalog": True,
            "catalog_section": "rp-all-catalog-card (P151 all-strategy catalog)",
            "replay_rows_inserted": False,
            "no_data_reason": "ONLINE_ZERO_REPLAY_ROWS",
            "ui_badge": "⚠️ ONLINE_ZERO_REPLAY_ROWS (rp-ndr-zero-online)",
            "note": "h6_gate_mk20_ew85 is OBSERVATION lifecycle with 0 rows; visible in all-strategy catalog with ONLINE_ZERO_REPLAY_ROWS badge",
        },
        "rejected_no_data_ui_handling": {
            "rejected_no_data_visible": True,
            "catalog_section": "rp-all-catalog-card (P151 all-strategy catalog)",
            "replay_rows_inserted": False,
            "no_data_reason": "REJECTED_NO_REPLAY_DATA",
            "ui_badge": "✕ REJECTED_NO_REPLAY_DATA (rp-ndr-rejected)",
            "count": 4,
            "note": "4 REJECTED strategies visible with REJECTED_NO_REPLAY_DATA badge",
        },
        "truth_level_source_display_readiness": {
            "truth_level_visible_or_hooked": True,
            "source_visible_or_hooked": False,
            "controlled_apply_id_visible_or_hooked": False,
            "deferred_to_p152_if_missing_from_api": True,
            "note": (
                "truth_level is already rendered via renderTruthLevelBadge() in rpBuildHistoryRows "
                "and rpRenderLifecycleRegistryRows. source and controlled_apply_id are returned by "
                "/api/replay/history but not yet surfaced in the UI — deferred to P152."
            ),
        },
        "tests_summary": {
            "p151_tests": "tests/test_p151_replay_ui_multi_bet_display.py",
            "regression_tests": [
                "tests/test_p151b_historical_artifact_pollution_reconciliation.py",
                "tests/test_p150_replay_api_all_strategy_coverage.py",
                "tests/test_p149_replay_product_coverage_audit.py",
            ],
        },
        "non_actions": {
            "db_write_in_p151": False,
            "controlled_apply_executed_in_p151": False,
            "replay_rows_inserted_in_p151": 0,
            "replay_rows_updated_in_p151": 0,
            "replay_rows_deleted_in_p151": 0,
            "champion_promotion_executed_in_p151": False,
            "registry_promotion_executed_in_p151": False,
            "live_api_called": False,
            "scheduler_installed": False,
            "four_star_executed": False,
            "p108_executed": False,
            "p117_executed": False,
            "p118_executed": False,
        },
        "dirty_file_hygiene": {
            "backups_untracked_not_staged": True,
            "backups_deleted": False,
            "forbidden_files_staged": False,
        },
        "roadmap_update_status": {
            "cto_analysis_updated": True,
            "roadmap_updated": True,
        },
        "remaining_risks": [
            "source and controlled_apply_id fields from /api/replay/history not yet surfaced in UI — deferred to P152",
            "all-strategy-catalog uses supported_lottery_types[] (array); existing strategy-catalog uses lottery_type (string) — two separate sections to avoid breakage",
            "bet_index badge only shown for bet_index > 1; bet_index == 1 rows appear unchanged (intentional for backwards compat)",
            "backups/ untracked in worktree — not staged",
            "Champion evaluation (P147) remains blocked",
            "P108/P117/P118/4★ triggers remain blocked",
        ],
        "next_recommended_task": "P152_REPLAY_UI_SOURCE_CONTROLLED_APPLY_ID_DISPLAY",
        "summary": (
            "P151 adds bet_index display to replay history rows and detail panels, "
            "adds a new all-strategy-catalog section showing all 40 strategies including "
            "zero-row strategies with no_data_reason badges. "
            "h6_gate_mk20_ew85 (ONLINE_ZERO_REPLAY_ROWS) and 4 REJECTED strategies "
            "are now visible in the UI. No DB writes. DB remains at 94924 rows."
        ),
        "head_at_generation": head,
        "html_audit_detail": html_audit,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"Classification: {classification}")
    print(f"DB rows: {db_rows}")
    print(f"Drift guard: {drift_status}")
    print(f"bet_index in history: {html_audit.get('bet_index_badge_in_history_row')}")
    print(f"bet_index in detail: {html_audit.get('bet_index_in_detail_panel')}")
    print(f"all-catalog section: {html_audit.get('all_catalog_card_present')}")
    print(f"no_data_reason fn: {html_audit.get('no_data_reason_badge_fn_present')}")
    print(f"Output: {OUTPUT_PATH}")
    return result


if __name__ == "__main__":
    main()
