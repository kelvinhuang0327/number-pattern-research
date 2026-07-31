"""
Live Retrainer — Online Model Update Engine
=============================================
Institution-grade module for:
  1. Automatic model weight updates after each game result
  2. Distribution drift detection (PSI, KL-divergence)
  3. Model staleness / performance decay monitoring
  4. Automatic model retirement & replacement

This module ensures the prediction system adapts to changing
conditions without human intervention, while guarding against
over-adaptation via stability checks.
"""
from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path


# ─── Data Structures ─────────────────────────────────────────────────────────

@dataclass
class GameResult:
    """Observed game outcome for model updating."""
    game_id: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    home_win: bool
    total_runs: int
    timestamp: float = 0.0


@dataclass
class ModelPerformance:
    """Performance tracking for a single sub-model."""
    model_name: str
    brier_scores: list[float] = field(default_factory=list)
    log_losses: list[float] = field(default_factory=list)
    predictions: list[float] = field(default_factory=list)
    actuals: list[int] = field(default_factory=list)
    timestamps: list[float] = field(default_factory=list)

    @property
    def recent_brier(self) -> float:
        """Average Brier score over last 20 games."""
        recent = self.brier_scores[-20:] if self.brier_scores else [0.25]
        return sum(recent) / len(recent)

    @property
    def recent_logloss(self) -> float:
        """Average log-loss over last 20 games."""
        recent = self.log_losses[-20:] if self.log_losses else [0.693]
        return sum(recent) / len(recent)

    @property
    def trend(self) -> str:
        """Performance trend: IMPROVING / STABLE / DEGRADING."""
        if len(self.brier_scores) < 10:
            return "STABLE"
        old = sum(self.brier_scores[-20:-10]) / 10
        new = sum(self.brier_scores[-10:]) / 10
        if new < old - 0.005:
            return "IMPROVING"
        if new > old + 0.01:
            return "DEGRADING"
        return "STABLE"

    @property
    def sample_size(self) -> int:
        return len(self.brier_scores)


@dataclass
class DriftReport:
    """Distribution drift detection result."""
    feature_name: str
    psi_score: float         # Population Stability Index
    kl_divergence: float     # KL-divergence
    drift_detected: bool
    severity: str            # "NONE" | "WARNING" | "CRITICAL"
    description: str


@dataclass
class ModelHealthReport:
    """Health status for the entire model ensemble."""
    model_performances: dict[str, ModelPerformance] = field(default_factory=dict)
    drift_reports: list[DriftReport] = field(default_factory=list)
    current_weights: dict[str, float] = field(default_factory=dict)
    updated_weights: dict[str, float] = field(default_factory=dict)
    retired_models: list[str] = field(default_factory=list)
    retrain_recommended: bool = False
    overall_health: str = "HEALTHY"  # HEALTHY | DEGRADING | CRITICAL
    summary: str = ""


# ─── Constants ────────────────────────────────────────────────────────────────

STATE_FILE = Path("data/wbc_backend/artifacts/retrainer_state.json")
PERFORMANCE_WINDOW = 50       # games to evaluate model health
BRIER_RETIRE_THRESHOLD = 0.28  # Brier > 0.28 → retire
BRIER_WARNING_THRESHOLD = 0.26
PSI_WARNING = 0.10             # PSI > 0.10 → warning
PSI_CRITICAL = 0.25            # PSI > 0.25 → critical drift
MIN_WEIGHT = 0.02              # minimum ensemble weight
MAX_WEIGHT = 0.40              # maximum ensemble weight
WEIGHT_SMOOTHING = 0.3         # exponential smoothing factor

DEFAULT_WEIGHTS = {
    "elo": 0.15,
    "bayesian": 0.15,
    "poisson": 0.20,
    "xgboost": 0.15,
    "lightgbm": 0.15,
    "neural_net": 0.10,
    "baseline": 0.10,
}


# ─── Core: Bayesian Weight Updater ──────────────────────────────────────────

def update_weights_bayesian(
    performances: dict[str, ModelPerformance],
    current_weights: dict[str, float],
    sigma: float = 0.15,
) -> dict[str, float]:
    """
    Bayesian posterior weight update using recent prediction accuracy.

    Each model's weight is proportional to exp(-brier / (2σ²)).
    Applies exponential smoothing to avoid sudden jumps.
    """
    new_weights = {}
    log_likelihoods = {}

    for name, perf in performances.items():
        brier = perf.recent_brier
        # Log-likelihood ∝ -brier / (2σ²)
        ll = -brier / (2 * sigma ** 2)
        log_likelihoods[name] = ll

    if not log_likelihoods:
        return current_weights

    # Normalise to probabilities (softmax)
    max_ll = max(log_likelihoods.values())
    exp_lls = {k: math.exp(v - max_ll) for k, v in log_likelihoods.items()}
    total = sum(exp_lls.values())

    for name in log_likelihoods:
        raw_weight = exp_lls[name] / total
        old_weight = current_weights.get(name, 1.0 / len(log_likelihoods))
        # Exponential smoothing
        smoothed = WEIGHT_SMOOTHING * raw_weight + (1 - WEIGHT_SMOOTHING) * old_weight
        new_weights[name] = max(MIN_WEIGHT, min(MAX_WEIGHT, smoothed))

    # Renormalise
    total_w = sum(new_weights.values())
    if total_w > 0:
        new_weights = {k: v / total_w for k, v in new_weights.items()}

    return new_weights


