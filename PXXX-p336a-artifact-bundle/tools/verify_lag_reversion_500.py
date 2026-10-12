#!/usr/bin/env python3
"""
LagReversion 策略獨立 500 期驗證
================================
驗證 Gemini 提出的 LagReversion 策略是否有效

核心問題：
1. LagReversion 的 M3+ 命中率是否優於隨機基準？
2. 特別號連開權重 (0.5) 是否過擬合？

正確基準 (威力彩 1-38 選 6)：
- 1 注 M3+: 3.87%
- 2 注 M3+: 7.59%
- 3 注 M3+: 11.17%

執行方式：
  python3 tools/verify_lag_reversion_500.py
"""
import sys
import os
import numpy as np
from collections import Counter
from typing import List, Dict

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager
from common import get_lottery_rules

# 固定隨機種子確保可復現
SEED = 42
np.random.seed(SEED)

# 正確的 N 注隨機基準 (威力彩)
BASELINE = {
    1: 3.87,
    2: 7.59,
    3: 11.17,
}


class LagReversionPredictor:
    """
    滯後回歸與重複號預測器 (Lag Reversion Predictor)
    複製自 Gemini 實作的 lottery_api/models/lag_reversion.py
    """
    def __init__(self, rules: Dict):
        self.min_num = rules.get('minNumber', 1)
        self.max_num = rules.get('maxNumber', 38)
        self.pick_count = rules.get('pickCount', 6)
        self.special_max = rules.get('specialMaxNumber', 8)

    def predict(self, history: List[Dict], rules: Dict) -> Dict:
        """主要號碼預測"""
        scores = self.calculate_scores(history)

        # 取得得分最高的號碼
        top_numbers = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:self.pick_count]

        return {
            'numbers': sorted([n for n, s in top_numbers]),
            'confidence': 0.7,
            'scores': scores
        }

    def calculate_scores(self, history: List[Dict]) -> Dict[int, float]:
        if not history:
            return {n: 0.0 for n in range(self.min_num, self.max_num + 1)}

        scores = {n: 0.0 for n in range(self.min_num, self.max_num + 1)}

        # 1. 短期重複權重 (Short-term Repeat / Lag-1, Lag-2)
        last_draw = set(history[-1]['numbers'])  # 最新一期
        prev_draw = set(history[-2]['numbers']) if len(history) > 1 else set()

        for n in last_draw:
            scores[n] += 0.4  # Lag-1 權重
        for n in prev_draw:
            scores[n] += 0.2  # Lag-2 權重

        # 2. 長期遺漏回歸 (Long-term Mean Reversion)
        freq_50 = Counter()
        for d in history[-50:]:
            freq_50.update(d['numbers'])

        # 計算最近 10 期的遺漏情況
        recent_10_missing = set(range(self.min_num, self.max_num + 1))
        for d in history[-10:]:
            recent_10_missing -= set(d['numbers'])

        for n in range(self.min_num, self.max_num + 1):
            avg_freq = freq_50[n] / 50
            if n in recent_10_missing and avg_freq > 0.15:
                scores[n] += 0.3 * (freq_50[n] / 10)

        # 3. 鄰號加成 (Neighbor Attraction)
        for n in last_draw:
            if n > self.min_num: scores[n-1] += 0.15
            if n < self.max_num: scores[n+1] += 0.15

        return scores

    def predict_special(self, history: List[Dict], rules: Dict) -> int:
        """特別號連開/回歸預測"""
        spec_max = rules.get('specialMaxNumber', 8)
        scores = {n: 0.0 for n in range(1, spec_max + 1)}

        if not history:
            return 1

        # 針對特別號連開 (Lag-1 Repeat)
        last_spec = history[-1].get('special')
        if last_spec:
            scores[last_spec] += 0.5  # 強制注入連開機率

        # 週期性歸位 (Cycle Reversion)
        gaps = {n: [] for n in range(1, spec_max + 1)}
        last_seen = {n: -1 for n in range(1, spec_max + 1)}

        for i, d in enumerate(history):
            s = d.get('special')
            if s and s in last_seen:
                if last_seen[s] != -1:
                    gaps[s].append(i - last_seen[s])
                last_seen[s] = i

        for n in range(1, spec_max + 1):
            if gaps[n]:
                avg_gap = np.mean(gaps[n])
                current_gap = len(history) - last_seen[n] if last_seen[n] != -1 else 0
                if current_gap > avg_gap:
                    scores[n] += 0.2 * (current_gap / avg_gap)

        # 返回得分最高的特別號
        return max(scores.items(), key=lambda x: x[1])[0]


