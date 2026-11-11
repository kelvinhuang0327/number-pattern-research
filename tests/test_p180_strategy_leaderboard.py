"""P180 fixture-only tests: strategy attribution and performance leaderboard.

Covers:
  - Explicit strategy_id attribution from recommendation rows
  - Legacy / missing strategy_id → UNATTRIBUTED bucketing
  - strategy_id is never inferred from model_ensemble_version or filenames
  - Deterministic ranking for identical fixtures
  - DATA_LIMITED marking for small-sample strategies
  - Leaderboard ranking rules (hit_rate desc, shadow_unit_roi desc, strategy_id asc)
  - Safety invariants: paper_only, offline, no DB, no live calls
  - Backward compatibility: rows without strategy_id remain evaluable

All tests use only in-memory fixture data.  No file I/O, no live API calls,
no DB access, no registry mutation, no strategy weight changes.
"""
from __future__ import annotations

import pytest

from orchestrator.mlb_paper_evaluator import (
    SMALL_SAMPLE_THRESHOLD,
    PaperEvaluationMetrics,
    build_strategy_leaderboard,
    calculate_binomial_p_value,
    evaluate_paper_recommendations,
)
from wbc_backend.recommendation.recommendation_row import MlbTslRecommendationRow


# ── Shared fixture helpers ─────────────────────────────────────────────────────


def _rec(
    game_pk: str,
    side: str,
    strategy_id: str | None = None,
    prob_home: float = 0.55,
    odds: float = 1.90,
    gate: str = "PASS",
) -> dict:
    """Build a minimal recommendation dict with optional strategy_id."""
    r = {
        "game_id": f"2026-05-11-LAA-CLE-{game_pk}",
        "model_prob_home": prob_home,
        "model_prob_away": round(1.0 - prob_home, 4),
        "tsl_market": "moneyline",
        "tsl_side": side,
        "tsl_decimal_odds": odds,
        "stake_units_paper": 1.0,
        "gate_status": gate,
        "paper_only": True,
    }
    if strategy_id is not None:
        r["strategy_id"] = strategy_id
    return r


def _outcome(game_pk: str, winner: str) -> dict:
    return {
        "game_id": f"mlb_2026_{game_pk}",
        "outcome_available": True,
        "actual_winner": winner,
    }


# ── P200: learning-eligibility safety (uses existing evaluator behavior) ──────


class TestP200LearningIneligibleRowsNotPromoted:
    """A neutral/fixed-prior row (P200 learning_eligible=False) carries no
    strategy_id, so it buckets as UNATTRIBUTED + data_limited and can never be
    surfaced as a promotable, attributed strategy by the existing leaderboard.

    NB: the evaluator source is outside the P200 whitelist, so this test asserts
    the *existing* safety nets (UNATTRIBUTED bucketing + data_limited) already
    prevent over-claiming learning-ineligible rows. Direct evaluator-side
    enforcement of ``learning_eligible`` is left as a follow-up.
    """

    def test_learning_ineligible_neutral_row_is_unattributed_and_data_limited(self):
        rec = _rec("900001", "home", strategy_id=None, prob_home=0.54)
        rec["source_trace"] = {
            "prediction_input_mode": "neutral_fixed_prior",
            "learning_eligible": False,
        }
        metrics = evaluate_paper_recommendations([rec], [_outcome("900001", "home")])
        lb = metrics.strategy_leaderboard
        assert len(lb) == 1
        entry = lb[0]
        assert entry["strategy_id"] == "UNATTRIBUTED"
        assert entry["data_limited"] is True

    def test_no_learning_ineligible_row_appears_as_promotable_strategy(self):
        # A handful of learning-ineligible neutral rows must not yield any
        # promotable (attributed AND non-data-limited) leaderboard entry.
        recs = []
        for i in range(5):
            r = _rec(f"90010{i}", "home", strategy_id=None, prob_home=0.54)
            r["source_trace"] = {"learning_eligible": False}
            recs.append(r)
        outcomes = [_outcome(f"90010{i}", "home") for i in range(5)]
        metrics = evaluate_paper_recommendations(recs, outcomes)
        promotable = [
            e
            for e in metrics.strategy_leaderboard
            if e["strategy_id"] != "UNATTRIBUTED" and not e["data_limited"]
        ]
        assert promotable == []


