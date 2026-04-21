#!/usr/bin/env python3
"""
Weekly Health Report
====================
週期性系統狀態健檢報告，涵蓋三彩種維護模式狀態、PSI 分佈、
combo_B 追蹤進度、exit trigger 評估，以及觸發器 mock 測試。

用法:
  python3 tools/weekly_health_report.py
  python3 tools/weekly_health_report.py --run-trigger-tests

輸出:
  stdout: 人類可讀摘要
  data/weekly_health_YYYYMMDD.json: 完整 JSON 報告

2026-04-19 Created
"""
from __future__ import annotations

import json
import os
import glob
import sys
import argparse
from datetime import datetime
from typing import Any, Dict, List, Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data")
TRIGGER_FILE = "maintenance_exit_triggers.json"

if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

LOTTERIES = ["BIG_LOTTO", "DAILY_539", "POWER_LOTTO"]
BASELINES = {
    "POWER_LOTTO": {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 5: 0.1791},
    "BIG_LOTTO": {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0896},
    "DAILY_539": {1: 0.1140, 2: 0.2154, 3: 0.3050, 4: 0.3843, 5: 0.4539},
}
METRIC_KEY = {"POWER_LOTTO": "is_m3plus", "BIG_LOTTO": "is_m3plus", "DAILY_539": "is_m2plus"}

# ANSI colours
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _status_color(status: str) -> str:
    return {
        "GREEN": GREEN, "OK": GREEN,
        "YELLOW": YELLOW, "WARNING": YELLOW,
        "RED": RED, "CRITICAL": RED,
    }.get(status.upper(), RESET)


def _parse_num_bets(name: str) -> int:
    import re
    m = re.search(r"(\d+)bet", name)
    return int(m.group(1)) if m else 1


def read_strategy_state(lt: str) -> Dict[str, Any]:
    """Read edge data from strategy_states_{lt}.json (or fallback from rolling_monitor)."""
    state_path = os.path.join(DATA_DIR, f"strategy_states_{lt}.json")
    states = _load_json(state_path)
    if states:
        best_name = max(states, key=lambda k: states[k].get("edge_1500p", states[k].get("edge_300p", 0)))
        best = states[best_name]
        return {
            "best_strategy": best_name,
            "edge_1500p": best.get("edge_1500p", None),
            "edge_300p": best.get("edge_300p", None),
            "edge_150p": best.get("edge_150p", None),
            "status": best.get("status", "UNKNOWN"),
        }

    # Fallback: compute edges from rolling_monitor
    monitor_path = os.path.join(DATA_DIR, f"rolling_monitor_{lt}.json")
    monitor = _load_json(monitor_path)
    if not monitor:
        return {"best_strategy": "N/A", "edge_1500p": None, "edge_300p": None, "edge_150p": None, "status": "NO_DATA"}

    records = monitor.get("records", {})
    metric = METRIC_KEY[lt]
    best_name = ""
    best_edge = -999.0
    best_hits: List[int] = []
    best_baseline = BASELINES[lt][1]

    for name, recs in records.items():
        if not recs:
            continue
        nb = _parse_num_bets(name)
        bl = BASELINES[lt].get(nb, BASELINES[lt][1])
        hits = [1 if r.get(metric, False) else 0 for r in recs]
        edge = sum(hits) / max(len(hits), 1) - bl
        if edge > best_edge:
            best_edge = edge
            best_name = name
            best_hits = hits
            best_baseline = bl

    n = len(best_hits)
    e1500 = (sum(best_hits[-1500:]) / min(n, 1500) - best_baseline) if n >= 100 else None
    e300 = (sum(best_hits[-300:]) / min(n, 300) - best_baseline) if n >= 50 else None
    e150 = (sum(best_hits[-150:]) / min(n, 150) - best_baseline) if n >= 50 else None

    return {
        "best_strategy": best_name,
        "edge_1500p": round(e1500, 4) if e1500 is not None else None,
        "edge_300p": round(e300, 4) if e300 is not None else None,
        "edge_150p": round(e150, 4) if e150 is not None else None,
        "status": "OK",
    }


