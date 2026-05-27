"""
P82: Replay Freshness / Source Gap Guard tests.

Verifies that the guard script correctly detects draw-level coverage
and gap analysis for POWER_LOTTO Batch A strategies.
Read-only — no DB writes.
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "p82_replay_freshness_guard.py"
ARTIFACT_PATH = PROJECT_ROOT / "outputs" / "replay" / "p82_replay_freshness_guard_20260526.json"
DB_PATH = PROJECT_ROOT / "lottery_api" / "data" / "lottery_v2.db"
PYTHON = sys.executable

EXPECTED_LATEST_DRAW = "115000041"
EXPECTED_LATEST_DATE = "2026/05/21"
EXPECTED_REPLAY_ROWS = 54462  # post-P94 Tier B Controlled Apply baseline (was 46962 pre-P94)
# Historical: the P82 artifact was generated 2026-05-26 before P94 Tier B Controlled Apply.
# At that time the DB had 46962 rows. The artifact is a fixed snapshot; do NOT update it.
HISTORICAL_P82_ARTIFACT_ROWS = 46962
EXPECTED_BATCH_A = {"fourier_rhythm_3bet", "fourier30_markov30_2bet"}
EXPECTED_COVERAGE_PCT = 100.0


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def artifact():
    with open(ARTIFACT_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def pl_result(artifact):
    return artifact["results"]["POWER_LOTTO"]


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(str(DB_PATH))
    yield conn
    conn.close()


# ── 1. Script existence and syntax ───────────────────────────────────────────

def test_01_script_exists():
    assert SCRIPT_PATH.exists(), f"Guard script not found: {SCRIPT_PATH}"


def test_02_script_compiles():
    proc = subprocess.run(
        [PYTHON, "-m", "py_compile", str(SCRIPT_PATH)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, f"Script syntax error:\n{proc.stderr}"


# ── 2. Script runs successfully ───────────────────────────────────────────────

def test_03_script_exit_zero(tmp_path):
    out = tmp_path / "result.json"
    proc = subprocess.run(
        [PYTHON, str(SCRIPT_PATH), "--lottery", "POWER_LOTTO", "--json-out", str(out)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, (
        f"Guard exited {proc.returncode}\nstdout: {proc.stdout}\nstderr: {proc.stderr}"
    )


# ── 3. Artifact structure ─────────────────────────────────────────────────────

def test_04_artifact_exists(artifact):
    assert artifact is not None


def test_05_overall_classification(artifact):
    assert artifact["overall_classification"] == "FRESHNESS_PASS"


def test_06_power_lotto_in_results(artifact):
    assert "POWER_LOTTO" in artifact["results"]


# ── 4. POWER_LOTTO results ───────────────────────────────────────────────────

def test_07_latest_draw(pl_result):
    assert pl_result["latest_draw"] == EXPECTED_LATEST_DRAW


def test_08_latest_draw_date(pl_result):
    assert pl_result["latest_draw_date"] == EXPECTED_LATEST_DATE


def test_09_replay_rows_total(pl_result):
    # The P82 artifact (2026-05-26) recorded 46962 rows at snapshot time (pre-P94).
    # This is a historical artifact check; live DB is validated in test_17_replay_rows_db.
    assert pl_result["replay_rows_total"] == HISTORICAL_P82_ARTIFACT_ROWS


def test_10_draw_gap_not_detected(pl_result):
    assert pl_result["draw_gap_detected"] is False


def test_11_replay_gap_not_detected(pl_result):
    assert pl_result["replay_gap_detected"] is False


def test_12_batch_a_covered(pl_result):
    covered = set(pl_result["batch_a_covered"])
    assert covered == EXPECTED_BATCH_A, (
        f"Expected {EXPECTED_BATCH_A}, got {covered}"
    )


def test_13_batch_a_gap_empty(pl_result):
    assert pl_result["batch_a_gap"] == [], (
        f"Unexpected Batch A gap: {pl_result['batch_a_gap']}"
    )


def test_14_batch_a_coverage_pct(pl_result):
    assert pl_result["batch_a_coverage_pct"] == EXPECTED_COVERAGE_PCT


def test_15_classification_freshness_pass(pl_result):
    assert pl_result["classification"] == "FRESHNESS_PASS"


def test_16_strategies_checked_count(pl_result):
    assert pl_result["strategies_checked"] == 9


# ── 5. DB state unchanged ─────────────────────────────────────────────────────

def test_17_replay_rows_db(db):
    c = db.cursor()
    c.execute("SELECT COUNT(*) FROM strategy_prediction_replays")
    assert c.fetchone()[0] == EXPECTED_REPLAY_ROWS


def test_18_max_draw_db(db):
    c = db.cursor()
    c.execute(
        "SELECT MAX(CAST(draw AS INTEGER)) FROM draws WHERE lottery_type='POWER_LOTTO'"
    )
    assert c.fetchone()[0] == int(EXPECTED_LATEST_DRAW)


def test_19_batch_a_rows_in_db(db):
    c = db.cursor()
    for strat in EXPECTED_BATCH_A:
        c.execute(
            """SELECT COUNT(*) FROM strategy_prediction_replays
               WHERE lottery_type='POWER_LOTTO' AND target_draw=? AND strategy_id=? AND dry_run=0""",
            (EXPECTED_LATEST_DRAW, strat),
        )
        assert c.fetchone()[0] == 1, (
            f"Missing production row for {strat} draw {EXPECTED_LATEST_DRAW}"
        )


# ── 6. Historical gap is expected ────────────────────────────────────────────

def test_20_historical_strategies_lag_expected(pl_result):
    """Historical-only strategies should have max_draw < latest draw — expected gap."""
    historical = pl_result["historical_strategies"]
    historical_gap = pl_result["historical_gap_expected"]
    assert set(historical_gap).issubset(set(historical)), (
        "historical_gap_expected contains non-historical strategy"
    )


# ── 7. Static: no forbidden git/write operations in script ───────────────────

_FORBIDDEN_PATTERNS = [
    "INSERT INTO", "UPDATE ", "DELETE FROM", "DROP TABLE",
    "CREATE TABLE", "git checkout", "git reset", "git push",
]


def test_21_no_forbidden_write_patterns():
    source = SCRIPT_PATH.read_text()
    violations = [p for p in _FORBIDDEN_PATTERNS if p in source]
    assert not violations, (
        f"Forbidden write patterns found in {SCRIPT_PATH.name}: {violations}"
    )