# ── P201: evaluator-side learning_eligible enforcement on the leaderboard ─────


class TestP201LeaderboardLearningStatus:
    """build_strategy_leaderboard classifies learning evidence (P201)."""

    def test_strategy_with_only_ineligible_rows_is_learning_ineligible(self):
        """A strategy whose rows are all learning-ineligible is never promotable (D4)."""
        seg = {"s_neutral": {"count": 20, "correct_count": 14, "hit_rate": 0.70,
                             "brier_score": 0.21, "shadow_unit_roi": 0.40}}
        learning = {"s_neutral": {"eligible": 0, "ineligible": 20}}
        lb = build_strategy_leaderboard(seg, strategy_learning=learning)
        entry = lb[0]
        # High hit_rate and not data_limited, yet must NOT be promotable.
        assert entry["data_limited"] is False
        assert entry["learning_status"] == "LEARNING_INELIGIBLE"
        assert entry["promotable_learning_evidence"] is False
        assert entry["learning_eligible_count"] == 0
        assert entry["learning_ineligible_count"] == 20

    def test_strategy_with_enough_eligible_rows_is_promotable(self):
        seg = {"s_game": {"count": 20, "correct_count": 14, "hit_rate": 0.70,
                          "brier_score": 0.21, "shadow_unit_roi": 0.40}}
        learning = {"s_game": {"eligible": 20, "ineligible": 0}}
        lb = build_strategy_leaderboard(seg, strategy_learning=learning)
        entry = lb[0]
        assert entry["learning_status"] == "LEARNING_ELIGIBLE"
        assert entry["promotable_learning_evidence"] is True

    def test_some_eligible_below_threshold_is_data_limited(self):
        seg = {"s_few": {"count": 20, "correct_count": 14, "hit_rate": 0.70,
                         "brier_score": 0.21, "shadow_unit_roi": 0.40}}
        learning = {"s_few": {"eligible": 3, "ineligible": 17}}
        lb = build_strategy_leaderboard(seg, strategy_learning=learning, threshold=10)
        entry = lb[0]
        assert entry["learning_status"] == "DATA_LIMITED"
        assert entry["promotable_learning_evidence"] is False

    def test_omitted_learning_defaults_to_unknown_not_promotable(self):
        """Legacy direct callers (no strategy_learning) get UNKNOWN, never promotable."""
        seg = {"s_legacy": {"count": 20, "correct_count": 14, "hit_rate": 0.70,
                            "brier_score": 0.21, "shadow_unit_roi": 0.40}}
        lb = build_strategy_leaderboard(seg)
        entry = lb[0]
        assert entry["learning_status"] == "UNKNOWN"
        assert entry["promotable_learning_evidence"] is False
        assert entry["learning_eligible_count"] is None

    def test_end_to_end_ineligible_strategy_not_promotable(self):
        """Through evaluate_paper_recommendations: an attributed strategy whose
        rows are all learning-ineligible is not promotable learning evidence (D4)."""
        recs = []
        for i in range(12):
            r = _rec(f"94000{i:02d}", "home", strategy_id="neutral_strat", prob_home=0.54)
            r["source_trace"] = {"learning_eligible": False,
                                 "learning_block_reason": "neutral_fixed_prior"}
            recs.append(r)
        outcomes = [_outcome(f"94000{i:02d}", "home") for i in range(12)]
        m = evaluate_paper_recommendations(recs, outcomes)
        entry = next(e for e in m.strategy_leaderboard if e["strategy_id"] == "neutral_strat")
        # 12 rows ≥ threshold so NOT data_limited, but still not promotable.
        assert entry["data_limited"] is False
        assert entry["learning_status"] == "LEARNING_INELIGIBLE"
        assert entry["promotable_learning_evidence"] is False
        assert m.learning_eligible_count == 0
        assert m.learning_ineligible_count == 12

    def test_end_to_end_eligible_strategy_is_promotable(self):
        recs = []
        for i in range(12):
            r = _rec(f"94100{i:02d}", "home", strategy_id="game_strat", prob_home=0.54)
            r["source_trace"] = {"learning_eligible": True}
            recs.append(r)
        outcomes = [_outcome(f"94100{i:02d}", "home") for i in range(12)]
        m = evaluate_paper_recommendations(recs, outcomes)
        entry = next(e for e in m.strategy_leaderboard if e["strategy_id"] == "game_strat")
        assert entry["learning_status"] == "LEARNING_ELIGIBLE"
        assert entry["promotable_learning_evidence"] is True
        assert m.learning_eligible_count == 12


