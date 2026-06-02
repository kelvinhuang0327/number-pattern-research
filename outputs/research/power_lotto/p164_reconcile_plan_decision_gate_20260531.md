# P164 Reconcile Plan Decision Gate

**Task**: P164_RECONCILE_PLAN_DECISION_GATE  
**Date**: 2026-06-01  
**Final Classification**: `P164_RECONCILE_PLAN_DECISION_GATE_READY`  
**Status**: WAITING_FOR_USER_AUTHORIZATION

---

## Phase 0 Verification — ALL PASS

| Check | Result |
|---|---|
| Worktree path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` ✓ |
| Branch | `claude/zen-gates-ff6802` ✓ |
| HEAD commit | `c8b423d0c1de26253be4cec79ae6de77719d1074` ✓ |
| DB rows | 94924 ✓ |
| Drift guard | PASS ✓ |
| P161 tests | PASS (23/23) ✓ |
| P162 tests | PASS (14/14) ✓ |
| P163 tests | PASS (17/17) ✓ |
| P163 JSON artifact | Present ✓ |
| P163 MD artifact | Present ✓ |

---

## P163 Audit Summary

P163 was a read-only audit (no DB write, no merge, no registry mutation, no commit, no push). Key findings:

| Dimension | zen-gates | main | Risk |
|---|---|---|---|
| DB total rows | 94,924 | 54,462 | HIGH — delta = 40,462 |
| POWER_LOTTO rows | 36,104 | 15,142 | HIGH |
| bet_index column | PRESENT (col 27) | ABSENT | HIGH — schema incompatibility |
| UNIQUE constraint | (type,draw,strategy,bet_index) | (type,draw,strategy) | HIGH |
| Research artifacts P161-P163 | PRESENT | NOT FOUND | LOW |
| P140-P162 test files | 36 files | 0 files | LOW |
| Roadmap last updated | 2026-05-30 | 2026-05-28 | LOW |

**Root cause of row delta**: zen-gates applied P129B bet_index schema migration + P130-P141 Wave2 multi-bet controlled_apply + P142-P159B replay governance chain. Main stopped at P128 (design only).

**Governance risk**: zen-gates is NOT a simple ahead-of-main branch. It contains irreversible DB mutations that main does not have. A naive merge would either fail on UNIQUE constraint violations or leave main DB in inconsistent state.

---

## Option A/B/C Comparison

| | Option A | Option B | Option C |
|---|---|---|---|
| **Label** | Code/docs/tests merge only | Designate zen-gates as canonical dataset | Controlled DB/data migration |
| **Risk** | LOW | MEDIUM | HIGH |
| **DB impact** | NONE | NONE (policy change only) | HIGH — schema + 40462 row inserts |
| **Key benefit** | Gets CI artifacts into main without DB risk | One canonical DB, no migration needed | Full consistency between main and zen-gates |
| **Key limitation** | main DB remains stale; bet_index code fails against main DB | Worktree must be preserved; Repo Policy update needed | ~12 sequential authorization phrases; irreversible without backup |
| **Authorization phrase** | `YES proceed with Option A code/docs/tests-only reconcile, no DB write` | `YES designate zen-gates as canonical research dataset` | `YES prepare controlled DB/data migration plan only, no apply` |

### Option A — Code/docs/tests merge only (LOW risk)

**What it does**: Merge the 36 test files, 30+ scripts, and research artifacts (P161-P163) from zen-gates to main. Leave main DB untouched at 54,462 rows. bet_index column remains absent on main.

**After Option A**: main DB remains at 54,462 rows with no bet_index. Code referencing bet_index will fail against main DB. This is an acknowledged, known inconsistency — not a hidden risk.

**STOP guards**:
- If any merged script auto-writes to main DB, STOP immediately
- Verify main DB row count = 54,462 before AND after merge
- If merge creates conflicts in DB migration scripts, STOP and report

**Required authorization phrase**:
> `YES proceed with Option A code/docs/tests-only reconcile, no DB write`

---

### Option B — Designate zen-gates as canonical dataset (MEDIUM risk)

**What it does**: Formally policy-designate the zen-gates worktree DB (94,924 rows, bet_index present) as the authoritative dataset. Main branch DB archived as legacy baseline.

**After Option B**: All future work uses zen-gates DB. Main remains stale. Repo Policy in roadmap.md must be updated to remove the "no worktree canonical" rule. zen-gates worktree must be copied to a permanent location before any worktree pruning.

**STOP guards**:
- If zen-gates worktree is removed before DB is backed up to permanent location, 40,462 rows are permanently lost
- Verify worktree path exists at each new session start

**Required authorization phrase**:
> `YES designate zen-gates as canonical research dataset`

---

### Option C — Controlled DB/data migration (HIGH risk — PLAN ONLY in P164)

**What it does**: Formally migrate main DB to match zen-gates state. Steps: (1) backup main DB, (2) run P129B schema migration on main, (3) re-run P130-P141 controlled_apply scripts in order, (4) verify drift guard at 94,924 on main, (5) merge code/tests/docs.

**P164 CANNOT authorize DB apply.** Option C authorization phrase above authorizes PLAN PREPARATION only in a subsequent P165 task. Actual DB migration requires a separate explicit authorization chain.

**STOP guards**:
- Backup must exist and be verified before step 1
- Each step requires its own authorization phrase (P129B + ~10 controlled_apply)
- If any step fails, STOP; do not proceed to next step
- Intermediate row counts must match expected values at each step

**Required authorization phrase**:
> `YES prepare controlled DB/data migration plan only, no apply`

---

## Recommended Option

**Primary recommendation: Option A** (conservative, gets CI parity without DB risk)  
**Secondary recommendation: Option B** (if user wants to preserve zen-gates as the single working environment)  
**Option C**: Deferred — must be planned as P165 with separate authorization chain after Option A or B

**Why Option A first**:
- Gets 36 test files and research artifacts into main history immediately
- No DB risk — main DB integrity preserved
- Explicitly documents the known code-DB inconsistency for resolution later
- Lower authorization burden for the user

**Why not Option C immediately**:
- Requires ~12 sequential authorization phrases across separate sessions
- Scripts are rehearsed but not yet sequenced for main DB application
- Should be preceded by a detailed P165 plan task

---

## No-Action Confirmations

This task (P164) has performed:
- **Zero DB writes** — main DB and zen-gates DB both unchanged
- **Zero merges** — no code merged between branches
- **Zero registry mutations** — no lifecycle labels changed
- **Zero commits or pushes** — artifact is untracked output only
- **Zero controlled_apply** — no new replay rows added
- **Zero champion promotions** — P147 still BLOCKED
- **Zero scheduler/cron installations**
- **No wagering recommendations, no win guarantees, no real-money wording**

---

## Next Step — WAITING_FOR_USER_AUTHORIZATION

**The P164 decision gate is READY.**

No reconcile action will be taken until the user explicitly provides one of the three authorization phrases below. Copy-paste the exact phrase to proceed:

**Option A** (code/docs/tests merge, no DB write — LOW risk):
```
YES proceed with Option A code/docs/tests-only reconcile, no DB write
```

**Option B** (designate zen-gates as canonical dataset — MEDIUM risk):
```
YES designate zen-gates as canonical research dataset
```

**Option C** (prepare controlled DB migration plan only, no apply — HIGH risk, plan step only):
```
YES prepare controlled DB/data migration plan only, no apply
```

**P165 and all subsequent reconcile tasks are BLOCKED until one of these phrases is received.**

No agent may assume authorization from context, implication, or prior conversation history.

---

## Governance Invariants (unchanged from P163)

| Invariant | Value |
|---|---|
| DB rows | 94,924 (must not change without explicit authorization) |
| Drift guard | PASS |
| No commit/push | True — artifact tasks must not auto-commit |
| No scheduler | True — no cron/launchd installed |
| No wagering/win-promise | True |
| main/zen-gates split | **UNRESOLVED** — not resolved by P164 |
| Reconcile finalized | **NO** — decision gate only |
