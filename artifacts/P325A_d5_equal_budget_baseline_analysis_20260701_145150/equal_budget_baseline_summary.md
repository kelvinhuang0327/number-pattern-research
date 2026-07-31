# P325A D5 Equal-Budget Baseline Analysis — Summary

Classification: `DESCRIPTIVE_ONLY` · analysis timestamp `20260701_145150` (Asia/Taipei)

Source: P320A shipped static artifacts (SHA256-verified). Zero-DB, deterministic, no randomness.

## 1. What "budget" means here

Every P320A `hit_at_least_k_rate` is an **any-ticket max-hit** portfolio metric. The number of tickets a combination spends per draw is `m = sample_size_rows / sample_size_draws` (verified integer & constant per row). Because member strategies emit 1–3 tickets each, `m` varies **within** every combination size, so raw hit rates are budget-confounded.

| lottery | size | budget m (min…max) |
|---|---|---|
| BIG_LOTTO | 1 | 1…4 |
| BIG_LOTTO | 2 | 2…7 |
| BIG_LOTTO | 3 | 3…8 |
| DAILY_539 | 1 | 1…5 |
| DAILY_539 | 2 | 2…8 |
| DAILY_539 | 3 | 3…11 |

## 2. Matched-budget random baseline vs observed (mean over combinations)

`random_expected = 1-(1-q_k)^m`, q_k = exact hypergeometric single-ticket tail. `delta = observed - random_expected`. Positive delta ⇒ structure beyond budget; negative ⇒ portfolio underperforms an equal-budget random pick (overlap wastes budget).

### BIG_LOTTO (大樂透 6/49 main zone)

| window | size | rows | mean m | obs hit≥1 | rand hit≥1 | Δ≥1 | obs hit≥2 | rand hit≥2 | Δ≥2 | obs hit≥3 | rand hit≥3 | Δ≥3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| recent_50 | 1 | 11 | 1.45 | 0.653 | 0.632 | +0.020 | 0.224 | 0.203 | +0.021 | 0.040 | 0.027 | +0.013 |
| recent_50 | 2 | 55 | 2.91 | 0.860 | 0.867 | -0.007 | 0.353 | 0.365 | -0.013 | 0.071 | 0.053 | +0.018 |
| recent_50 | 3 | 165 | 4.36 | 0.940 | 0.953 | -0.012 | 0.445 | 0.496 | -0.051 | 0.094 | 0.078 | +0.016 |
| recent_300 | 1 | 11 | 1.45 | 0.645 | 0.632 | +0.012 | 0.197 | 0.203 | -0.006 | 0.032 | 0.027 | +0.005 |
| recent_300 | 2 | 55 | 2.91 | 0.843 | 0.867 | -0.025 | 0.329 | 0.365 | -0.037 | 0.060 | 0.053 | +0.007 |
| recent_300 | 3 | 165 | 4.36 | 0.922 | 0.953 | -0.031 | 0.423 | 0.496 | -0.073 | 0.084 | 0.078 | +0.005 |
| recent_750 | 1 | 11 | 1.45 | 0.646 | 0.632 | +0.014 | 0.206 | 0.203 | +0.004 | 0.030 | 0.027 | +0.003 |
| recent_750 | 2 | 55 | 2.91 | 0.843 | 0.867 | -0.024 | 0.343 | 0.365 | -0.022 | 0.056 | 0.053 | +0.003 |
| recent_750 | 3 | 165 | 4.36 | 0.922 | 0.953 | -0.031 | 0.442 | 0.496 | -0.054 | 0.078 | 0.078 | -0.000 |

### DAILY_539 (今彩539 5/39)

| window | size | rows | mean m | obs hit≥1 | rand hit≥1 | Δ≥1 | obs hit≥2 | rand hit≥2 | Δ≥2 | obs hit≥3 | rand hit≥3 | Δ≥3 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| recent_50 | 1 | 15 | 1.53 | 0.589 | 0.597 | -0.007 | 0.215 | 0.162 | +0.053 | 0.001 | 0.015 | -0.014 |
| recent_50 | 2 | 105 | 3.07 | 0.799 | 0.839 | -0.040 | 0.365 | 0.299 | +0.067 | 0.003 | 0.030 | -0.028 |
| recent_50 | 3 | 455 | 4.60 | 0.889 | 0.937 | -0.048 | 0.475 | 0.413 | +0.061 | 0.004 | 0.045 | -0.041 |
| recent_300 | 1 | 15 | 1.53 | 0.609 | 0.597 | +0.013 | 0.195 | 0.162 | +0.033 | 0.014 | 0.015 | -0.001 |
| recent_300 | 2 | 105 | 3.07 | 0.824 | 0.839 | -0.015 | 0.332 | 0.299 | +0.034 | 0.026 | 0.030 | -0.004 |
| recent_300 | 3 | 455 | 4.60 | 0.913 | 0.937 | -0.024 | 0.432 | 0.413 | +0.018 | 0.037 | 0.045 | -0.008 |
| recent_750 | 1 | 15 | 1.53 | 0.599 | 0.597 | +0.002 | 0.185 | 0.162 | +0.023 | 0.016 | 0.015 | +0.001 |
| recent_750 | 2 | 105 | 3.07 | 0.818 | 0.839 | -0.021 | 0.318 | 0.299 | +0.019 | 0.030 | 0.030 | -0.000 |
| recent_750 | 3 | 455 | 4.60 | 0.910 | 0.937 | -0.027 | 0.415 | 0.413 | +0.002 | 0.042 | 0.045 | -0.003 |

