# P262A — Replay Strategy Coverage Audit — All Strategies vs Replay Rows

- Generated: `2026-06-09T08:18:42.992004+00:00`
- DB: `lottery_api/data/lottery_v2.db`  (READ-ONLY, no writes)
- Overview endpoint: `GET /api/replay/history-overview` (default bet_index=1)

## Summary

- Total known strategies (registry ∪ DB): **40**
- Registered strategies: **38** ({'ONLINE': 8, 'REJECTED': 16, 'RETIRED': 13, 'OBSERVATION': 1})
- Strategies with replay rows: **35**
- Strategies WITHOUT replay rows: **5**
- Strategies reachable in overview (any bet_index): **38**
- Strategies visible in DEFAULT (bet_index=1) overview view: **13**
- Rejected-archive artifacts: **42**
- Coverage cells (strategy×lottery): **41** (in_overview=38, default_view=13, has_rows=36, can_open_detail=36)

### Orphan strategies (replay rows but UNREGISTERED → never in overview)

- `midfreq_fourier_mk_3bet`
- `pp3_freqort_4bet`

### Registered strategies WITHOUT replay rows

- `biglotto_ts3_acb_4bet`
- `biglotto_ts3_markov_freq_5bet`
- `h6_gate_mk20_ew85`
- `p1_deviation_2bet_539`
- `power_shlc_midfreq`

## Issues

### [HIGH] ORPHAN_REPLAY_ROWS

Strategies with production replay rows that are NOT in the registry — the overview endpoint walks the registry only, so these never appear in the overview and have no UI path to detail.

- `POWER_LOTTO:midfreq_fourier_mk_3bet`
- `POWER_LOTTO:pp3_freqort_4bet`

### [HIGH] REGISTRY_LOTTERY_TYPE_MISMATCH

Replay rows exist for a (strategy, lottery_type) pair where the registry does NOT list that lottery_type for the strategy. The overview iterates registry supported_lottery_types, so these rows are never surfaced.

- `POWER_LOTTO:midfreq_fourier_2bet`

### [MEDIUM] HIDDEN_IN_DEFAULT_BET1_VIEW

Multi-bet strategies with replay rows are hidden from the default overview view because the endpoint defaults to bet_index=1; they only appear when the caller sets bet_index to the strategy's derived bet count (or bet_index=0).

- `BIG_LOTTO:biglotto_deviation_2bet(derived_bet=2)`
- `BIG_LOTTO:biglotto_echo_aware_3bet(derived_bet=3)`
- `BIG_LOTTO:biglotto_triple_strike(derived_bet=3)`
- `BIG_LOTTO:biglotto_ts3_markov_4bet_w30(derived_bet=4)`
- `BIG_LOTTO:markov_2bet_biglotto(derived_bet=2)`
- `BIG_LOTTO:ts3_regime_3bet(derived_bet=3)`
- `DAILY_539:539_3bet_orthogonal(derived_bet=3)`
- `DAILY_539:acb_markov_midfreq_3bet(derived_bet=3)`
- `DAILY_539:daily539_f4cold_3bet(derived_bet=3)`
- `DAILY_539:daily539_f4cold_5bet(derived_bet=5)`
- `DAILY_539:midfreq_acb_2bet(derived_bet=2)`
- `DAILY_539:midfreq_fourier_2bet(derived_bet=2)`
- `DAILY_539:p0b_539_3bet_f_cold_fmid(derived_bet=3)`
- `DAILY_539:p0c_539_3bet_f_cold_x2(derived_bet=3)`
- `DAILY_539:zone_gap_3bet_539(derived_bet=3)`
- `POWER_LOTTO:cold_complement_2bet(derived_bet=2)`
- `POWER_LOTTO:fourier30_markov30_2bet(derived_bet=2)`
- `POWER_LOTTO:fourier_rhythm_3bet(derived_bet=3)`
- `POWER_LOTTO:power_fourier_rhythm_2bet(derived_bet=2)`
- `POWER_LOTTO:power_orthogonal_5bet(derived_bet=5)`
- `POWER_LOTTO:power_precision_3bet(derived_bet=3)`
- `POWER_LOTTO:zonal_entropy_2bet(derived_bet=2)`

