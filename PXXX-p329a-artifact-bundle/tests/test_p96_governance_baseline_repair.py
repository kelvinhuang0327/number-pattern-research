"""
test_p96_governance_baseline_repair.py
=======================================
P96 Governance Baseline Repair verification tests.

Validates that the governance baseline has been correctly updated from the
stale pre-P94 value (46962) to the post-P94 Tier B Controlled Apply value (54462).

Rules:
- NO DB writes
- NO replay row inserts
- NO lifecycle/champion/registry mutation
- Read-only checks only
"""
import json
import pathlib
import sqlite3
import subprocess
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "lottery_api" / "data" / "lottery_v2.db"
DRIFT_GUARD_SCRIPT = REPO_ROOT / "scripts" / "replay_lifecycle_drift_guard.py"
ARTIFACT_PATH = REPO_ROOT / "outputs" / "replay" / "p96_governance_baseline_repair_20260527.json"
DOC_PATH = REPO_ROOT / "docs" / "replay" / "p96_governance_baseline_repair_20260527.md"
PYTHON = sys.executable

# --- Governance baseline constants ---
OLD_BASELINE = 46962
NEW_BASELINE = 54462
DELTA = 7500
MAX_DRAW = "115000041"
P94_APPLY_ID = "P94_TIERB_CONTROLLED_APPLY_20260526"
P94_TRUTH_LEVEL = "TIERB_DRYRUN_VALIDATED"


# ── 1. Artifact existence ──────────────────────────────────────────────────────

def test_01_json_artifact_exists():
    assert ARTIFACT_PATH.exists(), f"P96 JSON artifact not found: {ARTIFACT_PATH}"


def test_02_doc_artifact_exists():
    assert DOC_PATH.exists(), f"P96 doc not found: {DOC_PATH}"


# ── 2. JSON artifact content ───────────────────────────────────────────────────

@pytest.fixture(scope="module")
def p96_artifact():
    with open(ARTIFACT_PATH) as f:
        return json.load(f)


def test_03_classification(p96_artifact):
    assert p96_artifact["classification"] == "P96_GOVERNANCE_BASELINE_REPAIR_READY"


def test_04_old_baseline(p96_artifact):
    assert p96_artifact["old_baseline"] == OLD_BASELINE


def test_05_new_baseline(p96_artifact):
    assert p96_artifact["new_baseline"] == NEW_BASELINE


def test_06_delta(p96_artifact):
    assert p96_artifact["delta"] == DELTA


def test_07_max_draw_unchanged(p96_artifact):
    assert p96_artifact["max_draw_unchanged"] == MAX_DRAW


def test_08_no_db_writes(p96_artifact):
    assert p96_artifact["db_writes"] is False


def test_09_no_replay_rows_inserted(p96_artifact):
    assert p96_artifact["replay_rows_inserted"] == 0


def test_10_special3_special4_untouched(p96_artifact):
    assert p96_artifact["special3_special4_touched"] is False


def test_11_claude_code_showcase_untouched(p96_artifact):
    assert p96_artifact["claude_code_showcase_touched"] is False


# ── 3. Live DB state ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def test_12_db_replay_rows_equals_new_baseline(db):
    """Live DB must have exactly NEW_BASELINE (54462) rows."""
    rows = db.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert rows == NEW_BASELINE, f"Expected {NEW_BASELINE} rows, got {rows}"


def test_13_db_max_draw_unchanged(db):
    """POWER_LOTTO max_draw must remain 115000041."""
    max_draw = db.execute(
        "SELECT MAX(CAST(target_draw AS INTEGER)) FROM strategy_prediction_replays "
        "WHERE lottery_type='POWER_LOTTO'"
    ).fetchone()[0]
    assert str(max_draw) == MAX_DRAW, f"Expected max_draw={MAX_DRAW}, got {max_draw}"


def test_14_p94_rows_in_db(db):
    """P94 Tier B Controlled Apply must have exactly 7500 rows in the DB."""
    count = db.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
        (P94_APPLY_ID,),
    ).fetchone()[0]
    assert count == DELTA, f"Expected {DELTA} P94 rows, got {count}"


def test_15_p94_truth_level_in_db(db):
    """All P94 rows must have truth_level=TIERB_DRYRUN_VALIDATED."""
    count = db.execute(
        "SELECT COUNT(*) FROM strategy_prediction_replays "
        "WHERE controlled_apply_id=? AND truth_level=?",
        (P94_APPLY_ID, P94_TRUTH_LEVEL),
    ).fetchone()[0]
    assert count == DELTA, f"Expected {DELTA} rows with truth_level={P94_TRUTH_LEVEL}, got {count}"


def test_16_p79_sentinel_rows_intact(db):
    """P79 sentinel rows (id=46961, id=46962) must still exist and be unmodified."""
    rows = db.execute(
        "SELECT id, strategy_id, dry_run FROM strategy_prediction_replays "
        "WHERE id IN (46961, 46962) ORDER BY id"
    ).fetchall()
    ids = {r["id"] for r in rows}
    assert 46961 in ids, "Sentinel id=46961 missing"
    assert 46962 in ids, "Sentinel id=46962 missing"
    for r in rows:
        assert r["dry_run"] == 0, f"Sentinel id={r['id']} has dry_run={r['dry_run']}, expected 0"


def test_17_db_rows_did_not_decrease(db):
    """Total rows must be >= NEW_BASELINE (no rows deleted)."""
    rows = db.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
    assert rows >= NEW_BASELINE, f"Rows decreased: got {rows}, expected >= {NEW_BASELINE}"


# ── 4. Drift guard script passes with new baseline ─────────────────────────────

def test_18_drift_guard_exits_zero(tmp_path):
    """Drift guard must exit 0 (PASS) after P96 baseline repair."""
    json_out = tmp_path / "drift_result.json"
    proc = subprocess.run(
        [PYTHON, str(DRIFT_GUARD_SCRIPT), "--strict", "--json-out", str(json_out)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, (
        f"Drift guard exited {proc.returncode} (expected 0).\n"
        f"stderr: {proc.stderr}\nstdout: {proc.stdout}"
    )


def test_19_drift_guard_status_pass(tmp_path):
    """Drift guard JSON output must report status=PASS."""
    json_out = tmp_path / "drift_result.json"
    subprocess.run(
        [PYTHON, str(DRIFT_GUARD_SCRIPT), "--strict", "--json-out", str(json_out)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    assert json_out.exists(), "Drift guard produced no JSON output"
    result = json.loads(json_out.read_text())
    assert result.get("status") == "PASS", (
        f"Expected status=PASS, got {result.get('status')}.\n"
        f"Violations: {result.get('violations', [])}"
    )
    assert result.get("row_counts", {}).get("total") == NEW_BASELINE, (
        f"Drift guard total={result.get('row_counts', {}).get('total')}, expected {NEW_BASELINE}"
    )
    assert result.get("row_counts", {}).get("p94") == DELTA, (
        f"Drift guard p94={result.get('row_counts', {}).get('p94')}, expected {DELTA}"
    )


# ── 5. Governance invariants ───────────────────────────────────────────────────

def test_20_no_staged_db_files():
    """No DB/backup/runtime files staged for commit."""
    proc = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, cwd=str(REPO_ROOT)
    )
    staged = proc.stdout.strip().splitlines()
    forbidden = [f for f in staged if any(
        f.endswith(ext) for ext in (".db", ".bak", ".pid")
    ) or "runtime/" in f]
    assert forbidden == [], f"Forbidden files staged: {forbidden}"
