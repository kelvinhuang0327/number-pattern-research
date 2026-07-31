from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .feature_space import MANDATORY_FEATURE_DOMAINS, build_feature_space_expansion, domain_coverage
from .infrastructure import (
    CLVTracker,
    calibration_monitoring,
    cross_year_validation_splits,
    drift_detection,
    edge_decay_analysis,
    monte_carlo_season_simulation,
    walk_forward_windows,
)
from .methodology import MANDATORY_METHODS, build_methodological_expansion, dynamic_ensemble_weights
from .phase_plan import build_v3_phase_plan
from .portfolio_v3 import bankroll_survival_probability, optimize_cvar_allocation
from .system_audit import run_full_system_audit


@dataclass(frozen=True)
class PhaseExecutionResult:
    phase: str
    passed: bool
    summary: str
    metrics: dict[str, float]


class V3ResearchExecutor:
    def __init__(self, seed: int = 42):
        self.seed = seed

    def _phase_1_audit(self) -> PhaseExecutionResult:
        report = run_full_system_audit()
        sections = [
            report.structural_weaknesses,
            report.modeling_blind_spots,
            report.missing_feature_domains,
            report.data_leakage_risks,
            report.regime_dependency_risks,
            report.correlation_risks,
            report.stability_weaknesses,
        ]
        passed = bool(report.data_flow) and all(len(s) > 0 for s in sections)
        metrics = {
            "data_flow_stages": float(len(report.data_flow)),
            "findings_total": float(len(report.all_findings())),
        }
        return PhaseExecutionResult(
            phase="Phase 1",
            passed=passed,
            summary="Functional audit complete.",
            metrics=metrics,
        )

    def _phase_2_feature_expansion(self) -> PhaseExecutionResult:
        specs = build_feature_space_expansion()
        coverage = domain_coverage(specs)
        missing = [d for d in MANDATORY_FEATURE_DOMAINS if coverage.get(d, 0) <= 0]
        passed = len(missing) == 0
        return PhaseExecutionResult(
            phase="Phase 2",
            passed=passed,
            summary="Feature-space protocol generated.",
            metrics={
                "feature_specs": float(len(specs)),
                "missing_domains": float(len(missing)),
            },
        )

    def _phase_3_methodology(self) -> PhaseExecutionResult:
        methods = build_methodological_expansion()
        method_names = {m.method for m in methods}
        missing = [m for m in MANDATORY_METHODS if m not in method_names]
        weights = dynamic_ensemble_weights({"elo": -0.21, "poisson": -0.24, "gbm": -0.18})
        passed = len(missing) == 0 and abs(sum(weights.values()) - 1.0) < 1e-6
        return PhaseExecutionResult(
            phase="Phase 3",
            passed=passed,
            summary="Methodological expansion cataloged.",
            metrics={
                "methods": float(len(methods)),
                "missing_methods": float(len(missing)),
                "weight_sum": float(sum(weights.values())),
            },
        )

    def _phase_4_portfolio_risk(self) -> PhaseExecutionResult:
        rng = np.random.default_rng(self.seed)
        expected_edges = np.array([0.018, 0.013, 0.011, 0.009], dtype=float)
        scenarios = rng.normal(loc=0.0, scale=0.04, size=(500, 4))
        # Add shared factor to force realistic correlation structure.
        shared = rng.normal(loc=0.0, scale=0.02, size=(500, 1))
        scenarios = scenarios + shared

        opt = optimize_cvar_allocation(
            expected_edges=expected_edges,
            scenario_returns=scenarios,
            max_gross_exposure=0.18,
            lambda_cvar=0.2,
        )
        survival = bankroll_survival_probability(
            opt.weights,
            scenarios,
            horizon_days=90,
            ruin_threshold=0.65,
            n_paths=1200,
            seed=self.seed,
        )
        passed = (
            np.isfinite(opt.expected_return)
            and np.isfinite(opt.cvar_95)
            and 0.0 <= opt.gross_exposure <= 0.18 + 1e-9
            and 0.0 <= survival <= 1.0
        )
        return PhaseExecutionResult(
            phase="Phase 4",
            passed=bool(passed),
            summary="Portfolio CVaR optimization and survival simulation complete.",
            metrics={
                "gross_exposure": float(opt.gross_exposure),
                "cvar95": float(opt.cvar_95),
                "survival_prob": float(survival),
            },
        )

    def _phase_5_research_infra(self) -> PhaseExecutionResult:
        windows = walk_forward_windows(n_samples=420, train_size=240, test_size=30, step_size=30)
        splits = cross_year_validation_splits([2021, 2022, 2023, 2024, 2025], min_train_years=2)
        season = monte_carlo_season_simulation([0.005, -0.01, 0.012, -0.004, 0.007], horizon_days=80, n_paths=1200)
        calibration = calibration_monitoring(
            probabilities=[0.62, 0.45, 0.71, 0.39, 0.55, 0.67],
            outcomes=[1, 0, 1, 0, 1, 1],
            bins=5,
        )
        drift = drift_detection(
            reference=[0.42, 0.48, 0.51, 0.46, 0.49, 0.53],
            current=[0.57, 0.62, 0.58, 0.64, 0.55, 0.60],
        )
        decay = edge_decay_analysis([(0, 0.06), (30, 0.05), (60, 0.031), (90, 0.022)])
        tracker = CLVTracker()
        tracker.add(open_odds=2.05, close_odds=1.98, stake=1.0)
        tracker.add(open_odds=1.92, close_odds=1.87, stake=1.0)
        clv = tracker.summary()

        passed = (
            len(windows) > 0
            and len(splits) > 0
            and calibration["ece"] >= 0.0
            and 0.0 <= clv["positive_rate"] <= 1.0
            and season["median_ending_bankroll"] > 0.0
        )
        return PhaseExecutionResult(
            phase="Phase 5",
            passed=passed,
            summary="Continuous research infrastructure validated.",
            metrics={
                "walkforward_windows": float(len(windows)),
                "cross_year_splits": float(len(splits)),
                "clv_positive_rate": float(clv["positive_rate"]),
                "edge_half_life": float(decay["half_life"]),
                "drift_flag": float(drift["drift_flag"]),
            },
        )

    def _phase_6_plan(self) -> PhaseExecutionResult:
        phases = build_v3_phase_plan()
        has_tests = all(len(p.testing_strategy) > 0 for p in phases)
        has_metrics = all(len(p.validation_metrics) > 0 for p in phases)
        passed = len(phases) >= 6 and has_tests and has_metrics
        return PhaseExecutionResult(
            phase="Phase 6",
            passed=passed,
            summary="Implementation phase plan compiled.",
            metrics={"phase_count": float(len(phases))},
        )

    def execute_all(self) -> list[PhaseExecutionResult]:
        phases = [
            self._phase_1_audit,
            self._phase_2_feature_expansion,
            self._phase_3_methodology,
            self._phase_4_portfolio_risk,
            self._phase_5_research_infra,
            self._phase_6_plan,
        ]
        results: list[PhaseExecutionResult] = []
        for phase_fn in phases:
            result = phase_fn()
            results.append(result)
            if not result.passed:
                raise RuntimeError(f"{result.phase} failed: {result.summary}")
        return results
