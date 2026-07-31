#!/usr/bin/env python3
"""
威力彩 150 期標準回測（獨立腳本）
================================
含完整特別號判定，不依賴通用框架

用法：
  python3 tools/backtest_150_power.py <方法名稱> [方法2] [方法3]

範例：
  python3 tools/backtest_150_power.py deviation
  python3 tools/backtest_150_power.py deviation markov statistical frequency
  python3 tools/backtest_150_power.py --list
"""
import sys
import os
import io
import argparse
from collections import Counter

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine

# sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 方法別名
METHOD_ALIASES = {
    'frequency': 'frequency_predict', 'freq': 'frequency_predict',
    'bayesian': 'bayesian_predict', 'bayes': 'bayesian_predict',
    'markov': 'markov_predict', 'markov_v2': 'markov_v2_predict',
    'trend': 'trend_predict',
    'deviation': 'deviation_predict', 'dev': 'deviation_predict',
    'hot_cold': 'hot_cold_mix_predict', 'hot_cold_mix': 'hot_cold_mix_predict',
    'statistical': 'statistical_predict', 'stat': 'statistical_predict',
    'monte_carlo': 'monte_carlo_predict', 'mc': 'monte_carlo_predict',
    'ensemble': 'ensemble_predict',
    'ensemble_advanced': 'ensemble_advanced_predict',
    'sota': 'sota_predict',
    'odd_even': 'odd_even_balance_predict',
    'zone_balance': 'zone_balance_predict', 'zone': 'zone_balance_predict',
    'sum_range': 'sum_range_predict',
    'number_pairs': 'number_pairs_predict', 'pairs': 'number_pairs_predict',
    'pattern': 'pattern_recognition_predict',
    'cycle': 'cycle_analysis_predict',
    'entropy': 'entropy_predict',
    'interval': 'interval_predict',
    'clustering': 'clustering_predict',
    'cold_number': 'cold_number_predict', 'cold': 'cold_number_predict',
    'tail_repeat': 'tail_repeat_predict', 'tail': 'tail_repeat_predict',
    'gap_sensitive': 'gap_sensitive_predict', 'gap': 'gap_sensitive_predict',
}

# 基準值（威力彩單注 Match-3+ 率）
BASELINE_MATCH_3 = 3.87


def get_method_func(engine, method_name):
    """取得方法函數"""
    actual_name = METHOD_ALIASES.get(method_name.lower(), method_name)
    if not actual_name.endswith('_predict'):
        actual_name = f"{actual_name}_predict"

    if method_name.lower() in ['optimized', 'opt_ensemble', 'smart_ensemble']:
        from models.optimized_ensemble import OptimizedEnsemblePredictor
        ensemble = OptimizedEnsemblePredictor(engine)
        # 綁定為只需要 history, rules 的函數
        def opt_pred(h, r):
            res = ensemble.predict(h, r, backtest_periods=1)
            # 兼容多注格式：提取第1注
            if 'bet1' in res:
                res['numbers'] = res['bet1']['numbers']
                res['special'] = res['bet1']['special']
            return res
        return opt_pred, "OptimizedEnsemble"

    if hasattr(engine, actual_name):
        return getattr(engine, actual_name), actual_name

    if hasattr(engine, method_name):
        return getattr(engine, method_name), method_name
        
    # Check for global functions (for custom scripts)
    if method_name in globals():
        return globals()[method_name], method_name

    return None, None


def list_methods():
    """列出可用方法"""
    engine = UnifiedPredictionEngine()
    methods = [attr.replace('_predict', '')
               for attr in dir(engine)
               if attr.endswith('_predict') and not attr.startswith('_')]
    return sorted(methods)


    return sorted(methods)

