# P280AT — BIG 6/49 Strategy Ranking & Portfolio Contribution Replay

- **Final classification:** `P280AT_BIG649_STRATEGY_RANKING_REPLAY_PR_OPEN_NULL_NO_PUBLICATION`
- **Verdict:** `NULL` — historical replay only, NOT a future-success claim.
- **origin/main:** `5e810ec2b427823c9e2de575d429eb2c43b3836d` (PR #463 merged).
- **Canonical digest:** `a905cc7646f54f1e8ec4d64c8a07dce529e5b5455c70baf4c9f09e40a9d3e5db`

> Local research and replay validation ONLY. No prediction-success claim, no strategy promotion, no activation, no publication, no official target/deadline lookup, no pre-draw manifest.

## Dataset
- Source view: `draws_big_lotto_canonical_main` (BIG_LOTTO), read-only `mode=ro` + `query_only=ON`
- Rows: **2117** (96000001 → 115000062); duplicate ids: 0, malformed tickets: 0
- Eligible leakage-free replay targets (≥500 prior draws): **1617**
- DB content drift during read: **False** (main sha256 `539efda5874b08f7…`)

- History cutoff rule: strategy input for target t = draws strictly before t (history[:i]); target outcome never used before scoring
- Leakage guard: strategies receive only {'numbers'} of prior draws; special and future draws are withheld until scoring

## Current 11-ticket strategy pack
- Adapter digest reproduced: `b8ceac657f081bbf2be6ae0fabe6adbce564ea3a4b4cb77ab610035d0e4a800a` — reconciled vs `b8ceac65…`: **True**
- History cutoff `115000062` → synthetic target `115000063` (no official target)

## Prize-aware definition (大樂透 6/49 + special)
- Any-prize: `main_hits >= 3 OR (main_hits == 2 AND special in ticket)`
- Analytic single-ticket any-prize: **3.0952%**; E[main hits] = 0.734694

## Task B — Strategy-level ranking (frozen bet_index=1 primary; replay only)

| Rank | Strategy | long750 prize-win rate | long750 avg hits | stability | marginal contrib |
|---|---|---|---|---|---|
| 1 | `biglotto_deviation_2bet` | 0.0387 | 0.7987 | 0.000 | 0.167 |
| 2 | `fourier30_markov30_biglotto` | 0.0320 | 0.7320 | 0.935 | 0.500 |
| 3 | `bet2_fourier_expansion_biglotto` | 0.0307 | 0.7253 | 0.079 | 0.167 |
| 4 | `biglotto_echo_aware_3bet` | 0.0293 | 0.7320 | 0.516 | 0.167 |
| 5 | `biglotto_ts3_markov_4bet_w30` | 0.0280 | 0.7227 | 0.120 | 0.500 |
| 6 | `ts3_regime_3bet` | 0.0280 | 0.7227 | 0.120 | 0.500 |
| 7 | `biglotto_triple_strike` | 0.0280 | 0.7227 | 0.120 | 0.000 |
| 8 | `coldpool15_biglotto` | 0.0253 | 0.7787 | 0.729 | 0.333 |
| 9 | `cold_complement_biglotto` | 0.0253 | 0.7787 | 0.729 | 0.000 |
| 10 | `markov_2bet_biglotto` | 0.0240 | 0.7653 | 0.717 | 0.500 |
| 11 | `markov_single_biglotto` | 0.0240 | 0.7653 | 0.717 | 0.000 |

Analytic random any-prize baseline = 0.0310. Strategies beating it after Bonferroni: **0** (uncorrected: 0).

## Task C — Current pack contribution ranking (portfolio geometry)

| Rank | Strategy | ticket | unique # | max pair overlap | mean pair overlap | role |
|---|---|---|---|---|---|---|
| 1 | `biglotto_ts3_markov_4bet_w30` | [2, 29, 30, 31, 34, 42] | 3 | 3 | 0.30 | core |
| 2 | `ts3_regime_3bet` | [3, 9, 21, 30, 31, 34] | 3 | 3 | 0.30 | core |
| 3 | `fourier30_markov30_biglotto` | [12, 14, 15, 25, 32, 40] | 3 | 2 | 0.70 | core |
| 4 | `markov_2bet_biglotto` | [16, 19, 20, 36, 45, 47] | 3 | 3 | 0.90 | core |
| 5 | `coldpool15_biglotto` | [6, 7, 11, 12, 18, 41] | 2 | 2 | 0.70 | core |
| 6 | `bet2_fourier_expansion_biglotto` | [8, 12, 37, 38, 44, 46] | 1 | 5 | 0.80 | high-overlap |
| 7 | `biglotto_deviation_2bet` | [6, 16, 20, 22, 47, 48] | 1 | 4 | 1.30 | high-overlap |
| 8 | `biglotto_echo_aware_3bet` | [6, 16, 20, 25, 28, 37] | 1 | 3 | 1.30 | redundant |
| 9 | `markov_single_biglotto` | [11, 14, 18, 22, 25, 39] | 0 | 3 | 0.90 | redundant |
| 10 | `biglotto_triple_strike` | [8, 12, 37, 38, 44, 47] | 0 | 5 | 1.10 | high-overlap |
| 11 | `cold_complement_biglotto` | [16, 20, 22, 25, 39, 47] | 0 | 4 | 1.50 | high-overlap |

Distinct numbers covered by the pack: **35/49** (71.4%). Expected coverage of 11 independent random tickets: **37.3536** — pack beats random coverage: **False**.

## Task D — Fixed-budget portfolio / combination ranking (long_750)

### k = 1
| Method | long750 portfolio win rate | beats equal-budget random | uses outcomes |
|---|---|---|---|
| `top_k_by_historical_replay` | 0.0320 | True | True |
| `equal_budget_random_baseline` | 0.0308 | None | False |
| `diversity_first_low_overlap` | 0.0307 | False | False |
| `hybrid_strategy_plus_diversified_random` | 0.0307 | False | False |
| `marginal_contribution_greedy` | 0.0307 | False | False |
| `diversified_random_baseline` | 0.0301 | None | False |
| `stability_weighted_top_k` | 0.0227 | False | True |

### k = 3
| Method | long750 portfolio win rate | beats equal-budget random | uses outcomes |
|---|---|---|---|
| `hybrid_strategy_plus_diversified_random` | 0.0960 | True | False |
| `diversity_first_low_overlap` | 0.0947 | True | False |
| `marginal_contribution_greedy` | 0.0947 | True | False |
| `diversified_random_baseline` | 0.0908 | None | False |
| `equal_budget_random_baseline` | 0.0904 | None | False |
| `top_k_by_historical_replay` | 0.0773 | False | True |
| `stability_weighted_top_k` | 0.0720 | False | True |

### k = 5
| Method | long750 portfolio win rate | beats equal-budget random | uses outcomes |
|---|---|---|---|
| `hybrid_strategy_plus_diversified_random` | 0.1520 | True | False |
| `diversified_random_baseline` | 0.1508 | None | False |
| `equal_budget_random_baseline` | 0.1459 | None | False |
| `diversity_first_low_overlap` | 0.1227 | False | False |
| `marginal_contribution_greedy` | 0.1227 | False | False |
| `stability_weighted_top_k` | 0.0987 | False | True |
| `top_k_by_historical_replay` | 0.0920 | False | True |

### k = 7
| Method | long750 portfolio win rate | beats equal-budget random | uses outcomes |
|---|---|---|---|
| `diversified_random_baseline` | 0.2109 | None | False |
| `equal_budget_random_baseline` | 0.1987 | None | False |
| `hybrid_strategy_plus_diversified_random` | 0.1867 | False | False |
| `diversity_first_low_overlap` | 0.1333 | False | False |
| `marginal_contribution_greedy` | 0.1333 | False | False |
| `stability_weighted_top_k` | 0.1147 | False | True |
| `top_k_by_historical_replay` | 0.1133 | False | True |

### k = 11
| Method | long750 portfolio win rate | beats equal-budget random | uses outcomes |
|---|---|---|---|
| `diversified_random_baseline` | 0.3083 | None | False |
| `equal_budget_random_baseline` | 0.2932 | None | False |
| `hybrid_strategy_plus_diversified_random` | 0.2507 | False | False |
| `all_11_strategy_pack` | 0.1427 | False | False |
| `diversity_first_low_overlap` | 0.1427 | False | False |
| `marginal_contribution_greedy` | 0.1427 | False | False |
| `stability_weighted_top_k` | 0.1427 | False | True |
| `top_k_by_historical_replay` | 0.1427 | False | True |

## Task E — Baselines & statistical framing
- Analytic 6/49: P(≥3 main) = 0.018638; P(2 main + special) = 0.012314; P(any prize) = 0.030952
- Primary test family: 33 tests; Bonferroni α = 0.001515; BH-FDR max significant rank = 0
- Bonferroni and BH-FDR applied to the primary 33-test family only. The full ranking explores far more comparisons (combination methods x budgets x horizons x metrics); treat all non-primary positives as descriptive, not confirmatory. Retrospective replay cannot confirm a prospective edge.

## Verdict
- Any strategy beats random (uncorrected / Bonferroni): **False / False**
- Any combination beats equal-budget random (mean / beyond MC noise): **True / False**
- Random baseline DOMINATES the strategy pack at k≥3: **True**
- Any combination beats all_11 pack: **True**
- Observation-only candidates beyond MC noise: **0**
- Retrospective historical replay only. NULL = no strategy beats the analytic any-prize random baseline after Bonferroni correction AND no combination beats the equal-budget random baseline beyond Monte-Carlo noise. The few nominal combination wins over the random mean are within one MC standard deviation. At budgets k>=3 the equal-budget and diversified random baselines OUTPERFORM the strategy pack because the frozen primaries are internally redundant (lower distinct-number coverage than independent random tickets). Any observation-only candidate would still require separately authorized prospective / OOS validation before promotion; none is performed here.

## Limitations
- Retrospective historical replay only; not a forward prediction or success-probability estimate.
- Strategy unit is the frozen bet_index=1 primary; multi-bet strategies' additional bets are reflected only via the portfolio combinations (Task D).
- Tiny base rates (any-prize ~3.1% single ticket) make per-window estimates noisy; horizons overlap (recent_100 subset of mid_300 subset of long_750 subset of all_available).
- Walk-forward selection uses an expanding prior window with a 30-target warmup; the first 30 all_available targets are skipped for outcome-based methods.
- Combination significance is descriptive only under heavy multiple testing.
- Canonical DB is a single read-only snapshot; a live writer may change WAL/SHM but no content drift was observed.

## Next recommended research step
- If NULL (expected), proceed to a separately authorized P280AV private ticket-decision runner that consumes this ranking/coverage output without claiming an edge. If observation-only candidates surfaced, they require separately authorized prospective/OOS validation before any promotion. No publication, activation, or post-draw evaluation is authorized by this task.

### Safety assertions
- `prediction_success_claim` = False
- `strategy_promoted` = False
- `activation_authorized` = False
- `registry_mutated` = False
- `official_target_lookup` = False
- `official_deadline_lookup` = False
- `real_publication_performed` = False
- `pre_draw_manifest_created` = False
- `publication_pr_created` = False
- `post_draw_evaluation_started` = False
