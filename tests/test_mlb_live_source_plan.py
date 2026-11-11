"""Tests for MLB Live Source Adapter Selection and Integration Plan.

20 tests covering:
  1.  SourceCandidate schema completeness
  2.  Schedule contract required fields
  3.  Odds contract required fields
  4.  Result contract required fields
  5.  Candidate matrix has schedule / odds / result
  6.  Fixture source marked not production
  7.  Replay source marked historical only
  8.  Odds candidates marked requires_verification when unverified
  9.  Source health rules complete
  10. Fallback strategy complete
  11. Today fallback priority order
  12. Replay fallback priority order
  13. Odds normalization references existing function names
  14. Integration plan has at least 4 phases
  15. Each phase has acceptance_criteria
  16. Each phase has rollback_plan
  17. Gate is one of the 7 valid values
  18. Markdown report contains no-real-bet / no profit claim
  19. Markdown report contains completion marker
  20. Full regression guard (prior modules unbroken)
"""
from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from typing import Any

import pytest

# ─── Module imports ───────────────────────────────────────────────────────────

from orchestrator.mlb_live_source_plan import (
    COMPLETION_MARKER,
    FIXTURE_NOT_PRODUCTION,
    MODULE_VERSION,
    NO_AUTO_EXECUTION,
    NO_LIVE_API_CONNECTED,
    NO_PROFIT_CLAIM,
    NO_REAL_BET,
    PAPER_ONLY,
    PLAN_ONLY,
    PRODUCTION_MODIFIED,
    VALID_GATES,
    MLB_LIVE_SOURCE_PLAN_READY,
    MLB_LIVE_SOURCE_CONTRACT_READY,
    MLB_LIVE_SOURCE_NEEDS_VENDOR_DECISION,
    MLB_LIVE_SOURCE_NEEDS_API_VERIFICATION,
    MLB_LIVE_SOURCE_GOVERNANCE_RISK,
    MLB_LIVE_SOURCE_DATA_LIMITED,
    MLB_LIVE_SOURCE_NOT_READY,
    ACCESS_SCRAPING,
    SOURCE_TYPE_SCHEDULE,
    SOURCE_TYPE_ODDS,
    SOURCE_TYPE_RESULT,
    MLBScheduleSourceContract,
    MLBOddsSourceContract,
    MLBResultSourceContract,
    SourceCandidate,
    SourceHealthRules,
    build_fallback_strategy,
    build_integration_plan,
    build_live_source_plan_report,
    build_odds_normalization_contract,
    build_source_candidate_matrix,
    evaluate_live_source_gate,
)


# ════════════════════════════════════════════════════════════════════════════
# Test 1 — SourceCandidate dataclass schema
# ════════════════════════════════════════════════════════════════════════════


class TestSourceCandidateSchema:
    def test_source_candidate_has_all_required_fields(self) -> None:
        """SourceCandidate must have all required fields and correct types."""
        c = SourceCandidate(
            source_id="test_source_v1",
            source_type=SOURCE_TYPE_SCHEDULE,
            source_name="Test Source",
            access_method="rest_api",
            official_or_third_party="official",
            requires_api_key=False,
            cost_risk="none",
            rate_limit_risk="low",
            terms_risk="medium",
            freshness_expected="real-time",
            schema_fit_score=0.85,
            reliability_score=0.90,
            governance_risk="low",
            production_readiness="needs_verification",
            recommended=True,
            requires_verification=True,
            rejection_reason=None,
            notes="test",
        )
        assert c.source_id == "test_source_v1"
        assert c.source_type == SOURCE_TYPE_SCHEDULE
        assert isinstance(c.schema_fit_score, float)
        assert isinstance(c.reliability_score, float)
        assert 0.0 <= c.schema_fit_score <= 1.0
        assert 0.0 <= c.reliability_score <= 1.0
        assert c.rejection_reason is None

    def test_source_candidate_is_dataclass(self) -> None:
        """SourceCandidate should be a dataclass."""
        assert dataclasses.is_dataclass(SourceCandidate)

    def test_source_candidate_fields_complete(self) -> None:
        """SourceCandidate must include governance-critical fields."""
        required_fields = {
            "source_id", "source_type", "source_name", "access_method",
            "requires_api_key", "cost_risk", "terms_risk",
            "governance_risk", "production_readiness", "recommended",
            "requires_verification", "rejection_reason",
        }
        candidate_fields = {f.name for f in dataclasses.fields(SourceCandidate)}
        missing = required_fields - candidate_fields
        assert not missing, f"SourceCandidate missing fields: {missing}"


