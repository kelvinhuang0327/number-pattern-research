# P144C: Legacy Unverified Remediation Authorization Gate

**Generated:** 2026-05-29T10:15:22.724905+00:00  
**Classification:** `P144C_LEGACY_UNVERIFIED_REMEDIATION_AUTHORIZATION_GATE_READY`  
**Canonical Repo:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802`  
**Branch:** `claude/zen-gates-ff6802`

---

## 1. Repo / Branch Check

| Field | Expected | Actual | OK |
|-------|----------|--------|----|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | True |
| Branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | True |

---

## 2. DB Snapshot

| Field | Value |
|-------|-------|
| DB Path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db` |
| Total Rows | 94924 |
| Expected Rows | 94924 |
| Rows OK | True |
| bet_index column exists | True |

---

## 3. Predecessor Artifact Validation

| Artifact | Classification | OK |
|----------|---------------|----|
| P146B | `P146B_AUTHORIZED_OBSERVATION_ONLY_MONITORING_RUN_COMPLETED` | True |
| P142 | `P142_WAVE2_MULTI_BET_APPLY_CHAIN_CLOSED` | True |
| P138B | `P138B_P10_P12_LEGACY_ROWS_REMARKED` | True |

---

## 4. LEGACY_UNVERIFIED Current State

| Field | Value |
|-------|-------|
| power_precision_3bet rows | 50 |
| power_orthogonal_5bet rows | 50 |
| Total LEGACY_UNVERIFIED rows | 100 |
| All rows bet_index=1 | True |
| All rows controlled_apply_id NULL | True |
| P140/P141 multi-bet contamination | False |
| Source value | `P138B_LEGACY_REMARK` |

---

## 5. Strict Selector Definitions

```sql
WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') AND truth_level = 'LEGACY_UNVERIFIED' AND bet_index = 1 AND controlled_apply_id IS NULL AND source = 'P138B_LEGACY_REMARK'
```

| Criterion | Value |
|-----------|-------|
| strategy_id IN | ['power_precision_3bet', 'power_orthogonal_5bet'] |
| truth_level | `LEGACY_UNVERIFIED` |
| bet_index | 1 |
| controlled_apply_id | IS NULL |
| source | `P138B_LEGACY_REMARK` |

---

## 6. Remediation Option Matrix

### Option: option_a_keep_governed_legacy_baseline

**Description:** Keep LEGACY_UNVERIFIED rows as a governed legacy baseline. No DB mutation required.  
**DB Mutation Required:** False  
**Row Count Impact:** 0  
**Backup Required:** False  
**Rollback Path:** no action needed  
**Risk Level:** NONE  
**Champion Impact:** legacy rows excluded from champion eval by truth_level filter  
**Authorization Phrase:** `P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529`  

### Option: option_b_enrich_provenance_metadata

**Description:** Enrich provenance metadata (provenance_source, notes) for LEGACY_UNVERIFIED rows. UPDATE only — no INSERT/DELETE. Row count unchanged.  
**DB Mutation Required:** True  
**Row Count Impact:** 0  
**Backup Required:** True  
**Rollback Path:** restore from backup  
**Risk Level:** LOW  
**Champion Impact:** improves traceability, no count change  
**Authorization Phrase:** `P144C_AUTHORIZED_ENRICH_P10_P12_LEGACY_UNVERIFIED_PROVENANCE_20260529`  

### Option: option_c_quarantine_with_backup

**Description:** Move LEGACY_UNVERIFIED rows to a separate quarantine table or artifact. Removes them from strategy_prediction_replays but preserves them in quarantine.  
**DB Mutation Required:** True  
**Row Count Impact:** -100  
**Backup Required:** True  
**Rollback Path:** restore from backup and reverse move  
**Risk Level:** MEDIUM  
**Champion Impact:** removes rows from strategy_prediction_replays  
**Authorization Phrase:** `P144C_AUTHORIZED_QUARANTINE_P10_P12_LEGACY_UNVERIFIED_WITH_BACKUP_20260529`  

### Option: option_d_delete_with_strict_selector

