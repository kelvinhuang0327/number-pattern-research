# P137: P10/P12 Legacy Row Governance Authorization Gate

**Generated:** 2026-05-29T03:28:48.251675+00:00
**Classification:** `P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY`
**Worktree:** `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802`
**Branch:** `claude/zen-gates-ff6802`

---

## 1. Executive Summary

P137 is a **read-only governance gate** for `power_precision_3bet` (P10) and
`power_orthogonal_5bet` (P12). No DB writes, no controlled_apply, no row insertions.

Both strategies contain **50 NULL-provenance legacy rows each** (100 total) in addition
to 1500 clean production baseline rows from the P20 backfill. These legacy rows predate
the P20 provenance pipeline and have NULL `provenance_hash`, `controlled_apply_id`,
`truth_level`, and `source`.

P137 defines three governance options, provides authorization phrase templates for each,
and identifies the next executable task pending CTO authorization.

---

## 2. Canonical Repo / Branch Confirmation

| Field | Expected | Actual | OK |
|-------|----------|--------|----|
| Repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` | ✅ |
| Branch | `claude/zen-gates-ff6802` | `claude/zen-gates-ff6802` | ✅ |
| DB rows | `85924` | `85924` | ✅ |
| bet_index schema | required | present | ✅ |
| Drift guard | PASS | PASS | ✅ |

---

## 3. P136 Recap

**P136 classification:** `P136_POST_RSR6_P10_P12_REEVALUATION_READY`
**RSR6 cleanup classification:** `RSR6_ORPHAN_BET_INDEX2_CLEANUP_APPLIED`

P136 confirmed that after RSR6 orphan bet_index cleanup:
- P10/P12 each have 1550 bet-1 rows and 0 bet-2+ rows
- 1500 rows per strategy have full P20 production provenance
- 50 rows per strategy retain NULL provenance from pre-P20 replay runs

P136 deferred the governance decision to P137 without DB mutation.

---

## 4. Why P10/P12 Need a Governance Decision

The apply gate for multi-bet controlled_apply requires **provenance completeness** —
all rows must have non-NULL `provenance_hash`, `controlled_apply_id`, `truth_level`,
and `source`. The 50 NULL-provenance rows per strategy fail this check.

These rows come from two early replay runs:
- `replay_run_id=2`: 20 rows per strategy (earliest batch)
- `replay_run_id=6`: 30 rows per strategy (second batch)

Both batches were inserted before the P20 provenance pipeline was established.
RSR6 cleaned orphan bet_index>1 rows but was explicitly scoped to not touch
NULL-provenance rows.

---

## 5. Current P10/P12 Row Distribution

| Strategy | bet-1 rows | bet-2+ rows |
|----------|-----------|-------------|
| `power_precision_3bet` | 1550 | 0 |
| `power_orthogonal_5bet` | 1550 | 0 |

Both strategies: `apply_ready = false`

---

## 6. NULL-Provenance Legacy Row Audit

| Strategy | NULL provenance rows | Production baseline rows | Draw range |
|----------|---------------------|--------------------------|------------|
| `power_precision_3bet` | 50 | 1500 | 99000055–99000104 |
| `power_orthogonal_5bet` | 50 | 1500 | 99000055–99000104 |
| **Total under decision** | **100** | — | — |

**replay_run_id breakdown (per strategy):**
- `replay_run_id=2`: 20 rows (NULL truth_level, NULL source, NULL provenance_hash)
- `replay_run_id=6`: 30 rows (NULL truth_level, NULL source, NULL provenance_hash)

**No DB write in P137:** confirmed (`db_write_in_p137 = false`)

---

## 7. Governance Decision Options

### Option A — Keep as Governed Legacy Baseline

**DB mutation:** None
**Risk level:** LOW

Accept the 50+50 NULL-provenance rows as part of the historical record.
Document them as a recognized legacy class via policy artifact only.
The dry-run gate must be updated to explicitly accept NULL-provenance rows as a
`legacy_class` designation.

**Risks:** NULL provenance remains permanently unresolved. Future governance tooling
may re-flag these rows. apply_gate must include a legacy_class exception.

**Rollback/Backup:** Not required.

**Authorization phrase:**
```
I authorize Option A for P10/P12 NULL-provenance legacy rows: accept 50 rows per strategy as governed legacy baseline with no DB mutation, and approve future dry-run gate to proceed acknowledging this legacy class.
```

---

### Option B — Re-mark with Explicit Metadata (RECOMMENDED)

**DB mutation:** UPDATE 100 rows (50 per strategy)
**Risk level:** MEDIUM

UPDATE the 100 NULL-provenance rows to assign:
- `truth_level = 'LEGACY_UNVERIFIED'`
- `controlled_apply_id = 'P137_LEGACY_REMARK'`
- `source = 'LEGACY_REPLAY_RUN'`
- `provenance_hash = deterministic_hash(strategy_id + target_draw)`

This converts NULL-provenance rows to a traceable governed state while preserving
the historical record. DB row count remains 85924.

**Risks:** Requires DB backup. Introduces synthetic provenance_hash — must be labeled
`LEGACY_UNVERIFIED` to distinguish from real prediction provenances.

**Rollback/Backup:** Full DB backup required before execution.

**Authorization phrase:**
```
I authorize Option B for P10/P12 NULL-provenance legacy rows: execute a governed re-mark UPDATE of 100 rows assigning truth_level='LEGACY_UNVERIFIED', controlled_apply_id='P137_LEGACY_REMARK', source='LEGACY_REPLAY_RUN', and deterministic provenance_hash, with DB backup taken before execution. I understand this introduces synthetic provenance metadata.
```

---

### Option C — Quarantine/Delete with Strict Selector

**DB mutation:** DELETE 100 rows (50 per strategy)
**Risk level:** MEDIUM-HIGH

DELETE rows matching:
```sql
WHERE strategy_id IN ('power_precision_3bet','power_orthogonal_5bet')
  AND provenance_hash IS NULL
  AND CAST(target_draw AS INTEGER) BETWEEN 99000055 AND 99000104
