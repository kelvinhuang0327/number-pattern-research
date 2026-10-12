#!/usr/bin/env python3
"""
PHASE 5 — Continuous Loop Validation & Final Log
1. Re-run Phase 1 — all 40 games must be SKIP (idempotency)
2. Re-run Phase 2 — all must be skipped_existing_settlement
3. Write final entry to logs/activation_loop_log.jsonl
"""
import os, sys, json
os.environ["RESEARCH_MODE"] = "1"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from datetime import datetime, timezone
from pathlib import Path

from research.settlement_ingestion import SettlementIngestionEngine, SettlementInput
from scripts.activation.wbc_pool_results import build_settlement_records
from datetime import date as _date, timedelta as _td, time as _time


def _game_settlement_time(game_date: str) -> str:
    d = _date.fromisoformat(game_date)
    dt = datetime.combine(d, _time(23, 59, 0), tzinfo=timezone.utc)
    return dt.isoformat()


def test_phase1_idempotency() -> bool:
    """All 40 predictions already in ledger — re-run should produce 0 new."""
    print("\n── Phase 1 idempotency ─────────────────────────────────")
    ledger = Path("research/trade_ledger.jsonl")
    if not ledger.exists():
        print("  FAIL: trade_ledger.jsonl not found")
        return False

    existing = set()
    for line in ledger.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("event_type") == "prediction":
            existing.add(row.get("game_id", ""))

    from data.wbc_pool_a import list_wbc_matches_a
    from data.wbc_pool_b import list_wbc_matches_b
    from data.wbc_pool_c import list_wbc_matches
    from data.wbc_pool_d import list_wbc_matches_d

    all_game_ids = set()
    for lister in [list_wbc_matches_a, list_wbc_matches_b, list_wbc_matches, list_wbc_matches_d]:
        for g in lister():
            all_game_ids.add(g["game_id"])

    covered = all_game_ids & existing
    missing = all_game_ids - existing

    print(f"  Total pool games   : {len(all_game_ids)}")
    print(f"  Already predicted  : {len(covered)}")
    print(f"  Missing predictions: {len(missing)}")
    if missing:
        print(f"    {sorted(missing)}")
    ok = len(missing) == 0
    print(f"  Result: {'✅ PASS' if ok else '❌ FAIL'}")
    return ok


def test_phase2_idempotency() -> bool:
    """Re-ingesting all settlements should produce 0 new (all skipped as existing)."""
    print("\n── Phase 2 idempotency ─────────────────────────────────")
    records = build_settlement_records()
    settlements = []
    for gid in sorted(records.keys()):
        r = records[gid]
        result = "home_win" if r["home_win"] == 1 else "away_win"
        settlements.append(SettlementInput(
            game_id=gid,
            result=result,
            settlement_time=_game_settlement_time(r["game_date"]),
            final_score=r["result_desc"],
        ))

    engine = SettlementIngestionEngine()
    summary = engine.ingest(settlements)
    new_settled = summary.get("settled_count", 0)
    skipped = summary.get("skipped_existing_settlement", 0)

    print(f"  Input count              : {summary.get('input_count')}")
    print(f"  New settlements          : {new_settled}")
    print(f"  Skipped (already exist)  : {skipped}")
    print(f"  Skipped (inactive pred)  : {summary.get('skipped_inactive_prediction', 0)}")
    ok = new_settled == 0
    print(f"  Result: {'✅ PASS' if ok else '❌ FAIL'} (expect 0 new settlements)")
    return ok


def write_final_log(p1_ok: bool, p2_ok: bool) -> None:
    log_path = Path("logs/activation_loop_log.jsonl")
    log_path.parent.mkdir(parents=True, exist_ok=True)

    ledger = Path("research/trade_ledger.jsonl")
    predictions, settlements = 0, 0
    if ledger.exists():
        for line in ledger.read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            et = row.get("event_type", "")
            if et == "prediction":
                predictions += 1
            elif et == "settlement":
                settlements += 1

    roi_path = Path("research/roi_tracking.json")
    roi_sample_size = 0
    current_bankroll = None
    if roi_path.exists():
        roi = json.loads(roi_path.read_text())
        roi_sample_size = roi.get("sample_size", 0)
        current_bankroll = roi.get("current_bankroll")

    pm_dir = Path("research/postmortem_reports")
    pm_count = len(list(pm_dir.glob("*.md"))) if pm_dir.exists() else 0

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "job": "SCALE_UP_8H",
        "phase1_idempotency": p1_ok,
        "phase2_idempotency": p2_ok,
        "overall_pass": p1_ok and p2_ok,
        "predictions_in_ledger": predictions,
        "settlements_in_ledger": settlements,
        "roi_sample_size": roi_sample_size,
        "current_bankroll": current_bankroll,
        "postmortem_reports": pm_count,
    }

    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

    print(f"\n── Final log ────────────────────────────────────────────")
    print(f"  Written to: {log_path}")
    for k, v in entry.items():
        print(f"  {k}: {v}")


def main() -> None:
    print("=" * 60)
    print("PHASE 5 — CONTINUOUS LOOP VALIDATION")
    print("=" * 60)

    p1_ok = test_phase1_idempotency()
    p2_ok = test_phase2_idempotency()
    write_final_log(p1_ok, p2_ok)

    print(f"\n{'=' * 60}")
    overall = p1_ok and p2_ok
    print(f"PHASE 5 OVERALL: {'✅ PASS' if overall else '❌ FAIL'}")
    print("=" * 60)
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