# ════════════════════════════════════════════════════════════════════════════
# Test 2 — Schedule contract
# ════════════════════════════════════════════════════════════════════════════


class TestScheduleContract:
    def test_schedule_contract_required_fields(self) -> None:
        """MLBScheduleSourceContract must have all schedule-specific required fields."""
        contract = MLBScheduleSourceContract()
        required = {"game_id", "game_date", "home_team", "away_team",
                    "scheduled_start_time", "game_status"}
        assert set(contract.required_fields) == required

    def test_schedule_contract_has_fallback(self) -> None:
        """Schedule contract must define fallback behavior."""
        contract = MLBScheduleSourceContract()
        assert contract.fallback_behavior
        assert "DATA_LIMITED" in contract.fallback_behavior or "fallback" in contract.fallback_behavior.lower()

    def test_schedule_contract_governance_flags(self) -> None:
        """Schedule contract governance must include paper_only and fixture_not_production."""
        contract = MLBScheduleSourceContract()
        assert contract.governance_flags.get("paper_only") is True
        assert contract.governance_flags.get("fixture_not_production") is True

    def test_schedule_contract_freshness_sla(self) -> None:
        """Schedule contract freshness SLA must be positive integer."""
        contract = MLBScheduleSourceContract()
        assert isinstance(contract.freshness_sla_minutes, int)
        assert contract.freshness_sla_minutes > 0


# ════════════════════════════════════════════════════════════════════════════
# Test 3 — Odds contract
# ════════════════════════════════════════════════════════════════════════════


class TestOddsContract:
    def test_odds_contract_required_fields(self) -> None:
        """MLBOddsSourceContract must require moneyline + timestamp fields."""
        contract = MLBOddsSourceContract()
        required = {
            "game_id", "game_date",
            "home_moneyline_odds", "away_moneyline_odds",
            "source_timestamp",
        }
        assert required.issubset(set(contract.required_fields))

    def test_odds_contract_normalization_contract(self) -> None:
        """Odds contract must include normalization contract referencing existing functions."""
        contract = MLBOddsSourceContract()
        norm = contract.normalization_contract
        assert "normalization_function_used" in norm
        assert "normalize_two_way_no_vig" in norm["normalization_function_used"]
        assert "odds_conversion_function_used" in norm
        assert "american_odds_to_implied_prob" in norm["odds_conversion_function_used"]

    def test_odds_contract_governance_flags(self) -> None:
        """Odds contract governance must block stake sizing."""
        contract = MLBOddsSourceContract()
        assert contract.governance_flags.get("paper_only") is True
        assert contract.governance_flags.get("no_stake_sizing") is True
        assert contract.governance_flags.get("requires_verification_before_live_use") is True

    def test_odds_contract_unavailable_behavior(self) -> None:
        """Odds contract must define advisory PASS behavior when odds unavailable."""
        contract = MLBOddsSourceContract()
        assert "PASS" in contract.unavailable_behavior or "unavailable" in contract.unavailable_behavior.lower()

    def test_odds_contract_runline_optional(self) -> None:
        """Runline fields should be optional in odds contract."""
        contract = MLBOddsSourceContract()
        optional_names = set(contract.optional_fields)
        assert "runline_spread" in optional_names


# ════════════════════════════════════════════════════════════════════════════
# Test 4 — Result contract
# ════════════════════════════════════════════════════════════════════════════


class TestResultContract:
    def test_result_contract_required_fields(self) -> None:
        """MLBResultSourceContract must require score + home_win fields."""
        contract = MLBResultSourceContract()
        required = {
            "game_id", "game_date",
            "final_home_score", "final_away_score",
            "game_status", "home_win",
        }
        assert set(contract.required_fields) == required

    def test_result_contract_postponed_handling(self) -> None:
        """Result contract must mention postponed/cancelled handling."""
        contract = MLBResultSourceContract()
        rules_text = " ".join(contract.validation_rules)
        assert "postponed" in rules_text.lower() or "cancelled" in rules_text.lower()

    def test_result_contract_no_fabrication(self) -> None:
        """Result contract must prohibit result fabrication."""
        contract = MLBResultSourceContract()
        assert contract.governance_flags.get("no_auto_result_fabrication") is True

    def test_result_contract_governance_flags(self) -> None:
        """Result contract governance must include human_review for suspended."""
        contract = MLBResultSourceContract()
        assert contract.governance_flags.get("paper_only") is True
        assert contract.governance_flags.get("human_review_required_for_suspended") is True


