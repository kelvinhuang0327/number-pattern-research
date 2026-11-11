"""
Phase 41: Metrics SSOT — Test Suite
=====================================
Validates wbc_backend/evaluation/metrics.py as the canonical single source
of truth for all MLB evaluation computations.

≥ 17 tests required. This file covers 20 tests across 7 classes.

Hard rules enforced:
  - No external API / LLM calls.
  - No modification to model probabilities.
  - No calibration repair.
  - Probabilities clipped only in log_loss (not Brier/ECE).
"""
from __future__ import annotations

import math
import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from wbc_backend.evaluation.metrics import (
    american_odds_to_implied_prob,
    normalize_no_vig,
    american_moneyline_pair_to_no_vig,
    brier_score,
    brier_skill_score,
    log_loss_score,
    expected_calibration_error,
    reliability_bins,
    calibration_summary,
    compare_model_to_market,
)

# ── Phase 37/38 report constants ──────────────────────────────────────────────
REPORT_MODEL_BRIER = 0.2796
REPORT_MARKET_BRIER = 0.2451
REPORT_BSS = -0.141


# ══════════════════════════════════════════════════════════════════════════════
# § 1  American Odds Conversion
# ══════════════════════════════════════════════════════════════════════════════

class TestAmericanOddsConversion:
    """3 tests"""

    def test_01_plus100_returns_half(self):
        """T01: +100 (even money) → 0.5"""
        val = american_odds_to_implied_prob("+100")
        assert abs(val - 0.5) < 1e-9, f"Expected 0.5, got {val}"

    def test_02_minus150_conversion(self):
        """T02: -150 → 150/250 = 0.6"""
        val = american_odds_to_implied_prob("-150")
        expected = 150.0 / 250.0
        assert abs(val - expected) < 1e-9, f"Expected {expected}, got {val}"

    def test_03_plus120_conversion(self):
        """T03: +120 → 100/220"""
        val = american_odds_to_implied_prob("+120")
        expected = 100.0 / 220.0
        assert abs(val - expected) < 1e-9, f"Expected {expected}, got {val}"

    def test_04_numeric_input(self):
        """T04: numeric int/float input works same as string"""
        val_str = american_odds_to_implied_prob("-150")
        val_int = american_odds_to_implied_prob(-150)
        assert abs(val_str - val_int) < 1e-12

    def test_05_invalid_raises_without_safe(self):
        """T05: invalid odds string raises ValueError when safe=False"""
        with pytest.raises(ValueError):
            american_odds_to_implied_prob("INVALID", safe=False)

    def test_06_invalid_returns_half_with_safe(self):
        """T06: invalid odds returns 0.5 when safe=True"""
        val = american_odds_to_implied_prob("INVALID", safe=True)
        assert val == 0.5


# ══════════════════════════════════════════════════════════════════════════════
# § 2  No-Vig Normalization
# ══════════════════════════════════════════════════════════════════════════════

class TestNoVigNormalization:
    """3 tests"""

    def test_07_sums_to_one(self):
        """T07: normalize_no_vig output sums to 1.0"""
        h, a = normalize_no_vig(0.6, 0.55)
        assert abs(h + a - 1.0) < 1e-10, f"Sum = {h + a}"

    def test_08_rejects_zero_total(self):
        """T08: normalize_no_vig raises ValueError when total <= 0"""
        with pytest.raises(ValueError):
            normalize_no_vig(0.0, 0.0)

    def test_09_pair_helper_ok(self):
        """T09: american_moneyline_pair_to_no_vig returns ok=True and sums to 1"""
        r = american_moneyline_pair_to_no_vig("+100", "+100")
        assert r["ok"] is True
        assert abs(r["home_no_vig"] + r["away_no_vig"] - 1.0) < 1e-10
        assert r["home_no_vig"] == r["away_no_vig"]


# ══════════════════════════════════════════════════════════════════════════════
# § 3  Brier Score
# ══════════════════════════════════════════════════════════════════════════════

