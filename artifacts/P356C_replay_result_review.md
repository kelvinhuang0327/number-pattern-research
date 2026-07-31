# P356C Replay Result Review

## Scope

- Source manifest: `artifacts/P356B_replay_eligible_manifest.csv`
- Source replay CSV: `artifacts/P356B_biglotto_replay_30_150_750_1500.csv`
- Source replay report: `artifacts/P356B_biglotto_replay_30_150_750_1500.md`
- Review mode: post-commit artifact review only; no replay output was regenerated.
- Canonical DB mode: read-only/immutable guard only; no canonical DB write.

## Eligible Strategy List

| strategy_id | lineage_id | current_status | manifest_bet_count | callable_entrypoint |
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

## Excluded Counts By Reason

| reason | count |
| --- | ---: |
| UNKNOWN | 24 |
| DOC_ONLY | 10 |
| MISSING_CODE | 9 |
| ID_REUSED | 2 |
| DB_ONLY | 2 |

Total excluded Big Lotto lineages: `47`.

## Replay Row Counts

| replay_window | row_count |
| --- | ---: |
| 30 | 10 |
| 150 | 10 |
| 750 | 10 |
| 1500 | 10 |

Total replay rows: `40`.

## Ranking By 1500p Edge

| rank | strategy_id | current_status | bet_count | hit_rate | baseline | edge |
| ---: | --- | --- | ---: | ---: | ---: | ---: |
| 1 | biglotto_ts3_markov_4bet_w30 | RETIRED | 4 | 0.088667 | 0.072492 | 0.016175 |
| 2 | biglotto_triple_strike | ONLINE | 3 | 0.068000 | 0.054877 | 0.013123 |
| 3 | ts3_regime_3bet | ONLINE | 3 | 0.067333 | 0.054877 | 0.012456 |
| 4 | biglotto_echo_aware_3bet | RETIRED | 3 | 0.064000 | 0.054877 | 0.009123 |
| 5 | biglotto_deviation_2bet | ONLINE | 2 | 0.042000 | 0.036928 | 0.005072 |
| 6 | coldpool15_biglotto | REJECTED | 3 | 0.053333 | 0.054877 | -0.001544 |
| 7 | cold_complement_biglotto | REJECTED | 1 | 0.016000 | 0.018638 | -0.002638 |
| 8 | markov_single_biglotto | REJECTED | 1 | 0.016000 | 0.018638 | -0.002638 |
| 9 | fourier30_markov30_biglotto | REJECTED | 2 | 0.033333 | 0.036928 | -0.003594 |
| 10 | markov_2bet_biglotto | REJECTED | 2 | 0.030667 | 0.036928 | -0.006261 |

## UNKNOWN Manifest Bet Count Check

The replay CSV has concrete `bet_count` and `baseline` values for every eligible strategy whose manifest `bet_count` was `UNKNOWN`.

| strategy_id | replay_rows | replay_bet_count | replay_baseline |
| --- | ---: | ---: | ---: |
| biglotto_triple_strike | 4 | 3 | 0.054877 |
| cold_complement_biglotto | 4 | 1 | 0.018638 |
| coldpool15_biglotto | 4 | 3 | 0.054877 |
| fourier30_markov30_biglotto | 4 | 2 | 0.036928 |

No missing replay `bet_count` or `baseline` values were found for these four strategies.

## Warnings And Caveats

- Coverage Edge is not betting advice.
- Coverage Edge is not governance status approval.
- `REJECTED` and `RETIRED` strategies remain status unchanged.
- Excluded strategies were not proven bad; they were not replay-eligible under P356B criteria.
- Positive 1500p edge is descriptive replay coverage evidence only, not a deployment or promotion signal.
- The replay used an in-memory process and did not write canonical replay tables.
- Runtime caveat from P356B: the default `python3` lacked `numpy`, and the bundled Python had `numpy` but not `scipy`; P356B used a process-local `scipy.fft` compatibility shim backed by `numpy.fft` for legacy callables importing only `fft` and `fftfreq`.

## Review Conclusion

P356C found no concrete replay result bug requiring a rewrite. The primary result caveat is interpretive: the replay CSV resolves concrete `bet_count` and baseline values at runtime even where the manifest had `UNKNOWN`, and those resolved values must be read as replay-observed coverage parameters, not as lifecycle metadata updates.
