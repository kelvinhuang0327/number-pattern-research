#!/usr/bin/env python3
"""
P2: 特別號 V3 MAB recency bias 調整回測
==========================================
來源: 115000018期 — V3 MAB 偏向 #2 (近3期連開), 實際 #5 出現4次
問題: MAB 評估窗口=20期, 對3連開等近期極端事件過度敏感

調整方案:
  V3_orig:  MAB 評估窗口 = 20 期 (uniform)
  V3_w30:   MAB 評估窗口 = 30 期 (longer-term prior)
  V3_w40:   MAB 評估窗口 = 40 期 (even longer prior)
  V3_decay: MAB 評估窗口 = 20 期 + 指數衰減 (近期0.9^i加權)

指標: Top-1 命中率 (actual special 在預測 Top-1 中)
     Top-3 命中率 (actual special 在預測 Top-3 中)
     基準 Top-1: 1/8 = 12.5%, Top-3: 3/8 = 37.5%

驗證: 500/1000期三窗口
"""
import sys, os, json
import numpy as np
from collections import Counter, defaultdict
from typing import List, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lottery_api'))
from lottery_api.database import DatabaseManager

SEED = 42
np.random.seed(SEED)


def normalize_scores(scores: Dict[int, float]) -> Dict[int, float]:
    if not scores:
        return {}
    vals = list(scores.values())
    min_v, max_v = min(vals), max(vals)
    if max_v > min_v:
        return {k: (v - min_v) / (max_v - min_v) for k, v in scores.items()}
    return {k: 0.5 for k in scores}


def calc_long_term_bias(history):
    specials = [d.get('special') for d in history if d.get('special')]
    counts = Counter(specials)
    return normalize_scores({n: counts.get(n, 0) for n in range(1, 9)})


def calc_recent_hot(history, n=15):
    scores = {n: 0.0 for n in range(1, 9)}
    for i, d in enumerate(history[:n]):
        s = d.get('special')
        if s and 1 <= s <= 8:
            scores[s] += np.exp(-i * 0.2)
    max_s = max(scores.values()) if scores else 1
    if max_s > 0:
        scores = {k: v/max_s for k, v in scores.items()}
    return scores


def calc_cycle(history):
    scores = {n: 0.0 for n in range(1, 9)}
    last_seen = {n: 99 for n in range(1, 9)}
    for i, d in enumerate(history):
        s = d.get('special')
        if s and last_seen[s] == 99:
            last_seen[s] = i
    for n, gap in last_seen.items():
        if 5 <= gap <= 12:
            scores[n] = 1.0
        elif gap > 16:
            scores[n] = 0.5
        else:
            scores[n] = 0.2
    return scores


def calc_gap_pressure(history):
    scores = {n: 0.0 for n in range(1, 9)}
    if len(history) < 200:
        return scores
    specials = [d.get('special') for d in history if d.get('special')]
    max_gaps = {n: 0 for n in range(1, 9)}
    avg_gaps = {n: 8.0 for n in range(1, 9)}
    for n in range(1, 9):
        idxs = [i for i, x in enumerate(specials) if x == n]
        if len(idxs) > 2:
            gaps = [idxs[i] - idxs[i-1] for i in range(1, len(idxs))]
            max_gaps[n] = max(gaps)
            avg_gaps[n] = sum(gaps) / len(gaps)
    current_gaps = {n: 99 for n in range(1, 9)}
    for n in range(1, 9):
        try:
            current_gaps[n] = specials.index(n)
        except:
            pass
    for n in range(1, 9):
        c_gap = current_gaps[n]
        m_gap = max_gaps[n]
        a_gap = avg_gaps[n]
        if c_gap > a_gap:
            scores[n] = min(1.0, (c_gap - a_gap) / max(1, m_gap - a_gap))
        else:
            scores[n] = 0.1
    return scores


