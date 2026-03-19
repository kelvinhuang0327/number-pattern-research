# SB3 Walk-Forward Validation Report
**Date:** 2026-03-18 | **Total draws:** 318 | **Test window:** [270:318] (48 draws)

---

## Design

SB3 is a **meta-decision policy** (Track B). It selects which validated strategy
to deploy and when to skip — it does NOT predict raw lottery numbers.

| Split | Range | Draws |
|-------|-------|-------|
| Train | [30:200] | 170 |
| Val   | [200:270] | 70 |
| Test  | [270:318] | 48 |

---

## PPO — reward=edge

### Performance Across Windows

| Window | Draws | Active | Skips | Hit Rate | Baseline | Edge % |
|--------|-------|--------|-------|----------|----------|--------|
| Train | 170 | 170 | 0 | 0.312 | 0.201 | **+11.06%** |
| Val | 70 | 70 | 0 | 0.171 | 0.139 | **+3.29%** |
| Test | 48 | 48 | 0 | 0.354 | 0.248 | **+10.65%** |

### Static Baselines (Test Window)

| Policy | Hits | Active | Hit Rate | Edge % |
|--------|------|--------|----------|--------|
| Fixed static (acb_markov_midfreq_3bet) | 18 | 48 | 0.375 | +7.00% |
| Best rolling static (oracle) | 17 | 48 | 0.354 | +5.29% |

### Three-Window Stability

- Train edge: **+0.1106** | Val: **+0.0329** | Test: **+0.1065**
- All positive: ✅ YES | CV: 0.43 → ✅ STABLE

### Permutation Test (Test Window — Active Draws)

> Method: Monte Carlo null via Binomial(1, baseline_i) per draw.
> Prior bug (label-shuffle) produced p=1.0000 always — now fixed.

- Active draws: 48 | Hits: 17 | Rate: 0.354 | Avg baseline: 0.248
- Observed edge: **+10.65%**
- MC p-value (1000 perms): **0.0610** → ❌ NOT significant
- Poisson-Binomial Z=1.743, p=0.0407 → ✅ p<0.05
- Null 95th pct: +0.1065 | 99th pct: +0.1484

### McNemar Tests (Test Window)

| Comparison | b (RL only) | c (Static only) | Net | p-value | Significant |
|------------|-------------|-----------------|-----|---------|-------------|
| RL vs fixed static | 5 | 6 | -1 | 1.0000 | ❌ |
| RL vs rolling oracle | 6 | 6 | +0 | 1.0000 | ❌ |

### Baseline Inflation Audit

Checks whether RL inflates edge% by systematically selecting low-baseline strategies rather than genuinely predicting better.

| Metric | Value |
|--------|-------|
| RL avg baseline on test | 0.2477 |
| Uniform strategy baseline | 0.283 |
| Gap vs uniform | -0.0354 |
| Dominant action | 4 (acb_markov_fourier_3bet) @ 48% of draws |
| Dominant baseline | 0.305 |
| Inflation detected | ⚠️ YES — edge% is inflated |

> **Honest edge** (vs uniform baseline): **+7.12%**

### Deployment Gate (Tightened)

| Criterion | Required | Result |
|-----------|----------|--------|
| Three-window stability | Mandatory | ✅ |
| Permutation p<0.05 | Mandatory | ✅ |
| McNemar vs fixed p<0.05 | Mandatory | ❌ |
| No baseline inflation | Mandatory | ❌ |

> Note: edge improvement alone does NOT replace significance requirements.

**Deployment decision: 🔴 **FAIL****

---

## DQN — reward=edge

### Performance Across Windows

| Window | Draws | Active | Skips | Hit Rate | Baseline | Edge % |
|--------|-------|--------|-------|----------|----------|--------|
| Train | 170 | 163 | 7 | 0.503 | 0.290 | **+21.32%** |
| Val | 70 | 70 | 0 | 0.229 | 0.177 | **+5.20%** |
| Test | 48 | 48 | 0 | 0.375 | 0.308 | **+6.69%** |

### Static Baselines (Test Window)

