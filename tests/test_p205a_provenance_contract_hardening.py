from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from orchestrator.mlb_daily_advisory import build_advisory, run_mlb_daily_advisory
from orchestrator.mlb_daily_scheduler import run_paper_recommendation_job
from orchestrator.mlb_paper_evaluator import evaluate_paper_recommendations
from scripts import run_mlb_tsl_paper_recommendation as paper_script
from wbc_backend.recommendation.provenance_contract import (
    PROVENANCE_CONTRACT_VERSION,
    ProvenanceContractError,
    build_provenance_contract,
    legacy_or_missing_contract_is_learning_eligible,
    validate_provenance_contract,
)
from wbc_backend.recommendation.recommendation_row import MlbTslRecommendationRow


FIXTURE_GAME = {
    "gamePk": 824441,
    "gameDate": "2026-05-11T22:10:00Z",
    "status": {"detailedState": "Scheduled"},
    "teams": {
        "home": {"team": {"name": "Cleveland Guardians", "abbreviation": "CLE"}},
        "away": {"team": {"name": "Los Angeles Angels", "abbreviation": "LAA"}},
    },
}
FIXTURE_DATE = "2026-05-11"


def _pass_gate() -> dict:
    return {
        "allow_recommendation": True,
        "gate_status": "PASS",
        "gate_reasons": ["simulation gate PASS"],
        "simulation_id": "sim-p205a",
        "paper_only": True,
    }


def _valid_contract(**overrides):
    base = dict(
        prediction_input_mode="game_specific",
        prediction_source="unit_test_model",
        prediction_source_id="game-1",
        model_version="unit-test-v1",
        feature_fingerprint="feature-fp",
        prediction_as_of_utc="2026-05-11T10:00:00+00:00",
        game_specific=True,
        selected_side_method="argmax_model_probability",
        odds_source="observed_market",
        odds_is_market_observed=True,
        edge_is_real_evidence=True,
        learning_eligible=True,
        learning_block_reason="",
    )
    base.update(overrides)
    return build_provenance_contract(**base)


def _rec(game_pk: str, *, source_trace: dict, side: str = "home") -> dict:
    return {
        "game_id": f"2026-05-11-LAA-CLE-{game_pk}",
        "model_prob_home": 0.55,
        "model_prob_away": 0.45,
        "tsl_market": "moneyline",
        "tsl_side": side,
        "tsl_decimal_odds": 1.90,
        "stake_units_paper": 0.0,
        "gate_status": "BLOCKED_PAPER_ONLY",
        "paper_only": True,
        "source_trace": source_trace,
    }


def _outcome(game_pk: str, winner: str = "home") -> dict:
    return {
        "game_id": f"mlb_2026_{game_pk}",
        "outcome_available": True,
        "actual_winner": winner,
        "result_timestamp_utc": "2026-05-12T04:00:00+00:00",
    }


