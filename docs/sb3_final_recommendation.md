# SB3 RL Decision Layer — Final Recommendation
**Date:** 2026-03-18 | **Research Board Sign-off**
**Verdict: ❌ REJECT — remain EXPERIMENTAL TRACK ONLY**

---

## Executive Summary

Stable-Baselines3 (PPO + DQN) was trained and validated as a meta-decision policy
(Track B) on top of the existing RSM prediction signals for DAILY_539.

**Neither PPO nor DQN achieved all mandatory statistical gates on the held-out test
window (draws [270:318], 48 draws).  The RL layer does NOT improve decision quality
over the current static RSM-based selection.  Deployment is rejected.**

---

## 1. Experiment Setup

| Parameter | Value |
|-----------|-------|
| Lottery | DAILY_539 |
| Total aligned draws | 318 |
| Training window | [30:200] — 170 draws |
| Validation window | [200:270] — 70 draws |
| Test window (OOS) | [270:318] — 48 draws |
| Algorithms | PPO (n_steps=170, ent_coef=0.05) + DQN (buffer=5000) |
| Reward mode | edge-normalized, cost-discounted |
| Seed | 42 (fully reproducible) |
| SB3 environment | `/tmp/sb3_env` — Python 3.13, SB3 2.7.1, Gym 1.2.3, Torch 2.10.0 |

**Strategies available to RL agent (7 actions):**

| Action | Strategy | Bets | M2+ Baseline |
|--------|----------|------|--------------|
| 0 | SKIP | 0 | 0% |
| 1 | acb_1bet | 1 | 11.40% |
| 2 | midfreq_acb_2bet | 2 | 21.54% |
| 3 | acb_markov_midfreq_3bet | 3 | 30.50% |
| 4 | acb_markov_fourier_3bet | 3 | 30.50% |
| 5 | f4cold_3bet | 3 | 30.50% |
| 6 | f4cold_5bet | 5 | 45.39% |

---

## 2. Training Results (Walk-Forward Summary)

| Model | Window | Hit Rate | Avg Baseline | Edge % | Reward |
|-------|--------|----------|--------------|--------|--------|
| PPO | Train | 0.312 | 0.201 | **+11.06%** | +0.551 |
| PPO | Val | 0.171 | 0.139 | **+3.29%** | +0.362 |
| PPO | **Test** | **0.354** | 0.248 | **+10.65%** | +0.429 |
| DQN | Train | 0.503 | 0.290 | **+21.32%** | +0.692 |
| DQN | Val | 0.229 | 0.177 | **+5.20%** | +0.333 |
| DQN | **Test** | **0.375** | 0.308 | **+6.69%** | +0.135 |

**Static baselines on test window:**
| Baseline | Hit Rate | Edge % |
|----------|----------|--------|
| Fixed static (acb_markov_midfreq_3bet) | 0.354 | **+7.0%** |
| Best rolling oracle (past-only 300p) | 0.354 | **+5.29%** |
| Top any fixed static (acb_markov_fourier_3bet) | — | **+11.17%** |

> **Key observation**: The top fixed static strategy (acb_markov_fourier_3bet, +11.17%)
> outperforms PPO (+10.65%) and DQN (+6.69%) on the test window.  RL provides no lift.

---

## 3. Statistical Significance (Test Window)

### 3.1 Permutation Test (Monte Carlo, 1000 permutations)

> Method: Monte Carlo null via Binomial(1, baseline_i) per draw.
> Tests whether RL hit rate is significantly above its own per-action baselines.

| Model | Observed Edge | MC p-value | PB Z-score | PB p-value | Significant? |
|-------|--------------|------------|------------|------------|--------------|
| PPO | +10.65% | **0.0610** | 1.743 | 0.0407 | ❌ MC: NO (p>0.05) |
| DQN | +6.69% | **0.2070** | 1.005 | 0.1575 | ❌ BOTH: NO |

