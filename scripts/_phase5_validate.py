#!/usr/bin/env python3
"""
PHASE 5 — Final Validation & Activation Log
"""
import os, sys, json, datetime
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 55)
print("PHASE 5 — FINAL VALIDATION")
print("=" * 55)

from pathlib import Path

checks = {
    "prediction_registry (66 records)": Path("data/wbc_backend/reports/prediction_registry.jsonl"),
    "trade_ledger":         Path("research/trade_ledger.jsonl"),
    "roi_tracking":         Path("research/roi_tracking.json"),
    "daily_run_registry":   Path("research/daily_run_registry.jsonl"),
    "pending_settlements":  Path("research/pending_settlements.json"),
}

results = {}
for name, p in checks.items():
    if p.exists():
        size = p.stat().st_size
        # Count records if JSONL
        if p.suffix == ".jsonl":
            count = sum(1 for l in p.read_text().splitlines() if l.strip())
            results[name] = f"✅ OK ({count} records, {size} bytes)"
        else:
            results[name] = f"✅ OK ({size} bytes)"
    else:
        results[name] = "❌ FAIL (missing)"
    print(f"  {name}: {results[name]}")

pm_dir = Path("research/postmortem_reports")
pm_count = len(list(pm_dir.iterdir())) if pm_dir.exists() else 0  # .md reports
pm_status = f"✅ OK ({pm_count} files)" if pm_count > 0 else "❌ FAIL (0 files)"
print(f"  postmortem_reports: {pm_status}")

ins_latest = Path("research/strategy_insights/latest.json")
ins_status = "✅ OK" if ins_latest.exists() else "⚠️ MISSING"
print(f"  strategy_insights/latest.json: {ins_status}")

# Determine verdict
all_critical_ok = all("OK" in v for v in results.values())
has_postmortem   = pm_count > 0

if all_critical_ok and has_postmortem:
    status = "SUCCESS"
    reason = "Full loop achieved: prediction → trade_ledger → roi_tracking → postmortem"
elif all_critical_ok:
    status = "PARTIAL_SUCCESS"
    reason = "Core loop achieved but postmortem not generated"
elif results.get("trade_ledger", "").startswith("✅") and results.get("roi_tracking", "").startswith("✅"):
    status = "PARTIAL_SUCCESS"
    reason = "Trade ledger + ROI tracking active; some artifacts missing"
else:
    status = "FAILED"
    reason = "trade_ledger or roi_tracking missing — RESEARCH_MODE capture not triggered"

print(f"\n{'=' * 55}")
print(f"FINAL STATUS: {status}")
print(f"Reason: {reason}")
print(f"{'=' * 55}")

# Write activation log
log_entry = {
    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    "phase": "ACTIVATION_v2",
    "checks": results,
    "postmortem_count": pm_count,
    "strategy_insight_exists": ins_latest.exists(),
    "status": status.lower(),
    "reason": reason,
}
log_path = Path("logs/activation_loop_log.jsonl")
log_path.parent.mkdir(exist_ok=True)
with open(log_path, "a", encoding="utf-8") as f:
    f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
print(f"\nActivation log written: {log_path}")
