"""
Phase 8 Autonomous Optimization Governance — Integration Tests

8 scenarios / 32 tests + 1 success marker

Scenario 1: Mostly PENDING_CLOSING → DATA_WAITING
Scenario 2: Enough COMPUTED CLV → DATA_READY
Scenario 3: Negative CLV / poor Brier → MODEL_WEAKNESS_DETECTED
Scenario 4: Stale daemon / no recent runs → SYSTEM_RELIABILITY_ISSUE
Scenario 5: Duplicate modules / cleanup flags → ARCHITECTURE_DEBT
Scenario 6: Decision card missing phase fields → OPERATOR_UX_GAP
Scenario 7: Planner blocks model reinforcement when DATA_WAITING
Scenario 8: Planner allows model validation when DATA_READY

SUCCESS MARKER: PHASE_8_AUTONOMOUS_OPTIMIZATION_GOVERNANCE_VERIFIED
"""
from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from orchestrator import optimization_state
from orchestrator import training_memory


# ─────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────

def _make_phase6_status(
    computed: int = 0,
    pending: int = 14,
    blocked: int = 0,
) -> dict:
    total = computed + pending + blocked
    return {
        "dates": ["2026-04-30"],
        "registry_rows": total,
        "clv_computed": computed,
        "clv_pending_closing": pending,
        "clv_blocked": blocked,
        "clv_total": total,
        "eligible_for_simulation": 3,
        "all_clv_pending": computed == 0 and pending > 0,
        "next_required_event": "wait_for_market_settlement" if computed == 0 else "",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def _patch_phase6(status: dict):
    """Context manager: patch phase6_data_registry.get_phase6_status."""
    return patch(
        "orchestrator.phase6_data_registry.get_phase6_status",
        return_value=status,
    )


def _patch_clv_summary(avg_clv: float | None = None, total: int = 0):
    """Context manager: patch training_memory.get_clv_outcome_summary."""
    summary = {
        "total": total,
        "positive_count": 0,
        "negative_count": 0,
        "flat_count": 0,
        "avg_clv": avg_clv,
        "positive_rate": 0.0,
    }
    return patch(
        "orchestrator.training_memory.get_clv_outcome_summary",
        return_value=summary,
    )


# ─────────────────────────────────────────────────────────────────
# Scenario 1: Mostly PENDING_CLOSING → DATA_WAITING
# ─────────────────────────────────────────────────────────────────

class TestDataWaitingState:
    def test_all_pending_clv_returns_data_waiting(self):
        """14 PENDING_CLOSING, 0 COMPUTED → DATA_WAITING."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert result["state"] == optimization_state.STATE_DATA_WAITING

    def test_data_waiting_blocks_strategy_reinforcement(self):
        """DATA_WAITING must block strategy-reinforcement tasks."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert optimization_state.FAMILY_STRATEGY_REINFORCEMENT in result["blocked_task_families"]

    def test_data_waiting_blocks_model_patch(self):
        """DATA_WAITING must block model-patch tasks."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert optimization_state.FAMILY_MODEL_PATCH in result["blocked_task_families"]

    def test_data_waiting_allows_simulation(self):
        """DATA_WAITING allows simulation-only tasks."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert optimization_state.FAMILY_SIMULATION in result["allowed_task_families"]

    def test_data_waiting_includes_reason(self):
        """DATA_WAITING state result must include a reason string."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert len(result["reasons"]) >= 1
        assert any("pending" in r.lower() or "computed" in r.lower() for r in result["reasons"])


# ─────────────────────────────────────────────────────────────────
# Scenario 2: Enough COMPUTED CLV → DATA_READY
# ─────────────────────────────────────────────────────────────────

class TestDataReadyState:
    def test_computed_clv_triggers_data_ready(self):
        """5 COMPUTED, 5 PENDING → DATA_READY (50% ≥ 10% threshold, ≥ 1 absolute)."""
        with _patch_phase6(_make_phase6_status(computed=5, pending=5)):
            result = optimization_state.classify()
        assert result["state"] == optimization_state.STATE_DATA_READY

    def test_data_ready_allows_model_validation(self):
        """DATA_READY must allow model-validation tasks."""
        with _patch_phase6(_make_phase6_status(computed=5, pending=5)):
            result = optimization_state.classify()
        assert optimization_state.FAMILY_MODEL_VALIDATION in result["allowed_task_families"]

    def test_data_ready_allows_strategy_reinforcement(self):
        """DATA_READY must allow strategy-reinforcement tasks."""
        with _patch_phase6(_make_phase6_status(computed=5, pending=5)):
            result = optimization_state.classify()
        assert optimization_state.FAMILY_STRATEGY_REINFORCEMENT in result["allowed_task_families"]

    def test_data_ready_nothing_blocked(self):
        """DATA_READY should have an empty blocked list."""
        with _patch_phase6(_make_phase6_status(computed=5, pending=5)):
            result = optimization_state.classify()
        assert result["blocked_task_families"] == []


# ─────────────────────────────────────────────────────────────────
# Scenario 3: Negative CLV / poor Brier → MODEL_WEAKNESS_DETECTED
# ─────────────────────────────────────────────────────────────────

class TestModelWeaknessState:
    def test_negative_avg_clv_triggers_weakness(self):
        """avg_clv < -0.010 → MODEL_WEAKNESS_DETECTED (with enough computed CLV)."""
        with _patch_phase6(_make_phase6_status(computed=10, pending=4)), \
             _patch_clv_summary(avg_clv=-0.025, total=10):
            result = optimization_state.classify()
        assert result["state"] == optimization_state.STATE_MODEL_WEAKNESS

    def test_model_weakness_blocks_strategy_reinforcement(self):
        """MODEL_WEAKNESS_DETECTED blocks strategy-reinforcement."""
        with _patch_phase6(_make_phase6_status(computed=10, pending=4)), \
             _patch_clv_summary(avg_clv=-0.025, total=10):
            result = optimization_state.classify()
        assert optimization_state.FAMILY_STRATEGY_REINFORCEMENT in result["blocked_task_families"]

    def test_model_weakness_allows_patch(self):
        """MODEL_WEAKNESS_DETECTED must allow model-patch tasks."""
        with _patch_phase6(_make_phase6_status(computed=10, pending=4)), \
             _patch_clv_summary(avg_clv=-0.025, total=10):
            result = optimization_state.classify()
        assert optimization_state.FAMILY_MODEL_PATCH in result["allowed_task_families"]

    def test_model_weakness_includes_clv_reason(self):
        """MODEL_WEAKNESS_DETECTED reason should mention avg_clv."""
        with _patch_phase6(_make_phase6_status(computed=10, pending=4)), \
             _patch_clv_summary(avg_clv=-0.025, total=10):
            result = optimization_state.classify()
        assert any("avg_clv" in r or "clv" in r.lower() for r in result["reasons"])


# ─────────────────────────────────────────────────────────────────
# Scenario 4: Stale daemon / no recent runs → SYSTEM_RELIABILITY_ISSUE
# ─────────────────────────────────────────────────────────────────

class TestSystemReliabilityState:
    def _make_stale_heartbeat_path(self, tmpdir: Path) -> Path:
        """Write a heartbeat file with a very old timestamp."""
        hb_path = tmpdir / "daemon_heartbeat.jsonl"
        old_ts = "2026-01-01T00:00:00Z"  # months ago — guaranteed stale
        hb_path.write_text(json.dumps({"timestamp": old_ts}) + "\n", encoding="utf-8")
        return hb_path

    def test_stale_daemon_triggers_reliability_issue(self):
        """Stale daemon heartbeat → SYSTEM_RELIABILITY_ISSUE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            hb_path = self._make_stale_heartbeat_path(td)
            with _patch_phase6(_make_phase6_status(computed=5, pending=5)), \
                 patch.object(optimization_state, "_HEARTBEAT_PATH", hb_path), \
                 patch.object(optimization_state, "_STRATEGY_STATE_PATH", td / "strategy_state.json"):
                # Create dummy strategy_state so that artifact check passes
                (td / "strategy_state.json").write_text("{}", encoding="utf-8")
                result = optimization_state._check_system_reliability()
        assert result["issue_detected"] is True
        assert any("stale" in r.lower() or "heartbeat" in r.lower() for r in result["reasons"])

    def test_missing_heartbeat_triggers_reliability_issue(self):
        """Missing heartbeat file → SYSTEM_RELIABILITY_ISSUE."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            nonexistent_hb = td / "daemon_heartbeat.jsonl"  # does not exist
            with patch.object(optimization_state, "_HEARTBEAT_PATH", nonexistent_hb), \
                 patch.object(optimization_state, "_STRATEGY_STATE_PATH", td / "strategy_state.json"):
                (td / "strategy_state.json").write_text("{}", encoding="utf-8")
                result = optimization_state._check_system_reliability()
        assert result["issue_detected"] is True
        assert any("missing" in r.lower() or "heartbeat" in r.lower() for r in result["reasons"])

    def test_system_reliability_blocks_model_patch(self):
        """SYSTEM_RELIABILITY_ISSUE blocks model-patch tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            hb_path = self._make_stale_heartbeat_path(td)
            with _patch_phase6(_make_phase6_status(computed=5, pending=5)), \
                 patch.object(optimization_state, "_HEARTBEAT_PATH", hb_path), \
                 patch.object(optimization_state, "_STRATEGY_STATE_PATH", td / "strategy_state.json"):
                (td / "strategy_state.json").write_text("{}", encoding="utf-8")
                result = optimization_state.classify()
        assert result["state"] == optimization_state.STATE_SYSTEM_RELIABILITY
        assert optimization_state.FAMILY_MODEL_PATCH in result["blocked_task_families"]

    def test_system_reliability_allows_maintenance(self):
        """SYSTEM_RELIABILITY_ISSUE allows maintenance tasks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            hb_path = self._make_stale_heartbeat_path(td)
            with _patch_phase6(_make_phase6_status(computed=5, pending=5)), \
                 patch.object(optimization_state, "_HEARTBEAT_PATH", hb_path), \
                 patch.object(optimization_state, "_STRATEGY_STATE_PATH", td / "strategy_state.json"):
                (td / "strategy_state.json").write_text("{}", encoding="utf-8")
                result = optimization_state.classify()
        assert optimization_state.FAMILY_MAINTENANCE in result["allowed_task_families"]


# ─────────────────────────────────────────────────────────────────
# Scenario 5: Duplicate modules / cleanup flags → ARCHITECTURE_DEBT
# ─────────────────────────────────────────────────────────────────

class TestArchitectureDebtState:
    def test_many_cleanup_open_items_detected(self):
        """3+ unchecked items in CLEANUP_PLAN.md → architecture debt detected."""
        fake_cleanup = "# Cleanup Plan\n- [ ] item1\n- [ ] item2\n- [ ] item3\n"
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            cleanup_path = td / "CLEANUP_PLAN.md"
            cleanup_path.write_text(fake_cleanup, encoding="utf-8")
            with patch.object(optimization_state, "_WIKI_CLEANUP", cleanup_path), \
                 patch.object(optimization_state, "_WIKI_INVENTORY", td / "INVENTORY.md"):
                result = optimization_state._check_architecture_debt()
        assert result["debt_detected"] is True
        assert any("cleanup" in r.lower() or "open_item" in r.lower() for r in result["reasons"])

    def test_duplicate_inventory_entries_detected(self):
        """Duplicate module names in INVENTORY.md → architecture debt detected."""
        fake_inventory = (
            "# Inventory\n- closing_odds_monitor\n- closing_odds_monitor\n- strategy_tick\n"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            inv_path = td / "INVENTORY.md"
            inv_path.write_text(fake_inventory, encoding="utf-8")
            with patch.object(optimization_state, "_WIKI_INVENTORY", inv_path), \
                 patch.object(optimization_state, "_WIKI_CLEANUP", td / "CLEANUP_PLAN.md"):
                result = optimization_state._check_architecture_debt()
        assert result["debt_detected"] is True
        assert any("duplicate" in r.lower() for r in result["reasons"])


# ─────────────────────────────────────────────────────────────────
# Scenario 6: Decision card missing phase fields → OPERATOR_UX_GAP
# ─────────────────────────────────────────────────────────────────

class TestOperatorUXGapState:
    def test_missing_phase6_block_triggers_ux_gap(self):
        """Decision card payload missing phase6.available → OPERATOR_UX_GAP."""
        payload = {
            "phase6": {"available": False, "error": "not loaded"},
            "phase7": {"available": True},
            "phase8": {},
        }
        result = optimization_state._check_operator_ux_gap(payload)
        assert result["gap_detected"] is True
        assert any("phase6" in r for r in result["reasons"])

    def test_missing_phase7_block_triggers_ux_gap(self):
        """Decision card payload missing phase7.available → OPERATOR_UX_GAP."""
        payload = {
            "phase6": {"available": True, "clv_computed": 5, "clv_pending_closing": 5, "dates": []},
            "phase7": {"available": False, "error": "not loaded"},
            "phase8": {},
        }
        result = optimization_state._check_operator_ux_gap(payload)
        assert result["gap_detected"] is True
        assert any("phase7" in r for r in result["reasons"])

    def test_complete_payload_no_ux_gap(self):
        """Complete phase6 and phase7 blocks → no UX gap from those fields."""
        payload = {
            "phase6": {
                "available": True,
                "clv_computed": 5,
                "clv_pending_closing": 3,
                "dates": ["2026-04-30"],
            },
            "phase7": {"available": True},
            "phase8": {"available": True},
        }
        result = optimization_state._check_operator_ux_gap(payload)
        # Should not flag phase6/phase7 gaps
        assert not any("phase6" in r or "phase7" in r for r in result["reasons"])


# ─────────────────────────────────────────────────────────────────
# Scenario 7: Planner blocks model reinforcement when DATA_WAITING
# ─────────────────────────────────────────────────────────────────

class TestPlannerGovernanceDataWaiting:
    def test_strategy_reinforcement_family_is_blocked(self):
        """When state=DATA_WAITING, strategy-reinforcement is in blocked_task_families."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert result["state"] == optimization_state.STATE_DATA_WAITING
        assert optimization_state.is_task_family_blocked(
            optimization_state.FAMILY_STRATEGY_REINFORCEMENT, result
        )

    def test_model_validation_family_is_blocked(self):
        """When state=DATA_WAITING, model-validation is blocked."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert optimization_state.is_task_family_blocked(
            optimization_state.FAMILY_MODEL_VALIDATION, result
        )

    def test_simulation_family_is_not_blocked(self):
        """When state=DATA_WAITING, simulation is allowed."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert not optimization_state.is_task_family_blocked(
            optimization_state.FAMILY_SIMULATION, result
        )

    def test_is_task_family_allowed_returns_true_for_simulation(self):
        """is_task_family_allowed() returns True for simulation in DATA_WAITING."""
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            result = optimization_state.classify()
        assert optimization_state.is_task_family_allowed(
            optimization_state.FAMILY_SIMULATION, result
        )


