#!/usr/bin/env python3
"""
7-Expert Ensemble 過擬合檢測
專門針對 AI-Lab 7專家策略進行穩健性分析
"""
import os
import sys
import numpy as np
from collections import Counter

project_root = os.getcwd()
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))
sys.path.insert(0, os.path.join(project_root, 'ai_lab'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from ai_lab.adapter import AIAdapter
from ai_lab.scripts.seven_expert_ensemble import SevenExpertEnsemble


def evaluate_segment(predictor, all_draws, rules, start_idx, end_idx):
    """評估特定區段的表現"""
    wins = 0
    m4_plus = 0
    total = 0
    expert_wins = {f'Expert{i+1}': 0 for i in range(7)}
    expert_names = ['AI', 'DMS', 'Graph', 'Hybrid', 'Gap', 'Tail', 'Anomaly']

    for target_idx in range(start_idx, end_idx):
        if target_idx >= len(all_draws):
            break

        target_draw = all_draws[target_idx]
        history = all_draws[:target_idx]

        if len(history) < 50:
            continue

        actual = set(target_draw.get('numbers', []))

        try:
            res = predictor.predict(history, rules)
            bets = res['bets']

            best_match = 0
            hit = False

            for idx, bet in enumerate(bets):
                match = len(set(bet) & actual)
                if match > best_match:
                    best_match = match
                if match >= 3:
                    hit = True
                    if idx < len(expert_names):
                        expert_wins[expert_names[idx]] = expert_wins.get(expert_names[idx], 0) + 1

            if hit: wins += 1
            if best_match >= 4: m4_plus += 1
            total += 1

        except Exception as e:
            continue

    win_rate = wins / total * 100 if total > 0 else 0
    return {
        'win_rate': win_rate,
        'wins': wins,
        'total': total,
        'm4_plus': m4_plus,
        'expert_wins': expert_wins
    }


def main():
    print("=" * 80)
    print("🔬 7-Expert Ensemble 過擬合檢測報告")
    print("=" * 80)

    # 初始化
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery.db')
    db = DatabaseManager(db_path=db_path)
    all_draws = list(reversed(db.get_all_draws(lottery_type='BIG_LOTTO')))
    rules = get_lottery_rules('BIG_LOTTO')

    engine = UnifiedPredictionEngine()
    ai_adapter = AIAdapter()
    predictor = SevenExpertEnsemble(engine, ai_adapter)

    total_periods = len(all_draws) - 100
    print(f"   總期數: {len(all_draws)}")
    print(f"   測試期數: {total_periods}")
    print("=" * 80)

    # 1. 時段穩定性分析 (分4段)
    print("\n📊 1. 時段穩定性分析")
    print("-" * 60)

    num_segments = 4
    segment_size = total_periods // num_segments
    segment_results = []

    for i in range(num_segments):
        start = 100 + i * segment_size
        end = start + segment_size
        print(f"   測試段 {i+1} ({start}-{end})...", end=" ", flush=True)

        result = evaluate_segment(predictor, all_draws, rules, start, end)
        result['segment'] = i + 1
        result['range'] = f"{start}-{end}"
        segment_results.append(result)

        print(f"{result['win_rate']:.2f}% ({result['wins']}/{result['total']})")

    rates = [r['win_rate'] for r in segment_results]
    mean_rate = np.mean(rates)
    std_rate = np.std(rates)
    max_diff = max(rates) - min(rates)
    trend = segment_results[-1]['win_rate'] - segment_results[0]['win_rate']

    cv = std_rate / mean_rate if mean_rate > 0 else 0
    stability_score = 100 - (cv * 100) - (abs(trend) * 2)
    stability_score = max(0, min(100, stability_score))

    print(f"\n   平均勝率: {mean_rate:.2f}%")
    print(f"   標準差: {std_rate:.2f}%")
    print(f"   最大差異: {max_diff:.2f}%")
    print(f"   趨勢 (末段-首段): {trend:+.2f}%")
    print(f"   穩定性分數: {stability_score:.1f}/100")
    print(f"   判定: {'✅ 穩定' if max_diff < 5 and abs(trend) < 3 else '⚠️ 不穩定'}")

    # 2. 走勢衰減分析
    print("\n📉 2. 走勢衰減分析")
    print("-" * 60)

    # 全期表現
    print("   測試全期...", end=" ", flush=True)
    overall = evaluate_segment(predictor, all_draws, rules, 100, len(all_draws))
    print(f"{overall['win_rate']:.2f}%")

    # 最近150期
    recent_start = len(all_draws) - 150
    print("   測試最近150期...", end=" ", flush=True)
    recent = evaluate_segment(predictor, all_draws, rules, recent_start, len(all_draws))
    print(f"{recent['win_rate']:.2f}%")

    decay = overall['win_rate'] - recent['win_rate']
    decay_pct = (decay / overall['win_rate'] * 100) if overall['win_rate'] > 0 else 0

    print(f"\n   全期表現: {overall['win_rate']:.2f}% ({overall['total']}期)")
    print(f"   最近150期: {recent['win_rate']:.2f}%")
    print(f"   衰減幅度: {decay:+.2f}% ({decay_pct:+.1f}%)")

    if decay <= 2:
        status = 'HEALTHY'
        status_icon = '✅'
    elif decay <= 5:
        status = 'WARNING'
        status_icon = '⚠️'
    else:
        status = 'CRITICAL'
        status_icon = '🔴'

    print(f"   狀態: {status_icon} {status}")

    # 3. 複雜度評估
    print("\n🔧 3. 複雜度評估")
    print("-" * 60)

    num_experts = 7
    complexity_score = num_experts * 12  # 每個專家 12 分
    complexity_score = min(100, complexity_score)

    print(f"   專家數量: {num_experts}")
    print(f"   複雜度分數: {complexity_score}/100")
    print(f"   風險等級: 🔴 HIGH (多專家系統)")

    # 4. 專家貢獻分析
    print("\n🏆 4. 專家貢獻分析 (全期)")
    print("-" * 60)

    expert_names = ['AI', 'DMS', 'Graph', 'Hybrid', 'Gap', 'Tail', 'Anomaly']
    total_expert_wins = {name: 0 for name in expert_names}

    # 合併所有段的專家貢獻
    for seg in segment_results:
        for name in expert_names:
            total_expert_wins[name] += seg['expert_wins'].get(name, 0)

    sorted_experts = sorted(total_expert_wins.items(), key=lambda x: x[1], reverse=True)
    for name, wins in sorted_experts:
        bar = '█' * (wins // 2) if wins > 0 else ''
        print(f"   {name:<10}: {wins:>3} wins {bar}")

    # 5. 綜合評估
    print("\n" + "=" * 80)
    print("📋 綜合過擬合風險評估")
    print("=" * 80)

    overall_score = (
        stability_score * 0.4 +
        (100 - abs(decay_pct)) * 0.4 +
        (100 - complexity_score) * 0.2
    )
    overall_score = max(0, min(100, overall_score))

    if overall_score >= 70:
        verdict = '✅ 低過擬合風險 - 策略穩健'
    elif overall_score >= 50:
        verdict = '⚠️ 中等過擬合風險 - 需注意'
    else:
        verdict = '🔴 高過擬合風險 - 謹慎使用'

    print(f"\n   綜合分數: {overall_score:.1f}/100")
    print(f"   判定: {verdict}")

    # 與其他策略對比
    print("\n📊 與已驗證策略對比")
    print("-" * 60)
    print(f"   {'策略':<25} {'分數':<10} {'全期勝率':<12} {'風險'}")
    print("-" * 60)
    print(f"   {'7-Expert Ensemble':<25} {overall_score:.1f}      {overall['win_rate']:.2f}%        {'✅ 低' if overall_score >= 70 else '⚠️ 中' if overall_score >= 50 else '🔴 高'}")
    print(f"   {'4-Bet Top4':<25} {'81.9':<10} {'6.26%':<12} {'✅ 低'}")
    print(f"   {'5ME':<25} {'72.1':<10} {'7.77%':<12} {'✅ 低'}")
    print(f"   {'2-Bet Stat+Freq':<25} {'86.8':<10} {'3.53%':<12} {'✅ 低'}")

    print("\n" + "=" * 80)

    return {
        'overall_score': overall_score,
        'stability_score': stability_score,
        'overall_rate': overall['win_rate'],
        'recent_rate': recent['win_rate'],
        'decay': decay,
        'complexity': complexity_score,
        'segment_results': segment_results
    }


if __name__ == "__main__":
    main()
