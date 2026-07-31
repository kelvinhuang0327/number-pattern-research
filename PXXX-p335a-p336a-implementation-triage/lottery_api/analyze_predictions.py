#!/usr/bin/env python3
"""
分析外部預測號碼的信心度
將外部號碼與經過驗證的Top 5策略預測進行比對
"""
import sys
import os
from collections import Counter

sys.path.insert(0, os.getcwd())

from database import db_manager
from models.unified_predictor import prediction_engine
from common import get_lottery_rules

# 外部AI Agent提供的8組號碼
EXTERNAL_PREDICTIONS = [
    [6, 23, 26, 40, 46, 49],
    [1, 5, 9, 23, 38, 44],
    [26, 30, 34, 35, 38, 49],
    [22, 26, 35, 36, 37, 49],
    [5, 12, 26, 34, 35, 49],
    [20, 26, 30, 33, 34, 38],
    [9, 35, 37, 41, 43, 47],
    [13, 28, 39, 43, 45, 48],
]

# 已驗證的Top 5策略預測（從回測報告中提取）
VERIFIED_PREDICTIONS = {
    'Deviation (3.68%)': [
        [6, 23, 26, 40, 46, 49],
        [6, 26, 40, 43, 46, 49],
        [6, 26, 40, 44, 46, 49],
        [6, 10, 23, 40, 46, 49],
        [6, 23, 31, 40, 46, 49],
        [6, 17, 23, 26, 48, 49],
        [6, 39, 40, 43, 46, 49],
        [7, 9, 13, 26, 40, 46],
    ],
    'Frequency (3.24%)': [
        [1, 5, 9, 23, 38, 44],
        [5, 6, 8, 21, 30, 43],
        [5, 15, 21, 34, 38, 41],
        [21, 26, 30, 34, 38, 41],
        [8, 20, 31, 34, 38, 46],
        [19, 31, 33, 35, 39, 46],
        [5, 12, 26, 35, 36, 49],
        [2, 11, 18, 20, 25, 42],
    ],
    'Statistical (2.90%)': [
        [26, 30, 34, 35, 38, 49],
        [5, 8, 13, 22, 34, 35],
        [6, 7, 8, 21, 33, 45],
        [10, 30, 33, 34, 35, 47],
        [6, 11, 19, 29, 31, 34],
        [6, 13, 17, 31, 44, 48],
        [8, 10, 33, 35, 38, 42],
        [6, 19, 34, 35, 38, 43],
    ],
    'Hot-Cold (2.68%)': [
        [22, 26, 35, 36, 37, 49],
        [9, 22, 26, 35, 36, 37],
        [14, 22, 26, 28, 35, 36],
        [9, 24, 26, 33, 36, 49],
        [3, 16, 22, 26, 36, 49],
        [4, 12, 26, 30, 35, 49],
        [5, 22, 23, 34, 36, 49],
        [13, 15, 30, 36, 37, 49],
    ],
    'Ensemble (2.46%)': [
        [5, 12, 26, 35, 36, 49],
        [22, 26, 30, 34, 35, 49],
        [26, 30, 33, 34, 38, 40],
        [6, 26, 29, 30, 34, 35],
        [5, 6, 8, 12, 24, 49],
        [15, 17, 22, 23, 34, 49],
        [6, 26, 30, 34, 41, 42],
        [6, 11, 26, 29, 30, 35],
    ],
}

# Monte Carlo預測（排名第8，1.90%）
MONTE_CARLO_PREDICTIONS = [
    [20, 26, 30, 33, 34, 38],
    [20, 33, 34, 38, 40, 49],
    [20, 26, 33, 34, 38, 46],
    [13, 20, 26, 33, 34, 38],
    [26, 33, 34, 38, 40, 46],
    [26, 33, 34, 38, 40, 46],
    [20, 26, 33, 34, 38, 46],
    [20, 26, 30, 34, 38, 46],
]


def calculate_similarity(bet1, bet2):
    """計算兩注號碼的相似度（交集數量）"""
    return len(set(bet1).intersection(set(bet2)))


