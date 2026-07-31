"""
test_p32_replay_post_p31b_verification.py
==========================================
P32: Replay UI/API Verification After P31B Production Apply

Verifies:
  - Production DB has exactly 19960 rows (unchanged from P31B baseline)
  - P31B total (7500 rows) and per-strategy (1500 each) counts
  - All P31B rows are DAILY_539, dry_run=0, replay_status=PREDICTED
  - Data quality: 5 predicted numbers, no special, hit_count == len(hit_numbers)
  - prediction_cutoff_date and prediction_generated_at are present
  - Live API /api/replay/history returns 1500 rows per P31B strategy
  - Pagination works correctly (page_size=200 → 8 pages)
  - lifecycle_status=RETIRED filter returns 7500 rows; ONLINE filter returns 0
  - Strategy catalog shows all 5 P31B strategies with lifecycle=RETIRED
  - Draw order is descending (newest first)
  - Drift guard PASS (baseline=19960)
  - Governance guard PASS (expected-rows=19960)
  - Output JSON artifact exists and is valid

These tests:
  - DO require a production DB with P31B rows applied (19960 total rows)
  - DO require the backend to be running at http://localhost:8002
  - DO NOT write to the DB

P32 classification: P32_REPLAY_POST_P31B_VERIFICATION_MERGED_TO_MAIN
"""

import json
import sqlite3
import subprocess
import sys
import urllib.request
import urllib.parse
from pathlib import Path

import pytest

# ─── Paths ────────────────────────────────────────────────────────────────────

REPO_ROOT   = Path(__file__).parent.parent.resolve()
PYTHON      = sys.executable
DB_PATH     = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
OUTPUT_JSON = REPO_ROOT / "outputs" / "replay" / "p32_replay_post_p31b_verification_20260523.json"
DRIFT_SCRIPT  = REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"
GOVN_SCRIPT   = REPO_ROOT / "scripts" / "replay_branch_governance_guard.py"

API_BASE = "http://localhost:8002"

# ─── Constants ────────────────────────────────────────────────────────────────

EXPECTED_TOTAL_ROWS   = 19960
EXPECTED_P31B_TOTAL   = 7500
EXPECTED_PER_STRATEGY = 1500
CONTROLLED_APPLY_ID   = "P31B_DAILY539_RETIRED_7500_PROD_20260523"

WAVE1_STRATEGY_IDS = [
    "acb_1bet",
    "acb_markov_midfreq",
    "acb_markov_midfreq_3bet",
    "midfreq_acb_2bet",
    "midfreq_fourier_2bet",
]

# ─── Helpers ─────────────────────────────────────────────────────────────────

def _api_get(path: str) -> dict:
    url = f"{API_BASE}{path}"
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