# ─── Drift Detection ────────────────────────────────────────────────────────

def compute_psi(
    reference: list[float],
    current: list[float],
    bins: int = 10,
) -> float:
    """
    Population Stability Index (PSI) between reference and current distributions.

    PSI < 0.10 → no significant shift
    0.10–0.25  → moderate shift (warning)
    > 0.25     → significant shift (retrain needed)
    """
    if len(reference) < bins or len(current) < bins:
        return 0.0

    # Create bins from reference distribution
    ref_sorted = sorted(reference)
    bin_edges = [ref_sorted[int(i * len(ref_sorted) / bins)] for i in range(bins)]
    bin_edges.append(float("inf"))
    bin_edges[0] = float("-inf")

    def _bin_proportions(data):
        counts = [0] * bins
        for v in data:
            for b in range(bins):
                if v < bin_edges[b + 1]:
                    counts[b] += 1
                    break
        total = max(sum(counts), 1)
        return [max(c / total, 1e-6) for c in counts]

    ref_props = _bin_proportions(reference)
    cur_props = _bin_proportions(current)

    psi = sum(
        (cur_props[i] - ref_props[i]) * math.log(cur_props[i] / ref_props[i])
        for i in range(bins)
    )

    return abs(psi)


def detect_drift(
    performances: dict[str, ModelPerformance],
) -> list[DriftReport]:
    """
    Detect prediction distribution drift per model.

    Compares the first half of predictions (reference) against the
    second half (current) using PSI.
    """
    reports = []

    for name, perf in performances.items():
        preds = perf.predictions
        if len(preds) < 20:
            reports.append(DriftReport(
                feature_name=name,
                psi_score=0.0,
                kl_divergence=0.0,
                drift_detected=False,
                severity="NONE",
                description=f"{name}: insufficient data ({len(preds)} games)",
            ))
            continue

        mid = len(preds) // 2
        ref = preds[:mid]
        cur = preds[mid:]

        psi = compute_psi(ref, cur)

        # KL-divergence (binned approximation)
        kl = _kl_divergence_binned(ref, cur)

        if psi > PSI_CRITICAL:
            severity = "CRITICAL"
            drift = True
            desc = f"{name}: CRITICAL drift (PSI={psi:.3f}). Immediate retrain recommended."
        elif psi > PSI_WARNING:
            severity = "WARNING"
            drift = True
            desc = f"{name}: moderate drift (PSI={psi:.3f}). Monitor closely."
        else:
            severity = "NONE"
            drift = False
            desc = f"{name}: stable distribution (PSI={psi:.3f})."

        reports.append(DriftReport(
            feature_name=name,
            psi_score=round(psi, 4),
            kl_divergence=round(kl, 4),
            drift_detected=drift,
            severity=severity,
            description=desc,
        ))

    return reports


def _kl_divergence_binned(p_data: list[float], q_data: list[float], bins: int = 10) -> float:
    """KL(P || Q) via histogram approximation."""
    if len(p_data) < bins or len(q_data) < bins:
        return 0.0

    all_data = p_data + q_data
    min_v, max_v = min(all_data), max(all_data)
    if max_v == min_v:
        return 0.0

    def _hist(data):
        counts = [0] * bins
        for v in data:
            b = min(int((v - min_v) / (max_v - min_v + 1e-9) * bins), bins - 1)
            counts[b] += 1
        total = max(sum(counts), 1)
        return [max(c / total, 1e-6) for c in counts]

    p = _hist(p_data)
    q = _hist(q_data)

    return sum(p[i] * math.log(p[i] / q[i]) for i in range(bins))


# ─── Model Health Evaluation ────────────────────────────────────────────────

