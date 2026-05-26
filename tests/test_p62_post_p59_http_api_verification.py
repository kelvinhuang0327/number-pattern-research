"""tests/test_p62_post_p59_http_api_verification.py

Validates P62 evidence: torch import isolation fix, HTTP API verification, DB state.
READ-ONLY: zero production writes.

Tests are designed to run without a live server (TestClientMode uses httpx/TestClient
or direct DB queries). Live HTTP tests are run in a separate class and skipped if
server is not available.
"""
import importlib
import json
import os
import sqlite3
import sys
import urllib.request
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
DB_PATH = os.path.join(ROOT, "lottery_api", "data", "lottery_v2.db")
P62_JSON = os.path.join(ROOT, "outputs", "replay",
                        "p62_post_p59_http_api_verification_closure_20260525.json")
P59_CAID = "P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525"
BASE_URL = "http://localhost:8002"


@pytest.fixture(scope="module")
def p62_json():
    with open(P62_JSON) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    yield conn
    conn.close()


def _server_available():
    try:
        urllib.request.urlopen(f"{BASE_URL}/health", timeout=3)
        return True
    except Exception:
        return False


def _get(path, timeout=5):
    try:
        with urllib.request.urlopen(f"{BASE_URL}{path}", timeout=timeout) as r:
            return json.loads(r.read())
    except Exception as e:
        return {"__error__": str(e)}


# ── P62 JSON structure ────────────────────────────────────────────────────────
class TestP62JSONStructure:
    def test_phase(self, p62_json):
        assert p62_json["phase"] == "P62"

    def test_classification(self, p62_json):
        assert p62_json["classification"] == "P62_POST_P59_HTTP_API_VERIFICATION_PASS"

    def test_marker(self, p62_json):
        assert p62_json["marker"] == "P62_POST_P59_HTTP_API_VERIFICATION_PASS_20260525"

    def test_overall_status(self, p62_json):
        assert p62_json["overall_status"] == "PASS"

    def test_branch(self, p62_json):
        assert p62_json["branch"] == "p62-post-p59-http-api-verification-closure"

    def test_governance_no_db_write(self, p62_json):
        assert p62_json["governance"]["no_db_write"] is True

    def test_governance_no_online_promotion(self, p62_json):
        assert p62_json["governance"]["no_online_promotion"] is True

    def test_governance_production_rows(self, p62_json):
        assert p62_json["governance"]["production_rows"] == 43960


# ── P62 dependency fix section ────────────────────────────────────────────────
class TestP62DependencyFix:
    def test_fix_file_is_unified_predictor(self, p62_json):
        assert "unified_predictor.py" in p62_json["fix_applied"]["file"]

    def test_fix_mentions_meta_stacking(self, p62_json):
        assert "meta_stacking_predictor" in p62_json["fix_applied"]["change"]

    def test_fix_mentions_diffusion(self, p62_json):
        assert "diffusion_predictor" in p62_json["fix_applied"]["change"]

    def test_server_startup_success(self, p62_json):
        assert p62_json["server"]["startup"] == "SUCCESS"

    def test_server_port_8002(self, p62_json):
        assert p62_json["server"]["port"] == 8002


# ── P62 HTTP API section ──────────────────────────────────────────────────────
class TestP62HTTPAPISection:
    def test_summary_status(self, p62_json):
        assert p62_json["http_api_verification"]["summary_endpoint"]["status"] == "PASS"

    def test_summary_fourier30_total_rows(self, p62_json):
        assert p62_json["http_api_verification"]["summary_endpoint"]["fourier30_total_rows"] == 1500

    def test_summary_fourier30_predicted_count(self, p62_json):
        assert p62_json["http_api_verification"]["summary_endpoint"]["fourier30_predicted_count"] == 1500

    def test_summary_fourier30_avg_hit_count(self, p62_json):
        avg = p62_json["http_api_verification"]["summary_endpoint"]["fourier30_avg_hit_count"]
        assert isinstance(avg, float) and 0.0 <= avg <= 6.0

    def test_history_status(self, p62_json):
        assert p62_json["http_api_verification"]["history_endpoint"]["status"] == "PASS"

    def test_history_total_rows(self, p62_json):
        assert p62_json["http_api_verification"]["history_endpoint"]["total_rows_reported"] == 1500

    def test_history_strategy_id(self, p62_json):
        assert p62_json["http_api_verification"]["history_endpoint"]["sample_strategy_id"] == "fourier30_markov30_2bet"

    def test_history_replay_status(self, p62_json):
        assert p62_json["http_api_verification"]["history_endpoint"]["sample_replay_status"] == "PREDICTED"

    def test_history_predicted_numbers_6(self, p62_json):
        nums = p62_json["http_api_verification"]["history_endpoint"]["sample_predicted_numbers"]
        assert len(nums) == 6

    def test_strategies_status(self, p62_json):
        assert p62_json["http_api_verification"]["strategies_endpoint"]["status"] == "PASS"


# ── P62 DB section ────────────────────────────────────────────────────────────
class TestP62DBSection:
    def test_total_rows(self, p62_json):
        assert p62_json["db_verification"]["total_rows"] == 43960

    def test_p59_rows(self, p62_json):
        assert p62_json["db_verification"]["p59_rows"] == 1500

    def test_fourier30_rows(self, p62_json):
        assert p62_json["db_verification"]["fourier30_markov30_2bet_rows"] == 1500


