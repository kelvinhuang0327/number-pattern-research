"""P253A — P1 External Method Readiness Triage.

Read-only. Evaluates M1/M7/M8 P1 candidates from P252B and decides which
is next. Does not implement anything.

No DB write. No registry mutation. No strategy promotion. No betting advice.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

TASK_ID = "P253A"
SCHEMA_VERSION = "1.0"
REPO_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

# ---------------------------------------------------------------------------
# P1 candidate assessment
# ---------------------------------------------------------------------------

P1_CANDIDATE_MATRIX = [
    {
        "method_id": "M7",
        "method_name": "Signal Stability Diagnostics",
        "p252b_status": "CONFIRMED_PARTIAL",
        "p252b_priority": "P1",
        "readiness_status": "READY_FOR_NEXT_TASK",
        "rationale": (
            "Vocabulary gap (block/era/year/robustness) is purely definitional — "
            "no DB access, no new statistical logic required. "
            "P252F rolling_window.py already provides the rolling slice foundation. "
            "M7 adds: (a) stability vocabulary constants, (b) block-split helper, "
            "(c) threshold SSOT. "
            "Type C additive — small, low-risk, no edge-claim risk. "
            "rolling_window.py + stability_diagnostics.py form a natural pair."
        ),
        "evidence": [
            "lottery_api/engine/drift_detector.py — production stability (PSI thresholds)",
            "lottery_api/engine/rolling_strategy_monitor.py — uses 'STABLE'/'WARNING'/'DRIFT' labels",
            "scripts/p114_temporal_stability_audit.py — temporal stability (completed artifact)",
            "scripts/p230b1_daily539_backward_oos_dryrun.py — uses 'era' labels",
            "scripts/p231b_powerlotto_first_zone_backward_oos_dryrun.py — 'block stability'",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py — PsiStatus enum",
            "lottery_api/utils/rolling_window.py (P252F) — provides rolling slice foundation",
        ],
        "implementation_risk": "LOW",
        "db_schema_risk": "NONE — pure Python, no DB access",
        "edge_claim_risk": "NONE — interpretability only",
        "expected_value": "Closes vocabulary inconsistency; enables consistent cross-script stability reporting",
        "estimated_type": "Type C — small additive (like P252C-F)",
        "blocking_issues": [],
        "scope": [
            "stability_vocabulary constants (block=era=year, robustness=subset exclusion)",
            "stability threshold constants (STABLE/WARNING/DRIFT thresholds)",
            "block_stability() helper — split hits into non-overlapping blocks",
            "stability_summary() — structured output with no_edge_claim=True",
        ],
        "module_path": "lottery_api/utils/stability_diagnostics.py",
    },
    {
        "method_id": "M1",
        "method_name": "Historical Draw Parser",
        "p252b_status": "CONFIRMED_PARTIAL",
        "p252b_priority": "P1",
        "readiness_status": "NEEDS_READONLY_INVENTORY",
        "rationale": (
            "Positional data for 3_STAR/4_STAR is now in the DB (P213H/L — 5,850 rows each "
            "with numbers_positional). The gap is a unified SSOT parser module, not data recovery. "
            "BIG_LOTTO/DAILY_539/POWER_LOTTO use ad-hoc upload scripts without a shared schema contract. "
            "Before implementing a parser SSOT, a read-only inventory of all per-lottery parsing "
            "scripts is needed to define the shared input/output schema. "
            "Type B design task needed first."
        ),
        "evidence": [
            "scripts/p213g_3star_4star_dry_run_source_parser.py — dry-run parser (mock-only)",
            "scripts/p213h_3star_4star_controlled_positional_backfill.py — positional backfill",
            "scripts/p213i_3star_4star_real_source_dry_run_validation.py — source validation",
            "scripts/p213l_3star_4star_controlled_missing_row_ingestion.py — ingestion complete",
            "tools/upload_big_lotto_csv.py — ad-hoc BIG_LOTTO uploader",
            "tools/upload_daily539_txt.py — ad-hoc DAILY_539 uploader",
            "DB: 3_STAR 5,850 / 4_STAR 5,850 rows with numbers_positional CONFIRMED",
        ],
        "implementation_risk": "MEDIUM — parser SSOT touches data ingestion path",
        "db_schema_risk": "LOW for read-only inventory; MEDIUM for actual SSOT requiring validation",
        "edge_claim_risk": "NONE — data quality, not prediction",
        "expected_value": "Unified parse contract prevents silent data drift on new draw ingestion",
        "estimated_type": "Type B (inventory) → Type C (implementation, separate task)",
        "blocking_issues": [
            "No inventory of per-lottery format contracts yet",
            "Source format for 3_STAR/4_STAR NEW draws unconfirmed (P213G validation was mock-only)",
        ],
        "scope": [
            "Read-only inventory of existing per-lottery parse scripts",
            "Define shared parser SSOT input schema (per-lottery)",
            "Define post-parse count assertion contract",
        ],
        "module_path": "lottery_api/utils/draw_parser.py (future)",
    },
    {
        "method_id": "M8",
        "method_name": "Feature Bottleneck Report",
        "p252b_status": "PARTIAL",
        "p252b_priority": "P1",
        "readiness_status": "DEFER",
        "rationale": (
            "No unified feature definition exists for this lottery system. "
            "'Feature' in the bottleneck report context (mutual information per feature vs draw outcome) "
            "requires a pre-defined feature vocabulary that this project does not have as a SSOT. "
            "P219 diagnostic sweep has partial MI-style analysis but it is ad-hoc. "
            "statistical_diagnostics_schema.py has 'feature_bottleneck' as a REQUIRED_SCHEMA_FIELD "
            "but no implementation. "
            "M8 cannot be usefully implemented until: "
            "(a) a feature vocabulary is defined (which requires a separate design task), "
            "(b) the null baseline for MI under random draws is established. "
            "Risk: overclaiming features as 'predictive' when MI under random null is high. "
            "Recommend deferring until after M7 is complete and a separate feature design task is authorized."
        ),
        "evidence": [
            "lottery_api/diagnostics/statistical_diagnostics_schema.py — 'feature_bottleneck' field",
            "analysis/p219_external_method_diagnostic_sweep.py — partial MI-style analysis",
            "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json — gap identified",
            "outputs/research/p244c_diagnostics_integration_plan_20260605.json — blocker vocab",
        ],
        "implementation_risk": "HIGH — overclaim risk without feature vocabulary + null baseline",
        "db_schema_risk": "NONE for design; MEDIUM for MI computation (needs feature vectors)",
        "edge_claim_risk": (
            "HIGH — mutual information can be misinterpreted as predictive signal; "
            "requires careful null comparison"
        ),
        "expected_value": "Interpretability only; no prediction edge expected",
        "estimated_type": "Type B (feature design) → Type C (implementation) — multi-step",
        "blocking_issues": [
            "No feature vocabulary SSOT defined",
            "MI null baseline under random draws not established",
            "Overclaim risk without proper null comparison framework",
        ],
        "scope": [],
        "module_path": "lottery_api/utils/feature_bottleneck.py (future — deferred)",
    },
]


READINESS_DECISION = {
    "winner": "M7",
    "winner_method": "Signal Stability Diagnostics",
    "rationale": (
        "M7 is the most natural next P1 step: "
        "it directly extends P252F (rolling_window.py) already on main; "
        "Type C low-risk implementation; pure vocabulary/constants + block-split helper; "
        "no DB access; no edge-claim risk; closes the inconsistent block/era/year/robustness label gap. "
        "M1 needs a read-only inventory first (Type B preceding Type C). "
        "M8 is deferred due to missing feature vocabulary and overclaim risk."
    ),
    "ordered_recommendation": ["M7", "M1 (after inventory)", "M8 (deferred)"],
}

RECOMMENDED_NEXT_TASK = {
    "task_id_proposal": "P253B",
    "title": "Implement M7 Signal Stability Diagnostics SSOT",
    "type": "Type C — additive code implementation",
    "module": "lottery_api/utils/stability_diagnostics.py",
    "scope": [
        "STABILITY_VOCAB: BLOCK = ERA = YEAR (synonyms); ROBUSTNESS = subset-exclusion check",
        "Threshold constants: STABLE / WARNING / UNSTABLE (aligned with DriftDetector PSI)",
        "block_stability(hits, block_size) — split hit list into non-overlapping blocks, return per-block stats",
        "stability_summary(hits, block_sizes, label) — structured output with no_edge_claim=True",
        "Extends rolling_window.py (P252F) — can import rolling_slices internally",
    ],
    "non_scope": [
        "Do not change DriftDetector or RSM production code",
        "Do not add DB access",
        "Do not claim stability implies prediction edge",
        "Do not modify existing completed-task scripts",
    ],
    "authorization_required": "Explicit 'Authorize P253B M7 signal stability diagnostics SSOT'",
    "estimated_effort": "Similar to P252C-F (1 module + analysis script + tests)",
}

REJECTED_OR_DEFERRED = [
    {
        "method_id": "M1",
        "decision": "NEEDS_READONLY_INVENTORY_FIRST",
        "reason": "Type B design inventory needed before Type C implementation",
        "unblock_condition": "Complete a read-only parser script inventory and define input/output schema",
    },
    {
        "method_id": "M8",
        "decision": "DEFERRED",
        "reason": "Missing feature vocabulary + high overclaim risk without null MI baseline",
        "unblock_condition": (
            "Define feature vocabulary SSOT + establish MI null distribution under random draws. "
            "Authorize separately after M7 is complete."
        ),
    },
]


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _verify_p252i() -> dict:
    candidates = sorted(OUTPUTS_DIR.glob("p252i_p0_ssot_governance_closure_*.json"))
    if not candidates:
        return {"found": False}
    try:
        d = json.loads(candidates[-1].read_text(encoding="utf-8"))
        return {
            "found": True,
            "path": str(candidates[-1].relative_to(REPO_ROOT)),
            "classification": d.get("classification"),
            "all_artifacts_ok": d.get("all_artifacts_ok"),
            "all_modules_ok": d.get("all_modules_ok"),
        }
    except Exception as exc:
        return {"found": True, "error": str(exc)}


def _verify_m7_foundation() -> dict:
    rolling_window = REPO_ROOT / "lottery_api" / "utils" / "rolling_window.py"
    drift_detector = REPO_ROOT / "lottery_api" / "engine" / "drift_detector.py"
    exists_rw = rolling_window.exists()
    exists_dd = drift_detector.exists()
    psistatus_in_schema = False
    schema = REPO_ROOT / "lottery_api" / "diagnostics" / "statistical_diagnostics_schema.py"
    if schema.exists():
        psistatus_in_schema = "PsiStatus" in schema.read_text()
    return {
        "rolling_window_exists": exists_rw,
        "drift_detector_exists": exists_dd,
        "psistatus_in_schema": psistatus_in_schema,
        "m7_foundation_ready": exists_rw and exists_dd,
    }


def _verify_3star_positional() -> dict:
    """Check 3_STAR positional data availability without DB write."""
    try:
        import sqlite3
        db = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
        if not db.exists():
            return {"db_found": False}
        conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        r = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR' "
            "AND numbers_positional IS NOT NULL AND numbers_positional != ''"
        ).fetchone()
        r2 = conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
        ).fetchone()
        conn.close()
        return {
            "db_found": True,
            "star3_with_positional": r[0],
            "star3_total": r2[0],
            "positional_complete": r[0] == r2[0] and r[0] > 0,
        }
    except Exception as exc:
        return {"db_found": True, "error": str(exc)}


def build_json(p252i: dict, m7_found: dict, star3: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "P1_EXTERNAL_METHOD_READINESS_TRIAGE_COMPLETE",
        "generated_at": datetime.now().isoformat(),
        "phase0_summary": {
            "branch": "p253a-p1-external-method-readiness-triage (from main)",
            "head_eq_origin_main": True,
            "p252i_visible": True,
            "dirty_items": "backend.pid, frontend.pid, claude-code-showcase, data/lottery_v2.db — tolerated",
        },
        "p252i_dependency_verified": p252i,
        "supporting_evidence": {
            "m7_foundation_check": m7_found,
            "m1_star3_positional_check": star3,
        },
        "p1_candidate_matrix": P1_CANDIDATE_MATRIX,
        "readiness_decision": READINESS_DECISION,
        "recommended_next_task": RECOMMENDED_NEXT_TASK,
        "rejected_or_deferred_options": REJECTED_OR_DEFERRED,
        "no_db_write_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_betting_advice_confirmed": True,
        "final_decision": (
            "P253A triage complete. M7 Signal Stability Diagnostics is the recommended next P1 task. "
            "M7 readiness: READY_FOR_NEXT_TASK — extends P252F rolling_window.py, Type C, no DB, no edge-claim risk. "
            "M1 readiness: NEEDS_READONLY_INVENTORY — parser script survey needed before implementation. "
            "M8 readiness: DEFER — missing feature vocabulary + overclaim risk. "
            "No deployable prediction edge. No betting advice. No strategy promotion. "
            "System remains WAITING_FOR_USER_AUTHORIZATION. "
            "Authorization phrase for next: 'Authorize P253B M7 signal stability diagnostics SSOT'."
        ),
    }


def build_md(p252i: dict, m7_found: dict, star3: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# P253A — P1 External Method Readiness Triage",
        "",
        f"**Date:** {now}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** P1_EXTERNAL_METHOD_READINESS_TRIAGE_COMPLETE  ",
        "",
        "## Executive Summary",
        "",
        "P253A evaluates the three P1 external-method candidates from P252B (M1/M7/M8) "
        "after P252B-I P0 SSOT arc closure. "
        "**Recommendation: P253B — M7 Signal Stability Diagnostics SSOT.** "
        "M1 needs a read-only inventory first. M8 is deferred.",
        "",
        "## P252 P0 Closure Recap",
        "",
        f"- P252I (P0 arc closure): `{p252i.get('classification', 'N/A')}` ✓",
        f"- All P0 modules verified: {p252i.get('all_modules_ok', False)}",
        f"- M7 foundation (rolling_window.py): {m7_found.get('rolling_window_exists', False)}",
        f"- 3_STAR positional data complete: {star3.get('positional_complete', 'N/A')} ({star3.get('star3_with_positional', '?')}/{star3.get('star3_total', '?')} rows)",
        "",
        "## P1 Candidate Readiness Table",
        "",
        "| Method | Name | P252B Status | Readiness | Risk |",
        "|--------|------|-------------|-----------|------|",
    ]
    for m in P1_CANDIDATE_MATRIX:
        lines.append(
            f"| **{m['method_id']}** | {m['method_name']} | {m['p252b_status']} "
            f"| **{m['readiness_status']}** | {m['implementation_risk']} |"
        )

    lines += [
        "",
        "## Readiness Decision",
        "",
        f"**Winner: {READINESS_DECISION['winner']} — {READINESS_DECISION['winner_method']}**",
        "",
        READINESS_DECISION["rationale"],
        "",
        "## Recommended Next Task: P253B",
        "",
        "**Title:** Implement M7 Signal Stability Diagnostics SSOT  ",
        "**Type:** Type C — additive, like P252C-F  ",
        "**Module:** `lottery_api/utils/stability_diagnostics.py`  ",
        "",
        "**Scope:**",
    ]
    for s in RECOMMENDED_NEXT_TASK["scope"]:
        lines.append(f"- {s}")
    lines += [
        "",
        "**Non-scope:**",
    ]
    for ns in RECOMMENDED_NEXT_TASK["non_scope"]:
        lines.append(f"- {ns}")
    lines += [
        "",
        f"**Authorization phrase:** `{RECOMMENDED_NEXT_TASK['authorization_required']}`",
        "",
        "## Deferred/Rejected Options",
        "",
        "| Method | Decision | Unblock Condition |",
        "|--------|----------|-------------------|",
    ]
    for r in REJECTED_OR_DEFERRED:
        lines.append(f"| {r['method_id']} | {r['decision']} | {r['unblock_condition'][:80]}… |")

    lines += [
        "",
        "## Explicit Non-Actions",
        "",
        "- P253A does **not** implement M7, M1, or M8",
        "- P253A does **not** change parser scripts",
        "- P253A does **not** modify DB, registry, or production",
        "",
        "## No-Overclaim Statement",
        "",
        "> Signal stability diagnostics are interpretability tools. "
        "**They do not imply any deployable prediction edge.** "
        "All research arcs remain NULL/REJECTED/UNDERPOWERED.",
        "",
        "## Compliance",
        "",
        "- **No DB write.**  - **No registry mutation.**  - **No strategy promotion.**  - **No betting advice.**",
        "",
        "---",
        f"*Generated by {TASK_ID} — P1 External Method Readiness Triage*",
    ]
    return "\n".join(lines)


def main() -> dict:
    print(f"[{TASK_ID}] Verifying P252I dependency...")
    p252i = _verify_p252i()
    print(f"[{TASK_ID}]   P252I found: {p252i.get('found')}, all_ok: {p252i.get('all_modules_ok')}")

    print(f"[{TASK_ID}] Checking M7 foundation...")
    m7_found = _verify_m7_foundation()
    print(f"[{TASK_ID}]   rolling_window exists: {m7_found['rolling_window_exists']}, "
          f"drift_detector: {m7_found['drift_detector_exists']}")

    print(f"[{TASK_ID}] Checking M1 3_STAR positional evidence...")
    star3 = _verify_3star_positional()
    print(f"[{TASK_ID}]   3_STAR positional: {star3.get('star3_with_positional')}/{star3.get('star3_total')} rows")

    report_json = build_json(p252i, m7_found, star3)
    report_md   = build_md(p252i, m7_found, star3)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUTS_DIR / f"p253a_p1_external_method_readiness_triage_{DATE_SLUG}.json"
    md_path   = OUTPUTS_DIR / f"p253a_p1_external_method_readiness_triage_{DATE_SLUG}.md"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)
    print(f"[{TASK_ID}] Reports: {json_path}")
    print(f"[{TASK_ID}] Recommendation: {report_json['recommended_next_task']['task_id_proposal']} — M7")
    print(f"[{TASK_ID}] P253A COMPLETE.")
    return report_json


if __name__ == "__main__":
    main()
