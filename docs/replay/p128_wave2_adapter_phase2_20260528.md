# P128 Wave 2 Phase 2 — Multi-Bet Adapter Implementation Report

**Task ID**: P128_PHASE2  
**Date**: 2026-05-28  
**Classification**: P128_WAVE2_ADAPTER_PHASE2_READY  
**Commit**: P128: implement Wave 2 phase 2 multi-bet adapters

---

## Summary

P128 Wave 2 Phase 2 implements `get_all_bets()` adapters for priority 7-12 strategies
from the P127 multi-bet adapter build spec. Phase 1 (priority 1-6, 2-bet) was completed
at commit `ae89cdb`.

**This phase covers priority 7-12**: strategies with 3, 4, and 5 bets (3-bet, 4-bet,
5-bet). All adapters are ADAPTER-ONLY — no DB writes, no controlled_apply, no replay row
insertion.

---

## Scope Boundaries

| Parameter | Value |
|-----------|-------|
| DB write in P128 Phase 2 | NO |
| controlled_apply executed | NO |
| replay_rows_inserted | 0 |
| production_db_rows_expected | 72,462 |
| production_db_rows_after | 72,462 |
| DB row count invariant | ✓ MAINTAINED |

---

## Priority 7-12 Adapters

| Priority | Strategy ID | Lottery | Target Bets | DB Rows | RSR Status |
|----------|-------------|---------|-------------|---------|------------|
| P7 | `acb_markov_midfreq_3bet` | DAILY_539 | 3 | 1500 | None |
| P8 | `midfreq_fourier_mk_3bet` | POWER_LOTTO | 3 | 1500 | None |
| P9 | `fourier_rhythm_3bet` | POWER_LOTTO | 3 | 1501 | RSR-7 (+1 extra, not blocked) |
| P10 | `power_precision_3bet` | POWER_LOTTO | 3 | 1570 | **RSR-6 BLOCKED** |
| P11 | `pp3_freqort_4bet` | POWER_LOTTO | 4 | 1500 | None |
| P12 | `power_orthogonal_5bet` | POWER_LOTTO | 5 | 1570 | **RSR-6 BLOCKED** |

All 6 adapters: status = **PASS**

---

## Algorithm Design

### P7: acb_markov_midfreq_3bet (DAILY_539)

Three orthogonal signals:

- **bet-1 (ACB)**: Anomaly Capture Bet — `(expected − actual) / σ` over window=100.
  Underrepresented numbers (positive z-score) selected top-5.
- **bet-2 (Markov)**: Transition matrix from window=30. Score = sum of outgoing transition
  probabilities from last draw's numbers. Top-5 most-likely to follow.
- **bet-3 (MidFreq)**: Mean-reversion — `−|actual − expected|` over window=100. Numbers
  closest to expected frequency.

### P8: midfreq_fourier_mk_3bet (POWER_LOTTO)

Three signal dimensions:

- **bet-1 (MidFreq)**: Mean-reversion top-6, window=100.
- **bet-2 (Fourier)**: FFT dominant-period alignment, `1/(|gap − period| + 1)`, window=500.
- **bet-3 (Markov30)**: Transition probability from last draw, window=30. Top-6 arr.

### P9: fourier_rhythm_3bet (POWER_LOTTO)

Two Fourier timescales + ACB hedge:

- **bet-1 (Fourier-500)**: Long-window FFT rhythm, window=500. Primary signal.
- **bet-2 (Fourier-100)**: Short-window FFT rhythm, window=100. Near-term phase shift.
- **bet-3 (ACB)**: Anomaly hedge, window=100. Orthogonal reversion signal.

**RSR-7 note**: 1501 rows in DB (+1 extra). Does NOT block adapter.

### P10: power_precision_3bet (POWER_LOTTO) ⚠ RSR-6

**Adapter defined for FORWARD USE. Apply of bet_index≥2 is BLOCKED until RSR-6 resolved.**

- **bet-1 (MidFreq+Fourier Fusion)**: Intersection of top-20 MidFreq and top-20 Fourier,
  pick 6. Supplement from MidFreq remainder if intersection < 6.
- **bet-2 (Cold)**: Lowest-frequency top-6, window=100. *(Apply blocked)*
- **bet-3 (Markov30)**: Transition probability top-6, window=30.

### P11: pp3_freqort_4bet (POWER_LOTTO)

Four-bet full signal coverage:

- **bet-1 (MidFreq)**: Mean-reversion top-6, window=100.
- **bet-2 (Fourier)**: FFT rhythm top-6, window=500.
- **bet-3 (Cold)**: Lowest-frequency top-6, window=100.
- **bet-4 (Markov30)**: Transition from last draw, window=30.

### P12: power_orthogonal_5bet (POWER_LOTTO) ⚠ RSR-6

**Adapter defined for FORWARD USE. Apply of bet_index≥2 is BLOCKED until RSR-6 resolved.**

Five maximally orthogonal signals:

