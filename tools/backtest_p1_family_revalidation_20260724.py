#!/usr/bin/env python3
"""
BIG_LOTTO P1+偏差互補家族 重新驗證 (2026-07-24)
================================================
背景：
  `biglotto_p1_deviation_5bet()`（連同其 4-bet 子集 "P1+偏差互補"）於
  2026-02-25/26 驗證並部署，2026-05-09 被 commit 73062646
  ("feat(replay-ui): expose all-lifecycle strategy replay history")
  當作一次無關 quick_predict.py 重寫的 side-effect 意外刪除。

  原始策略邏輯已從 `73062646^` 逐字復原至：
    tools/backtest_p1_deviation_4bet.py
    tools/backtest_p1dev_5bet.py

  本腳本重新驗證同一套邏輯，但採用現行（非 2026-02 當時）的資料與統計慣例：
    1. `get_canonical_draws()` 而非原始的 `get_all_draws()` —— BIG_LOTTO 原始
       draws 表已知 ~90% 受污染（L_P246_A: SIM_HYPHEN/DATE_FORMAT_ALIEN/
       SMALL_POOL_ALIEN），現行 quick_predict.py::load_history() 已改用此
       過濾過的版本，本次重驗必須採用，否則會重新引入已修好的污染 bug。
    2. `lottery_api.utils.permutation_test`（Binomial MC null + Phipson-Smyth
       plus-one 校正）而非舊式 shuffle-based permutation —— 2026-06 記錄的
       L96 bug 指出 shuffle 會保留 hit-label 的 mean，導致 p 值虛高趨近 1.0。
    3. `lottery_api.utils.baseline_calculator.n_ticket_probability()` 作為
       baseline SSOT，取代原腳本手刻的 `1-(1-0.0186)^n`。
    4. 額外報告 2026-02-26（原始驗證截止日）之後的 walk-forward OOS 切片，
       誠實揭露這是「原始研究者從未見過」的資料。
    5. McNemar 對照組改為現行實際在跑的 `biglotto_5bet_orthogonal`（而非
       原腳本裡已經退役的 TS3+Markov 4注），這樣才是與現況的真實比較。
    6. 新增 Sharpe ratio（rolling-edge 方法，仿照
       tools/research_39lotto_step4_8.py）。

  策略演算法本身（p1_neighbor_cold_2bet / deviation_complement_2bet /
  p1_deviation_4bet / bet5_sum_constrained）逐字從復原檔案 import，不做任何
  參數或邏輯修改 —— 本次只重新驗證，不重新優化。

Usage:
    tools/backtest_p1_family_revalidation_20260724.py
"""
import os
import sys
import json
import time
import random
import numpy as np
from scipy.stats import norm as scipy_norm
from scipy.stats import chi2 as chi2_dist

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)
sys.path.insert(0, os.path.join(project_root, 'lottery_api'))

from lottery_api.database import DatabaseManager
from lottery_api.utils.baseline_calculator import n_ticket_probability
from lottery_api.utils.permutation_test import empirical_p_value, permutation_summary

from tools.backtest_p1dev_5bet import (
    p1_deviation_4bet,
    bet5_sum_constrained,
)
from tools.quick_predict import biglotto_5bet_orthogonal as live_default_5bet

MAX_NUM = 49
PICK = 6
SEED = 42
N_PERM = 2000
WINDOWS = [150, 500, 1500]
MIN_BUF = 150
DISCOVERY_CUTOFF_DATE = '2026/02/26'  # original P1-family validation cutoff

SNAPSHOT_DB = os.path.join(
    project_root, 'outputs', 'db_snapshots',
    'lottery_v2_p1family_revalidation_20260724.db'
)

BASELINE_4 = n_ticket_probability(pool_size=MAX_NUM, pick_count=PICK, n_tickets=4, match_threshold=3)
BASELINE_5 = n_ticket_probability(pool_size=MAX_NUM, pick_count=PICK, n_tickets=5, match_threshold=3)


def load_canonical_biglotto(db_path):
    db = DatabaseManager(db_path=db_path)
    draws = db.get_canonical_draws(lottery_type='BIG_LOTTO')
    return sorted(draws, key=lambda x: (x['date'], x['draw']))


def p1_deviation_5bet(history):
    bets4 = p1_deviation_4bet(history)
    used = set(n for b in bets4 for n in b)
    pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
    bet5 = sorted(bet5_sum_constrained(history, pool))
    return bets4 + [bet5]


def live_default_bets(history):
    raw = live_default_5bet(history)
    return [b['numbers'] for b in raw]


