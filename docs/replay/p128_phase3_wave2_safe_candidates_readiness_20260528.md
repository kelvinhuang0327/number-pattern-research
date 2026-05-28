# P128 Phase 3: Wave 2 Safe Candidate Readiness After RSR-6 Cleanup

**Task ID**: P128_PHASE3
**Classification**: P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY
**Generated At**: 2026-05-28T12:59:17.760663Z

---

## 1. Executive Summary

P128 Phase 3 dry-run readiness re-evaluation completed. No DB writes were performed.

- **Safe candidates (P7/P8/P9/P11)**: 4 strategies confirmed `DRY_RUN_READY`
  - All adapters present, all bi=1 rows intact, no conflicts
  - Estimated insert rows if applied: **13502**
- **Blocked candidates (P10/P12)**: RSR-6 cleanup done, apply gate re-evaluation required
  - Not apply-ready; per-strategy re-evaluation needed before controlled_apply
- **DB rows**: 72,422 (unchanged, no writes)
- **Drift guard**: PASS at 72,422

---

## 2. RSR-6 Cleanup Recap

| Field | Value |
|-------|-------|
| Cleanup classification | `RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED` |
| Orphan rows deleted | 40 (power_precision_3bet ×20, power_orthogonal_5bet ×20) |
| DB rows after cleanup | 72,422 |
| Backup | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2_before_rsr6_cleanup_20260528T124212Z.db` |
| Orphan bi=2 cleared | ✓ |

---

## 3. P128 Phase 2 Recap

| Field | Value |
|-------|-------|
| Classification | `P128_WAVE2_ADAPTER_PHASE2_READY` |
| Strategies in scope | 6 (P7–P12) |
| P10/P12 RSR-6 blocked at Phase 2 | Yes (now cleared by cleanup) |

---

## 4. Why Phase 3 Is Dry-Run Readiness Only

Phase 3 is a **planning and gate check** phase. Controlled_apply requires:
1. Per-strategy authorization phrase (not yet issued)
2. Dry-run execution confirming expected insert count matches actual
3. Duplicate guard pre-check passes (no existing bi>1 rows)
4. P10/P12 apply gate re-evaluation separate from P7/P8/P9/P11

No rows are written. No strategies are promoted. No lifecycle mutations.

---

## 5. Safe Candidate Scope (P7/P8/P9/P11)

{'candidate_strategy_ids': ['acb_markov_midfreq_3bet', 'midfreq_fourier_mk_3bet', 'fourier_rhythm_3bet', 'pp3_freqort_4bet'], 'excludes_rsr6_blocked': True, 'db_write_in_phase3': False, 'controlled_apply_executed': False, 'replay_rows_inserted': 0, 'production_db_rows_expected': 72422, 'production_db_rows_after': 72422, 'all_safe_candidates_dry_run_ready': True}

#### P7 `acb_markov_midfreq_3bet` (DAILY_539)
- Target bets: 3, Current bi=1 rows: 1500
- Missing bet indices: [2, 3]
- Estimated insert rows: **3000**
- Adapter function: `get_all_bets_acb_markov_midfreq` exists: True
- Duplicate guard: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..3)`
- Provenance hash: `SHA256(strategy_id + target_draw + bet_index + predicted_numbers)`
- Status: **DRY_RUN_READY**

#### P8 `midfreq_fourier_mk_3bet` (POWER_LOTTO)
- Target bets: 3, Current bi=1 rows: 1500
- Missing bet indices: [2, 3]
- Estimated insert rows: **3000**
- Adapter function: `get_all_bets_midfreq_fourier_mk` exists: True
- Duplicate guard: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..3)`
- Provenance hash: `SHA256(strategy_id + target_draw + bet_index + predicted_numbers)`
- Status: **DRY_RUN_READY**

#### P9 `fourier_rhythm_3bet` (POWER_LOTTO)
- Target bets: 3, Current bi=1 rows: 1501
- Missing bet indices: [2, 3]
- Estimated insert rows: **3002**
- Adapter function: `get_all_bets_fourier_rhythm` exists: True
- Duplicate guard: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..3)`
- Provenance hash: `SHA256(strategy_id + target_draw + bet_index + predicted_numbers)`
- Status: **DRY_RUN_READY**

#### P11 `pp3_freqort_4bet` (POWER_LOTTO)
- Target bets: 4, Current bi=1 rows: 1500
- Missing bet indices: [2, 3, 4]
- Estimated insert rows: **4500**
- Adapter function: `get_all_bets_pp3_freqort` exists: True
- Duplicate guard: `SELECT COUNT(*) = 0 WHERE bet_index IN (2..4)`
- Provenance hash: `SHA256(strategy_id + target_draw + bet_index + predicted_numbers)`
- Status: **DRY_RUN_READY**

---

## 6. Blocked Candidate Scope (P10/P12)

| Field | power_precision_3bet | power_orthogonal_5bet |
|-------|---------------------|----------------------|
| RSR-6 cleanup done | ✓ | ✓ |
| bi=2 orphans cleared | ✓ | ✓ |
| Current bi=1 rows | 1550 | 1550 |
| Apply ready | **False** | **False** |
| Reason | apply gate re-eval required | apply gate re-eval required |