# ════════════════════════════════════════════════════════════════════════════
# Test 5 — Candidate matrix type coverage
# ════════════════════════════════════════════════════════════════════════════


class TestCandidateMatrix:
    def test_matrix_has_schedule_candidates(self) -> None:
        """Candidate matrix must include at least one schedule source."""
        candidates = build_source_candidate_matrix()
        types = {c.source_type for c in candidates}
        assert SOURCE_TYPE_SCHEDULE in types

    def test_matrix_has_odds_candidates(self) -> None:
        """Candidate matrix must include at least one odds source."""
        candidates = build_source_candidate_matrix()
        types = {c.source_type for c in candidates}
        assert SOURCE_TYPE_ODDS in types

    def test_matrix_has_result_candidates(self) -> None:
        """Candidate matrix must include at least one result source."""
        candidates = build_source_candidate_matrix()
        types = {c.source_type for c in candidates}
        assert SOURCE_TYPE_RESULT in types

    def test_matrix_source_ids_are_unique(self) -> None:
        """All source_id values must be unique."""
        candidates = build_source_candidate_matrix()
        ids = [c.source_id for c in candidates]
        assert len(ids) == len(set(ids)), "Duplicate source_id found in matrix"


# ════════════════════════════════════════════════════════════════════════════
# Test 6 — Fixture source not production
# ════════════════════════════════════════════════════════════════════════════


class TestFixtureGovernance:
    def test_fixture_schedule_source_not_production(self) -> None:
        """Fixture schedule source must have production_readiness='not_ready' and recommended=False."""
        candidates = build_source_candidate_matrix()
        fixture_sched = [
            c for c in candidates
            if c.source_type == SOURCE_TYPE_SCHEDULE and "fixture" in c.source_id.lower()
        ]
        assert fixture_sched, "No fixture schedule source found"
        for c in fixture_sched:
            assert c.production_readiness == "not_ready", (
                f"{c.source_id} must have production_readiness=not_ready"
            )
            assert c.recommended is False, (
                f"{c.source_id} must not be recommended for production"
            )

    def test_fixture_odds_source_not_production(self) -> None:
        """Fixture odds source must not be recommended for production."""
        candidates = build_source_candidate_matrix()
        fixture_odds = [
            c for c in candidates
            if c.source_type == SOURCE_TYPE_ODDS and "fixture" in c.source_id.lower()
        ]
        assert fixture_odds, "No fixture odds source found"
        for c in fixture_odds:
            assert c.production_readiness == "not_ready"
            assert c.recommended is False

    def test_fixture_not_production_constant(self) -> None:
        """FIXTURE_NOT_PRODUCTION safety constant must be True."""
        assert FIXTURE_NOT_PRODUCTION is True


# ════════════════════════════════════════════════════════════════════════════
# Test 7 — Replay source historical only
# ════════════════════════════════════════════════════════════════════════════


class TestReplaySourceGovernance:
    def test_replay_artifact_historical_only(self) -> None:
        """Historical replay artifact must have freshness=historical and recommended=False."""
        candidates = build_source_candidate_matrix()
        replay = [
            c for c in candidates
            if "replay_artifact" in c.source_id or "historical" in c.freshness_expected.lower()
        ]
        assert replay, "No replay/historical source found"
        for c in replay:
            assert c.freshness_expected == "historical", (
                f"{c.source_id} must have freshness_expected=historical"
            )
            assert c.recommended is False, (
                f"{c.source_id} should not be recommended for live production"
            )

    def test_replay_source_not_suitable_for_today_mode(self) -> None:
        """Replay artifact's rejection_reason should mention 'historical' or 'today'."""
        candidates = build_source_candidate_matrix()
        replay = [c for c in candidates if "replay_artifact" in c.source_id]
        assert replay, "replay_artifact source not found"
        for c in replay:
            assert c.rejection_reason is not None
            reason_lower = c.rejection_reason.lower()
            assert "historical" in reason_lower or "today" in reason_lower


# ════════════════════════════════════════════════════════════════════════════
# Test 8 — Unverified odds candidates
# ════════════════════════════════════════════════════════════════════════════


