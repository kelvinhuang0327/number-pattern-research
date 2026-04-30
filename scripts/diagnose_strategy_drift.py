#!/usr/bin/env python3
"""
Diagnostic: Strategy drift & confidence decomposition
Writes per-strategy JSONs and a summary MD. Read-only against orchestrator/orchestrator.db.
"""

import argparse
import sqlite3
import json
import os
import sys
from datetime import datetime
import math
import statistics

try:
    import numpy as np
    from scipy import stats
except Exception:
    # Best-effort: require numpy and scipy; fail with clear message if missing
    np = None
    stats = None

SEED = 42


def ewma(series, alpha=0.05):
    s = None
    for x in series:
        if s is None:
            s = x
        else:
            s = alpha * x + (1 - alpha) * s
    return s


def cohens_d(a, b):
    # Cohen's d for two samples
    if len(a) < 2 or len(b) < 2:
        return None
    ma = statistics.mean(a)
    mb = statistics.mean(b)
    sa = statistics.pstdev(a)
    sb = statistics.pstdev(b)
    # pooled std (using population sd)
    try:
        pooled = math.sqrt((sa * sa + sb * sb) / 2)
        if pooled == 0:
            return None
        return (ma - mb) / pooled
    except Exception:
        return None


def ks_test(a, b):
    if stats is None:
        return {'statistic': None, 'pvalue': None}
    try:
        res = stats.ks_2samp(a, b)
        return {'statistic': float(res.statistic), 'pvalue': float(res.pvalue)}
    except Exception:
        return {'statistic': None, 'pvalue': None}


