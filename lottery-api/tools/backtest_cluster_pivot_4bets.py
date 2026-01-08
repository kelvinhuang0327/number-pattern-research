#!/usr/bin/env python3
"""
ClusterPivot 4注策略回測驗證腳本

目標：驗證 CLAUDE.md 中聲稱的 ~15% 中獎率
配置：method='cluster_pivot', anchor_count=2, resilience=True
"""

import sys
import os
import json
import argparse
from typing import List, Optional
from datetime import datetime
from collections import defaultdict, Counter

# 添加父目錄到路徑
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager
from models.multi_bet_optimizer import MultiBetOptimizer

def get_lottery_rules(lottery_type: str) -> dict:
    """獲取彩票規則"""
    rules = {
        'POWER_LOTTO': {
            'name': 'POWER_LOTTO',
            'pickCount': 6,
            'minNumber': 1,
            'maxNumber': 38,
            'hasSpecialNumber': True,
            'specialMinNumber': 1,
            'specialMaxNumber': 8,
        }
    }
    return rules.get(lottery_type, rules['POWER_LOTTO'])


def validate_no_leakage(target_draw: dict, train_data: list) -> bool:
    """驗證無數據洩漏"""
    target_date = target_draw.get('date', '')
    for d in train_data[:5]:  # 只檢查前幾筆
        if d.get('date', '') >= target_date:
            print(f"⚠️ 數據洩漏警告！訓練數據 {d['draw']} >= 目標 {target_draw['draw']}")
            return False
    return True


