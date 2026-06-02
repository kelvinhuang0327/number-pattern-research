# P167 — POWER_LOTTO Ensemble/Voting Research Implementation

**Task**: P167_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_IMPLEMENTATION  
**Date**: 2026-06-01  
**Final Classification**: `P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND`  
**Authorization**: YES execute P167 POWER_LOTTO ensemble/voting research implementation, read-only only, no DB write

---

## Phase 0 Verification — ALL PASS

| Check | Result |
|---|---|
| Authorization phrase | PRESENT ✓ |
| DB rows before | 94,924 ✓ |
| DB rows after | 94,924 (unchanged) ✓ |
| Drift guard | PASS ✓ |
| P161–P166 tests | PASS (236/236) ✓ |

---

## Dataset Summary

| Field | Value |
|---|---|
| Canonical dataset | zen-gates-ff6802 (designated in P165B) |
| Total POWER_LOTTO rows loaded | 36,000 |
| Complete draws (all 10 strategies present) | 1,499 |
| Strategies | 10 (cold_complement_2bet, fourier30_markov30_2bet, fourier_rhythm_3bet, midfreq_fourier_2bet, midfreq_fourier_mk_3bet, power_fourier_rhythm_2bet, power_orthogonal_5bet, power_precision_3bet, pp3_freqort_4bet, zonal_entropy_2bet) |

**Statistical unit**: all predictive tests use **per distinct target_draw** as the independent unit. Bet rows within the same draw are NOT independent units.

---

## Baselines (from P161)

| Metric | Value |
|---|---|
| Main-number random baseline | 0.9474 (6 × 6/38) |
| Special-number random baseline | 0.125 (1/8) |
| Best single-strategy (P161) | 0.9749 (fourier_rhythm_3bet, per-draw mean) |
| Family size for correction | 10 pre-declared tests |

---

## Module Results

### Module A — Strategy Consensus Voting

**Configuration**: Equal-weight voting, bet_index=1 only, top-6 by vote count (pre-declared, no leakage).

| Metric | Value |
|---|---|
| N draws | 1,499 |
| Ensemble mean hit count | **1.0007** |
| Random baseline | 0.9474 |
| Best single-strategy baseline | 0.9749 |
| Above random | **YES** (+0.053) |
| Above best single strategy | **YES** (+0.026) |
| z vs random | 2.43 |
| p_raw | 0.0153 |
| p_bh (corrected) | **0.038 — BH significant** |

**Module A in-sample verdict**: The ensemble beats both random and best single-strategy baselines, and the result survives BH correction. **However, this is in-sample (full 1499 draws). Predictive validity requires Module F walk-forward OOS.**

---

### Module B — bet_index Slot Effectiveness

**Type**: Descriptive (row-level, not per-draw). Statistical unit is bet row — NOT independent draws.

| Slot | N obs | Mean hit count | vs Random |
|---|---|---|---|
| bet_index=1 | varies | highest | baseline |
| bet_index=2 | varies | similar | p_bh=0.63 (not significant) |
| bet_index=3 | varies | lower | p_bh=0.00006 — significantly lower |
| bet_index=4 | varies | lower | p_bh=0.022 — significantly lower |
| bet_index=5 | varies | lower | p_bh=0.069 (marginal) |

**Verdict**: Higher bet_index slots (3, 4) have significantly lower hit rates than slot 1 — at the row level. This is descriptive. Slot 1 is most effective. Slot weighting for ensemble should downweight higher slots, but this requires OOS validation before predictive use.

---

### Module C — Recent-Window vs Full-History

| Window | N draws | Mean hit count | vs Full History |
|---|---|---|---|
| Full history | 1,499 | 1.0007 | — |
| Recent 1000 | 1,000 | similar | p_bh=0.689 (not different) |
| Recent 500 | 500 | similar | p_bh=0.097 (not different) |

**Verdict**: No significant difference between recent and full-history ensemble performance. Non-stationarity not detected.

---

### Module D — Lifecycle-Aware Descriptive Grouping

**Type**: Descriptive only. **⚠ Survivorship bias caveat**: truth_level labels were assigned after observing historical performance. ONLINE/higher-quality groups may appear to perform better due to selection bias, not predictive skill.

| Truth Level Group | Strategies |
|---|---|
| POWERLOTTO_WAVE4_STRATEGY_BACKFILL_VERIFIED | midfreq_fourier_2bet, midfreq_fourier_mk_3bet, pp3_freqort_4bet |
| POWERLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED | fourier_rhythm_3bet |
| POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED | power_orthogonal_5bet, power_precision_3bet |
| POWER_LOTTO_WAVE5/6_CONTROLLED_APPLY_VERIFIED | fourier30_markov30_2bet, cold_complement_2bet, zonal_entropy_2bet |
| TIERB_DRYRUN_VALIDATED | power_fourier_rhythm_2bet |

No predictive grouping performed. Descriptive tabulation only.

---

### Module E — Main-Number vs Special-Number Separated

| Target | N | Mean | Baseline | p_raw | p_bh | Verdict |
|---|---|---|---|---|---|---|
| Main hit count (per-draw mean across strategies) | 1,499 | 0.9834 | 0.9474 | 0.0073 | **0.024 — BH significant** | Above random |
| Special hit rate (per-draw, strategies with special) | 1,499 | ~0.120 | 0.125 | 0.418 | 0.522 | At or below random |

**Main**: 0.983 > 0.947 baseline; BH-corrected p=0.024. However, this is the aggregate mean across all strategies, not the ensemble — confirms strategies as a group marginally outperform random, consistent with P161 raw findings.

