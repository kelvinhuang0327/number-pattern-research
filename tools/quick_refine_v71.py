#!/usr/bin/env python3
import sys
import os
import json
import sqlite3
import numpy as np
import logging
from typing import List, Dict
from scipy.stats import binomtest

project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.models.multi_bet_optimizer import MultiBetOptimizer
from lottery_api.common import get_lottery_rules
from tools.biglotto_triple_strike import fourier_rhythm_bet, cold_numbers_bet, tail_balance_bet

# Re-import filter logic from existing script
import importlib.util
spec = importlib.util.spec_from_file_location("refine_v71", os.path.join(project_root, "tools/refine_strategies_v71.py"))
refine_v71 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(refine_v71)

def run_quick_audit(lottery_type='BIG_LOTTO', periods=50):
    print(f"Executing Quick Audit: {lottery_type} ({periods} periods)")
    refine_v71.run_refinement_audit(lottery_type, periods)

if __name__ == "__main__":
    run_quick_audit('BIG_LOTTO', 50)
    run_quick_audit('POWER_LOTTO', 50)
