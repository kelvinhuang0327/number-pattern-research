#!/usr/bin/env python3
"""CLEC diagnostic script
Outputs CSV with entropy metrics and collapse flags; runs per-strategy McNemar and permutation tests.
Usage: python3 tools/cross_lottery_clec_diag.py --window 150 --threshold 0.85 --delta 0.05 --seed 42 --lookback 500
"""
import argparse, sqlite3, json, os, math, random
from collections import Counter, defaultdict
from datetime import datetime
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import csv
import importlib.util

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
LOTTERY_TYPES_PATH = os.path.join(PROJECT_ROOT, 'lottery_api', 'data', 'lottery_types.json')

# Helper: load lottery types
with open(LOTTERY_TYPES_PATH, 'r', encoding='utf-8') as f:
    LOTTERY_TYPES = json.load(f)


def parse_numbers(text):
    # numbers stored as JSON array or comma-separated
    try:
        return json.loads(text)
    except Exception:
        return [int(x) for x in text.split(',') if x.strip()]


def load_draws(lottery_set=None):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    q = "SELECT draw, date, lottery_type, numbers FROM draws"
    if lottery_set:
        ph = ','.join('?' for _ in lottery_set)
        q += f" WHERE lottery_type IN ({ph})"
        cur.execute(q, tuple(lottery_set))
    else:
        cur.execute(q)
    rows = cur.fetchall()
    conn.close()
    draws = defaultdict(list)
    for draw, date, ltype, numbers in rows:
        # tolerant date parsing: DB uses formats like YYYY/MM/DD
        try:
            dt = datetime.fromisoformat(date)
        except Exception:
            try:
                dt = datetime.strptime(date, '%Y/%m/%d')
            except Exception:
                try:
                    dt = datetime.strptime(date, '%Y-%m-%d')
                except Exception:
                    # fallback: parse date part only
                    dt = datetime.fromtimestamp(0)
        nums = parse_numbers(numbers)
        draws[ltype].append({'draw': draw, 'date': dt, 'numbers': nums})
    # sort by date asc
    for k in draws:
        draws[k].sort(key=lambda x: (x['date'], int(x['draw'])))
    return draws


def shannon_entropy(freq_counts, pool_size):
    total = sum(freq_counts)
    if total == 0:
        return 0.0
    ent = 0.0
    for c in freq_counts:
        p = c / total
        if p > 0:
            ent -= p * math.log(p, 2)
    # normalize by max entropy log2(pool_size)
    max_ent = math.log(pool_size, 2)
    return ent / max_ent if max_ent > 0 else ent


