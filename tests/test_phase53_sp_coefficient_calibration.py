"""
tests/test_phase53_sp_coefficient_calibration.py
=================================================
Phase 53 — SP Feature Coefficient Calibration Audit Tests

覆蓋：
  - hard rules invariants
  - coefficient grid 可執行
  - scale=0.00 等於 baseline 或無調整
  - scale=1.00 等於 Phase52 目前 rule
  - safe selection 不允許 heavy_favorite ECE 惡化
  - best coefficient 標記 diagnostic_only=True
  - JSON / Markdown report 可產生
"""
from __future__ import annotations

import json
import math
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from orchestrator.phase53_sp_coefficient_calibration import (
    CANDIDATE_PATCH_CREATED,
    PRODUCTION_MODIFIED,
    DIAGNOSTIC_ONLY,
    FEATURE_COEFFICIENT_PAPER_ONLY,
    FEATURE_COEFFICIENT_NOT_SAFE,
    DEFAULT_SCALE_GRID,
    REQUIRED_SEGMENTS,
    Phase53CalibrationResult,
    GridSearchEntry,
    SegmentDelta,
    _apply_scaled_adjustment,
    _compute_metrics,
    _evaluate_scale,
    _select_safe_coefficient,
    _build_segment_comparison,
    run_calibration,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Helpers / fixtures
# ═══════════════════════════════════════════════════════════════════════════════

def _make_context_row(
    model_home_prob: float = 0.55,
    home_win: float = 1.0,
    market_home_prob_no_vig: float = 0.58,
    game_date: str = "2025-06-15",
    sp_fip_delta: float = 1.5,
    sp_fip_delta_available: bool = True,
    park_factor_available: bool = False,
    park_run_factor: float = 1.0,
    season_game_index_available: bool = False,
    season_game_index: float = 0.5,
) -> dict:
    return {
        "model_home_prob": model_home_prob,
        "home_win": home_win,
        "market_home_prob_no_vig": market_home_prob_no_vig,
        "game_date": game_date,
        "p0_features": {
            "sp_fip_delta": sp_fip_delta,
            "sp_fip_delta_available": sp_fip_delta_available,
            "park_factor_available": park_factor_available,
            "park_run_factor": park_run_factor,
            "season_game_index_available": season_game_index_available,
            "season_game_index": season_game_index,
        },
    }


def _make_synthetic_rows(n: int = 200) -> list[dict]:
    """Generate synthetic rows for unit-level tests (not real data)."""
    rows = []
    for i in range(n):
        prob = 0.40 + (i % 50) * 0.004
        home_win = 1.0 if i % 2 == 0 else 0.0
        mkt = prob + 0.02
        delta = -2.0 + (i % 40) * 0.1  # range -2.0 to +1.9
        month = ["2025-04", "2025-05", "2025-06", "2025-07"][i % 4]
        game_date = f"{month}-{(i % 28) + 1:02d}"
        rows.append(_make_context_row(
            model_home_prob=prob,
            home_win=home_win,
            market_home_prob_no_vig=mkt,
            game_date=game_date,
            sp_fip_delta=delta,
            sp_fip_delta_available=True,
        ))
    return rows


def _write_jsonl(rows: list[dict], path: Path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


# ═══════════════════════════════════════════════════════════════════════════════
# § T-001  Hard rules
# ═══════════════════════════════════════════════════════════════════════════════

class TestHardRules:
    """Phase 53 hard-rule invariants must always hold."""

    def test_candidate_patch_never_created(self):
        assert CANDIDATE_PATCH_CREATED is False

    def test_production_never_modified(self):
        assert PRODUCTION_MODIFIED is False

    def test_diagnostic_only_constant(self):
        assert DIAGNOSTIC_ONLY is True

    def test_gate_values_not_patch(self):
        assert "PATCH" not in FEATURE_COEFFICIENT_PAPER_ONLY
        assert "PATCH" not in FEATURE_COEFFICIENT_NOT_SAFE

    def test_result_hard_rules(self):
        """Phase53CalibrationResult always has hard-rule fields = False/True."""
        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.diagnostic_only is True

    def test_grid_entries_hard_rules(self):
        """Every GridSearchEntry must have diagnostic_only=True, patch=False."""
        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        for entry in result.coefficient_grid_results:
            assert entry.diagnostic_only is True
            assert entry.candidate_patch_created is False
            assert entry.production_modified is False


# ═══════════════════════════════════════════════════════════════════════════════
# § T-002  Scale=0.00 equals baseline (no SP adjustment)
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleZeroIsBaseline:
    """scale=0.00 should produce no SP FIP adjustment (zero fip_adj)."""

    def test_scale_zero_no_fip_adjustment(self):
        """With scale=0, FIP adj is 0 regardless of delta."""
        p0 = {
            "sp_fip_delta": 2.5,
            "sp_fip_delta_available": True,
            "park_factor_available": False,
            "season_game_index_available": False,
        }
        adj_scale0, _ = _apply_scaled_adjustment(0.60, p0, scale=0.0)
        # No park, no season → no adjustment
        assert abs(adj_scale0 - 0.60) < 1e-9

    def test_scale_zero_adjusted_rate_from_sp_is_zero(self):
        """With scale=0, sp_fip adjustment part contributes 0 to prob change."""
        # Only SP FIP should change; park and season disabled
        row = _make_context_row(
            model_home_prob=0.55,
            sp_fip_delta=1.5,
            sp_fip_delta_available=True,
            park_factor_available=False,
            season_game_index_available=False,
        )
        adj, was_adj = _apply_scaled_adjustment(0.55, row["p0_features"], scale=0.0)
        assert not was_adj
        assert abs(adj - 0.55) < 1e-9

    def test_scale_zero_grid_entry_adjusted_rows_zero(self):
        """GridSearchEntry for scale=0 with only SP-triggered rows → 0 adjusted."""
        rows = []
        for _ in range(50):
            rows.append(_make_context_row(
                model_home_prob=0.55,
                home_win=1.0,
                sp_fip_delta=1.5,
                park_factor_available=False,
                season_game_index_available=False,
            ))
        entry = _evaluate_scale(rows, scale=0.0)
        assert entry.coefficient_scale == 0.0
        assert entry.adjusted_rows == 0
        assert entry.adjusted_rate == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-003  Scale=1.00 matches Phase52 rule
# ═══════════════════════════════════════════════════════════════════════════════

class TestScaleOneIsPhase52:
    """scale=1.00 should reproduce Phase50/52 adjustment exactly."""

    def test_scale_one_fip_adjustment_matches_phase52(self):
        """fip_adj at scale=1.0 = tanh(delta * 0.5) * 0.003."""
        from orchestrator.phase53_sp_coefficient_calibration import _FIP_DELTA_BASE_SCALE

        for delta in [-2.0, -1.0, 0.0, 0.5, 1.5, 2.0]:
            p0 = {
                "sp_fip_delta": delta,
                "sp_fip_delta_available": True,
                "park_factor_available": False,
                "season_game_index_available": False,
            }
            base_prob = 0.55
            adj, _ = _apply_scaled_adjustment(base_prob, p0, scale=1.0)
            expected_fip_adj = math.tanh(delta * 0.5) * _FIP_DELTA_BASE_SCALE
            # Cap: raw = only fip_adj since park and season are 0
            expected_total = max(-0.025, min(0.025, expected_fip_adj))
            expected_prob = max(0.01, min(0.99, base_prob + expected_total))
            assert abs(adj - expected_prob) < 1e-9, (
                f"delta={delta}: expected {expected_prob:.8f}, got {adj:.8f}"
            )

    def test_scale_one_in_grid_results(self):
        """Grid results must include scale=1.00."""
        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        scales = [e.coefficient_scale for e in result.coefficient_grid_results]
        assert 1.0 in scales or any(abs(s - 1.0) < 1e-6 for s in scales)


# ═══════════════════════════════════════════════════════════════════════════════
# § T-004  Safe selection does not allow heavy_favorite ECE to worsen
# ═══════════════════════════════════════════════════════════════════════════════

class TestSafeSelectionHeavyFavoriteECE:
    """Safe coefficient must not allow heavy_favorite ECE to worsen vs baseline."""

    def _make_entries_with_hf_ece(self, scales_and_hf_eces: list[tuple]) -> list[GridSearchEntry]:
        """Create mock GridSearchEntry list with given (scale, hf_ece) pairs."""
        entries = []
        for scale, hf_ece in scales_and_hf_eces:
            entries.append(GridSearchEntry(
                coefficient_scale=scale,
                effective_fip_scale=0.003 * scale,
                adjusted_rows=100,
                adjusted_rate=0.5,
                mean_abs_adjustment=0.001,
                max_abs_adjustment=0.010,
                overall_brier=0.240,
                overall_bss=0.025,
                overall_ece=0.028,
                heavy_favorite_bss=0.200,
                heavy_favorite_ece=hf_ece,
                high_confidence_bss=0.200,
                high_confidence_ece=0.070,
                month_2025_04_bss=0.100,
                month_2025_04_ece=0.190,
                disagreement_high_bss=-0.010,
                disagreement_high_ece=0.080,
                diagnostic_only=True,
                candidate_patch_created=False,
                production_modified=False,
            ))
        return entries

    def test_safe_selection_rejects_worsened_hf_ece(self):
        """All candidates with hf_ece > baseline_hf_ece are rejected."""
        baseline_hf_ece = 0.085
        # All scales have hf_ece > baseline → should return NOT_SAFE
        entries = self._make_entries_with_hf_ece([
            (0.25, 0.090),
            (0.50, 0.087),
            (0.75, 0.086),
            (1.00, 0.0855),
            (1.25, 0.091),
        ])
        safe, gate, _ = _select_safe_coefficient(
            grid_results=entries,
            baseline_bss=0.020,
            baseline_ece=0.030,
            baseline_hf_ece=baseline_hf_ece,
            baseline_hc_bss=0.190,
            baseline_apr_bss=0.095,
        )
        assert gate == FEATURE_COEFFICIENT_NOT_SAFE
        assert safe is None

    def test_safe_selection_accepts_improved_hf_ece(self):
        """Candidate with hf_ece <= baseline_hf_ece should be accepted (if other conditions pass)."""
        baseline_hf_ece = 0.085
        entries = self._make_entries_with_hf_ece([
            (0.25, 0.082),   # improved HF ECE ← should be accepted
            (0.50, 0.084),   # improved HF ECE
            (1.00, 0.087),   # worsened → reject
        ])
        safe, gate, _ = _select_safe_coefficient(
            grid_results=entries,
            baseline_bss=0.020,
            baseline_ece=0.030,
            baseline_hf_ece=baseline_hf_ece,
            baseline_hc_bss=0.190,
            baseline_apr_bss=0.095,
        )
        # At least one candidate should pass
        assert gate == FEATURE_COEFFICIENT_PAPER_ONLY
        assert safe is not None
        assert safe in (0.25, 0.50)  # only the improved ones

    def test_safe_selection_rejects_worse_overall_bss(self):
        """Candidate with overall_bss < baseline is also rejected."""
        entries = [GridSearchEntry(
            coefficient_scale=0.50,
            effective_fip_scale=0.0015,
            adjusted_rows=80,
            adjusted_rate=0.4,
            mean_abs_adjustment=0.001,
            max_abs_adjustment=0.010,
            overall_brier=0.246,
            overall_bss=0.018,  # worse than baseline 0.020
            overall_ece=0.028,
            heavy_favorite_bss=0.195,
            heavy_favorite_ece=0.082,  # improved
            high_confidence_bss=0.198,
            high_confidence_ece=0.068,
            month_2025_04_bss=0.098,
            month_2025_04_ece=0.192,
            disagreement_high_bss=-0.015,
            disagreement_high_ece=0.082,
            diagnostic_only=True,
            candidate_patch_created=False,
            production_modified=False,
        )]
        safe, gate, _ = _select_safe_coefficient(
            grid_results=entries,
            baseline_bss=0.020,
            baseline_ece=0.030,
            baseline_hf_ece=0.085,
            baseline_hc_bss=0.190,
            baseline_apr_bss=0.095,
        )
        assert gate == FEATURE_COEFFICIENT_NOT_SAFE
        assert safe is None

    def test_safe_selection_skips_scale_zero(self):
        """scale=0.0 is never chosen as safe coefficient (trivially passes but meaningless)."""
        entries = [GridSearchEntry(
            coefficient_scale=0.0,  # baseline equivalent
            effective_fip_scale=0.0,
            adjusted_rows=0,
            adjusted_rate=0.0,
            mean_abs_adjustment=0.0,
            max_abs_adjustment=0.0,
            overall_brier=0.244,
            overall_bss=0.021,
            overall_ece=0.031,
            heavy_favorite_bss=0.195,
            heavy_favorite_ece=0.083,
            high_confidence_bss=0.200,
            high_confidence_ece=0.070,
            month_2025_04_bss=0.100,
            month_2025_04_ece=0.195,
            disagreement_high_bss=-0.010,
            disagreement_high_ece=0.075,
            diagnostic_only=True,
            candidate_patch_created=False,
            production_modified=False,
        )]
        safe, gate, _ = _select_safe_coefficient(
            grid_results=entries,
            baseline_bss=0.020,
            baseline_ece=0.031,
            baseline_hf_ece=0.085,
            baseline_hc_bss=0.195,
            baseline_apr_bss=0.095,
        )
        assert gate == FEATURE_COEFFICIENT_NOT_SAFE
        assert safe is None


# ═══════════════════════════════════════════════════════════════════════════════
# § T-005  Coefficient grid completeness
# ═══════════════════════════════════════════════════════════════════════════════

class TestCoefficientGrid:
    """Grid search produces entries for all specified scales."""

    def test_default_grid_has_expected_scales(self):
        assert 0.0 in DEFAULT_SCALE_GRID
        assert 0.25 in DEFAULT_SCALE_GRID
        assert 0.50 in DEFAULT_SCALE_GRID
        assert 0.75 in DEFAULT_SCALE_GRID
        assert 1.00 in DEFAULT_SCALE_GRID
        assert 1.25 in DEFAULT_SCALE_GRID
        assert len(DEFAULT_SCALE_GRID) == 6

    def test_grid_length_matches_scale_grid(self):
        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path, scale_grid=DEFAULT_SCALE_GRID)
        assert len(result.coefficient_grid_results) == len(DEFAULT_SCALE_GRID)

    def test_grid_custom_scales(self):
        """Custom scale grid is respected."""
        rows = _make_synthetic_rows(200)
        custom = [0.0, 0.5, 1.0]
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path, scale_grid=custom)
        assert len(result.coefficient_grid_results) == 3
        actual_scales = [e.coefficient_scale for e in result.coefficient_grid_results]
        assert sorted(actual_scales) == sorted(custom)

    def test_adjusted_rate_increases_with_scale(self):
        """For purely SP-driven rows, adjusted_rate at scale>0 > scale=0."""
        rows = []
        for i in range(100):
            rows.append(_make_context_row(
                model_home_prob=0.55,
                home_win=1.0 if i % 2 == 0 else 0.0,
                sp_fip_delta=1.0 if i % 2 == 0 else -1.0,
                sp_fip_delta_available=True,
                park_factor_available=False,
                season_game_index_available=False,
            ))
        e0 = _evaluate_scale(rows, scale=0.0)
        e1 = _evaluate_scale(rows, scale=1.0)
        assert e0.adjusted_rows == 0
        assert e1.adjusted_rows > 0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-006  Metrics computation
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetricsComputation:
    """_compute_metrics delegates to SSOT and returns correct structure."""

    def test_metrics_returns_expected_keys(self):
        probs = [0.6, 0.4, 0.7, 0.3, 0.55] * 20
        labels = [1.0, 0.0, 1.0, 0.0, 1.0] * 20
        m = _compute_metrics(probs, labels)
        assert "n" in m
        assert "bss" in m
        assert "ece" in m
        assert "brier" in m

    def test_metrics_insufficient_n_returns_none(self):
        """If n < _MIN_SEGMENT_N, metrics are None."""
        probs = [0.6, 0.4, 0.7]
        labels = [1.0, 0.0, 1.0]
        m = _compute_metrics(probs, labels)
        assert m["bss"] is None
        assert m["ece"] is None

    def test_metrics_bss_coin_flip_baseline(self):
        """BSS is computed relative to coin-flip baseline (0.25)."""
        # Perfect predictor: probs = labels = 1.0 or 0.0
        probs = [1.0] * 50 + [0.0] * 50
        labels = [1.0] * 50 + [0.0] * 50
        m = _compute_metrics(probs, labels)
        # BSS should be positive (better than coin flip)
        assert m["bss"] is not None
        assert m["bss"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# § T-007  Segment comparison table
# ═══════════════════════════════════════════════════════════════════════════════

class TestSegmentComparison:
    """Segment comparison table covers all required segments."""

    def test_all_required_segments_present(self):
        rows = _make_synthetic_rows(400)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        actual_segs = {s.segment for s in result.segment_comparison}
        for seg in REQUIRED_SEGMENTS:
            assert seg in actual_segs, f"Segment '{seg}' missing from comparison"

    def test_segment_label_values(self):
        """Labels are one of IMPROVED / DEGRADED / UNCHANGED."""
        rows = _make_synthetic_rows(400)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        valid_labels = {"IMPROVED", "DEGRADED", "UNCHANGED"}
        for s in result.segment_comparison:
            assert s.label in valid_labels, f"Invalid label '{s.label}' for '{s.segment}'"


# ═══════════════════════════════════════════════════════════════════════════════
# § T-008  JSON serialisability
# ═══════════════════════════════════════════════════════════════════════════════

class TestJsonReport:
    """Phase53CalibrationResult must be serialisable to JSON."""

    def test_result_serialisable(self):
        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        result_dict = asdict(result)
        json_str = json.dumps(result_dict, ensure_ascii=False, default=str)
        parsed = json.loads(json_str)
        assert "gate" in parsed
        assert "coefficient_grid_results" in parsed
        assert "candidate_patch_created" in parsed
        assert parsed["candidate_patch_created"] is False

    def test_json_report_written_to_disk(self):
        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bl_path = tmpdir_path / "baseline.jsonl"
            ctx_path = tmpdir_path / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

            # Write JSON manually (simulating --report)
            report_path = tmpdir_path / "phase53_report.json"
            import json as json_mod
            from dataclasses import asdict as _asdict
            with open(report_path, "w", encoding="utf-8") as f:
                json_mod.dump(_asdict(result), f, default=str)
            assert report_path.exists()
            with open(report_path) as f:
                data = json_mod.load(f)
            assert data["candidate_patch_created"] is False
            assert data["production_modified"] is False
            assert data["diagnostic_only"] is True


# ═══════════════════════════════════════════════════════════════════════════════
# § T-009  Markdown report generation
# ═══════════════════════════════════════════════════════════════════════════════

class TestMarkdownReport:
    """Markdown report can be generated and contains required sections."""

    def test_markdown_contains_required_sections(self):
        from scripts.run_phase53_sp_coefficient_calibration import _build_markdown

        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        md = _build_markdown(result, "2026-05-05")

        required_sections = [
            "Executive Summary",
            "Why Phase 52 Was Not Sufficient",
            "Coefficient Grid Table",
            "Best Overall Coefficient",
            "Best heavy_favorite-Safe Coefficient",
            "Safe Coefficient Selection Result",
            "Segment Comparison Table",
            "Gate Recommendation",
            "Limitations",
            "Next Phase Recommendation",
            "Hard Rules Verification",
            "Completion Marker",
        ]
        for section in required_sections:
            assert section in md, f"Section '{section}' missing from Markdown report"

    def test_markdown_contains_hard_rule_assertion(self):
        from scripts.run_phase53_sp_coefficient_calibration import _build_markdown

        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        md = _build_markdown(result, "2026-05-05")
        assert "candidate_patch_created=False" in md
        assert "production_modified=False" in md
        assert "diagnostic_only=True" in md

    def test_markdown_gate_present(self):
        from scripts.run_phase53_sp_coefficient_calibration import _build_markdown

        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            bl_path = Path(tmpdir) / "baseline.jsonl"
            ctx_path = Path(tmpdir) / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

        md = _build_markdown(result, "2026-05-05")
        assert result.gate in md

    def test_markdown_written_to_disk(self):
        from scripts.run_phase53_sp_coefficient_calibration import _build_markdown

        rows = _make_synthetic_rows(200)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            bl_path = tmpdir_path / "baseline.jsonl"
            ctx_path = tmpdir_path / "context.jsonl"
            _write_jsonl(rows, bl_path)
            _write_jsonl(rows, ctx_path)
            result = run_calibration(bl_path, ctx_path)

            md = _build_markdown(result, "2026-05-05")
            md_path = tmpdir_path / "report.md"
            md_path.write_text(md, encoding="utf-8")
            assert md_path.exists()
            content = md_path.read_text(encoding="utf-8")
            assert "Phase 53" in content


# ═══════════════════════════════════════════════════════════════════════════════
# § T-010  Apply scaled adjustment edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestApplyScaledAdjustment:
    """_apply_scaled_adjustment edge cases and correctness."""

    def test_clamp_low(self):
        """adjusted_prob never goes below 0.01."""
        p0 = {
            "sp_fip_delta": -10.0,
            "sp_fip_delta_available": True,
            "park_factor_available": False,
            "season_game_index_available": False,
        }
        adj, _ = _apply_scaled_adjustment(0.01, p0, scale=1.25)
        assert adj >= 0.01

    def test_clamp_high(self):
        """adjusted_prob never goes above 0.99."""
        p0 = {
            "sp_fip_delta": 10.0,
            "sp_fip_delta_available": True,
            "park_factor_available": False,
            "season_game_index_available": False,
        }
        adj, _ = _apply_scaled_adjustment(0.99, p0, scale=1.25)
        assert adj <= 0.99

    def test_cap_max_adjustment(self):
        """Total adjustment is capped at ±0.025."""
        # Multiple features all pushing in same direction
        p0 = {
            "sp_fip_delta": 3.0,
            "sp_fip_delta_available": True,
            "park_factor_available": True,
            "park_run_factor": 1.15,
            "season_game_index_available": True,
            "season_game_index": 0.05,  # early season
        }
        base = 0.55
        adj, _ = _apply_scaled_adjustment(base, p0, scale=1.25)
        total_adj = adj - base
        assert abs(total_adj) <= 0.025 + 1e-9

    def test_no_sp_fip_means_no_sp_adjustment(self):
        """If sp_fip_delta_available=False, SP part is 0 regardless of scale."""
        p0 = {
            "sp_fip_delta": 2.0,
            "sp_fip_delta_available": False,
            "park_factor_available": False,
            "season_game_index_available": False,
        }
        adj0, _ = _apply_scaled_adjustment(0.55, p0, scale=0.0)
        adj1, _ = _apply_scaled_adjustment(0.55, p0, scale=1.0)
        adj125, _ = _apply_scaled_adjustment(0.55, p0, scale=1.25)
        # All should equal base (no adjustment from any source)
        assert abs(adj0 - 0.55) < 1e-9
        assert abs(adj1 - 0.55) < 1e-9
        assert abs(adj125 - 0.55) < 1e-9

    def test_scale_monotonicity_for_positive_delta(self):
        """Higher scale → larger positive adjustment for positive delta."""
        p0 = {
            "sp_fip_delta": 2.0,
            "sp_fip_delta_available": True,
            "park_factor_available": False,
            "season_game_index_available": False,
        }
        base = 0.50
        adjs = []
        for scale in [0.0, 0.25, 0.50, 0.75, 1.0, 1.25]:
            adj, _ = _apply_scaled_adjustment(base, p0, scale)
            adjs.append(adj)
        # Monotonically non-decreasing
        for i in range(len(adjs) - 1):
            assert adjs[i] <= adjs[i + 1] + 1e-9, (
                f"scale ordering violated: scale[{i}]={adjs[i]} > scale[{i+1}]={adjs[i+1]}"
            )


# ═══════════════════════════════════════════════════════════════════════════════
# § T-011  Run calibration with real data (integration smoke test)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRunCalibrationIntegration:
    """Integration test using real JSONL files if they exist."""

    _BASELINE = Path("data/mlb_2025/derived/mlb_2025_per_game_predictions.jsonl")
    _CONTEXT  = Path("data/mlb_2025/derived/mlb_2025_per_game_predictions_phase52_sp_context_v1.jsonl")

    @pytest.mark.skipif(
        not (_BASELINE.exists() and _CONTEXT.exists()),
        reason="Real JSONL files not present",
    )
    def test_real_data_calibration_runs(self):
        result = run_calibration(self._BASELINE, self._CONTEXT)
        assert result.baseline_n >= 2000
        assert len(result.coefficient_grid_results) == len(DEFAULT_SCALE_GRID)
        assert result.gate in (FEATURE_COEFFICIENT_PAPER_ONLY, FEATURE_COEFFICIENT_NOT_SAFE)
        assert result.candidate_patch_created is False
        assert result.production_modified is False
        assert result.diagnostic_only is True

    @pytest.mark.skipif(
        not (_BASELINE.exists() and _CONTEXT.exists()),
        reason="Real JSONL files not present",
    )
    def test_real_data_scale_zero_is_baseline(self):
        """scale=0 with real data: no adjustment at all (adjusted_rows=0 from SP FIP alone)."""
        result = run_calibration(self._BASELINE, self._CONTEXT, scale_grid=[0.0, 1.0])
        zero_entry = next(e for e in result.coefficient_grid_results if e.coefficient_scale == 0.0)
        # Park and early season may still trigger some adjustments
        # But overall_bss at scale=0 should equal baseline_bss
        assert abs((zero_entry.overall_bss or 0.0) - (result.baseline_bss or 0.0)) < 0.001

    @pytest.mark.skipif(
        not (_BASELINE.exists() and _CONTEXT.exists()),
        reason="Real JSONL files not present",
    )
    def test_real_data_audit_hash_present(self):
        result = run_calibration(self._BASELINE, self._CONTEXT)
        assert len(result.audit_hash) == 16
        assert result.audit_hash.isalnum()
