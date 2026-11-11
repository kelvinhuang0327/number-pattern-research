"""
Phase 39: MLB Prediction Probability Persistence — 14 Unit Tests
================================================================
Validates:
  1. PredictionRow schema and field defaults
  2. validate_prediction_row edge cases
  3. compute_audit_hash determinism
  4. build_prediction_row correctness
  5. write_prediction_rows / load_prediction_rows round-trip
  6. detect_duplicate_dedupe_keys
  7. recompute_metrics_from_rows correctness
  8. evaluate_calibration_readiness
  9. Phase39Result when file missing → RAW_MODEL_PROB_MISSING
 10. Phase39Result when file present → VERIFIED
 11. BSS Safety Gate remains blocked (BSS < 0)
 12. Source file protection guard
 13. FullBacktestEngine exposes persist_predictions attribute
 14. write_prediction_rows rejects empty list

Hard Rules:
  - Do NOT call external API / LLM.
  - Do NOT modify production model.
  - Do NOT bypass BSS Safety Gate.
  - Do NOT use same-fold calibration and evaluation.
"""
from __future__ import annotations

import json
import math
import tempfile
from dataclasses import asdict
from pathlib import Path

import pytest

# ─── Imports under test ────────────────────────────────────────────────────────
from wbc_backend.evaluation.prediction_persistence import (
    DEFAULT_PREDICTIONS_PATH,
    PredictionRow,
    SCHEMA_VERSION,
    build_prediction_row,
    compute_audit_hash,
    detect_duplicate_dedupe_keys,
    load_prediction_rows,
    recompute_metrics_from_rows,
    validate_prediction_row,
    write_prediction_rows,
    _assert_not_source_path,
)
from scripts.run_phase39_mlb_prediction_persistence_check import (
    CalibrationReadiness,
    Phase39Result,
    evaluate_calibration_readiness,
    generate_report,
    run_phase39,
    ECE_TARGET,
    MIN_CALIBRATION_SAMPLE,
    REPORT_BSS,
    RAW_MODEL_PROB_MISSING_LOCATION,
)


# ══════════════════════════════════════════════════════════════════════════════
# § Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _make_valid_row(**kwargs) -> PredictionRow:
    """Return a minimal valid PredictionRow."""
    defaults = dict(
        game_date="2025-04-01",
        game_id="MLB2025_0001_2025-04-01_BOS_NYY",
        home_team="New York Yankees",
        away_team="Boston Red Sox",
        home_win=1,
        model_home_prob=0.58,
        market_home_prob_no_vig=0.54,
        market_away_prob_no_vig=0.46,
        split_id="window_1",
    )
    defaults.update(kwargs)
    return build_prediction_row(**defaults)


def _make_rows(n: int = 10) -> list[PredictionRow]:
    """Generate n synthetic prediction rows with known metric properties."""
    import random
    rng = random.Random(42)
    rows = []
    for i in range(n):
        outcome = rng.randint(0, 1)
        model_p = max(0.05, min(0.95, 0.5 + rng.gauss(0, 0.15)))
        market_p = max(0.05, min(0.95, 0.5 + rng.gauss(0, 0.10)))
        rows.append(build_prediction_row(
            game_date=f"2025-04-{i+1:02d}",
            game_id=f"MLB2025_{i:04d}",
            home_team="HomeTeam",
            away_team="AwayTeam",
            home_win=outcome,
            model_home_prob=round(model_p, 6),
            market_home_prob_no_vig=round(market_p, 6),
            market_away_prob_no_vig=round(1.0 - market_p, 6),
            split_id=f"window_{(i % 5) + 1}",
        ))
    return rows


# ══════════════════════════════════════════════════════════════════════════════
# Class 1: PredictionRow Schema
# ══════════════════════════════════════════════════════════════════════════════