class TestBrierScore:
    """3 tests"""

    def test_10_known_fixture(self):
        """T10: brier_score([0.9, 0.8], [1, 1]) = 0.025"""
        val = brier_score([0.9, 0.8], [1.0, 1.0])
        assert abs(val - 0.025) < 1e-10, f"Expected 0.025, got {val}"

    def test_11_rejects_prob_above_one(self):
        """T11: probability > 1 raises ValueError (not silently clipped)"""
        with pytest.raises(ValueError):
            brier_score([1.1], [1.0])

    def test_12_rejects_prob_below_zero(self):
        """T12: probability < 0 raises ValueError"""
        with pytest.raises(ValueError):
            brier_score([-0.1], [0.0])

    def test_13_perfect_prediction_is_zero(self):
        """T13: perfect predictions → Brier = 0"""
        val = brier_score([1.0, 0.0], [1.0, 0.0])
        assert abs(val) < 1e-10

    def test_14_coin_flip_is_025(self):
        """T14: constant 0.5 predictions → Brier = 0.25"""
        val = brier_score([0.5] * 100, [1.0] * 100)
        assert abs(val - 0.25) < 1e-10


# ══════════════════════════════════════════════════════════════════════════════
# § 4  Brier Skill Score
# ══════════════════════════════════════════════════════════════════════════════

class TestBrierSkillScore:
    """3 tests"""

    def test_15_report_constants_match(self):
        """T15: BSS from report constants matches REPORT_BSS within 0.001"""
        bss = brier_skill_score(REPORT_MODEL_BRIER, REPORT_MARKET_BRIER)
        assert bss is not None
        assert abs(bss - REPORT_BSS) < 0.001, f"Expected ≈{REPORT_BSS}, got {bss}"

    def test_16_positive_when_model_better(self):
        """T16: BSS > 0 when model_brier < market_brier"""
        bss = brier_skill_score(0.22, 0.25)
        assert bss is not None and bss > 0

    def test_17_baseline_zero_returns_none(self):
        """T17: BSS returns None when baseline_brier = 0 (not NaN, not crash)"""
        bss = brier_skill_score(0.2, 0.0)
        assert bss is None, f"Expected None, got {bss!r}"


# ══════════════════════════════════════════════════════════════════════════════
# § 5  Log Loss
# ══════════════════════════════════════════════════════════════════════════════

class TestLogLoss:
    """2 tests"""

    def test_18_clips_safely_no_crash(self):
        """T18: log_loss_score clips 0.0/1.0 to avoid -inf"""
        val = log_loss_score([1.0, 0.0], [1.0, 0.0])
        assert math.isfinite(val), f"Expected finite, got {val}"
        assert val >= 0.0

    def test_19_empty_raises(self):
        """T19: empty probs raises ValueError"""
        with pytest.raises(ValueError):
            log_loss_score([], [])


# ══════════════════════════════════════════════════════════════════════════════
# § 6  ECE and Reliability
# ══════════════════════════════════════════════════════════════════════════════

class TestECEAndReliability:
    """3 tests"""

    def test_20_ece_returns_required_keys(self):
        """T20: expected_calibration_error returns dict with ece, n_bins, sample_size, bins"""
        r = expected_calibration_error([0.5, 0.5], [0.0, 1.0])
        for key in ("ece", "n_bins", "sample_size", "bins"):
            assert key in r, f"Missing key: {key}"
        assert isinstance(r["bins"], list)

    def test_21_reliability_bins_structure(self):
        """T21: reliability_bins returns list[dict] with required keys per bin"""
        bins = reliability_bins([0.3, 0.7], [0.0, 1.0])
        assert isinstance(bins, list) and len(bins) > 0
        required = {"bin_lower", "bin_upper", "count", "mean_confidence", "mean_accuracy", "gap"}
        for b in bins:
            assert required.issubset(b.keys()), f"Missing keys in bin: {b}"

    def test_22_ece_perfect_calibration_is_zero(self):
        """T22: perfectly calibrated predictions → ECE = 0"""
        # 100 samples per 0.1-wide bin, each with matching accuracy
        probs = []
        labels = []
        for i in range(10):
            mid = (i + 0.5) / 10.0
            # Fill bin with mid probability, fraction = mid positive outcomes
            n = 100
            n_pos = round(mid * n)
            probs.extend([mid] * n)
            labels.extend([1.0] * n_pos + [0.0] * (n - n_pos))
        r = expected_calibration_error(probs, labels)
        assert r["ece"] < 0.02, f"ECE = {r['ece']} (expected ≈ 0)"


# ══════════════════════════════════════════════════════════════════════════════
# § 7  Model vs Market Comparison
# ══════════════════════════════════════════════════════════════════════════════

