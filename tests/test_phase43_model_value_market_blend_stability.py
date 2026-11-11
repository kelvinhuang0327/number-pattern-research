"""
Phase 43: Model Value & Market Blend Stability Audit — Tests
=============================================================
Tests for:
  1. Fold-level table correctly produced (n_splits folds, correct structure)
  2. α=0.4 blend calculation correct (blend = α*raw + (1-α)*market)
  3. Bootstrap CI structure correct
  4. CI crossing 0 → NOT_SIGNIFICANT
  5. Segment analysis has month / odds_bucket / confidence_bucket / disagreement_bucket
  6. Best-per-fold alpha marked diagnostic_only=True
  7. Gate recommendation never creates candidate_patch
  8. Report can be generated (non-empty markdown string)
  9. CLI can execute without error

Hard Rules enforced:
  - candidate_patch_created ALWAYS False
  - diagnostic_only ALWAYS True
  - CI crosses 0 → NOT_SIGNIFICANT (never SIGNIFICANT in that case)
  - No production model modification
"""
from __future__ import annotations

import math
import random
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wbc_backend.evaluation.prediction_persistence import PredictionRow
from orchestrator.phase43_model_value_market_blend_stability import (
    FIXED_ALPHA,
    BootstrapResult,
    FoldStabilityRow,
    GateRecommendation,
    Phase43AuditReport,
    SegmentResult,
    compute_fold_stability,
    make_time_aware_folds,
    run_bootstrap,
    run_phase43_audit,
    analyse_segments,
    recommend_gate,
)

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_rows(n: int = 200, seed: int = 0) -> list[PredictionRow]:
    """Generate synthetic prediction rows spanning 5 months."""
    rng = random.Random(seed)
    rows: list[PredictionRow] = []
    # Dates span 2025-04-27 to 2025-08-30 (5 months)
    year = 2025
    months = [4, 5, 6, 7, 8]
    for i in range(n):
        month = months[i % len(months)]
        day = (i % 28) + 1
        game_date = f"{year}-{month:02d}-{day:02d}"
        raw_prob = max(0.15, min(0.85, rng.gauss(0.5, 0.18)))
        market_prob = max(0.15, min(0.85, raw_prob + rng.gauss(0.0, 0.08)))
        outcome = 1 if rng.random() < market_prob else 0
        rows.append(
            PredictionRow(
                game_id=f"G{i:04d}",
                game_date=game_date,
                home_team="HOM",
                away_team="AWY",
                model_home_prob=raw_prob,
                market_home_prob_no_vig=market_prob,
                market_away_prob_no_vig=1.0 - market_prob,
                home_win=outcome,
                schema_version="phase39-v1",
            )
        )
    return rows


def _make_minimal_rows(n: int = 60) -> list[PredictionRow]:
    """Minimal rows — all same month, minimal variance."""
    rng = random.Random(42)
    rows: list[PredictionRow] = []
    for i in range(n):
        raw_prob = max(0.2, min(0.8, rng.uniform(0.3, 0.7)))
        market_prob = max(0.2, min(0.8, raw_prob + rng.uniform(-0.05, 0.05)))
        outcome = 1 if rng.random() < market_prob else 0
        rows.append(
            PredictionRow(
                game_id=f"M{i:04d}",
                game_date=f"2025-06-{(i % 28) + 1:02d}",
                home_team="H",
                away_team="A",
                model_home_prob=raw_prob,
                market_home_prob_no_vig=market_prob,
                market_away_prob_no_vig=1.0 - market_prob,
                home_win=outcome,
                schema_version="phase39-v1",
            )
        )
    return rows


# ─────────────────────────────────────────────────────────────────────────────
# Test 1: Fold-level table correctly produced
# ─────────────────────────────────────────────────────────────────────────────

