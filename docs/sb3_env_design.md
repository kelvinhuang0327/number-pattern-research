# SB3 RL Environment Design — Lottery Decision Layer
**Date:** 2026-03-18 | **Target:** DAILY_539 (primary), extensible to BIG_LOTTO / POWER_LOTTO

---

## Design Philosophy

> SB3 is NOT a lottery number predictor.
> SB3 learns a **meta-decision policy**: which validated strategy to deploy, when to skip, and
> how many bets to place — optimizing practical M2+ hit frequency above baseline.

Track A (prediction signals) remain unchanged.
Track B (RL) wraps around Track A as a strategy selector.

---

## 1. Observation Space

### State Vector (39 dimensions, dtype=float32)

**Per-strategy block** (6 strategies × 6 features = 36):
```
For each s in [acb_1bet, midfreq_acb_2bet, acb_markov_midfreq_3bet,
               acb_markov_fourier_3bet, f4cold_3bet, f4cold_5bet]:
  [0] edge_30  = rate_last30  - baseline_s        # short-term edge
  [1] edge_100 = rate_last100 - baseline_s         # medium-term edge
  [2] edge_300 = rate_last300 - baseline_s         # long-term edge (primary)
  [3] sharpe   = edge_300 / std_last300            # risk-adjusted
  [4] z_score  = (rate_30 - rate_300) / se_300    # trend direction
  [5] recent5  = mean(hits for last 5 draws)       # momentum signal
```

**Cross-strategy features** (3):
```
  [36] best_edge_300    = max(edge_300 over all strategies)
  [37] edge_dispersion  = std(edge_300 over all strategies)
  [38] consensus_pos    = fraction of strategies with edge_300 > 0
```

All features are computed from `rolling_monitor` records with strict past-only slicing.
No pre-computed strategy_states are used during training (prevents lookahead bias).

### Observation bounds
```python
observation_space = Box(low=-1.0, high=1.0, shape=(39,), dtype=np.float32)
```
Features clipped to [-1, 1] after normalization.

---

## 2. Action Space

### Discrete(7) actions

| Action | Strategy | Bets | Cost (NT) | M2+ Baseline |
|--------|----------|------|-----------|-------------|
| 0 | **SKIP** | 0 | 0 | 0% |
| 1 | acb_1bet | 1 | 50 | 11.40% |
| 2 | midfreq_acb_2bet | 2 | 100 | 21.54% |
| 3 | acb_markov_midfreq_3bet | 3 | 150 | 30.50% |
| 4 | acb_markov_fourier_3bet | 3 | 150 | 30.50% |
| 5 | f4cold_3bet | 3 | 150 | 30.50% |
| 6 | f4cold_5bet | 5 | 250 | 45.39% |

**Skip logic**: Agent may learn to skip when all strategies show negative short-term edge,
reducing total cost and improving expected ROI per active draw.

---

## 3. Reward Functions

### Primary Reward (edge-normalized)
```python
def reward_edge_normalized(action, outcome):
    if action == 0:
        return -0.02  # small skip penalty → avoid passive policy

    is_hit = outcome[STRATEGIES[action]]['is_m2plus']
    baseline = BASELINES[action]
    num_bets = NUM_BETS[action]

    # Edge fraction: how much above/below random expectation
    edge = (float(is_hit) - baseline) / baseline

    # Cost discount: penalize expensive bets proportionally
    cost_factor = 1.0 / np.sqrt(num_bets)

    return edge * cost_factor
```

**Reward range (approx):**
- 1-bet hit: +7.8 × 0.0327 ≈ +7.8 (rare, high reward)
- 3-bet hit: +2.3 × cost_factor ≈ +1.6
- Miss any: -1.0 × cost_factor
- Skip: -0.02

### Variant B — Payout-aware reward
```python
# Replace baseline with payout-weighted baseline
payout_weights = {1: 1.0, 2: 0.85, 3: 0.75, 5: 0.60}  # marginal value decay
reward = edge * payout_weights[num_bets]
```

### Variant C — Bankroll survival
```python
bankroll = INITIAL_BANKROLL
bankroll -= cost_per_bet
if is_hit:
    bankroll += PAYOUT  # estimated expected payout on M2+
reward = np.log(max(bankroll / INITIAL_BANKROLL, 1e-4))  # log-utility
```

### Variant D — Skip efficiency
```python
# Reward skip only when ALL strategies miss
actual_any_hit = any(outcome[s]['is_m2plus'] for s in ALL_STRATEGIES)
if action == 0:
    reward = 0.05 if not actual_any_hit else -0.10  # good/bad skip
```

