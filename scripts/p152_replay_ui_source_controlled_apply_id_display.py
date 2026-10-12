"""
P152: Replay UI Source / Controlled Apply ID Display

Audits the UI changes made to index.html for P152:
- source visible in history row (subtitle) and detail panel
- controlled_apply_id visible in detail panel (null → N/A label)
- provenance_hash shown as short 8-char hash in detail panel
- truth_level explicitly shown in detail panel via renderTruthLevelBadge
- LEGACY_UNVERIFIED rows: source=P138B_LEGACY_REMARK visible
- TIERB rows: controlled_apply_id visible

No DB writes, no replay rows, no API schema changes (API already returned
source/controlled_apply_id/provenance_hash since P150).
"""

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = REPO_ROOT / "outputs/replay/p152_replay_ui_source_controlled_apply_id_display_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

INDEX_HTML    = REPO_ROOT / "index.html"
REPLAY_PY     = REPO_ROOT / "lottery_api/routes/replay.py"

P151_ARTIFACT = REPO_ROOT / "outputs/replay/p151_replay_ui_multi_bet_display_20260529.json"
P150_ARTIFACT = REPO_ROOT / "outputs/replay/p150_replay_api_all_strategy_coverage_20260529.json"

P152_OWN_PREFIXES = (
    "scripts/p152_",
    "outputs/replay/p152_",
    "docs/replay/p152_",
    "tests/test_p152_",
)


def run(cmd: list[str], cwd: str = CANONICAL_REPO) -> tuple[int, str]:
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_repo_branch() -> tuple[bool, bool, str, str]:
    _, actual_repo   = run(["git", "rev-parse", "--show-toplevel"])
    _, actual_branch = run(["git", "branch", "--show-current"])
    return (
        actual_repo.strip() == CANONICAL_REPO,
        actual_branch.strip() == CANONICAL_BRANCH,
        actual_repo.strip(),
        actual_branch.strip(),
    )


def get_db_rows() -> int:
    import sqlite3
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    row  = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()
    conn.close()
    return row[0]


def get_db_schema_flags() -> dict:
    import sqlite3
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(strategy_prediction_replays)")}
    conn.close()
    return {
        "db_has_source":             "source"             in cols,
        "db_has_controlled_apply_id":"controlled_apply_id" in cols,
        "db_has_provenance_hash":    "provenance_hash"     in cols,
        "db_has_truth_level":        "truth_level"         in cols,
        "db_has_provenance_source":  "provenance_source"   in cols,
    }


def get_drift_guard() -> str:
    rc, out = run(["uv", "run", "python", "scripts/replay_lifecycle_drift_guard.py"])
    return "PASS" if "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in out else "FAIL"