# ─────────────────────────────────────────────────────────────────
# Scenario 8: Planner allows model validation when DATA_READY
# ─────────────────────────────────────────────────────────────────

class TestPlannerGovernanceDataReady:
    def test_model_validation_allowed_when_data_ready(self):
        """DATA_READY: model-validation is allowed and not blocked."""
        with _patch_phase6(_make_phase6_status(computed=8, pending=6)):
            result = optimization_state.classify()
        assert result["state"] == optimization_state.STATE_DATA_READY
        assert optimization_state.is_task_family_allowed(
            optimization_state.FAMILY_MODEL_VALIDATION, result
        )
        assert not optimization_state.is_task_family_blocked(
            optimization_state.FAMILY_MODEL_VALIDATION, result
        )

    def test_model_patch_allowed_when_data_ready(self):
        """DATA_READY: model-patch is allowed."""
        with _patch_phase6(_make_phase6_status(computed=8, pending=6)):
            result = optimization_state.classify()
        assert optimization_state.is_task_family_allowed(
            optimization_state.FAMILY_MODEL_PATCH, result
        )

    def test_strategy_reinforcement_allowed_when_data_ready(self):
        """DATA_READY: strategy-reinforcement is allowed."""
        with _patch_phase6(_make_phase6_status(computed=8, pending=6)):
            result = optimization_state.classify()
        assert optimization_state.is_task_family_allowed(
            optimization_state.FAMILY_STRATEGY_REINFORCEMENT, result
        )

    def test_data_ready_recommended_action_mentions_learning(self):
        """DATA_READY recommended action should mention model validation or learning."""
        with _patch_phase6(_make_phase6_status(computed=8, pending=6)):
            result = optimization_state.classify()
        action = result["recommended_next_action"].lower()
        assert "model" in action or "learning" in action or "validation" in action