| Policy | Hits | Active | Hit Rate | Edge % |
|--------|------|--------|----------|--------|
| Fixed static (acb_markov_midfreq_3bet) | 18 | 48 | 0.375 | +7.00% |
| Best rolling static (oracle) | 17 | 48 | 0.354 | +5.29% |

### Three-Window Stability

- Train edge: **+0.2132** | Val: **+0.0520** | Test: **+0.0669**
- All positive: ✅ YES | CV: 0.66 → ✅ STABLE

### Permutation Test (Test Window — Active Draws)

> Method: Monte Carlo null via Binomial(1, baseline_i) per draw.
> Prior bug (label-shuffle) produced p=1.0000 always — now fixed.

- Active draws: 48 | Hits: 18 | Rate: 0.375 | Avg baseline: 0.308
- Observed edge: **+6.69%**
- MC p-value (1000 perms): **0.2070** → ❌ NOT significant
- Poisson-Binomial Z=1.005, p=0.1575 → ❌ NOT significant
- Null 95th pct: +0.1086 | 99th pct: +0.1711

### McNemar Tests (Test Window)

| Comparison | b (RL only) | c (Static only) | Net | p-value | Significant |
|------------|-------------|-----------------|-----|---------|-------------|
| RL vs fixed static | 4 | 4 | +0 | 1.0000 | ❌ |
| RL vs rolling oracle | 5 | 4 | +1 | 1.0000 | ❌ |

### Baseline Inflation Audit

Checks whether RL inflates edge% by systematically selecting low-baseline strategies rather than genuinely predicting better.

| Metric | Value |
|--------|-------|
| RL avg baseline on test | 0.3081 |
| Uniform strategy baseline | 0.283 |
| Gap vs uniform | +0.0251 |
| Dominant action | 3 (acb_markov_midfreq_3bet) @ 46% of draws |
| Dominant baseline | 0.305 |
| Inflation detected | ✅ NO |

### Deployment Gate (Tightened)

| Criterion | Required | Result |
|-----------|----------|--------|
| Three-window stability | Mandatory | ✅ |
| Permutation p<0.05 | Mandatory | ❌ |
| McNemar vs fixed p<0.05 | Mandatory | ❌ |
| No baseline inflation | Mandatory | ✅ |

> Note: edge improvement alone does NOT replace significance requirements.

**Deployment decision: 🔴 **FAIL****

---

## Data Leakage Audit

| Component | Check | Result |
|-----------|-------|--------|
| `compute_rolling_features(draws, idx)` | Uses `draws[:idx]` only | ✅ CLEAN |
| `LotteryRLEnv.step()` observation | Computed after `current_idx += 1` | ✅ CLEAN |
| `LotteryRLEnv.step()` outcome | Revealed AFTER action taken | ✅ CLEAN |
| `align_records()` | Sort by draw_id, no cross-contamination | ✅ CLEAN |
| Walk-forward splits | Model trained on [30:200], applied to [200:270], [270:318] | ✅ CLEAN |
| `rollout_best_static()` | Uses `draws[:idx]` for rolling edge | ✅ CLEAN |
| `rollout_static()` fixed policy | No state, purely action-constant | ✅ CLEAN |

**Conclusion: No data leakage detected in observation, reward, or baseline logic.**

---

## Overall Recommendation

❌ **REJECT** — No combination passed all mandatory gates.

**Failure reasons:**
- `ppo_edge`: McNemar vs fixed net=-1, p=1.0000 (need <0.05) — no improvement over static policy
- `ppo_edge`: baseline inflation — RL avg baseline 0.248 vs uniform 0.283
- `dqn_edge`: permutation p=0.2070 (need <0.05) — hit rate NOT significantly above baseline
- `dqn_edge`: McNemar vs fixed net=+0, p=1.0000 (need <0.05) — no improvement over static policy

**Decision: Continue with current RSM-based static strategy selection.**
Re-evaluate after ≥200 additional draws (next checkpoint).

> Rationale (L76): passing an edge gate alone is insufficient.
> McNemar significance and permutation p<0.05 are both mandatory.
> RL that merely games the reward function must be rejected.

---

*Generated by `analysis/rl_decision/evaluate_sb3.py` — reproducible with seed=42*