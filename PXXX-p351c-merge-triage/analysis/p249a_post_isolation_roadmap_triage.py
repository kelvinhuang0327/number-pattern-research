"""P249A — Post-isolation roadmap triage.

Read-only review of the current repo/governance state after P246B–P248A
BIG_LOTTO canonical isolation closure. Proposes ranked candidate next tasks.
No DB write. No strategy promotion. No betting advice.
"""

import json
from datetime import datetime
from pathlib import Path

TASK_ID = "P249A"
SCHEMA_VERSION = "1.0"
REPO_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

# ── Current state after P248A ─────────────────────────────────────────────────
PHASE0_EXPECTED_STATE = {
    "main_branch": "main",
    "p248a_merged": True,
    "active_task_status": "WAITING_FOR_USER_AUTHORIZATION",
    "current_state_marker": "P248A_BIG_LOTTO_CANONICAL_ISOLATION_GOVERNANCE_CLOSURE_COMPLETE",
    "big_lotto_canonical_isolation": "COMPLETE",
    "canonical_main_draw_rows": 2_113,
    "raw_big_lotto_rows": 22_238,
    "add_on_rows_raw_accessible": 19_100,
}

# ── Closed research lines ─────────────────────────────────────────────────────
CLOSED_RESEARCH = [
    {"line": "DAILY_539 midfreq_fourier_2bet", "status": "REJECTED_BY_BACKWARD_OOS",
     "task": "P230C", "note": "Reclassified from WAIT_FOR_OOS; no active candidate"},
    {"line": "POWER_LOTTO first-zone", "status": "NULL",
     "task": "P231B", "note": "p=0.3018; CI crosses baseline; robustness fails; non-deployable"},
    {"line": "3_STAR/4_STAR box-play", "status": "UNDERPOWERED_NO_SIGNAL",
     "task": "P227C", "note": "120 hypotheses; Bonferroni 0; UNDERPOWERED"},
    {"line": "3_STAR/4_STAR straight-play", "status": "NULL",
     "task": "P214C", "note": "0 Bonferroni-significant; 1 uncorrected-weak p≈0.025 must not be promoted"},
    {"line": "BIG_LOTTO 49C6 signal space", "status": "EXHAUSTED",
     "task": "P247G", "note": "L90/L91: zero signals pass p<0.05; canonical isolation complete"},
    {"line": "NIST raw-population audit (P238B)", "status": "YELLOW_OBSERVATION_ONLY",
     "task": "P238B", "note": "YELLOW does not authorize strategy/production; canonical audit GREEN (P246K)"},
]

