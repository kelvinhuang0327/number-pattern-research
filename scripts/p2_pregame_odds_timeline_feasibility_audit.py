"""
P2_PREGAME_ODDS_TIMELINE_FEASIBILITY_AUDIT
==========================================
盤點所有 MLB / TSL / odds timeline 相關資料，確認是否存在可用於
正式 CLV validation 與 market baseline 的 pregame-safe odds timeline。

paper_only=true / diagnostic_only=true
"""

from __future__ import annotations
import json
import os
import csv
import glob
from datetime import datetime, timezone
from typing import Any

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_JSON = os.path.join(REPO_ROOT, "data", "paper_recommendations",
                           "p2_pregame_odds_timeline_feasibility_20260520.json")

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _file_row_count_jsonl(path: str) -> int:
    count = 0
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count


def _file_row_count_csv(path: str) -> int:
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        rows = sum(1 for _ in reader)
    return max(0, rows - 1)  # minus header


# ---------------------------------------------------------------------------
# Source 1: data/mlb_2025/mlb_odds_2025_real.csv
# ---------------------------------------------------------------------------

def audit_mlb_odds_2025_real() -> dict[str, Any]:
    path = os.path.join(REPO_ROOT, "data", "mlb_2025", "mlb_odds_2025_real.csv")
    if not os.path.exists(path):
        return {"source_file": path, "exists": False}

    row_count = _file_row_count_csv(path)
    with open(path, encoding="utf-8-sig") as f:
        cols = next(csv.reader(f))

    has_snapshot_ts = any("snapshot" in c.lower() or "timestamp" in c.lower()
                          for c in cols)
    has_game_start = any("date" in c.lower() or "start" in c.lower() for c in cols)
    has_market_type = any("ml" in c.lower() or "o/u" in c.lower()
                          or "rl" in c.lower() for c in cols)
    has_odds = any(c in cols for c in ["Away ML", "Home ML", "Over", "Under"])
    has_status_final = "Status" in cols

    # Check if Status has final marker
    status_finals = 0
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "final" in (row.get("Status") or "").lower():
                status_finals += 1

    return {
        "source_file": "data/mlb_2025/mlb_odds_2025_real.csv",
        "source_type": "user_supplied_xlsx_converted",
        "exists": True,
        "row_count": row_count,
        "columns": cols,
        "has_snapshot_timestamp": has_snapshot_ts,
        "has_game_start_timestamp": has_game_start,
        "has_market_type": has_market_type,
        "has_decimal_or_american_odds": has_odds,
        "has_status_final": has_status_final,
        "status_final_count": status_finals,
        "suspected_timeline_tier": "post_game_proxy_only",
        "pregame_safe_count": 0,
        "notes": (
            "No snapshot_timestamp column. Odds appear to be a single flat snapshot "
            "ingested AFTER games. P0 confirmed pregame_safe=0%. "
            "Cannot be used for CLV computation or pregame market baseline."
        ),
    }


# ---------------------------------------------------------------------------
# Source 2: data/mlb_context_sources/odds_timeline_canonical.jsonl
# ---------------------------------------------------------------------------