class TestP205AContractValidation:
    def test_valid_contract_serializes_expected_fields(self):
        contract = _valid_contract()
        validate_provenance_contract(contract)
        assert contract["provenance_contract_version"] == PROVENANCE_CONTRACT_VERSION
        assert tuple(contract.keys()) == (
            "provenance_contract_version",
            "prediction_input_mode",
            "prediction_source",
            "prediction_source_id",
            "model_version",
            "feature_fingerprint",
            "prediction_as_of_utc",
            "game_specific",
            "selected_side_method",
            "odds_source",
            "odds_is_market_observed",
            "edge_is_real_evidence",
            "learning_eligible",
            "learning_block_reason",
        )

    def test_boolean_fields_are_not_coerced_from_strings(self):
        with pytest.raises(ProvenanceContractError, match="literal boolean"):
            _valid_contract(learning_eligible="true")

    def test_learning_true_requires_game_specific_asof_and_empty_reason(self):
        with pytest.raises(ProvenanceContractError, match="game_specific=True"):
            _valid_contract(game_specific=False)
        with pytest.raises(ProvenanceContractError, match="prediction_as_of_utc"):
            _valid_contract(prediction_as_of_utc="")
        with pytest.raises(ProvenanceContractError, match="empty learning_block_reason"):
            _valid_contract(learning_block_reason="blocked")

    def test_learning_false_requires_non_empty_block_reason(self):
        with pytest.raises(ProvenanceContractError, match="non-empty"):
            _valid_contract(
                learning_eligible=False,
                edge_is_real_evidence=False,
                learning_block_reason="",
            )

    def test_estimated_and_historical_no_vig_are_not_real_edge_evidence(self):
        for odds_source in ("estimated", "historical_no_vig"):
            with pytest.raises(ProvenanceContractError, match="cannot set"):
                _valid_contract(odds_source=odds_source, edge_is_real_evidence=True)

    def test_learning_true_requires_observed_market_real_edge_evidence(self):
        with pytest.raises(ProvenanceContractError, match="odds_is_market_observed"):
            _valid_contract(odds_is_market_observed=False)
        with pytest.raises(ProvenanceContractError, match="edge_is_real_evidence"):
            _valid_contract(edge_is_real_evidence=False)
        with pytest.raises(ProvenanceContractError, match="learning_eligible=True"):
            _valid_contract(odds_source="estimated")

    def test_missing_or_legacy_contract_never_becomes_eligible(self):
        assert legacy_or_missing_contract_is_learning_eligible({}) is False
        assert legacy_or_missing_contract_is_learning_eligible({"learning_eligible": True}) is False


class TestPath1PaperRecommendationProvenance:
    def test_path1_uses_versioned_estimated_odds_contract_and_zero_stake(self):
        row = paper_script.build_recommendation(
            FIXTURE_GAME,
            FIXTURE_DATE,
            tsl_live=True,
            tsl_note="TSL reachable in test",
            simulation_gate=_pass_gate(),
        )

        st = row.source_trace
        assert row.gate_status == "BLOCKED_PAPER_ONLY"
        assert row.stake_units_paper == 0.0
        assert row.kelly_fraction == 0.0
        assert st["provenance_contract_version"] == PROVENANCE_CONTRACT_VERSION
        assert st["game_specific"] is False
        assert st["odds_source"] == "estimated"
        assert st["odds_is_market_observed"] is False
        assert st["edge_is_real_evidence"] is False
        assert st["learning_eligible"] is False
        assert "paper_only" in st["learning_block_reason"]
        assert st["selected_side_method"] == "argmax_model_probability"
        assert row.tsl_side in {"home", "away"}

    def test_tsl_live_does_not_make_estimated_odds_market_observed(self):
        row = paper_script.build_recommendation(
            FIXTURE_GAME,
            FIXTURE_DATE,
            tsl_live=True,
            tsl_note="TSL reachable in test",
            simulation_gate=_pass_gate(),
        )
        st = row.source_trace
        assert st["tsl_live"] is True
        assert st["odds_source"] == "estimated"
        assert st["odds_is_market_observed"] is False


class TestPath2DailyAdvisoryProvenance:
    def test_advisory_has_historical_replay_contract_and_is_learning_ineligible(self):
        row = {
            "game_date": FIXTURE_DATE,
            "game_id": "mlb_2025_1001",
            "home_team": "Home",
            "away_team": "Away",
            "model_home_prob": 0.61,
            "market_home_prob_no_vig": 0.49,
            "home_win": 1,
            "model_version": "historical-model-v1",
            "feature_fingerprint": "hist-fp",
            "prediction_as_of_utc": "2025-05-11T12:00:00+00:00",
            "p0_features": {"sp_home_pitcher": "H Pitcher", "sp_away_pitcher": "A Pitcher"},
        }
        advisory = build_advisory(row, 0, "replay")
        st = advisory["source_trace"]

        assert st["provenance_contract_version"] == PROVENANCE_CONTRACT_VERSION
        assert st["prediction_input_mode"] == "historical_replay"
        assert st["odds_source"] == "historical_no_vig"
        assert st["odds_is_market_observed"] is False
        assert st["edge_is_real_evidence"] is False
        assert st["learning_eligible"] is False
        assert "historical_replay" in st["learning_block_reason"]

    def test_daily_advisory_payload_declares_no_evaluator_routing(self):
        payload = run_mlb_daily_advisory(
            date_str=FIXTURE_DATE,
            mode="replay",
            limit=1,
            ledger_path="unused-ledger.jsonl",
            write_reports=False,
            override_games=[
                {
                    "game_date": FIXTURE_DATE,
                    "game_id": "mlb_2025_1002",
                    "home_team": "Home",
                    "away_team": "Away",
                    "model_home_prob": 0.50,
                    "market_home_prob_no_vig": 0.50,
                    "home_win": 1,
                    "p0_features": {},
                }
            ],
            source_mode="replay",
        )
        assert payload["evaluator_routing"] == "not_routed_to_paper_evaluator_or_strategy_leaderboard"
        assert payload["advisories"][0]["source_trace"]["learning_eligible"] is False


