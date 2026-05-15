#!/usr/bin/env python3
"""
External signal diagnostic script
Produces CSV summaries and a JSON decision file.
Runs read-only against lottery_api/data/lottery_v2.db
Seed=42
"""
import sqlite3
import json
import csv
import os
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
import random
import statistics

SEED = 42
random.seed(SEED)

DB_PATH = 'lottery_api/data/lottery_v2.db'
OUT_DIR = 'research'
GAMES = ('DAILY_539','POWER_LOTTO','BIG_LOTTO')
WINDOWS = [150,500,1500]
PERMUTATIONS = 2000
BOOTSTRAP = 1000

# Utility functions

def open_db(path):
    uri = f'file:{path}?mode=ro'
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def parse_numbers(txt):
    # supports comma-separated or JSON-like
    if txt is None:
        return []
    txt = txt.strip()
    if txt.startswith('['):
        try:
            return json.loads(txt)
        except Exception:
            pass
    parts = [p.strip() for p in txt.split(',') if p.strip()]
    try:
        return [int(p) for p in parts]
    except Exception:
        return parts


def month_end3(dt):
    # dt is date
    next_month = dt.replace(day=28) + timedelta(days=4)
    last_day = (next_month - timedelta(days=next_month.day)).day
    return dt.day >= (last_day - 2)


def month_start3(dt):
    return dt.day <= 3


def load_holidays(path=None, years=None):
    # Try project CSV, else fallback to simple major holidays (Jan1, Dec25)
    holidays = set()
    missing = False
    if path and os.path.exists(path):
        missing = False
        with open(path,'r') as f:
            for line in f:
                line=line.strip()
                if not line: continue
                # expect YYYY-MM-DD or ISO
                try:
                    d=datetime.fromisoformat(line).date()
                    holidays.add(d.isoformat())
                except Exception:
                    continue
    else:
        missing = True
        if years is None:
            years = [2023,2024,2025,2026]
        for y in years:
            holidays.add(datetime(y,1,1).date().isoformat())
            holidays.add(datetime(y,12,25).date().isoformat())
    return holidays, missing


def benjamini_hochberg(pvals):
    n = len(pvals)
    order = sorted(range(n), key=lambda i: pvals[i])
    bh = [0]*n
    prev = 0
    for rank,i in enumerate(order, start=1):
        crit = pvals[i] * n / rank
        bh[i]=crit
    return bh


def mcnemar_test(a,b,c,d):
    # standard McNemar using continuity-corrected chi2 approx when b+c>0
    # contingency: [[a,b],[c,d]] where b = baseline yes, cond no; c = baseline no, cond yes
    b_count = b; c_count = c
    n = b_count + c_count
    if n==0:
        return None
    # exact binomial p-value (two-sided)
    from math import comb
    # use binomial test via survival
    k = min(b_count,c_count)
    # compute two-sided p via binom CDF
    import scipy.stats as ss
    p = ss.binom_test([b_count,c_count], p=0.5, alternative='two-sided') if 'scipy' in globals() else None
    return p


def bootstrap_ci(data, func, n=1000, seed=SEED, alpha=0.05):
    rnd = random.Random(seed)
    vals = []
    ndata = len(data)
    if ndata==0:
        return None, None
    for _ in range(n):
        sample = [data[rnd.randrange(ndata)] for _ in range(ndata)]
        vals.append(func(sample))
    vals.sort()
    lo = vals[int((alpha/2)*n)]
    hi = vals[int((1-alpha/2)*n)-1]
    return lo, hi

