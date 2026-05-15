#!/usr/bin/env python3
"""
Line A: Full System OOS Refresh
Runs anti-leakage backtest for all deployed strategies across 3 lotteries.
Outputs:
  data/latest_draws_snapshot.json
  data/strategy_oos_refresh_{LOTTERY_TYPE}.jsonl
  data/strategy_refresh_report.json
  (also updates lottery_api/data/strategy_states_{LOTTERY_TYPE}.json)
"""
import sys, os, json, sqlite3
from datetime import datetime

ROOT = '/Users/kelvin/Kelvin-WorkSpace/LotteryNew'
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, 'lottery_api'))
sys.path.insert(0, os.path.join(ROOT, 'tools'))

DB_PATH = os.path.join(ROOT, 'lottery_api/data/lottery_v2.db')
DATA_DIR = os.path.join(ROOT, 'data')
STATES_DIR = os.path.join(ROOT, 'lottery_api/data')

# Baselines per n_bets
BASELINES = {
    'BIG_LOTTO':   {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0896},
    'POWER_LOTTO': {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 5: 0.1791},
    'DAILY_539':   {1: 0.1140, 2: 0.2154, 3: 0.3050, 4: 0.3843, 5: 0.4539},  # M2+
}
METRIC = {
    'BIG_LOTTO': 'is_m3plus', 'POWER_LOTTO': 'is_m3plus', 'DAILY_539': 'is_m2plus'
}
MIN_HIT_COUNTS = {'BIG_LOTTO': 3, 'POWER_LOTTO': 3, 'DAILY_539': 2}

