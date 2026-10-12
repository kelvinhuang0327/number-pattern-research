"""P252B — Unified external method coverage audit.

Inventories the 8 scientific/external methods intended to support
valid prediction research. Produces a coverage matrix and consolidation plan.
No DB write. No strategy promotion. No betting advice.
"""

import json
from datetime import datetime
from pathlib import Path

TASK_ID = "P252B"
SCHEMA_VERSION = "1.0"
REPO_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

# ── 8-method coverage matrix ─────────────────────────────────────────────────
METHOD_COVERAGE_MATRIX = [
    {
        "method_id": "M1",
        "method_name": "Historical Draw Parser",
        "category": "data-quality-control",
        "current_status": "CONFIRMED_PARTIAL",
        "evidence_files": [
            "scripts/p213g_3star_4star_dry_run_source_parser.py",
            "scripts/p213h_3star_4star_controlled_positional_backfill.py",
            "scripts/p213i_3star_4star_real_source_dry_run_validation.py",
            "scripts/p213l_3star_4star_controlled_missing_row_ingestion.py",
            "tools/upload_big_lotto_csv.py",
            "tools/upload_daily539_txt.py",
            "lottery_api/verify_big_lotto_rules.py",
            "lottery_api/verify_daily539_rules.py",
        ],
        "representative_tasks": ["P213G", "P213H", "P213I", "P213L", "P246B"],
        "repo_locations": [
            "scripts/p213*_3star_4star_*.py",
            "tools/upload_*.py",
            "lottery_api/verify_*_rules.py",
        ],
        "gaps": [
            "No unified parser SSOT module — per-lottery ad-hoc scripts",
            "3_STAR/4_STAR positional recovery complete (P213H/L) but source format unconfirmed for new draws",
            "BIG_LOTTO and DAILY_539 upload scripts lack formal validation contract/schema",
            "No automated test that verifies draw count + integrity after parse",
        ],
        "risk_if_left_inconsistent": (
            "Silent data quality drift — new draws may be ingested with wrong format "
            "without detection. 3_STAR/4_STAR positional source unconfirmed for future draws."
        ),
        "recommended_consolidation_priority": "P1",
        "recommended_next_action": (
            "Define a parser SSOT module with: (a) input schema validation, "
            "(b) post-parse count assertion, (c) per-lottery format contract. "
            "No DB write required for design — Type B."
        ),
    },
    {
        "method_id": "M2",
        "method_name": "Number / Position Frequency",
        "category": "data-quality-control",
        "current_status": "CONFIRMED_PARTIAL",
        "evidence_files": [
            "lottery_api/engine/rolling_strategy_monitor.py",
            "lottery_api/engine/drift_detector.py",
            "analysis/p219_external_method_diagnostic_sweep.py",
            "tools/dynamic_frequency_predictor.py",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
        ],
        "representative_tasks": ["P219", "P221F", "P222", "P213H"],
        "repo_locations": [
            "lottery_api/engine/rolling_strategy_monitor.py",
            "lottery_api/engine/drift_detector.py",
        ],
        "gaps": [
            "Number frequency: exists in many scripts but no SSOT module",
            "Position frequency: BLOCKED by sorted DB storage (database.py:463 json.dumps(sorted(...)))",
            "No unified interface: tools compute frequency independently without shared helper",
            "Position frequency for 3_STAR/4_STAR straight-play diagnostics-only (P213B/P214C)",
        ],
        "risk_if_left_inconsistent": (
            "Different frequency windows/definitions used in different scripts. "
            "Position frequency blocked — straight-play research permanently limited."
        ),
        "recommended_consolidation_priority": "P2",
        "recommended_next_action": (
            "P2: Create shared frequency_calculator.py with number frequency only. "
            "Position frequency remains BLOCKED until DB schema change authorized. "
            "Design-only, no DB write."
        ),
    },
    {
        "method_id": "M3",
        "method_name": "Rolling Window Statistics",
        "category": "reporting-interpretability",
        "current_status": "CONFIRMED_PARTIAL",
        "evidence_files": [
            "lottery_api/engine/rolling_strategy_monitor.py",
            "lottery_api/engine/drift_detector.py",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
            "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json",
            "outputs/research/p244c_diagnostics_integration_plan_20260605.json",
        ],
        "representative_tasks": ["P221F", "P222", "P224", "P230", "P231", "RSM"],
        "repo_locations": [
            "lottery_api/engine/rolling_strategy_monitor.py (WINDOWS = {short:150, medium:500, long:1500})",
            "lottery_api/engine/drift_detector.py",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
        ],
        "gaps": [
            "RSM has SSOT for production rolling stats but schema not enforced in research scripts",
            "P244C integration plan exists but not implemented as mandatory gate",
            "Window definitions (150/500/1500) frozen in P221F but not centrally imported from SSOT",
            "Research scripts define own windows independently",
        ],
        "risk_if_left_inconsistent": (
            "Research scripts may use different window sizes than RSM production paths, "
            "creating inconsistent short/medium/long window semantics."
        ),
        "recommended_consolidation_priority": "P0",
        "recommended_next_action": (
            "Promote P221F window constants to a shared constants module. "
            "Enforce schema (P242/P244C) in research artifact output. Type B read-only design."
        ),
    },
    {
        "method_id": "M4",
        "method_name": "Null Simulation / Random Baseline",
        "category": "false-positive-control",
        "current_status": "CONFIRMED_PARTIAL",
        "evidence_files": [
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
            "lottery_api/utils/benchmark_framework.py",
            "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json",
            "tools/backtest_150_biglotto.py",
            "tools/backtest_500_biglotto.py",
            "tools/backtest_150_power.py",
            "tools/backtest_500_power.py",
            "tools/rigorous_benchmark_power.py",
        ],
        "representative_tasks": ["P221F", "P222", "P224", "P231"],
        "repo_locations": [
            "lottery_api/utils/benchmark_framework.py",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
            "tools/backtest_*_{biglotto,power}.py",
        ],
        "gaps": [
            "Baseline formula 1-(1-p)^N is in individual scripts — no shared baseline_calculator.py",
            "Historical bug (L14): wrong baseline caused Attention LSTM/Zonal Pruning overclaim; fix applied ad-hoc",
            "No mandatory pre-check gate that verifies baseline is correctly computed before any result is reported",
            "Monte Carlo null distribution (for permutation) is per-script, not centralized",
        ],
        "risk_if_left_inconsistent": (
            "CRITICAL: baseline bug (L14) has caused false positives before. "
            "Without a SSOT, new research scripts may repeat the error silently."
        ),
        "recommended_consolidation_priority": "P0",
        "recommended_next_action": (
            "Create baseline_calculator.py with: (a) correct N-bet baseline formula, "
            "(b) per-lottery baseline table, (c) test suite asserting formula. "
            "This is the highest-impact consolidation gap. Type B/C."
        ),
    },
    {
        "method_id": "M5",
        "method_name": "Permutation Test",
        "category": "false-positive-control",
        "current_status": "CONFIRMED_PARTIAL",
        "evidence_files": [
            "tools/p3_shuffle_permutation_test.py",
            "tools/stability_coverage_study.py",
            "tools/rgf_walkforward_validator.py",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
            "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json",
        ],
        "representative_tasks": ["P3", "P51", "P222", "P224", "P227C"],
        "repo_locations": [
            "tools/p3_shuffle_permutation_test.py",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
        ],
        "gaps": [
            "Known past bug (L96): shuffling hit labels preserves mean → p=1.0 always; fixed in P3 but not in all scripts",
            "Naming inconsistency: 'shuffle test', 'permutation test', 'P3' used interchangeably",
            "No shared permutation_test.py with correct null generation (Binomial(1, baseline_i) MC)",
            "Hypothesis must be pre-declared before permutation; not enforced as gate",
            "Old rejected artifacts (P51/Special3) have inconsistent permutation implementations",
        ],
        "risk_if_left_inconsistent": (
            "HIGH: The L96 bug (shuffle preserves mean → p=1.0) was a critical false-negative. "
            "Without SSOT, new scripts may reintroduce it."
        ),
        "recommended_consolidation_priority": "P0",
        "recommended_next_action": (
            "Create permutation_test.py SSOT with: (a) correct Binomial(1, baseline_i) MC null, "
            "(b) documented hypothesis slot, (c) test asserting p<0.5 on known-signal data. "
            "Type B/C — critical for research validity."
        ),
    },
    {
        "method_id": "M6",
        "method_name": "Multiple Testing Correction",
        "category": "false-positive-control",
        "current_status": "CONFIRMED_PARTIAL",
        "evidence_files": [
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
            "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json",
            "outputs/research/p244c_diagnostics_integration_plan_20260605.json",
            "outputs/research/p245b_bias_gate_layer_20260605.json",
            "analysis/power_lotto/p176_advanced_feature_minimal_prototype_read_only.py",
        ],
        "representative_tasks": ["P222", "P223B", "P227C", "P214C", "P244C", "P245B"],
        "repo_locations": [
            "lottery_api/diagnostics/statistical_diagnostics_schema.py (CorrectionMethod enum)",
            "outputs/research/p245b_bias_gate_layer_20260605.json (gate design)",
        ],
        "gaps": [
            "CorrectionMethod enum exists in schema but not enforced as mandatory gate in all research tasks",
            "Old scripts (pre-P222) don't use Bonferroni/BH-FDR consistently",
            "P245B bias gate design exists but not wired as a pre-commit hook or hard gate",
            "No shared correction_gate.py that raises on uncorrected p-values",
            "Family size declaration is not mandatory in research scripts",
        ],
        "risk_if_left_inconsistent": (
            "CRITICAL: Without correction gate, future research may report uncorrected p-values "
            "and promote false positives. This is the most important false-positive-control gap."
        ),
        "recommended_consolidation_priority": "P0",
        "recommended_next_action": (
            "Implement mandatory correction gate: (a) any research artifact claiming p<0.05 "
            "must declare family size and correction method; (b) P245B bias gate as "
            "mandatory schema field. Type B/C design + lightweight enforcement module."
        ),
    },
    {
        "method_id": "M7",
        "method_name": "Signal Stability Diagnostics",
        "category": "reporting-interpretability",
        "current_status": "CONFIRMED_PARTIAL",
        "evidence_files": [
            "lottery_api/engine/rolling_strategy_monitor.py",
            "lottery_api/engine/drift_detector.py",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
            "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json",
            "outputs/research/p243a_diagnostic_report_fixture_pack_20260605.json",
            "outputs/research/p245b_bias_gate_layer_20260605.json",
        ],
        "representative_tasks": ["P221F", "P224", "P230", "P231", "P243A", "P245B"],
        "repo_locations": [
            "lottery_api/engine/rolling_strategy_monitor.py (block_stability)",
            "lottery_api/engine/drift_detector.py (DriftReport)",
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
        ],
        "gaps": [
            "Label inconsistency: 'block', 'year', 'era', 'robustness' used in different scripts without SSOT definition",
            "DriftDetector is production-only; no general research stability diagnostic module",
            "P243A fixtures cover stability but as evidence-backed examples, not a module",
            "P245B bias gate includes stability checks in design but not in code enforcement",
            "Threshold for 'stable' vs 'unstable' not centrally defined",
        ],
        "risk_if_left_inconsistent": (
            "Research results may use inconsistent stability criteria — "
            "'block stability' in one script ≠ 'era robustness' in another."
        ),
        "recommended_consolidation_priority": "P1",
        "recommended_next_action": (
            "Define stability vocabulary in schema (block, era, year as synonyms; "
            "robustness = subset exclusion). "
            "Add stability_threshold constants to shared module. Type B."
        ),
    },
    {
        "method_id": "M8",
        "method_name": "Feature Bottleneck Report",
        "category": "reporting-interpretability",
        "current_status": "PARTIAL",
        "evidence_files": [
            "lottery_api/diagnostics/statistical_diagnostics_schema.py",
            "outputs/research/p241b_p234_statistical_diagnostics_inventory_20260605.json",
            "analysis/p219_external_method_diagnostic_sweep.py",
            "tests/test_p241b_p234_statistical_diagnostics_inventory.py",
        ],
        "representative_tasks": ["P241B", "P232A", "P233A", "P219"],
        "repo_locations": [
            "lottery_api/diagnostics/statistical_diagnostics_schema.py (feature_bottleneck field in REQUIRED_SCHEMA_FIELDS)",
            "analysis/p219_external_method_diagnostic_sweep.py (partial MI analysis)",
        ],
        "gaps": [
            "No dedicated feature_bottleneck_report.py SSOT module",
            "P241B inventory identified 'feature bottleneck' as one of 16 method gaps",
            "statistical_diagnostics_schema.py has 'feature_bottleneck' as a REQUIRED_SCHEMA_FIELD but no implementation",
            "P232A/P233A strategy inventory != feature bottleneck analysis (different concept)",
            "No canonical output format for feature-information-rate or mutual information report",
            "P219 MI analysis is exploratory, not structured as a shareable module",
        ],
        "risk_if_left_inconsistent": (
            "Feature selection is done implicitly/ad-hoc in research scripts. "
            "Without bottleneck report, it's impossible to audit whether features "
            "are genuinely predictive vs correlated by chance."
        ),
        "recommended_consolidation_priority": "P1",
        "recommended_next_action": (
            "Design feature_bottleneck_report.py that computes: "
            "(a) mutual information per feature vs draw outcome, "
            "(b) information rate under null, "
            "(c) bottleneck score. "
            "Type B design + Type C implementation. No DB write."
        ),
    },
]

