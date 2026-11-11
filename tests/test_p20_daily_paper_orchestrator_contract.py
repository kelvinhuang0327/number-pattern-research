"""
tests/test_p20_daily_paper_orchestrator_contract.py

Unit tests for P20 contract constants and dataclasses.
"""
import pytest

from wbc_backend.recommendation.p20_daily_paper_orchestrator_contract import (
    EXPECTED_P16_6_GATE,
    EXPECTED_P17_REPLAY_GATE,
    EXPECTED_P19_GATE,
    P20_BLOCKED_CONTRACT_VIOLATION,
    P20_BLOCKED_P16_6_NOT_READY,
    P20_BLOCKED_P17_REPLAY_NOT_READY,
    P20_BLOCKED_P19_NOT_READY,
    P20_DAILY_PAPER_ORCHESTRATOR_READY,
    P20_FAIL_INPUT_MISSING,
    P20_FAIL_NON_DETERMINISTIC,
    STEP_P16_6_RECOMMENDATION_GATE,
    STEP_P17_REPLAY_WITH_P19_IDENTITY,
    STEP_P19_IDENTITY_JOIN_REPAIR,
    STEP_P20_DAILY_SUMMARY,
    REQUIRED_STEP_NAMES,
    P20PipelineStepResult,
    P20DailyPaperRunSummary,
    P20DailyPaperGateResult,
    P20ArtifactManifest,
)


# ---------------------------------------------------------------------------
# Gate constants
# ---------------------------------------------------------------------------

class TestGateConstants:
    def test_ready_constant_unique(self):
        assert P20_DAILY_PAPER_ORCHESTRATOR_READY == "P20_DAILY_PAPER_ORCHESTRATOR_READY"

    def test_blocked_constants_non_empty(self):
        for c in [
            P20_BLOCKED_P16_6_NOT_READY,
            P20_BLOCKED_P19_NOT_READY,
            P20_BLOCKED_P17_REPLAY_NOT_READY,
            P20_BLOCKED_CONTRACT_VIOLATION,
            P20_FAIL_INPUT_MISSING,
            P20_FAIL_NON_DETERMINISTIC,
        ]:
            assert isinstance(c, str) and len(c) > 0

    def test_all_gate_constants_distinct(self):
        constants = [
            P20_DAILY_PAPER_ORCHESTRATOR_READY,
            P20_BLOCKED_P16_6_NOT_READY,
            P20_BLOCKED_P19_NOT_READY,
            P20_BLOCKED_P17_REPLAY_NOT_READY,
            P20_BLOCKED_CONTRACT_VIOLATION,
            P20_FAIL_INPUT_MISSING,
            P20_FAIL_NON_DETERMINISTIC,
        ]
        assert len(constants) == len(set(constants))

    def test_expected_upstream_gates(self):
        assert EXPECTED_P16_6_GATE == "P16_6_PAPER_RECOMMENDATION_GATE_READY"
        assert EXPECTED_P19_GATE == "P19_IDENTITY_JOIN_REPAIR_READY"
        assert EXPECTED_P17_REPLAY_GATE == "P17_PAPER_LEDGER_READY"


# ---------------------------------------------------------------------------
# Step constants
# ---------------------------------------------------------------------------

class TestStepConstants:
    def test_required_steps_non_empty(self):
        assert len(REQUIRED_STEP_NAMES) >= 4

    def test_required_steps_contains_all_phases(self):
        assert STEP_P16_6_RECOMMENDATION_GATE in REQUIRED_STEP_NAMES
        assert STEP_P19_IDENTITY_JOIN_REPAIR in REQUIRED_STEP_NAMES
        assert STEP_P17_REPLAY_WITH_P19_IDENTITY in REQUIRED_STEP_NAMES
        assert STEP_P20_DAILY_SUMMARY in REQUIRED_STEP_NAMES


# ---------------------------------------------------------------------------
# P20PipelineStepResult
# ---------------------------------------------------------------------------

class TestP20PipelineStepResult:
    def test_frozen(self):
        step = P20PipelineStepResult(
            step_name="S1",
            gate_decision="READY",
            passed=True,
        )
        with pytest.raises((AttributeError, TypeError)):
            step.passed = False  # type: ignore[misc]

    def test_defaults(self):
        step = P20PipelineStepResult(
            step_name="S1",
            gate_decision="READY",
            passed=True,
        )
        assert step.artifact_paths == ()
        assert step.error_message is None


# ---------------------------------------------------------------------------
# P20ArtifactManifest
# ---------------------------------------------------------------------------

class TestP20ArtifactManifest:
    def test_frozen(self):
        m = P20ArtifactManifest(run_date="2026-05-12")
        with pytest.raises((AttributeError, TypeError)):
            m.run_date = "2026-01-01"  # type: ignore[misc]

    def test_default_safety_invariants(self):
        m = P20ArtifactManifest(run_date="2026-05-12")
        assert m.paper_only is True
        assert m.production_ready is False


# ---------------------------------------------------------------------------
# P20DailyPaperRunSummary
# ---------------------------------------------------------------------------

def _make_summary(**overrides) -> P20DailyPaperRunSummary:
    defaults = dict(
        run_date="2026-05-12",
        p20_gate=P20_DAILY_PAPER_ORCHESTRATOR_READY,
        source_p16_6_gate=EXPECTED_P16_6_GATE,
        source_p19_gate=EXPECTED_P19_GATE,
        source_p17_replay_gate=EXPECTED_P17_REPLAY_GATE,
        n_input_rows=1577,
        n_recommended_rows=324,
        n_active_paper_entries=324,
        n_settled_win=171,
        n_settled_loss=153,
        n_unsettled=0,
        settlement_join_method="JOIN_BY_GAME_ID",
        game_id_coverage=1.0,
        total_stake_units=81.0,
        total_pnl_units=8.73,
        roi_units=0.1078,
        hit_rate=0.5278,
        max_drawdown_pct=1.85,
        sharpe_ratio=0.10,
        paper_only=True,
        production_ready=False,
        generated_artifact_count=4,
    )
    defaults.update(overrides)
    return P20DailyPaperRunSummary(**defaults)


class TestP20DailyPaperRunSummary:
    def test_frozen(self):
        s = _make_summary()
        with pytest.raises((AttributeError, TypeError)):
            s.paper_only = False  # type: ignore[misc]

    def test_safety_invariants_default(self):
        s = _make_summary()
        assert s.paper_only is True
        assert s.production_ready is False

    def test_counts_match(self):
        s = _make_summary()
        assert s.n_settled_win + s.n_settled_loss + s.n_unsettled == s.n_active_paper_entries


# ---------------------------------------------------------------------------
# P20DailyPaperGateResult
# ---------------------------------------------------------------------------

class TestP20DailyPaperGateResult:
    def test_frozen(self):
        g = P20DailyPaperGateResult(
            run_date="2026-05-12",
            p20_gate=P20_DAILY_PAPER_ORCHESTRATOR_READY,
            paper_only=True,
            production_ready=False,
            n_recommended_rows=324,
            n_active_paper_entries=324,
            n_settled_win=171,
            n_settled_loss=153,
            n_unsettled=0,
            roi_units=0.1078,
            hit_rate=0.5278,
            settlement_join_method="JOIN_BY_GAME_ID",
            game_id_coverage=1.0,
        )
        with pytest.raises((AttributeError, TypeError)):
            g.paper_only = False  # type: ignore[misc]