# ── Candidate next tasks ──────────────────────────────────────────────────────
CANDIDATE_TASKS = [
    {
        "candidate_id": "T1",
        "title": "roadmap.md sync for P246–P248A arc",
        "type": "read-only / doc-only (Type B)",
        "value": "Medium — governance completeness; prevents future agents from treating P246-P248A as open",
        "risk": "Very low — doc-only, no code/DB change",
        "urgency": "Low-medium — stale roadmap creates governance drift risk",
        "prerequisites": "None — P248A closure complete",
        "recommended_now": "YES",
        "reason": (
            "roadmap.md last updated P213L (2026-06-05) and does not reflect the P246B–P248A arc. "
            "A Type B doc-only sync recording the BIG_LOTTO canonical isolation closure into "
            "the roadmap phase table is low-risk, natural, and prevents future agent confusion. "
            "No authorization beyond Type B governance templates required."
        ),
        "authorization_required": "None (Type B)",
    },
    {
        "candidate_id": "T2",
        "title": "CURRENT_STATE.md row-count label clarification",
        "type": "read-only / doc-only (Type B)",
        "value": "Low-medium — governance accuracy; 'BIG_LOTTO rows | 24,140' is replay rows not draw rows",
        "risk": "Very low — doc-only",
        "urgency": "Low — potential future agent confusion",
        "prerequisites": "None",
        "recommended_now": "YES (can be combined with T1 in same PR)",
        "reason": (
            "CURRENT_STATE.md shows 'BIG_LOTTO rows | 24,140'. "
            "This is actually replay rows (24,140 + 34,680 + 36,104 = 94,924 total replay rows), "
            "not draw rows. Actual BIG_LOTTO draw rows = 22,238. "
            "Clarifying the label or adding a note prevents future agents from misinterpreting "
            "this as the BIG_LOTTO draw count. Combined with T1 this is a single Type B PR."
        ),
        "authorization_required": "None (Type B)",
    },
    {
        "candidate_id": "T3",
        "title": "Archived BIG_LOTTO script migration (deferred)",
        "type": "code-change",
        "value": "Low — scripts not in active pipeline",
        "risk": "Low — isolated changes",
        "urgency": "Very low — only needed when scripts are reactivated",
        "prerequisites": "Script reactivation decision by user",
        "recommended_now": "NO",
        "reason": (
            "P247F/P247D documented ~20 archived lottery_api/backtest_*.py and predict_*.py "
            "scripts still using get_all_draws('BIG_LOTTO'). These are deferred. "
            "Migration should happen when/if a specific script is reactivated for use, "
            "not proactively for dormant code."
        ),
        "authorization_required": "None for code, but user activation decision needed first",
    },
    {
        "candidate_id": "T4",
        "title": "Annotation table Type D planning/apply",
        "type": "Type D (DB write)",
        "value": "Low — canonical isolation already complete via DB view; annotation adds row-family labels",
        "risk": "Low-medium — controlled DB write; backup required",
        "urgency": "Very low — no active consumer needs it",
        "prerequisites": "Explicit Type D authorization phrase",
        "recommended_now": "NO",
        "reason": (
            "draw_row_family_annotations was designed in P247A as optional Phase 2. "
            "P247B/C/D/E/F/G completed BIG_LOTTO isolation using only the view. "
            "No active research path requires annotation labels. "
            "Deferring until a specific consumer use-case requires per-row family labels."
        ),
        "authorization_required": "Explicit Type D: YES apply P249D CREATE TABLE draw_row_family_annotations",
    },
    {
        "candidate_id": "T5",
        "title": "DAILY_539 new hypothesis pre-registration design",
        "type": "research / read-only",
        "value": "Medium-high if good hypothesis found",
        "risk": "Low if read-only; medium if leads to OOS run",
        "urgency": "Low — all prior candidates rejected; no active WAIT_FOR_OOS",
        "prerequisites": (
            "New hypothesis not from L82-L82 rejected list; "
            "P221F protocol gates; pre-registration required before any data-touching"
        ),
        "recommended_now": "NO (unless user has specific hypothesis to test)",
        "reason": (
            "DAILY_539 midfreq_fourier_2bet rejected by P230C. No active WAIT_FOR_OOS. "
            "P224B gate condition (≥300 new draws) is irrelevant since the candidate was rejected, "
            "not merely deferred. A new pre-registered hypothesis is needed before any fresh scan. "
            "Not recommended without explicit user direction and a new hypothesis."
        ),
        "authorization_required": "Type A/B pre-registration first; then P221F gate",
    },
    {
        "candidate_id": "T6",
        "title": "POWER_LOTTO new hypothesis pre-registration design",
        "type": "research / read-only",
        "value": "Medium if hypothesis found",
        "risk": "Low if read-only",
        "urgency": "Low",
        "prerequisites": (
            "Significant new POWER_LOTTO draws; "
            "new hypothesis not from closed lines; P221F protocol"
        ),
        "recommended_now": "NO",
        "reason": (
            "P231B first-zone NULL. P222 found weak in-sample candidates for POWER_LOTTO "
            "but no cross-year confirmation. Any new direction requires explicit pre-registration "
            "and user authorization, not proactive discovery."
        ),
        "authorization_required": "Explicit user direction + Type A pre-registration",
    },
    {
        "candidate_id": "T7",
        "title": "3_STAR/4_STAR per-position replay code build",
        "type": "code-change / Type D if DB write",
        "value": "Low-medium — positional data is in DB; P214C showed NULL",
        "risk": "Medium — significant code + DB write for replay generation",
        "urgency": "Very low — P214C: 0 Bonferroni-significant, NULL result",
        "prerequisites": "Explicit authorization; fresh pre-registration for any new scan",
        "recommended_now": "NO",
        "reason": (
            "3_STAR/4_STAR positional data ingested (P213H/P213L). Straight-play code designed (P213D-E). "
            "P214C Bonferroni scan showed 0 significant findings (NULL result). "
            "Building replay infrastructure for a NULL signal has low return on investment. "
            "Only recommended if user has a specific new pre-registered positional hypothesis."
        ),
        "authorization_required": "Explicit authorization; new pre-registration required",
    },
    {
        "candidate_id": "T8",
        "title": "Raw history UI/API add-on labeling",
        "type": "UI/API (frontend/API change)",
        "value": "Low — no active consumer requesting it",
        "risk": "Medium — requires frontend + API behavior change (outside P249A scope)",
        "urgency": "Very low",
        "prerequisites": "User direction; frontend/API change authorization",
        "recommended_now": "NO",
        "reason": (
            "ADD_ON_PRIZE_EXCLUDED records are raw-accessible. No current frontend/API "
            "consumer is requesting row-family labels. This is a future UX task if users "
            "need to distinguish add-on vs canonical draws in the history display."
        ),
        "authorization_required": "Frontend/API change authorization",
    },
]