EDGE_SEARCH_SUMMARY = {
    "question": "Did the 8 external methods find a deployable prediction edge?",
    "answer": "NO",
    "detail": (
        "All completed research arcs (P222 DAILY_539/POWER_LOTTO scan, P230C DAILY_539 REJECTED_BY_BACKWARD_OOS, "
        "P231B POWER_LOTTO first-zone NULL, P227C 3_STAR/4_STAR UNDERPOWERED_NO_SIGNAL, "
        "P214C 3_STAR/4_STAR straight-play NULL Bonferroni, P246K BIG_LOTTO canonical GREEN random-compatible) "
        "confirm no deployable edge. Methods M3–M7 were applied in these arcs and returned NULL. "
        "GREEN randomness (P246K) does not imply predictive edge. "
        "No strategy should be promoted. No betting advice is given or implied."
    ),
    "no_betting_advice": True,
    "no_strategy_promotion": True,
    "green_randomness_means_prediction_edge": False,
}

CONSOLIDATION_PLAN = {
    "P0_mandatory_gates": {
        "description": "Must be implemented before any new research arc is started",
        "items": [
            {
                "method_id": "M4",
                "name": "Null Simulation / Random Baseline — SSOT baseline_calculator.py",
                "why_P0": "Historical bug (L14) caused false positives. Correct N-bet baseline must be enforced.",
                "action": "Create baseline_calculator.py with correct 1-(1-p)^N formula + per-lottery table + tests",
                "type": "Type B/C",
            },
            {
                "method_id": "M5",
                "name": "Permutation Test — Fix L96 bug SSOT permutation_test.py",
                "why_P0": "L96 bug (shuffle preserves mean → p=1.0) caused critical false-negatives. Must be fixed centrally.",
                "action": "Create permutation_test.py with correct Binomial(1, baseline_i) MC null + hypothesis declaration",
                "type": "Type B/C",
            },
            {
                "method_id": "M6",
                "name": "Multiple Testing Correction — mandatory correction_gate.py",
                "why_P0": "Without correction gate, future research may report uncorrected p-values and promote false positives.",
                "action": "Implement correction_gate.py enforcing family_size + correction_method in research artifact output",
                "type": "Type B/C",
            },
            {
                "method_id": "M3",
                "name": "Rolling Window Statistics — promote P221F constants to shared module",
                "why_P0": "Window semantic consistency (short=150, medium=500, long=1500) must be enforced across all research scripts.",
                "action": "Create window_constants.py importing from P221F definition; enforce in RSM and research templates",
                "type": "Type B",
            },
        ],
    },
    "P1_inventory_and_parser": {
        "description": "Important engineering hygiene; not blocking immediate research but needed for long-term consistency",
        "items": [
            {
                "method_id": "M1",
                "name": "Historical Draw Parser — unified parser SSOT",
                "action": "Design parser SSOT with per-lottery schema, validation contract, post-parse assertions",
                "type": "Type B",
            },
            {
                "method_id": "M7",
                "name": "Signal Stability Diagnostics — vocabulary and threshold SSOT",
                "action": "Define block/era/year/robustness synonyms; add stability_threshold to shared constants",
                "type": "Type B",
            },
            {
                "method_id": "M8",
                "name": "Feature Bottleneck Report — design + Type C implementation",
                "action": "Design feature_bottleneck_report.py (MI per feature, null rate, bottleneck score)",
                "type": "Type B + Type C",
            },
        ],
    },
    "P2_blocked_or_diagnostics_only": {
        "description": "Work blocked by external constraints or confirmed diagnostics-only",
        "items": [
            {
                "method_id": "M2",
                "name": "Position Frequency — BLOCKED by sorted DB storage",
                "why_blocked": "database.py:463 sorts numbers at write time; positional order lost for all lotteries except 3_STAR/4_STAR after P213H/L",
                "action": "Design position_frequency_calculator.py for number frequency only; position frequency remains BLOCKED",
                "type": "P2",
            },
        ],
    },
    "non_goals": [
        "Do not claim any consolidation raises P(win)",
        "Do not start new prediction research arcs in this consolidation",
        "Do not modify production strategy registry",
        "Position frequency BLOCKED — do not attempt DB schema change without separate Type D authorization",
        "Feature bottleneck report is interpretability only — not a predictor",
    ],
}


