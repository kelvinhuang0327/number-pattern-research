"""MLB Live Source Adapter Selection and Integration Plan.

Defines:
  - SourceCandidate matrix (schedule / odds / result candidates)
  - Source contract schemas (MLBScheduleSourceContract,
    MLBOddsSourceContract, MLBResultSourceContract)
  - Source health rules
  - Odds normalization contract (references existing helpers)
  - Fallback strategy (today + replay modes)
  - Fixture governance rules
  - Integration plan (Phase Live-1 → Live-4)
  - Gate evaluation (7-value enum)

Purpose:
  This module is a PLANNING ARTIFACT only.
  It does NOT connect to any live API.
  It does NOT place any real bet.
  It does NOT write to any sportsbook.
  All outputs are paper-only / dry-run research documents.

Safety:
  PRODUCTION_MODIFIED      = False
  NO_REAL_BET              = True
  PAPER_ONLY               = True
  NO_PROFIT_CLAIM          = True
  NO_LIVE_API_CONNECTED    = True
  PLAN_ONLY                = True
"""
from __future__ import annotations

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import Any

# ─── Safety constants ─────────────────────────────────────────────────────────

PRODUCTION_MODIFIED: bool = False
NO_REAL_BET: bool = True
PAPER_ONLY: bool = True
NO_PROFIT_CLAIM: bool = True
NO_EDGE_CLAIM: bool = True
NO_AUTO_EXECUTION: bool = True
NO_LIVE_API_CONNECTED: bool = True
PLAN_ONLY: bool = True
DIAGNOSTIC_ONLY: bool = True
FIXTURE_NOT_PRODUCTION: bool = True

MODULE_VERSION: str = "mlb_live_source_plan_v1"
COMPLETION_MARKER: str = "MLB_LIVE_SOURCE_PLAN_VERIFIED"

# ─── Gate constants (7 valid) ─────────────────────────────────────────────────

MLB_LIVE_SOURCE_PLAN_READY: str = "MLB_LIVE_SOURCE_PLAN_READY"
MLB_LIVE_SOURCE_CONTRACT_READY: str = "MLB_LIVE_SOURCE_CONTRACT_READY"
MLB_LIVE_SOURCE_NEEDS_VENDOR_DECISION: str = "MLB_LIVE_SOURCE_NEEDS_VENDOR_DECISION"
MLB_LIVE_SOURCE_NEEDS_API_VERIFICATION: str = "MLB_LIVE_SOURCE_NEEDS_API_VERIFICATION"
MLB_LIVE_SOURCE_GOVERNANCE_RISK: str = "MLB_LIVE_SOURCE_GOVERNANCE_RISK"
MLB_LIVE_SOURCE_DATA_LIMITED: str = "MLB_LIVE_SOURCE_DATA_LIMITED"
MLB_LIVE_SOURCE_NOT_READY: str = "MLB_LIVE_SOURCE_NOT_READY"

VALID_GATES: frozenset[str] = frozenset({
    MLB_LIVE_SOURCE_PLAN_READY,
    MLB_LIVE_SOURCE_CONTRACT_READY,
    MLB_LIVE_SOURCE_NEEDS_VENDOR_DECISION,
    MLB_LIVE_SOURCE_NEEDS_API_VERIFICATION,
    MLB_LIVE_SOURCE_GOVERNANCE_RISK,
    MLB_LIVE_SOURCE_DATA_LIMITED,
    MLB_LIVE_SOURCE_NOT_READY,
})

# ─── Source type constants ────────────────────────────────────────────────────

SOURCE_TYPE_SCHEDULE: str = "schedule"
SOURCE_TYPE_ODDS: str = "odds"
SOURCE_TYPE_RESULT: str = "result"

VALID_SOURCE_TYPES: frozenset[str] = frozenset({
    SOURCE_TYPE_SCHEDULE,
    SOURCE_TYPE_ODDS,
    SOURCE_TYPE_RESULT,
})

# ─── Access method constants ──────────────────────────────────────────────────

ACCESS_REST_API: str = "rest_api"
ACCESS_WEBSOCKET: str = "websocket"
ACCESS_CSV_IMPORT: str = "csv_import"
ACCESS_FIXTURE_FILE: str = "fixture_file"
ACCESS_JSONL_ARTIFACT: str = "jsonl_artifact"
ACCESS_SCRAPING: str = "web_scraping"

# ─── Default paths ────────────────────────────────────────────────────────────

DEFAULT_PLAN_REPORT_DIR: str = "reports"
DEFAULT_BETTINGPLAN_DIR: str = "00-BettingPlan"


# ════════════════════════════════════════════════════════════════════════════
# SECTION A — Source Candidate Dataclass
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class SourceCandidate:
    """Represents a single data source candidate for schedule / odds / result."""
    source_id: str
    source_type: str               # schedule | odds | result
    source_name: str
    access_method: str             # rest_api | csv_import | fixture_file | ...
    official_or_third_party: str   # "official" | "third_party" | "internal"
    requires_api_key: bool
    cost_risk: str                 # "none" | "low" | "medium" | "high" | "unknown"
    rate_limit_risk: str           # "none" | "low" | "medium" | "high" | "unknown"
    terms_risk: str                # "none" | "low" | "medium" | "high" | "unknown"
    freshness_expected: str        # e.g. "real-time" | "5min" | "daily" | "historical"
    schema_fit_score: float        # 0.0–1.0; how well it maps to our contract
    reliability_score: float       # 0.0–1.0
    governance_risk: str           # "none" | "low" | "medium" | "high"
    production_readiness: str      # "ready" | "needs_verification" | "not_ready" | "blocked"
    recommended: bool
    requires_verification: bool    # True → human must confirm before use in prod
    rejection_reason: str | None   # if not recommended, why
    notes: str = ""


# ════════════════════════════════════════════════════════════════════════════
# SECTION B — Source Contract Dataclasses
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class MLBScheduleSourceContract:
    """Contract schema for an MLB schedule source."""
    contract_id: str = "mlb_schedule_source_contract_v1"
    required_fields: list[str] = field(default_factory=lambda: [
        "game_id",
        "game_date",
        "home_team",
        "away_team",
        "scheduled_start_time",
        "game_status",
    ])
    optional_fields: list[str] = field(default_factory=lambda: [
        "probable_home_pitcher",
        "probable_away_pitcher",
        "venue",
        "series_description",
        "doubleheader_flag",
        "broadcast_info",
    ])
    freshness_sla_minutes: int = 60
    allowed_missing_fields: list[str] = field(default_factory=lambda: [
        "probable_home_pitcher",
        "probable_away_pitcher",
        "broadcast_info",
    ])
    validation_rules: list[str] = field(default_factory=lambda: [
        "game_date must be ISO YYYY-MM-DD format",
        "game_id must be non-empty string",
        "home_team and away_team must be non-empty strings",
        "game_status must be one of: scheduled, live, final, postponed, cancelled, suspended",
        "scheduled_start_time must be ISO 8601 or None",
    ])
    unavailable_behavior: str = (
        "If source is unavailable: set source_unavailable_flag=True, "
        "do not generate advisory, trigger fallback to DATA_LIMITED"
    )
    fallback_behavior: str = (
        "Fallback order: live current source → manual CSV import → "
        "fixture (tests/dry-run only) → DATA_LIMITED"
    )
    governance_flags: dict[str, Any] = field(default_factory=lambda: {
        "paper_only": True,
        "no_real_bet": True,
        "fixture_not_production": True,
        "human_review_required_for_postponed": True,
    })