#### P10 `power_precision_3bet` (POWER_LOTTO)
- RSR-6 cleanup completed ✓ (commit f624409, 20 orphan rows deleted)
- Current bi=1 rows: 1550 (orphan bi=2 cleared)
- Estimated insert rows if cleared: 3100
- Adapter function: `get_all_bets_power_precision` exists: True
- Apply ready: **False** — apply gate re-evaluation required
- Status: **BLOCKED_APPLY_GATE_RE_EVALUATION**

#### P12 `power_orthogonal_5bet` (POWER_LOTTO)
- RSR-6 cleanup completed ✓ (commit f624409, 20 orphan rows deleted)
- Current bi=1 rows: 1550 (orphan bi=2 cleared)
- Estimated insert rows if cleared: 6200
- Adapter function: `get_all_bets_power_orthogonal` exists: True
- Apply ready: **False** — apply gate re-evaluation required
- Status: **BLOCKED_APPLY_GATE_RE_EVALUATION**

---

## 7. Per-Candidate Readiness Matrix

| Priority | Strategy | Lottery | Bets | bi=1 Rows | Est. Insert | Adapter ✓ | Status |
|----------|----------|---------|------|-----------|-------------|-----------|--------|
| P7 | `acb_markov_midfreq_3bet` | DAILY_539 | 3 | 1500 | 3000 | True | **DRY_RUN_READY** |
| P8 | `midfreq_fourier_mk_3bet` | POWER_LOTTO | 3 | 1500 | 3000 | True | **DRY_RUN_READY** |
| P9 | `fourier_rhythm_3bet` | POWER_LOTTO | 3 | 1501 | 3002 | True | **DRY_RUN_READY** |
| P10 | `power_precision_3bet` | POWER_LOTTO | 3 | 1550 | 3100 | True | **BLOCKED_APPLY_GATE_RE_EVALUATION** |
| P11 | `pp3_freqort_4bet` | POWER_LOTTO | 4 | 1500 | 4500 | True | **DRY_RUN_READY** |
| P12 | `power_orthogonal_5bet` | POWER_LOTTO | 5 | 1550 | 6200 | True | **BLOCKED_APPLY_GATE_RE_EVALUATION** |

---

## 8. Estimated Insert Rows (If Safe Apply Proceeds)

| Strategy | Bet Indices to Add | Est. Insert Rows |
|----------|--------------------|-----------------|
| `acb_markov_midfreq_3bet` | [2, 3] | 3000 |
| `midfreq_fourier_mk_3bet` | [2, 3] | 3000 |
| `fourier_rhythm_3bet` | [2, 3] | 3002 |
| `pp3_freqort_4bet` | [2, 3, 4] | 4500 |
| **Total safe** | | **13502** |

- DB rows after safe apply (estimated): **85,924**
- Blocked candidates estimated (if cleared): 9300 additional rows

---

## 9. Duplicate Guard / Provenance Readiness Summary

**Duplicate guard strategy**: `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- Abort on conflict: True
- All safe candidates guard defined: True

**Provenance hash formula**: `SHA256(strategy_id + target_draw + bet_index + predicted_numbers)`
- Source: historical_only
- Dry-run required before any apply: True
- All safe candidates provenance defined: True

---

## 10. Apply Gate Rules After Phase 3

| Rule | Value |
|------|-------|
| dry_run_only | **True** |
| controlled_apply_executed | False |
| replay_rows_inserted | 0 |
| per_strategy_authorization_required | True |
| Safe candidates next step | Obtain per-strategy authorization phrase, run dry-run apply script, verify estimated insert rows match actual, then execute controlled_apply |
| Blocked candidates next step | Re-evaluate P10/P12 apply gate: verify bi=1 rows quality, confirm no legacy anomalies, obtain fresh authorization |

---

## 11. Explicit Non-Actions

| Non-Action | Confirmed |
|-----------|-----------|
| No DB write in P128 Phase 3 | ✓ |
| No controlled_apply in P128 Phase 3 | ✓ |
| P10/P12 not apply-ready until re-evaluation | ✓ |
| 4_STAR excluded | ✓ |
| P108 not run | ✓ |
| P117 not run | ✓ |
| P118 not run | ✓ |
| Rejected strategies — no action | ✓ |
| No scheduler / cron / launchd install | ✓ |
| No lifecycle / champion / registry mutation | ✓ |
| P126B–P126F rows untouched | ✓ |

---

## 12. Remaining Risks

1. P10/P12 apply gate re-evaluation must validate that bet_index=1 rows with replay_run_id=2,6 and controlled_apply_id IS NULL are valid production records before any controlled_apply proceeds
2. Dry-run execution for P7/P8/P9/P11 requires per-strategy authorization phrases not yet issued
3. fourier_rhythm_3bet has 1501 rows (1 extra draw vs 1500 baseline) — verify target draw range before estimating insert rows
4. P128 Phase 3 estimated insert rows are approximations; actual inserts require dry-run execution and deduplication checks

---

## 13. Recommended Next Task

P128 Phase 3b (or P130): Execute controlled_apply dry-run for P7/P8/P9/P11 safe candidates with per-strategy authorization. P10/P12 apply gate re-evaluation as separate task.

---

## 14. Final Classification

```text
P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY
```
