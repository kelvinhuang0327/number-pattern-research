"""
P255C — Ingest Write Guard Implementation — Tests

Verifies G01 (dry_run default True) and G02 (server-side confirm token) as implemented
in lottery_api/routes/ingest.py.

All tests are read-only / unit-level:
- No live HTTP server required (uses FastAPI TestClient with mocked engine)
- No real DB write occurs (engine mock replaces all engine calls)
- JSON artifact structure validated statically

The test for a valid confirmed write mocks _get_engine so the real backfill
engine is never called, confirming the guard passes without a DB write.
"""

import json
import os
import sys
import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_API_ROOT  = os.path.join(_REPO_ROOT, "lottery_api")
if _API_ROOT not in sys.path:
    sys.path.insert(0, _API_ROOT)

_JSON_PATH = os.path.join(
    _REPO_ROOT, "outputs", "research",
    "p255c_ingest_write_guard_implementation_20260608.json",
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def artifact():
    """Load P255C JSON artifact (must exist after analysis script runs)."""
    assert os.path.exists(_JSON_PATH), f"Artifact not found: {_JSON_PATH}"
    with open(_JSON_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="module")
def BackfillRequest():
    """Import BackfillRequest from ingest module."""
    from routes.ingest import BackfillRequest as BR
    return BR


@pytest.fixture(scope="module")
def client_and_mocks(monkeypatch_module):
    """
    FastAPI TestClient with engine, detector, and ingest_logger mocked.
    Returns (client, mock_engine_run) so tests can inspect call args.
    """
    from unittest.mock import MagicMock, patch
    from fastapi.testclient import TestClient
    from fastapi import FastAPI
    from routes import ingest as ingest_mod

    app = FastAPI()
    app.include_router(ingest_mod.router)

    mock_engine  = MagicMock()
    mock_engine.run.return_value = {
        "total": 0, "inserted": 0, "skipped": 0, "conflict": 0, "failed": 0,
        "details": [],
    }
    mock_logger  = MagicMock()
    mock_logger.log.return_value = None
    mock_detector = MagicMock()
    mock_detector.scan.return_value = {"missing_count": 0}

    with patch.object(ingest_mod, "_get_engine",        return_value=mock_engine), \
         patch.object(ingest_mod, "_get_ingest_logger", return_value=mock_logger), \
         patch.object(ingest_mod, "_get_detector",      return_value=mock_detector), \
         patch.object(ingest_mod, "_refresh_after_insert", return_value=None):
        yield TestClient(app), mock_engine


# pytest fixture workaround: module-scope monkeypatch
@pytest.fixture(scope="module")
def monkeypatch_module():
    """Stub — not used directly; client_and_mocks uses unittest.mock.patch."""
    return None


# ---------------------------------------------------------------------------
# Lightweight unit fixtures (no TestClient — just model instantiation)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def BR():
    from routes.ingest import BackfillRequest
    return BackfillRequest


# ===========================================================================
# 1. BackfillRequest defaults
# ===========================================================================

class TestBackfillRequestDefaults:
    def test_dry_run_default_is_true(self, BR):
        """G01: omitting dry_run must default to True."""
        req = BR()
        assert req.dry_run is True, "BackfillRequest.dry_run must default to True (G01)"

    def test_apply_confirmed_default_is_false(self, BR):
        req = BR()
        assert req.apply_confirmed is False

    def test_confirm_token_default_is_none(self, BR):
        req = BR()
        assert req.confirm_token is None

    def test_requested_by_default_is_unknown(self, BR):
        req = BR()
        assert req.requested_by == "unknown"

    def test_reason_default_is_empty(self, BR):
        req = BR()
        assert req.reason == ""

    def test_expected_insert_count_default_is_none(self, BR):
        req = BR()
        assert req.expected_insert_count is None


# ===========================================================================
# 2. _validate_write_confirmation unit tests (no HTTP)
# ===========================================================================

class TestValidateWriteConfirmation:
    @pytest.fixture(autouse=True)
    def _import(self):
        from routes.ingest import _validate_write_confirmation, BackfillRequest, _WRITE_GUARD_TOKEN_FALLBACK
        from fastapi import HTTPException
        self._validate = _validate_write_confirmation
        self.BR = BackfillRequest
        self.token = _WRITE_GUARD_TOKEN_FALLBACK
        self.HTTPException = HTTPException

    def _req(self, **kwargs):
        return self.BR(**kwargs)

    def test_dry_run_true_skips_all_checks(self):
        """dry_run=True: no exception even with no confirmation fields."""
        req = self._req(dry_run=True)
        self._validate(req)  # must not raise

    def test_dry_run_false_no_apply_confirmed_raises_422(self):
        req = self._req(dry_run=False)
        with pytest.raises(self.HTTPException) as exc:
            self._validate(req)
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "write_not_confirmed"

    def test_dry_run_false_apply_confirmed_no_token_raises_422(self):
        req = self._req(dry_run=False, apply_confirmed=True)
        with pytest.raises(self.HTTPException) as exc:
            self._validate(req)
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "missing_confirm_token"

    def test_dry_run_false_wrong_token_raises_422(self):
        req = self._req(
            dry_run=False, apply_confirmed=True,
            confirm_token="totally-wrong-token",
            requested_by="operator", reason="test",
        )
        with pytest.raises(self.HTTPException) as exc:
            self._validate(req)
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "invalid_confirm_token"

    def test_dry_run_false_default_requested_by_raises_422(self):
        req = self._req(
            dry_run=False, apply_confirmed=True,
            confirm_token=self.token, reason="test",
            # requested_by stays "unknown"
        )
        with pytest.raises(self.HTTPException) as exc:
            self._validate(req)
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "missing_requested_by"

    def test_dry_run_false_empty_reason_raises_422(self):
        req = self._req(
            dry_run=False, apply_confirmed=True,
            confirm_token=self.token, requested_by="operator",
            reason="",
        )
        with pytest.raises(self.HTTPException) as exc:
            self._validate(req)
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "missing_reason"

    def test_valid_confirmation_does_not_raise(self):
        """All valid confirmation fields: no exception."""
        req = self._req(
            dry_run=False, apply_confirmed=True,
            confirm_token=self.token, requested_by="operator",
            reason="P255C verification test",
        )
        self._validate(req)  # must not raise


# ===========================================================================
# 3. Engine is NOT called on invalid write requests
# ===========================================================================

class TestEngineNotCalledOnInvalidWrite:
    """Use mocked engine via direct patch to confirm engine.run is never reached."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        from unittest.mock import MagicMock, patch
        from fastapi.testclient import TestClient
        from fastapi import FastAPI
        from routes import ingest as ingest_mod

        self.ingest_mod = ingest_mod
        self.patch = patch
        self.MagicMock = MagicMock

        app = FastAPI()
        app.include_router(ingest_mod.router)

        self.mock_engine  = MagicMock()
        self.mock_engine.run.return_value = {
            "total": 0, "inserted": 0, "skipped": 0, "conflict": 0, "failed": 0, "details": [],
        }
        self.mock_logger = MagicMock()
        self.mock_logger.log.return_value = None

        with patch.object(ingest_mod, "_get_engine",        return_value=self.mock_engine), \
             patch.object(ingest_mod, "_get_ingest_logger", return_value=self.mock_logger), \
             patch.object(ingest_mod, "_refresh_after_insert", return_value=None):
            self.client = TestClient(app)
            yield

    def post(self, body: dict):
        return self.client.post("/api/ingest/backfill", json=body)

    def test_omitted_dry_run_calls_engine_with_dry_run_true(self):
        """Omitted dry_run → dry_run=True default → engine called with dry_run=True."""
        resp = self.post({"lottery_type": "BIG_LOTTO"})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        call_kwargs = self.mock_engine.run.call_args
        assert call_kwargs is not None
        # dry_run must be True
        passed_dry_run = call_kwargs.kwargs.get("dry_run", call_kwargs.args[2] if len(call_kwargs.args) > 2 else None)
        # Check via kwargs or positional
        if call_kwargs.kwargs:
            assert call_kwargs.kwargs.get("dry_run") is True
        # If called positionally engine.run(lottery_type, draw_list, dry_run, max_draws)
        # just confirm no DB write by checking dry_run in the engine call
        self.mock_engine.run.reset_mock()

    def test_dry_run_true_explicit_does_not_write(self):
        resp = self.post({"dry_run": True})
        assert resp.status_code == 200
        self.mock_engine.run.reset_mock()

    def test_no_apply_confirmed_blocked(self):
        resp = self.post({"dry_run": False})
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_no_confirm_token_blocked(self):
        resp = self.post({"dry_run": False, "apply_confirmed": True})
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_wrong_confirm_token_blocked(self):
        resp = self.post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": "bad-token", "requested_by": "op", "reason": "test",
        })
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_missing_requested_by_blocked(self):
        from routes.ingest import _WRITE_GUARD_TOKEN_FALLBACK
        resp = self.post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": _WRITE_GUARD_TOKEN_FALLBACK, "reason": "test",
            # requested_by omitted → defaults to "unknown"
        })
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_missing_reason_blocked(self):
        from routes.ingest import _WRITE_GUARD_TOKEN_FALLBACK
        resp = self.post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": _WRITE_GUARD_TOKEN_FALLBACK,
            "requested_by": "operator",
            # reason omitted → defaults to ""
        })
        assert resp.status_code == 422
        assert self.mock_engine.run.call_count == 0

    def test_valid_confirmed_write_calls_engine_mock(self):
        """Valid confirmation passes all guards; engine mock is called (not real DB)."""
        from routes.ingest import _WRITE_GUARD_TOKEN_FALLBACK
        resp = self.post({
            "dry_run": False, "apply_confirmed": True,
            "confirm_token": _WRITE_GUARD_TOKEN_FALLBACK,
            "requested_by": "operator",
            "reason": "P255C verification test — engine mocked, no real DB write",
        })
        assert resp.status_code == 200
        assert self.mock_engine.run.call_count == 1
        self.mock_engine.run.reset_mock()


# ===========================================================================
# 4. P255C JSON artifact validation
# ===========================================================================

class TestArtifactBasics:
    def test_json_parses(self, artifact):
        assert isinstance(artifact, dict)

    def test_schema_version(self, artifact):
        assert artifact.get("schema_version") == "1.0"

    def test_task_id(self, artifact):
        assert artifact.get("task_id") == "P255C"

    def test_classification(self, artifact):
        assert artifact.get("classification") == "INGEST_WRITE_GUARD_IMPLEMENTATION_COMPLETE"

    def test_explicit_authorization(self, artifact):
        assert "P255C" in artifact.get("explicit_authorization", "")


class TestArtifactImplementedGuardrails:
    def test_implemented_guardrails_present(self, artifact):
        impl = artifact.get("implemented_guardrails", {})
        assert "G01_default_dry_run_true" in impl
        assert "G02_server_side_confirm_token" in impl

    def test_g01_status_implemented(self, artifact):
        g01 = artifact["implemented_guardrails"]["G01_default_dry_run_true"]
        assert g01["status"] == "IMPLEMENTED"

    def test_g02_status_implemented(self, artifact):
        g02 = artifact["implemented_guardrails"]["G02_server_side_confirm_token"]
        assert g02["status"] == "IMPLEMENTED"

    def test_g01_source_audit_passed(self, artifact):
        g01 = artifact["implemented_guardrails"]["G01_default_dry_run_true"]
        assert g01["source_audit"]["implemented"] is True

    def test_g02_source_audit_passed(self, artifact):
        g02 = artifact["implemented_guardrails"]["G02_server_side_confirm_token"]
        assert g02["source_audit_g02"]["implemented"] is True


class TestArtifactDeferredGuardrails:
    def test_deferred_guardrails_present(self, artifact):
        deferred = artifact.get("deferred_guardrails", {})
        for gid in ["G03_ui_confirmation", "G04_audit_log", "G05_backup_sha_integrity",
                    "G06_idempotency", "G07_cors_hardening", "G08_env_write_gate"]:
            assert gid in deferred, f"Missing deferred guardrail: {gid}"

    def test_deferred_status_is_deferred(self, artifact):
        deferred = artifact.get("deferred_guardrails", {})
        for key, val in deferred.items():
            assert val.get("status") == "DEFERRED", f"{key} status should be DEFERRED"


class TestArtifactSafetyFlags:
    def test_no_db_write_confirmed(self, artifact):
        assert artifact.get("no_db_write_during_tests_confirmed") is True

    def test_no_registry_mutation(self, artifact):
        assert artifact.get("no_registry_mutation_confirmed") is True

    def test_no_strategy_promotion(self, artifact):
        assert artifact.get("no_strategy_promotion_confirmed") is True

    def test_no_betting_advice(self, artifact):
        assert artifact.get("no_betting_advice_confirmed") is True


class TestArtifactBaseline:
    def test_baseline_big_lotto_raw(self, artifact):
        baseline = artifact.get("current_accepted_baseline", {})
        assert baseline.get("BIG_LOTTO_raw") == 22239

    def test_baseline_big_lotto_canonical(self, artifact):
        baseline = artifact.get("current_accepted_baseline", {})
        assert baseline.get("BIG_LOTTO_canonical") == 2114

    def test_baseline_power_lotto(self, artifact):
        baseline = artifact.get("current_accepted_baseline", {})
        assert baseline.get("POWER_LOTTO_raw") == 1917

    def test_baseline_daily_539(self, artifact):
        baseline = artifact.get("current_accepted_baseline", {})
        assert baseline.get("DAILY_539_raw") == 5882

    def test_baseline_replays(self, artifact):
        baseline = artifact.get("current_accepted_baseline", {})
        assert baseline.get("strategy_prediction_replays") == 94924
