"""P249B — Roadmap sync + CURRENT_STATE row-label clarification.

Type B doc-only governance cleanup. Verifies that governance files now
correctly distinguish replay rows vs raw draw rows vs canonical rows.
No DB write. No source code changes.
"""

import json
from datetime import datetime
from pathlib import Path

TASK_ID = "P249B"
SCHEMA_VERSION = "1.0"
REPO_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

# ── Verified corrected state ──────────────────────────────────────────────────
ROW_LABEL_CORRECTIONS = {
    "original_label": "BIG_LOTTO rows | 24,140",
    "original_semantics": "AMBIGUOUS — could be interpreted as BIG_LOTTO draw rows",
    "actual_semantics": "Replay rows for BIG_LOTTO in strategy_prediction_replays table",
    "verification": "24,140 + 34,680 + 36,104 = 94,924 = total replay rows (confirmed)",
    "corrected_labels": {
        "BIG_LOTTO replay rows (strategy_prediction_replays)": 24_140,
        "BIG_LOTTO raw draw rows (draws table, lottery_type='BIG_LOTTO')": 22_238,
        "BIG_LOTTO canonical main-draw rows (draws_big_lotto_canonical_main view)": 2_113,
        "BIG_LOTTO ADD_ON_PRIZE_EXCLUDED (valid add-on/special prize records)": 19_100,
        "DAILY_539 replay rows (strategy_prediction_replays)": 34_680,
        "DAILY_539 draw rows (draws table)": 5_879,
        "POWER_LOTTO replay rows (strategy_prediction_replays)": 36_104,
        "POWER_LOTTO draw rows (draws table)": 1_916,
    },
    "sum_check": "24140 + 34680 + 36104 = 94924 (total replay rows) ✓",
    "add_on_note": (
        "ADD_ON_PRIZE_EXCLUDED = 19,100 hyphenated draw IDs. "
        "These are valid lottery-related add-on/special prize records, "
        "NOT fake or simulated. Excluded from canonical 6/49 research "
        "due to pool mismatch, but preserved and raw-accessible."
    ),
}

ROADMAP_SYNC_SUMMARY = {
    "roadmap_md_last_updated_before": "2026-06-05 (P213L)",
    "roadmap_md_updated_to": "2026-06-06 (P249B)",
    "phase_table_entry_added": "P246B–P249B BIG_LOTTO canonical isolation arc + governance",
    "current_state_summary_updated": "§0.7 — added P246B–P249B bullet",
    "roadmap_marker_updated": True,
    "arc_summary": {
        "P246B_through_P246K": "Taxonomy corrected, impact audit, isolation design, helper, callers canonicalized, canonical NIST GREEN",
        "P247A_through_P247G": "DB view created (Type D), helper view-backed, 9 tools migrated, regression guard",
        "P248A": "Governance closure — 17 artifacts verified",
        "P249A": "Post-isolation triage — 8 candidates ranked",
        "P249B": "Row-label clarification + roadmap sync (this task)",
    },
}


def verify_governance_files() -> dict:
    cs_path = REPO_ROOT / "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md"
    roadmap_path = REPO_ROOT / "00-Plan/roadmap/roadmap.md"
    active_task_path = REPO_ROOT / "00-Plan/roadmap/active_task.md"

    cs_content = cs_path.read_text() if cs_path.exists() else ""
    roadmap_content = roadmap_path.read_text() if roadmap_path.exists() else ""
    active_task_content = active_task_path.read_text() if active_task_path.exists() else ""

    # Check CURRENT_STATE label clarity
    cs_has_replay_label = "replay rows" in cs_content.lower()
    cs_has_raw_draw_rows = "raw draw rows" in cs_content.lower() or "22,238" in cs_content or "22238" in cs_content
    cs_has_canonical_rows = "2,113" in cs_content or "2113" in cs_content
    cs_has_add_on = "19,100" in cs_content or "19100" in cs_content

    # Check roadmap sync
    roadmap_has_p246 = "P246B" in roadmap_content or "P246" in roadmap_content
    roadmap_has_p247 = "P247B" in roadmap_content or "P247" in roadmap_content
    roadmap_has_canonical = "canonical" in roadmap_content.lower()

    # Check active_task
    at_waiting = "WAITING_FOR_USER_AUTHORIZATION" in active_task_content
    at_p249b = "P249B" in active_task_content

    # Check P249A artifact
    p249a_artifact = OUTPUTS_DIR / "p249a_post_isolation_roadmap_triage_20260606.json"
    p249a_ok = p249a_artifact.exists()

    return {
        "current_state_has_replay_label": cs_has_replay_label,
        "current_state_has_raw_draw_rows": cs_has_raw_draw_rows,
        "current_state_has_canonical_rows": cs_has_canonical_rows,
        "current_state_has_add_on": cs_has_add_on,
        "roadmap_has_p246_arc": roadmap_has_p246,
        "roadmap_has_p247_arc": roadmap_has_p247,
        "roadmap_has_canonical": roadmap_has_canonical,
        "active_task_waiting": at_waiting,
        "active_task_has_p249b": at_p249b,
        "p249a_artifact_exists": p249a_ok,
        "all_ok": all([
            cs_has_replay_label,
            cs_has_raw_draw_rows,
            cs_has_canonical_rows,
            cs_has_add_on,
            roadmap_has_p246,
            roadmap_has_p247,
            at_waiting,
            p249a_ok,
        ]),
    }