def read_latest_psi(lt: str) -> float:
    """Read latest PSI value from rolling_monitor or drift_detector."""
    try:
        sys.path.insert(0, ROOT)
        from lottery_api.engine.drift_detector import check_drift
        report = check_drift(lt)
        psi = report.metrics.get("number_freq_PSI", {})
        return round(float(psi.get("value", 0)), 6)
    except Exception:
        pass

    # Fallback from maintenance triggers
    triggers = _load_json(os.path.join(DATA_DIR, TRIGGER_FILE))
    if triggers and lt in triggers:
        return triggers[lt].get("psi_distribution", {}).get("latest", 0.0)
    return 0.0


def read_combo_b_milestone() -> Dict[str, Any]:
    path = os.path.join(DATA_DIR, "combo_b_milestone.json")
    ms = _load_json(path)
    if not ms:
        return {"status": "NO_FILE"}

    tracking_path = os.path.join(DATA_DIR, "combo_b_tracking_POWER_LOTTO.jsonl")
    tracked_count = 0
    if os.path.exists(tracking_path):
        with open(tracking_path) as f:
            tracked_count = sum(1 for line in f if line.strip())

    return {
        "status": ms.get("status"),
        "started_draw": ms.get("started_draw"),
        "evaluate_at_draw": ms.get("evaluate_at_draw"),
        "tracked_draws": tracked_count,
        "draws_remaining": max(0, int(ms.get("evaluate_at_draw", 0)) - int(ms.get("started_draw", 0)) - tracked_count),
        "retest_condition": ms.get("retest_condition"),
    }


def read_bankroll_advice() -> Dict[str, Any]:
    patterns = sorted(glob.glob(os.path.join(DATA_DIR, "betting_strategy_guide_*.json")))
    if not patterns:
        return {}
    path = patterns[-1]
    guide = _load_json(path) or {}
    summary = guide.get("summary", {})
    return {
        "source_file": os.path.basename(path),
        "best_priority": summary.get("best_priority"),
        "recommended_monthly_budget": summary.get("recommended_monthly_budget"),
        "starting_bankroll_assumption": summary.get("starting_bankroll_assumption"),
        "kelly_consistency": summary.get("kelly_consistency"),
        "ev_gate_open_lotteries": summary.get("ev_gate_open_lotteries", []),
        "ev_gate_closed_lotteries": summary.get("ev_gate_closed_lotteries", []),
        "monthly_budget_ev_gate": summary.get("monthly_budget_ev_gate"),
        "monthly_budget_kelly_ev": summary.get("monthly_budget_kelly_ev"),
        "monthly_savings_ev_gate": summary.get("monthly_savings_ev_gate"),
        "monthly_savings_kelly_ev": summary.get("monthly_savings_kelly_ev"),
        "ranking": guide.get("ranking", []),
    }


def read_ev_gate_snapshot() -> Dict[str, Any]:
    try:
        from tools.ev_gate import build_gate_snapshot

        return build_gate_snapshot()
    except Exception:
        return {}


def read_milestones() -> List[Dict[str, Any]]:
    try:
        from tools.milestone_monitor import check_milestones

        return check_milestones()
    except Exception:
        return []


def _read_trigger_data(lt: str) -> Dict[str, Any]:
    triggers = _load_json(os.path.join(DATA_DIR, TRIGGER_FILE))
    if not triggers or lt not in triggers:
        return {}
    return triggers[lt]


