"""
P104: Post-Ingestion DB Audit + Source Trace
Tests verify artifact existence, DB snapshot, delta fields, governance compliance.
"""

import json
import os
import sqlite3
import subprocess
import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), '..')
DB_PATH = os.path.join(REPO_ROOT, 'lottery_api', 'data', 'lottery_v2.db')
ARTIFACT_JSON = os.path.join(REPO_ROOT, 'outputs', 'replay', 'p104_post_ingestion_db_audit_source_trace_20260527.json')
ARTIFACT_MD = os.path.join(REPO_ROOT, 'docs', 'replay', 'p104_post_ingestion_db_audit_source_trace_20260527.md')

EXPECTED_REPLAY_ROWS = 54462
EXPECTED_PL_MAX = 115000041
STAR3_OLD_MAX = 115000024
STAR3_OLD_COUNT = 4115
STAR4_OLD_COUNT = 0

VALID_CLASSIFICATIONS = {
    "P104_POST_INGESTION_DB_AUDIT_SOURCE_UNKNOWN_READY",
    "P104_POST_INGESTION_DB_AUDIT_BLOCKED_DATA_QUALITY",
    "P104_POST_INGESTION_DB_AUDIT_SOURCE_CONFIRMED_READY",
}


@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    yield conn
    conn.close()


# --- 1. JSON artifact exists ---
def test_01_json_artifact_exists():
    assert os.path.exists(ARTIFACT_JSON), f"JSON artifact missing: {ARTIFACT_JSON}"


# --- 2. MD artifact exists ---
def test_02_md_artifact_exists():
    assert os.path.exists(ARTIFACT_MD), f"MD artifact missing: {ARTIFACT_MD}"


# --- 3. Classification is valid ---
def test_03_classification_valid(artifact):
    cls = artifact.get('p104_classification')
    assert cls in VALID_CLASSIFICATIONS, f"Invalid classification: {cls}"


# --- 4. DB snapshot included ---
def test_04_db_snapshot_included(artifact):
    snap = artifact.get('db_snapshot')
    assert snap is not None, "db_snapshot missing from artifact"
    assert 'replay_rows' in snap
    assert 'power_lotto_max_draw' in snap
    assert 'star3_count' in snap
    assert 'star3_max_draw' in snap
    assert 'star4_count' in snap
    assert 'star4_max_draw' in snap


# --- 5. 3_STAR current count/max included ---
def test_05_star3_current_count_max(artifact):
    snap = artifact['db_snapshot']
    assert snap['star3_count'] >= STAR3_OLD_COUNT, f"star3_count {snap['star3_count']} < old baseline {STAR3_OLD_COUNT}"
    assert snap['star3_max_draw'] > STAR3_OLD_MAX, f"star3_max_draw {snap['star3_max_draw']} should exceed old baseline {STAR3_OLD_MAX}"


# --- 6. 4_STAR current count/max included ---
def test_06_star4_current_count_max(artifact):
    snap = artifact['db_snapshot']
    assert snap['star4_count'] >= STAR4_OLD_COUNT, f"star4_count {snap['star4_count']} < old baseline {STAR4_OLD_COUNT}"
    assert 'star4_max_draw' in snap


# --- 7. 3_STAR delta from 115000024 included ---
def test_07_star3_delta_included(artifact):
    delta = artifact.get('star3_delta')
    assert delta is not None, "star3_delta missing"
    assert delta['old_baseline_max_draw'] == STAR3_OLD_MAX
    assert delta['old_baseline_count'] == STAR3_OLD_COUNT
    assert delta['current_count'] >= STAR3_OLD_COUNT
    assert delta['delta_rows'] == delta['current_count'] - STAR3_OLD_COUNT


# --- 8. Source trace status included ---
def test_08_source_trace_status(artifact):
    trace = artifact.get('source_trace')
    assert trace is not None, "source_trace missing"
    assert 'source_file_found' in trace
    assert 'ingestion_path_known' in trace
    assert 'source_classification' in trace
    assert 'conclusion' in trace


# --- 9. Ingestion path status included ---
def test_09_ingestion_path_status(artifact):
    trace = artifact['source_trace']
    assert 'ingest_log_3star_entries' in trace
    assert 'ingest_log_4star_entries' in trace
    assert trace['ingest_log_3star_entries'] == 0, "ingest_log should have 0 entries for 3_STAR"
    assert trace['ingest_log_4star_entries'] == 0, "ingest_log should have 0 entries for 4_STAR"


# --- 10. P100 evaluation authorization field exists ---
def test_10_p100_authorization_field(artifact):
    impact = artifact.get('governance_impact')
    assert impact is not None, "governance_impact missing"
    assert 'p100_evaluation_technically_possible' in impact
    assert 'p100_evaluation_authorized' in impact
    assert impact['p100_evaluation_authorized'] is False, "P100 must not be authorized in P104"