**Special**: No significant improvement. P161 finding confirmed — special number prediction is at or below random for all strategies with predictions.

---

### Module F — Walk-Forward OOS Final Gate ⚠ INSUFFICIENT DATA

**Pre-declared configuration**: equal-weight voting, bet_index=1, top-6 by vote count.  
**Required by P166**: ≥ 3 non-overlapping OOS windows × ≥ 500 draws each.

| Window | Train draws | OOS draws | Mean hit | Above random | Above best single | Status |
|---|---|---|---|---|---|---|
| OOS Window 1 | 0–499 | 500–999 (500 draws) | **1.040** | **YES** | **YES** | COMPUTED |
| OOS Window 2 | 0–999 | 1000–1498 (**499 draws**) | — | — | — | **INSUFFICIENT_OOS_DATA** |

**Problem**: With 1,499 complete draws, OOS Window 2 has only 499 draws (1499 − 1000 = 499 < 500 minimum). A third window is impossible.

**OOS Window 1 results** (500 draws):
- Ensemble mean = 1.040 vs random 0.9474 → +0.093 above random
- Ensemble mean = 1.040 vs best single 0.9749 → +0.065 above best single
- p_raw = 0.024, p_bh = **0.049 — BH significant**

**Module F gate FAILS**: P166 protocol requires stability confirmed across ≥ 2 computed OOS windows. Only 1 window was computed. Stability check cannot be performed.

**Final gate verdict: FAIL — INSUFFICIENT_OOS_DATA for stability check.**

---

## Multiple-Testing Correction Summary

**Family size**: 10 pre-declared tests (Module A=1, Module B=4, Module C=2, Module E=2, Module F=1).

| Test | p_raw | p_bh | Significant (BH)? |
|---|---|---|---|
| Module A: ensemble vs random | 0.0153 | 0.038 | **YES** |
| Module B: slot_2 vs slot_1 | 0.630 | 0.630 | No |
| Module B: slot_3 vs slot_1 | 0.000006 | 0.00006 | **YES** (slot 3 lower) |
| Module B: slot_4 vs slot_1 | 0.0044 | 0.022 | **YES** (slot 4 lower) |
| Module B: slot_5 vs slot_1 | 0.041 | 0.069 | No |
| Module C: recent_1000 vs full | 0.620 | 0.689 | No |
| Module C: recent_500 vs full | 0.068 | 0.097 | No |
| Module E: main vs random | 0.0073 | 0.024 | **YES** |
| Module E: special vs random | 0.418 | 0.522 | No |
| Module F: OOS window 1 vs random | 0.024 | 0.049 | **YES** |

**Summary**: 4 of 10 pre-declared tests are BH-significant. However, the significant Module F result is from only 1 OOS window — stability is unconfirmed.

---

## Final Decision — NULL Result

**`P167_POWER_LOTTO_NO_DEFENSIBLE_EDGE_FOUND`**

### What was found

The simple equal-weight consensus voting ensemble shows promising signals:
- In-sample (1499 draws): mean hit = 1.001, p_bh = 0.038 ✓
- OOS Window 1 (500 draws): mean hit = 1.040, p_bh = 0.049 ✓

### Why the gate failed

The P166 protocol requires Module F to pass the final gate:
1. **Beats random**: ✓ (both in-sample and OOS Window 1)
2. **Beats best single strategy**: ✓ (both in-sample and OOS Window 1)
3. **Survives BH correction**: ✓ (p_bh = 0.049 in OOS Window 1)
4. **Stable across ≥ 2 OOS windows**: ✗ — OOS Window 2 has only 499 draws (insufficient)
5. **≥ 3 OOS windows**: ✗ — data insufficient for 3 windows

The failure is due to **data volume limitation**, not a clear absence of signal. With 1,499 complete draws, the strict 3-window/500-draw requirement cannot be met.

### Honest conclusion

The ensemble voting approach shows a promising but **unconfirmed** signal. The current dataset is insufficient to certify stability under the P166 protocol. This does NOT mean the ensemble definitely has no edge — it means the available data is insufficient to prove it meets the strict Module F criteria.

**This result is NULL per the pre-declared protocol. No deployment, no champion promotion, no controlled_apply.**

### What this means for P168

P168 (decision review) should consider:
1. Collect more draws (≥ 200 more POWER_LOTTO draws would complete OOS Window 2)
2. Relax OOS window requirements (use 400-draw windows × 3 = 1200 draws OOS) — requires P168 re-authorization
3. Halt POWER_LOTTO research if cost/time budget is exceeded

---

## No-Action Confirmations

- **Zero DB writes** — DB unchanged at 94,924 rows
- **Zero registry mutations** — no lifecycle labels changed
- **Zero champion promotions** — P147 still blocked
- **Zero controlled_apply** — no new replay rows added
- **Zero commits or pushes**
- **No win guarantees, no real-money guidance**

---

## Next Task — P168_POWER_LOTTO_RESEARCH_DECISION_REVIEW

P167 results require user review before any deployment decision. P167 does NOT authorize:
- Strategy deployment or champion promotion
- Controlled_apply of new rows
- Main branch DB migration

The promising-but-unconfirmed ensemble signal should be reviewed in P168 with full context of data limitations and research costs.

---

## Governance Invariants

| Invariant | Value |
|---|---|
| DB rows | 94,924 (unchanged) |
| Drift guard | PASS |
| main/zen-gates split | UNRESOLVED |
| Success-rate method found | **NO — NULL result** |