def predict_special_mab(history, mab_window=20, use_decay=False):
    """
    簡化版特別號預測 (使用核心子策略 + MAB權重)
    mab_window: MAB 評估窗口 (原版=20, 建議30或40)
    use_decay: 是否在MAB評估中使用指數衰減 (衰減率0.9)
    """
    if len(history) < 20:
        scores = calc_long_term_bias(history)
        return sorted(scores.items(), key=lambda x: -x[1])

    # 子策略分數
    bias = calc_long_term_bias(history)
    hot = calc_recent_hot(history)
    cycle = calc_cycle(history)
    gap = calc_gap_pressure(history)

    # MAB 權重評估 (使用 mab_window 期)
    default_w = {'bias': 0.25, 'hot': 0.20, 'cycle': 0.20, 'gap': 0.20, 'other': 0.15}
    arms = {k: {'win': 1, 'total': 2} for k in default_w}

    eval_periods = min(mab_window, len(history) - 1)
    for i in range(eval_periods):
        target = history[i]
        prev_hist = history[i+1:i+51]
        actual = target.get('special')
        if not actual:
            continue

        weight = 1.0
        if use_decay:
            weight = 0.9 ** i  # 近期事件權重高

        # 各策略評估
        for arm_name, arm_func in [('bias', calc_long_term_bias), ('hot', calc_recent_hot),
                                   ('cycle', calc_cycle), ('gap', calc_gap_pressure)]:
            try:
                sc = arm_func(prev_hist)
                top2 = sorted(sc.items(), key=lambda x: -x[1])[:2]
                top2_nums = [x[0] for x in top2]
                arms[arm_name]['win'] += weight if actual in top2_nums else 0
            except:
                pass
        for k in arms:
            arms[k]['total'] += weight

    # 計算最終權重
    raw_rates = {k: arms[k]['win'] / arms[k]['total'] for k in arms}
    total_r = sum(raw_rates.values())
    final_w = {}
    for k in default_w:
        if k in raw_rates:
            final_w[k] = (raw_rates[k]/total_r) * 0.5 + default_w[k] * 0.5
        else:
            final_w[k] = default_w.get(k, 0.15)

    # 融合分數
    combined = {}
    for n in range(1, 9):
        combined[n] = (
            bias.get(n, 0.5) * final_w['bias'] +
            hot.get(n, 0.5) * final_w['hot'] +
            cycle.get(n, 0.5) * final_w['cycle'] +
            gap.get(n, 0.0) * final_w['gap']
        )

    return sorted(combined.items(), key=lambda x: -x[1])


def run_special_backtest(draws, window, mab_window=20, use_decay=False, min_history=50):
    """回測特別號預測 Top-1 和 Top-3 命中率"""
    top1_hits = []
    top3_hits = []
    start = max(min_history, len(draws) - window)
    for i in range(start, len(draws)):
        history = draws[:i]
        actual_special = draws[i].get('special')
        if not actual_special:
            continue
        try:
            ranked = predict_special_mab(history, mab_window=mab_window, use_decay=use_decay)
            top1 = ranked[0][0] if ranked else None
            top3 = [x[0] for x in ranked[:3]]
            top1_hits.append(1 if top1 == actual_special else 0)
            top3_hits.append(1 if actual_special in top3 else 0)
        except Exception:
            top1_hits.append(0)
            top3_hits.append(0)
    return top1_hits, top3_hits


