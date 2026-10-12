#!/usr/bin/env python3
"""Phase 52A verification script."""
import json
from pathlib import Path

sp_path = Path("data/mlb_2025/derived/mlb_2025_starting_pitcher_features_phase52.jsonl")
rows = [json.loads(l) for l in sp_path.read_text().splitlines() if l.strip()]

total = len(rows)
matched = sum(1 for r in rows if r.get("matched"))
avail = sum(1 for r in rows if r.get("sp_fip_delta_available"))
pit_safe = sum(1 for r in rows if r.get("point_in_time_safe"))
audit_present = sum(1 for r in rows if r.get("audit_hash"))
hist = sum(1 for r in rows if "historical_proxy" in str(r.get("stat_source", "")))
fallback = sum(1 for r in rows if "league_average" in str(r.get("stat_source", "")))
mixed = sum(1 for r in rows if r.get("stat_source") == "mixed")
home_present = sum(1 for r in rows if r.get("home_probable_pitcher_name", "") not in ("", "unknown"))
away_present = sum(1 for r in rows if r.get("away_probable_pitcher_name", "") not in ("", "unknown"))

unique_starters = set()
for r in rows:
    unique_starters.add(r.get("home_probable_pitcher_name", ""))
    unique_starters.add(r.get("away_probable_pitcher_name", ""))
unique_starters.discard("")
unique_starters.discard("unknown")

deltas = [r.get("sp_fip_delta", 0) for r in rows]
nonzero = sum(1 for d in deltas if abs(d) > 0.001)

print("=== SP Backfill Statistics ===")
print(f"total_rows:               {total}")
print(f"matched_rows:             {matched}")
print(f"match_rate:               {matched/total*100:.1f}%")
print(f"home_starter_present:     {home_present} ({home_present/total*100:.1f}%)")
print(f"away_starter_present:     {away_present} ({away_present/total*100:.1f}%)")
print(f"unique_starters:          {len(unique_starters)}")
print(f"sp_fip_available:         {avail} ({avail/total*100:.1f}%)")
print(f"historical_proxy:         {hist} ({hist/total*100:.1f}%)")
print(f"league_avg_fallback:      {fallback} ({fallback/total*100:.1f}%)")
print(f"mixed_source:             {mixed} ({mixed/total*100:.1f}%)")
print(f"point_in_time_safe:       {pit_safe} ({pit_safe/total*100:.1f}%)")
print(f"audit_hash_present:       {audit_present} ({audit_present/total*100:.1f}%)")
print(f"fip_delta_nonzero:        {nonzero} ({nonzero/total*100:.1f}%)")
print(f"fip_delta_mean:           {sum(deltas)/total:.4f}")
print(f"fip_delta_min:            {min(deltas):.4f}")
print(f"fip_delta_max:            {max(deltas):.4f}")

# context injection check
ctx_path = Path("data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl")
ctx_rows = [json.loads(l) for l in ctx_path.read_text().splitlines() if l.strip()]
ctx_total = len(ctx_rows)
ctx_avail = sum(1 for r in ctx_rows if r.get("p0_features", {}).get("sp_fip_delta_available"))
ctx_fv = sum(1 for r in ctx_rows if r.get("p0_features", {}).get("feature_version") == "phase52_sp_context_v1")
ctx_src = sum(1 for r in ctx_rows if r.get("p0_features", {}).get("sp_context_source"))
ctx_hash = sum(1 for r in ctx_rows if r.get("p0_features", {}).get("sp_context_audit_hash"))
ctx_prf = sum(1 for r in ctx_rows if "park_run_factor" in r.get("p0_features", {}))
ctx_sgi = sum(1 for r in ctx_rows if "season_game_index" in r.get("p0_features", {}))

print("\n=== Context Injection Verification ===")
print(f"context_total:            {ctx_total}")
print(f"sp_fip_available(ctx):    {ctx_avail} ({ctx_avail/ctx_total*100:.1f}%)")
print(f"feature_version_correct:  {ctx_fv} ({ctx_fv/ctx_total*100:.1f}%)")
print(f"sp_context_source set:    {ctx_src} ({ctx_src/ctx_total*100:.1f}%)")
print(f"sp_context_audit_hash:    {ctx_hash} ({ctx_hash/ctx_total*100:.1f}%)")
print(f"park_run_factor preserved:{ctx_prf} ({ctx_prf/ctx_total*100:.1f}%)")
print(f"season_game_index prsrvd: {ctx_sgi} ({ctx_sgi/ctx_total*100:.1f}%)")