---

## 4. Episode Structure

```
Episode = one pass through the training dataset (200 draws)

Step i:
  1. Compute observation from records[0:i] (past only)
  2. Agent selects action a
  3. Environment reveals outcome at draw i for strategy[a]
  4. Compute reward r
  5. Advance to i+1
  6. done = (i == episode_length)
```

**Episode resets**: For training, multiple episodes loop through the same training data
with shuffled starting points to prevent memorization.

---

## 5. Anti-Leakage Protocol

```python
# ENFORCED in env.py:
def _get_observation(self, idx):
    """ONLY reads records[0:idx] — never records[idx] or future."""
    history = {s: self.records[s][:idx] for s in self.STRATEGIES}
    # compute rolling statistics from history only
    return self._compute_features(history)

def step(self, action):
    """Outcome reveals records[self.current_idx] AFTER action is taken."""
    outcome = {s: self.records[s][self.current_idx] for s in self.STRATEGIES}
    reward = self._compute_reward(action, outcome)
    self.current_idx += 1
    obs = self._get_observation(self.current_idx)  # uses updated (past) idx
    return obs, reward, done, truncated, info
```

---

## 6. Walk-Forward Validation Splits

```
Total records: 318

Train:  draws[  0 : 200]  (62.9%) — 114000070 to ~115000014
Val:    draws[200 : 270]  (22.0%) — ~115000015 to ~115000050
Test:   draws[270 : 318]  (15.1%) — ~115000051 to 115000068

Walk-forward:
  Fold 1: train[0:100]   → eval[100:150]
  Fold 2: train[0:150]   → eval[150:200]
  Fold 3: train[0:200]   → eval[200:270]  ← primary validation
  Test:   train[0:270]   → eval[270:318]  ← final OOS
```

---

## 7. Algorithms

### PPO (primary)
```python
PPO(
    "MlpPolicy",
    env,
    learning_rate=3e-4,
    n_steps=200,        # one episode = 200 draws
    batch_size=64,
    n_epochs=10,
    gamma=0.95,         # slightly lower: lottery is short-horizon
    gae_lambda=0.90,
    clip_range=0.2,
    ent_coef=0.05,      # entropy bonus for exploration
    verbose=1,
    seed=42,
    tensorboard_log="./rl_logs/ppo"
)
```

### DQN (secondary)
```python
DQN(
    "MlpPolicy",
    env,
    learning_rate=1e-3,
    buffer_size=5000,
    batch_size=32,
    gamma=0.95,
    exploration_fraction=0.5,   # 50% of training = epsilon-greedy
    exploration_final_eps=0.05,
    train_freq=4,
    target_update_interval=100,
    verbose=1,
    seed=42,
    tensorboard_log="./rl_logs/dqn"
)
```

---

## 8. Evaluation Metrics

| Metric | Definition | Gate |
|--------|-----------|------|
| Hit Rate | M2+ / total active draws | > current_static_baseline |
| Edge % | hit_rate - random_baseline | > 0 (positive) |
| Edge/Cost | edge per NT spent | > static_policy |
| Skip Rate | skipped / total draws | < 30% (if > 30%, likely degenerate) |
| Skip Efficiency | correct_skips / total_skips | > 50% |
| Payout-adj Outcome | hits × fixed_payout - costs | > 0 ideally |
| Max Drawdown | longest consecutive miss streak | < 20 |
| Bankroll Survival | final bankroll > 0 (sim) | > 80% |

**Deployment gate (McNemar):**
RL vs. current best static: p < 0.05 OR risk-adjusted improvement > 10%.

---

## 9. Output Integration

```
quick_predict.py output:
┌──────────────────────────────────────────────────┐
│ TRACK A — Prediction Engine                      │
│   [ACB/MidFreq/Markov/Fourier signal scores]     │
│   → Candidate tickets (as currently)             │
├──────────────────────────────────────────────────┤
│ TRACK B — RL Decision Layer (NEW)                │
│   Chosen action:  acb_markov_midfreq_3bet (a=3)  │
│   Policy score:   0.73 (confidence)              │
│   Skip signal:    NO (active)                    │
│   Rationale:      edge_300=+8.5%, z=+1.2 (ACCEL)│
│   vs static:      SAME STRATEGY (agrees)         │
│   Status:         ADVISORY (not yet deployed)    │
└──────────────────────────────────────────────────┘
```