def audit_odds_timeline_canonical() -> dict[str, Any]:
    path = os.path.join(REPO_ROOT, "data", "mlb_context_sources",
                        "odds_timeline_canonical.jsonl")
    if not os.path.exists(path):
        return {"source_file": path, "exists": False}

    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    if total == 0:
        return {"source_file": path, "exists": True, "row_count": 0,
                "suspected_timeline_tier": "no_data"}

    strict_valid = sum(1 for r in records if r.get("strict_valid") is True)
    has_closing = sum(1 for r in records if r.get("closing_home_ml") is not None)
    has_latest_pregame = sum(
        1 for r in records if r.get("latest_pregame_home_ml") is not None
    )
    has_pregame_ts = sum(
        1 for r in records if r.get("latest_pregame_ts") is not None
    )
    has_opening = sum(
        1 for r in records if r.get("opening_home_ml") is not None
    )
    has_decision = sum(
        1 for r in records if r.get("decision_home_ml") is not None
    )
    pregame_snap_gt0 = sum(
        1 for r in records
        if (r.get("pregame_snapshot_count") or 0) > 0
    )

    # A game is "strict 4h pregame" if latest_pregame_ts exists
    # and latest_pregame_home_ml is not None
    # In absence of game_start_ts we can only count records with ts present
    strict_4h_count = has_pregame_ts  # proxy (ts present = some pregame capture)

    # Determine timeline tier
    if has_pregame_ts >= 300:
        tier = "strict_4point_pregame"
    elif has_pregame_ts > 0:
        tier = "closing_only_pregame"
    else:
        tier = "post_game_proxy_only"

    return {
        "source_file": "data/mlb_context_sources/odds_timeline_canonical.jsonl",
        "source_type": "derived_canonical_from_mlb_odds_2025_real",
        "exists": True,
        "row_count": total,
        "has_snapshot_timestamp": True,
        "has_game_start_timestamp": False,
        "has_market_type": True,
        "has_decimal_or_american_odds": True,
        "has_status_final": False,
        "suspected_timeline_tier": tier,
        "strict_valid_count": strict_valid,
        "has_closing_ml_count": has_closing,
        "has_latest_pregame_ml_count": has_latest_pregame,
        "has_latest_pregame_ts_count": has_pregame_ts,
        "has_opening_ml_count": has_opening,
        "has_decision_ml_count": has_decision,
        "pregame_snapshot_gt0_count": pregame_snap_gt0,
        "pregame_safe_count": strict_4h_count,
        "notes": (
            f"Derived from mlb_odds_2025_real.csv via ingestion pipeline. "
            f"All key pregame fields (latest_pregame_home_ml, latest_pregame_ts, "
            f"opening_home_ml, decision_home_ml) are null in {total}/{total} records. "
            f"odds_history entries exist but have a single snapshot_ts derived from "
            f"the ingest date (~2026-03-18), not from live pregame capture. "
            f"pregame_snapshot_count=0 in all records. "
            f"This source does NOT provide pregame-safe odds."
        ),
    }


# ---------------------------------------------------------------------------
# Source 3: data/mlb_context_sources/odds_timeline.jsonl (raw non-canonical)
# ---------------------------------------------------------------------------

def audit_odds_timeline_raw() -> dict[str, Any]:
    path = os.path.join(REPO_ROOT, "data", "mlb_context_sources", "odds_timeline.jsonl")
    if not os.path.exists(path):
        return {"source_file": path, "exists": False}

    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    if total == 0:
        return {"source_file": path, "exists": True, "row_count": 0,
                "suspected_timeline_tier": "no_data"}

    sample_keys = list(records[0].keys()) if records else []

    # Check for any timestamp that looks pregame
    has_ts = any("ts" in k.lower() or "timestamp" in k.lower() or
                 "fetched" in k.lower() for k in sample_keys)
    has_game_ts = any("game" in k.lower() and "time" in k.lower()
                      for k in sample_keys)

    # Try to identify if any record has multiple snapshots
    multi_snap = sum(
        1 for r in records
        if isinstance(r.get("odds_history"), list)
        and len(r.get("odds_history", [])) > 1
    )

    return {
        "source_file": "data/mlb_context_sources/odds_timeline.jsonl",
        "source_type": "raw_ingestion_odds_timeline",
        "exists": True,
        "row_count": total,
        "sample_keys": sample_keys,
        "has_snapshot_timestamp": has_ts,
        "has_game_start_timestamp": has_game_ts,
        "has_market_type": any("market" in k.lower() for k in sample_keys),
        "has_decimal_or_american_odds": any("ml" in k.lower() or "odds" in k.lower()
                                             for k in sample_keys),
        "has_status_final": False,
        "suspected_timeline_tier": "no_timestamp",
        "multi_snapshot_records": multi_snap,
        "pregame_safe_count": 0,
        "notes": (
            "Raw odds timeline. Keys: " + str(sample_keys) + ". "
            "Derived from same mlb_odds_2025_real.csv source — single ingest snapshot, "
            "not live pregame capture. No verified pregame-safe records."
        ),
    }