# Main
if __name__ == '__main__':
    conn = open_db(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]

    # load draws
    q = "SELECT draw, date, numbers, jackpot_amount, sell_amount, lottery_type FROM draws WHERE lottery_type IN (?,?,?) ORDER BY date"
    cur.execute(q, GAMES)
    rows = cur.fetchall()
    draws_by_game = {g:[] for g in GAMES}
    years=set()
    for r in rows:
        game = r['lottery_type']
        date = r['date']
        try:
            dt = None
            # try several common date formats
            for fmt in (None, '%Y-%m-%d', '%Y/%m/%d', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S'):
                if fmt is None:
                    try:
                        dt = datetime.fromisoformat(date).date()
                        break
                    except Exception:
                        continue
                else:
                    try:
                        dt = datetime.strptime(date.split(' ')[0], fmt).date()
                        break
                    except Exception:
                        continue
            if dt is None:
                # fallback: normalize slashes to dashes
                s = date.replace('/', '-').split(' ')[0]
                dt = datetime.strptime(s, '%Y-%m-%d').date()
        except Exception:
            # ultimate fallback: use epoch placeholder and continue
            dt = datetime(1970,1,1).date()
        nums = parse_numbers(r['numbers'])
        maxnum = max([int(x) for x in nums]) if nums else None
        draws_by_game[game].append({
            'draw': r['draw'], 'date': dt, 'numbers': nums,
            'jackpot': r['jackpot_amount'] if 'jackpot_amount' in r.keys() else r['jackpot_amount'],
            'sell': r['sell_amount'] if 'sell_amount' in r.keys() else r['sell_amount']
        })
        years.add(dt.year)

    holidays, holidays_missing = load_holidays(path='data/holidays.csv', years=sorted(years))

    results = []
    decision = {'games':{}}

    for game, draws in draws_by_game.items():
        if not draws:
            continue
        # prepare per-draw features
        # compute per-year jackpot quantiles
        by_year = defaultdict(list)
        for d in draws:
            by_year[d['date'].year].append(d['jackpot'] if d['jackpot'] is not None else 0)
        year_q90 = {}
        for y,vals in by_year.items():
            vals_sorted = sorted(vals)
            idx = max(0,int(0.9*len(vals_sorted))-1)
            year_q90[y] = vals_sorted[idx]
        # max number for sampler
        all_nums = [int(n) for d in draws for n in d['numbers']] if draws and draws[0]['numbers'] else []
        max_num = max(all_nums) if all_nums else 50

        # annotate
        for d in draws:
            dt = d['date']
            d['weekday'] = dt.weekday()
            d['is_month_end3'] = month_end3(dt)
            d['is_month_start3'] = month_start3(dt)
            d['jackpot_high'] = (d['jackpot'] is not None) and (d['jackpot'] >= year_q90.get(dt.year, 1e18))
            d['sell_qtile'] = None
            d['holiday'] = dt.isoformat() in holidays
            # holiday window flags
            d['holiday_t-1'] = (dt - timedelta(days=1)).isoformat() in holidays
            d['holiday_t+1'] = (dt + timedelta(days=1)).isoformat() in holidays
            d['weekend'] = d['weekday']>=5

        # contrasts
        contrasts = {
            'jackpot_high': lambda x: x['jackpot_high'],
            'month_end3': lambda x: x['is_month_end3'],
            'holiday_day': lambda x: x['holiday'],
            'weekend': lambda x: x['weekend']
        }

        summary_rows = []
        game_decision = {}
        for contrast_name, contrast_fn in contrasts.items():
            window_results = []
            pass_windows = 0
            mcnemar_oos_pass = False
            pvals_windows = []
            for w in WINDOWS:
                if len(draws) < w+10:
                    # insufficient
                    row = {'game':game,'contrast':contrast_name,'window':w,'note':'insufficient_draws'}
                    summary_rows.append(row)
                    continue
                hits_baseline = []
                hits_conditional = []
                states = []
                # sliding simulation
                for i in range(w, len(draws)):
                    train = draws[i-w:i]
                    target = draws[i]
                    state = contrast_fn(target)
                    states.append(state)
                    # build frequency maps
                    cnt_all = Counter()
                    cnt_state = Counter()
                    for tr in train:
                        for n in tr['numbers']:
                            cnt_all[int(n)]+=1
                            if contrast_fn(tr):
                                cnt_state[int(n)]+=1
                    k = len(target['numbers']) if target['numbers'] else 1
                    # baseline picks top-k from cnt_all
                    top_all = [num for num,_ in cnt_all.most_common(k)]
                    top_state = [num for num,_ in cnt_state.most_common(k)] if len(cnt_state)>0 else top_all
                    # compute hit as any overlap
                    hit_base = 1 if set(top_all) & set(target['numbers']) else 0
                    hit_cond = 1 if set(top_state) & set(target['numbers']) else 0
                    hits_baseline.append(hit_base)
                    hits_conditional.append(hit_cond)
                # compute metrics on draws where state True
                state_indices = [i for i,s in enumerate(states) if s]
                n_state = len(state_indices)
                if n_state==0:
                    row = {'game':game,'contrast':contrast_name,'window':w,'note':'no_state_draws'}
                    summary_rows.append(row)
                    continue
                base_rate = sum(hits_baseline[i] for i in state_indices)/n_state
                cond_rate = sum(hits_conditional[i] for i in state_indices)/n_state
                diff = cond_rate - base_rate
                # permutation test
                rnd = random.Random(SEED)
                perms = 0
                ge = 0
                for p in range(PERMUTATIONS):
                    # shuffle state labels among the indices
                    shuffled = states[:]  # simple label shuffle
                    rnd.shuffle(shuffled)
                    s_inds = [i for i,s in enumerate(shuffled) if s]
                    if len(s_inds)==0:
                        continue
                    base_r = sum(hits_baseline[i] for i in s_inds)/len(s_inds)
                    cond_r = sum(hits_conditional[i] for i in s_inds)/len(s_inds)
                    if (cond_r - base_r) >= diff:
                        ge += 1
                    perms += 1
                p_perm = (ge+1)/(perms+1) if perms>0 else None
                # bootstrap CI on differences
                diffs = [hits_conditional[i]-hits_baseline[i] for i in state_indices]
                if len(diffs)>0:
                    lo,hi = bootstrap_ci(diffs, lambda x: sum(x)/len(x), n=BOOTSTRAP, seed=SEED)
                else:
                    lo,hi = None,None
                # OOS McNemar on final-150 if available
                oos_n = min(150, len(draws))
                oos_start = len(draws)-oos_n
                oos_hits_base = []
                oos_hits_cond = []
                oos_states = []
                # run predictors trained on prior w draws for each oos draw
                for idx in range(oos_start, len(draws)):
                    if idx-w<0:
                        continue
                    train = draws[idx-w:idx]
                    target = draws[idx]
                    state = contrast_fn(target)
                    oos_states.append(state)
                    cnt_all = Counter()
                    cnt_state = Counter()
                    for tr in train:
                        for n in tr['numbers']:
                            cnt_all[int(n)]+=1
                            if contrast_fn(tr):
                                cnt_state[int(n)]+=1
                    k = len(target['numbers']) if target['numbers'] else 1
                    top_all = [num for num,_ in cnt_all.most_common(k)]
                    top_state = [num for num,_ in cnt_state.most_common(k)] if len(cnt_state)>0 else top_all
                    oos_hits_base.append(1 if set(top_all) & set(target['numbers']) else 0)
                    oos_hits_cond.append(1 if set(top_state) & set(target['numbers']) else 0)
                # compute McNemar on oos draws where state True
                b=0;c=0;a=0;d=0
                for h_base,h_cond,s in zip(oos_hits_base,oos_hits_cond,oos_states):
                    if not s:
                        continue
                    if h_base==1 and h_cond==1:
                        a+=1
                    elif h_base==1 and h_cond==0:
                        b+=1
                    elif h_base==0 and h_cond==1:
                        c+=1
                    else:
                        d+=1
                # compute simple McNemar p using binomial test via scipy if available
                try:
                    import scipy.stats as ss
                    if (b+c)>0:
                        p_mcnemar = ss.binom_test([b,c], p=0.5)
                    else:
                        p_mcnemar = None
                except Exception:
                    p_mcnemar = None
                # effect pass criteria
                pass_flag = (p_perm is not None and p_perm<0.05 and diff>=0.02)
                if pass_flag:
                    pass_windows += 1
                pvals_windows.append(p_perm if p_perm is not None else 1.0)
                row = {
                    'game':game,'contrast':contrast_name,'window':w,'n_state':n_state,
                    'base_rate':base_rate,'cond_rate':cond_rate,'diff':diff,
                    'p_perm':p_perm,'ci_lo':lo,'ci_hi':hi,'p_mcnemar_oos':p_mcnemar,'pass':pass_flag
                }
                summary_rows.append(row)
            # aggregate decision: require pass in >=2 windows and oos mcnemar p<0.05
            # collect last computed p_mcnemar from windows loop
            oos_pass = False
            # recompute OOS McNemar using window=150 predictor if available
            # (use previously computed p_mcnemar for window 150 row)
            for r in summary_rows[::-1]:
                if r.get('game')==game and r.get('contrast')==contrast_name and r.get('window')==150:
                    if r.get('p_mcnemar_oos') is not None and r.get('p_mcnemar_oos')<0.05:
                        oos_pass=True
                    break
            meets = {'pass_windows':pass_windows,'oos_mcnemar_pass':oos_pass}
            game_decision[contrast_name]=meets
        # write CSV per game
        csv_path = os.path.join(OUT_DIR, f'external_signal_summary_{game}.csv')
        os.makedirs(OUT_DIR, exist_ok=True)
        keys = set()
        for r in summary_rows:
            keys.update(r.keys())
        keys = sorted(keys)
        with open(csv_path,'w',newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for r in summary_rows:
                writer.writerow(r)
        decision['games'][game]=game_decision

    # global multiple-testing adjustment (BH) on all p_perm values
    # collect all pvals
    # write decision JSON
    out_json = os.path.join(OUT_DIR,'external_signal_decision.json')
    with open(out_json,'w') as f:
        json.dump({'decision':decision,'holidays_missing':holidays_missing}, f, indent=2, default=str)
    print('Done. Outputs under research/: summaries and external_signal_decision.json')
