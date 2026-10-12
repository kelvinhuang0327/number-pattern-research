
import sys
sys.path.insert(0, r'/Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged')
import unittest.mock
import tools.quick_predict as qp

with unittest.mock.patch.object(qp, 'DB_PATH', r'_integration_reports/PREDRAW_QUICK_PREDICT_LEDGER_OPT_IN_MIGRATION_R2A/runtime_sandbox/synthetic_lottery_v2.db'):
    sys.argv = ['quick_predict.py', '--dry-run', '--lottery', 'BIG_LOTTO', '--bets', '2', '--write-predraw-ledger', '--predraw-ledger-path', r'_integration_reports/PREDRAW_QUICK_PREDICT_LEDGER_OPT_IN_MIGRATION_R2A/runtime_sandbox/opt_in_ledger.jsonl']
    qp.main()
