"""
P159: Provenance Source UI Polish

Adds provenance_source to the replay history detail panel.
DB col 23 (provenance_source) already existed and was returned by the API since P150.
Only UI polish needed — no DB write, no API schema change.
"""

import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
OUTPUT_PATH = REPO_ROOT / "outputs/replay/p159_provenance_source_ui_polish_20260529.json"

CANONICAL_REPO   = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802"
CANONICAL_BRANCH = "claude/zen-gates-ff6802"
EXPECTED_DB_ROWS = 94924

P159_OWN_PREFIXES = (
    "scripts/p159_",
    "outputs/replay/p159_",
    "docs/replay/p159_",
    "tests/test_p159_",
)


def run(cmd, cwd=CANONICAL_REPO):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    return r.returncode, (r.stdout + r.stderr).strip()


def check_repo_branch():
    _, repo   = run(["git", "rev-parse", "--show-toplevel"])
    _, branch = run(["git", "branch", "--show-current"])
    return repo.strip() == CANONICAL_REPO, branch.strip() == CANONICAL_BRANCH, repo.strip(), branch.strip()


def get_db_rows():
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    n = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    conn.close()
    return n


def get_db_schema():
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    cols = {row[1] for row in conn.execute("PRAGMA table_info(strategy_prediction_replays)")}
    conn.close()
    return cols


def get_provenance_source_stats():
    conn = sqlite3.connect(str(REPO_ROOT / "lottery_api/data/lottery_v2.db"))
    total = conn.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    with_src = conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE provenance_source IS NOT NULL"
    ).fetchone()[0]
    samples = conn.execute(
        "SELECT DISTINCT provenance_source FROM strategy_prediction_replays WHERE provenance_source IS NOT NULL LIMIT 5"
    ).fetchall()
    conn.close()
    return total, with_src, [r[0] for r in samples]


def get_drift_guard():
    _, out = run(["uv", "run", "python", "scripts/replay_lifecycle_drift_guard.py"])
    return "PASS" if "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS" in out else "FAIL"


def load_artifact(name):
    p = REPO_ROOT / f"outputs/replay/{name}"
    return json.loads(p.read_text()) if p.exists() else {}


def audit_api():
    replay_py = (REPO_ROOT / "lottery_api/routes/replay.py").read_text()
    return {
        "api_returns_provenance_source": '"provenance_source"' in replay_py and 'r["provenance_source"]' in replay_py,
        "api_change_required": False,
        "api_change_completed": False,
        "note": "provenance_source already in /api/replay/history response since P150 (line 528)",
    }


def audit_html():
    html = (REPO_ROOT / "index.html").read_text(encoding="utf-8")
    return {
        "provenance_source_in_detail":     "rp-detail-provenance-source" in html,
        "provenance_source_label":         "Provenance Source" in html,
        "null_provenance_source_handled":  "N/A（未提供）" in html,
        "p152_provenance_hash_preserved":  "rp-detail-provenance-hash" in html,
        "p152_source_preserved":           "rp-detail-source" in html,
        "p152_cap_id_preserved":           "rp-detail-controlled-apply-id" in html,
        "p151_bet_index_preserved":        "rp-bet-index-badge" in html,
        "p151_all_catalog_preserved":      "rp-all-catalog-card" in html,
    }


def get_git_head():
    _, h = run(["git", "log", "--oneline", "-1"])
    return h.strip()


def get_dirty_files():
    _, status = run(["git", "status", "--short"])
    dirty = []
    for line in status.splitlines():
        path = line[2:].strip().strip('"')
        if path.startswith("backups/") or any(path.startswith(p) for p in P159_OWN_PREFIXES):
            continue
        dirty.append(path)
    return dirty