def ensure_dir(path):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--limit', type=int, default=500)
    parser.add_argument('--out', type=str, default='research/ux_diagnostics/')
    parser.add_argument('--db', type=str, default='orchestrator/orchestrator.db')
    args = parser.parse_args()

    np_random = None
    try:
        import numpy as _np
        np_random = _np.random.default_rng(SEED)
    except Exception:
        np_random = None

    ensure_dir(args.out)
    timestamp = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
    out_json_path = os.path.join(args.out, f'{timestamp}_report.json')
    out_md_path = os.path.join(args.out, f'{timestamp}_report.md')
    per_strategy_dir = os.path.join(args.out, 'output')
    ensure_dir(per_strategy_dir)

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    gaps = []
    results = []
    flagged_summary = []

    # 1. find strategies with sample_count >= 30
    try:
        cur.execute("SELECT strategy_id, game_type, backtest_edge, sample_count FROM strategy_live_state WHERE sample_count >= 30")
        strategies = cur.fetchall()
    except Exception as e:
        print('ERROR: reading strategy_live_state failed:', e)
        strategies = []

    for row in strategies:
        sid = row['strategy_id']
        game = row['game_type'] if 'game_type' in row.keys() else None
        backtest_edge = row['backtest_edge'] if 'backtest_edge' in row.keys() else None
        try:
            cur.execute("SELECT draw_id, roi, recorded_at FROM live_strategy_outcomes WHERE strategy_id = ? ORDER BY recorded_at DESC LIMIT ?", (sid, args.limit))
            draws = cur.fetchall()
        except Exception as e:
            gaps.append(f"missing live_strategy_outcomes for {sid}: {e}")
            draws = []

        draws = list(draws)[::-1]  # chronological
        rois = [r['roi'] for r in draws if r['roi'] is not None]
        recent_draws = [{'draw_id': r['draw_id'], 'roi': r['roi']} for r in draws]

        if len(rois) == 0:
            gaps.append(f'no roi data for {sid}')
            continue

        e_live = ewma(rois, alpha=0.05)
        drift_abs = None
        drift_rel = None
        if backtest_edge is not None:
            try:
                drift_abs = backtest_edge - e_live
                if backtest_edge != 0:
                    drift_rel = drift_abs / float(backtest_edge)
            except Exception:
                drift_abs = None
                drift_rel = None

        flagged = False
        flags = []

        # check absolute threshold
        if drift_abs is not None and drift_abs >= 0.02:
            flagged = True
            flags.append('abs_drift')

        # ewma decline > 2 sigma of prior 150-draw window
        if len(rois) >= 151:
            # compute rolling ewma series
            ewma_series = []
            s = None
            alpha = 0.05
            for x in rois:
                if s is None:
                    s = x
                else:
                    s = alpha * x + (1 - alpha) * s
                ewma_series.append(s)
            recent_ewma = ewma_series[-1]
            prior_window = ewma_series[-151:-1]
            mean_prior = statistics.mean(prior_window)
            sd_prior = statistics.pstdev(prior_window)
            if sd_prior is not None and sd_prior > 0:
                if (recent_ewma - mean_prior) < -2 * sd_prior:
                    flagged = True
                    flags.append('ewma_decline')
        else:
            # not enough history
            pass

        top_features = []
        # get most recent task_outcomes.features_json
        try:
            cur.execute("SELECT features_json, recorded_at, agent_task_run_id FROM task_outcomes WHERE strategy_id = ? ORDER BY recorded_at DESC LIMIT 1", (sid,))
            tf = cur.fetchone()
            if tf and tf['features_json']:
                try:
                    feat_obj = json.loads(tf['features_json'])
                    # expect a list of {name, contrib} or dict name->contrib
                    items = []
                    if isinstance(feat_obj, dict):
                        for k, v in feat_obj.items():
                            items.append({'name': k, 'contrib': float(v) if v is not None else 0.0})
                    elif isinstance(feat_obj, list):
                        for it in feat_obj:
                            name = it.get('name') if isinstance(it, dict) else None
                            contrib = it.get('contrib', 0.0) if isinstance(it, dict) else 0.0
                            items.append({'name': name, 'contrib': float(contrib)})
                    items = sorted(items, key=lambda x: abs(x['contrib']), reverse=True)[:10]
                    # For each top feature, attempt to fetch per-draw values: look into live_strategy_outcomes.features_json if present
                    for it in items:
                        fname = it['name']
                        contrib = it['contrib']
                        # gather baseline and recent values if available
                        baseline_vals = []
                        recent_vals = []
                        # attempt to get per-outcome features
                        try:
                            cur.execute("SELECT features_json FROM live_strategy_outcomes WHERE strategy_id = ? ORDER BY recorded_at DESC LIMIT ?", (sid, args.limit))
                            lof = cur.fetchall()[::-1]
                            vals = []
                            for of in lof:
                                if of['features_json']:
                                    try:
                                        fo = json.loads(of['features_json'])
                                        if isinstance(fo, dict) and fname in fo:
                                            vals.append(fo[fname])
                                    except Exception:
                                        pass
                            # split into baseline/backtest window and last 150 draws
                            if len(vals) > 0:
                                baseline_vals = vals[:max(0, len(vals)-150)]
                                recent_vals = vals[-150:]
                        except Exception:
                            pass

                        ks = {'statistic': None, 'pvalue': None}
                        cd = None
                        if len(baseline_vals) >= 2 and len(recent_vals) >= 2:
                            ks = ks_test(baseline_vals, recent_vals)
                            cd = cohens_d(baseline_vals, recent_vals)
                        else:
                            # record gap
                            if len(baseline_vals) < 2 or len(recent_vals) < 2:
                                gaps.append(f'not enough per-draw feature values for {sid}:{fname}')
                        top_features.append({'name': fname, 'contrib': contrib, 'ks_stat': ks.get('statistic'), 'ks_p': ks.get('pvalue'), 'cohens_d': cd})
                except Exception:
                    gaps.append(f'failed parsing features_json for {sid}')
            else:
                gaps.append(f'no task_outcomes.features_json for {sid}')
        except Exception as e:
            gaps.append(f'task_outcomes query failed for {sid}: {e}')

        obj = {
            'strategy_id': sid,
            'game_type': game,
            'backtest_edge': backtest_edge,
            'ewma_live_roi': e_live,
            'drift_delta_abs': drift_abs,
            'drift_delta_rel': drift_rel,
            'flagged': flagged,
            'flag_reasons': flags,
            'top_features': top_features,
            'recent_draws': recent_draws
        }

        # write per-strategy file
        per_path = os.path.join(per_strategy_dir, f'{sid}.json')
        with open(per_path, 'w') as fh:
            json.dump(obj, fh, indent=2, default=str)

        results.append(obj)
        if flagged:
            flagged_summary.append({'strategy_id': sid, 'game_type': game, 'backtest_edge': backtest_edge, 'ewma_live_roi': e_live, 'reasons': flags, 'agent_task_run_id': tf['agent_task_run_id'] if tf else None})

    # Evaluate detector vs cto_review_runs
    # Build a set of (strategy_id, draw_id) or strategy-level events
    actual_events = set()
    flagged_events = set()
    for r in results:
        if r['flagged']:
            flagged_events.add(r['strategy_id'])
    try:
        cur.execute("SELECT strategy_id, action, recorded_at, notes FROM cto_review_runs ORDER BY recorded_at DESC LIMIT ?", (args.limit,))
        rows = cur.fetchall()
        for rr in rows:
            sid = rr['strategy_id'] if 'strategy_id' in rr.keys() else None
            action = rr['action'] if 'action' in rr.keys() else None
            if sid and action and action.lower() in ('demote', 'promote', 'demotion', 'promotion'):
                actual_events.add(sid)
    except Exception as e:
        gaps.append(f'cto_review_runs query failed: {e}')

    # precision and recall at strategy-level
    tp = len([s for s in flagged_events if s in actual_events])
    fp = len([s for s in flagged_events if s not in actual_events])
    fn = len([s for s in actual_events if s not in flagged_events])
    precision = tp / (tp + fp) if (tp + fp) > 0 else None
    recall = tp / (tp + fn) if (tp + fn) > 0 else None

    # permutation test on hit counts
    import random
    rng = random.Random(SEED)
    combined = list(flagged_events.union(actual_events))
    observed = tp
    greater_equal = 0
    nperm = 2000
    for i in range(nperm):
        # shuffle labels: pick same number of flagged as observed, count overlaps
        # simulate by random sampling
        sim_flagged = set(rng.sample(combined, min(len(combined), len(flagged_events)))) if len(combined) > 0 else set()
        sim_overlap = len([s for s in sim_flagged if s in actual_events])
        if sim_overlap >= observed:
            greater_equal += 1
    p_perm = greater_equal / nperm if nperm > 0 else None

    out = {
        'timestamp': timestamp,
        'seed': SEED,
        'n_strategies_tested': len(results),
        'n_flagged': len(flagged_events),
        'n_actual_events': len(actual_events),
        'precision': precision,
        'recall': recall,
        'permutation_pvalue': p_perm,
        'flagged_summary': flagged_summary,
        'gaps': gaps
    }

    with open(out_json_path, 'w') as fh:
        json.dump({'meta': out, 'results': results}, fh, indent=2, default=str)

    # write MD summary
    lines = []
    lines.append(f'# UX Diagnostic — Strategy Drift ({timestamp})\n')
    lines.append('## Flagged strategies\n')
    if len(flagged_summary) == 0:
        lines.append('No strategies flagged.\n')
    else:
        lines.append('| strategy_id | game_type | backtest_edge | ewma_live_roi | reasons | agent_task_run_id |\n')
        lines.append('|---|---:|---:|---:|---|---|\n')
        for f in flagged_summary:
            lines.append(f"| {f['strategy_id']} | {f.get('game_type','')} | {f.get('backtest_edge', '')} | {f.get('ewma_live_roi','')} | {','.join(f.get('reasons',[]))} | {f.get('agent_task_run_id','')} |\n")

    lines.append('\n## Detector evaluation\n')
    lines.append(f"- strategies tested: {len(results)}\n")
    lines.append(f"- flagged: {len(flagged_events)}; actual CTO events: {len(actual_events)}\n")
    lines.append(f"- precision: {precision}; recall: {recall}; permutation p-value: {p_perm}\n")

    lines.append('\n## Recommended actions\n')
    if len(flagged_summary) == 0:
        lines.append('- No immediate actions.\n')
    else:
        for f in flagged_summary:
            # severity heuristic
            sev = 'watch'
            if 'abs_drift' in f['reasons']:
                sev = 'require CTO review'
            lines.append(f"- Strategy {f['strategy_id']}: severity={sev}. Top-3 causes: see per-strategy JSON in output/{f['strategy_id']}.json. Suggested action: { 'require CTO review' if sev!='watch' else 'watch' }\n")

    if len(gaps) > 0:
        lines.append('\n## Data gaps / follow-up\n')
        for g in gaps:
            lines.append(f'- {g}\n')

    with open(out_md_path, 'w') as fh:
        fh.writelines(lines)

    print('Wrote', out_json_path, out_md_path)
    conn.close()


if __name__ == '__main__':
    main()
