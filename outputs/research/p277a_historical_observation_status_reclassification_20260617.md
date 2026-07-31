# P277A — Historical Observation Status Reclassification Audit

**Generated:** 2026-06-17T00:00:00+00:00
**Source commit (origin/main):** `b6dd42f14e822a186187b90c50acdfedebe3fd07`
**Canonical payload digest:** `d75f8383c5029c5024279f9e3792d417885cecc202f25740f10406a701f14284`
**prediction_success_claim:** False
**strategy_promoted:** False
**database_opened:** False
**database_write:** False

---

## Owner Dual-Gate Rule

| Gate | Rule |
|------|------|
| Gate 1 (retention) | Beating the governed RANDOM baseline is SUFFICIENT to retain a strategy/portfolio as an OBSERVATION CANDIDATE. This is the minimum retention criterion. |
| Gate 2 (promotion) | Beating the BEST EQUAL-BUDGET strategy is a STRONGER priority/promotion criterion — NOT the minimum observation-retention criterion. |

> **Implication:** A strategy MAY beat random (Gate 1 PASS) while ALSO failing to beat the best equal-budget strategy. This is ALLOWED and not contradictory. Gate 1 alone is sufficient for OBSERVATION_POTENTIAL classification.

---

## Classification Summary

- Unique strategy-cell count: **36**
- Portfolio count: **8**
- Endpoint count: **3**
- Source artifact count: **18**

### Original Classifications (P275B)

| Original Classification | Count |
|------------------------|-------|
| DESCRIPTIVE_ONLY | 16 |
| GO_CANDIDATE_RESEARCH_ONLY | 3 |
| INSUFFICIENT_SUPPORT | 14 |
| NULL | 3 |

### New Classifications (P277A Dual-Gate)

| New Classification | Count |
|-------------------|-------|
| HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL | 1 |
| INSUFFICIENT_RANDOM_BASELINE_EVIDENCE | 4 |
| NO_EVIDENCE_OVER_RANDOM | 15 |
| OBSERVATION_POTENTIAL_ABOVE_RANDOM | 12 |
| OBSERVATION_SUPPORTED_ABOVE_RANDOM | 3 |
| UNDERPOWERED_OBSERVATION_POTENTIAL | 1 |

### Observation Counts

- Point-estimate observations only: **12**
- Corrected-supported observations: **3**
- Competitive observations: **0**
- Strong research candidates: **0**
- Underpowered observations: **1**
- OOS-superseded observations: **1**
- No evidence over random: **15**
- Missing-baseline items: **4**
- Items beating random but NOT best strategy: **14**
- Items beating BOTH random AND best strategy: **3**

---

## P276B Portfolio Table

Scientific verdict (preserved): **NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE**