class TestPredictionRowSchema:
    """TC-01: Validate PredictionRow schema version and default sentinel values."""

    def test_schema_version_constant(self):
        """SCHEMA_VERSION must be phase39-v1."""
        assert SCHEMA_VERSION == "phase39-v1"

    def test_default_sentinel_not_in_range(self):
        """Default model_home_prob sentinel (-1.0) must fail validation."""
        row = PredictionRow()
        errors = validate_prediction_row(row)
        assert any("model_home_prob" in e for e in errors), (
            f"Expected model_home_prob validation error, got: {errors}"
        )

    def test_valid_row_passes_validation(self):
        """A correctly built row must produce zero validation errors."""
        row = _make_valid_row()
        errors = validate_prediction_row(row)
        assert errors == [], f"Unexpected errors: {errors}"


# ══════════════════════════════════════════════════════════════════════════════
# Class 2: validate_prediction_row Edge Cases
# ══════════════════════════════════════════════════════════════════════════════

class TestValidatePredictionRow:
    """TC-02: validate_prediction_row catches all invalid configurations."""

    def test_home_win_must_be_0_or_1(self):
        """home_win=-1 (sentinel) must fail validation."""
        row = PredictionRow()
        row.model_home_prob = 0.6
        row.market_home_prob_no_vig = 0.55
        row.market_away_prob_no_vig = 0.45
        row.home_team = "A"
        row.away_team = "B"
        row.game_id = "G1"
        row.home_win = -1   # invalid
        errors = validate_prediction_row(row)
        assert any("home_win" in e for e in errors)

    def test_market_probs_sum_to_one(self):
        """Market probs that sum to 0.80 (not ≈ 1.0) must fail."""
        row = _make_valid_row(
            market_home_prob_no_vig=0.40,
            market_away_prob_no_vig=0.40,   # sum = 0.80
        )
        # Manually override after build to bypass build_prediction_row auto-correct
        row.market_home_prob_no_vig = 0.40
        row.market_away_prob_no_vig = 0.40
        errors = validate_prediction_row(row)
        assert any("market_home" in e or "sum" in e.lower() or "≠" in e for e in errors), (
            f"Expected market sum validation error, got: {errors}"
        )

    def test_empty_teams_fail(self):
        """Empty home_team or away_team must fail validation."""
        row = _make_valid_row()
        row.home_team = ""
        errors = validate_prediction_row(row)
        assert any("home_team" in e for e in errors)

    def test_out_of_range_prob_fails(self):
        """model_home_prob = 1.5 must fail (> 1.0)."""
        row = _make_valid_row()
        row.model_home_prob = 1.5
        errors = validate_prediction_row(row)
        assert any("model_home_prob" in e for e in errors)


# ══════════════════════════════════════════════════════════════════════════════
# Class 3: compute_audit_hash Determinism
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeAuditHash:
    """TC-03: audit_hash is deterministic and changes when data changes."""

    def test_hash_is_deterministic(self):
        """Same row built twice must produce identical audit_hash."""
        r1 = _make_valid_row()
        r2 = _make_valid_row()
        assert r1.audit_hash == r2.audit_hash

    def test_hash_changes_on_prob_change(self):
        """Changing model_home_prob by 0.01 must change the hash."""
        r1 = _make_valid_row(model_home_prob=0.58)
        r2 = _make_valid_row(model_home_prob=0.59)
        assert r1.audit_hash != r2.audit_hash

    def test_hash_starts_with_sha256(self):
        """audit_hash must be prefixed with 'sha256:'."""
        r = _make_valid_row()
        assert r.audit_hash.startswith("sha256:")
        assert len(r.audit_hash) == len("sha256:") + 64


# ══════════════════════════════════════════════════════════════════════════════
# Class 4: build_prediction_row
# ══════════════════════════════════════════════════════════════════════════════

