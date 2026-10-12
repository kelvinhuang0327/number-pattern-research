"""
Phase 0 Step 0.5 — Compare settlement results vs authoritative snapshot scores.
Checks if home_win correctly reflects actual game outcomes.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.activation.wbc_pool_results import build_settlement_records

# What our settlement pipeline generated
records = build_settlement_records()

# What the trade ledger settled
rows = [json.loads(l) for l in open('research/trade_ledger.jsonl') if l.strip()]
ledger_preds = {r["game_id"]: r for r in rows if r.get("event_type") == "prediction"}
ledger_setts = {r["game_id"]: r for r in rows if r.get("event_type") == "settlement"}

print("=" * 80)
print("SETTLEMENT CORRECTNESS CHECK: snap result vs bet result")
print(f"{'GID':5} {'home':5} {'away':5} {'score':12} {'snap_hw':8} {'rec_side':9} {'is_win':8} {'sett_res':10}")
print("-" * 80)

# Track correctness
correct_count = 0
incorrect_count = 0

for gid in sorted(records.keys()):
    r = records[gid]
    home_win = r["home_win"]  # 1 if snap home team won
    home_code = r["home_code"]
    away_code = r["away_code"]
    score = r["result_desc"]
    
    pred = ledger_preds.get(gid, {})
    sett = ledger_setts.get(gid)
    if sett is None:
        print(f"{gid:5} {home_code:5} {away_code:5} {score:12} hw={home_win}  (no settlement)")
        continue
    
    rec_side = (pred.get("metadata") or {}).get("recommended_side", "?")
    sett_result = sett.get("result", "?")
    
    # Expected: if rec_side=home and home_win=1 → win; if rec_side=away and home_win=0 → win
    expected_win = (rec_side == "home" and home_win == 1) or (rec_side == "away" and home_win == 0)
    actual_win = sett_result == "win"
    
    matches = "✅" if (expected_win == actual_win) else "❌ MISMATCH"
    if expected_win == actual_win:
        correct_count += 1
    else:
        incorrect_count += 1
    
    print(f"{gid:5} {home_code:5} {away_code:5} {score:20} hw={home_win}  {rec_side:9} exp={'win' if expected_win else 'loss'} got={sett_result:5} {matches}")

print("=" * 80)
print(f"Correct: {correct_count}, Incorrect: {incorrect_count}")
print()

# Now run the Orchestrator for B06 fresh to confirm rec_side
print("\n--- RE-RUN B06 PREDICTION ---")
os.environ["RESEARCH_MODE"] = "1"
from data.wbc_pool_b import fetch_wbc_match_b
from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator

md = fetch_wbc_match_b("B06")
orc = PredictionOrchestrator()
result = orc.predict(md, use_world_model=False)
print(f"home_win_prob:       {result.home_win_prob:.4f}")
print(f"recommended_side:    {result.recommended_side}")
print(f"recommended_kelly:   {result.recommended_kelly_fraction}")
print(f"edge_vs_market:      {getattr(result, 'edge_vs_market', 'N/A')}")
print(f"execution_mode:      {result.execution_mode}")
print(f"home team:           {getattr(md.home, 'name', '?')} (ELO={getattr(md.home, 'elo', '?')})")
print(f"away team:           {getattr(md.away, 'name', '?')} (ELO={getattr(md.away, 'elo', '?')})")
print(f"Actual result:       MEX 16-0 BRA (home=MEX won)")
print(f"Our bet:             {result.recommended_side} team ({getattr(md.away if result.recommended_side=='away' else md.home, 'name', '?')})")
print(f"Bet outcome:         {'WIN' if (result.recommended_side == 'home') else 'LOSS'} (since home MEX won)")
