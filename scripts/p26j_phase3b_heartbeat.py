#!/usr/bin/env python3
"""P26J Phase 3b - detailed daemon heartbeat inspection in window."""
import json
from datetime import datetime, timezone

WINDOW_START = datetime(2026, 5, 21, 7, 0, 0, tzinfo=timezone.utc)
WINDOW_END   = datetime(2026, 5, 21, 9, 10, 0, tzinfo=timezone.utc)

def parse_dt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except Exception:
        return None

window_rows = []
with open('logs/daemon_heartbeat.jsonl') as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        ts_raw = obj.get('timestamp', '') or obj.get('ts', '') or obj.get('time', '')
        ts = parse_dt(ts_raw)
        if ts and WINDOW_START <= ts <= WINDOW_END:
            window_rows.append((ts, obj))

window_rows.sort(key=lambda x: x[0])
print(f'Daemon heartbeat rows in 07:00-09:10Z: {len(window_rows)}')
for ts, r in window_rows:
    r2 = dict(r)
    r2.pop('timestamp', None)
    print(f'{ts.isoformat()[:19]} | {json.dumps(r2)[:400]}')
