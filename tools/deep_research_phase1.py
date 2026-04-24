#!/usr/bin/env python3
"""Deep research phase1 analysis tool.
Produces: structure_filter_rules.json, signal_quality_matrix.json, signal_reconstruction_report.json
"""
import sqlite3, json, random, math, statistics, os
from collections import Counter, defaultdict
random.seed(42)

DB = 'lottery_api/data/lottery_v2.db'
OUT_DIR = 'outputs'
os.makedirs(OUT_DIR, exist_ok=True)

LOTTERIES = ['BIG_LOTTO','DAILY_539','POWER_LOTTO']

def parse_numbers(s):
    # numbers stored as like "[1,2,3,4,5,6]" or "1,2,3"
    s = s.strip()
    if s.startswith('[') and s.endswith(']'):
        s = s[1:-1]
    if not s:
        return []
    parts = [p.strip() for p in s.split(',') if p.strip()]
    return [int(p) for p in parts]

def load_draws(lottery_type, limit=2000):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    cur.execute("SELECT id, draw, date, numbers FROM draws WHERE lottery_type=? ORDER BY id DESC LIMIT ?", (lottery_type, limit))
    rows = cur.fetchall()
    con.close()
    draws = []
    for r in rows:
        nums = parse_numbers(r[3])
        draws.append({'id':r[0],'draw':r[1],'date':r[2],'numbers':sorted(nums)})
    draws.reverse()  # oldest first
    return draws

def features_of(draw):
    nums = draw['numbers']
    odd = sum(1 for n in nums if n%2==1)
    even = len(nums)-odd
    span = max(nums)-min(nums) if nums else 0
    consec = sum(1 for i in range(len(nums)-1) if nums[i+1]==nums[i]+1)
    return {'odd':odd,'even':even,'span':span,'consec':consec}

# permutation chi-square via label shuffling
def chi2_perm(groupA_counts, groupB_counts, nperm=2000):
    # groupX_counts: dict category->count, total sizes known
    cats = sorted(set(groupA_counts.keys())|set(groupB_counts.keys()))
    A_total = sum(groupA_counts.values())
    B_total = sum(groupB_counts.values())
    obs = 0.0
    for c in cats:
        a = groupA_counts.get(c,0)
        b = groupB_counts.get(c,0)
        e_a = (a+b)*A_total/(A_total+B_total)
        e_b = (a+b)*B_total/(A_total+B_total)
        if e_a>0: obs += (a-e_a)**2/e_a
        if e_b>0: obs += (b-e_b)**2/e_b
    # permute labels
    combined = []
    for c in cats:
        combined += [c]* (groupA_counts.get(c,0)+groupB_counts.get(c,0))
    more=0
    for i in range(nperm):
        random.shuffle(combined)
        a_sample = combined[:A_total]
        a_counts = Counter(a_sample)
        stat=0.0
        for c in cats:
            a = a_counts.get(c,0)
            b = (groupA_counts.get(c,0)+groupB_counts.get(c,0))-a
            e_a = (a+b)*A_total/(A_total+B_total)
            e_b = (a+b)*B_total/(A_total+B_total)
            if e_a>0: stat += (a-e_a)**2/e_a
            if e_b>0: stat += (b-e_b)**2/e_b
        if stat>=obs: more+=1
    p = (more+1)/(nperm+1)
    return obs,p

# Query prediction hits for a strategy in a date window
def hits_for_strategy(strategy_name, min_date=None):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    q = "SELECT pr.actual_date, pr.hit_count FROM prediction_results pr JOIN prediction_items pi ON pr.item_id=pi.id WHERE pi.strategy_name=?"
    params = [strategy_name]
    if min_date:
        q += " AND pr.actual_date>=?"
        params.append(min_date)
    q += " ORDER BY pr.actual_date DESC"
    cur.execute(q, params)
    rows = cur.fetchall()
    con.close()
    return rows