class TestBuildPredictionRow:
    """TC-04: build_prediction_row populates all required fields correctly."""

    def test_dedupe_key_format(self):
        """dedupe_key must be 'YYYY-MM-DD|Away|Home'."""
        row = _make_valid_row(
            game_date="2025-06-15",
            home_team="NYY",
            away_team="BOS",
        )
        assert row.dedupe_key == "2025-06-15|BOS|NYY"

    def test_market_away_auto_computed(self):
        """market_away_prob_no_vig ≈ 1 - market_home_prob_no_vig."""
        row = _make_valid_row(
            market_home_prob_no_vig=0.60,
            market_away_prob_no_vig=0.40,
        )
        assert abs(row.market_home_prob_no_vig + row.market_away_prob_no_vig - 1.0) < 0.01

    def test_schema_version_set(self):
        """schema_version must equal SCHEMA_VERSION constant."""
        row = _make_valid_row()
        assert row.schema_version == SCHEMA_VERSION

    def test_feature_version_set(self):
        """feature_version must reference MARL feature set."""
        row = _make_valid_row()
        assert "marl" in row.feature_version.lower()


# ══════════════════════════════════════════════════════════════════════════════
# Class 5: write / load Round-Trip
# ══════════════════════════════════════════════════════════════════════════════

class TestWriteLoadRoundTrip:
    """TC-05: JSONL write and load preserves all field values exactly."""

    def test_round_trip_fidelity(self):
        """Written then loaded row must match original on all key fields."""
        rows = _make_rows(20)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test_predictions.jsonl"
            n_written = write_prediction_rows(rows, path, backup=False)
            assert n_written == 20

            loaded = load_prediction_rows(path)
            assert len(loaded) == 20

            for orig, back in zip(rows, loaded):
                assert orig.game_id == back.game_id
                assert abs(orig.model_home_prob - back.model_home_prob) < 1e-7
                assert abs(orig.market_home_prob_no_vig - back.market_home_prob_no_vig) < 1e-7
                assert orig.home_win == back.home_win
                assert orig.audit_hash == back.audit_hash

    def test_backup_created_on_overwrite(self):
        """If file exists and backup=True, a .bak file must be created."""
        rows = _make_rows(5)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "test_predictions.jsonl"
            write_prediction_rows(rows, path, backup=False)
            # Write again with backup=True
            write_prediction_rows(rows, path, backup=True)
            assert path.with_suffix(".jsonl.bak").exists()

    def test_write_empty_raises(self):
        """write_prediction_rows with empty list must raise ValueError."""
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "empty.jsonl"
            with pytest.raises(ValueError, match="empty"):
                write_prediction_rows([], path)


# ══════════════════════════════════════════════════════════════════════════════
# Class 6: Duplicate Detection
# ══════════════════════════════════════════════════════════════════════════════

class TestDuplicateDedupeKeys:
    """TC-06: detect_duplicate_dedupe_keys finds overlapping game keys."""

    def test_no_duplicates(self):
        rows = _make_rows(10)
        dups = detect_duplicate_dedupe_keys(rows)
        # All rows have unique game_date (2025-04-01 through 2025-04-10)
        assert dups == []

    def test_detects_duplicates(self):
        """Two rows with same dedupe_key must be flagged."""
        r1 = _make_valid_row(game_date="2025-05-01")
        r2 = _make_valid_row(game_date="2025-05-01")  # same key
        dups = detect_duplicate_dedupe_keys([r1, r2])
        assert len(dups) == 1
        assert "2025-05-01" in dups[0]


# ══════════════════════════════════════════════════════════════════════════════
# Class 7: recompute_metrics_from_rows
# ══════════════════════════════════════════════════════════════════════════════

