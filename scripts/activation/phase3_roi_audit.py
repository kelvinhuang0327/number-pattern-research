#!/usr/bin/env python3
"""
PHASE 3 — ROI Audit & Postmortem Review
Reads research/roi_tracking.json, postmortem_reports/, and strategy_insights/latest.json
and prints a comprehensive quality audit report.
PASS gates: sample_size >= 10, postmortem reports >= 5.
"""
import os, sys, json
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pathlib import Path


def _pct(n: float, base: float = 100.0) -> str:
    if base == 0:
        return "N/A"
    return f"{(n / base) * 100:+.2f}%"


def _roi_pct(current: float, initial: float) -> str:
    if initial == 0:
        return "N/A"
    return f"{((current - initial) / initial) * 100:+.2f}%"


def main() -> None:
    print("=" * 60)
    print("PHASE 3 — ROI AUDIT & POSTMORTEM REVIEW")
    print("=" * 60)

    # ── ROI Tracker ──────────────────────────────────────────────
    roi_path = Path("research/roi_tracking.json")
    if not roi_path.exists():
        print("ERROR: research/roi_tracking.json not found")
        sys.exit(1)

    roi = json.loads(roi_path.read_text())
    initial_bankroll = roi.get("initial_bankroll", 100.0)
    current_bankroll = roi.get("current_bankroll", 0.0)
    bankroll_change = roi.get("bankroll_change", 0.0)
    sample_size = roi.get("sample_size", 0)
    max_drawdown = roi.get("max_drawdown_pct", 0.0)
    updated_at = roi.get("updated_at", "unknown")
    curve = roi.get("bankroll_curve", [])

    wins = sum(1 for e in curve if e.get("pnl", 0) > 0)
    losses = sum(1 for e in curve if e.get("pnl", 0) < 0)
    pushes = sum(1 for e in curve if e.get("pnl", 0) == 0)
    win_rate = (wins / len(curve) * 100) if curve else 0.0

    total_profit = sum(e.get("pnl", 0) for e in curve if e.get("pnl", 0) > 0)
    total_loss = sum(abs(e.get("pnl", 0)) for e in curve if e.get("pnl", 0) < 0)

    print(f"\n── BANKROLL METRICS ──────────────────────────────────────")
    print(f"  Initial bankroll    : {initial_bankroll:.4f}")
    print(f"  Current bankroll    : {current_bankroll:.4f}")
    print(f"  Net change          : {bankroll_change:+.4f}  ({_roi_pct(current_bankroll, initial_bankroll)})")
    print(f"  Max drawdown        : {max_drawdown:.2f}%")
    print(f"  Updated at          : {updated_at}")

    print(f"\n── BET RECORD (sample_size={sample_size}) ──────────────────────")
    print(f"  Wins    : {wins}")
    print(f"  Losses  : {losses}")
    print(f"  Pushes  : {pushes}")
    print(f"  Win rate: {win_rate:.1f}%")
    if total_loss > 0:
        print(f"  Profit factor: {total_profit / total_loss:.2f}  (>1.0 = profitable)")
    else:
        print(f"  Profit factor: N/A (no losses)")

    # Daily breakdown
    daily = roi.get("daily", {})
    if daily:
        print(f"\n── DAILY BREAKDOWN ({len(daily)} days) ──────────────────────")
        for day in sorted(daily.keys()):
            d = daily[day]
            pnl = d.get("pnl", 0)
            n = d.get("bets", d.get("count", "?"))
            print(f"  {day}: pnl={pnl:+.4f}  bets={n}")

    # Regime breakdown
    regime = roi.get("regime_breakdown", {})
    if regime:
        print(f"\n── REGIME BREAKDOWN ────────────────────────────────────")
        for regime_name, rd in regime.items():
            pnl = rd.get("pnl", 0)
            n = rd.get("count", rd.get("bets", "?"))
            print(f"  {regime_name}: pnl={pnl:+.4f}  count={n}")

    # ── Postmortem Reports ────────────────────────────────────────
    pm_dir = Path("research/postmortem_reports")
    pm_files = sorted(pm_dir.glob("*.md")) if pm_dir.exists() else []
    print(f"\n── POSTMORTEM REPORTS ({len(pm_files)} files) ───────────────────")
    for f in pm_files[-5:]:  # show latest 5
        print(f"  {f.name}")
        # Print first meaningful line
        lines = f.read_text().splitlines()
        summary_line = next((l for l in lines if l.strip() and not l.startswith("#")), "")
        if summary_line:
            print(f"    → {summary_line[:80]}")

    # ── Strategy Insights ─────────────────────────────────────────
    insights_path = Path("research/strategy_insights/latest.json")
    if insights_path.exists():
        insights = json.loads(insights_path.read_text())
        print(f"\n── STRATEGY INSIGHTS ───────────────────────────────────")
        for key in ("recommendation", "confidence", "regime", "top_insight", "insight"):
            v = insights.get(key)
            if v is not None:
                print(f"  {key}: {str(v)[:100]}")

    # ── PASS GATE ─────────────────────────────────────────────────
    print(f"\n── PASS GATE ───────────────────────────────────────────")
    gate_sample = sample_size >= 10
    gate_pm = len(pm_files) >= 5
    print(f"  sample_size >= 10 : {'✅ PASS' if gate_sample else '❌ FAIL'}  ({sample_size})")
    print(f"  postmortems >= 5  : {'✅ PASS' if gate_pm else '❌ FAIL'}  ({len(pm_files)})")
    overall = gate_sample and gate_pm
    print(f"\n  OVERALL: {'✅ PASS' if overall else '❌ FAIL'}")
    print("=" * 60)
    return overall


if __name__ == "__main__":
    passed = main()
    sys.exit(0 if passed else 1)