@dataclass
class MLBOddsSourceContract:
    """Contract schema for an MLB odds source."""
    contract_id: str = "mlb_odds_source_contract_v1"
    required_fields: list[str] = field(default_factory=lambda: [
        "game_id",
        "game_date",
        "home_moneyline_odds",
        "away_moneyline_odds",
        "source_timestamp",
    ])
    optional_fields: list[str] = field(default_factory=lambda: [
        "runline_spread",
        "runline_home_odds",
        "runline_away_odds",
        "total_line",
        "over_odds",
        "under_odds",
        "bookmaker_source",
        "closing_line_flag",
        "market_consensus_flag",
    ])
    freshness_sla_minutes: int = 30
    allowed_missing_fields: list[str] = field(default_factory=lambda: [
        "runline_spread",
        "runline_home_odds",
        "runline_away_odds",
        "total_line",
        "over_odds",
        "under_odds",
        "bookmaker_source",
        "closing_line_flag",
    ])
    validation_rules: list[str] = field(default_factory=lambda: [
        "home_moneyline_odds must be American odds integer (e.g. -140, +120)",
        "away_moneyline_odds must be American odds integer",
        "source_timestamp must be ISO 8601",
        "No-vig normalization: use normalize_two_way_no_vig(home_ml, away_ml)",
        "market_home_prob_no_vig must be in (0.0, 1.0)",
        "runline_spread if present must be float (typically ±1.5)",
    ])
    unavailable_behavior: str = (
        "If odds unavailable: set market_home_prob_no_vig=None, "
        "advisory must output PASS (no_model_prediction mode). "
        "Do not invent or estimate odds."
    )
    fallback_behavior: str = (
        "Fallback: live odds API → manual CSV import → "
        "no odds (PASS advisory only) → DATA_LIMITED"
    )
    normalization_contract: dict[str, Any] = field(default_factory=lambda: {
        "raw_odds_available": "bool — True if home+away moneyline present",
        "no_vig_probability_available": "bool — True if normalize_two_way_no_vig succeeded",
        "derived_probability_flag": "bool — True if prob was derived (not from direct prob source)",
        "bookmaker_source": "str | None — name/id of bookmaker if available",
        "closing_line_available": "bool — True if closing-line odds present",
        "odds_timestamp": "str | None — ISO 8601 timestamp of the odds snapshot",
        "normalization_function_used": "normalize_two_way_no_vig (orchestrator.mlb_current_sources)",
        "odds_conversion_function_used": "american_odds_to_implied_prob (orchestrator.mlb_current_sources)",
    })
    governance_flags: dict[str, Any] = field(default_factory=lambda: {
        "paper_only": True,
        "no_real_bet": True,
        "no_stake_sizing": True,
        "no_closing_line_exploitation": True,
        "requires_verification_before_live_use": True,
    })


@dataclass
class MLBResultSourceContract:
    """Contract schema for an MLB result source."""
    contract_id: str = "mlb_result_source_contract_v1"
    required_fields: list[str] = field(default_factory=lambda: [
        "game_id",
        "game_date",
        "final_home_score",
        "final_away_score",
        "game_status",
        "home_win",
    ])
    optional_fields: list[str] = field(default_factory=lambda: [
        "result_verified_at",
        "innings_played",
        "outs_recorded",
        "postponed_rescheduled_date",
    ])
    freshness_sla_minutes: int = 240
    allowed_missing_fields: list[str] = field(default_factory=lambda: [
        "result_verified_at",
        "innings_played",
        "outs_recorded",
        "postponed_rescheduled_date",
    ])
    validation_rules: list[str] = field(default_factory=lambda: [
        "game_status must be one of: final, postponed, cancelled, suspended",
        "home_win must be 0 or 1 for final games; None for postponed/cancelled",
        "final_home_score and final_away_score must be non-negative integers for final games",
        "Postponed games: home_win=None, no ledger result update",
        "Cancelled games: home_win=None, mark ledger entry as CANCELLED",
        "Suspended games: treat as PENDING until resumed final posted",
    ])
    unavailable_behavior: str = (
        "If result unavailable: ledger entries remain PENDING_REVIEW. "
        "Do not fabricate results. Do not mark as WON/LOST without confirmed data."
    )
    fallback_behavior: str = (
        "Fallback: live result API → manual CSV import → "
        "manual override (human-entered) → remain PENDING"
    )
    governance_flags: dict[str, Any] = field(default_factory=lambda: {
        "paper_only": True,
        "no_real_bet": True,
        "no_auto_result_fabrication": True,
        "human_review_required_for_suspended": True,
        "human_review_required_for_cancelled": True,
    })


# ════════════════════════════════════════════════════════════════════════════
# SECTION C — Source Health Rules
# ════════════════════════════════════════════════════════════════════════════


@dataclass
class SourceHealthRules:
    """Defines the health check rules for a source."""
    # Checks
    check_reachable: bool = True
    check_schema_valid: bool = True
    check_freshness_ok: bool = True
    check_total_games_count: bool = True
    check_missing_moneyline: bool = True
    check_missing_runline: bool = True
    check_missing_total: bool = True
    check_missing_result: bool = True

    # Thresholds
    min_games_count: int = 1
    max_missing_moneyline_pct: float = 0.5      # >50% missing → stale_data_flag
    max_missing_runline_pct: float = 0.8        # runline often absent, more tolerant
    max_missing_total_pct: float = 0.8
    max_missing_result_pct: float = 1.0         # result often not yet available pregame

    # Health gate outputs
    stale_data_flag_threshold_minutes: int = 120
    source_unavailable_on_zero_games: bool = True

    # Gate values
    gate_healthy: str = "SOURCE_HEALTH_OK"
    gate_stale: str = "SOURCE_HEALTH_STALE"
    gate_unavailable: str = "SOURCE_HEALTH_UNAVAILABLE"
    gate_schema_error: str = "SOURCE_HEALTH_SCHEMA_ERROR"
    gate_data_limited: str = "SOURCE_HEALTH_DATA_LIMITED"

    valid_health_gates: list[str] = field(default_factory=lambda: [
        "SOURCE_HEALTH_OK",
        "SOURCE_HEALTH_STALE",
        "SOURCE_HEALTH_UNAVAILABLE",
        "SOURCE_HEALTH_SCHEMA_ERROR",
        "SOURCE_HEALTH_DATA_LIMITED",
    ])

    def evaluate(
        self,
        reachable: bool,
        schema_valid: bool,
        freshness_minutes: float | None,
        total_games_count: int,
        missing_moneyline_count: int,
        missing_runline_count: int,
        missing_total_count: int,
        missing_result_count: int,
    ) -> dict[str, Any]:
        """Evaluate source health and return a health report dict."""
        stale_data_flag = False
        source_unavailable_flag = False
        fallback_required = False
        source_health_gate = self.gate_healthy

        if not reachable:
            source_unavailable_flag = True
            fallback_required = True
            source_health_gate = self.gate_unavailable
            return self._build_report(
                reachable=reachable,
                schema_valid=schema_valid,
                freshness_minutes=freshness_minutes,
                total_games_count=total_games_count,
                missing_moneyline_count=missing_moneyline_count,
                missing_runline_count=missing_runline_count,
                missing_total_count=missing_total_count,
                missing_result_count=missing_result_count,
                stale_data_flag=stale_data_flag,
                source_unavailable_flag=source_unavailable_flag,
                fallback_required=fallback_required,
                source_health_gate=source_health_gate,
            )

        if not schema_valid:
            source_health_gate = self.gate_schema_error
            fallback_required = True
            return self._build_report(
                reachable=reachable,
                schema_valid=schema_valid,
                freshness_minutes=freshness_minutes,
                total_games_count=total_games_count,
                missing_moneyline_count=missing_moneyline_count,
                missing_runline_count=missing_runline_count,
                missing_total_count=missing_total_count,
                missing_result_count=missing_result_count,
                stale_data_flag=stale_data_flag,
                source_unavailable_flag=source_unavailable_flag,
                fallback_required=fallback_required,
                source_health_gate=source_health_gate,
            )

        # Freshness check
        if freshness_minutes is not None and freshness_minutes > self.stale_data_flag_threshold_minutes:
            stale_data_flag = True

        # Zero games
        if total_games_count == 0 and self.source_unavailable_on_zero_games:
            source_health_gate = self.gate_data_limited
            fallback_required = True
        elif stale_data_flag:
            source_health_gate = self.gate_stale
            fallback_required = True
        else:
            # Check missing data percentages
            n = total_games_count
            if n > 0:
                ml_pct = missing_moneyline_count / n
                if ml_pct > self.max_missing_moneyline_pct:
                    source_health_gate = self.gate_data_limited
                    fallback_required = True

        return self._build_report(
            reachable=reachable,
            schema_valid=schema_valid,
            freshness_minutes=freshness_minutes,
            total_games_count=total_games_count,
            missing_moneyline_count=missing_moneyline_count,
            missing_runline_count=missing_runline_count,
            missing_total_count=missing_total_count,
            missing_result_count=missing_result_count,
            stale_data_flag=stale_data_flag,
            source_unavailable_flag=source_unavailable_flag,
            fallback_required=fallback_required,
            source_health_gate=source_health_gate,
        )

    def _build_report(self, **kwargs: Any) -> dict[str, Any]:
        return {
            **kwargs,
            "health_rules_version": "source_health_rules_v1",
        }