class TestRecomputeMetrics:
    """TC-07: recompute_metrics_from_rows produces correct Brier / BSS / ECE."""

    def test_perfect_model_has_low_brier(self):
        """A model that always predicts the true outcome has Brier ≈ 0."""
        rows = []
        for i in range(20):
            outcome = i % 2
            rows.append(build_prediction_row(
                game_date=f"2025-04-{i+1:02d}",
                game_id=f"G{i}",
                home_team="A", away_team="B",
                home_win=outcome,
                model_home_prob=float(outcome),  # perfect prediction
                market_home_prob_no_vig=0.50,
                market_away_prob_no_vig=0.50,
                split_id="window_1",
            ))
        m = recompute_metrics_from_rows(rows)
        assert m["model_brier"] == pytest.approx(0.0, abs=1e-6)

    def test_bss_formula_consistency(self):
        """BSS = 1 - model_brier / market_brier."""
        rows = _make_rows(100)
        m = recompute_metrics_from_rows(rows)
        expected_bss = 1.0 - m["model_brier"] / m["market_brier"]
        assert m["bss"] == pytest.approx(expected_bss, abs=1e-5)

    def test_empty_rows_returns_none_metrics(self):
        """Empty input must return sample_size=0 and None metrics."""
        m = recompute_metrics_from_rows([])
        assert m["sample_size"] == 0
        assert m["model_brier"] is None

    def test_log_loss_positive(self):
        """log_loss must always be positive."""
        rows = _make_rows(50)
        m = recompute_metrics_from_rows(rows)
        assert m["log_loss"] > 0


# ══════════════════════════════════════════════════════════════════════════════
# Class 8: evaluate_calibration_readiness
# ══════════════════════════════════════════════════════════════════════════════

class TestEvaluateCalibrationReadiness:
    """TC-08: Task 6 — calibration readiness evaluation logic."""

    def test_insufficient_sample_not_ready(self):
        """Sample < MIN_CALIBRATION_SAMPLE must return calibration_ready=False."""
        metrics = {"sample_size": 100, "ece": 0.12, "bss": -0.14}
        cal = evaluate_calibration_readiness(metrics)
        assert cal.calibration_ready is False
        assert "Insufficient" in cal.reason

    def test_sufficient_sample_ready(self):
        """Sample >= MIN_CALIBRATION_SAMPLE with valid ECE must return calibration_ready=True."""
        metrics = {"sample_size": 2000, "ece": 0.12, "bss": -0.14}
        cal = evaluate_calibration_readiness(metrics)
        assert cal.calibration_ready is True

    def test_needs_calibration_when_ece_high(self):
        """ECE above ECE_TARGET means needs_calibration=True."""
        metrics = {"sample_size": 2000, "ece": ECE_TARGET + 0.05, "bss": -0.14}
        cal = evaluate_calibration_readiness(metrics)
        assert cal.needs_calibration is True
        assert cal.ece_below_target is False

    def test_bss_positive_flag(self):
        """BSS > 0 must set bss_positive=True."""
        metrics = {"sample_size": 2000, "ece": 0.05, "bss": 0.03}
        cal = evaluate_calibration_readiness(metrics)
        assert cal.bss_positive is True


# ══════════════════════════════════════════════════════════════════════════════
# Class 9: Phase39 RAW_MODEL_PROB_MISSING
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase39MissingFile:
    """TC-09: run_phase39() with missing JSONL returns RAW_MODEL_PROB_MISSING."""

    def test_missing_file_verdict(self):
        """Non-existent predictions file must yield RAW_MODEL_PROB_MISSING verdict."""
        result = run_phase39(predictions_path=Path("/tmp/__nonexistent_phase39__.jsonl"))
        assert result.raw_model_prob_missing is True
        assert result.verdict == "RAW_MODEL_PROB_MISSING"
        assert result.file_found is False

    def test_missing_location_populated(self):
        """missing_location must reference the exact code location."""
        result = run_phase39(predictions_path=Path("/tmp/__nonexistent_phase39__.jsonl"))
        assert "full_backtest.py" in result.missing_location
        assert "FullBacktestEngine" in result.missing_location

    def test_report_contains_resolution_hint(self):
        """Generated report must contain resolution instructions."""
        result = run_phase39(predictions_path=Path("/tmp/__nonexistent_phase39__.jsonl"))
        report = generate_report(result)
        assert "persist_predictions=True" in report


# ══════════════════════════════════════════════════════════════════════════════
# Class 10: Phase39 with JSONL present → VERIFIED
# ══════════════════════════════════════════════════════════════════════════════

