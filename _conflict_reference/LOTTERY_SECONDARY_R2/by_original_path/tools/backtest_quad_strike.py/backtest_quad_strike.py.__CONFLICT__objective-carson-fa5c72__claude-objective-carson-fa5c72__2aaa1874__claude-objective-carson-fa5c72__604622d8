#!/usr/bin/env python3
"""
大樂透 Quad Strike (4注) 穩定性回測
================================
驗證 150/500/1500 期回測, 使用正確的 4注隨機基準 (7.25%)
"""
import sqlite3
import json
import sys
import os
import numpy as np
from pathlib import Path
from collections import Counter

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / 'lottery_api'))

# Import the strategy from the newly created tool
from tools.predict_biglotto_quad_strike import generate_quad_strike


def _p291u_repo_root():
    current = Path(__file__)
    if not current.is_absolute():
        raise FileNotFoundError(f"Source file path is not absolute: {current}")
    for parent in (current.parent, *current.parents):
        if (parent / "lottery_api").is_dir():
            return parent
    raise FileNotFoundError(f"Unable to locate repository root from source file: {current}")


def _p291u_default_db_path():
    db_path = _p291u_repo_root() / "lottery_api" / "data" / "lottery_v2.db"
    if not db_path.is_file():
        raise FileNotFoundError(f"Default lottery DB path is missing or non-regular: {db_path}")
    return db_path


def _p291u_resolve_db_path(db_path=None):
    if db_path is None:
        return _p291u_default_db_path()
    path = Path(db_path)
    if not path.is_absolute():
        raise ValueError(f"Explicit DB path must be absolute: {db_path}")
    if not path.is_file():
        raise FileNotFoundError(f"Explicit DB path is missing or non-regular: {path}")
    return path


def _p291u_connect_resolved(db_path, *, uri=False):
    if uri:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    return sqlite3.connect(str(db_path))


BASELINE_4BET = 7.25 # 大樂透 4注 random M3+ rate (%)

def load_history():
    _p291u_db_path = _p291u_resolve_db_path()
    db_path = PROJECT_ROOT / 'lottery_api' / 'data' / 'lottery_v2.db'
    conn = _p291u_connect_resolved(_p291u_db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT draw, date, numbers, special FROM draws WHERE lottery_type=? ORDER BY date ASC",
        ('BIG_LOTTO',)
    )
    draws = []
    for row in cursor.fetchall():
        nums = json.loads(row[2]) if row[2] else []
        draws.append({
            'draw': row[0], 'date': row[1],
            'numbers': nums, 'special': row[3] or 0
        })
    conn.close()
    return draws

def run_backtest(test_periods=1500):
    all_draws = load_history()
    test_periods = min(test_periods, len(all_draws) - 500)
    
    hits_count = 0
    total = 0
    
    print(f"\n🔬 執行 Quad Strike (4注) 回測: 最近 {test_periods} 期")
    print(f"基準 (4注隨機): {BASELINE_4BET}%")
    
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 500: continue
        
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target_draw['numbers'])
        
        try:
            # 生成 4 注
            bets = generate_quad_strike(hist)
            
            best_match = 0
            for bet in bets[:4]:
                match = len(set(bet) & actual)
                best_match = max(best_match, match)
            
            if best_match >= 3:
                hits_count += 1
            
            total += 1
            if total % 100 == 0:
                print(f"  已完成 {total}/{test_periods} 期...")
        except Exception as e:
            continue
            
    if total == 0: return
    
    hit_rate = hits_count / total * 100
    edge = hit_rate - BASELINE_4BET
    
    print("=" * 60)
    print(f"📊 Quad Strike (4注) 回測結果 (最近 {total} 期)")
    print("-" * 60)
    print(f"  3+ 命中率: {hit_rate:.2f}%")
    print(f"  隨機基準 (4注): {BASELINE_4BET:.2f}%")
    print(f"  Edge: {edge:>+7.2f}%")
    print("=" * 60)
    
    if edge > 0.5:
        print("✅ STABLE (通過長期驗證)")
    elif edge > 0:
        print("⚠️ MARGINAL (微弱優勢)")
    else:
        print("❌ FAILED (比隨機差)")
    
    return hit_rate

if __name__ == "__main__":
    for period in [150, 500, 1500]:
        run_backtest(period)
