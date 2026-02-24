#!/usr/bin/env python3
"""
大樂透 150 期標準回測（獨立腳本）
================================
含完整特別號判定，不依賴通用框架

用法：
  python3 tools/backtest_150_biglotto.py <方法名稱> [方法2] [方法3]

範例：
  python3 tools/backtest_150_biglotto.py deviation
  python3 tools/backtest_150_biglotto.py deviation markov statistical
  python3 tools/backtest_150_biglotto.py --list
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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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
    'smart_bet1': 'smart_bet1_predict',
    'smart_bet2': 'smart_bet2_predict',
}

# 基準值（大樂透單注 Match-3+ 率）
BASELINE_MATCH_3 = 2.67


def get_method_func(engine, method_name):
    """取得方法函數"""
    actual_name = METHOD_ALIASES.get(method_name.lower(), method_name)
    if not actual_name.endswith('_predict'):
        actual_name = f"{actual_name}_predict"

    if hasattr(engine, actual_name):
        return getattr(engine, actual_name), actual_name

    if hasattr(engine, method_name):
        return getattr(engine, method_name), method_name

    # Check for global functions (for custom strategy functions)
    if actual_name in globals():
        return globals()[actual_name], actual_name
        
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


def calc_prize(match_count, special_hit):
    """
    大樂透中獎判定

    獎項規則：
    - 頭獎: 6 號碼全中
    - 貳獎: 5 號碼 + 特別號
    - 參獎: 5 號碼
    - 肆獎: 4 號碼 + 特別號
    - 伍獎: 4 號碼
    - 陸獎: 3 號碼 + 特別號
    - 柒獎: 3 號碼
    - 普獎: 2 號碼 + 特別號
    """
    if match_count == 6:
        return '頭獎', 1
    elif match_count == 5 and special_hit:
        return '貳獎', 2
    elif match_count == 5:
        return '參獎', 3
    elif match_count == 4 and special_hit:
        return '肆獎', 4
    elif match_count == 4:
        return '伍獎', 5
    elif match_count == 3 and special_hit:
        return '陸獎', 6
    elif match_count == 3:
        return '柒獎', 7
    elif match_count == 2 and special_hit:
        return '普獎', 8
    else:
        return None, 0


def check_special_hit(predicted_numbers, actual_special):
    """
    檢查預測號碼是否包含特別號

    大樂透特別號判定：預測的 6 個號碼中是否有一個等於特別號
    （注意：不是預測特別號，而是預測的主號剛好包含特別號）
    """
    if actual_special is None:
        return False
    return actual_special in predicted_numbers


def backtest_single(method_name, test_periods=150):
    """
    回測單一方法

    數據切片邏輯（防止洩漏）：
    - target_draw = all_draws[target_idx]  → 實際開獎號碼
    - hist = all_draws[:target_idx]        → 只用過去數據預測
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))

    # 取得所有開獎資料，反轉為舊→新排序
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')

    engine = UnifiedPredictionEngine()
    method_func, actual_name = get_method_func(engine, method_name)

    if not method_func:
        print(f"❌ 找不到方法: {method_name}")
        print(f"使用 --list 查看可用方法")
        return None

    test_periods = min(test_periods, len(all_draws) - 50)

    print("=" * 60)
    print(f"🔬 大樂透 150 期回測（獨立腳本）")
    print("=" * 60)
    print(f"方法: {actual_name}")
    print(f"測試期數: {test_periods}")
    print(f"號碼池: 1-49，選 6 個")
    print(f"特別號: 從未中獎號碼產生（兌獎用）")
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

            # 取得實際開獎結果
            actual = set(target_draw['numbers'])
            actual_special = target_draw.get('special')

            # 計算主號命中數
            match_count = len(predicted & actual)
            match_dist[match_count] += 1

            # 計算特別號命中（預測的號碼中是否包含特別號）
            special_hit = check_special_hit(predicted, actual_special)
            if special_hit:
                special_hits += 1

            # 判定中獎（完整大樂透規則）
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
    print(f"  （預測的 6 個號碼中包含實際特別號）")

    print(f"\n中獎統計:")
    print(f"  總中獎: {wins} 次 ({win_rate:.2f}%)")
    print(f"  Match-3+: {m3} 次 ({m3_rate:.2f}%)")
    print(f"  Match-4+: {m4} 次 ({m4/total*100:.2f}%)")

    if prize_dist:
        print(f"\n獎項分布:")
        for prize in ['頭獎', '貳獎', '參獎', '肆獎', '伍獎', '陸獎', '柒獎', '普獎']:
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

    成功判定：任一注符合大樂透獎項（Match >= 3 或 Match 2 + 特別號）
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')

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
    print(f"🔬 大樂透 {len(methods)} 注組合 150 期回測（獨立腳本）")
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
                    special_hit = check_special_hit(predicted, actual_special)

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
        for prize in ['頭獎', '貳獎', '參獎', '肆獎', '伍獎', '陸獎', '柒獎', '普獎']:
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
    parser = argparse.ArgumentParser(description='大樂透 150 期回測（獨立腳本）')
    parser.add_argument('methods', nargs='*', help='方法名稱')
    parser.add_argument('--list', '-l', action='store_true', help='列出可用方法')
    parser.add_argument('--periods', '-p', type=int, default=150, help='測試期數')

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
        print("  python3 tools/backtest_150_biglotto.py deviation")
        print("  python3 tools/backtest_150_biglotto.py deviation markov statistical")
        return

    if len(args.methods) == 1:
        backtest_single(args.methods[0], args.periods)
    else:
        backtest_multi(args.methods, args.periods)



# Smart 2-Bet Strategy (Standardized)
def smart_bet1_predict(history, rules):
    """Conservative: True Frequency Top 6"""
    engine = UnifiedPredictionEngine()
    # Use freq window 50
    r = rules.copy()
    r['frequency_window'] = 50
    r['pickCount'] = 6
    pred = engine.true_frequency_predict(history, r)
    return {'numbers': sorted(pred['numbers'])}

def smart_bet2_predict(history, rules):
    """Aggressive: Deviation Top 6"""
    engine = UnifiedPredictionEngine()
    r = rules.copy()
    r['pickCount'] = 6
    pred = engine.deviation_predict(history, r)
    return {'numbers': sorted(pred['numbers'])}

if __name__ == '__main__':
    main()