def run_cluster_pivot_backtest(num_bets: int = 4, anchors: Optional[List[int]] = None):
    """
    執行 ClusterPivot 多注策略回測

    Args:
        num_bets: 注數 (預設 4)
    """
    print("=" * 70)
    print(f"ClusterPivot {num_bets}注策略回測")
    print(f"日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 初始化
    db = DatabaseManager()
    optimizer = MultiBetOptimizer()
    rules = get_lottery_rules('POWER_LOTTO')

    # 獲取全部威力彩數據 (新→舊排序)
    all_draws = db.get_all_draws('POWER_LOTTO')
    print(f"\n總數據量: {len(all_draws)} 期")
    print(f"最新期號: {all_draws[0]['draw']} ({all_draws[0]['date']})")
    print(f"最舊期號: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")

    # 篩選 2025 年數據作為測試集
    test_draws = []
    for i, d in enumerate(all_draws):
        draw_id = d.get('draw', '')
        # 威力彩 2025 年期號格式: 114000XXX
        if draw_id.startswith('114'):
            test_draws.append((i, d))

    # 反轉為時間順序 (從早到晚)
    test_draws = list(reversed(test_draws))

    print(f"\n2025年測試期數: {len(test_draws)} 期")
    if test_draws:
        print(f"測試範圍: {test_draws[0][1]['draw']} ~ {test_draws[-1][1]['draw']}")

    # ClusterPivot 配置
    meta_config = {
        'method': 'cluster_pivot',
        'anchor_count': 2,
        'resilience': True,
        'window_size': 50,
    }

    if anchors:
        meta_config['forced_anchors'] = anchors

    print(f"\n配置: {json.dumps(meta_config, indent=2)}")
    print("-" * 70)

    # 回測
    results = []
    win_count = 0
    total_best_matches = 0
    match_distribution = Counter()
    hit_details = []

    for test_idx, (orig_idx, target_draw) in enumerate(test_draws):
        target_numbers = set(target_draw['numbers'])
        target_special = target_draw.get('special_number') or target_draw.get('special')

        # ⚠️ 關鍵：使用該期之後的數據作為訓練集 (無洩漏)
        train_data = all_draws[orig_idx + 1:]

        if len(train_data) < 100:
            continue

        # 驗證無洩漏
        if test_idx == 0:
            validate_no_leakage(target_draw, train_data)

        try:
            # 生成預測
            prediction = optimizer.generate_diversified_bets(
                train_data,
                rules,
                num_bets=num_bets,
                meta_config=meta_config
            )

            # 檢查每注匹配情況
            bet_matches = []
            best_match = 0
            best_bet_idx = -1
            special_hit = False

            for idx, bet in enumerate(prediction['bets']):
                matches = len(set(bet['numbers']) & target_numbers)
                bet_matches.append(matches)

                if matches > best_match:
                    best_match = matches
                    best_bet_idx = idx

                # 檢查特別號
                if bet.get('special') == target_special:
                    special_hit = True

            total_best_matches += best_match
            match_distribution[best_match] += 1

            # 任一注中3個及以上視為中獎
            is_win = best_match >= 3
            if is_win:
                win_count += 1
                hit_details.append({
                    'draw': target_draw['draw'],
                    'date': target_draw['date'],
                    'target_numbers': sorted(target_draw['numbers']),
                    'target_special': target_special,
                    'best_bet_idx': best_bet_idx + 1,
                    'best_match': best_match,
                    'special_hit': special_hit,
                    'predicted_numbers': prediction['bets'][best_bet_idx]['numbers'],
                    'predicted_special': prediction['bets'][best_bet_idx].get('special'),
                })

            results.append({
                'draw': target_draw['draw'],
                'date': target_draw['date'],
                'bet_matches': bet_matches,
                'best_match': best_match,
                'best_bet_idx': best_bet_idx,
                'is_win': is_win,
                'special_hit': special_hit,
            })

            # 進度輸出
            if (test_idx + 1) % 20 == 0 or test_idx == len(test_draws) - 1:
                current_win_rate = win_count / (test_idx + 1) * 100
                print(f"進度: {test_idx + 1}/{len(test_draws)}, "
                      f"中獎: {win_count}次, "
                      f"中獎率: {current_win_rate:.2f}%")

        except Exception as e:
            print(f"錯誤 ({target_draw['draw']}): {e}")
            import traceback
            traceback.print_exc()

    # 統計結果
    test_count = len(results)
    win_rate = win_count / test_count if test_count > 0 else 0
    avg_best_match = total_best_matches / test_count if test_count > 0 else 0
    periods_per_win = test_count / win_count if win_count > 0 else float('inf')

    # 特別號命中統計
    special_hits = sum(1 for r in results if r['special_hit'])
    special_hit_rate = special_hits / test_count if test_count > 0 else 0

    # 輸出結果
    print("\n" + "=" * 70)
    print("回測結果摘要")
    print("=" * 70)
    print(f"策略: ClusterPivot {num_bets}注")
    print(f"測試期數: {test_count}")
    print(f"中獎次數: {win_count}")
    print(f"中獎率: {win_rate * 100:.2f}%")
    print(f"每N期中1次: {periods_per_win:.1f}")
    print(f"平均最佳匹配: {avg_best_match:.2f}")
    print(f"特別號命中率: {special_hit_rate * 100:.1f}%")

    print("\n匹配分布:")
    for match_count in sorted(match_distribution.keys()):
        count = match_distribution[match_count]
        pct = count / test_count * 100
        bar = "█" * int(pct / 2)
        print(f"  中{match_count}個: {count:3d}次 ({pct:5.1f}%) {bar}")

    print("\n命中詳情 (前10筆):")
    for detail in hit_details[:10]:
        print(f"  {detail['draw']} ({detail['date']}): "
              f"第{detail['best_bet_idx']}注中{detail['best_match']}個 "
              f"{'🎯特別號' if detail['special_hit'] else ''}")

    # 轉換 numpy int64 為 Python int
    def convert_to_native(obj):
        if isinstance(obj, dict):
            return {k: convert_to_native(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [convert_to_native(i) for i in obj]
        elif hasattr(obj, 'item'):  # numpy types
            return obj.item()
        return obj

    # 儲存結果
    output = convert_to_native({
        'summary': {
            'lottery_type': 'POWER_LOTTO',
            'strategy': 'cluster_pivot',
            'num_bets': num_bets,
            'config': meta_config,
            'test_periods': test_count,
            'win_count': win_count,
            'win_rate': win_rate,
            'periods_per_win': periods_per_win,
            'avg_best_match': avg_best_match,
            'special_hit_rate': special_hit_rate,
            'match_distribution': dict(match_distribution),
            'backtest_timestamp': datetime.now().isoformat(),
        },
        'hit_details': hit_details,
        'all_results': results,
    })

    anchor_suffix = ''
    if anchors:
        anchor_suffix = '_anchors_' + '-'.join(str(a) for a in anchors)

    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data', 'backtest_results',
        f'POWER_LOTTO_cluster_pivot_{num_bets}bets_2025{anchor_suffix}.json'
    )

    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n結果已儲存至: {output_path}")

    # 驗證結論
    print("\n" + "=" * 70)
    print("驗證結論")
    print("=" * 70)

    claimed_rate = 0.15  # CLAUDE.md 聲稱 ~15%
    tolerance = 0.03     # 允許 ±3% 誤差

    if abs(win_rate - claimed_rate) <= tolerance:
        print(f"✅ 驗證通過: 實際 {win_rate*100:.2f}% ≈ 聲稱 15% (誤差 ±{tolerance*100}%)")
    elif win_rate > claimed_rate:
        print(f"✅ 優於預期: 實際 {win_rate*100:.2f}% > 聲稱 15%")
    else:
        print(f"⚠️ 低於預期: 實際 {win_rate*100:.2f}% < 聲稱 15%")
        print(f"   差距: {(claimed_rate - win_rate)*100:.2f}%")

    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='ClusterPivot 多注策略回測 (POWER_LOTTO, 2025)')
    parser.add_argument('--num-bets', type=int, default=4, help='注數 (預設 4)')
    parser.add_argument('--anchors', type=str, default='', help='強制錨點 (例如: 11,17)')
    args = parser.parse_args()

    anchors = None
    if args.anchors:
        anchors = [int(x.strip()) for x in args.anchors.split(',') if x.strip()]

    run_cluster_pivot_backtest(args.num_bets, anchors=anchors)