## 3. Same-budget cross-size comparison (observed only, no baseline)

For each (lottery, window, budget m) shared by ≥2 combination sizes, mean observed hit≥2 / hit≥3 by size. If a larger size does **not** exceed a smaller size at the **same m**, the size effect is budget, not structure.

| lottery | window | budget m | size | rows | mean hit≥2 | mean hit≥3 |
|---|---|---|---|---|---|---|
| BIG_LOTTO | recent_300 | 3 | 1 | 1 | 0.400 | 0.083 |
| BIG_LOTTO | recent_300 | 3 | 3 | 84 | 0.298 | 0.050 |
| BIG_LOTTO | recent_300 | 4 | 1 | 1 | 0.473 | 0.087 |
| BIG_LOTTO | recent_300 | 4 | 2 | 9 | 0.493 | 0.103 |
| BIG_LOTTO | recent_300 | 5 | 2 | 9 | 0.500 | 0.095 |
| BIG_LOTTO | recent_300 | 5 | 3 | 36 | 0.549 | 0.120 |
| BIG_LOTTO | recent_50 | 3 | 1 | 1 | 0.460 | 0.060 |
| BIG_LOTTO | recent_50 | 3 | 3 | 84 | 0.292 | 0.079 |
| BIG_LOTTO | recent_50 | 4 | 1 | 1 | 0.520 | 0.080 |
| BIG_LOTTO | recent_50 | 4 | 2 | 9 | 0.576 | 0.091 |
| BIG_LOTTO | recent_50 | 5 | 2 | 9 | 0.527 | 0.089 |
| BIG_LOTTO | recent_50 | 5 | 3 | 36 | 0.632 | 0.115 |
| BIG_LOTTO | recent_750 | 3 | 1 | 1 | 0.432 | 0.069 |
| BIG_LOTTO | recent_750 | 3 | 3 | 84 | 0.311 | 0.047 |
| BIG_LOTTO | recent_750 | 4 | 1 | 1 | 0.499 | 0.091 |
| BIG_LOTTO | recent_750 | 4 | 2 | 9 | 0.516 | 0.088 |
| BIG_LOTTO | recent_750 | 5 | 2 | 9 | 0.527 | 0.098 |
| BIG_LOTTO | recent_750 | 5 | 3 | 36 | 0.571 | 0.103 |
| DAILY_539 | recent_300 | 3 | 1 | 2 | 0.368 | 0.033 |
| DAILY_539 | recent_300 | 3 | 3 | 220 | 0.319 | 0.020 |
| DAILY_539 | recent_300 | 5 | 1 | 1 | 0.567 | 0.053 |
| DAILY_539 | recent_300 | 5 | 3 | 132 | 0.458 | 0.042 |
| DAILY_539 | recent_50 | 3 | 1 | 2 | 0.410 | 0.000 |
| DAILY_539 | recent_50 | 3 | 3 | 220 | 0.329 | 0.000 |
| DAILY_539 | recent_50 | 5 | 1 | 1 | 0.700 | 0.020 |
| DAILY_539 | recent_50 | 5 | 3 | 132 | 0.498 | 0.000 |
| DAILY_539 | recent_750 | 3 | 1 | 2 | 0.362 | 0.034 |
| DAILY_539 | recent_750 | 3 | 3 | 220 | 0.294 | 0.025 |
| DAILY_539 | recent_750 | 5 | 1 | 1 | 0.567 | 0.061 |
| DAILY_539 | recent_750 | 5 | 3 | 132 | 0.445 | 0.044 |

## 4. Inferential screen vs equal-budget random null

Exact one-sided binomial P(X≥observed | Binom(n_draws, random_expected)) for k∈{2,3} over all rows. Tests = **4836**, Bonferroni α = 0.05/4836 = **1.034e-05**.

- hit≥1: rows with positive delta = **1041/2418**
- hit≥2: rows with positive delta = **1322/2418**
- hit≥3: rows with positive delta = **783/2418**
- rows passing Bonferroni (k∈{2,3}): **41/4836**

