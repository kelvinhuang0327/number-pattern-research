"""
Lottery RL Decision Environment — Track B
==========================================
Gymnasium-compatible environment for Stable-Baselines3.

ROLE: Strategy selector, bet-count chooser, skip decision maker.
NOT a number predictor — all prediction signals come from Track A (RSM records).

Anti-leakage guarantee:
  observation at step i = f(records[0:i])  — strictly past-only
  outcome   at step i = records[i]         — revealed AFTER action

Author: RL Integration Layer 2026-03-18
"""

from __future__ import annotations

import json
import os
import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import gymnasium as gym
from gymnasium import spaces

# ─── Constants ───────────────────────────────────────────────────────────────

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

STRATEGIES = [
    "acb_1bet",
    "midfreq_acb_2bet",
    "acb_markov_midfreq_3bet",
    "acb_markov_fourier_3bet",
    "f4cold_3bet",
    "f4cold_5bet",
]

NUM_BETS: Dict[int, int] = {
    0: 0,  # SKIP
    1: 1,  # acb_1bet
    2: 2,  # midfreq_acb_2bet
    3: 3,  # acb_markov_midfreq_3bet
    4: 3,  # acb_markov_fourier_3bet
    5: 3,  # f4cold_3bet
    6: 5,  # f4cold_5bet
}

ACTION_TO_STRAT: Dict[int, Optional[str]] = {
    0: None,
    1: "acb_1bet",
    2: "midfreq_acb_2bet",
    3: "acb_markov_midfreq_3bet",
    4: "acb_markov_fourier_3bet",
    5: "f4cold_3bet",
    6: "f4cold_5bet",
}

# M2+ random baselines (geometric: 1-(1-p_single)^n)
BASELINES: Dict[str, float] = {
    "acb_1bet":                 0.1140,
    "midfreq_acb_2bet":         0.2154,
    "acb_markov_midfreq_3bet":  0.3050,
    "acb_markov_fourier_3bet":  0.3050,
    "f4cold_3bet":              0.3050,
    "f4cold_5bet":              0.4539,
}

ACTION_BASELINES: Dict[int, float] = {
    0: 0.0,
    1: BASELINES["acb_1bet"],
    2: BASELINES["midfreq_acb_2bet"],
    3: BASELINES["acb_markov_midfreq_3bet"],
    4: BASELINES["acb_markov_fourier_3bet"],
    5: BASELINES["f4cold_3bet"],
    6: BASELINES["f4cold_5bet"],
}

OBS_DIM = 39   # 6 strategies × 6 features + 3 cross-strategy
N_ACTIONS = 7  # 0=skip, 1-6=strategies

# ─── Reward variants ─────────────────────────────────────────────────────────

REWARD_MODES = ("edge", "payout_aware", "skip_efficiency", "bankroll")


# ─── Data Loading ─────────────────────────────────────────────────────────────

