#!/usr/bin/env python3
"""
ROI-Stacked (MEL) 500 期獨立驗證
================================
目標：驗證 Gemini 聲稱的 2-bet M3+ 命中率 10.67%
基線：7.59% (使用 1-(1-0.0387)^2)
"""
import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.common import get_lottery_rules
from lottery_api.models.optimized_ensemble import OptimizedEnsemblePredictor

def verify_roi_stacked_500():
    """執行 500 期滾動回測"""
    lottery_type = 'POWER_LOTTO'
    rules = get_lottery_rules(lottery_type)

    # 載入資料
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    draws = db.get_all_draws(lottery_type)
    draws = sorted(draws, key=lambda x: (x['date'], x['draw']))  # 確保時間排序

    if len(draws) < 550:
        print(f"❌ 資料不足：僅有 {len(draws)} 期")
        return

    # 初始化預測器
    predictor = OptimizedEnsemblePredictor(rules)

    # 統計變數
    test_periods = 500
    n_bets = 2
    m3_hits = 0
    m4_hits = 0
    m5_hits = 0

    results = []

    print(f"\n{'='*70}")
    print(f"ROI-Stacked (MEL) 500 期獨立驗證 - 威力彩 2-bet")
    print(f"{'='*70}")
    print(f"測試期數: {test_periods}")
    print(f"注數: {n_bets}")
    print(f"基線 (2-bet M3+): 7.59%")
    print(f"Gemini 聲稱: 10.67%")
    print(f"{'='*70}\n")

    for i in range(test_periods):
        # 滾動窗口：使用 draws[i : len(draws)-test_periods+i] 預測 draws[len(draws)-test_periods+i]
        test_idx = len(draws) - test_periods + i
        history = draws[:test_idx]
        actual_draw = draws[test_idx]
        actual_numbers = set(actual_draw['numbers'])

        if len(history) < 100:
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

    baseline_2bet = 7.59  # 1 - (1-0.0387)^2
    edge = m3_rate - baseline_2bet

    print(f"\n{'='*70}")
    print(f"📊 最終結果")
    print(f"{'='*70}")
    print(f"測試期數: {total_tested}")
    print(f"M3+ 命中: {m3_hits} ({m3_rate:.2f}%)")
    print(f"M4+ 命中: {m4_hits} ({m4_rate:.2f}%)")
    print(f"M5+ 命中: {m5_hits} ({m5_rate:.2f}%)")
    print(f"{'='*70}")
    print(f"2-bet 基線: {baseline_2bet:.2f}%")
    print(f"實際命中率: {m3_rate:.2f}%")
    print(f"Edge: {edge:+.2f}%")
    print(f"{'='*70}")

    # 驗證結論
    gemini_claim = 10.67
    print(f"\n📋 驗證結論:")
    print(f"Gemini 聲稱: {gemini_claim:.2f}%")
    print(f"實際結果: {m3_rate:.2f}%")

    if abs(m3_rate - gemini_claim) <= 2.0:
        print(f"✅ 驗證通過 - 結果在 ±2% 範圍內")
    elif m3_rate >= baseline_2bet:
        print(f"⚠️ 部分通過 - 優於基線但與聲稱有差距")
    else:
        print(f"❌ 驗證失敗 - 低於基線")

    # 顯示部分命中詳情
    print(f"\n📝 M3+ 命中樣本 (前 10 筆):")
    m3_samples = [r for r in results if r['match'] >= 3][:10]
    for s in m3_samples:
        print(f"  期 {s['draw']}: 預測 {s['best_bet']} vs 實際 {s['actual']} | 命中 {s['match']}")

    return {
        'm3_rate': m3_rate,
        'edge': edge,
        'gemini_claim': gemini_claim,
        'baseline': baseline_2bet
    }

if __name__ == "__main__":
    verify_roi_stacked_500()
