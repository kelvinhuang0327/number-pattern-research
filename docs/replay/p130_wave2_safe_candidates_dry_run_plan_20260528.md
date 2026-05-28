# P130: Wave 2 Safe Candidate Controlled-Apply Dry-Run Plan

**Task ID**: P130
**Classification**: P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY
**Generated At**: 2026-05-28T13:08:57.811959Z

---

## 1. Executive Summary

P130 produces the per-strategy **dry-run apply plan** for safe Wave 2 candidates
(P7/P8/P9/P11). No DB writes are performed.

- **4 safe candidates** planned: DRY_RUN_PLAN_READY
- **Estimated total insert rows** (if applied): **13,502**
- **DB rows**: 72,422 (unchanged)
- **Recommended apply order**: P7 → P8 → P11 → P9
- **P9 anomaly**: fourier_rhythm_3bet has 1501 bi=1 rows — verify before apply
- **P10/P12**: BLOCKED (post-RSR6 apply gate re-evaluation required)

---

## 2. P128 Phase 3 Recap

| Field | Value |
|-------|-------|
| Classification | `P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY` |
| All safe candidates DRY_RUN_READY | True |
| Estimated safe insert rows (Phase 3) | 13,502 |

---

## 3. RSR-6 Cleanup Recap

| Field | Value |
|-------|-------|
| Classification | `RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED` |
| Deleted rows | 40 |
| DB rows after cleanup | 72,422 |

---

## 4. Why P130 Is Dry-Run Plan Only

Controlled_apply requires **per-strategy authorization phrases** (not yet issued).
P130 establishes:
- Exact target draw ranges verified from live DB
- Estimated insert row counts per strategy
- Duplicate guard pre-check queries
- Provenance hash contract per strategy
- Recommended apply order (low-risk first)
- Authorization phrase templates for the next round

No rows are written. No strategies are promoted.

---

## 5. Safe Candidate Dry-Run Matrix

| P | Strategy | Lottery | Bets | bi=1 Rows | Missing bi | Est. Rows | Anomaly | Status |
|---|----------|---------|------|-----------|------------|-----------|---------|--------|
| P7 | `acb_markov_midfreq_3bet` | DAILY_539 | 3 | 1500 | [2, 3] | 3000 | — | **DRY_RUN_PLAN_READY** |
| P8 | `midfreq_fourier_mk_3bet` | POWER_LOTTO | 3 | 1500 | [2, 3] | 3000 | — | **DRY_RUN_PLAN_READY** |
| P9 | `fourier_rhythm_3bet` | POWER_LOTTO | 3 | 1501 | [2, 3] | 3002 | ⚠ 1501 anomaly | **DRY_RUN_PLAN_READY** |
| P11 | `pp3_freqort_4bet` | POWER_LOTTO | 4 | 1500 | [2, 3, 4] | 4500 | — | **DRY_RUN_PLAN_READY** |

---

## 6. P9 — fourier_rhythm_3bet 1501-Row Anomaly

> **⚠ Important**: `fourier_rhythm_3bet` has **1501** bi=1 rows vs 1500 for other
> POWER_LOTTO strategies.

fourier_rhythm_3bet has 1501 bi=1 rows vs 1500 for other POWER_LOTTO strategies. Extra draw = 115000041 (2026/05/21), added via P79 Batch A draw-ext (controlled_apply_id=P78_POWERLOTTO_BATCH_A_FOURIER_RHYTHM_DRAWEXT_20260526). This is legitimate. Estimated insert rows = 2×1501 = 3002. Verify target draw range includes 115000041 before controlled_apply.

**Action before P9 apply**:
1. Confirm target draw range includes draw `115000041` (2026/05/21)
2. Verify adapter reproduces this draw deterministically
3. Estimated insert rows = **3002** (not 3000)

---

## 7. Blocked Candidate Scope (P10/P12)

| Strategy | bi=1 Rows | Reason | Apply Ready |
|----------|-----------|--------|-------------|
| `power_precision_3bet` | 1550 | post_rsr6_cleanup_apply_gate_re_evaluation_required | **False** |
| `power_orthogonal_5bet` | 1550 | post_rsr6_cleanup_apply_gate_re_evaluation_required | **False** |

RSR-6 cleanup done (commit f624409). Apply gate re-evaluation required separately.

---