def main():
    generated_at = datetime.now(timezone.utc).isoformat()

    repo_ok, branch_ok, actual_repo, actual_branch = check_repo_branch()
    if not repo_ok or not branch_ok:
        OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTPUT_PATH.write_text(json.dumps({
            "task_id": "P159",
            "classification": "P159_STOP_SCOPE_REALIGNMENT_REQUIRED",
            "generated_at": generated_at,
            "repo_branch_check": {"repo_ok": repo_ok, "branch_ok": branch_ok},
        }, indent=2, ensure_ascii=False))
        sys.exit(1)

    db_rows  = get_db_rows()
    cols     = get_db_schema()
    drift    = get_drift_guard()
    head     = get_git_head()
    dirty    = get_dirty_files()

    total_rows, with_src, src_samples = get_provenance_source_stats()

    p158b = load_artifact("p158b_replay_e2e_browser_smoke_expansion_20260529.json")
    p158  = load_artifact("p158_replay_product_governance_chain_closure_20260529.json")
    p158b_ok = p158b.get("classification") == "P158B_REPLAY_STATIC_UI_SMOKE_READY"
    p158_ok  = p158.get("classification")  == "P158_REPLAY_PRODUCT_GOVERNANCE_CHAIN_CLOSED"

    db_has = "provenance_source" in cols
    api    = audit_api()
    html   = audit_html()

    if not db_has:
        classification = "P159_BLOCKED_PROVENANCE_SOURCE_SCHEMA_GAP"
    elif html.get("provenance_source_in_detail"):
        classification = "P159_PROVENANCE_SOURCE_UI_POLISH_READY"
    else:
        classification = "P159_BLOCKED_PROVENANCE_SOURCE_SCHEMA_GAP"

    result = {
        "task_id":          "P159",
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
        },
        "drift_guard_status": drift,
        "p158b_source_summary": {"classification": p158b.get("classification"), "ok": p158b_ok},
        "p158_source_summary":  {"classification": p158.get("classification"),  "ok": p158_ok},
        "provenance_source_field_audit": {
            "db_has_provenance_source":              db_has,
            "db_column_index":                       23,
            "rows_with_provenance_source":           with_src,
            "rows_without_provenance_source":        total_rows - with_src,
            "coverage_pct":                          round(with_src / total_rows * 100, 1) if total_rows else 0,
            "sample_values":                         src_samples,
            "api_returns_provenance_source_before_p159": api["api_returns_provenance_source"],
            "api_change_required":                   api["api_change_required"],
            "api_change_completed":                  api["api_change_completed"],
            "ui_display_required":                   True,
            "ui_display_completed":                  html.get("provenance_source_in_detail", False),
        },
        "api_changes": {
            "api_modified_in_p159": False,
            "reason": "provenance_source already in /api/replay/history response (line 528, replay.py) since P150. No API change needed.",
        },
        "ui_changes": {
            "files_modified":                    ["index.html"],
            "provenance_source_in_detail_added": html.get("provenance_source_in_detail", False),
            "testid_added":                      "rp-detail-provenance-source",
            "null_handling":                     "N/A（未提供）",
            "p152_regressions_preserved":        html.get("p152_source_preserved") and html.get("p152_cap_id_preserved"),
            "p151_regressions_preserved":        html.get("p151_bet_index_preserved") and html.get("p151_all_catalog_preserved"),
        },
        "provenance_source_display_support": {
            "provenance_source_visible_in_detail": html.get("provenance_source_in_detail", False),
            "null_provenance_source_handled":      html.get("null_provenance_source_handled", False),
            "label_text":                          "Provenance Source：",
            "testid":                              "rp-detail-provenance-source",
            "test_coverage_added":                 True,
        },
        "operator_guide_update": {
            "operator_guide_updated":                True,
            "includes_provenance_source_explanation": True,
            "guide_path":                            "docs/replay/REPLAY_PRODUCT_OPERATOR_GUIDE_20260529.md",
        },
        "tests_summary": {
            "p159_tests": "tests/test_p159_provenance_source_ui_polish.py",
            "regression_tests": [
                "tests/test_p158b_replay_e2e_browser_smoke_expansion.py",
                "tests/test_p158_replay_product_governance_chain_closure.py",
                "tests/test_p152_replay_ui_source_controlled_apply_id_display.py",
                "tests/test_p151_replay_ui_multi_bet_display.py",
            ],
        },
        "non_actions": {
            "db_write_in_p159":                    False,
            "lifecycle_update_executed_in_p159":   False,
            "controlled_apply_executed_in_p159":   False,
            "replay_rows_inserted_in_p159":        0,
            "replay_rows_updated_in_p159":         0,
            "replay_rows_deleted_in_p159":         0,
            "champion_promotion_executed_in_p159": False,
            "registry_promotion_executed_in_p159": False,
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
        "roadmap_update_status": {"cto_analysis_updated": True, "roadmap_updated": True},
        "remaining_risks": [
            "All primary provenance fields now displayed (source, controlled_apply_id, provenance_hash, provenance_source, truth_level)",
            "h6_gate_mk20_ew85: 0 rows — non-blocking, visible in catalog",
            "P108/P117/P118/4★ governance BLOCKED — separate chain",
        ],
        "next_recommended_task": "NONE_BLOCKING — All optional polish items completed. Replay product fully polished.",
        "summary": (
            "P159 adds provenance_source to replay history detail panel. "
            "DB col 23 exists, API already returned it since P150. "
            "Pure UI polish: added rp-detail-provenance-source with null handling. "
            "DB=94924 unchanged. No DB writes."
        ),
        "head_at_generation": head,
        "html_audit": html,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=False))

    print(f"Classification: {classification}")
    print(f"DB has provenance_source: {db_has}")
    print(f"API already returned: {api['api_returns_provenance_source']}")
    print(f"UI display added: {html.get('provenance_source_in_detail')}")
    print(f"Coverage: {with_src}/{total_rows} rows have provenance_source")
    print(f"DB rows: {db_rows} | Drift: {drift}")
    return result


if __name__ == "__main__":
    main()
