# P276B — Fixed-N Cross-Strategy Coverage & Complementarity Study

> **Read-only, retrospective, non-confirmatory.** Reuses frozen committed P273A ticket identities + read-only settled draw outcomes. `prediction_success_claim=false`; no strategy promotion, no registry mutation, no DB write, no activation. True confirmation begins only with draws strictly later than the frozen cutoff.

## Run metadata
- task_id: `P276B_FIXED_N_COVERAGE_COMPLEMENTARITY_BUILD`
- artifact_version: `p276b_fixed_n_coverage_complementarity_v1`
- scoring_version: `prize_aware_v1`
- generated_at: `2026-06-17T03:46:51.512525+00:00`
- **scientific_verdict: `NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE`**
- canonical_payload_digest: `2fbaa331eead6702c8da5dbae539405979573ce064301582d940af0d52d6ff39`

## Frozen contract
- preregistered_family_sha256: `48d0c30d7c7643204a76bd0c6b30823c9d74b3061f10e81042bc2399eeb38440`
- fixed_ticket_budgets: [3, 5]
- confirmatory_family_size: 6 (Bonferroni per-test alpha 0.00833)
- global_seed: 20260617, mc_replicates: 10000, mc_q_samples: 200000
- frozen_before_outcome_access: True

## DB snapshot (read-only)
- path_identifier: `lottery_v2.db`
- sha256 (pre==post): `4c8736caab661088c8430908ae4423a73522619f7521fb64e2c6f1affd20b056` (unchanged: True)
- size_bytes: 99368960; query_only_enabled: True; write_denying_authorizer: True
- latest_draw_in_db: {'DAILY_539': '115000145', 'BIG_LOTTO': '115000061', 'POWER_LOTTO': '115000048'}

## Count reproduction (fail-closed gate)
- reproduction_status: **PASS** (108 primary-window cells checked)

## Frozen future contract
- cutoff_target_draw_by_lottery: `{'DAILY_539': '115000121', 'BIG_LOTTO': '115000055', 'POWER_LOTTO': '115000040'}`
- future_confirmation_status: **FUTURE_CONFIRMATION_PENDING**

## Portfolio results (prize-aware union, primary lottery)