class TestOddsCandidateVerification:
    def test_recommended_odds_candidates_require_verification(self) -> None:
        """All recommended odds candidates must have requires_verification=True."""
        candidates = build_source_candidate_matrix()
        recommended_odds = [
            c for c in candidates
            if c.source_type == SOURCE_TYPE_ODDS and c.recommended
        ]
        assert recommended_odds, "No recommended odds candidates found"
        for c in recommended_odds:
            assert c.requires_verification is True, (
                f"{c.source_id} is recommended but requires_verification=False — "
                "unverified odds API must not be auto-approved"
            )

    def test_scraping_odds_candidate_not_recommended(self) -> None:
        """Scraping-based odds candidates must not be recommended."""
        candidates = build_source_candidate_matrix()
        scraping_odds = [
            c for c in candidates
            if c.source_type == SOURCE_TYPE_ODDS and c.access_method == ACCESS_SCRAPING
        ]
        assert scraping_odds, "No scraping odds candidate found"
        for c in scraping_odds:
            assert c.recommended is False, (
                f"Scraping candidate {c.source_id} must not be recommended"
            )
            assert c.production_readiness == "blocked", (
                f"Scraping candidate {c.source_id} must be blocked"
            )


# ════════════════════════════════════════════════════════════════════════════
# Test 9 — Source health rules
# ════════════════════════════════════════════════════════════════════════════


class TestSourceHealthRules:
    def test_health_rules_has_valid_gates(self) -> None:
        """SourceHealthRules must define valid health gate values."""
        rules = SourceHealthRules()
        expected_gates = {
            "SOURCE_HEALTH_OK",
            "SOURCE_HEALTH_STALE",
            "SOURCE_HEALTH_UNAVAILABLE",
            "SOURCE_HEALTH_SCHEMA_ERROR",
            "SOURCE_HEALTH_DATA_LIMITED",
        }
        assert expected_gates == set(rules.valid_health_gates)

    def test_health_rules_evaluate_unreachable(self) -> None:
        """evaluate() must return SOURCE_HEALTH_UNAVAILABLE when not reachable."""
        rules = SourceHealthRules()
        result = rules.evaluate(
            reachable=False,
            schema_valid=True,
            freshness_minutes=10.0,
            total_games_count=10,
            missing_moneyline_count=0,
            missing_runline_count=0,
            missing_total_count=0,
            missing_result_count=0,
        )
        assert result["source_health_gate"] == "SOURCE_HEALTH_UNAVAILABLE"
        assert result["source_unavailable_flag"] is True
        assert result["fallback_required"] is True

    def test_health_rules_evaluate_stale(self) -> None:
        """evaluate() must flag stale when freshness exceeds threshold."""
        rules = SourceHealthRules()
        result = rules.evaluate(
            reachable=True,
            schema_valid=True,
            freshness_minutes=200.0,  # > 120 min threshold
            total_games_count=10,
            missing_moneyline_count=0,
            missing_runline_count=0,
            missing_total_count=0,
            missing_result_count=0,
        )
        assert result["stale_data_flag"] is True
        assert result["source_health_gate"] == "SOURCE_HEALTH_STALE"

    def test_health_rules_evaluate_ok(self) -> None:
        """evaluate() should return SOURCE_HEALTH_OK for healthy source."""
        rules = SourceHealthRules()
        result = rules.evaluate(
            reachable=True,
            schema_valid=True,
            freshness_minutes=10.0,
            total_games_count=10,
            missing_moneyline_count=0,
            missing_runline_count=0,
            missing_total_count=0,
            missing_result_count=0,
        )
        assert result["source_health_gate"] == "SOURCE_HEALTH_OK"
        assert result["stale_data_flag"] is False
        assert result["source_unavailable_flag"] is False

    def test_health_rules_evaluate_missing_moneyline(self) -> None:
        """evaluate() should flag DATA_LIMITED when >50% moneyline missing."""
        rules = SourceHealthRules()
        result = rules.evaluate(
            reachable=True,
            schema_valid=True,
            freshness_minutes=5.0,
            total_games_count=10,
            missing_moneyline_count=8,  # 80% > 50%
            missing_runline_count=0,
            missing_total_count=0,
            missing_result_count=0,
        )
        assert result["source_health_gate"] == "SOURCE_HEALTH_DATA_LIMITED"
        assert result["fallback_required"] is True

    def test_health_rules_evaluate_schema_error(self) -> None:
        """evaluate() must return SCHEMA_ERROR when schema invalid."""
        rules = SourceHealthRules()
        result = rules.evaluate(
            reachable=True,
            schema_valid=False,
            freshness_minutes=5.0,
            total_games_count=10,
            missing_moneyline_count=0,
            missing_runline_count=0,
            missing_total_count=0,
            missing_result_count=0,
        )
        assert result["source_health_gate"] == "SOURCE_HEALTH_SCHEMA_ERROR"
        assert result["fallback_required"] is True


