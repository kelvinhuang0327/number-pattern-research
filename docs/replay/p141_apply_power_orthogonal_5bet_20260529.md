# P141: Apply power_orthogonal_5bet Controlled Replay Rows

## 1. Executive Summary
P141 executed the authorized single-strategy controlled apply for power_orthogonal_5bet bet-2..bet-5.

## 2. Authorization confirmation from P141A artifact
- phrase: `P139_AUTHORIZED_APPLY_POWER_ORTHOGONAL_5BET_BET2_BET3_BET4_BET5_USING_1500_PRODUCTION_BASE_20260529`
- source: `outputs/replay/p141a_power_orthogonal_5bet_authorization_gate_20260529.json`

## 3. Canonical repo / branch confirmation
- repo_ok: `True`
- branch_ok: `True`

## 4. P140 result recap
- P140 power_precision_3bet apply remained preserved.

## 5. P140A contract fix recap
- normalize_draw_context available and used.

## 6. P139 dry-run gate recap
- P139 classification validated.

## 7. LEGACY_UNVERIFIED exclusion rule
- 50 LEGACY_UNVERIFIED rows excluded from apply base.

## 8. Backup creation and verification
- backup_path: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p141_backup_20260529T063000Z.db`
- backup_row_count: `88924`

## 9. Single-strategy apply scope
- power_orthogonal_5bet only.

## 10. Inserted rows summary
- 6000 rows inserted (bet-2..bet-5).

## 11. Duplicate guard result
- UNIQUE(lottery_type,target_draw,strategy_id,bet_index) respected.

## 12. bet_index validation
- bet1=1550, bet2=1500, bet3=1500, bet4=1500, bet5=1500.

## 13. DB rows before / after
- 88924 -> 94924.

## 14. Row preservation check
- power_precision_3bet and P7/P8/P9/P11 preserved.

## 15. Drift guard baseline handling
- baseline updated to 94924 with p141 apply id/count.

## 16. Rollback reference / backup path
- `cp '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/backups/lottery_v2.db.p141_backup_20260529T063000Z.db' '/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db'`

## 17. Explicit non-actions
- no scheduler, no 4_STAR/P108/P117/P118, no lifecycle mutation.

## 18. Remaining risks
- future applies require separate authorization.

## 19. Recommended next task
- continue governance follow-up for post-P141 chain closure.

## 20. Final classification
P141_POWER_ORTHOGONAL_5BET_APPLIED
