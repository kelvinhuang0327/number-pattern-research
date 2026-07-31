from __future__ import annotations

from dataclasses import dataclass
from math import exp


MANDATORY_METHODS = [
    "Dynamic ensemble weighting",
    "Online learning",
    "Bayesian updating",
    "Regime-switching models",
    "Hidden Markov Models",
    "Hierarchical Bayesian models",
    "Survival analysis",
    "Reinforcement learning",
    "Meta-labeling",
    "Residual modeling",
    "Model stacking with meta learner",
    "Adversarial validation",
    "Feature stability selection",
    "Cross-season generalization testing",
]


@dataclass(frozen=True)
class MethodologySpec:
    method: str
    implementation_logic: str
    data_requirements: str
    validation_protocol: str


def build_methodological_expansion() -> list[MethodologySpec]:
    return [
        MethodologySpec(
            method="Dynamic ensemble weighting",
            implementation_logic="Use rolling inverse-Brier and CLV scores to update weights with softmax smoothing.",
            data_requirements="Per-model predictions, outcomes, CLV realizations by timestamp.",
            validation_protocol="Rolling out-of-sample comparison vs static weights on Brier, ECE, CLV hit rate.",
        ),
        MethodologySpec(
            method="Online learning",
            implementation_logic="Apply incremental updates (SGD/FTRL-style) with decay to handle non-stationary markets.",
            data_requirements="Chronological feature-outcome stream with strict event-time ordering.",
            validation_protocol="Prequential evaluation with concept drift checkpoints and rollback triggers.",
        ),
        MethodologySpec(
            method="Bayesian updating",
            implementation_logic="Treat market and model probabilities as priors/likelihoods and update posterior edge confidence.",
            data_requirements="Prior model uncertainty, observed outcomes, line move evidence.",
            validation_protocol="Posterior predictive calibration and credible interval coverage.",
        ),
        MethodologySpec(
            method="Regime-switching models",
            implementation_logic="Estimate latent market regimes and use regime-conditional model families and risk multipliers.",
            data_requirements="Microstructure state variables, liquidity, volatility, phase context.",
            validation_protocol="State persistence accuracy and regime-conditional profitability stability.",
        ),
        MethodologySpec(
            method="Hidden Markov Models",
            implementation_logic="Infer hidden states from observed line dynamics and transition probabilities.",
            data_requirements="Time-series of implied probabilities and volatility indicators.",
            validation_protocol="Out-of-sample log-likelihood and downstream decision uplift.",
        ),
        MethodologySpec(
            method="Hierarchical Bayesian models",
            implementation_logic="Pool information across teams/players/seasons while preserving group-level heterogeneity.",
            data_requirements="Multi-level panel data across leagues, seasons, teams, players.",
            validation_protocol="Cross-group posterior shrinkage diagnostics and transfer performance.",
        ),
        MethodologySpec(
            method="Survival analysis",
            implementation_logic="Model edge decay time-to-event for execution timing and order slicing decisions.",
            data_requirements="Edge birth timestamps, quote updates, edge expiration outcomes.",
            validation_protocol="Concordance index and half-life prediction error.",
        ),
        MethodologySpec(
            method="Reinforcement learning",
            implementation_logic="Learn action policy for execution timing and size under transaction cost and impact constraints.",
            data_requirements="State-action-reward trajectories from simulation and live logs.",
            validation_protocol="Off-policy evaluation and stress-tested reward stability.",
        ),
        MethodologySpec(
            method="Meta-labeling",
            implementation_logic="Primary model proposes candidates; meta-model predicts whether to execute/skip.",
            data_requirements="Candidate edge logs, realized CLV, slippage, post-trade outcomes.",
            validation_protocol="Precision at top-k and reduction in false-positive executions.",
        ),
        MethodologySpec(
            method="Residual modeling",
            implementation_logic="Fit residual learner on model error to capture omitted interactions and nonlinearities.",
            data_requirements="Base model predictions, realized outcomes, full feature set.",
            validation_protocol="Residual autocorrelation reduction and incremental logloss gain.",
        ),
        MethodologySpec(
            method="Model stacking with meta learner",
            implementation_logic="Combine statistical and ML base learners using leakage-safe out-of-fold meta features.",
            data_requirements="Out-of-fold base predictions and aligned labels.",
            validation_protocol="Stacked-vs-best-single model comparison across years.",
        ),
        MethodologySpec(
            method="Adversarial validation",
            implementation_logic="Train train-vs-test discriminator; high AUC implies shift requiring reweighting.",
            data_requirements="Train and deployment feature matrices with domain labels.",
            validation_protocol="AUC thresholding, feature drift attribution, retrain gating.",
        ),
        MethodologySpec(
            method="Feature stability selection",
            implementation_logic="Bootstrap subsampling and keep features with high selection probability.",
            data_requirements="Feature matrix, labels, repeated resample seeds.",
            validation_protocol="Selection frequency stability and out-of-sample variance reduction.",
        ),
        MethodologySpec(
            method="Cross-season generalization testing",
            implementation_logic="Train on prior seasons and evaluate on unseen seasons with strict chronological boundaries.",
            data_requirements="Multi-season aligned datasets with identical feature schema.",
            validation_protocol="Season-by-season Brier, ECE, CLV, and drawdown robustness matrix.",
        ),
    ]


def dynamic_ensemble_weights(model_scores: dict[str, float], temperature: float = 4.0) -> dict[str, float]:
    if not model_scores:
        return {}
    max_score = max(model_scores.values())
    shifted = {k: v - max_score for k, v in model_scores.items()}
    exps = {k: exp(temperature * s) for k, s in shifted.items()}
    denom = sum(exps.values()) or 1.0
    return {k: v / denom for k, v in exps.items()}


def bayesian_beta_update(alpha: float, beta: float, outcomes: list[int]) -> dict[str, float]:
    a = max(1e-6, alpha) + sum(1 for x in outcomes if x == 1)
    b = max(1e-6, beta) + sum(1 for x in outcomes if x == 0)
    mean = a / (a + b)
    variance = (a * b) / (((a + b) ** 2) * (a + b + 1))
    return {"alpha": a, "beta": b, "mean": mean, "variance": variance}
