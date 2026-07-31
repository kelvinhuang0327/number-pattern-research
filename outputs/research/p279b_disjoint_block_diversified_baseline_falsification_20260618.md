# P279B Frozen DAILY_539 Disjoint-Block Diversified-Baseline Falsification

> Retrospective artifact-only falsification. This is not OOS confirmation, a prediction-success claim, strategy promotion, betting value, or deployment authorization.

- Source commit: `8004c32c47cb99576ef5689f967c05306a83670c`
- Endpoint: `D539_ANY_PRIZE_AWARE_WIN` (hit_count >= 2; at most one success per draw per candidate)
- Canonical payload digest: `88e573947825c321bc8513f06dcfbe9b860445c688a30cbb32002900b604775e`
- Research verdict: `ONE_FALSIFIED_TWO_INCONCLUSIVE_ZERO_RETAINED`

## Source integrity

| Source | Path | Raw SHA-256 | Canonical digest |
|---|---|---|---|
| primary_observed_counts | `outputs/research/p273a_primary_window_observed_counts_20260615.json` | `14b2ed29628111f32925909ba07e9be0b3de48a04ee4b0877e39c1dfa4e51b73` | `65a4cc59f5ab64d685890566e38493b0295e622f351e0527782f1dce2f38645f` |
| distinct_ticket_identity | `outputs/research/p273a_distinct_ticket_identity_20260615.json` | `b10b916c00f807ace7342250b788dbf1d62c12a0b8e2d5aa627b5a4eb25089b0` | `ad85e447dfc7db7afd70e9fdde928bb12a2ae367d6c1f23f14b7e3504701ae51` |
| inferential_validation | `outputs/research/p273a_prize_aware_inferential_validation_20260615.json` | `ab923a06327afcc8595f224e65bcd98fec0cfdeaf31b10aeeb86ac54ed6648fe` | `5666e67c88e5f3b1233f2d6d5a5f86746c4f7605ae98bda3f2d59ec5aa0b2fb4` |
| unified_success_matrix | `outputs/research/p275b_unified_prize_aware_success_matrix_20260616.json` | `0a81b9e652b5d84e80ebf16e9d5c5ff625746d8c46e6cfe5d38e6cfe312cf964` | `c1b99e57024f528e39e4beeca03cb22dd3278eb1d356aafbe48d8485695102f6` |
| coverage_complementarity | `outputs/research/p276b_fixed_n_coverage_complementarity_20260617.json` | `ed6ba267de53443c46ecff76914887a4595aaaa2762fa31ed46d602b7fac3264` | `438dca463edb574a3ed346ac616728d4621e669d25f010efeb9909478d68657e` |

## Frozen candidates and disjoint counts

| Candidate | N | latest 50 | latest 300 | latest 750 | D50 | P250 | P450 | Recombined |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `acb_markov_midfreq_3bet` | 3 | 18 | 120 | 268 | 18 | 102 | 148 | PASS |
| `daily539_f4cold_3bet` | 3 | 23 | 101 | 275 | 23 | 78 | 174 | PASS |
| `daily539_f4cold_5bet` | 5 | 35 | 170 | 425 | 35 | 135 | 255 | PASS |

All nested supports are exactly 50/300/750. Every subtraction is a non-negative integer and both recombination identities pass.

## Exact diversified baseline

| N | Winning outcomes | Total outcomes | Exact probability | P276 MC | Reconciliation |
|---:|---:|---:|---:|---:|---|
| 3 | 187563 | 575757 | 0.325767641557 | 0.32541 | `RECONCILED_EXACT_SUPERSEDES_MC_FOR_P279B_ONLY` |
| 5 | 297105 | 575757 | 0.516024989709 | 0.51586 | `RECONCILED_EXACT_SUPERSEDES_MC_FOR_P279B_ONLY` |

Every valid mutually disjoint N-ticket family is related by a permutation of the 39 number labels. Uniform five-number draws and the overlap>=2 union event are invariant under that bijection, so the winning-outcome count is unchanged.
 Three alternative mutually disjoint ticket families were exhaustively verified; each produced the same N=3 and N=5 numerator. Exact probabilities supersede P276 Monte Carlo uncertainty for P279B only.

## Six primary tests

Bonferroni family: m=6, alpha=0.05, per-test threshold=0.00833333333333. D50 is excluded.

| Candidate | Block | n | k | Rate | Exact q | Excess | Direction | Raw p | Adjusted p | Pass |
|---|---|---:|---:|---:|---:|---:|---|---:|---:|---|
| `acb_markov_midfreq_3bet` | P250 | 250 | 102 | 0.408 | 0.325767641557 | 0.0822323584429 | POSITIVE | 0.00683243520276 | 0.0409946112165 | TRUE |
| `acb_markov_midfreq_3bet` | P450 | 450 | 148 | 0.328888888889 | 0.325767641557 | 0.00312124733177 | POSITIVE | 0.880188460297 | 1 | FALSE |
| `daily539_f4cold_3bet` | P250 | 250 | 78 | 0.312 | 0.325767641557 | -0.0137676415571 | NEGATIVE | 0.685751013802 | 1 | FALSE |
| `daily539_f4cold_3bet` | P450 | 450 | 174 | 0.386666666667 | 0.325767641557 | 0.0608990251096 | POSITIVE | 0.00656864788224 | 0.0394118872935 | TRUE |
| `daily539_f4cold_5bet` | P250 | 250 | 135 | 0.54 | 0.516024989709 | 0.0239750102908 | POSITIVE | 0.486468546801 | 1 | FALSE |
| `daily539_f4cold_5bet` | P450 | 450 | 255 | 0.566666666667 | 0.516024989709 | 0.0506416769575 | POSITIVE | 0.0337200235351 | 0.202320141211 | FALSE |