# ════════════════════════════════════════════════════════════════════════════
# SECTION D — Source Candidate Matrix
# ════════════════════════════════════════════════════════════════════════════


def build_source_candidate_matrix() -> list[SourceCandidate]:
    """
    Build the full source candidate matrix.
    All candidates are evaluated from a planning perspective only.
    No live API calls are made here.
    Candidates with requires_verification=True need human sign-off before prod use.
    """
    candidates: list[SourceCandidate] = []

    # ── Schedule Sources ──────────────────────────────────────────────────────

    candidates.append(SourceCandidate(
        source_id="sched_mlb_statsapi_v1",
        source_type=SOURCE_TYPE_SCHEDULE,
        source_name="MLB StatsAPI (statsapi.mlb.com)",
        access_method=ACCESS_REST_API,
        official_or_third_party="official",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="low",
        terms_risk="medium",
        freshness_expected="real-time",
        schema_fit_score=0.90,
        reliability_score=0.85,
        governance_risk="low",
        production_readiness="needs_verification",
        recommended=True,
        requires_verification=True,
        rejection_reason=None,
        notes=(
            "MLB StatsAPI (statsapi.mlb.com/api/v1/schedule) provides official "
            "schedule + game status. No key required. Terms: unofficial/public use "
            "allowed but ToS should be reviewed for commercial use. "
            "Rate limit: approximately 5–10 req/sec observed. "
            "Pitcher data available via /api/v1/game/{gamePk}/boxscore."
        ),
    ))

    candidates.append(SourceCandidate(
        source_id="sched_mlbdataapi_v1",
        source_type=SOURCE_TYPE_SCHEDULE,
        source_name="MLB Data API (via python-mlb-statsapi library)",
        access_method=ACCESS_REST_API,
        official_or_third_party="third_party",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="low",
        terms_risk="medium",
        freshness_expected="real-time",
        schema_fit_score=0.85,
        reliability_score=0.80,
        governance_risk="low",
        production_readiness="needs_verification",
        recommended=True,
        requires_verification=True,
        rejection_reason=None,
        notes=(
            "Python wrapper around MLB StatsAPI. "
            "Simplifies schedule/roster/pitcher queries. "
            "Dependency risk: library maintenance status unknown as of 2026."
        ),
    ))

    candidates.append(SourceCandidate(
        source_id="sched_manual_csv_v1",
        source_type=SOURCE_TYPE_SCHEDULE,
        source_name="Manual CSV Import (daily schedule)",
        access_method=ACCESS_CSV_IMPORT,
        official_or_third_party="internal",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="none",
        terms_risk="none",
        freshness_expected="daily",
        schema_fit_score=0.75,
        reliability_score=0.60,
        governance_risk="none",
        production_readiness="ready",
        recommended=False,
        requires_verification=False,
        rejection_reason="Manual process; not suitable for automated daily pipeline without human operator",
        notes="Fallback option when API unavailable. Requires human to prepare CSV per contract schema.",
    ))

    candidates.append(SourceCandidate(
        source_id="sched_fixture_v1",
        source_type=SOURCE_TYPE_SCHEDULE,
        source_name="Fixture Source (local JSON test file)",
        access_method=ACCESS_FIXTURE_FILE,
        official_or_third_party="internal",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="none",
        terms_risk="none",
        freshness_expected="static",
        schema_fit_score=0.95,
        reliability_score=1.0,
        governance_risk="none",
        production_readiness="not_ready",
        recommended=False,
        requires_verification=False,
        rejection_reason=(
            "FIXTURE_NOT_PRODUCTION: fixture is for tests / local dry-run / "
            "schema validation / demo only. Must never be used as production advisory source."
        ),
        notes="data/fixtures/mlb_current_source_sample_20260507.json",
    ))

    # ── Odds Sources ──────────────────────────────────────────────────────────

    candidates.append(SourceCandidate(
        source_id="odds_theoddsapi_v2",
        source_type=SOURCE_TYPE_ODDS,
        source_name="The Odds API (the-odds-api.com)",
        access_method=ACCESS_REST_API,
        official_or_third_party="third_party",
        requires_api_key=True,
        cost_risk="medium",
        rate_limit_risk="medium",
        terms_risk="low",
        freshness_expected="5min",
        schema_fit_score=0.85,
        reliability_score=0.80,
        governance_risk="low",
        production_readiness="needs_verification",
        recommended=True,
        requires_verification=True,
        rejection_reason=None,
        notes=(
            "Commercial API providing aggregated bookmaker odds (ML/RL/Total). "
            "Supports multiple bookmakers (DraftKings, FanDuel, BetMGM, etc.). "
            "Free tier: 500 requests/month. Paid: ~500-2500 req/month per plan. "
            "Suitable for pre-game odds. API key required. Terms: commercial use OK with subscription. "
            "REQUIRES_VERIFICATION: pricing, rate limits, available markets."
        ),
    ))

    candidates.append(SourceCandidate(
        source_id="odds_sportradar_v1",
        source_type=SOURCE_TYPE_ODDS,
        source_name="Sportradar Odds API",
        access_method=ACCESS_REST_API,
        official_or_third_party="third_party",
        requires_api_key=True,
        cost_risk="high",
        rate_limit_risk="low",
        terms_risk="low",
        freshness_expected="real-time",
        schema_fit_score=0.90,
        reliability_score=0.90,
        governance_risk="low",
        production_readiness="needs_verification",
        recommended=False,
        requires_verification=True,
        rejection_reason=(
            "High cost — enterprise pricing. Not appropriate for research/quant phase. "
            "Revisit if production deployment is approved."
        ),
        notes=(
            "Sportradar is a leading sports data provider. "
            "Enterprise pricing typically $thousands/month. "
            "Full ML/RL/Total coverage, high reliability. "
            "Not cost-appropriate for current research phase."
        ),
    ))

    candidates.append(SourceCandidate(
        source_id="odds_actionnetwork_scrape_v1",
        source_type=SOURCE_TYPE_ODDS,
        source_name="Action Network (web scraping)",
        access_method=ACCESS_SCRAPING,
        official_or_third_party="third_party",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="high",
        terms_risk="high",
        freshness_expected="variable",
        schema_fit_score=0.50,
        reliability_score=0.40,
        governance_risk="high",
        production_readiness="blocked",
        recommended=False,
        requires_verification=False,
        rejection_reason=(
            "GOVERNANCE_RISK: Web scraping violates Action Network ToS. "
            "High fragility (HTML structure changes). "
            "Not a viable production solution. "
            "Listed for awareness only — must not be used."
        ),
        notes=(
            "⚠️ SCRAPING RISK: Terms of Service likely prohibit scraping. "
            "HTML structure changes frequently. "
            "Marked as BLOCKED — must not be used in production pipeline."
        ),
    ))

    candidates.append(SourceCandidate(
        source_id="odds_manual_csv_v1",
        source_type=SOURCE_TYPE_ODDS,
        source_name="Manual CSV Import (pre-game odds)",
        access_method=ACCESS_CSV_IMPORT,
        official_or_third_party="internal",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="none",
        terms_risk="none",
        freshness_expected="daily",
        schema_fit_score=0.70,
        reliability_score=0.55,
        governance_risk="none",
        production_readiness="ready",
        recommended=False,
        requires_verification=False,
        rejection_reason="Manual process; not suitable for automated pipeline",
        notes=(
            "Fallback option. Human operator records opening-line or closing-line "
            "odds to CSV per contract schema. "
            "Acceptable for occasional use; not for continuous daily automation."
        ),
    ))

    candidates.append(SourceCandidate(
        source_id="odds_fixture_v1",
        source_type=SOURCE_TYPE_ODDS,
        source_name="Fixture Odds Source (embedded in fixture file)",
        access_method=ACCESS_FIXTURE_FILE,
        official_or_third_party="internal",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="none",
        terms_risk="none",
        freshness_expected="static",
        schema_fit_score=0.95,
        reliability_score=1.0,
        governance_risk="none",
        production_readiness="not_ready",
        recommended=False,
        requires_verification=False,
        rejection_reason=(
            "FIXTURE_NOT_PRODUCTION: odds embedded in fixture file are static test data. "
            "Must never be treated as real market odds."
        ),
        notes="Fixture file includes sample odds for adapter schema testing only.",
    ))

    # ── Result Sources ────────────────────────────────────────────────────────

    candidates.append(SourceCandidate(
        source_id="result_mlb_statsapi_v1",
        source_type=SOURCE_TYPE_RESULT,
        source_name="MLB StatsAPI — Game Result (statsapi.mlb.com/linescore)",
        access_method=ACCESS_REST_API,
        official_or_third_party="official",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="low",
        terms_risk="medium",
        freshness_expected="real-time",
        schema_fit_score=0.90,
        reliability_score=0.85,
        governance_risk="low",
        production_readiness="needs_verification",
        recommended=True,
        requires_verification=True,
        rejection_reason=None,
        notes=(
            "MLB StatsAPI provides final score + game status via "
            "/api/v1/game/{gamePk}/linescore. "
            "Official source. No key required. Same ToS considerations as schedule. "
            "home_win can be derived from final scores. "
            "Handles postponed/cancelled via game_status field."
        ),
    ))

    candidates.append(SourceCandidate(
        source_id="result_manual_csv_v1",
        source_type=SOURCE_TYPE_RESULT,
        source_name="Manual CSV Import (game results)",
        access_method=ACCESS_CSV_IMPORT,
        official_or_third_party="internal",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="none",
        terms_risk="none",
        freshness_expected="daily",
        schema_fit_score=0.75,
        reliability_score=0.60,
        governance_risk="none",
        production_readiness="ready",
        recommended=False,
        requires_verification=False,
        rejection_reason="Manual process only; acceptable as emergency fallback",
        notes="Human operator enters final scores after games complete.",
    ))

    candidates.append(SourceCandidate(
        source_id="result_replay_artifact_v1",
        source_type=SOURCE_TYPE_RESULT,
        source_name="Historical Replay Artifact (prediction JSONL)",
        access_method=ACCESS_JSONL_ARTIFACT,
        official_or_third_party="internal",
        requires_api_key=False,
        cost_risk="none",
        rate_limit_risk="none",
        terms_risk="none",
        freshness_expected="historical",
        schema_fit_score=0.90,
        reliability_score=1.0,
        governance_risk="none",
        production_readiness="ready",
        recommended=False,
        requires_verification=False,
        rejection_reason="Historical only — cannot provide today-mode results",
        notes=(
            "data/mlb_2025/derived/mlb_2025_per_game_predictions_phase56_sp_bullpen_context_v1.jsonl "
            "Contains home_win for 2025 season replay. "
            "Used for replay mode pipeline validation only."
        ),
    ))

    return candidates


