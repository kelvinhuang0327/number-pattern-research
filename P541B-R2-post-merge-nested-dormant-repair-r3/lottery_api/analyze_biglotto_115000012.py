"""
大樂透 第115000012期 全方位檢討分析
開獎日期: 115/02/10 (2026/02/10)
開獎號碼: 06, 16, 20, 21, 24, 35 (特別號: 13)
"""
import numpy as np
import sys
import os
import json
from collections import Counter

# Setup path
lottery_api_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, lottery_api_dir)
os.chdir(lottery_api_dir)

# Fix DB path
from database import db_manager
db_manager.db_path = os.path.join(lottery_api_dir, "data", "lottery_v2.db")

from models.entropy_transformer import EntropyTransformerModel
from models.unified_predictor import UnifiedPredictionEngine
from common import load_backend_history

def analyze():
    # ==================== 開獎數據 ====================
    target_numbers = [6, 16, 20, 21, 24, 35]
    special_number = 13
    all_target_main = set(target_numbers)
    draw_id = 115000012
    
    lottery_type = 'BIG_LOTTO'
    print("=" * 100)
    print(f"🎰 大樂透 第 {draw_id} 期 全方位檢討分析")
    print(f"📅 開獎日期: 2026/02/10")
    print(f"🎯 開獎號碼: {sorted(target_numbers)} (特別號: {special_number})")
    print("=" * 100)
    
    # ==================== 載入歷史數據 ====================
    history, rules = load_backend_history(lottery_type)
    # 只使用目標期之前的數據 (嚴格防止資料洩漏)
    history_for_prediction = [d for d in history if int(d['draw']) < draw_id]
    
    print(f"\n📊 載入預測用歷史數據: {len(history_for_prediction)} 期")
    print(f"   最新一期: {history_for_prediction[0]['draw']} ({history_for_prediction[0].get('date','N/A')})")
    print(f"   規則: pickCount={rules.get('pickCount',6)}, maxNumber={rules.get('maxNumber',49)}")
    
    # ==================== Part 1: 基礎特徵分析 ====================
    print("\n" + "=" * 100)
    print("📋 Part 1: 開獎號碼基礎特徵分析")
    print("=" * 100)
    
    total_sum = sum(target_numbers)
    odd_count = sum(1 for n in target_numbers if n % 2 == 1)
    even_count = 6 - odd_count
    big_count = sum(1 for n in target_numbers if n > 24)  # 49/2 ≈ 24
    small_count = 6 - big_count
    
    # 區間分析 (Z1: 1-10, Z2: 11-20, Z3: 21-30, Z4: 31-40, Z5: 41-49)
    zones = {f"Z{i+1}": 0 for i in range(5)}
    zone_labels = {"Z1": "01-10", "Z2": "11-20", "Z3": "21-30", "Z4": "31-40", "Z5": "41-49"}
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
    
    # 與前30期比較
    recent_30 = history_for_prediction[:30]
    avg_sum_30 = np.mean([sum(d['numbers']) for d in recent_30])
    avg_odd_30 = np.mean([sum(1 for n in d['numbers'] if n % 2 == 1) for d in recent_30])
    avg_big_30 = np.mean([sum(1 for n in d['numbers'] if n > 24) for d in recent_30])
    avg_consec_30 = np.mean([sum(1 for i in range(len(sorted(d['numbers']))-1) if sorted(d['numbers'])[i+1] - sorted(d['numbers'])[i] == 1) for d in recent_30])
    
    # 各區間平均
    zone_avgs = {f"Z{z+1}": 0 for z in range(5)}
    for d in recent_30:
        for n in d['numbers']:
            if n <= 10: zone_avgs["Z1"] += 1
            elif n <= 20: zone_avgs["Z2"] += 1
            elif n <= 30: zone_avgs["Z3"] += 1
            elif n <= 40: zone_avgs["Z4"] += 1
            else: zone_avgs["Z5"] += 1
    for k in zone_avgs: zone_avgs[k] /= 30
    
    print(f"\n{'特徵':<20} | {'本期':>8} | {'近30期均值':>10} | {'狀態':>15}")
    print("-" * 70)
    print(f"{'總和值':<20} | {total_sum:>8} | {avg_sum_30:>10.1f} | {'⚠️ 偏高' if total_sum > avg_sum_30 + 15 else '⚠️ 偏低' if total_sum < avg_sum_30 - 15 else '✅ 正常':>15}")
    print(f"{'奇數個數':<20} | {odd_count:>8} | {avg_odd_30:>10.1f} | {'⚠️ 偏高' if odd_count > avg_odd_30 + 1 else '⚠️ 偏低' if odd_count < avg_odd_30 - 1 else '✅ 正常':>15}")
    print(f"{'大號個數(>24)':<20} | {big_count:>8} | {avg_big_30:>10.1f} | {'⚠️ 偏高' if big_count > avg_big_30 + 1 else '⚠️ 偏低' if big_count < avg_big_30 - 1 else '✅ 正常':>15}")
    print(f"{'連號對數':<20} | {consecutive_pairs:>8} | {avg_consec_30:>10.2f} | {'⚠️ 很多' if consecutive_pairs > avg_consec_30 * 2 else '✅ 正常':>15}")
    
    print(f"\n{'區間':<8} | {'範圍':<8} | {'本期':>4} | {'近30期均值':>10} | {'號碼':>20}")
    print("-" * 60)
    for z in ["Z1", "Z2", "Z3", "Z4", "Z5"]:
        zone_nums = [n for n in target_numbers if (z == "Z1" and n <= 10) or (z == "Z2" and 11 <= n <= 20) or (z == "Z3" and 21 <= n <= 30) or (z == "Z4" and 31 <= n <= 40) or (z == "Z5" and n >= 41)]
        print(f"{z:<8} | {zone_labels[z]:<8} | {zones[z]:>4} | {zone_avgs[z]:>10.2f} | {zone_nums}")
    
    print(f"\n📊 尾數分佈: {dict(tail_dist)}")
    print(f"📊 連號組: {[(sorted_nums[i], sorted_nums[i+1]) for i in range(len(sorted_nums)-1) if sorted_nums[i+1] - sorted_nums[i] == 1]}")
    
    # 重號分析 (與上期比較)
    prev_draw = history_for_prediction[0]
    prev_numbers = set(prev_draw['numbers'])
    repeat_numbers = all_target_main & prev_numbers
    print(f"📊 重號 (來自上期 {prev_draw['draw']}): {sorted(list(repeat_numbers)) if repeat_numbers else '無'}")
    print(f"   上期號碼: {sorted(prev_draw['numbers'])}")
    
    # ==================== Part 2: 全策略預測比較 ====================
    print("\n" + "=" * 100)
    print("🔬 Part 2: 全策略預測比較 (Best Match Competition)")
    print("=" * 100)
    
    results = []
    max_num = rules.get('maxNumber', 49)
    pick_count = rules.get('pickCount', 6)
    
    # Helper: 計算 number_scores (純統計，不依賴 UnifiedPredictionEngine)
    recent_nums_all = [n for d in history_for_prediction[:200] for n in d['numbers']]
    freq_counter_all = Counter(recent_nums_all)
    number_scores = {n: freq_counter_all.get(n, 0) for n in range(1, max_num + 1)}
    
    # --- 預測器 1: Entropy Transformer ---
    print("\n🚀 運行 Entropy Transformer...")
    try:
        model = EntropyTransformerModel(lottery_rules=rules)
        probs = model.predict(history_for_prediction)
        et_pred = sorted([int(i + 1) for i in np.argsort(probs)[-pick_count:]])
        et_hit = len(set(et_pred) & all_target_main)
        results.append(('Entropy Transformer', et_pred, et_hit, "N/A"))
        print(f"   預測: {et_pred} → 命中 {et_hit}")
    except Exception as e:
        print(f"   ❌ 失敗: {e}")

    # --- 預測器 2: Optimized Ensemble (8注模式) ---
    print("🚀 運行 Optimized Ensemble (8bet)...")
    try:
        from models.optimized_ensemble import OptimizedEnsemblePredictor
        ensemble_model = OptimizedEnsemblePredictor(rules)
        ens_res = ensemble_model.predict(history_for_prediction, n_bets=8)
        all_bets = ens_res.get('all_bets', [])
        
        best_ens_hit = -1
        best_ens_bet = None
        for i, nums in enumerate(all_bets):
            hit = len(set(nums) & all_target_main)
            if hit > best_ens_hit:
                best_ens_hit = hit
                best_ens_bet = nums
        if best_ens_bet:
            results.append(('Optimized Ensemble (Best/8)', best_ens_bet, best_ens_hit, "N/A"))
            print(f"   最佳注: {best_ens_bet} → 命中 {best_ens_hit}")
    except Exception as e:
        print(f"   ❌ 失敗: {e}")

    # --- 預測器 3: SOTA Transformer (via Engine) ---
    print("🚀 運行 SOTA Transformer...")
    try:
        engine = UnifiedPredictionEngine()
        sota_res = engine.sota_predict(history_for_prediction, rules)
        sota_pred = sorted(sota_res.get('numbers', []))
        sota_hit = len(set(sota_pred) & all_target_main)
        results.append(('SOTA Transformer', sota_pred, sota_hit, sota_res.get('special', 'N/A')))
        print(f"   預測: {sota_pred} → 命中 {sota_hit}")
    except Exception as e:
        print(f"   ❌ SOTA 失敗: {e}")

    # --- 預測器 4: VAE Latent Distribution (via Engine) ---
    print("🚀 運行 VAE Latent Distribution...")
    try:
        if not 'engine' in dir(): engine = UnifiedPredictionEngine()
        vae_res = engine.vae_predict(history_for_prediction, rules)
        vae_pred = sorted(vae_res.get('numbers', []))
        vae_hit = len(set(vae_pred) & all_target_main)
        results.append(('VAE Latent Distribution', vae_pred, vae_hit, "N/A"))
        print(f"   預測: {vae_pred} → 命中 {vae_hit}")
    except Exception as e:
        print(f"   ❌ VAE 失敗: {e}")

    # --- 預測器 5: Orthogonal Strategy (3-bet) ---
    print("🚀 運行 Orthogonal Strategy 3-bet...")
    try:
        from models.multi_bet_optimizer import MultiBetOptimizer
        optimizer = MultiBetOptimizer()
        ortho_res = optimizer.generate_orthogonal_strategy_3bets(history_for_prediction, rules, number_scores)
        
        best_ortho_hit = -1
        best_ortho_bet = None
        all_ortho_bets = []
        for b in ortho_res.get('bets', []):
            nums = b['numbers']
            hit = len(set(nums) & all_target_main)
            all_ortho_bets.append((b.get('name', 'Unknown'), nums, hit))
            if hit > best_ortho_hit:
                best_ortho_hit = hit
                best_ortho_bet = nums
        
        results.append(('Orthogonal 3-Bet (Best)', best_ortho_bet, best_ortho_hit, "N/A"))
        for name, nums, hit in all_ortho_bets:
            print(f"   {name}: {nums} → 命中 {hit}")
            results.append((f'Ortho-{name}', nums, hit, "N/A"))
    except Exception as e:
        print(f"   ❌ Orthogonal 失敗: {e}")
        import traceback; traceback.print_exc()

    # --- 預測器 6: Tri-Core 3-bet ---
    print("🚀 運行 Tri-Core 3-bet...")
    try:
        from models.multi_bet_optimizer import MultiBetOptimizer
        opt2 = MultiBetOptimizer()
        tri_res = opt2.generate_tri_core_3bets(history_for_prediction, rules, number_scores, num_bets=3)
        best_tri_hit = -1
        best_tri_bet = None
        all_tri_bets = []
        for b in tri_res.get('bets', []):
            nums = b['numbers']
            hit = len(set(nums) & all_target_main)
            all_tri_bets.append((b.get('name', 'Unknown'), nums, hit))
            if hit > best_tri_hit:
                best_tri_hit = hit
                best_tri_bet = nums
        results.append(('Tri-Core 3-Bet (Best)', best_tri_bet, best_tri_hit, "N/A"))
        for name, nums, hit in all_tri_bets:
            print(f"   {name}: {nums} → 命中 {hit}")
            results.append((f'TriCore-{name}', nums, hit, "N/A"))
    except Exception as e:
        print(f"   ❌ Tri-Core 失敗: {e}")
        import traceback; traceback.print_exc()

    # --- 預測器 7: Hyper-Precision 2-bet ---
    print("🚀 運行 Hyper-Precision 2-bet...")
    try:
        from models.multi_bet_optimizer import MultiBetOptimizer
        opt3 = MultiBetOptimizer()
        hyper_res = opt3.generate_hyper_precision_2bets(history_for_prediction, rules, number_scores, num_bets=2)
        best_hyper_hit = -1
        best_hyper_bet = None
        for b in hyper_res.get('bets', []):
            nums = b['numbers']
            hit = len(set(nums) & all_target_main)
            if hit > best_hyper_hit:
                best_hyper_hit = hit
                best_hyper_bet = nums
            print(f"   {b.get('name','')}: {nums} → 命中 {hit}")
            results.append((f"Hyper-{b.get('name','')}", nums, hit, "N/A"))
        results.append(('Hyper-Precision 2-Bet (Best)', best_hyper_bet, best_hyper_hit, "N/A"))
    except Exception as e:
        print(f"   ❌ Hyper-Precision 失敗: {e}")
        import traceback; traceback.print_exc()

    # --- 預測器 8: Fourier Rhythm ---
    print("🚀 運行 Fourier Rhythm...")
    try:
        from models.fourier_rhythm import FourierRhythmPredictor
        fr = FourierRhythmPredictor(min_val=1, max_val=49)
        fr_scores = fr.predict_main_numbers(history_for_prediction, max_num=49)
        fr_top = sorted(fr_scores.keys(), key=lambda x: fr_scores[x], reverse=True)[:pick_count]
        fr_pred = sorted(fr_top)
        fr_hit = len(set(fr_pred) & all_target_main)
        results.append(('Fourier Rhythm', fr_pred, fr_hit, "N/A"))
        print(f"   預測: {fr_pred} → 命中 {fr_hit}")
    except Exception as e:
        print(f"   ❌ Fourier Rhythm 失敗: {e}")

    print("🚀 運行基礎統計方法群...")
    try:
        from models.unified_predictor import prediction_engine as pe
        stat_methods = [
            ("Frequency Top6", pe.frequency_predict),
            ("Bayesian", pe.bayesian_predict),
            ("Markov Transition", pe.markov_predict),
            ("Monte Carlo", pe.monte_carlo_predict),
            ("Deviation", pe.deviation_predict),
            ("Zone Balance", pe.zone_balance_predict),
            ("Hot Cold Mix", pe.hot_cold_mix_predict),
            ("Odd Even Balance", pe.odd_even_balance_predict),
            ("Trend", pe.trend_predict),
            ("Sum Range", pe.sum_range_predict),
            ("Number Pairs", pe.number_pairs_predict),
            ("Ensemble", pe.ensemble_predict),
            ("Random Forest", pe.random_forest_predict),
            ("Clustering", pe.clustering_predict),
            ("Temporal", pe.temporal_predict),
        ]
        for method_name, method_func in stat_methods:
            try:
                res = method_func(history_for_prediction, rules)
                pred = sorted(res.get('numbers', []))
                hit = len(set(pred) & all_target_main)
                results.append((method_name, pred, hit, res.get('special', 'N/A')))
                print(f"   {method_name}: {pred} → 命中 {hit}")
            except Exception as e2:
                print(f"   ❌ {method_name} 失敗: {e2}")
    except Exception as e:
        print(f"   ❌ 統計方法群載入失敗: {e}")

    # --- 預測器 10: Cold Rebound (手工策略) ---
    print("🚀 運行 Cold Rebound 策略...")
    try:
        recent_nums = [n for d in history_for_prediction[:30] for n in d['numbers']]
        freq_counter = Counter(recent_nums)
        all_possible = set(range(1, max_num + 1))
        cold_scores = {n: freq_counter.get(n, 0) for n in all_possible}
        coldest = sorted(cold_scores.keys(), key=lambda x: (cold_scores[x], -x))[:pick_count]
        cold_pred = sorted(coldest)
        cold_hit = len(set(cold_pred) & all_target_main)
        results.append(('Cold Rebound', cold_pred, cold_hit, "N/A"))
        print(f"   預測: {cold_pred} → 命中 {cold_hit}")
    except Exception as e:
        print(f"   ❌ Cold Rebound 失敗: {e}")

    # --- 預測器 11: Gap Rebound (遺漏期數) ---
    print("🚀 運行 Gap Rebound 策略...")
    try:
        gaps = {}
        for n in range(1, max_num + 1):
            for i, d in enumerate(history_for_prediction):
                if n in d['numbers']:
                    gaps[n] = i
                    break
            else:
                gaps[n] = len(history_for_prediction)
        gap_top = sorted(gaps.keys(), key=lambda x: gaps[x], reverse=True)[:pick_count]
        gap_pred = sorted(gap_top)
        gap_hit = len(set(gap_pred) & all_target_main)
        results.append(('Gap Rebound', gap_pred, gap_hit, "N/A"))
        print(f"   預測: {gap_pred} → 命中 {gap_hit}")
    except Exception as e:
        print(f"   ❌ Gap Rebound 失敗: {e}")
    
    # --- 預測器 12: Echo (近期重現) ---
    print("🚀 運行 Echo 策略...")
    try:
        echo_pred = sorted(list(prev_numbers))[:pick_count]
        echo_hit = len(set(echo_pred) & all_target_main)
        results.append(('Echo (上期重現)', echo_pred, echo_hit, "N/A"))
        print(f"   預測: {echo_pred} → 命中 {echo_hit}")
    except Exception as e:
        print(f"   ❌ Echo 失敗: {e}")

    # --- 預測器 13: Co-occurrence Graph ---
    print("🚀 運行 Co-occurrence Graph...")
    try:
        from models.cooccurrence_graph import CooccurrenceGraphPredictor
        cograph = CooccurrenceGraphPredictor()
        cg_res = cograph.predict(history_for_prediction, rules)
        cg_pred = sorted(cg_res.get('numbers', []))
        cg_hit = len(set(cg_pred) & all_target_main)
        results.append(('Co-occurrence Graph', cg_pred, cg_hit, "N/A"))
        print(f"   預測: {cg_pred} → 命中 {cg_hit}")
    except Exception as e:
        print(f"   ❌ Co-occurrence 失敗: {e}")

    # --- 預測器 14: Concentrated Pool ---
    print("🚀 運行 Concentrated Pool...")
    try:
        from models.concentrated_pool_predictor import ConcentratedPoolPredictor
        cp = ConcentratedPoolPredictor()
        cp_res = cp.predict(history_for_prediction, rules)
        cp_pred = sorted(cp_res.get('numbers', []))
        cp_hit = len(set(cp_pred) & all_target_main)
        results.append(('Concentrated Pool', cp_pred, cp_hit, "N/A"))
        print(f"   預測: {cp_pred} → 命中 {cp_hit}")
    except Exception as e:
        print(f"   ❌ Concentrated Pool 失敗: {e}")

    # --- 預測器 15: Anomaly Predictor ---
    print("🚀 運行 Anomaly Predictor...")
    try:
        from models.anomaly_predictor import AnomalyPredictor
        ap = AnomalyPredictor()
        ap_res = ap.predict(history_for_prediction, rules)
        ap_pred = sorted(ap_res.get('numbers', []))
        ap_hit = len(set(ap_pred) & all_target_main)
        results.append(('Anomaly Predictor', ap_pred, ap_hit, "N/A"))
        print(f"   預測: {ap_pred} → 命中 {ap_hit}")
    except Exception as e:
        print(f"   ❌ Anomaly 失敗: {e}")

    # --- 預測器 16: Zone Balance (手工) ---
    print("🚀 運行 Zone Balance 手工策略...")
    try:
        # 從每個 zone 各取 1-2 個頻率最高的
        zone_preds = []
        for z_start, z_end in [(1,10), (11,20), (21,30), (31,40), (41,49)]:
            zone_nums = [(n, freq_counter_all.get(n, 0)) for n in range(z_start, z_end + 1)]
            zone_nums.sort(key=lambda x: x[1], reverse=True)
            zone_preds.append(zone_nums[0][0])
        # 補充一個全局最高的不重複號
        remaining = sorted(freq_counter_all.keys(), key=lambda x: freq_counter_all[x], reverse=True)
        for r in remaining:
            if r not in zone_preds:
                zone_preds.append(r)
                break
        zb_pred = sorted(zone_preds[:pick_count])
        zb_hit = len(set(zb_pred) & all_target_main)
        results.append(('Zone Balance (手工)', zb_pred, zb_hit, "N/A"))
        print(f"   預測: {zb_pred} → 命中 {zb_hit}")
    except Exception as e:
        print(f"   ❌ Zone Balance 失敗: {e}")

    # --- 預測器 17: Hot-Cold Mix (手工) ---
    print("🚀 運行 Hot-Cold Mix 手工策略...")
    try:
        recent_30_nums = [n for d in history_for_prediction[:30] for n in d['numbers']]
        freq_30 = Counter(recent_30_nums)
        hot_3 = sorted([n for n, _ in freq_30.most_common(3)])
        cold_scores_30 = {n: freq_30.get(n, 0) for n in range(1, max_num + 1)}
        cold_3 = sorted(sorted(cold_scores_30.keys(), key=lambda x: (cold_scores_30[x], -x))[:3])
        hc_pred = sorted(hot_3 + cold_3)
        hc_hit = len(set(hc_pred) & all_target_main)
        results.append(('Hot-Cold Mix (手工)', hc_pred, hc_hit, "N/A"))
        print(f"   預測: {hc_pred} → 命中 {hc_hit}")
    except Exception as e:
        print(f"   ❌ Hot-Cold Mix 失敗: {e}")

    # ==================== 結果排名 ====================
    # Remove duplicates and sort
    seen = set()
    unique_results = []
    for r in results:
        key = (r[0], tuple(sorted(r[1])) if r[1] else ())
        if key not in seen:
            seen.add(key)
            unique_results.append(r)
    results = unique_results
    results.sort(key=lambda x: x[2], reverse=True)
    
    print("\n" + "=" * 100)
    print("🏆 Part 3: 全策略預測結果排名")
    print("=" * 100)
    print(f"\n{'排名':<4} | {'策略名稱':<35} | {'命中數':>6} | {'特別號':>6} | {'預測號碼'}")
    print("-" * 100)
    for rank, (name, pred, hits, spec) in enumerate(results, 1):
        stars = "★" * hits
        spec_str = f"✓{spec}" if str(spec) == str(special_number) else str(spec)
        pred_str = ", ".join([f"{n:02d}" for n in sorted(pred)]) if pred else "N/A"
        hit_nums = sorted(list(set(pred) & all_target_main)) if pred else []
        print(f"{rank:<4} | {name:<35} | {hits:>4} {stars:<4} | {spec_str:>6} | {pred_str}")
        if hit_nums:
            print(f"     |{'':35} |        |        | → 命中: {hit_nums}")
    
    # ==================== Part 4: 遺漏號碼深度分析 ====================
    print("\n" + "=" * 100)
    print("🔍 Part 4: 各號碼特徵深度分析 (為何命中 / 為何遺漏)")
    print("=" * 100)
    
    for num in sorted(target_numbers):
        # 頻率分析
        freq_30 = sum(1 for d in history_for_prediction[:30] for n in d['numbers'] if n == num)
        freq_50 = sum(1 for d in history_for_prediction[:50] for n in d['numbers'] if n == num)
        freq_100 = sum(1 for d in history_for_prediction[:100] for n in d['numbers'] if n == num)
        
        # 遺漏分析
        gap = 0
        for d in history_for_prediction:
            if num in d['numbers']:
                break
            gap += 1
        
        avg_gap = 49 / 6  # 期望間隔
        
        # 被多少方法預測到
        methods_predicted = [(name, pred) for name, pred, hit, spec in results if pred and num in pred]
        
        is_cold = freq_30 <= 2
        is_hot = freq_30 >= 6
        
        print(f"\n--- 號碼 {num:02d} ---")
        print(f"  近30期頻率: {freq_30} ({freq_30/30*100:.1f}%)")
        print(f"  近50期頻率: {freq_50} ({freq_50/50*100:.1f}%)")
        print(f"  近100期頻率: {freq_100} ({freq_100/100*100:.1f}%)")
        print(f"  遺漏期數: {gap} (期望: {avg_gap:.1f})")
        print(f"  冷/熱: {'🥶 冷號' if is_cold else '🔥 熱號' if is_hot else '😐 中性'}")
        print(f"  被 {len(methods_predicted)}/{len(results)} 個方法預測到")
        if methods_predicted:
            print(f"  預測方法: {[m[0] for m in methods_predicted]}")
    
    # ==================== Part 5: Union Coverage 分析 ====================
    print("\n" + "=" * 100)
    print("📐 Part 5: 多注聯合覆蓋分析 (2注/3注策略)")
    print("=" * 100)
    
    # 找出最佳2注組合和3注組合
    from itertools import combinations
    
    if len(results) >= 2:
        best_2bet_cov = 0
        best_2bet_pair = None
        best_3bet_cov = 0
        best_3bet_triple = None
        
        for combo in combinations(range(len(results)), 2):
            union = set()
            for idx in combo:
                if results[idx][1]:
                    union.update(set(results[idx][1]) & all_target_main)
            cov = len(union)
            if cov > best_2bet_cov:
                best_2bet_cov = cov
                best_2bet_pair = combo
        
        if len(results) >= 3:
            for combo in combinations(range(len(results)), 3):
                union = set()
                for idx in combo:
                    if results[idx][1]:
                        union.update(set(results[idx][1]) & all_target_main)
                cov = len(union)
                if cov > best_3bet_cov:
                    best_3bet_cov = cov
                    best_3bet_triple = combo
        
        if best_2bet_pair:
            print(f"\n🥇 最佳2注組合覆蓋: {best_2bet_cov}/6 號碼")
            for idx in best_2bet_pair:
                name, pred, hit, _ = results[idx]
                print(f"   → {name}: {pred} (命中 {hit})")
            two_union = set()
            for idx in best_2bet_pair:
                if results[idx][1]:
                    two_union.update(set(results[idx][1]) & all_target_main)
            print(f"   聯合命中: {sorted(two_union)}")
            print(f"   未覆蓋: {sorted(all_target_main - two_union)}")
        
        if best_3bet_triple:
            print(f"\n🥇 最佳3注組合覆蓋: {best_3bet_cov}/6 號碼")
            for idx in best_3bet_triple:
                name, pred, hit, _ = results[idx]
                print(f"   → {name}: {pred} (命中 {hit})")
            three_union = set()
            for idx in best_3bet_triple:
                if results[idx][1]:
                    three_union.update(set(results[idx][1]) & all_target_main)
            print(f"   聯合命中: {sorted(three_union)}")
            print(f"   未覆蓋: {sorted(all_target_main - three_union)}")

    # ==================== Part 6: 共現分析 ====================
    print("\n" + "=" * 100)
    print("🔗 Part 6: 開獎號碼共現分析")
    print("=" * 100)
    
    # 分析開獎號碼間的歷史共現次數
    recent_200 = history_for_prediction[:200]
    for i, n1 in enumerate(sorted(target_numbers)):
        for n2 in sorted(target_numbers)[i+1:]:
            cooccur = sum(1 for d in recent_200 if n1 in d['numbers'] and n2 in d['numbers'])
            print(f"  ({n1:02d}, {n2:02d}): 共現 {cooccur} 次/200期 ({cooccur/200*100:.1f}%)")

    # ==================== Summary ====================
    print("\n" + "=" * 100)
    print("📝 Part 7: 總結")
    print("=" * 100)
    
    if results:
        winner = results[0]
        print(f"\n🏆 表現最接近的方法: {winner[0]}")
        print(f"   命中 {winner[2]}/6 個主號碼")
        hit_nums = sorted(list(set(winner[1]) & all_target_main)) if winner[1] else []
        print(f"   命中號碼: {hit_nums}")
        missed = sorted(list(all_target_main - set(winner[1]))) if winner[1] else sorted(target_numbers)
        print(f"   遺漏號碼: {missed}")
    
    return results

if __name__ == '__main__':
    results = analyze()
