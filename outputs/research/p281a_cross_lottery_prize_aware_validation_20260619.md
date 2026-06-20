# P281A — Cross-Lottery Prize-Aware Success Definition and Inferential Validation

> **Local research / replay validation only.** No real publication, no pre-draw manifest, no publication PR, no official target/deadline lookup, no strategy promotion or activation, no registry/production/DB write. `prediction_success_claim = false`.

- **final_classification:** `P281A_CROSS_LOTTERY_PRIZE_AWARE_VALIDATION_PR_OPEN_OBSERVATION_CANDIDATES_NO_PUBLICATION`
- **analytical_outcome:** `OBSERVATION_CANDIDATES_FOUND` (candidates=3, null=29, blocked_support=4)
- task_id: `P281A_CROSS_LOTTERY_PRIZE_AWARE_SUCCESS_DEFINITION_AND_INFERENTIAL_VALIDATION`
- origin_main: `3fdc07fd2e27e64460c134acc433b5cfe0dd2da3`
- scoring_version: `prize_aware_v1` / source_verification_status: `MANUAL_VERIFICATION_REQUIRED`
- frozen cells: **36** (DAILY_539, BIG_LOTTO, POWER_LOTTO); inferential windows: 100, 500, 1500 (+ ALL_AVAILABLE supplementary)
- canonical_payload_digest: `4031800e030fd7ecda253cbf31f465a2edc96f8b960fe82e92a08e2d94a6934d`

## Reconciliation with P273A

- P273A PRIMARY windows [50, 300, 750] received full inference; its **100/500/1500 export was observed-count-only**.
- P281A adds: the inferential layer (random baseline, p-value, Bonferroni, BH-FDR, CIs) on the 100/500/1500 windows P273A left as observed-count-only, plus cross-lottery success-definition verification, contribution decomposition, and support audit
- methodology reused verbatim: `true`

## Lottery success definitions (verified against the committed scorer)

| lottery | endpoint | condition | min tier |
|---|---|---|---|
| DAILY_539 | `D539_ANY_PRIZE_AWARE_WIN` | `hit_count >= 2` | 肆獎 (2-match) |
| BIG_LOTTO | `BIG_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)` | 普獎 (2-match + special) |
| POWER_LOTTO | `POWER_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)` | 普獎 (1-match + second-zone) |

### Truth-table edges (via the real P271C scorer)

**DAILY_539**

| main_hits | special | tier | any_prize_win | is_m3_plus | note |
|---:|---:|---|:--:|:--:|---|
| 5 | 0 | `D539_FIRST_PRIZE` | ✅ | ✓ | M5 first prize |
| 3 | 0 | `D539_THIRD_PRIZE` | ✅ | ✓ | M3 wins |
| 2 | 0 | `D539_FOURTH_PRIZE` | ✅ | · | M2 lowest prize wins |
| 1 | 0 | `D539_NO_PRIZE` | ❌ | · | M1 loses |
| 0 | 0 | `D539_NO_PRIZE` | ❌ | · | M0 loses |

**BIG_LOTTO**

| main_hits | special | tier | any_prize_win | is_m3_plus | note |
|---:|---:|---|:--:|:--:|---|
| 6 | 0 | `BIG_FIRST_PRIZE` | ✅ | ✓ | M6 first prize (special irrelevant) |
| 3 | 0 | `BIG_SEVENTH_PRIZE` | ✅ | ✓ | M3 wins |
| 2 | 1 | `BIG_CONSOLATION_PRIZE` | ✅ | · | M2+special wins (consolation) |
| 2 | 0 | `BIG_NO_PRIZE` | ❌ | · | M2 without special loses |
| 1 | 1 | `BIG_NO_PRIZE` | ❌ | · | M1+special loses |

**POWER_LOTTO**

| main_hits | special | tier | any_prize_win | is_m3_plus | note |
|---:|---:|---|:--:|:--:|---|
| 6 | 1 | `POWER_FIRST_PRIZE` | ✅ | ✓ | M6+second first prize |
| 3 | 0 | `POWER_NINTH_PRIZE` | ✅ | ✓ | M3 wins |
| 2 | 1 | `POWER_EIGHTH_PRIZE` | ✅ | · | M2+second wins |
| 1 | 1 | `POWER_CONSOLATION_PRIZE` | ✅ | · | M1+second wins (consolation) |
| 1 | 0 | `POWER_NO_PRIZE` | ❌ | · | M1 without second loses |
| 2 | 0 | `POWER_NO_PRIZE` | ❌ | · | M2 without second loses |
| 0 | 1 | `POWER_NO_PRIZE` | ❌ | · | 0+second loses (needs >=1 first-zone hit) |

## Random baseline + correction config

