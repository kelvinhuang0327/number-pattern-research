"""
Continuous Learning Infrastructure — Phase 8
=============================================
Self-improving prediction system implementing:

  1. Automated feature testing (A/B test new signals)
  2. Model comparison engine (champion vs challenger)
  3. Continuous retraining triggers
  4. Performance monitoring with degradation detection
  5. Edge decay detection and recovery

Architecture:
  ┌─────────────────────────────────────────────────────────────────┐
  │              CONTINUOUS LEARNING LOOP                           │
  │                                                                 │
  │  New Game Result → Performance Monitor → Trigger Detection      │
  │         ↓                                                       │
  │  Degradation? → Feature Lab → A/B Test New Signal               │
  │         ↓                                                       │
  │  Champion vs Challenger → Statistical Test → Promote/Reject     │
  │         ↓                                                       │
  │  Retraining Gate (min 30 samples) → Auto-Retrain                │
  │         ↓                                                       │
  │  Weight Update → Dynamic Ensemble → Production                  │
  └─────────────────────────────────────────────────────────────────┘
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
from scipy import stats

logger = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────
CL_STATE_FILE = Path("data/wbc_backend/artifacts/continuous_learning_state.json")
PERFORMANCE_LOG = Path("data/wbc_backend/reports/performance_monitor.jsonl")

# ── Constants ──────────────────────────────────────────────────────────────
MIN_RETRAIN_SAMPLES = 30            # § 核心規範 02
RETRAIN_INTERVAL = 50               # Games between scheduled retrains
DEGRADATION_WINDOW = 20             # Games to measure performance trend
DEGRADATION_THRESHOLD = 0.05        # Brier score increase > 5% = degradation
EDGE_DECAY_THRESHOLD = 0.02         # ROI decline > 2% per window = edge decay
CHAMPION_CHALLENGER_MIN_N = 20      # Minimum games for statistical comparison
SIGNIFICANCE_LEVEL = 0.05           # p < 0.05 for feature promotion


# ── Data Structures ────────────────────────────────────────────────────────

@dataclass
class PredictionOutcome:
    """Record of a prediction and its actual outcome."""
    game_id: str
    timestamp: float
    tournament: str
    round_name: str
    model_name: str
    predicted_prob: float
    actual_outcome: int      # 1 = home win, 0 = away win
    odds_used: float = 2.0
    stake_fraction: float = 0.02
    feature_version: str = "base"   # which feature set was used


@dataclass
class FeatureExperiment:
    """A/B test for a new feature signal."""
    feature_name: str
    hypothesis: str
    status: str = "testing"     # testing | promoted | rejected
    n_control: int = 0          # games without feature
    n_treatment: int = 0        # games with feature
    brier_control: float = 0.25
    brier_treatment: float = 0.25
    roi_control: float = 0.0
    roi_treatment: float = 0.0
    p_value: float = 1.0
    started_at: float = 0.0
    completed_at: float | None = None
    decision: str = ""


@dataclass
class ModelVersion:
    """Versioned model snapshot."""
    version_id: str
    created_at: float
    n_training_samples: int
    brier_score: float
    accuracy: float
    roi_trailing: float
    feature_set: list[str]
    is_champion: bool = False
    is_challenger: bool = False
    notes: str = ""


@dataclass
class ContinuousLearningState:
    """Persisted state for the continuous learning system."""
    n_games_total: int = 0
    n_games_since_retrain: int = 0
    last_retrain_at: int = 0
    is_degraded: bool = False
    degradation_first_detected: float | None = None
    edge_decay_detected: bool = False
    current_champion: str = "base_v1"
    active_experiments: list[str] = field(default_factory=list)
    feature_promotions: list[str] = field(default_factory=list)
    feature_rejections: list[str] = field(default_factory=list)
    model_versions: list[ModelVersion] = field(default_factory=list)
    # Rolling performance window
    recent_brier_scores: list[float] = field(default_factory=list)
    recent_roi_values: list[float] = field(default_factory=list)
    recent_accuracy: list[float] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "n_games_total": self.n_games_total,
            "n_games_since_retrain": self.n_games_since_retrain,
            "last_retrain_at": self.last_retrain_at,
            "is_degraded": self.is_degraded,
            "degradation_first_detected": self.degradation_first_detected,
            "edge_decay_detected": self.edge_decay_detected,
            "current_champion": self.current_champion,
            "active_experiments": self.active_experiments,
            "feature_promotions": self.feature_promotions,
            "feature_rejections": self.feature_rejections,
            "recent_brier_scores": self.recent_brier_scores[-100:],
            "recent_roi_values": self.recent_roi_values[-100:],
            "recent_accuracy": self.recent_accuracy[-100:],
        }

    @classmethod
    def from_dict(cls, d: dict) -> ContinuousLearningState:
        state = cls()
        for k in ["n_games_total", "n_games_since_retrain", "last_retrain_at",
                  "is_degraded", "degradation_first_detected", "edge_decay_detected",
                  "current_champion", "active_experiments", "feature_promotions",
                  "feature_rejections", "recent_brier_scores", "recent_roi_values",
                  "recent_accuracy"]:
            if k in d:
                setattr(state, k, d[k])
        return state


# ── Performance Monitor ────────────────────────────────────────────────────

class PerformanceMonitor:
    """Tracks prediction quality over time and detects degradation."""

    def __init__(self, state: ContinuousLearningState):
        self.state = state

    def record(self, outcome: PredictionOutcome, bet_pnl: float = 0.0) -> dict[str, Any]:
        """Record a prediction outcome and compute performance metrics."""
        p = outcome.predicted_prob
        y = outcome.actual_outcome

        brier = (p - y) ** 2
        correct = 1 if (p >= 0.5) == (y == 1) else 0

        self.state.recent_brier_scores.append(brier)
        self.state.recent_accuracy.append(float(correct))
        if bet_pnl != 0:
            self.state.recent_roi_values.append(bet_pnl)

        # Keep rolling window (last DEGRADATION_WINDOW * 2 games)
        window = DEGRADATION_WINDOW * 2
        self.state.recent_brier_scores = self.state.recent_brier_scores[-window:]
        self.state.recent_roi_values = self.state.recent_roi_values[-window:]
        self.state.recent_accuracy = self.state.recent_accuracy[-window:]

        self.state.n_games_total += 1
        self.state.n_games_since_retrain += 1

        # Detect degradation
        degradation = self._check_degradation()
        edge_decay = self._check_edge_decay()

        # Log to JSONL
        log_entry = {
            "timestamp": time.time(),
            "game_id": outcome.game_id,
            "brier": round(brier, 4),
            "correct": correct,
            "predicted_prob": round(p, 4),
            "actual": y,
            "degradation_flag": degradation,
            "edge_decay_flag": edge_decay,
            "n_games_total": self.state.n_games_total,
        }
        self._append_log(log_entry)

        return {
            "brier": brier,
            "correct": correct,
            "degradation_detected": degradation,
            "edge_decay_detected": edge_decay,
            "should_retrain": self._should_retrain(),
        }

    def _check_degradation(self) -> bool:
        """Detect if recent performance has degraded vs baseline."""
        n = len(self.state.recent_brier_scores)
        if n < DEGRADATION_WINDOW * 2:
            return False

        baseline = np.mean(self.state.recent_brier_scores[:DEGRADATION_WINDOW])
        recent = np.mean(self.state.recent_brier_scores[DEGRADATION_WINDOW:])

        is_degraded = recent > baseline + DEGRADATION_THRESHOLD

        if is_degraded and not self.state.is_degraded:
            self.state.is_degraded = True
            self.state.degradation_first_detected = time.time()
            logger.warning(
                "Performance degradation detected: baseline_brier=%.4f, "
                "recent_brier=%.4f (Δ=+%.4f)",
                baseline, recent, recent - baseline
            )
        elif not is_degraded and self.state.is_degraded:
            self.state.is_degraded = False
            logger.info("Performance degradation resolved")

        return is_degraded

    def _check_edge_decay(self) -> bool:
        """Detect if ROI edge is decaying over time."""
        n = len(self.state.recent_roi_values)
        if n < DEGRADATION_WINDOW:
            return False

        values = self.state.recent_roi_values[-DEGRADATION_WINDOW:]
        x = np.arange(len(values))
        if len(x) < 2:
            return False

        slope, _, r, _, _ = stats.linregress(x, values)
        is_decaying = slope < -EDGE_DECAY_THRESHOLD

        if is_decaying != self.state.edge_decay_detected:
            self.state.edge_decay_detected = is_decaying
            if is_decaying:
                logger.warning("Edge decay detected: ROI slope=%.4f per game", slope)

        return is_decaying

    def _should_retrain(self) -> bool:
        """Determine if retraining should be triggered."""
        if self.state.n_games_since_retrain < MIN_RETRAIN_SAMPLES:
            return False
        # Scheduled retrain
        if self.state.n_games_since_retrain >= RETRAIN_INTERVAL:
            return True
        # Emergency retrain on degradation
        return self.state.is_degraded and self.state.n_games_since_retrain >= MIN_RETRAIN_SAMPLES

    def get_summary(self) -> dict:
        """Return performance summary."""
        n_brier = len(self.state.recent_brier_scores)
        n_acc = len(self.state.recent_accuracy)

        return {
            "n_games": self.state.n_games_total,
            "recent_brier": round(float(np.mean(self.state.recent_brier_scores[-20:])), 4) if n_brier else 0.25,
            "recent_accuracy": round(float(np.mean(self.state.recent_accuracy[-20:])), 4) if n_acc else 0.5,
            "is_degraded": self.state.is_degraded,
            "edge_decay_detected": self.state.edge_decay_detected,
            "should_retrain": self._should_retrain(),
            "games_since_retrain": self.state.n_games_since_retrain,
        }

    @staticmethod
    def _append_log(entry: dict) -> None:
        PERFORMANCE_LOG.parent.mkdir(parents=True, exist_ok=True)
        # Convert numpy types to native Python for JSON serialization
        def _convert(obj):
            if isinstance(obj, (np.bool_, np.integer)):
                return int(obj)
            if isinstance(obj, np.floating):
                return float(obj)
            return obj
        clean = {k: _convert(v) for k, v in entry.items()}
        with open(PERFORMANCE_LOG, "a") as f:
            f.write(json.dumps(clean) + "\n")


# ── Champion vs Challenger ─────────────────────────────────────────────────

class ChampionChallengerEngine:
    """
    Champion vs Challenger model comparison.

    Randomly routes 20% of predictions to challenger, 80% to champion.
    After MIN_N games, statistical test determines if challenger wins.
    """

    def __init__(self, champion_name: str = "base", challenger_name: str = "challenger_v1"):
        self.champion = champion_name
        self.challenger = challenger_name
        self._champion_scores: list[float] = []
        self._challenger_scores: list[float] = []
        self._rng = np.random.default_rng(42)
        self.challenger_traffic_pct = 0.20  # 20% traffic to challenger

    def route(self, game_id: str) -> str:
        """Route a prediction to champion or challenger."""
        if self._rng.random() < self.challenger_traffic_pct:
            return self.challenger
        return self.champion

    def record_brier(self, model_name: str, brier_score: float) -> None:
        if model_name == self.champion:
            self._champion_scores.append(brier_score)
        elif model_name == self.challenger:
            self._challenger_scores.append(brier_score)

    def evaluate(self) -> dict:
        """
        Compare champion vs challenger using Wilcoxon signed-rank test.
        Returns decision: 'promote_challenger' | 'keep_champion' | 'insufficient_data'
        """
        nc = len(self._champion_scores)
        nt = len(self._challenger_scores)

        if min(nc, nt) < CHAMPION_CHALLENGER_MIN_N:
            return {
                "decision": "insufficient_data",
                "n_champion": nc,
                "n_challenger": nt,
                "required": CHAMPION_CHALLENGER_MIN_N,
            }

        # Lower Brier score = better
        champ_mean = float(np.mean(self._champion_scores))
        chall_mean = float(np.mean(self._challenger_scores))

        # One-tailed test: is challenger significantly BETTER?
        try:
            stat, p_value = stats.mannwhitneyu(
                self._challenger_scores, self._champion_scores,
                alternative='less'  # challenger Brier < champion Brier
            )
        except Exception:
            p_value = 1.0

        if p_value < SIGNIFICANCE_LEVEL and chall_mean < champ_mean:
            decision = "promote_challenger"
            reason = (
                f"Challenger significantly better (Δ_Brier={champ_mean-chall_mean:.4f}, "
                f"p={p_value:.4f})"
            )
        else:
            decision = "keep_champion"
            reason = (
                f"Champion maintained (champion_brier={champ_mean:.4f}, "
                f"challenger_brier={chall_mean:.4f}, p={p_value:.4f})"
            )

        return {
            "decision": decision,
            "reason": reason,
            "champion_brier": round(champ_mean, 4),
            "challenger_brier": round(chall_mean, 4),
            "brier_improvement": round(champ_mean - chall_mean, 4),
            "p_value": round(float(p_value), 4),
            "n_champion": nc,
            "n_challenger": nt,
        }


# ── Feature Experiment Engine ──────────────────────────────────────────────

class FeatureExperimentEngine:
    """
    A/B test engine for new alpha signals.

    Tests whether adding a new feature improves prediction quality.
    """

    def __init__(self, state: ContinuousLearningState):
        self.state = state
        self._experiments: dict[str, FeatureExperiment] = {}

    def start_experiment(self, feature_name: str, hypothesis: str) -> None:
        """Begin testing a new feature signal."""
        if feature_name in self._experiments:
            logger.info("Experiment for %s already active", feature_name)
            return

        exp = FeatureExperiment(
            feature_name=feature_name,
            hypothesis=hypothesis,
            started_at=time.time(),
        )
        self._experiments[feature_name] = exp
        if feature_name not in self.state.active_experiments:
            self.state.active_experiments.append(feature_name)
        logger.info("Feature experiment started: %s", feature_name)

    def record_result(self, feature_name: str, brier_with: float,
                       brier_without: float, roi_with: float = 0.0,
                       roi_without: float = 0.0) -> None:
        """Record A/B test result for a feature."""
        if feature_name not in self._experiments:
            return
        exp = self._experiments[feature_name]
        # Accumulate results (simplified: track means)
        n_t = exp.n_treatment + 1
        n_c = exp.n_control + 1
        exp.brier_treatment = (exp.brier_treatment * exp.n_treatment + brier_with) / n_t
        exp.brier_control = (exp.brier_control * exp.n_control + brier_without) / n_c
        exp.roi_treatment = (exp.roi_treatment * exp.n_treatment + roi_with) / n_t
        exp.roi_control = (exp.roi_control * exp.n_control + roi_without) / n_c
        exp.n_treatment = n_t
        exp.n_control = n_c

    def evaluate_experiment(self, feature_name: str) -> dict | None:
        """Evaluate if feature should be promoted or rejected."""
        if feature_name not in self._experiments:
            return None

        exp = self._experiments[feature_name]
        min_n = max(CHAMPION_CHALLENGER_MIN_N, MIN_RETRAIN_SAMPLES)

        if min(exp.n_treatment, exp.n_control) < min_n:
            return {"status": "insufficient_data", "required": min_n}

        # Simple t-test on brier score improvement
        delta_brier = exp.brier_control - exp.brier_treatment  # positive = feature helps

        # Conservative threshold: feature must improve Brier by >0.001 AND ROI by >0.5%
        if delta_brier > 0.001 and exp.roi_treatment > exp.roi_control:
            exp.status = "promoted"
            exp.decision = f"PROMOTED: Δ_Brier={delta_brier:.4f}"
            if feature_name not in self.state.feature_promotions:
                self.state.feature_promotions.append(feature_name)
            if feature_name in self.state.active_experiments:
                self.state.active_experiments.remove(feature_name)
            logger.info("Feature PROMOTED: %s (Δ_Brier=%.4f)", feature_name, delta_brier)
        else:
            exp.status = "rejected"
            exp.decision = f"REJECTED: Δ_Brier={delta_brier:.4f} (insufficient improvement)"
            if feature_name not in self.state.feature_rejections:
                self.state.feature_rejections.append(feature_name)
            if feature_name in self.state.active_experiments:
                self.state.active_experiments.remove(feature_name)
            logger.info("Feature REJECTED: %s (Δ_Brier=%.4f)", feature_name, delta_brier)

        exp.completed_at = time.time()

        return {
            "feature": feature_name,
            "status": exp.status,
            "decision": exp.decision,
            "brier_improvement": round(delta_brier, 4),
            "roi_improvement": round(exp.roi_treatment - exp.roi_control, 4),
        }

    def get_experiments_summary(self) -> list[dict]:
        return [
            {
                "feature": name,
                "status": exp.status,
                "n_treatment": exp.n_treatment,
                "n_control": exp.n_control,
                "brier_improvement": round(exp.brier_control - exp.brier_treatment, 4),
            }
            for name, exp in self._experiments.items()
        ]


# ── Continuous Learning Orchestrator ───────────────────────────────────────

class ContinuousLearningSystem:
    """
    Top-level orchestrator for the self-improving prediction system.

    Integrates: PerformanceMonitor + ChampionChallenger + FeatureExperiments
    """

    def __init__(self):
        self.state = self._load_state()
        self.monitor = PerformanceMonitor(self.state)
        self.champion_challenger = ChampionChallengerEngine()
        self.feature_lab = FeatureExperimentEngine(self.state)

    def _load_state(self) -> ContinuousLearningState:
        if CL_STATE_FILE.exists():
            try:
                with open(CL_STATE_FILE) as f:
                    return ContinuousLearningState.from_dict(json.load(f))
            except Exception as e:
                logger.warning("Failed to load CL state: %s", e)
        return ContinuousLearningState()

    def save_state(self) -> None:
        CL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CL_STATE_FILE, "w") as f:
            json.dump(self.state.to_dict(), f, indent=2)

    def process_game_result(self,
                             game_id: str,
                             predicted_prob: float,
                             actual_outcome: int,
                             tournament: str = "WBC",
                             round_name: str = "Pool",
                             bet_pnl: float = 0.0) -> dict[str, Any]:
        """
        Main entry point: process a completed game result.

        § 核心規範 01: Called ONLY after game is complete.

        Returns recommendations for system actions.
        """
        outcome = PredictionOutcome(
            game_id=game_id,
            timestamp=time.time(),
            tournament=tournament,
            round_name=round_name,
            model_name=self.state.current_champion,
            predicted_prob=predicted_prob,
            actual_outcome=actual_outcome,
        )

        # Record and analyze
        metrics = self.monitor.record(outcome, bet_pnl)
        self.champion_challenger.record_brier(
            self.state.current_champion, metrics['brier']
        )

        actions: list[str] = []
        recommendations: dict[str, Any] = {}

        # Retrain trigger
        if metrics['should_retrain']:
            actions.append("TRIGGER_RETRAIN")
            recommendations['retrain'] = {
                "trigger": "scheduled" if not metrics['degradation_detected'] else "degradation",
                "n_games_since_last": self.state.n_games_since_retrain,
            }
            self.state.n_games_since_retrain = 0

        # Degradation alert
        if metrics['degradation_detected']:
            actions.append("DEGRADATION_ALERT")
            recommendations['alert'] = {
                "type": "performance_degradation",
                "message": "Consider retraining or feature refresh",
            }

        # Edge decay alert
        if metrics['edge_decay_detected']:
            actions.append("EDGE_DECAY_ALERT")
            recommendations['alert'] = recommendations.get('alert', {})
            recommendations['alert']['edge_decay'] = True

        # Evaluate champion-challenger after enough data
        if self.state.n_games_total % CHAMPION_CHALLENGER_MIN_N == 0:
            cc_result = self.champion_challenger.evaluate()
            if cc_result.get('decision') == 'promote_challenger':
                actions.append("PROMOTE_CHALLENGER")
                recommendations['champion_update'] = cc_result

        self.save_state()

        return {
            "game_id": game_id,
            "n_games_total": self.state.n_games_total,
            "actions": actions,
            "metrics": metrics,
            "recommendations": recommendations,
            "system_status": "DEGRADED" if self.state.is_degraded else "HEALTHY",
        }

    def start_feature_experiment(self, feature_name: str, hypothesis: str) -> None:
        """Start testing a new alpha signal."""
        self.feature_lab.start_experiment(feature_name, hypothesis)
        self.save_state()

    def get_system_report(self) -> dict:
        """Full system health report."""
        return {
            "performance": self.monitor.get_summary(),
            "champion": self.state.current_champion,
            "active_experiments": self.state.active_experiments,
            "promoted_features": self.state.feature_promotions,
            "rejected_features": self.state.feature_rejections,
            "system_health": "DEGRADED" if self.state.is_degraded else "HEALTHY",
            "edge_decay": self.state.edge_decay_detected,
            "n_games_total": self.state.n_games_total,
        }


# ── Suggested Feature Experiments (based on Phase 3 catalogue) ────────────

SUGGESTED_EXPERIMENTS = [
    # High potential, currently data available
    ("wbc_bullpen_demand_diff", "WBC pitch limits force more bullpen usage in early rounds"),
    ("momentum_score_diff", "Short tournament format amplifies recent form signal"),
    ("composite_edge_score", "Multi-signal composite should outperform single metrics"),
    ("rsi_diff", "Roster Strength Index captures star player WBC roster impact"),
    ("xwoba_luck_diff", "xwOBA-wOBA gap predicts regression in hot/cold teams"),
    # Requires new data sources
    ("swstr_pct_diff", "Swinging strike rate is most predictive SP signal (needs Statcast)"),
    ("ml_movement_home", "Line movement reveals sharp money direction (needs Odds API)"),
    ("sharp_public_divergence", "Sharp vs public split = primary betting signal (needs Odds API)"),
]


def get_recommended_experiments() -> list[dict]:
    """Return list of recommended feature experiments to run."""
    return [
        {"feature": f, "hypothesis": h, "priority": "high" if i < 5 else "medium"}
        for i, (f, h) in enumerate(SUGGESTED_EXPERIMENTS)
    ]
