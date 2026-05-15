#!/usr/bin/env python3
"""Deep research: number distribution bias and structure filtering.
Produces JSON reports and a strategy summary (lightweight, self-contained).
"""
import sqlite3, json, random, math, os
from collections import Counter, defaultdict

DB = 'lottery_api/data/lottery_v2.db'
OUT_DIR = 'outputs'
random.seed(42)

def parse_numbers(s):
    try:
        return list(map(int, s.strip().strip('[]').split(','))) if s else []
    except:
        return []

def fetch_draws(conn, game):
    cur = conn.cursor()
    cur.execute("SELECT draw, date, numbers FROM draws WHERE lottery_type=? ORDER BY date ASC", (game,))
    rows = cur.fetchall()
    parsed = [(r[0], r[1], parse_numbers(r[2])) for r in rows]
    return parsed

def sliding_freq_test(draws, long_w=1000, short_w=50, low_thresh=0.8):
    n_draws = len(draws)
    if n_draws < long_w + 2:
        return None
    domain = sorted({n for _,_,nums in draws for n in nums})
    trials = {'low':{'trials':0,'hits':0}, 'notlow':{'trials':0,'hits':0}}
    for i in range(long_w, n_draws-1):
        long_window = draws[i-long_w:i]
        short_window = draws[i-short_w:i]
        long_counts = Counter(n for _,_,nums in long_window for n in nums)
        short_counts = Counter(n for _,_,nums in short_window for n in nums)
        for num in domain:
            c_long = long_counts.get(num,0)
            c_short = short_counts.get(num,0)
            freq_long = c_long / long_w if long_w>0 else 0
            freq_short = c_short / short_w if short_w>0 else 0
            ratio = (freq_short+1e-9)/(freq_long+1e-9)
            is_low = ratio < low_thresh
            trials['low' if is_low else 'notlow']['trials'] += 1
            next_draw_nums = draws[i+1][2]
            if num in next_draw_nums:
                trials['low' if is_low else 'notlow']['hits'] += 1
    a = trials['low']
    b = trials['notlow']
    if a['trials']<100 or b['trials']<100:
        return {'trials':trials,'z':None,'p':None}
    p1 = a['hits']/a['trials']
    p2 = b['hits']/b['trials']
    pooled = (a['hits']+b['hits'])/(a['trials']+b['trials'])
    se = math.sqrt(pooled*(1-pooled)*(1/a['trials']+1/b['trials']))
    z = (p1-p2)/se if se>0 else 0
    p = math.erfc(abs(z)/math.sqrt(2))
    return {'trials':trials,'p':p,'z':z,'p1':p1,'p2':p2}

def compute_freq_ratios(draws, long_w=1000, short_w=50):
    n_draws = len(draws)
    domain = sorted({n for _,_,nums in draws for n in nums})
    long_window = draws[-long_w:] if n_draws>=long_w else draws
    short_window = draws[-short_w:] if n_draws>=short_w else draws
    long_counts = Counter(n for _,_,nums in long_window for n in nums)
    short_counts = Counter(n for _,_,nums in short_window for n in nums)
    ratios = {}
    for num in domain:
        freq_long = long_counts.get(num,0)/max(1,len(long_window))
        freq_short = short_counts.get(num,0)/max(1,len(short_window))
        ratio = (freq_short+1e-9)/(freq_long+1e-9)
        ratios[num] = {'long_count':long_counts.get(num,0),'short_count':short_counts.get(num,0),'ratio':ratio}
    return ratios

def monte_carlo_strategy(draws, pick_numbers, iters=1000):
    rng = random.Random(42)
    hits = []
    n = len(draws)
    for _ in range(iters):
        sample = [draws[rng.randrange(n)][2] for __ in range(len(draws))]
        tot = 0
        hitc = 0
        for sd in sample:
            tot += 1
            if any(num in sd for num in pick_numbers):
                hitc += 1
        hits.append(hitc/tot if tot>0 else 0)
    mean = sum(hits)/len(hits)
    std = (sum((x-mean)**2 for x in hits)/len(hits))**0.5
    hits.sort()
    p5 = hits[int(0.05*len(hits))]
    p95 = hits[int(0.95*len(hits))]
    return {'mean':mean,'std':std,'p5':p5,'p95':p95}

def structure_features(draws):
    feats = []
    for _,_,nums in draws:
        if not nums: continue
        odd = sum(1 for n in nums if n%2==1)
        even = len(nums)-odd
        span = max(nums)-min(nums)
        consec = 0
        s = set(nums)
        for n in nums:
            if n+1 in s:
                consec += 1
        feats.append({'odd_even':f"{odd}-{even}",'span':span,'consec':consec})
    return feats

