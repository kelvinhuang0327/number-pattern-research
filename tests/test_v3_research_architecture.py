from __future__ import annotations

import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from wbc_backend.research.execution import V3ResearchExecutor
from wbc_backend.research.feature_space import MANDATORY_FEATURE_DOMAINS, build_feature_space_expansion, domain_coverage
from wbc_backend.research.infrastructure import calibration_monitoring, drift_detection, walk_forward_windows
from wbc_backend.research.methodology import MANDATORY_METHODS, build_methodological_expansion
from wbc_backend.research.phase_plan import build_v3_phase_plan
from wbc_backend.research.portfolio_v3 import (
    compute_portfolio_covariance,
    correlation_adjusted_kelly,
    optimize_cvar_allocation,
)
from wbc_backend.research.system_audit import run_full_system_audit


class TestFunctionalAudit(unittest.TestCase):
    def test_audit_has_all_required_sections(self):
        report = run_full_system_audit()
        self.assertGreater(len(report.data_flow), 0)
        self.assertGreater(len(report.structural_weaknesses), 0)
        self.assertGreater(len(report.modeling_blind_spots), 0)
        self.assertGreater(len(report.missing_feature_domains), 0)
        self.assertGreater(len(report.data_leakage_risks), 0)
        self.assertGreater(len(report.regime_dependency_risks), 0)
        self.assertGreater(len(report.correlation_risks), 0)
        self.assertGreater(len(report.stability_weaknesses), 0)


class TestFeatureAndMethodCoverage(unittest.TestCase):
    def test_feature_domains_complete(self):
        specs = build_feature_space_expansion()
        coverage = domain_coverage(specs)
        for domain in MANDATORY_FEATURE_DOMAINS:
            self.assertIn(domain, coverage)
            self.assertGreater(coverage[domain], 0)

    def test_methodology_complete(self):
        methods = build_methodological_expansion()
        names = {m.method for m in methods}
        for required in MANDATORY_METHODS:
            self.assertIn(required, names)


class TestPortfolioNumerics(unittest.TestCase):
    def test_covariance_and_kelly_with_collinearity(self):
        # Perfect collinearity to test pseudo-inverse stability.
        scenarios = np.array(
            [
                [0.01, 0.01, 0.02],
                [-0.01, -0.01, -0.02],
                [0.02, 0.02, 0.01],
                [-0.02, -0.02, -0.01],
            ],
            dtype=float,
        )
        cov = compute_portfolio_covariance(scenarios)
        w = correlation_adjusted_kelly([0.01, 0.009, 0.012], cov, leverage_cap=0.15)
        self.assertTrue(np.all(np.isfinite(w)))
        self.assertLessEqual(float(np.sum(np.abs(w))), 0.15 + 1e-9)

    def test_cvar_optimizer_returns_finite(self):
        rng = np.random.default_rng(42)
        scenarios = rng.normal(0.0, 0.03, size=(300, 4))
        expected = [0.014, 0.011, 0.010, 0.008]
        result = optimize_cvar_allocation(expected, scenarios, max_gross_exposure=0.2, lambda_cvar=1.1)
        self.assertTrue(np.isfinite(result.expected_return))
        self.assertTrue(np.isfinite(result.cvar_95))
        self.assertGreaterEqual(result.gross_exposure, 0.0)
        self.assertLessEqual(result.gross_exposure, 0.2 + 1e-9)


class TestInfrastructureAndExecution(unittest.TestCase):
    def test_research_infra_metrics(self):
        windows = walk_forward_windows(240, 120, 20, 20)
        self.assertGreater(len(windows), 0)
        cal = calibration_monitoring([0.7, 0.4, 0.6, 0.3], [1, 0, 1, 0], bins=4)
        self.assertGreaterEqual(cal["ece"], 0.0)
        drift = drift_detection([0.45, 0.5, 0.48, 0.51], [0.6, 0.58, 0.62, 0.64])
        self.assertIn("drift_flag", drift)

    def test_phase_executor_all_pass(self):
        executor = V3ResearchExecutor(seed=42)
        results = executor.execute_all()
        self.assertEqual(len(results), 6)
        self.assertTrue(all(r.passed for r in results))

    def test_phase_plan_contains_testing_design(self):
        plan = build_v3_phase_plan()
        self.assertGreaterEqual(len(plan), 6)
        for phase in plan:
            self.assertGreater(len(phase.testing_strategy), 0)
            self.assertGreater(len(phase.validation_metrics), 0)


if __name__ == "__main__":
    unittest.main()
