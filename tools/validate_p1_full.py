#!/usr/bin/env python3
"""
P1 鄰號+冷號 2-bet — 完整驗證
================================
按 CLAUDE.md 驗證標準：
  1. 三窗口回測 (150 / 500 / 1500)
  2. Permutation test (200次 label shuffle, p < 0.05)
  3. 10 種子穩定性 (確定性策略應 ±0.00%)
  4. Walk-forward OOS (滾動 300期窗 × 5 fold)
  5. 與舊策略 McNemar 配對比較

鄰號定義：
  注1 選號池 = 上期 6 個開獎號 各自 ±1（含自身），
  即 {n-1, n, n+1} for each n in prev_draw（夾在 [1,49]），
  最終 pool ≈ 12~18 個號碼，按 (Fourier + 0.5*Markov) 排名取 Top 6。
  注2 = 近100期最冷號 Top12 → Sum-Constrained 組合取 6。

腳本路徑：
  策略實現: tools/backtest_p0_p3_optimization.py (neighbor_cold_2bet)
  production 入口: tools/quick_predict.py (biglotto_p1_neighbor_cold_2bet)
  本驗證: tools/validate_p1_full.py
"""
import os
import sys
import time
import json
import numpy as np
from collections import Counter, defaultdict
from itertools import combinations as _icombs

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager

# Import P1 strategy and old P0 baseline from backtest script
from tools.backtest_p0_p3_optimization import (
    neighbor_cold_2bet,
    original_p0_2bet,
    BASELINES,
    MAX_NUM, PICK,
)

N_BETS = 2
BASELINE_RATE = BASELINES[N_BETS]  # 3.6946%
WINDOWS = [150, 500, 1500]
PERM_ITERATIONS = 200
N_SEEDS = 10
WF_FOLDS = 5
WF_WINDOW = 300


# ============================================================
# 1. THREE-WINDOW BACKTEST (詳細版)
# ============================================================
def detailed_backtest(predict_func, all_draws, test_periods, label=""):
    """回測 + 逐期命中記錄"""
    hits_record = []  # 1=M3+, 0=miss
    per_bet_hits = Counter()
    bet_details = []  # 每注命中數列表

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 150:
            hits_record.append(0)
            continue

        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            bets = predict_func(hist)
            any_hit = False
            period_detail = []
            for j, bet in enumerate(bets):
                h = len(set(bet) & actual)
                period_detail.append(h)
                if h >= 3:
                    any_hit = True
                    per_bet_hits[j] += 1
            hits_record.append(1 if any_hit else 0)
            bet_details.append(period_detail)
        except Exception:
            hits_record.append(0)
            bet_details.append([0] * N_BETS)

    total = len(hits_record)
    m3 = sum(hits_record)
    rate = m3 / total * 100 if total > 0 else 0
    edge = rate - BASELINE_RATE

    # z-test
    p0 = BASELINE_RATE / 100
    se = np.sqrt(p0 * (1 - p0) / total) if total > 0 else 0.01
    z = ((m3 / total) - p0) / se if se > 0 and total > 0 else 0

    return {
        'label': label,
        'total': total,
        'm3_plus': m3,
        'rate': rate,
        'baseline': BASELINE_RATE,
        'edge': edge,
        'z': z,
        'per_bet': dict(per_bet_hits),
        'hits_record': hits_record,
    }