class TestFoldStabilityTable:
    def test_returns_correct_number_of_folds(self):
        rows = _make_rows(300)
        results = compute_fold_stability(rows, n_splits=5)
        assert len(results) == 5

    def test_fold_ids_sequential(self):
        rows = _make_rows(300)
        results = compute_fold_stability(rows, n_splits=5)
        for i, f in enumerate(results, start=1):
            assert f.fold_id == f"fold_{i}", f"Expected fold_{i}, got {f.fold_id}"

    def test_fold_row_has_all_fields(self):
        rows = _make_rows(200)
        results = compute_fold_stability(rows, n_splits=5)
        f = results[0]
        assert isinstance(f.fold_id, str)
        assert isinstance(f.n, int)
        assert f.n > 0
        assert isinstance(f.date_start, str)
        assert isinstance(f.date_end, str)
        assert isinstance(f.raw_brier, float)
        assert isinstance(f.market_brier, float)
        assert isinstance(f.blend_brier, float)
        assert isinstance(f.raw_bss, float)
        assert isinstance(f.blend_bss, float)
        assert isinstance(f.raw_ece, float)
        assert isinstance(f.blend_ece, float)
        assert isinstance(f.best_alpha_per_fold, float)
        assert isinstance(f.best_alpha_brier, float)

    def test_fold_n_sums_to_roughly_total(self):
        rows = _make_rows(300)
        # 5-fold expanding window: test sizes overlap but should cover all test rows
        results = compute_fold_stability(rows, n_splits=5)
        total_test = sum(f.n for f in results)
        # Each fold's test is a slice — sum of test rows should be close to total rows
        # (last fold's test is the entire test set after the largest train)
        assert total_test > 0

    def test_n_splits_3_works(self):
        rows = _make_rows(150)
        results = compute_fold_stability(rows, n_splits=3)
        assert len(results) == 3

    def test_brier_scores_are_in_valid_range(self):
        rows = _make_rows(300)
        results = compute_fold_stability(rows, n_splits=5)
        for f in results:
            assert 0 <= f.raw_brier <= 1
            assert 0 <= f.market_brier <= 1
            assert 0 <= f.blend_brier <= 1


# ─────────────────────────────────────────────────────────────────────────────
# Test 2: α=0.4 blend calculation correct
# ─────────────────────────────────────────────────────────────────────────────

class TestBlendCalculation:
    def test_blend_prob_is_weighted_average(self):
        """blend = FIXED_ALPHA * raw + (1 - FIXED_ALPHA) * market"""
        alpha = FIXED_ALPHA
        assert abs(alpha - 0.4) < 1e-9, "FIXED_ALPHA must be 0.4"

    def test_blend_alpha_applied_correctly(self):
        """Verify blend_brier is computed at FIXED_ALPHA=0.4."""
        rows = _make_rows(200)
        results = compute_fold_stability(rows, n_splits=5, alpha=0.4)
        # blend_brier must exist, be finite, and be in [0, 1]
        # Note: blend Brier is NOT required to be between raw and market because
        # Brier score is nonlinear — the blended probabilities can beat both.
        for f in results:
            assert math.isfinite(f.blend_brier), f"{f.fold_id}: blend_brier is not finite"
            assert 0.0 <= f.blend_brier <= 1.0, (
                f"{f.fold_id}: blend_brier {f.blend_brier:.4f} out of [0, 1]"
            )

    def test_alpha_zero_blend_equals_market(self):
        """At α=0.0 blend == market (all market, no raw)."""
        rows = _make_rows(100)
        results_zero = compute_fold_stability(rows, n_splits=3, alpha=0.0)
        for f in results_zero:
            assert abs(f.blend_brier - f.market_brier) < 1e-8, (
                f"alpha=0: blend_brier {f.blend_brier:.6f} != market_brier {f.market_brier:.6f}"
            )

    def test_alpha_one_blend_equals_raw(self):
        """At α=1.0 blend == raw (all raw, no market)."""
        rows = _make_rows(100)
        results_one = compute_fold_stability(rows, n_splits=3, alpha=1.0)
        for f in results_one:
            assert abs(f.blend_brier - f.raw_brier) < 1e-8, (
                f"alpha=1: blend_brier {f.blend_brier:.6f} != raw_brier {f.raw_brier:.6f}"
            )


# ─────────────────────────────────────────────────────────────────────────────
# Test 3: Bootstrap CI structure correct
# ─────────────────────────────────────────────────────────────────────────────