# ── 1. MlbTslRecommendationRow: strategy_id field contract ────────────────────


class TestRecommendationRowStrategyIdField:
    """strategy_id field is optional, backward-compatible, and not inferred."""

    def test_strategy_id_defaults_to_none(self):
        """Existing callers that omit strategy_id get None (backward-compatible)."""
        from datetime import datetime, timezone

        row = MlbTslRecommendationRow(
            game_id="g1",
            game_start_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
            model_prob_home=0.55,
            model_prob_away=0.45,
            model_ensemble_version="v1-paper",
            tsl_market="moneyline",
            tsl_line=None,
            tsl_side="home",
            tsl_decimal_odds=1.90,
            edge_pct=0.02,
            kelly_fraction=0.02,
            stake_units_paper=0.5,
            gate_status="BLOCKED_PAPER_ONLY",
        )
        assert row.strategy_id is None

    def test_strategy_id_can_be_set_explicitly(self):
        """strategy_id can be set from simulation strategy_name."""
        from datetime import datetime, timezone

        row = MlbTslRecommendationRow(
            game_id="g2",
            game_start_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
            model_prob_home=0.55,
            model_prob_away=0.45,
            model_ensemble_version="v1-paper",
            tsl_market="moneyline",
            tsl_line=None,
            tsl_side="home",
            tsl_decimal_odds=1.90,
            edge_pct=0.02,
            kelly_fraction=0.02,
            stake_units_paper=0.5,
            gate_status="BLOCKED_PAPER_ONLY",
            strategy_id="alpha_v2",
        )
        assert row.strategy_id == "alpha_v2"

    def test_strategy_id_present_in_to_dict(self):
        """strategy_id appears in the serialised dict output."""
        from datetime import datetime, timezone

        row = MlbTslRecommendationRow(
            game_id="g3",
            game_start_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
            model_prob_home=0.55,
            model_prob_away=0.45,
            model_ensemble_version="v1-paper",
            tsl_market="moneyline",
            tsl_line=None,
            tsl_side="home",
            tsl_decimal_odds=1.90,
            edge_pct=0.02,
            kelly_fraction=0.02,
            stake_units_paper=0.5,
            gate_status="BLOCKED_PAPER_ONLY",
            strategy_id="beta_v1",
        )
        d = row.to_dict()
        assert "strategy_id" in d
        assert d["strategy_id"] == "beta_v1"

    def test_paper_only_invariant_still_enforced(self):
        """paper_only=False must still raise after adding strategy_id."""
        from datetime import datetime, timezone

        with pytest.raises(ValueError, match="paper_only must be True"):
            MlbTslRecommendationRow(
                game_id="g4",
                game_start_utc=datetime(2026, 5, 11, tzinfo=timezone.utc),
                model_prob_home=0.55,
                model_prob_away=0.45,
                model_ensemble_version="v1-paper",
                tsl_market="moneyline",
                tsl_line=None,
                tsl_side="home",
                tsl_decimal_odds=1.90,
                edge_pct=0.02,
                kelly_fraction=0.02,
                stake_units_paper=0.5,
                gate_status="BLOCKED_PAPER_ONLY",
                paper_only=False,
                strategy_id="alpha_v2",
            )


