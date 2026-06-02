# P184 — Controlled DB Migration Rehearsal (Temp Copy Only)

**Task**: `P184_CONTROLLED_DB_MIGRATION_REHEARSAL_TEMP_COPY_ONLY`
**Final Classification**: `P184_CONTROLLED_DB_MIGRATION_REHEARSAL_TEMP_COPY_READY`
**Date**: 2026-06-01
**Branch**: `main`
**Authorization**: `YES start P184 controlled DB migration rehearsal on temp copy only`

---

## Phase 0 Verification — PASS

| Check | Expected | Actual | Status |
|-------|----------|--------|--------|
| repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | same | PASS |
| branch | `main` | `main` | PASS |
| main DB rows | `54462` | `54462` | PASS |
| main bet_index | ABSENT | ABSENT | PASS |
| zen-gates rows | `94924` | `94924` | PASS |
| zen-gates bet_index | PRESENT | PRESENT | PASS |
| P183 classification | `P183_CONTROLLED_DB_MIGRATION_REHEARSAL_PLAN_READY` | same | PASS |
| P178A–P183 tests | PASS/SKIP | 361 passed, 5 skipped | PASS |
| drift guard | PASS | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | PASS |

---

## Part A — Temp Copy Creation

| Item | Value |
|------|-------|
| Source | `lottery_api/data/lottery_v2.db` |
| Target | `outputs/research/power_lotto/p184_rehearsal/lottery_v2_p184_temp_rehearsal_20260601.db` |
| Rows at copy | `54462` |
| Production DB write | **NONE** |
| Production DB rows after | `54462` (UNCHANGED) |

---

## Part B — Schema Rehearsal Results

### ⚠️ Critical Finding: Duplicate Rows Discovered

Before schema migration, a pre-check revealed **120 duplicate groups** (same `lottery_type, target_draw, strategy_id` in multiple replay runs):

| Category | Count |
|----------|-------|
| Duplicate groups | 120 (40 per lottery_type) |
| Groups with 2 rows | 80 |
| Groups with 3 rows | 40 |
| Total rows in dup groups | 280 |
| Rows to be dropped by dedup | **160** |
| Source of duplicates | Integer `replay_run_id` 1–7 (early test runs) |
| NULL-replay_run_id duplicates | **0** (none) |

All 160 dropped rows had `controlled_apply_id=NULL`, `provenance_hash=NULL`, `truth_level=NULL` — early test run artifacts with no production provenance. **Safe to deduplicate.**

### Dedup Strategy: `MAX(id)` per `(lottery_type, target_draw, strategy_id)`

Keeps the row with the highest `id` (latest insertion) per combination. All production-wave rows (p31b, p37, p43, p48, P59, P66) preserved; only integer-run duplicates removed.

### Schema Migration Steps — All PASS

| Step | Action | Result |
|------|--------|--------|
| 1 | Confirm initial temp state | 54462 rows, bet_index ABSENT |
| 2 | Duplicate pre-check | 120 groups found — dedup required |
| 3 | Create new table with bet_index + UNIQUE(…, bet_index) | SUCCESS |
| 4 | INSERT deduplicated rows (MAX(id) per group) | 54302 rows inserted |
| 5 | Verify count | 54302 ✅ |
| 6 | Duplicate check under new constraint | **0 duplicates** ✅ |
| 7 | DROP old table | SUCCESS |
| 8 | RENAME new table | SUCCESS |
| 9 | CREATE INDEX idx_spr_bet_index | SUCCESS |
| 10 | Verify bet_index present | PRESENT ✅ |
| 11 | PRAGMA integrity_check | **ok** ✅ |

---

## Critical Validation: Post-Dedup Exactly Matches Zen-Gates bet_index=1

| lottery_type | Temp (post-dedup) | Zen-gates bet_index=1 | Match |
|--------------|-------------------|----------------------|-------|
| BIG_LOTTO | 16,600 | 16,600 | ✅ EXACT |
| DAILY_539 | 22,600 | 22,600 | ✅ EXACT |
| POWER_LOTTO | 15,102 | 15,102 | ✅ EXACT |
| **TOTAL** | **54,302** | **54,302** | ✅ **EXACT** |

**The `MAX(id)` dedup strategy is validated as correct.** Post-dedup main DB rows EXACTLY match zen-gates `bet_index=1` rows at every lottery_type. The dedup discards nothing that zen-gates kept.

---

## Part C — Row Delta Audit

