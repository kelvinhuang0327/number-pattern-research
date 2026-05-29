# P138B: P10/P12 Legacy Row Re-mark — LEGACY_UNVERIFIED

**Generated:** 2026-05-29T03:40:10.180190+00:00
**Classification:** `P138B_P10_P12_LEGACY_ROWS_REMARKED`
**Worktree:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802`
**Branch:** `claude/zen-gates-ff6802`

---

## 1. Executive Summary

P138B is the **authorized execution** of P137 governance Option B.
100 NULL-provenance legacy rows (50 per strategy) in `power_precision_3bet` (P10)
and `power_orthogonal_5bet` (P12) are re-marked with `LEGACY_UNVERIFIED` metadata.

**No rows inserted. No rows deleted. DB total remains 85924.**

After re-mark:
- All 100 rows have `truth_level = 'LEGACY_UNVERIFIED'`, `source = 'P138B_LEGACY_REMARK'`, and a deterministic `provenance_hash`
- The NULL-provenance strict selector returns 0 rows
- Drift guard PASS at 85924
- P10/P12 legacy governance resolved; future dry-run gate re-evaluation is now allowed

---

## 2. Authorization Confirmation

| Field | Value |
|-------|-------|
| Required phrase | `P137_AUTHORIZED_OPTION_B_REMARK_P10_P12_LEGACY_ROWS_AS_LEGACY_UNVERIFIED_20260529` |
| Authorization present | ✅ YES |
| Re-mark allowed | ✅ YES |

---

## 3. P137 Governance Recap

**P137 classification:** `P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY`
**P137 recommended option:** option_b

P137 defined three governance options for the 100 NULL-provenance legacy rows.
Option B (re-mark with LEGACY_UNVERIFIED) was recommended and is now authorized.

---

## 4. Backup Creation and Verification

| Field | Value |
|-------|-------|
| Backup path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p138b_backup_20260529T034010Z.db` |
| Backup created | ✅ |
| Backup row count | 85924 |
| Backup row count OK | ✅ |

---

## 5. Strict Re-mark Selector

Only rows matching ALL of the following are eligible:

```sql
strategy_id IN ('power_precision_3bet', 'power_orthogonal_5bet')
AND bet_index = 1
AND controlled_apply_id IS NULL
AND provenance_hash IS NULL
AND truth_level IS NULL
AND (source IS NULL OR source = '')
AND replay_run_id IN (2, 6)
```

**Rows matching selector before re-mark:** 100

---

## 6. Re-mark Execution Summary

| Field | Value |
|-------|-------|
| Mutation type | `UPDATE_ONLY` |
| Expected rows to re-mark | 100 |
| Actual rows re-marked | 100 |
| Rows inserted | 0 |
| Rows deleted | 0 |
| truth_level set | `LEGACY_UNVERIFIED` |
| source set | `P138B_LEGACY_REMARK` |
| provenance_hash | deterministic SHA256[:16](strategy_id, target_draw, bet_index, replay_run_id, predicted_numbers, `P138B_LEGACY_REMARK_20260529`) |
| controlled_apply_id | NULL (unchanged) |

---

## 7. DB Rows Before / After

| Metric | Value |
|--------|-------|
| DB rows before re-mark | 85924 |
| DB rows after re-mark | 85924 |
| Row count unchanged | ✅ |

---

## 8. Selector Validation After Re-mark

| Check | Result |
|-------|--------|
| NULL-provenance selector count after | 0 |
| Selector returns 0 | ✅ |
| LEGACY_UNVERIFIED total | 100 |
| LEGACY_UNVERIFIED == 100 | ✅ |
| power_precision_3bet LEGACY_UNVERIFIED | 50 |
| power_orthogonal_5bet LEGACY_UNVERIFIED | 50 |

---

## 9. Row Preservation Check

**Production baseline rows (1500 per strategy) must be untouched:**

| Strategy | Production baseline rows | OK |
|----------|--------------------------|-----|
| `power_precision_3bet` | 1500 | ✅ |
| `power_orthogonal_5bet` | 1500 | ✅ |

**bet_index distribution after re-mark:**

| Strategy | bet_index | Rows |
|----------|-----------|------|
| `power_precision_3bet` | 1 | 1550 |
| `power_orthogonal_5bet` | 1 | 1550 |

---

## 10. Future Dry-Run Gate Impact

| Field | Value |
|-------|-------|
| P10 legacy governance resolved | ✅ |
| P12 legacy governance resolved | ✅ |
| Dry-run gate re-evaluation allowed | ✅ |
| controlled_apply executed | ❌ NO |
| Replay rows inserted | 0 |

P10/P12 are NOT automatically apply-ready after this re-mark.
A separate dry-run gate task (P139) must evaluate apply readiness.

---

## 11. Rollback Reference / Backup Path

**Backup path:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p138b_backup_20260529T034010Z.db`

To roll back:
```bash
# Stop any DB access first, then:
cp "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p138b_backup_20260529T034010Z.db" "/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db"
```

**Rollback removes:** The 100-row re-mark (restores NULL provenance).
**Rollback does NOT affect:** Any other rows or strategies.

---

## 12. Explicit Non-Actions

- ❌ No controlled_apply executed
- ❌ No replay rows inserted
- ❌ No replay rows deleted
- ❌ No P131–P134 / P126B–P126F rows touched
- ❌ No Wave 2 safe candidate rows touched
- ❌ No 4_STAR / P108 / P117 / P118 execution
- ❌ No scheduler / cron / launchd install
- ❌ No strategy lifecycle / champion / registry mutation
- ✅ DB rows: 85924 (unchanged)
- ✅ Only the 100 strict-selector rows were modified

---

## 13. Remaining Risks

- P10/P12 still require a separate multi-bet dry-run gate (P139) before apply_ready=true.
- The LEGACY_UNVERIFIED provenance_hash is synthetic — not derived from the original prediction run.
- P10/P12 bet-2+ rows have not been inserted; multi-bet controlled_apply is still a future task.
- drift_guard allowlist now includes LEGACY_UNVERIFIED — this is intentional and audited.
- Backup file exists at backups/ (untracked) — it should not be staged or committed.

---

## 14. Recommended Next Task

**P139: P10/P12 multi-bet dry-run gate — re-evaluate apply_ready status after legacy governance resolution, plan bet-2+ row controlled_apply.**

---

## 15. Final Classification

```
P138B_P10_P12_LEGACY_ROWS_REMARKED
```