## D50 descriptive results

| Candidate | N | k/50 | Rate | Exact q | Excess | Direction | Two-sided p (descriptive) |
|---|---:|---:|---:|---:|---:|---|---:|
| `acb_markov_midfreq_3bet` | 3 | 18/50 | 0.36 | 0.325767641557 | 0.0342323584429 | POSITIVE | 0.651176510383 |
| `daily539_f4cold_3bet` | 3 | 23/50 | 0.46 | 0.325767641557 | 0.134232358443 | POSITIVE | 0.0495779916873 |
| `daily539_f4cold_5bet` | 5 | 35/50 | 0.7 | 0.516024989709 | 0.183975010291 | POSITIVE | 0.010384590884 |

## Ordinary-random sensitivity

Secondary only: `q = 1 - C(T-W,N)/C(T,N)`, with T=575757 and W=65621. These reproduce committed P273 values and do not control P279B classifications.

| N | Exact ordinary-random probability | P273 reproduced |
|---:|---:|---|
| 3 | 0.304431435743 | PASS |
| 5 | 0.45394956375 | PASS |

| Candidate | Block | N | Rate | Ordinary q | Excess | Direction | Two-sided p (sensitivity) |
|---|---|---:|---:|---:|---:|---|---:|
| `acb_markov_midfreq_3bet` | D50 | 3 | 0.36 | 0.304431435743 | 0.0555685642574 | POSITIVE | 0.442111117763 |
| `acb_markov_midfreq_3bet` | P250 | 3 | 0.408 | 0.304431435743 | 0.103568564257 | POSITIVE | 0.000560651083095 |
| `acb_markov_midfreq_3bet` | P450 | 3 | 0.328888888889 | 0.304431435743 | 0.0244574531463 | POSITIVE | 0.260061953207 |
| `daily539_f4cold_3bet` | D50 | 3 | 0.46 | 0.304431435743 | 0.155568564257 | POSITIVE | 0.0207949398449 |
| `daily539_f4cold_3bet` | P250 | 3 | 0.312 | 0.304431435743 | 0.00756856425737 | POSITIVE | 0.783766972287 |
| `daily539_f4cold_3bet` | P450 | 3 | 0.386666666667 | 0.304431435743 | 0.082235230924 | POSITIVE | 0.000217684230618 |
| `daily539_f4cold_5bet` | D50 | 5 | 0.7 | 0.45394956375 | 0.24605043625 | POSITIVE | 0.000544906104218 |
| `daily539_f4cold_5bet` | P250 | 5 | 0.54 | 0.45394956375 | 0.0860504362503 | POSITIVE | 0.00751413128778 |
| `daily539_f4cold_5bet` | P450 | 5 | 0.566666666667 | 0.45394956375 | 0.112717102917 | POSITIVE | 2.00126243197e-06 |

## Candidate decisions

| Candidate | N | Decision |
|---|---:|---|
| `acb_markov_midfreq_3bet` | 3 | `RETROSPECTIVE_STABILITY_INCONCLUSIVE` |
| `daily539_f4cold_3bet` | 3 | `RETROSPECTIVE_STABILITY_FALSIFIED` |
| `daily539_f4cold_5bet` | 5 | `RETROSPECTIVE_STABILITY_INCONCLUSIVE` |

Project decision counts:
- `RETROSPECTIVE_STABILITY_NOT_FALSIFIED_RETAIN_FOR_FUTURE_ONLY`: 0
- `RETROSPECTIVE_STABILITY_INCONCLUSIVE`: 2
- `RETROSPECTIVE_STABILITY_FALSIFIED`: 1

## Boundaries and limitations

- All blocks are retrospective and were derived from nested committed historical aggregates.
- The disjoint P250 and P450 blocks remove overlap but do not create prospective OOS evidence.
- The exact diversified baseline tests equal-budget number coverage, not every possible null model.
- D50 is descriptive only and cannot rescue, promote, or override either primary block.
- Candidate labels authorize future-only research at most; they do not establish betting value.

- `deployment_authorized=false`
- `network_used=false`
- `prediction_generation_performed=false`
- `prediction_success_claim=false`
- `production_db_copied=false`
- `production_db_opened=false`
- `production_db_queried=false`
- `production_db_written=false`
- `prospective_confirmation_complete=false`
- `registry_mutated=false`
- `replay_generation_performed=false`
- `strategy_promoted=false`
