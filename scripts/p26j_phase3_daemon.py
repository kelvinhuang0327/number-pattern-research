#!/usr/bin/env python3
"""P26J Phase 3 – daemon continuity verification for 07:00–09:00Z 2026-05-21."""
import json
from datetime import datetime, timezone, timedelta

WINDOW_START = datetime(2026, 5, 21, 7, 0, 0, tzinfo=timezone.utc)
WINDOW_END   = datetime(2026, 5, 21, 9, 0, 0, tzinfo=timezone.utc)
TARGETS = ['3469930.1', '3469931.1']

def parse_dt(s):
    if not s:
        return None
    s = s.replace('Z', '+00:00')
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

# Read daemon heartbeat
heartbeat_rows = []
try:
    with open('logs/daemon_heartbeat.jsonl') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                heartbeat_rows.append(obj)
            except Exception:
                pass
except FileNotFoundError:
    print('WARNING: logs/daemon_heartbeat.jsonl not found')

# Filter to window
window_rows = []
for r in heartbeat_rows:
    ts = parse_dt(r.get('timestamp', '') or r.get('ts', '') or r.get('time', ''))
    if ts and WINDOW_START <= ts <= WINDOW_END:
        window_rows.append((ts, r))

window_rows.sort(key=lambda x: x[0])

print(f'=== PHASE 3 — Daemon Heartbeat 07:00–09:00Z ===')
print(f'Total heartbeat rows all time: {len(heartbeat_rows)}')
print(f'Heartbeat rows in window: {len(window_rows)}')

if window_rows:
    for ts, r in window_rows:
        status = r.get('status', r.get('event', ''))
        added = r.get('snapshots_added', r.get('added', ''))
        skipped = r.get('snapshots_skipped', r.get('skipped', ''))
        fetched = r.get('fetched', r.get('fetch_ok', ''))
        print(f'  {ts.isoformat()} | status={status} | added={added} | skipped={skipped} | fetch_ok={fetched}')
else:
    print('  NO heartbeat rows found in 07:00–09:00Z window')

# Check last heartbeat before and after window
before = [(ts, r) for ts, r in [(parse_dt(r2.get('timestamp','') or r2.get('ts','') or r2.get('time','')), r2) for r2 in heartbeat_rows] if ts and ts < WINDOW_START]
after  = [(ts, r) for ts, r in [(parse_dt(r2.get('timestamp','') or r2.get('ts','') or r2.get('time','')), r2) for r2 in heartbeat_rows] if ts and ts > WINDOW_END]

if before:
    before.sort(key=lambda x: x[0])
    last_before_ts, last_before = before[-1]
    print(f'\nLast heartbeat BEFORE window: {last_before_ts.isoformat()} | {last_before.get("status", last_before.get("event",""))}')
else:
    print('\nNo heartbeat before window found.')

if after:
    after.sort(key=lambda x: x[0])
    first_after_ts, first_after = after[0]
    print(f'First heartbeat AFTER window: {first_after_ts.isoformat()} | {first_after.get("status", first_after.get("event",""))}')
else:
    print('No heartbeat after window found.')

# Classify
if not heartbeat_rows:
    classification = 'DAEMON_STOPPED_BEFORE_CLOSING_WINDOW'
elif not window_rows:
    classification = 'DAEMON_STOPPED_BEFORE_CLOSING_WINDOW'
else:
    # Check if targets were captured
    target_in_window = False
    # Read odds history for window
    try:
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
                    fa_dt = parse_dt(obj.get('fetched_at', ''))
                    if fa_dt and WINDOW_START <= fa_dt <= WINDOW_END:
                        target_in_window = True
                        break
    except Exception:
        pass
    if target_in_window:
        classification = 'DAEMON_RAN_AND_CAPTURED_CLOSING'
    else:
        classification = 'DAEMON_RAN_BUT_SOURCE_DID_NOT_RETURN_TARGETS'

print(f'\nDAEMON_CLASSIFICATION: {classification}')

# Also check capture schedule
print('\n=== odds_capture_schedule.json ===')
try:
    with open('data/mlb_context/odds_capture_schedule.json') as f:
        schedule = json.load(f)
    # Show relevant entries for today
    if isinstance(schedule, list):
        for entry in schedule:
            gid = str(entry.get('match_id', entry.get('game_id', '')))
            if gid in TARGETS:
                print(f'  {entry}')
    elif isinstance(schedule, dict):
        print(json.dumps(schedule, indent=2)[:2000])
except FileNotFoundError:
    print('  File not found')
except Exception as e:
    print(f'  Error: {e}')