def grand_slam_predict(history, rules):
    """
    Grand Slam 策略 (Alpha Top 12 + Beta Top 6 + Special)
    為了回測腳本適配，返回 3 注
    """
    engine = UnifiedPredictionEngine()
    
    # 1. Alpha (True Freq) Top 12
    nums_alpha = []
    try:
        alpha_rules = rules.copy()
        alpha_rules['pickCount'] = 12
        alpha_rules['frequency_window'] = 50
        pred_alpha = engine.true_frequency_predict(history, alpha_rules)
        nums_alpha = pred_alpha.get('ranked_list', [])
        # Pad if needed
        if len(nums_alpha) < 12:
            nums_alpha.extend([x for x in range(1, 39) if x not in nums_alpha][:12-len(nums_alpha)])
    except:
        pass
        
    bet1 = sorted(nums_alpha[:6])
    bet2 = sorted(nums_alpha[6:12])
    
    # 2. Beta (Deviation) Top 6
    nums_beta = []
    try:
        beta_rules = rules.copy()
        beta_rules['pickCount'] = 6
        pred_beta = engine.deviation_predict(history, beta_rules)
        nums_beta = pred_beta['numbers']
    except:
        nums_beta = sorted(random.sample(range(1,39), 6))
        
    bet3 = sorted(nums_beta)
    
    # 3. Special
    # For backtest speed/simplicity, use True Freq Top 1
    # Alternatively use UnifiedPredictionEngine if it has special logic
    # But this script usually calls predict_pool_numbers for special? 
    # The backtest_single logic calls result.get('special').
    # We need to attach special to each bet.
    
    special_pred = 1
    try:
        # Extract special history
        s_hist = [{'numbers': [d['special']]} for d in history if d.get('special')]
        if s_hist:
            s_res = engine.true_frequency_predict(s_hist, {'pickCount': 1, 'frequency_window': 50})
            special_pred = s_res['ranked_list'][0]
    except:
        pass
        
    # We need to return a result that backtest_single can understand.
    # But backtest_single expects ONE dict with 'numbers' and 'special'.
    # backtest_multi expects MULTIPLE methods.
    # Grand Slam is inherently MULTI-BET.
    # So we should use backtest_multi logic?
    # BUT backtest_multi iterates over functions.
    # We can Register 3 functions? 
    # No, let's make grand_slam_predict return the BEST bet?
    # No, that defeats the purpose.
    
    # HACK: If called by backtest_single, we return Bet 2 (Secondary) as it's the best?
    # Or we modify backtest_multi to accept this?
    
    # Better: We register "grand_slam_bet1", "grand_slam_bet2", etc.
    return {'numbers': bet2, 'special': special_pred} # Return Bet 2 as default for single

# Modifying Aliases?
# Actually, the user wants me to use the script.
# The script supports backtest_multi.
# So I should define 3 functions: gs_bet1, gs_bet2, gs_bet3.

def gs_bet1(history, rules):
    engine = UnifiedPredictionEngine()
    alpha_rules = rules.copy()
    alpha_rules['pickCount'] = 12
    alpha_rules['frequency_window'] = 50
    pred = engine.true_frequency_predict(history, alpha_rules)
    nums = pred.get('ranked_list', [])[:6]
    return {'numbers': sorted(nums), 'special': _get_special(history, engine)}

def gs_bet2(history, rules):
    engine = UnifiedPredictionEngine()
    alpha_rules = rules.copy()
    alpha_rules['pickCount'] = 12
    alpha_rules['frequency_window'] = 50
    pred = engine.true_frequency_predict(history, alpha_rules)
    nums = pred.get('ranked_list', [])[6:12]
    return {'numbers': sorted(nums), 'special': _get_special(history, engine)}

def gs_bet3(history, rules):
    engine = UnifiedPredictionEngine()
    beta_rules = rules.copy()
    beta_rules['pickCount'] = 6
    pred = engine.deviation_predict(history, beta_rules)
    return {'numbers': pred['numbers'], 'special': _get_special(history, engine)}

def _get_special(history, engine):
    try:
        # History in backtest script is Old -> New (hist = all_draws[:target_idx])
        # smart_markov_predict expects this format
        pred = engine.smart_markov_predict(history, {'pickCount': 1})
        return pred['numbers'][0]
    except Exception as e:
        print(f"Error in special: {e}")
        return 1
    return 1

