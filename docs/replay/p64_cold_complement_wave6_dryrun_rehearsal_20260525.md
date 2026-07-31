# P64a: POWER_LOTTO Wave 6 — cold_complement_2bet Dry-Run Rehearsal

**Classification marker:** `P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_COMPLETED`  
**Task:** P64a  
**Date:** 2026-05-25  
**Branch:** `p64-cold-complement-wave6-dryrun-rehearsal`  
**Base commit:** `cc05a10` (P63)  
**Preceding task:** P63 — Wave 6 candidate planning  
**Next task:** P64b — lag_reversion_2bet mini-backtest  

---

## Executive Summary

P64a executes a controlled dry-run rehearsal for `cold_complement_2bet` as the
Wave 6 rank-1 candidate identified in P63. The rehearsal reuses the
`ColdComplement2BetAdapter` built in P56 with zero modifications. All 1500
dry-run rows are written to a temp SQLite DB (`/tmp/p64_cold_complement_temp.db`)
— the production DB remains at **43960 rows unchanged**.

**Readiness verdict:** `READY_FOR_P65_WITH_CAUTION`

M3+ rate = **3.67%** vs theoretical baseline **3.87%** (−0.20 pp). This delta
is within the ±2 SE noise band at N=1500 (SE ≈ 0.50 pp) and is **identical to
the P57 Wave 5 rehearsal result**, confirming stable, reproducible cold-reversion
behaviour across the full POWER_LOTTO draw history.

---

## Governance

| Rule | Status |
|------|--------|
| Production DB writes | ❌ No |
| Online promotions | ❌ No |
| Champion replacement | ❌ No |
| Registry mutation | ❌ No |
| Production apply | ❌ No |
| Production rows before | 43960 |
| Production rows after | 43960 |
| Drift guard | ✅ PASS |
| Branch governance guard | ✅ PASS |

---

## Adapter Details

| Field | Value |
|-------|-------|
| Class | `ColdComplement2BetAdapter` |
| File | `lottery_api/models/p56_wave5_powerlotto_adapters.py` |
| Algorithm | Cold reversion — 100-draw frequency window |
| Mechanism | 6 coldest numbers by frequency over last 100 draws |
| Pool | 1–38 (first zone, pick 6) |
| Special pool | 1–8 (pick 1) |
| Deterministic | ✅ Yes — no `random.seed()` |
| Strategy version | v0.1-p56 |

---

## Dry-Run Configuration

| Parameter | Value |
|-----------|-------|
| Window periods | 1500 draws |
| Target draws | 101000003 → 115000041 |
| Lifecycle | `DRY_RUN` |
| Temp DB | `/tmp/p64_cold_complement_temp.db` |
| POWER_LOTTO draws total | 1913 |

---

## Metrics

### Hit Distribution (first-zone only)

| Hit count | Rows | % |
|-----------|------|---|
| 0 | 478 | 31.87% |
| 1 | 693 | 46.20% |
| 2 | 274 | 18.27% |
| 3 | 51 | 3.40% |
| 4 | 4 | 0.27% |
| 5 | 0 | — |
| 6 | 0 | — |

### Summary Statistics

| Metric | Value |
|--------|-------|
| Total rows | 1500 |
| Predicted rows | 1500 |
| Insufficient history rows | 0 |
| Error rows | 0 |
| M3+ count (hits ≥ 3) | 55 |
| **M3+ rate** | **3.67%** |
| Theoretical M3+ baseline | 3.87% |
| **vs baseline** | **−0.20 pp** |
| Special hit count | 178 |
| Special hit rate | 11.87% |
| Avg hit count | 0.94 |
| Duplicate target draws | 0 |

### Comparison Table

| Metric | P57 Wave 5 rehearsal | P64a Wave 6 rehearsal | Delta |
|--------|---------------------|----------------------|-------|
| M3+ rate | 3.67% | 3.67% | 0.00 pp |
| vs baseline | −0.20 pp | −0.20 pp | identical |
| Special hit rate | — | 11.87% | — |
| McNemar p (vs baseline) | 0.656 | ~0.656 | not significant |