def load_draws(lottery_type):
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT draw, date, numbers FROM draws
        WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC
    ''', (lottery_type,)).fetchall()
    conn.close()
    result = []
    for draw, date, nums_str in rows:
        s = nums_str.strip()
        nums = json.loads(s) if s.startswith('[') else [int(n) for n in s.split(',')]
        result.append({'draw': str(draw), 'date': date, 'numbers': nums})
    return result

def check_hit(bets, actual, min_hits):
    actual_set = set(actual)
    for bet in bets:
        if sum(1 for n in bet if n in actual_set) >= min_hits:
            return True
    return False

def run_backtest_for_strategy(all_draws, lottery_type, strategy_name, predict_func, n_bets,
                              start_idx=None, out_file=None):
    """Run anti-leakage backtest. start_idx: start from this index."""
    min_hits = MIN_HIT_COUNTS[lottery_type]
    metric_key = METRIC[lottery_type]
    total = len(all_draws)
    if start_idx is None:
        start_idx = 50
    
    errors = 0
    records = []
    for idx in range(start_idx, total):
        hist = all_draws[:idx]
        target = all_draws[idx]
        try:
            raw_bets = predict_func(hist)
            # Normalize: some functions return list of dicts, some list of lists
            if raw_bets and isinstance(raw_bets[0], dict):
                bets = [b['numbers'] for b in raw_bets]
            else:
                bets = raw_bets
            if not bets:
                bets = []
            hit = check_hit(bets, target['numbers'], min_hits) if bets else False
        except Exception as e:
            errors += 1
            hit = False
        
        rec = {
            'draw': target['draw'],
            'date': target['date'],
            metric_key: hit,
            'strategy': strategy_name,
        }
        records.append(rec)
        if out_file and len(records) % 100 == 0:
            for r in records[-100:]:
                out_file.write(json.dumps(r) + '\n')
            out_file.flush()
    
    # Flush remaining
    if out_file:
        remainder = len(records) % 100
        if remainder > 0:
            for r in records[-remainder:]:
                out_file.write(json.dumps(r) + '\n')
        out_file.flush()
    
    return records, errors

def compute_windows(records, lottery_type, n_bets):
    """Compute edge for various windows."""
    baseline = BASELINES[lottery_type][n_bets]
    metric_key = METRIC[lottery_type]
    results = {}
    n = len(records)
    for w in [150, 300, 500, 1500, n]:
        label = f'{w}p' if w != n else 'all'
        if n < w:
            results[label] = None
            continue
        last_w = records[-w:]
        hits = sum(1 for r in last_w if r.get(metric_key, False))
        rate = hits / w
        results[label] = round(rate - baseline, 4)
    return results

# ============================================================
# A1: Latest draws snapshot
# ============================================================
def a1_snapshot():
    print('\n=== A1: Latest Draws Snapshot ===')
    conn = sqlite3.connect(DB_PATH)
    snap = {}
    for lt in ['BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO']:
        row = conn.execute('''
            SELECT draw, date FROM draws WHERE lottery_type=?
            ORDER BY CAST(draw AS INTEGER) DESC LIMIT 1
        ''', (lt,)).fetchone()
        count = conn.execute('SELECT COUNT(*) FROM draws WHERE lottery_type=?', (lt,)).fetchone()[0]
        snap[lt] = {'latest_draw': row[0], 'latest_date': row[1], 'total_draws': count}
        print(f'  {lt}: latest={row[0]} ({row[1]}), total={count}')
    conn.close()
    with open(os.path.join(DATA_DIR, 'latest_draws_snapshot.json'), 'w') as f:
        json.dump({'generated_at': datetime.now().isoformat(), **snap}, f, indent=2)
    return snap

# ============================================================
# A2: OOS Backtest per lottery
# ============================================================
def a2_backtest_daily539():
    print('\n=== A2: DAILY_539 Backtest ===')
    from tools.quick_predict import (
        _539_acb_bet, _539_midfreq_bet, _539_markov_bet, _539_fourier_scores,
    )
    from tools.predict_539_5bet_f4cold import predict as f4cold_predict

    def acb_1bet(h): return [_539_acb_bet(h)]
    def midfreq_acb_2bet(h):
        b1 = _539_midfreq_bet(h)
        b2 = _539_acb_bet(h, exclude=set(b1))
        return [b1, b2]
    def acb_markov_midfreq_3bet(h):
        b1 = _539_acb_bet(h)
        b2 = _539_markov_bet(h, exclude=set(b1))
        excl = set(b1) | set(b2)
        b3 = _539_midfreq_bet(h, exclude=excl)
        return [b1, b2, b3]
    def f4cold_5bet(h): return f4cold_predict(h)

    strategies = [
        ('acb_1bet', acb_1bet, 1),
        ('midfreq_acb_2bet', midfreq_acb_2bet, 2),
        ('acb_markov_midfreq_3bet', acb_markov_midfreq_3bet, 3),
        ('f4cold_5bet', f4cold_5bet, 5),
    ]
    
    draws = load_draws('DAILY_539')
    total = len(draws)
    # Run last 1600 to cover 1500p window + buffer
    start = max(50, total - 1600)
    print(f'  Total draws: {total}. Running from idx {start} (draw {draws[start]["draw"]}) to {draws[-1]["draw"]}')
    
    all_results = {}
    out_path = os.path.join(DATA_DIR, 'strategy_oos_refresh_DAILY_539.jsonl')
    out_file = open(out_path, 'w', encoding='utf-8')
    
    for name, func, n_bets in strategies:
        print(f'  {name}...', end=' ', flush=True)
        records, errors = run_backtest_for_strategy(
            draws, 'DAILY_539', name, func, n_bets,
            start_idx=start, out_file=out_file
        )
        windows = compute_windows(records, 'DAILY_539', n_bets)
        print(f'errors={errors}  150p={windows.get("150p", "N/A")} 1500p={windows.get("1500p", "N/A")}')
        all_results[name] = {'n_bets': n_bets, 'windows': windows, 'total': len(records), 'errors': errors}
    
    out_file.close()
    print(f'  Output: {out_path}')
    return all_results

def a2_backtest_biglotto():
    print('\n=== A2: BIG_LOTTO Backtest ===')
    from tools.backtest_p1_deviation_4bet import p1_deviation_4bet as _p1_dev_4bet
    from tools.quick_predict import biglotto_p1_deviation_5bet as _p1_dev_5bet

    def p1_deviation_4bet(h): return _p1_dev_4bet(h)
    def p1_dev_sum5bet(h):
        bets = _p1_dev_5bet(h)
        return [b['numbers'] for b in bets]

    strategies = [
        ('p1_deviation_4bet', p1_deviation_4bet, 4),
        ('p1_dev_sum5bet', p1_dev_sum5bet, 5),
    ]
    
    draws = load_draws('BIG_LOTTO')
    total = len(draws)
    start = max(50, total - 1600)
    print(f'  Total draws: {total}. Running from idx {start} (draw {draws[start]["draw"]}) to {draws[-1]["draw"]}')
    
    all_results = {}
    out_path = os.path.join(DATA_DIR, 'strategy_oos_refresh_BIG_LOTTO.jsonl')
    out_file = open(out_path, 'w', encoding='utf-8')
    
    for name, func, n_bets in strategies:
        print(f'  {name}...', end=' ', flush=True)
        records, errors = run_backtest_for_strategy(
            draws, 'BIG_LOTTO', name, func, n_bets,
            start_idx=start, out_file=out_file
        )
        windows = compute_windows(records, 'BIG_LOTTO', n_bets)
        print(f'errors={errors}  150p={windows.get("150p","N/A")} 1500p={windows.get("1500p","N/A")}')
        all_results[name] = {'n_bets': n_bets, 'windows': windows, 'total': len(records), 'errors': errors}
    
    out_file.close()
    print(f'  Output: {out_path}')
    return all_results

def a2_backtest_powerlotto():
    print('\n=== A2: POWER_LOTTO Backtest ===')
    from tools.power_fourier_rhythm import fourier_rhythm_predict
    from tools.predict_power_orthogonal_5bet import generate_orthogonal_5bet
    from tools.power_midfreq_fourier import midfreq_fourier_2bet

    def fourier_2bet(h): return fourier_rhythm_predict(h, n_bets=2, window=500)
    def fourier_3bet(h): return fourier_rhythm_predict(h, n_bets=3, window=500)
    def pp3_freqort_4bet(h): return generate_orthogonal_5bet(h)[:4]
    def orthogonal_5bet(h): return generate_orthogonal_5bet(h)
    def mf_fourier_2bet(h): return midfreq_fourier_2bet(h)

    strategies = [
        ('fourier_rhythm_2bet', fourier_2bet, 2),
        ('midfreq_fourier_2bet', mf_fourier_2bet, 2),
        ('fourier_rhythm_3bet', fourier_3bet, 3),
        ('pp3_freqort_4bet', pp3_freqort_4bet, 4),
        ('orthogonal_5bet', orthogonal_5bet, 5),
    ]
    
    draws = load_draws('POWER_LOTTO')
    total = len(draws)
    start = max(50, total - 1600)
    print(f'  Total draws: {total}. Running from idx {start} (draw {draws[start]["draw"]}) to {draws[-1]["draw"]}')
    
    all_results = {}
    out_path = os.path.join(DATA_DIR, 'strategy_oos_refresh_POWER_LOTTO.jsonl')
    out_file = open(out_path, 'w', encoding='utf-8')
    
    for name, func, n_bets in strategies:
        print(f'  {name}...', end=' ', flush=True)
        records, errors = run_backtest_for_strategy(
            draws, 'POWER_LOTTO', name, func, n_bets,
            start_idx=start, out_file=out_file
        )
        windows = compute_windows(records, 'POWER_LOTTO', n_bets)
        print(f'errors={errors}  150p={windows.get("150p","N/A")} 1500p={windows.get("1500p","N/A")}')
        all_results[name] = {'n_bets': n_bets, 'windows': windows, 'total': len(records), 'errors': errors}
    
    out_file.close()
    print(f'  Output: {out_path}')
    return all_results

# ============================================================
# A3: Update strategy_states
# ============================================================
def a3_update_states(lottery_type, new_results):
    print(f'\n=== A3: Update strategy_states_{lottery_type} ===')
    states_path = os.path.join(STATES_DIR, f'strategy_states_{lottery_type}.json')
    try:
        with open(states_path) as f:
            states = json.load(f)
    except Exception:
        states = {}
    
    now = datetime.now().isoformat()
    for strategy_name, data in new_results.items():
        windows = data['windows']
        if strategy_name not in states:
            states[strategy_name] = {}
        
        old_1500p = states[strategy_name].get('edge_1500p')
        
        if windows.get('1500p') is not None:
            states[strategy_name]['edge_1500p'] = windows['1500p']
        if windows.get('500p') is not None:
            states[strategy_name]['edge_500p'] = windows['500p']
        if windows.get('300p') is not None:
            states[strategy_name]['edge_300p'] = windows['300p']
        if windows.get('150p') is not None:
            states[strategy_name]['edge_150p'] = windows['150p']
        states[strategy_name]['last_refreshed'] = now
        
        new_1500p = states[strategy_name].get('edge_1500p')
        delta = round(new_1500p - old_1500p, 4) if (new_1500p is not None and old_1500p is not None) else None
        drift_marker = '⚠️ DRIFT' if (delta is not None and abs(delta) > 0.015) else ''
        print(f'  {strategy_name}: old_1500p={old_1500p}  new_1500p={new_1500p}  delta={delta}  {drift_marker}')
    
    with open(states_path, 'w') as f:
        json.dump(states, f, indent=2)
    print(f'  Saved: {states_path}')
    return states

# ============================================================
# A4: Refresh report
# ============================================================
def a4_report(all_results_by_lottery, previous_states_by_lottery):
    print('\n=== A4: Strategy Refresh Report ===')
    report = {
        'refreshed_at': datetime.now().isoformat(),
        'by_lottery': {},
        'notable_drifts': [],
    }
    
    for lt, results in all_results_by_lottery.items():
        old_states = previous_states_by_lottery.get(lt, {})
        lt_list = []
        for strat, data in results.items():
            w = data['windows']
            old_1500p = old_states.get(strat, {}).get('edge_1500p')
            new_1500p = w.get('1500p')
            delta = round(new_1500p - old_1500p, 4) if (new_1500p is not None and old_1500p is not None) else None
            entry = {
                'strategy': strat,
                'n_bets': data['n_bets'],
                'old_1500p': old_1500p,
                'new_1500p': new_1500p,
                'new_500p': w.get('500p'),
                'new_300p': w.get('300p'),
                'new_150p': w.get('150p'),
                'delta_1500p': delta,
            }
            lt_list.append(entry)
            if delta is not None and abs(delta) > 0.015:
                report['notable_drifts'].append({
                    'strategy': strat, 'lottery': lt,
                    'drift_1500p': delta,
                    'old_1500p': old_1500p, 'new_1500p': new_1500p,
                })
        report['by_lottery'][lt] = lt_list
    
    out_path = os.path.join(DATA_DIR, 'strategy_refresh_report.json')
    with open(out_path, 'w') as f:
        json.dump(report, f, indent=2)
    print(f'  Saved: {out_path}')
    
    if report['notable_drifts']:
        print(f'  ⚠️ Notable drifts (>1.5pp): {len(report["notable_drifts"])}')
        for d in report['notable_drifts']:
            print(f'    {d["lottery"]} {d["strategy"]}: {d["drift_1500p"]*100:+.2f}pp')
    else:
        print('  ✓ No notable drifts (all <1.5pp)')
    
    return report

# ============================================================
# Main
# ============================================================
def main():
    print('=== LINE A: Full System OOS Refresh ===')
    
    # Save previous states for delta computation
    prev_states = {}
    for lt in ['BIG_LOTTO', 'DAILY_539', 'POWER_LOTTO']:
        try:
            with open(os.path.join(STATES_DIR, f'strategy_states_{lt}.json')) as f:
                prev_states[lt] = json.load(f)
        except Exception:
            prev_states[lt] = {}
    
    # A1
    a1_snapshot()
    
    # A2 - run all backtests
    results_539 = a2_backtest_daily539()
    results_bl = a2_backtest_biglotto()
    results_pl = a2_backtest_powerlotto()
    
    all_results = {
        'DAILY_539': results_539,
        'BIG_LOTTO': results_bl,
        'POWER_LOTTO': results_pl,
    }
    
    # A3 - update states
    for lt, results in all_results.items():
        a3_update_states(lt, results)
    
    # A4 - report
    report = a4_report(all_results, prev_states)
    
    print('\n=== LINE A COMPLETE ===')
    print(f'Strategies refreshed: {sum(len(v) for v in all_results.values())}')
    print(f'Notable drifts: {len(report["notable_drifts"])}')
    return all_results, report

if __name__ == '__main__':
    main()