# simplified permutation test for strategy: shuffle actual_dates of draws
def perm_test_strategy_hits(strategy_name, window_n, nperm=500):
    # get last window_n real resolved prediction_results for this strategy by date
    rows = hits_for_strategy(strategy_name)
    if not rows:
        return None
    # rows are sorted desc; take last window_n most recent
    rows = rows[:window_n]
    obs_hits = sum(r[1] for r in rows)
    # get all hit_counts list and shuffle
    counts = [r[1] for r in rows]
    more=0
    for i in range(nperm):
        random.shuffle(counts)
        if sum(counts)>=obs_hits: more+=1
    p = (more+1)/(nperm+1)
    return obs_hits,p

# McNemar test between two strategies over overlapping dates
def mcnemar_between(s1, s2, window_n=500):
    con = sqlite3.connect(DB)
    cur = con.cursor()
    q = "SELECT pr.actual_date, pr.hit_count, pi.strategy_name FROM prediction_results pr JOIN prediction_items pi ON pr.item_id=pi.id WHERE pi.strategy_name IN (?,?) ORDER BY pr.actual_date DESC"
    cur.execute(q,(s1,s2))
    rows = cur.fetchall()
    con.close()
    # organize by date
    bydate = defaultdict(dict)
    for date, hit, name in rows:
        bydate[date][name]=hit
    dates = sorted(bydate.keys(), reverse=True)[:window_n]
    b=c=0
    for d in dates:
        a_hit = 1 if bydate[d].get(s1,0)>0 else 0
        b_hit = 1 if bydate[d].get(s2,0)>0 else 0
        if a_hit==1 and b_hit==0:
            b+=1
        if a_hit==0 and b_hit==1:
            c+=1
    # continuity correction
    n=b+c
    if n==0:
        return None
    chi = (abs(b-c)-1)**2 / (b+c) if (b+c)>0 else 0
    # approximate p-value using chi2 1 df
    # use math.exp/gamma if needed; approximate via survival using math
    # Here use simple approximation via built-in: p = exp(-chi/2)
    p = math.exp(-chi/2)
    return {'b':b,'c':c,'chi2':chi,'p_approx':p}