def verify_artifacts() -> dict:
    """Check key supporting artifacts exist."""
    checks = {
        "p241b_diagnostics_inventory": (OUTPUTS_DIR / "p241b_p234_statistical_diagnostics_inventory_20260605.json").exists(),
        "p242_schema": (OUTPUTS_DIR / "p242_statistical_diagnostics_schema_implementation_20260605.json").exists(),
        "p244c_integration_plan": (OUTPUTS_DIR / "p244c_diagnostics_integration_plan_20260605.json").exists(),
        "p245b_bias_gate": (OUTPUTS_DIR / "p245b_bias_gate_layer_20260605.json").exists(),
        "p236a_methods_scouting": (OUTPUTS_DIR / "p236a_external_statistical_methods_scouting_20260604.json").exists(),
        "p219_diagnostic_sweep": (OUTPUTS_DIR / "p219_external_method_diagnostic_sweep_20260605.json").exists(),
        "statistical_diagnostics_schema": (REPO_ROOT / "lottery_api/diagnostics/statistical_diagnostics_schema.py").exists(),
        "rolling_strategy_monitor": (REPO_ROOT / "lottery_api/engine/rolling_strategy_monitor.py").exists(),
        "drift_detector": (REPO_ROOT / "lottery_api/engine/drift_detector.py").exists(),
        "p3_permutation_test": (REPO_ROOT / "tools/p3_shuffle_permutation_test.py").exists(),
    }
    return checks


