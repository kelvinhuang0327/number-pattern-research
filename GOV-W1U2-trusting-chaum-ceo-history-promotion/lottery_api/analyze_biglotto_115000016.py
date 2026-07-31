
import numpy as np
import sys
import os
import json
from collections import Counter

# Setup path
lottery_api_dir = os.path.dirname(os.path.abspath(__file__))
if lottery_api_dir not in sys.path:
    sys.path.insert(0, lottery_api_dir)
os.chdir(lottery_api_dir)

# Fix DB path
from database import db_manager
db_manager.db_path = os.path.join(lottery_api_dir, "data", "lottery_v2.db")

from models.entropy_transformer import EntropyTransformerModel
from models.unified_predictor import UnifiedPredictionEngine
from common import load_backend_history
from models.multi_bet_optimizer import MultiBetOptimizer

def analyze():
    # ==================== 開獎數據 ====================
    # 第115000016期 開獎日期:115/02/15
    target_numbers = [3, 6, 11, 18, 25, 28] # Ascending
    special_number = 35
    all_target_main = set(target_numbers)
    draw_id = 115000016
    
    lottery_type = 'BIG_LOTTO'
    print("=" * 100)
    print(f"🎰 大樂透 第 {draw_id} 期 全方位檢討分析 (虛擬設計評審團開會中)")
    print(f"📅 開獎日期: 115/02/15 (2026/02/15)")
    print(f"🎯 開獎號碼: {sorted(target_numbers)} (特別號: {special_number})")
    print("=" * 100)
    
    # ==================== 載入歷史數據 ====================
    # 確保不包含第 115000016 期
    history, rules = load_backend_history(lottery_type)
    history_for_prediction = [d for d in history if int(d['draw']) < draw_id]
    
    print(f"\n📊 載入預測用歷史數據: {len(history_for_prediction)} 期")
    if history_for_prediction:
        print(f"   最新一期: {history_for_prediction[0]['draw']} ({history_for_prediction[0].get('date','N/A')})")
    
    max_num = 49
    # Number scores for optimizers
    recent_nums_all = [n for d in history_for_prediction[:200] for n in d['numbers']]
    freq_counter_all = Counter(recent_nums_all)
    number_scores = {n: freq_counter_all.get(n, 0) for n in range(1, max_num + 1)}

    # Debug: Check Lukewarm and Symmetry
    opt = MultiBetOptimizer()
    lukewarm = opt._get_lukewarm_candidates(history_for_prediction, rules['minNumber'], rules['maxNumber'])
    regime = opt.regime_detector.detect_regime(history_for_prediction)
    print(f"DEBUG: Lukewarm candidates: {sorted(lukewarm)}")
    lukewarm_scores = {n: number_scores.get(n, 0) for n in lukewarm}
    sorted_lukewarm = sorted(lukewarm_scores.items(), key=lambda x: x[1], reverse=True)
    print(f"DEBUG: Lukewarm scores (top 10): {sorted_lukewarm[:10]}")
    print(f"DEBUG: Symmetry score: {regime.get('symmetry_score')}")
    print(f"DEBUG: Regime: {regime.get('regime')}")
    
    # ==================== Part 1: 基礎特徵分析 ====================
    print("\n" + "=" * 100)
    print("📋 Part 1: 開獎號碼基礎特徵分析")
    print("=" * 100)
    
    total_sum = sum(target_numbers)
    odd_count = sum(1 for n in target_numbers if n % 2 == 1)
    even_count = 6 - odd_count
    big_count = sum(1 for n in target_numbers if n > 24)
    
    # 區間分析
    zones = {f"Z{i+1}": 0 for i in range(5)}
    for n in target_numbers:
        if n <= 10: zones["Z1"] += 1
        elif n <= 20: zones["Z2"] += 1
        elif n <= 30: zones["Z3"] += 1
        elif n <= 40: zones["Z4"] += 1
        else: zones["Z5"] += 1
    
    # 連號分析
    sorted_nums = sorted(target_numbers)
    consecutive_pairs = sum(1 for i in range(len(sorted_nums)-1) if sorted_nums[i+1] - sorted_nums[i] == 1)
    
    # 尾數分析
    tail_dist = Counter(n % 10 for n in target_numbers)
    
    # 與前50期比較
    recent_50 = history_for_prediction[:50]
    avg_sum_50 = np.mean([sum(d['numbers']) for d in recent_50]) if recent_50 else 0
    avg_odd_50 = np.mean([sum(1 for n in d['numbers'] if n % 2 == 1) for d in recent_50]) if recent_50 else 0
    avg_big_50 = np.mean([sum(1 for n in d['numbers'] if n > 24) for d in recent_50]) if recent_50 else 0
    
    print(f"\n{'特徵':<20} | {'本期':>8} | {'前50期均值':>10} | {'狀態':>15}")
    print("-" * 70)
    print(f"{'總和值':<20} | {total_sum:>8} | {avg_sum_50:>10.1f} | {'⚠️ 偏低' if total_sum < avg_sum_50 - 15 else '✅ 正常':>15}")
    print(f"{'奇數個數':<20} | {odd_count:>8} | {avg_odd_50:>10.1f} | {'✅ 平衡' if 2 <= odd_count <= 4 else '⚠️ 偏多/少':>15}")
    print(f"{'大號個數':<20} | {big_count:>8} | {avg_big_50:>10.1f} | {'✅ 平衡' if 2 <= big_count <= 4 else '⚠️ 偏多/少':>15}")
    print(f"{'連號對數':<20} | {consecutive_pairs:>8} | {'N/A':>10} | {'✅ 正常' if consecutive_pairs <= 0 else '⚠️ 密集':>15}")
    
    # 跡象分析 (Gaps: 3, 5, 7, 7, 3)
    gaps = [sorted_nums[i+1] - sorted_nums[i] for i in range(len(sorted_nums)-1)]
    print(f"📊 號碼間距 (Gaps): {gaps} -> 呈高度對稱性 3-5-7-7-3")
    print(f"📊 區間分佈: {zones}")
    print(f"📊 尾數分佈: {dict(tail_dist)}")
    
    # ==================== Part 2: 全策略預測比較 ====================
    print("\n" + "=" * 100)
    print("🔬 Part 2: 全策略預測比較 (誰最接近?)")
    print("=" * 100)
    
    results = []
    
    # 1. TS3+ (5-bets)
    print("🚀 運行 TS3+ (Triple Strike Plus)...")
    try:
        ts3_res = opt.generate_verified_ts3_plus_5bets(history_for_prediction, rules)
        for b in ts3_res.get('bets', []):
            nums = b['numbers']; hit = len(set(nums) & all_target_main)
            name = b.get('name', b.get('source', 'unknown'))
            results.append((f"TS3-{name}", nums, hit, "N/A"))
    except Exception as e:
        print(f"TS3 Error: {e}")

    # 2. Orthogonal 3-Bet
    print("🚀 運行 Orthogonal 3-Bet...")
    try:
        ortho_res = opt.generate_orthogonal_strategy_3bets(history_for_prediction, rules, number_scores)
        for b in ortho_res.get('bets', []):
            nums = b['numbers']; hit = len(set(nums) & all_target_main)
            name = b.get('name', b.get('source', 'unknown'))
            results.append((f"Ortho-{name}", nums, hit, "N/A"))
    except Exception as e:
        print(f"Ortho Error: {e}")

    # 3. SOTA
    print("🚀 運行 SOTA Transformer...")
    try:
        engine = UnifiedPredictionEngine()
        sota_res = engine.sota_predict(history_for_prediction, rules)
        sota_pred = sorted(sota_res.get('numbers', []))
        sota_hit = len(set(sota_pred) & all_target_main)
        results.append(('SOTA Transformer', sota_pred, sota_hit, sota_res.get('special', 'N/A')))
    except Exception as e:
        print(f"SOTA Error: {e}")

    # 4. Entropy Transformer
    print("🚀 運行 Entropy Transformer...")
    try:
        model = EntropyTransformerModel(lottery_rules=rules)
        probs = model.predict(history_for_prediction)
        et_pred = sorted([int(i + 1) for i in np.argsort(probs)[-6:]])
        et_hit = len(set(et_pred) & all_target_main)
        results.append(('Entropy Transformer', et_pred, et_hit, "N/A"))
    except Exception as e:
        print(f"ET Error: {e}")

    # 5. Hyper-Precision 2-Bet
    print("🚀 運行 Hyper-Precision 2-Bet...")
    try:
        hyper_res = opt.generate_hyper_precision_2bets(history_for_prediction, rules, number_scores)
        for b in hyper_res.get('bets', []):
            nums = b['numbers']; hit = len(set(nums) & all_target_main)
            name = b.get('name', b.get('source', 'unknown'))
            results.append((f"Hyper-{name}", nums, hit, "N/A"))
    except Exception as e:
        print(f"Hyper Error: {e}")

    # 6. Statistics methods
    print("🚀 運行 統計學方法 (Bayesian, Markov, etc.)...")
    from models.unified_predictor import prediction_engine as pe
    for name, func in [("Bayesian", pe.bayesian_predict), ("Markov", pe.markov_predict), 
                       ("HotCold", pe.hot_cold_mix_predict), ("Deviation", pe.deviation_predict),
                       ("Frequency", pe.frequency_predict), ("Trend", pe.trend_predict)]:
        try:
            res = func(history_for_prediction, rules)
            pred = sorted(res.get('numbers', []))
            hit = len(set(pred) & all_target_main)
            results.append((name, pred, hit, "N/A"))
        except Exception as e:
            print(f"{name} Error: {e}")

    # ==================== 結果彙整 ====================
    results.sort(key=lambda x: x[2], reverse=True)
    
    print("\n" + "=" * 100)
    print(f"{'排名':<4} | {'策略名稱':<30} | {'命中':>4} | {'預測號碼'}")
    print("-" * 100)
    for rank, (name, pred, hits, _) in enumerate(results[:25], 1):
        pred_str = ", ".join([f"{n:02d}" for n in sorted(pred)]) if pred else "N/A"
        match_str = ""
        if hits > 0:
            matches = sorted(list(set(pred) & all_target_main))
            match_str = f" (中: {matches})"
        print(f"{rank:<4} | {name:<30} | {hits:>4} | {pred_str}{match_str}")

    # ==================== 分析沒預測到的原因 ====================
    all_predicted_nums = set()
    for _, pred, _, _ in results:
        all_predicted_nums.update(pred)
    
    missed_nums = all_target_main - all_predicted_nums
    print("\n" + "=" * 100)
    print(f"❌ 沒被任何模型預測到的號碼: {sorted(list(missed_nums)) if missed_nums else 'None'}")
    print("=" * 100)

    return results

if __name__ == '__main__':
    analyze()
