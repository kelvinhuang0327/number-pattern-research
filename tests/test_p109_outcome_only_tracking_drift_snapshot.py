# tests/test_p109_outcome_only_tracking_drift_snapshot.py
# 測試 P109 Outcome-Only Tracking Drift Snapshot
import os
import json
import pytest

P108_PATH = 'data/mlb_2026/derived/p108_outcome_only_diagnostic_tracking_report_summary.json'
P109_PATH = 'data/mlb_2026/derived/p109_outcome_only_tracking_drift_snapshot_summary.json'

@pytest.mark.order(1)
def test_p108_classification():
    with open(P108_PATH, encoding='utf-8') as f:
        p108 = json.load(f)
    assert p108['final_classification'] == 'P108_DIAGNOSTIC_TRACKING_REPORT_READY'

@pytest.mark.order(2)
def test_p109_summary_exists():
    assert os.path.exists(P109_PATH)
    with open(P109_PATH, encoding='utf-8') as f:
        p109 = json.load(f)
    assert 'drift_snapshot' in p109
    assert 'final_classification' in p109

@pytest.mark.order(3)
def test_tracked_signals():
    with open(P109_PATH, encoding='utf-8') as f:
        p109 = json.load(f)
    snapshot = p109['drift_snapshot']
    for signal in ['HIGH_FIP', 'MID_FIP', 'LOW_FIP', 'ALL_ROWS']:
        assert signal in snapshot
        snap = snapshot[signal]
        assert 'drift_status' in snap
        assert 'monthly_hit_rate' in snap
        assert 'eligible_rows' in snap
        assert 'sample_status' in snap
        assert 'next_check_trigger' in snap

@pytest.mark.order(4)
def test_governance_flags():
    with open(P109_PATH, encoding='utf-8') as f:
        p109 = json.load(f)
    g = p109['governance']
    assert g['paper_only'] is True
    assert g['diagnostic_only'] is True
    assert g['production_ready'] is False
    assert g['odds_used'] is False
    assert g['ev_computed'] is False
    assert g['clv_computed'] is False
    assert g['kelly_computed'] is False
    assert g['stake_sizing'] is False
    assert g['taiwan_lottery_recommendation'] is False
    assert g['recommendation_allowed'] is False
    assert g['real_bet_allowed'] is False
    assert g['product_surface_allowed'] is False
    assert g['champion_replacement'] is False
    assert g['production_mutation'] is False
    assert g['calibration_refit'] is False
    assert g['live_api_calls'] == 0
    assert g['paid_api_calls'] == 0
    assert g['canonical_rows_modified'] is False
    assert g['outcome_rows_modified'] is False
    assert g['p83e_mapping_modified'] is False

@pytest.mark.order(5)
def test_final_classification():
    with open(P109_PATH, encoding='utf-8') as f:
        p109 = json.load(f)
    assert p109['final_classification'].startswith('P109_TRACKING_DRIFT_SNAPSHOT_READY')