| Portfolio ID | Kind | Budget | Lottery | Obs Rate | Ord Rand Base | Div Rand Base | Ord Status | Div Status | Best EQ Status | Current Mapping |
|-------------|------|--------|---------|----------|---------------|---------------|------------|------------|----------------|-----------------|
| D539_N3_f4cold3 | SINGLE | 3 | DAILY_539 | 0.3667 | 0.3045 | 0.3254 | ABOVE_RANDOM | ABOVE_RANDOM | EQUAL_TO_BEST_EQUAL_BUDGET | OBSERVATION_SUPPORTED_ABOVE_RANDOM |
| D539_N3_acbmm3 | SINGLE | 3 | DAILY_539 | 0.3573 | 0.3045 | 0.3254 | ABOVE_RANDOM | ABOVE_RANDOM | EQUAL_TO_BEST_EQUAL_BUDGET | OBSERVATION_SUPPORTED_ABOVE_RANDOM |
| D539_N3_f4cold3_x_acbmm3 | CROSS | 3 | DAILY_539 | 0.3333 | 0.3045 | 0.3254 | ABOVE_RANDOM | ABOVE_RANDOM | BELOW_BEST_EQUAL_BUDGET | OBSERVATION_POTENTIAL_ABOVE_RANDOM |
| D539_N5_f4cold5 | SINGLE | 5 | DAILY_539 | 0.5667 | 0.4542 | 0.5159 | ABOVE_RANDOM | ABOVE_RANDOM | EQUAL_TO_BEST_EQUAL_BUDGET | OBSERVATION_SUPPORTED_ABOVE_RANDOM |
| D539_N5_f4cold5_x_acbmm3 | CROSS | 5 | DAILY_539 | 0.4973 | 0.4542 | 0.5159 | ABOVE_RANDOM | AT_OR_BELOW_RANDOM | BELOW_BEST_EQUAL_BUDGET | OBSERVATION_POTENTIAL_ABOVE_RANDOM |
| D539_N5_f4cold5_x_f4cold3_x_acbmm3 | CROSS | 5 | DAILY_539 | 0.4947 | 0.4542 | 0.5159 | ABOVE_RANDOM | AT_OR_BELOW_RANDOM | BELOW_BEST_EQUAL_BUDGET | OBSERVATION_POTENTIAL_ABOVE_RANDOM |
| BIG_N3_echo3 | SINGLE | 3 | BIG_LOTTO | 0.1000 | 0.0905 | 0.0935 | ABOVE_RANDOM | ABOVE_RANDOM | EQUAL_TO_BEST_EQUAL_BUDGET | OBSERVATION_POTENTIAL_ABOVE_RANDOM |
| BIG_N4_ts3markov4 | SINGLE | 4 | BIG_LOTTO | 0.1320 | 0.1176 | 0.1226 | ABOVE_RANDOM | ABOVE_RANDOM | EQUAL_TO_BEST_EQUAL_BUDGET | OBSERVATION_POTENTIAL_ABOVE_RANDOM |

---

## Required Research Questions

### Q1: How many strategy cells pass the random-baseline observation gate?

**Answer:** 16 strategy cells pass the random-baseline observation gate (observed prize-aware success rate > governed random null baseline, adequate support, OOS not NULL).

**Identities:**
- `BIG_LOTTO/bet2_fourier_expansion_biglotto`
- `BIG_LOTTO/biglotto_deviation_2bet`
- `BIG_LOTTO/biglotto_echo_aware_3bet`
- `BIG_LOTTO/biglotto_ts3_markov_4bet_w30`
- `DAILY_539/539_3bet_orthogonal`
- `DAILY_539/acb_1bet`
- `DAILY_539/acb_markov_midfreq_3bet`
- `DAILY_539/acb_single_539`
- `DAILY_539/daily539_f4cold`
- `DAILY_539/daily539_f4cold_3bet`
- `DAILY_539/daily539_f4cold_5bet`
- `DAILY_539/midfreq_acb_2bet`
- `DAILY_539/p0b_539_3bet_f_cold_fmid`
- `DAILY_539/p0c_539_3bet_f_cold_x2`
- `POWER_LOTTO/midfreq_fourier_mk_3bet`
- `POWER_LOTTO/pp3_freqort_4bet`

### Q2: How many are point-estimate observations only?

**Answer:** 12 strategy cells have point-estimate observation only (above random but corrected p >= 0.05 or no inference possible).

**Identities:**
- `BIG_LOTTO/bet2_fourier_expansion_biglotto`
- `BIG_LOTTO/biglotto_deviation_2bet`
- `BIG_LOTTO/biglotto_echo_aware_3bet`
- `BIG_LOTTO/biglotto_ts3_markov_4bet_w30`
- `DAILY_539/539_3bet_orthogonal`
- `DAILY_539/acb_1bet`
- `DAILY_539/acb_single_539`
- `DAILY_539/daily539_f4cold`
- `DAILY_539/midfreq_acb_2bet`
- `DAILY_539/p0b_539_3bet_f_cold_fmid`
- `DAILY_539/p0c_539_3bet_f_cold_x2`
- `POWER_LOTTO/pp3_freqort_4bet`

### Q3: How many have corrected support?

**Answer:** 3 strategy cells have Bonferroni-corrected support (corrected p < 0.05 in at least one primary window of the 108-hypothesis family).

