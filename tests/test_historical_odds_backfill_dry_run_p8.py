"""
P8-C Tests — Historical Odds Backfill Dry-Run

驗收條件：
- dry-run 不呼叫外部 API
- sample payload 可 normalize
- missing timestamp -> UNKNOWN
- post-game timestamp blocked from PREGAME
- invalid odds blocked
- output contains paper_only=true
- provider missing -> fail with clear reason
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone

from scripts.run_historical_odds_backfill_dry_run_p8 import (
    SUPPORTED_PROVIDERS,
    _build_sample_toa_payload,
    _build_sample_tsl_payload,
    _normalize_payload,
    run_dry_run,
)
from wbc_backend.recommendation.historical_odds_import_plan import (
    HistoricalOddsImportConfig,
    OddsImportError,
    OddsProviderType,
    PaperOnlyViolationError,
)
from wbc_backend.recommendation.odds_contract import OddsSourceType


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def default_config() -> HistoricalOddsImportConfig:
    return HistoricalOddsImportConfig(
        provider=OddsProviderType.THE_ODDS_API,
        paper_only=True,
        closing_window_sec=3600,
        pregame_min_sec=60,
        allow_unknown_ts=True,
        team_norm_table={},
    )


@pytest.fixture()
def tsl_config() -> HistoricalOddsImportConfig:
    return HistoricalOddsImportConfig(
        provider=OddsProviderType.TSL_2026_FORWARD,
        paper_only=True,
        closing_window_sec=3600,
        pregame_min_sec=60,
        allow_unknown_ts=True,
        team_norm_table={},
    )


@pytest.fixture()
def sample_game_start_utc() -> datetime:
    return datetime(2026, 5, 20, 4, 0, 0, tzinfo=timezone.utc)


# ── P8-C-1: dry-run does not call external API ────────────────────────────────

class TestDryRunNoExternalCall:
    def test_dry_run_false_sample_payload_raises(self):
        """live fetch (use_sample_payload=False) must raise in dry-run."""
        with pytest.raises(OddsImportError, match="Live API fetch is NOT permitted"):
            run_dry_run(
                provider="the_odds_api",
                season=2025,
                market="h2h",
                use_sample_payload=False,
                output_path=None,
            )

    def test_dry_run_sample_payload_succeeds_without_network(self):
        """Sample payload succeeds without any network call."""
        result = run_dry_run(
            provider="the_odds_api",
            season=2025,
            market="h2h",
            use_sample_payload=True,
            output_path=None,
        )
        assert result["live_api_called"] is False

    def test_tsl_sample_payload_succeeds_without_network(self):
        """TSL sample payload succeeds without any network call."""
        result = run_dry_run(
            provider="tsl_2026",
            season=2026,
            market="h2h",
            use_sample_payload=True,
            output_path=None,
        )
        assert result["live_api_called"] is False


# ── P8-C-2: sample payload can normalize ──────────────────────────────────────

class TestSamplePayloadNormalization:
    def test_toa_sample_produces_snapshots(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        snaps = _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)
        assert len(snaps) >= 1

    def test_toa_snapshot_paper_only_true(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        snaps = _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)
        assert all(s.paper_only is True for s in snaps)

    def test_tsl_sample_produces_snapshots(self, tsl_config, sample_game_start_utc):
        payload = _build_sample_tsl_payload("MNL")
        snaps = _normalize_payload(OddsProviderType.TSL_2026_FORWARD, payload, tsl_config, sample_game_start_utc)
        assert len(snaps) >= 1

    def test_toa_source_trace_populated(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        snaps = _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)
        assert all(bool(s.source_trace) for s in snaps)

    def test_toa_decimal_odds_valid(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        snaps = _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)
        assert all(s.decimal_odds >= 1.0 for s in snaps)

    def test_run_dry_run_result_has_snapshots(self):
        result = run_dry_run(
            provider="the_odds_api",
            season=2025,
            market="h2h",
            use_sample_payload=True,
            output_path=None,
        )
        assert result["snapshots_normalized"] >= 1
        assert len(result["snapshots"]) >= 1


# ── P8-C-3: missing timestamp → UNKNOWN ──────────────────────────────────────

class TestMissingTimestampYieldsUnknown:
    def test_toa_missing_last_update_yields_unknown(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        # Remove last_update from all bookmaker markets
        for bk in payload["bookmakers"]:
            bk.pop("last_update", None)
            for mkt in bk.get("markets", []):
                mkt.pop("last_update", None)
        snaps = _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)
        assert any(s.source_type == OddsSourceType.UNKNOWN for s in snaps)


# ── P8-C-4: post-game timestamp blocked from PREGAME ─────────────────────────

class TestPostGameTimestampBlocked:
    def test_post_game_snapshot_is_not_pregame(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        # Set last_update AFTER game start (2025-08-10T23:05:00Z → use 2025-08-11)
        post_game_ts = "2025-08-11T01:00:00Z"
        for bk in payload["bookmakers"]:
            bk["last_update"] = post_game_ts
            for mkt in bk.get("markets", []):
                mkt["last_update"] = post_game_ts
        snaps = _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)
        assert all(s.source_type != OddsSourceType.PREGAME for s in snaps)
        assert all(s.source_type != OddsSourceType.CLOSING for s in snaps)

    def test_post_game_snapshot_is_post_game_proxy(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        post_game_ts = "2025-08-11T01:00:00Z"
        for bk in payload["bookmakers"]:
            bk["last_update"] = post_game_ts
            for mkt in bk.get("markets", []):
                mkt["last_update"] = post_game_ts
        snaps = _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)
        assert all(s.source_type == OddsSourceType.POST_GAME_PROXY for s in snaps)


# ── P8-C-5: invalid odds blocked ─────────────────────────────────────────────

class TestInvalidOddsBlocked:
    def test_odds_below_1_raises(self, default_config):
        payload = _build_sample_toa_payload("h2h")
        payload["bookmakers"][0]["markets"][0]["outcomes"][0]["price"] = 0.5
        with pytest.raises(OddsImportError, match="Invalid decimal odds"):
            _normalize_payload(OddsProviderType.THE_ODDS_API, payload, default_config)

    def test_tsl_invalid_odds_string_raises(self, tsl_config, sample_game_start_utc):
        payload = _build_sample_tsl_payload("MNL")
        payload["markets"][0]["outcomes"][0]["odds"] = "N/A"
        with pytest.raises(OddsImportError):
            _normalize_payload(OddsProviderType.TSL_2026_FORWARD, payload, tsl_config, sample_game_start_utc)


# ── P8-C-6: output contains paper_only=true ───────────────────────────────────

class TestOutputPaperOnly:
    def test_result_paper_only_true(self):
        result = run_dry_run(
            provider="the_odds_api",
            season=2025,
            market="h2h",
            use_sample_payload=True,
            output_path=None,
        )
        assert result["paper_only"] is True

    def test_result_all_snapshots_paper_only_true(self):
        result = run_dry_run(
            provider="the_odds_api",
            season=2025,
            market="h2h",
            use_sample_payload=True,
            output_path=None,
        )
        assert all(s["paper_only"] is True for s in result["snapshots"])

    def test_validation_paper_only_all_true(self):
        result = run_dry_run(
            provider="the_odds_api",
            season=2025,
            market="h2h",
            use_sample_payload=True,
            output_path=None,
        )
        assert result["validation"]["paper_only_all_true"] is True

    def test_tsl_result_paper_only_true(self):
        result = run_dry_run(
            provider="tsl_2026",
            season=2026,
            market="h2h",
            use_sample_payload=True,
            output_path=None,
        )
        assert result["paper_only"] is True
        assert result["production_write"] is False


# ── P8-C-7: unknown provider raises with clear reason ────────────────────────

class TestProviderValidation:
    def test_unknown_provider_raises(self):
        with pytest.raises(OddsImportError, match="Unknown provider"):
            run_dry_run(
                provider="nonexistent_provider_xyz",
                season=2025,
                market="h2h",
                use_sample_payload=True,
                output_path=None,
            )

    def test_supported_providers_include_the_odds_api(self):
        assert "the_odds_api" in SUPPORTED_PROVIDERS

    def test_supported_providers_include_tsl(self):
        assert "tsl_2026" in SUPPORTED_PROVIDERS or "tsl" in SUPPORTED_PROVIDERS