def analyze_external_predictions():
    """分析外部預測的信心度"""

    print("=" * 100)
    print("🔍 外部AI預測號碼分析報告")
    print("=" * 100)

    print("\n📋 外部AI提供的8組號碼:")
    print("-" * 100)
    for idx, bet in enumerate(EXTERNAL_PREDICTIONS, 1):
        bet_str = ", ".join(f"{n:02d}" for n in sorted(bet))
        print(f"第{idx}注: [{bet_str}]")

    # 1. 完全匹配分析
    print("\n" + "=" * 100)
    print("✅ 完全匹配分析 (與驗證策略100%相同的號碼)")
    print("=" * 100)

    exact_matches = []
    for idx, external_bet in enumerate(EXTERNAL_PREDICTIONS, 1):
        external_set = set(external_bet)

        for strategy_name, verified_bets in VERIFIED_PREDICTIONS.items():
            for v_idx, verified_bet in enumerate(verified_bets, 1):
                if external_set == set(verified_bet):
                    exact_matches.append({
                        'external_idx': idx,
                        'strategy': strategy_name,
                        'verified_idx': v_idx,
                        'bet': sorted(external_bet)
                    })

    if exact_matches:
        for match in exact_matches:
            bet_str = ", ".join(f"{n:02d}" for n in match['bet'])
            print(f"🎯 第{match['external_idx']}注 完全匹配 {match['strategy']} 第{match['verified_idx']}注")
            print(f"   號碼: [{bet_str}]")
    else:
        print("❌ 沒有完全匹配的號碼組合")

    # 2. 高相似度分析 (5個或以上號碼相同)
    print("\n" + "=" * 100)
    print("⭐ 高相似度分析 (5-6個號碼相同)")
    print("=" * 100)

    high_similarity = []
    for idx, external_bet in enumerate(EXTERNAL_PREDICTIONS, 1):
        for strategy_name, verified_bets in VERIFIED_PREDICTIONS.items():
            for v_idx, verified_bet in enumerate(verified_bets, 1):
                similarity = calculate_similarity(external_bet, verified_bet)
                if similarity >= 5:
                    high_similarity.append({
                        'external_idx': idx,
                        'strategy': strategy_name,
                        'verified_idx': v_idx,
                        'similarity': similarity,
                        'external_bet': sorted(external_bet),
                        'verified_bet': sorted(verified_bet)
                    })

    if high_similarity:
        # 按相似度排序
        high_similarity.sort(key=lambda x: -x['similarity'])

        for match in high_similarity:
            ext_str = ", ".join(f"{n:02d}" for n in match['external_bet'])
            ver_str = ", ".join(f"{n:02d}" for n in match['verified_bet'])
            print(f"\n🔸 第{match['external_idx']}注 與 {match['strategy']} 第{match['verified_idx']}注")
            print(f"   相似度: {match['similarity']}/6 個號碼相同")
            print(f"   外部: [{ext_str}]")
            print(f"   驗證: [{ver_str}]")
    else:
        print("⚠️  沒有5個以上號碼相同的組合")

    # 3. 號碼頻率分析
    print("\n" + "=" * 100)
    print("📊 號碼頻率分析")
    print("=" * 100)

    # 外部號碼頻率
    external_numbers = []
    for bet in EXTERNAL_PREDICTIONS:
        external_numbers.extend(bet)
    external_freq = Counter(external_numbers)

    # 驗證號碼頻率（Top 5平均）
    verified_numbers = []
    for verified_bets in VERIFIED_PREDICTIONS.values():
        for bet in verified_bets:
            verified_numbers.extend(bet)
    verified_freq = Counter(verified_numbers)

    print("\n🔥 外部AI高頻號碼 (出現≥4次):")
    external_hot = [(num, count) for num, count in external_freq.most_common() if count >= 4]
    for num, count in external_hot:
        percentage = (count / 8) * 100
        bar = "█" * count + "░" * (8 - count)
        print(f"   {num:02d}: {bar} {count}/8注 ({percentage:.0f}%)")

    print("\n🔥 驗證策略高頻號碼 (Top 10):")
    for num, count in verified_freq.most_common(10):
        percentage = (count / 40) * 100  # 5個策略 × 8注
        print(f"   {num:02d}: {count}次 ({percentage:.1f}%)")

    # 4. 共同核心號碼
    print("\n" + "=" * 100)
    print("💎 共同核心號碼分析")
    print("=" * 100)

    external_top10 = set([num for num, _ in external_freq.most_common(10)])
    verified_top10 = set([num for num, _ in verified_freq.most_common(10)])

    common_core = external_top10.intersection(verified_top10)

    print(f"\n✨ 外部AI Top 10: {sorted(external_top10)}")
    print(f"✨ 驗證策略 Top 10: {sorted(verified_top10)}")
    print(f"✨ 共同核心號碼: {sorted(common_core)}")
    print(f"   共同度: {len(common_core)}/10 = {len(common_core)/10*100:.0f}%")

    # 5. 信心度評分
    print("\n" + "=" * 100)
    print("🎯 綜合信心度評分")
    print("=" * 100)

    confidence_scores = []

    for idx, external_bet in enumerate(EXTERNAL_PREDICTIONS, 1):
        score = 0
        reasons = []

        # 完全匹配 +50分
        is_exact_match = any(
            set(external_bet) == set(verified_bet)
            for verified_bets in VERIFIED_PREDICTIONS.values()
            for verified_bet in verified_bets
        )
        if is_exact_match:
            score += 50
            reasons.append("完全匹配驗證策略(+50)")

        # 高相似度 +30分
        max_similarity = max([
            calculate_similarity(external_bet, verified_bet)
            for verified_bets in VERIFIED_PREDICTIONS.values()
            for verified_bet in verified_bets
        ])
        if max_similarity >= 5:
            score += 30
            reasons.append(f"高相似度{max_similarity}/6(+30)")
        elif max_similarity >= 4:
            score += 15
            reasons.append(f"中相似度{max_similarity}/6(+15)")

        # 包含共同核心號碼 +20分
        core_count = len(set(external_bet).intersection(common_core))
        if core_count >= 4:
            score += 20
            reasons.append(f"含{core_count}個核心號碼(+20)")
        elif core_count >= 3:
            score += 10
            reasons.append(f"含{core_count}個核心號碼(+10)")

        # 包含高頻號碼
        hot_numbers = [num for num, count in external_freq.most_common(6)]
        hot_count = len(set(external_bet).intersection(set(hot_numbers)))
        if hot_count >= 4:
            score += 10
            reasons.append(f"含{hot_count}個高頻號碼(+10)")

        confidence_scores.append({
            'idx': idx,
            'bet': sorted(external_bet),
            'score': score,
            'reasons': reasons,
            'level': '極高' if score >= 80 else '高' if score >= 50 else '中' if score >= 30 else '低'
        })

    # 按分數排序
    confidence_scores.sort(key=lambda x: -x['score'])

    print(f"\n{'注數':<6} {'號碼':<30} {'分數':<8} {'信心度':<8} {'原因'}")
    print("-" * 100)

    for item in confidence_scores:
        bet_str = ", ".join(f"{n:02d}" for n in item['bet'])
        reasons_str = " | ".join(item['reasons']) if item['reasons'] else "無特殊優勢"
        emoji = "🌟" if item['level'] == '極高' else "⭐" if item['level'] == '高' else "✨" if item['level'] == '中' else "💫"
        print(f"{emoji} 第{item['idx']}注  [{bet_str}]  {item['score']:<8} {item['level']:<8} {reasons_str}")

    # 6. 最終建議
    print("\n" + "=" * 100)
    print("💡 最終建議")
    print("=" * 100)

    high_confidence = [item for item in confidence_scores if item['score'] >= 50]
    medium_confidence = [item for item in confidence_scores if 30 <= item['score'] < 50]

    if high_confidence:
        print(f"\n✅ 推薦投注 ({len(high_confidence)}注) - 高信心度:")
        for item in high_confidence:
            bet_str = ", ".join(f"{n:02d}" for n in item['bet'])
            print(f"   第{item['idx']}注: [{bet_str}] (信心度: {item['level']}, {item['score']}分)")

    if medium_confidence:
        print(f"\n⚠️  謹慎考慮 ({len(medium_confidence)}注) - 中等信心度:")
        for item in medium_confidence:
            bet_str = ", ".join(f"{n:02d}" for n in item['bet'])
            print(f"   第{item['idx']}注: [{bet_str}] (信心度: {item['level']}, {item['score']}分)")

    low_confidence = [item for item in confidence_scores if item['score'] < 30]
    if low_confidence:
        print(f"\n❌ 不建議投注 ({len(low_confidence)}注) - 低信心度:")
        for item in low_confidence:
            bet_str = ", ".join(f"{n:02d}" for n in item['bet'])
            print(f"   第{item['idx']}注: [{bet_str}] (信心度: {item['level']}, {item['score']}分)")

    # 7. 與Monte Carlo比較
    print("\n" + "=" * 100)
    print("🎲 與Monte Carlo (排名第8, 1.90%) 比較")
    print("=" * 100)

    mc_similarities = []
    for idx, external_bet in enumerate(EXTERNAL_PREDICTIONS, 1):
        max_mc_sim = max([
            calculate_similarity(external_bet, mc_bet)
            for mc_bet in MONTE_CARLO_PREDICTIONS
        ])
        if max_mc_sim >= 4:
            mc_similarities.append((idx, max_mc_sim))

    if mc_similarities:
        print("⚠️  以下號碼與Monte Carlo相似度較高（Monte Carlo在回測中排名較後）:")
        for idx, sim in mc_similarities:
            bet_str = ", ".join(f"{n:02d}" for n in sorted(EXTERNAL_PREDICTIONS[idx-1]))
            print(f"   第{idx}注: [{bet_str}] - {sim}/6個號碼相同")
    else:
        print("✅ 這8注與Monte Carlo的相似度都不高")

    print("\n" + "=" * 100)
    print("✅ 分析完成！")
    print("=" * 100)


if __name__ == '__main__':
    analyze_external_predictions()