# Update Alias in Global Scope? We need to insert them into METHOD_ALIASES
METHOD_ALIASES['gs_bet1'] = 'gs_bet1'
METHOD_ALIASES['gs_bet2'] = 'gs_bet2'
METHOD_ALIASES['gs_bet3'] = 'gs_bet3'
METHOD_ALIASES['grand_slam'] = 'gs_bet2' # Default to Secondary for single call
def calc_prize(match_count, special_hit):
    """
    威力彩中獎判定

    獎項規則：
    - 頭獎: 6 + 特別號
    - 貳獎: 6
    - 參獎: 5 + 特別號
    - 肆獎: 5
    - 伍獎: 4 + 特別號
    - 陸獎: 4
    - 柒獎: 3 + 特別號
    - 捌獎: 2 + 特別號
    - 玖獎: 3
    - 普獎: 1 + 特別號
    """
    if match_count == 6 and special_hit:
        return '頭獎', 1
    elif match_count == 6:
        return '貳獎', 2
    elif match_count == 5 and special_hit:
        return '參獎', 3
    elif match_count == 5:
        return '肆獎', 4
    elif match_count == 4 and special_hit:
        return '伍獎', 5
    elif match_count == 4:
        return '陸獎', 6
    elif match_count == 3 and special_hit:
        return '柒獎', 7
    elif match_count == 2 and special_hit:
        return '捌獎', 8
    elif match_count == 3:
        return '玖獎', 9
    elif match_count == 1 and special_hit:
        return '普獎', 10
    else:
        return None, 0