def load_rsm_records(lottery_type: str = "DAILY_539") -> Dict[str, List[Dict]]:
    """Load rolling_monitor records. Returns {strategy_name: [record, ...]}."""
    path = os.path.join(PROJECT_ROOT, "data", f"rolling_monitor_{lottery_type}.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    records = data.get("records", {})
    # Keep only strategies we model
    return {s: records[s] for s in STRATEGIES if s in records}


def align_records(raw: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Align all strategies by draw_id, return sorted list of draws.
    Each draw: {'draw_id': str, 'date': str, 'outcomes': {strat: {'is_m2plus': bool, ...}}}
    """
    draw_map: Dict[str, Dict] = {}
    for strat, recs in raw.items():
        for r in recs:
            did = r["draw_id"]
            if did not in draw_map:
                draw_map[did] = {"draw_id": did, "date": r.get("date", ""), "outcomes": {}}
            draw_map[did]["outcomes"][strat] = {
                "is_m2plus": bool(r.get("is_m2plus", False)),
                "is_m3plus": bool(r.get("is_m3plus", False)),
                "best_match": r.get("best_match", 0),
                "match_counts": r.get("match_counts", []),
                "num_bets": r.get("num_bets", 1),
            }
    # Sort by draw_id (lexicographic ≈ chronological for Taiwan lottery IDs)
    aligned = sorted(draw_map.values(), key=lambda x: x["draw_id"])
    # Keep only draws with all 6 strategies
    aligned = [d for d in aligned if len(d["outcomes"]) == len(STRATEGIES)]
    return aligned


# ─── Feature Engineering ──────────────────────────────────────────────────────

def compute_rolling_features(
    draws: List[Dict],
    idx: int,
    windows: Tuple[int, int, int] = (30, 100, 300),
) -> np.ndarray:
    """
    Compute 39-dim observation vector at position idx using ONLY draws[:idx].

    Strictly no-leakage: reads draws[0:idx], computes statistics,
    returns feature vector WITHOUT any information from draws[idx:].
    """
    past = draws[:idx]   # ← strict past-only slice
    n = len(past)
    w30, w100, w300 = windows
    features = []

    for strat in STRATEGIES:
        baseline = BASELINES[strat]

        # Extract hit history for this strategy
        hits = [
            float(d["outcomes"][strat]["is_m2plus"])
            for d in past
            if strat in d["outcomes"]
        ]
        n_hist = len(hits)

        def _rate(w: int) -> float:
            if n_hist == 0:
                return baseline
            slice_ = hits[-w:]
            return float(np.mean(slice_)) if slice_ else baseline

        r30  = _rate(w30)
        r100 = _rate(w100)
        r300 = _rate(w300)

        e30  = r30  - baseline
        e100 = r100 - baseline
        e300 = r300 - baseline

        # Sharpe: edge_300 / std of recent hits (300p)
        hist300 = hits[-w300:] if n_hist >= 2 else hits
        std300 = float(np.std(hist300)) if len(hist300) > 1 else 1.0
        sharpe = e300 / (std300 + 1e-6)

        # z-score trend: (rate_30 - rate_300) / SE(rate_300)
        n300_eff = max(1, min(w300, n_hist))
        se300 = math.sqrt(r300 * (1 - r300) / n300_eff + 1e-8)
        z_score = (r30 - r300) / se300

        # Recent 5-draw momentum
        recent5 = float(np.mean(hits[-5:])) if len(hits) >= 5 else float(np.mean(hits)) if hits else baseline

        features.extend([
            np.clip(e30,    -0.3, 0.3),
            np.clip(e100,   -0.3, 0.3),
            np.clip(e300,   -0.3, 0.3),
            np.clip(sharpe, -5.0, 5.0) / 5.0,    # normalize to [-1, 1]
            np.clip(z_score,-3.0, 3.0) / 3.0,    # normalize to [-1, 1]
            recent5 - baseline,
        ])

    # Cross-strategy features
    edge300s = [features[i * 6 + 2] for i in range(len(STRATEGIES))]
    best_edge  = float(max(edge300s))
    dispersion = float(np.std(edge300s))
    consensus  = float(sum(1 for e in edge300s if e > 0)) / len(STRATEGIES)

    features.extend([
        np.clip(best_edge,   -0.3, 0.3),
        np.clip(dispersion,   0.0, 0.2),
        consensus,
    ])

    arr = np.array(features, dtype=np.float32)
    return arr


# ─── Environment ──────────────────────────────────────────────────────────────

class LotteryRLEnv(gym.Env):
    """
    Gymnasium environment for lottery strategy selection.

    Track B: RL decision layer on top of validated prediction signals.

    observation: 39-dim float32 vector (past-only RSM features)
    action:      Discrete(7)  — 0=skip, 1-6=strategy selection
    reward:      edge-normalized, optionally payout-aware
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        draws: List[Dict],
        start_idx: int = 0,
        end_idx: Optional[int] = None,
        reward_mode: str = "edge",
        min_history: int = 30,
        skip_penalty: float = -0.02,
        seed: int = 42,
    ):
        super().__init__()
        assert reward_mode in REWARD_MODES, f"reward_mode must be one of {REWARD_MODES}"

        self.draws = draws
        self.start_idx = max(start_idx, min_history)
        self.end_idx = end_idx if end_idx is not None else len(draws)
        self.reward_mode = reward_mode
        self.min_history = min_history
        self.skip_penalty = skip_penalty

        # Gymnasium spaces
        self.action_space = spaces.Discrete(N_ACTIONS)
        self.observation_space = spaces.Box(
            low=-1.0, high=1.0, shape=(OBS_DIM,), dtype=np.float32
        )

        self._rng = np.random.default_rng(seed)
        self.current_idx: int = self.start_idx
        self._ep_returns: List[float] = []
        self._ep_hits: int = 0
        self._ep_steps: int = 0
        self._ep_skips: int = 0

    # ─── Gymnasium API ───────────────────────────────────────────────────────

    def reset(self, *, seed=None, options=None) -> Tuple[np.ndarray, Dict]:
        super().reset(seed=seed)
        self.current_idx = self.start_idx
        self._ep_returns = []
        self._ep_hits = 0
        self._ep_steps = 0
        self._ep_skips = 0
        obs = compute_rolling_features(self.draws, self.current_idx)
        return obs, {}

    def step(self, action: int) -> Tuple[np.ndarray, float, bool, bool, Dict]:
        if self.current_idx >= self.end_idx:
            obs = compute_rolling_features(self.draws, self.current_idx)
            return obs, 0.0, True, False, {"reason": "exhausted"}

        outcome = self.draws[self.current_idx]["outcomes"]
        reward, hit, info = self._compute_reward(action, outcome)

        self._ep_returns.append(reward)
        self._ep_hits += int(hit)
        self._ep_steps += 1
        if action == 0:
            self._ep_skips += 1

        self.current_idx += 1
        done = self.current_idx >= self.end_idx
        obs = compute_rolling_features(self.draws, self.current_idx)

        info.update({
            "action": action,
            "hit": hit,
            "draw_id": self.draws[self.current_idx - 1]["draw_id"],
        })
        return obs, reward, done, False, info

    # ─── Reward computation ──────────────────────────────────────────────────

    def _compute_reward(
        self, action: int, outcome: Dict[str, Dict]
    ) -> Tuple[float, bool, Dict]:
        """Returns (reward, is_hit, info_dict)."""
        if action == 0:
            # Skip: neutral to slightly negative
            # Bonus if ALL strategies would have missed anyway
            any_hit = any(
                outcome.get(s, {}).get("is_m2plus", False) for s in STRATEGIES
            )
            r = 0.05 if not any_hit else self.skip_penalty
            return r, False, {"mode": "skip", "any_would_hit": any_hit}

        strat = ACTION_TO_STRAT[action]
        if strat is None or strat not in outcome:
            return 0.0, False, {"mode": "invalid"}

        is_hit = outcome[strat]["is_m2plus"]
        baseline = ACTION_BASELINES[action]
        num_bets = NUM_BETS[action]
        cost_factor = 1.0 / math.sqrt(num_bets)

        if self.reward_mode == "edge":
            edge = (float(is_hit) - baseline) / (baseline + 1e-6)
            r = edge * cost_factor

        elif self.reward_mode == "payout_aware":
            payout_weights = {1: 1.0, 2: 0.85, 3: 0.75, 5: 0.60}
            pw = payout_weights.get(num_bets, 0.7)
            edge = (float(is_hit) - baseline) / (baseline + 1e-6)
            r = edge * pw

        elif self.reward_mode == "skip_efficiency":
            edge = (float(is_hit) - baseline) / (baseline + 1e-6)
            r = edge * cost_factor

        elif self.reward_mode == "bankroll":
            cost = num_bets * 50     # NT per bet
            payout = 1000 if is_hit else 0    # simplified fixed payout
            r = math.log(max((payout - cost + 10000) / 10000, 1e-4))
        else:
            r = 0.0

        return float(r), is_hit, {
            "mode": self.reward_mode,
            "strategy": strat,
            "is_hit": is_hit,
            "baseline": baseline,
            "num_bets": num_bets,
        }

    # ─── Episode summary ─────────────────────────────────────────────────────

    def episode_summary(self) -> Dict[str, Any]:
        n = self._ep_steps
        if n == 0:
            return {}
        active = n - self._ep_skips
        active_hits = self._ep_hits  # hits among active bets only
        hit_rate = active_hits / active if active > 0 else 0.0
        return {
            "total_steps": n,
            "active_steps": active,
            "skips": self._ep_skips,
            "skip_rate": self._ep_skips / n,
            "hits": self._ep_hits,
            "hit_rate": hit_rate,
            "mean_reward": float(np.mean(self._ep_returns)) if self._ep_returns else 0.0,
            "sum_reward": float(np.sum(self._ep_returns)),
        }

    def render(self):
        pass


# ─── Factory helpers ──────────────────────────────────────────────────────────

def make_train_val_test_envs(
    lottery_type: str = "DAILY_539",
    reward_mode: str = "edge",
    train_end: int = 200,
    val_end: int = 270,
    min_history: int = 30,
    seed: int = 42,
) -> Tuple[LotteryRLEnv, LotteryRLEnv, LotteryRLEnv]:
    """
    Load data and create three non-overlapping environments.

    Walk-forward protocol:
      train: draws[min_history : train_end]
      val:   draws[train_end   : val_end]   (trained model applied, no fit)
      test:  draws[val_end     : end]       (final OOS)
    """
    raw = load_rsm_records(lottery_type)
    draws = align_records(raw)

    env_train = LotteryRLEnv(
        draws, start_idx=min_history, end_idx=train_end,
        reward_mode=reward_mode, seed=seed
    )
    env_val = LotteryRLEnv(
        draws, start_idx=train_end, end_idx=val_end,
        reward_mode=reward_mode, seed=seed + 1
    )
    env_test = LotteryRLEnv(
        draws, start_idx=val_end, end_idx=len(draws),
        reward_mode=reward_mode, seed=seed + 2
    )
    return env_train, env_val, env_test


# ─── SB3 env checker ─────────────────────────────────────────────────────────

if __name__ == "__main__":
    from stable_baselines3.common.env_checker import check_env

    raw = load_rsm_records("DAILY_539")
    draws = align_records(raw)
    print(f"Total aligned draws: {len(draws)}")
    print(f"Strategies: {STRATEGIES}")
    print(f"Observation dim: {OBS_DIM}  |  Actions: {N_ACTIONS}")

    env = LotteryRLEnv(draws, start_idx=30, end_idx=200, reward_mode="edge")
    print("\nRunning SB3 env_checker...")
    check_env(env, warn=True, skip_render_check=True)
    print("✅ env_checker passed")

    # Sanity run
    obs, _ = env.reset()
    print(f"\nObs shape: {obs.shape}  min={obs.min():.3f}  max={obs.max():.3f}")
    total_r = 0.0
    for _ in range(50):
        action = env.action_space.sample()
        obs, r, done, _, info = env.step(action)
        total_r += r
        if done:
            break
    print(f"50-step random policy sum_reward={total_r:.3f}")
    print("Episode summary:", env.episode_summary())
