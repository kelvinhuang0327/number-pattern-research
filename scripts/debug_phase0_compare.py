"""
Phase 0 Final — Compare wbc_pool_results source vs postgame_results.jsonl ground truth.
Check if ANY game has a different home_win assignment.
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.activation.wbc_pool_results import build_settlement_records, CODE_TO_NAME

# Our current settlement data (from live_scores matching)
current = build_settlement_records()

# Ground truth from postgame_results.jsonl using actual_result.home_win
pg_path = "data/wbc_backend/reports/postgame_results.jsonl"
postgame_gt = {}
if os.path.exists(pg_path):
    for line in open(pg_path):
        try:
            r = json.loads(line)
            gid = r.get("game_id")
            ar = r.get("actual_result", {})
            if gid and ar and ar.get("home_score") is not None:
                postgame_gt[gid] = {
                    "home_win": 1 if ar.get("home_win") else 0,
                    "home_score": ar.get("home_score"),
                    "away_score": ar.get("away_score"),
                    "home_team": r.get("home_team"),
                    "away_team": r.get("away_team"),
                }
        except:
            pass

print(f"Current settlement records: {len(current)}")
print(f"Postgame GT records: {len(postgame_gt)}")
print()

# Now compare using the AUTHORITATIVE SNAPSHOT to get canonical home/away names  
snap = json.loads(open("data/wbc_2026_authoritative_snapshot.json").read())
snap_map = {}
for g in snap["games"]:
    gid = g["canonical_game_id"]
    snap_map[gid] = {
        "home_code": g["home"],
        "away_code": g["away"],
        "home_name": CODE_TO_NAME.get(g["home"], g["home"]),
        "away_name": CODE_TO_NAME.get(g["away"], g["away"]),
    }

print("=" * 90)
print(f"{'GID':5} {'snap_home':15} {'snap_away':15} {'curr_hw':8} {'pg_hw':6} {'match':8}")
print("-" * 90)

mismatches = 0
for gid in sorted(current.keys()):
    curr = current[gid]
    pg = postgame_gt.get(gid)
    snap_info = snap_map.get(gid, {})
    
    curr_hw = curr["home_win"]
    snap_home = snap_info.get("home_name", "?")
    snap_away = snap_info.get("away_name", "?")
    
    if pg:
        pg_hw = pg["home_win"]
        pg_home = pg.get("home_team", "?")
        pg_away = pg.get("away_team", "?")
        
        # Check if home teams match (snap home == pg home)
        home_matches = snap_home.lower() in pg_home.lower() if pg_home else "?"
        
        # Direct home_win comparison
        hw_match = "✅" if curr_hw == pg_hw else "❌ MISMATCH"
        if curr_hw != pg_hw:
            mismatches += 1
            print(f"{gid:5} {snap_home:15} {snap_away:15} curr_hw={curr_hw}  pg_hw={pg_hw}  {hw_match}")
            print(f"       → pg home={pg_home}, pg away={pg_away}, snap home={snap_home}")
        else:
            print(f"{gid:5} {snap_home:15} {snap_away:15} curr_hw={curr_hw}  pg_hw={pg_hw}  {hw_match}")
    else:
        print(f"{gid:5} {snap_home:15} {snap_away:15} curr_hw={curr_hw}  (no pg data)")

print("=" * 90)
print(f"Mismatches: {mismatches}")
print()

# Also check if postgame orientation matches snap orientation for any mismatch
print("\n--- POSTGAME RECORDS CROSS-REFERENCE ---")
for gid, pg in sorted(postgame_gt.items()):
    si = snap_map.get(gid, {})
    snap_home = si.get("home_name", "?")
    pg_home = pg.get("home_team", "?")
    if snap_home and pg_home and snap_home.lower() not in pg_home.lower() and pg_home.lower() not in snap_home.lower():
        print(f"{gid}: ORIENTATION DIFF: snap_home={snap_home!r} vs pg_home={pg_home!r}")
