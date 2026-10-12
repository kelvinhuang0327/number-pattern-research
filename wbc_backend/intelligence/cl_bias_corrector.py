"""
Closing Line Bias Corrector — Phase 4a Intelligence Module
============================================================
Tracks systematic bias between predicted and actual closing lines,
and applies EWMA-based correction to edge estimates.

Why needed:
  If the model consistently overestimates closing line value (CLV),
  raw edges are inflated → overbetting. This module detects and
  corrects for that drift.

Algorithm:
  For each settled bet i:
    error[i] = predicted_cl[i] - actual_cl[i]
    bias[i]  = α · error[i] + (1 - α) · bias[i-1]    (EWMA)

  Adjusted edge:
    adjusted_edge = raw_edge - bias[latest]

  Confidence weighting:
    |bias| > 0.03 → confidence × 0.80
    |bias| > 0.05 → confidence × 0.60
    |bias| > 0.08 → flag model staleness

Integration:
  Applied in decision_engine BEFORE bet selection (Phase 4).
  Adjusts raw_edge and confidence before position sizing.
"""
from __future__ import annotations

from dataclasses import dataclass, field


# ─── Configuration ──────────────────────────────────────────────────────────

DEFAULT_ALPHA = 0.05          # EWMA decay rate (slow)
MIN_SAMPLES_FOR_CORRECTION = 20
BIAS_WARNING = 0.03           # mild correction starts
BIAS_DANGER = 0.05            # serious correction
BIAS_STALENESS = 0.08         # model staleness alert


# ─── Data Structures ───────────────────────────────────────────────────────

@dataclass
class CLBiasReport:
    """Output from the bias corrector."""
    adjusted_edge: float = 0.0
    confidence_multiplier: float = 1.0
    bias_estimate: float = 0.0
    correction_applied: float = 0.0   # how much was subtracted
    is_stale: bool = False
    is_converged: bool = False
    sample_count: int = 0
    recent_mae: float = 0.0           # mean absolute error (last 10)
    drift_direction: str = "NEUTRAL"  # HOME / AWAY / NEUTRAL
    details: dict[str, str] = field(default_factory=dict)


# ─── Main Class ─────────────────────────────────────────────────────────────

class ClosingLineBiasCorrector:
    """
    EWMA-based closing line bias correction.

    Usage:
        corrector = ClosingLineBiasCorrector()

        # After each settled bet:
        corrector.record(predicted_cl=0.52, actual_cl=0.54)

        # Before each new bet:
        report = corrector.correct_edge(raw_edge=0.05)
        # report.adjusted_edge will be bias-corrected
    """

    def __init__(
        self,
        alpha: float = DEFAULT_ALPHA,
        min_samples: int = MIN_SAMPLES_FOR_CORRECTION,
    ):
        self.alpha = alpha
        self.min_samples = min_samples

        # State
        self.bias_estimate: float = 0.0
        self.errors: list[float] = []
        self.calibration_pairs: list[tuple[float, float]] = []
        self._n_positive: int = 0
        self._n_negative: int = 0

    @property
    def sample_count(self) -> int:
        return len(self.errors)

    @property
    def has_enough_data(self) -> bool:
        return self.sample_count >= self.min_samples

    # ── Recording ──────────────────────────────────────────────

    def record(self, predicted_cl: float, actual_cl: float) -> None:
        """
        Record a predicted vs actual closing line pair.

        Args:
            predicted_cl: Model's predicted closing implied probability
            actual_cl: Actual observed closing implied probability
        """
        error = predicted_cl - actual_cl
        self.errors.append(error)
        self.calibration_pairs.append((predicted_cl, actual_cl))

        # EWMA update
        self.bias_estimate = (
            self.alpha * error + (1 - self.alpha) * self.bias_estimate
        )

        if error > 0:
            self._n_positive += 1
        else:
            self._n_negative += 1

    # ── Correction ─────────────────────────────────────────────

    def correct_edge(self, raw_edge: float) -> CLBiasReport:
        """
        Apply bias correction to a raw edge estimate.

        Returns CLBiasReport with adjusted edge and confidence multiplier.
        """
        report = CLBiasReport()
        report.sample_count = self.sample_count

        if not self.has_enough_data:
            # Not enough data — return raw edge, no correction
            report.adjusted_edge = raw_edge
            report.confidence_multiplier = 1.0
            report.details["status"] = (
                f"Insufficient data ({self.sample_count}/{self.min_samples})"
            )
            return report

        # Apply correction
        report.bias_estimate = round(self.bias_estimate, 6)
        report.correction_applied = round(-self.bias_estimate, 6)
        report.adjusted_edge = round(raw_edge - self.bias_estimate, 6)

        # Confidence multiplier based on bias magnitude
        abs_bias = abs(self.bias_estimate)
        if abs_bias > BIAS_STALENESS:
            report.confidence_multiplier = 0.60
            report.is_stale = True
        elif abs_bias > BIAS_DANGER:
            # Linear interpolation between 0.60 and 0.80
            t = (BIAS_STALENESS - abs_bias) / (BIAS_STALENESS - BIAS_DANGER)
            report.confidence_multiplier = round(0.60 + t * 0.20, 3)
        elif abs_bias > BIAS_WARNING:
            # Linear interpolation between 0.80 and 1.00
            t = (BIAS_DANGER - abs_bias) / (BIAS_DANGER - BIAS_WARNING)
            report.confidence_multiplier = round(0.80 + t * 0.20, 3)
        else:
            report.confidence_multiplier = 1.0

        # Convergence check
        report.is_converged = abs_bias < 0.02

        # Drift direction
        if self.bias_estimate > 0.01:
            report.drift_direction = "HOME"  # Model overestimates home CL
        elif self.bias_estimate < -0.01:
            report.drift_direction = "AWAY"  # Model overestimates away CL
        else:
            report.drift_direction = "NEUTRAL"

        # Recent MAE
        recent = self.errors[-10:] if len(self.errors) >= 10 else self.errors
        report.recent_mae = round(
            sum(abs(e) for e in recent) / max(len(recent), 1), 5
        )

        # Diagnostics
        report.details = {
            "bias": f"{self.bias_estimate:+.5f}",
            "correction": f"{report.correction_applied:+.5f}",
            "conf_mult": f"{report.confidence_multiplier:.3f}",
            "stale": str(report.is_stale),
            "mae_10": f"{report.recent_mae:.5f}",
            "positive_errors": str(self._n_positive),
            "negative_errors": str(self._n_negative),
            "converged": str(report.is_converged),
        }

        return report

    # ── Metrics ────────────────────────────────────────────────

    def convergence_metrics(self) -> dict:
        """Track bias convergence over time."""
        if len(self.errors) < 10:
            return {"converged": False, "samples": len(self.errors)}

        recent_10 = self.errors[-10:]
        recent_50 = (
            self.errors[-50:] if len(self.errors) >= 50 else self.errors
        )

        return {
            "converged": abs(self.bias_estimate) < 0.02,
            "bias": round(self.bias_estimate, 5),
            "mae_10": round(
                sum(abs(e) for e in recent_10) / len(recent_10), 5
            ),
            "mae_50": round(
                sum(abs(e) for e in recent_50) / len(recent_50), 5
            ),
            "drift_direction": "HOME" if self.bias_estimate > 0 else "AWAY",
            "samples": len(self.errors),
            "positive_pct": round(
                self._n_positive / max(self.sample_count, 1), 3
            ),
        }

    def reset(self) -> None:
        """Reset all accumulated state."""
        self.bias_estimate = 0.0
        self.errors.clear()
        self.calibration_pairs.clear()
        self._n_positive = 0
        self._n_negative = 0


