# P140: power_precision_3bet Controlled Replay Rows Applied

**Generated:** 2026-05-29T04:36:50.225466+00:00  
**Classification:** `P140_POWER_PRECISION_3BET_APPLIED`  
**Strategy:** `power_precision_3bet` — POWER_LOTTO  
**Rows inserted:** 3000  
**DB rows before / after:** 85924 → 88924  

---

## 1. Executive Summary

P140 applied the `power_precision_3bet` (POWER_LOTTO, 3-bet) bet-2 and bet-3 rows via the P128 phase2 adapter `get_all_bets_power_precision` with `normalize_draw_context()` (added in P140A). Apply base: 1500 production baseline rows (LEGACY_UNVERIFIED excluded). All 3000 rows inserted (1500 bet-2, 1500 bet-3). power_orthogonal_5bet not applied — reserved for P141. Drift guard baseline updated to 88924.

---

## 2. Authorization Confirmation

- **Authorization present:** True
- **Apply allowed:** True
- **Exact phrase required:** `P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529`
- **Phrase observed:** `P139_AUTHORIZED_APPLY_POWER_PRECISION_3BET_BET2_BET3_USING_1500_PRODUCTION_BASE_20260529`

---

## 3. Canonical Repo / Branch Confirmation

- **Worktree path:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802`
- **Branch:** `claude/zen-gates-ff6802`
- **Worktree confirmed:** True
- **Repo OK:** True
- **Branch OK:** True

---

## 4. P140A Contract Fix Recap

- **P140A classification:** `P140A_DRAW_CONTEXT_CONTRACT_READY_FOR_P10_P12_APPLY`
- **P140A classification pass:** True
- **fix_applied:** True
- **canonical_key:** `history`
- **accepted_alias:** `historical_draws`
- **normalize_draw_context():** available in p128_wave2_phase2_adapters.py
- **rsr6_blocked_strategies_cleared:** False

---

## 5. P139 Dry-Run Gate Recap

- **P139 classification:** `P139_P10_P12_MULTI_BET_DRY_RUN_GATE_READY`
- **P139 classification pass:** True
- **P10 dry_run_ready:** True
- **P10 apply_base_rows:** 1500
- **P10 estimated_insert_rows:** 3000
- **P10 controlled_apply_id:** `P140_APPLY_POWER_PRECISION_3BET_v1`
- **P10 legacy_unverified_handling:** EXCLUDE_FROM_APPLY_BASE
- **P138B classification:** `P138B_P10_P12_LEGACY_ROWS_REMARKED`
- **P138B pass:** True

---

## 6. LEGACY_UNVERIFIED Exclusion Rule

- **Decision:** EXCLUDE_FROM_APPLY_BASE
- **Legacy rows total for strategy:** 50
- **Legacy excluded from apply base:** True
- **Production baseline rows used:** 1500
- **Apply base selector:**
  ```sql
  WHERE strategy_id='power_precision_3bet' AND lottery_type='POWER_LOTTO' AND bet_index=1 AND truth_level='POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED' AND controlled_apply_id='P20_POWERLOTTO_REMAINING_1500_PROD_20260520'
  ```
- **Legacy rows modified:** 0
- **Post-apply legacy count:** 50 (unchanged)
- **Legacy untouched verified:** True

---

## 7. Backup Creation and Verification

- **Backup path:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p140_backup_20260529T043650Z.db`
- **Backup created:** True
- **Backup row count:** 85924
- **Backup verification:** PASS

**Rollback command:**
```bash
cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p140_backup_20260529T043650Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'
```

---

## 8. Single-Strategy Apply Scope

| Field | Value |
|---|---|
| strategy_id | `power_precision_3bet` |
| lottery_type | `POWER_LOTTO` |
| target_bet_count | 3 |
| expected_insert_rows | 3000 |
| actual_insert_rows | 3000 |
| bet-2 rows | 1500 |
| bet-3 rows | 1500 |
| controlled_apply_id | `P140_APPLY_POWER_PRECISION_3BET_v1` |
| adapter_function | `get_all_bets_power_precision` |
| contract_normalizer | `normalize_draw_context` |
| adapter_source | `lottery_api/models/p128_wave2_phase2_adapters.py` |

**Strategies NOT applied in this task:**

