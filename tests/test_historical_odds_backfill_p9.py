"""
Tests for P9-C: Historical Odds Backfill Readiness Gate
scripts/run_historical_odds_backfill_p9.py

硬性約束驗證：
- no api key → P9_BLOCKED_NEEDS_API_KEY
- api key exists but no ALLOW_SAMPLE_API_CALL=true → no external call
- --no-network default enforced
- sample payload normalization still works
- output paper_only=True
- POST_GAME_PROXY cannot pass as PREGAME/CLOSING
- missing closing line blocks CLV (via source_type check)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_historical_odds_backfill_p9 import (
    API_KEY_ENV_VAR,
    ALLOW_SAMPLE_API_CALL_ENV_VAR,
    ApiKeyMissingError,
    NetworkModeBlockedError,
    SampleApiCallNotAllowedError,
    _build_sample_toa_payload,
    assert_allow_sample_api_call,
    check_api_key_readiness,
    get_api_key,
    run_backfill_gate,
)
from wbc_backend.recommendation.odds_contract import OddsSourceType


# ── Helpers ───────────────────────────────────────────────────────────────────


def _clear_api_env(monkeypatch):
    monkeypatch.delenv(API_KEY_ENV_VAR, raising=False)
    monkeypatch.delenv(ALLOW_SAMPLE_API_CALL_ENV_VAR, raising=False)


# ── Test: No API Key → Blocked ────────────────────────────────────────────────


class TestNoApiKeyBlocked:
    def test_gate_status_blocked_when_no_key(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["gate_status"] == "P9_BLOCKED_NEEDS_API_KEY"

    def test_api_key_present_false_when_env_unset(self, monkeypatch):
        _clear_api_env(monkeypatch)
        status = check_api_key_readiness()
        assert status["api_key_present"] is False

    def test_get_api_key_returns_none_when_empty(self, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR, "")
        assert get_api_key() is None

    def test_get_api_key_returns_none_when_whitespace(self, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR, "   ")
        assert get_api_key() is None

    def test_live_call_raises_when_no_key_and_not_dry_run(self, monkeypatch):
        _clear_api_env(monkeypatch)
        with pytest.raises(ApiKeyMissingError):
            run_backfill_gate(
                season=2025, market="h2h",
                dry_run=False, sample_only=False, no_network=False,
                output_path=None,
            )

    def test_api_key_missing_raised_for_live_path(self, monkeypatch):
        _clear_api_env(monkeypatch)
        with pytest.raises((ApiKeyMissingError, NetworkModeBlockedError)):
            run_backfill_gate(
                season=2025, market="h2h",
                dry_run=False, sample_only=False, no_network=False,
                output_path=None,
            )


# ── Test: API key present but no ALLOW flag → no external call ────────────────


class TestApiKeyPresentNoAllowFlag:
    def test_no_allow_flag_assertion_error(self, monkeypatch):
        _clear_api_env(monkeypatch)
        monkeypatch.setenv(ALLOW_SAMPLE_API_CALL_ENV_VAR, "false")
        with pytest.raises(SampleApiCallNotAllowedError):
            assert_allow_sample_api_call()

    def test_allow_flag_unset_triggers_assertion(self, monkeypatch):
        _clear_api_env(monkeypatch)
        with pytest.raises(SampleApiCallNotAllowedError):
            assert_allow_sample_api_call()

    def test_allow_flag_true_passes(self, monkeypatch):
        monkeypatch.setenv(ALLOW_SAMPLE_API_CALL_ENV_VAR, "true")
        # Should not raise
        assert_allow_sample_api_call()

    def test_dry_run_with_key_but_no_flag_still_ok(self, monkeypatch):
        """dry_run=True bypasses the sample-only allow-flag gate entirely."""
        _clear_api_env(monkeypatch)
        monkeypatch.setenv(API_KEY_ENV_VAR, "fake_key_abc123")
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        # Key present, no allow flag, dry_run → should be SAMPLE_READY or similar
        assert result["live_api_called"] is False

    def test_live_api_called_false_in_dry_run(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["live_api_called"] is False


# ── Test: --no-network default enforced ──────────────────────────────────────


class TestNoNetworkDefault:
    def test_no_network_blocks_non_dry_run(self, monkeypatch):
        _clear_api_env(monkeypatch)
        with pytest.raises(NetworkModeBlockedError):
            run_backfill_gate(
                season=2025, market="h2h",
                dry_run=False, sample_only=False, no_network=True,
                output_path=None,
            )

    def test_no_network_with_dry_run_passes(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["mode"]["no_network"] is True
        assert result["live_api_called"] is False

    def test_mode_no_network_true_in_output(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["mode"]["no_network"] is True


# ── Test: Sample payload normalization works ──────────────────────────────────


class TestSamplePayloadNormalization:
    def test_sample_payload_has_bookmakers(self):
        payload = _build_sample_toa_payload("h2h")
        assert "bookmakers" in payload
        assert len(payload["bookmakers"]) >= 1

    def test_sample_payload_odds_above_one(self):
        payload = _build_sample_toa_payload("h2h")
        for bm in payload["bookmakers"]:
            for mkt in bm.get("markets", []):
                for outcome in mkt.get("outcomes", []):
                    assert outcome["price"] > 1.0

    def test_normalized_snapshots_returned(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["snapshots_count"] >= 1

    def test_normalized_snapshots_have_game_id(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        for snap in result["snapshots"]:
            assert "game_id" in snap
            assert snap["game_id"]


# ── Test: Output paper_only=True ──────────────────────────────────────────────


class TestOutputPaperOnly:
    def test_result_paper_only_true(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["paper_only"] is True

    def test_all_snapshots_paper_only(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["all_paper_only"] is True
        for snap in result["snapshots"]:
            assert snap["paper_only"] is True

    def test_production_write_false(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["production_write"] is False

    def test_output_written_to_file(self, monkeypatch, tmp_path):
        _clear_api_env(monkeypatch)
        out = tmp_path / "p9_test.json"
        run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=out,
        )
        assert out.exists()
        with open(out) as f:
            data = json.load(f)
        assert data["paper_only"] is True


# ── Test: POST_GAME_PROXY cannot pass as PREGAME/CLOSING ─────────────────────


class TestPostGameProxyGuard:
    def test_sample_payload_yields_pregame_not_proxy(self, monkeypatch):
        """Sample payload has pregame timestamps → source_type must be PREGAME."""
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        for snap in result["snapshots"]:
            assert snap["source_type"] == OddsSourceType.PREGAME.value

    def test_validation_post_game_proxy_misclassified_zero(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["validation"]["post_game_proxy_misclassified"] == 0
        assert result["validation"]["source_type_check"] == "PASS"

    def test_validation_source_type_check_pass(self, monkeypatch):
        _clear_api_env(monkeypatch)
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        assert result["validation"]["source_type_check"] == "PASS"


# ── Test: API Key env var check (never log key) ───────────────────────────────


class TestApiKeyEnvCheck:
    def test_check_api_key_readiness_returns_dict(self, monkeypatch):
        _clear_api_env(monkeypatch)
        status = check_api_key_readiness()
        assert "api_key_present" in status
        assert "api_key_env_var" in status

    def test_api_key_present_true_when_set(self, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR, "test_key_12345")
        status = check_api_key_readiness()
        assert status["api_key_present"] is True

    def test_result_does_not_contain_key_value(self, monkeypatch):
        monkeypatch.setenv(API_KEY_ENV_VAR, "secret_api_key_xyz")
        _clear_api_env(monkeypatch)
        monkeypatch.setenv(API_KEY_ENV_VAR, "secret_api_key_xyz")
        result = run_backfill_gate(
            season=2025, market="h2h",
            dry_run=True, sample_only=False, no_network=True,
            output_path=None,
        )
        result_str = json.dumps(result)
        assert "secret_api_key_xyz" not in result_str