def _resolve_trigger_status(
    td: Dict[str, Any],
    psi_val: float,
    edge150: float,
    sustained_psi: bool,
    force_psi_valid: bool,
) -> Dict[str, Any]:
    psi_dist = td.get("psi_distribution", {})
    p75 = psi_dist.get("p75", 0.1)
    p90 = psi_dist.get("p90", 0.15)
    psi_valid = force_psi_valid or td.get("psi_is_valid_trigger", False)
    level1 = bool(psi_valid and psi_val > p75 and edge150 < 0)
    level2_mc = td.get("level2_conditions", {}).get("mcnemar_recent300", {}).get("reversal", False)
    level3_b = td.get("level3_conditions", {}).get("below_half_baseline", False)
    level2 = bool((psi_valid and psi_val > p90) or level2_mc)
    level3 = bool(sustained_psi or level3_b)
    current = "GREEN"
    if level3:
        current = "RED"
    elif level1 or level2:
        current = "YELLOW"

    return {
        "psi_p75": round(p75, 6),
        "psi_p90": round(p90, 6),
        "psi_is_valid_trigger": psi_valid,
        "level1_triggered": level1,
        "level2_triggered": level2,
        "level3_triggered": level3,
        "current_status": current,
    }


def evaluate_exit_triggers(
    lt: str,
    override_psi: Optional[float] = None,
    override_edge150: Optional[float] = None,
    consecutive_psi: Optional[List[float]] = None,
    force_psi_valid: bool = False,
) -> Dict[str, Any]:
    """
    Evaluate exit trigger conditions for a given lottery.
    Can be called with real data or mock overrides for testing.
    """
    td = _read_trigger_data(lt)
    if not td:
        return {"error": f"No trigger data for {lt}"}

    # Use live PSI or override
    psi_val = override_psi if override_psi is not None else td.get("psi_distribution", {}).get("latest", 0.0)

    # Edge 150p (real or override)
    if override_edge150 is not None:
        edge150 = override_edge150
    else:
        l1 = td.get("level1_conditions", {})
        edge150 = l1.get("recent_150p_edge", 0.0)

    # Consecutive PSI for Level 3
    if consecutive_psi is not None:
        sustained_psi = len(consecutive_psi) >= 3 and all(v > 0.2 for v in consecutive_psi[-3:])
    else:
        # Use sustained check from existing triggers
        sustained_psi = td.get("level3_conditions", {}).get("psi_gt_0_2_3x", False)

    result = _resolve_trigger_status(td, psi_val, edge150, sustained_psi, force_psi_valid)
    result.update({
        "lottery": lt,
        "psi_val": round(psi_val, 6),
        "edge_150p": round(edge150, 6),
    })
    return result


