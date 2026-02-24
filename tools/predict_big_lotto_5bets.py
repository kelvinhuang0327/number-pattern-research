#!/usr/bin/env python3
"""
Big Lotto Best 5 Bets Predictor (Phase 3.5)
"""
import sys
import os
import argparse

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery-api'))

from tools.auto_optimizer_v2 import IntegratedPredictor

def run_5bets_prediction(args):
    """執行最佳五注預測"""
    use_kill = not getattr(args, 'no_kill', False)
    kill_mode = f"Kill-{args.kill_count}" if use_kill else "No Kill"
    
    print("=" * 80)
    print("大樂透最佳五注預測 (Phase 3.5 Best 5 Bets)")
    print(f"配置: 遺傳優化 + {kill_mode}")
    print("=" * 80)
    
    predictor = IntegratedPredictor('BIG_LOTTO')
    
    result = predictor.predict_best_5_bets(
        optimize_weights=args.optimize,
        use_genetic=True,
        use_kill=use_kill,
        kill_count=args.kill_count
    )
    
    # 顯示權重 (簡化顯示前3名)
    weights = sorted(result['weights'].items(), key=lambda x: x[1], reverse=True)
    top3_weights = ", ".join([f"{k}:{v:.1%}" for k, v in weights[:3]])
    print(f"\n📊 策略權重 (Top 3): {top3_weights}")
    
    if result.get('kill_list'):
        print(f"🔪 排除號碼 ({kill_mode}): {result['kill_list']}")
    
    print("\n🎯 推薦五注組合:")
    print("-" * 60)
    
    bets = [
        (result['bet1'], result['desc1']),
        (result['bet2'], result['desc2']),
        (result['bet3'], result['desc3']),
        (result['bet4'], result['desc4']),
        (result['bet5'], result['desc5'])
    ]
    
    for i, (numbers, desc) in enumerate(bets, 1):
        # Format numbers for better readability
        nums_str = ", ".join([f"{n:02d}" for n in numbers])
        print(f"Bet {i} [{desc}]:")
        print(f"   [{nums_str}]")
        print("-" * 60)
        
    print(f"💡 綜合共識池: {result.get('consensus', [])}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description='Big Lotto Best 5 Bets Predictor')
    
    parser.add_argument('--no-optimize', action='store_false', dest='optimize',
                        help='停用權重優化')
    parser.add_argument('--no-kill', action='store_true',
                        help='停用負向排除')
    parser.add_argument('--kill-count', type=int, default=5,
                        help='負向排除數量 (預設 5)')
    
    args = parser.parse_args()
    
    run_5bets_prediction(args)

if __name__ == '__main__':
    main()
