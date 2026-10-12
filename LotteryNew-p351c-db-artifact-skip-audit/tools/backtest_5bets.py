#!/usr/bin/env python3
"""
Backtest Big Lotto Best 5 Bets Strategy
"""
import sys
import os
import argparse

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from tools.auto_optimizer_v2 import IntegratedPredictor

def run_backtest_5bets(args):
    print("=" * 80)
    print(f"啟動最佳五注策略 (Best 5 Bets) 回測 - 年份: {args.year}, Kill-{args.kill_count}")
    print("=" * 80)
    
    predictor = IntegratedPredictor('BIG_LOTTO')
    
    results = predictor.backtest_5bets(
        year=args.year,
        use_genetic=args.genetic,
        kill_count=args.kill_count if not args.no_kill else 0
    )
    
    if 'error' in results:
        print(f"Error: {results['error']}")
        return

    print("\n" + "=" * 80)
    print("📈 五注策略回測總結")
    print("=" * 80)
    
    total = results['total_draws']
    wins_any = results['total_wins']
    win_rate_any = wins_any / total if total > 0 else 0
    
    print(f"總期數: {total}")
    print(f"中獎期數 (任一注中3+): {wins_any}")
    print(f"🔥 組合勝率: {win_rate_any*100:.2f}%")
    print(f"最高命中: {results['max_match']} 號")
    
    print("\n📊 各策略中獎貢獻:")
    breakdown = results['bet_wins']
    print(f"   Bet 1 (穩健 - 加權投票): {breakdown.get('bet1', 0)} 勝 ({breakdown.get('bet1', 0)/total*100:.1f}%)")
    print(f"   Bet 2 (平衡 - 分區平衡): {breakdown.get('bet2', 0)} 勝 ({breakdown.get('bet2', 0)/total*100:.1f}%)")
    print(f"   Bet 3 (趨勢 - 熱號共現): {breakdown.get('bet3', 0)} 勝 ({breakdown.get('bet3', 0)/total*100:.1f}%)")
    print(f"   Bet 4 (回補 - 乖離率):   {breakdown.get('bet4', 0)} 勝 ({breakdown.get('bet4', 0)/total*100:.1f}%)")
    print(f"   Bet 5 (綜合 - 共識決):   {breakdown.get('bet5', 0)} 勝 ({breakdown.get('bet5', 0)/total*100:.1f}%)")
    
    print("\n⚠️ 殺號統計:")
    print(f"   總誤殺中獎號碼: {results['total_killed_winners']}")
    print(f"   發生誤殺期數: {results['draws_with_kill_mistakes']} / {total} ({results['draws_with_kill_mistakes']/total*100:.1f}%)")

def main():
    parser = argparse.ArgumentParser(description='Backtest 5 Bets Strategy')
    parser.add_argument('--year', type=int, default=2025, help='Year to backtest')
    parser.add_argument('--genetic', action='store_true', default=True, help='Use genetic optimization')
    parser.add_argument('--no-kill', action='store_true', help='Disable kill list')
    parser.add_argument('--kill-count', type=int, default=5, help='Kill count')
    
    args = parser.parse_args()
    
    run_backtest_5bets(args)

if __name__ == '__main__':
    main()
