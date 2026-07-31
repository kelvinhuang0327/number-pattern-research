#!/usr/bin/env python3
"""PHASE 0 pre-flight audit — read-only checks."""
import json, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

print("=" * 55)
print("PHASE 0 — PRE-FLIGHT AUDIT")
print("=" * 55)

# 0.2 Research paths
print("\n── 0.2 Research paths ──")
from research.config import research_paths
for k, v in research_paths().items():
    status = "OK     " if Path(v).exists() else "MISSING"
    print(f"  {status} | {k}")

# 0.3 Last prediction_registry record
print("\n── 0.3 prediction_registry (last record) ──")
reg = Path("data/wbc_backend/reports/prediction_registry.jsonl")
if reg.exists():
    lines = [json.loads(l) for l in reg.read_text().splitlines() if l.strip()]
    print(f"  Total records: {len(lines)}")
    last = lines[-1]
    pred = last.get("prediction", {})
    verif = last.get("verification", {})
    print(f"  game_id:              {last.get('game_id')}")
    print(f"  prediction.home_win_prob: {pred.get('home_win_prob')}")
    print(f"  verification.status:      {verif.get('status')}")
    print(f"  prediction keys: {list(pred.keys())}")
else:
    print("  MISSING — prediction_registry.jsonl not found")

# Orchestrator capture check
print("\n── 0.4 Orchestrator capture call (static) ──")
try:
    import inspect
    from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator
    src = inspect.getsource(PredictionOrchestrator.predict)
    found = []
    for i, line in enumerate(src.splitlines()):
        if "research" in line.lower() and "capture" in line.lower():
            found.append(f"  Line {i}: {line.rstrip()}")
    if found:
        for f in found:
            print(f)
    else:
        print("  WARNING: no 'research.*capture' call found in predict()")
except Exception as exc:
    print(f"  ERROR importing Orchestrator: {exc}")

# RESEARCH_MODE env check
print("\n── 0.5 RESEARCH_MODE env ──")
from research.config import is_research_mode_enabled
print(f"  RESEARCH_MODE env value: {os.getenv('RESEARCH_MODE', '(unset)')}")
print(f"  is_research_mode_enabled(): {is_research_mode_enabled()}")

print("\n── 0.6 run_mode.py existence ──")
rmp = Path("scripts/run_mode.py")
print(f"  scripts/run_mode.py: {'EXISTS' if rmp.exists() else 'MISSING'}")
if rmp.exists():
    head = rmp.read_text()[:500]
    if "--mode" in head:
        print("  Has --mode argument: YES")