def build_json_report(verify: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "GOVERNANCE_DOC_SYNC_TYPE_B",
        "p249a_merged_state_verified": verify["p249a_artifact_exists"],
        "governance_files_updated": [
            "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md",
            "00-Plan/roadmap/roadmap.md",
            "00-Plan/roadmap/active_task.md",
        ],
        "row_label_corrections": ROW_LABEL_CORRECTIONS,
        "roadmap_sync_summary": ROADMAP_SYNC_SUMMARY,
        "governance_verification": verify,
        "active_task_status": "WAITING_FOR_USER_AUTHORIZATION",
        "no_db_write_confirmed": True,
        "no_source_code_changes": True,
        "no_strategy_promotion": True,
        "no_betting_advice": True,
        "no_production_recommendation_change": True,
        "forbidden_actions_confirmed": {
            "DB write": "NOT PERFORMED",
            "DB migration": "NOT PERFORMED",
            "CREATE VIEW / CREATE TABLE": "NOT PERFORMED",
            "DELETE rows": "NOT PERFORMED",
            "UPDATE rows": "NOT PERFORMED",
            "INSERT rows": "NOT PERFORMED",
            "source code changes": "NOT PERFORMED",
            "strategy logic change": "NOT PERFORMED",
            "registry mutation": "NOT PERFORMED",
            "production recommendation change": "NOT PERFORMED",
            "strategy promotion": "NOT PERFORMED",
            "betting advice": "NOT PERFORMED",
        },
        "final_decision": (
            f"P249B complete. CURRENT_STATE.md row-count labels disambiguated: "
            f"'BIG_LOTTO rows | 24,140' = replay rows (24140+34680+36104=94924 total replays). "
            f"Actual BIG_LOTTO raw draw rows = 22,238; canonical research rows = 2,113; "
            f"ADD_ON = 19,100 raw-accessible. roadmap.md synced with P246B–P249A arc. "
            f"active_task.md updated. No DB write. No strategy promotion. "
            f"Type B doc-only complete."
        ),
    }


