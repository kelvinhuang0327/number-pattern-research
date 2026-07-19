# P20S All-Strategies Bulk Recovery Backtest

Status: **COMPLETED**.

This is a historical empirical research result for entertainment and audit use. It is not a future winning probability, betting recommendation, or strategy promotion.

## Exact denominator

- Unique governed Big Lotto strategy identities: 39
- Non-baseline evidence records: 607
- Random comparison baselines: 1
- Aliases: 2
- Equivalent implementations: 3
- Independent algorithms after alias/equivalence collapse: 34

The denominator rule admits current registry/P24 governed IDs, a proven ID-reuse split, reviewed P20C historical identities, and explicit P357/P358 recovery identities. Source files, helper functions, fixtures, composite DB scopes, publication runners, and evidence gaps remain in the resolution ledger but do not inflate the strategy count.

## Execution outcome

- Previously complete strategies: 14
- Newly recovered standard backtests: 4
- Complete native 20-ticket identities: 2
- Complete adapter-assisted identities: 16
- Total complete identities: 18
- Partial shape/parity results: 4
- Conclusive alias/equivalence/document/safety exclusions: 5
- Missing implementations: 12
- External state not reproducible: 0
- Remaining engineering backlog: 16

## Historical backtest contract

- Canonical draws: 2125
- Common window after 100 prior draws: 2025
- Constructor: strategy_preserving_20_ticket/v1
- Exactly 20 unique legal tickets per completed draw/replicate portfolio
- Ten deterministic random-baseline replicates; deterministic strategies use one replicate
- Random M4+ rate: 2.034568%

## Random comparison

Strategies whose paired 95% historical interval is strictly above zero: 0.
No historical confidence interval is interpreted as a future advantage. Multiple comparisons, shared histories, and correlated strategy families remain material limitations.

## Equivalent and alias families

- core_satellite_family: history::lottery_api/models/core_satellite.py, core_satellite_biglotto
- social_wisdom_family: history::lottery_api/models/social_wisdom_predictor.py, biglotto_social_wisdom_anti_popularity
- ts3_acb_aliases: biglotto_ts3_acb_4bet, ts3_acb_4bet_biglotto
- ts3_markov_freq_aliases: biglotto_ts3_markov_freq_5bet, ts3_markov_freq_5bet_biglotto
- zone_split_family: history::lottery_api/models/zone_split.py, biglotto_zone_split_3bet_bet1

Aliases and equivalent implementations are excluded from independent-evidence counts and valid rankings.

## Remaining engineering backlog

- acb_hot_fourier_3bet_biglotto
- apriori_3bet_biglotto
- bet2_fourier_expansion_biglotto@rejected_json_historical
- biglotto_10bet_combined
- biglotto_5bet_orthogonal
- biglotto_ts3_acb_4bet
- biglotto_ts3_markov_freq_5bet
- biglotto_zonal_pruning
- cluster_pivot_biglotto
- gap_dynamic_threshold_biglotto
- hot_gap_return_biglotto
- hot_stop_rebound_biglotto
- markov_repeat_exception_biglotto
- multiwindow_fourier_biglotto
- neighbor_injection_biglotto
- predict_biglotto_regime

No resource boundary was reached; next unprocessed strategy: null.

## Data quality and verification

The immutable read-only source contained 3150 raw Big Lotto rows, 2125 canonical rows, and 1025 excluded noncanonical rows. Duplicate IDs/dates, malformed number rows, range errors, negative financial fields, and cutoff violations were all checked. Positional-order fields are null and were not treated as signal.

Validation status: PASS.

> Out of 39 Big Lotto strategy identities, 18 completed the standard 20-ticket historical backtest, 5 were conclusively excluded, and 16 still require implementation work.
