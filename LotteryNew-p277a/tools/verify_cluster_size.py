#!/usr/bin/env python3
"""
驗證 Cluster Size 15 vs 18 的效果差異
"""
import sys
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules
from models.unified_predictor import UnifiedPredictionEngine
from collections import defaultdict

def generate_2bets_custom(engine, history, rules, cluster_size):
    """自定義集群大小的 2-bet 生成"""
    # 簡化 MTFF
    scores = defaultdict(float)
    windows = [(50, 0.3), (200, 0.5)]

    for w, weight in windows:
        try:
            window = history[:min(w, len(history))]
            res = engine.ensemble_predict(window, rules)
            for rank, num in enumerate(res['numbers'][:8]):
                scores[num] += (8 - rank) / 8 * weight
        except:
            pass

    # 取 Top N
    sorted_nums = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    elite = [n for n, s in sorted_nums[:cluster_size]]

    if len(elite) < 12:
        return None

    # 生成兩注
    bet1 = sorted(elite[:6])
    bet2 = sorted(elite[5:11])

    return [bet1, bet2]

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api/data/lottery_v2.db'))
    draws = db.get_all_draws('BIG_LOTTO')
    rules = get_lottery_rules('BIG_LOTTO')
    engine = UnifiedPredictionEngine()

    test_periods = 50

    print("=" * 50)
    print(f"Cluster Size 驗證 ({test_periods}期)")
    print("=" * 50)

    for cluster_size in [15, 18]:
        hits = 0
        total = 0

        print(f"\n測試 {cluster_size} 碼...")

        for i in range(test_periods):
            target = draws[i + 1]
            history = draws[i + 2:]

            if len(history) < 200:
                continue

            actual = set(target['numbers'])
            bets = generate_2bets_custom(engine, history, rules, cluster_size)

            if not bets:
                continue

            max_match = max(len(set(b) & actual) for b in bets)

            if max_match >= 3:
                hits += 1
            total += 1

            if (i + 1) % 10 == 0:
                print(f"  進度: {i+1}/{test_periods}")

        rate = hits / total * 100 if total > 0 else 0
        print(f"結果: {cluster_size}碼 = {rate:.1f}% ({hits}/{total})")

if __name__ == '__main__':
    main()