# ============================================================
# 2. PERMUTATION TEST (正確版：打亂 actual draws 配對)
# ============================================================
def permutation_test(predict_func, all_draws, test_periods=1500,
                     n_perm=PERM_ITERATIONS, seed=42):
    """
    Permutation test：
    保持 predictions 不變，將 actual draws 隨機 shuffle，
    計算 shuffle 後的 M3+ 率。
    若真實 Edge 顯著大於 shuffle 分佈 → 策略有效。
    """
    rng = np.random.RandomState(seed)

    # 先收集所有 (predictions, actual) 配對
    predictions = []
    actuals = []
    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 150:
            continue
        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])
        try:
            bets = predict_func(hist)
            predictions.append(bets)
            actuals.append(actual)
        except:
            predictions.append(None)
            actuals.append(actual)

    # 真實 M3+ 率
    real_hits = 0
    for pred, act in zip(predictions, actuals):
        if pred is None:
            continue
        if any(len(set(b) & act) >= 3 for b in pred):
            real_hits += 1
    total = len(actuals)
    real_rate = real_hits / total * 100
    real_edge = real_rate - BASELINE_RATE

    # Permutation: shuffle actuals
    perm_edges = []
    actual_list = list(actuals)
    for _ in range(n_perm):
        rng.shuffle(actual_list)
        perm_hits = 0
        for pred, act in zip(predictions, actual_list):
            if pred is None:
                continue
            if any(len(set(b) & act) >= 3 for b in pred):
                perm_hits += 1
        perm_rate = perm_hits / total * 100
        perm_edges.append(perm_rate - BASELINE_RATE)

    p_value = np.mean([1 if pe >= real_edge else 0 for pe in perm_edges])
    perm_mean = np.mean(perm_edges)
    perm_std = np.std(perm_edges)

    return {
        'real_edge': real_edge,
        'real_hits': real_hits,
        'total': total,
        'perm_mean': perm_mean,
        'perm_std': perm_std,
        'p_value': p_value,
        'n_perm': n_perm,
    }


# ============================================================
# 3. MULTI-SEED STABILITY
# ============================================================
def multi_seed_test(predict_func, all_draws, test_periods=1000):
    """
    10 種子穩定性測試。
    P1 是確定性策略（無隨機成分），預期 std=0.00%。
    """
    edges = []
    for seed in range(N_SEEDS):
        np.random.seed(seed)  # 不應影響結果
        r = detailed_backtest(predict_func, all_draws, test_periods, f"seed_{seed}")
        edges.append(r['edge'])
    return {
        'edges': edges,
        'mean': np.mean(edges),
        'std': np.std(edges),
        'is_deterministic': np.std(edges) < 0.001,
    }


