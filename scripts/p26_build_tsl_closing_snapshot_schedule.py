#!/usr/bin/env python3
"""
P26 — TSL Closing Snapshot Schedule Builder
paper_only=true / diagnostic_only=true

Root cause: determine_capture_windows() only reads data/mlb_context/odds_timeline.jsonl
(MLB games). WBC/NPB game times in tsl_odds_history.jsonl are NEVER checked by the
scheduler → closing window never fires for WBC/NPB → 577/886 matches missing closing
snapshots.

This script:
1. Reads data/tsl_odds_history.jsonl to get known match game_times
2. Classifies each match into coverage tiers
3. Builds a diagnostic closing capture schedule for matches that lack closing snapshots
4. Outputs: data/paper_recommendations/p26_tsl_closing_snapshot_schedule_20260520.json

Does NOT execute real crawler. Does NOT write to tsl_odds_history.jsonl.
"""
from __future__ import annotations

import json
import math
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from dateutil.parser import parse as dtparse

# ── Config ─────────────────────────────────────────────────────────────────────
DATE = "2026-05-20"
INPUT_PATH = os.path.join(ROOT, "data", "tsl_odds_history.jsonl")
SCHEDULE_OUT = os.path.join(
    ROOT, "data", "paper_recommendations",
    "p26_tsl_closing_snapshot_schedule_20260520.json"
)

PREGAME_MIN_H = 4.0       # ≥4h before game = pregame
CLOSING_MAX_H = 2.0       # ±2h around game_time = closing window
CLOSING_TARGET_OFFSETS_H = [-1.5, -0.5, 0.5]  # proposed capture times relative to game_time

os.makedirs(os.path.join(ROOT, "data", "paper_recommendations"), exist_ok=True)


def to_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        dt = dtparse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def classify_match(
    records: list[dict],
) -> tuple[str, dict]:
    """
    Returns (tier, detail_dict) where tier is one of:
      COMPLETE_PAIR        - has both pregame(>=4h) and closing(±2h)
      PREGAME_ONLY         - has pregame but no closing → needs schedule fix
      CLOSING_ONLY         - has closing but no pregame
      NO_VALID_SNAPSHOTS   - has neither
    """
    game_dt = to_utc(records[0].get("game_time", ""))
    if not game_dt:
        return "NO_VALID_SNAPSHOTS", {"reason": "missing_game_time"}

    snap_times = [to_utc(r.get("fetched_at", "")) for r in records]
    snap_times = [t for t in snap_times if t]
    if not snap_times:
        return "NO_VALID_SNAPSHOTS", {"reason": "no_valid_fetched_at"}

    has_pre = any((game_dt - t).total_seconds() / 3600 >= PREGAME_MIN_H for t in snap_times)
    has_clo = any(abs((game_dt - t).total_seconds() / 3600) <= CLOSING_MAX_H for t in snap_times)

    best_pre_gap = None
    best_clo_gap = None
    for t in snap_times:
        h = (game_dt - t).total_seconds() / 3600
        if h >= PREGAME_MIN_H:
            if best_pre_gap is None or h < best_pre_gap:
                best_pre_gap = h
    for t in snap_times:
        h = abs((game_dt - t).total_seconds() / 3600)
        if h <= CLOSING_MAX_H:
            if best_clo_gap is None or h < best_clo_gap:
                best_clo_gap = h

    detail = {
        "snapshot_count": len(snap_times),
        "best_pregame_gap_h": round(best_pre_gap, 2) if best_pre_gap else None,
        "best_closing_gap_h": round(best_clo_gap, 2) if best_clo_gap else None,
        "game_time_utc": game_dt.isoformat(),
        "game_time_hour_utc": game_dt.hour,
    }

    if has_pre and has_clo:
        return "COMPLETE_PAIR", detail
    elif has_pre:
        return "PREGAME_ONLY", detail
    elif has_clo:
        return "CLOSING_ONLY", detail
    else:
        return "NO_VALID_SNAPSHOTS", detail


# ── Load data ──────────────────────────────────────────────────────────────────
print("[P26] Loading tsl_odds_history.jsonl...")
with open(INPUT_PATH) as f:
    rows = [json.loads(l) for l in f if l.strip()]

by_mid: dict[str, list] = defaultdict(list)
for r in rows:
    by_mid[r["match_id"]].append(r)

print(f"  Total rows:    {len(rows)}")
print(f"  Unique matches: {len(by_mid)}")

# ── Classify ───────────────────────────────────────────────────────────────────
print("[P26] Classifying matches...")
tier_counts: Counter[str] = Counter()
matches_needing_closing: list[dict] = []
complete_pairs: list[dict] = []

