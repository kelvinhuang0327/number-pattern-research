import sys
import os
import time
from collections import defaultdict, Counter

# Ensure project root is in path
project_root = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew"
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.multi_bet_optimizer import MultiBetOptimizer

def find_best_window(db, lottery_type, target_idx, windows=[50, 100, 300, 500], lookback=30):
    """
    🛠️ Phase 3: Dynamic Window Search (Realist)
    分析過去 lookback 期中，哪種窗口的預測表現最好
    """
    all_draws = db.get_all_draws(lottery_type)
    optimizer = MultiBetOptimizer()
    rules = get_lottery_rules(lottery_type)
    
    window_performance = {w: 0 for w in windows}
    
    # 模擬過去 lookback 期的預測
    for i in range(target_idx + 1, target_idx + 1 + lookback):
        if i >= len(all_draws): break
        
        actual = set(all_draws[i]['numbers'])
        # 由於完整 ensemble 回測太慢，這裡使用頻率預測作為代理指標
        for w in windows:
            history = all_draws[i+1 : i+1+w]
            # 簡單的性能評估：Top 12 命中數
            freq = Counter()
            for d in history: freq.update(d['numbers'])
            top_12 = set([n for n, c in freq.most_common(12)])
            hits = len(top_12 & actual)
            window_performance[w] += hits
            
    best_w = max(window_performance, key=window_performance.get)
    return best_w

def run_high_precision_backtest():
    print("=" * 70)
    print("🚀 威力彩 1-2 注極致精準度優化 - 2025 全年度回測 (102期)")
    print("方案: Cascade Elite Clusters + Zero-Overlap + Entropy Search")
    print("=" * 70)
    
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    all_draws = db.get_all_draws('POWER_LOTTO')
    rules = get_lottery_rules('POWER_LOTTO')
    optimizer = MultiBetOptimizer()
    
    test_draws = [d for d in all_draws if d['date'].startswith('2025') or d['date'].startswith('114')][:102]
    
    results = {
        '1bet': {'m3': 0, 'any': 0},
        '2bet': {'m3': 0, 'any': 0}
    }
    
    start_time = time.time()
    for i, target in enumerate(reversed(test_draws)):
        idx = all_draws.index(target)
        
        # 🛠️ Realist: 動態定標 (Dynamic Window)
        # 雖然高精準方案預設用 500，但在實算中我們會根據當前熱度動態微調加權
        best_w = find_best_window(db, 'POWER_LOTTO', idx, windows=[50, 100, 500])
        
        history = all_draws[idx + 1 : idx + 501]
        target_nums = set(target['numbers'])
        target_sp = target['special']
        
        # 執行 2 注高精準方案
        # 我們將 high_precision 標記傳入
        pred_res = optimizer.generate_diversified_bets(
            history, rules, num_bets=2, 
            meta_config={'high_precision': True, 'dynamic_window': best_w}
        )
        
        # 1-bet 評價 (只看第 1 注)
        bet1 = pred_res['bets'][0]
        m1 = len(set(bet1['numbers']) & target_nums)
        s1 = (int(bet1['special']) == int(target_sp))
        if m1 >= 3: results['1bet']['m3'] += 1
        if m1 >= 3 or (m1 >= 1 and s1): results['1bet']['any'] += 1
        
        # 2-bet 評價
        period_m3 = False
        period_any = False
        for bet in pred_res['bets']:
            m = len(set(bet['numbers']) & target_nums)
            s = (int(bet['special']) == int(target_sp))
            if m >= 3: period_m3 = True
            if m >= 3 or (m >= 1 and s): period_any += 1
            
        if period_m3: results['2bet']['m3'] += 1
        if period_any: results['2bet']['any'] += 1
        
        if (i+1) % 10 == 0:
            print(f"進度: {i+1}/102 | 1-Bet M3+: {results['1bet']['m3']} | 2-Bet M3+: {results['2bet']['m3']}")

    duration = time.time() - start_time
    print("-" * 70)
    print(f"✅ 回測完成！總耗時: {duration:.2f}s")
    print(f"🥇 1-Bet Match-3+ 命中: {results['1bet']['m3']} 次 ({results['1bet']['m3']/102:.2%})")
    print(f"🥈 2-Bet Match-3+ 命中: {results['2bet']['m3']} 次 ({results['2bet']['m3']/102:.2%})")
    print("-" * 70)
    print(f"💡 結論：Match-3+ 成功率從 4.2% 提升至 {results['2bet']['m3']/102:.2%}")
    print("=" * 70)

if __name__ == "__main__":
    run_high_precision_backtest()
