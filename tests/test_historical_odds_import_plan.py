"""
P7-C — Tests for historical_odds_import_plan.py
=================================================
執行 adapter contract 驗證測試。
所有測試均為 paper_only=True，無任何外部 API 呼叫。
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from wbc_backend.recommendation.odds_contract import (
    MlbOddsSnapshot,
    OddsContractError,
    OddsSourceType,
)
from wbc_backend.recommendation.historical_odds_import_plan import (
    HistoricalOddsImportConfig,
    OddsProviderType,
    OddsImportError,
    PaperOnlyViolationError,
    normalize_the_odds_api_payload,
    normalize_tsl_forward_payload,
    classify_source_type,
    normalize_to_utc,
    map_game_id,
    _snapshot_dedup_key,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GAME_START = datetime(2025, 7, 4, 23, 10, tzinfo=timezone.utc)
PREGAME_TS = datetime(2025, 7, 4, 21, 0, tzinfo=timezone.utc)   # 2h before start
CLOSING_TS = datetime(2025, 7, 4, 22, 30, tzinfo=timezone.utc)  # 40min before start
POSTGAME_TS = datetime(2025, 7, 5, 2, 0, tzinfo=timezone.utc)   # 3h after start


def make_toa_payload(
    game_id: str = "abc123",
    commence: str = "2025-07-04T23:10:00Z",
    away: str = "Boston Red Sox",
    home: str = "New York Yankees",
    last_update: str = "2025-07-04T21:00:00Z",
    odds_away: float = 2.10,
    odds_home: float = 1.75,
    book_key: str = "pinnacle",
    market_key: str = "h2h",
) -> dict:
    return {
        "id": game_id,
        "sport_key": "baseball_mlb",
        "commence_time": commence,
        "away_team": away,
        "home_team": home,
        "bookmakers": [
            {
                "key": book_key,
                "title": book_key.title(),
                "last_update": last_update,
                "markets": [
                    {
                        "key": market_key,
                        "last_update": last_update,
                        "outcomes": [
                            {"name": away, "price": odds_away},
                            {"name": home, "price": odds_home},
                        ],
                    }
                ],
            }
        ],
    }


def make_tsl_record(
    match_id: str = "3452364.1",
    fetched_at: str = "2026-03-13T03:30:16.039741Z",
    game_time: str = "2026-03-13T12:00:00+08:00",
    home_name: str = "洛德海洋",
    away_name: str = "西武獅",
    odds_home: str = "1.93",
    odds_away: str = "1.53",
) -> dict:
    return {
        "source": "TSL_BLOB3RD",
        "fetched_at": fetched_at,
        "match_id": match_id,
        "game_time": game_time,
        "home_team_name": home_name,
        "away_team_name": away_name,
        "markets": [
            {
                "marketCode": "MNL",
                "outcomes": [
                    {"outcomeName": away_name, "odds": odds_away},
                    {"outcomeName": home_name, "odds": odds_home},
                ],
            }
        ],
    }


DEFAULT_CONFIG = HistoricalOddsImportConfig(
    provider=OddsProviderType.THE_ODDS_API,
    paper_only=True,
    closing_window_sec=3600,
    pregame_min_sec=60,
)

TSL_CONFIG = HistoricalOddsImportConfig(
    provider=OddsProviderType.TSL_2026_FORWARD,
    paper_only=True,
)


# ---------------------------------------------------------------------------
# 1. Provider payload normalized to MlbOddsSnapshot
# ---------------------------------------------------------------------------

class TestProviderPayloadNormalization:
    def test_toa_payload_produces_snapshots(self):
        payload = make_toa_payload()
        snaps = normalize_the_odds_api_payload(payload, DEFAULT_CONFIG)
        assert len(snaps) == 2
        for s in snaps:
            assert isinstance(s, MlbOddsSnapshot)
            assert s.paper_only is True
            assert s.source_trace != ""
            assert s.decimal_odds >= 1.0

    def test_toa_market_code_mapped_correctly(self):
        payload = make_toa_payload(market_key="totals")
        # totals → OU with OVER/UNDER outcomes — adjust outcomes
        payload["bookmakers"][0]["markets"][0]["outcomes"] = [
            {"name": "Over", "price": 1.90},
            {"name": "Under", "price": 1.90},
        ]
        snaps = normalize_the_odds_api_payload(payload, DEFAULT_CONFIG)
        assert all(s.market == "OU" for s in snaps)
        sides = {s.side for s in snaps}
        assert "OVER" in sides or "UNDER" in sides

    def test_tsl_payload_produces_snapshots(self):
        record = make_tsl_record()
        game_start = datetime(2026, 3, 13, 4, 0, tzinfo=timezone.utc)  # UTC of 12:00 JST
        snaps = normalize_tsl_forward_payload(record, TSL_CONFIG, game_start)
        assert len(snaps) == 2
        for s in snaps:
            assert isinstance(s, MlbOddsSnapshot)
            assert s.paper_only is True
            assert "TSL" in s.source_trace

    def test_toa_source_trace_contains_required_fields(self):
        payload = make_toa_payload(game_id="ev_xyz", book_key="draftkings")
        snaps = normalize_the_odds_api_payload(payload, DEFAULT_CONFIG)
        for s in snaps:
            assert "TheOddsAPI v4 historical" in s.source_trace
            assert "ev_xyz" in s.source_trace
            assert "draftkings" in s.source_trace


# ---------------------------------------------------------------------------
# 2. Post-game timestamp blocked from PREGAME
# ---------------------------------------------------------------------------

class TestPostGameTimestampBlocking:
    def test_post_game_captured_at_becomes_post_game_proxy(self):
        """captured_at > game_start → POST_GAME_PROXY"""
        result = classify_source_type(
            captured_at_utc=POSTGAME_TS,
            game_start_utc=GAME_START,
        )
        assert result == OddsSourceType.POST_GAME_PROXY

    def test_post_game_proxy_snapshot_created_but_type_enforced(self):
        """payload with post-game timestamp produces POST_GAME_PROXY snapshots"""
        payload = make_toa_payload(
            commence="2025-07-04T23:10:00Z",
            last_update="2025-07-05T02:00:00Z",   # 3h after game
        )
        snaps = normalize_the_odds_api_payload(payload, DEFAULT_CONFIG)
        assert all(s.source_type == OddsSourceType.POST_GAME_PROXY for s in snaps)

    def test_post_game_proxy_not_pregame(self):
        result = classify_source_type(
            captured_at_utc=POSTGAME_TS,
            game_start_utc=GAME_START,
        )
        assert result != OddsSourceType.PREGAME

    def test_post_game_proxy_not_closing(self):
        result = classify_source_type(
            captured_at_utc=POSTGAME_TS,
            game_start_utc=GAME_START,
        )
        assert result != OddsSourceType.CLOSING


# ---------------------------------------------------------------------------
# 3. Missing timestamp becomes UNKNOWN
# ---------------------------------------------------------------------------

class TestMissingTimestampBecomeUnknown:
    def test_none_captured_at_returns_unknown(self):
        result = classify_source_type(
            captured_at_utc=None,
            game_start_utc=GAME_START,
        )
        assert result == OddsSourceType.UNKNOWN

    def test_toa_payload_missing_last_update_yields_unknown(self):
        payload = make_toa_payload(last_update="")
        # Patch: remove last_update entirely
        for bm in payload["bookmakers"]:
            bm.pop("last_update", None)
            for mkt in bm["markets"]:
                mkt.pop("last_update", None)
        snaps = normalize_the_odds_api_payload(payload, DEFAULT_CONFIG)
        assert all(s.source_type == OddsSourceType.UNKNOWN for s in snaps)

    def test_tsl_missing_fetched_at_yields_unknown(self):
        record = make_tsl_record(fetched_at="")
        game_start = GAME_START
        snaps = normalize_tsl_forward_payload(record, TSL_CONFIG, game_start)
        assert all(s.source_type == OddsSourceType.UNKNOWN for s in snaps)


# ---------------------------------------------------------------------------
# 4. Doubleheader game_number preserved
# ---------------------------------------------------------------------------

class TestDoubleheaderGameNumberPreserved:
    def test_game_number_2_appended_to_id(self):
        result = map_game_id(
            provider_game_id="dh_game",
            game_date="2025-07-04",
            away_team="BOS",
            home_team="NYY",
            game_number=2,
        )
        assert result.game_number == 2
        assert result.is_doubleheader is True
        assert "_G2" in result.game_id

    def test_game_number_1_no_suffix(self):
        result = map_game_id(
            provider_game_id="single",
            game_date="2025-07-04",
            away_team="BOS",
            home_team="NYY",
            game_number=1,
        )
        assert result.game_number == 1
        assert result.is_doubleheader is False
        assert "_G" not in result.game_id

    def test_gamePk_lookup_used_when_available(self):
        def mock_lookup(date, away, home, gnum):
            return 745678

        result = map_game_id(
            provider_game_id="ep_id",
            game_date="2025-07-04",
            away_team="BOS",
            home_team="NYY",
            game_number=1,
            gamepk_lookup_fn=mock_lookup,
        )
        assert result.gamePk == 745678
        assert "745678" in result.game_id
        assert result.mapping_method == "gamePk_lookup"


# ---------------------------------------------------------------------------
# 5. Invalid decimal odds blocked
# ---------------------------------------------------------------------------

class TestInvalidDecimalOddsBlocked:
    def test_odds_below_1_raises_import_error(self):
        payload = make_toa_payload(odds_away=0.5, odds_home=1.75)
        with pytest.raises(OddsImportError, match="Invalid decimal odds"):
            normalize_the_odds_api_payload(payload, DEFAULT_CONFIG)

    def test_odds_zero_raises_import_error(self):
        payload = make_toa_payload(odds_away=1.90, odds_home=0.0)
        with pytest.raises(OddsImportError, match="Invalid decimal odds"):
            normalize_the_odds_api_payload(payload, DEFAULT_CONFIG)

    def test_tsl_invalid_odds_string_raises(self):
        record = make_tsl_record(odds_home="not_a_number")
        with pytest.raises(OddsImportError, match="Invalid odds value"):
            normalize_tsl_forward_payload(record, TSL_CONFIG, GAME_START)

    def test_tsl_odds_below_1_raises(self):
        record = make_tsl_record(odds_home="0.5")
        with pytest.raises(OddsImportError, match="Decimal odds < 1.0"):
            normalize_tsl_forward_payload(record, TSL_CONFIG, GAME_START)

    def test_contract_rejects_snapshot_with_decimal_below_1(self):
        """MlbOddsSnapshot contract itself rejects odds < 1.0"""
        with pytest.raises(OddsContractError):
            MlbOddsSnapshot(
                game_id="G001",
                game_start_utc=GAME_START,
                captured_at_utc=PREGAME_TS,
                market="ML",
                side="HOME",
                decimal_odds=0.99,
                source="test",
                source_type=OddsSourceType.PREGAME,
                paper_only=True,
                source_trace="test trace",
            )


# ---------------------------------------------------------------------------
# 6. source_trace required
# ---------------------------------------------------------------------------

class TestSourceTraceRequired:
    def test_snapshot_without_source_trace_raises(self):
        with pytest.raises(OddsContractError):
            MlbOddsSnapshot(
                game_id="G001",
                game_start_utc=GAME_START,
                captured_at_utc=PREGAME_TS,
                market="ML",
                side="HOME",
                decimal_odds=2.00,
                source="test",
                source_type=OddsSourceType.PREGAME,
                paper_only=True,
                source_trace="",  # empty → should raise
            )

    def test_snapshot_with_source_trace_passes(self):
        snap = MlbOddsSnapshot(
            game_id="G001",
            game_start_utc=GAME_START,
            captured_at_utc=PREGAME_TS,
            market="ML",
            side="HOME",
            decimal_odds=2.00,
            source="test",
            source_type=OddsSourceType.PREGAME,
            paper_only=True,
            source_trace="TheOddsAPI v4 | event_id=abc123 | book=pinnacle",
        )
        assert snap.source_trace != ""


# ---------------------------------------------------------------------------
# 7. Duplicate snapshot handled deterministically
# ---------------------------------------------------------------------------

class TestDuplicateSnapshotHandling:
    def test_duplicate_snapshot_skipped(self):
        payload = make_toa_payload()
        seen = set()
        snaps1 = normalize_the_odds_api_payload(payload, DEFAULT_CONFIG, seen_dedup=seen)
        snaps2 = normalize_the_odds_api_payload(payload, DEFAULT_CONFIG, seen_dedup=seen)
        # Second pass should produce no new snapshots (all dedup'd)
        assert len(snaps2) == 0
        assert len(snaps1) == 2

    def test_different_timestamps_not_deduped(self):
        payload1 = make_toa_payload(last_update="2025-07-04T21:00:00Z")
        payload2 = make_toa_payload(last_update="2025-07-04T22:00:00Z")
        seen = set()
        snaps1 = normalize_the_odds_api_payload(payload1, DEFAULT_CONFIG, seen_dedup=seen)
        snaps2 = normalize_the_odds_api_payload(payload2, DEFAULT_CONFIG, seen_dedup=seen)
        # Different timestamps → different dedup keys → both accepted
        assert len(snaps1) == 2
        assert len(snaps2) == 2

    def test_dedup_key_is_deterministic(self):
        snap = MlbOddsSnapshot(
            game_id="G001",
            game_start_utc=GAME_START,
            captured_at_utc=PREGAME_TS,
            market="ML",
            side="HOME",
            decimal_odds=2.00,
            source="test",
            source_type=OddsSourceType.PREGAME,
            paper_only=True,
            source_trace="trace",
        )
        key1 = _snapshot_dedup_key(snap)
        key2 = _snapshot_dedup_key(snap)
        assert key1 == key2
        assert len(key1) == 16  # 16-char hex prefix


# ---------------------------------------------------------------------------
# 8. paper_only=false raises
# ---------------------------------------------------------------------------

class TestPaperOnlyEnforcement:
    def test_paper_only_false_in_toa_normalizer_raises(self):
        config = HistoricalOddsImportConfig(
            provider=OddsProviderType.THE_ODDS_API,
            paper_only=False,
        )
        payload = make_toa_payload()
        with pytest.raises(PaperOnlyViolationError):
            normalize_the_odds_api_payload(payload, config)

    def test_paper_only_false_in_tsl_normalizer_raises(self):
        config = HistoricalOddsImportConfig(
            provider=OddsProviderType.TSL_2026_FORWARD,
            paper_only=False,
        )
        record = make_tsl_record()
        with pytest.raises(PaperOnlyViolationError):
            normalize_tsl_forward_payload(record, config, GAME_START)

    def test_snapshot_paper_only_false_raises_contract_error(self):
        with pytest.raises(OddsContractError):
            MlbOddsSnapshot(
                game_id="G001",
                game_start_utc=GAME_START,
                captured_at_utc=PREGAME_TS,
                market="ML",
                side="HOME",
                decimal_odds=2.00,
                source="test",
                source_type=OddsSourceType.PREGAME,
                paper_only=False,
                source_trace="trace",
            )


# ---------------------------------------------------------------------------
# 9. Source type classification correctness
# ---------------------------------------------------------------------------

class TestSourceTypeClassification:
    def test_pregame_classified_correctly(self):
        result = classify_source_type(PREGAME_TS, GAME_START)
        assert result == OddsSourceType.PREGAME

    def test_closing_classified_correctly(self):
        result = classify_source_type(CLOSING_TS, GAME_START)
        assert result == OddsSourceType.CLOSING

    def test_exactly_at_game_start_is_closing(self):
        result = classify_source_type(GAME_START, GAME_START)
        assert result == OddsSourceType.CLOSING

    def test_one_second_before_game_start_is_closing(self):
        one_sec_before = GAME_START - timedelta(seconds=1)
        result = classify_source_type(one_sec_before, GAME_START, pregame_min_sec=60)
        # 1 second before < 60 second threshold → CLOSING
        assert result == OddsSourceType.CLOSING


# ---------------------------------------------------------------------------
# 10. Timezone normalization
# ---------------------------------------------------------------------------

class TestTimezoneNormalization:
    def test_naive_edt_normalized_to_utc(self):
        naive_edt = datetime(2025, 7, 4, 19, 10)  # 7:10 PM EDT = 23:10 UTC
        utc = normalize_to_utc(naive_edt, tz_hint="EDT")
        assert utc.tzinfo == timezone.utc
        assert utc.hour == 23

    def test_aware_datetime_passthrough(self):
        aware = datetime(2025, 7, 4, 23, 10, tzinfo=timezone.utc)
        result = normalize_to_utc(aware)
        assert result == aware

    def test_unknown_tz_raises(self):
        naive = datetime(2025, 7, 4, 19, 10)
        with pytest.raises(OddsImportError, match="Unknown timezone hint"):
            normalize_to_utc(naive, tz_hint="UNKNOWN_ZONE")