- baseline: analytic exact distinct-ticket without-replacement q_N = 1 - C(T-W,N)/C(T,N) per draw; aggregated via exact binomial (constant N) or exact Poisson-binomial (varying N)
- CIs: Wilson + Clopper-Pearson 95% (reused); gates: support >= 30 AND expected >= 5.0
- correction family: lottery x strategy x endpoint x window = **m=108** (windows [100, 500, 1500]); alpha=0.05
- evaluable tested (cell,window): **87**; any beats random uncorrected: `true`; any survives Bonferroni: `true`
- BH-FDR (descriptive only) rejections: 17
- Monte-Carlo cross-check (seed=42, trials=40000, NOT used for inference): all_within_tolerance=`true`

## Per-cell verdicts (windows 100 / 500 / 1500)

| lottery | strategy | support | verdict | overall | LONG obs_rate | LONG baseline | LONG Δpp | LONG bonf_p | prize−legacy Δ |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| DAILY_539 | 539_3bet_orthogonal | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.11933 | 0.11397 | +0.5360 | 1.0000 | +0.10867 |
| DAILY_539 | acb_1bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.11933 | 0.11397 | +0.5360 | 1.0000 | +0.10867 |
| DAILY_539 | acb_markov_midfreq | ENOUGH_SUPPORT | **NULL** | NULL | 0.11333 | 0.11397 | -0.0640 | 1.0000 | +0.10000 |
| DAILY_539 | acb_markov_midfreq_3bet | ENOUGH_SUPPORT | **OBSERVATION_CANDIDATE** | GO_CANDIDATE_RESEARCH_ONLY | 0.35067 | 0.30443 | +4.6235 | 0.0073 | +0.31600 |
| DAILY_539 | acb_single_539 | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.11933 | 0.11397 | +0.5360 | 1.0000 | +0.10867 |
| DAILY_539 | daily539_f4cold | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.13933 | 0.11397 | +2.5360 | 0.1602 | +0.13067 |
| DAILY_539 | daily539_f4cold_3bet | ENOUGH_SUPPORT | **OBSERVATION_CANDIDATE** | GO_CANDIDATE_RESEARCH_ONLY | 0.36200 | 0.30443 | +5.7569 | 0.0001 | +0.32800 |
| DAILY_539 | daily539_f4cold_5bet | ENOUGH_SUPPORT | **OBSERVATION_CANDIDATE** | GO_CANDIDATE_RESEARCH_ONLY | 0.55400 | 0.45395 | +10.0050 | 0.0000 | +0.49067 |
| DAILY_539 | daily539_markov_cold | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.12067 | 0.11397 | +0.6693 | 1.0000 | +0.10933 |
| DAILY_539 | markov_1bet_539 | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.12067 | 0.11397 | +0.6693 | 1.0000 | +0.10933 |
| DAILY_539 | midfreq_acb_2bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.13267 | 0.11397 | +1.8693 | 1.0000 | +0.12000 |
| DAILY_539 | midfreq_fourier_2bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.13267 | 0.11397 | +1.8693 | 1.0000 | +0.12000 |
| DAILY_539 | p0b_539_3bet_f_cold_fmid | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.14067 | 0.11397 | +2.6693 | 0.0962 | +0.13200 |
| DAILY_539 | p0c_539_3bet_f_cold_x2 | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.14067 | 0.11397 | +2.6693 | 0.0962 | +0.13200 |
| DAILY_539 | zone_gap_3bet_539 | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.10467 | 0.11397 | -0.9307 | 1.0000 | +0.09733 |
| BIG_LOTTO | bet2_fourier_expansion_biglotto | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.03600 | 0.03095 | +0.5048 | 1.0000 | +0.01200 |
| BIG_LOTTO | biglotto_deviation_2bet | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.03600 | 0.03095 | +0.5048 | 1.0000 | +0.01200 |
| BIG_LOTTO | biglotto_echo_aware_3bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.09667 | 0.09001 | +0.6656 | 1.0000 | +0.03200 |
| BIG_LOTTO | biglotto_triple_strike | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.03533 | 0.03095 | +0.4382 | 1.0000 | +0.01133 |
| BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.13067 | 0.11818 | +1.2490 | 1.0000 | +0.04400 |
| BIG_LOTTO | cold_complement_biglotto | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.02667 | 0.03095 | -0.4285 | 1.0000 | +0.01200 |
| BIG_LOTTO | coldpool15_biglotto | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.02667 | 0.03095 | -0.4285 | 1.0000 | +0.01200 |
| BIG_LOTTO | fourier30_markov30_biglotto | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.02400 | 0.03095 | -0.6952 | 1.0000 | +0.01000 |
| BIG_LOTTO | markov_2bet_biglotto | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.02533 | 0.03095 | -0.5618 | 1.0000 | +0.01000 |
| BIG_LOTTO | markov_single_biglotto | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.02533 | 0.03095 | -0.5618 | 1.0000 | +0.01000 |
| BIG_LOTTO | ts3_regime_3bet | LOW_SUPPORT | **NULL** | INSUFFICIENT_SUPPORT | 0.03533 | 0.03095 | +0.4382 | 1.0000 | +0.01133 |
| POWER_LOTTO | cold_complement_2bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.10533 | 0.11783 | -1.2496 | 1.0000 | +0.06867 |
| POWER_LOTTO | fourier30_markov30_2bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.12275 | 0.11783 | +0.4919 | 1.0000 | +0.08205 |
| POWER_LOTTO | fourier_rhythm_3bet | NO_SECOND_ZONE_SUPPORT | **BLOCKED_SUPPORT** | INSUFFICIENT_SUPPORT | — | — | — | — | — |
| POWER_LOTTO | midfreq_fourier_2bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.12133 | 0.11783 | +0.3504 | 1.0000 | +0.07467 |
| POWER_LOTTO | midfreq_fourier_mk_3bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.12800 | 0.11783 | +1.0170 | 1.0000 | +0.08400 |
| POWER_LOTTO | power_fourier_rhythm_2bet | NO_SECOND_ZONE_SUPPORT | **BLOCKED_SUPPORT** | INSUFFICIENT_SUPPORT | — | — | — | — | — |
| POWER_LOTTO | power_orthogonal_5bet | NO_SECOND_ZONE_SUPPORT | **BLOCKED_SUPPORT** | INSUFFICIENT_SUPPORT | — | — | — | — | — |
| POWER_LOTTO | power_precision_3bet | NO_SECOND_ZONE_SUPPORT | **BLOCKED_SUPPORT** | INSUFFICIENT_SUPPORT | — | — | — | — | — |
| POWER_LOTTO | pp3_freqort_4bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.12933 | 0.11783 | +1.1504 | 1.0000 | +0.07533 |
| POWER_LOTTO | zonal_entropy_2bet | ENOUGH_SUPPORT | **NULL** | DESCRIPTIVE_ONLY | 0.10600 | 0.11783 | -1.1830 | 1.0000 | +0.06933 |