def compute_metrics(draws, windows=[30,150,500], lookback=500):
    # builds timeline union of dates where any draw exists
    all_dates = set()
    for l, dl in draws.items():
        for d in dl[-lookback:]:
            all_dates.add(d['date'])
    timeline = sorted(all_dates)
    # For each date and lottery, compute metrics using prior w draws (dates < t)
    records = []
    # Precompute per-lottery cumulative lists
    by_l = {l: dl for l, dl in draws.items()}
    for tdate in timeline:
        ent_by_w = {}
        topk_by_w = {}
        for ltype, dl in by_l.items():
            # find index of last draw with date < tdate
            prior = [d for d in dl if d['date'] < tdate]
            if not prior:
                continue
            ent_by_w[ltype] = {}
            topk_by_w[ltype] = {}
            for w in windows:
                hist = prior[-w:] if len(prior) >= w else prior
                pool_min = LOTTERY_TYPES[ltype]['minNumber']
                pool_max = LOTTERY_TYPES[ltype]['maxNumber']
                pool = list(range(pool_min, pool_max+1))
                counts = [0] * len(pool)
                cnt_map = Counter()
                for d in hist:
                    for n in d['numbers']:
                        cnt_map[n] += 1
                counts = [cnt_map.get(n, 0) for n in pool]
                ent = shannon_entropy(counts, len(pool))
                ent_by_w[ltype][w] = ent
                # top-10 by frequency
                topk = [n for n, _ in cnt_map.most_common(10)]
                topk_by_w[ltype][w] = topk
        # now for lotteries that have draws exactly on tdate (we will output for those draws)
        for ltype, dl in by_l.items():
            # check if there is a draw on tdate for this lottery
            draws_on_t = [d for d in dl if d['date'] == tdate]
            if not draws_on_t:
                continue
            drow = draws_on_t[0]
            for w in windows:
                if ltype not in ent_by_w or any(l not in ent_by_w for l in ent_by_w):
                    # ensure other lotteries computed
                    pass
                entropy = ent_by_w.get(ltype, {}).get(w, None)
                if entropy is None:
                    continue
                # mean entropy of other lotteries
                others = [ent_by_w[ol].get(w) for ol in ent_by_w if ol != ltype and w in ent_by_w[ol]]
                mean_others = float(np.mean([x for x in others if x is not None])) if others else None
                cross_entropy_ratio = entropy / mean_others if mean_others and mean_others > 0 else None
                # cross_sync_index: average Jaccard between top-10 sets
                top_l = set(topk_by_w.get(ltype, {}).get(w, []))
                jaccs = []
                for ol in topk_by_w:
                    if ol == ltype: continue
                    top_ol = set(topk_by_w[ol].get(w, []))
                    if not top_l and not top_ol:
                        j = 0.0
                    else:
                        j = len(top_l & top_ol) / len(top_l | top_ol) if (top_l | top_ol) else 0.0
                    jaccs.append(j)
                cross_sync = float(np.mean(jaccs)) if jaccs else None
                # entropy_gradient: entropy(t) - entropy(t_prev)
                # compute previous entropy using prior date one step earlier (tdate_prev = previous date in timeline)
                prev_date_idx = timeline.index(tdate) - 1
                ent_prev = None
                if prev_date_idx >= 0:
                    prev_date = timeline[prev_date_idx]
                    ent_prev = None
                    # find ent_prev for ltype on prev_date if available
                    # recompute quickly: prior to prev_date
                    prior_prev = [d for d in dl if d['date'] < prev_date]
                    if prior_prev:
                        hist_prev = prior_prev[-w:] if len(prior_prev) >= w else prior_prev
                        cnt_map_prev = Counter()
                        for d in hist_prev:
                            for n in d['numbers']:
                                cnt_map_prev[n] += 1
                        counts_prev = [cnt_map_prev.get(n, 0) for n in range(LOTTERY_TYPES[ltype]['minNumber'], LOTTERY_TYPES[ltype]['maxNumber']+1)]
                        ent_prev = shannon_entropy(counts_prev, len(counts_prev))
                entropy_gradient = entropy - ent_prev if ent_prev is not None else None
                records.append({
                    'draw_index': int(drow['draw']),
                    'draw_date': drow['date'].isoformat(),
                    'lottery_type': ltype,
                    'window': w,
                    'entropy': entropy,
                    'cross_entropy_ratio': cross_entropy_ratio,
                    'cross_sync_index': cross_sync,
                    'entropy_gradient': entropy_gradient,
                })
    return records


def flag_collapses(records, threshold=0.85, delta=0.05):
    # records is list dicts; produce collapse_flag where ratio < threshold and entropy_gradient < -delta
    flagged = {}
    for r in records:
        key = (r['draw_index'], r['lottery_type'], r['window'])
        flag = False
        if r['cross_entropy_ratio'] is not None and r['entropy_gradient'] is not None:
            if r['cross_entropy_ratio'] < threshold and r['entropy_gradient'] < -delta:
                flag = True
        flagged[key] = flag
    return flagged


def save_csv(records, flagged, out_csv):
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['draw_index','draw_date','lottery_type','window','entropy','cross_entropy_ratio','cross_sync_index','entropy_gradient','collapse_flag'])
        for r in records:
            key = (r['draw_index'], r['lottery_type'], r['window'])
            w.writerow([r['draw_index'], r['draw_date'], r['lottery_type'], r['window'], r['entropy'] if r['entropy'] is not None else '', r['cross_entropy_ratio'] if r['cross_entropy_ratio'] is not None else '', r['cross_sync_index'] if r['cross_sync_index'] is not None else '', r['entropy_gradient'] if r['entropy_gradient'] is not None else '', int(flagged.get(key, False))])


