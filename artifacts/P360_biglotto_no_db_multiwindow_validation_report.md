# P360 Big Lotto no-DB Multi-window Walk-forward Validation (parity tier only)

## Scope statements

- This is historical descriptive validation only.
- No future prediction guarantee. Past hit rates do not predict future draws.
- No betting advice. Nothing here recommends placing any bet.
- No DB was opened or written. The only data source is the committed JSONL fixture below.
- No blended leaderboard: P356/P358 baseline strategies are excluded from every table in this report.
- Shape/safety-only adapters and blocked targets were excluded from scoring: `adapt_biglotto_10bet_combined`, `adapt_biglotto_5bet_orthogonal`, `adapt_biglotto_zonal_pruning`, `adapt_predict_biglotto_regime_3bet`.

## Method

- Fixture: `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl`
- Fixture SHA256: `f4accb6f527694e739689242c929e87e4b031a364becb4fadb4aaea50ef2e3f8`
- BIG_LOTTO rows: 2139 (validated; 6 unique ascending mains in 1-49, special in 1-49)
- Walk-forward: fixed 520-draw trailing lookback; each adapter scored against the next draw only; 1619 scoreable periods; no future leakage, no parameter tuning, no randomization.
- Hit definition: any ticket matching >= 3 main numbers.
- Baseline: `1 - (1 - 0.0186375) ** bet_count` — an independent-ticket approximation (real tickets within a strategy overlap, so this is approximate context, not proof of edge).
- Trailing evaluation windows: 30, 150, 750, 1500 periods.
- Null expectation (pre-registered): prior L90/L91 evidence found BIG_LOTTO indistinguishable from fair random, so edge is expected to be approximately zero in every window.

## Included adapters (parity tier)

| adapter_function | strategy_id | bet_count | parity_status |
| --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | biglotto_p0_2bet | 2 | PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS |
| adapt_predict_biglotto_echo_2bet | predict_biglotto_echo_2bet | 2 | PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS |
| adapt_predict_biglotto_echo_phase2_2bet | predict_biglotto_echo_phase2 | 2 | PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS |
| adapt_predict_biglotto_echo_phase2_3bet | predict_biglotto_echo_phase2 | 3 | PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS |
| adapt_predict_biglotto_echo_mixed_3bet | predict_biglotto_echo_mixed_3bet | 3 | PARITY_ACCEPTABLE_FOR_NO_DB_HARNESS |

## Results by trailing window

### Trailing 30 periods

| adapter_function | bet_count | hit_count | hit_rate | same_bet_count_baseline | edge_vs_same_bet_count_baseline | positive_edge |
| --- | --- | --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | 2 | 0 | 0.00000000 | 0.03692764 | -0.03692764 | false |
| adapt_predict_biglotto_echo_2bet | 2 | 1 | 0.03333333 | 0.03692764 | -0.00359431 | false |
| adapt_predict_biglotto_echo_phase2_2bet | 2 | 1 | 0.03333333 | 0.03692764 | -0.00359431 | false |
| adapt_predict_biglotto_echo_phase2_3bet | 3 | 2 | 0.06666667 | 0.05487690 | 0.01178976 | true |
| adapt_predict_biglotto_echo_mixed_3bet | 3 | 2 | 0.06666667 | 0.05487690 | 0.01178976 | true |

### Trailing 150 periods

| adapter_function | bet_count | hit_count | hit_rate | same_bet_count_baseline | edge_vs_same_bet_count_baseline | positive_edge |
| --- | --- | --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | 2 | 4 | 0.02666667 | 0.03692764 | -0.01026098 | false |
| adapt_predict_biglotto_echo_2bet | 2 | 6 | 0.04000000 | 0.03692764 | 0.00307236 | true |
| adapt_predict_biglotto_echo_phase2_2bet | 2 | 6 | 0.04000000 | 0.03692764 | 0.00307236 | true |
| adapt_predict_biglotto_echo_phase2_3bet | 3 | 11 | 0.07333333 | 0.05487690 | 0.01845643 | true |
| adapt_predict_biglotto_echo_mixed_3bet | 3 | 11 | 0.07333333 | 0.05487690 | 0.01845643 | true |

### Trailing 750 periods

