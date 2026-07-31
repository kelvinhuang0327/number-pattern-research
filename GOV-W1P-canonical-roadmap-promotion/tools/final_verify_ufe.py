#!/usr/bin/env python3
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from tools.verify_strategy_longterm import UnifiedAuditor
from tools.predict_ultimate_feature_ensemble import ultimate_ensemble_predict

def run_final_audit(lottery='BIG_LOTTO', n=500):
    auditor = UnifiedAuditor(lottery_type=lottery)
    
    # Bridge for the auditor
    def ufe_bridge(history, num_bets=2):
        # Suppress prints from UFE during audit to keep it clean
        # import contextlib, io
        # with contextlib.redirect_stdout(io.StringIO()):
        return ultimate_ensemble_predict(history, lottery_type=lottery, num_bets=num_bets)

    print(f"🏁 FINAL AUDIT: Dynamic Ultimate Feature Ensemble (UFE)")
    print(f"Target: {lottery}, N={n}")
    auditor.audit(ufe_bridge, n=n, num_bets=2)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='BIG_LOTTO')
    parser.add_argument('--n', type=int, default=500)
    args = parser.parse_args()
    run_final_audit(args.lottery, args.n)
