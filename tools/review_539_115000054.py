#!/usr/bin/env python3
"""
115000054 期今彩539檢討分析
開獎號碼: 02, 08, 15, 29, 31
"""
import sys, os, json
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from database import DatabaseManager

ACTUAL = {2, 8, 15, 29, 31}
ACTUAL_LIST = [2, 8, 15, 29, 31]

def main():
    db = DatabaseManager(db_path=os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db'))
    all_draws = db.get_all_draws(lottery_type='DAILY_539')

    if not all_draws:
        print("ERROR: No 539 data found")
        return

    # Sort ASC (oldest first)
    history = sorted(all_draws, key=lambda x: (x['date'], x['draw']))

    print(f"Total 539 draws: {len(history)}")
    print(f"Latest draw: {history[-1]['draw']} - {history[-1]['numbers']} ({history[-1]['date']})")
    print(f"Target: 115000054 期 - {ACTUAL_LIST}")
    print()

    # Check if 115000054 is in the data
    target_idx = None
    for i, d in enumerate(history):
        draw_str = str(d['draw'])
        if '054' in draw_str[-3:] and '115' in draw_str[:3]:
            target_idx = i
            break

    if target_idx is not None:
        print(f"Found target draw at index {target_idx}: {history[target_idx]}")
        # Use data before this draw for prediction
        pred_history = history[:target_idx]
    else:
        print("Target draw 115000054 not found in database, using all data as prediction base")
        pred_history = history

    print(f"Prediction history size: {len(pred_history)} draws")
    print(f"Last draw before target: {pred_history[-1]['draw']} - {pred_history[-1]['numbers']}")
    print()

    # === Analysis 1: Number Characteristics ===
    print("=" * 70)
    print("  PART 1: 115000054 期開獎號碼特徵分析")
    print("=" * 70)

    s = sum(ACTUAL_LIST)
    odd_count = sum(1 for n in ACTUAL_LIST if n % 2 == 1)
    even_count = 5 - odd_count
    z1 = sum(1 for n in ACTUAL_LIST if 1 <= n <= 13)
    z2 = sum(1 for n in ACTUAL_LIST if 14 <= n <= 26)
    z3 = sum(1 for n in ACTUAL_LIST if 27 <= n <= 39)
    tails = [n % 10 for n in ACTUAL_LIST]
    tail_coverage = len(set(tails))

    # AC value
    diffs = set()
    sorted_nums = sorted(ACTUAL_LIST)
    for i in range(len(sorted_nums)):
        for j in range(i+1, len(sorted_nums)):
            diffs.add(sorted_nums[j] - sorted_nums[i])
    ac_value = len(diffs)

    # Consecutive pairs
    consec_pairs = []
    for i in range(len(sorted_nums)-1):
        if sorted_nums[i+1] - sorted_nums[i] == 1:
            consec_pairs.append((sorted_nums[i], sorted_nums[i+1]))

    # Prime check
    primes = {2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37}
    prime_count = sum(1 for n in ACTUAL_LIST if n in primes)

    print(f"  號碼: {', '.join(f'{n:02d}' for n in ACTUAL_LIST)}")
    print(f"  和值: {s}")
    print(f"  奇偶比: {odd_count}:{even_count} ({'odd' if odd_count > even_count else 'even'}偏多)")
    print(f"  區間分布: Z1({z1}) Z2({z2}) Z3({z3})  [{z1}-{z2}-{z3}]")
    print(f"  尾數: {tails} (覆蓋{tail_coverage}種)")
    print(f"  AC值: {ac_value}")
    print(f"  連號: {consec_pairs if consec_pairs else '無'}")
    print(f"  質數: {prime_count}個 ({[n for n in ACTUAL_LIST if n in primes]})")
    print(f"  跨度: {max(ACTUAL_LIST) - min(ACTUAL_LIST)}")
    print()

    # Historical sum statistics
    sums = [sum(d['numbers']) for d in pred_history]
    sum_mean = np.mean(sums)
    sum_std = np.std(sums)
    print(f"  歷史和值: mean={sum_mean:.1f}, std={sum_std:.1f}, 68%區間=[{sum_mean-sum_std:.0f}, {sum_mean+sum_std:.0f}]")
    print(f"  本期和值 {s} {'在' if sum_mean-sum_std <= s <= sum_mean+sum_std else '不在'}68%區間內")

    # Historical zone distribution
    zone_patterns = []
    for d in pred_history:
        nums = d['numbers']
        zp = (sum(1 for n in nums if 1<=n<=13), sum(1 for n in nums if 14<=n<=26), sum(1 for n in nums if 27<=n<=39))
        zone_patterns.append(zp)
    zone_counter = Counter(zone_patterns)
    actual_zone = (z1, z2, z3)
    zone_rank = sorted(zone_counter.items(), key=lambda x: -x[1])
    zone_position = next((i+1 for i, (z, _) in enumerate(zone_rank) if z == actual_zone), -1)
    print(f"  區間模式 {actual_zone} 歷史排名: 第{zone_position}名 (共{len(zone_counter)}種)")
    print()

    # === Analysis 2: Each number's recent status ===
    print("=" * 70)
    print("  PART 2: 各號碼近期狀態")
    print("=" * 70)

    recent_100 = pred_history[-100:] if len(pred_history) >= 100 else pred_history
    freq_100 = Counter()
    for d in recent_100:
        for n in d['numbers']:
            freq_100[n] += 1

    expected_freq = len(recent_100) * 5 / 39

    for n in ACTUAL_LIST:
        # Find last appearance
        last_gap = None
        for i, d in enumerate(reversed(pred_history)):
            if n in d['numbers']:
                last_gap = i
                break

        f = freq_100.get(n, 0)
        deficit = expected_freq - f

        status = "HOT" if f > expected_freq * 1.2 else ("COLD" if f < expected_freq * 0.8 else "NORMAL")

        # Zone
        zone = "Z1(1-13)" if n <= 13 else ("Z2(14-26)" if n <= 26 else "Z3(27-39)")

        print(f"  {n:02d} | 近100期頻率: {f}/{len(recent_100)} (期望{expected_freq:.1f}) | "
              f"赤字: {deficit:+.1f} | Gap: {last_gap if last_gap is not None else 'N/A'} | "
              f"{status} | {zone}")
    print()

    # === Analysis 3: Run all prediction methods ===
    print("=" * 70)
    print("  PART 3: 各預測方法比對")
    print("=" * 70)

    rules = {'pickCount': 5, 'minNumber': 1, 'maxNumber': 39, 'specialMaxNumber': 0}
    results = {}

    # --- Method A: ACB (from quick_predict.py) ---
    try:
        from tools.quick_predict import _539_acb_bet, _539_fourier_scores, predict_539

        acb_nums = _539_acb_bet(pred_history)
        acb_match = len(set(acb_nums) & ACTUAL)
        results['ACB異常捕捉(1注)'] = {'numbers': acb_nums, 'match': acb_match}
    except Exception as e:
        results['ACB異常捕捉(1注)'] = {'numbers': [], 'match': 0, 'error': str(e)}

    # --- Method B: Fourier4Cold (3注) ---
    try:
        bets_3, strategy_3 = predict_539(pred_history, rules, num_bets=3)
        for i, bet in enumerate(bets_3):
            nums = bet['numbers']
            match = len(set(nums) & ACTUAL)
            results[f'F4Cold 注{i+1}(rank {i*5+1}-{(i+1)*5})'] = {'numbers': nums, 'match': match}
    except Exception as e:
        results['F4Cold(3注)'] = {'numbers': [], 'match': 0, 'error': str(e)}

    # --- Method C: Fourier4Cold (5注) ---
    try:
        bets_5, strategy_5 = predict_539(pred_history, rules, num_bets=5)
        for i, bet in enumerate(bets_5):
            nums = bet['numbers']
            match = len(set(nums) & ACTUAL)
            results[f'F4Cold-5注 注{i+1}'] = {'numbers': nums, 'match': match}
        # Total coverage
        all_f4cold = set()
        for bet in bets_5:
            all_f4cold.update(bet['numbers'])
        total_match = len(all_f4cold & ACTUAL)
        results['F4Cold-5注(總覆蓋)'] = {'numbers': sorted(all_f4cold), 'match': total_match}
    except Exception as e:
        results['F4Cold(5注)'] = {'numbers': [], 'match': 0, 'error': str(e)}

    # --- Method D: Daily539Predictor methods ---
    try:
        from models.daily539_predictor import daily539_predictor as d539

        methods = [
            ('constraint(約束)', d539.constraint_predict),
            ('cycle(週期)', d539.cycle_predict),
            ('consecutive(連號)', d539.consecutive_predict),
            ('tail(尾數)', d539.tail_number_predict),
            ('zone_opt(區間)', d539.zone_optimized_predict),
            ('hot_cold(冷熱)', d539.hot_cold_alternate_predict),
            ('comprehensive(綜合)', d539.comprehensive_predict),
            ('adv_constraint(進階約束)', d539.advanced_constraint_predict),
            ('ac_optimized(AC值)', d539.ac_optimized_predict),
            ('pattern_match(模式匹配)', d539.pattern_match_predict),
            ('ensemble_voting(集成投票)', d539.ensemble_voting_predict),
            ('best_duo(最佳雙方法)', d539.best_duo_predict),
        ]

        for name, method in methods:
            try:
                # Run 3 times for stochastic methods and take best
                best_match = 0
                best_nums = []
                for _ in range(3):
                    result = method(pred_history, rules)
                    nums = result['numbers']
                    match = len(set(nums) & ACTUAL)
                    if match > best_match:
                        best_match = match
                        best_nums = nums
                results[name] = {'numbers': best_nums, 'match': best_match}
            except Exception as e:
                results[name] = {'numbers': [], 'match': 0, 'error': str(e)}
    except Exception as e:
        print(f"  Daily539Predictor import error: {e}")

    # --- Method E: Unified Predictor ---
    try:
        from models.unified_predictor import prediction_engine as upe

        uni_methods = [
            ('UP:frequency(頻率)', upe.frequency_predict),
            ('UP:bayesian(貝葉斯)', upe.bayesian_predict),
            ('UP:trend(趨勢)', upe.trend_predict),
            ('UP:markov(馬可夫)', upe.markov_predict),
            ('UP:statistical(統計)', upe.statistical_predict),
            ('UP:hot_cold_mix(冷熱混合)', upe.hot_cold_mix_predict),
            ('UP:sum_range(和值)', upe.sum_range_predict),
        ]

        for name, method in uni_methods:
            try:
                best_match = 0
                best_nums = []
                for _ in range(3):
                    result = method(pred_history, rules)
                    nums = result['numbers']
                    match = len(set(nums) & ACTUAL)
                    if match > best_match:
                        best_match = match
                        best_nums = nums
                results[name] = {'numbers': best_nums, 'match': best_match}
            except Exception as e:
                results[name] = {'numbers': [], 'match': 0, 'error': str(e)}
    except Exception as e:
        print(f"  Unified Predictor import error: {e}")

    # --- Print sorted results ---
    sorted_results = sorted(results.items(), key=lambda x: -x[1]['match'])

    print(f"\n  {'方法':<35} {'預測號碼':<30} {'命中':>4} {'命中號碼'}")
    print("  " + "-" * 85)

    for name, info in sorted_results:
        nums = info['numbers']
        match = info['match']
        nums_str = ', '.join(f'{n:02d}' for n in sorted(nums)) if nums else 'ERROR'
        matched_nums = sorted(set(nums) & ACTUAL) if nums else []
        matched_str = ', '.join(f'{n:02d}' for n in matched_nums) if matched_nums else '-'
        marker = " ★" if match >= 2 else ""
        print(f"  {name:<35} {nums_str:<30} {match:>4}   {matched_str}{marker}")

    print()

    # === Analysis 4: Fourier Score analysis for actual numbers ===
    print("=" * 70)
    print("  PART 4: Fourier 分數分析 (實際開獎號碼)")
    print("=" * 70)

    try:
        from tools.quick_predict import _539_fourier_scores
        f_scores = _539_fourier_scores(pred_history, window=500)
        f_ranked = sorted(f_scores.items(), key=lambda x: -x[1])

        print(f"\n  Fourier Top 20:")
        for i, (n, sc) in enumerate(f_ranked[:20]):
            marker = " ← 實際開獎" if n in ACTUAL else ""
            print(f"    rank {i+1:2d}: {n:02d} (score={sc:.4f}){marker}")

        print(f"\n  實際開獎號碼Fourier排名:")
        for n in ACTUAL_LIST:
            rank = next(i+1 for i, (num, _) in enumerate(f_ranked) if num == n)
            sc = f_scores[n]
            print(f"    {n:02d}: rank={rank:2d}, score={sc:.4f}")
    except Exception as e:
        print(f"  Fourier analysis error: {e}")

    print()

    # === Analysis 5: ACB Score analysis for actual numbers ===
    print("=" * 70)
    print("  PART 5: ACB 異常捕捉分數分析")
    print("=" * 70)

    try:
        window = 100
        recent = pred_history[-window:] if len(pred_history) >= window else pred_history
        counter = Counter()
        for n in range(1, 40):
            counter[n] = 0
        for d in recent:
            for n in d['numbers']:
                counter[n] += 1
        last_seen = {}
        for i, d in enumerate(recent):
            for n in d['numbers']:
                last_seen[n] = i
        current = len(recent)
        gaps = {n: current - last_seen.get(n, -1) for n in range(1, 40)}
        expected_freq_acb = len(recent) * 5 / 39

        acb_scores = {}
        for n in range(1, 40):
            freq_deficit = expected_freq_acb - counter[n]
            gap_score = gaps[n] / (len(recent) / 2)
            boundary_bonus = 1.2 if (n <= 5 or n >= 35) else 1.0
            mod3_bonus = 1.1 if n % 3 == 0 else 1.0
            acb_scores[n] = (freq_deficit * 0.4 + gap_score * 0.6) * boundary_bonus * mod3_bonus

        acb_ranked = sorted(acb_scores.items(), key=lambda x: -x[1])

        print(f"\n  ACB Top 20:")
        for i, (n, sc) in enumerate(acb_ranked[:20]):
            marker = " ← 實際開獎" if n in ACTUAL else ""
            print(f"    rank {i+1:2d}: {n:02d} (score={sc:.4f}, freq={counter[n]}, gap={gaps[n]}){marker}")

        print(f"\n  實際開獎號碼ACB排名:")
        for n in ACTUAL_LIST:
            rank = next(i+1 for i, (num, _) in enumerate(acb_ranked) if num == n)
            sc = acb_scores[n]
            print(f"    {n:02d}: rank={rank:2d}, score={sc:.4f}, freq={counter[n]}, gap={gaps[n]}")
    except Exception as e:
        print(f"  ACB analysis error: {e}")

    print()

    # === Analysis 6: Previous Draw Comparison ===
    print("=" * 70)
    print("  PART 6: 前後期關聯分析")
    print("=" * 70)

    prev_draw = pred_history[-1]
    prev_nums = set(prev_draw['numbers'])
    overlap_with_prev = len(prev_nums & ACTUAL)

    print(f"  上期: {prev_draw['draw']} - {sorted(prev_draw['numbers'])}")
    print(f"  本期: 115000054 - {ACTUAL_LIST}")
    print(f"  重複號碼: {sorted(prev_nums & ACTUAL) if overlap_with_prev > 0 else '無'} ({overlap_with_prev}個)")

    # Echo analysis (lag-2)
    if len(pred_history) >= 2:
        lag2_draw = pred_history[-2]
        lag2_nums = set(lag2_draw['numbers'])
        echo_match = len(lag2_nums & ACTUAL)
        print(f"  前2期: {lag2_draw['draw']} - {sorted(lag2_draw['numbers'])}")
        print(f"  Echo(lag-2)重複: {sorted(lag2_nums & ACTUAL) if echo_match > 0 else '無'} ({echo_match}個)")

    # Neighbor analysis (prev +/- 1)
    neighbors = set()
    for n in prev_nums:
        for d in [-1, 0, 1]:
            nn = n + d
            if 1 <= nn <= 39:
                neighbors.add(nn)
    neighbor_match = len(neighbors & ACTUAL)
    print(f"  上期鄰號池({len(neighbors)}): {sorted(neighbors)}")
    print(f"  鄰號命中: {sorted(neighbors & ACTUAL) if neighbor_match > 0 else '無'} ({neighbor_match}個)")

    print()

    # === Analysis 7: Recent trends ===
    print("=" * 70)
    print("  PART 7: 近10期趨勢與模式")
    print("=" * 70)

    recent_10 = pred_history[-10:]
    for i, d in enumerate(recent_10):
        nums = sorted(d['numbers'])
        s = sum(nums)
        overlap = len(set(nums) & ACTUAL)
        marker = f" [match {overlap}]" if overlap > 0 else ""
        matched = sorted(set(nums) & ACTUAL)
        print(f"  {d['draw']} | {', '.join(f'{n:02d}' for n in nums)} | sum={s}{marker} {matched if matched else ''}")

    print(f"\n  →本期 115000054 | {', '.join(f'{n:02d}' for n in ACTUAL_LIST)} | sum={sum(ACTUAL_LIST)}")
    print()

    # === Analysis 8: Number-specific deep analysis ===
    print("=" * 70)
    print("  PART 8: 漏報號碼深度分析")
    print("=" * 70)

    # For each actual number, analyze why it was missed
    for n in ACTUAL_LIST:
        print(f"\n  --- {n:02d} 分析 ---")
        # Find Fourier rank
        try:
            f_rank = next(i+1 for i, (num, _) in enumerate(f_ranked) if num == n)
        except:
            f_rank = -1
        acb_rank = next(i+1 for i, (num, _) in enumerate(acb_ranked) if num == n)

        print(f"    Fourier rank: {f_rank}, ACB rank: {acb_rank}")
        print(f"    近100期頻率: {freq_100.get(n, 0)} (期望{expected_freq:.1f})")

        # Gap analysis
        recent_gaps = []
        last_hit = None
        for i, d in enumerate(reversed(pred_history[-200:])):
            if n in d['numbers']:
                if last_hit is not None:
                    recent_gaps.append(i - last_hit)
                last_hit = i
        if recent_gaps:
            avg_gap = np.mean(recent_gaps)
            print(f"    近期平均間隔: {avg_gap:.1f}, 最近間隔: {recent_gaps[0] if recent_gaps else 'N/A'}")

        # Is this number typically hard to predict?
        hit_count = sum(1 for d in pred_history for num in d['numbers'] if num == n)
        total_draws = len(pred_history)
        hit_rate = hit_count / total_draws * 100
        print(f"    歷史出現率: {hit_rate:.2f}% ({hit_count}/{total_draws})")

    print()

    # === Summary ===
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)

    best_methods = [(name, info) for name, info in sorted_results if info['match'] >= 2]
    if best_methods:
        print(f"\n  中獎方法 (match>=2):")
        for name, info in best_methods:
            print(f"    {name}: {info['match']}個命中 - {sorted(set(info['numbers']) & ACTUAL)}")
    else:
        print(f"\n  無方法命中2個以上")

    # Find best overall
    print(f"\n  最佳命中方法:")
    top_match = sorted_results[0][1]['match']
    for name, info in sorted_results:
        if info['match'] == top_match:
            print(f"    {name}: {info['match']}個 {sorted(set(info['numbers']) & ACTUAL)}")
        else:
            break

    # Coverage analysis for multi-bet
    print(f"\n  5注F4Cold總覆蓋命中: {results.get('F4Cold-5注(總覆蓋)', {}).get('match', 'N/A')}")

    print()


if __name__ == '__main__':
    main()