def _api_backend_available() -> bool:
    try:
        _api_get("/api/ping")
        return True
    except Exception:
        return False


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db_conn():
    if not DB_PATH.exists():
        pytest.skip(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def backend():
    if not _api_backend_available():
        pytest.skip("Backend not available at http://localhost:8002")


@pytest.fixture(scope="module")
def output_json():
    if not OUTPUT_JSON.exists():
        pytest.skip(f"Output JSON not found: {OUTPUT_JSON}")
    with open(OUTPUT_JSON, encoding="utf-8") as f:
        return json.load(f)


# ─── DB-Level Tests ───────────────────────────────────────────────────────────

def test_01_production_total_rows(db_conn):
    """Production DB must have exactly 19960 rows — P31B baseline unchanged."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays"
    ).fetchone()[0]
    assert count == EXPECTED_TOTAL_ROWS, (
        f"Expected {EXPECTED_TOTAL_ROWS} production rows, got {count}"
    )


def test_02_p31b_total_rows(db_conn):
    """P31B rows must total 7500 (5 strategies × 1500)."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ?",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert count == EXPECTED_P31B_TOTAL, (
        f"Expected {EXPECTED_P31B_TOTAL} P31B rows, got {count}"
    )


@pytest.mark.parametrize("strategy_id", WAVE1_STRATEGY_IDS)
def test_03_per_strategy_row_count(db_conn, strategy_id):
    """Each Wave 1 strategy must have exactly 1500 production rows."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE strategy_id = ? AND controlled_apply_id = ?",
        (strategy_id, CONTROLLED_APPLY_ID),
    ).fetchone()[0]
    assert count == EXPECTED_PER_STRATEGY, (
        f"Strategy {strategy_id}: expected {EXPECTED_PER_STRATEGY}, got {count}"
    )


def test_04_all_p31b_daily539(db_conn):
    """All P31B rows must have lottery_type = DAILY_539."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND lottery_type != 'DAILY_539'",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert count == 0, f"{count} P31B rows have wrong lottery_type"


def test_05_no_dry_run_rows(db_conn):
    """Production DB must not contain any dry_run=1 rows."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE dry_run = 1"
    ).fetchone()[0]
    assert count == 0, f"Found {count} dry_run=1 rows in production"


def test_06_all_p31b_predicted(db_conn):
    """All P31B rows must have replay_status = PREDICTED."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND replay_status != 'PREDICTED'",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert count == 0, f"{count} P31B rows have non-PREDICTED replay_status"


def test_07_prediction_5_numbers(db_conn):
    """All P31B rows must have exactly 5 predicted numbers."""
    rows = db_conn.execute(
        "SELECT strategy_id, target_draw, predicted_numbers "
        "FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ?",
        (CONTROLLED_APPLY_ID,),
    ).fetchall()
    bad = []
    for row in rows:
        try:
            nums = json.loads(row["predicted_numbers"])
            if len(nums) != 5:
                bad.append((row["strategy_id"], row["target_draw"], len(nums)))
        except Exception:
            bad.append((row["strategy_id"], row["target_draw"], "parse_error"))
    assert len(bad) == 0, f"{len(bad)} rows have ≠5 predicted numbers: {bad[:5]}"


def test_08_no_special_number_daily539(db_conn):
    """DAILY_539 rows must have NULL predicted_special."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND predicted_special IS NOT NULL",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert count == 0, f"{count} DAILY_539 P31B rows have non-NULL predicted_special"


def test_09_hit_count_equals_hit_numbers_length(db_conn):
    """hit_count must equal len(hit_numbers) for all P31B rows."""
    rows = db_conn.execute(
        "SELECT strategy_id, target_draw, hit_count, hit_numbers "
        "FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ?",
        (CONTROLLED_APPLY_ID,),
    ).fetchall()
    bad = []
    for row in rows:
        try:
            hits = json.loads(row["hit_numbers"] or "[]")
            if row["hit_count"] != len(hits):
                bad.append((row["strategy_id"], row["target_draw"],
                             row["hit_count"], len(hits)))
        except Exception:
            bad.append((row["strategy_id"], row["target_draw"], "parse_error", -1))
    assert len(bad) == 0, (
        f"{len(bad)} rows have hit_count ≠ len(hit_numbers): {bad[:5]}"
    )


def test_10_prediction_cutoff_date_present(db_conn):
    """All P31B rows must have a non-null prediction_cutoff_date."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND prediction_cutoff_date IS NULL",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert count == 0, f"{count} P31B rows have NULL prediction_cutoff_date"


def test_11_prediction_generated_at_present(db_conn):
    """All P31B rows must have a non-null prediction_generated_at."""
    count = db_conn.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id = ? AND prediction_generated_at IS NULL",
        (CONTROLLED_APPLY_ID,),
    ).fetchone()[0]
    assert count == 0, f"{count} P31B rows have NULL prediction_generated_at"


# ─── API-Level Tests ──────────────────────────────────────────────────────────

@pytest.mark.parametrize("strategy_id", WAVE1_STRATEGY_IDS)
def test_12_history_api_returns_1500_per_strategy(backend, strategy_id):
    """Live API /api/replay/history must return total=1500 for each P31B strategy."""
    path = f"/api/replay/history?strategy_id={strategy_id}&lottery_type=DAILY_539&page_size=1"
    data = _api_get(path)
    total = data.get("total", -1)
    assert total == EXPECTED_PER_STRATEGY, (
        f"Strategy {strategy_id}: API returned total={total}, expected {EXPECTED_PER_STRATEGY}"
    )


def test_13_history_api_prediction_format(backend):
    """API records must contain exactly 5 predicted numbers, no special number."""
    path = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&page_size=10"
    data = _api_get(path)
    records = data.get("records", [])
    assert len(records) > 0, "No records returned"
    for rec in records:
        nums = rec.get("predicted_numbers", [])
        assert isinstance(nums, list) and len(nums) == 5, (
            f"Draw {rec.get('target_draw')}: expected 5 numbers, got {nums}"
        )
        special = rec.get("predicted_special")
        assert special is None, (
            f"Draw {rec.get('target_draw')}: expected null special, got {special!r}"
        )


