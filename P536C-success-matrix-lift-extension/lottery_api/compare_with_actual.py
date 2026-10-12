#!/usr/bin/env python3
"""
比對實際號碼與預測號碼的相似度
"""

# 實際號碼
ACTUAL_NUMBERS = [6, 7, 15, 19, 24, 33, 46]

# 外部AI提供的8組號碼
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

# 已驗證的Top 5策略預測
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

# Monte Carlo預測
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


def calculate_match(predicted, actual):
    """計算命中數和相似度"""
    pred_set = set(predicted)
    actual_set = set(actual)
    matches = pred_set.intersection(actual_set)
    match_count = len(matches)
    return match_count, sorted(list(matches))


def analyze_similarity():
    """分析所有預測與實際號碼的相似度"""

    print("=" * 100)
    print("🎯 實際號碼與預測號碼相似度分析")
    print("=" * 100)

    actual_str = ", ".join(f"{n:02d}" for n in sorted(ACTUAL_NUMBERS))
    print(f"\n實際號碼: [{actual_str}]")
    print(f"共 {len(ACTUAL_NUMBERS)} 個號碼")

    # 收集所有結果
    all_results = []

    # 1. 分析外部AI預測
    print("\n" + "=" * 100)
    print("📋 外部AI提供的8組號碼 - 命中分析")
    print("=" * 100)

    for idx, pred in enumerate(EXTERNAL_PREDICTIONS, 1):
        match_count, matches = calculate_match(pred, ACTUAL_NUMBERS)
        pred_str = ", ".join(f"{n:02d}" for n in sorted(pred))
        matches_str = ", ".join(f"{n:02d}" for n in matches) if matches else "無"

        all_results.append({
            'source': f'外部AI第{idx}注',
            'prediction': pred,
            'match_count': match_count,
            'matches': matches,
            'category': 'external'
        })

        emoji = "🎯" if match_count >= 4 else "⭐" if match_count >= 3 else "✓" if match_count >= 2 else "○"
        print(f"{emoji} 第{idx}注: [{pred_str}]")
        print(f"   命中 {match_count}/6 個號碼: {matches_str}")

    # 2. 分析驗證策略預測
    print("\n" + "=" * 100)
    print("🔍 Top 5 驗證策略 - 命中分析")
    print("=" * 100)

    for strategy_name, predictions in VERIFIED_PREDICTIONS.items():
        print(f"\n【{strategy_name}】")

        for idx, pred in enumerate(predictions, 1):
            match_count, matches = calculate_match(pred, ACTUAL_NUMBERS)
            pred_str = ", ".join(f"{n:02d}" for n in sorted(pred))
            matches_str = ", ".join(f"{n:02d}" for n in matches) if matches else "無"

            all_results.append({
                'source': f'{strategy_name} 第{idx}注',
                'prediction': pred,
                'match_count': match_count,
                'matches': matches,
                'category': 'verified'
            })

            if match_count >= 3:
                emoji = "🎯" if match_count >= 4 else "⭐"
                print(f"   {emoji} 第{idx}注: [{pred_str}] - 命中 {match_count}/6: {matches_str}")

    # 3. 分析Monte Carlo預測
    print("\n" + "=" * 100)
    print("🎲 Monte Carlo (1.90%) - 命中分析")
    print("=" * 100)

    for idx, pred in enumerate(MONTE_CARLO_PREDICTIONS, 1):
        match_count, matches = calculate_match(pred, ACTUAL_NUMBERS)
        pred_str = ", ".join(f"{n:02d}" for n in sorted(pred))
        matches_str = ", ".join(f"{n:02d}" for n in matches) if matches else "無"

        all_results.append({
            'source': f'Monte Carlo 第{idx}注',
            'prediction': pred,
            'match_count': match_count,
            'matches': matches,
            'category': 'monte_carlo'
        })

        if match_count >= 2:
            emoji = "🎯" if match_count >= 4 else "⭐" if match_count >= 3 else "✓"
            print(f"   {emoji} 第{idx}注: [{pred_str}] - 命中 {match_count}/6: {matches_str}")

    # 4. 排名分析
    print("\n" + "=" * 100)
    print("🏆 最佳命中排名 (Top 10)")
    print("=" * 100)

    # 按命中數排序
    all_results.sort(key=lambda x: -x['match_count'])

    print(f"\n{'排名':<6} {'來源':<35} {'命中':<10} {'命中號碼'}")
    print("-" * 100)

    for rank, result in enumerate(all_results[:10], 1):
        pred_str = ", ".join(f"{n:02d}" for n in sorted(result['prediction']))
        matches_str = ", ".join(f"{n:02d}" for n in result['matches']) if result['matches'] else "無"

        emoji = "🥇" if rank == 1 else "🥈" if rank == 2 else "🥉" if rank == 3 else f"{rank}."
        print(f"{emoji:<6} {result['source']:<35} {result['match_count']}/6{'個':<6} {matches_str}")

        # 只顯示前3名的詳細號碼
        if rank <= 3:
            print(f"       預測: [{pred_str}]")

    # 5. 分類統計
    print("\n" + "=" * 100)
    print("📊 各類別平均命中率")
    print("=" * 100)

    categories = {
        'external': '外部AI預測',
        'verified': 'Top 5驗證策略',
        'monte_carlo': 'Monte Carlo'
    }

    for cat_id, cat_name in categories.items():
        cat_results = [r for r in all_results if r['category'] == cat_id]

        if cat_results:
            total_matches = sum(r['match_count'] for r in cat_results)
            avg_matches = total_matches / len(cat_results)
            max_matches = max(r['match_count'] for r in cat_results)

            # 統計命中分布
            match_dist = {}
            for r in cat_results:
                count = r['match_count']
                match_dist[count] = match_dist.get(count, 0) + 1

            print(f"\n【{cat_name}】")
            print(f"   總注數: {len(cat_results)}")
            print(f"   平均命中: {avg_matches:.2f} 個號碼")
            print(f"   最高命中: {max_matches} 個號碼")
            print(f"   命中分布: ", end="")
            for count in sorted(match_dist.keys(), reverse=True):
                print(f"{count}個×{match_dist[count]}注 ", end="")
            print()

    # 6. 最接近的預測
    print("\n" + "=" * 100)
    print("🎯 最接近實際號碼的預測 (命中≥3個)")
    print("=" * 100)

    best_matches = [r for r in all_results if r['match_count'] >= 3]

    if best_matches:
        for result in best_matches[:5]:
            pred_str = ", ".join(f"{n:02d}" for n in sorted(result['prediction']))
            matches_str = ", ".join(f"{n:02d}" for n in result['matches'])

            print(f"\n✨ {result['source']}")
            print(f"   預測: [{pred_str}]")
            print(f"   命中: [{matches_str}] ({result['match_count']}/6)")

            # 計算獎項
            if result['match_count'] == 6:
                print(f"   🏆 獎項: 頭獎")
            elif result['match_count'] == 5:
                print(f"   🏆 獎項: 參獎 (5個號碼)")
            elif result['match_count'] == 4:
                print(f"   🏆 獎項: 伍獎 (4個號碼)")
            elif result['match_count'] == 3:
                print(f"   🏆 獎項: 普獎 (3個號碼)")
    else:
        print("⚠️  沒有預測命中3個或以上號碼")

    print("\n" + "=" * 100)
    print("✅ 分析完成！")
    print("=" * 100)


if __name__ == '__main__':
    analyze_similarity()