# ════════════════════════════════════════════════════════════════════════════
# Test 10 — Fallback strategy complete
# ════════════════════════════════════════════════════════════════════════════


class TestFallbackStrategyComplete:
    def test_fallback_strategy_has_both_modes(self) -> None:
        """Fallback strategy must define both today_mode and replay_mode priority lists."""
        strategy = build_fallback_strategy()
        assert "today_mode_fallback_priority" in strategy
        assert "replay_mode_fallback_priority" in strategy
        assert len(strategy["today_mode_fallback_priority"]) >= 3
        assert len(strategy["replay_mode_fallback_priority"]) >= 2

    def test_fallback_strategy_has_fixture_governance_rules(self) -> None:
        """Fallback strategy must define fixture governance (allowed / forbidden uses)."""
        strategy = build_fallback_strategy()
        fixture_rules = strategy.get("fixture_governance_rules", {})
        assert "allowed_uses" in fixture_rules
        assert "forbidden_uses" in fixture_rules
        forbidden_str = " ".join(fixture_rules["forbidden_uses"]).lower()
        assert "production" in forbidden_str or "real-money" in forbidden_str or "real_money" in forbidden_str


# ════════════════════════════════════════════════════════════════════════════
# Test 11 — Today fallback priority
# ════════════════════════════════════════════════════════════════════════════


class TestTodayFallbackPriority:
    def test_today_fallback_live_source_is_priority_1(self) -> None:
        """Today mode: live_current_source must be priority 1."""
        strategy = build_fallback_strategy()
        today_fb = strategy["today_mode_fallback_priority"]
        prio1 = next((x for x in today_fb if x["priority"] == 1), None)
        assert prio1 is not None
        assert "live" in prio1["source"].lower() or "current" in prio1["source"].lower()

    def test_today_fallback_data_limited_is_last(self) -> None:
        """Today mode: DATA_LIMITED must be the highest priority number (last resort)."""
        strategy = build_fallback_strategy()
        today_fb = strategy["today_mode_fallback_priority"]
        priorities = sorted(today_fb, key=lambda x: x["priority"])
        last = priorities[-1]
        assert "DATA_LIMITED" in last["source"].upper() or "data_limited" in last["source"].lower()

    def test_today_fallback_fixture_has_restriction_note(self) -> None:
        """Today mode: fixture entry must note it is restricted to dry-run only."""
        strategy = build_fallback_strategy()
        today_fb = strategy["today_mode_fallback_priority"]
        fixture_entries = [x for x in today_fb if "fixture" in x["source"].lower()]
        assert fixture_entries, "No fixture entry found in today fallback"
        for entry in fixture_entries:
            condition_lower = entry["condition"].lower()
            assert (
                "dry-run" in condition_lower
                or "test" in condition_lower
                or "never" in condition_lower
            ), f"Fixture fallback entry should note dry-run restriction: {entry}"


# ════════════════════════════════════════════════════════════════════════════
# Test 12 — Replay fallback priority
# ════════════════════════════════════════════════════════════════════════════


class TestReplayFallbackPriority:
    def test_replay_fallback_artifact_is_priority_1(self) -> None:
        """Replay mode: historical prediction artifact must be priority 1."""
        strategy = build_fallback_strategy()
        replay_fb = strategy["replay_mode_fallback_priority"]
        prio1 = next((x for x in replay_fb if x["priority"] == 1), None)
        assert prio1 is not None
        assert "historical" in prio1["source"].lower() or "artifact" in prio1["source"].lower()

    def test_replay_fallback_data_limited_is_last(self) -> None:
        """Replay mode: DATA_LIMITED must appear as final fallback."""
        strategy = build_fallback_strategy()
        replay_fb = strategy["replay_mode_fallback_priority"]
        priorities = sorted(replay_fb, key=lambda x: x["priority"])
        last = priorities[-1]
        assert "DATA_LIMITED" in last["source"].upper() or "data_limited" in last["source"].lower()


# ════════════════════════════════════════════════════════════════════════════
# Test 13 — Odds normalization references existing functions
# ════════════════════════════════════════════════════════════════════════════


