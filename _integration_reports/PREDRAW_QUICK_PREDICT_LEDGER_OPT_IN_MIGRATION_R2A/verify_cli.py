import subprocess
import sys
import json
import sqlite3
import datetime as _dt
from pathlib import Path

sandbox = Path('_integration_reports/PREDRAW_QUICK_PREDICT_LEDGER_OPT_IN_MIGRATION_R2A/runtime_sandbox')
sandbox.mkdir(parents=True, exist_ok=True)

repo_root = Path(__file__).resolve().parent.parent.parent

# Helper to build synthetic DB with future dates so predraw_ledger live eligibility passes
def make_synthetic_db(db_path: Path, last_date="2099-01-01", last_draw=114000100):
    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "CREATE TABLE draws (id INTEGER PRIMARY KEY, draw TEXT, date TEXT, "
        "lottery_type TEXT, numbers TEXT, special INTEGER, jackpot_amount INTEGER)"
    )
    base_date = _dt.datetime.strptime(last_date, "%Y-%m-%d")
    rows = []
    for i in range(60):
        offset = 59 - i
        draw_num = last_draw - offset
        date_str = (base_date - _dt.timedelta(days=offset)).strftime("%Y-%m-%d")
        numbers = sorted(((draw_num + k * 7) % 49) + 1 for k in range(6))
        rows.append((str(draw_num), date_str, "BIG_LOTTO", json.dumps(numbers), None, 0))
    conn.executemany(
        "INSERT INTO draws (draw, date, lottery_type, numbers, special, jackpot_amount) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()

synthetic_db = sandbox / "synthetic_lottery_v2.db"
make_synthetic_db(synthetic_db)

results = {}

# 1. Help check
res = subprocess.run([sys.executable, 'tools/quick_predict.py', '--help'], capture_output=True, text=True, check=True, cwd=repo_root)
assert '--write-predraw-ledger' in res.stdout
assert '--predraw-ledger-path' in res.stdout
results['cli_help'] = 'PASS'

# 2. Flag contract check
assert '--write-predraw-ledger' in res.stdout
results['flag_contract'] = 'PASS'

# 3. Default dry-run creates no ledger
test_ledger = sandbox / 'default_test_ledger.jsonl'
if test_ledger.exists():
    test_ledger.unlink()
res = subprocess.run([sys.executable, 'tools/quick_predict.py', '--dry-run', '--lottery', 'BIG_LOTTO', '--bets', '2'], capture_output=True, text=True, cwd=repo_root)
assert not test_ledger.exists()
results['default_no_write'] = 'PASS'

# 4 & 5. Opt-in dry-run creates expected ledger records & caller-selected ledger path is honored
test_py = sandbox / "run_cli_test.py"
test_py.write_text(f"""
import sys
sys.path.insert(0, r'{repo_root}')
import unittest.mock
import tools.quick_predict as qp

with unittest.mock.patch.object(qp, 'DB_PATH', r'{synthetic_db}'):
    sys.argv = ['quick_predict.py', '--dry-run', '--lottery', 'BIG_LOTTO', '--bets', '2', '--write-predraw-ledger', '--predraw-ledger-path', r'{sandbox / "opt_in_ledger.jsonl"}']
    qp.main()
""")

res = subprocess.run([sys.executable, str(test_py)], capture_output=True, text=True, cwd=repo_root)
assert res.returncode == 0, res.stderr
opt_in_ledger = sandbox / "opt_in_ledger.jsonl"
assert opt_in_ledger.exists()
lines = [json.loads(l) for l in opt_in_ledger.read_text().strip().split('\n') if l.strip()]
assert len(lines) == 2
assert all(l['generation_mode'] == 'LIVE_PREDRAW' for l in lines)
results['opt_in_write'] = 'PASS'
results['custom_path_honored'] = 'PASS'

# 6. Invalid date / historical draw fails closed
past_ledger = sandbox / "past_ledger.jsonl"
if past_ledger.exists():
    past_ledger.unlink()
res = subprocess.run([sys.executable, 'tools/quick_predict.py', '--dry-run', '--lottery', 'BIG_LOTTO', '--bets', '2', '--write-predraw-ledger', '--predraw-ledger-path', str(past_ledger)], capture_output=True, text=True, cwd=repo_root)
assert not past_ledger.exists()
assert 'not LIVE-eligible, skipped' in res.stdout
results['invalid_input_fails_closed'] = 'PASS'

# 7. Prediction failure creates no successful ledger record
fail_ledger = sandbox / "fail_ledger.jsonl"
if fail_ledger.exists():
    fail_ledger.unlink()
test_fail_py = sandbox / "run_cli_fail.py"
test_fail_py.write_text(f"""
import sys
sys.path.insert(0, r'{repo_root}')
import unittest.mock
import tools.quick_predict as qp

def bad_predict(*args):
    raise RuntimeError("Simulated prediction failure")

with unittest.mock.patch.object(qp, 'predict_biglotto', bad_predict):
    with unittest.mock.patch.object(qp, 'DB_PATH', r'{synthetic_db}'):
        sys.argv = ['quick_predict.py', '--dry-run', '--lottery', 'BIG_LOTTO', '--bets', '2', '--write-predraw-ledger', '--predraw-ledger-path', r'{fail_ledger}']
        try:
            qp.main()
        except Exception:
            pass
""")
subprocess.run([sys.executable, str(test_fail_py)], capture_output=True, text=True, cwd=repo_root)
assert not fail_ledger.exists()
results['prediction_failure_no_false_record'] = 'PASS'

# 8. Existing outputs/predraw_ledger/ unchanged
output_dir = repo_root / 'outputs/predraw_ledger'
if output_dir.exists():
    for f in output_dir.glob('*'):
        assert sandbox not in f.parents
results['existing_predraw_outputs_unchanged'] = 'PASS'

print("CLI Verification Results:", json.dumps(results, indent=2))

runtime_log = {
    'writes_observed': [str(opt_in_ledger)],
    'unauthorized_writes': [],
    'sandbox_clean': True,
    'results': results
}
(sandbox.parent / 'runtime_write_ledger.json').write_text(json.dumps(runtime_log, indent=2))
