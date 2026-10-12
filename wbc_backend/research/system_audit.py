from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DataFlowStage:
    stage: str
    module: str
    inputs: list[str]
    outputs: list[str]


@dataclass(frozen=True)
class AuditFinding:
    category: str
    severity: str
    title: str
    weakness: str
    optimization_opportunity: str
    files: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FunctionalAuditReport:
    data_flow: list[DataFlowStage]
    structural_weaknesses: list[AuditFinding]
    modeling_blind_spots: list[AuditFinding]
    missing_feature_domains: list[AuditFinding]
    data_leakage_risks: list[AuditFinding]
    regime_dependency_risks: list[AuditFinding]
    correlation_risks: list[AuditFinding]
    stability_weaknesses: list[AuditFinding]

    def all_findings(self) -> list[AuditFinding]:
        buckets = [
            self.structural_weaknesses,
            self.modeling_blind_spots,
            self.missing_feature_domains,
            self.data_leakage_risks,
            self.regime_dependency_risks,
            self.correlation_risks,
            self.stability_weaknesses,
        ]
        merged: list[AuditFinding] = []
        for bucket in buckets:
            merged.extend(bucket)
        return merged


def map_data_flow() -> list[DataFlowStage]:
    return [
        DataFlowStage(
            stage="Data ingestion",
            module="wbc_backend/ingestion/providers.py",
            inputs=["WBC schedule", "team metrics feeds", "odds feeds"],
            outputs=["raw schedule dataframe", "raw metrics dataframe"],
        ),
        DataFlowStage(
            stage="Cleaning and validation",
            module="wbc_backend/cleaning/preprocess.py",
            inputs=["raw schedule dataframe", "raw metrics dataframe"],
            outputs=["validated metrics", "completeness diagnostics"],
        ),
        DataFlowStage(
            stage="Feature engineering",
            module="wbc_backend/features/advanced.py",
            inputs=["matchup context", "roster snapshots", "travel context"],
            outputs=["feature dictionary", "fatigue and stress factors"],
        ),
        DataFlowStage(
            stage="Model ensemble prediction",
            module="wbc_backend/models/ensemble.py",
            inputs=["base models", "advanced features"],
            outputs=["win probability", "expected runs", "confidence"],
        ),
        DataFlowStage(
            stage="WBC tournament rule adjustment",
            module="wbc_backend/pipeline/wbc_rule_engine.py",
            inputs=["raw ensemble prediction", "pitch limit", "sample size"],
            outputs=["rule-adjusted prediction", "diagnostic deltas"],
        ),
        DataFlowStage(
            stage="Simulation and market calibration",
            module="wbc_backend/simulation/monte_carlo.py + wbc_backend/betting/market.py",
            inputs=["rule-adjusted prediction", "totals/spread lines"],
            outputs=["probability map", "market-bias adjusted probability"],
        ),
        DataFlowStage(
            stage="Bet selection and risk controls",
            module="wbc_backend/betting/optimizer.py + wbc_backend/betting/risk_control.py",
            inputs=["true probabilities", "market odds", "bankroll state"],
            outputs=["top recommendations", "stake sizing"],
        ),
        DataFlowStage(
            stage="Reporting and persistence",
            module="wbc_backend/reporting/renderers.py",
            inputs=["game output", "simulation summary", "market diagnostics"],
            outputs=["markdown report", "json report"],
        ),
    ]


def _f(
    category: str,
    severity: str,
    title: str,
    weakness: str,
    optimization_opportunity: str,
    files: list[str],
) -> AuditFinding:
    return AuditFinding(
        category=category,
        severity=severity,
        title=title,
        weakness=weakness,
        optimization_opportunity=optimization_opportunity,
        files=files,
    )


