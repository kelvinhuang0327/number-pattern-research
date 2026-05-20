# P6 Source Promotion Policy Report
**Date**: 2026-05-20  
**Phase**: P6 (read-only, no DB write)  
**P5 Source**: `p5_historical_reconstruction_plan_20260520.json`  

## Summary

| Metric | Count |
|--------|-------|
| Total plan rows | 128 |
| PLAN_INSERT_REPLAY_ROW | 121 |
| Approved for P7 candidate | **121** |
| Rejected (NOT_P7_CANDIDATE) | 7 |
| Manual review required | 0 |
| DB rows verified (unchanged) | 460 |

## By Strategy

| Strategy | Lifecycle | Approved | Rejected | Manual | Total |
|----------|-----------|----------|----------|--------|-------|
| fourier_rhythm_3bet | ONLINE | 12 | 0 | 0 | 12 |
| ts3_regime_3bet | ONLINE | 16 | 0 | 0 | 16 |
| biglotto_ts3_acb_4bet | REJECTED | 0 | 1 | 0 | 1 |
| biglotto_ts3_markov_freq_5bet | REJECTED | 0 | 1 | 0 | 1 |
| power_shlc_midfreq | REJECTED | 0 | 1 | 0 | 1 |
| p1_deviation_2bet_539 | REJECTED | 0 | 1 | 0 | 1 |
| acb_1bet | RETIRED | 31 | 0 | 0 | 31 |
| acb_markov_midfreq | RETIRED | 0 | 1 | 0 | 1 |
| acb_markov_midfreq_3bet | RETIRED | 31 | 0 | 0 | 31 |
| midfreq_acb_2bet | RETIRED | 31 | 0 | 0 | 31 |
| midfreq_fourier_2bet | RETIRED | 0 | 1 | 0 | 1 |
| h6_gate_mk20_ew85 | OBSERVATION | 0 | 1 | 0 | 1 |

## Rejection Reasons

- `planned_action='SKIP_NO_HISTORICAL_PAYLOAD' is not PLAN_INSERT_REPLAY_ROW`: 6
- `planned_action='SKIP_SOURCE_MISSING' is not PLAN_INSERT_REPLAY_ROW`: 1

## Lifecycle Warnings

93 candidate rows involve non-ONLINE strategies. These require human review before P7 apply.

- `acb_1bet` (RETIRED): 31 rows
- `acb_markov_midfreq_3bet` (RETIRED): 31 rows
- `midfreq_acb_2bet` (RETIRED): 31 rows

## Safety Confirmation

- `strategy_prediction_replays` rows: **460** (verified unchanged)
- No DB write performed
- No replay rows generated
- No lifecycle_state mutations
- All results have `p6_can_apply = False`

## P7 Authorization Gate

P7 controlled replay row apply is **NOT** triggered by this script.

To authorize P7 dry-run preparation, a human operator must respond:

> `YES prepare P7 dry-run`

P7 prerequisites:
- [ ] P6 committed and verified
- [ ] UI visibility recovery committed (`a89a7ca`)
- [ ] Drift guard PASS
- [ ] DB rows unchanged (460)
- [ ] Lifecycle warnings reviewed by human
- [ ] Backup/rollback design complete
