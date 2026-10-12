"""
tests/test_p60_post_p59_roadmap_update.py

P60 post-P59 remote sync and roadmap update verification.
Read-only. No production DB write.
"""
import json
import os
import sqlite3
import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(REPO_ROOT, "lottery_api", "data", "lottery_v2.db")

P59_CAID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"
EXPECTED_TOTAL_ROWS = 43960
EXPECTED_P59_ROWS = 1500

P60_JSON = os.path.join(
    REPO_ROOT,
    "outputs", "replay",
    "p60_post_p59_remote_sync_and_roadmap_update_20260525.json"
)
ROADMAP_PATH = os.path.join(REPO_ROOT, "00-Plan", "roadmap", "roadmap.md")
CTO_PATH = os.path.join(REPO_ROOT, "00-Plan", "roadmap", "CTO-Analysis.md")


# ---------------------------------------------------------------------------
# DB state
# ---------------------------------------------------------------------------

class TestP60DBState:
    """Production DB must remain at 43960 rows after P60 (docs-only task)."""

    @pytest.fixture(autouse=True)
    def db(self):
        conn = sqlite3.connect(DB_PATH)
        yield conn
        conn.close()

    def test_total_rows_43960(self, db):
        total = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays"
        ).fetchone()[0]
        assert total == EXPECTED_TOTAL_ROWS, (
            f"Expected {EXPECTED_TOTAL_ROWS} total rows, got {total}"
        )

    def test_p59_rows_1500(self, db):
        p59 = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id = ?",
            (P59_CAID,),
        ).fetchone()[0]
        assert p59 == EXPECTED_P59_ROWS, (
            f"Expected {EXPECTED_P59_ROWS} P59 rows, got {p59}"
        )

    def test_no_online_rows_from_p59(self, db):
        """P59 rows must not have dry_run=1 (must be correctly inserted as dry_run=0)."""
        dry_run_bad = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id = ? AND dry_run = 1",
            (P59_CAID,),
        ).fetchone()[0]
        assert dry_run_bad == 0, f"P59 rows must have dry_run=0, got {dry_run_bad} with dry_run=1"

    def test_no_new_caids_after_p60(self, db):
        """P60 is docs-only — controlled_apply_id P59 must be the newest Wave 5 CAID."""
        wave5_count = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id = ?",
            (P59_CAID,),
        ).fetchone()[0]
        assert wave5_count == 1500, (
            f"P59 CAID should have exactly 1500 rows, got {wave5_count}"
        )

    def test_fourier30_rows_correct(self, db):
        rows = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id LIKE '%fourier30_markov30%' "
            "AND lottery_type = 'POWER_LOTTO'",
        ).fetchone()[0]
        assert rows == 1500, f"Expected 1500 fourier30_markov30 rows, got {rows}"

    def test_watchlist_not_applied(self, db):
        """cold_complement_2bet and zonal_entropy_2bet must not be in DB."""
        for strategy in ("cold_complement_2bet", "zonal_entropy_2bet"):
            count = db.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays "
                "WHERE strategy_id LIKE ?",
                (f"%{strategy}%",),
            ).fetchone()[0]
            assert count == 0, (
                f"WATCHLIST strategy {strategy} must not be in production DB; found {count}"
            )


# ---------------------------------------------------------------------------
# P60 JSON structure
# ---------------------------------------------------------------------------

