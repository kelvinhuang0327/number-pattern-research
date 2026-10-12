import json
from pathlib import Path
from datetime import date, timedelta

CODE_TO_NAME = {
    'AUS': 'Australia', 'BRA': 'Brazil', 'CAN': 'Canada', 'COL': 'Colombia',
    'CUB': 'Cuba', 'CZE': 'Czechia', 'DOM': 'Dominican Republic', 'GBR': 'Great Britain',
    'ISR': 'Israel', 'ITA': 'Italy', 'JPN': 'Japan', 'KOR': 'Korea',
    'MEX': 'Mexico', 'NED': 'Kingdom of the Netherlands', 'NIC': 'Nicaragua',
    'PAN': 'Panama', 'PUR': 'Puerto Rico', 'TPE': 'Chinese Taipei',
    'USA': 'United States', 'VEN': 'Venezuela',
}

snap = json.loads(Path('data/wbc_2026_authoritative_snapshot.json').read_text())
live = json.loads(Path('data/wbc_2026_live_scores.json').read_text())

# Build lookup: (date, home_name, away_name) and (date, away_name, home_name) with ±1 day
live_lookup = {}
for g in live['games']:
    d = g['date']
    d_obj = date.fromisoformat(d)
    for delta in [-1, 0, 1]:
        dd = (d_obj + timedelta(days=delta)).isoformat()
        live_lookup.setdefault((dd, g['home'], g['away']), g)
        # also try swapped for venue confusion
        live_lookup.setdefault((dd, g['away'], g['home']), g)

matched = []
unmatched = []
for g in snap['games']:
    hname = CODE_TO_NAME.get(g['home'], g['home'])
    aname = CODE_TO_NAME.get(g['away'], g['away'])
    found = None
    for delta in [-1, 0, 1]:
        d_obj = date.fromisoformat(g['date'])
        dd = (d_obj + timedelta(days=delta)).isoformat()
        key1 = (dd, hname, aname)  # canonical orientation
        key2 = (dd, aname, hname)  # swapped
        if key1 in live_lookup:
            found = live_lookup[key1]
            break
        if key2 in live_lookup:
            found = live_lookup[key2]
            break
    if found:
        matched.append((g['canonical_game_id'], found))
    else:
        unmatched.append(f"{g['canonical_game_id']}: {g['date']} {aname}@{hname}")

print(f'Matched: {len(matched)}/40')
for cid, lg in matched[:8]:
    print(f'  {cid}: {lg["away"]}@{lg["home"]} {lg["away_score"]}-{lg["home_score"]} [{lg["status"]}]')
print(f'Unmatched ({len(unmatched)}):')
for u in unmatched:
    print(f'  {u}')
