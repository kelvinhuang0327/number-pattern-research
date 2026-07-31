#!/usr/bin/env python3
"""P26J Phase 2 – post-window target pair verification."""
import json
from datetime import datetime, timezone

TARGETS = ['3469930.1', '3469931.1']

def parse_dt(s):
    if not s:
        return None
    s = s.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

rows = {t: [] for t in TARGETS}
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
        if mid in TARGETS:
            rows[mid].append(obj)

print('=== PHASE 2 — Gap Analysis ===')
pair_delta = 0
for t in TARGETS:
    pregame_rows = []
    closing_rows = []
    fc_rows = []
    db_rows = []
    for r in rows[t]:
        fa_dt = parse_dt(r.get('fetched_at', ''))
        gt_dt = parse_dt(r.get('game_time', ''))
        gap_h = (gt_dt - fa_dt).total_seconds() / 3600 if fa_dt and gt_dt else None
        cr = r.get('capture_reason', '')
        fc = r.get('force_closing_snapshot', r.get('force_closing', False))
        db = r.get('dedup_bypassed', False)
        mkts = r.get('markets', {})
        mkt_count = len(mkts) if isinstance(mkts, dict) else 0
        gap_str = f'{gap_h:.2f}' if gap_h is not None else 'N/A'
        print(f'  [{t}] fetched_at={r.get("fetched_at","")[:19]} gap_h={gap_str} cr={cr!r:20s} fc={str(fc):5s} db={str(db):5s} mkts={mkt_count}')
        if gap_h is not None:
            if gap_h >= 4.0:
                pregame_rows.append(r)
            if 0.0 <= gap_h <= 2.0:
                closing_rows.append(r)
        if fc:
            fc_rows.append(r)
        if db:
            db_rows.append(r)
    has_pregame = len(pregame_rows) > 0
    has_closing = len(closing_rows) > 0
    has_any_market = any(
        len(r.get('markets', {})) > 0
        for r in rows[t]
        if isinstance(r.get('markets', {}), dict)
    )
    print(f'  SUMMARY [{t}]: total_rows={len(rows[t])} pregame={len(pregame_rows)} closing={len(closing_rows)} fc_labeled={len(fc_rows)} db_labeled={len(db_rows)} any_market={has_any_market}')
    if has_pregame and has_closing:
        status = 'COMPLETE_PAIR_FORMED'
        pair_delta += 1
    elif has_pregame and not has_closing:
        status = 'PREGAME_ONLY_NO_CLOSING'
    elif not has_pregame and has_closing:
        status = 'CLOSING_ONLY_NO_PREGAME'
    elif not rows[t]:
        status = 'NO_TARGET_ROWS'
    else:
        status = 'AMBIGUOUS_TIMESTAMP_OR_MAPPING'
    print(f'  PAIR_STATUS [{t}]: {status}')
    print()

print(f'target_pair_delta = {pair_delta}  (both complete = {pair_delta == 2})')
