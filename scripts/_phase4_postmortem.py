#!/usr/bin/env python3
"""
PHASE 4 — Postmortem & Insight Verification
Triggers the tail-end of the feedback loop.
"""
import os, sys, json
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 55)
print("PHASE 4 — POSTMORTEM & INSIGHT")
print("=" * 55)

from pathlib import Path
from research.roi_tracker import ROITracker
from research.trade_journal import TradeJournal
from research.postmortem_engine import PostmortemEngine
from research.trigger_engine import TriggerEngine

roi_tracker = ROITracker()
journal     = TradeJournal()
postmortem  = PostmortemEngine()
trigger_eng = TriggerEngine()

print("\n── Step 4.1: Rebuild ROI ──")
try:
    roi_summary = roi_tracker.rebuild()
    print(f"  roi_summary keys: {list(roi_summary.keys())}")
    # The ROI tracker uses bankroll-style keys
    print(f"  current_bankroll: {roi_summary.get('current_bankroll', 'n/a')}")
    print(f"  bankroll_change:  {roi_summary.get('bankroll_change', 'n/a')}")
    print(f"  sample_size:      {roi_summary.get('sample_size', 'n/a')}")
    print(f"  max_drawdown_pct: {roi_summary.get('max_drawdown_pct', 'n/a')}")
    # daily shows per-date P&L
    daily = roi_summary.get('daily', {})
    print(f"  daily entries:    {list(daily.keys()) if daily else 'none'}")
except Exception as exc:
    print(f"  ❌ ROI rebuild error: {exc}")
    roi_summary = {}

print("\n── Step 4.2: Load journal ──")
try:
    rows = journal.load()
    print(f"  Journal rows: {len(rows)}")
except Exception as exc:
    print(f"  ❌ journal.load() error: {exc}")
    rows = []

print("\n── Step 4.3: Evaluate triggers ──")
try:
    triggers = trigger_eng.evaluate(roi_summary)
    print(f"  Triggers: {triggers}")
except Exception as exc:
    print(f"  ❌ trigger_eng.evaluate() error: {exc}")
    triggers = []

print("\n── Step 4.4: Generate postmortem ──")
generated = []
try:
    if triggers:
        for t in triggers:
            path = postmortem.generate(roi_summary, rows, t)
            print(f"  ✅ Postmortem generated (trigger={t.get('trigger_type', t)}): {path}")
            generated.append(path)
    else:
        print("  No new triggers (already fired in Phase 3) — skipping forced postmortem")
except Exception as exc:
    print(f"  ❌ postmortem.generate() error: {exc}")
    import traceback; traceback.print_exc()

print("\n── Step 4.5: Verify artifact directories ──")
pm_dir = Path("research/postmortem_reports")
ins_dir = Path("research/strategy_insights")

if pm_dir.exists():
    files = list(pm_dir.iterdir())  # reports can be .md or .json
    print(f"  postmortem_reports: {len(files)} files")
    for f in files[:5]:
        print(f"    - {f.name}")
else:
    print("  ❌ postmortem_reports: MISSING")

if ins_dir.exists():
    files = list(ins_dir.iterdir())
    print(f"  strategy_insights:  {len(files)} files")
    latest = ins_dir / "latest.json"
    print(f"    latest.json: {'EXISTS' if latest.exists() else 'MISSING'}")
else:
    print("  ❌ strategy_insights: MISSING")