**Identities:**
- `DAILY_539/acb_markov_midfreq_3bet`
- `DAILY_539/daily539_f4cold_3bet`
- `DAILY_539/daily539_f4cold_5bet`

### Q4: How many beat random but not the best strategy?

**Answer:** 14 strategy cells beat random but do not beat the best equal-budget strategy in the same lottery/budget bucket.

**Identities:**
- `BIG_LOTTO/bet2_fourier_expansion_biglotto`
- `BIG_LOTTO/biglotto_echo_aware_3bet`
- `BIG_LOTTO/biglotto_ts3_markov_4bet_w30`
- `DAILY_539/539_3bet_orthogonal`
- `DAILY_539/acb_1bet`
- `DAILY_539/acb_markov_midfreq_3bet`
- `DAILY_539/acb_single_539`
- `DAILY_539/daily539_f4cold`
- `DAILY_539/daily539_f4cold_5bet`
- `DAILY_539/midfreq_acb_2bet`
- `DAILY_539/midfreq_fourier_2bet`
- `DAILY_539/p0b_539_3bet_f_cold_fmid`
- `DAILY_539/p0c_539_3bet_f_cold_x2`
- `POWER_LOTTO/pp3_freqort_4bet`

### Q5: How many beat both random and best strategy?

**Answer:** 3 strategy cells beat both the random baseline AND the best equal-budget strategy.

**Identities:**
- `BIG_LOTTO/biglotto_deviation_2bet`
- `DAILY_539/daily539_f4cold_3bet`
- `POWER_LOTTO/midfreq_fourier_mk_3bet`

### Q6: How many remain NULL vs random?

**Answer:** 16 strategy cells remain NULL vs random (NO_EVIDENCE_OVER_RANDOM or superseded by OOS null).

**Identities:**
- `BIG_LOTTO/biglotto_triple_strike`
- `BIG_LOTTO/cold_complement_biglotto`
- `BIG_LOTTO/coldpool15_biglotto`
- `BIG_LOTTO/fourier30_markov30_biglotto`
- `BIG_LOTTO/markov_2bet_biglotto`
- `BIG_LOTTO/markov_single_biglotto`
- `BIG_LOTTO/ts3_regime_3bet`
- `DAILY_539/acb_markov_midfreq`
- `DAILY_539/daily539_markov_cold`
- `DAILY_539/markov_1bet_539`
- `DAILY_539/midfreq_fourier_2bet`
- `DAILY_539/zone_gap_3bet_539`
- `POWER_LOTTO/cold_complement_2bet`
- `POWER_LOTTO/fourier30_markov30_2bet`
- `POWER_LOTTO/midfreq_fourier_2bet`
- `POWER_LOTTO/zonal_entropy_2bet`

### Q7: How many earlier observations are superseded by OOS NULL?

**Answer:** 1 earlier observation(s) superseded by OOS NULL: DAILY_539/midfreq_fourier_2bet

**Identities:**
- `DAILY_539/midfreq_fourier_2bet`

### Q8: Which P276B portfolios beat random but not the best constituent?

**Answer:** 8 P276B portfolio(s) beat ordinary random but do NOT beat the best equal-budget constituent: D539_N3_f4cold3, D539_N3_acbmm3, D539_N3_f4cold3_x_acbmm3, D539_N5_f4cold5, D539_N5_f4cold5_x_acbmm3, D539_N5_f4cold5_x_f4cold3_x_acbmm3, BIG_N3_echo3, BIG_N4_ts3markov4

**Identities:**
- `D539_N3_f4cold3`
- `D539_N3_acbmm3`
- `D539_N3_f4cold3_x_acbmm3`
- `D539_N5_f4cold5`
- `D539_N5_f4cold5_x_acbmm3`
- `D539_N5_f4cold5_x_f4cold3_x_acbmm3`
- `BIG_N3_echo3`
- `BIG_N4_ts3markov4`

### Q9: Which identities lack valid baseline evidence?