class TestOddsNormalizationContract:
    def test_normalization_references_american_odds_to_implied_prob(self) -> None:
        """Odds normalization contract must reference american_odds_to_implied_prob."""
        norm = build_odds_normalization_contract()
        fns = norm.get("existing_functions", {})
        assert "american_odds_to_implied_prob" in fns

    def test_normalization_references_normalize_two_way_no_vig(self) -> None:
        """Odds normalization contract must reference normalize_two_way_no_vig."""
        norm = build_odds_normalization_contract()
        fns = norm.get("existing_functions", {})
        assert "normalize_two_way_no_vig" in fns

    def test_normalization_functions_point_to_correct_module(self) -> None:
        """Both normalization functions must reference orchestrator.mlb_current_sources."""
        norm = build_odds_normalization_contract()
        for fn_name, fn_info in norm.get("existing_functions", {}).items():
            assert fn_info.get("module") == "orchestrator.mlb_current_sources", (
                f"{fn_name} must reference orchestrator.mlb_current_sources"
            )

    def test_normalization_functions_status_implemented(self) -> None:
        """Normalization functions must have status=implemented_and_tested."""
        norm = build_odds_normalization_contract()
        for fn_name, fn_info in norm.get("existing_functions", {}).items():
            assert fn_info.get("status") == "implemented_and_tested", (
                f"{fn_name} status should be implemented_and_tested"
            )

    def test_normalization_actual_functions_callable(self) -> None:
        """The actual normalize functions must be importable and callable."""
        from orchestrator.mlb_current_sources import (
            american_odds_to_implied_prob,
            normalize_two_way_no_vig,
        )
        # Test american_odds_to_implied_prob
        prob = american_odds_to_implied_prob(-140.0)
        assert 0.0 < prob < 1.0

        # Test normalize_two_way_no_vig
        home_prob, away_prob = normalize_two_way_no_vig(-140.0, 120.0)
        assert 0.0 < home_prob < 1.0
        assert 0.0 < away_prob < 1.0
        assert abs(home_prob + away_prob - 1.0) < 1e-6


# ════════════════════════════════════════════════════════════════════════════
# Test 14 — Integration plan has ≥ 4 phases
# ════════════════════════════════════════════════════════════════════════════


class TestIntegrationPlan:
    def test_integration_plan_has_4_phases(self) -> None:
        """Integration plan must have at least 4 phases."""
        plan = build_integration_plan()
        assert len(plan) >= 4, f"Expected ≥4 phases, got {len(plan)}"

    def test_integration_plan_phase_ids(self) -> None:
        """Integration plan phases must include Live-1 through Live-4."""
        plan = build_integration_plan()
        phase_ids = {p["phase_id"] for p in plan}
        expected = {"Live-1", "Live-2", "Live-3", "Live-4"}
        assert expected.issubset(phase_ids)


# ════════════════════════════════════════════════════════════════════════════
# Test 15 — Each phase has acceptance_criteria
# ════════════════════════════════════════════════════════════════════════════


class TestPhaseAcceptanceCriteria:
    def test_each_phase_has_acceptance_criteria(self) -> None:
        """Every integration plan phase must have non-empty acceptance_criteria."""
        plan = build_integration_plan()
        for phase in plan:
            ac = phase.get("acceptance_criteria", [])
            assert len(ac) >= 1, (
                f"Phase {phase.get('phase_id')} missing acceptance_criteria"
            )

    def test_each_phase_has_governance_guard(self) -> None:
        """Every integration plan phase must have a governance_guard."""
        plan = build_integration_plan()
        for phase in plan:
            guard = phase.get("governance_guard", "")
            assert guard, f"Phase {phase.get('phase_id')} missing governance_guard"


# ════════════════════════════════════════════════════════════════════════════
# Test 16 — Each phase has rollback_plan
# ════════════════════════════════════════════════════════════════════════════


class TestPhaseRollbackPlan:
    def test_each_phase_has_rollback_plan(self) -> None:
        """Every integration plan phase must have a non-empty rollback_plan."""
        plan = build_integration_plan()
        for phase in plan:
            rollback = phase.get("rollback_plan", "")
            assert rollback, f"Phase {phase.get('phase_id')} missing rollback_plan"

    def test_rollback_plan_mentions_safety(self) -> None:
        """Rollback plans should mention data safety (no loss / revert)."""
        plan = build_integration_plan()
        for phase in plan:
            rollback = phase.get("rollback_plan", "").lower()
            assert (
                "revert" in rollback
                or "delete" in rollback
                or "remain" in rollback
                or "fallback" in rollback
            ), f"Phase {phase.get('phase_id')} rollback_plan should mention revert/delete/remain/fallback"


# ════════════════════════════════════════════════════════════════════════════
# Test 17 — Gate is one of the 7 valid values
# ════════════════════════════════════════════════════════════════════════════