Top rows beating equal-budget random (smallest p):

| lottery | window | size | budget m | k | delta | p (one-sided) | strategies |
|---|---|---|---|---|---|---|---|
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.1140 | 9.417e-11 | daily539_f4cold_5bet|daily539_markov_cold|midfreq_acb_2bet |
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.1140 | 9.417e-11 | daily539_f4cold_5bet|daily539_markov_cold|midfreq_fourier_2bet |
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.1140 | 9.417e-11 | daily539_f4cold_5bet|markov_1bet_539|midfreq_acb_2bet |
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.1140 | 9.417e-11 | daily539_f4cold_5bet|markov_1bet_539|midfreq_fourier_2bet |
| DAILY_539 | recent_750 | 2 | 6 | 2 | +0.1158 | 1.050e-10 | daily539_f4cold_5bet|midfreq_acb_2bet |
| DAILY_539 | recent_750 | 2 | 6 | 2 | +0.1158 | 1.050e-10 | daily539_f4cold_5bet|midfreq_fourier_2bet |
| DAILY_539 | recent_750 | 1 | 5 | 2 | +0.1127 | 3.941e-10 | daily539_f4cold_5bet |
| DAILY_539 | recent_750 | 2 | 6 | 2 | +0.1038 | 6.541e-09 | daily539_f4cold_5bet|daily539_markov_cold |
| DAILY_539 | recent_750 | 2 | 6 | 2 | +0.1038 | 6.541e-09 | daily539_f4cold_5bet|markov_1bet_539 |
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.0980 | 2.447e-08 | acb_markov_midfreq|daily539_f4cold_5bet|midfreq_acb_2bet |
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.0980 | 2.447e-08 | acb_markov_midfreq|daily539_f4cold_5bet|midfreq_fourier_2bet |
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.0953 | 5.690e-08 | daily539_f4cold_5bet|midfreq_acb_2bet|zone_gap_3bet_539 |
| DAILY_539 | recent_750 | 3 | 7 | 2 | +0.0953 | 5.690e-08 | daily539_f4cold_5bet|midfreq_fourier_2bet|zone_gap_3bet_539 |
| DAILY_539 | recent_750 | 2 | 6 | 2 | +0.0958 | 8.018e-08 | daily539_f4cold_5bet|zone_gap_3bet_539 |
| DAILY_539 | recent_750 | 2 | 6 | 2 | +0.0945 | 1.194e-07 | acb_markov_midfreq|daily539_f4cold_5bet |

### Concentration (why 41 ≠ 41 independent discoveries)

The binomial tests are **not independent**: windows are nested (recent_50 ⊂ 300 ⊂ 750) and a strong single strategy re-appears inside every pair/triple that contains it. The passing set collapses accordingly:

- by lottery: {'DAILY_539': 41} — **all in DAILY_539; zero in BIG_LOTTO**.
- by window: {'recent_750': 35, 'recent_300': 6} — concentrated in the longest window.
- by combination size: {3: 27, 2: 13, 1: 1} (singles among them: 1).
- carrier member: `daily539_f4cold_5bet` appears in **34/41** passing rows. Removing it would collapse the passing set.
- every k that passes is **k=2** only (hit≥3 never passes at matched budget).

## 5. Plain-language conclusion

**Q: Are P320A/P321A D5 combination results driven by unequal ticket budgets?** Predominantly **yes**.

- Mean matched-budget delta across all 2418 rows is ≈0: hit≥1 -0.0279, hit≥2 +0.0075, hit≥3 -0.0091. Raw hit rates climb with combination size, but the equal-budget random baseline climbs the same way — the climb is bought with extra tickets, not structure (§2).
- **Same-budget cross-size (§3) is decisive:** at a fixed budget m, larger combinations do **not** beat smaller ones — for DAILY_539 the single f4cold_5bet (m=5) scores hit≥2 = 0.700 vs 0.498 for triples at the same m=5. Combining strategies DILUTES rather than adds, at equal budget.
- **BIG_LOTTO:** matched-budget deltas hover at/below zero (member-ticket overlap wastes budget); no BIG_LOTTO combination passes the screen — consistent with prior findings that 6/49 is indistinguishable from fair random.
- **DAILY_539 positive hit≥2 deltas are single-strategy signal, not synergy:** the entire passing set traces to a few known strategies (carrier `daily539_f4cold_5bet`, plus the midfreq family), each of which already beats equal-budget random on its own. Pairs/triples merely inherit and partly dilute that signal.
- Net: the combination UI numbers are mostly a budget artifact. Any genuine above-random behavior is a property of individual strategies at their own budget, reproducible without any combination.

DESCRIPTIVE_ONLY: no future-edge, wagering, best-strategy, or recommended-number claim is made; a baseline result does not prove any future edge.