**Answer:** 4 strategy cells lack valid random baseline evidence (INSUFFICIENT_SUPPORT or INSUFFICIENT_RANDOM_BASELINE_EVIDENCE).

**Identities:**
- `POWER_LOTTO/fourier_rhythm_3bet`
- `POWER_LOTTO/power_fourier_rhythm_2bet`
- `POWER_LOTTO/power_orthogonal_5bet`
- `POWER_LOTTO/power_precision_3bet`

### Q10: Which candidates should appear on the future strategy hit-spectrum page?

**Answer:** 3 identities suitable for the future hit-spectrum page: DAILY_539/acb_markov_midfreq_3bet, DAILY_539/daily539_f4cold_3bet, DAILY_539/daily539_f4cold_5bet

**Identities:**
- `DAILY_539/acb_markov_midfreq_3bet`
- `DAILY_539/daily539_f4cold_3bet`
- `DAILY_539/daily539_f4cold_5bet`

### Q11: Which items require new evidence rather than status remapping?

**Answer:** 13 strategy cells require new evidence (additional OOS draws) rather than status remapping.

**Identities:**
- `BIG_LOTTO/bet2_fourier_expansion_biglotto`
- `BIG_LOTTO/biglotto_deviation_2bet`
- `BIG_LOTTO/biglotto_echo_aware_3bet`
- `BIG_LOTTO/biglotto_ts3_markov_4bet_w30`
- `DAILY_539/539_3bet_orthogonal`
- `DAILY_539/acb_1bet`
- `DAILY_539/acb_single_539`
- `DAILY_539/daily539_f4cold`
- `DAILY_539/midfreq_acb_2bet`
- `DAILY_539/p0b_539_3bet_f_cold_fmid`
- `DAILY_539/p0c_539_3bet_f_cold_x2`
- `POWER_LOTTO/midfreq_fourier_mk_3bet`
- `POWER_LOTTO/pp3_freqort_4bet`

---

## Strategy Records

