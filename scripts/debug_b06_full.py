import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# B06 schedule entry
from data.wbc_pool_b import _POOL_B_SCHEDULE, list_wbc_matches_b
for g in _POOL_B_SCHEDULE:
    if g['game_id'] == 'B06':
        print("B06 SCHEDULE ENTRY:")
        print(json.dumps(g, indent=2, default=str))
        break

# B06 match data
from data.wbc_pool_b import fetch_wbc_match_b
md = fetch_wbc_match_b("B06")
print("\nB06 MatchData:")
print("  home:", getattr(md, 'home', None))
print("  away:", getattr(md, 'away', None))
home_obj = getattr(md, 'home', None)
away_obj = getattr(md, 'away', None)
print("  home code:", getattr(home_obj, 'code', None) if home_obj else None)
print("  away code:", getattr(away_obj, 'code', None) if away_obj else None)
print("  home name:", getattr(home_obj, 'name', None) if home_obj else None)
print("  away name:", getattr(away_obj, 'name', None) if away_obj else None)

# Actual result from live scores
snap_live = json.loads(open('data/wbc_2026_live_scores.json').read())
for g in snap_live['games']:
    if 'Mexico' in (g['home'], g['away']) and 'Brazil' in (g['home'], g['away']):
        date = g['date']
        if '2026-03' in date:
            print("\nB06 LIVE SCORE:")
            print(f"  date: {g['date']}, home={g['home']} score={g['home_score']}, away={g['away']} score={g['away_score']}")
            print(f"  status: {g['status']}")