class TestGateValidation:
    def test_valid_gates_has_7_values(self) -> None:
        """VALID_GATES must contain exactly 7 gate strings."""
        assert len(VALID_GATES) == 7

    def test_valid_gates_content(self) -> None:
        """VALID_GATES must contain the 7 expected gate strings."""
        expected = {
            MLB_LIVE_SOURCE_PLAN_READY,
            MLB_LIVE_SOURCE_CONTRACT_READY,
            MLB_LIVE_SOURCE_NEEDS_VENDOR_DECISION,
            MLB_LIVE_SOURCE_NEEDS_API_VERIFICATION,
            MLB_LIVE_SOURCE_GOVERNANCE_RISK,
            MLB_LIVE_SOURCE_DATA_LIMITED,
            MLB_LIVE_SOURCE_NOT_READY,
        }
        assert expected == VALID_GATES

    def test_evaluated_gate_in_valid_gates(self) -> None:
        """evaluate_live_source_gate() must return a gate in VALID_GATES."""
        candidates = build_source_candidate_matrix()
        schedule_contract = MLBScheduleSourceContract()
        odds_contract = MLBOddsSourceContract()
        result_contract = MLBResultSourceContract()
        fallback_strategy = build_fallback_strategy()
        integration_plan = build_integration_plan()

        gate, rationale = evaluate_live_source_gate(
            candidates=candidates,
            schedule_contract=schedule_contract,
            odds_contract=odds_contract,
            result_contract=result_contract,
            fallback_strategy=fallback_strategy,
            integration_plan=integration_plan,
        )
        assert gate in VALID_GATES, f"Gate {gate!r} not in VALID_GATES"
        assert rationale, "Gate rationale must be non-empty"

    def test_gate_governance_risk_when_scraping_recommended(self) -> None:
        """evaluate_live_source_gate() must return GOVERNANCE_RISK if scraping is recommended."""
        from orchestrator.mlb_live_source_plan import ACCESS_SCRAPING
        # Inject a scraping candidate as recommended
        bad_candidate = SourceCandidate(
            source_id="test_scraping_v1",
            source_type=SOURCE_TYPE_ODDS,
            source_name="Bad Scraping Source",
            access_method=ACCESS_SCRAPING,
            official_or_third_party="third_party",
            requires_api_key=False,
            cost_risk="none",
            rate_limit_risk="high",
            terms_risk="high",
            freshness_expected="variable",
            schema_fit_score=0.3,
            reliability_score=0.3,
            governance_risk="high",
            production_readiness="blocked",
            recommended=True,   # ← Should trigger GOVERNANCE_RISK
            requires_verification=False,
            rejection_reason=None,
        )
        candidates = [bad_candidate]
        gate, _ = evaluate_live_source_gate(
            candidates=candidates,
            schedule_contract=MLBScheduleSourceContract(),
            odds_contract=MLBOddsSourceContract(),
            result_contract=MLBResultSourceContract(),
            fallback_strategy=build_fallback_strategy(),
            integration_plan=build_integration_plan(),
        )
        assert gate == MLB_LIVE_SOURCE_GOVERNANCE_RISK

    def test_gate_not_ready_when_missing_candidate_type(self) -> None:
        """evaluate_live_source_gate() must return NOT_READY if a source type is missing."""
        # Only schedule candidates — no odds or result
        schedule_only = [
            c for c in build_source_candidate_matrix()
            if c.source_type == SOURCE_TYPE_SCHEDULE
        ]
        gate, _ = evaluate_live_source_gate(
            candidates=schedule_only,
            schedule_contract=MLBScheduleSourceContract(),
            odds_contract=MLBOddsSourceContract(),
            result_contract=MLBResultSourceContract(),
            fallback_strategy=build_fallback_strategy(),
            integration_plan=build_integration_plan(),
        )
        assert gate == MLB_LIVE_SOURCE_NOT_READY


# ════════════════════════════════════════════════════════════════════════════
# Test 18 — Markdown report safety flags
# ════════════════════════════════════════════════════════════════════════════


