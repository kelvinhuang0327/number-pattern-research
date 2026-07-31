# P66 — POWER_LOTTO Wave 6 Controlled Production Apply

**Classification:** `P66_WAVE6_CONTROLLED_APPLY_COMPLETED`
**Date:** 2026-05-25
**Phase:** P66
**P65 Ref commit:** `b2ae277`

---

## Summary

P66 executes the authorized production apply for the two Wave 6 strategies proposed in P65.
Both strategies are inserted into the production replay DB for coverage-expansion purposes only.
No lifecycle promotion, no champion replacement, no ONLINE status granted.

### Strategies Applied

| Strategy | CAID | Rows | M3+ Rate |
|---|---|---|---|
| `cold_complement_2bet` | `P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525` | 1500 | 3.67% |
| `zonal_entropy_2bet` | `P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525` | 1500 | 3.67% |

### Excluded Strategy

| Strategy | Reason |
|---|---|
| `lag_reversion_2bet` | P64b GATE_FAIL — w150=0.67%, w500=2.00%, w1500=3.73%. MUST NOT apply. |

---

## Production Row Counts

| Metric | Before P66 | After P66 |
|---|---|---|
| Total rows | 43960 | **46960** |
| `cold_complement_2bet` (POWER_LOTTO) | 0 | **1500** |
| `zonal_entropy_2bet` (POWER_LOTTO) | 0 | **1500** |
| `lag_reversion_2bet` (POWER_LOTTO) | 0 | **0** (excluded) |
| Wave 5 (`fourier30_markov30_2bet`) | 1500 | **1500** (preserved) |

---

## Pre-flight Results

- `production_rows_ok`: **True** (43960 == 43960)
- `cold_complement_clean`: **True** (0 existing rows)
- `zonal_entropy_clean`: **True** (0 existing rows)
- `duplicate_check_pass`: **True**
- `p59_rows_ok`: **True** (1500 preserved)
- `wave6_clean`: **True** (0 prior Wave 6 rows)

---

## Validation Results

### cold_complement_2bet

- Schema: **PASS** (0 errors)
- Leakage: **PASS** (0 violations)
- Dup pre-check: **PASS**
- Insert: 1500 inserted, 0 skipped

### zonal_entropy_2bet

- Schema: **PASS** (0 errors)
- Leakage: **PASS** (0 violations)
- Dup pre-check: **PASS**
- Insert: 1500 inserted, 0 skipped

---

## Post-apply Verification

- `total_ok`: **True** (46960 == 46960)
- `cold_rows_ok`: **True** (1500)
- `zonal_rows_ok`: **True** (1500)
- `lag_reversion_absent`: **True** (0 rows)
- `online_promotion_ok`: **True** (0 ONLINE rows)
- `semantic_ok`: **True** (0 errors)
- `p59_rows_preserved`: **True** (1500)

---

## Hit Statistics

| Strategy | M3+ | M3+ Rate | Theoretical Baseline | Notes |
|---|---|---|---|---|
| `cold_complement_2bet` | 55/1500 | **3.67%** | 3.87% | Within noise band (-0.20pp) |
| `zonal_entropy_2bet` | 55/1500 | **3.67%** | 3.87% | Within noise band (-0.20pp) |

*Noise band SE ≈ 0.50pp at N=1500. -0.20pp delta is within READY_WITH_CAUTION threshold.*

---

## Governance

| Gate | Status |
|---|---|
| production_db_write | **True** (authorized) |
| lifecycle_promotion | **False** |
| champion_replacement | **False** |
| registry_mutation | **False** |
| online_promotion | **False** |
| wave5_champion_unchanged | `fourier30_markov30_2bet` |
| coverage_expansion_only | **True** |
| performance_improvement_claim | **False** |

---

## Backup

- Path: `backups/lottery_v2_pre_p66_wave6_20260525_*.db`
- Backup rows: 43960 (verified)

---

## Rollback

```sql
DELETE FROM strategy_prediction_replays
WHERE controlled_apply_id IN (
    'P66_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525',
    'P66_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525'
);
-- Expected rows after rollback: 43960
```

---

## Authorization

- `YES create new branch for P66 Wave 6 controlled production apply` ✓
- `YES apply cold_complement_2bet 1500 rows to production for P66` ✓
- `YES apply zonal_entropy_2bet 1500 rows to production for P66` ✓
- `lag_reversion_2bet` — NOT authorized, NOT applied ✓
