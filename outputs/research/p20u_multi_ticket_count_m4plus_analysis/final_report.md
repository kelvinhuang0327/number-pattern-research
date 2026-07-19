# P20U Big Lotto 10/15/20-Ticket M4+ Analysis

All 30 completed governed strategies were evaluated over the same 2,025 historical target draws. Each 10- and 15-ticket portfolio is a prefix of the exact ordered 20-ticket portfolio; the random baseline uses the same nesting and ticket count. All nesting, M4+ monotonicity, and P20T 20-ticket parity gates passed.

This is descriptive historical research for entertainment purposes only. It is not a future winning probability, betting recommendation, profitability analysis, or production guarantee.

## Historical rates by strategy

Each cell is strategy M4+ rate followed by the same-count random rate in parentheses.

| Strategy | 10 tickets | 15 tickets | 20 tickets |
|---|---:|---:|---:|
| `acb_hot_fourier_3bet_biglotto` | 1.3333% (1.0370%) | 1.5309% (1.5309%) | 1.7778% (2.0346%) |
| `apriori_3bet_biglotto` | 0.6420% (1.0370%) | 0.9877% (1.5309%) | 1.2840% (2.0346%) |
| `bet2_fourier_expansion_biglotto@p42_p280_frozen_code` | 0.8889% (1.0370%) | 1.4321% (1.5309%) | 1.6296% (2.0346%) |
| `biglotto_10bet_combined` | 0.7901% (1.0370%) | 1.3827% (1.5309%) | 1.7778% (2.0346%) |
| `biglotto_5bet_orthogonal` | 0.7407% (1.0370%) | 1.2346% (1.5309%) | 1.6296% (2.0346%) |
| `biglotto_deviation_2bet` | 0.7901% (1.0370%) | 1.2346% (1.5309%) | 1.5802% (2.0346%) |
| `biglotto_echo_aware_3bet` | 0.9877% (1.0370%) | 1.4815% (1.5309%) | 2.1235% (2.0346%) |
| `biglotto_p0_2bet` | 0.6914% (1.0370%) | 1.0370% (1.5309%) | 1.2840% (2.0346%) |
| `biglotto_triple_strike` | 0.8889% (1.0370%) | 1.3827% (1.5309%) | 2.0247% (2.0346%) |
| `biglotto_ts3_acb_4bet` | 1.2840% (1.0370%) | 1.7778% (1.5309%) | 2.3704% (2.0346%) |
| `biglotto_ts3_markov_4bet_w30` | 0.6420% (1.0370%) | 1.1852% (1.5309%) | 1.7284% (2.0346%) |
| `biglotto_ts3_markov_freq_5bet` | 1.0864% (1.0370%) | 1.5802% (1.5309%) | 2.0741% (2.0346%) |
| `cluster_pivot_biglotto` | 0.7407% (1.0370%) | 1.4321% (1.5309%) | 1.8272% (2.0346%) |
| `cold_complement_biglotto` | 0.8889% (1.0370%) | 1.5309% (1.5309%) | 2.0247% (2.0346%) |
| `coldpool15_biglotto` | 0.9877% (1.0370%) | 1.4815% (1.5309%) | 1.9259% (2.0346%) |
| `fourier30_markov30_biglotto` | 0.8395% (1.0370%) | 1.1852% (1.5309%) | 1.5309% (2.0346%) |
| `gap_dynamic_threshold_biglotto` | 0.7407% (1.0370%) | 1.0864% (1.5309%) | 1.6790% (2.0346%) |
| `history::lottery_api/models/core_satellite.py` | 0.9637% (1.0370%) | 1.4381% (1.5309%) | 1.7791% (2.0346%) |
| `history::lottery_api/models/social_wisdom_predictor.py` | 1.0025% (1.0370%) | 1.4667% (1.5309%) | 1.9802% (2.0346%) |
| `history::lottery_api/models/zone_split.py` | 0.6519% (1.0370%) | 1.0519% (1.5309%) | 1.5506% (2.0346%) |
| `hot_stop_rebound_biglotto` | 0.6914% (1.0370%) | 0.9877% (1.5309%) | 1.5309% (2.0346%) |
| `markov_2bet_biglotto` | 0.7901% (1.0370%) | 1.2840% (1.5309%) | 1.8765% (2.0346%) |
| `markov_repeat_exception_biglotto` | 0.9877% (1.0370%) | 1.4815% (1.5309%) | 1.8272% (2.0346%) |
| `markov_single_biglotto` | 0.5926% (1.0370%) | 0.9877% (1.5309%) | 1.5309% (2.0346%) |
| `neighbor_injection_biglotto` | 0.8395% (1.0370%) | 1.0370% (1.5309%) | 1.2840% (2.0346%) |
| `predict_biglotto_echo_2bet` | 0.8889% (1.0370%) | 1.4321% (1.5309%) | 1.7778% (2.0346%) |
| `predict_biglotto_echo_phase2` | 0.7407% (1.0370%) | 1.2346% (1.5309%) | 1.6790% (2.0346%) |
| `predict_biglotto_mixed_3bet` | 1.0864% (1.0370%) | 1.6296% (1.5309%) | 1.9753% (2.0346%) |
| `predict_biglotto_regime` | 0.8889% (1.0370%) | 1.5309% (1.5309%) | 1.9753% (2.0346%) |
| `ts3_regime_3bet` | 0.7901% (1.0370%) | 1.0864% (1.5309%) | 1.5802% (2.0346%) |