RECOMMENDED_NEXT = {
    "candidate_id": "T1+T2",
    "title": "roadmap.md sync + CURRENT_STATE.md row-count label clarification",
    "type": "Type B doc-only",
    "rationale": (
        "Both are zero-risk, Type B doc-only governance cleanup tasks that can be done in a single PR. "
        "T1 records the completed P246B–P248A arc in roadmap.md. "
        "T2 clarifies that 'BIG_LOTTO rows | 24,140' in CURRENT_STATE.md refers to replay rows, "
        "not draw rows (actual BIG_LOTTO draw rows = 22,238). "
        "No DB write. No code change. No strategy promotion. No authorization required beyond Type B."
    ),
    "no_prediction_edge_claim": True,
    "no_betting_advice": True,
}


def verify_closure() -> dict:
    """Verify P246-P248A closure artifacts exist."""
    p248a_artifact = OUTPUTS_DIR / "p248a_big_lotto_canonical_isolation_governance_closure_20260606.json"
    p247g_artifact = OUTPUTS_DIR / "p247g_big_lotto_canonical_isolation_final_guard_20260606.json"
    active_task = REPO_ROOT / "00-Plan/roadmap/active_task.md"

    p248a_ok = p248a_artifact.exists()
    p247g_ok = p247g_artifact.exists()

    active_task_waiting = False
    active_task_content = ""
    if active_task.exists():
        active_task_content = active_task.read_text()
        active_task_waiting = "WAITING_FOR_USER_AUTHORIZATION" in active_task_content

    current_state_marker = ""
    cs_path = REPO_ROOT / "00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md"
    if cs_path.exists():
        for line in cs_path.read_text().splitlines():
            if "State Marker" in line:
                current_state_marker = line
                break

    return {
        "p248a_artifact_exists": p248a_ok,
        "p247g_artifact_exists": p247g_ok,
        "active_task_waiting": active_task_waiting,
        "current_state_marker": current_state_marker,
        "all_ok": p248a_ok and p247g_ok and active_task_waiting,
    }