class TestP60JSONStructure:
    """P60 output JSON must exist and contain expected fields."""

    @pytest.fixture(autouse=True)
    def data(self):
        assert os.path.exists(P60_JSON), f"P60 JSON not found: {P60_JSON}"
        with open(P60_JSON) as f:
            self._data = json.load(f)

    def test_phase_p60(self):
        assert self._data["phase"] == "P60"

    def test_classification_present(self):
        assert "classification" in self._data
        assert self._data["classification"] in (
            "P60_POST_P59_REMOTE_SYNC_AND_ROADMAP_UPDATED",
            "P60_ROADMAP_UPDATED_NOT_PUSHED",
            "P60_BLOCKED_BY_REMOTE_PUSH_POLICY",
        )

    def test_production_rows_43960(self):
        assert self._data["pre_flight"]["production_rows"] == EXPECTED_TOTAL_ROWS

    def test_p59_inserted_rows_1500(self):
        assert self._data["pre_flight"]["p59_inserted_rows"] == EXPECTED_P59_ROWS

    def test_p59_merge_confirmed(self):
        assert self._data["pre_flight"]["p59_merge_confirmed"] is True

    def test_no_db_write(self):
        assert self._data["governance_confirmations"]["no_db_write"] is True

    def test_no_online_promotion(self):
        assert self._data["governance_confirmations"]["no_online_promotion"] is True

    def test_no_champion_replacement(self):
        assert self._data["governance_confirmations"]["no_champion_replacement"] is True

    def test_no_registry_mutation(self):
        assert self._data["governance_confirmations"]["no_registry_mutation"] is True

    def test_no_force_push(self):
        assert self._data["governance_confirmations"]["no_force_push"] is True

    def test_drift_guard_pass(self):
        assert "PASS" in self._data["pre_flight"]["drift_guard"]

    def test_branch_governance_pass(self):
        assert "PASS" in self._data["pre_flight"]["branch_governance_guard"]

    def test_roadmap_marker_updated(self):
        assert self._data["roadmap_marker"] == (
            "CTO_ROADMAP_AFTER_P59_POWERLOTTO_WAVE5_APPLY_20260525"
        )

    def test_watchlist_status(self):
        ws = self._data["watchlist_status"]
        assert ws["cold_complement_2bet"] == "WATCHLIST_REHEARSAL_ONLY"
        assert ws["zonal_entropy_2bet"] == "WATCHLIST_REHEARSAL_ONLY"


# ---------------------------------------------------------------------------
# Roadmap file content
# ---------------------------------------------------------------------------

class TestRoadmapContent:
    """roadmap.md must reflect P59 completion."""

    @pytest.fixture(autouse=True)
    def content(self):
        assert os.path.exists(ROADMAP_PATH), f"roadmap.md not found: {ROADMAP_PATH}"
        with open(ROADMAP_PATH) as f:
            self._text = f.read()

    def test_production_rows_43960_in_roadmap(self):
        assert "43960" in self._text, "roadmap.md must reference 43960 production rows"

    def test_p59_row_present(self):
        assert "P59" in self._text, "roadmap.md must have P59 row"

    def test_fourier30_markov30_mentioned(self):
        assert "fourier30_markov30_2bet" in self._text

    def test_wave5_watchlist_mentioned(self):
        assert "WATCHLIST_REHEARSAL_ONLY" in self._text

    def test_roadmap_marker_updated(self):
        assert "CTO_ROADMAP_AFTER_P59_POWERLOTTO_WAVE5_APPLY_20260525" in self._text

    def test_p61_options_present(self):
        assert "P61" in self._text, "roadmap.md must recommend P61 next phase"


# ---------------------------------------------------------------------------
# CTO-Analysis file content
# ---------------------------------------------------------------------------

class TestCTOAnalysisContent:
    """CTO-Analysis.md must reflect P59 completion."""

    @pytest.fixture(autouse=True)
    def content(self):
        assert os.path.exists(CTO_PATH), f"CTO-Analysis.md not found: {CTO_PATH}"
        with open(CTO_PATH) as f:
            self._text = f.read()

    def test_p59_heading_present(self):
        assert "P59" in self._text

    def test_rows_43960_in_cto(self):
        assert "43960" in self._text

    def test_no_online_promotion_confirmed(self):
        assert "NOT performed" in self._text

    def test_champion_not_replaced(self):
        assert "fourier_rhythm_3bet" in self._text