def precompute(draws, start_idx):
    """One pass over [start_idx, len(draws)) with strict history[:i] slicing (no lookahead)."""
    N = len(draws) - start_idx
    print(f"  precomputing {N} periods... ", end='', flush=True)
    t0 = time.time()

    dates = []
    hit4 = []
    hit5 = []
    hit_live = []

    for i in range(start_idx, len(draws)):
        target = set(draws[i]['numbers'])
        history = draws[:i]
        dates.append(draws[i]['date'])

        try:
            bets4 = p1_deviation_4bet(history)
            h4 = any(len(set(b) & target) >= 3 for b in bets4)
        except Exception:
            bets4, h4 = None, False
        hit4.append(h4)

        try:
            if bets4 is None:
                raise RuntimeError("bets4 unavailable")
            used = set(n for b in bets4 for n in b)
            pool = [n for n in range(1, MAX_NUM + 1) if n not in used]
            bet5 = sorted(bet5_sum_constrained(history, pool))
            h5 = h4 or (len(set(bet5) & target) >= 3)
        except Exception:
            h5 = h4
        hit5.append(h5)

        try:
            live_bets = live_default_bets(history)
            hl = any(len(set(b) & target) >= 3 for b in live_bets)
        except Exception:
            hl = False
        hit_live.append(hl)

    print(f"done ({time.time() - t0:.1f}s)")
    return {
        'dates': dates,
        'hit4': hit4,
        'hit5': hit5,
        'hit_live': hit_live,
    }


def edge_stats(hits, n_periods, baseline, label=""):
    N = len(hits)
    start = max(0, N - n_periods)
    window = hits[start:]
    total = len(window)
    if total == 0:
        return None
    h = sum(window)
    rate = h / total
    edge = rate - baseline
    z = (rate - baseline) / np.sqrt(baseline * (1 - baseline) / total)
    p = 2 * (1 - scipy_norm.cdf(abs(z)))
    return {
        'label': label, 'n_periods': total, 'hits': h, 'rate': rate,
        'baseline': baseline, 'edge_pct': edge * 100, 'z': z, 'p': p,
    }


def binomial_mc_null(n_periods, baseline, n_perm, seed):
    """L96-safe null: fresh Bernoulli(baseline) draws per trial (not label-shuffling)."""
    rng = random.Random(seed)
    null_rates = []
    for _ in range(n_perm):
        hits = sum(1 for _ in range(n_periods) if rng.random() < baseline)
        null_rates.append(hits / n_periods)
    return null_rates


def mcnemar(hits_a, hits_b, n_periods, label=""):
    """McNemar with continuity correction. b_wins = b hit & a missed; a_wins = a hit & b missed."""
    N = len(hits_a)
    start = max(0, N - n_periods)
    a = hits_a[start:]
    b = hits_b[start:]
    a_wins = sum(1 for ha, hb in zip(a, b) if ha and not hb)
    b_wins = sum(1 for ha, hb in zip(a, b) if hb and not ha)
    total_disc = a_wins + b_wins
    if total_disc == 0:
        return {'label': label, 'chi2': 0.0, 'p': 1.0, 'a_wins': a_wins, 'b_wins': b_wins}
    chi2 = (abs(a_wins - b_wins) - 1) ** 2 / total_disc
    p = 1 - chi2_dist.cdf(chi2, df=1)
    return {'label': label, 'chi2': chi2, 'p': p, 'a_wins': a_wins, 'b_wins': b_wins}


def sharpe_ratio(hits, n_periods, baseline, window=300, step=150):
    N = len(hits)
    start = max(0, N - n_periods)
    arr = np.array(hits[start:], dtype=float)
    n = len(arr)
    rolling_edges = []
    for j in range(0, max(0, n - window) + 1, step):
        chunk = arr[j:j + window]
        if len(chunk) < window:
            continue
        rolling_edges.append(chunk.mean() - baseline)
    if not rolling_edges:
        return None, 0
    rolling_edges = np.array(rolling_edges)
    if rolling_edges.std() == 0:
        return 0.0, len(rolling_edges)
    return float(rolling_edges.mean() / rolling_edges.std()), len(rolling_edges)


def oos_slice_stats(dates, hits, baseline, cutoff_date, label=""):
    idx = [i for i, d in enumerate(dates) if d > cutoff_date]
    if not idx:
        return None
    window = [hits[i] for i in idx]
    total = len(window)
    h = sum(window)
    rate = h / total
    edge = rate - baseline
    z = (rate - baseline) / np.sqrt(baseline * (1 - baseline) / total) if 0 < baseline < 1 else float('nan')
    p = 2 * (1 - scipy_norm.cdf(abs(z))) if not np.isnan(z) else float('nan')
    return {
        'label': label, 'n_periods': total, 'hits': h, 'rate': rate,
        'baseline': baseline, 'edge_pct': edge * 100, 'z': z, 'p': p,
        'first_date': dates[idx[0]], 'last_date': dates[idx[-1]],
    }


