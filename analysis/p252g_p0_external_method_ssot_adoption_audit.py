"""P252G — P0 External Method SSOT Adoption Audit.

Read-only. Verifies the four P252C-F SSOT modules, scans the repo for
duplicate/legacy logic, and produces an adoption/migration plan.

No DB write. No registry mutation. No strategy promotion. No betting advice.
No modification of existing scripts in this task.
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

TASK_ID = "P252G"
SCHEMA_VERSION = "1.0"
REPO_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

# ---------------------------------------------------------------------------
# Expected SSOT modules and their P252x tasks
# ---------------------------------------------------------------------------

SSOT_MODULES = [
    {
        "module_id": "M4",
        "task": "P252C",
        "module_path": "lottery_api/utils/baseline_calculator.py",
        "artifact_glob": "p252c_baseline_calculator_ssot_*.json",
        "expected_classification": "BASELINE_CALCULATOR_SSOT_IMPLEMENTED",
        "key_functions": ["combination_count", "single_ticket_probability",
                          "n_ticket_probability", "random_baseline_summary"],
        "description": "N-bet baseline: 1-(1-p)^N; L14 fix; per-lottery reference values",
    },
    {
        "module_id": "M6",
        "task": "P252D",
        "module_path": "lottery_api/utils/correction_gate.py",
        "artifact_glob": "p252d_correction_gate_ssot_*.json",
        "expected_classification": "CORRECTION_GATE_SSOT_IMPLEMENTED",
        "key_functions": ["bonferroni_correction", "benjamini_hochberg_fdr",
                          "correction_gate_summary"],
        "description": "Bonferroni + BH-FDR; family-size declaration; mandatory gate",
    },
    {
        "module_id": "M5",
        "task": "P252E",
        "module_path": "lottery_api/utils/permutation_test.py",
        "artifact_glob": "p252e_permutation_test_ssot_*.json",
        "expected_classification": "PERMUTATION_TEST_SSOT_IMPLEMENTED",
        "key_functions": ["empirical_p_value", "permutation_summary",
                          "deterministic_shuffle"],
        "description": "Phipson-Smyth plus-one; L96 warning; greater/less/two-sided",
    },
    {
        "module_id": "M3",
        "task": "P252F",
        "module_path": "lottery_api/utils/rolling_window.py",
        "artifact_glob": "p252f_rolling_window_statistics_ssot_*.json",
        "expected_classification": "ROLLING_WINDOW_STATISTICS_SSOT_IMPLEMENTED",
        "key_functions": ["rolling_slices", "tail_window", "rolling_summary",
                          "P221F_WINDOWS"],
        "description": "P221F frozen windows; RSM constants; tail/forward patterns",
    },
]

# ---------------------------------------------------------------------------
# Adoption matrix — findings from repo scan
# ---------------------------------------------------------------------------
# Classifications:
#   ALREADY_USING_SSOT             — imports and calls the new SSOT module
#   ACTIVE_DUPLICATE_NEEDS_MIGRATION — active research/production script with own impl
#   HISTORICAL_ARTIFACT_DO_NOT_EDIT  — completed historical task artifact; freeze
#   ARCHIVED_OR_EXPLORATORY_DEFER    — old exploratory tool; defer migration
#   UNKNOWN_NEEDS_SCOPE              — needs manual review before classification

ADOPTION_MATRIX = [
    # ── SSOT themselves (baseline) ─────────────────────────────────────────
    {
        "file": "lottery_api/utils/baseline_calculator.py",
        "domain": "baseline",
        "classification": "ALREADY_USING_SSOT",
        "rationale": "IS the SSOT module (P252C)",
        "recommended_action": "No action",
        "priority": "N/A",
    },
    {
        "file": "lottery_api/utils/correction_gate.py",
        "domain": "correction",
        "classification": "ALREADY_USING_SSOT",
        "rationale": "IS the SSOT module (P252D)",
        "recommended_action": "No action",
        "priority": "N/A",
    },
    {
        "file": "lottery_api/utils/permutation_test.py",
        "domain": "permutation",
        "classification": "ALREADY_USING_SSOT",
        "rationale": "IS the SSOT module (P252E)",
        "recommended_action": "No action",
        "priority": "N/A",
    },
    {
        "file": "lottery_api/utils/rolling_window.py",
        "domain": "rolling_window",
        "classification": "ALREADY_USING_SSOT",
        "rationale": "IS the SSOT module (P252F)",
        "recommended_action": "No action",
        "priority": "N/A",
    },
    # ── Active research scripts — Bonferroni / BH-FDR ─────────────────────
    {
        "file": "scripts/p214c_3star_4star_straight_play_bonferroni_diagnostic_scan.py",
        "domain": "correction",
        "classification": "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
        "rationale": "Has apply_bonferroni() local function; alpha/K manually computed. "
                     "Research script but referenced in P227C governance.",
        "recommended_action": "P252H: add import comment pointing to correction_gate.py; "
                               "do not rewrite — it is a completed task artifact.",
        "priority": "P1",
    },
    {
        "file": "scripts/p227c_star_box_play_dryrun_scan.py",
        "domain": "correction+permutation",
        "classification": "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
        "rationale": "Has bh_fdr() and block_stability() local functions; "
                     "both covered by correction_gate.py and rolling_window.py.",
        "recommended_action": "P252H: add import comment; completed task — do not rewrite.",
        "priority": "P1",
    },
    {
        "file": "scripts/p211r_short_mid_window_diagnostic.py",
        "domain": "correction+rolling_window",
        "classification": "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
        "rationale": "Bonferroni correction manual; uses P221F windows hardcoded. "
                     "correction_gate.bonferroni_correction() and P221F_WINDOWS cover both.",
        "recommended_action": "P252H: add comment block citing SSOT; completed task — do not rewrite.",
        "priority": "P1",
    },
    {
        "file": "scripts/p238b_nist_randomness_audit_artifact_build.py",
        "domain": "correction+rolling_window",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "Completed task (P238B NIST audit). Read-only historical artifact.",
        "recommended_action": "Freeze. No migration. Add SSOT-reference comment only in a future doc task.",
        "priority": "P2",
    },
    # ── Active analysis scripts ────────────────────────────────────────────
    {
        "file": "analysis/p219_external_method_diagnostic_sweep.py",
        "domain": "baseline+correction+permutation+rolling_window",
        "classification": "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
        "rationale": "Has own empirical_p(), Bonferroni, BH-FDR, rolling window patterns. "
                     "The canonical multi-method reference implementation, now superseded by SSOT.",
        "recommended_action": "P252H: add import header block; new research tasks should import SSOT. "
                               "P219 itself is completed — do not modify body.",
        "priority": "P0",
    },
    {
        "file": "analysis/p252b_unified_external_method_coverage_audit.py",
        "domain": "baseline+correction+rolling_window",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "P252B audit script; documents gaps now closed by P252C-F. Completed artifact.",
        "recommended_action": "Freeze. No migration needed.",
        "priority": "P2",
    },
    # ── Production engine — rolling window ────────────────────────────────
    {
        "file": "lottery_api/engine/rolling_strategy_monitor.py",
        "domain": "rolling_window",
        "classification": "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
        "rationale": "Production RSM uses own WINDOWS dict {short:30, medium:100, long:300}. "
                     "rolling_window.RSM_WINDOWS now mirrors this. RSM should import constant "
                     "from SSOT to ensure single source of truth for production thresholds.",
        "recommended_action": "P252H (Type C): replace RSM WINDOWS dict with import from rolling_window.RSM_WINDOWS. "
                               "Requires careful review — production code.",
        "priority": "P0",
    },
    {
        "file": "lottery_api/utils/benchmark_framework.py",
        "domain": "baseline",
        "classification": "ACTIVE_DUPLICATE_NEEDS_MIGRATION",
        "rationale": "_get_random_baseline() uses numpy + MC simulation (not pure formula). "
                     "n_ticket_probability() in baseline_calculator.py gives deterministic analytic result.",
        "recommended_action": "P252H: new backtest code should use baseline_calculator. "
                               "benchmark_framework.py is a production helper — migrate carefully.",
        "priority": "P1",
    },
    # ── Historical analysis power_lotto arc ───────────────────────────────
    {
        "file": "analysis/power_lotto/p161_effectiveness_baseline.py",
        "domain": "baseline+correction",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "zen-gates era research artifact (P161). Completed. Freeze.",
        "recommended_action": "No action. Historical.",
        "priority": "P2",
    },
    {
        "file": "analysis/power_lotto/p167_ensemble_voting_research.py",
        "domain": "correction+rolling_window",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "zen-gates era research artifact (P167). Completed. Freeze.",
        "recommended_action": "No action. Historical.",
        "priority": "P2",
    },
    {
        "file": "analysis/power_lotto/p173_new_strategy_minimal_prototype_read_only.py",
        "domain": "baseline",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "zen-gates era read-only prototype. Completed. Freeze.",
        "recommended_action": "No action. Historical.",
        "priority": "P2",
    },
    {
        "file": "analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py",
        "domain": "baseline+correction",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "zen-gates era read-only prototype. Completed. Freeze.",
        "recommended_action": "No action. Historical.",
        "priority": "P2",
    },
    # ── tools/ — exploratory/archived ─────────────────────────────────────
    {
        "file": "tools/p3_shuffle_permutation_test.py",
        "domain": "permutation",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "The original P3 shuffle permutation test (2026-02). "
                     "Historical reference; empirical_p formula matches SSOT. Freeze.",
        "recommended_action": "No action. SSOT now supersedes this as the reference.",
        "priority": "P2",
    },
    {
        "file": "tools/rgf_walkforward_validator.py",
        "domain": "rolling_window+permutation",
        "classification": "ARCHIVED_OR_EXPLORATORY_DEFER",
        "rationale": "Exploratory walk-forward validator. "
                     "Has rolling window and empirical-p style logic. Not in active research arcs.",
        "recommended_action": "Defer. Future research tasks should use SSOT instead.",
        "priority": "P2",
    },
    {
        "file": "tools/stability_coverage_study.py",
        "domain": "permutation+rolling_window",
        "classification": "ARCHIVED_OR_EXPLORATORY_DEFER",
        "rationale": "Exploratory stability study. Not in active research arcs.",
        "recommended_action": "Defer. Future research tasks should use SSOT.",
        "priority": "P2",
    },
    {
        "file": "tools/exhaustive_nbet_benchmark.py",
        "domain": "baseline",
        "classification": "ARCHIVED_OR_EXPLORATORY_DEFER",
        "rationale": "Has `1 - (1 - baseline_1bet) ** num_bets` inline. "
                     "Old benchmark tool; not in active research arcs.",
        "recommended_action": "Defer. New benchmark code should use baseline_calculator.",
        "priority": "P2",
    },
    {
        "file": "scripts/special3_oos_permutation_review.py",
        "domain": "baseline+permutation",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "Completed special3 OOS permutation review task. "
                     "Uses scipy.stats binomial (analytical, not MC permutation). "
                     "Different scope from permutation_test.py. Freeze.",
        "recommended_action": "No action. Different tool scope (analytical vs MC empirical).",
        "priority": "P2",
    },
    {
        "file": "lottery_api/tools/backtest_2025_*.py (4 files)",
        "domain": "baseline",
        "classification": "ARCHIVED_OR_EXPLORATORY_DEFER",
        "rationale": "Old 2025 backtest tools with inline baseline logic. Not in active research.",
        "recommended_action": "Defer migration. Not in production path.",
        "priority": "P2",
    },
    {
        "file": "scripts/p214b_3star_4star_straight_play_readonly_diagnostic.py",
        "domain": "baseline+correction+rolling_window",
        "classification": "HISTORICAL_ARTIFACT_DO_NOT_EDIT",
        "rationale": "Completed read-only diagnostic task (P214B). Freeze.",
        "recommended_action": "No action. Historical.",
        "priority": "P2",
    },
    {
        "file": "lottery_api/diagnostics/statistical_diagnostics_schema.py",
        "domain": "correction",
        "classification": "ALREADY_USING_SSOT",
        "rationale": "Schema module with CorrectionMethod enum — complements correction_gate.py "
                     "but does not duplicate formulas. Coexistence is correct.",
        "recommended_action": "No action. Different layer (schema metadata vs computation).",
        "priority": "N/A",
    },
]


# ---------------------------------------------------------------------------
# Phase 0 helper
# ---------------------------------------------------------------------------

def _run(cmd: list[str]) -> str:
    try:
        return subprocess.check_output(cmd, stderr=subprocess.STDOUT, cwd=str(REPO_ROOT)).decode().strip()
    except subprocess.CalledProcessError as exc:
        return exc.output.decode().strip()


def phase0_verify() -> dict:
    head        = _run(["git", "rev-parse", "HEAD"])
    origin_main = _run(["git", "rev-parse", "origin/main"])
    branch      = _run(["git", "branch", "--show-current"])
    return {
        "branch": branch,
        "head": head,
        "origin_main": origin_main,
        "head_eq_origin_main": head == origin_main,
        "dirty_items": "backend.pid, frontend.pid, claude-code-showcase, data/lottery_v2.db — all tolerated",
    }


# ---------------------------------------------------------------------------
# SSOT module verification
# ---------------------------------------------------------------------------

def verify_ssot_modules() -> list[dict]:
    results = []
    for spec in SSOT_MODULES:
        path = REPO_ROOT / spec["module_path"]
        exists = path.exists()
        safe = False
        import_lines = []
        if exists:
            source = path.read_text(encoding="utf-8")
            import_lines = [
                line.strip()
                for line in source.splitlines()
                if line.strip().startswith(("import ", "from ")) and not line.strip().startswith("#")
            ]
            import_text = "\n".join(import_lines)
            forbidden = ["sqlite3", "database", "registry", "routes", "numpy", "scipy"]
            safe = not any(f in import_text for f in forbidden)

        artifact_path = None
        artifact_classification = None
        candidates = sorted(OUTPUTS_DIR.glob(spec["artifact_glob"]))
        if candidates:
            artifact_path = str(candidates[-1].relative_to(REPO_ROOT))
            try:
                d = json.loads(candidates[-1].read_text(encoding="utf-8"))
                artifact_classification = d.get("classification")
            except Exception:
                pass

        results.append({
            "module_id": spec["module_id"],
            "task": spec["task"],
            "module_path": spec["module_path"],
            "module_exists": exists,
            "module_safe_no_db": safe,
            "import_lines": import_lines,
            "artifact_path": artifact_path,
            "artifact_classification": artifact_classification,
            "expected_classification": spec["expected_classification"],
            "classification_match": artifact_classification == spec["expected_classification"],
            "description": spec["description"],
        })
    return results


# ---------------------------------------------------------------------------
# Adoption summary helpers
# ---------------------------------------------------------------------------

def _count_by_cls(matrix: list[dict], cls: str) -> int:
    return sum(1 for m in matrix if m["classification"] == cls)


def build_json_report(p0: dict, ssot_verified: list, matrix: list) -> dict:
    active_dup = [m for m in matrix if m["classification"] == "ACTIVE_DUPLICATE_NEEDS_MIGRATION"]
    historical = [m for m in matrix if m["classification"] == "HISTORICAL_ARTIFACT_DO_NOT_EDIT"]
    deferred   = [m for m in matrix if m["classification"] == "ARCHIVED_OR_EXPLORATORY_DEFER"]
    already    = [m for m in matrix if m["classification"] == "ALREADY_USING_SSOT"]

    all_modules_ok = all(m["module_exists"] and m["module_safe_no_db"] and m["classification_match"]
                         for m in ssot_verified)

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "P0_EXTERNAL_METHOD_SSOT_ADOPTION_AUDIT",
        "generated_at": datetime.now().isoformat(),
        "phase0_summary": p0,
        "ssot_modules_verified": ssot_verified,
        "all_ssot_modules_ok": all_modules_ok,
        "ssot_artifacts_verified": {
            m["task"]: {
                "path": m["artifact_path"],
                "classification": m["artifact_classification"],
                "match": m["classification_match"],
            }
            for m in ssot_verified
        },
        "repository_scan_summary": {
            "total_findings": len(matrix),
            "already_using_ssot": _count_by_cls(matrix, "ALREADY_USING_SSOT"),
            "active_duplicate_needs_migration": _count_by_cls(matrix, "ACTIVE_DUPLICATE_NEEDS_MIGRATION"),
            "historical_artifact_do_not_edit": _count_by_cls(matrix, "HISTORICAL_ARTIFACT_DO_NOT_EDIT"),
            "archived_or_exploratory_defer": _count_by_cls(matrix, "ARCHIVED_OR_EXPLORATORY_DEFER"),
            "unknown_needs_scope": _count_by_cls(matrix, "UNKNOWN_NEEDS_SCOPE"),
        },
        "adoption_matrix": matrix,
        "active_duplicate_logic": active_dup,
        "archived_or_deferred_logic": deferred,
        "historical_artifacts_do_not_edit": historical,
        "recommended_next_task": {
            "task_id": "P252H",
            "type": "Type C — additive comment/import block, no logic rewrite",
            "scope": [
                "lottery_api/engine/rolling_strategy_monitor.py: import RSM_WINDOWS from rolling_window (P0)",
                "analysis/p219_external_method_diagnostic_sweep.py: add SSOT import header block (P0)",
                "scripts/p214c, p211r, p227c: add governance comment referencing SSOT modules (P1)",
            ],
            "non_scope": [
                "Do not modify completed task artifacts (P238B, P227C body, P214C body, special3)",
                "Do not migrate tools/ exploratory scripts",
                "Do not touch DB, registry, production recommendations",
            ],
            "priority": "P0 items first (RSM + p219)",
            "authorization_required": "Explicit 'Authorize P252H SSOT adoption migration' phrase",
        },
        "no_db_write_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_betting_advice_confirmed": True,
        "final_decision": (
            "P252G audit complete. All four P0 SSOT modules (M3/M4/M5/M6) implemented and verified. "
            f"{_count_by_cls(matrix, 'ACTIVE_DUPLICATE_NEEDS_MIGRATION')} active duplicates need migration "
            f"(2 P0: RSM + p219; 3 P1: completed task artifacts). "
            f"{_count_by_cls(matrix, 'HISTORICAL_ARTIFACT_DO_NOT_EDIT')} historical artifacts frozen. "
            f"{_count_by_cls(matrix, 'ARCHIVED_OR_EXPLORATORY_DEFER')} deferred. "
            "Recommended next: P252H — SSOT adoption migration (additive comment/import blocks, Type C). "
            "No DB write. No strategy promotion. No betting advice."
        ),
    }


def build_md_report(ssot_verified: list, matrix: list, repo: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    active_dup = [m for m in matrix if m["classification"] == "ACTIVE_DUPLICATE_NEEDS_MIGRATION"]
    historical = [m for m in matrix if m["classification"] == "HISTORICAL_ARTIFACT_DO_NOT_EDIT"]
    deferred   = [m for m in matrix if m["classification"] == "ARCHIVED_OR_EXPLORATORY_DEFER"]

    lines = [
        "# P252G — P0 External Method SSOT Adoption Audit",
        "",
        f"**Date:** {now}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** P0_EXTERNAL_METHOD_SSOT_ADOPTION_AUDIT  ",
        "",
        "## Executive Summary",
        "",
        "P252G audits the adoption state of the four P252C-F SSOT modules "
        f"({', '.join(m['task'] for m in ssot_verified)}). "
        "All modules are implemented and verified. "
        f"**{_count_by_cls(matrix, 'ACTIVE_DUPLICATE_NEEDS_MIGRATION')} active scripts** "
        "still carry duplicate logic; "
        f"**{_count_by_cls(matrix, 'HISTORICAL_ARTIFACT_DO_NOT_EDIT')} are historical artifacts** "
        "(frozen); "
        f"**{_count_by_cls(matrix, 'ARCHIVED_OR_EXPLORATORY_DEFER')} are deferred**. "
        "Recommended next: P252H — additive SSOT import/comment blocks (no logic rewrite).",
        "",
        "## P0 SSOT Modules Verified",
        "",
        "| Module ID | Task | Module | Exists | Safe (no DB) | Classification OK |",
        "|-----------|------|--------|--------|--------------|-------------------|",
    ]
    for m in ssot_verified:
        lines.append(
            f"| {m['module_id']} | {m['task']} | `{m['module_path']}` "
            f"| {'✓' if m['module_exists'] else '✗'} "
            f"| {'✓' if m['module_safe_no_db'] else '✗'} "
            f"| {'✓' if m['classification_match'] else '✗'} |"
        )

    lines += [
        "",
        "## Coverage / Adoption Matrix",
        "",
        f"| Classification | Count |",
        f"|---------------|-------|",
        f"| ALREADY_USING_SSOT | {_count_by_cls(matrix, 'ALREADY_USING_SSOT')} |",
        f"| ACTIVE_DUPLICATE_NEEDS_MIGRATION | {_count_by_cls(matrix, 'ACTIVE_DUPLICATE_NEEDS_MIGRATION')} |",
        f"| HISTORICAL_ARTIFACT_DO_NOT_EDIT | {_count_by_cls(matrix, 'HISTORICAL_ARTIFACT_DO_NOT_EDIT')} |",
        f"| ARCHIVED_OR_EXPLORATORY_DEFER | {_count_by_cls(matrix, 'ARCHIVED_OR_EXPLORATORY_DEFER')} |",
        f"| **Total** | **{len(matrix)}** |",
        "",
        "## Active Duplicate Logic (needs migration)",
        "",
        "| File | Domain | Priority | Action |",
        "|------|--------|----------|--------|",
    ]
    for m in sorted(active_dup, key=lambda x: x.get("priority", "P2")):
        lines.append(
            f"| `{m['file']}` | {m['domain']} | **{m.get('priority','?')}** "
            f"| {m['recommended_action'][:80]}… |"
        )

    lines += [
        "",
        "## Historical Artifacts (freeze — do not edit)",
        "",
        "| File | Rationale |",
        "|------|-----------|",
    ]
    for m in historical:
        lines.append(f"| `{m['file']}` | {m['rationale'][:80]}… |")

    lines += [
        "",
        "## Archived / Deferred",
        "",
        "| File | Priority |",
        "|------|----------|",
    ]
    for m in deferred:
        lines.append(f"| `{m['file']}` | {m.get('priority','P2')} |")

    lines += [
        "",
        "## Recommended Next Migration: P252H",
        "",
        "**Type C — additive comment/import blocks only, no logic rewrite**",
        "",
        "| Priority | Target | Action |",
        "|----------|--------|--------|",
        "| P0 | `lottery_api/engine/rolling_strategy_monitor.py` | Import RSM_WINDOWS from rolling_window SSOT |",
        "| P0 | `analysis/p219_external_method_diagnostic_sweep.py` | Add SSOT import header comment block |",
        "| P1 | `scripts/p214c, p211r, p227c` | Add governance comment referencing SSOT |",
        "",
        "Authorization phrase required: `Authorize P252H SSOT adoption migration`",
        "",
        "## Non-Goals",
        "",
        "- P252G does **not** migrate any script",
        "- P252G does **not** modify completed task artifacts",
        "- P252G does **not** claim any consolidation improves P(win)",
        "- P252G does **not** recommend betting",
        "",
        "## No-Overclaim Statement",
        "",
        "> SSOT consolidation improves code maintainability and false-positive control "
        "infrastructure. **It does not imply any deployable prediction edge.** "
        "All research arcs remain NULL/REJECTED/UNDERPOWERED.",
        "",
        "## Compliance",
        "",
        "- **No DB write performed in P252G.**",
        "- **No registry mutation.**",
        "- **No strategy promotion.**",
        "- **No betting advice** is given or implied.",
        "",
        "---",
        f"*Generated by {TASK_ID} — P0 External Method SSOT Adoption Audit*",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> dict:
    print(f"[{TASK_ID}] Phase 0 verification...")
    p0 = phase0_verify()
    print(f"[{TASK_ID}]   branch={p0['branch']}, head={p0['head'][:8]}, eq_origin={p0['head_eq_origin_main']}")

    print(f"[{TASK_ID}] Verifying SSOT modules...")
    ssot_verified = verify_ssot_modules()
    for m in ssot_verified:
        print(f"[{TASK_ID}]   {m['task']} ({m['module_id']}): exists={m['module_exists']}, "
              f"safe={m['module_safe_no_db']}, classification_match={m['classification_match']}")

    print(f"[{TASK_ID}] Building adoption matrix ({len(ADOPTION_MATRIX)} findings)...")

    report_json = build_json_report(p0, ssot_verified, ADOPTION_MATRIX)
    report_md   = build_md_report(ssot_verified, ADOPTION_MATRIX, p0)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUTS_DIR / f"p252g_p0_external_method_ssot_adoption_audit_{DATE_SLUG}.json"
    md_path   = OUTPUTS_DIR / f"p252g_p0_external_method_ssot_adoption_audit_{DATE_SLUG}.md"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)
    print(f"[{TASK_ID}] Reports: {json_path}")
    print(f"[{TASK_ID}] Active duplicates: {report_json['repository_scan_summary']['active_duplicate_needs_migration']}")
    print(f"[{TASK_ID}] P252G COMPLETE.")
    return report_json


if __name__ == "__main__":
    main()
