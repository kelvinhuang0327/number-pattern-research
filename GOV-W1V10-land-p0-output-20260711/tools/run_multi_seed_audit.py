import subprocess
import re
import numpy as np
import argparse
from typing import List, Dict

def run_backtest(seed: int, periods: int, bets: int) -> Dict[str, float]:
    """執行單個種子的回測並解析結果"""
    cmd = [
        "python3", "lottery_api/backtest_power_2025.py",
        "--periods", str(periods),
        "--bets", str(bets),
        "--seed", str(seed)
    ]
    print(f"🚀 Running Seed {seed}...")
    try:
        result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8')
        
        # 解析命中率
        hit_rate_match = re.search(r"Overall Hit Rate: ([\d.]+)%", result)
        overall_hit_rate = float(hit_rate_match.group(1)) if hit_rate_match else 0.0
        
        # 解析特別號命中
        special_hits_match = re.search(r"Special Number Hits:  (\d+) draws", result)
        special_hits_count = int(special_hits_match.group(1)) if special_hits_match else 0
        special_hit_rate = (special_hits_count / periods) * 100
        
        # 解析 Match 分佈
        m3_match = re.search(r"Max Match 3:  (\d+) draws", result)
        m3_count = int(m3_match.group(1)) if m3_match else 0
        m3_rate = (m3_count / periods) * 100

        return {
            "seed": seed,
            "overall_hit_rate": overall_hit_rate,
            "special_hit_rate": special_hit_rate,
            "m3_rate": m3_rate
        }
    except Exception as e:
        print(f"❌ Seed {seed} failed: {e}")
        return None

def main():
    parser = argparse.ArgumentParser(description='Multi-Seed Robustness Audit')
    parser.add_argument('--seeds', type=int, nargs='+', default=[42, 123, 777, 2025, 999], help='List of random seeds')
    parser.add_argument('--periods', type=int, default=20, help='Periods per backtest')
    parser.add_argument('--bets', type=int, default=4, help='Bets per draw')
    args = parser.parse_args()

    results = []
    for seed in args.seeds:
        res = run_backtest(seed, args.periods, args.bets)
        if res:
            results.append(res)
            print(f"✅ Seed {seed}: Hit Rate={res['overall_hit_rate']:.1f}%, Special={res['special_hit_rate']:.1f}%")

    if not results:
        print("❌ No results to aggregate")
        return

    # 聚合結果
    hit_rates = [r['overall_hit_rate'] for r in results]
    special_rates = [r['special_hit_rate'] for r in results]
    m3_rates = [r['m3_rate'] for r in results]

    print("\n" + "="*50)
    print("🏆 MULTI-SEED AUDIT SUMMARY")
    print("="*50)
    print(f"Seeds tested: {len(results)} ({args.seeds})")
    print(f"Periods per seed: {args.periods}")
    print("-" * 50)
    print(f"Overall Hit Rate:    {np.mean(hit_rates):.2f}% (±{np.std(hit_rates):.2f}%)")
    print(f"Special Hit Rate:    {np.mean(special_rates):.2f}% (±{np.std(special_rates):.2f}%)")
    print(f"Match 3+ Rate:       {np.mean(m3_rates):.2f}% (±{np.std(m3_rates):.2f}%)")
    print("="*50)

    # 魯棒性判斷
    if np.mean(special_rates) >= 20.0 and np.std(special_rates) < 10.0:
        print("💎 STATUS: HIGHLY ROBUST (Special Number Alpha is Significant)")
    elif np.mean(special_rates) >= 15.0:
        print("✅ STATUS: MODERATELY ROBUST")
    else:
        print("⚠️ STATUS: LOW ROBUSTNESS / HIGH VARIANCE")

if __name__ == "__main__":
    main()