### [LOW] ARTIFACT_ONLY_NO_REPLAY_ROWS

Strategies registered with a rejected/ archive artifact but no production replay rows. Expected for rejected strategies; listed for completeness (do NOT backfill in P262A).

- `biglotto_ts3_acb_4bet`
- `biglotto_ts3_markov_freq_5bet`
- `p1_deviation_2bet_539`
- `power_shlc_midfreq`

### [MEDIUM] PARTIAL_BET_INDEX_COVERAGE

strategy_id naming implies N bets but the replay table only stores up to max_bet_index < N for that (strategy, lottery).

- `BIG_LOTTO:biglotto_triple_strike(name=3bet,max_bet_index=2)`
- `BIG_LOTTO:markov_2bet_biglotto(name=2bet,max_bet_index=1)`
- `BIG_LOTTO:ts3_regime_3bet(name=3bet,max_bet_index=1)`
- `DAILY_539:539_3bet_orthogonal(name=3bet,max_bet_index=1)`
- `DAILY_539:midfreq_acb_2bet(name=2bet,max_bet_index=1)`
- `DAILY_539:midfreq_fourier_2bet(name=2bet,max_bet_index=1)`
- `DAILY_539:p0b_539_3bet_f_cold_fmid(name=3bet,max_bet_index=1)`
- `DAILY_539:p0c_539_3bet_f_cold_x2(name=3bet,max_bet_index=1)`
- `DAILY_539:zone_gap_3bet_539(name=3bet,max_bet_index=1)`
- `POWER_LOTTO:cold_complement_2bet(name=2bet,max_bet_index=1)`
- `POWER_LOTTO:fourier30_markov30_2bet(name=2bet,max_bet_index=1)`
- `POWER_LOTTO:midfreq_fourier_2bet(name=2bet,max_bet_index=1)`
- `POWER_LOTTO:zonal_entropy_2bet(name=2bet,max_bet_index=1)`

### [INFO] REGISTERED_WITHOUT_REPLAY_ROWS

Registered strategies with zero replay rows in any lottery_type. Most are REJECTED/OBSERVATION stubs with no production data.

- `biglotto_ts3_acb_4bet`
- `biglotto_ts3_markov_freq_5bet`
- `h6_gate_mk20_ew85`
- `p1_deviation_2bet_539`
- `power_shlc_midfreq`

## Coverage Matrix