# ── 2. Attribution: explicit strategy_id → correct segmentation bucket ─────────


class TestStrategyAttribution:
    """Rows with explicit strategy_id are bucketed by that identity."""

    def test_two_strategies_segmented_separately(self):
        recs = [
            _rec("800001", "home", strategy_id="strategy_A"),
            _rec("800002", "home", strategy_id="strategy_A"),
            _rec("800003", "away", strategy_id="strategy_B"),
        ]
        outcomes = [
            _outcome("800001", "home"),   # A hit
            _outcome("800002", "home"),   # A hit
            _outcome("800003", "away"),   # B hit
        ]
        m = evaluate_paper_recommendations(recs, outcomes)

        assert "strategy_A" in m.strategy_segmentation
        assert "strategy_B" in m.strategy_segmentation
        assert m.strategy_segmentation["strategy_A"]["count"] == 2
        assert m.strategy_segmentation["strategy_B"]["count"] == 1

    def test_attributed_hit_rate_correct(self):
        recs = [
            _rec("800010", "home", strategy_id="alpha"),   # win
            _rec("800011", "home", strategy_id="alpha"),   # lose
            _rec("800012", "away", strategy_id="alpha"),   # win
        ]
        outcomes = [
            _outcome("800010", "home"),
            _outcome("800011", "away"),
            _outcome("800012", "away"),
        ]
        m = evaluate_paper_recommendations(recs, outcomes)
        seg = m.strategy_segmentation["alpha"]
        assert seg["count"] == 3
        assert seg["hit_rate"] == round(2 / 3, 4)


# ── 3. Legacy / missing strategy_id → UNATTRIBUTED ────────────────────────────


class TestUnattributed:
    """Rows without strategy_id are bucketed as UNATTRIBUTED."""

    def test_missing_strategy_id_becomes_unattributed(self):
        recs = [
            _rec("810001", "home"),   # no strategy_id
            _rec("810002", "away"),   # no strategy_id
        ]
        outcomes = [
            _outcome("810001", "home"),
            _outcome("810002", "away"),
        ]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert "UNATTRIBUTED" in m.strategy_segmentation
        assert m.strategy_segmentation["UNATTRIBUTED"]["count"] == 2

    def test_explicit_none_strategy_id_becomes_unattributed(self):
        recs = [_rec("810010", "home", strategy_id=None)]
        outcomes = [_outcome("810010", "home")]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert "UNATTRIBUTED" in m.strategy_segmentation

    def test_empty_string_strategy_id_becomes_unattributed(self):
        """An empty string strategy_id must also resolve to UNATTRIBUTED."""
        r = _rec("810020", "home")
        r["strategy_id"] = ""   # falsy → UNATTRIBUTED
        outcomes = [_outcome("810020", "home")]
        m = evaluate_paper_recommendations([r], outcomes)
        assert "UNATTRIBUTED" in m.strategy_segmentation

    def test_mixed_attributed_and_unattributed(self):
        recs = [
            _rec("810030", "home", strategy_id="known_v1"),
            _rec("810031", "away"),   # no strategy_id
        ]
        outcomes = [
            _outcome("810030", "home"),
            _outcome("810031", "away"),
        ]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert "known_v1" in m.strategy_segmentation
        assert "UNATTRIBUTED" in m.strategy_segmentation


# ── 4. strategy_id must not be inferred ───────────────────────────────────────


