# P5 Historical Reconstruction Dry-run Row Plan

Generated: 2026-05-19T13:09:55.510125Z
Lottery type filter: `DAILY_539`  
Draw range: `115000072-115000121`  
Candidate cells: 300  
**rows_to_insert_planned: 62**  

## Plan Action Summary

| Action | Count |
|--------|-------|
| `NEEDS_P6_POLICY` | 100 |
| `SKIP_NO_HISTORICAL_PAYLOAD` | 88 |
| `PLAN_INSERT_REPLAY_ROW` | 62 |
| `SKIP_SOURCE_MISSING` | 50 |

## Per-Strategy Breakdown

| Strategy | Total | Planned | Skipped |
|---|---|---|---|
| p1_deviation_2bet_539 | 50 | 0 | 50 |
| acb_1bet | 50 | 9 | 41 |
| acb_markov_midfreq | 50 | 0 | 50 |
| acb_markov_midfreq_3bet | 50 | 44 | 6 |
| midfreq_acb_2bet | 50 | 9 | 41 |
| midfreq_fourier_2bet | 50 | 0 | 50 |

## Provenance Quality

- Rows with provenance_hash: 62
- Rows without provenance_hash: 238
- ARTIFACT_DERIVED trust: 150
- UNKNOWN trust: 150

## Safety Flags

- no_apply_option: True
- all_dry_run: True
- all_can_apply_false: True
- db_rows before/after: 460 / 460
- rows_unchanged: True

## Notes

- `PLAN_INSERT_REPLAY_ROW` = has payload from prediction_items; ready for P7 review
- `NEEDS_P6_POLICY` = CODE_SCAN only; P6 must approve re-execution before P7
- `SKIP_SOURCE_MISSING` = REJECTED_JSON has no per-draw payload
- `SKIP_NO_HISTORICAL_PAYLOAD` = PREDICTION_LOG exists but no entry for this draw
- **No rows were inserted in this plan run.**