# ════════════════════════════════════════════════════════════════════════════
# SECTION E — Odds Normalization Contract
# ════════════════════════════════════════════════════════════════════════════


def build_odds_normalization_contract() -> dict[str, Any]:
    """
    Define the odds normalization contract.
    References existing functions in orchestrator.mlb_current_sources.
    Does NOT re-implement them.
    """
    return {
        "contract_id": "mlb_odds_normalization_contract_v1",
        "existing_functions": {
            "american_odds_to_implied_prob": {
                "module": "orchestrator.mlb_current_sources",
                "signature": "american_odds_to_implied_prob(odds: float) -> float",
                "description": (
                    "Converts American odds to raw implied probability. "
                    "Positive (underdog): 100/(odds+100). "
                    "Negative (favorite): |odds|/(|odds|+100)."
                ),
                "status": "implemented_and_tested",
            },
            "normalize_two_way_no_vig": {
                "module": "orchestrator.mlb_current_sources",
                "signature": "normalize_two_way_no_vig(home_ml: float, away_ml: float) -> tuple[float, float]",
                "description": (
                    "Removes bookmaker vig from two-way market. "
                    "Divides each raw implied prob by total overround. "
                    "Returns (no_vig_home_prob, no_vig_away_prob)."
                ),
                "status": "implemented_and_tested",
            },
        },
        "output_fields": {
            "raw_odds_available": "bool — True if home + away moneyline American odds present",
            "no_vig_probability_available": "bool — True if normalize_two_way_no_vig succeeded",
            "derived_probability_flag": "bool — True if probability was derived (not raw)",
            "bookmaker_source": "str | None — bookmaker name/id if available",
            "closing_line_available": "bool — True if closing-line snapshot present",
            "odds_timestamp": "str | None — ISO 8601 timestamp of odds snapshot",
            "market_home_prob_no_vig": "float — no-vig home win probability",
            "market_away_prob_no_vig": "float — no-vig away win probability (= 1 - home)",
        },
        "governance": {
            "no_stake_sizing": True,
            "no_vig_removal_does_not_imply_edge": True,
            "derived_probs_are_estimates_not_true_probabilities": True,
            "closing_line_value_not_computed_in_current_phase": True,
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# SECTION F — Fallback Strategy
# ════════════════════════════════════════════════════════════════════════════


def build_fallback_strategy() -> dict[str, Any]:
    """
    Define the fallback priority strategy for today and replay modes.
    """
    return {
        "strategy_id": "mlb_live_source_fallback_v1",
        "today_mode_fallback_priority": [
            {
                "priority": 1,
                "source": "live_current_source",
                "condition": "source reachable, schema valid, freshness OK",
                "action": "use for advisory + ledger",
            },
            {
                "priority": 2,
                "source": "manual_csv_import",
                "condition": "live source unavailable; human operator provides CSV",
                "action": "use for advisory + ledger; flag as manual_import=True",
            },
            {
                "priority": 3,
                "source": "fixture_source",
                "condition": "ONLY if explicitly allowed (dry-run / schema-test / demo); NEVER for production",
                "action": "use for schema validation and dry-run only; fixture_not_production=True",
            },
            {
                "priority": 4,
                "source": "replay_source",
                "condition": "historical data only; date must be in historical range",
                "action": "use for replay mode advisory; flag as today_schedule_unavailable=True",
            },
            {
                "priority": 5,
                "source": "DATA_LIMITED",
                "condition": "all sources exhausted or unavailable",
                "action": "do not generate advisory; return gate=MLB_SCHEDULER_DATA_LIMITED",
            },
        ],
        "replay_mode_fallback_priority": [
            {
                "priority": 1,
                "source": "historical_prediction_artifact",
                "condition": "date in JSONL, home_win available",
                "action": "full replay: advisory + ledger + result review",
            },
            {
                "priority": 2,
                "source": "historical_ledger_review_snapshot",
                "condition": "ledger JSONL exists; reviewed_snapshot available",
                "action": "review-only mode; no new advisory",
            },
            {
                "priority": 3,
                "source": "DATA_LIMITED",
                "condition": "date not in historical data",
                "action": "return gate=MLB_LIVE_SOURCE_DATA_LIMITED",
            },
        ],
        "fixture_governance_rules": {
            "allowed_uses": [
                "unit tests",
                "local dry-run",
                "schema contract validation",
                "demo / documentation",
                "adapter integration testing",
            ],
            "forbidden_uses": [
                "production advisory (real advisory treated as live)",
                "real-money recommendation",
                "live source readiness claim",
                "override of live source in production pipeline",
                "bankroll / stake sizing calculation",
            ],
            "enforcement": (
                "FIXTURE_NOT_PRODUCTION=True must be set on all fixture-sourced responses. "
                "Scheduler gate must not reach MLB_DAILY_SCHEDULER_READY when fixture source is active."
            ),
        },
    }


# ════════════════════════════════════════════════════════════════════════════
# SECTION G — Integration Plan (Phase Live-1 → Live-4)
# ════════════════════════════════════════════════════════════════════════════


def build_integration_plan() -> list[dict[str, Any]]:
    """
    Define the integration plan for next-phase live source implementation.
    4 phases: Live-1 (schedule), Live-2 (odds), Live-3 (result), Live-4 (full daily).
    """
    phases: list[dict[str, Any]] = [
        {
            "phase_id": "Live-1",
            "phase_name": "Schedule Source Adapter",
            "goal": (
                "Implement a live schedule source adapter that fetches today's MLB schedule "
                "from MLB StatsAPI (or manual CSV fallback). "
                "Validates schema contract. No odds dependency."
            ),
            "files_to_modify": [
                "orchestrator/mlb_current_sources.py",
                "data/fixtures/mlb_current_source_sample_20260507.json",
            ],
            "files_to_create": [
                "orchestrator/mlb_schedule_source_adapter.py",
                "tests/test_mlb_schedule_source_adapter.py",
                "data/fixtures/mlb_schedule_source_test.json",
            ],
            "tests_to_add": [
                "test_mlb_statsapi_schedule_fetch_contract",
                "test_schedule_schema_validation_required_fields",
                "test_schedule_source_health_probe",
                "test_schedule_fallback_to_csv_on_unavailable",
                "test_fixture_not_used_as_production_schedule",
                "test_postponed_game_handling",
            ],
            "acceptance_criteria": [
                "Adapter returns list of schedule rows matching MLBScheduleSourceContract",
                "All required fields present or explicit unavailable flags set",
                "Source health gate evaluates correctly (OK / STALE / UNAVAILABLE)",
                "Fixture source returns FIXTURE_NOT_PRODUCTION flag",
                "Postponed/cancelled games handled without exception",
                "All 6 new tests pass",
                "No regression in existing 1086+ tests",
            ],
            "rollback_plan": (
                "Revert orchestrator/mlb_schedule_source_adapter.py to previous version "
                "or delete if newly created. "
                "Fixture source remains available for testing. "
                "mlb_daily_scheduler.py already handles fixture fallback."
            ),
            "governance_guard": (
                "PRODUCTION_MODIFIED=False throughout. "
                "Fixture source must not bypass production pipeline. "
                "Any live API fetch must be read-only."
            ),
        },
        {
            "phase_id": "Live-2",
            "phase_name": "Odds Source Adapter",
            "goal": (
                "Implement an odds source adapter that normalizes moneyline/runline/total "
                "from a verified API (e.g. The Odds API). "
                "Applies american_odds_to_implied_prob + normalize_two_way_no_vig. "
                "Produces source health report per MLBOddsSourceContract."
            ),
            "files_to_modify": [
                "orchestrator/mlb_current_sources.py",
                "orchestrator/mlb_live_source_plan.py",
            ],
            "files_to_create": [
                "orchestrator/mlb_odds_source_adapter.py",
                "tests/test_mlb_odds_source_adapter.py",
                "data/fixtures/mlb_odds_source_test.json",
            ],
            "tests_to_add": [
                "test_odds_normalization_moneyline",
                "test_odds_normalization_no_vig",
                "test_odds_schema_validation_required_fields",
                "test_odds_source_health_missing_moneyline_threshold",
                "test_odds_fallback_to_csv_on_unavailable",
                "test_odds_fixture_not_production",
                "test_runline_optional_field_handling",
                "test_total_optional_field_handling",
            ],
            "acceptance_criteria": [
                "Adapter normalizes moneyline to no-vig probability using existing functions",
                "market_home_prob_no_vig in (0.0, 1.0) for all valid inputs",
                "Missing runline/total fields handled without exception",
                "Source health gate triggers correctly on >50% missing moneyline",
                "No stake_sizing field in any output",
                "All 8 new tests pass",
                "No regression in existing tests",
            ],
            "rollback_plan": (
                "Delete orchestrator/mlb_odds_source_adapter.py if newly created. "
                "Advisory falls back to market_home_prob_no_vig=None → PASS advisory."
            ),
            "governance_guard": (
                "No stake sizing. No closing line value calculation. "
                "odds_normalization_contract_v1 enforced. "
                "API key must be stored in .env — never hardcoded. "
                "Scraping (ACTION_NETWORK) is blocked — must not be implemented."
            ),
        },
        {
            "phase_id": "Live-3",
            "phase_name": "Result Source Adapter + Auto Post-game Review",
            "goal": (
                "Implement a result source adapter that fetches final scores from MLB StatsAPI "
                "and triggers automatic post-game ledger review. "
                "Handles postponed/cancelled/suspended per MLBResultSourceContract. "
                "Writes reviewed snapshot."
            ),
            "files_to_modify": [
                "orchestrator/mlb_result_review.py",
                "orchestrator/mlb_daily_scheduler.py",
            ],
            "files_to_create": [
                "orchestrator/mlb_result_source_adapter.py",
                "tests/test_mlb_result_source_adapter.py",
                "data/fixtures/mlb_result_source_test.json",
            ],
            "tests_to_add": [
                "test_result_source_final_game_schema",
                "test_result_source_postponed_handling",
                "test_result_source_cancelled_handling",
                "test_result_source_home_win_derivation",
                "test_result_source_health_probe",
                "test_auto_review_trigger_on_final_result",
                "test_no_result_fabrication_on_pending",
                "test_ledger_remains_pending_on_suspended",
            ],
            "acceptance_criteria": [
                "Adapter returns final scores matching MLBResultSourceContract",
                "home_win correctly derived from final scores",
                "Postponed games: home_win=None, ledger entries remain PENDING",
                "Cancelled games: ledger entries marked CANCELLED",
                "Auto post-game review triggers for FINAL games",
                "All 8 new tests pass",
                "No regression in existing tests",
            ],
            "rollback_plan": (
                "Delete orchestrator/mlb_result_source_adapter.py if newly created. "
                "Scheduler falls back to manual result ingestion path. "
                "Ledger entries remain PENDING — no data loss."
            ),
            "governance_guard": (
                "No result fabrication. "
                "no_auto_result_fabrication=True enforced. "
                "human_review_required for suspended/cancelled games. "
                "LEDGER_OVERWRITE_BLOCKED=True must remain throughout."
            ),
        },
        {
            "phase_id": "Live-4",
            "phase_name": "Daily Scheduler Integration + API Status + Source Freshness Dashboard",
            "goal": (
                "Integrate live schedule/odds/result adapters into mlb_daily_scheduler.py. "
                "Add API status endpoint for source freshness. "
                "Build source health dashboard (JSON + markdown). "
                "Full pipeline: live schedule → live odds → advisory → ledger → "
                "live result → post-game review → failure notes → manifest."
            ),
            "files_to_modify": [
                "orchestrator/mlb_daily_scheduler.py",
                "orchestrator/mlb_advisory_api.py",
                "scripts/run_mlb_daily_scheduler.py",
            ],
            "files_to_create": [
                "orchestrator/mlb_source_health_dashboard.py",
                "tests/test_mlb_source_health_dashboard.py",
            ],
            "tests_to_add": [
                "test_daily_scheduler_live_source_integration",
                "test_api_status_endpoint_live_source_health",
                "test_source_freshness_dashboard_output",
                "test_scheduler_gate_upgrades_on_live_source",
                "test_scheduler_falls_back_on_live_unavailable",
                "test_full_pipeline_live_schedule_odds_result",
            ],
            "acceptance_criteria": [
                "Scheduler gate reaches MLB_DAILY_SCHEDULER_READY with live sources",
                "API status endpoint returns source_health per source type",
                "Source freshness dashboard JSON + markdown generated",
                "Fallback to DATA_LIMITED when all live sources unavailable",
                "Completion marker MLB_DAILY_SCHEDULER_API_MVP_VERIFIED preserved",
                "All 6 new tests pass",
                "No regression in existing tests",
            ],
            "rollback_plan": (
                "Revert orchestrator/mlb_daily_scheduler.py to current version (scheduler v1). "
                "Fixture-based and replay-based pipelines remain operational. "
                "Gate reverts to MLB_SCHEDULER_DATA_LIMITED / MLB_SCHEDULER_API_MVP_READY."
            ),
            "governance_guard": (
                "NO_REAL_BET=True throughout. "
                "PRODUCTION_MODIFIED=False throughout. "
                "No stake sizing in any new API endpoint. "
                "Live source freshness checks must not bypass DATA_LIMITED gate. "
                "MLB_LIVE_SOURCE_PLAN_VERIFIED must be in Phase Live-4 report."
            ),
        },
    ]
    return phases


# ════════════════════════════════════════════════════════════════════════════
# SECTION H — Gate Evaluation
# ════════════════════════════════════════════════════════════════════════════


def evaluate_live_source_gate(
    candidates: list[SourceCandidate],
    schedule_contract: MLBScheduleSourceContract,
    odds_contract: MLBOddsSourceContract,
    result_contract: MLBResultSourceContract,
    fallback_strategy: dict[str, Any],
    integration_plan: list[dict[str, Any]],
) -> tuple[str, str]:
    """
    Evaluate and return (gate, rationale).
    Conservative: if any odds API candidate requires_verification → NEEDS_API_VERIFICATION.
    If contracts complete + plan ready but vendor pending → NEEDS_VENDOR_DECISION.
    """
    # Check for governance risks (scraping candidates recommended)
    scraping_recommended = any(
        c.access_method == ACCESS_SCRAPING and c.recommended
        for c in candidates
    )
    if scraping_recommended:
        return (
            MLB_LIVE_SOURCE_GOVERNANCE_RISK,
            "Scraping candidate marked recommended — governance risk. Must be blocked.",
        )

    # Check candidate coverage
    has_schedule = any(c.source_type == SOURCE_TYPE_SCHEDULE for c in candidates)
    has_odds = any(c.source_type == SOURCE_TYPE_ODDS for c in candidates)
    has_result = any(c.source_type == SOURCE_TYPE_RESULT for c in candidates)

    if not (has_schedule and has_odds and has_result):
        return (
            MLB_LIVE_SOURCE_NOT_READY,
            "Missing candidates in one or more source types (schedule / odds / result)",
        )

    # Check contracts
    if not schedule_contract.required_fields:
        return (MLB_LIVE_SOURCE_NOT_READY, "Schedule contract missing required_fields")
    if not odds_contract.required_fields:
        return (MLB_LIVE_SOURCE_NOT_READY, "Odds contract missing required_fields")
    if not result_contract.required_fields:
        return (MLB_LIVE_SOURCE_NOT_READY, "Result contract missing required_fields")

    # Check integration plan completeness
    if len(integration_plan) < 4:
        return (MLB_LIVE_SOURCE_NOT_READY, "Integration plan must have at least 4 phases")

    for phase in integration_plan:
        if not phase.get("acceptance_criteria"):
            return (MLB_LIVE_SOURCE_NOT_READY, f"Phase {phase.get('phase_id')} missing acceptance_criteria")
        if not phase.get("rollback_plan"):
            return (MLB_LIVE_SOURCE_NOT_READY, f"Phase {phase.get('phase_id')} missing rollback_plan")

    # Check fallback strategy
    today_fallback = fallback_strategy.get("today_mode_fallback_priority", [])
    replay_fallback = fallback_strategy.get("replay_mode_fallback_priority", [])
    if not today_fallback or not replay_fallback:
        return (MLB_LIVE_SOURCE_DATA_LIMITED, "Fallback strategy incomplete")

    # Check for unverified odds sources (conservative gate)
    odds_candidates = [c for c in candidates if c.source_type == SOURCE_TYPE_ODDS]
    unverified_odds = [c for c in odds_candidates if c.requires_verification and c.recommended]
    if unverified_odds:
        return (
            MLB_LIVE_SOURCE_NEEDS_API_VERIFICATION,
            (
                f"Contracts and plan complete; "
                f"{len(unverified_odds)} recommended odds source(s) require human API verification: "
                + ", ".join(c.source_name for c in unverified_odds)
            ),
        )

    # Check schedule/result candidates needing verification
    unverified_sched = [
        c for c in candidates
        if c.source_type == SOURCE_TYPE_SCHEDULE and c.requires_verification and c.recommended
    ]
    unverified_result = [
        c for c in candidates
        if c.source_type == SOURCE_TYPE_RESULT and c.requires_verification and c.recommended
    ]
    if unverified_sched or unverified_result:
        return (
            MLB_LIVE_SOURCE_NEEDS_VENDOR_DECISION,
            (
                "Schedule/result source candidates need vendor/ToS review before production use. "
                "Contracts and plan are otherwise complete."
            ),
        )

    # All good
    return (
        MLB_LIVE_SOURCE_CONTRACT_READY,
        (
            "Source contracts, candidate matrix, fallback strategy, and integration plan "
            "are all complete. Pending human API verification for live use."
        ),
    )


# ════════════════════════════════════════════════════════════════════════════
# SECTION I — Report Builder
# ════════════════════════════════════════════════════════════════════════════


def build_live_source_plan_report(
    run_date: str = "2026-05-07",
    *,
    write_reports: bool = True,
    report_path: str | None = None,
    markdown_path: str | None = None,
) -> dict[str, Any]:
    """
    Build the full MLB Live Source Adapter Selection and Integration Plan report.

    Returns:
        Full report payload dict (planning document only — no live API calls).
    """
    run_ts = datetime.datetime.now(datetime.timezone.utc).isoformat()
    date_nd = run_date.replace("-", "")

    # Build components
    candidates = build_source_candidate_matrix()
    schedule_contract = MLBScheduleSourceContract()
    odds_contract = MLBOddsSourceContract()
    result_contract = MLBResultSourceContract()
    odds_normalization = build_odds_normalization_contract()
    fallback_strategy = build_fallback_strategy()
    health_rules = SourceHealthRules()
    integration_plan = build_integration_plan()

    # Gate evaluation
    gate, gate_rationale = evaluate_live_source_gate(
        candidates=candidates,
        schedule_contract=schedule_contract,
        odds_contract=odds_contract,
        result_contract=result_contract,
        fallback_strategy=fallback_strategy,
        integration_plan=integration_plan,
    )

    assert gate in VALID_GATES, f"Gate {gate!r} not in VALID_GATES"

    # Build candidate summary
    def _cand_to_dict(c: SourceCandidate) -> dict[str, Any]:
        return {
            "source_id": c.source_id,
            "source_type": c.source_type,
            "source_name": c.source_name,
            "access_method": c.access_method,
            "official_or_third_party": c.official_or_third_party,
            "requires_api_key": c.requires_api_key,
            "cost_risk": c.cost_risk,
            "rate_limit_risk": c.rate_limit_risk,
            "terms_risk": c.terms_risk,
            "freshness_expected": c.freshness_expected,
            "schema_fit_score": c.schema_fit_score,
            "reliability_score": c.reliability_score,
            "governance_risk": c.governance_risk,
            "production_readiness": c.production_readiness,
            "recommended": c.recommended,
            "requires_verification": c.requires_verification,
            "rejection_reason": c.rejection_reason,
            "notes": c.notes,
        }

    report: dict[str, Any] = {
        "module_version": MODULE_VERSION,
        "run_timestamp_utc": run_ts,
        "run_date": run_date,
        "plan_type": "live_source_adapter_selection_and_integration_plan",
        "safety": {
            "production_modified": PRODUCTION_MODIFIED,
            "no_real_bet": NO_REAL_BET,
            "paper_only": PAPER_ONLY,
            "no_profit_claim": NO_PROFIT_CLAIM,
            "no_edge_claim": NO_EDGE_CLAIM,
            "no_auto_execution": NO_AUTO_EXECUTION,
            "no_live_api_connected": NO_LIVE_API_CONNECTED,
            "plan_only": PLAN_ONLY,
            "diagnostic_only": DIAGNOSTIC_ONLY,
            "fixture_not_production": FIXTURE_NOT_PRODUCTION,
        },
        "source_candidate_matrix": [_cand_to_dict(c) for c in candidates],
        "source_candidate_summary": {
            "total_candidates": len(candidates),
            "schedule_candidates": sum(1 for c in candidates if c.source_type == SOURCE_TYPE_SCHEDULE),
            "odds_candidates": sum(1 for c in candidates if c.source_type == SOURCE_TYPE_ODDS),
            "result_candidates": sum(1 for c in candidates if c.source_type == SOURCE_TYPE_RESULT),
            "recommended_count": sum(1 for c in candidates if c.recommended),
            "needs_verification_count": sum(1 for c in candidates if c.requires_verification),
            "blocked_count": sum(1 for c in candidates if c.production_readiness == "blocked"),
        },
        "contracts": {
            "schedule_source_contract": {
                "contract_id": schedule_contract.contract_id,
                "required_fields": schedule_contract.required_fields,
                "optional_fields": schedule_contract.optional_fields,
                "freshness_sla_minutes": schedule_contract.freshness_sla_minutes,
                "allowed_missing_fields": schedule_contract.allowed_missing_fields,
                "validation_rules": schedule_contract.validation_rules,
                "unavailable_behavior": schedule_contract.unavailable_behavior,
                "fallback_behavior": schedule_contract.fallback_behavior,
                "governance_flags": schedule_contract.governance_flags,
            },
            "odds_source_contract": {
                "contract_id": odds_contract.contract_id,
                "required_fields": odds_contract.required_fields,
                "optional_fields": odds_contract.optional_fields,
                "freshness_sla_minutes": odds_contract.freshness_sla_minutes,
                "allowed_missing_fields": odds_contract.allowed_missing_fields,
                "validation_rules": odds_contract.validation_rules,
                "unavailable_behavior": odds_contract.unavailable_behavior,
                "fallback_behavior": odds_contract.fallback_behavior,
                "normalization_contract": odds_contract.normalization_contract,
                "governance_flags": odds_contract.governance_flags,
            },
            "result_source_contract": {
                "contract_id": result_contract.contract_id,
                "required_fields": result_contract.required_fields,
                "optional_fields": result_contract.optional_fields,
                "freshness_sla_minutes": result_contract.freshness_sla_minutes,
                "allowed_missing_fields": result_contract.allowed_missing_fields,
                "validation_rules": result_contract.validation_rules,
                "unavailable_behavior": result_contract.unavailable_behavior,
                "fallback_behavior": result_contract.fallback_behavior,
                "governance_flags": result_contract.governance_flags,
            },
        },
        "source_health_rules": {
            "version": "source_health_rules_v1",
            "checks": [
                "reachable",
                "schema_valid",
                "freshness_ok",
                "total_games_count",
                "missing_moneyline_count",
                "missing_runline_count",
                "missing_total_count",
                "missing_result_count",
            ],
            "outputs": [
                "stale_data_flag",
                "source_unavailable_flag",
                "fallback_required",
                "source_health_gate",
            ],
            "valid_health_gates": health_rules.valid_health_gates,
            "thresholds": {
                "stale_data_flag_threshold_minutes": health_rules.stale_data_flag_threshold_minutes,
                "max_missing_moneyline_pct": health_rules.max_missing_moneyline_pct,
                "max_missing_runline_pct": health_rules.max_missing_runline_pct,
                "max_missing_total_pct": health_rules.max_missing_total_pct,
            },
        },
        "odds_normalization_contract": odds_normalization,
        "fallback_strategy": fallback_strategy,
        "integration_plan": integration_plan,
        "gate": gate,
        "gate_rationale": gate_rationale,
        "completion_marker": COMPLETION_MARKER,
    }

    # Write JSON report
    _report_path = report_path or os.path.join(
        DEFAULT_PLAN_REPORT_DIR, f"mlb_live_source_plan_{date_nd}.json"
    )
    if write_reports:
        os.makedirs(os.path.dirname(_report_path) if os.path.dirname(_report_path) else ".", exist_ok=True)
        with open(_report_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)

    # Write markdown report
    _md_path = markdown_path or os.path.join(
        DEFAULT_BETTINGPLAN_DIR, run_date, f"mlb_live_source_plan_report_{date_nd}.md"
    )
    if write_reports:
        _write_markdown_report(report, candidates, integration_plan, _md_path, run_date)

    report["_report_path"] = _report_path
    report["_markdown_path"] = _md_path
    return report


def _write_markdown_report(
    report: dict[str, Any],
    candidates: list[SourceCandidate],
    integration_plan: list[dict[str, Any]],
    md_path: str,
    run_date: str,
) -> None:
    """Write the markdown report for the live source plan."""
    gate = report.get("gate", "")
    gate_rationale = report.get("gate_rationale", "")
    run_ts = report.get("run_timestamp_utc", "")

    lines: list[str] = []
    lines.append("# MLB Live Source Adapter Selection and Integration Plan")
    lines.append("")
    lines.append("> **⚠️ PAPER-ONLY — PLAN DOCUMENT — NO REAL BET — NO PROFIT CLAIM**")
    lines.append(">")
    lines.append("> 本報告為 live source adapter 選擇與整合計畫文件。")
    lines.append("> 不連接任何真實 API。不執行任何真實下注。不宣稱任何真實獲利。")
    lines.append("> 所有候選 source 需人工驗證後方可用於 production 環境。")
    lines.append("")
    lines.append(f"**Date:** {run_date}")
    lines.append(f"**Generated:** {run_ts}")
    lines.append(f"**Module:** `mlb_live_source_plan_v1`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Safety flags
    lines.append("## Safety Flags")
    lines.append("")
    safety = report.get("safety", {})
    for k, v in safety.items():
        lines.append(f"- **{k}**: `{v}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Source Candidate Matrix
    lines.append("## Source Candidate Matrix")
    lines.append("")
    lines.append("| Source ID | Type | Name | Method | Recommended | Needs Verification | Prod Readiness | Governance Risk |")
    lines.append("|-----------|------|------|--------|-------------|-------------------|----------------|-----------------|")
    for c in candidates:
        rec_str = "✅ YES" if c.recommended else "❌ NO"
        ver_str = "⚠️ YES" if c.requires_verification else "NO"
        lines.append(
            f"| {c.source_id} | {c.source_type} | {c.source_name[:30]} | "
            f"{c.access_method} | {rec_str} | {ver_str} | {c.production_readiness} | {c.governance_risk} |"
        )
    lines.append("")

    # Summary counts
    summary = report.get("source_candidate_summary", {})
    lines.append(f"**Total Candidates:** {summary.get('total_candidates', 0)}")
    lines.append(f"- Schedule: {summary.get('schedule_candidates', 0)}")
    lines.append(f"- Odds: {summary.get('odds_candidates', 0)}")
    lines.append(f"- Result: {summary.get('result_candidates', 0)}")
    lines.append(f"- Recommended: {summary.get('recommended_count', 0)}")
    lines.append(f"- Needs Verification: {summary.get('needs_verification_count', 0)}")
    lines.append(f"- Blocked (scraping/fixture): {summary.get('blocked_count', 0)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Contracts
    lines.append("## Source Contract Schemas")
    lines.append("")
    for contract_key, label in [
        ("schedule_source_contract", "Schedule Source Contract"),
        ("odds_source_contract", "Odds Source Contract"),
        ("result_source_contract", "Result Source Contract"),
    ]:
        c = report.get("contracts", {}).get(contract_key, {})
        lines.append(f"### {label} (`{c.get('contract_id', '')}`)")
        lines.append("")
        lines.append(f"**Freshness SLA:** {c.get('freshness_sla_minutes')} minutes")
        lines.append("")
        lines.append("**Required Fields:**")
        for f_ in c.get("required_fields", []):
            lines.append(f"  - `{f_}`")
        lines.append("")
        lines.append("**Optional Fields:**")
        for f_ in c.get("optional_fields", []):
            lines.append(f"  - `{f_}`")
        lines.append("")
        lines.append(f"**Unavailable Behavior:** {c.get('unavailable_behavior', '')}")
        lines.append("")
        lines.append(f"**Fallback Behavior:** {c.get('fallback_behavior', '')}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Odds Normalization
    lines.append("## Odds Normalization Contract")
    lines.append("")
    norm = report.get("odds_normalization_contract", {})
    lines.append(f"**Contract ID:** `{norm.get('contract_id', '')}`")
    lines.append("")
    lines.append("**Existing Functions (reused — not re-implemented):**")
    for fn_name, fn_info in norm.get("existing_functions", {}).items():
        lines.append(f"- `{fn_name}` ({fn_info.get('module', '')}): {fn_info.get('description', '')}")
    lines.append("")
    lines.append("**Governance:**")
    for k, v in norm.get("governance", {}).items():
        lines.append(f"- **{k}**: `{v}`")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Fallback Strategy
    lines.append("## Fallback Strategy")
    lines.append("")
    fb = report.get("fallback_strategy", {})
    lines.append("### Today Mode Fallback Priority")
    lines.append("")
    lines.append("| Priority | Source | Condition |")
    lines.append("|----------|--------|-----------|")
    for item in fb.get("today_mode_fallback_priority", []):
        lines.append(f"| {item['priority']} | {item['source']} | {item['condition'][:80]} |")
    lines.append("")
    lines.append("### Replay Mode Fallback Priority")
    lines.append("")
    lines.append("| Priority | Source | Condition |")
    lines.append("|----------|--------|-----------|")
    for item in fb.get("replay_mode_fallback_priority", []):
        lines.append(f"| {item['priority']} | {item['source']} | {item['condition'][:80]} |")
    lines.append("")
    lines.append("### Fixture Governance Rules")
    lines.append("")
    fixture_rules = fb.get("fixture_governance_rules", {})
    lines.append("**Allowed Uses:**")
    for u in fixture_rules.get("allowed_uses", []):
        lines.append(f"- {u}")
    lines.append("")
    lines.append("**Forbidden Uses:**")
    for u in fixture_rules.get("forbidden_uses", []):
        lines.append(f"- ⛔ {u}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Integration Plan
    lines.append("## Integration Plan")
    lines.append("")
    for phase in integration_plan:
        lines.append(f"### Phase {phase['phase_id']}: {phase['phase_name']}")
        lines.append("")
        lines.append(f"**Goal:** {phase['goal']}")
        lines.append("")
        lines.append("**Files to Create:**")
        for f_ in phase.get("files_to_create", []):
            lines.append(f"- `{f_}`")
        lines.append("")
        lines.append("**Acceptance Criteria:**")
        for ac in phase.get("acceptance_criteria", []):
            lines.append(f"- {ac}")
        lines.append("")
        lines.append(f"**Rollback Plan:** {phase.get('rollback_plan', '')}")
        lines.append("")
        lines.append(f"**Governance Guard:** {phase.get('governance_guard', '')}")
        lines.append("")

    lines.append("---")
    lines.append("")

    # Gate
    lines.append("## Gate Conclusion")
    lines.append("")
    lines.append(f"**Gate: `{gate}`**")
    lines.append("")
    lines.append(f"> {gate_rationale}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Human decisions needed
    lines.append("## 人工決策事項")
    lines.append("")
    lines.append("以下項目需人工確認後才可進入 production 環境：")
    lines.append("")
    lines.append("1. **The Odds API** — 確認 API key 取得流程、費用方案、rate limit")
    lines.append("2. **MLB StatsAPI** — 確認 ToS 對商業使用的限制")
    lines.append("3. **Sportradar** — 成本評估（目前標記為 high cost / not recommended）")
    lines.append("4. **Action Network scraping** — 已標記 BLOCKED，確認不會被誤用")
    lines.append("5. **Fixture source** — 確認 FIXTURE_NOT_PRODUCTION guard 在所有 pipeline 路徑有效")
    lines.append("")
    lines.append("---")
    lines.append("")

    # No profit claim
    lines.append("## No Profit Claim")
    lines.append("")
    lines.append(
        "本系統不宣稱已找到任何可盈利的投注 edge。"
        "本計畫文件僅為 live source adapter 選擇與整合規劃。"
        "所有 paper advisory 均為研究目的，不代表任何真實獲利預期。"
    )
    lines.append("")
    lines.append("**NO_PROFIT_CLAIM = True**")
    lines.append("**NO_EDGE_CLAIM = True**")
    lines.append("**PAPER_ONLY = True**")
    lines.append("**NO_REAL_BET = True**")
    lines.append("**NO_LIVE_API_CONNECTED = True**")
    lines.append("**PLAN_ONLY = True**")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Completion Marker")
    lines.append("")
    lines.append(f"`{COMPLETION_MARKER}`")
    lines.append("")

    os.makedirs(os.path.dirname(md_path) if os.path.dirname(md_path) else ".", exist_ok=True)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
