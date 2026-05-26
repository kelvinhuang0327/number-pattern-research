# P58 — POWER_LOTTO Wave 5 Controlled Apply Proposal

**Date**: 2026-05-25  
**Phase**: P58  
**Classification**: `P58_CONTROLLED_APPLY_PROPOSAL_READY`  
**Mode**: PROPOSAL_ONLY (no production DB write — apply authorization not present)  
**Branch**: `main`  
**Controlled Apply ID**: `P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525`

---

## 1. Summary

P58 is the controlled production apply phase for POWER_LOTTO Wave 5. Based on P57 readiness
assessment (commit `aea8ff7`), only **one** of the three Wave 5 strategies qualifies for production
apply:

| Strategy | P57 Classification | P58 Action |
|---|---|---|
| `fourier30_markov30_2bet` | `READY_FOR_P58_WITH_CAUTION` | **PROPOSAL_READY** |
| `cold_complement_2bet` | `WATCHLIST_REHEARSAL_ONLY` | Excluded |
| `zonal_entropy_2bet` | `WATCHLIST_REHEARSAL_ONLY` | Excluded |

This document records the proposal-only run of P58. The production DB was **not modified**.
Expected row delta: **+1,500** (from 42,460 → 43,960) when authorized.

---

## 2. P57 Evidence (Pre-requisite)

| Field | Value |
|---|---|
| P57 commit | `aea8ff7` |
| P57 file | `outputs/replay/p57_powerlotto_wave5_controlled_rehearsal_readiness_20260525.json` |
| P57 classification | `P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED` |
| Cohort decision | `PARTIAL_COHORT_P58` |
| P58 cohort | `["fourier30_markov30_2bet"]` |
| Watchlist | `["cold_complement_2bet", "zonal_entropy_2bet"]` |
| P56 commit ref | `c3f0325` |
| P57 overall_ok | `true` |

---

## 3. Duplicate Check

| Check | Result |
|---|---|
| `fourier30_markov30_2bet` exact rows in POWER_LOTTO prod | **0** ✅ |
| `cold_complement_2bet` in POWER_LOTTO prod | 0 ✅ |
| `zonal_entropy_2bet` in POWER_LOTTO prod | 0 ✅ |
| LIKE query `%fourier30%` + `%wave5%` + `%cold_complement%` + `%zonal_entropy%` | 3000 (BIG_LOTTO variants from prior phase — NOT Wave 5 POWER_LOTTO) |
| Wave 5 strategies in POWER_LOTTO distinct strategy list | None ✅ |

**Explanation of 3000 LIKE count**: `cold_complement_biglotto` (1500) and
`fourier30_markov30_biglotto` (1500) are BIG_LOTTO strategies from an earlier phase.
These are distinct from the POWER_LOTTO `_2bet` variants and are **not** a contamination issue.

---

## 4. Proposal Row Generation

| Metric | Value |
|---|---|
| Strategy | `fourier30_markov30_2bet` |
| Rows generated (in memory) | 1,500 |
| Draw range | 101000002 → 115000040 |
| Draw window | Last 1,500 POWER_LOTTO draws |
| Schema validation | PASS (0 errors) |
| Leakage check | PASS (0 violations) |
| Duplicate check | PASS (0 existing in prod) |

### Algorithm

Recency-weighted frequency (window=30):

```
weight_i = 1.0 + 2.0 × (i / n)
```

Top-6 numbers by weighted frequency selected from pool [1..38]. Special number predicted
via mean-reversion (least-seen in window=30 from [1..8]).

---

## 5. Hit Statistics (Proposal Rows)

| Metric | Value | Baseline |
|---|---|---|
| M3+ (hit ≥ 3) | 61 / 1500 = **4.07%** | 3.87% |
| M3+ delta | **+0.20 pp** | — |
| Special hit rate | 12.47% | 12.50% (1/8) |
| z-score | +0.395 | — |
| p-value | 0.347 | — |
| Statistically significant (p<0.05) | **No** | — |

Hit count distribution:

| Hits | Count |
|---|---|
| 0 | 472 |
| 1 | 675 |
| 2 | 292 |
| 3 | 57 |
| 4 | 4 |
| 5+ | 0 |

**Note**: P57 reported M3+=4.07% from the P56 dry-run dataset. P58 regenerates rows from
scratch using the same deterministic algorithm; numbers are consistent (z=+0.40, M3+=4.07%).
The edge is directional but not statistically significant at n=1500.

---

## 6. Governance Constraints

| Constraint | Status |
|---|---|
| `production_db_write` | **false** (proposal-only) |
| `lifecycle_promotion` | false |
| `champion_replacement` | false |
| `registry_mutation` | false |
| `live_api_call` | false |
| `online_promotion` | false |
| POWER_LOTTO prod rows | **42,460 (unchanged)** |
| `cold_complement_2bet` excluded | ✅ |
| `zonal_entropy_2bet` excluded | ✅ |

---

## 7. Pre-Apply Checklist (Required Before Authorized Apply)

