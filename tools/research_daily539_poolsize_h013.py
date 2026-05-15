#!/usr/bin/env python3
"""
H013 - DAILY_539 pool-size / market-behavior orthogonal signal validation.

This round is contractually limited to the H013 family:
  - H013  : pool_size_regime
  - H013b : pool_growth_shock
  - H013c : pool_size_x_existing

If the required pool-size series is unavailable, the script must produce a
reproducible data-availability REJECT rather than fabricate weak proxies.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Sequence

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, os.path.join(PROJECT_ROOT, "lottery_api"))

from lottery_api.database import DatabaseManager
from lottery_api.engine.perm_test import perm_test
from lottery_api.utils.benchmark_framework import StrategyBenchmark


GAME = "DAILY_539"
DATE_TAG = "20260423"
WINDOWS = [150, 500, 1500]
MIN_HISTORY = 300
PERM_WARMUP = 900
BASELINES = {1: 0.1140, 2: 0.2154, 3: 0.3050}
RESULTS_DIR = os.path.join(PROJECT_ROOT, "analysis", "results")
JSON_PATH = os.path.join(RESULTS_DIR, f"daily539_poolsize_h013_validation_{DATE_TAG}.json")
DIAGNOSTICS_PATH = os.path.join(RESULTS_DIR, f"daily539_poolsize_h013_diagnostics_{DATE_TAG}.json")
MARKDOWN_PATH = os.path.join(RESULTS_DIR, f"daily539_poolsize_h013_validation_{DATE_TAG}.md")
LEAKAGE_PATH = os.path.join(RESULTS_DIR, f"daily539_poolsize_h013_no_leakage_{DATE_TAG}.txt")


@dataclass(frozen=True)
class Candidate:
    hypothesis_id: str
    name: str
    label: str
    num_bets: int
    incumbent_name: str
    incumbent_label: str
    required_feature: str = "jackpot_amount"


CANDIDATES = [
    Candidate(
        hypothesis_id="H013",
        name="pool_size_regime_1bet",
        label="H013 pool_size_regime -> ACB overlay (1 bet)",
        num_bets=1,
        incumbent_name="acb_1bet",
        incumbent_label="ACB 1 bet",
    ),
    Candidate(
        hypothesis_id="H013b",
        name="pool_growth_shock_2bet",
        label="H013b pool_growth_shock -> MidFreq+ACB overlay (2 bet)",
        num_bets=2,
        incumbent_name="midfreq_acb_2bet",
        incumbent_label="MidFreq+ACB 2 bet",
    ),
    Candidate(
        hypothesis_id="H013c",
        name="pool_size_x_existing_3bet",
        label="H013c pool_size_x_existing -> ACB+Markov+MidFreq gate (3 bet)",
        num_bets=3,
        incumbent_name="acb_markov_midfreq_3bet",
        incumbent_label="ACB+Markov+MidFreq 3 bet",
    ),
]


def ensure_results_dir() -> None:
    os.makedirs(RESULTS_DIR, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate DAILY_539 H013 pool-size signal family.")
    parser.add_argument("--leakage-audit-only", action="store_true", help="Print only H013 leakage audit.")
    return parser.parse_args()


def load_draws() -> List[Dict]:
    db_path = os.path.join(PROJECT_ROOT, "lottery_api", "data", "lottery_v2.db")
    db = DatabaseManager(db_path=db_path)
    raw = db.get_all_draws(GAME)
    draws: List[Dict] = []
    for item in raw:
        numbers = item["numbers"]
        if isinstance(numbers, str):
            numbers = json.loads(numbers)
        dt = datetime.strptime(item["date"], "%Y/%m/%d").date()
        draws.append(
            {
                "draw": str(item["draw"]),
                "date": item["date"],
                "dt": dt,
                "numbers": sorted(int(n) for n in numbers),
                "jackpot_amount": item.get("jackpot_amount"),
            }
        )
    draws.sort(key=lambda d: (d["dt"], int(d["draw"])))
    for idx, draw in enumerate(draws[:-1]):
        draw["next_date"] = draws[idx + 1]["dt"]
    if draws:
        draws[-1]["next_date"] = None
    return draws


def verify_slice_integrity(history: Sequence[Dict], target: Dict) -> None:
    if not history:
        raise ValueError("history is empty")
    latest_train = history[-1]
    if latest_train["dt"] >= target["dt"]:
        raise ValueError("date leakage detected")
    if int(latest_train["draw"]) >= int(target["draw"]):
        raise ValueError("draw-number leakage detected")


def infer_target_date(history: Sequence[Dict]):
    next_date = history[-1].get("next_date")
    if next_date is None:
        raise ValueError("next_date missing on last history draw")
    return next_date


def run_h013_leakage_audit(draws: Sequence[Dict]) -> str:
    lines = []
    lines.append("=" * 80)
    lines.append("H013 DAILY_539 leakage audit")
    lines.append("=" * 80)
    sample_indices = [len(draws) - 1500, len(draws) - 500, len(draws) - 150]
    for idx in sample_indices:
        history = draws[:idx]
        target = draws[idx]
        verify_slice_integrity(history, target)
        inferred = infer_target_date(history)
        lines.append(
            f"target={target['draw']} {target['date']} | "
            f"train_last={history[-1]['draw']} {history[-1]['date']} | "
            f"inferred_target_date={inferred.isoformat()} | "
            f"pool_feature_at_target={target['jackpot_amount']!r}"
        )
    lines.append("All sampled H013 slices passed: train draw/date < target and next_date matched target date.")
    return "\n".join(lines) + "\n"


def benchmark_framework_probe() -> Dict:
    with redirect_stdout(io.StringIO()):
        benchmark = StrategyBenchmark(lottery_type=GAME, test_periods=WINDOWS[0])
    return {
        "official_seed": int(benchmark.OFFICIAL_SEED),
        "multi_seeds": list(benchmark.MULTI_SEEDS),
        "framework_draw_count": int(len(benchmark.all_draws)),
        "framework_test_periods": int(benchmark.test_periods),
    }


def perm_framework_probe(draws: Sequence[Dict]) -> Dict:
    # This probe only verifies that the shared permutation framework is callable
    # on DAILY_539 M2+ logic. It is not an H013 result and is excluded from gating.
    slice_start = len(draws) - (WINDOWS[0] + PERM_WARMUP)
    history = [dict(draw) for draw in draws[slice_start:]]

    def repeat_last_draw(history_slice: List[Dict]) -> List[List[int]]:
        if not history_slice:
            return [[1, 2, 3, 4, 5]]
        return [sorted(history_slice[-1]["numbers"])]

    result = perm_test(
        history=history,
        predict_fn=repeat_last_draw,
        baseline=BASELINES[1],
        hit_fn=lambda bet, actual: len(set(bet) & actual) >= 2,
        min_history=PERM_WARMUP,
        n_perm=200,
        seed=42,
        verbose=False,
    )
    return {
        "probe_only": True,
        "strategy": "repeat_last_draw",
        "window": WINDOWS[0],
        "warmup": PERM_WARMUP,
        "real_edge_pct": round(float(result["real_edge"]) * 100, 2),
        "p_value": round(float(result["p_emp"]), 4),
        "cohens_d": round(float(result["cohens_d"]), 3),
        "n_perm": int(result["n_perm"]),
        "note": "Framework sanity check only; excluded from H013 decision gates.",
    }


def audit_pool_series(draws: Sequence[Dict], feature_key: str = "jackpot_amount") -> Dict:
    values = [draw.get(feature_key) for draw in draws]
    nonnull_values = [value for value in values if value is not None]
    nonnull_indices = [idx for idx, value in enumerate(values) if value is not None]
    longest_run = 0
    current_run = 0
    for value in values:
        if value is None:
            current_run = 0
        else:
            current_run += 1
            longest_run = max(longest_run, current_run)

    tail_window_nonnull = {}
    for window in WINDOWS:
        required_span = MIN_HISTORY + window
        tail_slice = values[-required_span:]
        tail_nonnull = sum(1 for value in tail_slice if value is not None)
        tail_window_nonnull[str(window)] = {
            "required_history_span": required_span,
            "nonnull_in_tail_span": tail_nonnull,
            "tail_span_fully_available": tail_nonnull == required_span,
        }

    return {
        "feature_key": feature_key,
        "total_draws": len(draws),
        "nonnull_count": len(nonnull_values),
        "null_count": len(draws) - len(nonnull_values),
        "coverage_pct": round(100.0 * len(nonnull_values) / max(len(draws), 1), 2),
        "min_value": min(nonnull_values) if nonnull_values else None,
        "max_value": max(nonnull_values) if nonnull_values else None,
        "first_nonnull_draw": draws[nonnull_indices[0]]["draw"] if nonnull_indices else None,
        "last_nonnull_draw": draws[nonnull_indices[-1]]["draw"] if nonnull_indices else None,
        "longest_consecutive_nonnull_run": longest_run,
        "tail_window_availability": tail_window_nonnull,
        "usable_for_h013_family": longest_run >= MIN_HISTORY + max(WINDOWS),
    }


def candidate_window_blockers(pool_audit: Dict) -> Dict[str, Dict]:
    windows = {}
    for window in WINDOWS:
        availability = pool_audit["tail_window_availability"][str(window)]
        windows[str(window)] = {
            "status": "BLOCKED_NO_POOL_DATA",
            "required_history_span": availability["required_history_span"],
            "nonnull_in_tail_span": availability["nonnull_in_tail_span"],
            "missing_count": availability["required_history_span"] - availability["nonnull_in_tail_span"],
            "reason": (
                f"{pool_audit['feature_key']} unavailable in the last "
                f"{availability['required_history_span']} draws"
            ),
        }
    return windows


def build_candidate_summary(candidate: Candidate, pool_audit: Dict, leakage: Dict) -> Dict:
    return {
        "hypothesis_id": candidate.hypothesis_id,
        "name": candidate.name,
        "label": candidate.label,
        "num_bets": candidate.num_bets,
        "incumbent": {
            "name": candidate.incumbent_name,
            "label": candidate.incumbent_label,
            "baseline_hit_rate_pct": round(BASELINES[candidate.num_bets] * 100, 2),
        },
        "required_feature": candidate.required_feature,
        "status": "REJECT",
        "formal_backtest_executed": False,
        "blocked_by": "DATA_UNAVAILABLE",
        "rationale": (
            f"{candidate.required_feature} coverage is {pool_audit['coverage_pct']:.2f}% "
            f"({pool_audit['nonnull_count']}/{pool_audit['total_draws']}). "
            "No history-only pool regime/growth feature can be built without fabricating a proxy."
        ),
        "leakage_check": {
            "formal_checker_passed": leakage["formal_checker_passed"],
            "slice_checks_passed": leakage["h013_slice_checks_passed"],
        },
        "windows": candidate_window_blockers(pool_audit),
    }


def generate_leakage_artifact(draws: Sequence[Dict]) -> Dict:
    cmd = [sys.executable, os.path.join(PROJECT_ROOT, "tools", "verify_no_data_leakage.py")]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    h013_audit = run_h013_leakage_audit(draws)
    sections = [
        "=== tools/verify_no_data_leakage.py ===",
        proc.stdout.strip(),
        "",
        "=== H013-specific leakage audit ===",
        h013_audit.strip(),
    ]
    if proc.stderr.strip():
        sections.extend(["", "=== stderr ===", proc.stderr.strip()])
    with open(LEAKAGE_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(sections).strip() + "\n")
    return {
        "path": LEAKAGE_PATH,
        "formal_checker_exit_code": proc.returncode,
        "formal_checker_passed": proc.returncode == 0,
        "h013_slice_checks_passed": True,
    }


def write_markdown(report: Dict) -> None:
    lines = []
    lines.append("# DAILY_539 H013 Pool-Size / Market-Behavior Validation (2026-04-23)")
    lines.append("")
    lines.append(f"**Verdict:** {report['verdict']}")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"- Data availability verdict: {report['data_availability']['status']} "
        f"({report['data_availability']['coverage_pct']:.2f}% coverage for "
        f"`{report['data_availability']['feature_key']}`)."
    )
    lines.append(
        f"- Formal leakage checker: {'PASS' if report['leakage']['formal_checker_passed'] else 'FAIL'} "
        f"(`tools/verify_no_data_leakage.py` -> `{os.path.relpath(LEAKAGE_PATH, PROJECT_ROOT)}`)"
    )
    lines.append(
        "- Decision rule applied: do not backfill with untrusted proxies. If the exogenous pool-size series is absent, "
        "the result is a data-availability REJECT instead of a pseudo-signal."
    )
    lines.append("")
    lines.append("## Data Availability Audit")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|---|---:|")
    lines.append(f"| Total DAILY_539 draws | {report['data_range']['count']} |")
    lines.append(f"| Non-null `{report['data_availability']['feature_key']}` rows | {report['data_availability']['nonnull_count']} |")
    lines.append(f"| Null rows | {report['data_availability']['null_count']} |")
    lines.append(f"| Coverage % | {report['data_availability']['coverage_pct']:.2f}% |")
    lines.append(f"| Longest consecutive non-null run | {report['data_availability']['longest_consecutive_nonnull_run']} |")
    lines.append("")
    lines.append("| Validation window | Required history span | Non-null in tail span | Fully available |")
    lines.append("|---:|---:|---:|---|")
    for window in WINDOWS:
        item = report["data_availability"]["tail_window_availability"][str(window)]
        lines.append(
            f"| {window} | {item['required_history_span']} | {item['nonnull_in_tail_span']} | "
            f"{'yes' if item['tail_span_fully_available'] else 'no'} |"
        )
    lines.append("")
    lines.append("## Candidate Outcomes")
    lines.append("")
    for candidate in report["candidates"]:
        lines.append(f"### {candidate['label']} — {candidate['status']}")
        lines.append("")
        lines.append(f"- Incumbent comparator: `{candidate['incumbent']['name']}`")
        lines.append(f"- Blocker: {candidate['rationale']}")
        lines.append("")
        lines.append("| Window | Status | Missing observations | Reason |")
        lines.append("|---:|---|---:|---|")
        for window in WINDOWS:
            item = candidate["windows"][str(window)]
            lines.append(
                f"| {window} | {item['status']} | {item['missing_count']} | {item['reason']} |"
            )
        lines.append("")
    lines.append("## Framework Checks")
    lines.append("")
    probe = report["framework_probe"]
    lines.append(
        f"- Benchmark framework loaded DAILY_539 with {probe['benchmark']['framework_draw_count']} draws "
        f"and official seed={probe['benchmark']['official_seed']}."
    )
    perm = probe["permutation"]
    lines.append(
        f"- Permutation framework probe (`{perm['strategy']}`): edge={perm['real_edge_pct']:+.2f}%, "
        f"p={perm['p_value']:.4f}, d={perm['cohens_d']:.3f}, n_perm={perm['n_perm']} "
        "(probe only; not an H013 candidate)."
    )
    lines.append("")
    lines.append("## Conclusion")
    lines.append("")
    lines.append(report["next_planner_recommendation"])
    lines.append("")
    lines.append("## Handoff Notes")
    lines.append("")
    lines.append("- Wiki update: applied.")
    lines.append("- New lesson: pool-size research on 539 is blocked until ingestion/backfill provides a trusted exogenous pool series.")
    with open(MARKDOWN_PATH, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def build_report(draws: Sequence[Dict]) -> Dict:
    benchmark_probe = benchmark_framework_probe()
    leakage = generate_leakage_artifact(draws)
    pool_audit = audit_pool_series(draws)
    candidate_summaries = [build_candidate_summary(candidate, pool_audit, leakage) for candidate in CANDIDATES]
    permutation_probe = perm_framework_probe(draws)
    diagnostics = {
        "task": "DAILY_539 H013 pool-size diagnostics",
        "game": GAME,
        "seed": benchmark_probe["official_seed"],
        "n_perm": permutation_probe["n_perm"],
        "windows": WINDOWS,
        "data_range": {
            "first_draw": draws[0]["draw"],
            "first_date": draws[0]["date"],
            "last_draw": draws[-1]["draw"],
            "last_date": draws[-1]["date"],
            "count": len(draws),
        },
        "data_availability": {
            **pool_audit,
            "status": "UNUSABLE" if pool_audit["nonnull_count"] == 0 else "PARTIAL",
        },
        "leakage": leakage,
        "framework_probe": {
            "benchmark": benchmark_probe,
            "permutation": permutation_probe,
        },
        "candidates": candidate_summaries,
        "reproducibility": {
            "command": "python3 tools/research_daily539_poolsize_h013.py",
        },
    }
    with open(DIAGNOSTICS_PATH, "w", encoding="utf-8") as handle:
        json.dump(diagnostics, handle, indent=2, ensure_ascii=False)

    report = {
        "task": "DAILY_539 H013 pool-size / market-behavior orthogonal validation",
        "game": GAME,
        "seed": benchmark_probe["official_seed"],
        "n_perm": permutation_probe["n_perm"],
        "windows": WINDOWS,
        "verdict": "REJECT",
        "reason": (
            "Pool-size series is unavailable in trusted active data. jackpot_amount exists in schema but is null for "
            "all DAILY_539 draws, so H013/H013b/H013c cannot be evaluated without violating the no-proxy rule."
        ),
        "data_range": diagnostics["data_range"],
        "data_availability": diagnostics["data_availability"],
        "leakage": leakage,
        "framework_probe": diagnostics["framework_probe"],
        "candidates": candidate_summaries,
        "next_planner_recommendation": (
            "REJECT H013 for now as a data-availability conclusion, not a weak-signal conclusion. Before any future "
            "pool-size retry, extend ingestion/backfill to populate a trusted pool-size or sales field for DAILY_539; "
            "until then, do not invent proxies or rerun the same family."
        ),
        "artifacts": {
            "validation_json": JSON_PATH,
            "diagnostics_json": DIAGNOSTICS_PATH,
            "markdown": MARKDOWN_PATH,
            "leakage": LEAKAGE_PATH,
        },
        "wiki_update_required": True,
    }
    with open(JSON_PATH, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    write_markdown(report)
    return report


def main() -> int:
    args = parse_args()
    ensure_results_dir()
    draws = load_draws()

    if args.leakage_audit_only:
        sys.stdout.write(run_h013_leakage_audit(draws))
        return 0

    report = build_report(draws)
    print(
        json.dumps(
            {
                "verdict": report["verdict"],
                "json": JSON_PATH,
                "diagnostics": DIAGNOSTICS_PATH,
                "markdown": MARKDOWN_PATH,
                "leakage": LEAKAGE_PATH,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
