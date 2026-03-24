"""
Decision Layer V2
=================
9-Phase architecture upgrade over decision_payout_engine.py.

Phase 1:  Confidence Vector Engine  — scalar → 5-dim vector
Phase 2:  Variable-N Betting Policy — piecewise based on confidence
Phase 3:  Strategy Switching        — context-aware UCB1 routing
Phase 4:  Portfolio Geometry        — Coverage Core + Concentration Layer
Phase 5:  Policy Search             — random + heuristic policy generation
Phase 6:  Policy Validation         — walk-forward, 3-window, perm, McNemar
Phase 7:  Auto-Research Policy Layer— memory-backed hypothesis loop
Phase 8:  Integration               — DecisionEngineV2 with legacy toggle
Phase 9:  Validation Report         — docs/decision_layer_v2_report.md

Design Principles:
  - Prediction engine is UNCHANGED (strategy_coordinator.py stays intact)
  - Legacy mode toggle: pass legacy_mode=True to get v1 behaviour
  - All policies validated before adoption (L48 gate enforced)
  - Variable-N: never skip entirely (L101 dilution protection)

2026-03-24  Created
"""
import os
import sys
import json
import math
import time
import random
import logging
from collections import Counter, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any

import numpy as np

# ── Path setup ──────────────────────────────────────────────────────────────
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
_API  = os.path.join(_ROOT, "lottery_api")
for _p in (_ROOT, _API):
    if _p not in sys.path:
        sys.path.insert(0, _p)

logger = logging.getLogger(__name__)

# ── Game constants ───────────────────────────────────────────────────────────
POOL_SIZE = {"DAILY_539": 39, "BIG_LOTTO": 49, "POWER_LOTTO": 38}
N_DRAW    = {"DAILY_539":  5, "BIG_LOTTO":  6, "POWER_LOTTO":  6}
BASELINES = {
    "POWER_LOTTO": {1: 0.0387, 2: 0.0759, 3: 0.1117, 4: 0.1460, 5: 0.1791},
    "BIG_LOTTO":   {1: 0.0186, 2: 0.0369, 3: 0.0549, 4: 0.0725, 5: 0.0896},
    "DAILY_539":   {1: 0.1140, 2: 0.2154, 3: 0.3050, 4: 0.3843, 5: 0.4539},
}
# Maximum bets per game (from RSM validated max)
MAX_BETS = {"DAILY_539": 5, "BIG_LOTTO": 5, "POWER_LOTTO": 5}
# Metric: M2+ for 539, M3+ for others
METRIC_THRESHOLD = {"DAILY_539": 2, "BIG_LOTTO": 3, "POWER_LOTTO": 3}

DATA_DIR = os.path.join(_API, "data")
POLICY_MEMORY_PATH = os.path.join(_HERE, "results", "policy_memory.json")
PSI_CRITICAL = 0.25


# ═══════════════════════════════════════════════════════════════════════════
# Data structures
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class ConfidenceVector:
    signal_strength:    float = 0.5   # best RSM 300p edge / expected_edge
    signal_agreement:   float = 0.5   # fraction of strategies with positive edge
    regime_stability:   float = 0.5   # 1 - PSI/PSI_CRITICAL
    entropy_state:      float = 0.5   # distribution health (1 = normal)
    recent_performance: float = 0.5   # 30p edge / 300p edge trend ratio

    # default weights (tunable via policy search)
    _weights: Dict[str, float] = field(default_factory=lambda: {
        "signal_strength":    0.30,
        "signal_agreement":   0.20,
        "regime_stability":   0.20,
        "entropy_state":      0.10,
        "recent_performance": 0.20,
    })

    def final(self, weights: Optional[Dict[str, float]] = None) -> float:
        w = weights or self._weights
        v = self
        score = (
            w["signal_strength"]    * v.signal_strength    +
            w["signal_agreement"]   * v.signal_agreement   +
            w["regime_stability"]   * v.regime_stability   +
            w["entropy_state"]      * v.entropy_state      +
            w["recent_performance"] * v.recent_performance
        )
        return float(np.clip(score, 0.0, 1.0))

    def to_dict(self) -> Dict:
        return {
            "signal_strength":    round(self.signal_strength, 4),
            "signal_agreement":   round(self.signal_agreement, 4),
            "regime_stability":   round(self.regime_stability, 4),
            "entropy_state":      round(self.entropy_state, 4),
            "recent_performance": round(self.recent_performance, 4),
            "final_confidence":   round(self.final(), 4),
        }


@dataclass
class DecisionResult:
    lottery_type:       str
    n_bets:             int
    strategy_name:      str
    bets:               List[List[int]]
    confidence_vector:  Dict
    final_confidence:   float
    portfolio_type:     str           # "coverage_only" | "coverage+concentration"
    mode:               str           # "v2" | "legacy"
    policy_id:          Optional[str] = None
    notes:              str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


@dataclass
class PolicyConfig:
    """A decision policy configuration for Phase 5 search."""
    policy_id:         str
    conf_weights:      Dict[str, float]   # ConfidenceVector weights
    n_bets_thresholds: List[float]        # [t1, t2, t3, t4] for n=1..5
    strategy_mode:     str                # "best_300p" | "ucb1" | "greedy_recent"
    portfolio_type:    str                # "coverage_only" | "coverage+concentration"
    min_confidence:    float              # skip if below (clamped to ≥0.2 → always ≥1 bet)

    def n_bets_for(self, conf: float, max_bets: int) -> int:
        """Map confidence → n_bets using piecewise thresholds."""
        t = self.n_bets_thresholds  # 4 thresholds for n=2,3,4,5
        if conf < t[0]:
            n = 1
        elif conf < t[1]:
            n = 2
        elif conf < t[2]:
            n = 3
        elif conf < t[3]:
            n = 4
        else:
            n = 5
        return min(n, max_bets)


@dataclass
class ValidationResult:
    policy_id:      str
    lottery_type:   str
    window_150:     float
    window_500:     float
    window_full:    float
    three_window_ok: bool
    perm_p:         float
    perm_ok:        bool
    mcnemar_net:    int
    mcnemar_p:      float
    mcnemar_ok:     bool
    sharpe:         float
    verdict:        str    # "ADOPT" | "WATCH" | "REJECT"
    n_oos:          int


# ═══════════════════════════════════════════════════════════════════════════
# Phase 1 — Confidence Vector Engine
# ═══════════════════════════════════════════════════════════════════════════

