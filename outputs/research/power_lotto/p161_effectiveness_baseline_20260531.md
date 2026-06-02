# P161 — POWER_LOTTO Replay Strategy Effectiveness Baseline

- **Task**: P161_POWER_LOTTO_REPLAY_STRATEGY_EFFECTIVENESS_BASELINE (v2.1)
- **Generated**: 2026-06-01T05:22:30.387697+00:00
- **Classification**: `P161_POWER_LOTTO_EFFECTIVENESS_BASELINE_READY`
- **Mode**: READ-ONLY (PRAGMA query_only=ON). DB writes: 0.

## DB snapshot

- total rows before/after: **94924 / 94924** (unchanged: True)
- POWER_LOTTO rows: 36104 | strategies: 10 | distinct draws: 1551
- **Statistical unit**: distinct target_draw (n=1551). 36104 rows = sum over strategies of (n_draws x n_bet_slots). The statistical unit is distinct target_draw (1551), NOT 36104 rows.

## Random baselines

- main E[hit_count] = `6 * 6/38 = 36/38` = **0.947368**
- special = `1/8 (POWER_LOTTO special pool 1..8)` = **0.125**

## §2 Main vs Special (SEPARATED)

- Pool main avg hit_count = **0.967427** (delta vs random = +0.020059, verdict **ABOVE**)
- Special (predicted_special NOT NULL, n=9000): hit_rate = **0.118111** (delta vs 0.125 = -0.006889, verdict **BELOW**)
- _Diluted all-row special avg (DO NOT USE): 0.029443_

## §1+§3 Per-strategy table

| strategy_id | lifecycle | n_draws | bet_rows | slots | mean hit | 95% CI | vs rand | p_raw | p_bonf | p_BH | special rate (n) |
|---|---|--:|--:|--:|--:|---|:--:|--:|--:|--:|---|
| cold_complement_2bet | ONLINE | 1500 | 1500 | 1 | 0.9407 | [0.8996, 0.9817] | BELOW | 0.748908 | 1.0 | 0.80963 | 0.1140 (1500) |
| fourier30_markov30_2bet | ONLINE | 1501 | 1501 | 1 | 0.9647 | [0.9228, 1.0066] | ABOVE | 0.417371 | 1.0 | 0.771653 | 0.1247 (1500) |
| fourier_rhythm_3bet | ONLINE | 1501 | 4503 | 3 | 0.9749 | [0.9483, 1.0015] | ABOVE | 0.042793 | 1.0 | 0.142867 | — |
| midfreq_fourier_2bet | RETIRED | 1500 | 1500 | 1 | 0.9727 | [0.9306, 1.0148] | ABOVE | 0.238993 | 1.0 | 0.531918 | 0.1187 (1500) |
| midfreq_fourier_mk_3bet | ONLINE | 1500 | 4500 | 3 | 0.9896 | [0.9586, 1.0205] | ABOVE | 0.007594 | 0.30376 | 0.091493 | 0.1187 (1500) |
| power_fourier_rhythm_2bet | ONLINE | 1500 | 3000 | 2 | 0.9633 | [0.9367, 0.9899] | ABOVE | 0.239363 | 1.0 | 0.531918 | — |
| power_orthogonal_5bet | ONLINE | 1550 | 7550 | 5 | 0.9612 | [0.9365, 0.9858] | ABOVE | 0.273085 | 1.0 | 0.574916 | — |
| power_precision_3bet | ONLINE | 1550 | 4550 | 3 | 0.9563 | [0.9329, 0.9798] | ABOVE | 0.453953 | 1.0 | 0.771653 | — |
| pp3_freqort_4bet | ONLINE | 1500 | 6000 | 4 | 0.9710 | [0.9451, 0.9969] | ABOVE | 0.073533 | 1.0 | 0.226255 | 0.1187 (1500) |
| zonal_entropy_2bet | ONLINE | 1500 | 1500 | 1 | 0.9460 | [0.9048, 0.9872] | BELOW | 0.948124 | 1.0 | 0.972435 | 0.1140 (1500) |

Per-strategy hit_count distribution (0..6 main hits):

| strategy_id | 0 | 1 | 2 | 3 | 4 | 5 | 6 |
|---|--:|--:|--:|--:|--:|--:|--:|
| cold_complement_2bet | 477 | 694 | 274 | 51 | 4 | 0 | 0 |
| fourier30_markov30_2bet | 472 | 675 | 293 | 57 | 4 | 0 | 0 |
| fourier_rhythm_3bet | 1416 | 1997 | 887 | 193 | 10 | 0 | 0 |
| midfreq_fourier_2bet | 466 | 681 | 283 | 68 | 2 | 0 | 0 |
| midfreq_fourier_mk_3bet | 1409 | 1947 | 940 | 190 | 14 | 0 | 0 |
| power_fourier_rhythm_2bet | 968 | 1317 | 579 | 129 | 7 | 0 | 0 |
| power_orthogonal_5bet | 2406 | 3356 | 1464 | 307 | 17 | 0 | 0 |
| power_precision_3bet | 1463 | 2014 | 885 | 177 | 11 | 0 | 0 |
| pp3_freqort_4bet | 1913 | 2635 | 1178 | 261 | 13 | 0 | 0 |
| zonal_entropy_2bet | 483 | 671 | 291 | 54 | 1 | 0 | 0 |

## §4 Lifecycle-group comparison (DESCRIPTIVE)

_DESCRIPTIVE_ONLY_