def run_trigger_mock_tests() -> Dict[str, Any]:
    """Mock test suite for exit trigger logic."""
    test_cases = []

    # Use BIG_LOTTO as the test subject since it has p75/p90 values
    triggers = _load_json(os.path.join(DATA_DIR, TRIGGER_FILE))
    lt = "BIG_LOTTO"
    psi_dist = triggers.get(lt, {}).get("psi_distribution", {})
    p75 = psi_dist.get("p75", 0.10)
    p90 = psi_dist.get("p90", 0.15)

    # test_case_1: PSI > P75, edge < 0 → Level 1 should trigger
    tc1_psi = p75 * 1.5
    result1 = evaluate_exit_triggers(lt, override_psi=tc1_psi, override_edge150=-0.02, force_psi_valid=True)
    expected1 = {"level1_triggered": True, "level2_triggered": False, "level3_triggered": False}
    pass1 = result1["level1_triggered"] == expected1["level1_triggered"]
    test_cases.append({
        "case": 1,
        "description": f"PSI={tc1_psi:.3f} (>P75={p75:.3f}), edge_150p=-2%",
        "input": {"psi": tc1_psi, "edge_150p": -0.02},
        "expected": expected1,
        "actual": {
            "level1_triggered": result1["level1_triggered"],
            "level2_triggered": result1["level2_triggered"],
            "level3_triggered": result1["level3_triggered"],
        },
        "pass": pass1,
    })

    # test_case_2: PSI > P90, consecutive PSI > 0.2 x3 → Level 2 + Level 3 should trigger
    tc2_psi = max(p90 * 1.5, 0.35)
    result2 = evaluate_exit_triggers(
        lt, override_psi=tc2_psi, override_edge150=-0.03,
        consecutive_psi=[0.25, 0.28, 0.35], force_psi_valid=True
    )
    expected2 = {"level2_triggered": True, "level3_triggered": True}
    pass2 = result2["level2_triggered"] == expected2["level2_triggered"] and \
            result2["level3_triggered"] == expected2["level3_triggered"]
    test_cases.append({
        "case": 2,
        "description": f"PSI={tc2_psi:.3f} (>P90={p90:.3f}), consecutive_psi=[0.25, 0.28, 0.35]",
        "input": {"psi": tc2_psi, "edge_150p": -0.03, "consecutive_psi": [0.25, 0.28, 0.35]},
        "expected": expected2,
        "actual": {
            "level2_triggered": result2["level2_triggered"],
            "level3_triggered": result2["level3_triggered"],
        },
        "pass": pass2,
    })

    # test_case_3: PSI = 0.05, edge = +3% → all GREEN (no forced psi_valid needed)
    result3 = evaluate_exit_triggers(lt, override_psi=0.05, override_edge150=0.03,
                                     consecutive_psi=[0.05, 0.04, 0.06], force_psi_valid=False)
    expected3 = {"level1_triggered": False, "level2_triggered": False, "level3_triggered": False}
    pass3 = (
        result3["level1_triggered"] == expected3["level1_triggered"]
        and result3["level2_triggered"] == expected3["level2_triggered"]
        and result3["level3_triggered"] == expected3["level3_triggered"]
    )
    test_cases.append({
        "case": 3,
        "description": "PSI=0.05, edge_150p=+3% (normal/GREEN)",
        "input": {"psi": 0.05, "edge_150p": 0.03},
        "expected": expected3,
        "actual": {
            "level1_triggered": result3["level1_triggered"],
            "level2_triggered": result3["level2_triggered"],
            "level3_triggered": result3["level3_triggered"],
        },
        "pass": pass3,
    })

    all_pass = all(tc["pass"] for tc in test_cases)
    return {"test_cases": test_cases, "all_pass": all_pass}


def generate_report(run_trigger_tests: bool = False) -> Dict[str, Any]:
    today = datetime.now().strftime("%Y-%m-%d")
    report: Dict[str, Any] = {
        "generated_at": datetime.now().isoformat(),
        "report_date": today,
        "by_lottery": {},
        "combo_b_milestone": {},
        "exit_triggers": {},
        "trigger_test_results": None,
        "system_status": "GREEN",
        "actions_required": [],
    }

    triggers = _load_json(os.path.join(DATA_DIR, TRIGGER_FILE)) or {}
    stage2 = _load_json(os.path.join(DATA_DIR, "stage2_recalibration.json")) or {}
    combo_ms = read_combo_b_milestone()
    report["combo_b_milestone"] = combo_ms
    report["bankroll_advice"] = read_bankroll_advice()
    report["ev_gate"] = read_ev_gate_snapshot()
    report["milestones"] = read_milestones()
    perf_30p = (_load_json(os.path.join(DATA_DIR, "recent_30p_performance.json")) or {}).get("by_lottery", {})

    statuses = []

    for lt in LOTTERIES:
        psi = read_latest_psi(lt)
        strat = read_strategy_state(lt)
        trigger_status = triggers.get(lt, {}).get("current_status", "GREEN")
        s2_data = stage2.get("by_lottery", {}).get(lt, {})
        optimal_threshold = s2_data.get("optimal_threshold", 0.0)
        recommendation = s2_data.get("recommendation", "N/A")
        best_strategy = triggers.get(lt, {}).get("best_strategy", strat.get("best_strategy", "N/A"))
        full_edge = triggers.get(lt, {}).get("best_strategy_edge_full", strat.get("edge_1500p", None))

        edge_150 = strat.get("edge_150p")
        p30 = perf_30p.get(lt, {})
        edge_30p = p30.get("edge_30p")
        status_30p = p30.get("status", "N/A")
        report["by_lottery"][lt] = {
            "mode": "MAINTENANCE",
            "best_strategy": best_strategy,
            "edge_full": round(full_edge, 4) if full_edge is not None else None,
            "edge_150p": edge_150,
            "edge_30p": edge_30p,
            "status_30p": status_30p,
            "psi_latest": psi,
            "psi_status": triggers.get(lt, {}).get("level1_conditions", {}).get("psi_gt_p75", False),
            "stage2_skip_threshold": optimal_threshold,
            "stage2_recommendation": recommendation,
            "exit_trigger_status": trigger_status,
        }

        if lt == "POWER_LOTTO":
            report["by_lottery"][lt]["combo_b"] = {
                "status": combo_ms.get("status"),
                "tracked_draws": combo_ms.get("tracked_draws"),
                "evaluate_at": combo_ms.get("evaluate_at_draw"),
            }

        statuses.append(trigger_status)
        report["exit_triggers"][lt] = evaluate_exit_triggers(lt)

        if trigger_status == "RED" or (psi > 0.2 and edge_150 is not None and edge_150 < 0):
            report["actions_required"].append(f"{lt}: status={trigger_status}, PSI={psi:.4f}")

    # Overall
    if any(s == "RED" for s in statuses):
        report["system_status"] = "RED"
    elif any(s == "YELLOW" for s in statuses):
        report["system_status"] = "YELLOW"

    # Trigger mock tests
    if run_trigger_tests:
        report["trigger_test_results"] = run_trigger_mock_tests()

    return report