def evaluate_model_health(
    performances: dict[str, ModelPerformance],
    current_weights: dict[str, float],
) -> ModelHealthReport:
    """
    Comprehensive model health evaluation.

    Returns updated weights, retirement decisions, drift assessment,
    and overall health status.
    """
    # 1. Drift detection
    drift_reports = detect_drift(performances)

    # 2. Weight update
    updated_weights = update_weights_bayesian(performances, current_weights)

    # 3. Model retirement check
    retired = []
    for name, perf in performances.items():
        if perf.sample_size >= 20 and perf.recent_brier > BRIER_RETIRE_THRESHOLD:
            retired.append(name)
            updated_weights.pop(name, None)

    # Renormalise after retirement
    if retired and updated_weights:
        total = sum(updated_weights.values())
        updated_weights = {k: v / total for k, v in updated_weights.items()}

    # 4. Overall health
    critical_drifts = sum(1 for d in drift_reports if d.severity == "CRITICAL")
    degrading = sum(1 for p in performances.values() if p.trend == "DEGRADING")
    retrain = critical_drifts > 0 or len(retired) > 0

    if critical_drifts >= 2 or len(retired) >= 2:
        health = "CRITICAL"
    elif critical_drifts >= 1 or degrading >= 2:
        health = "DEGRADING"
    else:
        health = "HEALTHY"

    # Summary
    parts = [
        f"Health: {health}",
        f"Drift alerts: {critical_drifts} critical",
        f"Retired: {retired or 'none'}",
        f"Retrain: {'YES' if retrain else 'no'}",
    ]

    return ModelHealthReport(
        model_performances=performances,
        drift_reports=drift_reports,
        current_weights=current_weights,
        updated_weights=updated_weights,
        retired_models=retired,
        retrain_recommended=retrain,
        overall_health=health,
        summary=" | ".join(parts),
    )


# ─── Game Result Ingestion ───────────────────────────────────────────────────

def ingest_game_result(
    result: GameResult,
    predictions: dict[str, float],
    performances: dict[str, ModelPerformance],
) -> dict[str, ModelPerformance]:
    """
    Process a completed game: record each model's Brier & log-loss.

    Parameters
    ----------
    result : observed game outcome
    predictions : {model_name: predicted_home_win_prob}
    performances : current tracking state (modified in place)
    """
    actual = 1 if result.home_win else 0
    ts = result.timestamp or time.time()

    for model_name, pred in predictions.items():
        if model_name not in performances:
            performances[model_name] = ModelPerformance(model_name=model_name)

        perf = performances[model_name]
        perf.predictions.append(pred)
        perf.actuals.append(actual)
        perf.timestamps.append(ts)

        # Brier score
        brier = (pred - actual) ** 2
        perf.brier_scores.append(brier)

        # Log loss
        p = max(min(pred, 0.999), 0.001)
        ll = -(actual * math.log(p) + (1 - actual) * math.log(1 - p))
        perf.log_losses.append(ll)

    return performances


# ─── Persistence ─────────────────────────────────────────────────────────────

def save_state(
    performances: dict[str, ModelPerformance],
    weights: dict[str, float],
):
    """Persist retrainer state to JSON."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "weights": weights,
        "performances": {},
        "last_updated": time.time(),
    }
    for name, perf in performances.items():
        data["performances"][name] = {
            "brier_scores": perf.brier_scores[-100:],
            "log_losses": perf.log_losses[-100:],
            "predictions": perf.predictions[-100:],
            "actuals": perf.actuals[-100:],
        }
    STATE_FILE.write_text(json.dumps(data, indent=2))


def load_state() -> tuple[dict[str, ModelPerformance], dict[str, float]]:
    """Load persisted retrainer state."""
    if not STATE_FILE.exists():
        return {}, dict(DEFAULT_WEIGHTS)

    data = json.loads(STATE_FILE.read_text())
    weights = data.get("weights", dict(DEFAULT_WEIGHTS))

    performances: dict[str, ModelPerformance] = {}
    for name, pdata in data.get("performances", {}).items():
        perf = ModelPerformance(model_name=name)
        perf.brier_scores = pdata.get("brier_scores", [])
        perf.log_losses = pdata.get("log_losses", [])
        perf.predictions = pdata.get("predictions", [])
        perf.actuals = pdata.get("actuals", [])
        performances[name] = perf

    return performances, weights


# ─── Full Retraining Pipeline ────────────────────────────────────────────────

def run_retraining_cycle(
    new_results: list[GameResult],
    all_predictions: list[dict[str, float]],
) -> ModelHealthReport:
    """
    Complete retraining cycle: ingest results → update weights → check health.

    Parameters
    ----------
    new_results : list of completed game outcomes
    all_predictions : parallel list of {model_name: predicted_home_wp}

    Returns
    -------
    ModelHealthReport with updated weights and health assessment
    """
    performances, current_weights = load_state()

    # Ingest each game
    for result, preds in zip(new_results, all_predictions):
        performances = ingest_game_result(result, preds, performances)

    # Evaluate health
    report = evaluate_model_health(performances, current_weights)

    # Persist
    save_state(performances, report.updated_weights)

    return report
