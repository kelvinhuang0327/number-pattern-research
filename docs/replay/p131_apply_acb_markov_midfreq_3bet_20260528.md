# P131: acb_markov_midfreq_3bet Controlled Replay Rows Applied

**Generated:** 2026-05-28T14:07:44.061799+00:00  
**Classification:** `P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED`  
**Strategy:** `acb_markov_midfreq_3bet` — DAILY_539  
**Rows inserted:** 3000  
**DB rows before / after:** 72422 → 75422  

---

## 1. Executive Summary

P131 applied the first authorized Wave 2 per-strategy controlled apply from the P130 gate. `acb_markov_midfreq_3bet` (DAILY_539, 3-bet) received its bet-2 and bet-3 rows via the P128 phase2 adapter `get_all_bets_acb_markov_midfreq`. All 3000 rows were inserted (1500 bet-2, 1500 bet-3). P8/P9/P11 remain untouched. P10/P12 remain not apply-ready. Drift guard baseline updated to 75422.

---

## 2. Authorization Confirmation

- **Authorization present:** True
- **Apply allowed:** True
- **Exact phrase required:** `P130_AUTHORIZED_APPLY_ACB_MARKOV_MIDFREQ_3BET_DAILY539_BET2_BET3_V20260528`
- **Phrase observed:** `P130_AUTHORIZED_APPLY_ACB_MARKOV_MIDFREQ_3BET_DAILY539_BET2_BET3_V20260528`

---

## 3. P130 Dry-Run Plan Recap

- **P130 classification:** `P130_WAVE2_SAFE_CANDIDATES_DRY_RUN_PLAN_READY`
- **P130 classification pass:** True
- **P7 acb_markov_midfreq_3bet in safe candidates:** True
- **P7 apply_ready_after_authorization:** True
- **P7 estimated_insert_rows:** 3000
- **P7 conflict_free:** True
- **P128 Phase 3 classification:** `P128_PHASE3_WAVE2_SAFE_CANDIDATES_READINESS_READY`
- **P128 Phase 3 pass:** True

---

## 4. Backup Creation and Verification

- **Backup path:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p131_backup_20260528T140744Z.db`
- **Backup created:** True
- **Backup row count:** 72422
- **Backup verification:** PASS

**Rollback command:**
```bash
cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p131_backup_20260528T140744Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'
```

---

## 5. Single-Strategy Apply Scope

| Field | Value |
|---|---|
| strategy_id | `acb_markov_midfreq_3bet` |
| lottery_type | `DAILY_539` |
| target_bet_count | 3 |
| expected_insert_rows | 3000 |
| actual_insert_rows | 3000 |
| bet-2 rows | 1500 |
| bet-3 rows | 1500 |
| controlled_apply_id | `P131_ACB_MARKOV_MIDFREQ_3BET_DAILY539_V20260528` |
| adapter_function | `get_all_bets_acb_markov_midfreq` |
| adapter_source | `lottery_api/models/p128_wave2_phase2_adapters.py` |

**Wave 2 candidates NOT applied in this task:**

- `midfreq_fourier_mk_3bet` (P8) — requires separate authorization
- `fourier_rhythm_3bet` (P9) — requires separate authorization
- `pp3_freqort_4bet` (P11) — requires separate authorization
- `power_precision_3bet` (P10) — not apply-ready until re-evaluation
- `power_orthogonal_5bet` (P12) — not apply-ready until re-evaluation

---

## 6. Inserted Rows Summary

- **Total rows inserted:** 3000
- **bet-2 rows:** 1500
- **bet-3 rows:** 1500
- **truth_level:** inherited from bet-1 rows
- **controlled_apply_id:** `P131_ACB_MARKOV_MIDFREQ_3BET_DAILY539_V20260528`
- **source:** `P131_CONTROLLED_APPLY`
- **dry_run:** False

---

## 7. Duplicate Guard Result

- **Unique key:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- **Constraint active:** True
- **Duplicate insert rejected:** True
- **Other Wave 2 candidates extra rows:** {'midfreq_fourier_mk_3bet': 0, 'fourier_rhythm_3bet': 0, 'pp3_freqort_4bet': 0, 'power_precision_3bet': 0, 'power_orthogonal_5bet': 0}
- **Other Wave 2 untouched:** True
- **Guard OK:** True

---

## 8. bet_index Validation

- **bet_index=1 count:** 1500 (expected 1500)
- **bet_index=2 count:** 1500 (expected 1500)
- **bet_index=3 count:** 1500 (expected 1500)
- **Distribution OK:** True
- **All rows DAILY_539:** True
- **Validation:** `PASS`

---

## 9. DB Rows Before / After

| Metric | Value |
|---|---:|
| Rows before | 72422 |
| Rows inserted | 3000 |
| Expected after | 75422 |
| Actual after | 75422 |
| Preservation OK | True |

---

## 10. Drift Guard Baseline Handling

- **Previous total:** 72422
- **New total:** 75422
- **Rows added:** 3000
- **Update required:** True
- **Update note:** scripts/replay_lifecycle_drift_guard.py BASELINE total_count updated from 72422 to 75422; p131_apply_id added as 'P131_ACB_MARKOV_MIDFREQ_3BET_DAILY539_V20260528' with count 3000

The `scripts/replay_lifecycle_drift_guard.py` baseline has been updated to reflect 75422 rows.

---

## 11. Rollback Reference / Backup Path

**Backup:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p131_backup_20260528T140744Z.db`

**Rollback command:**
```bash
cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p131_backup_20260528T140744Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'
```

Restore backup to rollback P131 apply. Backup was verified at 72422 rows before any write.

---

## 12. Explicit Non-Actions

This P131 task did **not**:

- Apply `midfreq_fourier_mk_3bet` (P8 — requires separate authorization)
- Apply `fourier_rhythm_3bet` (P9 — requires separate authorization)
- Apply `pp3_freqort_4bet` (P11 — requires separate authorization)
- Apply `power_precision_3bet` (P10 — not apply-ready until post-RSR6 re-evaluation)
- Apply `power_orthogonal_5bet` (P12 — not apply-ready until post-RSR6 re-evaluation)
- Touch any 4_STAR strategies
- Execute P108 / P117 / P118
- Install any scheduler, cron, or launchd
- Perform strategy promotion, lifecycle, champion, or registry mutation
- Modify any other DB tables

---

## 13. Remaining Risks

- bet1_mismatch_count > 0 implies ACB boundary rounding non-determinism — soft warning only, bet-2/bet-3 are independently generated
- P8/P9/P11 still await per-strategy authorization before apply
- P10/P12 blocked pending post-RSR6 re-evaluation
- fourier_rhythm_3bet (P9) has 1501-row anomaly (draw-ext 115000041) — apply gate must account for +1 row variance

---

## 14. Recommended Next Task

P132: acb_markov_midfreq_3bet DAILY_539 Wave 2 apply complete. Next: P132 — apply midfreq_fourier_mk_3bet (P8) POWER_LOTTO bet-2 + bet-3, authorization phrase: P130_AUTHORIZED_APPLY_MIDFREQ_FOURIER_MK_3BET_POWERLOTTO_BET2_BET3_V20260528. After P8: P11 (pp3_freqort_4bet), then P9 (fourier_rhythm_3bet, 1501-row anomaly last).

---

## 15. Final Classification

```text
P131_ACB_MARKOV_MIDFREQ_3BET_APPLIED
```

**Task:** P131  
**DB rows after apply:** 75422  
**Next Wave 2 candidates awaiting authorization:** P8, P11, P9  
