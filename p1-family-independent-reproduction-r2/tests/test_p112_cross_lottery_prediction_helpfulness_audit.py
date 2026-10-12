"""
tests/test_p112_cross_lottery_prediction_helpfulness_audit.py

P112: Cross-Lottery Prediction-Helpfulness Audit — acceptance tests.

Read-only audit: no DB writes, no promotion, no 4_STAR backtest,
no Special3 P108 rerun.  Replay rows must remain at 54462 throughout.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent

JSON_PATH = REPO_ROOT / "outputs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.json"
MD_PATH   = REPO_ROOT / "docs/replay/p112_cross_lottery_prediction_helpfulness_audit_20260527.md"
SCRIPT_PATH = REPO_ROOT / "scripts/p112_cross_lottery_prediction_helpfulness_audit.py"
DB_PATH = REPO_ROOT / "lottery_api/data/lottery_v2.db"

EXPECTED_TASK_ID          = "P112_CROSS_LOTTERY_PREDICTION_HELPFULNESS_AUDIT"
EXPECTED_CLASSIFICATION   = "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY"
EXPECTED_REPLAY_ROWS      = 54462
AUDIT_SCOPE               = {"POWER_LOTTO", "DAILY_539", "BIG_LOTTO"}
EXCLUDED_SCOPE            = {"3_STAR", "4_STAR"}

ALLOWED_CLASSIFICATIONS = {
    "PREDICTION_HELPFUL",
    "WATCHLIST_CANDIDATE",
    "FALLBACK_EQUIVALENT",
    "SUB_BASELINE",
    "OBSERVE_MORE",
    "INSUFFICIENT_DATA",
    "INCONCLUSIVE",
}

SQL_WRITE_VERBS = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+|DELETE\s+FROM|DROP\s+TABLE|ALTER\s+TABLE|CREATE\s+TABLE)\b",
    re.IGNORECASE | re.MULTILINE,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact() -> dict:
    assert JSON_PATH.exists(), f"JSON artifact missing: {JSON_PATH}"
    with JSON_PATH.open() as f:
        return json.load(f)


@pytest.fixture(scope="module")
def md_text() -> str:
    assert MD_PATH.exists(), f"MD report missing: {MD_PATH}"
    return MD_PATH.read_text()


@pytest.fixture(scope="module")
def script_text() -> str:
    assert SCRIPT_PATH.exists(), f"Script missing: {SCRIPT_PATH}"
    return SCRIPT_PATH.read_text()


@pytest.fixture(scope="module")
def db_conn():
    uri = DB_PATH.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    yield conn
    conn.close()


# ---------------------------------------------------------------------------
# 1. File existence
# ---------------------------------------------------------------------------

class TestFileExistence:
    def test_json_exists(self):
        assert JSON_PATH.exists()

    def test_md_exists(self):
        assert MD_PATH.exists()

    def test_script_exists(self):
        assert SCRIPT_PATH.exists()


# ---------------------------------------------------------------------------
# 2. JSON — top-level fields
# ---------------------------------------------------------------------------

class TestJsonTopLevel:
    def test_task_id(self, artifact):
        assert artifact["task_id"] == EXPECTED_TASK_ID

    def test_classification(self, artifact):
        assert artifact["classification"] == EXPECTED_CLASSIFICATION

    def test_replay_rows_before(self, artifact):
        assert artifact["replay_rows_before"] == EXPECTED_REPLAY_ROWS

    def test_replay_rows_after(self, artifact):
        assert artifact["replay_rows_after"] == EXPECTED_REPLAY_ROWS

    def test_audit_scope_contains_power_lotto(self, artifact):
        assert "POWER_LOTTO" in artifact["audit_scope"]

    def test_audit_scope_contains_daily_539(self, artifact):
        assert "DAILY_539" in artifact["audit_scope"]

    def test_audit_scope_contains_big_lotto(self, artifact):
        assert "BIG_LOTTO" in artifact["audit_scope"]

    def test_excluded_scope_contains_3star(self, artifact):
        es = artifact["excluded_scope"]
        # excluded_scope is a list of strings; check at least one contains "3_STAR"
        if isinstance(es, list):
            assert any("3_STAR" in e for e in es)
        else:
            assert "3_STAR" in es

    def test_excluded_scope_contains_4star(self, artifact):
        es = artifact["excluded_scope"]
        if isinstance(es, list):
            assert any("4_STAR" in e for e in es)
        else:
            assert "4_STAR" in es


# ---------------------------------------------------------------------------
# 3. JSON — governance flags
# ---------------------------------------------------------------------------

class TestGovernanceFlags:
    def test_db_writes_false(self, artifact):
        assert artifact["db_writes"] is False

    def test_no_promotion_true(self, artifact):
        assert artifact["no_strategy_promotion"] is True

    def test_no_4star_backtest_true(self, artifact):
        assert artifact["no_4star_backtest"] is True

    def test_no_p108_rerun_true(self, artifact):
        assert artifact["no_special3_p108_rerun"] is True


# ---------------------------------------------------------------------------
# 4. JSON — DB snapshot invariants
# ---------------------------------------------------------------------------

class TestDbSnapshot:
    def test_snapshot_present(self, artifact):
        assert "current_db_snapshot" in artifact

    def test_3star_count(self, artifact):
        snap = artifact["current_db_snapshot"]
        assert snap.get("three_star_count", snap.get("3_STAR_count")) == 4179

    def test_3star_max_draw(self, artifact):
        snap = artifact["current_db_snapshot"]
        val = snap.get("three_star_max_draw", snap.get("3_STAR_max_draw"))
        assert int(val) == 115000106

    def test_4star_count(self, artifact):
        snap = artifact["current_db_snapshot"]
        assert snap.get("four_star_count", snap.get("4_STAR_count")) == 2922

    def test_4star_max_draw(self, artifact):
        snap = artifact["current_db_snapshot"]
        val = snap.get("four_star_max_draw", snap.get("4_STAR_max_draw"))
        assert int(val) == 115000103

    def test_power_lotto_count(self, artifact):
        snap = artifact["current_db_snapshot"]
        assert snap.get("power_lotto_count", snap.get("POWER_LOTTO_count")) == 1913

    def test_power_lotto_max_draw(self, artifact):
        snap = artifact["current_db_snapshot"]
        val = snap.get("power_lotto_max_draw", snap.get("POWER_LOTTO_max_draw"))
        assert int(val) == 115000041


# ---------------------------------------------------------------------------
# 5. JSON — per_lottery_summary
# ---------------------------------------------------------------------------

class TestPerLotterySummary:
    def test_per_lottery_summary_present(self, artifact):
        assert "per_lottery_summary" in artifact

    def test_power_lotto_in_summary(self, artifact):
        pls = artifact["per_lottery_summary"]
        if isinstance(pls, dict):
            assert "POWER_LOTTO" in pls
        else:
            assert any(r.get("lottery_type") == "POWER_LOTTO" for r in pls)

    def test_daily_539_in_summary(self, artifact):
        pls = artifact["per_lottery_summary"]
        if isinstance(pls, dict):
            assert "DAILY_539" in pls
        else:
            assert any(r.get("lottery_type") == "DAILY_539" for r in pls)

    def test_big_lotto_in_summary(self, artifact):
        pls = artifact["per_lottery_summary"]
        if isinstance(pls, dict):
            assert "BIG_LOTTO" in pls
        else:
            assert any(r.get("lottery_type") == "BIG_LOTTO" for r in pls)


# ---------------------------------------------------------------------------
# 6. JSON — per_strategy_results
# ---------------------------------------------------------------------------

class TestPerStrategyResults:
    def test_per_strategy_results_present(self, artifact):
        assert "per_strategy_results" in artifact

    def test_per_strategy_results_nonempty(self, artifact):
        assert len(artifact["per_strategy_results"]) > 0

    def test_every_strategy_has_classification(self, artifact):
        for r in artifact["per_strategy_results"]:
            assert "classification" in r, f"Missing classification: {r.get('strategy_id')}"

    def test_every_classification_allowed(self, artifact):
        for r in artifact["per_strategy_results"]:
            cls = r["classification"]
            assert cls in ALLOWED_CLASSIFICATIONS, (
                f"Unexpected classification '{cls}' for strategy '{r.get('strategy_id')}'"
            )

    def test_power_lotto_has_prediction_helpful(self, artifact):
        pw = [r for r in artifact["per_strategy_results"] if r.get("lottery_type") == "POWER_LOTTO"]
        helpful = [r for r in pw if r["classification"] == "PREDICTION_HELPFUL"]
        assert len(helpful) >= 1

    def test_daily_539_strategies_present(self, artifact):
        d539 = [r for r in artifact["per_strategy_results"] if r.get("lottery_type") == "DAILY_539"]
        assert len(d539) >= 10

    def test_big_lotto_strategies_present(self, artifact):
        bl = [r for r in artifact["per_strategy_results"] if r.get("lottery_type") == "BIG_LOTTO"]
        assert len(bl) >= 5

    def test_every_strategy_has_lottery_type(self, artifact):
        for r in artifact["per_strategy_results"]:
            assert "lottery_type" in r

    def test_every_strategy_has_edge_main(self, artifact):
        for r in artifact["per_strategy_results"]:
            # edge field may be named edge_main or edge_vs_baseline
            has_edge = "edge_main" in r or "edge_vs_baseline" in r
            assert has_edge, f"No edge field in strategy: {r.get('strategy_id')}"


# ---------------------------------------------------------------------------
# 7. JSON — recommendations
# ---------------------------------------------------------------------------

class TestRecommendations:
    def test_recommendations_present(self, artifact):
        assert "action_recommendations" in artifact

    def test_recommendations_nonempty(self, artifact):
        assert len(artifact["action_recommendations"]) > 0

    def test_every_recommendation_has_rationale(self, artifact):
        for rec in artifact["action_recommendations"]:
            assert "rationale" in rec or "reason" in rec or "description" in rec, (
                f"Recommendation missing rationale: {rec}"
            )


# ---------------------------------------------------------------------------
# 8. JSON — limitations
# ---------------------------------------------------------------------------

class TestLimitations:
    def test_limitations_present(self, artifact):
        assert "limitations" in artifact

    def test_limitations_nonempty(self, artifact):
        assert len(artifact["limitations"]) >= 3


# ---------------------------------------------------------------------------
# 9. Script safety — no SQL write verbs
# ---------------------------------------------------------------------------

class TestScriptSafety:
    def test_no_sql_write_verbs(self, script_text):
        matches = SQL_WRITE_VERBS.findall(script_text)
        assert len(matches) == 0, f"Script contains SQL write verbs: {matches}"

    def test_read_only_uri_in_script(self, script_text):
        assert "mode=ro" in script_text, "Script does not open DB in read-only mode"

    def test_script_has_argparse_json_out(self, script_text):
        assert "--json-out" in script_text


# ---------------------------------------------------------------------------
# 10. MD report content
# ---------------------------------------------------------------------------

class TestMdReport:
    def test_md_has_project_context_lock(self, md_text):
        assert "PROJECT_CONTEXT_LOCK" in md_text

    def test_md_has_classification(self, md_text):
        assert "P112_CROSS_LOTTERY_HELPFULNESS_AUDIT_READY" in md_text

    def test_md_has_p108_blocked_note(self, md_text):
        assert "P108" in md_text and "blocked" in md_text.lower()

    def test_md_has_4star_unauthorized_note(self, md_text):
        assert "unauthorized" in md_text.lower() or "four_star_backtest_authorized" in md_text

    def test_md_has_replay_rows(self, md_text):
        assert "54462" in md_text

    def test_md_has_governance_flags_table(self, md_text):
        assert "db_writes" in md_text

    def test_md_has_per_strategy_results_section(self, md_text):
        assert "Per-Strategy Results" in md_text or "per_strategy_results" in md_text

    def test_md_has_limitations_section(self, md_text):
        assert "Limitations" in md_text or "limitations" in md_text


# ---------------------------------------------------------------------------
# 11. Live DB invariants
# ---------------------------------------------------------------------------

class TestLiveDbInvariants:
    def test_replay_rows_unchanged(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert count == EXPECTED_REPLAY_ROWS

    def test_3star_count(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='3_STAR'"
        ).fetchone()[0]
        assert count == 4179

    def test_4star_count(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='4_STAR'"
        ).fetchone()[0]
        assert count == 2922

    def test_power_lotto_count(self, db_conn):
        count = db_conn.execute(
            "SELECT COUNT(*) FROM draws WHERE lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
        assert count == 1913
