#!/usr/bin/env python3
"""
自我演化策略發現系統 - OOS 驗證與統計嚴謹版
"""
import sys, os, json, time, argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from evolving_strategy_engine.data_loader import load_big_lotto_draws
from evolving_strategy_engine.evolution_engine import EvolutionEngine


def print_report(report: dict):
    print("\n" + "═" * 70)
    print("  🎰 自我演化策略發現系統 - 嚴格 P-Value 最終報告")
    print("═" * 70)
    
    print(f"\n📊 統計檢定基礎:")
    print(f"   總開獎期數: {report['total_draws']}")
    print(f"   測試策略數: {report['total_strategies_tested']} (多重比較)")
    print(f"   演化代數: {report['generations']}")
    print(f"   Bonferroni P-Value 門檻: p < {report.get('bonferroni_threshold', 0):.6f}")
    
    print(f"\n🏆 存活優勢排行榜 TOP 10 (M3+ 基線=1.86%):")
    print(f"   {'#':>3} {'Name':<35} {'EdgeM3':>8} {'M3_Hit':>8} {'P-Value':>8}")
    print(f"   {'─'*3} {'─'*35} {'─'*8} {'─'*8} {'─'*8}")
    for i, s in enumerate(report.get('1_leaderboard', [])[:10]):
        edge = s.get('edge_>=3', 0)
        hit3 = s.get('hit_rates', {}).get('>=3', 0)
        pval = s.get('params', {}).get('p_value', 1.0)
        print(f"   {i+1:>3} {s['name'][:35]:<35} {edge:>+7.4f} {hit3:>7.3f} {pval:>8.5f}")
        print(f"        -> 號碼預測: {s.get('numbers', [])}")
    
    print(f"\n" + "═" * 70)
    exists = report.get('6_pattern_exists', False)
    if exists:
        print(f"  ✅ 發現統計顯著的可利用模式! (通過 Bonferroni 校正與 300次 Permutation)")
        why = report.get('8_why_no_pattern', '')
        print(f"  說明: {why}")
    else:
        print(f"  ⚠️  未能突破多重比較過擬合限制")
        why = report.get('8_why_no_pattern', '')
        if why:
            print(f"  原因: {why[:300]}")
    print("═" * 70)
    
    # Evolution progress
    print(f"\n📈 演化進程:")
    for h in report.get('evolution_history', []):
        bar = "█" * max(0, int((h.get('best_edge', 0)) * 200))
        print(f"   Gen {h['generation']:>2}: best_M3_edge={h['best_edge']:>+.4f} "
              f"pop={h['pop_size']:>3} {bar}")

def main():
    parser = argparse.ArgumentParser(description='Self-Evolving Strategy Discovery')
    parser.add_argument('--generations', '-g', type=int, default=8)
    parser.add_argument('--pop-size', '-p', type=int, default=50)
    parser.add_argument('--n-test', '-t', type=int, default=1500)
    parser.add_argument('--output', '-o', type=str, default=None)
    args = parser.parse_args()
    
    t0 = time.time()
    draws, meta = load_big_lotto_draws()
    print(f"Loaded {len(draws)} Big Lotto draws ({meta[0]['draw']}~{meta[-1]['draw']})")
    
    engine = EvolutionEngine(draws, meta)
    report = engine.run(
        n_generations=args.generations,
        n_test=args.n_test,
        pop_size=args.pop_size
    )
    
    elapsed = time.time() - t0
    report['total_elapsed_seconds'] = elapsed
    
    print_report(report)
    
    out_path = args.output or os.path.join(
        os.path.dirname(__file__), 
        f'evolution_report_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    )
    
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n📁 Report saved to: {out_path}")
    print(f"⏱️  Total time: {elapsed:.1f}s")


if __name__ == '__main__':
    main()