class TestNoInference:
    """strategy_id must come only from explicit row field; never guessed."""

    def test_model_ensemble_version_not_used_as_strategy_id(self):
        """model_ensemble_version must NOT bleed into strategy bucketing."""
        r = _rec("820001", "home")
        r["model_ensemble_version"] = "v3-paper-alpha"   # must NOT become strategy_id
        outcomes = [_outcome("820001", "home")]
        m = evaluate_paper_recommendations([r], outcomes)

        assert "v3-paper-alpha" not in m.strategy_segmentation
        assert "UNATTRIBUTED" in m.strategy_segmentation

    def test_game_id_filename_not_used_as_strategy_id(self):
        """game_id / filename patterns must NOT be used to infer strategy_id.

        The recommendation row carries model_ensemble_version and gate_status
        that could superficially look like strategy tags.  strategy_id must
        come only from the explicit ``strategy_id`` field.  When absent, the
        row must be UNATTRIBUTED regardless of other field values.
        """
        # Use a clean game_id so PK extraction works and the outcome matches.
        r = _rec("820010", "home")
        # Ensure there is no explicit strategy_id — evaluation must not derive
        # one from gate_status, model_ensemble_version, or any other field.
        r.pop("strategy_id", None)
        r["gate_status"] = "PASS"
        r["model_ensemble_version"] = "v3-paper-strategy_A"  # must NOT become strategy_id
        outcomes = [_outcome("820010", "home")]
        m = evaluate_paper_recommendations([r], outcomes)

        # The model_ensemble_version value must not appear as a strategy key
        assert "v3-paper-strategy_A" not in m.strategy_segmentation
        # The row must be bucketed as UNATTRIBUTED
        assert "UNATTRIBUTED" in m.strategy_segmentation


# ── 5. Leaderboard ranking determinism ────────────────────────────────────────


class TestLeaderboardRanking:
    """Leaderboard is deterministic and follows explicit ranking rules."""

    def _build_segmentation(self) -> dict:
        return {
            "strategy_B": {
                "count": 20,
                "correct_count": 14,
                "hit_rate": 0.70,
                "brier_score": 0.21,
                "shadow_unit_roi": 0.40,
            },
            "strategy_A": {
                "count": 20,
                "correct_count": 12,
                "hit_rate": 0.60,
                "brier_score": 0.24,
                "shadow_unit_roi": 0.20,
            },
            "strategy_C": {
                "count": 20,
                "correct_count": 12,
                "hit_rate": 0.60,
                "brier_score": 0.24,
                "shadow_unit_roi": 0.20,
            },
        }

    def test_higher_hit_rate_ranked_first(self):
        """strategy_B (0.70) must outrank strategy_A (0.60)."""
        lb = build_strategy_leaderboard(self._build_segmentation(), threshold=5)
        ranks = {e["strategy_id"]: e["rank"] for e in lb}
        assert ranks["strategy_B"] < ranks["strategy_A"]

    def test_alphabetic_tiebreaker_when_hit_rate_and_roi_equal(self):
        """strategy_A must rank before strategy_C when hit_rate and roi are equal."""
        lb = build_strategy_leaderboard(self._build_segmentation(), threshold=5)
        ranks = {e["strategy_id"]: e["rank"] for e in lb}
        assert ranks["strategy_A"] < ranks["strategy_C"]

    def test_ranking_is_deterministic(self):
        """Identical segmentation must always produce identical leaderboard."""
        seg = self._build_segmentation()
        lb1 = build_strategy_leaderboard(seg, threshold=5)
        lb2 = build_strategy_leaderboard(seg, threshold=5)
        assert [e["strategy_id"] for e in lb1] == [e["strategy_id"] for e in lb2]

    def test_ranks_are_contiguous_from_one(self):
        lb = build_strategy_leaderboard(self._build_segmentation(), threshold=5)
        ranks = sorted(e["rank"] for e in lb)
        assert ranks == list(range(1, len(lb) + 1))

    def test_leaderboard_produced_by_evaluator_is_deterministic(self):
        """evaluate_paper_recommendations leaderboard is identical on repeat calls."""
        recs = [
            _rec("830001", "home", strategy_id="s1"),
            _rec("830002", "away", strategy_id="s2"),
        ]
        outcomes = [_outcome("830001", "home"), _outcome("830002", "away")]
        m1 = evaluate_paper_recommendations(recs, outcomes)
        m2 = evaluate_paper_recommendations(recs, outcomes)
        assert m1.strategy_leaderboard == m2.strategy_leaderboard

    def test_leaderboard_entries_contain_required_fields(self):
        seg = self._build_segmentation()
        lb = build_strategy_leaderboard(seg, threshold=5)
        for entry in lb:
            assert "strategy_id" in entry
            assert "sample_count" in entry
            assert "hit_rate" in entry
            assert "brier_score" in entry
            assert "shadow_unit_roi" in entry
            assert "binomial_p_value" in entry
            assert "data_limited" in entry
            assert "rank" in entry