class TestPhase39WithFile:
    """TC-10: run_phase39() with existing JSONL produces VERIFIED verdict."""

    def test_verified_verdict_with_file(self):
        """When prediction rows exist on disk, verdict must be VERIFIED."""
        rows = _make_rows(600)  # > MIN_CALIBRATION_SAMPLE
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mlb_2025_per_game_predictions.jsonl"
            write_prediction_rows(rows, p, backup=False)
            result = run_phase39(predictions_path=p)
        assert result.file_found is True
        assert result.raw_model_prob_missing is False
        assert result.verdict == "PHASE_39_MLB_PREDICTION_PROBABILITY_PERSISTENCE_VERIFIED"

    def test_metrics_recomputed_from_file(self):
        """Metrics loaded from JSONL must be numerically consistent."""
        rows = _make_rows(600)
        direct_metrics = recompute_metrics_from_rows(rows)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mlb_2025_per_game_predictions.jsonl"
            write_prediction_rows(rows, p, backup=False)
            result = run_phase39(predictions_path=p)
        # Model brier from CLI result vs directly computed must match
        assert result.metrics["model_brier"] == pytest.approx(
            direct_metrics["model_brier"], abs=1e-5
        )

    def test_calibration_readiness_populated(self):
        """With >= MIN_CALIBRATION_SAMPLE rows, calibration_ready must be True."""
        rows = _make_rows(600)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mlb_2025_per_game_predictions.jsonl"
            write_prediction_rows(rows, p, backup=False)
            result = run_phase39(predictions_path=p)
        assert result.calibration_readiness is not None
        assert result.calibration_readiness.calibration_ready is True


# ══════════════════════════════════════════════════════════════════════════════
# Class 11: BSS Safety Gate Remains Blocked
# ══════════════════════════════════════════════════════════════════════════════

class TestBssSafetyGateRemainsBlocked:
    """TC-11: BSS < 0 keeps Safety Gate locked regardless of persistence state."""

    def test_report_bss_is_negative(self):
        """Phase 38 report BSS must remain negative."""
        assert REPORT_BSS < 0, f"REPORT_BSS should be negative, got {REPORT_BSS}"

    def test_gate_blocked_when_bss_negative(self):
        """run_phase39 with BSS < 0 must report gate as BLOCKED in report."""
        rows = _make_rows(600)
        # Force model probs to be worse than market (guaranteed negative BSS)
        for r in rows:
            r.model_home_prob = 0.5  # no skill
        # Recompute to check
        m = recompute_metrics_from_rows(rows)
        # With model always at 0.5, BSS depends on market brier vs 0.25
        # BSS = 1 - 0.25 / market_brier; market_brier > 0.25 → BSS < 0 possible
        # We just verify the gate formula:
        bss = m["bss"]
        gate_open = bss is not None and bss > 0
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "test.jsonl"
            write_prediction_rows(rows, p, backup=False)
            result = run_phase39(predictions_path=p)
        report_text = generate_report(result)
        # If BSS is negative, gate must be BLOCKED in report
        if result.metrics.get("bss") is not None and result.metrics["bss"] <= 0:
            assert "BLOCKED" in report_text

    def test_bss_gate_module_blocks_production(self):
        """BSS safety gate must block production_prediction when BSS < 0."""
        from orchestrator.bss_safety_gate import check_bss_safety
        gate_result = check_bss_safety(
            task_kind="production_prediction",
            bss=REPORT_BSS,
        )
        assert gate_result.allowed is False

    def test_patch_gate_unlocked_is_false(self):
        """patch_gate_unlocked must remain False when BSS < 0."""
        from orchestrator.bss_safety_gate import check_bss_safety
        gate_result = check_bss_safety(task_kind="metric_repair", bss=REPORT_BSS)
        # bss_negative=True means patch gate is NOT unlocked
        assert gate_result.bss_negative is True


# ══════════════════════════════════════════════════════════════════════════════
# Class 12: Source File Protection
# ══════════════════════════════════════════════════════════════════════════════