def calc_prize(match_count, special_hit):
    """威力彩中獎判定"""
    if match_count == 6 and special_hit:
        return '頭獎', 1
    elif match_count == 6:
        return '貳獎', 2
    elif match_count == 5 and special_hit:
        return '參獎', 3
    elif match_count == 5:
        return '肆獎', 4
    elif match_count == 4 and special_hit:
        return '伍獎', 5
    elif match_count == 4:
        return '陸獎', 6
    elif match_count == 3 and special_hit:
        return '柒獎', 7
    elif match_count == 2 and special_hit:
        return '捌獎', 8
    elif match_count == 3:
        return '玖獎', 9
    elif match_count == 1 and special_hit:
        return '普獎', 10
    else:
        return None, 0


def run_backtest(test_periods=500, num_bets=1):
    """
    執行 LagReversion 回測

    參數：
    - test_periods: 測試期數
    - num_bets: 投注注數 (1/2/3)
    """
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = list(reversed(db.get_all_draws(lottery_type='POWER_LOTTO')))
    rules = get_lottery_rules('POWER_LOTTO')

    test_periods = min(test_periods, len(all_draws) - 50)

    print("=" * 70)
    print(f"🔬 LagReversion 策略獨立驗證 ({test_periods} 期, {num_bets} 注)")
    print("=" * 70)
    print(f"隨機種子: {SEED}")
    print(f"正確基準 ({num_bets} 注 M3+): {BASELINE.get(num_bets, 'N/A')}%")
    print("-" * 70)

    predictor = LagReversionPredictor(rules)

    # 統計
    match_dist = Counter()
    special_hits = 0
    m3_plus_periods = 0
    total = 0
    prize_dist = Counter()

    # 詳細記錄
    detailed_results = []

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx <= 50:
            continue

        # ===== 關鍵：數據切片防止洩漏 =====
        target_draw = all_draws[target_idx]  # 實際開獎
        hist = all_draws[:target_idx]         # 只用過去數據
        # ==================================

        actual = set(target_draw['numbers'])
        actual_special = target_draw.get('special')

        best_match = 0
        best_special_hit = False
        all_bets = []

        # 生成 num_bets 注預測
        scores = predictor.calculate_scores(hist)
        all_sorted = sorted(scores.items(), key=lambda x: x[1], reverse=True)

        for bet_idx in range(num_bets):
            try:
                if bet_idx == 0:
                    # 第一注：純 LagReversion (Top 1-6)
                    nums = [n for n, s in all_sorted[:6]]
                    pred_special = predictor.predict_special(hist, rules)
                elif bet_idx == 1:
                    # 第二注：次高分號碼 (Top 7-12)
                    nums = [n for n, s in all_sorted[6:12]]
                    pred_special = (predictor.predict_special(hist, rules) % 8) + 1
                else:
                    # 第三注：冷號補充 (近 100 期最冷)
                    freq = Counter()
                    for d in hist[-100:]:
                        freq.update(d['numbers'])
                    cold_sorted = sorted(range(1, 39), key=lambda x: freq.get(x, 0))
                    # 排除前兩注已用的號碼
                    used = set(all_bets[0] + all_bets[1]) if len(all_bets) >= 2 else set()
                    nums = [n for n in cold_sorted if n not in used][:6]
                    pred_special = (predictor.predict_special(hist, rules) + 2) % 8 + 1

                all_bets.append(nums)
                predicted = set(nums)
                match_count = len(predicted & actual)
                special_hit = (pred_special == actual_special)

                if match_count > best_match:
                    best_match = match_count
                if special_hit:
                    best_special_hit = True

            except Exception as e:
                continue

        match_dist[best_match] += 1
        if best_special_hit:
            special_hits += 1
        if best_match >= 3:
            m3_plus_periods += 1

        # 記錄獎項
        prize_name, _ = calc_prize(best_match, best_special_hit)
        if prize_name:
            prize_dist[prize_name] += 1

        total += 1

        # 記錄詳細結果
        detailed_results.append({
            'draw': target_draw['draw'],
            'actual': target_draw['numbers'],
            'actual_special': actual_special,
            'best_match': best_match,
            'special_hit': best_special_hit
        })

        if total % 100 == 0:
            current_m3_rate = m3_plus_periods / total * 100
            print(f"  進度: {total}/{test_periods} | 當前 M3+: {current_m3_rate:.2f}%")

    if total == 0:
        print("❌ 無有效數據")
        return None

    # 計算最終結果
    m3_rate = m3_plus_periods / total * 100
    special_rate = special_hits / total * 100
    baseline = BASELINE.get(num_bets, 3.87)
    edge = m3_rate - baseline

    # 輸出結果
    print("\n" + "=" * 70)
    print("📊 回測結果")
    print("=" * 70)

    print(f"\n測試期數: {total}")
    print(f"投注注數: {num_bets}")

    print(f"\n主號命中分布 (最佳注):")
    for mc in sorted(match_dist.keys(), reverse=True):
        cnt = match_dist[mc]
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        print(f"  Match-{mc}: {cnt:3d} ({pct:5.1f}%) {bar}")

    print(f"\n特別號命中: {special_hits} 次 ({special_rate:.2f}%)")
    print(f"  基準 (1/8): 12.50%")
    print(f"  Edge: {'+' if special_rate > 12.5 else ''}{special_rate - 12.5:.2f}%")

    print(f"\n獎項分布:")
    for prize in ['頭獎', '貳獎', '參獎', '肆獎', '伍獎', '陸獎', '柒獎', '捌獎', '玖獎', '普獎']:
        if prize in prize_dist:
            print(f"  {prize}: {prize_dist[prize]} 次")

    print("\n" + "=" * 70)
    print("📈 核心指標 (M3+)")
    print("=" * 70)
    print(f"\n實測 M3+ 命中率: {m3_rate:.2f}%")
    print(f"正確基準 ({num_bets} 注): {baseline:.2f}%")
    print(f"Edge: {'+' if edge >= 0 else ''}{edge:.2f}%")

    if edge >= 1.0:
        print(f"\n✅ 顯著優於基準 (Edge >= 1%)")
        verdict = "PASS"
    elif edge >= 0:
        print(f"\n⚠️ 微弱優勢 (0 <= Edge < 1%)")
        verdict = "MARGINAL"
    else:
        print(f"\n❌ 低於基準 (Edge < 0)")
        verdict = "FAIL"

    # 分析 Gemini 聲稱的「特別號連開」效果
    print("\n" + "=" * 70)
    print("🔍 特別號連開效果分析")
    print("=" * 70)

    consecutive_special = 0
    consecutive_correct = 0
    for i in range(1, len(detailed_results)):
        prev_actual_special = detailed_results[i-1]['actual_special']
        curr_actual_special = detailed_results[i]['actual_special']
        if prev_actual_special == curr_actual_special:
            consecutive_special += 1
            # 檢查我們是否預測正確
            if detailed_results[i]['special_hit']:
                consecutive_correct += 1

    if consecutive_special > 0:
        consec_rate = consecutive_correct / consecutive_special * 100
        print(f"\n實際特別號連開期數: {consecutive_special}")
        print(f"LagReversion 正確捕捉: {consecutive_correct} ({consec_rate:.1f}%)")
        print(f"理論隨機命中率: 12.5% (1/8)")
        if consec_rate > 12.5:
            print(f"✅ 連開預測有效 (Edge +{consec_rate - 12.5:.1f}%)")
        else:
            print(f"❌ 連開預測無效")
    else:
        print("\n測試期間無特別號連開情況")

    return {
        'test_periods': total,
        'num_bets': num_bets,
        'm3_rate': m3_rate,
        'baseline': baseline,
        'edge': edge,
        'special_rate': special_rate,
        'verdict': verdict
    }


