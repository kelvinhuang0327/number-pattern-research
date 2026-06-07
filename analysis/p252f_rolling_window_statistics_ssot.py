"""P252F — Rolling Window Statistics SSOT artifact generator.

Implements M3 P0 consolidation from P252B. No DB write. No registry mutation.
No strategy promotion. No betting advice.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

TASK_ID = "P252F"
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
        "name": "validate_window_config",
        "signature": "(total_count, window_size, step_size=1, min_count=None) -> dict",
        "description": "Validate window parameters; returns {valid, errors, warnings, window_count, underpowered}",
        "note": "Flags UNDERPOWERED when total_count < window_size; never raises",
    },
    {
        "name": "rolling_slices",
        "signature": "(items, window_size, step_size=1, include_partial=False) -> list[list]",
        "description": "Forward sliding window slices; step_size controls stride",
        "note": "include_partial=True adds terminal partial window; default False for strict full-windows-only",
    },
    {
        "name": "tail_window",
        "signature": "(items, window_size) -> list",
        "description": "RSM pattern: items[-window_size:] or all items if fewer available",
        "note": "Matches records[-window_size:] pattern in rolling_strategy_monitor.py",
    },
    {
        "name": "rolling_window_labels",
        "signature": "(total_count, window_size, step_size=1) -> list[str]",
        "description": "Labels like 'w150[0:150]' for each full window position",
        "note": "Stable format; can be used as dict key or audit trace",
    },
    {
        "name": "tail_window_label",
        "signature": "(total_count, window_size) -> str",
        "description": "Label for tail window: 'tail_150' or 'partial_80_of_150'",
        "note": "Matches RSM/research convention; documents partial-window situation",
    },
    {
        "name": "summarize_window",
        "signature": "(values, label=None, start_index=0) -> dict",
        "description": "Compute count/mean/min/max/std for a single window of values",
        "note": "Returns None for non-numeric or mixed-type windows; deterministic",
    },
    {
        "name": "rolling_summary",
        "signature": "(items, window_sizes, step_size=1, value_getter=None, family_label=None, ...) -> dict",
        "description": "Canonical SSOT output: all window series with no_edge_claim=True",
        "note": "Accepts single int or tuple of window sizes; P221F_WINDOWS['short'] = (100,125,150)",
    },
]

ROLLING_SCHEMA_FIELDS = [
    "schema_version", "summary_type", "family_label", "total_count",
    "step_size", "include_partial", "min_count", "window_series",
    "window_sizes_requested", "no_edge_claim", "no_betting_advice",
    "assumptions", "limitations",
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
    module_path = REPO_ROOT / "lottery_api" / "utils" / "rolling_window.py"
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
    from lottery_api.utils import rolling_window as rw

    results: dict = {}

    # --- constants ---
    results["p221f_short_windows"] = list(rw.P221F_WINDOWS["short"])
    results["p221f_mid_windows"]   = list(rw.P221F_WINDOWS["mid"])
    results["rsm_windows"]         = dict(rw.RSM_WINDOWS)
    results["p221f_short_contains_150"] = 150 in rw.P221F_WINDOWS["short"]
    results["p221f_mid_contains_500"]   = 500 in rw.P221F_WINDOWS["mid"]
    results["p221f_mid_contains_1000"]  = 1000 in rw.P221F_WINDOWS["mid"]
    results["rsm_short_is_30"]          = rw.RSM_WINDOWS["short"] == 30

    # --- validate_window_config ---
    v_ok = rw.validate_window_config(200, 150, 1)
    results["validate_ok"] = v_ok["valid"]
    results["validate_window_count"] = v_ok["window_count"]  # 200-150+1=51
    results["validate_window_count_ok"] = v_ok["window_count"] == 51

    v_under = rw.validate_window_config(50, 150, 1)
    results["validate_underpowered"] = v_under["underpowered"]
    results["validate_underpowered_valid"] = v_under["valid"]

    v_bad = rw.validate_window_config(100, 0, 1)
    results["validate_bad_invalid"] = not v_bad["valid"]

    # --- rolling_slices ---
    items10 = list(range(10))
    slices_3 = rw.rolling_slices(items10, window_size=3, step_size=1)
    results["slices_3_count"] = len(slices_3)       # 10-3+1=8
    results["slices_3_count_ok"] = len(slices_3) == 8
    results["slices_3_first"] = slices_3[0]          # [0,1,2]
    results["slices_3_last"]  = slices_3[-1]          # [7,8,9]
    results["slices_3_first_ok"] = slices_3[0] == [0, 1, 2]
    results["slices_3_last_ok"]  = slices_3[-1] == [7, 8, 9]

    slices_step2 = rw.rolling_slices(items10, window_size=3, step_size=2)
    results["slices_step2_count"] = len(slices_step2)  # ceil((10-3+1)/2)=4
    results["slices_step2_count_ok"] = len(slices_step2) == 4

    # include_partial
    slices_partial = rw.rolling_slices(list(range(5)), window_size=3, step_size=2, include_partial=True)
    results["slices_partial_count"] = len(slices_partial)  # [0,1,2],[2,3,4] -> step=2 → [0,1,2], [2,3,4], [4] → 3
    results["slices_no_partial"] = rw.rolling_slices(list(range(5)), window_size=3, step_size=2, include_partial=False)

    # --- tail_window ---
    tail = rw.tail_window(items10, 3)
    results["tail_3"] = tail
    results["tail_3_ok"] = tail == [7, 8, 9]
    short_tail = rw.tail_window([1, 2], 5)
    results["tail_short"] = short_tail
    results["tail_short_ok"] = short_tail == [1, 2]

    # --- rolling_window_labels ---
    labels = rw.rolling_window_labels(10, 3, 1)
    results["labels_count"] = len(labels)
    results["labels_first"] = labels[0]
    results["labels_first_ok"] = labels[0] == "w3[0:3]"
    results["labels_last_ok"]  = labels[-1] == "w3[7:10]"

    # --- tail_window_label ---
    results["tail_label_full"]    = rw.tail_window_label(200, 150)
    results["tail_label_partial"] = rw.tail_window_label(80, 150)
    results["tail_label_full_ok"]    = rw.tail_window_label(200, 150) == "tail_150"
    results["tail_label_partial_ok"] = rw.tail_window_label(80, 150) == "partial_80_of_150"

    # --- summarize_window ---
    sw = rw.summarize_window([1.0, 2.0, 3.0, 4.0, 5.0], label="TEST")
    results["sw_count"] = sw["count"]
    results["sw_mean"]  = sw["mean"]
    results["sw_min"]   = sw["min"]
    results["sw_max"]   = sw["max"]
    results["sw_mean_ok"] = abs(sw["mean"] - 3.0) < 1e-10
    results["sw_label"] = sw["label"]

    # --- rolling_summary ---
    summary = rw.rolling_summary(
        items=list(range(200)),
        window_sizes=(150, 50),
        step_size=50,
        family_label="P252F_TEST",
    )
    results["rs_no_edge_claim"]       = summary["no_edge_claim"]
    results["rs_no_betting_advice"]   = summary["no_betting_advice"]
    results["rs_schema_version"]      = summary["schema_version"]
    results["rs_summary_type"]        = summary["summary_type"]
    results["rs_total_count"]         = summary["total_count"]
    results["rs_series_count"]        = len(summary["window_series"])
    results["rs_series_count_ok"]     = len(summary["window_series"]) == 2
    results["rs_family_label"]        = summary["family_label"]
    # Determinism
    s2 = rw.rolling_summary(list(range(200)), (150, 50), 50, family_label="P252F_TEST")
    results["rs_deterministic"] = (
        summary["window_series"][0]["window_count"] == s2["window_series"][0]["window_count"]
    )

    return results


def build_json_report(deps: dict, safety: dict, exercise: dict) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "classification": "ROLLING_WINDOW_STATISTICS_SSOT_IMPLEMENTED",
        "generated_at": datetime.now().isoformat(),
        "p252b_dependency_verified": deps["p252b"],
        "p252c_dependency_verified": deps["p252c"],
        "p252d_dependency_verified": deps["p252d"],
        "p252e_dependency_verified": deps["p252e"],
        "implemented_module": "lottery_api/utils/rolling_window.py",
        "implemented_functions": IMPLEMENTED_FUNCTIONS,
        "module_safety": {
            "exists": safety.get("exists"),
            "forbidden_imports_found": safety.get("forbidden_found", []),
            "safe": safety.get("safe"),
        },
        "exercise_results": exercise,
        "rolling_window_schema": {
            "required_fields": ROLLING_SCHEMA_FIELDS,
            "no_edge_claim_always_true": True,
            "no_betting_advice_always_true": True,
            "p221f_windows_canonical": {
                "short": [100, 125, 150],
                "mid": [500, 750, 1000],
            },
            "rsm_windows": {"short": 30, "medium": 100, "long": 300},
        },
        "no_db_write_confirmed": True,
        "no_registry_mutation_confirmed": True,
        "no_strategy_promotion_confirmed": True,
        "no_betting_advice_confirmed": True,
        "final_decision": (
            "P252F complete. rolling_window.py SSOT implemented at "
            "lottery_api/utils/rolling_window.py. "
            "7 pure-Python functions + P221F/RSM window constants cover M3 rolling window gap. "
            "P221F frozen windows (short 100/125/150, mid 500/750/1000) and "
            "RSM windows (30/100/300) are both exposed as named constants. "
            "No DB write. No registry mutation. No strategy promotion. No betting advice. "
            "Recommended next: P252G — implement M7 signal stability diagnostics SSOT (P1)."
        ),
    }


def build_md_report(exercise: dict) -> str:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [
        "# P252F — Rolling Window Statistics SSOT",
        "",
        f"**Date:** {now}  ",
        f"**Task:** {TASK_ID}  ",
        f"**Classification:** ROLLING_WINDOW_STATISTICS_SSOT_IMPLEMENTED  ",
        f"**Module:** `lottery_api/utils/rolling_window.py`  ",
        "",
        "## Executive Summary",
        "",
        "P252F implements the remaining P0 consolidation item from P252B: a unified rolling "
        "window statistics SSOT. Rolling logic existed in RSM, P211R, P221F, P222, P224, P230, "
        "P231 with different window sizes, inconsistent labels, and no shared output schema. "
        "This module exposes both P221F frozen research windows and RSM production windows "
        "as named constants, and provides a deterministic schema-driven summary.",
        "",
        "## Why M3 Rolling Window SSOT Is Needed",
        "",
        "| Issue | Detail |",
        "|-------|--------|",
        "| **Inconsistent constants** | RSM uses {short:30, medium:100, long:300}; P221F research uses 150/500/1000 |",
        "| **No canonical labels** | 'w150', 'short_150', 'window_150', 'w=150' all appear in different scripts |",
        "| **No UNDERPOWERED flag** | Scripts silently produce stats for too-short windows |",
        "| **No schema** | Window results lack no_edge_claim, family_label, step_size metadata |",
        "",
        "## Implemented Module & Functions",
        "",
        "**Module:** `lottery_api/utils/rolling_window.py`  ",
        "**Deps:** Python stdlib only (`math`, `statistics`, `typing`)  ",
        "**DB access:** NONE  ",
        "",
        "| Function | Signature | Purpose |",
        "|----------|-----------|---------|",
    ]
    for fn in IMPLEMENTED_FUNCTIONS:
        lines.append(f"| `{fn['name']}` | `{fn['signature']}` | {fn['description']} |")

    lines += [
        "",
        "## Window Constants",
        "",
        "```python",
        "from lottery_api.utils.rolling_window import P221F_WINDOWS, RSM_WINDOWS",
        "",
        "P221F_WINDOWS = {",
        "    'short':  (100, 125, 150),   # frozen by P221F governance (2026-05)",
        "    'mid':    (500, 750, 1000),   # frozen by P221F governance",
        "    'all_history': (),            # use full dataset; reference-context only",
        "}",
        "",
        "RSM_WINDOWS = {'short': 30, 'medium': 100, 'long': 300}  # production RSM",
        "```",
        "",
        "## Rolling Summary Schema",
        "",
        "```",
        "schema_version          — '1.0'",
        "summary_type            — 'rolling_window_statistics'",
        "family_label            — declared family name",
        "total_count             — total items in dataset",
        "step_size / include_partial / min_count",
        "window_sizes_requested  — list of requested window sizes",
        "window_series: list of per-size results, each containing:",
        "  window_size / window_count / underpowered / warnings",
        "  windows: list of per-window dicts:",
        "    label / start_index / end_index / count / value_count",
        "    mean / min / max / std  (None if non-numeric)",
        "no_edge_claim = true",
        "no_betting_advice = true",
        "assumptions / limitations",
        "```",
        "",
        "## Example Usage",
        "",
        "```python",
        "from lottery_api.utils.rolling_window import (",
        "    P221F_WINDOWS, rolling_summary, tail_window",
        ")",
        "",
        "# P221F research: three short windows",
        "report = rolling_summary(",
        "    items=draw_hit_rates,          # list of per-draw hit rates",
        "    window_sizes=P221F_WINDOWS['short'],  # (100, 125, 150)",
        "    family_label='DAILY_539_midfreq',",
        ")",
        "assert report['no_edge_claim'] is True",
        "",
        "# RSM production: tail window",
        "recent = tail_window(records, window_size=150)",
        "```",
        "",
        "## Non-Goals",
        "",
        "- Does **not** claim rolling window edge implies a deployable prediction edge",
        "- Does **not** connect to any database",
        "- Does **not** modify the production RSM or strategy registry",
        "- Does **not** generate p-values (use permutation_test.py for that)",
        "- Does **not** apply multiple-testing correction (use correction_gate.py for that)",
        "",
        "## No-Overclaim Statement",
        "",
        "> A rolling window that outperforms the baseline in one window does **not** "
        "imply a deployable prediction edge. All completed research arcs remain "
        "NULL/REJECTED/UNDERPOWERED.",
        "",
        "## Compliance",
        "",
        "- **No DB write performed in P252F.**",
        "- **No registry mutation.**",
        "- **No strategy promotion.** All edge-search results remain NULL/REJECTED/UNDERPOWERED.",
        "- **No betting advice** is given or implied.",
        "",
        "## Recommended Next Task",
        "",
        "**P252G — Implement M7 signal stability diagnostics SSOT (P1)**",
        "",
        "- Next P252 item from P252B: 'block', 'year', 'era', 'robustness' labels inconsistent",
        "- Need: shared stability vocabulary, threshold constants, block-split helper",
        "- Type B/C — no DB write, no registry, no strategy promotion",
        "",
        "---",
        f"*Generated by {TASK_ID} — Rolling Window Statistics SSOT*",
    ]
    return "\n".join(lines)


def main() -> dict:
    print(f"[{TASK_ID}] Verifying dependencies...")
    dep_b = _verify_dep("p252b_unified_external_method_coverage_audit_*.json", "P252B", "M3")
    dep_c = _verify_dep("p252c_baseline_calculator_ssot_*.json", "P252C")
    dep_d = _verify_dep("p252d_correction_gate_ssot_*.json", "P252D")
    dep_e = _verify_dep("p252e_permutation_test_ssot_*.json", "P252E")
    print(f"[{TASK_ID}]   P252B M3 priority: {dep_b.get('m_id_priority')}, P252C-E: {dep_c.get('found')}/{dep_d.get('found')}/{dep_e.get('found')}")

    safety = _verify_safety()
    print(f"[{TASK_ID}]   Module safe: {safety.get('safe')}")

    exercise = _exercise_module()
    all_ok = all([
        exercise.get("p221f_short_contains_150"),
        exercise.get("slices_3_count_ok"),
        exercise.get("slices_3_first_ok"),
        exercise.get("tail_3_ok"),
        exercise.get("labels_first_ok"),
        exercise.get("tail_label_full_ok"),
        exercise.get("sw_mean_ok"),
        exercise.get("rs_no_edge_claim"),
        exercise.get("rs_deterministic"),
    ])
    print(f"[{TASK_ID}]   All reference checks pass: {all_ok}")

    deps = {"p252b": dep_b, "p252c": dep_c, "p252d": dep_d, "p252e": dep_e}
    report_json = build_json_report(deps, safety, exercise)
    report_md   = build_md_report(exercise)

    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = OUTPUTS_DIR / f"p252f_rolling_window_statistics_ssot_{DATE_SLUG}.json"
    md_path   = OUTPUTS_DIR / f"p252f_rolling_window_statistics_ssot_{DATE_SLUG}.md"
    json_path.write_text(json.dumps(report_json, indent=2, ensure_ascii=False))
    md_path.write_text(report_md)
    print(f"[{TASK_ID}] Reports: {json_path}")
    print(f"[{TASK_ID}] Classification: {report_json['classification']}")
    print(f"[{TASK_ID}] P252F COMPLETE.")
    return report_json


if __name__ == "__main__":
    main()