# ============================================================
# 4. WALK-FORWARD OOS
# ============================================================
def walk_forward_oos(predict_func, all_draws, n_folds=WF_FOLDS, window=WF_WINDOW):
    """
    滾動 walk-forward OOS:
    把最後 n_folds * window 期分成 n 個 fold，
    每個 fold 獨立回測 window 期。
    """
    total_test = n_folds * window
    available = len(all_draws)
    if available < total_test + 150:
        # 調整
        window = min(window, (available - 150) // n_folds)
        total_test = n_folds * window

    results = []
    for fold in range(n_folds):
        # fold 0 = 最早的 OOS, fold n-1 = 最近的
        start_offset = total_test - (fold + 1) * window
        fold_start = len(all_draws) - total_test + start_offset

        m3 = 0
        tested = 0
        for i in range(window):
            target_idx = fold_start + i
            if target_idx < 150 or target_idx >= len(all_draws):
                continue
            target = all_draws[target_idx]
            hist = all_draws[:target_idx]
            actual = set(target['numbers'])
            try:
                bets = predict_func(hist)
                hit = any(len(set(b) & actual) >= 3 for b in bets)
                if hit:
                    m3 += 1
                tested += 1
            except:
                tested += 1

        rate = m3 / tested * 100 if tested > 0 else 0
        edge = rate - BASELINE_RATE
        results.append({
            'fold': fold,
            'start_idx': fold_start,
            'tested': tested,
            'm3_plus': m3,
            'rate': rate,
            'edge': edge,
        })

    return results


# ============================================================
# 5. McNEMAR PAIRED COMPARISON (P1 vs OLD P0)
# ============================================================
def mcnemar_comparison(all_draws, test_periods=1500):
    """P1 vs 舊 P0偏差互補+回聲 配對比較"""
    both_hit = 0
    p1_only = 0
    p0_only = 0
    both_miss = 0

    for i in range(test_periods):
        target_idx = len(all_draws) - test_periods + i
        if target_idx < 150:
            continue
        target = all_draws[target_idx]
        hist = all_draws[:target_idx]
        actual = set(target['numbers'])

        try:
            p1_bets = neighbor_cold_2bet(hist)
            p1_hit = any(len(set(b) & actual) >= 3 for b in p1_bets)
        except:
            p1_hit = False

        try:
            p0_bets = original_p0_2bet(hist)
            p0_hit = any(len(set(b) & actual) >= 3 for b in p0_bets)
        except:
            p0_hit = False

        if p1_hit and p0_hit:
            both_hit += 1
        elif p1_hit and not p0_hit:
            p1_only += 1
        elif not p1_hit and p0_hit:
            p0_only += 1
        else:
            both_miss += 1

    # McNemar χ²
    if p1_only + p0_only > 0:
        chi2 = (abs(p1_only - p0_only) - 1) ** 2 / (p1_only + p0_only)
    else:
        chi2 = 0

    # 單側 p-value (P1 > P0)
    from scipy.stats import norm
    p_one_sided = 1 - norm.cdf(np.sqrt(chi2)) if p1_only > p0_only else 1.0

    return {
        'both_hit': both_hit,
        'p1_only': p1_only,
        'p0_only': p0_only,
        'both_miss': both_miss,
        'chi2': chi2,
        'p_one_sided': p_one_sided,
        'p1_total_hits': both_hit + p1_only,
        'p0_total_hits': both_hit + p0_only,
    }


# ============================================================
# MAIN
# ============================================================
def main():
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = sorted(db.get_all_draws('BIG_LOTTO'), key=lambda x: (x['date'], x['draw']))

    print("=" * 72)
    print("  P1 鄰號+冷號 2-bet — 完整驗證報告")
    print("=" * 72)
    print(f"  資料: {len(all_draws)} 期 大樂透")
    print(f"  最新: {all_draws[-1]['draw']} ({all_draws[-1]['date']})")
    print(f"  基準: {BASELINE_RATE:.4f}% (2注 M3+)")

    # === 鄰號定義 ===
    print("\n" + "-" * 72)
    print("  【鄰號定義】")
    print("  注1 選號池 = 上期開獎號各自 ±1（含自身）")
    print("    例: 上期 [6,10,23,27,47,48]")
    prev_example = [6, 10, 23, 27, 47, 48]
    nb = set()
    for n in prev_example:
        for d in range(-1, 2):
            nn = n + d
            if 1 <= nn <= 49:
                nb.add(nn)
    print(f"    → 鄰域 pool = {sorted(nb)} (共{len(nb)}個)")
    print(f"    → 按 (Fourier + 0.5×Markov) 綜合排名取 Top 6")
    print(f"  注2 = 近100期最冷號 Top12 → Sum-Constrained 組合取 6")
    print(f"  兩注之間零重疊")

    def p1_func(hist):
        return neighbor_cold_2bet(hist, cold_window=100, cold_pool=12)

    # ============ TEST 1: THREE-WINDOW ============
    print("\n" + "=" * 72)
    print("  TEST 1: 三窗口回測 (150 / 500 / 1500)")
    print("=" * 72)

    window_results = {}
    for w in WINDOWS:
        t0 = time.time()
        r = detailed_backtest(p1_func, all_draws, w, f"P1_{w}p")
        elapsed = time.time() - t0
        window_results[w] = r
        sig = "★" if abs(r['z']) > 1.96 else " "
        print(f"\n  [{w}期]")
        print(f"    M3+ = {r['m3_plus']} / {r['total']} ({r['rate']:.4f}%)")
        print(f"    基準 = {r['baseline']:.4f}%")
        print(f"    Edge = {r['edge']:+.4f}%")
        print(f"    z = {r['z']:.4f} {sig}")
        bet_str = " | ".join(f"注{k+1}: {v}次" for k, v in sorted(r['per_bet'].items()))
        print(f"    各注命中: {bet_str}")
        print(f"    耗時: {elapsed:.1f}s")

    # 模式判定
    edges = [window_results[w]['edge'] for w in WINDOWS]
    if all(e > 0 for e in edges):
        pattern = "STABLE ✅"
    elif edges[2] < 0:
        pattern = "INEFFECTIVE ❌" if edges[0] < 0 else "SHORT_MOMENTUM ⚠️"
    elif edges[0] < 0 and edges[2] > 0:
        pattern = "LATE_BLOOMER ⚠️"
    else:
        pattern = "MIXED ⚠️"
    print(f"\n  三窗口模式: {pattern}")
    print(f"  Edge 走勢: {edges[0]:+.4f}% → {edges[1]:+.4f}% → {edges[2]:+.4f}%")

    # ============ TEST 2: PERMUTATION TEST ============
    print("\n" + "=" * 72)
    print(f"  TEST 2: Permutation Test ({PERM_ITERATIONS} iterations, 1500期)")
    print("=" * 72)

    t0 = time.time()
    perm = permutation_test(p1_func, all_draws, test_periods=1500, n_perm=PERM_ITERATIONS)
    elapsed = time.time() - t0
    print(f"\n    真實 Edge   = {perm['real_edge']:+.4f}% ({perm['real_hits']}/{perm['total']})")
    print(f"    Perm 均值   = {perm['perm_mean']:+.4f}%")
    print(f"    Perm StdDev = {perm['perm_std']:.4f}%")
    print(f"    p-value     = {perm['p_value']:.4f}")
    sig_perm = "✅ 顯著 (p < 0.05)" if perm['p_value'] < 0.05 else "❌ 不顯著 (p ≥ 0.05)"
    print(f"    判定: {sig_perm}")
    print(f"    耗時: {elapsed:.1f}s")

    # ============ TEST 3: MULTI-SEED STABILITY ============
    print("\n" + "=" * 72)
    print(f"  TEST 3: {N_SEEDS} 種子穩定性 (1000期)")
    print("=" * 72)

    t0 = time.time()
    seed_result = multi_seed_test(p1_func, all_draws, test_periods=1000)
    elapsed = time.time() - t0
    print(f"\n    各種子 Edge: {[f'{e:+.4f}%' for e in seed_result['edges']]}")
    print(f"    Mean Edge = {seed_result['mean']:+.4f}%")
    print(f"    Std  Edge = {seed_result['std']:.4f}%")
    det = "✅ 確定性策略 (std=0)" if seed_result['is_deterministic'] else "⚠️ 含隨機成分"
    print(f"    判定: {det}")
    print(f"    耗時: {elapsed:.1f}s")

    # ============ TEST 4: WALK-FORWARD OOS ============
    print("\n" + "=" * 72)
    print(f"  TEST 4: Walk-Forward OOS ({WF_FOLDS} folds × {WF_WINDOW}期)")
    print("=" * 72)

    t0 = time.time()
    wf_results = walk_forward_oos(p1_func, all_draws)
    elapsed = time.time() - t0
    positive_folds = 0
    print()
    for fr in wf_results:
        sign = "+" if fr['edge'] > 0 else ""
        mark = "✅" if fr['edge'] > 0 else "❌"
        print(f"    Fold {fr['fold']}: {fr['m3_plus']}/{fr['tested']} "
              f"({fr['rate']:.2f}%) Edge={sign}{fr['edge']:.4f}% {mark}")
        if fr['edge'] > 0:
            positive_folds += 1
    wf_edges = [fr['edge'] for fr in wf_results]
    print(f"\n    正 Edge folds: {positive_folds}/{len(wf_results)}")
    print(f"    Avg OOS Edge: {np.mean(wf_edges):+.4f}%")
    print(f"    耗時: {elapsed:.1f}s")

    # ============ TEST 5: McNEMAR vs OLD P0 ============
    print("\n" + "=" * 72)
    print("  TEST 5: McNemar 配對比較 — P1 vs 舊 P0偏差互補+回聲 (1500期)")
    print("=" * 72)

    t0 = time.time()
    mc = mcnemar_comparison(all_draws, 1500)
    elapsed = time.time() - t0
    print(f"\n    2×2 配對表:")
    print(f"                P0 命中    P0 未中")
    print(f"    P1 命中     {mc['both_hit']:>5}     {mc['p1_only']:>5}")
    print(f"    P1 未中     {mc['p0_only']:>5}     {mc['both_miss']:>5}")
    print(f"\n    P1 總命中: {mc['p1_total_hits']}   P0 總命中: {mc['p0_total_hits']}")
    print(f"    P1 獨贏: {mc['p1_only']}   P0 獨贏: {mc['p0_only']}")
    print(f"    χ² = {mc['chi2']:.4f}")
    print(f"    p(單側, P1>P0) = {mc['p_one_sided']:.4f}")
    if mc['p1_total_hits'] > mc['p0_total_hits']:
        if mc['p_one_sided'] < 0.05:
            mc_verdict = "✅ P1 顯著優於 P0"
        else:
            mc_verdict = "⚠️ P1 命中更多但差異不顯著"
    else:
        mc_verdict = "❌ P1 未優於 P0"
    print(f"    判定: {mc_verdict}")
    print(f"    耗時: {elapsed:.1f}s")

    # ============ FINAL VERDICT ============
    print("\n" + "=" * 72)
    print("  綜合判定")
    print("=" * 72)

    checks = {
        '三窗口全正': all(window_results[w]['edge'] > 0 for w in WINDOWS),
        '1500p z>1.96': abs(window_results[1500]['z']) > 1.96,
        'Permutation p<0.05': perm['p_value'] < 0.05,
        '確定性 (std=0)': seed_result['is_deterministic'],
        'WF OOS ≥3/5 正': positive_folds >= 3,
        'WF Avg Edge>0': np.mean(wf_edges) > 0,
    }

    all_pass = True
    for check, passed in checks.items():
        mark = "✅" if passed else "❌"
        print(f"    {mark} {check}")
        if not passed:
            all_pass = False

    print()
    if all_pass:
        print("  🟢 全部通過 — P1 可升級 production")
    else:
        failed = [k for k, v in checks.items() if not v]
        print(f"  🔴 未全部通過 — 失敗項: {', '.join(failed)}")
        print("  建議: 維持舊策略，P1 暫不升級")

    # Save report
    report = {
        'strategy': 'P1_NeighborCold_2bet',
        'neighbor_definition': {
            'bet1': '上期6個開獎號各自±1含自身 → Fourier+0.5*Markov排名 → Top6',
            'bet2': '近100期最冷號Top12 → Sum-Constrained組合 → Top6',
            'overlap': '零重疊',
            'delta': 1,
            'pool_size_typical': '12~18',
        },
        'script_paths': {
            'strategy_impl': 'tools/backtest_p0_p3_optimization.py::neighbor_cold_2bet',
            'production': 'tools/quick_predict.py::biglotto_p1_neighbor_cold_2bet',
            'validation': 'tools/validate_p1_full.py',
        },
        'three_window': {
            str(w): {
                'm3_plus': window_results[w]['m3_plus'],
                'total': window_results[w]['total'],
                'rate': round(window_results[w]['rate'], 4),
                'edge': round(window_results[w]['edge'], 4),
                'z': round(window_results[w]['z'], 4),
            } for w in WINDOWS
        },
        'permutation': {
            'real_edge': round(perm['real_edge'], 4),
            'perm_mean': round(perm['perm_mean'], 4),
            'perm_std': round(perm['perm_std'], 4),
            'p_value': round(perm['p_value'], 4),
            'n_perm': PERM_ITERATIONS,
        },
        'multi_seed': {
            'mean_edge': round(seed_result['mean'], 4),
            'std_edge': round(seed_result['std'], 4),
            'is_deterministic': seed_result['is_deterministic'],
        },
        'walk_forward': [{
            'fold': fr['fold'],
            'edge': round(fr['edge'], 4),
            'tested': fr['tested'],
        } for fr in wf_results],
        'mcnemar_vs_p0': {
            'p1_hits': mc['p1_total_hits'],
            'p0_hits': mc['p0_total_hits'],
            'p1_only': mc['p1_only'],
            'p0_only': mc['p0_only'],
            'chi2': round(mc['chi2'], 4),
            'p_one_sided': round(mc['p_one_sided'], 4),
        },
        'checks': checks,
        'all_pass': all_pass,
    }

    out_path = os.path.join(project_root, 'p1_validation_report.json')
    with open(out_path, 'w') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, default=str)
    print(f"\n  完整報告已保存: {out_path}")


if __name__ == "__main__":
    main()
