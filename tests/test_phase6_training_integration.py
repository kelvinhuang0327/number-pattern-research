"""
Tests — Phase 6 Training Loop Integration
==========================================

Five test scenarios verifying the Phase 6 pipeline integrates correctly
with the autonomous training scheduler:

  1. simulation uses registry rows but NOT PENDING_CLOSING as realized CLV
  2. strategy does NOT reinforce on PENDING_CLOSING CLV
  3. training_memory records CLV state without incrementing success counters
  4. decision card shows Phase 6 pending/computed counts
  5. closing monitor upgrades PENDING → COMPUTED ONLY with valid closing odds
"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ─────────────────────────────────────────────
# Shared fixtures & helpers
# ─────────────────────────────────────────────

_PRED_TIME = "2026-04-30T08:35:10Z"   # reference prediction timestamp
_BEFORE_PRED = "2026-04-30T05:16:54Z"  # snapshot BEFORE prediction (stale)
_AFTER_PRED  = "2026-04-30T10:00:00Z"  # timestamp AFTER prediction (valid)


def _make_registry_row(
    prediction_id: str = "pred-001",
    game_id: str = "game-001",
    selection: str = "home",
    ev_percent: float = 4.5,
    ml_predicted_probability: float = 0.58,
    implied_probability: float = 0.535,
    execution_mode: str = "RESEARCH_ONLY",
    governance_status: str = "VALIDATED_ML_ONLY",
) -> dict:
    return {
        "prediction_id": prediction_id,
        "canonical_match_id": game_id,
        "selection": selection,
        "ev_percent": ev_percent,
        "ml_predicted_probability": ml_predicted_probability,
        "implied_probability": implied_probability,
        "execution_mode": execution_mode,
        "governance_status": governance_status,
        "prediction_time_utc": _PRED_TIME,
        "market_type": "home_ml",
        "odds_snapshot_ref": "snap-001",
        "regime": "wbc_2026",
        "clv_usable": True,
    }


def _make_clv_row(
    prediction_id: str = "pred-001",
    game_id: str = "game-001",
    selection: str = "home",
    clv_status: str = "PENDING_CLOSING",
    clv_value: float | None = None,
    closing_odds: float | None = None,
    closing_ts: str | None = None,
    implied_prob: float = 0.535,
) -> dict:
    return {
        "prediction_id": prediction_id,
        "canonical_match_id": game_id,
        "selection": selection,
        "clv_status": clv_status,
        "clv_value": clv_value,
        "closing_odds": closing_odds,
        "closing_ts": closing_ts,
        "prediction_time_utc": _PRED_TIME,
        "implied_probability_at_prediction": implied_prob,
        "odds_snapshot_ref": "snap-001",
        "clv_record_id": f"6u-{prediction_id}",
        "source_phase": "6U",
        "live_bet_submitted": False,
        "governance_status": "VALIDATED_ML_ONLY",
        "execution_mode": "RESEARCH_ONLY",
        "clv_usable": True,
    }


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _make_timeline_row(
    game_id: str = "game-001",
    closing_home_ml: float | None = None,
    closing_ts: str | None = None,
    ext_closing_home_ml: float | None = None,
    ext_closing_ts: str | None = None,
) -> dict:
    return {
        "game_id": game_id,
        "closing_home_ml": closing_home_ml,
        "closing_away_ml": None,
        "closing_ts": closing_ts,
        "external_closing_home_ml": ext_closing_home_ml,
        "external_closing_away_ml": None,
        "external_closing_ts": ext_closing_ts,  # matches closing_odds_monitor field name
        "source": "live",
    }


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 1: simulation uses registry rows but NOT PENDING_CLOSING as CLV
# ═══════════════════════════════════════════════════════════════════════════

class TestScenario1SimulationWithRegistryRows:
    """simulation_tick consumes 6T registry rows for EV scenarios only."""

    def test_registry_rows_to_simulation_records_excludes_result_and_roi(self):
        from orchestrator.phase6_data_registry import registry_rows_to_simulation_records
        rows = [_make_registry_row()]
        sim = registry_rows_to_simulation_records(rows)
        assert len(sim) == 1
        rec = sim[0]
        assert rec["result"] is None, "No settled result — must not be set"
        assert rec["roi"] is None, "No ROI — must not be set"
        assert rec["pnl"] is None, "No PnL — must not be set"

    def test_registry_rows_have_predicted_and_market_prob(self):
        from orchestrator.phase6_data_registry import registry_rows_to_simulation_records
        rows = [_make_registry_row(ml_predicted_probability=0.60, implied_probability=0.54)]
        sim = registry_rows_to_simulation_records(rows)
        rec = sim[0]
        assert rec["predicted_prob"] == pytest.approx(0.60)
        assert rec["market_prob"] == pytest.approx(0.54)

    def test_registry_rows_missing_probs_are_skipped(self):
        from orchestrator.phase6_data_registry import registry_rows_to_simulation_records
        bad_row = _make_registry_row()
        bad_row["ml_predicted_probability"] = None
        sim = registry_rows_to_simulation_records([bad_row])
        assert sim == [], "Row with None prob must be skipped"

    def test_compute_phase6_ev_analysis_returns_no_realized_clv(self):
        """_compute_phase6_ev_analysis() must not use PENDING_CLOSING as realized CLV."""
        from orchestrator import simulation_tick

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir)
            date = "2026-04-30"

            # Write 6T registry file
            reg_path = reports_dir / f"prediction_registry_6t_{date}.jsonl"
            _write_jsonl(reg_path, [
                _make_registry_row("pred-001", ev_percent=5.0),
                _make_registry_row("pred-002", ev_percent=-1.0),   # negative EV
            ])

            # Write 6U CLV file — all PENDING
            clv_path = reports_dir / f"clv_validation_records_6u_{date}.jsonl"
            _write_jsonl(clv_path, [
                _make_clv_row("pred-001", clv_status="PENDING_CLOSING"),
                _make_clv_row("pred-002", clv_status="PENDING_CLOSING"),
            ])

            with patch(
                "orchestrator.phase6_data_registry.REPORTS_DIR",
                reports_dir,
            ):
                result = simulation_tick._compute_phase6_ev_analysis()

        # Key assertions: PENDING_CLOSING rows excluded from CLV reinforcement
        assert result["clv_pending"] == 2
        assert result["clv_computed"] == 0
        assert result["clv_pending_excluded_from_reinforcement"] is True
        # n_registry_rows loaded for EV analysis
        assert result["n_registry_rows"] == 2
        # Only 1 has positive EV
        assert result["n_eligible_ev"] == 1

    def test_ev_analysis_source_label(self):
        from orchestrator import simulation_tick
        with patch(
            "orchestrator.phase6_data_registry.get_phase6_status",
            return_value={
                "dates": [],
                "clv_computed": 0,
                "clv_pending_closing": 0,
            },
        ):
            result = simulation_tick._compute_phase6_ev_analysis()
        assert result["source"] == "phase6t_registry"


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 2: strategy does NOT reinforce on PENDING_CLOSING CLV
# ═══════════════════════════════════════════════════════════════════════════

class TestScenario2StrategyNoPendingReinforcement:
    """strategy_tick loads Phase 6U CLV state; no CLV reinforcement on PENDING."""

    def test_load_phase6_clv_state_all_pending(self):
        from orchestrator import strategy_tick

        with patch(
            "orchestrator.phase6_data_registry.get_phase6_status",
            return_value={
                "clv_computed": 0,
                "clv_pending_closing": 14,
                "clv_blocked": 0,
            },
        ):
            state = strategy_tick._load_phase6_clv_state()

        assert state["clv_state"] == "WAITING_FOR_MARKET_SETTLEMENT"
        assert state["pending"] == 14
        assert state["computed"] == 0
        assert state["eligible_for_reinforcement"] is False

    def test_load_phase6_clv_state_some_computed(self):
        from orchestrator import strategy_tick

        with patch(
            "orchestrator.phase6_data_registry.get_phase6_status",
            return_value={
                "clv_computed": 3,
                "clv_pending_closing": 11,
                "clv_blocked": 0,
            },
        ):
            state = strategy_tick._load_phase6_clv_state()

        assert state["clv_state"] == "COMPUTED"
        assert state["computed"] == 3
        assert state["eligible_for_reinforcement"] is True

    def test_load_phase6_clv_state_no_data(self):
        from orchestrator import strategy_tick

        with patch(
            "orchestrator.phase6_data_registry.get_phase6_status",
            return_value={
                "clv_computed": 0,
                "clv_pending_closing": 0,
                "clv_blocked": 0,
            },
        ):
            state = strategy_tick._load_phase6_clv_state()

        assert state["clv_state"] == "NO_PHASE6_DATA"
        assert state["eligible_for_reinforcement"] is False

    def test_strategy_tick_result_includes_phase6_clv_state(self):
        """run_strategy_tick() result must carry phase6_clv_state when insights present."""
        from orchestrator import strategy_tick

        fake_insight = {
            "id": "ins-001",
            "status": "VALIDATED",
            "category": "feature_engineering",
        }

        with (
            patch.object(strategy_tick, "_load_new_insights", return_value=[fake_insight]),
            patch.object(strategy_tick, "load_strategy_state",
                         return_value=strategy_tick._default_state()),
            patch.object(strategy_tick, "_save_strategy_state"),
            patch.object(strategy_tick, "_load_sim_weakness_penalty", return_value=0.0),
            patch.object(strategy_tick, "_load_phase6_clv_state", return_value={
                "clv_state": "WAITING_FOR_MARKET_SETTLEMENT",
                "computed": 0,
                "pending": 14,
                "blocked": 0,
                "eligible_for_reinforcement": False,
            }),
            patch("orchestrator.execution_policy.evaluate_execution",
                  return_value={"allowed": True}),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = strategy_tick.run_strategy_tick()

        assert result["status"] == "SUCCESS"
        p6 = result.get("phase6_clv_state", {})
        assert p6.get("clv_state") == "WAITING_FOR_MARKET_SETTLEMENT"
        assert p6.get("eligible_for_reinforcement") is False

    def test_pending_clv_does_not_block_insight_based_adjustments(self):
        """PENDING_CLOSING CLV blocks CLV reinforcement but NOT insight-based adjustments."""
        from orchestrator import strategy_tick

        fake_insight = {"id": "ins-x", "status": "VALIDATED", "category": "feature_engineering"}
        base_state = strategy_tick._default_state()
        base_confidence = base_state["confidence_weight"]

        with (
            patch.object(strategy_tick, "_load_new_insights", return_value=[fake_insight]),
            patch.object(strategy_tick, "load_strategy_state", return_value=base_state),
            patch.object(strategy_tick, "_save_strategy_state"),
            patch.object(strategy_tick, "_load_sim_weakness_penalty", return_value=0.0),
            patch.object(strategy_tick, "_load_phase6_clv_state", return_value={
                "clv_state": "WAITING_FOR_MARKET_SETTLEMENT",
                "computed": 0, "pending": 14, "blocked": 0,
                "eligible_for_reinforcement": False,
            }),
            patch("orchestrator.execution_policy.evaluate_execution",
                  return_value={"allowed": True}),
            patch.dict("os.environ", {}, clear=True),
        ):
            result = strategy_tick.run_strategy_tick()

        # VALIDATED insight → confidence delta = +0.05 → confidence should increase
        assert result["status"] == "SUCCESS"
        assert result["confidence_weight"] > base_confidence, (
            "Insight-based confidence adjustment must NOT be blocked by PENDING_CLOSING CLV"
        )


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 3: training_memory records CLV state without success increment
# ═══════════════════════════════════════════════════════════════════════════

class TestScenario3TrainingMemoryNoPendingSuccess:
    """record_phase6_clv_state does NOT increment consecutive_successes."""

    def test_record_phase6_clv_state_pending_no_success_increment(self):
        from orchestrator import training_memory

        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with (
                patch.object(training_memory, "MEMORY_PATH", mem_path),
            ):
                # Record an all-pending state
                mem = training_memory.record_phase6_clv_state(
                    date="2026-04-30",
                    registry_rows=14,
                    clv_pending=14,
                    clv_computed=0,
                    clv_blocked=0,
                )

        # consecutive_successes must NOT increase
        assert mem["consecutive_successes"] == 0, (
            "PENDING_CLOSING state must NOT increment consecutive_successes"
        )
        assert mem["consecutive_failures"] == 0, (
            "PENDING_CLOSING state must NOT increment consecutive_failures"
        )

    def test_record_phase6_clv_state_stored_with_correct_fields(self):
        from orchestrator import training_memory

        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with patch.object(training_memory, "MEMORY_PATH", mem_path):
                mem = training_memory.record_phase6_clv_state(
                    date="2026-04-30",
                    registry_rows=14,
                    clv_pending=14,
                    clv_computed=0,
                    clv_blocked=0,
                )

        states = mem.get("phase6_states", [])
        assert len(states) == 1
        entry = states[0]
        assert entry["date"] == "2026-04-30"
        assert entry["registry_rows"] == 14
        assert entry["clv_pending"] == 14
        assert entry["clv_computed"] == 0
        assert entry["clv_state"] == "PENDING_CLOSING"
        assert entry["settlement_complete"] is False
        assert entry["reinforcement_eligible"] is False

    def test_record_phase6_clv_state_computed_is_reinforcement_eligible(self):
        from orchestrator import training_memory

        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with patch.object(training_memory, "MEMORY_PATH", mem_path):
                mem = training_memory.record_phase6_clv_state(
                    date="2026-05-01",
                    registry_rows=14,
                    clv_pending=0,
                    clv_computed=14,
                    clv_blocked=0,
                )

        states = mem.get("phase6_states", [])
        entry = next(e for e in states if e["date"] == "2026-05-01")
        assert entry["clv_state"] == "COMPUTED"
        assert entry["reinforcement_eligible"] is True
        # Still no automatic success increment — needs separate patch record
        assert mem["consecutive_successes"] == 0

    def test_record_phase6_clv_deduplicates_by_date(self):
        from orchestrator import training_memory

        with tempfile.TemporaryDirectory() as tmpdir:
            mem_path = Path(tmpdir) / "training_memory.json"
            with patch.object(training_memory, "MEMORY_PATH", mem_path):
                training_memory.record_phase6_clv_state(
                    "2026-04-30", 14, 14, 0, 0
                )
                mem = training_memory.record_phase6_clv_state(
                    "2026-04-30", 14, 0, 14, 0   # same date, now computed
                )

        # Should have only one entry for this date (latest wins)
        states = [e for e in mem.get("phase6_states", []) if e["date"] == "2026-04-30"]
        assert len(states) == 1
        assert states[0]["clv_computed"] == 14   # latest values kept


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 4: decision card shows Phase 6 pending/computed counts
# ═══════════════════════════════════════════════════════════════════════════

class TestScenario4DecisionCardPhase6:
    """ops_decision_card.compute_phase6_status() returns correct counts."""

    def test_compute_phase6_status_all_pending(self):
        import sys
        # Ensure scripts/ path is accessible
        import importlib.util, os
        card_path = Path(__file__).resolve().parents[1] / "scripts" / "ops_decision_card.py"
        spec = importlib.util.spec_from_file_location("ops_decision_card", card_path)
        card_mod = importlib.util.module_from_spec(spec)

        with patch(
            "orchestrator.phase6_data_registry.get_phase6_status",
            return_value={
                "dates": ["2026-04-30"],
                "registry_rows": 14,
                "clv_computed": 0,
                "clv_pending_closing": 14,
                "clv_blocked": 0,
                "eligible_for_simulation": 8,
                "all_clv_pending": True,
                "next_required_event": "Wait for post-prediction closing odds",
            },
        ):
            spec.loader.exec_module(card_mod)
            result = card_mod.compute_phase6_status()

        assert result["available"] is True
        assert result["registry_rows"] == 14
        assert result["clv_computed"] == 0
        assert result["clv_pending_closing"] == 14
        assert result["all_clv_pending"] is True
        assert "next_required_event" in result

    def test_build_payload_includes_phase6(self):
        """build_payload() must include 'phase6' key."""
        card_path = Path(__file__).resolve().parents[1] / "scripts" / "ops_decision_card.py"
        import importlib.util
        spec = importlib.util.spec_from_file_location("ops_decision_card", card_path)
        card_mod = importlib.util.module_from_spec(spec)

        # Patch all compute functions to return minimal valid structures
        _empty_clv = {"coverage_pct": 0, "external_closing_rows": 0,
                      "total_live_rows": 0, "clv_samples": 0, "clv_std": 0.0}
        _empty_sched = {"fetched_today": False, "api_calls_today": 0, "api_cap": 2,
                        "state_date": "-", "last_run_ts": "unknown",
                        "next_trigger_minutes": None, "heartbeat_present": False}

        with (
            patch("orchestrator.phase6_data_registry.get_phase6_status",
                  return_value={"dates": [], "registry_rows": 0, "clv_computed": 0,
                                "clv_pending_closing": 0, "clv_blocked": 0,
                                "eligible_for_simulation": 0, "all_clv_pending": False,
                                "next_required_event": "No Phase 6 data"}),
        ):
            spec.loader.exec_module(card_mod)

            with (
                patch.object(card_mod, "compute_clv_metrics", return_value=_empty_clv),
                patch.object(card_mod, "compute_scheduler_status", return_value=_empty_sched),
                patch.object(card_mod, "collect_flags", return_value=[]),
                patch.object(card_mod, "compute_system_health", return_value={}),
                patch.object(card_mod, "compute_today_wbc", return_value={"games": [], "date": "-"}),
                patch.object(card_mod, "compute_recent_performance", return_value={"available": False}),
                patch.object(card_mod, "compute_last_postmortem", return_value={"available": False, "count": 0}),
            ):
                payload = card_mod.build_payload()

        assert "phase6" in payload, "build_payload() must include 'phase6' key"

    def test_render_card_includes_phase6_section(self):
        """render_card() must include PHASE 6 PIPELINE STATUS in output."""
        card_path = Path(__file__).resolve().parents[1] / "scripts" / "ops_decision_card.py"
        import importlib.util
        spec = importlib.util.spec_from_file_location("ops_decision_card", card_path)
        card_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(card_mod)

        payload = {
            "status": "RED",
            "reasons": ["test"],
            "clv": {"coverage_pct": 0, "external_closing_rows": 0,
                    "total_live_rows": 0, "clv_samples": 0, "clv_std": 0.0},
            "scheduler": {"fetched_today": False, "api_calls_today": 0, "api_cap": 2,
                          "state_date": "-", "last_run_ts": "unknown",
                          "next_trigger_minutes": None, "heartbeat_present": False},
            "flags": [],
            "action": "HOLD",
            "system_health": {},
            "today_wbc": {"games": [], "date": "-", "note": "no games"},
            "recent_performance": {"available": False},
            "last_postmortem": {"available": False, "count": 0},
            "phase6": {
                "available": True,
                "dates": ["2026-04-30"],
                "registry_rows": 14,
                "clv_computed": 0,
                "clv_pending_closing": 14,
                "clv_blocked": 0,
                "eligible_for_simulation": 8,
                "all_clv_pending": True,
                "next_required_event": "Wait for post-prediction closing odds",
            },
        }
        rendered = card_mod.render_card(payload)
        assert "PHASE 6 PIPELINE STATUS" in rendered
        assert "WAITING_FOR_MARKET_SETTLEMENT" in rendered
        assert "registry_rows" in rendered.lower() or "Registry rows" in rendered


# ═══════════════════════════════════════════════════════════════════════════
# SCENARIO 5: closing monitor upgrades PENDING → COMPUTED with valid odds only
# ═══════════════════════════════════════════════════════════════════════════

class TestScenario5ClosingOddsMonitor:
    """closing_odds_monitor upgrades PENDING → COMPUTED only with valid closing odds."""

    def _setup_dirs(self, tmpdir: str):
        """Returns (reports_dir, timeline_path)."""
        reports_dir = Path(tmpdir) / "reports"
        reports_dir.mkdir(parents=True)
        timeline_path = Path(tmpdir) / "odds_timeline.jsonl"
        return reports_dir, timeline_path

    def test_no_upgrade_when_closing_ts_before_prediction(self):
        """Stale closing_ts (before prediction_time_utc) must NOT trigger upgrade."""
        from orchestrator import closing_odds_monitor

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir, tl_path = self._setup_dirs(tmpdir)

            # CLV file: PENDING row
            clv_path = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
            _write_jsonl(clv_path, [_make_clv_row("pred-001", "game-001", "home")])

            # Timeline: closing_ts is BEFORE prediction_time_utc (stale snapshot)
            _write_jsonl(tl_path, [_make_timeline_row(
                game_id="game-001",
                closing_home_ml=-120,
                closing_ts=_BEFORE_PRED,   # stale
            )])

            output_path = reports_dir / "clv_validation_records_6u_upgraded_2026-04-30.jsonl"
            stats = closing_odds_monitor.upgrade_pending_records(clv_path, tl_path, output_path)

        assert stats["upgraded"] == 0, "Stale closing_ts must NOT produce an upgrade"
        assert stats["still_pending"] == 1
        assert not output_path.exists() or output_path.stat().st_size == 0 or (
            sum(1 for _ in output_path.read_text().splitlines() if _.strip()) == 0
        )

    def test_upgrade_when_closing_ts_after_prediction(self):
        """Valid closing_ts (after prediction_time_utc) MUST produce a COMPUTED upgrade."""
        from orchestrator import closing_odds_monitor

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir, tl_path = self._setup_dirs(tmpdir)

            clv_path = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
            _write_jsonl(clv_path, [_make_clv_row("pred-001", "game-001", "home",
                                                   implied_prob=0.535)])

            # Timeline: valid closing_ts AFTER prediction
            _write_jsonl(tl_path, [_make_timeline_row(
                game_id="game-001",
                closing_home_ml=-120,      # -120 → 0.545455
                closing_ts=_AFTER_PRED,
            )])

            output_path = reports_dir / "upgraded.jsonl"
            stats = closing_odds_monitor.upgrade_pending_records(clv_path, tl_path, output_path)

            assert stats["upgraded"] == 1
            assert stats["still_pending"] == 0

            # Verify the written record
            upgraded_rows = list(closing_odds_monitor._iter_jsonl(output_path))
            assert len(upgraded_rows) == 1
            rec = upgraded_rows[0]
            assert rec["clv_status"] == "COMPUTED"
            assert rec["original_clv_status"] == "PENDING_CLOSING"
            # CLV = closing_implied - implied_at_pred ≈ 0.545455 - 0.535 = 0.010455
            assert rec["clv_value"] is not None
            assert abs(rec["clv_value"] - (round(120/220, 6) - 0.535)) < 1e-5

    def test_external_closing_takes_priority_over_tsl(self):
        """external_closing_home_ml takes priority over closing_home_ml."""
        from orchestrator import closing_odds_monitor

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir, tl_path = self._setup_dirs(tmpdir)

            clv_path = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
            _write_jsonl(clv_path, [_make_clv_row("pred-001", "game-001", "home")])

            # Both TSL and external closing available, external is priority
            _write_jsonl(tl_path, [_make_timeline_row(
                game_id="game-001",
                closing_home_ml=-115,
                closing_ts=_AFTER_PRED,
                ext_closing_home_ml=-110,   # external: higher odds for home
                ext_closing_ts=_AFTER_PRED,
            )])

            output_path = reports_dir / "upgraded.jsonl"
            closing_odds_monitor.upgrade_pending_records(clv_path, tl_path, output_path)

            rows = list(closing_odds_monitor._iter_jsonl(output_path))
            assert len(rows) == 1
            assert rows[0]["closing_odds"] == -110.0, "External closing must take priority"
            assert rows[0]["closing_odds_source"] == "external_closing"

    def test_no_upgrade_when_game_not_in_timeline(self):
        """No timeline entry → record remains PENDING, no upgrade."""
        from orchestrator import closing_odds_monitor

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir, tl_path = self._setup_dirs(tmpdir)

            clv_path = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
            _write_jsonl(clv_path, [_make_clv_row("pred-001", "game-missing", "home")])

            # Timeline has a DIFFERENT game
            _write_jsonl(tl_path, [_make_timeline_row(
                game_id="game-OTHER",
                closing_home_ml=-120,
                closing_ts=_AFTER_PRED,
            )])

            output_path = reports_dir / "upgraded.jsonl"
            stats = closing_odds_monitor.upgrade_pending_records(clv_path, tl_path, output_path)

        assert stats["upgraded"] == 0
        assert stats["still_pending"] == 1

    def test_upgraded_record_id_is_different_from_original(self):
        """Upgraded record must have a NEW clv_record_id (not same as original)."""
        from orchestrator import closing_odds_monitor

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir, tl_path = self._setup_dirs(tmpdir)

            clv_path = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
            original_row = _make_clv_row("pred-001", "game-001", "home")
            _write_jsonl(clv_path, [original_row])

            _write_jsonl(tl_path, [_make_timeline_row(
                game_id="game-001",
                closing_home_ml=-120,
                closing_ts=_AFTER_PRED,
            )])

            output_path = reports_dir / "upgraded.jsonl"
            closing_odds_monitor.upgrade_pending_records(clv_path, tl_path, output_path)

            rows = list(closing_odds_monitor._iter_jsonl(output_path))
            assert rows[0]["clv_record_id"] != original_row["clv_record_id"]
            assert rows[0]["original_clv_record_id"] == original_row["clv_record_id"]

    def test_check_pending_for_upgrade_dry_run(self):
        """check_pending_for_upgrade returns preview without writing files."""
        from orchestrator import closing_odds_monitor

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir, tl_path = self._setup_dirs(tmpdir)

            clv_path = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
            _write_jsonl(clv_path, [
                _make_clv_row("pred-001", "game-001", "home"),  # has valid odds
                _make_clv_row("pred-002", "game-002", "away"),  # no odds
            ])
            _write_jsonl(tl_path, [
                _make_timeline_row("game-001", closing_home_ml=-120, closing_ts=_AFTER_PRED),
                _make_timeline_row("game-002"),   # no closing odds
            ])

            preview = closing_odds_monitor.check_pending_for_upgrade(clv_path, tl_path)

        assert preview["total_records"] == 2
        assert preview["pending"] == 2
        assert preview["upgradeable_count"] == 1
        assert preview["not_yet"] == 1
        assert preview["upgradeable"][0]["prediction_id"] == "pred-001"

    def test_run_closing_odds_monitor_full_pipeline(self):
        """run_closing_odds_monitor() scans all CLV files."""
        from orchestrator import closing_odds_monitor

        with tempfile.TemporaryDirectory() as tmpdir:
            reports_dir = Path(tmpdir) / "reports"
            reports_dir.mkdir()
            tl_path = Path(tmpdir) / "odds_timeline.jsonl"

            clv_path = reports_dir / "clv_validation_records_6u_2026-04-30.jsonl"
            _write_jsonl(clv_path, [_make_clv_row("pred-001", "game-001", "home")])
            _write_jsonl(tl_path, [_make_timeline_row(
                "game-001", closing_home_ml=-120, closing_ts=_AFTER_PRED
            )])

            result = closing_odds_monitor.run_closing_odds_monitor(
                reports_dir=reports_dir,
                timeline_path=tl_path,
            )

        assert "2026-04-30" in result["dates_scanned"]
        assert result["total_stats"]["upgraded"] == 1
        assert result["total_stats"]["still_pending"] == 0


# ─────────────────────────────────────────────
# Data registry contract tests (supplemental)
# ─────────────────────────────────────────────

class TestPhase6DataRegistryContracts:
    """Verify data registry read-only contracts."""

    def test_discover_phase6_dates_empty_dir(self):
        from orchestrator import phase6_data_registry
        with tempfile.TemporaryDirectory() as tmpdir:
            dates = phase6_data_registry.discover_phase6_dates(Path(tmpdir))
        assert dates == []

    def test_discover_phase6_dates_finds_correct_files(self):
        from orchestrator import phase6_data_registry
        with tempfile.TemporaryDirectory() as tmpdir:
            rdir = Path(tmpdir)
            (rdir / "prediction_registry_6t_2026-04-30.jsonl").write_text("")
            (rdir / "prediction_registry_6t_2026-05-01.jsonl").write_text("")
            (rdir / "unrelated.jsonl").write_text("")
            dates = phase6_data_registry.discover_phase6_dates(rdir)
        assert dates == ["2026-04-30", "2026-05-01"]

    def test_load_registry_6t_rows_filters_governance(self):
        from orchestrator import phase6_data_registry
        with tempfile.TemporaryDirectory() as tmpdir:
            rdir = Path(tmpdir)
            valid_row = _make_registry_row(governance_status="VALIDATED_ML_ONLY")
            invalid_row = _make_registry_row("pred-bad", governance_status="UNVALIDATED")
            _write_jsonl(rdir / "prediction_registry_6t_2026-04-30.jsonl",
                         [valid_row, invalid_row])
            rows = phase6_data_registry.load_registry_6t_rows("2026-04-30", rdir)
        assert len(rows) == 1
        assert rows[0]["prediction_id"] == "pred-001"

    def test_get_phase6_status_all_pending(self):
        from orchestrator import phase6_data_registry
        with tempfile.TemporaryDirectory() as tmpdir:
            rdir = Path(tmpdir)
            _write_jsonl(rdir / "prediction_registry_6t_2026-04-30.jsonl",
                         [_make_registry_row(ev_percent=5.0)])
            _write_jsonl(rdir / "clv_validation_records_6u_2026-04-30.jsonl",
                         [_make_clv_row(clv_status="PENDING_CLOSING")])
            status = phase6_data_registry.get_phase6_status(rdir)

        assert status["registry_rows"] == 1
        assert status["clv_pending_closing"] == 1
        assert status["clv_computed"] == 0
        assert status["all_clv_pending"] is True
        assert "Wait" in status["next_required_event"]