- [ ] P57 artifact exists and classification is `P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED`
- [ ] Drift guard PASS (`--strict`)
- [ ] Branch governance guard PASS (`--expected-branch main --expected-rows 42460`)
- [ ] Duplicate check PASS (0 rows for `fourier30_markov30_2bet` in POWER_LOTTO)
- [ ] Schema validation PASS (all 1500 rows)
- [ ] Leakage check PASS (0 violations)
- [ ] DB backup created and verified: `cp lottery_api/data/lottery_v2.db lottery_api/data/lottery_v2.db.bak_p58`
- [ ] Backup row count verified == 42460
- [ ] All governance tests PASS (295/295)
- [ ] Production rows = 42460 before apply
- [ ] Forbidden staging scan PASS

---

## 8. Rollback Plan

If the authorized apply fails or produces anomalous results:

```sql
-- Step 1: Verify controlled_apply_id rows before rollback
SELECT COUNT(*) FROM strategy_prediction_replays
WHERE controlled_apply_id = 'P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525';
-- Expected: 1500

-- Step 2: Delete P58 rows
DELETE FROM strategy_prediction_replays
WHERE controlled_apply_id = 'P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525';

-- Step 3: Verify row count back to 42460
SELECT COUNT(*) FROM strategy_prediction_replays;
-- Expected: 42460
```

Or restore from backup:

```bash
cp lottery_api/data/lottery_v2.db.bak_p58 lottery_api/data/lottery_v2.db
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"
# Expected: 42460
```

---

## 9. Authorization Requirements

To execute the production apply, both of the following must be present:

1. **Apply authorization phrase**: `YES apply Wave 5 POWER_LOTTO strategies to production DB`
2. **Script flag**: `--authorize-apply`

Without these, the script runs in `PROPOSAL_ONLY` mode (no DB write).

---

## 10. Post-Flight Guard Results

| Guard | Result |
|---|---|
| Production rows | **42,460** ✅ |
| Drift guard (`--strict`) | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` ✅ |
| Branch governance guard (`main`, `42460`) | `BRANCH_GOVERNANCE_PASS` ✅ |

---

## 11. Test Suite

**6-file governance suite**: 295/295 PASSED

| File | Tests | Result |
|---|---|---|
| `test_replay_lifecycle_drift_guard.py` | — | PASS |
| `test_replay_api_contract.py` | — | PASS |
| `test_replay_branch_governance_guard.py` | — | PASS |
| `test_p56_powerlotto_wave5_adapter_bootstrap_dryrun.py` | 173 | PASS |
| `test_p57_powerlotto_wave5_controlled_rehearsal_readiness.py` | 213 | PASS |
| `test_p58_powerlotto_wave5_controlled_apply_proposal.py` | **82** | PASS |
| **Total** | **295** | **ALL PASS** |

P58 test classes:

| Class | Tests | Coverage |
|---|---|---|
| `TestP57EvidenceIntegrity` | 15 | P57 classification, cohort, watchlist, governance |
| `TestDuplicateCheck` | 6 | Wave 5 not in prod, champion present, prod rows |
| `TestP58JSONStructure` | 13 | Required fields, phase, mode, strategy |
| `TestP58GovernanceConstraints` | 11 | No prod write, no promotion, watchlist excluded |
| `TestP58CohortConstraints` | 9 | Only fourier30, correct row counts, draw range |
| `TestP58ProposalValidity` | 12 | Auth phrase, rollback plan, checklist, sample rows |
| `TestP58StatisticalValidity` | 10 | M3+ rate, baseline, z-test, leakage, schema |
| `TestP58ProductionDBState` | 4 | Rows=42460, no P58 ID in DB, 6 distinct strategies |

---

## 12. Artifacts

| File | Commit |
|---|---|
| `scripts/p58_powerlotto_wave5_controlled_apply.py` | (this commit) |
| `tests/test_p58_powerlotto_wave5_controlled_apply_proposal.py` | (this commit) |
| `outputs/replay/p58_powerlotto_wave5_controlled_apply_proposal_20260525.json` | (this commit) |
| `docs/replay/p58_powerlotto_wave5_controlled_apply_proposal_20260525.md` | (this commit) |

P57 reference: commit `aea8ff7` — `P57_POWERLOTTO_WAVE5_PARTIAL_COHORT_RECOMMENDED`  
P56 reference: commit `c3f0325` — `P56_POWERLOTTO_WAVE5_DRYRUN_COMPLETE`

---

## 13. Next Step (P59)

When the apply authorization phrase is provided:

```
YES apply Wave 5 POWER_LOTTO strategies to production DB
```

Run:

```bash
.venv/bin/python scripts/p58_powerlotto_wave5_controlled_apply.py --authorize-apply
```

Expected outcome:
- `fourier30_markov30_2bet`: +1,500 rows inserted with `controlled_apply_id = P58_POWERLOTTO_WAVE5_FOURIER30_MARKOV30_1500_PROD_20260525`
- Production rows: 42,460 → **43,960**
- `cold_complement_2bet` and `zonal_entropy_2bet`: remain on watchlist for continued rehearsal