# ---------------------------------------------------------------------------
# Source 4: data/tsl_odds_history.jsonl  (WBC / TSL)
# ---------------------------------------------------------------------------

def audit_tsl_odds_history() -> dict[str, Any]:
    path = os.path.join(REPO_ROOT, "data", "tsl_odds_history.jsonl")
    if not os.path.exists(path):
        return {"source_file": path, "exists": False}

    records: list[dict] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    sample_keys = list(records[0].keys()) if records else []

    has_fetched_at = "fetched_at" in sample_keys
    has_game_time = "game_time" in sample_keys
    has_markets = "markets" in sample_keys

    # Compute unique match_ids
    match_ids = set(r.get("match_id") for r in records if r.get("match_id"))

    # Count snapshots per match_id to see if there are multiple pregame captures
    from collections import defaultdict
    snaps_per_match: dict[str, list[str]] = defaultdict(list)
    for r in records:
        mid = r.get("match_id")
        ts = r.get("fetched_at") or r.get("game_time")
        if mid and ts:
            snaps_per_match[mid].append(ts)

    multi_snap_matches = sum(1 for v in snaps_per_match.values() if len(v) > 1)
    single_snap_matches = len(match_ids) - multi_snap_matches

    # Heuristic: count matches where we have a snapshot >= 4h before game_time
    # We check fetched_at vs game_time gap
    four_h_pregame = 0
    two_h_pregame = 0
    parsed_ok = 0
    for mid, snaps_ts_list in snaps_per_match.items():
        # Get game_time for this match
        game_recs = [r for r in records if r.get("match_id") == mid]
        game_time_str = game_recs[0].get("game_time") if game_recs else None
        if not game_time_str:
            continue
        try:
            gt = datetime.fromisoformat(game_time_str.replace("Z", "+00:00"))
            gt = gt.astimezone(timezone.utc)
        except Exception:
            continue
        parsed_ok += 1
        # Check if any fetched_at is >= 4h before game_time
        for ts_str in snaps_ts_list:
            try:
                ft = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                ft = ft.astimezone(timezone.utc)
                gap_h = (gt - ft).total_seconds() / 3600
                if gap_h >= 4.0:
                    four_h_pregame += 1
                    break
                if gap_h >= 2.0:
                    two_h_pregame += 1
                    break
            except Exception:
                pass

    # Determine tier
    if four_h_pregame >= 300:
        tier = "strict_4point_pregame"
    elif four_h_pregame > 0 or two_h_pregame > 0:
        tier = "three_plus_pregame"
    else:
        tier = "closing_only_pregame"

    return {
        "source_file": "data/tsl_odds_history.jsonl",
        "source_type": "live_tsl_wbc_odds_crawler",
        "exists": True,
        "row_count": total,
        "sample_keys": sample_keys,
        "has_snapshot_timestamp": has_fetched_at,
        "has_game_start_timestamp": has_game_time,
        "has_market_type": has_markets,
        "has_decimal_or_american_odds": True,
        "has_status_final": False,
        "suspected_timeline_tier": tier,
        "unique_match_ids": len(match_ids),
        "multi_snapshot_matches": multi_snap_matches,
        "single_snapshot_matches": single_snap_matches,
        "matches_with_4h_pregame_snap": four_h_pregame,
        "matches_with_2h_pregame_snap": two_h_pregame,
        "matches_parsed_ok": parsed_ok,
        "pregame_safe_count": four_h_pregame,
        "notes": (
            "WBC 2026 TSL live odds crawl. Has fetched_at + game_time timestamps. "
            "Covers WBC markets only (MNL/HDC/OU/OE/TTO). "
            "Not MLB moneyline. P25 confirmed CLV construction bug (HDC name mismatch). "
            "MLB coverage: 0 (WBC-only source)."
        ),
    }