| Identity | Current Mapping | Obs Rate | Base | Delta | Corrected Support | OOS Status | Observation Retention |
|----------|-----------------|----------|------|-------|-------------------|------------|-----------------------|
| `BIG_LOTTO/bet2_fourier_expansion_biglotto` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.0333 | 0.0310 | +0.0024 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `BIG_LOTTO/biglotto_deviation_2bet` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.0427 | 0.0310 | +0.0117 | DESCRIPTIVE_ONLY_ABOVE_RANDOM | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `BIG_LOTTO/biglotto_echo_aware_3bet` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1000 | 0.0900 | +0.0100 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `BIG_LOTTO/biglotto_triple_strike` | NO_EVIDENCE_OVER_RANDOM | 0.0293 | 0.0310 | -0.0016 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `BIG_LOTTO/biglotto_ts3_markov_4bet_w30` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1320 | 0.1182 | +0.0138 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `BIG_LOTTO/cold_complement_biglotto` | NO_EVIDENCE_OVER_RANDOM | 0.0280 | 0.0310 | -0.0030 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `BIG_LOTTO/coldpool15_biglotto` | NO_EVIDENCE_OVER_RANDOM | 0.0280 | 0.0310 | -0.0030 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `BIG_LOTTO/fourier30_markov30_biglotto` | NO_EVIDENCE_OVER_RANDOM | 0.0253 | 0.0310 | -0.0056 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `BIG_LOTTO/markov_2bet_biglotto` | NO_EVIDENCE_OVER_RANDOM | 0.0240 | 0.0310 | -0.0070 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `BIG_LOTTO/markov_single_biglotto` | NO_EVIDENCE_OVER_RANDOM | 0.0240 | 0.0310 | -0.0070 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `BIG_LOTTO/ts3_regime_3bet` | NO_EVIDENCE_OVER_RANDOM | 0.0293 | 0.0310 | -0.0016 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `DAILY_539/539_3bet_orthogonal` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1240 | 0.1140 | +0.0100 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/acb_1bet` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1240 | 0.1140 | +0.0100 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/acb_markov_midfreq` | NO_EVIDENCE_OVER_RANDOM | 0.0987 | 0.1140 | -0.0153 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `DAILY_539/acb_markov_midfreq_3bet` | OBSERVATION_SUPPORTED_ABOVE_RANDOM | 0.3573 | 0.3044 | +0.0529 | CORRECTED_SIGNIFICANT | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/acb_single_539` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1240 | 0.1140 | +0.0100 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/daily539_f4cold` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1400 | 0.1140 | +0.0260 | DESCRIPTIVE_ONLY_ABOVE_RANDOM | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/daily539_f4cold_3bet` | OBSERVATION_SUPPORTED_ABOVE_RANDOM | 0.3667 | 0.3044 | +0.0622 | CORRECTED_SIGNIFICANT | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/daily539_f4cold_5bet` | OBSERVATION_SUPPORTED_ABOVE_RANDOM | 0.5667 | 0.4539 | +0.1127 | CORRECTED_SIGNIFICANT | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/daily539_markov_cold` | NO_EVIDENCE_OVER_RANDOM | 0.1080 | 0.1140 | -0.0060 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `DAILY_539/markov_1bet_539` | NO_EVIDENCE_OVER_RANDOM | 0.1080 | 0.1140 | -0.0060 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `DAILY_539/midfreq_acb_2bet` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1347 | 0.1140 | +0.0207 | DESCRIPTIVE_ONLY_ABOVE_RANDOM | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/midfreq_fourier_2bet` | HISTORICAL_OBSERVATION_SUPERSEDED_BY_OOS_NULL | 0.1347 | 0.1140 | +0.0207 | DESCRIPTIVE_ONLY_ABOVE_RANDOM | OOS_NULL | OBSERVATION_NOT_RETAINED |
| `DAILY_539/p0b_539_3bet_f_cold_fmid` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1413 | 0.1140 | +0.0274 | DESCRIPTIVE_ONLY_ABOVE_RANDOM | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/p0c_539_3bet_f_cold_x2` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1413 | 0.1140 | +0.0274 | DESCRIPTIVE_ONLY_ABOVE_RANDOM | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `DAILY_539/zone_gap_3bet_539` | NO_EVIDENCE_OVER_RANDOM | 0.1013 | 0.1140 | -0.0126 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/cold_complement_2bet` | NO_EVIDENCE_OVER_RANDOM | 0.1147 | 0.1178 | -0.0032 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/fourier30_markov30_2bet` | NO_EVIDENCE_OVER_RANDOM | 0.1121 | 0.1178 | -0.0057 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/fourier_rhythm_3bet` | INSUFFICIENT_RANDOM_BASELINE_EVIDENCE | N/A | N/A | N/A | NO_INFERENCE_PERFORMED | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/midfreq_fourier_2bet` | NO_EVIDENCE_OVER_RANDOM | 0.1120 | 0.1178 | -0.0058 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/midfreq_fourier_mk_3bet` | UNDERPOWERED_OBSERVATION_POTENTIAL | 0.1347 | 0.1178 | +0.0168 | CORRECTED_NULL | OOS_INCONCLUSIVE_ABOVE_RANDOM | OBSERVATION_RETAINED |
| `POWER_LOTTO/power_fourier_rhythm_2bet` | INSUFFICIENT_RANDOM_BASELINE_EVIDENCE | N/A | N/A | N/A | NO_INFERENCE_PERFORMED | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/power_orthogonal_5bet` | INSUFFICIENT_RANDOM_BASELINE_EVIDENCE | N/A | N/A | N/A | NO_INFERENCE_PERFORMED | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/power_precision_3bet` | INSUFFICIENT_RANDOM_BASELINE_EVIDENCE | N/A | N/A | N/A | NO_INFERENCE_PERFORMED | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |
| `POWER_LOTTO/pp3_freqort_4bet` | OBSERVATION_POTENTIAL_ABOVE_RANDOM | 0.1267 | 0.1178 | +0.0088 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_RETAINED |
| `POWER_LOTTO/zonal_entropy_2bet` | NO_EVIDENCE_OVER_RANDOM | 0.1067 | 0.1178 | -0.0112 | CORRECTED_NULL | NO_OOS_AVAILABLE | OBSERVATION_NOT_RETAINED |