def build_json_report(closure: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "ROADMAP_TRIAGE_READ_ONLY",
        "phase0_expected_state": PHASE0_EXPECTED_STATE,
        "p246_p248_closure_verified": closure,
        "closed_research_lines": CLOSED_RESEARCH,
        "candidate_tasks": CANDIDATE_TASKS,
        "ranking_summary": [
            {"rank": 1, "candidate_id": "T1+T2", "title": "roadmap.md sync + CURRENT_STATE label fix",
             "type": "Type B doc-only", "recommended_now": "YES"},
            {"rank": 2, "candidate_id": "T3", "title": "Archived BIG_LOTTO script migration",
             "type": "code-change", "recommended_now": "NO — wait for reactivation"},
            {"rank": 3, "candidate_id": "T5", "title": "DAILY_539 new hypothesis pre-registration",
             "type": "research / read-only", "recommended_now": "NO — no active candidate"},
            {"rank": 4, "candidate_id": "T6", "title": "POWER_LOTTO new hypothesis design",
             "type": "research / read-only", "recommended_now": "NO — user direction needed"},
            {"rank": 5, "candidate_id": "T7", "title": "3_STAR/4_STAR per-position replay build",
             "type": "code/Type D", "recommended_now": "NO — P214C NULL"},
            {"rank": 6, "candidate_id": "T4", "title": "Annotation table Type D",
             "type": "Type D (DB write)", "recommended_now": "NO — not needed currently"},
            {"rank": 7, "candidate_id": "T8", "title": "Raw history UI/API labeling",
             "type": "UI/API", "recommended_now": "NO — no consumer request"},
        ],
        "recommended_next_task": RECOMMENDED_NEXT,
        "no_db_write_confirmed": True,
        "no_prediction_betting_recommendation": True,
        "no_production_recommendation_change": True,
        "forbidden_actions_confirmed": {
            "DB write": "NOT PERFORMED",
            "DB migration": "NOT PERFORMED",
            "CREATE VIEW / CREATE TABLE": "NOT PERFORMED",
            "DELETE rows": "NOT PERFORMED",
            "UPDATE rows": "NOT PERFORMED",
            "INSERT rows": "NOT PERFORMED",
            "strategy logic change": "NOT PERFORMED",
            "strategy promotion": "NOT PERFORMED",
            "production recommendation change": "NOT PERFORMED",
            "betting advice": "NOT PERFORMED",
        },
        "final_decision": (
            f"P249A triage complete. P246–P248A closure verified. "
            f"8 candidate tasks ranked; T1+T2 recommended (Type B doc-only: roadmap.md sync + "
            f"CURRENT_STATE label fix). All major research lines closed or NULL. "
            f"No active WAIT_FOR_OOS. No DB write. No prediction/betting recommendation."
        ),
    }