- PPO is borderline (MC p=0.061 misses threshold by 0.011).  Poisson-Binomial
  approximation reaches p=0.041, but the more conservative MC test is the reference.
- DQN is clearly non-significant.

### 3.2 McNemar Test (RL vs Fixed Static Baseline)

| Model | b (RL only) | c (Static only) | Net | p-value | Significant? |
|-------|-------------|-----------------|-----|---------|--------------|
| PPO vs fixed | 5 | 6 | **−1** | 1.0000 | ❌ NO |
| DQN vs fixed | 4 | 4 | **0** | 1.0000 | ❌ NO |

**Both models fail McNemar completely.**  On the 48 test draws, RL does not improve
the number of unique hits vs. the static policy.  Net discordant pairs ≈ 0.

### 3.3 Three-Window Stability

| Model | Train Edge | Val Edge | Test Edge | All Positive | Stable? |
|-------|-----------|---------|----------|--------------|---------|
| PPO | +11.06% | **+3.29%** | +10.65% | ✅ YES | ✅ YES |
| DQN | +21.32% | **+5.20%** | +6.69% | ✅ YES | ✅ YES |

Both models show positive edge across all three windows — but this metric is necessary,
not sufficient.  The large train→val drop (DQN: 21% → 5%) indicates overfitting.

---

## 4. Reward Gaming: Baseline Inflation Audit

PPO learned to frequently select **acb_1bet** (11.4% baseline) — 27% of test draws.
This artificially depresses the average baseline, inflating the reported edge %.

| Metric | PPO | DQN |
|--------|-----|-----|
| RL avg baseline on test | 0.2477 | 0.3081 |
| Uniform strategy baseline | 0.2830 | 0.2830 |
| Gap vs uniform | **−0.0353** | **+0.0251** |
| Baseline inflation detected | ⚠️ **YES** | ✅ NO |
| Honest edge (vs uniform baseline) | **+7.12%** | **+9.20%** |

PPO's headline "+10.65% edge" shrinks to **+7.12% honest edge** when measured against
the uniform baseline — and still fails McNemar (net=−1, zero improvement).

DQN has no inflation (chose mostly 3-bet strategies); its honest edge is +9.20% but
the hit rate is not statistically significant (p=0.207).

---

## 5. Behavioral Analysis

**Neither model learned to skip** (skip rate = 0.00% for both).
The skip action (action 0) was never chosen on the test window.

**PPO action distribution on test (48 draws):**
- action 4 acb_markov_fourier_3bet: 23 draws (48%)
- action 1 acb_1bet: 13 draws (27%) ← reward gaming
- action 3 acb_markov_midfreq_3bet: 9 draws (19%)
- action 2 midfreq_acb_2bet: 3 draws (6%)

**DQN action distribution on test (48 draws):**
- action 3 acb_markov_midfreq_3bet: 22 draws (46%)
- action 4 acb_markov_fourier_3bet: 20 draws (42%)
- action 5 f4cold_3bet: 5 draws (10%)
- action 6 f4cold_5bet: 1 draw (2%)

**Root causes of failure:**
1. **Dataset too small**: 170 train draws, 48 test draws — insufficient for RL convergence
2. **Reward sparsity**: M2+ hit rate ≈ 30% on 3-bet strategies; signal is very noisy
3. **Reward gaming**: Cost-discount factor incentivizes low-bet, low-baseline selections
4. **No skip learning**: Positive rewards for all actions regardless of market conditions
5. **Non-stationarity**: Strategy performance varies across windows; 170 draws is insufficient
   for the agent to learn generalizable state→action mappings

---

## 6. Data Leakage Audit

All components passed the leakage audit:

| Component | Status |
|-----------|--------|
| `compute_rolling_features(draws, idx)` — uses `draws[:idx]` only | ✅ CLEAN |
| `LotteryRLEnv.step()` — outcome revealed AFTER action | ✅ CLEAN |
| `align_records()` — pure sort by draw_id | ✅ CLEAN |
| Walk-forward splits [30:200] / [200:270] / [270:318] | ✅ CLEAN |
| `rollout_best_static()` — uses `draws[:idx]` for rolling edges | ✅ CLEAN |