**Description:** Permanently delete LEGACY_UNVERIFIED rows using strict selector. Irreversible without backup restore.  
**DB Mutation Required:** True  
**Row Count Impact:** -100  
**Backup Required:** True  
**Rollback Path:** restore from backup only  
**Risk Level:** HIGH/DESTRUCTIVE  
**Champion Impact:** permanent row removal  
**Authorization Phrase:** `P144C_AUTHORIZED_DELETE_P10_P12_LEGACY_UNVERIFIED_WITH_STRICT_SELECTOR_20260529`  

---

## 7. Recommended Remediation Path

**Recommended Option:** `option_a_keep_governed_legacy_baseline`  
**Reason:** LEGACY_UNVERIFIED rows are already excluded from champion eval and multi-bet apply by truth_level filter. No remediation required at this stage. Rows are isolated, non-contaminating, and well-documented via P138B remark.  
**DB Write Required Later:** False  
**Next Gate:** `P144D_LEGACY_UNVERIFIED_REMEDIATION_EXECUTION`  
**Note:** If richer traceability is desired before P147 live monitoring, option_b is safe. Options C and D require explicit authorization with backup verification.

---

## 8. Authorization Phrase Templates

| Option | Authorization Phrase |
|--------|---------------------|
| option_a | `P144C_AUTHORIZED_KEEP_LEGACY_UNVERIFIED_AS_GOVERNED_BASELINE_20260529` |
| option_b | `P144C_AUTHORIZED_ENRICH_P10_P12_LEGACY_UNVERIFIED_PROVENANCE_20260529` |
| option_c | `P144C_AUTHORIZED_QUARANTINE_P10_P12_LEGACY_UNVERIFIED_WITH_BACKUP_20260529` |
| option_d | `P144C_AUTHORIZED_DELETE_P10_P12_LEGACY_UNVERIFIED_WITH_STRICT_SELECTOR_20260529` |

---

## 9. Champion / Monitoring Impact

| Field | Value |
|-------|-------|
| champion_promotion_allowed_in_p144c | False |
| live_monitoring_blocked_by_legacy_rows | False |
| registry_update_blocked_by_legacy_rows | False |
| recommended_before_p147 | option_a or option_b |

---

## 10. Non-Actions (All False/0)

| Action | Value |
|--------|-------|
| db_write_in_p144c | False |
| remediation_executed_in_p144c | False |
| replay_rows_updated_in_p144c | 0 |
| replay_rows_deleted_in_p144c | 0 |
| controlled_apply_executed | False |
| registry_update_executed | False |
| champion_promotion_executed | False |
| monitoring_run_executed | False |
| scheduler_installed | False |
| live_api_call_made | False |
| four_star_executed | False |
| p108_executed | False |
| p117_executed | False |
| p118_executed | False |

---

## 11. Dirty File Hygiene

| Field | Value |
|-------|-------|
| backups_untracked_not_staged | True |
| forbidden_files_staged | False |

---

## 12. Remaining Risks

**R1** (LOW): LEGACY_UNVERIFIED rows could confuse future analyst if not documented  
Mitigation: P138B remark + P144C artifact provide full audit trail  

**R2** (MEDIUM): If option_d is authorized without backup, rows are permanently lost  
Mitigation: Backup required gate in all destructive options  

**R3** (LOW): Autouse-regenerated JSON artifacts may appear as dirty in git status  
Mitigation: Whitelist-only staging; restore autouse files before commit  

---

## 13. Roadmap / CTO Update

Roadmap and CTO-Analysis updated as part of this script run.

---

## 14. Next Recommended Task

**Task ID:** P144D  
**Description:** Legacy unverified remediation execution (requires explicit authorization phrase)  
**Prerequisite Artifact:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/outputs/replay/p144c_legacy_unverified_remediation_authorization_gate_20260529.json`  
**Prerequisite Classification:** `P144C_LEGACY_UNVERIFIED_REMEDIATION_AUTHORIZATION_GATE_READY`

---

## 15. Summary

P144C authorization gate complete. LEGACY_UNVERIFIED rows: power_precision_3bet=50, power_orthogonal_5bet=50, total=100. All rows have bet_index=1, controlled_apply_id=NULL, source='P138B_LEGACY_REMARK'. No multi-bet contamination. Recommended option: option_a (keep as governed baseline). No DB writes in P144C. Four remediation options documented with authorization phrases.
