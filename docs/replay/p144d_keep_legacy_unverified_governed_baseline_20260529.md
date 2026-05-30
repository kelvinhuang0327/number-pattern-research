# P144D: Keep Legacy Unverified as Governed Baseline — Option A Decision Recorded

Generated: 2026-05-30T07:17:03.702985+00:00
Task: P144D
Classification: `P144D_LEGACY_UNVERIFIED_KEEP_GOVERNED_BASELINE_DECISION_RECORDED`

---

## 1. Authorization

- Required phrase: `P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529`
- Authorization present: True
- Decision allowed: True
- Source: explicit_command_argument

---

## 2. Canonical Repo / Branch Check

| Check | Expected | Actual | OK |
|-------|----------|--------|----|
| Repo  | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | True |
| Branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | True |

---

## 3. DB Snapshot (Read-Only)

- Total rows: 94924 (expected: 94924)
- Rows OK: True
- bet_index column exists: True

---

## 4. Predecessor Artifact Validation

| Artifact | Classification | OK |
|----------|----------------|----|
| P144C | `P144C_LEGACY_UNVERIFIED_REMEDIATION_AUTHORIZATION_GATE_READY` | ✓ |
| P146B | `P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED` | ✓ |
| P142  | `P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED` | ✓ |

---

## 5. Legacy Unverified Current State (Read-Only DB Queries)

| Strategy | LEGACY_UNVERIFIED Rows | bet_index |
|----------|------------------------|-----------|
| power_precision_3bet | 50 | 1 only |
| power_orthogonal_5bet | 50 | 1 only |
| **Total** | **100** | — |

- All rows bet_index=1: True
- All rows controlled_apply_id NULL: True
- P140/P141 multi-bet contamination: False
- Actual source: `P138B_LEGACY_REMARK`
- Counts OK (50+50=100): True

---

## 6. Selected Remediation Option

- **Option**: `option_a_keep_governed_legacy_baseline`
- DB mutation required: False
- Row count impact: 0
- Risk level: NONE
- Execution performed in P144D: True
- Remediation mutation performed: False

---

## 7. Governed Baseline Policy

| Policy | Value |
|--------|-------|
| Keep legacy unverified rows | True |
| Exclude from champion evaluation | True |
| Exclude from apply base | True |
| Live monitoring blocked by legacy rows | False |
| Registry update blocked by legacy rows | False |
| Future remediation allowed with new authorization | True |

---

## 8. Strict Selector Definitions

```sql
strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') AND truth_level = 'LEGACY_UNVERIFIED' AND bet_index = 1 AND controlled_apply_id IS NULL AND source = 'P138B_LEGACY_REMARK'
```

- strategy_id IN: ['power_precision_3bet', 'power_orthogonal_5bet']
- truth_level: `LEGACY_UNVERIFIED`
- bet_index: 1
- controlled_apply_id: IS NULL
- source: `P138B_LEGACY_REMARK`

---

## 9. Champion / Monitoring Impact

| Impact | Value |
|--------|-------|
| Champion promotion allowed in P144D | False |
| Champion eval still requires live monitoring verified | True |
| Live monitoring can continue | True |
| P147 blocked until live monitoring verified | True |

---

## 10. Non-Actions Confirmation

| Action | Performed |
|--------|-----------|
| DB write in P144D | False |
| Controlled apply executed | False |
| Remediation mutation executed | False |
| Replay rows inserted | 0 |
| Replay rows updated | 0 |
| Replay rows deleted | 0 |
| Registry update executed | False |
| Champion promotion executed | False |
| Monitoring run executed | False |
| Scheduler installed | False |
| Live API called | False |
| 4-STAR executed | False |
| P108 executed | False |
| P117 executed | False |
| P118 executed | False |

---

## 11. Dirty File Hygiene

- backups/ untracked (not staged): True
- P135/P136/P142 autouse regen risk noted: True
- Forbidden files staged: False

---

## 12. Remaining Risks

- LEGACY_UNVERIFIED rows remain in DB indefinitely until future remediation with new authorization.
- Champion promotion (P147) requires live monitoring verified draws — not yet achieved.
- Future schema migrations must preserve bet_index=1 / LEGACY_UNVERIFIED isolation.
- Any new controlled_apply must use strict selector to avoid overwriting legacy rows.

---

## 13. Next Recommended Task

**P147_CHAMPION_EVALUATION_GATE**

---

## 14. Summary

P144D records the Option A decision: keep 100 LEGACY_UNVERIFIED rows (50 power_precision_3bet + 50 power_orthogonal_5bet, all bet_index=1, controlled_apply_id IS NULL, source=P138B_LEGACY_REMARK) as a governed legacy baseline. No DB mutation was performed. DB row count remains 94924. Champion evaluation and apply base exclude LEGACY_UNVERIFIED rows by truth_level filter. Live monitoring is NOT blocked. P147 champion promotion gate remains blocked until live monitoring verified draws are accumulated.
