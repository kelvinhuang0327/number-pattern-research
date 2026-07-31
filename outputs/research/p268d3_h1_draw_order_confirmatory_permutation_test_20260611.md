# P268D-3 H1 Draw-Order Confirmatory Permutation Test

Generated: 2026-06-11T02:35:49.354163+00:00

## P268D-1 / P268D-2 Boundary

P268D-1 (PR #409, merged) produced the registry-freeze artifact (H1/H1_holdout/H2/H3, status=FROZEN_NOT_TESTED at that time) and the full-history drawNumberAppear backfill artifact (21,682 records, 2007-01..2026-05, 0 pending/error, 100% parse success). P268D-2 (PR #410, merged) ran a structure-validation aggregate (PASS) and a read-only DB alignment audit (PARTIAL_ENV_LIMITATION / NO_LOCAL_ROWS), concluding P268D-3 may proceed using the JSONL artifact (not the local DB) as the H1 data source.

## Hypothesis Registry Pre-Registration

- Registry entry appended (append-only, before H1 computation): `HR-P268D3-H1-DRAW-ORDER-EXIT-RANK-001`
- Status: `PRE_REGISTERED_BEFORE_TEST`
- Registered at: 2026-06-11T02:35:36.435709+00:00
- Registry path: `lottery_api/data/hypothesis_registry.jsonl`

## Data Source Summary

- Source artifact: `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl`
- DB used: False

## Estimation / Holdout Split Summary

| Game | Total | Excluded (2026-04/05) | Eligible | Estimation (70%) | Holdout (30%, sealed) |
|---|---:|---:|---:|---:|---:|
| DAILY_539 | 5876 | 52 | 5824 | 4076 | 1748 |
| BIG_LOTTO | 2139 | 17 | 2122 | 1485 | 637 |
| POWER_LOTTO | 1915 | 17 | 1898 | 1328 | 570 |
| 3_STAR | 5876 | 52 | 5824 | 4076 | 1748 |
| 4_STAR | 5876 | 52 | 5824 | 4076 | 1748 |

- 2026-04 and 2026-05 are excluded from the eligible set (already inspected by P268B).
- The holdout window is **sealed and not used** by any statistic in this task (reserved for H1_holdout, future task).

## H1 Method

Test statistic T = sum over balls b (with n_b >= 1 appearances in the estimation window) of z_b^2, where z_b = (mean_exit_rank_b - mu_k) / sqrt(sigma_k^2 / n_b), mu_k=(k+1)/2, sigma_k^2=(k^2-1)/12. Larger T indicates greater dispersion of per-ball mean exit-rank than expected under full within-draw exchangeability (heterogeneity).

- Null model: Within-draw permutation null: for each draw, the k drawn balls are assigned a uniformly random permutation of exit-ranks 1..k, independently across draws and across Monte Carlo replicates.
- Permutation count: 10000 (target 10000, fallback 1000)
- Lower power fallback used: False
- Seed: 42

## Primary Result: DAILY_539

- Pool: 1-39 (39 balls), k=5
- Estimation-window draws: 4076
- Observed statistic T_obs: 43.169505
- Null distribution (n=10000): mean=39.1475, std=8.9029, p95=54.7356, p99=62.5927
- One-sided permutation p-value: 0.305069
- alpha (pre-registered): 0.01
- Result: **H1_PRIMARY_FAIL**

## Secondary / Exploratory Game Results

**These results are SECONDARY / EXPLORATORY ONLY. They cannot alone promote H1 to PASS, change the H1 classification, or trigger H2/H3.**

| Game | Pool | k | n_draws | T_obs | p-value (one-sided, exploratory) |
|---|---|---:|---:|---:|---:|
| BIG_LOTTO | 1-49 | 7 | 1485 | 43.0864 | 0.705729 |
| POWER_LOTTO | 1-38 | 6 | 1328 | 21.6482 | 0.985401 |
| 3_STAR | 0-9 | 3 | 4076 | 10.3164 | 0.321268 |
| 4_STAR | 0-9 | 4 | 4076 | 6.4838 | 0.683832 |

## Final Classification

`P268D3_H1_DRAW_ORDER_CONFIRMATORY_TEST_COMPLETE_PRIMARY_FAIL`

## Run Booleans

- H2/H3 run in this task: False
- DB write in this task: False
- Hypothesis Registry write in this task: True (append-only, 1 entry)
- Strategy generated in this task: False
- Hit-rate / success-rate improvement claim made: False

## Next-Step Recommendation

H1 estimation-window result FAILED (p >= 0.01) for DAILY_539. Per the registry-freeze, this is a diagnostics-only NULL closure for the draw-order exit-rank-heterogeneity hypothesis: H1_holdout/H2/H3 are NOT opened, and no strategy is proposed from this line.

## Explicit Non-Claims

- No H2 or H3 statistical test was run in this task.
- The holdout window (30%, chronologically most recent eligible draws) was not opened, read for statistics, or used in any computation in this task.
- No production database connection of any kind (read or write) was opened in this script.
- No new strategy was generated and no betting recommendation is made.
- No hit-rate / success-rate-improvement claim is made by this artifact, regardless of the H1 classification.
- Secondary/exploratory game results (BIG_LOTTO, POWER_LOTTO, 3_STAR, 4_STAR) cannot alone promote H1 to PASS or trigger H2/H3.
