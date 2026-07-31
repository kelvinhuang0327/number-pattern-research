# P47 POWER_LOTTO Wave 4 Dry-Run + Temp Rehearsal

**Date:** 2026-05-24
**Branch:** p47-powerlotto-wave4-dryrun-rehearsal
**Classification:** P47_POWERLOTTO_WAVE4_DRYRUN_REHEARSAL_READY

---

## P47 Scope

P47 is a readiness/rehearsal task for POWER_LOTTO Wave 4. It does NOT apply any rows to the production database.

- Build POWER_LOTTO Wave 4 adapter scaffold (`lottery_api/models/p47_wave4_powerlotto_adapters.py`)
- Generate 1500 dry-run rows per strategy (4500 total) into a temp SQLite DB
- Complete temp DB rehearsal R1/R2/R3
- Verify production DB remains unchanged at 37960 rows
- STOP before production apply (P48 requires separate authorization)

---

## Wave 4 Strategies

| Strategy ID | Type | RSM Evidence | Adapter Effort |
|---|---|---|---|
| `pp3_freqort_4bet` | PP3+FreqOrt 4注 | edge300=+3.40%, Sharpe=0.088, perm p=0.000 VALIDATED | LOW |
| `midfreq_fourier_mk_3bet` | MidFreq+Fourier+Markov 3注 | edge300=+1.83%, validated edge+2.48% p=0.015 | LOW-MEDIUM |
| `midfreq_fourier_2bet` | MidFreq+Fourier 2注 | edge300=+0.08% (WATCH), validated +2.27% p=0.005 | LOW |

All three are designated `DRY_RUN` lifecycle. Promotion to production requires P48 authorization.

---

## POWER_LOTTO Adapter Design

### First Zone (predicted_numbers)
- Pool: 1–38 (38 numbers)
- Pick: 6 unique integers per bet
- Format: sorted list of 6 unique ints in [1, 38]

### Second Zone / Special (predicted_special)
- Pool: 1–8 (8 numbers)
- Pick: 1 integer per bet
- Format: single int in [1, 8]
- Prediction method: frequency mean-reversion over last 100 draws

### hit_count Semantics
- `hit_count` = count of first-zone matches ONLY
- Special hits are tracked separately as `special_hit` (0 or 1)
- `hit_count` NEVER includes the special number

### special_hit Semantics
- `special_hit = 1` if `predicted_special == actual_special`
- `special_hit = 0` otherwise

---

## Adapter Algorithm Summary

### pp3_freqort_4bet (bet-1)
Fourier Rhythm top-6 from first-zone pool [1..38], window=500 draws.
FFT period detection: score = 1 / (|gap - period| + 1). Bet-1 = top-6 by score.

### midfreq_fourier_mk_3bet (bet-1)
Composite blend: MidFreq(w=100) × 0.3 + Fourier(w=500) × 0.4 + Markov(w=30) × 0.3.
Each signal normalized to [0,1] before blending. Bet-1 = top-6 by blended score.

### midfreq_fourier_2bet (bet-1)
Orthogonal: MidFreq top-20 ∩ Fourier top-20 → pick 6 from intersection.
If intersection < 6, supplement from MidFreq top-20 remainder.

### Special Number Prediction (all strategies)
Mean-reversion over last 100 draws: pick the number in [1..8] closest to expected frequency.

---

## Dry-Run Row Counts

| Strategy | Rows | Lifecycle |
|---|---|---|
| pp3_freqort_4bet | 1500 | DRY_RUN |
| midfreq_fourier_mk_3bet | 1500 | DRY_RUN |
| midfreq_fourier_2bet | 1500 | DRY_RUN |
| **TOTAL** | **4500** | **DRY_RUN** |

Source: 1912 POWER_LOTTO draws in production DB (97000001 through 115000040).

---

## Temp Rehearsal R1/R2/R3 Results

| Step | Description | Result |
|---|---|---|
| R1 | Insert 4500 rows into temp DB | **PASS** (inserted=4500) |
| R2 | Rerun: expect 0 new rows | **PASS** (duplicate_inserted=0) |
| R3 | Rollback: expect 0 rows after delete | **PASS** (after=0) |

---

## Schema Validation

- Schema valid: **True** (0 errors)
- Data leakage violations: **0** (prediction_cutoff_date < draw_date for all rows)
- POWER_LOTTO first-zone format ok: **True** (6 unique ints in [1,38])
- Special zone format ok: **True** (1 int in [1,8])

---

## Production DB Guard

| Checkpoint | Value |
|---|---|
| Production rows before | 37960 |
| Production rows after | 37960 |
| Rows unchanged | **True** |

---

## Guard Results

| Guard | Status |
|---|---|
| Drift guard (pre) | PASS |
| Drift guard (post) | PASS |
| Branch governance (pre) | PASS (main, 37960 rows) |
| Branch governance (post) | PASS (p47-..., 37960 rows) |

---

## P48 Production Apply Readiness

P47 classification: **P47_POWERLOTTO_WAVE4_DRYRUN_REHEARSAL_READY**

P48 production apply is authorized to:
- Insert 4500 DRY_RUN rows into production `strategy_prediction_replays`
- Target draw range: last 1500 POWER_LOTTO draws
- Expected post-apply row count: 37960 + 4500 = **42460**

P48 requires separate explicit authorization before execution.

---

## Files

| File | Purpose |
|---|---|
| `lottery_api/models/p47_wave4_powerlotto_adapters.py` | Wave 4 adapter scaffold |
| `scripts/p47_powerlotto_wave4_dryrun_rehearsal.py` | Rehearsal orchestration script |
| `tests/test_p47_powerlotto_wave4_dryrun_rehearsal.py` | 36 contract tests |
| `outputs/replay/p47_powerlotto_wave4_dryrun_rehearsal_20260524.json` | Main output JSON |
| `outputs/replay/p47_temp_rehearsal_20260524.json` | Detailed rehearsal results |
| `docs/replay/p47_powerlotto_wave4_dryrun_rehearsal_20260524.md` | This document |
