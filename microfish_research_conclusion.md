# MicroFish Research Conclusion
## 2026-03-15

### Executive Summary
- Feature space: 221 features across 13 families
- Strategy candidates: 10000 evaluated via evolutionary search
- Validated strategies: 30 pass all gates (3-window + perm p<0.05)
- Micro-edges: 74 features with lift >= 1.02
- Best evolved edge: +4.93% (vs ACB baseline +2.60%)
- MicroFish outperforms current system: YES

### Phase Results
| Phase | Time | Output |
|-------|------|--------|
| Phase 2: Features | 48s | 221 features |
| Phase 3: Evolution | 47s | 10000 candidates |
| Phase 4: Validation | 16s | 30 validated |
| Phase 5: Micro-Edge | 1s | 74 edges |
| Phase 6: Combos | 1s | 122 positive |
| **Total** | **114s** | |

### Best Evolved Strategy
- Features: ['freq_zscore_80', 'freq_raw_150', 'freq_zscore_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_sq_entropy_binary_100']
- Weights: [0.10419047784039072, 0.14800937134180914, 0.1503555479528559, 0.06461303008259887, 0.08603002547381224, 0.1460586397447596, 0.1890333867886392, 0.11170952077513423]
- Edge: +4.93%

### Feature Family Coverage
{
  "freq": 27,
  "gap": 27,
  "parity": 18,
  "zone": 27,
  "sum": 18,
  "tail": 18,
  "consec": 9,
  "markov": 9,
  "fourier": 3,
  "entropy": 18,
  "ac": 3,
  "ix": 20,
  "nl": 24
}

### Micro-Edge Top 10
- freq_deficit_100: lift=1.234, edge=+2.67%
- entropy_inverted_100: lift=1.234, edge=+2.67%
- ix_freq_deficit_100_x_ac_mean_100: lift=1.234, edge=+2.67%
- ix_sum_mean_100_x_freq_deficit_100: lift=1.234, edge=+2.67%
- nl_log_freq_deficit_100: lift=1.234, edge=+2.67%
- nl_sqrt_freq_deficit_100: lift=1.234, edge=+2.67%
- nl_sq_freq_deficit_100: lift=1.234, edge=+2.67%
- nl_tanh_freq_deficit_100: lift=1.234, edge=+2.67%
- ix_freq_deficit_100_x_entropy_binary_100: lift=1.228, edge=+2.60%
- fourier_phase: lift=1.216, edge=+2.47%


### Validated Strategies
- #1: ['freq_zscore_80', 'freq_raw_150', 'freq_zscore_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_sq_entropy_binary_100'], edge_1500=+4.93%, perm_p=0.005
- #2: ['freq_zscore_80', 'freq_raw_150', 'freq_zscore_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100'], edge_1500=+4.80%, perm_p=0.005
- #3: ['freq_raw_150', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.80%, perm_p=0.005
- #4: ['freq_raw_150', 'entropy_binary_20', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #5: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #6: ['freq_raw_150', 'entropy_binary_20', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #7: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #8: ['freq_zscore_80', 'freq_raw_150', 'parity_even_rate_80', 'tail_entropy_10', 'markov_lag1_30', 'ix_freq_deficit_100_x_ac_mean_100'], edge_1500=+4.73%, perm_p=0.005
- #9: ['freq_zscore_80', 'freq_raw_150', 'zone_deficit_80', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #10: ['freq_zscore_80', 'freq_raw_150', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #11: ['freq_raw_150', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100', 'nl_tanh_markov_lag1_100'], edge_1500=+4.73%, perm_p=0.005
- #12: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #13: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'markov_lag1_30', 'ix_freq_deficit_100_x_ac_mean_100'], edge_1500=+4.73%, perm_p=0.005
- #14: ['freq_zscore_80', 'freq_raw_150', 'markov_lag3_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.73%, perm_p=0.005
- #15: ['freq_raw_150', 'tail_entropy_10', 'ix_freq_raw_100_x_markov_lag1_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.67%, perm_p=0.005
- #16: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100'], edge_1500=+4.67%, perm_p=0.005
- #17: ['freq_raw_150', 'tail_entropy_10', 'entropy_binary_80', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100', 'nl_tanh_markov_lag1_100'], edge_1500=+4.67%, perm_p=0.005
- #18: ['freq_raw_150', 'markov_lag3_300', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.67%, perm_p=0.005
- #19: ['freq_raw_150', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.67%, perm_p=0.005
- #20: ['freq_zscore_80', 'freq_raw_150', 'markov_lag2_30', 'markov_lag3_100', 'ix_freq_deficit_100_x_ac_mean_100'], edge_1500=+4.67%, perm_p=0.005
- #21: ['freq_raw_150', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.53%, perm_p=0.005
- #22: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100'], edge_1500=+4.53%, perm_p=0.005
- #23: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'entropy_binary_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.53%, perm_p=0.005
- #24: ['freq_raw_150', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.53%, perm_p=0.005
- #25: ['freq_zscore_80', 'freq_raw_150', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.53%, perm_p=0.005
- #26: ['freq_zscore_80', 'freq_raw_150', 'zone_deficit_200', 'tail_entropy_10', 'ix_freq_deficit_100_x_ac_mean_100'], edge_1500=+4.47%, perm_p=0.005
- #27: ['freq_zscore_80', 'freq_raw_150', 'tail_entropy_10', 'markov_lag3_100', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_gap_ratio_100'], edge_1500=+4.47%, perm_p=0.005
- #28: ['freq_zscore_80', 'freq_raw_150', 'zone_deficit_80', 'ix_gap_ratio_100_x_zone_deficit_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_tanh_freq_deficit_100'], edge_1500=+4.47%, perm_p=0.005
- #29: ['freq_zscore_80', 'freq_raw_150', 'ix_freq_raw_100_x_markov_lag1_100', 'ix_freq_deficit_100_x_ac_mean_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.40%, perm_p=0.005
- #30: ['freq_raw_150', 'entropy_binary_20', 'ix_freq_raw_100_x_markov_lag1_100', 'nl_sq_freq_deficit_100'], edge_1500=+4.40%, perm_p=0.005

### Key Findings
1. MicroFish discovered strategies that outperform the current ACB system.
2. The evolutionary search converged by generation 50, with diminishing improvements after generation ~25.
3. 74 individual features show measurable lift (>= 1.02), suggesting the signal space is not fully exhausted.
4. Feature interactions did partially improve over single features.

### Limitations
1. Single-bet (1-bet) evaluation only; multi-bet portfolio not tested
2. 8-feature max per strategy = bounded combinatorial complexity
3. Evolutionary search: 200 pop x 50 gen = 10000 evaluations
4. Permutation test resolution: 200 shuffles (min p = 0.0050)
5. No neural/gradient-boosting models; linear score aggregation only

### Future Research Directions
1. Multi-bet evolutionary optimization (2-bet, 3-bet portfolio)
2. Conditional strategy activation (regime-dependent feature selection)
3. Gradient boosting models (XGBoost/LightGBM) as score aggregators
4. Genetic programming for automated feature construction
5. Seasonal decomposition features (day-of-week, month effects)
6. Expanding test window beyond 1500 periods for stronger significance

### Deliverables
- expanded_feature_space.json
- strategy_population.json
- validated_strategy_set.json
- micro_edge_catalog.json
- strategy_combination_results.json
- microfish_research_conclusion.md
