# P320A Handoff Report

Final classification: `P320A_D5_COMBINATION_ANALYSIS_COMPLETE_WITH_RISKS`

Risk basis: results are retrospective, unequal-ticket-budget, descriptive portfolio metrics; no random baseline or inference was computed. POWER_LOTTO is excluded.

## Result

- Evidence root: `/Users/kelvin/Kelvin-WorkSpace/p320a_d5_per_draw_combination_analysis_20260701_131917`.
- True per-draw combination metrics: computed for BIG_LOTTO and DAILY_539.
- Output: 2,418 rows covering 26 singles, 160 pairs, and 620 triples across each of the 50/300/750 windows.
- Metric semantics: per draw, pool all stored tickets from constituent strategies and score the maximum main-number hit count; hit-at-least-N is an any-ticket rate.
- Source: immutable read-only `p213l` backup; 19,500 committed strategy/draw identity records and 29,250 tickets matched exactly.
- Baseline: `not_computed`. Inference: `DESCRIPTIVE_ONLY`.

## Exact common windows

- BIG_LOTTO: recent_50 `115000053..115000004`; recent_300 `115000053..112000106`; recent_750 `115000053..108000108`. Each metric denominator is exactly 50, 300, or 750 common draws. Eleven strategies yield 11 singles, 55 pairs, and 165 triples per window.
- DAILY_539: recent_50 `115000121..115000072`; recent_300 `115000121..114000138`; recent_750 `115000121..113000002`. Each metric denominator is exactly 50, 300, or 750 common draws. Fifteen strategies yield 15 singles, 105 pairs, and 455 triples per window.
- `sample_size_rows` in the CSV is the exact number of stored ticket rows pooled for that combination/window; it varies with each strategy's intrinsic ticket count.

## Descriptive candidate examples

- BIG_LOTTO recent_750 pair `biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30`: 5,250 ticket rows / 750 draws; hit>=2 `0.702666666667`; hit>=3 `0.153333333333`; descriptive hit>=3 delta versus the stronger constituent `0.062666666666`.
- BIG_LOTTO recent_750 triple `biglotto_deviation_2bet|biglotto_echo_aware_3bet|biglotto_ts3_markov_4bet_w30`: 6,000 ticket rows / 750 draws; hit>=2 `0.737333333333`; hit>=3 `0.176000000000`; descriptive hit>=3 delta `0.085333333333`.
- DAILY_539 recent_750 pair `acb_markov_midfreq_3bet|daily539_f4cold_5bet`: 6,000 ticket rows / 750 draws; hit>=2 `0.710666666667`; hit>=3 `0.092000000000`; descriptive hit>=3 delta `0.030666666667`.
- DAILY_539 recent_750 triple `acb_markov_midfreq|acb_markov_midfreq_3bet|daily539_f4cold_5bet`: 6,750 ticket rows / 750 draws; hit>=2 `0.728000000000`; hit>=3 `0.104000000000`; descriptive hit>=3 delta `0.042666666667`.

These are deterministic display examples from `top_descriptive_candidates.csv`, not equal-budget comparisons or endorsements.

## Validation

- PASS: evidence root exists.
- PASS: manifest covers every non-manifest payload artifact, including the reproducibility script and command log.
- PASS: manifest hashes recompute.
- PASS: repo tracked files unchanged; working tree clean after analysis.
- PASS: no staged files.
- PASS: source fields sufficient for true per-draw overlap.
- PASS: DB read-only source check (`mode=ro&immutable=1`, `query_only=1`).
- PASS: DB SHA256, size, mtime, and sidecar inventory unchanged.
- PASS: no fake/default/random/actual-value filling of missing fields.
- PASS: no aggregate-rate-only combination approximation.
- NOT RUN: code test suites and npm checks; no repo code was changed.
- NOT RUN: POWER_LOTTO scoring due to second-zone readiness block.
- NOT RUN: production apply, registry publication, future-ticket creation, migration, checkpoint, commit, push, or PR.

No repo files changed. No DB write, migration, or checkpoint occurred.