| portfolio | tier/kind | N | window | support | union_rate | best_constituent | Δ vs constituent | McNemar p | ord_excess | div_excess | div_p |
|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| D539_N3_f4cold3 | PRIMARY/SINGLE | 3 | SHORT | 50 | 0.4600 | daily539_f4cold_3bet | 0.0000 | 1.0000 | 0.1555 | 0.1346 | 0.0308 |
| D539_N3_f4cold3 | PRIMARY/SINGLE | 3 | MID | 300 | 0.3367 | daily539_f4cold_3bet | 0.0000 | 1.0000 | 0.0322 | 0.0113 | 0.3578 |
| D539_N3_f4cold3 | PRIMARY/SINGLE | 3 | LONG | 750 | 0.3667 | daily539_f4cold_3bet | 0.0000 | 1.0000 | 0.0622 | 0.0413 | 0.0099 |
| D539_N3_acbmm3 | PRIMARY/SINGLE | 3 | SHORT | 50 | 0.3600 | acb_markov_midfreq_3bet | 0.0000 | 1.0000 | 0.0555 | 0.0346 | 0.3496 |
| D539_N3_acbmm3 | PRIMARY/SINGLE | 3 | MID | 300 | 0.4000 | acb_markov_midfreq_3bet | 0.0000 | 1.0000 | 0.0955 | 0.0746 | 0.0047 |
| D539_N3_acbmm3 | PRIMARY/SINGLE | 3 | LONG | 750 | 0.3573 | acb_markov_midfreq_3bet | 0.0000 | 1.0000 | 0.0529 | 0.0319 | 0.0372 |
| D539_N3_f4cold3_x_acbmm3 | PRIMARY/CROSS | 3 | SHORT | 50 | 0.3600 | daily539_f4cold_3bet | -0.1000 | 0.2266 | 0.0555 | 0.0346 | 0.3496 |
| D539_N3_f4cold3_x_acbmm3 | PRIMARY/CROSS | 3 | MID | 300 | 0.3033 | acb_markov_midfreq_3bet | -0.0967 | 0.0070 | -0.0011 | -0.0221 | 0.8160 |
| D539_N3_f4cold3_x_acbmm3 | PRIMARY/CROSS | 3 | LONG | 750 | 0.3333 | daily539_f4cold_3bet | -0.0333 | 0.0370 | 0.0289 | 0.0079 | 0.3335 |
| D539_N5_f4cold5 | PRIMARY/SINGLE | 5 | SHORT | 50 | 0.7000 | daily539_f4cold_5bet | 0.0000 | 1.0000 | 0.2458 | 0.1841 | 0.0073 |
| D539_N5_f4cold5 | PRIMARY/SINGLE | 5 | MID | 300 | 0.5667 | daily539_f4cold_5bet | 0.0000 | 1.0000 | 0.1124 | 0.0508 | 0.0403 |
| D539_N5_f4cold5 | PRIMARY/SINGLE | 5 | LONG | 750 | 0.5667 | daily539_f4cold_5bet | 0.0000 | 1.0000 | 0.1124 | 0.0508 | 0.0018 |
| D539_N5_f4cold5_x_acbmm3 | PRIMARY/CROSS | 5 | SHORT | 50 | 0.5800 | daily539_f4cold_5bet | -0.1200 | 0.2101 | 0.1258 | 0.0641 | 0.2213 |
| D539_N5_f4cold5_x_acbmm3 | PRIMARY/CROSS | 5 | MID | 300 | 0.4900 | daily539_f4cold_5bet | -0.0767 | 0.0165 | 0.0358 | -0.0259 | 0.8273 |
| D539_N5_f4cold5_x_acbmm3 | PRIMARY/CROSS | 5 | LONG | 750 | 0.4973 | daily539_f4cold_5bet | -0.0693 | 0.0003 | 0.0431 | -0.0185 | 0.8548 |
| D539_N5_f4cold5_x_f4cold3_x_acbmm3 | PRIMARY/CROSS | 5 | SHORT | 50 | 0.5600 | daily539_f4cold_5bet | -0.1400 | 0.1435 | 0.1058 | 0.0441 | 0.3121 |
| D539_N5_f4cold5_x_f4cold3_x_acbmm3 | PRIMARY/CROSS | 5 | MID | 300 | 0.4833 | daily539_f4cold_5bet | -0.0833 | 0.0073 | 0.0291 | -0.0325 | 0.8807 |
| D539_N5_f4cold5_x_f4cold3_x_acbmm3 | PRIMARY/CROSS | 5 | LONG | 750 | 0.4947 | daily539_f4cold_5bet | -0.0720 | 0.0001 | 0.0404 | -0.0212 | 0.8861 |
| BIG_N3_echo3 | SECONDARY/SINGLE | 3 | SHORT | 50 | 0.0800 | biglotto_echo_aware_3bet | 0.0000 | 1.0000 | -0.0105 | -0.0135 | 0.7028 |
| BIG_N3_echo3 | SECONDARY/SINGLE | 3 | MID | 300 | 0.1100 | biglotto_echo_aware_3bet | 0.0000 | 1.0000 | 0.0195 | 0.0165 | 0.1876 |
| BIG_N3_echo3 | SECONDARY/SINGLE | 3 | LONG | 750 | 0.1000 | biglotto_echo_aware_3bet | 0.0000 | 1.0000 | 0.0095 | 0.0065 | 0.2878 |
| BIG_N4_ts3markov4 | SECONDARY/SINGLE | 4 | SHORT | 50 | 0.1000 | biglotto_ts3_markov_4bet_w30 | 0.0000 | 1.0000 | -0.0176 | -0.0226 | 0.7476 |
| BIG_N4_ts3markov4 | SECONDARY/SINGLE | 4 | MID | 300 | 0.1267 | biglotto_ts3_markov_4bet_w30 | 0.0000 | 1.0000 | 0.0091 | 0.0041 | 0.4408 |
| BIG_N4_ts3markov4 | SECONDARY/SINGLE | 4 | LONG | 750 | 0.1320 | biglotto_ts3_markov_4bet_w30 | 0.0000 | 1.0000 | 0.0144 | 0.0094 | 0.2295 |

## Limitations
- Retrospective evidence only; not confirmatory and not a future-only result; no claim of improved future prediction success.
- Prize-tier semantics carry source_verification_status=MANUAL_VERIFICATION_REQUIRED (P271B/P271C).
- 50-draw (SHORT) windows are integrity guardrails and cannot support promotion.
- Tickets are the frozen committed P273A identities; portfolios reuse existing strategy tickets without any refitting.
- POWER second-zone-missing rows are excluded as missing eligibility, never imputed or counted as losses.
- Per-draw union-win probability Q is treated as constant across draws by combinatorial symmetry of the outcome; the window null is Binomial(support, Q).
- No monetary budget, EV, ROI, or betting recommendation is computed.
- BIG_LOTTO / POWER_LOTTO portfolios are secondary generalization checks (descriptive only, no promotion verdict).
