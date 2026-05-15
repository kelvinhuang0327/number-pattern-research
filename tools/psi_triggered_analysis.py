#!/usr/bin/env python3
"""
PSI 觸發分析腳本
當 DAILY_539 PSI > 0.2 時執行，快速定位漂移特徵並生成假設優先序。

用法: python3 tools/psi_triggered_analysis.py [--lottery DAILY_539] [--window 30]
"""
import sys, os, json, argparse
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sqlite3

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'lottery_api', 'data', 'lottery_v2.db')


def load_draws(lottery_type: str, n: int = 300):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute(
        "SELECT numbers FROM draws WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) DESC LIMIT ?",
        (lottery_type, n)
    )
    rows = [json.loads(r[0]) for r in cur.fetchall()]
    conn.close()
    return rows


def compute_features(draws):
    feats = []
    for d in draws:
        d = sorted(d)
        gaps = [d[i+1] - d[i] for i in range(len(d)-1)]
        consec = sum(1 for g in gaps if g == 1)
        feats.append({
            'sum': sum(d),
            'odd': sum(1 for n in d if n % 2 == 1),
            'zone_low':  sum(1 for n in d if n <= 13),
            'zone_mid':  sum(1 for n in d if 14 <= n <= 26),
            'zone_high': sum(1 for n in d if n >= 27),
            'consec_pairs': consec,
            'max_gap': max(gaps) if gaps else 0,
        })
    return feats


def z_score(val, mean, std):
    return (val - mean) / std if std > 0 else 0.0


def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0


def std(xs):
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / len(xs)) ** 0.5 if xs else 0.0


def run_analysis(lottery_type: str = 'DAILY_539', short_window: int = 30):
    print(f"\n{'='*60}")
    print(f"  PSI 觸發分析 — {lottery_type}")
    print(f"  短窗口={short_window}p  長基準=300p")
    print(f"{'='*60}")

    draws_all = load_draws(lottery_type, 300)
    if len(draws_all) < short_window + 50:
        print(f"  ⚠️  資料不足（{len(draws_all)}期），無法分析")
        return

    draws_short = draws_all[:short_window]
    draws_long  = draws_all[:300]

    fs_short = compute_features(draws_short)
    fs_long  = compute_features(draws_long)

    keys = ['sum', 'odd', 'zone_low', 'zone_mid', 'zone_high', 'consec_pairs', 'max_gap']
    labels = {
        'sum':         '和值',
        'odd':         '奇數碼數',
        'zone_low':    'Zone低(1-13)',
        'zone_mid':    'Zone中(14-26)',
        'zone_high':   'Zone高(27-39)',
        'consec_pairs':'連號對數',
        'max_gap':     '最大Gap',
    }

    print(f"\n{'特徵':<16} {'短期均值':>10} {'長期均值':>10} {'z-score':>8} {'狀態':>10}")
    print("-" * 60)

    alerts = []
    for k in keys:
        short_vals = [f[k] for f in fs_short]
        long_vals  = [f[k] for f in fs_long]
        m_short = mean(short_vals)
        m_long  = mean(long_vals)
        s_long  = std(long_vals)
        se      = s_long / (short_window ** 0.5)
        z = z_score(m_short, m_long, se) if se > 0 else 0.0

        status = '正常'
        if abs(z) > 2.5:
            status = '🔴 ALERT'
            alerts.append((k, z, m_short, m_long))
        elif abs(z) > 1.8:
            status = '🟡 WATCH'

        print(f"  {labels[k]:<14} {m_short:>10.2f} {m_long:>10.2f} {z:>8.2f} {status:>10}")

    # Per-number hot/cold analysis
    freq_short = Counter(n for d in draws_short for n in d)
    freq_long  = Counter(n for d in draws_long  for n in d)
    pool_size  = 39 if lottery_type == 'DAILY_539' else (49 if lottery_type == 'BIG_LOTTO' else 38)
    draw_size  = 5  if lottery_type == 'DAILY_539' else (6  if lottery_type == 'BIG_LOTTO' else 6)
    exp_rate   = draw_size / pool_size

    hot_cold = []
    for n in range(1, pool_size + 1):
        r_short = freq_short.get(n, 0) / short_window
        r_long  = freq_long.get(n, 0)  / 300
        se_n    = (exp_rate * (1 - exp_rate) / short_window) ** 0.5
        z_n     = (r_short - exp_rate) / se_n if se_n > 0 else 0.0
        if abs(z_n) > 2.5:
            hot_cold.append((n, z_n, r_short))

    if hot_cold:
        print(f"\n  個別號碼急速漂移（|z|>2.5）：")
        for n, z_n, rate in sorted(hot_cold, key=lambda x: -abs(x[1])):
            tag = '🔥過熱' if z_n > 0 else '🧊過冷'
            print(f"    號碼 {n:2d}: rate={rate:.3f} exp={exp_rate:.3f} z={z_n:.2f} {tag}")

    # Summary
    print(f"\n{'='*60}")
    print(f"  ⚡ 漂移摘要")
    print(f"{'='*60}")
    if not alerts and not hot_cold:
        print(f"  ✅ 無顯著漂移（PSI 上升可能屬採樣波動）")
        print(f"  建議：繼續監控，等待下期 PSI 更新")
    else:
        print(f"  🔴 發現 {len(alerts)} 個特徵漂移 + {len(hot_cold)} 個號碼漂移")
        print()
        for k, z, m_s, m_l in alerts:
            direction = '偏高' if z > 0 else '偏低'
            hyp_map = {
                'sum': 'H-PSI-1（和值 Regime）',
                'odd': 'H-PSI-3（奇偶比例）',
                'zone_low': 'H-PSI-2（Zone 分布）',
                'zone_mid': 'H-PSI-2（Zone 分布）',
                'zone_high': 'H-PSI-2（Zone 分布）',
                'consec_pairs': 'H-PSI-5（連號模式）',
                'max_gap': 'H-PSI-5（連號模式）',
            }
            print(f"  → {labels[k]} {direction}（z={z:.2f}）→ 執行 {hyp_map.get(k,'未知假設')}")
        if hot_cold:
            print(f"  → 號碼急速漂移 → 執行 H-PSI-4（冷熱切換）")

        print(f"\n  執行優先序：")
        priority = sorted(set(
            [hyp_map.get(k, 'H-PSI-4') for k, _, _, _ in alerts] +
            (['H-PSI-4'] if hot_cold else [])
        ))
        for i, h in enumerate(priority, 1):
            print(f"    {i}. {h}")

    print()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--lottery', default='DAILY_539')
    parser.add_argument('--window', type=int, default=30)
    args = parser.parse_args()
    run_analysis(args.lottery, args.window)