def main():
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(project_root, 'lottery_api', 'data', 'lottery_v2.db')
    db = DatabaseManager(db_path)
    all_draws = db.get_all_draws('POWER_LOTTO')
    draws = sorted(all_draws, key=lambda x: (len(x['draw']), x['draw']))
    draws_with_special = [d for d in draws if d.get('special')]

    print("=" * 70)
    print("  P2: 特別號 MAB recency bias 調整回測")
    print(f"  N={len(draws_with_special)}期(有特別號), seed={SEED}")
    print(f"  基準: Top-1=12.5%, Top-3=37.5%")
    print("=" * 70)

    configs = [
        ("V3_orig",  20, False),
        ("V3_w30",   30, False),
        ("V3_w40",   40, False),
        ("V3_decay", 20, True),
    ]

    results = {}
    for name, mab_w, decay in configs:
        print(f"\n[{name}] (mab_window={mab_w}, decay={decay})")
        row = {}
        for window in [500, 1000]:
            top1, top3 = run_special_backtest(draws_with_special, window, mab_window=mab_w, use_decay=decay)
            if not top1:
                continue
            n = len(top1)
            top1_rate = sum(top1) / n
            top3_rate = sum(top3) / n
            top1_edge = top1_rate - 0.125  # 基準 1/8
            top3_edge = top3_rate - 0.375  # 基準 3/8
            row[window] = {
                'n': n, 'top1_rate': top1_rate, 'top3_rate': top3_rate,
                'top1_edge': top1_edge, 'top3_edge': top3_edge
            }
            t1s = "+" if top1_edge >= 0 else ""
            t3s = "+" if top3_edge >= 0 else ""
            print(f"  {window:4d}期 (n={n}): Top-1={top1_rate*100:.2f}% ({t1s}{top1_edge*100:.2f}%), Top-3={top3_rate*100:.2f}% ({t3s}{top3_edge*100:.2f}%)")
        results[name] = row

    # 比較分析
    print(f"\n{'='*70}")
    print(f"  [比較分析 (1000期)]")
    print(f"  {'策略':<15} {'Top-1 Edge':>12} {'Top-3 Edge':>12} {'較V3_orig Top-1':>16}")
    orig_t1_1000 = results.get('V3_orig', {}).get(1000, {}).get('top1_edge', 0)
    for name, _, _ in configs:
        if 1000 in results.get(name, {}):
            t1e = results[name][1000]['top1_edge']
            t3e = results[name][1000]['top3_edge']
            diff = t1e - orig_t1_1000
            t1s = "+" if t1e >= 0 else ""
            t3s = "+" if t3e >= 0 else ""
            ds = "+" if diff >= 0 else ""
            print(f"  {name:<15} {t1s}{t1e*100:.2f}%{'':>6} {t3s}{t3e*100:.2f}%{'':>6} {ds}{diff*100:.2f}%")

    # 最佳配置
    best = max([(name, results[name][1000]['top1_edge'])
                for name, _, _ in configs if 1000 in results.get(name, {})],
               key=lambda x: x[1])
    print(f"\n  最佳配置: {best[0]} (Top-1 Edge={best[1]*100:+.2f}%)")

    # 結論
    best_name = best[0]
    best_edge = best[1]
    orig_edge = orig_t1_1000
    improvement = best_edge - orig_edge

    if improvement > 0.02 and best_name != 'V3_orig':
        conclusion = f"ADOPT: {best_name} 改善Top-1 {improvement*100:+.2f}% → 更新special_predictor.py"
    elif improvement > 0.01 and best_name != 'V3_orig':
        conclusion = f"WEAK: {best_name} 輕微改善 {improvement*100:+.2f}%, 可選擇性更新"
    else:
        conclusion = "REJECT: 無顯著改善, 維持V3_orig"

    print(f"\n  [結論] {conclusion}")

    out = {
        'strategy': 'special_predictor_mab_decay_adjustment',
        'draw_count': len(draws_with_special),
        'baseline_top1': 0.125,
        'baseline_top3': 0.375,
        'results': results,
        'best_config': {'name': best_name, 'top1_edge_1000': best_edge, 'improvement_vs_orig': improvement},
        'conclusion': conclusion
    }
    out_path = os.path.join(project_root, 'backtest_power_special_decay_results.json')
    with open(out_path, 'w') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(f"\n  結果已保存: backtest_power_special_decay_results.json")


if __name__ == '__main__':
    main()