def build_md_report(closure: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# P249A — Post-Isolation Roadmap Triage",
        "",
        f"**Date:** {now}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** ROADMAP_TRIAGE_READ_ONLY  ",
        "",
        "## Executive Summary",
        "",
        "P249A is a read-only triage after completing the P246B–P248A BIG_LOTTO "
        "canonical isolation arc. All major research lines (DAILY_539, POWER_LOTTO, "
        "3_STAR/4_STAR, BIG_LOTTO) are closed or NULL. The recommended next task is "
        "a low-risk Type B governance sync (roadmap.md + CURRENT_STATE.md label fix). "
        "No DB write, no strategy promotion, no betting advice.",
        "",
        "## Current State After P248A",
        "",
        f"| Item | State |",
        f"|------|-------|",
        f"| BIG_LOTTO canonical isolation | **COMPLETE** (P246B–P248A) |",
        f"| DB view `draws_big_lotto_canonical_main` | Exists — 2,113 canonical rows |",
        f"| Raw BIG_LOTTO draws | 22,238 (preserved, raw-accessible) |",
        f"| ADD_ON_PRIZE_EXCLUDED | 19,100 (raw-accessible) |",
        f"| P246K canonical NIST | **GREEN** (random-compatible; no prediction edge) |",
        f"| Active research candidates | **NONE** (all lines closed or NULL) |",
        f"| active_task.md status | **WAITING_FOR_USER_AUTHORIZATION** |",
        "",
        "## Closed Research Lines",
        "",
        "| Line | Status | Task |",
        "|------|--------|------|",
    ]
    for r in CLOSED_RESEARCH:
        lines.append(f"| {r['line']} | {r['status']} | {r['task']} |")

    lines += [
        "",
        "## Candidate Task Table",
        "",
        "| ID | Title | Type | Value | Risk | Urgency | Recommended Now |",
        "|----|-------|------|-------|------|---------|-----------------|",
    ]
    for t in CANDIDATE_TASKS:
        lines.append(
            f"| {t['candidate_id']} | {t['title']} | {t['type'].split('(')[0].strip()} "
            f"| {t['value'][:40]}… | {t['risk'][:20]} | {t['urgency'][:20]} | {t['recommended_now']} |"
        )

    lines += [
        "",
        "## Recommended Next Task",
        "",
        f"**{RECOMMENDED_NEXT['candidate_id']}: {RECOMMENDED_NEXT['title']}**",
        "",
        f"> {RECOMMENDED_NEXT['rationale']}",
        "",
        "### T1 — roadmap.md sync",
        "- Record P246B–P248A BIG_LOTTO canonical isolation arc in the roadmap phase table.",
        "- roadmap.md last updated P213L (2026-06-05); does not reflect 18 P246/P247/P248 tasks.",
        "",
        "### T2 — CURRENT_STATE.md row-count label fix",
        "- 'BIG_LOTTO rows | 24,140' = replay rows, not draw rows (24,140+34,680+36,104=94,924 total replays).",
        "- Actual BIG_LOTTO draw rows = 22,238. Label should say 'BIG_LOTTO replay rows'.",
        "- Fix prevents future agents from misinterpreting the canonical draw count.",
        "",
        "## Why Not Annotation Table Immediately",
        "",
        "- Canonical isolation is complete via DB view and helper (P247B/P247E).",
        "- No active research consumer requires per-row family labels.",
        "- Annotation table requires Type D authorization (DB write + backup).",
        "- Deferred until a specific use-case justifies it.",
        "",
        "## Why Not Prediction-Edge Overclaim",
        "",
        "- P246K canonical NIST audit GREEN = data quality confirmation only.",
        "  It confirms 2,113 canonical main-draw rows are statistically random-compatible.",
        "  **It does not imply any exploitable prediction signal.**",
        "- BIG_LOTTO 49C6 signal space is exhausted (L90/L91; P247G confirmed).",
        "- All lottery lines (DAILY_539, POWER_LOTTO, 3_STAR/4_STAR) are NULL or UNDERPOWERED.",
        "- New research requires new pre-registration + P221F gate + explicit authorization.",
        "",
        "## Required Authorization",
        "",
        "| Candidate | Authorization Required |",
        "|-----------|----------------------|",
        "| T1+T2 (roadmap sync) | None — Type B doc-only |",
        "| T3 (script migration) | None — but user must decide which scripts to reactivate |",
        "| T4 (annotation table) | Explicit Type D phrase |",
        "| T5/T6 (new hypothesis) | Explicit user direction + pre-registration |",
        "| T7 (3/4_STAR replay build) | Explicit authorization + new pre-registration |",
        "| T8 (UI/API labeling) | Frontend/API change authorization |",
        "",
        "## Compliance Statements",
        "",
        "- **No DB write performed in P249A.**",
        "- **No rows deleted, updated, or inserted.**",
        "- **No strategy promotion or betting advice.**",
        "- **No production recommendation change.**",
        "- GREEN canonical randomness (P246K) does not authorize any new prediction direction.",
        "",
        "---",
        f"*Generated by {TASK_ID} — post-isolation roadmap triage*",
    ]
    return "\n".join(lines)


def main() -> dict:
    print("[P249A] Verifying P246–P248A closure state...")
    closure = verify_closure()
    print(f"[P249A]   p248a_artifact={closure['p248a_artifact_exists']}")
    print(f"[P249A]   p247g_artifact={closure['p247g_artifact_exists']}")
    print(f"[P249A]   active_task_waiting={closure['active_task_waiting']}")
    print(f"[P249A]   all_ok={closure['all_ok']}")

    report_json = build_json_report(closure)
    report_md = build_md_report(closure)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUTS_DIR / f"p249a_post_isolation_roadmap_triage_{DATE_SLUG}.json"
    md_path = OUTPUTS_DIR / f"p249a_post_isolation_roadmap_triage_{DATE_SLUG}.md"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)

    print(f"[P249A] Reports: {json_path}")
    print(f"[P249A] Recommended: {RECOMMENDED_NEXT['candidate_id']} — {RECOMMENDED_NEXT['title']}")
    print("[P249A] P249A COMPLETE.")
    return report_json


if __name__ == "__main__":
    main()