The exact reproducibility confirms the adapter is deterministic and the strategy
signal is stable.

---

## Validation Results

| Check | Status | Notes |
|-------|--------|-------|
| pick_6_unique_numbers | ✅ PASS | 0 violations |
| numbers_in_range_1_38 | ✅ PASS | 0 violations |
| special_in_range_1_8 | ✅ PASS | 0 violations |
| no_duplicate_numbers | ✅ PASS | 0 violations |
| hit_count_integrity | ✅ PASS | 0 violations |
| no_leakage_indicators | ✅ PASS | 0 violations |
| Causal ordering (leakage) | ✅ PASS | prediction_cutoff < target_date for all 1500 rows |
| Idempotency | ✅ PASS | Re-insert → count unchanged (1500 → 1500) |
| Production rollback | ✅ PASS | Production rows unchanged, cold_complement rows = 0 |

---

## Readiness Decision

**Classification:** `READY_FOR_P65_WITH_CAUTION`

**Rationale:** M3+=3.67% vs baseline 3.87% (−0.20 pp), within 2 SE noise band.
P57 precedent: −0.20 pp. All semantic, leakage, idempotency, and rollback checks
pass. Recommend monitoring first 50 draws post-apply in P65.

### Readiness Threshold Decision Matrix

| Condition | Threshold | Result |
|-----------|-----------|--------|
| Semantic validations | All pass | ✅ PASS |
| Leakage-free | 0 violations | ✅ PASS |
| Idempotent | count unchanged | ✅ PASS |
| Production unchanged | 43960 rows | ✅ PASS |
| M3+ ≥ baseline (3.87%) | ≥ 3.87% | ❌ 3.67% |
| M3+ within noise (≥ −1.0 pp) | ≥ 2.87% | ✅ −0.20 pp |
| Readiness | — | `READY_FOR_P65_WITH_CAUTION` |

---

## P65 Controlled Apply Proposal (Draft)

> ⚠️ **P65 requires explicit authorization phrase:**  
> `"YES apply cold_complement_2bet 1500 rows to production for P65"`

| Field | Value |
|-------|-------|
| Strategy ID | `cold_complement_2bet` |
| Proposed rows | 1500 |
| Expected production rows after | 45460 |
| CAID template | `P64_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525` |
| Backup required | ✅ Yes |
| Backup table | `strategy_prediction_replays_backup_before_p65_cold_complement` |
| Rollback SQL | `DELETE FROM strategy_prediction_replays WHERE strategy_id='cold_complement_2bet'` |
| Caution | M3+ −0.20 pp below theoretical; P57 precedent same; not statistically significant (McNemar p=0.656). Monitor first 50 draws post-apply. |

---

## P64 Sequencing

```
P64a (this task) — cold_complement_2bet dry-run rehearsal
  ↓ READY_FOR_P65_WITH_CAUTION
P64b — lag_reversion_2bet mini-backtest (150/500/1500 windows) + adapter build
P64c — zonal_entropy_2bet determinism fix + dry-run rehearsal
  ↓
P65 — cold_complement_2bet controlled apply proposal (requires explicit auth)
```

---

## Output Artifacts

| File | Status |
|------|--------|
| `scripts/p64_cold_complement_wave6_dryrun_rehearsal.py` | ✅ Created |
| `outputs/replay/p64_cold_complement_wave6_dryrun_rehearsal_20260525.json` | ✅ Created |
| `docs/replay/p64_cold_complement_wave6_dryrun_rehearsal_20260525.md` | ✅ This file |
| `tests/test_p64_cold_complement_wave6_dryrun_rehearsal.py` | ✅ Created |
| `/tmp/p64_cold_complement_temp.db` | ✅ Temp only — NOT staged, NOT committed |