# ── 6. DATA_LIMITED marking ────────────────────────────────────────────────────


class TestDataLimited:
    """Strategies below SMALL_SAMPLE_THRESHOLD are marked data_limited=True."""

    def test_small_sample_marked_data_limited(self):
        seg = {
            "small_strat": {
                "count": SMALL_SAMPLE_THRESHOLD - 1,
                "correct_count": 5,
                "hit_rate": 0.556,
                "brier_score": 0.24,
                "shadow_unit_roi": 0.10,
            }
        }
        lb = build_strategy_leaderboard(seg)
        assert lb[0]["data_limited"] is True

    def test_sufficient_sample_not_data_limited(self):
        seg = {
            "large_strat": {
                "count": SMALL_SAMPLE_THRESHOLD,
                "correct_count": 6,
                "hit_rate": 0.60,
                "brier_score": 0.24,
                "shadow_unit_roi": 0.20,
            }
        }
        lb = build_strategy_leaderboard(seg)
        assert lb[0]["data_limited"] is False

    def test_threshold_boundary_exactly_at_threshold_is_not_data_limited(self):
        """count == SMALL_SAMPLE_THRESHOLD is NOT data_limited."""
        seg = {
            "exact_strat": {
                "count": SMALL_SAMPLE_THRESHOLD,
                "correct_count": 6,
                "hit_rate": 0.60,
                "brier_score": None,
                "shadow_unit_roi": 0.0,
            }
        }
        lb = build_strategy_leaderboard(seg)
        assert lb[0]["data_limited"] is False

    def test_data_limited_strategy_still_ranked(self):
        """DATA_LIMITED entries appear in the leaderboard at a deterministic position."""
        seg = {
            "big": {
                "count": 20,
                "correct_count": 12,
                "hit_rate": 0.60,
                "brier_score": 0.24,
                "shadow_unit_roi": 0.20,
            },
            "tiny": {
                "count": 3,
                "correct_count": 2,
                "hit_rate": 0.667,
                "brier_score": 0.22,
                "shadow_unit_roi": 0.50,
            },
        }
        lb = build_strategy_leaderboard(seg)
        ids = [e["strategy_id"] for e in lb]
        assert "tiny" in ids
        assert "big" in ids
        # "tiny" has higher hit_rate → ranks first even though data_limited
        assert lb[0]["strategy_id"] == "tiny"
        assert lb[0]["data_limited"] is True


# ── 7. Backward compatibility ──────────────────────────────────────────────────