## Answers

1. The complete per-strategy rates are in the table above and `strategy_ticket_count_metrics.csv` (90 strategy/count rows).
2. Same-count random rates were 10 tickets: 1.0370%; 15 tickets: 1.5309%; 20 tickets: 2.0346%.
3. Strategies descriptively above random: 10 tickets = 4; 15 tickets = 3; 20 tickets = 3. Descriptive uplift is not confirmatory evidence.
4. Strategies surviving the frozen Bonferroni confirmatory rule: 10 tickets = 0; 15 tickets = 0; 20 tickets = 0.
5. The largest 10→15 historical gain was `cluster_pivot_biglotto` at 0.6914%; all 30 results and uncertainty intervals are in `marginal_gain_10_to_15.csv`.
6. The largest 15→20 historical gain was `biglotto_triple_strike` at 0.6420%; all results are in `marginal_gain_15_to_20.csv`.
7. Positive strategy-minus-random marginal differences occurred for 8/30 strategies at 10→15, 9/30 at 15→20, and 8/30 at 10→20. The paired intervals determine uncertainty.
8. The five-ticket marginal leaders are `cluster_pivot_biglotto` for 10→15 and `biglotto_triple_strike` for 15→20.
9. 15 strategies had a smaller 15→20 increment than 10→15; this is the report's descriptive definition of diminishing marginal improvement.
10. The highest M4+ rate per ticket was `acb_hot_fourier_3bet_biglotto` at 10 tickets, `biglotto_ts3_acb_4bet` at 15, and `biglotto_ts3_acb_4bet` at 20. These are hit-rate efficiency measures, not financial returns.
11. Nested M4+ monotonicity passed for every strategy and the random baseline (31/31 detail groups).
12. The 20-ticket slice reproduced P20T: metric parity = True, portfolio-hash parity = True, random parity = True, ranking parity = True.
13. The multiplicity-adjusted conclusion about credible historical advantage did not change; the earlier P20T result had zero credible 20-ticket advantages. No historical conclusion establishes future predictive advantage.
14. Apparent leaders tied to governed alias/equivalence groups: `biglotto_ts3_acb_4bet` (ts3_acb_aliases, 10 tickets), `biglotto_ts3_acb_4bet` (ts3_acb_aliases, 15 tickets), `biglotto_ts3_acb_4bet` (ts3_acb_aliases, 20 tickets), `biglotto_ts3_markov_freq_5bet` (ts3_markov_freq_aliases, 10 tickets), `biglotto_ts3_markov_freq_5bet` (ts3_markov_freq_aliases, 15 tickets), `biglotto_ts3_markov_freq_5bet` (ts3_markov_freq_aliases, 20 tickets), `history::lottery_api/models/social_wisdom_predictor.py` (social_wisdom_family, 10 tickets). Group members are not counted as independent confirmation.
15. Across strategies, the mean historical M4+ rate rose from 0.8626% at 10 tickets to 1.3204% at 15 and 1.7540% at 20. More tickets mechanically expand coverage, while the marginal files show how much additional historical success the extra prefixes supplied.
16. This analysis cannot establish future win probabilities, causal predictive skill, expected profit, ticket affordability, an optimal spend, or a production guarantee. It also does not justify strategy promotion.

## Reproducibility and verification

- Historical draw portfolios: 346230 count-specific strategy portfolios across the three ticket counts.
- Confirmatory family: unique independent_algorithm_id x ticket_count across the frozen 30-strategy universe and ticket counts 10,15,20; one-sided exact draw-cluster sign-flip p-values; credible adjusted advantage requires paired CI lower bound > 0 and Bonferroni-adjusted p < 0.05; BH-FDR is reported as a secondary adjustment.
- Tests: 158 passed, 0 failed, 0 skipped, 0 deselected.
- Large ticket detail was independently recomputed, used for aggregate reproduction, and removed after successful byte reproduction; only compact evidence is committed.

Across 30 completed governed Big Lotto strategies, the historical portfolio-level M4+ rates were evaluated at 10, 15 and 20 tickets using nested portfolios and same-ticket-count random baselines. These results describe historical behavior only and do not establish future winning probabilities or betting profitability.
