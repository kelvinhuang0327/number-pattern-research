#!/usr/bin/env python3
import json
import sqlite3
import os
import numpy as np
from scipy import stats
from collections import Counter

from pathlib import Path


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


def _p291u_connect_resolved(db_path):
    return sqlite3.connect(str(_p291u_resolve_db_path(db_path)))


DB_PATH = str(_p291u_resolve_db_path())

# 49 Lotto Configuration
POOL = 49
PICK = 6 # Using 6 regular numbers from Big Lotto

def load_draws():
    conn = _p291u_connect_resolved(DB_PATH)
    cursor = conn.cursor()
    # BIG_LOTTO numbers usually contain 7 numbers (6 + special)
    cursor.execute("""
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type = 'BIG_LOTTO'
        ORDER BY date ASC, draw ASC
    """)
    rows = cursor.fetchall()
    conn.close()
    draws = []
    for draw_id, date, numbers_str in rows:
        nums = json.loads(numbers_str)
        # 49 Lotto ONLY uses the first 6 regular numbers
        regular_nums = sorted(nums[:6]) 
        draws.append({'draw': draw_id, 'date': date, 'numbers': regular_nums})
    return draws

def analyze_best_lags_49(draws):
    N = len(draws)
    p_theoretical = PICK / POOL
    max_lag = 20
    
    number_best_lags = {}
    
    print(f"Analyzing Best Lags (1-{max_lag}) for 49 Lotto ({N} draws)...")
    
    for n in range(1, POOL + 1):
        lags_p = []
        for lag in range(1, max_lag + 1):
            obs = 0
            total = 0
            for i in range(lag, N):
                if n in draws[i-lag]['numbers']:
                    total += 1
                    if n in draws[i]['numbers']:
                        obs += 1
            if total > 50:
                try:
                    p = stats.binomtest(obs, total, p_theoretical, alternative='greater').pvalue
                except AttributeError:
                    p = stats.binom_test(obs, total, p_theoretical, alternative='greater')
                lags_p.append((lag, p, obs/total))
        
        if lags_p:
            lags_p.sort(key=lambda x: x[1])
            number_best_lags[n] = lags_p[0]
            
    sorted_nums = sorted(number_best_lags.items(), key=lambda x: x[1][1])
    
    print(f"\n{'Num':<5} {'Lag':<5} {'p-value':<15} {'Rate':<10} {'Edge':<10}")
    print("-" * 60)
    for n, (lag, p, rate) in sorted_nums[:15]:
        edge = rate - p_theoretical
        status = "🌟 HIGHLY SIG" if p < 0.01 else ("✅ SIG" if p < 0.05 else "")
        print(f"{n:<5} {lag:<5} {p:15.6f} {rate*100:6.2f}% {edge*100:+7.2f}% {status}")
        
    return number_best_lags, np.mean([x[1][1] for x in sorted_nums])

def main():
    draws = load_draws()
    best_lags, avg_p = analyze_best_lags_49(draws)
    
    print("\n" + "=" * 60)
    print("49 Lotto (Big Lotto Base) vs 39 Lotto 研究對比")
    print("=" * 60)
    print(f"49 Lotto 樣本數: {len(draws)} 期")
    print(f"49 Lotto 最佳滯後平均 p-value: {avg_p:.4f}")
    
    # Analyze global echo rate
    p_atleast1_theoretical = 1 - (stats.hypergeom.pmf(0, POOL, PICK, PICK))
    overlaps = []
    hits = 0
    for i in range(1, len(draws)):
        ov = len(set(draws[i-1]['numbers']) & set(draws[i]['numbers']))
        overlaps.append(ov)
        if ov >= 1: hits += 1
    
    actual_rate = hits / (len(draws) - 1)
    print(f"1-Lag 回聲率: {actual_rate*100:.2f}% (理論: {p_atleast1_theoretical*100:.2f}%)")
    print(f"平均每期重疊數: {np.mean(overlaps):.4f} (理論: {PICK*PICK/POOL:.4f})")
    
    print("\n💡 結論預判:")
    if actual_rate > p_atleast1_theoretical + 0.02:
        print(">>> 49 樂合彩展現了比 39 樂合彩更強的【短期回聲慣性】。")
    else:
        print(">>> 49 樂合彩在全局層面同樣接近隨機。")

if __name__ == "__main__":
    main()