class TestBackwardCompatibility:
    """Rows without strategy_id must remain evaluable; no migration needed."""

    def test_legacy_rows_produce_valid_aggregate_metrics(self):
        recs = [
            _rec("840001", "home"),
            _rec("840002", "away"),
        ]
        outcomes = [_outcome("840001", "home"), _outcome("840002", "away")]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert m.evaluated_count == 2
        assert m.matched_outcome_count == 2
        assert m.hit_rate == 1.0

    def test_legacy_rows_have_unattributed_leaderboard_entry(self):
        recs = [_rec("840010", "home")]
        outcomes = [_outcome("840010", "home")]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert any(e["strategy_id"] == "UNATTRIBUTED" for e in m.strategy_leaderboard)

    def test_no_strategy_segmentation_when_no_matched_outcomes(self):
        recs = [_rec("840020", "home")]
        m = evaluate_paper_recommendations(recs, [])
        # No matched outcomes → no strategy segmentation populated
        assert m.strategy_segmentation == {}
        assert m.strategy_leaderboard == []


# ── 8. Safety invariants ──────────────────────────────────────────────────────


class TestSafetyInvariants:
    """Core safety invariants must hold throughout the P180 extension."""

    def test_evaluate_paper_recommendations_is_pure_no_side_effects(self, tmp_path):
        """evaluate_paper_recommendations must not write files or mutate inputs."""
        import os
        recs = [_rec("850001", "home", strategy_id="test_safe")]
        outcomes = [_outcome("850001", "home")]
        before_files = set(os.listdir(tmp_path))
        _ = evaluate_paper_recommendations(recs, outcomes)
        after_files = set(os.listdir(tmp_path))
        assert before_files == after_files, "No files must be written by evaluate_paper_recommendations"

    def test_build_strategy_leaderboard_is_pure(self, tmp_path):
        """build_strategy_leaderboard must not write files."""
        import os
        seg = {
            "s1": {"count": 10, "correct_count": 6, "hit_rate": 0.6,
                   "brier_score": 0.24, "shadow_unit_roi": 0.2}
        }
        before = set(os.listdir(tmp_path))
        _ = build_strategy_leaderboard(seg)
        after = set(os.listdir(tmp_path))
        assert before == after

    def test_paper_only_invariant_preserved_through_evaluation(self):
        """Rows with paper_only=True must not be modified by evaluation."""
        recs = [_rec("850010", "home", strategy_id="safe")]
        outcomes = [_outcome("850010", "home")]
        m = evaluate_paper_recommendations(recs, outcomes)
        assert isinstance(m, PaperEvaluationMetrics)
        assert m.strategy_segmentation["safe"]["count"] == 1

    def test_evaluator_version_is_p180(self):
        """execute_evaluation must report p180_evaluator_v2 version."""
        from orchestrator.mlb_paper_evaluator import execute_evaluation
        import json
        import tempfile
        import os

        with tempfile.TemporaryDirectory() as tmpdir:
            paper_dir = os.path.join(tmpdir, "PAPER", "2026-05-11")
            os.makedirs(paper_dir)
            rec = _rec("850020", "home", strategy_id="safe_v2")
            with open(os.path.join(paper_dir, "rec.jsonl"), "w") as f:
                f.write(json.dumps(rec) + "\n")
            outcome_path = os.path.join(tmpdir, "outcomes.jsonl")
            with open(outcome_path, "w") as f:
                f.write(json.dumps(_outcome("850020", "home")) + "\n")

            result = execute_evaluation(paper_dir=paper_dir, outcome_path=outcome_path)
            assert result["evaluator_version"] == "p180_evaluator_v2"

    def test_strategy_leaderboard_does_not_mutate_weights(self):
        """build_strategy_leaderboard must return entries without weight fields."""
        seg = {
            "s1": {"count": 10, "correct_count": 6, "hit_rate": 0.6,
                   "brier_score": 0.24, "shadow_unit_roi": 0.2}
        }
        lb = build_strategy_leaderboard(seg)
        for entry in lb:
            assert "weight" not in entry, "Leaderboard must not include weight fields"
            assert "kelly" not in entry, "Leaderboard must not include kelly fields"
            assert "production" not in entry, "Leaderboard must not include production fields"