| adapter_function | bet_count | hit_count | hit_rate | same_bet_count_baseline | edge_vs_same_bet_count_baseline | positive_edge |
| --- | --- | --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | 2 | 36 | 0.04800000 | 0.03692764 | 0.01107236 | true |
| adapt_predict_biglotto_echo_2bet | 2 | 36 | 0.04800000 | 0.03692764 | 0.01107236 | true |
| adapt_predict_biglotto_echo_phase2_2bet | 2 | 36 | 0.04800000 | 0.03692764 | 0.01107236 | true |
| adapt_predict_biglotto_echo_phase2_3bet | 3 | 51 | 0.06800000 | 0.05487690 | 0.01312310 | true |
| adapt_predict_biglotto_echo_mixed_3bet | 3 | 52 | 0.06933333 | 0.05487690 | 0.01445643 | true |

### Trailing 1500 periods

| adapter_function | bet_count | hit_count | hit_rate | same_bet_count_baseline | edge_vs_same_bet_count_baseline | positive_edge |
| --- | --- | --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | 2 | 69 | 0.04600000 | 0.03692764 | 0.00907236 | true |
| adapt_predict_biglotto_echo_2bet | 2 | 67 | 0.04466667 | 0.03692764 | 0.00773902 | true |
| adapt_predict_biglotto_echo_phase2_2bet | 2 | 62 | 0.04133333 | 0.03692764 | 0.00440569 | true |
| adapt_predict_biglotto_echo_phase2_3bet | 3 | 88 | 0.05866667 | 0.05487690 | 0.00378976 | true |
| adapt_predict_biglotto_echo_mixed_3bet | 3 | 97 | 0.06466667 | 0.05487690 | 0.00978976 | true |

## Cohort coverage (parity tier only, full scoreable range)

| adapter_a | adapter_b | both_hit_count | union_hit_count | jaccard |
| --- | --- | --- | --- | --- |
| adapt_biglotto_p0_2bet | adapt_predict_biglotto_echo_2bet | 9 | 135 | 0.06666667 |
| adapt_biglotto_p0_2bet | adapt_predict_biglotto_echo_phase2_2bet | 10 | 130 | 0.07692308 |
| adapt_biglotto_p0_2bet | adapt_predict_biglotto_echo_phase2_3bet | 10 | 159 | 0.06289308 |
| adapt_biglotto_p0_2bet | adapt_predict_biglotto_echo_mixed_3bet | 9 | 168 | 0.05357143 |
| adapt_predict_biglotto_echo_2bet | adapt_predict_biglotto_echo_phase2_2bet | 64 | 74 | 0.86486486 |
| adapt_predict_biglotto_echo_2bet | adapt_predict_biglotto_echo_phase2_3bet | 64 | 103 | 0.62135922 |
| adapt_predict_biglotto_echo_2bet | adapt_predict_biglotto_echo_mixed_3bet | 71 | 104 | 0.68269231 |
| adapt_predict_biglotto_echo_phase2_2bet | adapt_predict_biglotto_echo_phase2_3bet | 67 | 96 | 0.69791667 |
| adapt_predict_biglotto_echo_phase2_2bet | adapt_predict_biglotto_echo_mixed_3bet | 64 | 107 | 0.59813084 |
| adapt_predict_biglotto_echo_phase2_3bet | adapt_predict_biglotto_echo_mixed_3bet | 92 | 108 | 0.85185185 |

| adapter_a | unique_hit_count | total_hit_count |
| --- | --- | --- |
| adapt_biglotto_p0_2bet | 63 | 73 |
| adapt_predict_biglotto_echo_2bet | 0 | 71 |
| adapt_predict_biglotto_echo_phase2_2bet | 0 | 67 |
| adapt_predict_biglotto_echo_phase2_3bet | 1 | 96 |
| adapt_predict_biglotto_echo_mixed_3bet | 5 | 104 |

| scope | cohort_any_hit_count |
| --- | --- |
| trailing_30 | 2 |
| trailing_150 | 15 |
| trailing_750 | 86 |
| trailing_1500 | 160 |
| trailing_1619 | 171 |

## Excluded cohorts

- Shape/safety-only adapters (`PARITY_PARTIAL_SHAPE_ONLY`) and blocked targets: excluded from scoring.
- P356 baseline strategies: excluded from scoring and from every table above; prior P356 evidence lives in its own artifacts and is intentionally not blended here.