- **bet-1 (MidFreq)**: Mean-reversion top-6, window=100.
- **bet-2 (Fourier)**: FFT rhythm top-6, window=500. *(Apply blocked)*
- **bet-3 (Cold)**: Lowest-frequency top-6, window=100.
- **bet-4 (Markov30)**: Transition top-6, window=30.
- **bet-5 (ACB)**: Anomaly capture top-6, window=100.

---

## RSR-6 Audit

**Strategies affected**: `power_precision_3bet`, `power_orthogonal_5bet`

Both strategies have orphan `bet_index=2` rows in the DB that predate P128:

| Strategy | bet_index=1 rows | bet_index=2 orphan rows |
|----------|-----------------|-------------------------|
| `power_precision_3bet` | 1550 | **20** |
| `power_orthogonal_5bet` | 1550 | **20** |

Orphan rows span draws ~99000085–99000094. `source` field is empty string.

**Consequence**: Before any `controlled_apply` adds `bet_index≥2` rows for these
strategies, the 20 orphan rows must be audited and quarantined or deleted to prevent
constraint violations.

**Resolution path**: File RSR-6-RESOLUTION as a subtask under P128 or a successor phase.
Inspect orphan rows, determine provenance, quarantine/delete if they are legacy test rows.
Then mark these strategies as apply-ready.

---

## RSR-7 Note

`fourier_rhythm_3bet` has **1501 rows** in the DB (expected 1500, +1 extra row).
- Only `bet_index=1` rows exist (min=1, max=1).
- The extra row does not block adapter implementation.
- Low priority. No action required in P128.

---

## Test Coverage

| Test Suite | Tests | Status |
|------------|-------|--------|
| `test_p128_wave2_adapter_phase2.py` | **86** | ✓ ALL PASS |
| `test_p128_wave2_adapter_phase1.py` (regression) | **88** | ✓ ALL PASS |
| `replay_lifecycle_drift_guard.py` | N/A | ✓ PASS |

**Test classes**:
- `TestModuleLevel` (9): manifest, RSR-6 flags, bet_counts, lottery_types, provenance
- `TestAcbMarkovMidfreq3bet` (10): P7 structure, dispatch, determinism, edge cases
- `TestMidfreqFourierMk3bet` (8): P8 structure, dispatch, determinism, edge cases
- `TestFourierRhythm3bet` (9): P9 structure + RSR-7 manifest verification
- `TestPowerPrecision3bet` (11): P10 structure + RSR-6 flag verification
- `TestPp3Freqort4bet` (10): P11 4-bet structure, dispatch, determinism
- `TestPowerOrthogonal5bet` (12): P12 5-bet structure + RSR-6 flag verification
- `TestUnifiedDispatch` (4): error paths, all-6 dispatch, idempotency
- `TestValidateBets` (9): validation error paths for wrong count, pick, dup, sort, range
- `TestFullHistoryRegression` (6): all 6 adapters with 1500-draw window

---

## Files Changed

| File | Action |
|------|--------|
| `lottery_api/models/p128_wave2_phase2_adapters.py` | CREATED — 6 adapters |
| `tests/test_p128_wave2_adapter_phase2.py` | CREATED — 86 tests |
| `scripts/p128_wave2_adapter_phase2.py` | CREATED — verification script |
| `outputs/replay/p128_wave2_adapter_phase2_20260528.json` | CREATED — artifact |
| `docs/replay/p128_wave2_adapter_phase2_20260528.md` | CREATED — this file |
| `00-Plan/roadmap/CTO-Analysis.md` | UPDATED — Phase 2 section |
| `00-Plan/roadmap/roadmap.md` | UPDATED — Phase 2 section |

---

## Blocked / Excluded

- No DB write
- No controlled_apply
- 4-STAR strategies excluded
- P108 / P117 / P118 not run
- Rejected strategies: no action
- No scheduler change
- No lifecycle / champion / registry mutation

---

## Provenance

```
SHA256: <see outputs/replay/p128_wave2_adapter_phase2_20260528.json>
Input:  P128_PHASE2|P127_ADAPTER_BUILD_SPECS_READY|
        acb_markov_midfreq_3bet|midfreq_fourier_mk_3bet|fourier_rhythm_3bet|
        power_precision_3bet|pp3_freqort_4bet|power_orthogonal_5bet
```

---

## Next Steps

1. **RSR-6 resolution**: Audit 20 orphan `bet_index=2` rows per RSR-6 strategy.
   File as `RSR-6-RESOLUTION` subtask.
2. **Wave 2 Phase 3 (if applicable)**: Any remaining strategies beyond priority 12.
3. **controlled_apply integration**: Once RSR-6 resolved for P10/P12, these adapters
   can be wired into the controlled_apply pipeline alongside P7/P8/P9/P11.

---

*Marker: `CTO_ROADMAP_UPDATED_AFTER_P128_WAVE2_ADAPTER_PHASE2_20260528`*
