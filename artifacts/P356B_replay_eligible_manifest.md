# P356B Replay-Eligible Manifest

- Generated at UTC: `2026-07-03T13:30:26.816172+00:00`
- Big Lotto lineages evaluated: `57`
- Eligible lineages: `10`
- Excluded lineages: `47`

## Exclusions By Reason
```json
{
  "DB_ONLY": 2,
  "DOC_ONLY": 10,
  "ID_REUSED": 2,
  "MISSING_CODE": 9,
  "UNKNOWN": 24
}
```

## Eligible Lineages
| strategy_id | lineage_id | current_status | bet_count | callable_entrypoint |
| --- | --- | --- | --- | --- |
| biglotto_deviation_2bet | biglotto_deviation_2bet__current | ONLINE | 2 | tools.predict_biglotto_deviation_2bet.deviation_complement_2bet |
| biglotto_echo_aware_3bet | biglotto_echo_aware_3bet__current | RETIRED | 3 | tools.predict_biglotto_echo_3bet.echo_aware_mixed_3bet |
| biglotto_triple_strike | biglotto_triple_strike__current | ONLINE | UNKNOWN | tools.predict_biglotto_triple_strike.generate_triple_strike |
| biglotto_ts3_markov_4bet_w30 | biglotto_ts3_markov_4bet_w30__current | RETIRED | 4 | tools.backtest_biglotto_5bet_ts3markov.generate_ts3_markov_4bet |
| cold_complement_biglotto | cold_complement_biglotto__current | REJECTED | UNKNOWN | lottery_api.models.p42_wave3_biglotto_adapters.predict_cold_complement_bet1 |
| coldpool15_biglotto | coldpool15_biglotto__current | REJECTED | UNKNOWN | lottery_api.models.p42_wave3_biglotto_adapters.predict_coldpool15_candidates |
| fourier30_markov30_biglotto | fourier30_markov30_biglotto__current | REJECTED | UNKNOWN | lottery_api.models.p42_wave3_biglotto_adapters.predict_fourier30_markov30_candidates |
| markov_2bet_biglotto | markov_2bet_biglotto__current | REJECTED | 2 | lottery_api.models.p42_wave3_biglotto_adapters.predict_markov_2bet_candidates |
| markov_single_biglotto | markov_single_biglotto__current | REJECTED | 1 | lottery_api.models.p42_wave3_biglotto_adapters.predict_markov_single |
| ts3_regime_3bet | ts3_regime_3bet__current | ONLINE | 3 | tools.backtest_biglotto_enhancements.ts3_regime_candidates |

## Explicit Guarded Exclusions
| strategy_id | lineage_id | executable_status | eligibility_status | exclusion_reason |
| --- | --- | --- | --- | --- |
| bet2_fourier_expansion_biglotto | bet2_fourier_expansion_biglotto__p42_p280_frozen_code | ID_REUSED | EXCLUDED | ID_REUSED |
| bet2_fourier_expansion_biglotto | bet2_fourier_expansion_biglotto__rejected_json_historical | ID_REUSED | EXCLUDED | ID_REUSED |
| biglotto_ts3_acb_4bet | biglotto_ts3_acb_4bet__current | MISSING_CODE | EXCLUDED | MISSING_CODE |
| biglotto_ts3_markov_freq_5bet | biglotto_ts3_markov_freq_5bet__current | MISSING_CODE | EXCLUDED | MISSING_CODE |
| ts3_acb_4bet_biglotto | ts3_acb_4bet_biglotto__current | MISSING_CODE | EXCLUDED | MISSING_CODE |
| ts3_markov_freq_5bet_biglotto | ts3_markov_freq_5bet_biglotto__current | MISSING_CODE | EXCLUDED | MISSING_CODE |