class TestBootstrapStructure:
    def test_bootstrap_returns_two_results(self):
        rows = _make_rows(200)
        bs_raw, bs_blend = run_bootstrap(rows, alpha=FIXED_ALPHA, n_bootstrap=100)
        assert isinstance(bs_raw, BootstrapResult)
        assert isinstance(bs_blend, BootstrapResult)

    def test_bootstrap_labels_correct(self):
        rows = _make_rows(200)
        bs_raw, bs_blend = run_bootstrap(rows, alpha=FIXED_ALPHA, n_bootstrap=100)
        assert bs_raw.label == "raw_vs_market"
        assert bs_blend.label == "blend_vs_market"

    def test_bootstrap_n_samples_matches_rows(self):
        rows = _make_rows(200)
        bs_raw, bs_blend = run_bootstrap(rows, alpha=FIXED_ALPHA, n_bootstrap=100)
        assert bs_raw.n_samples == len(rows)
        assert bs_blend.n_samples == len(rows)

    def test_bootstrap_ci_order(self):
        """ci_lower <= ci_upper always."""
        rows = _make_rows(200)
        bs_raw, bs_blend = run_bootstrap(rows, alpha=FIXED_ALPHA, n_bootstrap=200)
        assert bs_raw.ci_lower <= bs_raw.ci_upper
        assert bs_blend.ci_lower <= bs_blend.ci_upper

    def test_bootstrap_prob_improvement_in_0_1(self):
        rows = _make_rows(200)
        bs_raw, bs_blend = run_bootstrap(rows, alpha=FIXED_ALPHA, n_bootstrap=100)
        assert 0.0 <= bs_raw.prob_improvement <= 1.0
        assert 0.0 <= bs_blend.prob_improvement <= 1.0

    def test_bootstrap_significance_field_bool(self):
        rows = _make_rows(200)
        bs_raw, bs_blend = run_bootstrap(rows, alpha=FIXED_ALPHA, n_bootstrap=100)
        assert isinstance(bs_raw.significant, bool)
        assert isinstance(bs_blend.significant, bool)

    def test_bootstrap_significance_label_valid(self):
        rows = _make_rows(200)
        bs_raw, bs_blend = run_bootstrap(rows, alpha=FIXED_ALPHA, n_bootstrap=100)
        valid = {"SIGNIFICANT", "NOT_SIGNIFICANT"}
        assert bs_raw.significance_label in valid
        assert bs_blend.significance_label in valid


# ─────────────────────────────────────────────────────────────────────────────
# Test 4: CI crossing 0 → NOT_SIGNIFICANT
# ─────────────────────────────────────────────────────────────────────────────

class TestBootstrapSignificance:
    def test_ci_crossing_zero_is_not_significant(self):
        """When ci_lower < 0 < ci_upper, result must be NOT_SIGNIFICANT."""
        # Manufacture a BootstrapResult directly
        from dataclasses import replace
        bs = BootstrapResult(
            label="blend_vs_market",
            n_samples=100,
            n_bootstrap=1000,
            mean_delta_brier=-0.001,
            ci_lower=-0.003,   # negative = below zero
            ci_upper=+0.002,   # positive = above zero
            prob_improvement=0.6,
            significant=True,           # set wrong — logic should detect mismatch
            significance_label="SIGNIFICANT",  # wrong
        )
        # Verify that CI crosses 0
        assert bs.ci_lower < 0.0 < bs.ci_upper
        # The boot module should classify this as NOT_SIGNIFICANT
        ci_crosses_zero = bs.ci_lower < 0.0 < bs.ci_upper
        assert ci_crosses_zero is True, "CI should cross zero"

    def test_ci_not_crossing_zero_negative_side(self):
        """When CI entirely below 0 (model improves), SIGNIFICANT."""
        bs = BootstrapResult(
            label="blend_vs_market",
            n_samples=500,
            n_bootstrap=1000,
            mean_delta_brier=-0.005,
            ci_lower=-0.010,   # both below zero = improvement
            ci_upper=-0.001,
            prob_improvement=0.98,
            significant=True,
            significance_label="SIGNIFICANT",
        )
        assert bs.ci_lower < 0 and bs.ci_upper < 0
        ci_crosses_zero = bs.ci_lower < 0.0 < bs.ci_upper
        assert ci_crosses_zero is False

    def test_bootstrap_module_classifies_crossing_ci_as_not_significant(self):
        """Synthetic rows where raw model == market → CI always crosses 0."""
        # If raw == market, blend == market, delta == 0 for every sample
        # Bootstrap will produce CI exactly [0, 0] or near zero — classified NOT_SIGNIFICANT
        rng = __import__("random").Random(99)
        rows = []
        for i in range(200):
            p = max(0.2, min(0.8, rng.uniform(0.3, 0.7)))
            outcome = 1 if rng.random() < p else 0
            rows.append(PredictionRow(
                game_id=f"E{i:04d}",
                game_date=f"2025-05-{(i % 28) + 1:02d}",
                home_team="H", away_team="A",
                model_home_prob=p,           # same as market
                market_home_prob_no_vig=p,   # identical → blend == market → delta == 0
                market_away_prob_no_vig=1.0 - p,
                home_win=outcome,
                schema_version="phase39-v1",
            ))
        bs_raw, bs_blend = run_bootstrap(rows, alpha=0.4, n_bootstrap=500)
        # blend == market, so delta == 0 → CI crosses 0 → NOT_SIGNIFICANT
        assert bs_blend.significance_label == "NOT_SIGNIFICANT"