def pr(r):
    if not r:
        print("  (no data)")
        return
    sig = "***" if r['p'] < 0.01 else ("**" if r['p'] < 0.05 else ("*" if r['p'] < 0.10 else ""))
    print(f"  {r['label']:<32s} {r['hits']:4d}/{r['n_periods']:5d} "
          f"= {r['rate']:.4f}  baseline={r['baseline']:.4f}  "
          f"Edge={r['edge_pct']:+.2f}%  z={r['z']:+.2f}{sig}  p={r['p']:.4f}")


def main():
    np.random.seed(SEED)
    random.seed(SEED)

    print(f"\nSnapshot DB: {SNAPSHOT_DB}")
    draws = load_canonical_biglotto(SNAPSHOT_DB)
    print(f"Canonical BIG_LOTTO draws: {len(draws)}  (seed={SEED})")
    print(f"Earliest: {draws[0]['draw']} {draws[0]['date']}   Latest: {draws[-1]['draw']} {draws[-1]['date']}")
    n_post_cutoff = sum(1 for d in draws if d['date'] > DISCOVERY_CUTOFF_DATE)
    print(f"Draws strictly after original discovery cutoff ({DISCOVERY_CUTOFF_DATE}): {n_post_cutoff}\n")

    t0 = time.time()
    start_idx = max(len(draws) - 1500, MIN_BUF)
    pre = precompute(draws, start_idx)

    results = {'windows': {}, 'oos': {}, 'mcnemar': {}, 'sharpe': {}, 'permutation': {}}

    print(f"\n{'=' * 78}\n  Three-window Edge (150 / 500 / 1500)\n{'=' * 78}")
    for w in WINDOWS:
        print(f"\n--- {w}p window ---")
        r4 = edge_stats(pre['hit4'], w, BASELINE_4, label="4-bet P1+DevComp")
        r5 = edge_stats(pre['hit5'], w, BASELINE_5, label="5-bet P1+DevComp+Sum")
        rl = edge_stats(pre['hit_live'], w, BASELINE_5, label="LIVE biglotto_5bet_orthogonal")
        pr(r4); pr(r5); pr(rl)
        results['windows'][w] = {'bet4': r4, 'bet5': r5, 'live': rl}

    print(f"\n{'=' * 78}\n  Post-{DISCOVERY_CUTOFF_DATE} walk-forward OOS slice (n={n_post_cutoff}, honest-disclosure: small N, limited power)\n{'=' * 78}")
    oos4 = oos_slice_stats(pre['dates'], pre['hit4'], BASELINE_4, DISCOVERY_CUTOFF_DATE, label="4-bet OOS")
    oos5 = oos_slice_stats(pre['dates'], pre['hit5'], BASELINE_5, DISCOVERY_CUTOFF_DATE, label="5-bet OOS")
    oosl = oos_slice_stats(pre['dates'], pre['hit_live'], BASELINE_5, DISCOVERY_CUTOFF_DATE, label="LIVE OOS")
    pr(oos4); pr(oos5); pr(oosl)
    results['oos'] = {'bet4': oos4, 'bet5': oos5, 'live': oosl}

    print(f"\n{'=' * 78}\n  Permutation Test — Binomial MC null (L96-safe), 1500p, B={N_PERM}\n{'=' * 78}")
    real4_rate = edge_stats(pre['hit4'], 1500, BASELINE_4)['rate']
    real5_rate = edge_stats(pre['hit5'], 1500, BASELINE_5)['rate']
    n1500 = len(pre['hit4'][-1500:])

    null4 = binomial_mc_null(n1500, BASELINE_4, N_PERM, SEED)
    null5 = binomial_mc_null(n1500, BASELINE_5, N_PERM + 1, SEED + 1)

    perm4 = permutation_summary(real4_rate, null4, alternative="greater", seed=SEED, family_label="BIG_LOTTO_4bet_P1_DevComp")
    perm5 = permutation_summary(real5_rate, null5, alternative="greater", seed=SEED + 1, family_label="BIG_LOTTO_5bet_P1_DevComp_Sum")
    print(f"  4-bet: observed_rate={real4_rate:.4f}  null_mean={perm4['null_mean']:.4f}  "
          f"empirical_p={perm4['empirical_p_value']:.4f}")
    print(f"  5-bet: observed_rate={real5_rate:.4f}  null_mean={perm5['null_mean']:.4f}  "
          f"empirical_p={perm5['empirical_p_value']:.4f}")
    results['permutation'] = {'bet4': perm4, 'bet5': perm5}

    print(f"\n{'=' * 78}\n  McNemar (1500p)\n{'=' * 78}")
    mc_5v4 = mcnemar(pre['hit5'], pre['hit4'], 1500, label="5-bet vs 4-bet (bet5 marginal value)")
    mc_4vlive = mcnemar(pre['hit4'], pre['hit_live'], 1500, label="4-bet vs LIVE default")
    mc_5vlive = mcnemar(pre['hit5'], pre['hit_live'], 1500, label="5-bet vs LIVE default")
    for mc in (mc_5v4, mc_4vlive, mc_5vlive):
        print(f"  {mc['label']:<38s} chi2={mc['chi2']:.2f}  p={mc['p']:.4f}  "
              f"(a_wins={mc['a_wins']}, b_wins={mc['b_wins']})")
    results['mcnemar'] = {'5v4': mc_5v4, '4vlive': mc_4vlive, '5vlive': mc_5vlive}

    print(f"\n{'=' * 78}\n  Sharpe Ratio (rolling window=300, step=150)\n{'=' * 78}")
    sh4, n4 = sharpe_ratio(pre['hit4'], 1500, BASELINE_4)
    sh5, n5 = sharpe_ratio(pre['hit5'], 1500, BASELINE_5)
    shl, nl = sharpe_ratio(pre['hit_live'], 1500, BASELINE_5)
    print(f"  4-bet Sharpe: {sh4:.3f}  (n_windows={n4})" if sh4 is not None else "  4-bet Sharpe: N/A")
    print(f"  5-bet Sharpe: {sh5:.3f}  (n_windows={n5})" if sh5 is not None else "  5-bet Sharpe: N/A")
    print(f"  LIVE Sharpe:  {shl:.3f}  (n_windows={nl})" if shl is not None else "  LIVE Sharpe: N/A")
    results['sharpe'] = {'bet4': sh4, 'bet5': sh5, 'live': shl}

    print(f"\n{'=' * 78}\n  Verdict (per lottery_api/CLAUDE.md 驗證標準)\n{'=' * 78}")
    for name, bet_key, perm in [("4-bet P1+DevComp", 'bet4', perm4),
                                 ("5-bet P1+DevComp+Sum", 'bet5', perm5)]:
        edges = [results['windows'][w][bet_key]['edge_pct'] for w in WINDOWS]
        three_window_pass = all(e > 0 for e in edges)
        oos_r = results['oos'][bet_key]
        oos_pass = oos_r is not None and oos_r['edge_pct'] > 0
        perm_pass = perm['empirical_p_value'] < 0.05
        sharpe_val = results['sharpe'][bet_key]
        sharpe_pass = sharpe_val is not None and sharpe_val > 0
        overall = three_window_pass and perm_pass and oos_pass and sharpe_pass

        oos_str = 'N/A' if oos_r is None else f"{oos_r['edge_pct']:+.2f}%"
        sharpe_str = 'N/A' if sharpe_val is None else f"{sharpe_val:.3f}"

        print(f"\n  {name}:")
        print(f"    Three-window all positive : {three_window_pass}  ({', '.join(f'{e:+.2f}%' for e in edges)})")
        print(f"    Permutation p<0.05        : {perm_pass}  (p={perm['empirical_p_value']:.4f})")
        print(f"    Post-cutoff OOS edge > 0  : {oos_pass}  ({oos_str})")
        print(f"    Sharpe > 0                : {sharpe_pass}  ({sharpe_str})")
        print(f"    ==> {'PASS — eligible for redeployment' if overall else 'FAIL — must archive to rejected/'}")

    results['meta'] = {
        'seed': SEED,
        'snapshot_db': SNAPSHOT_DB,
        'canonical_draws': len(draws),
        'latest_draw': draws[-1]['draw'],
        'latest_date': draws[-1]['date'],
        'discovery_cutoff_date': DISCOVERY_CUTOFF_DATE,
        'n_post_cutoff_draws': n_post_cutoff,
        'baseline_4bet': BASELINE_4,
        'baseline_5bet': BASELINE_5,
        'elapsed_sec': time.time() - t0,
    }

    out_path = os.path.join(project_root, 'outputs', 'research', 'p1_family_revalidation_20260724.json')
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"\nFull results written to: {out_path}")
    print(f"Elapsed: {time.time() - t0:.1f}s")


if __name__ == "__main__":
    main()