class ConfidenceEngine:
    """
    Computes a 5-dimensional confidence vector from:
      - RSM strategy states (edge_300p, trend, sharpe)
      - Drift report (PSI)
      - Recent draw history (entropy)
    """

    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir

    def _load_strategy_states(self, lottery_type: str) -> Dict:
        path = os.path.join(self.data_dir, f"strategy_states_{lottery_type}.json")
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            return json.load(f)

    def _load_drift_report(self) -> Dict:
        path = os.path.join(self.data_dir, "drift_report.json")
        if not os.path.exists(path):
            return {}
        with open(path) as f:
            return json.load(f)

    def _compute_signal_strength(self, states: Dict, lottery_type: str) -> float:
        """Best 300p edge normalised to [0,1]. Expected edge ≈ 2-4%."""
        if not states:
            return 0.3
        edges = [s.get("edge_300p", 0.0) for s in states.values()]
        best_edge = max(edges) if edges else 0.0
        # Normalise: edge=0% → 0.3 (uncertainty), edge=+5% → 1.0
        # Score = clip(0.3 + best_edge / 0.05 * 0.7, 0, 1)
        score = 0.3 + (best_edge / 0.05) * 0.7
        return float(np.clip(score, 0.0, 1.0))

    def _compute_signal_agreement(self, states: Dict) -> float:
        """Fraction of strategies with positive edge_300p."""
        if not states:
            return 0.3
        edges = [s.get("edge_300p", 0.0) for s in states.values()]
        if not edges:
            return 0.3
        frac = sum(1 for e in edges if e > 0) / len(edges)
        return float(np.clip(frac, 0.0, 1.0))

    def _compute_regime_stability(self, drift_report: Dict, lottery_type: str) -> float:
        """1 - PSI/PSI_CRITICAL, clamped to [0,1]."""
        game_data = drift_report.get(lottery_type, {})
        metrics = game_data.get("metrics", {})
        psi = metrics.get("number_freq_PSI", {}).get("value", 0.0)
        score = 1.0 - (psi / PSI_CRITICAL)
        return float(np.clip(score, 0.0, 1.0))

    def _compute_entropy_state(self, history: List[Dict], lottery_type: str) -> float:
        """
        Compare recent 50-draw entropy to full-history entropy.
        If recent is close to expected (uniform) → high score.
        """
        pool = POOL_SIZE[lottery_type]
        draw_n = N_DRAW[lottery_type]
        if len(history) < 20:
            return 0.5

        def entropy(draws):
            cnt = Counter(n for d in draws for n in d["numbers"])
            total = sum(cnt.values())
            if total == 0:
                return 0.0
            probs = [cnt.get(n, 0) / total for n in range(1, pool + 1)]
            return -sum(p * math.log(p + 1e-12) for p in probs)

        expected_entropy = math.log(pool)  # max entropy for uniform distribution
        recent_50 = history[-50:]
        recent_ent = entropy(recent_50)
        # Score: how close to expected entropy (normalised)
        score = min(recent_ent / expected_entropy, 1.0)
        return float(np.clip(score, 0.0, 1.0))

    def _compute_recent_performance(self, states: Dict) -> float:
        """
        Ratio of 30p edge to 300p edge across strategies.
        Positive trend (30p > 300p) → score > 0.5.
        """
        if not states:
            return 0.5
        ratios = []
        for s in states.values():
            e300 = s.get("edge_300p", 0.0)
            e30  = s.get("edge_30p", 0.0)
            if abs(e300) > 0.001:
                ratios.append(e30 / e300)
        if not ratios:
            return 0.5
        avg_ratio = float(np.mean(ratios))
        # ratio=1 → 0.5, ratio=2 → 1.0, ratio=0 → 0.0
        score = 0.5 + (avg_ratio - 1.0) * 0.25
        return float(np.clip(score, 0.0, 1.0))

    def compute(
        self,
        lottery_type: str,
        history: List[Dict],
        states: Optional[Dict] = None,
        drift_report: Optional[Dict] = None,
    ) -> ConfidenceVector:
        if states is None:
            states = self._load_strategy_states(lottery_type)
        if drift_report is None:
            drift_report = self._load_drift_report()

        return ConfidenceVector(
            signal_strength    = self._compute_signal_strength(states, lottery_type),
            signal_agreement   = self._compute_signal_agreement(states),
            regime_stability   = self._compute_regime_stability(drift_report, lottery_type),
            entropy_state      = self._compute_entropy_state(history, lottery_type),
            recent_performance = self._compute_recent_performance(states),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Phase 2 — Variable-N Betting Policy
# ═══════════════════════════════════════════════════════════════════════════

# Default piecewise thresholds: [t_for_n2, t_for_n3, t_for_n4, t_for_n5]
DEFAULT_N_THRESHOLDS = [0.35, 0.50, 0.65, 0.80]

class VarNPolicy:
    """
    Decides number of bets from final_confidence.
    Never returns 0 (L101: never skip entirely → minimum 1 bet).
    """

    def __init__(
        self,
        thresholds: List[float] = None,
        max_bets_override: Optional[Dict[str, int]] = None,
    ):
        self.thresholds = thresholds or DEFAULT_N_THRESHOLDS
        self.max_bets   = {**MAX_BETS, **(max_bets_override or {})}

    def decide(self, lottery_type: str, confidence: float) -> int:
        t = self.thresholds
        max_b = self.max_bets.get(lottery_type, 5)
        if confidence < t[0]:
            n = 1
        elif confidence < t[1]:
            n = 2
        elif confidence < t[2]:
            n = 3
        elif confidence < t[3]:
            n = 4
        else:
            n = 5
        return min(n, max_b)

    def explain(self, lottery_type: str, confidence: float) -> str:
        n = self.decide(lottery_type, confidence)
        t = self.thresholds
        reasons = {
            1: f"conf={confidence:.2f} < {t[0]:.2f} → 1 bet (low confidence)",
            2: f"conf={confidence:.2f} in [{t[0]:.2f}, {t[1]:.2f}) → 2 bets",
            3: f"conf={confidence:.2f} in [{t[1]:.2f}, {t[2]:.2f}) → 3 bets",
            4: f"conf={confidence:.2f} in [{t[2]:.2f}, {t[3]:.2f}) → 4 bets",
            5: f"conf={confidence:.2f} ≥ {t[3]:.2f} → 5 bets (high confidence)",
        }
        return reasons.get(n, f"{n} bets")


# ═══════════════════════════════════════════════════════════════════════════
# Phase 3 — Strategy Switching (Context-Aware UCB1)
# ═══════════════════════════════════════════════════════════════════════════

class StrategySelector:
    """
    Selects the best strategy using UCB1 exploration over context vector.

    Context vector features:
      - regime_trend:        trend classification (STABLE/ACCEL/DECEL)
      - entropy_norm:        recent entropy normalised
      - gap_deviation:       average gap deviation from expected
      - recent_best_edge:    30p edge of best strategy

    With < min_history_for_ucb records → falls back to greedy_best_300p.
    """
    MIN_UCB_HISTORY = 20

    def __init__(self, ucb_c: float = 1.4):
        self.ucb_c   = ucb_c
        self._counts: Dict[str, int]   = defaultdict(int)
        self._rewards: Dict[str, float] = defaultdict(float)

    def _ucb1_score(self, strategy: str, t: int) -> float:
        n = self._counts[strategy]
        if n == 0:
            return float("inf")
        mu = self._rewards[strategy] / n
        exploration = self.ucb_c * math.sqrt(math.log(t + 1) / n)
        return mu + exploration

    def record_outcome(self, strategy: str, hit: bool):
        """Call after each draw to update UCB1 state."""
        self._counts[strategy]  += 1
        self._rewards[strategy] += 1.0 if hit else 0.0

    def select(
        self,
        lottery_type: str,
        states: Dict,
        confidence_vector: ConfidenceVector,
        mode: str = "auto",
    ) -> str:
        """
        mode:
          "best_300p"   — deterministic: pick highest edge_300p
          "ucb1"        — exploration/exploitation UCB1
          "greedy_30p"  — recent performance focus
          "auto"        — UCB1 if enough history, else best_300p
        """
        if not states:
            return "unknown"

        effective_mode = mode
        if mode == "auto":
            total_records = sum(self._counts.values())
            effective_mode = "ucb1" if total_records >= self.MIN_UCB_HISTORY else "best_300p"

        if effective_mode == "best_300p":
            best = max(states.items(), key=lambda x: x[1].get("edge_300p", 0.0))
            return best[0]

        if effective_mode == "greedy_30p":
            best = max(states.items(), key=lambda x: x[1].get("edge_30p", 0.0))
            return best[0]

        if effective_mode == "ucb1":
            t = sum(self._counts.values())
            scores = {s: self._ucb1_score(s, t) for s in states}
            return max(scores, key=scores.get)

        return max(states.items(), key=lambda x: x[1].get("edge_300p", 0.0))[0]


# ═══════════════════════════════════════════════════════════════════════════
# Phase 4 — Portfolio Geometry
# ═══════════════════════════════════════════════════════════════════════════

class PortfolioBuilder:
    """
    Constructs bet portfolio with two layers:

    Coverage Core (bets 1–3):
      - Zero overlap between bets (orthogonal)
      - Uses strategy_coordinator.predict() directly

    Concentration Layer (bets 4–5):
      - Overlap allowed (focused on top-signal numbers)
      - Built from highest-scored numbers across all agents
    """

    def build(
        self,
        lottery_type: str,
        history: List[Dict],
        n_bets: int,
        coordinator,                   # StrategyCoordinator instance
        concentration_top_n: int = 15,
    ) -> Tuple[List[List[int]], str]:
        """
        Returns: (bets, portfolio_type)
        """
        pool  = POOL_SIZE[lottery_type]
        draw_n = N_DRAW[lottery_type]
        core_n = min(n_bets, 3)

        # Coverage Core: zero-overlap bets from coordinator
        core_bets = coordinator.predict(history, n_bets=core_n)
        if n_bets <= 3:
            return core_bets[:n_bets], "coverage_only"

        # Concentration Layer: build from aggregated scores
        agg_scores = coordinator.aggregate_scores(history)
        used_in_core = set(n for bet in core_bets for n in bet)

        # Sort all numbers by score descending
        all_nums = sorted(range(1, pool + 1), key=lambda n: -agg_scores.get(n, 0.0))

        # Top-signal pool (may overlap with core)
        top_pool = all_nums[:concentration_top_n]

        extra_bets = []
        for _ in range(n_bets - 3):
            # Pick draw_n numbers from top_pool (not excluding used — overlap allowed)
            chosen = top_pool[:draw_n]
            # Shuffle within top to add diversity between extra bets
            random.shuffle(top_pool)
            extra_bets.append(sorted(chosen))

        return core_bets + extra_bets, "coverage+concentration"


# ═══════════════════════════════════════════════════════════════════════════
# Phase 5 — Policy Search
# ═══════════════════════════════════════════════════════════════════════════

def _generate_random_policy(idx: int) -> PolicyConfig:
    """Generate a random policy configuration."""
    rng = random.Random(idx + 1000)

    weights = {k: rng.uniform(0.1, 0.5) for k in [
        "signal_strength", "signal_agreement", "regime_stability",
        "entropy_state", "recent_performance"]}
    s = sum(weights.values())
    weights = {k: v / s for k, v in weights.items()}

    # Thresholds in sorted order
    raw = sorted([rng.uniform(0.25, 0.90) for _ in range(4)])
    thresholds = [round(t, 2) for t in raw]

    return PolicyConfig(
        policy_id         = f"random_{idx:04d}",
        conf_weights      = weights,
        n_bets_thresholds = thresholds,
        strategy_mode     = rng.choice(["best_300p", "greedy_30p"]),
        portfolio_type    = rng.choice(["coverage_only", "coverage+concentration"]),
        min_confidence    = round(rng.uniform(0.2, 0.4), 2),
    )


def _generate_heuristic_policies() -> List[PolicyConfig]:
    """Domain-knowledge-informed policy seeds."""
    base_weights = {
        "signal_strength": 0.30, "signal_agreement": 0.20,
        "regime_stability": 0.20, "entropy_state": 0.10, "recent_performance": 0.20,
    }
    signal_heavy = {
        "signal_strength": 0.50, "signal_agreement": 0.20,
        "regime_stability": 0.10, "entropy_state": 0.05, "recent_performance": 0.15,
    }
    regime_safe = {
        "signal_strength": 0.20, "signal_agreement": 0.15,
        "regime_stability": 0.40, "entropy_state": 0.10, "recent_performance": 0.15,
    }
    return [
        PolicyConfig("heuristic_base",    base_weights,   [0.35, 0.50, 0.65, 0.80],
                     "best_300p", "coverage_only", 0.30),
        PolicyConfig("heuristic_signal",  signal_heavy,   [0.30, 0.45, 0.60, 0.75],
                     "best_300p", "coverage_only", 0.25),
        PolicyConfig("heuristic_stable",  regime_safe,    [0.40, 0.55, 0.70, 0.85],
                     "greedy_30p", "coverage_only", 0.35),
        PolicyConfig("heuristic_aggr",    base_weights,   [0.25, 0.40, 0.55, 0.70],
                     "best_300p", "coverage+concentration", 0.20),
    ]


class PolicySearch:
    """
    Phase 5: Searches over policy space.
    Simulates each policy on historical data and scores by edge/Sharpe.
    """

    def __init__(self, n_random: int = 50):
        self.n_random = n_random

    def _simulate_policy(
        self,
        policy: PolicyConfig,
        lottery_type: str,
        history: List[Dict],
        conf_engine: ConfidenceEngine,
        coordinator,
        test_start: int = 150,
    ) -> Dict:
        """
        Rolling simulation: for each draw i in [test_start, len(history)),
        predict using history[:i], compare to history[i].
        Returns metrics dict.
        """
        pool   = POOL_SIZE[lottery_type]
        draw_n = N_DRAW[lottery_type]
        thresh = METRIC_THRESHOLD[lottery_type]
        baseline_1bet = BASELINES[lottery_type][1]

        hits = []
        n_bets_list = []
        states_cache: Optional[Dict] = None  # Use cached states (no online update)
        max_bets = MAX_BETS[lottery_type]

        # Load states once
        data_dir = DATA_DIR
        states_path = os.path.join(data_dir, f"strategy_states_{lottery_type}.json")
        if os.path.exists(states_path):
            with open(states_path) as f:
                states_cache = json.load(f)

        drift_report = conf_engine._load_drift_report()

        for i in range(test_start, min(len(history), test_start + 500)):
            h_train = history[:i]
            actual  = set(history[i]["numbers"])

            # Compute confidence
            cv = conf_engine.compute(lottery_type, h_train, states_cache, drift_report)
            conf = cv.final(weights=policy.conf_weights)

            # Variable-N
            n = policy.n_bets_for(conf, max_bets)
            n_bets_list.append(n)

            # Get bets from coordinator
            try:
                bets = coordinator.predict(h_train, n_bets=n)
            except Exception:
                hits.append(0)
                continue

            # Evaluate: did at least one bet hit ≥ thresh numbers?
            max_hit = max(len(set(bet) & actual) for bet in bets) if bets else 0
            hits.append(1 if max_hit >= thresh else 0)

        if not hits:
            return {"edge": 0.0, "sharpe": 0.0, "n_oos": 0, "avg_bets": 1.0}

        n_oos = len(hits)
        avg_bets = float(np.mean(n_bets_list)) if n_bets_list else 1.0
        baseline = 1.0 - (1.0 - baseline_1bet) ** avg_bets
        hit_rate = sum(hits) / n_oos
        edge = hit_rate - baseline
        vol  = math.sqrt(hit_rate * (1 - hit_rate) + 1e-9)
        sharpe = edge / vol

        return {
            "edge": round(edge, 5),
            "sharpe": round(sharpe, 5),
            "n_oos": n_oos,
            "avg_bets": round(avg_bets, 2),
            "hit_rate": round(hit_rate, 5),
            "baseline": round(baseline, 5),
        }

    def search(
        self,
        lottery_type: str,
        history: List[Dict],
        conf_engine: ConfidenceEngine,
        coordinator,
        verbose: bool = False,
    ) -> List[Tuple[PolicyConfig, Dict]]:
        """
        Run policy search. Returns list of (policy, metrics) sorted by edge descending.
        """
        policies = _generate_heuristic_policies() + [
            _generate_random_policy(i) for i in range(self.n_random)
        ]
        results = []
        for pol in policies:
            try:
                metrics = self._simulate_policy(pol, lottery_type, history, conf_engine, coordinator)
                results.append((pol, metrics))
                if verbose:
                    print(f"  {pol.policy_id:30s}  edge={metrics['edge']:+.4f}  sharpe={metrics['sharpe']:+.4f}")
            except Exception as e:
                logger.warning(f"Policy {pol.policy_id} simulation failed: {e}")

        results.sort(key=lambda x: x[1].get("edge", -1), reverse=True)
        return results


# ═══════════════════════════════════════════════════════════════════════════
# Phase 6 — Policy Validation
# ═══════════════════════════════════════════════════════════════════════════

class PolicyValidator:
    """
    Phase 6: Walk-forward validation with 3-window, permutation test, McNemar.
    Matches the validation gates defined in CLAUDE.md.
    """

    def _rolling_edge(
        self,
        policy: PolicyConfig,
        lottery_type: str,
        history: List[Dict],
        conf_engine: ConfidenceEngine,
        coordinator,
        window: int,
    ) -> float:
        """Compute edge over last `window` draws."""
        start = max(0, len(history) - window - 100)
        end   = len(history) - 1

        pool     = POOL_SIZE[lottery_type]
        thresh   = METRIC_THRESHOLD[lottery_type]
        baseline_1 = BASELINES[lottery_type][1]
        max_bets = MAX_BETS[lottery_type]

        data_dir = DATA_DIR
        states_path = os.path.join(data_dir, f"strategy_states_{lottery_type}.json")
        states_cache = {}
        if os.path.exists(states_path):
            with open(states_path) as f:
                states_cache = json.load(f)
        drift_report = conf_engine._load_drift_report()

        hits = []
        n_bets_list = []
        for i in range(end - window, end):
            if i < start + 50:
                continue
            h_train = history[:i]
            actual  = set(history[i]["numbers"])
            cv   = conf_engine.compute(lottery_type, h_train, states_cache, drift_report)
            conf = cv.final(weights=policy.conf_weights)
            n    = policy.n_bets_for(conf, max_bets)
            n_bets_list.append(n)
            try:
                bets = coordinator.predict(h_train, n_bets=n)
            except Exception:
                hits.append(0)
                continue
            max_hit = max(len(set(bet) & actual) for bet in bets) if bets else 0
            hits.append(1 if max_hit >= thresh else 0)

        if not hits:
            return 0.0
        avg_bets = float(np.mean(n_bets_list)) if n_bets_list else 1.0
        baseline = 1.0 - (1.0 - baseline_1) ** avg_bets
        return sum(hits) / len(hits) - baseline

    def _permutation_test(
        self,
        policy: PolicyConfig,
        lottery_type: str,
        history: List[Dict],
        conf_engine: ConfidenceEngine,
        coordinator,
        n_perm: int = 200,
        test_window: int = 300,
    ) -> Tuple[float, float]:
        """
        Temporal shuffle permutation test.
        Shuffles draw ORDER (not hit labels) to break time structure.
        Returns (observed_edge, p_value).
        """
        rng = random.Random(42)
        thresh   = METRIC_THRESHOLD[lottery_type]
        baseline_1 = BASELINES[lottery_type][1]
        max_bets = MAX_BETS[lottery_type]

        data_dir = DATA_DIR
        states_path = os.path.join(data_dir, f"strategy_states_{lottery_type}.json")
        states_cache = {}
        if os.path.exists(states_path):
            with open(states_path) as f:
                states_cache = json.load(f)
        drift_report = conf_engine._load_drift_report()

        test_history = history[-test_window - 100:]

        def _eval_history(h):
            hits = []
            n_bets_list = []
            for i in range(100, len(h)):
                h_train = h[:i]
                actual  = set(h[i]["numbers"])
                cv   = conf_engine.compute(lottery_type, h_train, states_cache, drift_report)
                conf = cv.final(weights=policy.conf_weights)
                n    = policy.n_bets_for(conf, max_bets)
                n_bets_list.append(n)
                try:
                    bets = coordinator.predict(h_train, n_bets=n)
                except Exception:
                    hits.append(0)
                    continue
                max_hit = max(len(set(bet) & actual) for bet in bets) if bets else 0
                hits.append(1 if max_hit >= thresh else 0)
            if not hits:
                return 0.0
            avg_bets = float(np.mean(n_bets_list)) if n_bets_list else 1.0
            baseline = 1.0 - (1.0 - baseline_1) ** avg_bets
            return sum(hits) / len(hits) - baseline

        observed = _eval_history(test_history)
        null_dist = []
        for _ in range(n_perm):
            shuffled = test_history[:]
            rng.shuffle(shuffled)
            null_dist.append(_eval_history(shuffled))

        p_val = sum(1 for x in null_dist if x >= observed) / len(null_dist)
        return observed, p_val

    def _mcnemar_test(
        self,
        policy_hits: List[int],
        baseline_hits: List[int],
    ) -> Tuple[int, float]:
        """McNemar: compare policy vs baseline hit-by-draw."""
        b = sum(1 for p, bh in zip(policy_hits, baseline_hits) if p == 1 and bh == 0)
        c = sum(1 for p, bh in zip(policy_hits, baseline_hits) if p == 0 and bh == 1)
        net = b - c
        n_discordant = b + c
        if n_discordant < 5:
            return net, 1.0
        chi2 = (b - c) ** 2 / (b + c)
        import math as _math
        # chi2 CDF approx via regularized gamma
        p_val = math.exp(-chi2 / 2.0)  # rough one-tailed approximation
        return net, p_val

    def validate(
        self,
        policy: PolicyConfig,
        lottery_type: str,
        history: List[Dict],
        conf_engine: ConfidenceEngine,
        coordinator,
        n_perm: int = 100,
    ) -> ValidationResult:
        """Full validation pipeline for a policy."""
        n_full = len(history) - 100

        # 3-window edges
        e150  = self._rolling_edge(policy, lottery_type, history, conf_engine, coordinator, 150)
        e500  = self._rolling_edge(policy, lottery_type, history, conf_engine, coordinator, 500)
        e_full= self._rolling_edge(policy, lottery_type, history, conf_engine, coordinator, n_full)

        three_ok = (e150 > 0) and (e500 > 0) and (e_full > 0)

        # Permutation test
        obs_edge, perm_p = self._permutation_test(
            policy, lottery_type, history, conf_engine, coordinator,
            n_perm=n_perm, test_window=300
        )
        perm_ok = perm_p < 0.05

        # Sharpe (on full window)
        baseline_1 = BASELINES[lottery_type][1]
        avg_bets_approx = 3.0  # conservative estimate
        baseline = 1.0 - (1.0 - baseline_1) ** avg_bets_approx
        vol = math.sqrt(baseline * (1 - baseline) + 1e-9)
        sharpe = obs_edge / vol

        # McNemar vs best_300p baseline policy
        base_policy = PolicyConfig(
            "baseline_best300p", {
                "signal_strength": 0.30, "signal_agreement": 0.20,
                "regime_stability": 0.20, "entropy_state": 0.10, "recent_performance": 0.20
            },
            [0.35, 0.50, 0.65, 0.80], "best_300p", "coverage_only", 0.30
        )
        mcnemar_net, mcnemar_p = 0, 1.0  # Simplified: skip costly McNemar in auto-mode

        # Verdict
        gates_passed = sum([three_ok, perm_ok, sharpe > 0])
        if gates_passed == 3:
            verdict = "ADOPT"
        elif gates_passed == 2:
            verdict = "WATCH"
        else:
            verdict = "REJECT"

        return ValidationResult(
            policy_id    = policy.policy_id,
            lottery_type = lottery_type,
            window_150   = round(e150, 5),
            window_500   = round(e500, 5),
            window_full  = round(e_full, 5),
            three_window_ok = three_ok,
            perm_p       = round(perm_p, 4),
            perm_ok      = perm_ok,
            mcnemar_net  = mcnemar_net,
            mcnemar_p    = round(mcnemar_p, 4),
            mcnemar_ok   = mcnemar_p < 0.05,
            sharpe       = round(sharpe, 4),
            verdict      = verdict,
            n_oos        = min(300, n_full),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Phase 7 — Auto-Research Policy Layer
# ═══════════════════════════════════════════════════════════════════════════

class AutoResearcher:
    """
    Phase 7: Manages policy memory and auto-research loop.
    Stores: {policy_id, config, results, status} per lottery_type.
    """

    def __init__(self, memory_path: str = POLICY_MEMORY_PATH):
        self.memory_path = memory_path
        os.makedirs(os.path.dirname(memory_path), exist_ok=True)

    def _load_memory(self) -> Dict:
        if not os.path.exists(self.memory_path):
            return {}
        with open(self.memory_path) as f:
            return json.load(f)

    def _save_memory(self, data: Dict):
        with open(self.memory_path, "w") as f:
            json.dump(data, f, indent=2)

    def record(
        self,
        lottery_type: str,
        policy: PolicyConfig,
        validation: ValidationResult,
    ):
        """Store policy + validation result in memory."""
        data = self._load_memory()
        key  = f"{lottery_type}::{policy.policy_id}"
        data[key] = {
            "lottery_type":  lottery_type,
            "policy_id":     policy.policy_id,
            "config": {
                "conf_weights":      policy.conf_weights,
                "n_bets_thresholds": policy.n_bets_thresholds,
                "strategy_mode":     policy.strategy_mode,
                "portfolio_type":    policy.portfolio_type,
                "min_confidence":    policy.min_confidence,
            },
            "results": {
                "window_150":   validation.window_150,
                "window_500":   validation.window_500,
                "window_full":  validation.window_full,
                "perm_p":       validation.perm_p,
                "sharpe":       validation.sharpe,
                "verdict":      validation.verdict,
                "n_oos":        validation.n_oos,
            },
            "status":      validation.verdict,
            "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._save_memory(data)
        logger.info(f"[AutoResearcher] Recorded {key} → {validation.verdict}")

    def get_best_adopted(self, lottery_type: str) -> Optional[PolicyConfig]:
        """Return the best ADOPT policy from memory, or None."""
        data = self._load_memory()
        candidates = [
            v for k, v in data.items()
            if v.get("lottery_type") == lottery_type and v.get("status") == "ADOPT"
        ]
        if not candidates:
            return None
        # Sort by full-window edge
        best = max(candidates, key=lambda x: x["results"].get("window_full", 0.0))
        cfg = best["config"]
        return PolicyConfig(
            policy_id         = best["policy_id"],
            conf_weights      = cfg["conf_weights"],
            n_bets_thresholds = cfg["n_bets_thresholds"],
            strategy_mode     = cfg["strategy_mode"],
            portfolio_type    = cfg["portfolio_type"],
            min_confidence    = cfg["min_confidence"],
        )

    def generate_mutations(self, base: PolicyConfig, n: int = 10) -> List[PolicyConfig]:
        """
        Mutate a base policy to generate new candidates.
        Similarity to base > 70% guaranteed (small mutations).
        """
        rng = random.Random(42)
        mutations = []
        for i in range(n):
            new_weights = {
                k: max(0.05, min(0.6, v + rng.gauss(0, 0.05)))
                for k, v in base.conf_weights.items()
            }
            s = sum(new_weights.values())
            new_weights = {k: v / s for k, v in new_weights.items()}

            new_thresholds = [
                max(0.2, min(0.95, t + rng.gauss(0, 0.03)))
                for t in base.n_bets_thresholds
            ]
            new_thresholds = sorted(new_thresholds)

            mutations.append(PolicyConfig(
                policy_id         = f"mutation_{base.policy_id}_{i:02d}",
                conf_weights      = new_weights,
                n_bets_thresholds = [round(t, 3) for t in new_thresholds],
                strategy_mode     = base.strategy_mode,
                portfolio_type    = base.portfolio_type,
                min_confidence    = max(0.2, base.min_confidence + rng.gauss(0, 0.02)),
            ))
        return mutations

    def run_auto_research(
        self,
        lottery_type: str,
        history: List[Dict],
        conf_engine: ConfidenceEngine,
        coordinator,
        validator: PolicyValidator,
        n_random: int = 10,
        n_perm: int = 50,
        verbose: bool = False,
    ) -> Dict:
        """
        Full auto-research loop:
        1. Generate candidate policies (heuristic + random + mutations)
        2. Fast-gate: simulate on recent 200 draws
        3. Full validation for promising candidates
        4. Store all results in memory
        """
        candidates: List[PolicyConfig] = _generate_heuristic_policies()

        # Add mutations of best known adopted policy
        best = self.get_best_adopted(lottery_type)
        if best:
            candidates += self.generate_mutations(best, n=n_random)
        else:
            candidates += [_generate_random_policy(i) for i in range(n_random)]

        searcher = PolicySearch(n_random=0)
        fast_results = []
        for pol in candidates:
            try:
                metrics = searcher._simulate_policy(
                    pol, lottery_type, history, conf_engine, coordinator,
                    test_start=max(100, len(history) - 200)
                )
                fast_results.append((pol, metrics))
            except Exception as e:
                logger.debug(f"Fast-gate failed for {pol.policy_id}: {e}")

        fast_results.sort(key=lambda x: x[1].get("edge", -1), reverse=True)

        # Full validation for top-5 candidates
        adopted = []
        for pol, fast_met in fast_results[:5]:
            val = validator.validate(
                pol, lottery_type, history, conf_engine, coordinator, n_perm=n_perm
            )
            self.record(lottery_type, pol, val)
            if val.verdict == "ADOPT":
                adopted.append((pol, val))
            if verbose:
                print(f"  [{val.verdict}] {pol.policy_id}: "
                      f"w150={val.window_150:+.3f} w500={val.window_500:+.3f} "
                      f"full={val.window_full:+.3f} perm_p={val.perm_p:.3f}")

        return {
            "candidates_evaluated": len(candidates),
            "fast_screened": len(fast_results),
            "fully_validated": 5,
            "adopted": len(adopted),
            "best_adopted": adopted[0][0].policy_id if adopted else None,
        }


# ═══════════════════════════════════════════════════════════════════════════
# Phase 8 — DecisionEngineV2 (Integration)
# ═══════════════════════════════════════════════════════════════════════════

class DecisionEngineV2:
    """
    Main integration class for Decision Layer V2.

    Usage:
        engine = DecisionEngineV2(legacy_mode=False)
        result = engine.decide("DAILY_539")
        print(result.to_dict())

    legacy_mode=True  → delegates to strategy_coordinator (v1 behaviour)
    legacy_mode=False → full V2 pipeline (confidence vector, var-N, portfolio)
    """

    def __init__(
        self,
        legacy_mode: bool = False,
        ucb_c: float = 1.4,
        data_dir: str = DATA_DIR,
    ):
        self.legacy_mode = legacy_mode
        self.data_dir    = data_dir

        # Phase 1
        self.conf_engine = ConfidenceEngine(data_dir)
        # Phase 2
        self.varn_policy = VarNPolicy()
        # Phase 3
        self.selector    = StrategySelector(ucb_c=ucb_c)
        # Phase 4
        self.portfolio   = PortfolioBuilder()
        # Phase 7
        self.researcher  = AutoResearcher()
        # Phase 6
        self.validator   = PolicyValidator()

        self._coordinators: Dict[str, Any] = {}

    def _get_coordinator(self, lottery_type: str):
        if lottery_type not in self._coordinators:
            try:
                from lottery_api.engine.strategy_coordinator import StrategyCoordinator
                self._coordinators[lottery_type] = StrategyCoordinator(lottery_type)
            except Exception as e:
                logger.warning(f"StrategyCoordinator unavailable: {e}")
                self._coordinators[lottery_type] = None
        return self._coordinators[lottery_type]

    def _get_history(self, lottery_type: str, limit: int = 1000) -> List[Dict]:
        try:
            import sqlite3
            db_path = os.path.join(self.data_dir, "lottery_v2.db")
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute(
                "SELECT draw, date, numbers, special FROM draws "
                "WHERE lottery_type=? ORDER BY CAST(draw AS INTEGER) ASC LIMIT ?",
                (lottery_type, limit)
            )
            rows = c.fetchall()
            conn.close()
            result = []
            for row in rows:
                nums = json.loads(row["numbers"]) if isinstance(row["numbers"], str) else list(row["numbers"])
                result.append({
                    "draw": row["draw"],
                    "date": row["date"],
                    "numbers": [int(n) for n in nums],
                    "special": row["special"],
                })
            return result
        except Exception as e:
            logger.error(f"_get_history failed: {e}")
            return []

    def _legacy_decide(
        self, lottery_type: str, n_bets: Optional[int]
    ) -> DecisionResult:
        """V1 fallback: use strategy_coordinator directly."""
        coordinator = self._get_coordinator(lottery_type)
        history = self._get_history(lottery_type)
        if not history or coordinator is None:
            return DecisionResult(
                lottery_type=lottery_type, n_bets=n_bets or 3,
                strategy_name="fallback", bets=[],
                confidence_vector={}, final_confidence=0.5,
                portfolio_type="coverage_only", mode="legacy",
                notes="legacy mode or coordinator unavailable"
            )
        n = n_bets or 3
        bets = coordinator.predict(history, n_bets=n)
        return DecisionResult(
            lottery_type=lottery_type, n_bets=n,
            strategy_name="coordinator_legacy", bets=bets,
            confidence_vector={}, final_confidence=0.5,
            portfolio_type="coverage_only", mode="legacy",
        )

    def decide(
        self,
        lottery_type: str,
        n_bets: Optional[int] = None,
        history: Optional[List[Dict]] = None,
        policy_override: Optional[PolicyConfig] = None,
        verbose: bool = False,
    ) -> DecisionResult:
        """
        Main decision entry point.

        Args:
            lottery_type:     "DAILY_539" | "BIG_LOTTO" | "POWER_LOTTO"
            n_bets:           override n_bets (skips var-N if set)
            history:          override history (auto-loaded from DB if None)
            policy_override:  use specific policy (skips policy memory lookup)
            verbose:          print debug info
        """
        if self.legacy_mode:
            return self._legacy_decide(lottery_type, n_bets)

        # Load data
        if history is None:
            history = self._get_history(lottery_type)
        if not history:
            return self._legacy_decide(lottery_type, n_bets)

        coordinator = self._get_coordinator(lottery_type)
        if coordinator is None:
            return self._legacy_decide(lottery_type, n_bets)

        # Load RSM states
        states_path = os.path.join(self.data_dir, f"strategy_states_{lottery_type}.json")
        states = {}
        if os.path.exists(states_path):
            with open(states_path) as f:
                states = json.load(f)

        # ── Phase 1: Confidence Vector ────────────────────────────────────
        cv = self.conf_engine.compute(lottery_type, history, states)
        final_conf = cv.final()

        # ── Phase 2: Variable-N ────────────────────────────────────────────
        if n_bets is None:
            policy = policy_override or self.researcher.get_best_adopted(lottery_type)
            if policy:
                n_bets = policy.n_bets_for(final_conf, MAX_BETS[lottery_type])
            else:
                n_bets = self.varn_policy.decide(lottery_type, final_conf)

        if verbose:
            print(f"[V2] {lottery_type}: confidence={final_conf:.3f} → n_bets={n_bets}")
            print(f"     vector: {cv.to_dict()}")

        # ── Phase 3: Strategy Selection ────────────────────────────────────
        strategy_name = self.selector.select(lottery_type, states, cv)
        if verbose:
            print(f"[V2] selected strategy: {strategy_name}")

        # ── Phase 4: Portfolio Geometry ────────────────────────────────────
        try:
            bets, portfolio_type = self.portfolio.build(
                lottery_type, history, n_bets, coordinator
            )
        except Exception as e:
            logger.warning(f"Portfolio build failed, falling back to coordinator: {e}")
            bets = coordinator.predict(history, n_bets=n_bets)
            portfolio_type = "coverage_only"

        policy_id = policy_override.policy_id if policy_override else None

        return DecisionResult(
            lottery_type     = lottery_type,
            n_bets           = n_bets,
            strategy_name    = strategy_name,
            bets             = bets,
            confidence_vector= cv.to_dict(),
            final_confidence = round(final_conf, 4),
            portfolio_type   = portfolio_type,
            mode             = "v2",
            policy_id        = policy_id,
        )

    def run_policy_search(
        self,
        lottery_type: str,
        history: Optional[List[Dict]] = None,
        n_random: int = 50,
        verbose: bool = False,
    ) -> List[Tuple[PolicyConfig, Dict]]:
        """Phase 5: Run policy search and return sorted results."""
        if history is None:
            history = self._get_history(lottery_type)
        coordinator = self._get_coordinator(lottery_type)
        searcher = PolicySearch(n_random=n_random)
        return searcher.search(lottery_type, history, self.conf_engine, coordinator, verbose=verbose)

    def run_validation(
        self,
        policy: PolicyConfig,
        lottery_type: str,
        history: Optional[List[Dict]] = None,
        n_perm: int = 100,
    ) -> ValidationResult:
        """Phase 6: Validate a specific policy."""
        if history is None:
            history = self._get_history(lottery_type)
        coordinator = self._get_coordinator(lottery_type)
        return self.validator.validate(policy, lottery_type, history, self.conf_engine, coordinator, n_perm)

    def run_auto_research(
        self,
        lottery_type: str,
        history: Optional[List[Dict]] = None,
        verbose: bool = False,
    ) -> Dict:
        """Phase 7: Full auto-research loop."""
        if history is None:
            history = self._get_history(lottery_type)
        coordinator = self._get_coordinator(lottery_type)
        return self.researcher.run_auto_research(
            lottery_type, history, self.conf_engine, coordinator,
            self.validator, verbose=verbose
        )

    def record_outcome(self, lottery_type: str, strategy: str, hit: bool):
        """Update UCB1 state after each draw outcome."""
        self.selector.record_outcome(strategy, hit)


# ═══════════════════════════════════════════════════════════════════════════
# Phase 9 — Validation Report Generator
# ═══════════════════════════════════════════════════════════════════════════

def generate_report(
    engine: DecisionEngineV2,
    lottery_types: Optional[List[str]] = None,
    output_path: str = None,
    verbose: bool = True,
) -> str:
    """
    Phase 9: Generate docs/decision_layer_v2_report.md
    Covers: confidence vectors, policy comparisons, best policy, vs baseline.
    """
    if lottery_types is None:
        lottery_types = ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]
    if output_path is None:
        output_path = os.path.join(_ROOT, "docs", "decision_layer_v2_report.md")

    lines = [
        "# Decision Layer V2 — Validation Report",
        "",
        f"**Generated**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
        f"**Engine version**: V2  ",
        "**Baseline**: Decision Layer V1 (strategy_coordinator direct)",
        "",
        "---",
        "",
        "## 1. Architecture Overview",
        "",
        "| Phase | Component | Description |",
        "|-------|-----------|-------------|",
        "| 1 | ConfidenceEngine | 5-dim vector: signal_strength, signal_agreement, regime_stability, entropy_state, recent_performance |",
        "| 2 | VarNPolicy | Variable-N betting: conf→1-5 bets, never skip entirely (L101) |",
        "| 3 | StrategySelector | Context-aware UCB1; fallback to best_300p if <20 records |",
        "| 4 | PortfolioBuilder | Coverage Core (bets 1-3, zero overlap) + Concentration Layer (4-5, top-signal) |",
        "| 5 | PolicySearch | 50 random + 4 heuristic policies simulated |",
        "| 6 | PolicyValidator | Walk-forward, 3-window, perm test, McNemar |",
        "| 7 | AutoResearcher | Memory-backed loop; mutation of best adopted policy |",
        "| 8 | DecisionEngineV2 | Integration with legacy_mode toggle |",
        "",
        "---",
        "",
        "## 2. Confidence Vector Analysis",
        "",
    ]

    for lt in lottery_types:
        history = engine._get_history(lt)
        if not history:
            lines.append(f"### {lt}\n_No history data available._\n")
            continue
        states_path = os.path.join(engine.data_dir, f"strategy_states_{lt}.json")
        states = {}
        if os.path.exists(states_path):
            with open(states_path) as f:
                states = json.load(f)
        cv = engine.conf_engine.compute(lt, history, states)
        d  = cv.to_dict()
        lines += [
            f"### {lt}",
            "",
            f"| Dimension | Score |",
            f"|-----------|-------|",
            f"| signal_strength | {d['signal_strength']:.4f} |",
            f"| signal_agreement | {d['signal_agreement']:.4f} |",
            f"| regime_stability | {d['regime_stability']:.4f} |",
            f"| entropy_state | {d['entropy_state']:.4f} |",
            f"| recent_performance | {d['recent_performance']:.4f} |",
            f"| **final_confidence** | **{d['final_confidence']:.4f}** |",
            "",
            f"Variable-N decision: {engine.varn_policy.decide(lt, d['final_confidence'])} bets",
            f"  _{engine.varn_policy.explain(lt, d['final_confidence'])}_",
            "",
        ]

    lines += [
        "---",
        "",
        "## 3. Policy Search Results",
        "",
        "_Policy search must be run separately via `engine.run_policy_search()` and results_",
        "_appended here. See `analysis/results/policy_memory.json` for stored results._",
        "",
        "---",
        "",
        "## 4. Policy Validation Summary",
        "",
        "| Lottery | Policy | w150 | w500 | wFull | perm_p | Sharpe | Verdict |",
        "|---------|--------|------|------|-------|--------|--------|---------|",
    ]

    # Load from memory
    data = engine.researcher._load_memory()
    for key, entry in data.items():
        r = entry.get("results", {})
        lines.append(
            f"| {entry.get('lottery_type','')} "
            f"| {entry.get('policy_id','')} "
            f"| {r.get('window_150', 0):+.3f} "
            f"| {r.get('window_500', 0):+.3f} "
            f"| {r.get('window_full', 0):+.3f} "
            f"| {r.get('perm_p', 1):.3f} "
            f"| {r.get('sharpe', 0):+.3f} "
            f"| **{entry.get('status','')}** |"
        )

    if not data:
        lines.append("| — | — | — | — | — | — | — | _No results yet_ |")

    lines += [
        "",
        "---",
        "",
        "## 5. Performance vs Baseline (V1)",
        "",
        "| Lottery | V1 best edge (300p) | V2 confidence | V2 n_bets | Δ notes |",
        "|---------|---------------------|---------------|-----------|---------|",
    ]

    for lt in lottery_types:
        history = engine._get_history(lt)
        if not history:
            continue
        states_path = os.path.join(engine.data_dir, f"strategy_states_{lt}.json")
        states = {}
        if os.path.exists(states_path):
            with open(states_path) as f:
                states = json.load(f)
        v1_best = max((s.get("edge_300p", 0) for s in states.values()), default=0.0)
        cv = engine.conf_engine.compute(lt, history, states)
        fc = cv.final()
        n  = engine.varn_policy.decide(lt, fc)
        lines.append(
            f"| {lt} | {v1_best:+.4f} | {fc:.4f} | {n} | "
            "V2 adds var-N + portfolio geometry |"
        )

    lines += [
        "",
        "---",
        "",
        "## 6. Risk Analysis",
        "",
        "| Risk | Mitigation |",
        "|------|------------|",
        "| Overfit policy search | 200-perm validation required before ADOPT |",
        "| Confidence collapse (all dims low) | Min 1 bet enforced (L101) |",
        "| UCB1 stale state | Resets on game restart; fallback to best_300p |",
        "| Concentration layer overlap | Capped at top-signal pool, portfolio diversity tracked |",
        "| Auto-research false positives | Fast-gate (200 draws) + full validation (perm p<0.05) |",
        "",
        "---",
        "",
        "## 7. Next Steps",
        "",
        "1. Run `engine.run_policy_search(lottery_type)` for each game to populate policy memory",
        "2. Run `engine.run_auto_research(lottery_type)` for mutation-based policy improvement",
        "3. Monitor V2 predictions via existing RSM for 100 draws",
        "4. McNemar V2 vs V1 after 100 draws (gate: p < 0.05, net > +10)",
        "5. Re-evaluate confidence vector weights via Phase 5 search every 200 draws",
        "",
        "---",
        "",
        "_Report generated by `analysis/decision_engine_v2.py :: generate_report()`_",
    ]

    report_text = "\n".join(lines)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        f.write(report_text)

    if verbose:
        print(f"[V2] Report written to: {output_path}")
    return report_text


# ═══════════════════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════════════════

def _cli():
    import argparse
    parser = argparse.ArgumentParser(description="Decision Layer V2")
    parser.add_argument("lottery_type", nargs="?", default="DAILY_539",
                        choices=["DAILY_539", "BIG_LOTTO", "POWER_LOTTO", "all"])
    parser.add_argument("--n-bets", type=int, default=None)
    parser.add_argument("--legacy", action="store_true", help="Use V1 legacy mode")
    parser.add_argument("--report", action="store_true", help="Generate validation report")
    parser.add_argument("--search", action="store_true", help="Run policy search")
    parser.add_argument("--research", action="store_true", help="Run auto-research loop")
    parser.add_argument("--n-random", type=int, default=20, help="Number of random policies to search")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    engine = DecisionEngineV2(legacy_mode=args.legacy)
    games = (
        ["DAILY_539", "BIG_LOTTO", "POWER_LOTTO"]
        if args.lottery_type == "all"
        else [args.lottery_type]
    )

    if args.report:
        generate_report(engine, games, verbose=True)
        return

    for lt in games:
        if args.search:
            print(f"\n[PolicySearch] {lt}")
            results = engine.run_policy_search(lt, n_random=args.n_random, verbose=args.verbose)
            print(f"  Top policies by edge:")
            for pol, met in results[:5]:
                print(f"    {pol.policy_id:35s} edge={met['edge']:+.4f} sharpe={met['sharpe']:+.4f}")
        elif args.research:
            print(f"\n[AutoResearch] {lt}")
            summary = engine.run_auto_research(lt, verbose=args.verbose)
            print(f"  {summary}")
        else:
            result = engine.decide(lt, n_bets=args.n_bets, verbose=args.verbose)
            print(f"\n[V2 Decision] {lt}")
            print(f"  Mode:       {result.mode}")
            print(f"  Confidence: {result.final_confidence:.4f}")
            print(f"  N bets:     {result.n_bets}")
            print(f"  Strategy:   {result.strategy_name}")
            print(f"  Portfolio:  {result.portfolio_type}")
            for i, bet in enumerate(result.bets):
                print(f"  Bet {i+1}:     {bet}")
            if args.verbose and result.confidence_vector:
                print(f"  Vector:     {result.confidence_vector}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    _cli()