def main():
    print("\n" + "=" * 70)
    print("🧪 Gemini LagReversion 策略獨立驗證")
    print("=" * 70)
    print("\n根據 Gemini 合作協議，所有聲稱必須經 500 期獨立驗證。\n")

    # 驗證 1 注、2 注、3 注
    results = []
    for num_bets in [1, 2, 3]:
        print(f"\n{'='*70}")
        print(f"【{num_bets} 注驗證】")
        print(f"{'='*70}")
        result = run_backtest(test_periods=500, num_bets=num_bets)
        if result:
            results.append(result)
        print()

    # 總結
    print("\n" + "=" * 70)
    print("📋 驗證總結")
    print("=" * 70)
    print(f"\n| 注數 | 實測 M3+ | 正確基準 | Edge | 結論 |")
    print(f"|------|----------|----------|------|------|")
    for r in results:
        edge_str = f"+{r['edge']:.2f}%" if r['edge'] >= 0 else f"{r['edge']:.2f}%"
        verdict_emoji = "✅" if r['verdict'] == "PASS" else ("⚠️" if r['verdict'] == "MARGINAL" else "❌")
        print(f"| {r['num_bets']}注 | {r['m3_rate']:.2f}% | {r['baseline']:.2f}% | {edge_str} | {verdict_emoji} {r['verdict']} |")

    print("\n" + "-" * 70)
    print("Gemini 聲稱 vs 實測:")
    print("-" * 70)
    print("Gemini 聲稱: 中獎覆蓋率 50% (Edge +10%), 特號覆蓋率 45% (Edge +12.5%)")
    print("Claude 獨立驗證: 見上表 M3+ 指標")
    print("\n⚠️ 注意: Gemini 的「中獎覆蓋率」定義不明確，包含普獎等虧本情況。")
    print("   正確評估應使用 M3+ 命中率 vs 正確基準。")


if __name__ == '__main__':
    main()