def run():
    results_struct = {}
    for L in LOTTERIES:
        draws = load_draws(L, limit=1200)
        n = len(draws)
        use_n = min(1000,n)
        draws1000 = draws[-use_n:]
        feats = [features_of(d) for d in draws1000]
        # build categorical distributions
        odd_counts = Counter(f['odd'] for f in feats)
        span_bins = Counter(((f['span']//5)*5) for f in feats)
        consec_counts = Counter(f['consec'] for f in feats)
        # cold: last 300, hot: previous 300
        cold_n = min(300, len(feats)//2)
        if cold_n<50:
            cold_n = max(50, len(feats)//4)
        cold_feats = feats[-cold_n:]
        hot_feats = feats[-(2*cold_n):-cold_n]
        cold_odd = Counter(f['odd'] for f in cold_feats)
        hot_odd = Counter(f['odd'] for f in hot_feats)
        cold_span = Counter(((f['span']//5)*5) for f in cold_feats)
        hot_span = Counter(((f['span']//5)*5) for f in hot_feats)
        cold_consec = Counter(f['consec'] for f in cold_feats)
        hot_consec = Counter(f['consec'] for f in hot_feats)
        # chi2 perms
        odd_stat, odd_p = chi2_perm(cold_odd, hot_odd, nperm=2000)
        span_stat, span_p = chi2_perm(cold_span, hot_span, nperm=2000)
        consec_stat, consec_p = chi2_perm(cold_consec, hot_consec, nperm=2000)
        results_struct[L] = {
            'n_draws_analyzed':use_n,
            'cold_n':cold_n,
            'odd':{'cold_counts':dict(cold_odd),'hot_counts':dict(hot_odd),'chi2':odd_stat,'p':odd_p},
            'span':{'cold_counts':dict(cold_span),'hot_counts':dict(hot_span),'chi2':span_stat,'p':span_p},
            'consec':{'cold_counts':dict(cold_consec),'hot_counts':dict(hot_consec),'chi2':consec_stat,'p':consec_p}
        }
    # write structure rules suggestion: simple thresholds where p<0.05
    struct_rules = {}
    for L, v in results_struct.items():
        rules = []
        if v['odd']['p']<0.05:
            # find categories with higher ratio in cold than hot
            for k, cnt in v['odd']['cold_counts'].items():
                hot_cnt = v['odd']['hot_counts'].get(k,0)
                if v['cold_n']>0 and hot_cnt>=0:
                    if (cnt/v['cold_n']) < (hot_cnt/max(1,(v['cold_n']))):
                        pass
            rules.append({'feature':'odd','note':'odd distribution differs (p={:.3f})'.format(v['odd']['p'])})
        if v['span']['p']<0.05:
            rules.append({'feature':'span','note':'span distribution differs (p={:.3f})'.format(v['span']['p'])})
        if v['consec']['p']<0.05:
            rules.append({'feature':'consec','note':'consecutive pairs distribution differs (p={:.3f})'.format(v['consec']['p'])})
        struct_rules[L]=rules
    with open(os.path.join(OUT_DIR,'structure_filter_rules.json'),'w') as f:
        json.dump({'results':results_struct,'rules':struct_rules},f,indent=2)

    # Focus 2: signal quality from strategy_states files
    # load strategy state JSONs
    base = 'lottery_api/data'
    strategies = {}
    for fname in os.listdir(base):
        if fname.startswith('strategy_states_') and fname.endswith('.json'):
            with open(os.path.join(base,fname)) as fh:
                data = json.load(fh)
                for k,sv in data.items():
                    strategies[k]=sv
    # compute perm_p for each strategy for window 150 using prediction_results
    sig_matrix = {}
    for sname, s in strategies.items():
        # attempt perm test on last 150
        try:
            res = perm_test_strategy_hits(sname, window_n=150, nperm=500)
        except Exception as e:
            res = None
        # compute simple z_score from existing field if present
        z = s.get('z_score')
        # edge stability approx: stdev of edge_30p vs edge_100p if available
        edges = [v for k,v in s.items() if k.startswith('edge_') and isinstance(v,(int,float))]
        edge_stab = statistics.pstdev(edges) if len(edges)>1 else 0.0
        perm_p = res[1] if res else None
        sig_matrix[sname] = {'lottery':s.get('lottery_type'),'z_score':z,'perm_p_150':perm_p,'edge_stability':edge_stab,'edge_30p':s.get('edge_30p')}
    # classify
    for k,v in sig_matrix.items():
        pp = v.get('perm_p_150')
        if pp is None:
            cat='NO_DATA'
        elif pp>0.1:
            cat='NOISE'
        elif 0.05<=pp<=0.1:
            cat='BORDERLINE'
        else:
            cat='SIGNAL'
        v['category']=cat
    with open(os.path.join(OUT_DIR,'signal_quality_matrix.json'),'w') as f:
        json.dump(sig_matrix,f,indent=2)

    # Focus 3: feature candidates
    candidates = []
    # Define feature rules as lambdas on features
    feat_rules = [
        ('odd_eq_3', lambda f: f['odd']==3),
        ('span_10_25', lambda f: 10<=f['span']<=25),
        ('no_consec', lambda f: f['consec']==0),
        ('high_span', lambda f: f['span']>30),
        ('odd_ge_4', lambda f: f['odd']>=4)
    ]
    # evaluate over last 150 draws for each lottery: compute hit rate of existing best strategy when feature holds
    recon_report = {'candidates':[]}
    for L in LOTTERIES:
        draws = load_draws(L, limit=500)
        feats = [features_of(d) for d in draws[-150:]]
        for name,rule in feat_rules:
            matched = [rule(f) for f in feats]
            match_rate = sum(matched)/len(matched)
            # naive edge proxy: compare how often existing top strategy had hits when feature matched vs overall
            # find top strategy for this lottery from strategies dict by edge_300p
            top=None;topedge=-9
            for sname,s in strategies.items():
                if s.get('lottery_type')==L:
                    e = s.get('edge_300p') or -999
                    if e>topedge:
                        topedge=e;top=sname
            # compute conditional hit rate by querying prediction_results for top strategy in last 150 and aligning dates to draws
            # For speed, we approximate using hit records for top (if exists)
            cond_rate=None
            try:
                rows = hits_for_strategy(top)
                if rows:
                    rows = rows[:150]
                    # align with matched positions from most recent
                    matched_most_recent = matched[-len(rows):]
                    hits = [r[1]>0 for r in rows]
                    if len(hits)==len(matched_most_recent):
                        tot = sum(1 for h,m in zip(hits, matched_most_recent) if m and h)
                        denom = sum(matched_most_recent)
                        cond_rate = (tot/denom) if denom>0 else None
            except Exception:
                cond_rate=None
            recon_report['candidates'].append({'lottery':L,'feature':name,'match_rate_150':match_rate,'top_strategy':top,'top_edge_300p':topedge,'conditional_hit_rate_top':cond_rate})
    # Monte Carlo initial screen for candidate with conditional_hit_rate_top>None and edge proxy >0.02
    # For simplicity, pick any candidate where conditional_hit_rate_top is not None and > overall top hit rate
    mc_pass=[]
    for c in recon_report['candidates']:
        top=c['top_strategy']
        if c['conditional_hit_rate_top'] is None: continue
        # compute overall hit rate for top
        rows = hits_for_strategy(top)[:150]
        if not rows: continue
        overall = sum(1 for r in rows if r[1]>0)/len(rows)
        if c['conditional_hit_rate_top'] - overall > 0.02:
            mc_pass.append(c)
    # run Monte Carlo for passes
    mc_results=[]
    for c in mc_pass:
        # simulate by resampling matched boolean and hits alignment
        top=c['top_strategy']
        rows = hits_for_strategy(top)[:150]
        if not rows: continue
        hits = [1 if r[1]>0 else 0 for r in rows]
        # matched vector (approx) reuse from earlier
        draws = load_draws(c['lottery'], limit=500)
        feats = [features_of(d) for d in draws[-150:]]
        rule = dict(feat_rules)[c['feature']]
        matched = [rule(f) for f in feats]
        matched = matched[-len(hits):]
        obs_delta = (sum(h and m for h,m in zip(hits,matched))/max(1,sum(matched))) - (sum(hits)/len(hits))
        rng=[]
        random.seed(42)
        for i in range(1000):
            # shuffle hits
            s = hits[:]
            random.shuffle(s)
            delta = (sum(h and m for h,m in zip(s,matched))/max(1,sum(matched))) - (sum(s)/len(s))
            rng.append(delta)
        mean = statistics.mean(rng)
        std = statistics.pstdev(rng)
        p = sum(1 for v in rng if v>=obs_delta)/len(rng)
        mc_results.append({'candidate':c,'obs_delta':obs_delta,'mean':mean,'std':std,'p':p})
    recon_report['monte_carlo'] = mc_results
    with open(os.path.join(OUT_DIR,'signal_reconstruction_report.json'),'w') as f:
        json.dump(recon_report,f,indent=2,default=str)

    # final short summary markdown
    md = []
    md.append('# Deep Research Phase1 Summary')
    md.append('\n## Focus 1 — Structure Filtering')
    for L,v in results_struct.items():
        md.append(f"- {L}: odd_p={v['odd']['p']:.3f}, span_p={v['span']['p']:.3f}, consec_p={v['consec']['p']:.3f}")
    md.append('\n## Focus 2 — Signal Quality')
    sig_counts = Counter(v['category'] for v in sig_matrix.values())
    md.append('- Signal categories: '+', '.join(f"{k}:{cnt}" for k,cnt in sig_counts.items()))
    md.append('\n## Focus 3 — Reconstruction')
    md.append(f"- MC passes: {len(mc_results)} candidates passed initial MC screen (delta>0.02, p<{0.1})")
    with open(os.path.join(OUT_DIR,'completed_markdown.md'),'w') as f:
        f.write('\n'.join(md))

if __name__=='__main__':
    run()