# ─────────────────────────────────────────────────────────────────
# Training memory state transition recording
# ─────────────────────────────────────────────────────────────────

class TestTrainingMemoryStateTransitions:
    def test_records_state_transition(self):
        """record_optimization_state_transition stores a transition entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with patch.object(training_memory, "MEMORY_PATH", mem_path):
                training_memory.record_optimization_state_transition(
                    new_state="DATA_WAITING",
                    reasons=["all_clv_pending: 14 records"],
                    previous_state="",
                )
                transitions = training_memory.get_optimization_state_transitions()
        assert len(transitions) == 1
        assert transitions[0]["new_state"] == "DATA_WAITING"
        assert transitions[0]["previous_state"] == ""

    def test_does_not_change_consecutive_counters(self):
        """State transition recording must not affect consecutive_successes/failures."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with patch.object(training_memory, "MEMORY_PATH", mem_path):
                before = training_memory.load_memory()
                cs_before = before.get("consecutive_successes", 0)
                cf_before = before.get("consecutive_failures", 0)
                training_memory.record_optimization_state_transition(
                    "DATA_READY", ["computed_clv_available"], ""
                )
                after = training_memory.load_memory()
        assert after.get("consecutive_successes", 0) == cs_before
        assert after.get("consecutive_failures", 0) == cf_before

    def test_skips_unchanged_state(self):
        """Transition with same previous and new state is not recorded (noise reduction)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with patch.object(training_memory, "MEMORY_PATH", mem_path):
                # First: record DATA_WAITING
                training_memory.record_optimization_state_transition(
                    "DATA_WAITING", ["reason1"], ""
                )
                # Second: same state again (auto-detects previous from last entry)
                training_memory.record_optimization_state_transition(
                    "DATA_WAITING", ["reason1"], "DATA_WAITING"
                )
                transitions = training_memory.get_optimization_state_transitions()
        # Only 1 entry: the second same-state call is skipped
        assert len(transitions) == 1

    def test_get_transitions_returns_newest_last(self):
        """get_optimization_state_transitions returns entries in chronological order."""
        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with patch.object(training_memory, "MEMORY_PATH", mem_path):
                training_memory.record_optimization_state_transition(
                    "DATA_WAITING", ["reason"], ""
                )
                training_memory.record_optimization_state_transition(
                    "DATA_READY", ["computed=5"], "DATA_WAITING"
                )
                transitions = training_memory.get_optimization_state_transitions()
        assert transitions[-1]["new_state"] == "DATA_READY"
        assert transitions[0]["new_state"] == "DATA_WAITING"


# ─────────────────────────────────────────────────────────────────
# Decision card Phase 8 governance block
# ─────────────────────────────────────────────────────────────────

class TestDecisionCardPhase8:
    def test_compute_phase8_status_returns_available(self):
        """compute_phase8_status() should return available=True when classifier works."""
        from scripts.ops_decision_card import compute_phase8_status
        with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
            status = compute_phase8_status()
        assert status["available"] is True
        assert "current_state" in status
        assert "allowed_task_families" in status
        assert "blocked_task_families" in status

    def test_phase8_block_in_build_payload(self):
        """build_payload() includes 'phase8' key."""
        from scripts.ops_decision_card import build_payload
        payload = build_payload()
        assert "phase8" in payload

    def test_render_card_includes_governance_section(self):
        """render_card() output includes Phase 8 governance section."""
        from scripts.ops_decision_card import build_payload, render_card
        payload = build_payload()
        rendered = render_card(payload)
        assert "PHASE 8" in rendered or "OPTIMIZATION GOVERNANCE" in rendered


# ─────────────────────────────────────────────────────────────────
# Success marker
# ─────────────────────────────────────────────────────────────────

def test_phase8_autonomous_optimization_governance_verified():
    """
    SUCCESS MARKER — all Phase 8 governance checks pass.

    This test asserts that:
    1. DATA_WAITING correctly blocks strategy reinforcement.
    2. DATA_READY correctly allows model validation.
    3. The classify() function returns a well-formed result.
    4. Training memory records state transitions without side effects.
    """
    # Check 1: DATA_WAITING blocks reinforcement
    with _patch_phase6(_make_phase6_status(computed=0, pending=14)):
        waiting = optimization_state.classify()
    assert waiting["state"] == optimization_state.STATE_DATA_WAITING
    assert optimization_state.FAMILY_STRATEGY_REINFORCEMENT in waiting["blocked_task_families"]

    # Check 2: DATA_READY allows model validation
    with _patch_phase6(_make_phase6_status(computed=8, pending=6)):
        ready = optimization_state.classify()
    assert ready["state"] == optimization_state.STATE_DATA_READY
    assert optimization_state.FAMILY_MODEL_VALIDATION in ready["allowed_task_families"]

    # Check 3: Classify result is well-formed
    for key in ("state", "reasons", "allowed_task_families", "blocked_task_families",
                "recommended_next_action", "classified_at"):
        assert key in ready, f"Missing key: {key}"

    # Check 4: State transition recording has no side effects
    with tempfile.TemporaryDirectory() as tmpdir:
        mem_path = Path(tmpdir) / "training_memory.json"
        with patch.object(training_memory, "MEMORY_PATH", mem_path):
            before = training_memory.load_memory()
            training_memory.record_optimization_state_transition(
                "DATA_WAITING", ["test_reason"], ""
            )
            after = training_memory.load_memory()
    assert after["consecutive_successes"] == before.get("consecutive_successes", 0)
    assert after["consecutive_failures"] == before.get("consecutive_failures", 0)

    # Final marker
    assert True, "PHASE_8_AUTONOMOUS_OPTIMIZATION_GOVERNANCE_VERIFIED"