## 8. Estimated Insert Rows Summary

| Strategy | Bet Indices | Est. Insert Rows | Note |
|----------|-------------|-----------------|------|
| `acb_markov_midfreq_3bet` | [2, 3] | 3000 | — |
| `midfreq_fourier_mk_3bet` | [2, 3] | 3000 | — |
| `fourier_rhythm_3bet` | [2, 3] | 3002 | ⚠ anomaly |
| `pp3_freqort_4bet` | [2, 3, 4] | 4500 | — |
| **Total** | | **13,502** | |

DB rows after safe apply (estimated): **85,924**

---

## 9. Recommended Apply Order

| Step | Strategy | Est. Rows | Rationale |
|------|----------|-----------|-----------|
| 1 | `acb_markov_midfreq_3bet` | 3000 | P7 first — DAILY_539, cleanest 1500-row baseline, lowest ris… |
| 2 | `midfreq_fourier_mk_3bet` | 3000 | P8 second — POWER_LOTTO, standard 1500 rows, same pool as P9… |
| 3 | `pp3_freqort_4bet` | 4500 | P11 third — POWER_LOTTO 4-bet, widest insert scope (4500 row… |
| 4 | `fourier_rhythm_3bet` | 3002 | P9 last — verify 115000041 draw-ext row inclusion before app… |

---

## 10. Authorization Phrases Required Later

These are **templates** — actual phrases must be issued with a real date suffix before
any controlled_apply execution. **Do not use in this round.**

| Strategy | Phrase Template | Status |
|----------|----------------|--------|
| `acb_markov_midfreq_3bet` | `P130_AUTHORIZED_APPLY_ACB_MARKOV_MIDFREQ_3BET_DAILY539_BET2_BET3_V20260528` | NOT_YET_ISSUED |
| `midfreq_fourier_mk_3bet` | `P130_AUTHORIZED_APPLY_MIDFREQ_FOURIER_MK_3BET_POWERLOTTO_BET2_BET3_V20260528` | NOT_YET_ISSUED |
| `fourier_rhythm_3bet` | `P130_AUTHORIZED_APPLY_FOURIER_RHYTHM_3BET_POWERLOTTO_BET2_BET3_V20260528` | NOT_YET_ISSUED |
| `pp3_freqort_4bet` | `P130_AUTHORIZED_APPLY_PP3_FREQORT_4BET_POWERLOTTO_BET2_BET3_BET4_V20260528` | NOT_YET_ISSUED |

---

## 11. Duplicate Guard / Provenance Readiness Summary

**Guard strategy**: `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- Abort on conflict: True
- All safe candidates conflict-free: **True**

**Provenance hash**: `SHA256(strategy_id|target_draw|bet_index|predicted_numbers)`
- Source: historical_only
- All templates defined: True

---

## 12. Explicit Non-Actions

| Non-Action | Confirmed |
|-----------|-----------|
| No DB write in P130 | ✓ |
| No controlled_apply in P130 | ✓ |
| No apply execution script created | ✓ |
| P10/P12 not in scope | ✓ |
| 4_STAR excluded | ✓ |
| P108 not run | ✓ |
| P117 not run | ✓ |
| P118 not run | ✓ |
| Rejected strategies — no action | ✓ |
| No scheduler install | ✓ |
| No lifecycle / champion / registry mutation | ✓ |

---

## 13. Remaining Risks

1. P9 fourier_rhythm_3bet draw-ext row (115000041) must be included in controlled_apply target draws; verify the adapter reproduces this draw's numbers deterministically before apply.
2. Authorization phrases are templates only; actual phrases with real DATE suffix must be obtained and validated before any controlled_apply proceeds.
3. P7 acb_markov_midfreq_3bet draw range starts at 110000190 (not 101000002 like POWER_LOTTO strategies) — ensure adapter history window is compatible with DAILY_539 draw numbering.
4. P10/P12 apply gate re-evaluation may surface additional anomalies (bi=1 rows with replay_run_id=2,6 and controlled_apply_id IS NULL).

---

## 14. Recommended Next Task

P130b / P131: Issue per-strategy authorization phrases for P7/P8/P9/P11 and execute controlled_apply. Recommended order: P7 → P8 → P11 → P9 (verify P9 115000041 inclusion last).

---

## 15. Final Classification

```text
P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY
```
