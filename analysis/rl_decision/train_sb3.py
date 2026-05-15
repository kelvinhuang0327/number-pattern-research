"""
SB3 Training Script — Lottery RL Decision Layer
================================================
Trains PPO and DQN agents on the lottery strategy selection task.

Walk-forward protocol:
  train : draws[30:200]   (170 draws)
  val   : draws[200:270]  (70 draws)
  test  : draws[270:end]  (48 draws)

Reproducible: seed=42 throughout.

Usage:
    /tmp/sb3_env/bin/python3 analysis/rl_decision/train_sb3.py
    /tmp/sb3_env/bin/python3 analysis/rl_decision/train_sb3.py --algo dqn
    /tmp/sb3_env/bin/python3 analysis/rl_decision/train_sb3.py --reward payout_aware
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List

import numpy as np

# ─── Path setup ──────────────────────────────────────────────────────────────
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(os.path.dirname(SCRIPT_DIR))
sys.path.insert(0, SCRIPT_DIR)

from env import (
    LotteryRLEnv,
    load_rsm_records,
    align_records,
    compute_rolling_features,
    ACTION_TO_STRAT,
    NUM_BETS,
    ACTION_BASELINES,
    BASELINES,
    STRATEGIES,
    N_ACTIONS,
)

from stable_baselines3 import PPO, DQN
from stable_baselines3.common.env_checker import check_env
from stable_baselines3.common.callbacks import BaseCallback, EvalCallback
from stable_baselines3.common.evaluation import evaluate_policy

# ─── Config ───────────────────────────────────────────────────────────────────

SEED = 42
TRAIN_END = 200
VAL_END   = 270
MIN_HIST  = 30
LOG_DIR   = os.path.join(PROJECT_ROOT, "rl_logs")
MODEL_DIR = os.path.join(PROJECT_ROOT, "analysis", "rl_decision", "models")
os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(MODEL_DIR, exist_ok=True)

PPO_KWARGS = dict(
    policy="MlpPolicy",
    learning_rate=3e-4,
    n_steps=170,          # one episode = train window length
    batch_size=85,        # 170 / 85 = 2 (exact factor, no truncated mini-batch)
    n_epochs=10,
    gamma=0.95,
    gae_lambda=0.90,
    clip_range=0.2,
    ent_coef=0.05,        # exploration entropy bonus
    policy_kwargs=dict(net_arch=[64, 64]),
    verbose=1,
    seed=SEED,
    tensorboard_log=LOG_DIR,
)

DQN_KWARGS = dict(
    policy="MlpPolicy",
    learning_rate=1e-3,
    buffer_size=5000,
    batch_size=32,
    gamma=0.95,
    exploration_fraction=0.5,
    exploration_final_eps=0.05,
    train_freq=4,
    target_update_interval=100,
    policy_kwargs=dict(net_arch=[64, 64]),
    verbose=1,
    seed=SEED,
    tensorboard_log=LOG_DIR,
)


# ─── Static baselines ─────────────────────────────────────────────────────────

def run_static_policy(draws: List[Dict], action: int, start: int, end: int) -> Dict:
    """Evaluate a fixed action policy over a draw window."""
    hits = 0
    total = 0
    strat = ACTION_TO_STRAT[action]
    baseline = ACTION_BASELINES[action]

    for draw in draws[start:end]:
        if strat is None:
            total += 1
            continue
        outcome = draw["outcomes"].get(strat, {})
        is_hit = outcome.get("is_m2plus", False)
        hits += int(is_hit)
        total += 1

    hit_rate = hits / total if total > 0 else 0.0
    edge = hit_rate - baseline
    return {
        "policy": f"static_action_{action}_{strat or 'skip'}",
        "action": action,
        "hits": hits,
        "total": total,
        "hit_rate": round(hit_rate, 4),
        "baseline": baseline,
        "edge": round(edge, 4),
        "edge_pct": round(edge * 100, 2),
    }


def run_best_static_policy(draws: List[Dict], start: int, end: int) -> Dict:
    """
    Oracle: always pick the strategy with highest 300p edge at each draw.
    Uses PAST-ONLY data to compute rolling edge (no leakage).
    """
    hits = 0
    total = 0
    actions_chosen: List[int] = []

    for idx in range(start, end):
        # Compute current edges using past only
        past = draws[:idx]
        best_action = 1  # fallback: acb_1bet
        best_edge = -999.0
        for a in range(1, N_ACTIONS):
            strat = ACTION_TO_STRAT[a]
            if strat is None:
                continue
            hist = [
                float(d["outcomes"][strat]["is_m2plus"])
                for d in past[-300:]
                if strat in d["outcomes"]
            ]
            if not hist:
                continue
            rate = float(np.mean(hist))
            edge = rate - ACTION_BASELINES[a]
            if edge > best_edge:
                best_edge = edge
                best_action = a

        strat = ACTION_TO_STRAT[best_action]
        outcome = draws[idx]["outcomes"].get(strat, {})
        is_hit = outcome.get("is_m2plus", False)
        hits += int(is_hit)
        total += 1
        actions_chosen.append(best_action)

    # Count action distribution
    from collections import Counter
    action_dist = Counter(actions_chosen)

    hit_rate = hits / total if total > 0 else 0.0
    baseline = float(np.mean([ACTION_BASELINES[a] for a in actions_chosen])) if actions_chosen else 0.3
    edge = hit_rate - baseline
    return {
        "policy": "best_static_rolling_300p",
        "hits": hits,
        "total": total,
        "hit_rate": round(hit_rate, 4),
        "baseline": round(baseline, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge * 100, 2),
        "action_distribution": {str(k): v for k, v in action_dist.items()},
    }


# ─── RL evaluation helper ─────────────────────────────────────────────────────

def evaluate_rl_model(
    model, draws: List[Dict], start: int, end: int, reward_mode: str
) -> Dict:
    """Run deterministic policy over draw window, collect stats."""
    env = LotteryRLEnv(draws, start_idx=start, end_idx=end, reward_mode=reward_mode)
    obs, _ = env.reset()

    hits = 0
    total = 0
    skips = 0
    rewards: List[float] = []
    actions_taken: List[int] = []
    baselines_used: List[float] = []

    while True:
        action, _ = model.predict(obs, deterministic=True)
        obs, r, done, _, info = env.step(int(action))
        rewards.append(r)
        actions_taken.append(int(action))
        total += 1

        if int(action) == 0:
            skips += 1
        else:
            hits += int(info.get("hit", False))
            baselines_used.append(ACTION_BASELINES[int(action)])

        if done:
            break

    active = total - skips
    hit_rate = hits / active if active > 0 else 0.0
    avg_baseline = float(np.mean(baselines_used)) if baselines_used else 0.3
    edge = hit_rate - avg_baseline

    from collections import Counter
    action_dist = Counter(actions_taken)

    return {
        "total_draws": total,
        "active": active,
        "skips": skips,
        "skip_rate": round(skips / total, 4),
        "hits": hits,
        "hit_rate": round(hit_rate, 4),
        "avg_baseline": round(avg_baseline, 4),
        "edge": round(edge, 4),
        "edge_pct": round(edge * 100, 2),
        "mean_reward": round(float(np.mean(rewards)), 4),
        "sum_reward": round(float(np.sum(rewards)), 4),
        "action_distribution": {str(k): v for k, v in action_dist.items()},
    }


# ─── Training function ────────────────────────────────────────────────────────

def train(algo: str = "ppo", reward_mode: str = "edge") -> Dict[str, Any]:
    """Full training pipeline with walk-forward evaluation."""
    t0 = time.time()
    np.random.seed(SEED)

    print(f"\n{'='*65}")
    print(f"  SB3 Training: algo={algo.upper()}  reward={reward_mode}")
    print(f"  Train: [30:{TRAIN_END}]  Val: [{TRAIN_END}:{VAL_END}]  Test: [{VAL_END}:end]")
    print(f"{'='*65}\n")

    # Load data
    raw = load_rsm_records("DAILY_539")
    draws = align_records(raw)
    total_draws = len(draws)
    test_start = VAL_END
    print(f"Loaded {total_draws} aligned draws | Test: [{test_start}:{total_draws}]")

    # Verify env
    env_train = LotteryRLEnv(
        draws, start_idx=MIN_HIST, end_idx=TRAIN_END,
        reward_mode=reward_mode, seed=SEED
    )
    check_env(env_train, warn=False, skip_render_check=True)
    print("✅ Env checker passed")

    # ── Train model ──────────────────────────────────────────────────────────
    total_timesteps = 170 * 50    # 50 passes through 170-draw train set

    if algo == "ppo":
        model = PPO(env=env_train, **PPO_KWARGS)
    elif algo == "dqn":
        model = DQN(env=env_train, **DQN_KWARGS)
    else:
        raise ValueError(f"Unknown algo: {algo}")

    print(f"\nTraining {algo.upper()} for {total_timesteps:,} timesteps...")
    model.learn(
        total_timesteps=total_timesteps,
        reset_num_timesteps=True,
        tb_log_name=f"{algo}_{reward_mode}",
        progress_bar=False,
    )
    print("Training complete.")

    # Save model
    model_path = os.path.join(MODEL_DIR, f"{algo}_{reward_mode}")
    model.save(model_path)
    print(f"Model saved → {model_path}.zip")

    # ── Evaluate on all windows ──────────────────────────────────────────────
    print("\nEvaluating...")

    rl_train = evaluate_rl_model(model, draws, MIN_HIST, TRAIN_END, reward_mode)
    rl_val   = evaluate_rl_model(model, draws, TRAIN_END, VAL_END, reward_mode)
    rl_test  = evaluate_rl_model(model, draws, test_start, total_draws, reward_mode)

    # Static baselines
    statics = {}
    for a in range(N_ACTIONS):
        statics[f"action_{a}"] = {
            "train": run_static_policy(draws, a, MIN_HIST, TRAIN_END),
            "val":   run_static_policy(draws, a, TRAIN_END, VAL_END),
            "test":  run_static_policy(draws, a, test_start, total_draws),
        }

    # Best rolling policy
    best_static = {
        "train": run_best_static_policy(draws, MIN_HIST, TRAIN_END),
        "val":   run_best_static_policy(draws, TRAIN_END, VAL_END),
        "test":  run_best_static_policy(draws, test_start, total_draws),
    }

    elapsed = time.time() - t0
    results = {
        "algo": algo,
        "reward_mode": reward_mode,
        "seed": SEED,
        "total_draws": total_draws,
        "splits": {"train_end": TRAIN_END, "val_end": VAL_END, "test_start": test_start},
        "training_timesteps": total_timesteps,
        "training_seconds": round(elapsed, 1),
        "rl_results": {
            "train": rl_train,
            "val":   rl_val,
            "test":  rl_test,
        },
        "static_baselines": statics,
        "best_rolling_static": best_static,
    }

    # Pretty print key numbers
    print(f"\n{'─'*55}")
    print(f"  RESULTS SUMMARY ({algo.upper()} | {reward_mode})")
    print(f"{'─'*55}")
    for window, rdata in [("TRAIN", rl_train), ("VAL", rl_val), ("TEST", rl_test)]:
        print(f"  [{window}] edge={rdata['edge_pct']:+.2f}%  "
              f"hit={rdata['hit_rate']:.3f}  "
              f"skip={rdata['skip_rate']:.2f}  "
              f"reward={rdata['mean_reward']:+.3f}")

    # Best static on test
    bs_test = best_static["test"]
    print(f"\n  [BEST_STATIC_TEST] edge={bs_test['edge_pct']:+.2f}%  "
          f"hit={bs_test['hit_rate']:.3f}")

    # Top static on test
    top_static_test = max(
        [v["test"] for k, v in statics.items() if k != "action_0"],
        key=lambda x: x["edge_pct"]
    )
    print(f"  [TOP_STATIC_TEST]  edge={top_static_test['edge_pct']:+.2f}%  "
          f"strategy={top_static_test['policy']}")
    print(f"{'─'*55}\n")

    return results


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Train SB3 RL lottery decision agent")
    parser.add_argument("--algo", choices=["ppo", "dqn", "both"], default="both")
    parser.add_argument("--reward", choices=["edge", "payout_aware", "skip_efficiency"], default="edge")
    parser.add_argument("--output", default=None, help="Output JSON path")
    args = parser.parse_args()

    algos = ["ppo", "dqn"] if args.algo == "both" else [args.algo]
    all_results = {}

    for algo in algos:
        result = train(algo=algo, reward_mode=args.reward)
        all_results[algo] = result

    # Save combined results
    out_path = args.output or os.path.join(PROJECT_ROOT, "sb3_walkforward_results.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Results saved → {out_path}")


if __name__ == "__main__":
    main()