def build_json_report(artifact_checks: dict) -> dict:
    p0 = [m["method_id"] for m in CONSOLIDATION_PLAN["P0_mandatory_gates"]["items"]]
    p1 = [m["method_id"] for m in CONSOLIDATION_PLAN["P1_inventory_and_parser"]["items"]]
    p2 = [m["method_id"] for m in CONSOLIDATION_PLAN["P2_blocked_or_diagnostics_only"]["items"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "UNIFIED_EXTERNAL_METHOD_COVERAGE_AUDIT",
        "phase0_summary": {
            "head_eq_origin_main": True,
            "p251e_merge_visible": True,
            "active_task_waiting": True,
            "dirty_items": "tolerated runtime only (backend.pid, frontend.pid, claude-code-showcase, data/lottery_v2.db metadata-only)",
        },
        "method_coverage_matrix": METHOD_COVERAGE_MATRIX,
        "method_count": len(METHOD_COVERAGE_MATRIX),
        "edge_search_summary": EDGE_SEARCH_SUMMARY,
        "core_layer_consolidation_plan": CONSOLIDATION_PLAN,
        "p0_priorities": p0,
        "p1_priorities": p1,
        "p2_priorities": p2,
        "artifact_checks": artifact_checks,
        "gaps_and_unknowns": [
            "M4 (baseline_calculator.py): MISSING SSOT — highest risk (L14 precedent)",
            "M5 (permutation_test.py): MISSING SSOT — critical bug L96 known",
            "M6 (correction_gate.py): DESIGN EXISTS (P245B) but NOT ENFORCED in code",
            "M8 (feature_bottleneck_report.py): FIELD in schema but NO implementation",
            "M2 (position_frequency): BLOCKED by sorted DB storage — not addressable without Type D",
            "M7 (stability labels): vocabulary inconsistency across scripts",
            "M1 (parser SSOT): per-lottery scripts without unified contract",
            "M3 (window constants): P221F frozen but not imported from single source",
        ],
        "no_db_write_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_betting_advice_confirmed": True,
        "final_decision": (
            f"P252B audit complete. External methods (M1-M8) coverage: CONFIRMED_PARTIAL for 7, PARTIAL for 1 (M8). "
            f"No deployable prediction edge found — all research arcs NULL/REJECTED/UNDERPOWERED. "
            f"GREEN randomness (P246K) does not imply prediction edge. "
            f"Consolidation plan: P0 (M3/M4/M5/M6) — SSOT baseline, permutation, correction gate, window constants. "
            f"P1 (M1/M7/M8) — parser SSOT, stability vocab, feature bottleneck report. "
            f"P2 (M2) — position frequency BLOCKED. "
            f"Recommended next: P252C — implement M4 baseline_calculator.py SSOT (Type C, highest risk gap)."
        ),
    }


def build_md_report(artifact_checks: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# P252B — Unified External Method Coverage Audit",
        "",
        f"**Date:** {now}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** UNIFIED_EXTERNAL_METHOD_COVERAGE_AUDIT  ",
        "",
        "## Executive Summary",
        "",
        "P252B audits the 8 scientific/external methods intended to support valid prediction research. "
        "The audit answers two distinct questions clearly:",
        "",
        "1. **Did external methods find a deployable prediction edge?** → **NO** — all completed research "
           "arcs (P222/P230C/P231B/P227C/P214C) returned NULL/REJECTED/UNDERPOWERED.",
        "2. **Are the 8 methods fully engineered as a unified core layer/SSOT?** → **NO** — 7 are "
           "CONFIRMED_PARTIAL and 1 (M8 feature bottleneck) is PARTIAL with no implementation.",
        "",
        "## Direct Answers",
        "",
        "> **External methods have NOT found a deployable prediction edge.** "
        "All research arcs are NULL, REJECTED, or UNDERPOWERED. "
        "GREEN canonical randomness (P246K) confirms random-compatibility of 2,113 BIG_LOTTO draws — "
        "**this does not imply any exploitable prediction signal.** "
        "No strategy promotion. No betting advice.",
        "",
        "> **The 8-method core coverage is NOT fully unified.** "
        "Critical gaps exist in null simulation SSOT (M4), permutation test SSOT (M5), "
        "and multiple testing correction enforcement (M6). These are P0 priorities.",
        "",
        "## 8-Method Coverage Table",
        "",
        "| ID | Method | Category | Status | Priority | Key Gap |",
        "|----|--------|----------|--------|----------|---------|",
    ]
    for m in METHOD_COVERAGE_MATRIX:
        lines.append(
            f"| {m['method_id']} | {m['method_name']} | {m['category'].replace('-', ' ')} "
            f"| {m['current_status']} | {m['recommended_consolidation_priority']} "
            f"| {m['gaps'][0][:50]}… |"
        )

    lines += [
        "",
        "## Evidence Links",
        "",
        "| Artifact | Task | Relevance |",
        "|----------|------|-----------|",
        "| `lottery_api/diagnostics/statistical_diagnostics_schema.py` | P242 | M3/M4/M5/M6/M7/M8 schema fields |",
        "| `lottery_api/engine/rolling_strategy_monitor.py` | RSM | M3 rolling window SSOT (partial) |",
        "| `lottery_api/engine/drift_detector.py` | P246G | M3/M7 signal stability (production) |",
        "| `tools/p3_shuffle_permutation_test.py` | P3 | M5 permutation test (per-lottery) |",
        "| `outputs/research/p245b_bias_gate_layer*.json` | P245B | M6 correction gate design |",
        "| `outputs/research/p241b_p234_statistical_diagnostics_inventory*.json` | P241B | All 8 methods inventoried |",
        "| `outputs/research/p244c_diagnostics_integration_plan*.json` | P244C | Integration checkpoints |",
        "| `scripts/p213g_3star_4star_dry_run_source_parser.py` | P213G | M1 parser (3_STAR/4_STAR) |",
        "",
        "## P0/P1/P2 Consolidation Plan",
        "",
        "### P0 — Mandatory Gates (implement before next research arc)",
        "",
        "These gaps have caused false positives (L14) or false negatives (L96) before.",
        "",
    ]
    for item in CONSOLIDATION_PLAN["P0_mandatory_gates"]["items"]:
        lines += [
            f"**{item['method_id']} — {item['name']}**  ",
            f"Why P0: {item['why_P0']}  ",
            f"Action: {item['action']}  ",
            f"Type: {item['type']}",
            "",
        ]

    lines += [
        "### P1 — Inventory and Parser (engineering hygiene)",
        "",
    ]
    for item in CONSOLIDATION_PLAN["P1_inventory_and_parser"]["items"]:
        lines += [
            f"**{item['method_id']} — {item['name']}**  ",
            f"Action: {item['action']} ({item['type']})",
            "",
        ]

    lines += [
        "### P2 — Blocked or Diagnostics-Only",
        "",
    ]
    for item in CONSOLIDATION_PLAN["P2_blocked_or_diagnostics_only"]["items"]:
        lines += [
            f"**{item['method_id']} — {item['name']}**  ",
            f"Blocked reason: {item['why_blocked']}  ",
            f"Action: {item['action']}",
            "",
        ]

    lines += [
        "### Non-Goals",
        "",
    ]
    for ng in CONSOLIDATION_PLAN["non_goals"]:
        lines.append(f"- {ng}")

    lines += [
        "",
        "## Risks",
        "",
        "| Method | Risk If Left Inconsistent |",
        "|--------|--------------------------|",
    ]
    for m in METHOD_COVERAGE_MATRIX:
        lines.append(f"| {m['method_id']} — {m['method_name']} | {m['risk_if_left_inconsistent'][:80]}… |")

    lines += [
        "",
        "## Recommended Next Task",
        "",
        "**P252C — Implement M4 baseline_calculator.py SSOT (Type C)**",
        "",
        "- Highest risk gap: L14 baseline bug caused two false positives (Attention LSTM, Zonal Pruning)",
        "- Correct formula: `baseline(n, p_single) = 1 - (1 - p_single) ** n`",
        "- Output: shared module `lottery_api/utils/baseline_calculator.py` with per-lottery table + tests",
        "- Type C small additive implementation — no DB write, no registry change, no strategy promotion",
        "",
        "## Compliance Statements",
        "",
        "- **No DB write performed in P252B.**",
        "- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.",
        "- **No betting advice** is given or implied in this audit.",
        "- GREEN canonical randomness (P246K) does not authorize any prediction direction.",
        "",
        "---",
        f"*Generated by {TASK_ID} — Unified external method coverage audit*",
    ]
    return "\n".join(lines)


def main() -> dict:
    print(f"[P252B] Auditing 8 external methods...")
    artifact_checks = verify_artifacts()
    for k, v in artifact_checks.items():
        print(f"[P252B]   {k}: {'OK' if v else 'MISSING'}")

    report_json = build_json_report(artifact_checks)
    report_md = build_md_report(artifact_checks)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUTS_DIR / f"p252b_unified_external_method_coverage_audit_{DATE_SLUG}.json"
    md_path = OUTPUTS_DIR / f"p252b_unified_external_method_coverage_audit_{DATE_SLUG}.md"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)

    print(f"[P252B] Reports: {json_path}")
    print(f"[P252B] Coverage: {len(METHOD_COVERAGE_MATRIX)} methods audited")
    print(f"[P252B] P0: {report_json['p0_priorities']}, P1: {report_json['p1_priorities']}, P2: {report_json['p2_priorities']}")
    print("[P252B] P252B COMPLETE.")
    return report_json


if __name__ == "__main__":
    main()
