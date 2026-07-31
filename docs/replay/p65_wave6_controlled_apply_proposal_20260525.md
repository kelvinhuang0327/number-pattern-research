# P65: POWER_LOTTO Wave 6 — Controlled Apply Proposal

**Marker**: `P65_WAVE6_CONTROLLED_APPLY_PROPOSAL_20260525`  
**Task ID**: P65  
**Date**: 2026-05-25  
**Branch**: `p65-wave6-controlled-apply-proposal`  

---

## Summary

| Item | Value |
|------|-------|
| Production rows (current) | 43960 |
| Decision | **D** — ['cold_complement_2bet', 'zonal_entropy_2bet'] |
| Apply rows (total) | 3000 |
| Projected rows after apply | 46960 |
| Classification | **P65_WAVE6_CONTROLLED_APPLY_PROPOSAL_READY_WITH_CAUTION** |
| Performance improvement claim | NO |
| Online promotion | NO |
| Champion replacement | NO |

---

## Pre-Flight Results

- Repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` ✓  
- Branch: `main` → `p65-wave6-controlled-apply-proposal` ✓  
- HEAD: `de70f32` (P64c) ✓  
- Production rows: `43960` ✓  
- P59 rows: `1500` ✓  
- Drift guard: PASS ✓  
- Branch governance guard: PASS ✓  

---

## P64 Artifact Verification

| Task | Strategy | Classification | M3+ | Readiness |
|------|----------|---------------|-----|-----------|
| P64a | `cold_complement_2bet` | `P64_COLD_COMPLEMENT_WAVE6_DRYRUN_REHEARSAL_COMPLETED` | 3.67% | READY_FOR_P65_WITH_CAUTION |
| P64b | `lag_reversion_2bet` | `P64B_LAG_REVERSION_WAVE6_MINI_BACKTEST_GATE_FAIL` | w150=0.67%, w500=2.00%, w1500=3.73% | GATE_FAIL |
| P64c | `zonal_entropy_2bet` | `P64C_ZONAL_ENTROPY_WAVE6_READY_WITH_CAUTION` | 3.67% | READY_FOR_P65_WITH_CAUTION |

---

## Duplicate Check

| Strategy | Prod Rows | Safe to Apply |
|----------|-----------|---------------|
| `cold_complement_2bet` | 0 | ✅ YES |
| `zonal_entropy_2bet` | 0 | ✅ YES |
| Wave 6 CAIDs in prod | 0 | ✅ CLEAR |

---

## Candidate Decision Matrix

### `cold_complement_2bet` — INCLUDE WITH CAUTION

| Metric | Value |
|--------|-------|
| M3+ rate | 3.67% |
| vs Baseline | -0.20 pp |
| Special hit | 11.87% |
| Avg hit | 0.9400 |
| Deterministic | YES |
| Dry-run rows | 1500 |
| Risk level | MEDIUM |
| Coverage value | HIGH |
| Evidence strength | MODERATE |
| Recommendation | **INCLUDE_WITH_CAUTION** |

Deterministic adapter (P56). Single 1500-window: M3+=3.67% (-0.20pp vs 3.87% baseline). Delta within 2SE noise band (SE≈0.50pp at N=1500). Regime: standard cold-complement selection. Coverage expansion justifies inclusion despite sub-baseline M3+. NOT a performance improvement claim.

### `zonal_entropy_2bet` — INCLUDE WITH CAUTION

| Metric | Value |
|--------|-------|
| M3+ rate | 3.67% |
| vs Baseline | -0.20 pp |
| Special hit | 11.87% |
| Avg hit | 0.9400 |
| Deterministic | True (P64c verified) |
| Dry-run rows | 1500 |
| Risk level | MEDIUM |
| Coverage value | HIGH |
| Evidence strength | MODERATE |
| Recommendation | **INCLUDE_WITH_CAUTION** |

Determinism verified in P64c (5 checks, 0 violations; random.seed() removed in P56). Single 1500-window: M3+=3.67% (-0.20pp vs 3.87% baseline). Delta within 2SE noise band (SE≈0.50pp at N=1500). P57 precedent: same result, p=0.656. Notable: 100% chaotic regime — adapter always uses cold fallback. Distinct entropy axis provides signal diversity. NOT a performance improvement claim.

**Notable**: 100% of 1500 draws classified as chaotic (entropy > 2.2 bits). Adapter in practice = cold fallback at window=100 for all draws.

### `lag_reversion_2bet` — EXCLUDED

Gate: FAIL. GATE_FAIL, DEFER_ADAPTER_BUILD, window inconsistency  
Window 150: M3+=0.67% (-3.20pp)  
Window 500: M3+=2.00% (-1.87pp)  
Window 1500: M3+=3.73% (-0.14pp)  

---

## Proposal Decision: Option D

Option D: Apply both cold_complement_2bet and zonal_entropy_2bet. Both are READY_WITH_CAUTION (M3+=3.67%, -0.20pp, within 2SE noise band). Distinct signal axes (frequency-gap vs entropy-adaptive) justify dual coverage. This is a coverage expansion, NOT a performance superiority claim. lag_reversion_2bet excluded (GATE_FAIL, DEFER_ADAPTER_BUILD).

---

## Controlled Apply Plan (for P66, if authorized)

### `cold_complement_2bet`
- CAID: `P65_POWERLOTTO_WAVE6_COLD_COMPLEMENT_1500_PROD_20260525`
- Apply rows: 1500
- Auth phrase: `YES apply cold_complement_2bet 1500 rows to production for P66`

### `zonal_entropy_2bet`
- CAID: `P65_POWERLOTTO_WAVE6_ZONAL_ENTROPY_1500_PROD_20260525`
- Apply rows: 1500
- Auth phrase: `YES apply zonal_entropy_2bet 1500 rows to production for P66`

**Apply order**: ['cold_complement_2bet', 'zonal_entropy_2bet']  
**Apply one at a time**: YES  
**Backup required**: YES — `strategy_prediction_replays_backup_before_p66_wave6`  

**Backup SQL**:
```sql
CREATE TABLE strategy_prediction_replays_backup_before_p66_wave6 AS SELECT * FROM strategy_prediction_replays;
```

**Rollback SQL**:
```sql
DELETE FROM strategy_prediction_replays WHERE strategy_id='cold_complement_2bet';
DELETE FROM strategy_prediction_replays WHERE strategy_id='zonal_entropy_2bet';
```

**Pre-apply checks**:
```sql
SELECT COUNT(*) FROM strategy_prediction_replays;  -- expect 43960
SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='cold_complement_2bet';  -- expect 0
SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='zonal_entropy_2bet';  -- expect 0
```

**Post-apply checks**:
```sql
SELECT COUNT(*) FROM strategy_prediction_replays;  -- expect 46960
SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='cold_complement_2bet';  -- expect 1500
SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id='zonal_entropy_2bet';  -- expect 1500
```

**Caution notes**:
- M3+ rate is 3.67% (-0.20pp below 3.87% baseline)
- Statistical test: p=0.656 (not significant) — no strong performance signal
- Regime: 100% chaotic for zonal_entropy (always cold fallback)
- Rationale is coverage expansion, NOT performance improvement
- Do NOT promote ONLINE
- Do NOT replace champion fourier30_markov30_2bet

---

## Conservative Policy Statement

This proposal is for **coverage expansion** and **replay completeness only**.  
It does **NOT** claim performance improvement.  
Both strategies perform at M3+=3.67% (-0.20pp vs baseline 3.87%).  
Statistical test p=0.656 indicates no significant difference from random.  
Post-apply monitoring at 50-draw intervals is required.  
No ONLINE promotion. No champion replacement. No registry mutation.  

---

## Governance

- Production rows before: `43960`  
- Production rows after (this proposal): `43960` (NO WRITE)  
- Production apply: **NO** (proposal only)  
- Online promotion: **NO**  
- Champion replacement: **NO**  
- Registry mutation: **NO**  

---

## Next Step

If authorized, proceed to **P66 Wave 6 controlled apply**.  
Required authorization phrases:

- `cold_complement_2bet`: `YES apply cold_complement_2bet 1500 rows to production for P66`
- `zonal_entropy_2bet`: `YES apply zonal_entropy_2bet 1500 rows to production for P66`

If not authorized, proceed to **P66 Wave 7 candidate planning** or `lag_reversion_2bet` rework.  

---

## Classification

`P65_WAVE6_CONTROLLED_APPLY_PROPOSAL_READY_WITH_CAUTION`  

_Generated by P65 proposal script. No production DB write._  
_Production rows: 43960 (unchanged)._  
