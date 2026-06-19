# P280AQ Private BIG Strategy-Pack Duplicate Remediation

## Classification

`P280AQ_PRIVATE_BIG649_STRATEGY_PACK_DUPLICATE_REMEDIATED_PR_OPEN_NO_PUBLICATION`

Private research only. No official target or deadline lookup, no publication,
no pre-draw manifest, no prediction-success claim, no promotion, and no activation.

## Root Cause And Fix

Latest local canonical BIG history ends at draw `115000062` on `2026/06/16`.
The private reference is `NEXT_LOCAL_DRAW_AFTER_115000062`, derived local id
`115000063`; it is not an official target.

Before remediation, `fourier30_markov30_biglotto` duplicated
`biglotto_echo_aware_3bet` on `[6, 16, 20, 25, 28, 37]`. Its only exposed
candidate came from `predict_fourier30_markov30_bet1`, so the adapter failed:

`UNRESOLVED_DUPLICATE_STOP: fourier30_markov30_biglotto has no non-duplicate candidate among 1 options`

Root-cause classification: `SAFE_ADDITIVE_CANDIDATE_INTERFACE_NEEDED`.
The source already defines the strategy as Fourier30 bet-1 plus a Markov30
second bet. The new `predict_fourier30_markov30_candidates` preserves frozen
bet-1 at candidate 0 and exposes a deterministic Markov30-ranked candidate 1,
constrained to at most three overlaps. No manual or fabricated numbers are used.

## Candidate Availability

| Strategy | Candidates | Source callable |
|---|---:|---|
| `bet2_fourier_expansion_biglotto` | 1 | `predict_fourier_expansion_bet1` |
| `biglotto_deviation_2bet` | 2 | `deviation_complement_2bet` |
| `biglotto_echo_aware_3bet` | 3 | `echo_aware_mixed_3bet` |
| `biglotto_triple_strike` | 3 | `generate_triple_strike` |
| `biglotto_ts3_markov_4bet_w30` | 4 | `generate_ts3_markov_4bet` |
| `cold_complement_biglotto` | 1 | `predict_cold_complement_bet1` |
| `coldpool15_biglotto` | 3 | `predict_coldpool15_candidates` |
| `fourier30_markov30_biglotto` | 2 | `predict_fourier30_markov30_candidates` |
| `markov_2bet_biglotto` | 3 | `predict_markov_2bet_candidates` |
| `markov_single_biglotto` | 1 | `predict_markov_single` |
| `ts3_regime_3bet` | 3 | `ts3_regime_candidates` |

## Strategy Adapter Pack

All 11 tickets contain six unique integers in `1..49`; all complete tickets are
unique; deterministic rerun passed. Adapter digest:
`b8ceac657f081bbf2be6ae0fabe6adbce564ea3a4b4cb77ab610035d0e4a800a`.

| Strategy | Candidate | Ticket |
|---|---:|---|
| `bet2_fourier_expansion_biglotto` | 0/1 | `8 12 37 38 44 46` |
| `biglotto_deviation_2bet` | 0/2 | `6 16 20 22 47 48` |
| `biglotto_echo_aware_3bet` | 0/3 | `6 16 20 25 28 37` |
| `biglotto_triple_strike` | 0/3 | `8 12 37 38 44 47` |
| `biglotto_ts3_markov_4bet_w30` | 1/4 | `2 29 30 31 34 42` |
| `cold_complement_biglotto` | 0/1 | `16 20 22 25 39 47` |
| `coldpool15_biglotto` | 1/3 | `6 7 11 12 18 41` |
| `fourier30_markov30_biglotto` | 1/2 | `12 14 15 25 32 40` |
| `markov_2bet_biglotto` | 0/3 | `16 19 20 36 45 47` |
| `markov_single_biglotto` | 0/1 | `11 14 18 22 25 39` |
| `ts3_regime_3bet` | 1/3 | `3 9 21 30 31 34` |

## Diversified Random Comparison

P280AP seed `964cb0b5e635cd0556e19f24670bb9a5ea395f38d520e9874bbaf11b7e66afed`.
Policy: `sha256(P280AP|origin/main|latest_local_draw_id)`, then deterministic
greedy low-overlap selection over 256 PRNG candidates per slot.

1. `5 7 23 25 33 48`
2. `4 11 14 32 35 36`
3. `1 6 22 31 45 46`
4. `19 29 38 39 42 43`
5. `8 9 10 18 26 44`
6. `2 13 15 17 24 28`
7. `17 21 37 40 41 47`
8. `3 8 30 36 38 49`
9. `1 7 12 21 27 34`
10. `16 20 22 35 43 48`
11. `4 9 20 27 37 42`

Validation: 11 unique tickets, 49/49 number coverage, maximum pair overlap 1,
deterministic rerun passed.

## Hybrid Reference Pack

Five strategy-derived tickets selected by the P280AP low-overlap hybrid policy,
followed by the first six diversified-random tickets:

1. `strategy:fourier30_markov30_biglotto` - `12 14 15 25 32 40`
2. `strategy:biglotto_ts3_markov_4bet_w30` - `2 29 30 31 34 42`
3. `strategy:coldpool15_biglotto` - `6 7 11 12 18 41`
4. `strategy:markov_2bet_biglotto` - `16 19 20 36 45 47`
5. `strategy:bet2_fourier_expansion_biglotto` - `8 12 37 38 44 46`
6. `random:1` - `5 7 23 25 33 48`
7. `random:2` - `4 11 14 32 35 36`
8. `random:3` - `1 6 22 31 45 46`
9. `random:4` - `19 29 38 39 42 43`
10. `random:5` - `8 9 10 18 26 44`
11. `random:6` - `2 13 15 17 24 28`

Validation: 11 unique tickets, 45/49 number coverage, maximum pair overlap 2,
deterministic rerun passed.

## Freeze And Safety

P280D is reconciled from source SHA-256 `f53dd8...13da` to
`d07b1c...bb79`, preserving the prior hashes and recording a forward interface
revision. Frozen bet-1 semantics and historical future-only evidence are unchanged.
The registry is unchanged.

The canonical DB was opened and queried read-only (`mode=ro/immutable=1`,
`query_only=ON`); copied/written = no/no. Main DB, WAL, and SHM bytes remained
unchanged, so no content drift was detected.

These private packs do not improve lottery odds and are not evidence of prediction
success. Independent audit is recommended before merging the remediation. Real
publication and post-draw evaluation remain separate and unauthorized.