def print_report(report: Dict[str, Any]) -> None:
    print(f"\n{BOLD}=== LOTTERY SYSTEM HEALTH REPORT ==={RESET}")
    print(f"Generated: {report['report_date']}")

    for lt in LOTTERIES:
        _print_lottery_section(lt, report["by_lottery"][lt])

    sys_status = report["system_status"]
    sc = _status_color(sys_status)
    print(f"\n{BOLD}[SYSTEM STATUS]{RESET} {sc}{sys_status}{RESET}")

    actions = report["actions_required"]
    if actions:
        print(f"{BOLD}[ACTION REQUIRED]{RESET}")
        for a in actions:
            print(f"  ⚠ {a}")
    else:
        print(f"{BOLD}[ACTION REQUIRED]{RESET} None")

    bankroll = report.get("bankroll_advice", {})
    if bankroll:
        print(f"\n{BOLD}[BANKROLL ADVICE]{RESET}")
        print(
            f"  priority={bankroll.get('best_priority')}  monthly_budget={bankroll.get('recommended_monthly_budget')}  "
            f"kelly_consistent={bankroll.get('kelly_consistency')}"
        )
        print(
            f"  ev_gate_open={bankroll.get('ev_gate_open_lotteries')}  "
            f"ev_gate_closed={bankroll.get('ev_gate_closed_lotteries')}"
        )
        print(
            f"  monthly_spend_ev_gate={bankroll.get('monthly_budget_ev_gate')}  "
            f"monthly_savings_ev_gate={bankroll.get('monthly_savings_ev_gate')}"
        )
        print(
            f"  monthly_spend_kelly_ev={bankroll.get('monthly_budget_kelly_ev')}  "
            f"monthly_savings_kelly_ev={bankroll.get('monthly_savings_kelly_ev')}"
        )

    ev_gate = report.get("ev_gate", {})
    if ev_gate:
        print(f"\n{BOLD}[EV GATE]{RESET}")
        for lt in LOTTERIES:
            gate = ev_gate.get(lt, {})
            jackpot = gate.get("current_jackpot")
            breakeven = gate.get("breakeven_jackpot")
            status = "OPEN" if gate.get("ev_gate_open") else "CLOSE"
            hit_rate = gate.get("stage2_gate", {}).get("rolling_50p_hit_rate")
            hit_text = f"{hit_rate:.3f}" if hit_rate is not None else "N/A"
            jackpot_text = f"{jackpot:,.0f}" if jackpot is not None else "N/A"
            breakeven_text = f"{breakeven:,.0f}" if breakeven is not None else "N/A"
            print(
                f"  {lt}: {status} current={jackpot_text} breakeven={breakeven_text} "
                f"recommended_bets={gate.get('recommended_bet_count')} stage2_50p={hit_text}"
            )

    milestones = report.get("milestones", [])
    if milestones:
        print(f"\n{BOLD}[MILESTONES]{RESET}")
        for milestone in milestones:
            name = milestone.get("name", "milestone")
            lottery_type = milestone.get("lottery_type", "N/A")
            status = milestone.get("status", "TRACKING")
            current_draw = milestone.get("current_draw")
            evaluate_at = milestone.get("evaluate_at_draw")
            draws_remaining = milestone.get("draws_remaining")
            weeks_remaining = milestone.get("weeks_remaining")
            started_draw = milestone.get("started_draw")
            print(
                f"  {name} ({lottery_type}): {status} current={current_draw} "
                f"evaluate_at={evaluate_at} started={started_draw} remaining={draws_remaining} "
                f"~{weeks_remaining} weeks"
            )

    _print_trigger_tests(report.get("trigger_test_results"))