**No data leakage found.**  The statistical non-significance is genuine, not an artifact
of look-ahead bias being corrected.

---

## 7. Mandatory Gate Checklist

| Gate | Requirement | PPO | DQN |
|------|-------------|-----|-----|
| Three-window stability | All windows edge > 0 | ✅ | ✅ |
| Permutation p < 0.05 | MC null test | ❌ p=0.061 | ❌ p=0.207 |
| McNemar p < 0.05 vs fixed | Significant improvement | ❌ p=1.000 | ❌ p=1.000 |
| No baseline inflation | RL avg baseline ≥ uniform−2pp | ❌ FAIL | ✅ |
| **All gates pass** | **MANDATORY** | **❌ FAIL** | **❌ FAIL** |

> **Note:** Edge improvement alone does NOT replace significance requirements.
> This was explicitly enforced per research protocol update 2026-03-18.

---

## 8. Verdict

### ❌ REJECT

**SB3 does NOT improve lottery decision quality at this time.**

Specifically:
- Hit rate improvement over static baseline is **not statistically significant**
  (PPO: MC p=0.061, DQN: MC p=0.207)
- **Zero McNemar improvement** — RL does not generate unique correct decisions
  that the best static policy misses
- PPO shows **reward gaming** (baseline inflation via low-bet strategy preference)
- Neither model learned **skip behavior**, failing to add cost efficiency
- Overfitting is evident: DQN train edge +21.32% collapses to +5.20% on val

**Current production decision:** Continue using RSM-based static strategy selection
(`acb_markov_midfreq_3bet` as primary 3-bet strategy, `midfreq_acb_2bet` as 2-bet).

---

## 9. SB3 Track Status

| Track | Status | Rationale |
|-------|--------|-----------|
| Track A — RSM prediction signals | ✅ PRODUCTION | Validated, stable, deployed |
| Track B — SB3 RL layer | 🔬 **EXPERIMENTAL ONLY** | All gates failed; no deployment |

**Track B remains modular and removable.**  It does not interfere with Track A.

---

## 10. Re-evaluation Conditions

SB3 may be re-evaluated when **all** of the following are met:

1. **≥200 additional draws available** (dataset grows to ≥518 records)
   - Larger test window → sufficient power for McNemar significance
2. **Reward function redesign** — eliminate cost-discount factor that incentivizes
   low-baseline gaming; use uniform baseline in reward computation
3. **Skip learning fix** — add explicit skip reward calibration tied to market regime
4. **Longer training** — increase `total_timesteps` to ≥50,000 (currently 8,500)
5. **Strategy stability confirmed** — no RSM regime change in interim 200 draws

Earliest re-evaluation checkpoint: **draw 115000268** (~2026-09, +200 draws from now).

---

## 11. Artifacts

| File | Description |
|------|-------------|
| `analysis/rl_decision/env.py` | Gymnasium environment (anti-leakage, 39-dim obs) |
| `analysis/rl_decision/train_sb3.py` | PPO + DQN walk-forward training |
| `analysis/rl_decision/evaluate_sb3.py` | McNemar + permutation tests + audit |
| `analysis/rl_decision/models/ppo_edge.zip` | Trained PPO model (EXPERIMENTAL) |
| `analysis/rl_decision/models/dqn_edge.zip` | Trained DQN model (EXPERIMENTAL) |
| `sb3_walkforward_results.json` | Raw training metrics |
| `sb3_evaluation_results.json` | Statistical test results |
| `sb3_combined_results.json` | Merged training + evaluation |
| `docs/sb3_validation_report.md` | Full validation report with all tables |
| `docs/sb3_final_recommendation.md` | **This document** |

---

*Signed off by LLM Research Board — 2026-03-18*
*Reproducible: seed=42, `/tmp/sb3_env/bin/python3`, SB3 2.7.1*
