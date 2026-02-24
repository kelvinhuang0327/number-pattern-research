import numpy as np
import sys
import os
import json

# Setup path
sys.path.insert(0, os.getcwd())

# 🔧 Fix: Ensure we use the correct database path
from models.database import db_manager
db_manager.db_path = "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db"

from models.entropy_transformer import EntropyTransformerModel
from models.unified_predictor import UnifiedPredictionEngine
from common import load_backend_history

def analyze():
    # Winning Number: 04, 12, 24, 25, 39, 48 [Special 09]
    target_numbers = [4, 12, 24, 25, 39, 48]
    special_number = 9
    all_target_main = set(target_numbers)
    
    lottery_type = 'BIG_LOTTO'
    print(f"🎯 目標號碼: {sorted(list(target_numbers))} (特別號: {special_number})")
    print("-" * 90)

    # Note: We need to predict for 115000011, so we use history UP TO 115000010
    history, rules = load_backend_history(lottery_type)
    # Ensure we use history before the target draw
    history_for_prediction = [d for d in history if int(d['draw']) < 115000011]
    
    print(f"📊 載入預測用歷史數據: {len(history_for_prediction)} 期 (最新一期: {history_for_prediction[0]['draw']})")
    
    engine = UnifiedPredictionEngine()
    results = []

    # --- 預測器 1: Entropy Transformer ---
    print("🚀 正在運行 Entropy Transformer...")
    try:
        model = EntropyTransformerModel(lottery_rules=rules)
        probs = model.predict(history_for_prediction)
        et_pred = sorted([int(i + 1) for i in np.argsort(probs)[-6:]])
        et_hit = len(set(et_pred) & all_target_main)
        results.append(('Entropy Transformer', et_pred, et_hit, "N/A"))
    except Exception as e:
        print(f"❌ Entropy Transformer 失敗: {e}")

    # --- 預測器 2: Optimized Ensemble (8注模式) ---
    print("🚀 正在運行 Optimized Ensemble...")
    try:
        from models.optimized_ensemble import OptimizedEnsemblePredictor
        ensemble_model = OptimizedEnsemblePredictor(rules)
        # 獲取多注
        ens_res = ensemble_model.predict(history_for_prediction, n_bets=8)
        all_bets = ens_res.get('all_bets', [])
             
        best_ens_hit = -1
        best_ens_bet = None
        best_ens_spec = None
        
        for i, nums in enumerate(all_bets):
            # OptimizedEnsemblePredictor doesn't currently predict special for Big Lotto explicitly in 'all_bets' list
            # It just returns numbers.
            hit = len(set(nums) & all_target_main)
            if hit > best_ens_hit:
                best_ens_hit = hit
                best_ens_bet = nums
        
        results.append(('Optimized Ensemble (Best of 8)', best_ens_bet, best_ens_hit, "N/A"))
    except Exception as e:
        print(f"❌ Optimized Ensemble 失敗: {e}")
        import traceback
        traceback.print_exc()

    # --- 預測器 3: SOTA Transformer ---
    print("🚀 正在運行 SOTA (Pattern-Aware Transformer)...")
    try:
        sota_res = engine.sota_predict(history_for_prediction, rules)
        sota_pred = sota_res.get('numbers', [])
        sota_hit = len(set(sota_pred) & all_target_main)
        results.append(('SOTA Transformer', sota_pred, sota_hit, sota_res.get('special', 'N/A')))
    except Exception as e:
        print(f"❌ SOTA Transformer 失敗: {e}")

    # --- 預測器 4: VAE Latent Distribution ---
    print("🚀 正在運行 VAE Latent Distribution...")
    try:
        vae_res = engine.vae_predict(history_for_prediction, rules)
        nums = vae_res['numbers']
        hit = len(set(nums) & all_target_main)
        results.append(('VAE Latent Distribution', nums, hit, "N/A"))
    except Exception as e:
        print(f"❌ VAE 失敗: {e}")

    # --- 預測器 5: Orthogonal Strategy (3-bet) ---
    print("🚀 正在運行 Orthogonal Strategy (3-bet)...")
    try:
        from models.multi_bet_optimizer import MultiBetOptimizer
        optimizer = MultiBetOptimizer()
        ortho_res = optimizer.generate_diversified_bets(history_for_prediction, rules, num_bets=3)
        
        best_ortho_hit = -1
        best_ortho_bet = None
        
        for b in ortho_res['bets']:
            nums = b['numbers']
            hit = len(set(nums) & all_target_main)
            if hit > best_ortho_hit:
                best_ortho_hit = hit
                best_ortho_bet = nums
        
        results.append(('Orthogonal Strategy (Best of 3)', best_ortho_bet, best_ortho_hit, "N/A"))
    except Exception as e:
        print(f"❌ Orthogonal Strategy 失敗: {e}")

    # --- 預測器 6: Frequency Baseline ---
    pick_count = rules.get('pickCount', 6)
    all_nums = [n for d in history_for_prediction for n in d['numbers']]
    from collections import Counter
    top_freq = sorted([n for n, c in Counter(all_nums).most_common(pick_count)])
    freq_hit = len(set(top_freq) & all_target_main)
    results.append(('Frequency Baseline', top_freq, freq_hit, "N/A"))

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
