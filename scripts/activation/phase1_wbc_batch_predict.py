#!/usr/bin/env python3
"""
PHASE 1 — WBC Batch Prediction
Run ALL 40 WBC pool games through PredictionOrchestrator with RESEARCH_MODE=1.
Skips games already in trade_ledger (idempotent).
"""
import os, sys, json, time
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

from data.wbc_pool_a import list_wbc_matches_a, fetch_wbc_match_a, _POOL_A_SCHEDULE
from data.wbc_pool_b import list_wbc_matches_b, fetch_wbc_match_b, _POOL_B_SCHEDULE
from data.wbc_pool_c import list_wbc_matches, fetch_wbc_match, _POOL_C_SCHEDULE
from data.wbc_pool_d import list_wbc_matches_d, fetch_wbc_match_d, _POOL_D_SCHEDULE
from wbc_backend.pipeline.prediction_orchestrator import PredictionOrchestrator


def _decimal_to_american(dec: float) -> int:
    """Convert decimal odds to American ML format."""
    if dec <= 1.0:
        return -10000
    if dec < 2.0:
        return int(round(-(100.0 / (dec - 1.0))))
    return int(round((dec - 1.0) * 100.0))


def _market_home_prob(ml_home: float) -> float:
    """Implied probability from decimal home odds (no vig removal)."""
    return 1.0 / ml_home if ml_home > 0 else 0.5


def _existing_game_ids() -> set:
    path = "research/trade_ledger.jsonl"
    if not os.path.exists(path):
        return set()
    ids = set()
    for line in open(path):
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row.get("event_type") == "prediction":
            ids.add(row.get("game_id", ""))
    return ids


# Build schedule lookup: game_id → odds_params + meta
def _build_schedule_map() -> Dict[str, Dict]:
    result = {}
    for sched, pool in [(_POOL_A_SCHEDULE, "A"), (_POOL_B_SCHEDULE, "B"),
                         (_POOL_C_SCHEDULE, "C"), (_POOL_D_SCHEDULE, "D")]:
        for g in sched:
            gid = g["game_id"]
            op = g.get("odds_params", {})
            result[gid] = {
                "pool": pool,
                "home_code": g["home_code"],
                "away_code": g["away_code"],
                "date": g["date"],
                "ml_home": op.get("ml_home", 2.0),
                "ml_away": op.get("ml_away", 2.0),
            }
    return result


FETCHERS = {
    "A": (list_wbc_matches_a, fetch_wbc_match_a),
    "B": (list_wbc_matches_b, fetch_wbc_match_b),
    "C": (list_wbc_matches, fetch_wbc_match),
    "D": (list_wbc_matches_d, fetch_wbc_match_d),
}

SCHEDULE_MAP = _build_schedule_map()


@dataclass
class WBCGameRecord:
    """Wrapper that adds game_id + odds to MatchData for the orchestrator."""
    game_id: str
    tournament: str = "WBC"
    league: str = "WBC"
    round_name: str = "Pool"
    home_team: str = ""
    away_team: str = ""
    home_elo: float = 1500.0
    away_elo: float = 1500.0
    home_woba: float = 0.310
    away_woba: float = 0.310
    home_fip: float = 4.20
    away_fip: float = 4.20
    home_rest_days: int = 1
    away_rest_days: int = 1
    market_home_prob: float = 0.50
    ou_line: float = 8.5
    actual_home_score: Optional[int] = None
    actual_away_score: Optional[int] = None
    actual_home_win: Optional[int] = None
    data_source: str = "real"
    odds: dict = field(default_factory=dict)
    weather: dict = field(default_factory=dict)
    pitchers: dict = field(default_factory=dict)
    lineups: dict = field(default_factory=dict)
    bullpen_usage: dict = field(default_factory=dict)
    injury_report: dict = field(default_factory=dict)
    # passthrough for adapter probing
    _match_data: Any = field(default=None, repr=False)

    def __getattr__(self, name: str):
        """Proxy to underlying MatchData for any unknown attr."""
        md = object.__getattribute__(self, '_match_data')
        if md is not None and hasattr(md, name):
            return getattr(md, name)
        raise AttributeError(name)