| lifecycle | n_strategies | bet_rows | group mean hit | vs rand |
|---|--:|--:|--:|:--:|
| ONLINE | 9 | 34604 | 0.966511 | ABOVE |
| RETIRED | 1 | 1500 | 0.972667 | ABOVE |

**Survivorship caveat**: Lifecycle labels (ONLINE/RETIRED/REJECTED/OBSERVATION) were assigned partly on PAST performance/governance. Comparing 'ONLINE > RETIRED' is therefore partly circular (survivorship / selection bias) and is NOT evidence that the label predicts future hit rate UNLESS restricted to draws AFTER the label was assigned. No such post-label split is performed here.

_Among the 10 POWER_LOTTO strategies WITH replay data: 9 ONLINE, 1 RETIRED (midfreq_fourier_2bet, see cross-lottery mismatch). No REJECTED or OBSERVATION strategies carry POWER_LOTTO replay rows, so a 4-way lifecycle comparison is not possible with this data._

## §5 Multi-bet slot comparison (coverage-normalized)

Each bet slot = exactly 6 main numbers (one bet). Per-slot means are compared like-for-like; we do NOT sum hits across slots, which would inflate hit rate simply by selecting more numbers (L37 geometric-benefit trap). Only bet slots actually present in the DB are analysed (3 '2bet' strategies are stored first-bet-only).

_DB-stored bet counts differ from strategy names: cold_complement_2bet / fourier30_markov30_2bet / zonal_entropy_2bet / midfreq_fourier_2bet are stored as bet_index=1 only. power_fourier_rhythm_2bet=2, fourier_rhythm_3bet/midfreq_fourier_mk_3bet/power_precision_3bet=3, pp3_freqort_4bet=4, power_orthogonal_5bet=5._

Aggregate by bet position (across strategies that have the slot):

| bet_index | #strategies | n_rows | mean hit | 95% CI | vs rand | p_raw |
|--:|--:|--:|--:|---|:--:|--:|
| 1 | 10 | 15102 | 0.982519 | [0.9691, 0.9959] | ABOVE | 0.0 |
| 2 | 6 | 9001 | 0.978780 | [0.9613, 0.9963] | ABOVE | 0.000428 |
| 3 | 5 | 7501 | 0.940008 | [0.9214, 0.9586] | BELOW | 0.437191 |
| 4 | 2 | 3000 | 0.939333 | [0.9095, 0.9692] | BELOW | 0.598146 |
| 5 | 1 | 1500 | 0.940667 | [0.8996, 0.9817] | BELOW | 0.748908 |

## §6 Multiple-testing correction

- Family size (finite p): **40** (methods: bonferroni, benjamini_hochberg, alpha=0.05)
- Survivors above-random after Bonferroni: **NONE**
- Survivors above-random after BH: **NONE**
- **Any strategy beats random after correction (PRIMARY, per-strategy main per-draw mean): False**
- Family = 10 strategy-main tests + per-strategy special tests + per-bet-slot tests. No naked ranking: a min n_draws>=500 gate and 95% CIs are enforced before ranking (L47/L91).

- Secondary — individual bet-SLOT survivors after Bonferroni: **['slot::midfreq_fourier_mk_3bet#bet1']**
- Secondary — individual bet-SLOT survivors after BH: **['slot::midfreq_fourier_mk_3bet#bet1']**
- **Slot survivor caveat**: One INDIVIDUAL bet slot — midfreq_fourier_mk_3bet bet_index=1 (per-draw mean ~1.027, raw p~0.0003, p_bonf~0.010, p_BH~0.010) — does survive correction as an ABOVE-random slot. This is a DESCRIPTIVE, FULL-HISTORY (in-sample) finding only. It is NOT a predictive claim: (a) it is the single first bet of a strategy whose 3-bet per-draw aggregate does NOT survive (bet3 sits below random), (b) no walk-forward / OOS>=500 evaluation has been run (L101), and (c) selecting the best-looking slot post hoc on full history is itself a selection effect. Treat as a hypothesis to test prospectively, NOT as evidence the slot 'works'.

## §7 Leakage-safe labeling

- All comparisons in this report are **DESCRIPTIVE** (in-sample).
- PREDICTIVE claims require walk-forward / only-past-data evaluation with an OOS window >= 500 distinct draws (L101). This baseline selects/ranks strategies on the FULL replay history and therefore CANNOT assert that any strategy 'works' going forward.
- Predictive status: **NOT_ESTABLISHED_NO_WALK_FORWARD**

## Best single strategy

- **midfreq_fourier_mk_3bet** (lifecycle ONLINE, n_draws=1500): mean hit = 0.989556, CI [0.958583, 1.020528], vs random **ABOVE**
- p_raw=0.007594, p_bonferroni=0.30376, p_BH=0.091493
- **Beats random after correction: False**

## Cross-lottery registry mismatch (flagged)

- `midfreq_fourier_2bet`: registry lottery types ['DAILY_539'] but observed replay rows under POWER_LOTTO (lifecycle resolved by id = RETIRED).

## Honest NULL statement

POWER_LOTTO replay strategies are, in aggregate and individually after multiple-testing correction, statistically indistinguishable from a fair-random 6-of-38 process on main numbers, and at/below random on the special number. This is an EXPECTED, ACCEPTABLE NULL/at-random result. No strategy is shown to beat random out-of-sample; NO betting advice and NO guaranteed-win claim is made or implied.