def run_full_system_audit() -> FunctionalAuditReport:
    structural = [
        _f(
            category="Structural",
            severity="HIGH",
            title="Research loop is not hard-gated by tests",
            weakness="Optimization/self-improve modules are present but not orchestrated with mandatory validation gates before deployment.",
            optimization_opportunity="Introduce phase executor with pass/fail validation and stop-on-failure semantics.",
            files=["wbc_backend/optimization/self_improve.py", "wbc_backend/strategy/master_optimizer.py"],
        ),
        _f(
            category="Structural",
            severity="MEDIUM",
            title="Prediction pipeline fallback can hide data quality failures",
            weakness="When matchup lookup fails, default matchup values are injected and execution continues.",
            optimization_opportunity="Promote fallback to explicit degraded mode with confidence and stake hard-cap.",
            files=["wbc_backend/pipeline/service.py"],
        ),
        _f(
            category="Structural",
            severity="MEDIUM",
            title="Backtest engine coverage is fragmented",
            weakness="There are multiple backtest scripts and runners without a single canonical harness for comparable metrics.",
            optimization_opportunity="Unify via one backtest contract producing calibration/CLV/risk outputs per market.",
            files=["scripts/legacy_entrypoints/backtester.py", "wbc_backend/optimization/walkforward.py", "wbc_backend/backtest/runner.py"],
        ),
    ]

    blind_spots = [
        _f(
            category="Modeling",
            severity="HIGH",
            title="No explicit residual alpha model",
            weakness="Ensemble combines direct predictors but lacks a residual learner for systematic misspecification.",
            optimization_opportunity="Train residual model on model_error(t) using market microstructure and late lineup deltas.",
            files=["wbc_backend/models/ensemble.py"],
        ),
        _f(
            category="Modeling",
            severity="HIGH",
            title="No explicit regime-switching estimator in core inference path",
            weakness="Regime classifier exists but not fully integrated into probability generation and uncertainty scaling.",
            optimization_opportunity="Gate model families and variance multipliers by inferred regime state.",
            files=["wbc_backend/intelligence/regime_classifier.py", "wbc_backend/models/ensemble.py"],
        ),
        _f(
            category="Modeling",
            severity="MEDIUM",
            title="No adversarial validation in training loop",
            weakness="Train/test distribution shift risk is not explicitly quantified before model release.",
            optimization_opportunity="Add adversarial AUC thresholding to block unstable model updates.",
            files=["wbc_backend/models/trainer.py", "wbc_backend/optimization/modeling.py"],
        ),
    ]

    missing_features = [
        _f(
            category="Feature",
            severity="HIGH",
            title="Market microstructure features are underrepresented in model training",
            weakness="Steam velocity, depth imbalance, and quote fragility are not first-class features in core model input.",
            optimization_opportunity="Add quote-level derived factors and evaluate incremental CLV lift.",
            files=["wbc_backend/features/advanced.py", "wbc_backend/strategy/market_microstructure.py"],
        ),
        _f(
            category="Feature",
            severity="MEDIUM",
            title="Psychological pressure proxies not encoded",
            weakness="Elimination pressure, host bias, and leverage-context proxies are not represented in standardized feature schema.",
            optimization_opportunity="Engineer elimination pressure index and benchmark with cross-year holdout.",
            files=["wbc_backend/domain/schemas.py"],
        ),
        _f(
            category="Feature",
            severity="MEDIUM",
            title="Cross-market correlation graph missing",
            weakness="No explicit feature representation of joint market dislocations (ML-RL-OU interactions).",
            optimization_opportunity="Build graph-based cross-market features and feed to meta-layer.",
            files=["wbc_backend/betting/optimizer.py"],
        ),
    ]

    leakage = [
        _f(
            category="Leakage",
            severity="HIGH",
            title="Potential odds-timestamp leakage in training datasets",
            weakness="If closing or near-close odds snapshots enter pregame training set without strict cutoff, leakage can inflate edge.",
            optimization_opportunity="Enforce event-time feature cut with immutable as-of snapshot registry.",
            files=["wbc_backend/optimization/dataset.py", "wbc_backend/evaluation/real_backtest.py"],
        ),
        _f(
            category="Leakage",
            severity="MEDIUM",
            title="Simulation and bet logic share same adjusted probability",
            weakness="Single adjusted probability reused across downstream decisions can hide calibration mismatch.",
            optimization_opportunity="Use nested calibration outputs (raw, calibrated, market-adjusted) and compare reliability curves.",
            files=["wbc_backend/pipeline/service.py"],
        ),
    ]

    regime = [
        _f(
            category="Regime",
            severity="HIGH",
            title="Tournament phase transition risk",
            weakness="Pool-stage behavior differs from knockout stage in lineup certainty, volatility, and motivation.",
            optimization_opportunity="Use phase-specific model priors and distinct calibration maps.",
            files=["wbc_backend/pipeline/wbc_rule_engine.py", "wbc_backend/intelligence/regime_classifier.py"],
        ),
        _f(
            category="Regime",
            severity="MEDIUM",
            title="Liquidity regime shifts not tied to size constraints",
            weakness="Risk controls are mostly bankroll-based; market depth and execution regime are not direct inputs.",
            optimization_opportunity="Link allowed stake to real-time liquidity regime score.",
            files=["wbc_backend/betting/risk_control.py", "wbc_backend/intelligence/risk_engine.py"],
        ),
    ]

    correlation = [
        _f(
            category="Correlation",
            severity="HIGH",
            title="Daily portfolio covariance is heuristic-only",
            weakness="Existing allocation logic uses rule heuristics and does not estimate covariance from scenario returns.",
            optimization_opportunity="Deploy covariance + CVaR-aware optimizer for daily slate construction.",
            files=["wbc_backend/strategy/portfolio_allocator.py"],
        ),
        _f(
            category="Correlation",
            severity="MEDIUM",
            title="Venue/weather cluster concentration risk",
            weakness="Common-factor concentration across same venue/time window can amplify downside tail.",
            optimization_opportunity="Apply exposure clustering constraints across weather and venue buckets.",
            files=["wbc_backend/strategy/portfolio_allocator.py"],
        ),
    ]

    stability = [
        _f(
            category="Stability",
            severity="HIGH",
            title="Core model path previously had brittle field assumptions",
            weakness="Model path expected optional odds fields and side identifiers that may not exist on matchup object.",
            optimization_opportunity="Harden schema tolerance and initialize diagnostics deterministically.",
            files=["wbc_backend/models/ensemble.py"],
        ),
        _f(
            category="Stability",
            severity="HIGH",
            title="Clutch feature computation previously returned None",
            weakness="Missing return path can silently poison downstream arithmetic and calibration.",
            optimization_opportunity="Bounded scalar return with deterministic clamp.",
            files=["wbc_backend/features/advanced.py"],
        ),
        _f(
            category="Stability",
            severity="MEDIUM",
            title="Confidence mutation in bet loop can cascade",
            weakness="In-loop confidence adjustment can influence subsequent bets unintentionally.",
            optimization_opportunity="Use immutable local confidence per candidate and preserve global base confidence.",
            files=["wbc_backend/betting/optimizer.py"],
        ),
    ]

    return FunctionalAuditReport(
        data_flow=map_data_flow(),
        structural_weaknesses=structural,
        modeling_blind_spots=blind_spots,
        missing_feature_domains=missing_features,
        data_leakage_risks=leakage,
        regime_dependency_risks=regime,
        correlation_risks=correlation,
        stability_weaknesses=stability,
    )