## Observation candidates (research-only; NOT promoted, NOT activated)

- `DAILY_539/acb_markov_midfreq_3bet` — research-only observation candidate (stability=STABILITY_PASS, LONG Δpp=+4.6235, bonf_p=0.0073). Requires separate future-only/OOS authorization before any promotion.
- `DAILY_539/daily539_f4cold_3bet` — research-only observation candidate (stability=STABILITY_PASS, LONG Δpp=+5.7569, bonf_p=0.0001). Requires separate future-only/OOS authorization before any promotion.
- `DAILY_539/daily539_f4cold_5bet` — research-only observation candidate (stability=STABILITY_PASS, LONG Δpp=+10.0050, bonf_p=0.0000). Requires separate future-only/OOS authorization before any promotion.

## Cross-lottery summary

| lottery | cells | mean prize−legacy Δ (LONG) | missing 2nd-zone rows | top strategy changed? | full order changed? |
|---|---:|---:|---:|:--:|:--:|
| DAILY_539 | 15 | +0.16742 | 0 | no | yes |
| BIG_LOTTO | 11 | +0.01606 | 0 | no | yes |
| POWER_LOTTO | 10 | +0.07568 | 27104 | no | yes |

- success-def differs most from M3+: **DAILY_539**
- most affected by missing second-zone: **POWER_LOTTO**
- BIG already uses M2+special (P280AT). P281A does not change the BIG NULL/no-edge conclusion; the BIG runner remains no-edge / no-claim.
- POWER ranking should be treated as BLOCKED pending adequate predicted second-zone support wherever NO_SECOND_ZONE_SUPPORT / heavy missing-second-zone exclusion is observed.
- DAILY_539 is validatable with the M2+ (>=2 main) baseline; it carries the most lower-tier contribution.

## Limitations

- Backward replay over already-drawn historical data; not prospective and not out-of-sample for live deployment.
- source_verification_status = MANUAL_VERIFICATION_REQUIRED: official prize-table pages were not machine-verified (carried from P271B/C).
- POWER_LOTTO support is reduced by missing-predicted-second-zone exclusions; missing values are NEVER backfilled.
- Observation candidates (if any) are research-only and require a separate, separately-authorized future-only / OOS validation before any promotion; none is performed or implied here.
- all_available window is descriptive only and excluded from the Bonferroni family.

## Next recommended research step

Independent audit of this validation PR; then, only if observation candidates exist, a separately-authorized prospective / out-of-sample validation. POWER strategy ranking should remain blocked pending a separate predicted-second-zone data-support task. No promotion, activation, or publication without explicit Owner authorization.