def _elo_from_match(md, home_code: str, away_code: str):
    """Extract ELO from TeamStats if available."""
    home_elo = getattr(getattr(md, 'home', None), 'elo', 1500.0) or 1500.0
    away_elo = getattr(getattr(md, 'away', None), 'elo', 1500.0) or 1500.0
    return float(home_elo), float(away_elo)


def _woba_from_match(md):
    home_woba = getattr(getattr(md, 'home', None), 'team_woba', 0.310) or 0.310
    away_woba = getattr(getattr(md, 'away', None), 'team_woba', 0.310) or 0.310
    return float(home_woba), float(away_woba)


def _fip_from_match(md):
    home_fip = getattr(getattr(md, 'home_sp', None), 'fip', 4.20) or 4.20
    away_fip = getattr(getattr(md, 'away_sp', None), 'fip', 4.20) or 4.20
    return float(home_fip), float(away_fip)


def main():
    print("=" * 60)
    print("PHASE 1 — WBC BATCH PREDICTION")
    print("=" * 60)

    existing = _existing_game_ids()
    print(f"\nAlready in ledger: {len(existing)} predictions")
    if existing:
        print(f"  {sorted(existing)}")

    orc = PredictionOrchestrator()
    ok_count = 0
    skip_count = 0
    err_count = 0
    results = []

    for pool, (lister, fetcher) in FETCHERS.items():
        print(f"\n── Pool {pool} ──")
        for game in lister():
            gid = game["game_id"]

            if gid in existing:
                print(f"  SKIP {gid} (already in ledger)")
                skip_count += 1
                continue

            meta = SCHEDULE_MAP.get(gid, {})
            ml_home = meta.get("ml_home", 2.0)
            ml_away = meta.get("ml_away", 2.0)
            home_code = meta.get("home_code", "")
            away_code = meta.get("away_code", "")

            try:
                md = fetcher(gid)
                home_elo, away_elo = _elo_from_match(md, home_code, away_code)
                home_woba, away_woba = _woba_from_match(md)
                home_fip, away_fip = _fip_from_match(md)

                rec = WBCGameRecord(
                    game_id=gid,
                    round_name=f"Pool {pool}",
                    home_team=home_code,
                    away_team=away_code,
                    home_elo=home_elo,
                    away_elo=away_elo,
                    home_woba=home_woba,
                    away_woba=away_woba,
                    home_fip=home_fip,
                    away_fip=away_fip,
                    market_home_prob=_market_home_prob(ml_home),
                    odds={
                        "home_ml": _decimal_to_american(ml_home),
                        "away_ml": _decimal_to_american(ml_away),
                    },
                    _match_data=md,
                )

                result = orc.predict(rec, use_world_model=False, use_hierarchical_mc=True)
                print(f"  OK   {gid}  home={result.home_win_prob:.4f}  "
                      f"side={result.recommended_side}  kelly={result.recommended_kelly_fraction:.4f}  "
                      f"mode={result.execution_mode}")
                results.append({"game_id": gid, "status": "ok",
                                 "home_win_prob": result.home_win_prob})
                ok_count += 1

            except Exception as exc:
                print(f"  ERR  {gid}: {exc}")
                results.append({"game_id": gid, "status": "error", "error": str(exc)})
                err_count += 1

    print(f"\n{'=' * 60}")
    print(f"BATCH PREDICT SUMMARY")
    print(f"  OK:     {ok_count}")
    print(f"  SKIP:   {skip_count}")
    print(f"  ERROR:  {err_count}")

    # Verify ledger
    from pathlib import Path
    ledger = Path("research/trade_ledger.jsonl")
    if ledger.exists():
        rows = [json.loads(l) for l in ledger.read_text().splitlines() if l.strip()]
        preds = [r for r in rows if r.get("event_type") == "prediction"]
        print(f"\nTrade ledger predictions: {len(preds)}")
        gate = len(preds) >= 35
        print(f"PASS gate (>=35): {'✅ PASS' if gate else '❌ FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
