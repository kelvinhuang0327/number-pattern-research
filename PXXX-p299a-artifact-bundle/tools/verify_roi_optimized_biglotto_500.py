#!/usr/bin/env python3
"""
ROI Optimized Ensemble 大樂透 500 期獨立驗證
============================================
目標：驗證大樂透 2-3 注的 M3+ 命中率
基線：2注 3.69%, 3注 5.49%
"""
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.optimized_ensemble import OptimizedEnsemblePredictor

def verify_roi_optimized_biglotto(n_bets=2):
    """執行 500 期滾動回測"""
    lottery_type = 'BIG_LOTTO'
    rules = get_lottery_rules(lottery_type)

    # 載入資料
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = db.get_all_draws(lottery_type)
    draws = sorted(draws, key=lambda x: (x['date'], x['draw']))

    if len(draws) < 550:
        print(f"❌ 資料不足：僅有 {len(draws)} 期")
        return

    # 初始化預測器
    predictor = OptimizedEnsemblePredictor(rules)

    # 統計變數
    test_periods = 500
    m3_hits = 0
    m4_hits = 0
    m5_hits = 0

    results = []

    # 基線計算
    p_single = 0.0186  # 大樂透 1注 M3+ 基線
    baseline = 1 - (1 - p_single) ** n_bets
    baseline_pct = baseline * 100

    print(f"\n{'='*70}")
    print(f"ROI Optimized Ensemble 500 期獨立驗證 - 大樂透 {n_bets}-bet")
    print(f"{'='*70}")
    print(f"測試期數: {test_periods}")
    print(f"注數: {n_bets}")
    print(f"基線 ({n_bets}-bet M3+): {baseline_pct:.2f}%")
    print(f"{'='*70}\n")

    for i in range(test_periods):
        test_idx = len(draws) - test_periods + i
        history = draws[:test_idx]
        actual_draw = draws[test_idx]
        actual_numbers = set(actual_draw['numbers'])

        if len(history) < 150:
            continue

        # 預測
        try:
            result = predictor.predict(history, n_bets=n_bets)
            all_bets = result.get('all_bets', [])
        except Exception as e:
            print(f"⚠️ 預測失敗 (期 {actual_draw['draw']}): {e}")
            continue

        # 計算最佳命中
        best_match = 0
        best_bet = []
        for bet in all_bets:
            bet_set = set(bet)
            match_count = len(bet_set & actual_numbers)
            if match_count > best_match:
                best_match = match_count
                best_bet = bet

        # 統計
        if best_match >= 3:
            m3_hits += 1
        if best_match >= 4:
            m4_hits += 1
        if best_match >= 5:
            m5_hits += 1

        results.append({
            'draw': actual_draw['draw'],
            'actual': sorted(actual_numbers),
            'best_bet': best_bet,
            'match': best_match
        })

        # 進度顯示
        if (i + 1) % 100 == 0:
            current_rate = m3_hits / (i + 1) * 100
            print(f"進度: {i+1}/{test_periods} | 當前 M3+ 命中率: {current_rate:.2f}%")

    # 最終統計
    total_tested = len(results)
    m3_rate = m3_hits / total_tested * 100 if total_tested > 0 else 0
    m4_rate = m4_hits / total_tested * 100 if total_tested > 0 else 0
    m5_rate = m5_hits / total_tested * 100 if total_tested > 0 else 0

    edge = m3_rate - baseline_pct

    print(f"\n{'='*70}")
    print(f"📊 最終結果 ({n_bets} 注)")
    print(f"{'='*70}")
    print(f"測試期數: {total_tested}")
    print(f"M3+ 命中: {m3_hits} ({m3_rate:.2f}%)")
    print(f"M4+ 命中: {m4_hits} ({m4_rate:.2f}%)")
    print(f"M5+ 命中: {m5_hits} ({m5_rate:.2f}%)")
    print(f"{'='*70}")
    print(f"{n_bets}-bet 基線: {baseline_pct:.2f}%")
    print(f"實際命中率: {m3_rate:.2f}%")
    print(f"Edge: {edge:+.2f}%")
    print(f"{'='*70}")

    # 驗證結論
    if edge >= 1.0:
        verdict = "✅ 驗證通過 - 顯著優勢"
    elif edge >= 0.3:
        verdict = "⚠️ 微弱優勢 - 可考慮使用"
    elif edge >= -0.3:
        verdict = "⚠️ 與隨機相當 - 不建議"
    else:
        verdict = "❌ 驗證失敗 - 低於基線"

    print(f"\n📋 驗證結論: {verdict}")

    # 顯示部分命中詳情
    print(f"\n📝 M3+ 命中樣本 (前 10 筆):")
    m3_samples = [r for r in results if r['match'] >= 3][:10]
    for s in m3_samples:
        print(f"  期 {s['draw']}: 預測 {s['best_bet']} vs 實際 {s['actual']} | 命中 {s['match']}")

    return {
        'n_bets': n_bets,
        'm3_rate': m3_rate,
        'edge': edge,
        'baseline': baseline_pct,
        'verdict': verdict
    }

if __name__ == "__main__":
    print("\n" + "="*70)
    print("開始 ROI Optimized Ensemble 大樂透回測")
    print("="*70)

    # 測試 2 注和 3 注
    results = {}
    for n in [2, 3]:
        results[n] = verify_roi_optimized_biglotto(n_bets=n)
        print("\n")

    # 總結
    print("="*70)
    print("📊 總結對比")
    print("="*70)
    print(f"{'注數':<6} | {'M3+ 命中率':<12} | {'基線':<10} | {'Edge':<10} | 判定")
    print("-"*70)
    for n, r in results.items():
        if r:
            print(f"{n}注    | {r['m3_rate']:.2f}%        | {r['baseline']:.2f}%     | {r['edge']:+.2f}%     | {r['verdict']}")
