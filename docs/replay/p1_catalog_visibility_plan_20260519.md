# P1 Catalog Visibility Plan — 2026-05-19

Generated: 2026-05-19T11:30:21.776274Z  Phase: P1  dry_run_only: true

## Runtime Canonical Universe (Before P1 Apply)

| Field | Value |
|-------|-------|
| Total registered strategies | **18** |
| Strategies with replay rows | **6** |
| ONLINE | 8 |
| REJECTED | 4 |
| RETIRED | 5 |
| OBSERVATION | 1 |

## Visibility State Distribution

| State | Count |
|-------|-------|
| REGISTERED_WITH_REPLAY_ROWS | 6 |
| RECONSTRUCTIBLE | 12 |
| REGISTERED_NO_DATA | 0 |
| ARTIFACT_CANDIDATE | 41 |
| UNSUPPORTED | 0 |

## Artifact Candidates (not in registry): 41

> These strategies exist in `rejected/` or artifact scan but are NOT in the
> runtime registry. They require governance review before any row generation.

## RECONSTRUCTIBLE Candidates (P5-P7 inputs)

Count: **12**

- `fourier_rhythm_3bet`
- `ts3_regime_3bet`
- `biglotto_ts3_acb_4bet`
- `biglotto_ts3_markov_freq_5bet`
- `power_shlc_midfreq`
- `p1_deviation_2bet_539`
- `acb_1bet`
- `acb_markov_midfreq`
- `acb_markov_midfreq_3bet`
- `midfreq_acb_2bet`
- `midfreq_fourier_2bet`
- `h6_gate_mk20_ew85`

## Planned Actions (all dry_run_only=True)

| Strategy | Action | Reason |
|----------|--------|--------|
| `power_precision_3bet` | SKIP | Already has 70 replay rows |
| `power_orthogonal_5bet` | SKIP | Already has 70 replay rows |
| `fourier_rhythm_3bet` | INSERT_PENDING_P5 | Reconstructible via PREDICTION_LOG; deferred to P5-P7 |
| `biglotto_triple_strike` | SKIP | Already has 70 replay rows |
| `biglotto_deviation_2bet` | SKIP | Already has 70 replay rows |
| `ts3_regime_3bet` | INSERT_PENDING_P5 | Reconstructible via PREDICTION_LOG; deferred to P5-P7 |
| `daily539_f4cold` | SKIP | Already has 90 replay rows |
| `daily539_markov_cold` | SKIP | Already has 90 replay rows |
| `biglotto_ts3_acb_4bet` | INSERT_PENDING_P5 | Reconstructible via CODE_SCAN; deferred to P5-P7 |
| `biglotto_ts3_markov_freq_5bet` | INSERT_PENDING_P5 | Reconstructible via CODE_SCAN; deferred to P5-P7 |
| `power_shlc_midfreq` | INSERT_PENDING_P5 | Reconstructible via CODE_SCAN; deferred to P5-P7 |
| `p1_deviation_2bet_539` | INSERT_PENDING_P5 | Reconstructible via REJECTED_JSON; deferred to P5-P7 |
| `acb_1bet` | INSERT_PENDING_P5 | Reconstructible via PREDICTION_LOG; deferred to P5-P7 |
| `acb_markov_midfreq` | INSERT_PENDING_P5 | Reconstructible via CODE_SCAN; deferred to P5-P7 |
| `acb_markov_midfreq_3bet` | INSERT_PENDING_P5 | Reconstructible via PREDICTION_LOG; deferred to P5-P7 |
| `midfreq_acb_2bet` | INSERT_PENDING_P5 | Reconstructible via PREDICTION_LOG; deferred to P5-P7 |
| `midfreq_fourier_2bet` | INSERT_PENDING_P5 | Reconstructible via CODE_SCAN; deferred to P5-P7 |
| `h6_gate_mk20_ew85` | INSERT_PENDING_P5 | Reconstructible via CODE_SCAN; deferred to P5-P7 |

## Notes

All entries have dry_run_only=True. can_generate_replay_rows() returns False for all entries. RECONSTRUCTIBLE strategies are P5-P7 inputs. ARTIFACT_CANDIDATE strategies are NOT in runtime registry and require governance review before any row generation.

## Safety Confirmation

- ✅ No DB writes
- ✅ No draw imports
- ✅ No replay rows generated
- ✅ No prediction execution
- ✅ All entries: dry_run_only=True
- ✅ can_generate_replay_rows() → False
- ✅ ARTIFACT_CANDIDATE strategies: lifecycle_state=NOT_REGISTERED
