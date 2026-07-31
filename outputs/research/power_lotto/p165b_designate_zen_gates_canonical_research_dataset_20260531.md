# P165B — Designate zen-gates as Canonical Research Dataset

**Task**: P165B_DESIGNATE_ZEN_GATES_AS_CANONICAL_RESEARCH_DATASET  
**Date**: 2026-06-01  
**Final Classification**: `P165B_ZEN_GATES_CANONICAL_RESEARCH_DATASET_DESIGNATED`  
**Authorized Option**: B — Designate zen-gates as canonical research dataset

---

## Authorization Confirmed

**User-provided phrase**:
> `YES designate zen-gates as canonical research dataset`

This phrase matches the required Option B authorization from P164. P165B proceeds on this basis.

---

## Phase 0 Verification — ALL PASS

| Check | Result |
|---|---|
| Authorization phrase | PRESENT ✓ |
| Worktree path | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` ✓ |
| Branch | `claude/zen-gates-ff6802` ✓ |
| HEAD commit | `c8b423d0c1de26253be4cec79ae6de77719d1074` ✓ |
| DB rows | 94924 ✓ |
| Drift guard | PASS ✓ |
| P161 tests | PASS ✓ |
| P162 tests | PASS ✓ |
| P163 tests | PASS ✓ |
| P164 tests | PASS ✓ |
| P164 JSON artifact | Present ✓ |
| P164 MD artifact | Present ✓ |

---

## Canonical Research Dataset — Formally Designated

| Field | Value |
|---|---|
| **Designation** | CANONICAL_RESEARCH_DATASET |
| **Worktree path** | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802` |
| **Branch** | `claude/zen-gates-ff6802` |
| **DB path** | `lottery_api/data/lottery_v2.db` |
| **DB total rows** | 94,924 |
| **bet_index column** | PRESENT (column 27, INTEGER NOT NULL DEFAULT 1) |
| **UNIQUE constraint** | `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)` |
| **POWER_LOTTO rows** | 36,104 |
| **Distinct POWER_LOTTO draws** | 1,551 |
| **Effective from** | 2026-06-01 |

### Why Option B was chosen

1. zen-gates DB is already migrated, validated, and drift-guard clean (94,924 rows, bet_index present)
2. All P161/P162/P163/P164 research tests pass against this dataset
3. Avoids high-risk DB migration on main (Option C deferred)
4. All P149–P159B replay governance chain artifacts are present and valid in this worktree
5. Future POWER_LOTTO effectiveness research (P166+) requires the full 36,104-row dataset — not the stale main dataset at 15,142 rows
6. Option A (code/docs/tests merge only) would not solve research data completeness — main DB still lacks bet_index and 40,462 rows

---

## ⚠ main Remains Stale — Split Unresolved

| Dimension | zen-gates (canonical) | main (stale) |
|---|---|---|
| DB total rows | 94,924 | 54,462 |
| POWER_LOTTO rows | 36,104 | 15,142 |
| bet_index column | PRESENT | ABSENT |
| Schema columns | 27 | 26 |
| Research artifacts P161–P165B | PRESENT | NOT FOUND |

**The main/zen-gates DB split is NOT resolved by P165B.**

Option B is a policy designation, not a migration. main branch DB remains at 54,462 rows with no bet_index column. Production/mainline governance decisions still require a separate controlled migration (Option C) with its own authorization chain.

**Agent guard**: All research agents must target the zen-gates worktree DB. Any agent using main DB for POWER_LOTTO research is operating on stale, incomplete data.

---

## Worktree Preservation Guard — ACTIVE

The zen-gates worktree contains 94,924 rows including 40,462 rows absent from main. If the worktree is removed before the DB is copied to a permanent location, these rows are permanently lost.

**Required action before any worktree pruning**: copy `lottery_api/data/lottery_v2.db` to a permanent backup location. Backup directory: `backups/`.

At the start of each new session, verify:
```
ls /Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db
```

---

## No-Action Confirmations

P165B performed:
- **Zero DB writes** — DB unchanged at 94,924 rows
- **Zero merges** — no code merged between branches
- **Zero registry mutations** — no lifecycle labels changed
- **Zero commits or pushes** — artifact is untracked output only
- **Zero controlled_apply** — no new replay rows added
- **Zero champion promotions** — P147 still blocked
- **Zero scheduler/cron installations**
- **No wagering recommendations, no win guarantees, no real-money wording**
- **No API/UI/strategy implementation changes**

---

## Next Task

**P166_POWER_LOTTO_ENSEMBLE_VOTING_RESEARCH_PLAN_ONLY**

Scope: Research plan only — written plan for POWER_LOTTO ensemble/voting strategy effectiveness evaluation using zen-gates canonical dataset (94,924 rows, 36,104 POWER_LOTTO rows, 1,551 draws). No implementation, no DB write, no controlled_apply without separate authorization.

P165B does NOT authorize P166 implementation. A separate authorization is required before P166 research execution begins.

---

## Governance Invariants (unchanged)

| Invariant | Value |
|---|---|
| DB rows | 94,924 (must not change without explicit authorization) |
| Drift guard | PASS |
| No commit/push | True |
| No scheduler | True |
| No wagering/win-promise | True |
| main/zen-gates split | **UNRESOLVED** — not resolved by P165B |
| DB migration performed | **NO** |
| Merge performed | **NO** |