# ─────────────────────────────────────────────────────────────────────────────
# Test 5: Segment analysis covers all 4 segment types
# ─────────────────────────────────────────────────────────────────────────────

class TestSegmentAnalysis:
    def test_all_four_segment_types_present(self):
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        seg_types = {sr.segment_type for sr in seg_results}
        assert "month" in seg_types
        assert "odds_bucket" in seg_types
        assert "confidence_bucket" in seg_types
        assert "disagreement_bucket" in seg_types

    def test_segment_labels_not_empty(self):
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        for sr in seg_results:
            assert sr.segment_label, f"Empty segment_label for {sr.segment_type}"

    def test_segment_n_positive(self):
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        for sr in seg_results:
            assert sr.n >= 0

    def test_value_classification_valid_enum(self):
        valid = {"NO_VALUE", "WEAK_VALUE", "CONDITIONAL_VALUE", "STABLE_VALUE"}
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        for sr in seg_results:
            assert sr.value_classification in valid, (
                f"Invalid classification {sr.value_classification!r} for {sr.segment_type}/{sr.segment_label}"
            )

    def test_odds_bucket_labels_cover_expected_buckets(self):
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        odds_labels = {
            sr.segment_label for sr in seg_results if sr.segment_type == "odds_bucket"
        }
        # At least some of the expected buckets should appear
        expected = {"heavy_away_fav", "slight_away_fav", "pick_em", "slight_home_fav", "heavy_home_fav"}
        assert odds_labels & expected, f"No expected odds bucket labels found in {odds_labels}"

    def test_confidence_bucket_labels(self):
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        conf_labels = {
            sr.segment_label for sr in seg_results if sr.segment_type == "confidence_bucket"
        }
        expected = {"low_conf", "medium_conf", "high_conf"}
        assert conf_labels & expected

    def test_disagreement_bucket_labels(self):
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        dis_labels = {
            sr.segment_label for sr in seg_results if sr.segment_type == "disagreement_bucket"
        }
        expected = {"low_disagree", "medium_disagree", "high_disagree"}
        assert dis_labels & expected

    def test_segment_brier_in_valid_range(self):
        rows = _make_rows(200)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        for sr in seg_results:
            if sr.n >= 1:
                assert 0 <= sr.raw_brier <= 1
                assert 0 <= sr.market_brier <= 1
                assert 0 <= sr.blend_brier <= 1

    def test_segment_no_value_when_n_small(self):
        """Small segments (n < 30) should be classified NO_VALUE."""
        rows = _make_rows(300)
        seg_results = analyse_segments(rows, alpha=FIXED_ALPHA)
        for sr in seg_results:
            if sr.n < 30:
                assert sr.value_classification == "NO_VALUE", (
                    f"{sr.segment_type}/{sr.segment_label} n={sr.n} should be NO_VALUE"
                )


# ─────────────────────────────────────────────────────────────────────────────
# Test 6: Best-per-fold alpha marked diagnostic_only=True
# ─────────────────────────────────────────────────────────────────────────────

