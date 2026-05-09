import numpy as np
import sys
import os
import json

# Setup path
sys.path.insert(0, os.getcwd())

from models.entropy_transformer import EntropyTransformerModel
from models.optimized_ensemble import OptimizedEnsemblePredictor
from models.unified_predictor import UnifiedPredictionEngine
from common import load_backend_history

def analyze():
    # 用戶提供的號碼: 01, 03, 12, 33, 39, 41, [特別號 29]
    target_numbers = [1, 3, 12, 33, 39, 41]
    special_number = 29
    all_target_main = set(target_numbers)
    
    lottery_type = 'BIG_LOTTO'
    print(f"🎯 目標號碼: {sorted(list(target_numbers))} (特別號: {special_number})")
    print("-" * 90)

    history, rules = load_backend_history(lottery_type)
    print(f"📊 載入歷史數據: {len(history)} 期")
    
    engine = UnifiedPredictionEngine()
    results = []

    # --- 預測器 1: Entropy Transformer ---
    print("🚀 正在運行 Entropy Transformer...")
    try:
        model = EntropyTransformerModel(lottery_rules=rules)
        probs = model.predict(history)
        et_pred = sorted([int(i + 1) for i in np.argsort(probs)[-6:]])
        et_hit = len(set(et_pred) & all_target_main)
        results.append(('Entropy Transformer', et_pred, et_hit, "N/A"))
    except Exception as e:
        print(f"❌ Entropy Transformer 失敗: {e}")

    # --- 預測器 2: Optimized Ensemble (快速版) ---
    print("🚀 正在運行 Optimized Ensemble (取其主推 bet1)...")
    try:
        ensemble = OptimizedEnsemblePredictor(engine)
        # 覆蓋權重計算為固定，避免長時間回測
        ensemble.calculate_strategy_weights = lambda h, r, **kwargs: {k: 1.0/len(ensemble.strategy_methods) for k in ensemble.strategy_methods}
        
        res = ensemble.predict(history, rules)
        bet1 = res['bet1']['numbers']
        spec1 = res['bet1']['special']
        bet1_hit = len(set(bet1) & all_target_main)
        results.append(('Optimized Ensemble (Fast)', bet1, bet1_hit, spec1))
    except Exception as e:
        print(f"❌ Optimized Ensemble 失敗: {e}")

    # --- 預測器 3: SOTA Transformer ---
    print("🚀 正在運行 SOTA (Pattern-Aware Transformer)...")
    try:
        sota_res = engine.sota_predict(history, rules)
        sota_pred = sota_res.get('numbers', [])
        sota_hit = len(set(sota_pred) & all_target_main)
        results.append(('SOTA Transformer', sota_pred, sota_hit, sota_res.get('special', 'N/A')))
    except Exception as e:
        print(f"❌ SOTA Transformer 失敗: {e}")

    # --- 預測器 4: Frequency Baseline ---
    all_nums = []
    for d in history[-200:]: # 使用最近200期
        all_nums.extend(d['numbers'])
    from collections import Counter
    top_freq = sorted([n for n, c in Counter(all_nums).most_common(6)])
    freq_hit = len(set(top_freq) & all_target_main)
    results.append(('Frequency Baseline (R200)', top_freq, freq_hit, "N/A"))

    # 排序並顯示結果
    results.sort(key=lambda x: (x[2], 1 if str(x[3]) == str(special_number) else 0), reverse=True)

    print("\n" + "="*100)
    print(f"{'預測方法':<35} | {'命中主號':<8} | {'預測特別號':<10} | {'預測號碼'}")
    print("-" * 100)
    for name, pred, hits, spec in results:
        spec_str = f"[{spec}]" if str(spec) == str(special_number) else str(spec)
        pred_formatted = ", ".join([f"{n:02d}" for n in sorted(pred)])
        print(f"{name:<35} | {hits:<8} | {spec_str:<10} | {pred_formatted}")
    print("="*100)

    if results:
        winner = results[0]
        print(f"\n🏆 表現最接近的方法是: {winner[0]}")
        hit_nums = sorted(list(set(winner[1]) & all_target_main))
        spec_msg = " [特別號命中!]" if str(winner[3]) == str(special_number) else ""
        print(f"   主號命中 {winner[2]} 個: {hit_nums}{spec_msg}")

if __name__ == '__main__':
    analyze()