# ─── Convenience Function ──────────────────────────────────────────────────

def create_corrector(
    alpha: float = DEFAULT_ALPHA,
    min_samples: int = MIN_SAMPLES_FOR_CORRECTION,
) -> ClosingLineBiasCorrector:
    """Factory function for creating a bias corrector."""
    return ClosingLineBiasCorrector(alpha=alpha, min_samples=min_samples)


# ─── Smoke Tests ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print()
    print("=" * 60)
    print("📐 Closing Line Bias Corrector — Smoke Tests")
    print("=" * 60)

    c = ClosingLineBiasCorrector(min_samples=5)

    # Simulate: model consistently overestimates CL by ~2%
    print("\n━━━ Test 1: Systematic positive bias ━━━")
    for i in range(10):
        c.record(predicted_cl=0.55 + 0.005 * i, actual_cl=0.53 + 0.005 * i)

    report = c.correct_edge(raw_edge=0.05)
    print(f"  Bias: {report.bias_estimate:+.5f}")
    print(f"  Correction: {report.correction_applied:+.5f}")
    print(f"  Raw edge: 0.05 → Adjusted: {report.adjusted_edge:.5f}")
    print(f"  Confidence: {report.confidence_multiplier:.3f}")
    print(f"  Converged: {report.is_converged}")
    assert report.adjusted_edge < 0.05, "Should reduce edge"
    # With α=0.05, 10 samples at 2% bias → bias ~0.008 (below 0.03 confidence threshold)
    # Confidence stays at 1.0 — this is correct (EWMA is conservative by design)
    assert report.bias_estimate > 0, "Should detect positive bias direction"
    print("  ✅ PASSED")

    # Test 2: Unbiased model
    print("\n━━━ Test 2: Unbiased model ━━━")
    c2 = ClosingLineBiasCorrector(min_samples=5)
    import random
    random.seed(42)
    for _ in range(20):
        cl = 0.50 + random.gauss(0, 0.02)
        c2.record(predicted_cl=cl, actual_cl=cl + random.gauss(0, 0.005))

    r2 = c2.correct_edge(raw_edge=0.05)
    print(f"  Bias: {r2.bias_estimate:+.5f}")
    print(f"  Correction: {r2.correction_applied:+.5f}")
    print(f"  Adjusted edge: {r2.adjusted_edge:.5f}")
    print(f"  Confidence: {r2.confidence_multiplier:.3f}")
    print(f"  Converged: {r2.is_converged}")
    assert r2.confidence_multiplier >= 0.8, "Should have high confidence"
    print("  ✅ PASSED")

    # Test 3: Large bias → staleness alert
    print("\n━━━ Test 3: Large bias → staleness ━━━")
    c3 = ClosingLineBiasCorrector(alpha=0.3, min_samples=3)
    for _ in range(10):
        c3.record(predicted_cl=0.60, actual_cl=0.50)  # 10% systematic bias

    r3 = c3.correct_edge(raw_edge=0.05)
    print(f"  Bias: {r3.bias_estimate:+.5f}")
    print(f"  Stale: {r3.is_stale}")
    print(f"  Confidence: {r3.confidence_multiplier:.3f}")
    assert r3.is_stale, "Should flag staleness"
    assert r3.confidence_multiplier <= 0.60, "Should heavily reduce confidence"
    print("  ✅ PASSED")

    # Test 4: Convergence metrics
    print("\n━━━ Test 4: Convergence metrics ━━━")
    metrics = c.convergence_metrics()
    print(f"  {metrics}")
    assert "converged" in metrics
    assert "mae_10" in metrics
    print("  ✅ PASSED")

    print(f"\n{'=' * 60}")
    print("✅ All 4 smoke tests passed")
    print(f"{'=' * 60}")