def _print_lottery_section(lt: str, d: Dict[str, Any]) -> None:
    ts = d["exit_trigger_status"]
    c = _status_color(ts)
    print(f"\n{BOLD}[{lt}]{RESET} 維護模式")
    e_full = f"{d['edge_full']:+.2%}" if d["edge_full"] is not None else "N/A"
    e150 = f"{d['edge_150p']:+.2%}" if d["edge_150p"] is not None else "N/A"
    e30 = f"{d['edge_30p']:+.1%}" if d.get("edge_30p") is not None else "N/A"
    s30 = d.get("status_30p", "N/A")
    s30_color = {"NORMAL": GREEN, "WATCH": YELLOW, "ALERT": RED}.get(s30, RESET)
    print(f"  最佳策略: {d['best_strategy']}  1500p={e_full}  150p={e150}  30p={e30} → {s30_color}{s30}{RESET}")
    print(f"  PSI={d['psi_latest']:.4f}  exit_trigger={c}{ts}{RESET}")

    th = d["stage2_skip_threshold"]
    rec = d["stage2_recommendation"]
    print(f"  Stage2 skip_threshold: {th:.1%}  ({rec})")
    print(f"  Exit trigger: {c}{ts}{RESET}")

    if lt == "POWER_LOTTO" and "combo_b" in d:
        cb = d["combo_b"]
        print(f"  combo_B: {cb['status']}  已追蹤 {cb['tracked_draws']} 期  evaluate_at={cb['evaluate_at']}")


def _print_trigger_tests(ttr: Optional[Dict[str, Any]]) -> None:
    if not ttr:
        return

    ap = ttr["all_pass"]
    c = GREEN if ap else RED
    print(f"\n{BOLD}[TRIGGER TESTS]{RESET} {c}{'ALL PASS' if ap else 'SOME FAILED'}{RESET}")
    for tc in ttr["test_cases"]:
        p = tc["pass"]
        pc = GREEN if p else RED
        print(f"  Case {tc['case']}: {pc}{'PASS' if p else 'FAIL'}{RESET}  {tc['description']}")


def main():
    parser = argparse.ArgumentParser(description="Weekly Health Report")
    parser.add_argument("--run-trigger-tests", action="store_true", help="Run mock trigger validation tests")
    parser.add_argument("--json-only", action="store_true", help="只輸出 JSON，不印 stdout")
    args = parser.parse_args()

    report = generate_report(run_trigger_tests=args.run_trigger_tests)

    if not args.json_only:
        print_report(report)

    today = datetime.now().strftime("%Y%m%d")
    out_path = os.path.join(DATA_DIR, f"weekly_health_{today}.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nReport written → {out_path}")


if __name__ == "__main__":
    main()