# ── Import isolation: unified_predictor guards torch ─────────────────────────
class TestTorchImportIsolation:
    def test_meta_stacking_guard_exists_in_source(self):
        """The try/except guard for MetaStackingPredictor must exist in unified_predictor.py."""
        src = os.path.join(ROOT, "lottery_api", "models", "unified_predictor.py")
        with open(src) as f:
            content = f.read()
        assert "except ImportError:" in content
        assert "MetaStackingPredictor = None" in content

    def test_diffusion_generator_guard_exists_in_source(self):
        """The try/except guard for LotteryDiffusionGenerator must exist in unified_predictor.py."""
        src = os.path.join(ROOT, "lottery_api", "models", "unified_predictor.py")
        with open(src) as f:
            content = f.read()
        assert "LotteryDiffusionGenerator = None" in content

    def test_no_unconditional_torch_import_in_unified_predictor(self):
        """unified_predictor.py must not import torch directly at module level."""
        src = os.path.join(ROOT, "lottery_api", "models", "unified_predictor.py")
        with open(src) as f:
            lines = f.readlines()
        direct_torch = [l.strip() for l in lines if l.strip().startswith("import torch")]
        assert len(direct_torch) == 0, f"Direct torch imports found: {direct_torch}"

    def test_meta_stacking_not_imported_unconditionally(self):
        """meta_stacking_predictor must not be imported unconditionally at module level."""
        src = os.path.join(ROOT, "lottery_api", "models", "unified_predictor.py")
        with open(src) as f:
            content = f.read()
        # Must be inside a try block
        assert "try:\n    from .meta_stacking_predictor import MetaStackingPredictor" in content


# ── Live DB cross-checks ──────────────────────────────────────────────────────
class TestP62LiveDB:
    def test_total_rows(self, db):
        cnt = db.execute("SELECT COUNT(*) FROM strategy_prediction_replays").fetchone()[0]
        assert cnt == 43960

    def test_p59_rows(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays WHERE controlled_apply_id=?",
            (P59_CAID,)
        ).fetchone()[0]
        assert cnt == 1500

    def test_fourier30_rows(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE strategy_id='fourier30_markov30_2bet' AND lottery_type='POWER_LOTTO'"
        ).fetchone()[0]
        assert cnt == 1500

    def test_p59_dry_run_zero(self, db):
        cnt = db.execute(
            "SELECT COUNT(*) FROM strategy_prediction_replays "
            "WHERE controlled_apply_id=? AND dry_run != 0",
            (P59_CAID,)
        ).fetchone()[0]
        assert cnt == 0

    def test_watchlist_not_in_db(self, db):
        for strat in ("cold_complement_2bet", "zonal_entropy_2bet"):
            cnt = db.execute(
                "SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id LIKE ?",
                (f"%{strat}%",)
            ).fetchone()[0]
            assert cnt == 0, f"{strat}: expected 0 rows, got {cnt}"

    def test_fourier30_summary_query(self, db):
        """Simulate the API summary query for fourier30_markov30_2bet."""
        rows = db.execute("""
            SELECT strategy_id, COUNT(*) as n, AVG(hit_count) as avg_hit
            FROM strategy_prediction_replays
            WHERE lottery_type = 'POWER_LOTTO'
              AND strategy_id = 'fourier30_markov30_2bet'
              AND replay_status = 'PREDICTED'
            GROUP BY strategy_id
        """).fetchall()
        assert len(rows) == 1
        assert rows[0]["n"] == 1500
        assert 0.0 <= rows[0]["avg_hit"] <= 6.0


# ── Live HTTP tests (skip if server not available) ───────────────────────────
@pytest.mark.skipif(not _server_available(), reason="lottery_api server not running on port 8002")
class TestP62LiveHTTP:
    def test_server_health(self):
        d = _get("/health")
        assert "__error__" not in d
        assert d.get("status") == "healthy"

    def test_summary_fourier30_visible(self):
        d = _get("/api/replay/summary?lottery_type=POWER_LOTTO&strategy_id=fourier30_markov30_2bet")
        assert "__error__" not in d
        summaries = d.get("summaries", [])
        fourier = [s for s in summaries if "fourier30_markov30" in s.get("strategy_id", "")]
        assert len(fourier) == 1, f"Expected 1 fourier30 entry, got {len(fourier)}"
        assert fourier[0]["total_rows"] == 1500
        assert fourier[0]["predicted_count"] == 1500

    def test_history_total_1500(self):
        d = _get("/api/replay/history?lottery_type=POWER_LOTTO&strategy_id=fourier30_markov30_2bet&page=1&page_size=5")
        assert "__error__" not in d
        assert d.get("total") == 1500

    def test_history_sample_row(self):
        d = _get("/api/replay/history?lottery_type=POWER_LOTTO&strategy_id=fourier30_markov30_2bet&page=1&page_size=5")
        records = d.get("records", [])
        assert len(records) > 0
        r = records[0]
        assert r["strategy_id"] == "fourier30_markov30_2bet"
        assert r["replay_status"] == "PREDICTED"
        assert isinstance(r["predicted_numbers"], list) and len(r["predicted_numbers"]) == 6

    def test_strategies_endpoint_responds(self):
        d = _get("/api/replay/strategies?lottery_type=POWER_LOTTO")
        assert "__error__" not in d
        strats = d.get("strategies", [])
        assert len(strats) >= 1