def import_predictor(module_path, func_name='predict'):
    # load module from path and return predict function
    spec = importlib.util.spec_from_file_location('modtmp', module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return getattr(mod, func_name)


def evaluate_strategies(strategies, draws, flagged_map, test_window=500, seed=42):
    random.seed(seed); np.random.seed(seed)
    results = {}
    # Build list of draw dates per lottery (sorted)
    draws_by_l = draws
    for strat in strategies:
        sid = strat['id']
        module = strat.get('script')
        ltype = strat['lottery_type']
        try:
            predict = import_predictor(os.path.join(PROJECT_ROOT, module))
        except Exception as e:
            print(f"Skipping {sid}: cannot import {module}: {e}")
            continue
        # prepare draws list and test draws
        dl = draws_by_l.get(ltype, [])
        if not dl:
            print(f"No draws for {ltype}")
            continue
        # use last test_window draws as targets
        targets = dl[-test_window:]
        unfiltered = []
        filtered = []
        for tgt in targets:
            # build history prior to this draw
            hist = [d for d in dl if d['date'] < tgt['date']]
            # call predict(hist)
            try:
                bets = predict(hist)
            except Exception as e:
                print(f"Predict error for {sid} at draw {tgt['draw']}: {e}")
                bets = []
            # compute hit (m3 or more)
            pick_count = LOTTERY_TYPES[ltype]['pickCount']
            hit_thresh = 3 if pick_count >= 5 else 1
            actual = set(tgt['numbers'])
            hit = 0
            for bet in bets:
                if len(set(bet) & actual) >= hit_thresh:
                    hit = 1; break
            # filtered: check collapse flag for window 150 (primary) — key uses draw_index, lottery_type, window
            key = (int(tgt['draw']), ltype, 150)
            is_flag = flagged_map.get(key, False)
            if is_flag:
                fhit = 0
            else:
                fhit = hit
            unfiltered.append(hit)
            filtered.append(fhit)
        # compute McNemar
        b = sum(1 for u,f in zip(unfiltered, filtered) if u==1 and f==0)
        c = sum(1 for u,f in zip(unfiltered, filtered) if u==0 and f==1)
        n = len(unfiltered)
        mcn_p = 1.0
        if (b + c) > 0:
            # continuity correction
            stat = (abs(b - c) - 1)**2 / (b + c)
            from math import exp
            # chi-square with 1 df p-value
            import scipy.stats as ss
            mcn_p = 1 - ss.chi2.cdf(stat, df=1)
        # compute effect sizes: difference in proportions and Cohen's d
        p1 = sum(unfiltered)/n
        p2 = sum(filtered)/n
        diff = (p2 - p1) * 100  # in percentage points
        # pooled std
        denom = math.sqrt(((p1*(1-p1) + p2*(1-p2)) / 2)) if n>0 else 0
        cohen_d = (p2 - p1) / denom if denom > 0 else 0.0
        # permutation test: shuffle collapse labels across draws 10000 times
        # here we treat collapse label array as original flags for targets
        orig_flags = [flagged_map.get((int(t['draw']), ltype, 150), False) for t in targets]
        observed_edge_diff = (sum(filtered)/n - sum(unfiltered)/n) * 100
        perm_diffs = []
        rng = np.random.RandomState(seed)
        K = 10000
        if n > 0:
            for _ in range(K):
                perm = rng.permutation(orig_flags)
                # recompute filtered hits
                f_hits = [u if not pf else 0 for u,pf in zip(unfiltered, perm)]
                perm_diffs.append((sum(f_hits)/n - sum(unfiltered)/n) * 100)
            perm_p = (sum(1 for d in perm_diffs if abs(d) >= abs(observed_edge_diff)) + 1) / (K + 1)
        else:
            perm_p = 1.0
        results[sid] = {
            'sample_size': n,
            'edge_pct_unfiltered': float(p1*100),
            'edge_pct_filtered': float(p2*100),
            'edge_diff_pct': float(diff),
            'McNemar_p': float(mcn_p),
            'perm_p': float(perm_p),
            'cohen_d': float(cohen_d),
            'b': int(b), 'c': int(c)
        }
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--window', type=int, default=150)
    parser.add_argument('--threshold', type=float, default=0.85)
    parser.add_argument('--delta', type=float, default=0.05)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--lookback', type=int, default=500)
    parser.add_argument('--out_csv', type=str, default='research/clec_diag.csv')
    args = parser.parse_args()
    random.seed(args.seed); np.random.seed(args.seed)

    lotteries = ['DAILY_539','POWER_LOTTO','BIG_LOTTO']
    draws = load_draws(lottery_set=lotteries)
    records = compute_metrics(draws, windows=[30, args.window, 500], lookback=args.lookback)
    flagged = flag_collapses(records, threshold=args.threshold, delta=args.delta)
    save_csv(records, flagged, args.out_csv)

    # select representative strategies (hard-coded selection mapping)
    strategies = [
        {'id':'DAILY_539/5bet_fourier4_cold','lottery_type':'DAILY_539','script':'tools/predict_539_5bet_f4cold.py'},
        {'id':'DAILY_539/markov_cold','lottery_type':'DAILY_539','script':'tools/predict_539_markov_cold.py'},
        {'id':'POWER_LOTTO/5bet_orthogonal','lottery_type':'POWER_LOTTO','script':'tools/predict_power_orthogonal_5bet.py'},
        {'id':'POWER_LOTTO/precision_3bet','lottery_type':'POWER_LOTTO','script':'tools/predict_power_precision_3bet.py'},
        {'id':'BIG_LOTTO/6bet_optimized','lottery_type':'BIG_LOTTO','script':'tools/predict_biglotto_6bets_optimized.py'},
        {'id':'BIG_LOTTO/7bet_cluster','lottery_type':'BIG_LOTTO','script':'tools/predict_biglotto_7bets_cluster.py'},
    ]

    results = evaluate_strategies(strategies, draws, flagged, test_window=500, seed=args.seed)
    # write JSON results
    os.makedirs('research', exist_ok=True)
    with open('research/clec_validation_results_2026-04-30.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)

    # plots: entropy time series (window=args.window) per lottery
    import pandas as pd
    df = pd.read_csv(args.out_csv)
    # select window rows
    dfw = df[df['window'] == args.window]
    dfw['draw_date'] = pd.to_datetime(dfw['draw_date'])
    for l in dfw['lottery_type'].unique():
        sub = dfw[dfw['lottery_type']==l]
        plt.figure(figsize=(10,3))
        plt.plot(sub['draw_date'], sub['entropy'], label=f'{l} entropy')
        plt.title(f'Entropy time series {l} w={args.window}')
        plt.xlabel('date'); plt.ylabel('normalized entropy')
        plt.tight_layout()
        plt.savefig(f'research/entropy_{l}_{args.window}.png')
        plt.close()
    # histogram of cross_entropy_ratio
    plt.figure(figsize=(6,4))
    vals = dfw['cross_entropy_ratio'].dropna()
    plt.hist(vals, bins=50)
    plt.title('cross_entropy_ratio histogram')
    plt.savefig('research/cross_entropy_ratio_hist.png')
    plt.close()

    # before/after edge distribution boxplots using results
    # build simple boxplot of per-strategy unfiltered vs filtered edge_pct
    unfiltered = [v['edge_pct_unfiltered'] for v in results.values()]
    filtered = [v['edge_pct_filtered'] for v in results.values()]
    plt.figure(figsize=(6,4))
    plt.boxplot([unfiltered, filtered], labels=['unfiltered','filtered'])
    plt.title('Edge% distribution before/after CLEC')
    plt.savefig('research/edge_boxplots.png')
    plt.close()

    # zip images
    import zipfile
    with zipfile.ZipFile('research/clec_plots_2026-04-30.zip', 'w') as zf:
        for fn in [p for p in os.listdir('research') if p.endswith('.png')]:
            zf.write(os.path.join('research', fn), arcname=fn)

    print('Done. Outputs: research/clec_diag.csv, research/clec_validation_results_2026-04-30.json, research/clec_plots_2026-04-30.zip')

if __name__ == '__main__':
    main()
