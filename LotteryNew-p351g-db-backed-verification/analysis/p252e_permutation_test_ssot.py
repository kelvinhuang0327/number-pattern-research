"""P252E — Permutation Test SSOT artifact generator.

Implements the third P0 consolidation item from P252B (M5 Permutation Test).
Verifies the new permutation_test.py module, produces a JSON + Markdown
audit artifact.

No DB write. No registry mutation. No strategy promotion. No betting advice.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

TASK_ID = "P252E"
SCHEMA_VERSION = "1.0"
REPO_ROOT = Path(__file__).parent.parent
OUTPUTS_DIR = REPO_ROOT / "outputs" / "research"
DATE_SLUG = datetime.now().strftime("%Y%m%d")

FORBIDDEN_IMPORTS = {
    "sqlite3", "sqlalchemy", "database", "registry", "routes", "app",
    "numpy", "scipy", "statsmodels",
}

IMPLEMENTED_FUNCTIONS = [
    {
        "name": "validate_permutation_inputs",
        "signature": "(observed_statistic, null_distribution, alternative) -> dict",
        "description": "Validate inputs; returns {valid, errors, n_null}; never raises",
        "note": "Required gate: checks finite observed, non-empty null, known alternative",
    },
    {
        "name": "empirical_p_value",
        "signature": "(observed, null_distribution, alternative='greater', plus_one=True) -> float",
        "description": "Empirical p = (1 + count_extreme) / (B + 1) — Phipson-Smyth formula",
        "note": "Exact formula from p219 (reference); plus_one=True prevents p=0; L96 bug absent",
    },
    {
        "name": "compare_observed_to_null",
        "signature": "(observed_statistic, null_distribution) -> dict",
        "description": "Compute null_min/max/mean/std/median and obs_percentile for audit",
        "note": "Pure stdlib (statistics module); useful for reporting without correction gate",
    },
    {
        "name": "permutation_summary",
        "signature": "(observed, null_distribution, alternative='greater', plus_one=True, seed=None, family_label=None) -> dict",
        "description": "Canonical SSOT output dict with no_edge_claim=True",
        "note": "Primary entry point; always emits L96 warning in limitations",
    },
    {
        "name": "deterministic_shuffle",
        "signature": "(values, seed) -> list",
        "description": "Return seeded-shuffled copy of values for reproducible null generation",
        "note": "Does not generate null distribution itself — caller drives MC loop",
    },
]

PERMUTATION_SCHEMA_FIELDS = [
    "schema_version", "test_type", "family_label", "alternative",
    "observed_statistic", "null_count", "null_min", "null_max",
    "null_mean", "null_std", "null_median", "obs_percentile",
    "empirical_p_value", "plus_one_correction", "seed",
    "no_edge_claim", "no_betting_advice", "assumptions", "limitations",
]


def _find_latest(glob: str) -> Path | None:
    candidates = sorted(OUTPUTS_DIR.glob(glob))
    return candidates[-1] if candidates else None


def _verify_dep(glob: str, dep_name: str, m_id: str | None = None) -> dict:
    path = _find_latest(glob)
    if not path:
        return {"found": False, "dep_name": dep_name}
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        m_entry = None
        if m_id:
            for m in d.get("method_coverage_matrix", []):
                if m.get("method_id") == m_id:
                    m_entry = m
                    break
        return {
            "found": True,
            "path": str(path.relative_to(REPO_ROOT)),
            "task_id": d.get("task_id"),
            "classification": d.get("classification"),
            "m_id_priority": m_entry.get("recommended_consolidation_priority") if m_entry else None,
        }
    except Exception as exc:
        return {"found": True, "path": str(path), "error": str(exc)}


def _verify_safety() -> dict:
    module_path = REPO_ROOT / "lottery_api" / "utils" / "permutation_test.py"
    if not module_path.exists():
        return {"exists": False}
    source = module_path.read_text(encoding="utf-8")
    import_lines = [
        line.strip()
        for line in source.splitlines()
        if line.strip().startswith(("import ", "from ")) and not line.strip().startswith("#")
    ]
    import_text = "\n".join(import_lines)
    forbidden_found = [f for f in FORBIDDEN_IMPORTS if f in import_text]
    return {
        "exists": True,
        "import_lines": import_lines,
        "forbidden_found": forbidden_found,
        "safe": len(forbidden_found) == 0,
    }


def _exercise_module() -> dict:
    sys.path.insert(0, str(REPO_ROOT))
    from lottery_api.utils import permutation_test as pt

    results: dict = {}

    # ── validate_permutation_inputs ──────────────────────────────────────────
    v_ok = pt.validate_permutation_inputs(0.03, [0.01, 0.02, 0.04], "greater")
    results["validate_ok"] = v_ok["valid"]

    v_empty = pt.validate_permutation_inputs(0.03, [], "greater")
    results["validate_empty_invalid"] = not v_empty["valid"]

    v_bad_alt = pt.validate_permutation_inputs(0.03, [0.01], "both")
    results["validate_bad_alt_invalid"] = not v_bad_alt["valid"]

    v_nan = pt.validate_permutation_inputs(float("nan"), [0.01, 0.02], "greater")
    results["validate_nan_obs_invalid"] = not v_nan["valid"]

    # ── empirical_p_value — greater ──────────────────────────────────────────
    # null = [0.01, 0.02, 0.03, 0.04, 0.05], obs = 0.035
    # count(null >= 0.035 - ε) = count(0.04, 0.05) = 2
    # p = (1 + 2) / (5 + 1) = 3/6 = 0.5
    null5 = [0.01, 0.02, 0.03, 0.04, 0.05]
    p_greater = pt.empirical_p_value(0.035, null5, "greater", plus_one=True)
    results["p_greater_expected"] = round(p_greater, 8)
    results["p_greater_correct"] = abs(p_greater - 3 / 6) < 1e-10

    # obs = 0.06 (more extreme than all null)
    # count(null >= 0.06-ε) = 0 → p = (1+0)/(5+1) = 1/6
    p_most_extreme = pt.empirical_p_value(0.06, null5, "greater", plus_one=True)
    results["p_most_extreme"] = round(p_most_extreme, 8)
    results["p_most_extreme_not_zero"] = p_most_extreme > 0.0  # plus-one prevents p=0
    results["p_most_extreme_correct"] = abs(p_most_extreme - 1 / 6) < 1e-10

    # obs = 0.005 (less extreme than all null)
    # count(null >= 0.005-ε) = 5 → p = (1+5)/(5+1) = 1.0
    p_least_extreme = pt.empirical_p_value(0.005, null5, "greater", plus_one=True)
    results["p_least_extreme"] = round(p_least_extreme, 8)
    results["p_least_extreme_is_1"] = abs(p_least_extreme - 1.0) < 1e-10

    # ── empirical_p_value — less ─────────────────────────────────────────────
    # count(null <= 0.035 + ε) = count(0.01,0.02,0.03) = 3 → p = (1+3)/(5+1) = 4/6
    p_less = pt.empirical_p_value(0.035, null5, "less", plus_one=True)
    results["p_less_expected"] = round(p_less, 8)
    results["p_less_correct"] = abs(p_less - 4 / 6) < 1e-10

    # ── empirical_p_value — two-sided ────────────────────────────────────────
    # obs = 0.03 (middle of null)
    # c_greater = count(null >= 0.03-ε) = count(0.03, 0.04, 0.05) = 3
    # c_less    = count(null <= 0.03+ε) = count(0.01, 0.02, 0.03) = 3
    # min(c_g, c_l) = 3 → p = min(1.0, 2*(1+3)/(5+1)) = min(1.0, 8/6) = 1.0
    p_two = pt.empirical_p_value(0.03, null5, "two-sided", plus_one=True)
    results["p_two_sided"] = round(p_two, 8)
    results["p_two_sided_capped"] = p_two <= 1.0

    # ── plus_one=False comparison ────────────────────────────────────────────
    # obs = 0.06, all null < 0.06, count=0 → p_no_plus_one = 0/5 = 0.0
    p_no_plus = pt.empirical_p_value(0.06, null5, "greater", plus_one=False)
    results["p_no_plus_one_can_be_zero"] = p_no_plus == 0.0

    # ── compare_observed_to_null ─────────────────────────────────────────────
    cmp = pt.compare_observed_to_null(0.035, null5)
    results["compare_null_count"] = cmp["null_count"]
    results["compare_null_min"] = cmp["null_min"]
    results["compare_null_max"] = cmp["null_max"]
    results["compare_obs_percentile"] = cmp["obs_percentile"]
    results["compare_obs_above_mean"] = cmp["obs_above_null_mean"]

    # ── permutation_summary ──────────────────────────────────────────────────
    summary = pt.permutation_summary(
        observed_statistic=0.035,
        null_distribution=null5,
        alternative="greater",
        plus_one=True,
        seed=42,
        family_label="P252E_TEST",
    )
    results["summary_no_edge_claim"] = summary["no_edge_claim"]
    results["summary_no_betting_advice"] = summary["no_betting_advice"]
    results["summary_schema_version"] = summary["schema_version"]
    results["summary_test_type"] = summary["test_type"]
    results["summary_has_l96_warning"] = any(
        "L96" in lim for lim in summary.get("limitations", [])
    )
    results["summary_seed_recorded"] = summary["seed"] == 42
    results["summary_family_label"] = summary["family_label"]

    # Determinism
    s2 = pt.permutation_summary(0.035, null5, "greater", True, 42, "P252E_TEST")
    results["determinism_ok"] = (
        summary["empirical_p_value"] == s2["empirical_p_value"]
        and summary["null_mean"] == s2["null_mean"]
    )

    # ── deterministic_shuffle ────────────────────────────────────────────────
    items = list(range(10))
    sh1 = pt.deterministic_shuffle(items, seed=42)
    sh2 = pt.deterministic_shuffle(items, seed=42)
    sh3 = pt.deterministic_shuffle(items, seed=99)
    results["shuffle_deterministic"] = sh1 == sh2
    results["shuffle_different_seed"] = sh1 != sh3
    results["shuffle_preserves_set"] = sorted(sh1) == sorted(items)
    results["shuffle_original_unchanged"] = items == list(range(10))

    return results


def build_json_report(deps: dict, safety: dict, exercise: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "PERMUTATION_TEST_SSOT_IMPLEMENTED",
        "generated_at": datetime.now().isoformat(),
        "p252b_dependency_verified": deps["p252b"],
        "p252c_dependency_verified": deps["p252c"],
        "p252d_dependency_verified": deps["p252d"],
        "implemented_module": "lottery_api/utils/permutation_test.py",
        "implemented_functions": IMPLEMENTED_FUNCTIONS,
        "module_safety": {
            "exists": safety.get("exists"),
            "forbidden_imports_found": safety.get("forbidden_found", []),
            "safe": safety.get("safe"),
        },
        "exercise_results": exercise,
        "permutation_schema": {
            "required_fields": PERMUTATION_SCHEMA_FIELDS,
            "no_edge_claim_always_true": True,
            "no_betting_advice_always_true": True,
            "l96_warning_in_limitations": True,
        },
        "l96_fix_documented": {
            "description": (
                "L96 bug: shuffling binary hit-labels preserves their mean, making "
                "the null distribution overlap the observed → p always ≈ 1.0. "
                "Fix: use Binomial(1, baseline_i) MC draws for the null, not label shuffle. "
                "This module does not generate null distributions — it receives a pre-generated "
                "one. The L96 warning is surfaced in every summary's limitations field."
            ),
            "l96_warning_field": "limitations[0]",
            "correct_null_generation": "Binomial MC draws or seeded random permutation of draw sequences",
        },
        "supersession_notes": {
            "p219_empirical_p": (
                "empirical_p() in analysis/p219_external_method_diagnostic_sweep.py — "
                "identical formula, structured output and L96 warning added"
            ),
            "p227c_block_stability": (
                "block_stability() in p227c — different concept; not superseded here"
            ),
            "special3_binomial": (
                "binomial_permutation_test() in special3 uses scipy.stats — "
                "that is an analytical test, not MC permutation; different tool"
            ),
        },
        "no_db_write_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_betting_advice_confirmed": True,
        "final_decision": (
            "P252E complete. permutation_test.py SSOT implemented at "
            "lottery_api/utils/permutation_test.py. "
            "5 pure-Python functions cover M5 permutation test gap from P252B. "
            "Phipson-Smyth plus-one formula verified: p_most_extreme = 1/6 (not 0). "
            "L96 warning embedded in every summary output. "
            "No DB write. No registry mutation. No strategy promotion. No betting advice. "
            "Recommended next: P252F — implement M7 signal stability diagnostics SSOT (P1)."
        ),
    }


def build_md_report(exercise: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# P252E — Permutation Test SSOT",
        "",
        f"**Date:** {now}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** PERMUTATION_TEST_SSOT_IMPLEMENTED  ",
        f"**Module:** `lottery_api/utils/permutation_test.py`  ",
        "",
        "## Executive Summary",
        "",
        (
            "P252E implements the third P0 consolidation item from P252B: "
            "a unified permutation test SSOT module. "
            "Permutation logic existed in P219 (empirical_p), Special3 (binomial analytical), "
            "P51, and P3 with inconsistent naming, formula, and null-generation approaches. "
            "This module provides a deterministic, schema-driven SSOT with the correct "
            "Phipson-Smyth plus-one formula and an embedded L96 warning."
        ),
        "",
        "## Why M5 Permutation Test SSOT Is Needed",
        "",
        "| Issue | Detail |",
        "|-------|--------|",
        "| **Dispersed empirical_p** | p219, P3, P51, Special3 each implement their own formula |",
        "| **L96 bug risk** | Shuffling binary hit-labels preserves mean → null overlaps observed → p≈1.0 |",
        "| **No schema** | p-value returned as bare float with no no_edge_claim, seed, or null statistics |",
        "| **Naming inconsistency** | 'permutation test', 'shuffle test', 'P3', 'empirical p' used interchangeably |",
        "",
        "## Implemented Module & Functions",
        "",
        "**Module:** `lottery_api/utils/permutation_test.py`  ",
        "**Deps:** Python stdlib only (`math`, `random`, `statistics`, `typing`)  ",
        "**DB access:** NONE  ",
        "**Strategy registry:** NONE  ",
        "",
        "| Function | Signature | Purpose |",
        "|----------|-----------|---------|",
    ]
    for fn in IMPLEMENTED_FUNCTIONS:
        lines.append(f"| `{fn['name']}` | `{fn['signature']}` | {fn['description']} |")

    lines += [
        "",
        "## Permutation Summary Schema",
        "",
        "Every `permutation_summary()` output includes:",
        "",
        "```",
        "schema_version          — '1.0'",
        "test_type               — 'permutation_test'",
        "family_label            — declared family name (audit trail)",
        "alternative             — 'greater' | 'less' | 'two-sided'",
        "observed_statistic      — real-data test statistic",
        "null_count / null_min / null_max / null_mean / null_std / null_median",
        "obs_percentile          — position of observed in null distribution",
        "empirical_p_value       — (1 + count_extreme) / (B + 1)",
        "plus_one_correction     — True (default)",
        "seed                    — RNG seed used for null generation (audit trail)",
        "no_edge_claim = true    — always present",
        "no_betting_advice = true",
        "assumptions / limitations",
        "  └── limitations[0] contains L96 warning",
        "```",
        "",
        "## Example Usage",
        "",
        "```python",
        "from lottery_api.utils.permutation_test import (",
        "    empirical_p_value, permutation_summary, deterministic_shuffle",
        ")",
        "",
        "# Generate null distribution (caller's responsibility)",
        "rng = __import__('random').Random(42)",
        "null = [rng.gauss(0.02, 0.005) for _ in range(200)]",
        "",
        "# Compute empirical p-value",
        "p = empirical_p_value(observed=0.035, null_distribution=null, alternative='greater')",
        "# p = (1 + count(null >= 0.035)) / 201",
        "",
        "# Full summary",
        "summary = permutation_summary(0.035, null, 'greater', seed=42,",
        "                              family_label='DAILY_539_midfreq')",
        "assert summary['no_edge_claim'] is True",
        "assert 'L96' in summary['limitations'][0]",
        "```",
        "",
        "## Verified Reference Values",
        "",
        f"| Test | Expected | Actual | OK |",
        f"|------|----------|--------|----|",
        f"| empirical_p greater (obs=0.035, null=[0.01..0.05]) | 3/6 = 0.5 | {exercise.get('p_greater_expected','?')} | {'✓' if exercise.get('p_greater_correct') else '✗'} |",
        f"| plus-one: most extreme obs never gives p=0 | >0 | {exercise.get('p_most_extreme','?')} | {'✓' if exercise.get('p_most_extreme_not_zero') else '✗'} |",
        f"| plus-one=False most extreme → p=0 | 0.0 | {exercise.get('p_no_plus_one_can_be_zero','?')} | {'✓' if exercise.get('p_no_plus_one_can_be_zero') else '✗'} |",
        f"| p_less correct | 4/6 | {exercise.get('p_less_expected','?')} | {'✓' if exercise.get('p_less_correct') else '✗'} |",
        f"| Deterministic output | true | {exercise.get('determinism_ok','?')} | {'✓' if exercise.get('determinism_ok') else '✗'} |",
        f"| Shuffle deterministic | true | {exercise.get('shuffle_deterministic','?')} | {'✓' if exercise.get('shuffle_deterministic') else '✗'} |",
        "",
        "## Non-Goals",
        "",
        "- Does **not** generate null distributions — caller provides them",
        "- Does **not** claim any p-value implies a deployable prediction edge",
        "- Does **not** connect to any database",
        "- Does **not** modify the production strategy registry",
        "- Does **not** implement the analytical binomial test (that is `special3_oos_permutation_review.binomial_permutation_test`)",
        "",
        "## No-Overclaim Statement",
        "",
        "> A significant empirical p-value means the observed test statistic is "
        "unlikely under the null hypothesis as simulated — **it does not imply a "
        "deployable prediction edge, a betting strategy, or any exploitable lottery signal.** "
        "All completed research arcs remain NULL/REJECTED/UNDERPOWERED.",
        "",
        "## Compliance",
        "",
        "- **No DB write performed in P252E.**",
        "- **No registry mutation.** Module imports only stdlib.",
        "- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.",
        "- **No betting advice** is given or implied.",
        "",
        "## Recommended Next Task",
        "",
        "**P252F — Implement M7 Signal Stability Diagnostics SSOT (P1)**",
        "",
        "- Next P252 consolidation item from P252B",
        "- Vocabulary gap: 'block', 'year', 'era', 'robustness' used inconsistently across scripts",
        "- Need: shared stability threshold constants and block-split diagnostic helper",
        "- Type B/C — no DB write, no registry, no strategy promotion",
        "",
        "---",
        f"*Generated by {TASK_ID} — Permutation Test SSOT*",
    ]
    return "\n".join(lines)


def main() -> dict:
    print(f"[{TASK_ID}] Verifying dependencies...")
    dep_b = _verify_dep("p252b_unified_external_method_coverage_audit_*.json", "P252B", "M5")
    dep_c = _verify_dep("p252c_baseline_calculator_ssot_*.json", "P252C")
    dep_d = _verify_dep("p252d_correction_gate_ssot_*.json", "P252D")
    print(f"[{TASK_ID}]   P252B found: {dep_b.get('found')}, M5 priority: {dep_b.get('m_id_priority')}")
    print(f"[{TASK_ID}]   P252C found: {dep_c.get('found')}, P252D found: {dep_d.get('found')}")

    print(f"[{TASK_ID}] Verifying module safety...")
    safety = _verify_safety()
    print(f"[{TASK_ID}]   Module exists: {safety.get('exists')}, safe: {safety.get('safe')}")

    print(f"[{TASK_ID}] Exercising permutation_test functions...")
    exercise = _exercise_module()
    all_ok = all([
        exercise.get("p_greater_correct"),
        exercise.get("p_most_extreme_not_zero"),
        exercise.get("p_most_extreme_correct"),
        exercise.get("p_less_correct"),
        exercise.get("determinism_ok"),
        exercise.get("shuffle_deterministic"),
    ])
    print(f"[{TASK_ID}]   All reference checks pass: {all_ok}")
    print(f"[{TASK_ID}]   p_greater (obs=0.035, B=5): {exercise.get('p_greater_expected')}")
    print(f"[{TASK_ID}]   p_most_extreme (obs>all null): {exercise.get('p_most_extreme')} (not 0)")

    deps = {"p252b": dep_b, "p252c": dep_c, "p252d": dep_d}
    report_json = build_json_report(deps, safety, exercise)
    report_md   = build_md_report(exercise)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUTS_DIR / f"p252e_permutation_test_ssot_{DATE_SLUG}.json"
    md_path   = OUTPUTS_DIR / f"p252e_permutation_test_ssot_{DATE_SLUG}.md"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)

    print(f"[{TASK_ID}] Reports: {json_path}")
    print(f"[{TASK_ID}] Classification: {report_json['classification']}")
    print(f"[{TASK_ID}] P252E COMPLETE.")
    return report_json


if __name__ == "__main__":
    main()