```

P10/P12 would have exactly 1500 clean production rows each.
DB total drops from 85924 to **85824**. Drift guard baseline must be updated.

**Risks:** Data deletion is irreversible without backup. 100 historical prediction
records permanently removed. Drift guard re-baseline required.

**Rollback/Backup:** Full DB backup required before execution. Restore procedure required.

**Authorization phrase:**
```
I authorize Option C for P10/P12 NULL-provenance legacy rows: execute a governed DELETE of 100 rows (strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') AND provenance_hash IS NULL AND CAST(target_draw AS INTEGER) BETWEEN 99000055 AND 99000104) with DB backup taken before execution. I acknowledge that total DB rows will decrease from 85924 to 85824 and drift guard baseline must be updated after deletion.
```

---

## 8. Recommended Decision

**Recommended: Option B** (re-mark with LEGACY_UNVERIFIED metadata)

Option B (re-mark) is recommended because it resolves the NULL-provenance state without data loss (unlike Option C) and without leaving permanent untracked metadata (unlike Option A). Re-marking with LEGACY_UNVERIFIED truth_level explicitly acknowledges that these rows predate the P20 provenance pipeline while preserving the historical record. The synthetic provenance_hash approach is well-established in the codebase (see P20 backfill). Option A creates permanent technical debt in governance tooling. Option C reduces the dataset unnecessarily for rows that are otherwise valid historical data.

> **This recommendation is advisory only. Option B requires explicit CTO authorization before execution. The authorization phrase in option_b.authorization_phrase_template must be provided verbatim before any DB mutation proceeds.**
>
> **Authorization status: PENDING — not yet authorized**

---

## 9. Authorization Phrase Templates

All phrases must be provided **verbatim** by the authorizing party.
Paraphrasing or partial repetition does not constitute authorization.

**Option A:**
```
I authorize Option A for P10/P12 NULL-provenance legacy rows: accept 50 rows per strategy as governed legacy baseline with no DB mutation, and approve future dry-run gate to proceed acknowledging this legacy class.
```

**Option B (recommended):**
```
I authorize Option B for P10/P12 NULL-provenance legacy rows: execute a governed re-mark UPDATE of 100 rows assigning truth_level='LEGACY_UNVERIFIED', controlled_apply_id='P137_LEGACY_REMARK', source='LEGACY_REPLAY_RUN', and deterministic provenance_hash, with DB backup taken before execution. I understand this introduces synthetic provenance metadata.
```

**Option C:**
```
I authorize Option C for P10/P12 NULL-provenance legacy rows: execute a governed DELETE of 100 rows (strategy_id IN ('power_precision_3bet','power_orthogonal_5bet') AND provenance_hash IS NULL AND CAST(target_draw AS INTEGER) BETWEEN 99000055 AND 99000104) with DB backup taken before execution. I acknowledge that total DB rows will decrease from 85924 to 85824 and drift guard baseline must be updated after deletion.
```

---

## 10. Future Dry-Run Gate Impact

**Current blocker:** P10/P12 are blocked from dry-run gate because both strategies contain NULL-provenance legacy rows. The apply gate cannot validate provenance completeness until the governance decision is made and executed.

| After option | Dry-run gate feasible? | Condition | Next task |
|-------------|----------------------|-----------|-----------|
| Option A | ✅ | Dry-run gate must include explicit legacy_class acceptance clause for NULL-provenance rows. | `P138A: dry-run gate with legacy_class acceptance for P10/P12` |
| Option B | ✅ | All 100 rows have non-NULL provenance_hash. Drift guard re-check at 85924. | `P138B: dry-run gate for P10/P12 post-re-mark` |
| Option C | ✅ | Drift guard re-baseline at 85824. P10/P12 have clean 1500-row production state. | `P138C: drift guard re-baseline + dry-run gate for P10/P12 post-deletion` |

**Note:** Even after resolving the NULL-provenance issue, P10/P12 will still need a separate multi-bet controlled_apply to insert bet-2+ rows. P10 is power_precision_3bet (bet-2, bet-3 needed). P12 is power_orthogonal_5bet (bet-2 through bet-5 needed). The governance gate decision is a prerequisite, not a sufficient condition, for apply_ready.

---

## 11. Explicit Non-Actions in P137

- ❌ No DB writes executed
- ❌ No controlled_apply executed
- ❌ No replay rows inserted
- ❌ No `4_STAR` / `P108` / `P117` / `P118` execution
- ❌ No scheduler / cron / launchd install
- ❌ No strategy lifecycle / champion / registry mutation
- ❌ No P7/P8/P9/P11 Wave 2 rows touched
- ❌ No P126B–P126F / P131–P134 completed data touched
- ✅ DB rows: 85924 (unchanged)

---

## 12. Remaining Risks

- NULL-provenance rows remain unresolved until governance option is authorized and executed.
- P10/P12 cannot enter dry-run gate until governance decision is made.
- Option B introduces synthetic provenance_hash that must be clearly labeled LEGACY_UNVERIFIED.
- Option C permanently reduces DB row count from 85924 to 85824 — drift guard baseline must be updated.
- Option A leaves NULL-provenance rows permanently unresolved — future governance tools may re-flag them.
- No multi-bet row gap covered in P137 — P10/P12 still need bet-2+ rows regardless of governance option chosen.

---

## 13. Recommended Next Task

**After governance decision authorization: P138 — execute chosen governance option for P10/P12 legacy rows, then re-assess dry-run gate readiness.**

After CTO provides the authorization phrase for the chosen option, the next task is:
- **P138A** (after Option A): update dry-run gate to accept legacy_class for P10/P12
- **P138B** (after Option B): execute re-mark UPDATE with backup, verify 100 rows re-marked
- **P138C** (after Option C): execute DELETE with backup, re-baseline drift guard at 85824

---

## 14. Final Classification

```
P137_P10_P12_LEGACY_ROW_GOVERNANCE_GATE_READY
```
