import sqlite3, os, sys

con = sqlite3.connect('lottery_api/data/lottery_v2.db')
cur = con.cursor()
cur.execute('SELECT COUNT(*) FROM strategy_prediction_replays')
rows = cur.fetchone()[0]
cur.execute("SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'")
max_draw = cur.fetchone()[0]
cur.execute("SELECT draw,date,numbers,special FROM draws WHERE lottery_type='POWER_LOTTO' AND CAST(draw AS INTEGER)=115000041")
draw_row = cur.fetchone()
cur.execute('SELECT id,strategy_id,dry_run,truth_level FROM strategy_prediction_replays WHERE id IN (46961,46962) ORDER BY id')
sentinels = cur.fetchall()
con.close()

print(f'replay_rows={rows}')
print(f'max_draw={max_draw}')
print(f'draw_row={draw_row}')
for s in sentinels:
    print(f'sentinel id={s[0]} strat={s[1]} dry_run={s[2]} tl={s[3]}')

p87_files = [
    'docs/replay/p87_live_operations_runbook_20260526.md',
    'outputs/replay/p87_live_operations_runbook_20260526.json',
    'tests/test_p87_live_operations_runbook.py',
]
for f in p87_files:
    print(f'P87_ARTIFACT {f}={os.path.exists(f)}')

baseline_ok = (
    rows == 46962
    and max_draw == 115000041
    and draw_row is not None
    and len(sentinels) == 2
    and all(s[2] == 0 for s in sentinels)
    and all(os.path.exists(f) for f in p87_files)
)
print('PREFLIGHT_PASS' if baseline_ok else 'PREFLIGHT_FAIL')