def test_14_history_api_hit_count_consistency(backend):
    """API hit_count must equal len(hit_numbers) for returned records."""
    path = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&page_size=50"
    data = _api_get(path)
    records = data.get("records", [])
    bad = []
    for rec in records:
        hit_count = rec.get("hit_count", -999)
        hit_numbers = rec.get("hit_numbers") or []
        if hit_count != len(hit_numbers):
            bad.append((rec.get("target_draw"), hit_count, len(hit_numbers)))
    assert len(bad) == 0, (
        f"{len(bad)} API records have hit_count ≠ len(hit_numbers): {bad[:5]}"
    )


def test_15_history_api_cutoff_date_present(backend):
    """API records must have prediction_cutoff_date present."""
    path = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&page_size=10"
    data = _api_get(path)
    records = data.get("records", [])
    missing = [r.get("target_draw") for r in records
               if not r.get("prediction_cutoff_date")]
    assert len(missing) == 0, (
        f"{len(missing)} records missing prediction_cutoff_date: {missing}"
    )


def test_16_history_api_generated_at_present(backend):
    """API records must have prediction_generated_at present."""
    path = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&page_size=10"
    data = _api_get(path)
    records = data.get("records", [])
    missing = [r.get("target_draw") for r in records
               if not r.get("prediction_generated_at")]
    assert len(missing) == 0, (
        f"{len(missing)} records missing prediction_generated_at: {missing}"
    )


def test_17_history_api_draw_order_descending(backend):
    """API must return draws in descending order (newest first)."""
    path = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&page_size=20"
    data = _api_get(path)
    records = data.get("records", [])
    assert len(records) >= 2, "Not enough records to test ordering"
    draws = [r["target_draw"] for r in records]
    assert draws == sorted(draws, reverse=True), (
        f"Draws not in descending order: {draws[:5]}"
    )


def test_18_history_api_pagination_works(backend):
    """API pagination must work: page_size=200 → total=1500, pages=8."""
    path = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&page_size=200"
    data = _api_get(path)
    assert data["total"] == EXPECTED_PER_STRATEGY, (
        f"Expected total=1500, got {data['total']}"
    )
    assert data["pages"] == 8, f"Expected 8 pages, got {data['pages']}"
    assert len(data["records"]) == 200, (
        f"Expected 200 records on page 1, got {len(data['records'])}"
    )
    # Page 2
    path2 = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&page_size=200&page=2"
    data2 = _api_get(path2)
    assert len(data2["records"]) == 200, (
        f"Expected 200 records on page 2, got {len(data2['records'])}"
    )


def test_19_lifecycle_retired_filter_returns_7500(backend):
    """API lifecycle_status=RETIRED filter for DAILY_539 must return total=7500."""
    path = "/api/replay/history?lottery_type=DAILY_539&lifecycle_status=RETIRED&page_size=1"
    data = _api_get(path)
    total = data.get("total", -1)
    assert total == EXPECTED_P31B_TOTAL, (
        f"RETIRED filter returned total={total}, expected {EXPECTED_P31B_TOTAL}"
    )


def test_20_lifecycle_online_filter_returns_0_for_p31b_strategy(backend):
    """API lifecycle_status=ONLINE must return 0 rows for P31B strategies."""
    path = "/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539&lifecycle_status=ONLINE&page_size=1"
    data = _api_get(path)
    total = data.get("total", -1)
    assert total == 0, (
        f"ONLINE filter for acb_1bet returned total={total}, expected 0"
    )


def test_21_strategy_catalog_shows_p31b_strategies(backend):
    """Strategy catalog must list all 5 P31B strategies."""
    data = _api_get("/api/replay/strategy-catalog")
    strategies_list = data.get("strategies", []) if isinstance(data, dict) else data
    found = {s["strategy_id"]: s for s in strategies_list
             if s["strategy_id"] in WAVE1_STRATEGY_IDS}
    missing = set(WAVE1_STRATEGY_IDS) - set(found.keys())
    assert len(missing) == 0, (
        f"Strategy catalog missing P31B strategies: {missing}"
    )


