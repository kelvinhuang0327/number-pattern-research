#!/usr/bin/env python3
"""
PHASE 3 — Settlement Injection
Injects the verified C09 (KOR 7 - AUS 2) result into the research layer.
"""
import os, sys, json
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 55)
print("PHASE 3 — SETTLEMENT INJECTION")
print("=" * 55)

import tempfile
from pathlib import Path

# C09: KOR 7 - AUS 2 → away_win
settlement = [
    {
        "game_id": "C09",
        "result": "away_win",
        "final_score": "2-7",           # home-away format
        "settlement_time": "2026-03-09T15:00:00Z",
        "raw": {
            "away_team": "KOR",
            "home_team": "AUS",
            "away_score": 7,
            "home_score": 2,
        },
    }
]

# Write to temp file and ingest
with tempfile.NamedTemporaryFile(
    mode="w", suffix=".json", delete=False, encoding="utf-8"
) as tf:
    json.dump(settlement, tf, ensure_ascii=False)
    tmp_path = tf.name

print(f"\n── Injecting settlement for C09 ──")
print(f"  game_id: C09 | result: away_win (KOR 7, AUS 2)")

try:
    from research.settlement_ingestion import ingest_settlements
    summary = ingest_settlements(tmp_path)
    print(f"\n  Settlement summary:")
    print(json.dumps(summary, indent=4, ensure_ascii=False, default=str))
except Exception as exc:
    print(f"  ❌ ingest_settlements error: {exc}")
    import traceback; traceback.print_exc()
finally:
    try:
        Path(tmp_path).unlink(missing_ok=True)
    except Exception:
        pass

# Verify outputs
print("\n── Verifying settlement artifacts ──")
ledger = Path("research/trade_ledger.jsonl")
if ledger.exists():
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    preds    = [r for r in rows if r.get("event_type") == "prediction"]
    settles  = [r for r in rows if r.get("event_type") == "settlement"]
    print(f"  trade_ledger: {len(preds)} predictions, {len(settles)} settlements")
    if settles:
        s = settles[-1]
        print(f"    last settlement: game_id={s.get('game_id')}, result={s.get('result')}, pnl={s.get('pnl')}")
else:
    print("  ❌ trade_ledger.jsonl still missing — run Phase 2 first")

roi = Path("research/roi_tracking.json")
if roi.exists():
    data = json.loads(roi.read_text())
    print(f"\n  roi_tracking.json:")
    print(f"    total_pnl:     {data.get('total_pnl', 'n/a')}")
    print(f"    roi:           {data.get('roi', 'n/a')}")
    print(f"    total_samples: {data.get('total_samples', 'n/a')}")
    print(f"    total_staked:  {data.get('total_staked', 'n/a')}")
else:
    print("  ❌ roi_tracking.json still missing")