| Metric | Value |
|--------|-------|
| Main (original) | 54,462 rows |
| Main (post-dedup) | 54,302 rows |
| Dedup rows removed | 160 (no provenance — safe) |
| Zen-gates total | 94,924 rows |
| Multi-bet delta (to add) | **40,622** rows (bet_index 2–5) |
| Original stated delta | 40,462 (based on pre-dedup count) |

### Zen-Gates bet_index Distribution

| bet_index | Rows |
|-----------|------|
| 1 | 54,302 (= post-dedup main) |
| 2 | 16,581 |
| 3 | 15,041 |
| 4 | 6,000 |
| 5 | 3,000 |
| **Total** | **94,924** |

### Row Delta Attribution

| Category | Rows | Status |
|----------|------|--------|
| bet_index=1 base (post-dedup main) | 54,302 | VERIFIED — exact match |
| bet_index=2–5 (multi-bet to import) | 40,622 | REQUIRES_P185_ROW_DELTA_IMPORT_AUDIT |
| Exact wave attribution (P126/P130-P135/P149-P159B) | — | UNKNOWN — needs controlled_apply_id audit in P185 |

### Provenance Preservation

| Field | Prod count | Temp count | Match |
|-------|-----------|-----------|-------|
| controlled_apply_id NOT NULL | 54,002 | 54,002 | ✅ |
| provenance_hash NOT NULL | 54,000 | 54,000 | ✅ |
| truth_level NOT NULL | 54,002 | 54,002 | ✅ |

All provenance counts identical. The 160 dropped rows had NULL provenance — no provenance loss.

---

## Part D — Acceptance Criteria

| Criterion | Target | Result |
|-----------|--------|--------|
| Production DB unchanged | 54,462 rows | ✅ 54,462 |
| Production bet_index | ABSENT | ✅ ABSENT |
| Temp DB schema migration | PASS | ✅ PASS |
| Temp DB rows after migration | 54,302 | ✅ 54,302 |
| Temp DB bet_index present | YES | ✅ YES |
| UNIQUE constraint matches zen-gates | YES | ✅ YES |
| Duplicate check | 0 | ✅ 0 |
| Post-dedup matches zen-gates bet_index=1 | EXACT | ✅ EXACT |
| Row delta audit complete | YES | ✅ YES |
| Provenance preserved | YES | ✅ YES |
| No production DB write | 0 | ✅ 0 |
| No DB copy to production | YES | ✅ YES |
| No controlled_apply | YES | ✅ YES |
| No stage/commit/push | YES | ✅ YES |

**Open item**: `P185_ROW_DELTA_IMPORT_REHEARSAL_REQUIRED` — 40,622 multi-bet rows need import rehearsal.

---

## Part E — P185 Next Options

| Option | Phrase | Recommended |
|--------|--------|-------------|
| **A** | `YES start P185 row delta import rehearsal on temp copy only` | **YES** |
| B | `YES start P185 production DB migration authorization gate only` | No |
| C | `YES start P185 DB migration risk review only` | No |
| D | `YES start P185 maintain documented divergence and pause DB migration` | No |
| E | `YES start P185 replay product UI backlog implementation plan only` | No |

**P185 BLOCKED until CEO provides one of the above authorization phrases.**

---

## Part F — CTO Recommendation

**Primary**: `YES start P185 row delta import rehearsal on temp copy only`

P184 schema rehearsal PASSED. The `MAX(id)` dedup strategy is validated — post-dedup main EXACTLY matches zen-gates `bet_index=1`. The next step is rehearsing the import of 40,622 multi-bet rows (bet_index 2–5) from zen-gates into a temp copy, with controlled_apply_id audit.

**Do NOT:**
- Copy zen-gates DB file over main DB
- Perform production DB migration (schema or row import) until P185 rehearsal completes
- Run controlled_apply
- Reopen POWER_LOTTO research (P178A closure active)

**Production migration** sequence: P184 schema rehearsal PASS (done) → P185 row delta import rehearsal → P186+ production authorization gate → exact CEO phrase → execution.

---

## Governance Confirmations

| Item | Status |
|------|--------|
| Production main DB rows before/after | 54,462 / 54,462 |
| Production DB write | **0** |
| DB copy to production | **NONE** |
| controlled_apply | **NONE** |
| Registry mutation | **NONE** |
| merge/rebase/cherry-pick | **NONE** |
| stage/commit/push | **NONE** |
| POWER_LOTTO research | **CLOSED** (P178A active) |
| main/zen-gates split | **STILL UNRESOLVED** |
| P185 | **BLOCKED** — CEO auth required |

---

*P184 executed rehearsal on temp copy only. Production DB untouched. No wagering recommendations. No win outcome guaranteed.*