---

## Evidence Gaps

### p230c

**Description:** P230C (DAILY_539 backward-OOS apply) — no committed artifact found at outputs/research/p230c_*.json

**Impact:** Backward-OOS for DAILY_539 covered only by P230B1 (dry-run); P230C was not committed to origin/main.

**Resolution:** Use P230B1 dry-run evidence; treat as evidence gap for DAILY_539 backward-OOS real-apply.

### p245a

**Description:** P245A (external predictive method scouting) — untracked file, not committed to origin/main.

**Impact:** External method scouting evidence not available for classification.

**Resolution:** Excluded from universe; record as evidence gap.

### power_lotto_second_zone_inference

**Description:** POWER_LOTTO second-zone (special number) separate inference not committed as standalone artifact.

**Impact:** POWER_ANY_PRIZE_AWARE_WIN combines first-zone and second-zone. No separate second-zone-only inference available.

**Resolution:** Record as evidence gap; combined prize-aware endpoint used for all POWER_LOTTO classifications.

### big_lotto_m3plus_standalone_inference

**Description:** BIG_LOTTO M3+ standalone corrected inference (P267C) found NO corrected-significant cells. Prize-aware (P275B) adds special-hit dimension. No standalone BIG_LOTTO prize-aware corrected-significant cell found.

**Impact:** BIG_LOTTO strategies classifiable as at most OBSERVATION_POTENTIAL_ABOVE_RANDOM under prize-aware endpoint.

**Resolution:** Classification applied consistently; BIG_LOTTO strategies reflect combined prize-aware evidence.

---

## Recommended Follow-ups

### RFU-01 (Priority: HIGH)

DAILY_539 acb_markov_midfreq_3bet: Collect 300+ new prospective draws for the independent confirmatory gate (P272B power analysis: needs ~300 new draws for 80% power to detect +9.5pp above random).

### RFU-02 (Priority: HIGH)

DAILY_539 daily539_f4cold_5bet: Collect 300+ new prospective draws. Strongest corrected signal (p_corr=4.3e-8 in LONG window). Most promising candidate for hit-spectrum page.

### RFU-03 (Priority: HIGH)

DAILY_539 daily539_f4cold_3bet: Corrected-significant in LONG window (p_corr=0.017). Collect 300+ new prospective draws.

### RFU-04 (Priority: LOW)

DAILY_539 midfreq_fourier_2bet: P230B1 backward-OOS (4265 draws) showed below-baseline performance. No further investment recommended without architectural change.

### RFU-05 (Priority: MEDIUM)

P276B portfolios: All cross-strategy portfolios underperform best constituent (NO_RETROSPECTIVE_COMPLEMENTARITY_EVIDENCE). Additional OOS draws needed before cross-strategy portfolio deployment can be reconsidered.

### RFU-06 (Priority: MEDIUM)

POWER_LOTTO all strategies: 4 strategies have no prize-aware replay data (INSUFFICIENT_SUPPORT). Consider generating replay data for fourier_rhythm_3bet, power_fourier_rhythm_2bet, power_orthogonal_5bet, power_precision_3bet under read-only conditions.

### RFU-07 (Priority: LOW)

BIG_LOTTO all strategies: No corrected-significant cells found under prize-aware endpoint. L91 finding (49C6 pool is fair-random indistinguishable) remains operative. No further investment recommended.

---

## Governance

- All source artifacts are read-only committed JSON files on origin/main.
- No SQLite DB opened. No production DB accessed or written.
- No strategy promotion. No registry mutation. No controlled_apply.
- No historical artifact modified.
- prediction_success_claim=false; strategy_promoted=false.
- Canonical payload digest: `d75f8383c5029c5024279f9e3792d417885cecc202f25740f10406a701f14284`