class TestCompareModelToMarket:
    """3 tests"""

    def test_23_all_required_keys_present(self):
        """T23: compare_model_to_market returns all 9 required output keys"""
        r = compare_model_to_market(
            model_probs=[0.6, 0.4, 0.7],
            market_probs=[0.55, 0.45, 0.65],
            labels=[1.0, 0.0, 1.0],
        )
        required = {
            "sample_size", "model_brier", "market_brier", "bss",
            "model_log_loss", "market_log_loss", "model_ece", "market_ece",
            "reliability_bins",
        }
        assert required.issubset(r.keys()), f"Missing: {required - r.keys()}"

    def test_24_bss_none_when_market_brier_zero(self):
        """T24: bss = None when market probs are perfect (market_brier = 0)"""
        # Perfect market → market_brier = 0
        r = compare_model_to_market(
            model_probs=[0.6, 0.4],
            market_probs=[1.0, 0.0],
            labels=[1.0, 0.0],
        )
        assert r["bss"] is None, f"Expected None bss, got {r['bss']}"

    def test_25_negative_bss_when_model_worse(self):
        """T25: BSS negative when model is worse than market"""
        r = compare_model_to_market(
            model_probs=[0.5, 0.5, 0.5, 0.5],
            market_probs=[0.9, 0.1, 0.8, 0.2],
            labels=[1.0, 0.0, 1.0, 0.0],
        )
        assert r["bss"] is not None
        assert r["bss"] < 0, f"Expected BSS < 0, got {r['bss']}"


# ══════════════════════════════════════════════════════════════════════════════
# § 8  SSOT Delegation: prediction_persistence
# ══════════════════════════════════════════════════════════════════════════════

class TestPredictionPersistenceSSoT:
    """2 tests"""

    def test_26_recompute_metrics_uses_metrics_module(self):
        """T26: recompute_metrics_from_rows is implemented via metrics SSOT"""
        import inspect
        from wbc_backend.evaluation import prediction_persistence as pp
        source = inspect.getsource(pp.recompute_metrics_from_rows)
        # Must reference metrics SSOT delegation functions
        assert "_metrics_brier_score" in source, (
            "recompute_metrics_from_rows must delegate to _metrics_brier_score from metrics.py"
        )

    def test_27_recompute_metrics_empty_rows(self):
        """T27: recompute_metrics_from_rows returns error dict for empty input"""
        from wbc_backend.evaluation.prediction_persistence import recompute_metrics_from_rows
        result = recompute_metrics_from_rows([])
        assert result["sample_size"] == 0
        assert result["model_brier"] is None
        assert "error" in result


# ══════════════════════════════════════════════════════════════════════════════
# § 9  SSOT Delegation: Scripts
# ══════════════════════════════════════════════════════════════════════════════

class TestScriptsDelegateToSSoT:
    """2 tests"""

    def test_28_phase37_script_imports_metrics(self):
        """T28: Phase 37 script imports from wbc_backend.evaluation.metrics"""
        script = ROOT / "scripts" / "run_phase37_mlb_bss_root_cause_audit.py"
        source = script.read_text(encoding="utf-8")
        assert "from wbc_backend.evaluation.metrics import" in source, (
            "Phase 37 script must import from wbc_backend.evaluation.metrics"
        )

    def test_29_phase38_script_imports_metrics(self):
        """T29: Phase 38 script imports from wbc_backend.evaluation.metrics"""
        script = ROOT / "scripts" / "run_phase38_mlb_bss_repair_preview.py"
        source = script.read_text(encoding="utf-8")
        assert "from wbc_backend.evaluation.metrics import" in source, (
            "Phase 38 script must import from wbc_backend.evaluation.metrics"
        )


# ══════════════════════════════════════════════════════════════════════════════
# § 10  Hard Rule: No External API / LLM
# ══════════════════════════════════════════════════════════════════════════════

class TestNoExternalAPI:
    """1 test"""

    def test_30_metrics_module_no_external_calls(self):
        """T30: metrics.py contains no external HTTP/API call imports"""
        metrics_path = ROOT / "wbc_backend" / "evaluation" / "metrics.py"
        source = metrics_path.read_text(encoding="utf-8")
        banned = ["requests.get", "requests.post", "urllib.request.urlopen",
                  "openai", "anthropic", "httpx"]
        for token in banned:
            assert token not in source, (
                f"metrics.py must not contain: {token!r}"
            )
