#!/usr/bin/env python3
"""
PHASE 2 — WBC Batch Settlement Ingestion
Ingests real game results for all 40 WBC pool games into the research layer.
Only settles games that already have predictions in trade_ledger (from Phase 1).
Idempotent — skips already-settled games.
"""
import os, sys
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import timezone, time as dtime, datetime, date
from typing import List

from research.settlement_ingestion import SettlementIngestionEngine, SettlementInput
from scripts.activation.wbc_pool_results import build_settlement_records


def _game_settlement_time(game_date: str) -> str:
    """Build an ISO timestamp for end-of-game-day (23:59 UTC on game_date)."""
    d = date.fromisoformat(game_date)
    dt = datetime.combine(d, dtime(23, 59, 0), tzinfo=timezone.utc)
    return dt.isoformat()


def main() -> None:
    print("=" * 60)
    print("PHASE 2 — WBC BATCH SETTLEMENT INGESTION")
    print("=" * 60)

    records = build_settlement_records()
    print(f"\nBuilt {len(records)} settlement records from live scores\n")

    settlements: List[SettlementInput] = []
    for gid in sorted(records.keys()):
        r = records[gid]
        result = "home_win" if r["home_win"] == 1 else "away_win"
        st = SettlementInput(
            game_id=gid,
            result=result,
            settlement_time=_game_settlement_time(r["game_date"]),
            final_score=r["result_desc"],
        )
        settlements.append(st)

    print(f"Submitting {len(settlements)} settlements to ingestion engine…\n")

    engine = SettlementIngestionEngine()
    summary = engine.ingest(settlements)

    print(f"Ingestion complete:")
    print(f"  input_count                   : {summary.get('input_count', '?')}")
    print(f"  settled_count                 : {summary.get('settled_count', '?')}")
    print(f"  skipped_existing_settlement   : {summary.get('skipped_existing_settlement', '?')}")
    print(f"  skipped_missing_prediction    : {summary.get('skipped_missing_prediction', '?')}")
    print(f"  skipped_inactive_prediction   : {summary.get('skipped_inactive_prediction', '?')}")
    print(f"  skipped_missing_odds          : {summary.get('skipped_missing_odds', '?')}")
    print(f"  invalid_rows                  : {summary.get('invalid_rows', '?')}")
    print(f"  trigger_count                 : {summary.get('trigger_count', '?')}")
    print(f"  postmortem_reports generated  : {len(summary.get('postmortem_reports', []))}")

    # Verify ROI tracker
    import json
    from pathlib import Path
    roi_path = Path("research/roi_tracking.json")
    if roi_path.exists():
        roi = json.loads(roi_path.read_text())
        sample_size = roi.get("sample_size", 0)
        bankroll = roi.get("current_bankroll", 0)
        print(f"\nROI tracker:")
        print(f"  sample_size      : {sample_size}")
        print(f"  current_bankroll : {bankroll}")
        gate = sample_size >= 15 and summary.get("settled_count", 0) >= 20
        print(f"\nPASS gate (sample_size>=15, settled>=20): {'✅ PASS' if gate else '❌ FAIL'}")
    print("=" * 60)


if __name__ == "__main__":
    main()
