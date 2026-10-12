#!/usr/bin/env python3
"""
PHASE 2 — First Closure Loop
Direct call to PredictionOrchestrator with RESEARCH_MODE=1.
Uses C09 (KOR vs AUS) — most recent game with VERIFIED_WITH_FALLBACK status.
"""
import os, sys, json
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 55)
print("PHASE 2 — FIRST CLOSURE LOOP")
print("=" * 55)

# Verify RESEARCH_MODE is active
from research.config import is_research_mode_enabled
print(f"\n✅ research_mode: {is_research_mode_enabled()}")

# Build a minimal duck-typed GameRecord for C09
from dataclasses import dataclass, field
from typing import Optional, Any

@dataclass
class MinimalGameRecord:
    game_id: str
    tournament: str
    league: str
    round_name: str
    home_team: str
    away_team: str
    # Pre-game ELO / stats
    home_elo: float = 1480.0   # AUS
    away_elo: float = 1620.0   # KOR
    home_woba: float = 0.305
    away_woba: float = 0.340
    home_fip: float = 4.50
    away_fip: float = 3.80
    home_rest_days: int = 2
    away_rest_days: int = 1
    home_rsi: float = 75.0
    away_rsi: float = 82.0
    market_home_prob: float = 0.377   # from ML odds: home AUS 2.65 → 37.7%
    ou_line: float = 8.5
    # post-game fields — intentionally null at prediction time
    actual_home_score: Optional[int] = None
    actual_away_score: Optional[int] = None
    actual_home_win: Optional[int] = None
    actual_total_runs: Optional[int] = None
    data_source: str = "real"
    # extra attrs the adapter might probe
    weather: dict = field(default_factory=dict)
    # Real C09 ML odds: AUS (home) 2.65 → +165 American, KOR (away) 1.52 → -192 American
    odds: dict = field(default_factory=lambda: {"home_ml": 165, "away_ml": -192})
    pitchers: dict = field(default_factory=dict)
    lineups: dict = field(default_factory=dict)
    bullpen_usage: dict = field(default_factory=dict)
    injury_report: dict = field(default_factory=dict)

record = MinimalGameRecord(
    game_id="C09",
    tournament="WBC",
    league="WBC",
    round_name="Pool C",
    home_team="AUS",
    away_team="KOR",
)

print(f"\n── Calling PredictionOrchestrator.predict(C09) ──")
from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator

orc = PredictionOrchestrator()
result = orc.predict(
    record,
    use_world_model=False,
    use_hierarchical_mc=True,
)

print(f"  home_win_prob:      {result.home_win_prob:.4f}")
print(f"  away_win_prob:      {result.away_win_prob:.4f}")
print(f"  execution_mode:    {result.execution_mode}")
print(f"  models_activated:  {result.models_activated}")
print(f"  audit_trail keys:  {list(result.audit_trail.keys())}")
print(f"  warnings:          {result.warnings}")

# Verify trade_ledger was created
print("\n── Verifying research artifacts ──")
from pathlib import Path
ledger = Path("research/trade_ledger.jsonl")
if ledger.exists():
    rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
    print(f"  ✅ trade_ledger.jsonl: {len(rows)} records")
    last = rows[-1]
    print(f"     event_type:     {last.get('event_type')}")
    print(f"     game_id:        {last.get('game_id')}")
    print(f"     decision:       {last.get('decision')}")
    print(f"     predicted_prob: {last.get('predicted_prob')}")
else:
    print("  ❌ trade_ledger.jsonl: MISSING")
    print("     → capture() was not called — check RESEARCH_MODE guard in orchestrator")

daily = Path("research/daily_run_registry.jsonl")
print(f"  daily_run_registry: {'EXISTS' if daily.exists() else 'MISSING'}")