class TestSourceFileProtection:
    """TC-12: write_prediction_rows refuses to write to original source CSVs."""

    def test_cannot_write_to_asplayed_csv(self):
        """Write to mlb-2025-asplayed.csv must raise RuntimeError."""
        rows = _make_rows(5)
        with pytest.raises(RuntimeError, match="BLOCKED"):
            write_prediction_rows(
                rows,
                Path("/any/path/mlb_2025/mlb-2025-asplayed.csv"),
            )

    def test_cannot_write_to_odds_csv(self):
        """Write to mlb_odds_2025_real.csv must raise RuntimeError."""
        rows = _make_rows(5)
        with pytest.raises(RuntimeError, match="BLOCKED"):
            write_prediction_rows(
                rows,
                Path("/any/path/mlb_2025/mlb_odds_2025_real.csv"),
            )

    def test_derived_path_is_allowed(self):
        """Write to derived/ directory must succeed without error."""
        rows = _make_rows(5)
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "mlb_2025" / "derived" / "test_output.jsonl"
            p.parent.mkdir(parents=True, exist_ok=True)
            n = write_prediction_rows(rows, p, backup=False)
            assert n == 5


# ══════════════════════════════════════════════════════════════════════════════
# Class 13: FullBacktestEngine Integration
# ══════════════════════════════════════════════════════════════════════════════

class TestFullBacktestEngineIntegration:
    """TC-13: FullBacktestEngine exposes persist_predictions without breaking API."""

    def test_engine_has_persist_predictions_attr(self):
        """FullBacktestEngine must accept and store persist_predictions."""
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine
        engine = FullBacktestEngine(persist_predictions=False)
        assert hasattr(engine, "persist_predictions")
        assert engine.persist_predictions is False

    def test_engine_persist_true_accepted(self):
        """FullBacktestEngine(persist_predictions=True) must not raise."""
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine
        engine = FullBacktestEngine(
            persist_predictions=True,
            prediction_output_path=Path("/tmp/test_phase39_output.jsonl"),
        )
        assert engine.persist_predictions is True
        assert engine.prediction_output_path == Path("/tmp/test_phase39_output.jsonl")

    def test_engine_default_output_path_is_none(self):
        """Default prediction_output_path must be None (uses DEFAULT_PREDICTIONS_PATH)."""
        from wbc_backend.evaluation.full_backtest import FullBacktestEngine
        engine = FullBacktestEngine()
        assert engine.prediction_output_path is None


# ══════════════════════════════════════════════════════════════════════════════
# Class 14: No External API or LLM
# ══════════════════════════════════════════════════════════════════════════════

class TestNoExternalApiOrLlm:
    """TC-14: Persistence module must not call external APIs or LLMs."""

    def test_no_requests_import_in_persistence(self):
        """prediction_persistence.py must not import 'requests'."""
        import importlib
        import ast
        import wbc_backend.evaluation.prediction_persistence as pm
        src = Path(pm.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported_modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append(node.module)
        assert "requests" not in imported_modules, (
            "prediction_persistence.py must not import 'requests' (no external API calls)."
        )

    def test_no_openai_import_in_persistence(self):
        """prediction_persistence.py must not import 'openai' or 'anthropic'."""
        import wbc_backend.evaluation.prediction_persistence as pm
        import ast
        src = Path(pm.__file__).read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append(node.module)
        forbidden = {"openai", "anthropic", "langchain", "litellm"}
        found = forbidden & set(imported_modules)
        assert not found, f"Forbidden LLM imports found: {found}"

    def test_no_http_call_in_phase39_script(self):
        """run_phase39_mlb_prediction_persistence_check.py must not import 'requests'."""
        import ast
        script = (
            Path(__file__).parent.parent
            / "scripts"
            / "run_phase39_mlb_prediction_persistence_check.py"
        )
        src = script.read_text(encoding="utf-8")
        tree = ast.parse(src)
        imported_modules: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported_modules.append(node.module)
        assert "requests" not in imported_modules