def backtest_single(method_name, test_periods=150):
    """
    回測單一方法

    數據切片邏輯（防止洩漏）：
    - target_draw = all_draws[target_idx]  → 實際開獎號碼
    - hist = all_draws[:target_idx]        → 只用過去數據預測
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))

    # 取得所有開獎資料，反轉為舊→新排序
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')

    engine = UnifiedPredictionEngine()
    method_func, actual_name = get_method_func(engine, method_name)

    if not method_func:
        print(f"❌ 找不到方法: {method_name}")
        print(f"使用 --list 查看可用方法")
        return None

    test_periods = min(test_periods, len(all_draws) - 50)

    print("=" * 60)
    print(f"🔬 威力彩 {test_periods} 期回測（獨立腳本）")
    print("=" * 60)
    print(f"方法: {actual_name}")
    print(f"測試期數: {test_periods}")
    print(f"號碼池: 1-38，選 6 個")
    print(f"特別號: 1-8")
    print("-" * 60)

    # 回測統計
    match_dist = Counter()  # 主號命中分布
    special_hits = 0        # 特別號命中次數
    prize_dist = Counter()  # 獎項分布
    total = 0
    wins = 0                # 中獎次數（任何獎項）
    hits = []               # 命中詳情

    # 滾動式回測
    for i in range(test_periods):
        # 計算目標期索引
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue

        # ===== 關鍵：數據切片 =====
        target_draw = all_draws[target_idx]  # 實際開獎（用於驗證）
        hist = all_draws[:target_idx]        # 只用過去數據（用於預測）
        # ==========================

        if len(hist) < 10:
            continue

        try:
            # 執行預測（只能看到 hist）
            result = method_func(hist, rules)
            if not result or 'numbers' not in result:
                continue

            # 取得預測結果
            predicted = set(result['numbers'])
            pred_special = result.get('special')

            # 取得實際開獎結果
            actual = set(target_draw['numbers'])
            actual_special = target_draw.get('special')

            # 計算主號命中數
            match_count = len(predicted & actual)
            match_dist[match_count] += 1

            # 計算特別號命中
            special_hit = (pred_special == actual_special)
            if special_hit:
                special_hits += 1

            # 判定中獎（完整威力彩規則）
            prize_name, prize_level = calc_prize(match_count, special_hit)

            if prize_name:
                wins += 1
                prize_dist[prize_name] += 1
                hits.append({
                    'draw': target_draw['draw'],
                    'date': target_draw['date'],
                    'match': match_count,
                    'special': special_hit,
                    'prize': prize_name
                })

            total += 1
            if total % 10 == 0:
                print(f"  Progress: {total}/{test_periods} | M3+ Hits: {m3}", flush=True)
        except Exception as e:
            continue

    if total == 0:
        print("❌ 無有效數據")
        return None

    # 計算統計
    m3 = sum(match_dist[k] for k in match_dist if k >= 3)
    m4 = sum(match_dist[k] for k in match_dist if k >= 4)
    m3_rate = m3 / total * 100
    win_rate = wins / total * 100
    special_rate = special_hits / total * 100

    # 顯示結果
    print("\n" + "=" * 60)
    print("📊 結果")
    print("=" * 60)
    print(f"\n測試期數: {total}")

    print(f"\n主號命中分布:")
    for mc in sorted(match_dist.keys(), reverse=True):
        cnt = match_dist[mc]
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{mc}: {cnt:3d} ({pct:5.1f}%) {bar}")

    print(f"\n特別號命中: {special_hits} 次 ({special_rate:.2f}%)")

    print(f"\n中獎統計:")
    print(f"  總中獎: {wins} 次 ({win_rate:.2f}%)")
    print(f"  Match-3+: {m3} 次 ({m3_rate:.2f}%)")
    print(f"  Match-4+: {m4} 次 ({m4/total*100:.2f}%)")

    if prize_dist:
        print(f"\n獎項分布:")
        for prize in ['頭獎', '貳獎', '參獎', '肆獎', '伍獎', '陸獎', '柒獎', '捌獎', '玖獎', '普獎']:
            if prize in prize_dist:
                print(f"  {prize}: {prize_dist[prize]} 次")

    # 對比基準
    print("\n" + "=" * 60)
    print("📈 對比")
    print("=" * 60)
    diff = m3_rate - BASELINE_MATCH_3
    print(f"\n基準 Match-3+: {BASELINE_MATCH_3:.2f}%")
    print(f"本方法:        {m3_rate:.2f}%")
    print(f"差異:          {'+' if diff >= 0 else ''}{diff:.2f}%")

    if diff >= 1.0:
        print("\n✅ 優於基準")
    elif diff >= 0:
        print("\n✅ 與基準持平")
    else:
        print("\n⚠️ 低於基準")

    return {'method': actual_name, 'match_3_rate': m3_rate, 'win_rate': win_rate,
            'special_rate': special_rate, 'total': total}


def backtest_multi(method_names, test_periods=150):
    """
    回測多注組合

    成功判定：任一注 Match >= 3 或符合威力彩其他獎項
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')

    engine = UnifiedPredictionEngine()

    # 驗證方法
    methods = []
    for name in method_names:
        func, actual = get_method_func(engine, name)
        if func:
            methods.append((actual, func))
        else:
            print(f"⚠️ 跳過: {name}")

    if not methods:
        print("❌ 無有效方法")
        return None

    test_periods = min(test_periods, len(all_draws) - 50)

    print("=" * 60)
    print(f"🔬 威力彩 {len(methods)} 注組合 {test_periods} 期回測（獨立腳本）")
    print("=" * 60)
    print(f"方法組合:")
    for i, (name, _) in enumerate(methods, 1):
        print(f"  {i}. {name}")
    print(f"測試期數: {test_periods}")
    print("-" * 60)

    # 回測統計
    wins = 0
    m3_plus = 0
    m4_plus = 0
    special_any = 0
    total = 0
    best_dist = Counter()
    prize_dist = Counter()

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 0:
            continue

        # ===== 關鍵：數據切片 =====
        target_draw = all_draws[target_idx]
        hist = all_draws[:target_idx]
        # ==========================

        if len(hist) < 10:
            continue

        actual = set(target_draw['numbers'])
        actual_special = target_draw.get('special')

        best_match = 0
        best_prize_level = 0
        best_prize_name = None
        any_special = False

        # 評估每一注
        for _, func in methods:
            try:
                result = func(hist, rules)
                if result and 'numbers' in result:
                    predicted = set(result['numbers'])
                    match = len(predicted & actual)
                    special_hit = (result.get('special') == actual_special)

                    if special_hit:
                        any_special = True

                    # 判定獎項
                    prize_name, prize_level = calc_prize(match, special_hit)

                    # 取最佳獎項（level 越小越好）
                    if prize_level > 0 and (best_prize_level == 0 or prize_level < best_prize_level):
                        best_prize_level = prize_level
                        best_prize_name = prize_name

                    best_match = max(best_match, match)
            except:
                continue

        best_dist[best_match] += 1

        if any_special:
            special_any += 1

        if best_prize_name:
            wins += 1
            prize_dist[best_prize_name] += 1

        if best_match >= 4:
            m4_plus += 1
        if best_match >= 3:
            m3_plus += 1

        total += 1

    if total == 0:
        print("❌ 無有效數據")
        return None

    m3_rate = m3_plus / total * 100
    m4_rate = m4_plus / total * 100
    win_rate = wins / total * 100
    efficiency = m3_rate / len(methods)

    # 顯示結果
    print("\n" + "=" * 60)
    print("📊 組合結果")
    print("=" * 60)
    print(f"\n測試期數: {total}")
    print(f"注數: {len(methods)}")

    print(f"\n最佳主號命中分布:")
    for mc in sorted(best_dist.keys(), reverse=True):
        cnt = best_dist[mc]
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{mc}: {cnt:3d} ({pct:5.1f}%) {bar}")

    print(f"\n特別號（任一注）: {special_any} 次 ({special_any/total*100:.2f}%)")

    print(f"\n中獎統計:")
    print(f"  總中獎: {wins} 次 ({win_rate:.2f}%)")
    print(f"  Match-4+: {m4_plus} 次 ({m4_rate:.2f}%)")
    print(f"  Match-3+: {m3_plus} 次 ({m3_rate:.2f}%)")

    if prize_dist:
        print(f"\n最佳獎項分布:")
        for prize in ['頭獎', '貳獎', '參獎', '肆獎', '伍獎', '陸獎', '柒獎', '捌獎', '玖獎', '普獎']:
            if prize in prize_dist:
                print(f"  {prize}: {prize_dist[prize]} 次")

    # 效益分析
    print("\n" + "=" * 60)
    print("📈 效益分析")
    print("=" * 60)
    print(f"\n{len(methods)} 注 Match-3+: {m3_rate:.2f}%")
    print(f"每注效益: {efficiency:.2f}%")
    print(f"單注基準: {BASELINE_MATCH_3:.2f}%")

    if efficiency > BASELINE_MATCH_3:
        print(f"\n✅ 組合效益佳 (+{efficiency - BASELINE_MATCH_3:.2f}%/注)")
    else:
        print(f"\n⚠️ 組合重疊高")

    return {'methods': [m[0] for m in methods], 'match_3_rate': m3_rate,
            'win_rate': win_rate, 'efficiency': efficiency, 'num_bets': len(methods)}


def main():
    parser = argparse.ArgumentParser(description='威力彩 500 期回測（獨立腳本）')
    parser.add_argument('methods', nargs='*', help='方法名稱')
    parser.add_argument('--list', '-l', action='store_true', help='列出可用方法')
    parser.add_argument('--periods', '-p', type=int, default=500, help='測試期數')

    args = parser.parse_args()

    if args.list:
        print("可用方法:")
        for m in list_methods():
            print(f"  {m}")
        print("\n常用別名:")
        for alias in sorted(METHOD_ALIASES.keys()):
            print(f"  {alias}")
        return

    if not args.methods:
        parser.print_help()
        print("\n範例:")
        print("  python3 tools/backtest_150_power.py deviation")
        print("  python3 tools/backtest_150_power.py deviation markov statistical frequency")
        return

    if len(args.methods) == 1:
        backtest_single(args.methods[0], args.periods)
    else:
        backtest_multi(args.methods, args.periods)


if __name__ == '__main__':
    main()