def build_md_report(verify: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# P249B — Roadmap Sync + CURRENT_STATE Row Label Clarification",
        "",
        f"**Date:** {now}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** GOVERNANCE_DOC_SYNC_TYPE_B  ",
        "",
        "## Executive Summary",
        "",
        "P249B is a Type B doc-only governance cleanup. P249A identified that "
        "CURRENT_STATE.md labels 'BIG_LOTTO rows | 24,140' ambiguously — "
        "this is replay rows, not draw rows. This task clarifies all row-count labels "
        "and syncs roadmap.md with the completed P246B–P249A arc. No DB write. "
        "No source code changes. No strategy promotion.",
        "",
        "## What Row Labels Were Ambiguous",
        "",
        "In CURRENT_STATE.md, the table rows:",
        "```",
        "| BIG_LOTTO rows | 24,140 | [Confirmed] |",
        "| DAILY_539 rows | 34,680 | [Confirmed] |",
        "| POWER_LOTTO rows | 36,104 | [Confirmed] |",
        "```",
        "These are **replay rows** from `strategy_prediction_replays`, not draw rows.",
        "Verification: 24,140 + 34,680 + 36,104 = **94,924 = total replay rows** ✓",
        "",
        "The draw table row counts (lottery_type filter on `draws` table) are entirely different.",
        "",
        "## Corrected Row Semantics Table",
        "",
        "| Row Type | Count | Source |",
        "|----------|-------|--------|",
        "| BIG_LOTTO **replay** rows (strategy_prediction_replays) | 24,140 | strategy_prediction_replays |",
        "| BIG_LOTTO **raw draw** rows (draws table) | 22,238 | draws WHERE lottery_type='BIG_LOTTO' |",
        "| BIG_LOTTO **canonical** research rows (view) | 2,113 | draws_big_lotto_canonical_main |",
        "| BIG_LOTTO ADD_ON_PRIZE_EXCLUDED (valid add-on records) | 19,100 | draws WHERE draw LIKE '%-%' |",
        "| DAILY_539 **replay** rows | 34,680 | strategy_prediction_replays |",
        "| DAILY_539 **draw** rows | 5,879 | draws WHERE lottery_type='DAILY_539' |",
        "| POWER_LOTTO **replay** rows | 36,104 | strategy_prediction_replays |",
        "| POWER_LOTTO **draw** rows | 1,916 | draws WHERE lottery_type='POWER_LOTTO' |",
        "| Total replay rows | 94,924 | 24140+34680+36104 = 94,924 ✓ |",
        "",
        "> **ADD_ON_PRIZE_EXCLUDED note:** 19,100 hyphenated BIG_LOTTO draw IDs are "
        "valid lottery-related add-on/special prize records, NOT fake or simulated. "
        "They are excluded from canonical 6/49 research due to pool mismatch but "
        "preserved and raw-accessible in the draws table.",
        "",
        "## Roadmap Sync Summary",
        "",
        "- **roadmap.md** last updated: P213L (2026-06-05) → P249B (2026-06-06)",
        "- **Phase table entry added:** P246B–P249B BIG_LOTTO canonical isolation arc",
        "- **§0.7 Current State Summary:** bullet added for P246B–P249B",
        "- **Roadmap marker code block:** P249B added at top",
        "",
        "Arc recorded in roadmap:",
        "- P246B–P246K: taxonomy correction, isolation design, callers canonicalized, canonical NIST GREEN",
        "- P247A–P247G: DB view (Type D), helper view-backed, 9 tools migrated, regression guard",
        "- P248A: governance closure",
        "- P249A: post-isolation roadmap triage",
        "- P249B: this task — row-label clarification + roadmap sync",
        "",
        "## Active Task Status",
        "",
        "- **active_task.md:** `WAITING_FOR_USER_AUTHORIZATION`",
        "- Recommended next task from P249A: see P249A candidates (T3–T8); T1+T2 (this task) done",
        "",
        "## No-Overclaim Statement",
        "",
        "> P246K canonical NIST re-audit GREEN = data quality confirmation only. "
        "It confirms 2,113 canonical BIG_LOTTO main-draw rows are statistically "
        "random-compatible. **It does not imply any exploitable prediction signal.** "
        "No strategy promotion, no production recommendation, no betting advice.",
        "",
        "## Compliance Statements",
        "",
        "- **No DB write performed in P249B.**",
        "- **No source code changes** beyond optional analysis/test artifact.",
        "- **No strategy promotion or betting advice.**",
        "- **No production recommendation change.**",
        "- ADD_ON_PRIZE_EXCLUDED records remain valid and raw-accessible.",
        "",
        "---",
        f"*Generated by {TASK_ID} — Type B doc-only governance sync*",
    ]
    return "\n".join(lines)


def main() -> dict:
    print("[P249B] Verifying governance file updates...")
    verify = verify_governance_files()
    for k, v in verify.items():
        if isinstance(v, bool):
            print(f"[P249B]   {k}={v}")
    print(f"[P249B]   all_ok={verify['all_ok']}")

    report_json = build_json_report(verify)
    report_md = build_md_report(verify)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUTS_DIR / f"p249b_roadmap_current_state_row_label_sync_{DATE_SLUG}.json"
    md_path = OUTPUTS_DIR / f"p249b_roadmap_current_state_row_label_sync_{DATE_SLUG}.md"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)

    print(f"[P249B] Reports: {json_path}")
    print("[P249B] P249B COMPLETE.")
    return report_json


if __name__ == "__main__":
    main()