for mid, records in by_mid.items():
    tier, detail = classify_match(records)
    tier_counts[tier] += 1

    game_time_str = records[0].get("game_time", "")
    base = {
        "match_id": mid,
        "home_team": records[0].get("home_team_name", ""),
        "away_team": records[0].get("away_team_name", ""),
        "game_time": game_time_str,
        "tier": tier,
        **detail,
    }

    if tier == "PREGAME_ONLY":
        # Build proposed closing capture times
        game_dt = to_utc(game_time_str)
        if game_dt:
            proposed = []
            for offset_h in CLOSING_TARGET_OFFSETS_H:
                target_dt = game_dt.replace(microsecond=0)
                from datetime import timedelta
                target_dt = target_dt + timedelta(hours=offset_h)
                proposed.append({
                    "target_utc": target_dt.isoformat().replace("+00:00", "Z"),
                    "offset_h": offset_h,
                    "label": (
                        "closing_pre_90min" if offset_h == -1.5 else
                        "closing_pre_30min" if offset_h == -0.5 else
                        "closing_post_30min"
                    ),
                })
            base["proposed_closing_captures"] = proposed
        matches_needing_closing.append(base)
    elif tier == "COMPLETE_PAIR":
        complete_pairs.append(base)

# ── Summary stats ──────────────────────────────────────────────────────────────
print(f"\n[P26] Coverage summary:")
for tier, count in sorted(tier_counts.items(), key=lambda x: -x[1]):
    pct = count / len(by_mid) * 100
    print(f"  {tier:25s}: {count:4d} ({pct:.1f}%)")

# Missing-closing by game hour
missing_by_hour: Counter[int] = Counter()
for m in matches_needing_closing:
    h = m.get("game_time_hour_utc")
    if h is not None:
        missing_by_hour[h] += 1

print(f"\n[P26] Missing-closing by UTC game hour:")
for h in sorted(missing_by_hour):
    bar = "█" * (missing_by_hour[h] // 5)
    print(f"  {h:02d}:00 UTC  {missing_by_hour[h]:3d}  {bar}")

# ── Root cause classification ──────────────────────────────────────────────────
root_causes = [
    "CLOSING_SCHEDULE_NOT_DEFINED",   # PRIMARY: determine_capture_windows() doesn't read WBC/NPB game times
    "CRAWLER_RUNTIME_NOT_TRIGGERED",  # SECONDARY: 15-min daemon never triggers closing for WBC/NPB
]

print(f"\n[P26] Root cause: {root_causes}")
print(f"\n[P26] Proposed fix: extend determine_capture_windows() to also read")
print(f"  tsl_odds_history.jsonl game_times, or build a WBC game manifest")
print(f"  that the scheduler reads alongside odds_timeline.jsonl")

# ── Expected coverage lift ─────────────────────────────────────────────────────
total = len(by_mid)
current_pairs = tier_counts["COMPLETE_PAIR"]
target_pairs_if_schedule_fixed = current_pairs + tier_counts["PREGAME_ONLY"]
lift_pct = (target_pairs_if_schedule_fixed - current_pairs) / total * 100

print(f"\n[P26] Expected coverage lift:")
print(f"  Current CLV pairs:    {current_pairs} ({current_pairs/total*100:.1f}%)")
print(f"  If schedule fixed:   ~{target_pairs_if_schedule_fixed} ({target_pairs_if_schedule_fixed/total*100:.1f}%)")
print(f"  Lift:                +{target_pairs_if_schedule_fixed - current_pairs} pairs (+{lift_pct:.1f}pp)")

# ── Write schedule JSON ────────────────────────────────────────────────────────
print(f"\n[P26] Writing schedule to {SCHEDULE_OUT}...")
schedule_payload = {
    "artifact_id": "p26_tsl_closing_snapshot_schedule_20260520",
    "date": DATE,
    "paper_only": True,
    "diagnostic_only": True,
    "production_proposal": False,
    "promotion_allowed": False,
    "profitability_claim": False,
    "source_file": "data/tsl_odds_history.jsonl",
    "total_matches": total,
    "tier_counts": dict(tier_counts),
    "complete_pair_matches": current_pairs,
    "pregame_only_matches": tier_counts["PREGAME_ONLY"],
    "closing_only_matches": tier_counts["CLOSING_ONLY"],
    "no_valid_snapshot_matches": tier_counts["NO_VALID_SNAPSHOTS"],
    "expected_pairs_after_fix": target_pairs_if_schedule_fixed,
    "root_causes": root_causes,
    "proposed_fix": {
        "summary": (
            "Extend wbc_backend/mlb_data/odds_capture_scheduler.determine_capture_windows() "
            "to also read a WBC/NPB game manifest, so the daemon triggers closing captures "
            "at game_time -90min and -30min for WBC/NPB games. "
            "Alternative: build a dedicated TSL game-time-aware closing trigger script."
        ),
        "closing_offsets_h": CLOSING_TARGET_OFFSETS_H,
        "daemon_interval_min": 15,
        "scheduler_file": "wbc_backend/mlb_data/odds_capture_scheduler.py",
        "function_to_extend": "determine_capture_windows",
        "missing_input": "WBC/NPB game_times not read by determine_capture_windows()",
    },
    "matches_needing_closing_count": len(matches_needing_closing),
    "matches_needing_closing": matches_needing_closing,
}

with open(SCHEDULE_OUT, "w", encoding="utf-8") as f:
    json.dump(schedule_payload, f, ensure_ascii=False, indent=2)

print(f"  Written {len(json.dumps(schedule_payload))//1024}KB")
print(f"\n[P26] Done.")