- `power_orthogonal_5bet` (P12) — reserved for P141
- P7/P8/P9/P11 Wave 2 rows — already applied and preserved

---

## 9. Inserted Rows Summary

- **Total rows inserted:** 3000
- **bet-2 rows:** 1500
- **bet-3 rows:** 1500
- **truth_level:** inherited from bet-1 base (POWERLOTTO_REMAINING_STRATEGIES_BACKFILL_VERIFIED)
- **controlled_apply_id:** `P140_APPLY_POWER_PRECISION_3BET_v1`
- **source:** `P140_POWER_PRECISION_3BET_MULTI_BET_APPLY`
- **dry_run:** False

---

## 10. Duplicate Guard Result

- **Unique key:** `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`
- **Constraint active:** True
- **Duplicate insert rejected:** True
- **P12 extra rows:** 0
- **Guard OK:** True

---

## 11. bet_index Validation

- **bet_index=1 total count:** 1550 (expected 1550, includes 50 LEGACY_UNVERIFIED)
- **bet_index=2 count:** 1500 (expected 1500)
- **bet_index=3 count:** 1500 (expected 1500)
- **LEGACY_UNVERIFIED count:** 50 (expected 50)
- **Distribution OK:** True
- **All rows POWER_LOTTO:** True
- **Validation:** `PASS`

---

## 12. DB Rows Before / After

| Metric | Value |
|---|---:|
| Rows before | 85924 |
| Rows inserted | 3000 |
| Expected after | 88924 |
| Actual after | 88924 |
| Preservation OK | True |

---

## 13. Row Preservation Check

- **P7/P8/P9/P11 Wave 2 rows preserved:** True
- **P12 not applied:** True
- **LEGACY_UNVERIFIED untouched:** True

---

## 14. Drift Guard Baseline Handling

- **Previous total:** 85924
- **New total:** 88924
- **Rows added:** 3000
- **Update required:** True
- **p140_apply_id:** `P140_APPLY_POWER_PRECISION_3BET_v1`
- **p140_count:** 3000
- **Update note:** scripts/replay_lifecycle_drift_guard.py BASELINE total_count updated from 85924 to 88924; p140_apply_id='P140_APPLY_POWER_PRECISION_3BET_v1' count=3000 added

The `scripts/replay_lifecycle_drift_guard.py` baseline updated to 88924 rows.

---

## 15. Rollback Reference / Backup Path

**Backup:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p140_backup_20260529T043650Z.db`

**Rollback command:**
```bash
cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p140_backup_20260529T043650Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'
```

Restore backup to rollback P140 apply. Backup was verified at 85924 rows before any write.

---

## 16. Explicit Non-Actions

This P140 task did **not**:

- Apply `power_orthogonal_5bet` (P12) — reserved for P141
- Use LEGACY_UNVERIFIED rows as apply base
- Modify LEGACY_UNVERIFIED rows
- Modify P7/P8/P9/P11 Wave 2 already-applied rows
- Touch any 4_STAR strategies
- Execute P108 / P117 / P118
- Install any scheduler, cron, or launchd
- Perform strategy promotion, lifecycle, champion, or registry mutation
- Modify any other DB tables

---

## 17. Remaining Risks

- bet1_mismatch_count > 0 implies power_precision adapter rounding non-determinism — soft warning only; bet-2/bet-3 are independently generated from history
- power_orthogonal_5bet (P12) still awaits P141 authorization (P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529)
- RSR6_BLOCKED_STRATEGIES retained in p128 adapter for test compatibility — cleared operationally (P138B governance). No functional blocker for replay generation.
- LEGACY_UNVERIFIED 50 rows remain in DB; must never be used as apply base in P141

---

## 18. Recommended Next Task

P141: power_precision_3bet POWER_LOTTO Wave apply complete. Next: P141 — apply power_orthogonal_5bet (P12) POWER_LOTTO bet-2 through bet-5, +6000 rows, DB 88924 → 94924. Authorization phrase: P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_THRU_BET5_USING_1500_PRODUCTION_BASE_20260529

---

## 19. Final Classification

```text
P140_POWER_PRECISION_3BET_APPLIED
```

**Task:** P140  
**DB rows after apply:** 88924  
**Next:** P141 — power_orthogonal_5bet bet-2 through bet-5 (+6000 rows)  
