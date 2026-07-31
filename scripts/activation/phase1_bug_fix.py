"""
Phase 1 Bug Fix — Verification Script

Root cause: use_hierarchical_mc=True in batch predict causes HMC to use
market_home_prob as its starting point (line 327-328 in prediction_orchestrator.py):
    base_pred = PredictionResult(home_win_prob=market_prob, ...)
    hmc = run_hierarchical_monte_carlo(pred=base_pred, ...)

This creates circular market contamination:
  market_home_prob → HMC seed → fused_prob ≈ market_prob + small_delta
  → edge = fused_prob - market_prob ≈ very small / noise
  → recommends underdogs when market strongly prices favorites

Fix: use_hierarchical_mc=False — use MARL only for genuine independent prediction.

This script verifies the fix on B06 and C09 before full rebuild.
"""
import os, sys
os.environ["RESEARCH_MODE"] = "1"
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _ROOT)

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

# ── Reuse WBCGameRecord dataclass from phase1 script ──────────────────────
@dataclass
class WBCGameRecord:
    game_id: str
    round_name: str = "Pool"
    home_team: str = ""
    away_team: str = ""
    home_elo: float = 1500.0
    away_elo: float = 1500.0
    home_woba: float = 0.320
    away_woba: float = 0.320
    home_fip: float = 4.00
    away_fip: float = 4.00
    market_home_prob: float = 0.50
    odds: Dict[str, Any] = field(default_factory=dict)
    league: str = "WBC"
    tournament: str = "WBC"
    ou_line: float = 8.5
    _match_data: Any = field(default=None, repr=False)

    def __getattr__(self, name: str) -> Any:
        md = object.__getattribute__(self, "_match_data")
        if md is not None and hasattr(md, name):
            return getattr(md, name)
        raise AttributeError(f"WBCGameRecord has no attribute {name!r}")


def _decimal_to_american(dec: float) -> int:
    if dec <= 1.0:
        return -10000
    if dec < 2.0:
        return int(-(100.0 / (dec - 1.0)))
    return int((dec - 1.0) * 100.0)


def _market_home_prob(ml_home: float) -> float:
    return 1.0 / ml_home if ml_home > 0 else 0.5


# ── Test B06 and C09 ──────────────────────────────────────────────────────
from data.wbc_pool_b import fetch_wbc_match_b, _POOL_B_SCHEDULE
from data.wbc_pool_c import fetch_wbc_match
from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator

orc = PredictionOrchestrator()

test_cases = [
    {
        "gid": "B06",
        "fetcher": fetch_wbc_match_b,
        "schedule": _POOL_B_SCHEDULE,
        "actual": "home_win (MEX 16-0 BRA)",
    },
    {
        "gid": "C09",
        "fetcher": fetch_wbc_match,
        "schedule": None,
        "actual": "away_win (KOR 7-2 AUS)",
    },
]

# Load schedule data for C pool
from data.wbc_pool_c import _POOL_C_SCHEDULE

print("=" * 70)
print("PHASE 1 FIX VERIFICATION: with_hmc vs without_hmc")
print("=" * 70)

for tc in test_cases:
    gid = tc["gid"]
    md = tc["fetcher"](gid)
    schedule = tc["schedule"] or _POOL_C_SCHEDULE
    entry = next((g for g in schedule if g["game_id"] == gid), {})
    op = entry.get("odds_params", {})
    ml_home = op.get("ml_home", 2.0)
    ml_away = op.get("ml_away", 2.0)

    rec = WBCGameRecord(
        game_id=gid,
        round_name="Pool",
        home_team=entry.get("home_code", ""),
        away_team=entry.get("away_code", ""),
        market_home_prob=_market_home_prob(ml_home),
        odds={
            "home_ml": _decimal_to_american(ml_home),
            "away_ml": _decimal_to_american(ml_away),
        },
        _match_data=md,
    )

    print(f"\n{'─'*70}")
    print(f"{gid}: home={entry.get('home_code')} away={entry.get('away_code')}")
    print(f"  market_home_prob: {_market_home_prob(ml_home):.4f}  (home_ml={_decimal_to_american(ml_home)}, away_ml={_decimal_to_american(ml_away)})")
    print(f"  actual result   : {tc['actual']}")

    for use_hmc in [True, False]:
        r = orc.predict(rec, use_world_model=False, use_hierarchical_mc=use_hmc)
        tag = "WITH_HMC (old)" if use_hmc else "WITHOUT_HMC (fix)"
        print(f"\n  [{tag}]")
        print(f"    home_win_prob     : {r.home_win_prob:.4f}")
        print(f"    recommended_side  : {r.recommended_side}")
        print(f"    kelly             : {r.recommended_kelly_fraction:.4f}")
        if r.recommended_side in ("home", "away"):
            expected_result = (
                "WIN ✅" if (
                    (r.recommended_side == "home" and "home_win" in tc["actual"]) or
                    (r.recommended_side == "away" and "away_win" in tc["actual"])
                ) else "LOSS ❌"
            )
            print(f"    expected outcome  : {expected_result}")

print("\n" + "=" * 70)
print("Fix classification: HMC seed contamination (market_home_prob → HMC start)")
print("Fix: change use_hierarchical_mc=True → False in batch predict")
print("=" * 70)