class TestMarkdownReportSafety:
    def test_markdown_contains_no_real_bet(self, tmp_path: Any) -> None:
        """Markdown report must contain NO_REAL_BET and paper-only warning."""
        md_path = str(tmp_path / "test_report.md")
        report_path = str(tmp_path / "test_report.json")

        build_live_source_plan_report(
            run_date="2026-05-07",
            write_reports=True,
            report_path=report_path,
            markdown_path=md_path,
        )

        with open(md_path, encoding="utf-8") as fh:
            content = fh.read()

        assert "NO_REAL_BET" in content
        assert "PAPER-ONLY" in content or "paper_only" in content.lower()

    def test_markdown_contains_no_profit_claim(self, tmp_path: Any) -> None:
        """Markdown report must contain NO_PROFIT_CLAIM."""
        md_path = str(tmp_path / "test_report.md")
        report_path = str(tmp_path / "test_report.json")

        build_live_source_plan_report(
            run_date="2026-05-07",
            write_reports=True,
            report_path=report_path,
            markdown_path=md_path,
        )

        with open(md_path, encoding="utf-8") as fh:
            content = fh.read()

        assert "NO_PROFIT_CLAIM" in content or "no profit claim" in content.lower()


# ════════════════════════════════════════════════════════════════════════════
# Test 19 — Markdown report contains completion marker
# ════════════════════════════════════════════════════════════════════════════


class TestMarkdownCompletionMarker:
    def test_markdown_contains_completion_marker(self, tmp_path: Any) -> None:
        """Markdown report must contain MLB_LIVE_SOURCE_PLAN_VERIFIED completion marker."""
        md_path = str(tmp_path / "test_report.md")
        report_path = str(tmp_path / "test_report.json")

        build_live_source_plan_report(
            run_date="2026-05-07",
            write_reports=True,
            report_path=report_path,
            markdown_path=md_path,
        )

        with open(md_path, encoding="utf-8") as fh:
            content = fh.read()

        assert COMPLETION_MARKER in content

    def test_completion_marker_value(self) -> None:
        """Completion marker must be MLB_LIVE_SOURCE_PLAN_VERIFIED."""
        assert COMPLETION_MARKER == "MLB_LIVE_SOURCE_PLAN_VERIFIED"

    def test_json_report_has_completion_marker(self, tmp_path: Any) -> None:
        """JSON report must include completion_marker field."""
        report_path = str(tmp_path / "test_report.json")
        md_path = str(tmp_path / "test_report.md")

        report = build_live_source_plan_report(
            run_date="2026-05-07",
            write_reports=True,
            report_path=report_path,
            markdown_path=md_path,
        )

        assert report.get("completion_marker") == COMPLETION_MARKER

        with open(report_path, encoding="utf-8") as fh:
            loaded = json.load(fh)
        assert loaded.get("completion_marker") == COMPLETION_MARKER


# ════════════════════════════════════════════════════════════════════════════
# Test 20 — Full regression guard
# ════════════════════════════════════════════════════════════════════════════


class TestFullRegressionGuard:
    def test_prior_modules_import_cleanly(self) -> None:
        """All prior orchestrator modules must import without error."""
        import orchestrator.mlb_daily_advisory as mda
        import orchestrator.mlb_current_sources as mcs
        import orchestrator.mlb_result_review as mrr
        import orchestrator.mlb_daily_scheduler as mds
        import orchestrator.mlb_advisory_api as maa
        import orchestrator.metrics_ssot as ms

        # Safety constants
        assert mda.PRODUCTION_MODIFIED is False
        assert mcs.PRODUCTION_MODIFIED is False
        assert mds.PRODUCTION_MODIFIED is False
        assert maa.PRODUCTION_MODIFIED is False

        # Gate sets non-empty
        assert len(mda.VALID_GATES) == 7
        assert len(mcs.VALID_GATES) == 7
        assert len(mds.VALID_GATES) == 7

        # metrics_ssot
        assert hasattr(ms, "MODULE_VERSION") or hasattr(ms, "MetricsPayload") or hasattr(ms, "BrierResult")

    def test_live_source_plan_safety_constants(self) -> None:
        """mlb_live_source_plan safety constants must all be correct."""
        assert PRODUCTION_MODIFIED is False
        assert NO_REAL_BET is True
        assert PAPER_ONLY is True
        assert NO_PROFIT_CLAIM is True
        assert NO_AUTO_EXECUTION is True
        assert NO_LIVE_API_CONNECTED is True
        assert PLAN_ONLY is True
        assert FIXTURE_NOT_PRODUCTION is True

    def test_full_report_build_no_disk_writes(self) -> None:
        """build_live_source_plan_report() with write_reports=False must not crash."""
        report = build_live_source_plan_report(
            run_date="2026-05-07",
            write_reports=False,
        )
        assert report.get("gate") in VALID_GATES
        assert report.get("completion_marker") == COMPLETION_MARKER
        assert report.get("safety", {}).get("production_modified") is False
        assert report.get("safety", {}).get("no_real_bet") is True
        assert report.get("safety", {}).get("no_live_api_connected") is True
