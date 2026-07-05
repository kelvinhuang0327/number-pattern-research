"""
P255D — Ingest Write Guard Runtime Smoke & Governance Closure — Tests

Validates:
1. JSON artifact structure and required fields
2. Runtime smoke results (all 8 cases pass)
3. DB baseline unchanged before/after smoke
4. Governance flags and arc closure

All write-path tests use mocked engine — no real DB write.
"""

import json
import os
import sys
import pytest

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_API_ROOT  = os.path.join(_REPO_ROOT, "lottery_api")
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

_JSON_PATH = os.path.join(
    _REPO_ROOT, "outputs", "research",
    "p255d_ingest_write_guard_runtime_smoke_governance_closure_20260608.json",
)

_ACCEPTED_BASELINE = {
    "BIG_LOTTO_raw": 22239,
    "BIG_LOTTO_canonical": 2114,
    "POWER_LOTTO_raw": 1917,
    "DAILY_539_raw": 5882,
    "strategy_prediction_replays": 94924,
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact():
    assert os.path.exists(_JSON_PATH), f"P255D artifact missing: {_JSON_PATH}"
    with open(_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# 1. Artifact basics
# ---------------------------------------------------------------------------

class TestArtifactBasics:
    def test_json_parses(self, artifact):
        assert isinstance(artifact, dict)

    def test_schema_version(self, artifact):
        assert artifact.get("schema_version") == "1.0"

    def test_task_id(self, artifact):
        assert artifact.get("task_id") == "P255D"

    def test_classification(self, artifact):
        assert artifact.get("classification") == \
            "INGEST_WRITE_GUARD_RUNTIME_SMOKE_GOVERNANCE_CLOSURE_COMPLETE"

    def test_explicit_authorization(self, artifact):
        assert "P255D" in artifact.get("explicit_authorization", "")

    def test_generated_at_present(self, artifact):
        assert artifact.get("generated_at")


# ---------------------------------------------------------------------------
# 2. PR merge statuses
# ---------------------------------------------------------------------------

class TestPRStatuses:
    @pytest.mark.parametrize("pr_key", [
        "pr360_status", "pr361_status", "pr362_status",
        "pr363_status", "pr364_status", "pr365_status",
    ])
    def test_pr_is_merged(self, artifact, pr_key):
        assert artifact.get(pr_key) == "MERGED", f"{pr_key} must be MERGED"


# ---------------------------------------------------------------------------
# 3. P255C dependency
# ---------------------------------------------------------------------------

class TestP255CDependency:
    def test_p255c_dependency_verified(self, artifact):
        assert artifact.get("p255c_dependency_verified") is True

    def test_p255c_pr_365(self, artifact):
        dep = artifact.get("p255c_dependency", {})
        assert dep.get("pr") == 365

    def test_p255c_g01_implemented(self, artifact):
        dep = artifact.get("p255c_dependency", {})
        assert dep.get("G01_implemented") is True

    def test_p255c_g02_implemented(self, artifact):
        dep = artifact.get("p255c_dependency", {})
        assert dep.get("G02_implemented") is True


# ---------------------------------------------------------------------------
# 4. Runtime smoke results
# ---------------------------------------------------------------------------

class TestSmokeResults:
    def test_smoke_results_present(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        assert len(results) >= 8, "Expected at least 8 smoke cases"

    def test_all_smoke_passed(self, artifact):
        assert artifact.get("all_smoke_passed") is True

    def test_omitted_dry_run_case_present(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s01 = next((r for r in results if r.get("case_id") == "S01"), None)
        assert s01 is not None
        assert s01.get("passed") is True

    def test_explicit_dry_run_true_case_present(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s02 = next((r for r in results if r.get("case_id") == "S02"), None)
        assert s02 is not None
        assert s02.get("passed") is True

    def test_no_confirmation_blocked(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s03 = next((r for r in results if r.get("case_id") == "S03"), None)
        assert s03 is not None
        assert s03.get("actual_status") == 422
        assert s03.get("engine_called") is False
        assert s03.get("passed") is True

    def test_no_token_blocked(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s04 = next((r for r in results if r.get("case_id") == "S04"), None)
        assert s04 is not None
        assert s04.get("actual_status") == 422
        assert s04.get("engine_called") is False

    def test_invalid_token_blocked(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s05 = next((r for r in results if r.get("case_id") == "S05"), None)
        assert s05 is not None
        assert s05.get("actual_status") == 422
        assert s05.get("engine_called") is False

    def test_missing_requested_by_blocked(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s06 = next((r for r in results if r.get("case_id") == "S06"), None)
        assert s06 is not None
        assert s06.get("actual_status") == 422
        assert s06.get("engine_called") is False

    def test_missing_reason_blocked(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s07 = next((r for r in results if r.get("case_id") == "S07"), None)
        assert s07 is not None
        assert s07.get("actual_status") == 422
        assert s07.get("engine_called") is False

    def test_mocked_confirmed_write_present(self, artifact):
        results = artifact.get("runtime_smoke_results", [])
        s08 = next((r for r in results if r.get("case_id") == "S08"), None)
        assert s08 is not None
        assert s08.get("mock_confirmed_write") is True
        assert s08.get("real_db_write_risk") is False
        assert s08.get("passed") is True


# ---------------------------------------------------------------------------
# 5. Blocked / dry-run case summaries
# ---------------------------------------------------------------------------

class TestBlockedWriteCases:
    def test_blocked_write_cases_present(self, artifact):
        blocked = artifact.get("blocked_write_cases", [])
        assert len(blocked) >= 5

    def test_all_blocked_cases_have_422(self, artifact):
        blocked = artifact.get("blocked_write_cases", [])
        for bc in blocked:
            assert bc["status"] == 422, f"{bc['case_id']} expected 422 got {bc['status']}"

    def test_all_blocked_cases_engine_not_called(self, artifact):
        blocked = artifact.get("blocked_write_cases", [])
        for bc in blocked:
            assert bc["engine_called"] is False, f"{bc['case_id']} engine should not be called"


class TestDryRunSafeCases:
    def test_dry_run_safe_cases_present(self, artifact):
        safe = artifact.get("dry_run_safe_cases", [])
        assert len(safe) >= 2

    def test_dry_run_cases_return_200(self, artifact):
        safe = artifact.get("dry_run_safe_cases", [])
        for sc in safe:
            assert sc["status"] == 200, f"{sc['case_id']} expected 200 got {sc['status']}"

    def test_dry_run_cases_passed(self, artifact):
        safe = artifact.get("dry_run_safe_cases", [])
        for sc in safe:
            assert sc["passed"] is True


# ---------------------------------------------------------------------------
# 6. Mocked confirmed-write case
# ---------------------------------------------------------------------------

class TestMockedConfirmedWrite:
    def test_mocked_write_case_present(self, artifact):
        mw = artifact.get("mocked_confirmed_write_case", {})
        assert mw.get("case_id") == "S08"

    def test_mocked_write_no_real_db_risk(self, artifact):
        mw = artifact.get("mocked_confirmed_write_case", {})
        assert mw.get("real_db_write_risk") is False

    def test_mocked_write_engine_called(self, artifact):
        mw = artifact.get("mocked_confirmed_write_case", {})
        assert mw.get("engine_called") is True

    def test_mocked_write_is_mock_only(self, artifact):
        mw = artifact.get("mocked_confirmed_write_case", {})
        assert mw.get("mock_confirmed_write") is True

    def test_mocked_write_passed(self, artifact):
        mw = artifact.get("mocked_confirmed_write_case", {})
        assert mw.get("passed") is True


# ---------------------------------------------------------------------------
# 7. DB baseline unchanged
# ---------------------------------------------------------------------------

class TestDBBaseline:
    @pytest.mark.parametrize("metric,expected", list(_ACCEPTED_BASELINE.items()))
    def test_db_before_matches_accepted(self, artifact, metric, expected):
        db = artifact.get("db_baseline_before", {})
        assert db.get(metric) == expected, \
            f"db_baseline_before.{metric} = {db.get(metric)}, expected {expected}"

    @pytest.mark.parametrize("metric,expected", list(_ACCEPTED_BASELINE.items()))
    def test_db_after_matches_accepted(self, artifact, metric, expected):
        db = artifact.get("db_baseline_after", {})
        assert db.get(metric) == expected, \
            f"db_baseline_after.{metric} = {db.get(metric)}, expected {expected}"

    def test_db_unchanged_confirmed(self, artifact):
        assert artifact.get("db_unchanged_confirmed") is True


# ---------------------------------------------------------------------------
# 8. Safety flags
# ---------------------------------------------------------------------------

class TestSafetyFlags:
    def test_no_real_non_dry_run_backfill(self, artifact):
        assert artifact.get("no_real_non_dry_run_backfill_confirmed") is True

    def test_no_db_write(self, artifact):
        assert artifact.get("no_db_write_confirmed") is True

    def test_no_registry_mutation(self, artifact):
        assert artifact.get("no_registry_mutation_confirmed") is True

    def test_no_strategy_promotion(self, artifact):
        assert artifact.get("no_strategy_promotion_confirmed") is True

    def test_no_betting_advice(self, artifact):
        assert artifact.get("no_betting_advice_confirmed") is True


# ---------------------------------------------------------------------------
# 9. Deferred guardrails
# ---------------------------------------------------------------------------

class TestDeferredGuardrails:
    EXPECTED = [
        "G03_ui_confirmation", "G04_audit_log", "G05_backup_sha",
        "G06_idempotency", "G07_cors_hardening", "G08_env_write_gate",
    ]

    def test_deferred_guardrails_present(self, artifact):
        deferred = artifact.get("deferred_guardrails", {})
        for gid in self.EXPECTED:
            assert gid in deferred, f"Missing deferred guardrail: {gid}"

    def test_deferred_status_is_deferred(self, artifact):
        deferred = artifact.get("deferred_guardrails", {})
        for key, val in deferred.items():
            assert val.get("status") == "DEFERRED"


# ---------------------------------------------------------------------------
# 10. Final decision
# ---------------------------------------------------------------------------

class TestFinalDecision:
    def test_final_decision_present(self, artifact):
        fd = artifact.get("final_decision", "")
        assert len(fd) > 0

    def test_final_decision_is_hold(self, artifact):
        fd = artifact.get("final_decision", "").upper()
        assert "HOLD" in fd or "WAITING_FOR_USER_AUTHORIZATION" in fd


# ---------------------------------------------------------------------------
# 11. Live runtime smoke re-verification (requires .venv starlette ≥ 0.40)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.path.exists(os.path.join(_REPO_ROOT, ".venv", "bin", "python3")),
    reason=".venv not found — skip live smoke re-run"
)
class TestLiveSmoke:
    """Re-run the smoke cases live to verify guard behavior at test time."""

    @pytest.fixture(scope="class", autouse=True)
    def _setup(self, request):
        from unittest.mock import MagicMock, patch
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from routes import ingest as ingest_mod
        from routes.ingest import _WRITE_GUARD_TOKEN_FALLBACK

        app = FastAPI()
        app.include_router(ingest_mod.router)

        mock_engine = MagicMock()
        mock_engine.run.return_value = {
            "total": 0, "inserted": 0, "skipped": 0, "conflict": 0, "failed": 0, "details": [],
        }
        mock_logger = MagicMock()
        mock_logger.log.return_value = None

        with patch.object(ingest_mod, "_get_engine",            return_value=mock_engine), \
             patch.object(ingest_mod, "_get_ingest_logger",     return_value=mock_logger), \
             patch.object(ingest_mod, "_refresh_after_insert",  return_value=None):
            request.cls.client = TestClient(app)
            request.cls.mock_engine = mock_engine
            request.cls.token = _WRITE_GUARD_TOKEN_FALLBACK
            yield

    def _post(self, body):
        self.mock_engine.run.reset_mock()
        return self.client.post("/api/ingest/backfill", json=body)

    def test_S01_omitted_dry_run_returns_200(self):
        resp = self._post({})
        assert resp.status_code == 200

    def test_S02_dry_run_true_returns_200(self):
        resp = self._post({"dry_run": True})
        assert resp.status_code == 200

    def test_S03_no_confirmation_returns_422(self):
        resp = self._post({"dry_run": False})
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_S04_no_token_returns_422(self):
        resp = self._post({"dry_run": False, "apply_confirmed": True})
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_S05_invalid_token_returns_422(self):
        resp = self._post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": "bad-token", "requested_by": "op", "reason": "test",
        })
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_S06_missing_requested_by_returns_422(self):
        resp = self._post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": self.token, "reason": "test",
        })
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_S07_missing_reason_returns_422(self):
        resp = self._post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": self.token, "requested_by": "operator",
        })
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_S08_valid_confirmation_calls_mocked_engine(self):
        resp = self._post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": self.token,
            "requested_by": "operator",
            "reason": "P255D live smoke test — mock only",
        })
        assert resp.status_code == 200
        assert self.mock_engine.run.call_count == 1
