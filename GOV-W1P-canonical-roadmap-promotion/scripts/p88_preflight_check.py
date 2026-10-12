import sqlite3, os, sys
from pathlib import Path


def _repo_root():
    return Path(__file__).resolve().parent.parent


def _canonical_db_path():
    return _repo_root() / "lottery_api" / "data" / "lottery_v2.db"


def _resolve_db_path(db_path=None):
    candidate = _canonical_db_path() if db_path is None else Path(db_path)
    if db_path is not None and not candidate.is_absolute():
        raise ValueError("db_path must be absolute; use None for the canonical lottery_v2.db")
    if not candidate.exists():
        raise FileNotFoundError(f"Lottery DB path does not exist: {candidate}")
    if not candidate.is_file():
        raise FileNotFoundError(f"Lottery DB path is not a regular file: {candidate}")
    return str(candidate)

con = sqlite3.connect(_resolve_db_path())
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