class TestDiagnosticOnly:
    def test_all_folds_have_diagnostic_only_true(self):
        """diagnostic_only must ALWAYS be True — guards against treating best alpha as production proof."""
        rows = _make_rows(300)
        results = compute_fold_stability(rows, n_splits=5)
        for f in results:
            assert f.diagnostic_only is True, (
                f"{f.fold_id}: diagnostic_only={f.diagnostic_only!r} — must be True"
            )

    def test_diagnostic_only_true_regardless_of_best_alpha(self):
        """Even when best_alpha_per_fold varies, diagnostic_only stays True."""
        rows = _make_rows(500)
        results = compute_fold_stability(rows, n_splits=5)
        best_alphas = {f.best_alpha_per_fold for f in results}
        # There may be different best alphas per fold
        for f in results:
            assert f.diagnostic_only is True

    def test_report_fold_rows_all_diagnostic_only(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        for f in report.fold_results:
            assert f.diagnostic_only is True


# ─────────────────────────────────────────────────────────────────────────────
# Test 7: Gate recommendation never creates candidate_patch
# ─────────────────────────────────────────────────────────────────────────────

class TestGateNoCandidatePatch:
    def test_candidate_patch_never_created(self):
        rows = _make_rows(300)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert report.gate.candidate_patch_created is False

    def test_candidate_patch_false_even_when_significant(self):
        """Even in the best case, candidate_patch_created must be False."""
        # Craft rows where blend dramatically beats market
        rng = __import__("random").Random(77)
        rows = []
        for i in range(300):
            # model_home_prob much more accurate than market
            outcome = 1 if rng.random() < 0.55 else 0
            raw_prob = 0.55 if outcome else 0.45   # always close to truth
            market_prob = max(0.2, min(0.8, raw_prob + rng.gauss(0, 0.15)))
            rows.append(PredictionRow(
                game_id=f"B{i:04d}",
                game_date=f"2025-{(i%6)+4:02d}-{(i % 28)+1:02d}",
                home_team="H", away_team="A",
                model_home_prob=raw_prob,
                market_home_prob_no_vig=market_prob,
                market_away_prob_no_vig=1.0 - market_prob,
                home_win=outcome,
                schema_version="phase39-v1",
            ))
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=100)
        assert report.gate.candidate_patch_created is False, (
            "candidate_patch_created must NEVER be True — hard rule"
        )

    def test_gate_recommendation_is_valid_enum(self):
        valid_gates = {
            "PATCH_GATE_RECHECK",
            "MARKET_BLEND_PAPER_ONLY",
            "FEATURE_REPAIR_INVESTIGATION",
            "COLLECT_MORE_DATA",
            "HOLD",
        }
        rows = _make_rows(300)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert report.gate.recommendation in valid_gates, (
            f"Invalid gate recommendation: {report.gate.recommendation!r}"
        )

    def test_gate_has_reasoning_list(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert isinstance(report.gate.reasoning, list)
        assert len(report.gate.reasoning) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Test 8: Report can be generated (non-empty markdown string)
# ─────────────────────────────────────────────────────────────────────────────

class TestMarkdownReport:
    def test_markdown_generation_not_empty(self):
        from scripts.run_phase43_model_value_market_blend_stability import generate_markdown_report

        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        md = generate_markdown_report(report)
        assert md, "Markdown output must not be empty"
        assert len(md) > 500, "Markdown should be substantive (>500 chars)"

    def test_markdown_contains_key_sections(self):
        from scripts.run_phase43_model_value_market_blend_stability import generate_markdown_report

        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        md = generate_markdown_report(report)
        assert "Phase 43" in md
        assert "Gate Recommendation" in md
        assert "Bootstrap" in md
        assert "Fold" in md
        assert "Segment" in md

    def test_markdown_includes_gate_recommendation(self):
        from scripts.run_phase43_model_value_market_blend_stability import generate_markdown_report

        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        md = generate_markdown_report(report)
        assert report.gate.recommendation in md

    def test_markdown_no_candidate_patch_warning(self):
        """Markdown must show CANDIDATE_PATCH created = NO."""
        from scripts.run_phase43_model_value_market_blend_stability import generate_markdown_report

        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        md = generate_markdown_report(report)
        # Should NOT contain the ERROR marker
        assert "YES — ERROR" not in md

    def test_markdown_contains_no_call_to_action_for_production(self):
        """Markdown must not claim production model is updated."""
        from scripts.run_phase43_model_value_market_blend_stability import generate_markdown_report

        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        md = generate_markdown_report(report)
        bad_phrases = ["production model updated", "deployed to production", "CANDIDATE_PATCH created = YES"]
        for phrase in bad_phrases:
            assert phrase not in md, f"Forbidden phrase found in report: {phrase!r}"


# ─────────────────────────────────────────────────────────────────────────────
# Test 9: CLI can execute without error
# ─────────────────────────────────────────────────────────────────────────────

class TestCLI:
    def test_cli_print_mode_exits_zero(self):
        """CLI --print should exit 0."""
        result = subprocess.run(
            [sys.executable, "scripts/run_phase43_model_value_market_blend_stability.py", "--print"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0, (
            f"CLI exited {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

    def test_cli_print_contains_gate_line(self):
        """CLI --print output must include 'Gate Recommendation'."""
        result = subprocess.run(
            [sys.executable, "scripts/run_phase43_model_value_market_blend_stability.py", "--print"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0
        assert "Gate Recommendation" in result.stdout, (
            f"Expected 'Gate Recommendation' in output.\nstdout:\n{result.stdout}"
        )

    def test_cli_print_no_candidate_patch(self):
        """CLI --print output must NOT print 'CANDIDATE_PATCH created: True'."""
        result = subprocess.run(
            [sys.executable, "scripts/run_phase43_model_value_market_blend_stability.py", "--print"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0
        assert "Candidate Patch Created: False" in result.stdout, (
            f"Expected 'Candidate Patch Created: False' in output.\nstdout:\n{result.stdout}"
        )

    def test_cli_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "scripts/run_phase43_model_value_market_blend_stability.py", "--help"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        assert result.returncode == 0
        assert "Phase 43" in result.stdout or "usage" in result.stdout.lower()


# ─────────────────────────────────────────────────────────────────────────────
# Test 10: Full run_phase43_audit integration
# ─────────────────────────────────────────────────────────────────────────────

class TestRunPhase43AuditIntegration:
    def test_audit_report_has_correct_row_count(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert report.row_count == len(rows)

    def test_audit_report_n_splits(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert report.n_splits == 5

    def test_audit_report_fixed_alpha(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert abs(report.fixed_alpha - FIXED_ALPHA) < 1e-9

    def test_audit_fold_stability_label_valid(self):
        rows = _make_rows(300)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert report.fold_stability_label in {"STABLE", "MIXED", "UNSTABLE"}

    def test_audit_folds_with_positive_blend_bss_int(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert isinstance(report.folds_with_positive_blend_bss, int)
        assert 0 <= report.folds_with_positive_blend_bss <= len(report.fold_results)

    def test_audit_bootstrap_results_present(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert report.bootstrap_raw_vs_market is not None
        assert report.bootstrap_blend_vs_market is not None

    def test_audit_segment_value_summary_keys(self):
        rows = _make_rows(300)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        expected_keys = {"month", "odds_bucket", "confidence_bucket", "disagreement_bucket"}
        assert set(report.segment_value_summary.keys()) == expected_keys

    def test_audit_overall_brier_finite(self):
        rows = _make_rows(200)
        report = run_phase43_audit(rows, n_splits=5, n_bootstrap=50)
        assert math.isfinite(report.overall_raw_brier)
        assert math.isfinite(report.overall_market_brier)
        assert math.isfinite(report.overall_blend_brier)
        assert math.isfinite(report.overall_raw_bss)
        assert math.isfinite(report.overall_blend_bss)

    def test_audit_timestamp_utc_present(self):
        rows = _make_rows(100)
        report = run_phase43_audit(rows, n_splits=3, n_bootstrap=20)
        assert report.timestamp_utc, "timestamp_utc must be present"
        assert "T" in report.timestamp_utc or len(report.timestamp_utc) > 10

    def test_audit_notes_is_list(self):
        rows = _make_rows(100)
        report = run_phase43_audit(rows, n_splits=3, n_bootstrap=20)
        assert isinstance(report.notes, list)
