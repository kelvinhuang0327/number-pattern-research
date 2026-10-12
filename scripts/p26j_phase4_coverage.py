#!/usr/bin/env python3
"""P26J Phase 4 – COMPLETE_PAIR coverage recheck."""
import json
from datetime import datetime, timezone

BASELINE_COMPLETE_PAIR = 220
BOOTSTRAP_THRESHOLD = 300

def parse_dt(s):
    if not s:
        return None
    s = s.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

rows_by_match = {}
with open('data/tsl_odds_history.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        mid = str(obj.get('match_id', ''))
        if mid not in rows_by_match:
            rows_by_match[mid] = []
        rows_by_match[mid].append(obj)

complete_pairs = 0
pregame_only = 0
closing_only = 0
no_rows = 0
ambiguous = 0
total_fc_rows = 0
total_db_rows = 0
missing_pregame = 0
missing_closing = 0

for mid, rlist in rows_by_match.items():
    has_pregame = False
    has_closing = False
    for r in rlist:
        fa_dt = parse_dt(r.get('fetched_at', ''))
        gt_dt = parse_dt(r.get('game_time', ''))
        fc = r.get('force_closing_snapshot', r.get('force_closing', False))
        db = r.get('dedup_bypassed', False)
        if fc:
            total_fc_rows += 1
        if db:
            total_db_rows += 1
        if fa_dt and gt_dt:
            gap_h = (gt_dt - fa_dt).total_seconds() / 3600
            if gap_h >= 4.0:
                has_pregame = True
            if 0.0 <= gap_h <= 2.0:
                has_closing = True
    if has_pregame and has_closing:
        complete_pairs += 1
    elif has_pregame and not has_closing:
        pregame_only += 1
        missing_closing += 1
    elif not has_pregame and has_closing:
        closing_only += 1
        missing_pregame += 1
    else:
        no_rows += 1

print(f'=== PHASE 4 — Coverage Recheck ===')
print(f'Total match_ids in history: {len(rows_by_match)}')
print(f'COMPLETE_PAIR (current):     {complete_pairs}')
print(f'COMPLETE_PAIR (baseline):    {BASELINE_COMPLETE_PAIR}')
print(f'delta vs baseline:           {complete_pairs - BASELINE_COMPLETE_PAIR:+d}')
print(f'pregame_only:                {pregame_only}')
print(f'closing_only:                {closing_only}')
print(f'no_rows:                     {no_rows}')
print(f'missing_pregame:             {missing_pregame}')
print(f'missing_closing:             {missing_closing}')
print(f'total force_closing rows:    {total_fc_rows}')
print(f'total dedup_bypassed rows:   {total_db_rows}')
print()
if complete_pairs >= BOOTSTRAP_THRESHOLD:
    print(f'P25C BOOTSTRAP ELIGIBILITY: ELIGIBLE (>= {BOOTSTRAP_THRESHOLD})')
    print('STOP — report eligibility changed, do NOT run bootstrap unless explicitly authorized')
else:
    print(f'P25C BOOTSTRAP ELIGIBILITY: NOT ELIGIBLE ({complete_pairs} < {BOOTSTRAP_THRESHOLD})')
    print('bootstrap_ran = false — no change')