# --- 11. 4_STAR backtest NOT RUN ---
def test_11_star4_backtest_not_run(artifact):
    impact = artifact['governance_impact']
    assert impact.get('star4_backtest_status') == "NOT_RUN", "4_STAR backtest must remain NOT_RUN"


# --- 12. No DB writes ---
def test_12_no_db_writes(artifact):
    assert artifact['governance']['db_writes'] is False, "db_writes must be false"


# --- 13. No replay row inserts ---
def test_13_no_replay_row_inserts(artifact):
    assert artifact['governance']['replay_row_inserts'] is False, "replay_row_inserts must be false"


# --- 14. replay_rows remains 54462 ---
def test_14_replay_rows_unchanged(db):
    c = db.cursor()
    c.execute('SELECT COUNT(*) FROM strategy_prediction_replays')
    count = c.fetchone()[0]
    assert count == EXPECTED_REPLAY_ROWS, f"replay_rows changed: expected {EXPECTED_REPLAY_ROWS}, got {count}"


# --- 15. POWER_LOTTO max_draw remains 115000041 ---
def test_15_power_lotto_max_draw_unchanged(db):
    c = db.cursor()
    c.execute("SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'")
    val = c.fetchone()[0]
    assert val == EXPECTED_PL_MAX, f"POWER_LOTTO max_draw changed: expected {EXPECTED_PL_MAX}, got {val}"


# --- 16. DB file is not staged ---
def test_16_db_not_staged():
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    db_staged = any('lottery_v2.db' in f for f in staged)
    assert not db_staged, f"lottery_v2.db must not be staged. Staged files: {staged}"


# --- 17. Next action matrix exists ---
def test_17_next_action_matrix(artifact):
    matrix = artifact.get('next_action_decision_matrix')
    assert matrix is not None, "next_action_decision_matrix missing"
    assert 'option_A' in matrix
    assert 'option_B' in matrix
    assert 'option_C' in matrix


# --- 18. DB writes false in artifact governance ---
def test_18_governance_db_staged_false(artifact):
    assert artifact['governance']['db_staged'] is False


# --- 19. 3_STAR integrity verdict is PASS ---
def test_19_star3_integrity_pass(artifact):
    integrity = artifact.get('star3_integrity', {})
    assert integrity.get('duplicate_draws', -1) == 0
    assert integrity.get('invalid_digit_range', -1) == 0
    assert integrity.get('wrong_number_count', -1) == 0
    verdict = integrity.get('integrity_verdict', '')
    assert 'PASS' in verdict, f"Unexpected integrity verdict: {verdict}"


# --- 20. 4_STAR integrity verdict is PASS ---
def test_20_star4_integrity_pass(artifact):
    integrity = artifact.get('star4_integrity', {})
    assert integrity.get('duplicate_draws', -1) == 0
    assert integrity.get('invalid_digit_range', -1) == 0
    verdict = integrity.get('integrity_verdict', '')
    assert 'PASS' in verdict, f"Unexpected integrity verdict: {verdict}"


# --- 21. Source not found ---
def test_21_source_not_found(artifact):
    trace = artifact['source_trace']
    assert trace['source_file_found'] is False
    assert trace['ingestion_path_known'] is False


# --- 22. Backup DB timeline included ---
def test_22_backup_db_timeline(artifact):
    trace = artifact['source_trace']
    timeline = trace.get('backup_db_timeline')
    assert timeline is not None, "backup_db_timeline missing"
    assert len(timeline) >= 8, f"Expected >=8 backup entries, got {len(timeline)}"
    for k, v in timeline.items():
        assert v.get('star3_count') == STAR3_OLD_COUNT, f"Backup {k} star3_count should be {STAR3_OLD_COUNT}"
        assert v.get('star4_count') == STAR4_OLD_COUNT, f"Backup {k} star4_count should be {STAR4_OLD_COUNT}"


# --- 23. lottery_history.json not staged ---
def test_23_lottery_history_not_staged():
    result = subprocess.run(
        ['git', 'diff', '--cached', '--name-only'],
        cwd=REPO_ROOT, capture_output=True, text=True
    )
    staged = result.stdout.strip().splitlines()
    hist_staged = any('lottery_history.json' in f for f in staged)
    assert not hist_staged, f"lottery_history.json must not be staged. Staged: {staged}"


# --- 24. Known risks and unknowns present ---
def test_24_known_risks_present(artifact):
    risks = artifact.get('known_risks_and_unknowns')
    assert risks is not None and len(risks) > 0, "known_risks_and_unknowns must be non-empty"
