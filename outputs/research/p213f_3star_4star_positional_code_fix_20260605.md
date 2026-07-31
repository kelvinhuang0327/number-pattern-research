# P213F 3_STAR / 4_STAR Positional Code Fix Implementation and Tests

**Date:** 2026-06-05
**Classification:** `P213F_3STAR_4STAR_POSITIONAL_CODE_FIX_COMPLETE`
**Task Type:** Type C (small additive implementation + tests) under P240D governance simplification rules
**Status:** Additive code fix + tests only — no production DB write, no schema change on production DB
**Authorization:** `Authorize P213F 3_STAR/4_STAR positional code fix implementation and tests (no production DB write)`

---

## 1. Scope and Non-Goals

### In Scope
- Additive code change to `lottery_api/database.py`
- New nullable `numbers_positional` column definition and migration
- Dual-write logic for permutation games in `insert_draws()`
- Targeted tests using in-memory / temp SQLite DB only

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Production DB write | Not authorized |
| Production schema migration | Not authorized (column is added at next `_init_database()` call for new installs; production DB unchanged until P213H) |
| `csv_validator.py` changes | Not authorized — file is already correct |
| Ingestion or re-ingestion | Not authorized |
| Registry mutation | Not authorized |
| Strategy work | Not authorized |
| Production/recommendation/monitoring change | Not authorized |
| Betting advice | Never authorized |

---

## 2. Implementation Summary

### 2.1 Change 1 — `numbers_positional` in CREATE TABLE

Added `numbers_positional TEXT DEFAULT NULL` to the `CREATE TABLE IF NOT EXISTS draws` definition. This ensures new installs automatically include the column.

### 2.2 Change 2 — Safe Migration for Existing Installs

Added a try/except `ALTER TABLE draws ADD COLUMN numbers_positional TEXT DEFAULT NULL` block after the existing `jackpot_amount` migration. This is the established pattern used for 5+ other columns in `database.py`. The try/except makes it idempotent — safe to run multiple times on any installation.

### 2.3 Change 3 — Dual-Write in `insert_draws()`

Added permutation detection and dual-write logic:
```python
lottery_type = draw.get('lotteryType', draw.get('lottery_type', ''))
if lottery_type in ('3_STAR', '4_STAR'):
    numbers_positional_json = json.dumps(numbers)
else:
    numbers_positional_json = None
```

- `numbers` field: always `json.dumps(sorted(numbers))` — unchanged for all types
- `numbers_positional` field: draw order for `3_STAR` / `4_STAR`; `NULL` for all other types

---

## 3. Modified File Summary

| File | Change Type | Lines Changed |
|---|---|---|
| `lottery_api/database.py` | Additive | +8 lines in schema definition, migration, and insert path |

No other files were modified.

---

## 4. Schema Behavior Summary

| Field | Semantics | All Types |
|---|---|---|
| `numbers` | Sorted JSON array — canonical, backward-compatible | Unchanged ✓ |
| `numbers_positional` | Original draw order for permutation games; NULL otherwise | New nullable column |

| Lottery Type | `numbers` | `numbers_positional` |
|---|---|---|
| `3_STAR` | sorted `[0,5,9]` | original `[9,0,5]` |
| `4_STAR` | sorted `[0,3,5,7]` | original `[7,0,5,3]` |
| `BIG_LOTTO` | sorted (unchanged) | `NULL` |
| `POWER_LOTTO` | sorted (unchanged) | `NULL` |
| `DAILY_539` | sorted (unchanged) | `NULL` |

---

## 5. Backward Compatibility Summary

- All existing consumers read `numbers` — semantics unchanged
- Adding a nullable column is non-destructive on SQLite
- `INSERT OR IGNORE` semantics unchanged — duplicate draws continue to be skipped
- All historical rows in production DB retain `NULL` in `numbers_positional` until a future re-ingestion task (P213H) is authorized
- Production DB file (`lottery_api/data/lottery_v2.db`) was **not written** during this task

---

## 6. Test Summary

**29 targeted tests — all PASS**

| Test Group | Count | What Is Verified |
|---|---|---|
| Schema (in-memory DB) | 3 | Column exists; nullable; migration idempotent |
| 3_STAR permutation storage | 4 | draw order preserved; sorted field unchanged |
| 4_STAR permutation storage | 3 | draw order preserved; sorted field unchanged |
| Non-permutation backward compatibility | 6 | BIG_LOTTO / POWER_LOTTO / DAILY_539 NULL + sorted unchanged |
| Duplicate insert guard | 1 | INSERT OR IGNORE semantics preserved |
| Read / query compatibility | 2 | SELECT on numbers still works |
| Production DB isolation | 2 | Production DB not opened; row count unchanged at 94,924 |
| Source code checks | 4 | `numbers_positional` present in CREATE TABLE, migration, INSERT; no registry/strategy changes |
| Artifact checks | 3 | JSON exists, MD exists, JSON parses with correct classification |

All tests use `:memory:` or `tmp_path` — production DB is never written.

---

## 7. Production DB Non-Write Attestation

- Production DB (`lottery_api/data/lottery_v2.db`) row count before: **94,924**
- Production DB row count after: **94,924**
- Production DB integrity: **ok**
- Drift guard: **REPLAY_LIFECYCLE_DRIFT_GUARD_PASS**

The `numbers_positional` column is NOT yet present in the production DB. It will only be added when `_init_database()` runs on a new install or when P213H explicitly authorizes production DB migration.

---

## 8. Remaining Limitations

| Limitation | Status |
|---|---|
| Existing historical rows remain unrecovered | Expected — 4,179 3_STAR and 2,922 4_STAR rows have `NULL` positional data until re-ingestion |
| Raw source files not in repo | Confirmed in P213C — external source re-download required |
| Production DB migration not yet applied | Requires P213H explicit authorization |
| Raw source format validation still required | P213G dry-run required before any historical positional data can be trusted |
| Permutation detection uses hardcoded types | `{'3_STAR', '4_STAR'}` — sufficient for current scope; expandable if needed |

---

## 9. Future Phases

| Phase | Description | Authorization Required |
|---|---|---|
| P213G | Dry-run source parser validation — re-obtain historical CSV/TXT, run parser, validate `開出順序` extraction, no production DB write | `"Authorize P213G 3_STAR/4_STAR historical draw re-download and dry-run source parser validation (no DB write to production)"` |
| P213H | Controlled production DB migration — confirmed backup, dry-run passed, rollback plan, apply schema migration + re-ingest historical draws with positional data | `"Authorize P213H 3_STAR/4_STAR controlled production DB migration (DB write authorized, backup confirmed, dry-run passed)"` |

---

## 10. Type C Same-PR Closeout Rationale

This task is **Type C** under P240D — small additive implementation + tests, governance changes ≤4 files, ≤120 lines. **No separate closeout PR is required.**

---

## 11. Safety / No-Claim Attestation

This implementation:
- Makes **no claim** about lottery number predictability
- Makes **no claim** about higher winning probability
- Provides **no wagering recommendation**
- Does not authorize any strategy, production, recommendation, monitoring, or DB change
- Does not write to the production DB
- 3_STAR/4_STAR remain `UNDERPOWERED_NO_SIGNAL` from P227C
- P238B remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`