def perm_p_for_structure(draws, structure_key, n_iters=200):
    rng = random.Random(42)
    observed = sum(1 for _,_,nums in draws if structure_key(nums))
    counts = 0
    for _ in range(n_iters):
        sim_hits = 0
        domain = sorted({n for _,_,nums in draws for n in nums})
        for _,_,nums in draws:
            k = len(nums)
            sample = rng.sample(domain, k)
            if structure_key(sample): sim_hits += 1
        if sim_hits >= observed:
            counts += 1
    return counts / n_iters

def backtest_structure_filter(draws, allow_structure_fn, window=300):
    recent = draws[-window:] if len(draws)>=window else draws
    domain = sorted({n for _,_,nums in draws for n in nums})
    k = len(recent[0][2]) if recent else 0
    rng = random.Random(42)
    baseline_hits = 0
    filtered_hits = 0
    for _,_,nums in recent:
        rand_pick = rng.sample(domain, k)
        if any(x in nums for x in rand_pick): baseline_hits += 1
        attempts=0
        pick=None
        while attempts<500:
            p = rng.sample(domain, k)
            if allow_structure_fn(p): pick=p; break
            attempts+=1
        if not pick: pick = rng.sample(domain,k)
        if any(x in nums for x in pick): filtered_hits +=1
    return {'baseline_hit_rate':baseline_hits/len(recent) if recent else 0,'filtered_hit_rate':filtered_hits/len(recent) if recent else 0}

def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB)
    games = ['POWER_LOTTO','BIG_LOTTO','DAILY_539']
    strategy_summary = []
    freq_report = {}
    struct_report = {}
    for game in games:
        draws = fetch_draws(conn, game)
        if not draws:
            continue
        ratios = compute_freq_ratios(draws,1000,50)
        sres = sliding_freq_test(draws,1000,50,low_thresh=0.8)
        freq_report[game] = {'ratios': ratios, 'sliding_test': sres}
        sorted_nums = sorted(ratios.items(), key=lambda x: x[1]['ratio'])
        low3 = [n for n,_ in sorted_nums[:3]]
        low5 = [n for n,_ in sorted_nums[:5]]
        low6 = [n for n,_ in sorted_nums[:6]]
        mc3 = monte_carlo_strategy(draws, low3, iters=1000)
        mc5 = monte_carlo_strategy(draws, low5, iters=1000)
        mc6 = monte_carlo_strategy(draws, low6, iters=1000)
        strategy_summary.append({'strategy_name':f'freq_rev_top3_{game.lower()}','game':game,'edge_150':round(mc3['mean'],4),'mc':mc3})
        strategy_summary.append({'strategy_name':f'freq_rev_top5_{game.lower()}','game':game,'edge_150':round(mc5['mean'],4),'mc':mc5})
        strategy_summary.append({'strategy_name':f'freq_rev_top6_{game.lower()}','game':game,'edge_150':round(mc6['mean'],4),'mc':mc6})
        feats = structure_features(draws[-1000:])
        odd_even_counts = Counter(f['odd_even'] for f in feats)
        span_counts = Counter((f['span']//5)*5 for f in feats)
        consec_counts = Counter(min(f['consec'],3) for f in feats)
        struct_report[game] = {'odd_even':odd_even_counts,'span_bins':span_counts,'consec':consec_counts}
        candidates = list(odd_even_counts.keys())
        allowed = []
        for c in candidates:
            def key_fn(nums,cc=c): return f"{sum(1 for n in nums if n%2==1)}-{len(nums)-sum(1 for n in nums if n%2==1)}"==cc
            p = perm_p_for_structure(draws[-1000:], key_fn, n_iters=200)
            struct_report[game].setdefault('perm_p', {})[c]=p
            if p <= 0.15:
                allowed.append(c)
        def allow_fn(nums, allowed_set=set(allowed)):
            return f"{sum(1 for n in nums if n%2==1)}-{len(nums)-sum(1 for n in nums if n%2==1)}" in allowed_set
        bt = backtest_structure_filter(draws, allow_fn, window=300)
        struct_report[game]['backtest_300'] = bt
        strategy_summary.append({'strategy_name':f'struct_filter_odd_even_{game.lower()}','game':game,'edge_150':round(bt['filtered_hit_rate']-bt['baseline_hit_rate'],4),'mc':None})
    with open(os.path.join(OUT_DIR,'frequency_reversion_report.json'),'w') as f:
        json.dump(freq_report,f,indent=2)
    with open(os.path.join(OUT_DIR,'structure_filter_rules.json'),'w') as f:
        json.dump(struct_report,f,indent=2)
    with open(os.path.join(OUT_DIR,'strategy_summary.json'),'w') as f:
        json.dump(strategy_summary,f,indent=2)
    print('WROTE outputs to',OUT_DIR)

if __name__=='__main__':
    main()