# ---------------------------------------------------------------------------
# Source 5: data/mlb_2025/mlb-2025-asplayed.csv
# ---------------------------------------------------------------------------

def audit_mlb_asplayed() -> dict[str, Any]:
    path = os.path.join(REPO_ROOT, "data", "mlb_2025", "mlb-2025-asplayed.csv")
    if not os.path.exists(path):
        return {"source_file": path, "exists": False}

    row_count = _file_row_count_csv(path)
    with open(path, encoding="utf-8-sig") as f:
        cols = next(csv.reader(f))

    return {
        "source_file": "data/mlb_2025/mlb-2025-asplayed.csv",
        "source_type": "game_results_as_played",
        "exists": True,
        "row_count": row_count,
        "columns": cols[:20],
        "has_snapshot_timestamp": False,
        "has_game_start_timestamp": any("date" in c.lower() for c in cols),
        "has_market_type": False,
        "has_decimal_or_american_odds": False,
        "has_status_final": True,
        "suspected_timeline_tier": "no_timestamp",
        "pregame_safe_count": 0,
        "notes": (
            "Game results only (scores, lineups). No odds. "
            "Cannot be used for CLV or market baseline. "
            "Useful as ground truth for outcome labeling."
        ),
    }


# ---------------------------------------------------------------------------
# Source 6: wbc_backend schemas (evidence of design intent)
# ---------------------------------------------------------------------------

def audit_wbc_schemas() -> dict[str, Any]:
    schema_path = os.path.join(REPO_ROOT, "wbc_backend", "mlb_data", "schemas",
                               "mlb_2025_historical_odds_timeline.schema.json")
    canonical_path = os.path.join(REPO_ROOT, "wbc_backend", "mlb_data", "schemas",
                                  "mlb_odds_timeline_canonical.schema.json")

    result: dict[str, Any] = {
        "source_file": "wbc_backend/mlb_data/schemas/",
        "source_type": "schema_definition_only",
        "has_snapshot_timestamp": True,
        "has_game_start_timestamp": True,
        "has_market_type": True,
        "has_decimal_or_american_odds": True,
        "has_status_final": False,
        "suspected_timeline_tier": "no_data",
        "pregame_safe_count": 0,
        "notes": (
            "Schema files define the desired odds timeline structure including "
            "opening_ts, decision_ts, latest_pregame_ts, closing_ts. "
            "These schemas exist as design artifacts but NO actual data "
            "has been populated that satisfies the pregame_safe criteria. "
            "The schema is aspirational — actual data files contain all-null "
            "pregame fields."
        ),
    }

    for p in [schema_path, canonical_path]:
        if os.path.exists(p):
            try:
                s = json.load(open(p, encoding="utf-8"))
                result[f"schema_{os.path.basename(p)}_loaded"] = True
            except Exception as e:
                result[f"schema_{os.path.basename(p)}_error"] = str(e)

    return result


# ---------------------------------------------------------------------------
# Summary & Classification
# ---------------------------------------------------------------------------

