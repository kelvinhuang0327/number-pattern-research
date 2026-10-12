import json, csv

with open('outputs/predictions/PAPER/2026-05-11/mlb_odds_with_model_probabilities.csv') as f:
    csv_rows = list(csv.DictReader(f))

with open('data/mlb_context/bullpen_usage_3d.jsonl') as f:
    bullpen = [json.loads(l) for l in f if l.strip()]

with open('data/mlb_context/injury_rest.jsonl') as f:
    rest = [json.loads(l) for l in f if l.strip()]

print(f'CSV rows: {len(csv_rows)}, Bullpen rows: {len(bullpen)}, Rest rows: {len(rest)}')

# Check positional alignment
match = 0
for i, (cr, bp) in enumerate(zip(csv_rows[:20], bullpen[:20])):
    away_norm = cr['Away'].upper().replace(' ', '_')
    home_norm = cr['Home'].upper().replace(' ', '_')
    if away_norm in bp['game_id'] and home_norm in bp['game_id']:
        match += 1
    else:
        print(f'  MISMATCH {i}: CSV: {cr["Away"]} vs {cr["Home"]}, BULLPEN: {bp["game_id"]}')
print(f'Positional match first 20: {match}/20')

# Check rest days availability
rest_available = sum(1 for r in rest if r.get('rest_days_home') is not None)
print(f'Rest days available: {rest_available}/{len(rest)}')

# Sample rest data
for r in rest[:5]:
    print(f'  rest_home={r.get("rest_days_home")}, rest_away={r.get("rest_days_away")}')
