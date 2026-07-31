# V2: ARTIFACT_ONLY Strategy Inventory

**Date**: 2026-05-14  
**Purpose**: Identify and classify ARTIFACT_ONLY strategies for V2 parser development  
**Status**: Phase 1 Complete

---

## Summary

| Category | Count | Strategies |
|----------|-------|-----------|
| EXECUTABLE_NOW | 6 | biglotto_deviation_2bet, biglotto_triple_strike, daily539_f4cold, daily539_markov_cold, power_orthogonal_5bet, power_precision_3bet |
| ARTIFACT_ONLY | 4 | **biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, p1_deviation_2bet_539** |
| CODE_MISSING | 6 | acb_1bet, acb_markov_midfreq, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet, h6_gate_mk20_ew85 |
| TOMBSTONE | 0 | (none) |

---

## ARTIFACT_ONLY Strategies (V2 Target)

### 1. biglotto_ts3_acb_4bet

**Lottery**: BIG_LOTTO  
**Expected Role**: 4-bet strategy using TS3 (Triple Strike 3) + ACB (Anomaly Capture Bet)  
**Registry Status**: Present  
**Adapter Status**: Unknown (requires Phase 2 audit)  
**V2 Target**: Parse artifact rows and create dry-run candidates  

### 2. biglotto_ts3_markov_freq_5bet

**Lottery**: BIG_LOTTO  
**Expected Role**: 5-bet strategy using TS3 + Markov + Frequency  
**Registry Status**: Present  
**Adapter Status**: Unknown (requires Phase 2 audit)  
**V2 Target**: Parse artifact rows and create dry-run candidates  

### 3. power_shlc_midfreq

**Lottery**: POWER_LOTTO  
**Expected Role**: SHLC (Shift HLC) + Mid-frequency strategy  
**Registry Status**: Present  
**Adapter Status**: Unknown (requires Phase 2 audit)  
**V2 Target**: Parse artifact rows and create dry-run candidates  

### 4. p1_deviation_2bet_539

**Lottery**: DAILY_539  
**Expected Role**: 2-bet strategy using P1 + Deviation + Mid-frequency  
**Registry Status**: Present  
**Adapter Status**: Unknown (requires Phase 2 audit)  
**V2 Target**: Parse artifact rows and create dry-run candidates  

---

## Strategy Exclusions (Not V2 Target)

### EXECUTABLE_NOW (Already handled by V1)
- biglotto_deviation_2bet (50 rows in DB, truth_level=REGENERATED_RETROSPECTIVE)
- biglotto_triple_strike (50 rows in DB, truth_level=REGENERATED_RETROSPECTIVE)
- daily539_f4cold (50 rows in DB, truth_level=REGENERATED_RETROSPECTIVE)
- daily539_markov_cold (50 rows in DB, truth_level=REGENERATED_RETROSPECTIVE)
- power_orthogonal_5bet (50 rows in DB, truth_level=REGENERATED_RETROSPECTIVE)
- power_precision_3bet (50 rows in DB, truth_level=REGENERATED_RETROSPECTIVE)

**Note**: These 6 strategies have already been processed by V1 P6-lite closure and have 300 total controlled rows in DB.

### CODE_MISSING (Tombstone - Not to be processed)
- acb_1bet
- acb_markov_midfreq
- acb_markov_midfreq_3bet
- midfreq_acb_2bet
- midfreq_fourier_2bet
- h6_gate_mk20_ew85

**Note**: CODE_MISSING strategies have no reconstructable code path. These are marked as tombstones in the inventory. V2 does NOT process these.

---

## Next Steps

Phase 2: Audit artifact sources for each ARTIFACT_ONLY strategy
- Locate original prediction/backtest artifacts
- Verify row format and completeness
- Check data integrity
- Assess leakage risk