class TestSchedulerStrategyAttribution:
    def test_scheduler_passes_only_explicit_simulation_strategy_name(
        self, tmp_path, monkeypatch
    ):
        class Simulation:
            strategy_name = "explicit_simulation_strategy"

        import wbc_backend.simulation.simulation_result_loader as loader
        import wbc_backend.recommendation.recommendation_gate_policy as gate_policy

        monkeypatch.setattr(loader, "load_latest_simulation_result", lambda *a, **kw: Simulation())
        monkeypatch.setattr(gate_policy, "build_recommendation_gate_from_simulation", lambda sim: _pass_gate())
        monkeypatch.setattr(paper_script, "_pick_game", lambda run_date: FIXTURE_GAME)
        monkeypatch.setattr(paper_script, "_probe_tsl", lambda: (False, "TSL blocked"))

        captured: dict[str, str | None] = {}
        original_build = paper_script.build_recommendation

        def capturing_build_recommendation(*args, **kwargs):
            captured["strategy_id"] = kwargs.get("strategy_id")
            return original_build(*args, **kwargs)

        monkeypatch.setattr(paper_script, "build_recommendation", capturing_build_recommendation)

        result = run_paper_recommendation_job(
            FIXTURE_DATE,
            allow_replay=True,
            allow_missing_simulation_gate=False,
            output_base_dir=str(tmp_path),
        )

        assert result.status == "SUCCESS"
        assert captured["strategy_id"] == "explicit_simulation_strategy"
        written = list((tmp_path / "outputs" / "recommendations" / "PAPER" / FIXTURE_DATE).glob("*.jsonl"))
        assert len(written) == 1
        row = json.loads(written[0].read_text(encoding="utf-8"))
        assert row["strategy_id"] == "explicit_simulation_strategy"


class TestReadOnlyEvaluatorCompatibility:
    def test_valid_contract_false_remains_learning_ineligible_in_evaluator(self):
        source_trace = _valid_contract(
            odds_source="estimated",
            odds_is_market_observed=False,
            edge_is_real_evidence=False,
            learning_eligible=False,
            learning_block_reason="paper_only_block",
        )
        metrics = evaluate_paper_recommendations(
            [_rec("930001", source_trace=source_trace)],
            [_outcome("930001")],
        )
        assert metrics.learning_eligible_count == 0
        assert metrics.learning_ineligible_count == 1

    def test_valid_contract_true_still_works_with_literal_boolean_evaluator(self):
        metrics = evaluate_paper_recommendations(
            [_rec("930002", source_trace=_valid_contract())],
            [_outcome("930002")],
        )
        assert metrics.learning_eligible_count == 1
        assert metrics.learning_ineligible_count == 0

    def test_recommendation_row_rejects_legacy_learning_true_contract(self):
        with pytest.raises(ValueError, match="legacy or missing provenance contract"):
            MlbTslRecommendationRow(
                game_id="2026-05-11-LAA-CLE-824441",
                game_start_utc=datetime.now(timezone.utc),
                model_prob_home=0.55,
                model_prob_away=0.45,
                model_ensemble_version="v1",
                tsl_market="moneyline",
                tsl_line=None,
                tsl_side="home",
                tsl_decimal_odds=1.9,
                edge_pct=0.0,
                kelly_fraction=0.0,
                stake_units_paper=0.0,
                gate_status="BLOCKED_PAPER_ONLY",
                source_trace={"learning_eligible": True},
            )