| strategy_id | name | lifecycle | lottery | in_overview | default_view | has_rows | rows | draws | max_bet | can_detail | visibility | missing_reason |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 539_3bet_orthogonal | 今彩539 3注正交 | REJECTED | DAILY_539 | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 3 bets but stored max_bet_index=1 |
| acb_1bet | 今彩539 ACB 1注 | RETIRED | DAILY_539 | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| acb_markov_midfreq | 今彩539 ACB+Markov 中頻 | RETIRED | DAILY_539 | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| acb_markov_midfreq_3bet | 今彩539 ACB+Markov 中頻 3注 | RETIRED | DAILY_539 | YES | NO | YES | 4500 | 1500 | 3 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) |
| acb_single_539 | 今彩539 ACB Single | REJECTED | DAILY_539 | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| bet2_fourier_expansion_biglotto | 大樂透 Bet2 Fourier Expansion | REJECTED | BIG_LOTTO | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| biglotto_deviation_2bet | 大樂透 Deviation 2注 | ONLINE | BIG_LOTTO | YES | NO | YES | 1570 | 1550 | 2 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) |
| biglotto_echo_aware_3bet | 大樂透 Echo Aware 3注 | RETIRED | BIG_LOTTO | YES | NO | YES | 4500 | 1500 | 3 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) |
| biglotto_triple_strike | 大樂透 Triple Strike | ONLINE | BIG_LOTTO | YES | NO | YES | 1570 | 1550 | 2 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 3 bets but stored max_bet_index=2 |
| biglotto_ts3_acb_4bet | 大樂透 TS3+ACB 4注 | REJECTED | BIG_LOTTO | YES | NO | NO | 0 | 0 | 0 | NO | RECONSTRUCTIBLE | ARTIFACT_ONLY: registered (REJECTED) with rejected/ artifact but zero production replay rows |
| biglotto_ts3_markov_4bet_w30 | 大樂透 TS3+Markov 4注 w30 | RETIRED | BIG_LOTTO | YES | NO | YES | 6000 | 1500 | 4 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=4 so the row is only visible when the overview bet_index filter == 4 (default bet_index=1 hides it) |
| biglotto_ts3_markov_freq_5bet | 大樂透 TS3+Markov 頻率正交 5注 | REJECTED | BIG_LOTTO | YES | NO | NO | 0 | 0 | 0 | NO | RECONSTRUCTIBLE | ARTIFACT_ONLY: registered (REJECTED) with rejected/ artifact but zero production replay rows |
| cold_complement_2bet | 威力彩 Cold Complement 2注 | RETIRED | POWER_LOTTO | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 2 bets but stored max_bet_index=1 |
| cold_complement_biglotto | 大樂透 Cold Complement | REJECTED | BIG_LOTTO | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| coldpool15_biglotto | 大樂透 ColdPool-15 | REJECTED | BIG_LOTTO | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| daily539_f4cold | 今彩539 F4 Cold | ONLINE | DAILY_539 | YES | YES | YES | 1590 | 1550 | 3 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| daily539_f4cold_3bet | 今彩539 F4Cold 3注 | RETIRED | DAILY_539 | YES | NO | YES | 4500 | 1500 | 3 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) |
| daily539_f4cold_5bet | 今彩539 F4Cold 5注 | RETIRED | DAILY_539 | YES | NO | YES | 7500 | 1500 | 5 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=5 so the row is only visible when the overview bet_index filter == 5 (default bet_index=1 hides it) |
| daily539_markov_cold | 今彩539 Markov Cold | ONLINE | DAILY_539 | YES | YES | YES | 1590 | 1550 | 3 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| fourier30_markov30_2bet | 威力彩 Fourier30+Markov30 2注 | RETIRED | POWER_LOTTO | YES | NO | YES | 1501 | 1501 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 2 bets but stored max_bet_index=1 |
| fourier30_markov30_biglotto | 大樂透 Fourier30+Markov30 | REJECTED | BIG_LOTTO | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| fourier_rhythm_3bet | 威力彩 Fourier Rhythm 3注 | ONLINE | POWER_LOTTO | YES | NO | YES | 4503 | 1501 | 3 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) |
| h6_gate_mk20_ew85 | 威力彩 H6 Gate mk20 ew85 | OBSERVATION | POWER_LOTTO | YES | YES | NO | 0 | 0 | 0 | NO | REGISTERED_NO_DATA | REGISTERED_NO_DATA: registered (OBSERVATION) but zero production replay rows and no rejected/ artifact |
| markov_1bet_539 | 今彩539 Markov 1注 | REJECTED | DAILY_539 | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| markov_2bet_biglotto | 大樂透 Markov 2注 | REJECTED | BIG_LOTTO | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 2 bets but stored max_bet_index=1 |
| markov_single_biglotto | 大樂透 Markov Single | REJECTED | BIG_LOTTO | YES | YES | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | OK: covered (registered, lottery matched, rows present, in default view) |
| midfreq_acb_2bet | 今彩539 中頻 ACB 2注 | RETIRED | DAILY_539 | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 2 bets but stored max_bet_index=1 |
| midfreq_fourier_2bet | 今彩539 中頻 Fourier 2注 | RETIRED | DAILY_539 | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 2 bets but stored max_bet_index=1 |
| midfreq_fourier_2bet | 今彩539 中頻 Fourier 2注 | RETIRED | POWER_LOTTO | NO | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | REGISTRY_LOTTERY_MISMATCH: replay rows exist for RETIRED strategy under a lottery_type the registry does not list -> cell never produced by overview | PARTIAL_BET_INDEX: name implies 2 bets but stored max_bet_index=1 |
| midfreq_fourier_mk_3bet | 威力彩 MidFreq+Fourier+Markov 3注 | UNREGISTERED | POWER_LOTTO | NO | NO | YES | 4500 | 1500 | 3 | YES | ARTIFACT_CANDIDATE | ORPHAN: has replay rows but NOT registered -> never iterated by overview endpoint (overview only walks the registry) |
| p0b_539_3bet_f_cold_fmid | 今彩539 P0B 3注 F+Cold+FMid | REJECTED | DAILY_539 | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 3 bets but stored max_bet_index=1 |
| p0c_539_3bet_f_cold_x2 | 今彩539 P0C 3注 F+Cold×2 | REJECTED | DAILY_539 | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 3 bets but stored max_bet_index=1 |
| p1_deviation_2bet_539 | 今彩539 P1鄰號+偏差互補 2注 | REJECTED | DAILY_539 | YES | NO | NO | 0 | 0 | 0 | NO | RECONSTRUCTIBLE | ARTIFACT_ONLY: registered (REJECTED) with rejected/ artifact but zero production replay rows |
| power_fourier_rhythm_2bet | 威力彩 Power Fourier Rhythm 2注 | RETIRED | POWER_LOTTO | YES | NO | YES | 3000 | 1500 | 2 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) |
| power_orthogonal_5bet | 威力彩 Orthogonal 5注 | ONLINE | POWER_LOTTO | YES | NO | YES | 7550 | 1550 | 5 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=5 so the row is only visible when the overview bet_index filter == 5 (default bet_index=1 hides it) |
| power_precision_3bet | 威力彩 Precision 3注 | ONLINE | POWER_LOTTO | YES | NO | YES | 4550 | 1550 | 3 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) |
| power_shlc_midfreq | 威力彩 SHLC 中頻指標 | REJECTED | POWER_LOTTO | YES | YES | NO | 0 | 0 | 0 | NO | RECONSTRUCTIBLE | ARTIFACT_ONLY: registered (REJECTED) with rejected/ artifact but zero production replay rows |
| pp3_freqort_4bet | 威力彩 PP3+FreqOrt 4注 | UNREGISTERED | POWER_LOTTO | NO | NO | YES | 6000 | 1500 | 4 | YES | ARTIFACT_CANDIDATE | ORPHAN: has replay rows but NOT registered -> never iterated by overview endpoint (overview only walks the registry) |
| ts3_regime_3bet | 大樂透 TS3+Regime 3注 | ONLINE | BIG_LOTTO | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 3 bets but stored max_bet_index=1 |
| zonal_entropy_2bet | 威力彩 Zonal Entropy 2注 | RETIRED | POWER_LOTTO | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=2 so the row is only visible when the overview bet_index filter == 2 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 2 bets but stored max_bet_index=1 |
| zone_gap_3bet_539 | 今彩539 Zone Gap 3注 | REJECTED | DAILY_539 | YES | NO | YES | 1500 | 1500 | 1 | YES | REGISTERED_WITH_REPLAY_ROWS | HIDDEN_IN_DEFAULT_VIEW: derived_bet_count=3 so the row is only visible when the overview bet_index filter == 3 (default bet_index=1 hides it) | PARTIAL_BET_INDEX: name implies 3 bets but stored max_bet_index=1 |