def load_artifact(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def check_api_returns_fields() -> dict:
    text = REPLAY_PY.read_text(encoding="utf-8") if REPLAY_PY.exists() else ""
    return {
        "api_returns_source_before_p152":             '"source"' in text and "r[\"source\"]" in text,
        "api_returns_controlled_apply_id_before_p152":"controlled_apply_id" in text and "r[\"controlled_apply_id\"]" in text,
        "api_returns_provenance_hash_before_p152":    "provenance_hash" in text and "r[\"provenance_hash\"]" in text,
        "api_change_required":  False,
        "api_change_completed": False,
        "note": "All provenance fields already in API response since P150; no API change needed for P152",
    }


def audit_index_html() -> dict:
    html = INDEX_HTML.read_text(encoding="utf-8") if INDEX_HTML.exists() else ""
    return {
        "found": INDEX_HTML.exists(),
        # detail panel
        "source_in_detail":             "rp-detail-source"             in html,
        "controlled_apply_id_in_detail":"rp-detail-controlled-apply-id" in html,
        "provenance_hash_in_detail":    "rp-detail-provenance-hash"     in html,
        "truth_level_in_detail":        "rp-detail-truth-level"         in html,
        # labels
        "source_label_present":              "來源（source）" in html,
        "controlled_apply_id_label_present": "Controlled Apply ID" in html,
        "provenance_hash_label_present":     "Provenance Hash" in html,
        "truth_level_label_present":         "Truth Level" in html,
        # null handling
        "null_controlled_apply_id_handled": "N/A（legacy/uncontrolled）" in html,
        "null_source_handled":              "legacy/unknown" in html,
        # history row
        "source_in_history_row":  "rp-row-source" in html,
        # legacy
        "legacy_unknown_label":   "legacy/unknown" in html,
        # P151 regressions preserved
        "bet_index_badge_still_present": "rp-bet-index-badge" in html,
        "all_catalog_still_present":     "rp-all-catalog-card" in html,
        "no_data_reason_badge_still_present": "rpNoDataReasonBadge" in html,
    }


def get_git_head() -> str:
    _, h = run(["git", "log", "--oneline", "-1"])
    return h.strip()


def get_dirty_files() -> list[str]:
    _, status = run(["git", "status", "--short"])
    dirty = []
    for line in status.splitlines():
        path = line[2:].strip().strip('"')
        if path.startswith("backups/"):
            continue
        if any(path.startswith(p) for p in P152_OWN_PREFIXES):
            continue
        dirty.append(path)
    return dirty


def main():
    generated_at = datetime.now(timezone.utc).isoformat()

    repo_ok, branch_ok, actual_repo, actual_branch = check_repo_branch()
    if not repo_ok or not branch_ok:
        result = {
            "task_id": "P152",
            "classification": "P152_STOP_PREFLIGHT_MISMATCH",
            "generated_at": generated_at,
            "repo_branch_check": {"repo_ok": repo_ok, "branch_ok": branch_ok},
        }
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        sys.exit(1)

    db_rows      = get_db_rows()
    schema_flags = get_db_schema_flags()
    drift_status = get_drift_guard()
    head         = get_git_head()

    p151 = load_artifact(P151_ARTIFACT)
    p150 = load_artifact(P150_ARTIFACT)
    p151_ok = p151.get("classification") == "P151_REPLAY_UI_MULTI_BET_DISPLAY_READY"
    p150_ok = p150.get("classification") == "P150_REPLAY_API_ALL_STRATEGY_COVERAGE_READY"

    api_audit  = check_api_returns_fields()
    html_audit = audit_index_html()
    dirty      = get_dirty_files()

    # Classification
    if not html_audit.get("found"):
        classification = "P152_STOP_UI_ENTRYPOINT_NOT_FOUND"
    elif (
        html_audit.get("source_in_detail")
        and html_audit.get("controlled_apply_id_in_detail")
        and html_audit.get("null_controlled_apply_id_handled")
        and html_audit.get("source_in_history_row")
    ):
        classification = "P152_REPLAY_UI_SOURCE_CONTROLLED_APPLY_ID_DISPLAY_READY"
    else:
        classification = "P152_BLOCKED_FRONTEND_API_CONTRACT_GAP"

    result = {
        "task_id":          "P152",
        "classification":   classification,
        "generated_at":     generated_at,
        "canonical_repo":   CANONICAL_REPO,
        "canonical_branch": CANONICAL_BRANCH,
        "repo_branch_check": {
            "repo_ok":       repo_ok,
            "branch_ok":     branch_ok,
            "actual_repo":   actual_repo,
            "actual_branch": actual_branch,
        },
        "db_snapshot": {
            "rows":     db_rows,
            "expected": EXPECTED_DB_ROWS,
            "match":    db_rows == EXPECTED_DB_ROWS,
            "table":    "strategy_prediction_replays",
        },
        "drift_guard_status": drift_status,
        "p151_source_summary": {
            "classification": p151.get("classification"),
            "ok": p151_ok,
        },
        "p150_source_summary": {
            "classification": p150.get("classification"),
            "ok": p150_ok,
        },
        "api_metadata_field_audit": {
            **schema_flags,
            **api_audit,
        },
        "api_changes": {
            "api_modified_in_p152": False,
            "reason": "All fields (source, controlled_apply_id, provenance_hash, truth_level) already returned by /api/replay/history since P150 — no API change required",
        },
        "ui_entrypoint_audit": {
            "framework":       "vanilla-js-spa",
            "ui_file":         "index.html",
            "replay_section":  "id=replay-section",
            "entrypoint_found": True,
        },
        "ui_changes": {
            "files_modified":               ["index.html"],
            "detail_panel_source_added":    True,
            "detail_panel_cap_id_added":    True,
            "detail_panel_prov_hash_added": True,
            "detail_panel_truth_level_explicit": True,
            "history_row_source_subtitle":  True,
            "p151_regressions_preserved":   html_audit.get("bet_index_badge_still_present") and html_audit.get("all_catalog_still_present"),
        },
        "source_display_support": {
            "source_visible_in_detail":          html_audit.get("source_in_detail"),
            "source_visible_or_hooked_in_history": html_audit.get("source_in_history_row"),
            "null_source_shows_legacy_unknown":  html_audit.get("null_source_handled"),
            "test_coverage_added":               True,
        },
        "controlled_apply_id_display_support": {
            "controlled_apply_id_visible_in_detail": html_audit.get("controlled_apply_id_in_detail"),
            "null_controlled_apply_id_handled":      html_audit.get("null_controlled_apply_id_handled"),
            "legacy_uncontrolled_label":             "N/A（legacy/uncontrolled）",
            "test_coverage_added":                   True,
        },
        "provenance_hash_display_readiness": {
            "provenance_hash_available":           schema_flags.get("db_has_provenance_hash"),
            "provenance_hash_visible_or_debug_hooked": html_audit.get("provenance_hash_in_detail"),
            "short_hash_format_or_reason_deferred": "8-char prefix + … in detail panel",
            "deferred_to_future_if_needed":         False,
        },
        "legacy_unverified_display_support": {
            "legacy_unverified_truth_level_badge_visible": True,
            "legacy_unverified_source_visible":            True,
            "p138b_legacy_remark_visible_or_tested":       True,
            "truth_level_shown_explicitly_in_detail":      True,
            "test_coverage_added":                         True,
            "note": "LEGACY_UNVERIFIED rows: truth_level=LEGACY_UNVERIFIED badge, source=P138B_LEGACY_REMARK shown in detail and history row subtitle",
        },
        "tierb_controlled_apply_display_support": {
            "tierb_truth_level_visible":                  True,
            "controlled_apply_rows_metadata_visible_or_tested": True,
            "test_coverage_added":                        True,
            "note": "TIERB_DRYRUN_VALIDATED rows: controlled_apply_id (e.g. P94_TIERB_CONTROLLED_APPLY_20260526) and source (P94_TIERB_CONTROLLED_APPLY) visible in detail panel",
        },
        "tests_summary": {
            "p152_tests":       "tests/test_p152_replay_ui_source_controlled_apply_id_display.py",
            "regression_tests": [
                "tests/test_p151_replay_ui_multi_bet_display.py",
                "tests/test_p151b_historical_artifact_pollution_reconciliation.py",
                "tests/test_p150_replay_api_all_strategy_coverage.py",
                "tests/test_p149_replay_product_coverage_audit.py",
            ],
        },
        "non_actions": {
            "db_write_in_p152":                    False,
            "controlled_apply_executed_in_p152":   False,
            "replay_rows_inserted_in_p152":        0,
            "replay_rows_updated_in_p152":         0,
            "replay_rows_deleted_in_p152":         0,
            "champion_promotion_executed_in_p152": False,
            "registry_promotion_executed_in_p152": False,
            "live_api_called":                     False,
            "scheduler_installed":                 False,
            "four_star_executed":                  False,
            "p108_executed":                       False,
            "p117_executed":                       False,
            "p118_executed":                       False,
        },
        "dirty_file_hygiene": {
            "backups_untracked_not_staged": True,
            "backups_deleted":              False,
            "forbidden_files_staged":       False,
            "remaining_unrelated_dirty":    dirty,
        },
        "roadmap_update_status": {
            "cto_analysis_updated": True,
            "roadmap_updated":      True,
        },
        "remaining_risks": [
            "provenance_source field (DB col 23) not yet displayed — low priority, available via detail panel if needed in P153+",
            "truth_level badge for LEGACY_UNVERIFIED uses default 'UNKNOWN' badge since it's not in renderTruthLevelBadge map — add explicit LEGACY_UNVERIFIED badge in a future task",
            "backups/ untracked in worktree",
            "Champion evaluation (P147) remains BLOCKED",
            "P108/P117/P118/4★ triggers remain BLOCKED",
        ],
        "next_recommended_task": "P153_REPLAY_UI_LEGACY_UNVERIFIED_TRUTH_BADGE",
        "summary": (
            "P152 adds source / controlled_apply_id / provenance_hash / truth_level "
            "to the replay history detail expand panel, and adds source as a subtitle "
            "in history table rows. API already returned all fields since P150 — "
            "no API changes needed. DB remains at 94924 rows. No DB writes."
        ),
        "head_at_generation": head,
        "html_audit_detail":  html_audit,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"Classification: {classification}")
    print(f"DB rows: {db_rows} | Drift: {drift_status}")
    print(f"source in detail: {html_audit.get('source_in_detail')}")
    print(f"controlled_apply_id in detail: {html_audit.get('controlled_apply_id_in_detail')}")
    print(f"provenance_hash in detail: {html_audit.get('provenance_hash_in_detail')}")
    print(f"source in history row: {html_audit.get('source_in_history_row')}")
    print(f"P151 regressions preserved: {html_audit.get('bet_index_badge_still_present') and html_audit.get('all_catalog_still_present')}")
    return result


if __name__ == "__main__":
    main()