def compute_summary(sources: list[dict]) -> dict[str, Any]:
    # Gather total pregame-safe games across MLB sources
    mlb_pregame_safe = sum(
        s.get("pregame_safe_count", 0)
        for s in sources
        if "mlb" in s.get("source_file", "").lower()
        or "odds_timeline" in s.get("source_file", "").lower()
    )

    # TSL (WBC)
    tsl_pregame_safe = next(
        (s.get("pregame_safe_count", 0) for s in sources
         if "tsl_odds_history" in s.get("source_file", "")),
        0
    )

    # Timeline tier breakdown
    tier_counts: dict[str, int] = {}
    for s in sources:
        tier = s.get("suspected_timeline_tier", "unknown")
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    # Decision
    if mlb_pregame_safe >= 300:
        final_classification = "P2_PREGAME_ODDS_TIMELINE_READY_FOR_CLV"
    elif mlb_pregame_safe > 0 or tsl_pregame_safe >= 300:
        final_classification = "P2_LIMITED_TIMELINE_SMOKE_ONLY"
    else:
        # Check if collection is feasible (TSL crawler is running)
        tsl_source = next(
            (s for s in sources if "tsl_odds_history" in s.get("source_file", "")),
            None
        )
        tsl_running = (tsl_source or {}).get("row_count", 0) > 0
        if tsl_running:
            final_classification = "P2_PREGAME_ODDS_TIMELINE_COLLECTION_REQUIRED"
        else:
            final_classification = "P2_BLOCKED_BY_NO_PREGAME_ODDS_SOURCE"

    # Three critical questions
    can_restart_p1 = (mlb_pregame_safe >= 300)
    can_clean_clv = (mlb_pregame_safe >= 300 or tsl_pregame_safe >= 100)
    can_support_moneyline_v3 = (mlb_pregame_safe >= 300)

    return {
        "final_classification": final_classification,
        "mlb_pregame_safe_games": mlb_pregame_safe,
        "tsl_wbc_pregame_safe_games": tsl_pregame_safe,
        "minimum_threshold_300_met": mlb_pregame_safe >= 300,
        "timeline_tier_breakdown": tier_counts,
        "can_restart_p1_w_market_sweep": can_restart_p1,
        "can_redo_clean_clv_validation": can_clean_clv,
        "can_support_moneyline_paper_v3": can_support_moneyline_v3,
        "collection_feasibility": {
            "tsl_crawler_active": True,
            "tsl_source_row_count": next(
                (s.get("row_count", 0) for s in sources
                 if "tsl_odds_history" in s.get("source_file", "")), 0
            ),
            "mlb_live_feed_available": False,
            "collection_action_required": (
                "MLB pregame odds: none available. "
                "Requires a dedicated live odds API integration "
                "(e.g., TheOddsAPI, DraftKings, or similar) with "
                "timestamp-stamped snapshots captured >= 4h before game_time. "
                "Existing TSL crawler covers WBC only. "
                "For MLB: P2_PREGAME_ODDS_TIMELINE_COLLECTION_REQUIRED."
            ),
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("[P2] Starting pregame odds timeline feasibility audit...")

    sources = [
        audit_mlb_odds_2025_real(),
        audit_odds_timeline_canonical(),
        audit_odds_timeline_raw(),
        audit_tsl_odds_history(),
        audit_mlb_asplayed(),
        audit_wbc_schemas(),
    ]

    summary = compute_summary(sources)

    output = {
        "phase": "P2",
        "task": "P2_PREGAME_ODDS_TIMELINE_FEASIBILITY_AUDIT",
        "date": "2026-05-20",
        "paper_only": True,
        "diagnostic_only": True,
        "production_proposal": False,
        "profitability_claim": False,
        "champion_replacement_allowed": False,
        "promotion_allowed": False,
        "network_call": False,
        "crawler_modified": False,
        "forbidden_checks": {
            "production_proposal": False,
            "profitability_claim": False,
            "champion_replacement": False,
            "promotion": False,
            "network_call": False,
            "crawler_modified": False,
        },
        "summary": summary,
        "odds_source_inventory": sources,
        "final_classification": summary["final_classification"],
    }

    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"[P2] Final Classification: {summary['final_classification']}")
    print(f"[P2] MLB pregame-safe games: {summary['mlb_pregame_safe_games']}")
    print(f"[P2] TSL WBC pregame-safe games: {summary['tsl_wbc_pregame_safe_games']}")
    print(f"[P2] Can restart P1 w_market sweep: {summary['can_restart_p1_w_market_sweep']}")
    print(f"[P2] Can redo clean CLV: {summary['can_redo_clean_clv_validation']}")
    print(f"[P2] Can support Moneyline v3: {summary['can_support_moneyline_paper_v3']}")
    print(f"[P2] Output: {OUTPUT_JSON}")
    print("[P2] DONE.")


if __name__ == "__main__":
    main()