def test_22_catalog_lifecycle_retired(backend):
    """Catalog must show all 5 P31B strategies with lifecycle_state=RETIRED."""
    data = _api_get("/api/replay/strategy-catalog")
    strategies_list = data.get("strategies", []) if isinstance(data, dict) else data
    strategies = {s["strategy_id"]: s for s in strategies_list}
    bad = []
    for sid in WAVE1_STRATEGY_IDS:
        entry = strategies.get(sid)
        if entry is None:
            bad.append((sid, "not_found"))
        elif entry.get("lifecycle_state") != "RETIRED":
            bad.append((sid, entry.get("lifecycle_state")))
    assert len(bad) == 0, (
        f"P31B strategies with wrong lifecycle_state in catalog: {bad}"
    )


def test_23_strategies_list_endpoint_retired_filter(backend):
    """GET /api/replay/strategies?lifecycle_status=RETIRED must include all 5 P31B strategies."""
    data = _api_get("/api/replay/strategies?lifecycle_status=RETIRED")
    # Normalize: could be list or dict with 'strategies' key
    if isinstance(data, list):
        ids = {s.get("strategy_id") for s in data}
    else:
        ids = {s.get("strategy_id") for s in data.get("strategies", [])}
    missing = set(WAVE1_STRATEGY_IDS) - ids
    assert len(missing) == 0, (
        f"RETIRED strategies list missing: {missing}"
    )


# ─── Output JSON ─────────────────────────────────────────────────────────────

def test_24_output_json_exists():
    assert OUTPUT_JSON.exists(), f"Output JSON not found: {OUTPUT_JSON}"


def test_25_output_json_status(output_json):
    assert output_json["status"] == "PASS", (
        f"Output JSON status={output_json['status']!r}, expected 'PASS'"
    )


def test_26_output_json_phase(output_json):
    assert output_json["phase"] == "P32_REPLAY_POST_P31B_VERIFICATION"


def test_27_output_json_production_rows_unchanged(output_json):
    rc = output_json.get("row_counts", {})
    assert rc.get("production_rows_before") == EXPECTED_TOTAL_ROWS
    assert rc.get("production_rows_after") == EXPECTED_TOTAL_ROWS
    assert rc.get("p31b_total") == EXPECTED_P31B_TOTAL


def test_28_output_json_per_strategy(output_json):
    per_strat = output_json.get("per_strategy_row_counts", {})
    for sid in WAVE1_STRATEGY_IDS:
        assert per_strat.get(sid) == EXPECTED_PER_STRATEGY, (
            f"Strategy {sid}: expected {EXPECTED_PER_STRATEGY} in JSON, got {per_strat.get(sid)}"
        )


# ─── Guards ───────────────────────────────────────────────────────────────────

def test_29_drift_guard_pass(tmp_path):
    """Drift guard must PASS with 19960-row baseline."""
    if not DRIFT_SCRIPT.exists():
        pytest.skip("Drift guard script not found")
    out = tmp_path / "drift.json"
    result = subprocess.run(
        [PYTHON, str(DRIFT_SCRIPT), "--strict", "--json-out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Drift guard FAIL (exit={result.returncode})\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    if out.exists():
        with open(out) as f:
            d = json.load(f)
        assert d["final_classification"] == "REPLAY_LIFECYCLE_DRIFT_GUARD_PASS", (
            f"Unexpected classification: {d['final_classification']}\n"
            f"violations: {d.get('violations', [])}"
        )
        assert d["row_counts"]["total"] == EXPECTED_TOTAL_ROWS


def test_30_governance_guard_pass(tmp_path):
    """Branch governance guard must PASS with --expected-rows 19960."""
    if not GOVN_SCRIPT.exists():
        pytest.skip("Governance guard script not found")
    current_branch = subprocess.check_output(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"], text=True
    ).strip()
    out = tmp_path / "gov.json"
    result = subprocess.run(
        [PYTHON, str(GOVN_SCRIPT),
         "--expected-branch", current_branch,
         "--expected-rows", str(EXPECTED_TOTAL_ROWS),
         "--json-out", str(out)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f"Governance guard exit={result.returncode}\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    if out.exists():
        with open(out) as f:
            d = json.load(f)
        assert d["classification"] == "BRANCH_GOVERNANCE_PASS"
        assert d["production_rows"] == EXPECTED_TOTAL_ROWS
