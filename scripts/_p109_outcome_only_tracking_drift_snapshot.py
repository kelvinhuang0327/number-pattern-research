# P109 Outcome-Only Tracking Drift Snapshot
# Governance: paper_only, diagnostic_only, production_ready=false
# This script computes drift snapshot for HIGH_FIP, MID_FIP, LOW_FIP, ALL_ROWS
# using P108 diagnostic tracking report and P84E outcome rows.
# No odds, EV, CLV, Kelly, stake sizing, or recommendation logic.

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# --- Config ---
P108_PATH = 'data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json'
P84E_PATH = 'data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl'
OUTPUT_PATH = 'data/mlb_2026/derived/p109_outcome_only_tracking_drift_snapshot_summary.json'
REPORT_PATH = 'report/p109_outcome_only_tracking_drift_snapshot_20260531.md'

TRACKED_SIGNALS = ['HIGH_FIP', 'MID_FIP', 'LOW_FIP', 'ALL_ROWS']

# --- Load P108 ---
with open(P108_PATH, encoding='utf-8') as f:
    p108 = json.load(f)

if p108['final_classification'] != 'P108_DIAGNOSTIC_TRACKING_REPORT_READY':
    raise RuntimeError('P108 classification not ready: ' + p108['final_classification'])

# --- Load P84E ---
p84e_rows = []
with open(P84E_PATH, encoding='utf-8') as f:
    for line in f:
        try:
            row = json.loads(line)
            p84e_rows.append(row)
        except Exception:
            continue

def get_month(dtstr):
    try:
        return dtstr[:7]
    except Exception:
        return None

def filter_rows(rows, signal):
    if signal == 'HIGH_FIP':
        return [r for r in rows if r.get('rule_primary_125_flag') is False and r.get('sp_fip_delta', 0) >= 1.0]
    if signal == 'MID_FIP':
        return [r for r in rows if r.get('rule_primary_125_flag') is False and 0.5 <= r.get('sp_fip_delta', 0) < 1.0]
    if signal == 'LOW_FIP':
        return [r for r in rows if r.get('rule_primary_125_flag') is False and 0.0 <= r.get('sp_fip_delta', 0) < 0.5]
    if signal == 'ALL_ROWS':
        return rows
    return []

def compute_drift(rows):
    eligible = [r for r in rows if r.get('outcome_available') and r.get('is_correct') is not None]
    n = len(eligible)
    if n == 0:
        return {
            'eligible_rows': 0,
            'overall_hit_rate': None,
            'monthly_hit_rate': {},
            'monthly_n': {},
            'latest_month_hit_rate': None,
            'prior_month_hit_rate': None,
            'delta_latest_vs_prior': None,
            'delta_latest_vs_overall': None,
            'sample_status': 'SAMPLE_LIMITED',
            'drift_status': 'DRIFT_BLOCKED_BY_SAMPLE',
            'next_check_trigger': '等待樣本累積',
        }
    # Hit rate
    hit_rate = sum(1 for r in eligible if r['is_correct']) / n
    # Monthly
    monthly = defaultdict(list)
    for r in eligible:
        m = get_month(r['game_date'])
        if m:
            monthly[m].append(r)
    monthly_hit_rate = {m: (sum(1 for r in v if r['is_correct']) / len(v)) for m, v in monthly.items() if len(v) > 0}
    monthly_n = {m: len(v) for m, v in monthly.items()}
    months = sorted(monthly_hit_rate.keys())
    latest_month = months[-1] if months else None
    prior_month = months[-2] if len(months) > 1 else None
    latest_hr = monthly_hit_rate[latest_month] if latest_month else None
    prior_hr = monthly_hit_rate[prior_month] if prior_month else None
    delta_latest_vs_prior = latest_hr - prior_hr if latest_hr is not None and prior_hr is not None else None
    delta_latest_vs_overall = latest_hr - hit_rate if latest_hr is not None and hit_rate is not None else None
    # Sample status
    sample_status = 'OK' if n >= 100 else 'SAMPLE_LIMITED'
    # Drift status
    if sample_status == 'SAMPLE_LIMITED':
        drift_status = 'DRIFT_BLOCKED_BY_SAMPLE'
        next_check_trigger = '等待樣本累積'
    elif latest_hr is not None and prior_hr is not None and abs(delta_latest_vs_prior) > 0.08:
        drift_status = 'DRIFT_WARNING'
        next_check_trigger = '需進行異常檢查'
    else:
        drift_status = 'STABLE_DIAGNOSTIC' if sample_status == 'OK' else 'SAMPLE_LIMITED'
        next_check_trigger = '下月檢查'
    return {
        'eligible_rows': n,
        'overall_hit_rate': round(hit_rate, 3) if hit_rate is not None else None,
        'monthly_hit_rate': {k: round(v, 3) for k, v in monthly_hit_rate.items()},
        'monthly_n': monthly_n,
        'latest_month_hit_rate': round(latest_hr, 3) if latest_hr is not None else None,
        'prior_month_hit_rate': round(prior_hr, 3) if prior_hr is not None else None,
        'delta_latest_vs_prior': round(delta_latest_vs_prior, 3) if delta_latest_vs_prior is not None else None,
        'delta_latest_vs_overall': round(delta_latest_vs_overall, 3) if delta_latest_vs_overall is not None else None,
        'sample_status': sample_status,
        'drift_status': drift_status,
        'next_check_trigger': next_check_trigger,
    }

snapshot = {}
for signal in TRACKED_SIGNALS:
    filtered = filter_rows(p84e_rows, signal)
    snapshot[signal] = compute_drift(filtered)

final_classification = 'P109_TRACKING_DRIFT_SNAPSHOT_READY_DIAGNOSTIC_ONLY'
governance = {
    'paper_only': True,
    'diagnostic_only': True,
    'production_ready': False,
    'real_bet_allowed': False,
    'recommendation_allowed': False,
    'product_surface_allowed': False,
    'odds_used': False,
    'ev_computed': False,
    'clv_computed': False,
    'kelly_computed': False,
    'stake_sizing': False,
    'taiwan_lottery_recommendation': False,
    'champion_replacement': False,
    'production_mutation': False,
    'calibration_refit': False,
    'live_api_calls': 0,
    'paid_api_calls': 0,
    'canonical_rows_modified': False,
    'outcome_rows_modified': False,
    'p83e_mapping_modified': False
}

result = {
    'date': datetime.now().strftime('%Y-%m-%d'),
    'final_classification': final_classification,
    'drift_snapshot': snapshot,
    'governance': governance,
    'next_implementation_target': 'P110 Outcome-Only Tracking Dashboard Contract',
}

with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

# --- Write report ---
with open(REPORT_PATH, 'w', encoding='utf-8') as f:
    f.write(f"""# P109 Outcome-Only Tracking Drift Snapshot\n\n- 日期: {result['date']}\n- 最終分類: {final_classification}\n- 治理: paper_only, diagnostic_only, production_ready=false\n- 下一步: {result['next_implementation_target']}\n\n## 各策略追蹤訊號 Drift Snapshot\n\n""")
    for signal in TRACKED_SIGNALS:
        snap = snapshot[signal]
        f.write(f"### {signal}\n")
        for k, v in snap.items():
            f.write(f"- {k}: {v}\n")
        f.write('\n')
    f.write(f"\n## 治理確認\n\n{json.dumps(governance, ensure_ascii=False, indent=2)}\n")
    f.write(f"\n## 產出檔案\n- {OUTPUT_PATH}\n- {REPORT_PATH}\n")
