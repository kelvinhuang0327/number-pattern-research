# P213E 3_STAR / 4_STAR Positional Schema Implementation Design Review

**Date:** 2026-06-05
**Classification:** `P213E_3STAR_4STAR_POSITIONAL_SCHEMA_IMPLEMENTATION_DESIGN_REVIEW_COMPLETE`
**Task Type:** Type B (read-only implementation design review) under P240D governance simplification rules
**Status:** Read-only design review only — no code changes, no DB write, no schema change, no migration, no ingestion
**Authorization:** `Authorize P213E 3_STAR/4_STAR positional schema implementation design review (read-only, no DB write)`

---

## 1. Scope and Non-Goals

### In Scope
- Review of exact code touchpoints P213F would need to modify
- Test plan for permutation-order storage behavior
- Schema semantics definition for `numbers` and `numbers_positional`
- Backward-compatibility requirements
- Migration boundaries
- Authorization requirements for each future phase

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Code changes (any file) | Not authorized |
| DB write | Not authorized |
| Schema change | Not authorized |
| Migration files | Not authorized |
| Ingestion or re-ingestion | Not authorized |
| Registry mutation | Not authorized |
| Live API calls | Not performed |
| Strategy promotion | Not authorized |
| Betting advice | Never authorized |
| Production/recommendation/monitoring change | Not authorized |

---

## 2. P213D Decision Recap

P213D concluded:

| Finding | Detail |
|---|---|
| Root cause | `lottery_api/database.py:463` — `json.dumps(sorted(numbers))` sorts unconditionally |
| Existing validator | `lottery_api/utils/csv_validator.py:286,451-452` already preserves draw order for `isPermutation=True` games |
| Recommended option | **Option C** — dual-write additive `numbers_positional` column |
| `numbers` semantics | Keep sorted canonical arrays; unchanged for all game types |
| `numbers_positional` | New nullable column; draw order for permutation games only |
| Historical rows | Cannot recover from DB alone; original CSV/TXT files not in repo |
| Future recovery | Requires re-obtaining source files + explicit DB-write authorization (P213G/P213H) |

---

## 3. Candidate Implementation Touchpoints

### 3.1 DB Schema Definition

**File:** `lottery_api/database.py`
**Location:** `_init_database()` method, `CREATE TABLE IF NOT EXISTS draws` block (line ~70)

Current schema includes no `numbers_positional` column. P213F would need to:
1. Add `numbers_positional TEXT DEFAULT NULL` to the `CREATE TABLE` statement (for new installations)
2. Add a try/except `ALTER TABLE draws ADD COLUMN numbers_positional TEXT DEFAULT NULL` migration block (for existing installations)

The existing migration pattern is well-established in the same file (see lines 83–206: multiple `ALTER TABLE X ADD COLUMN Y DEFAULT NULL` blocks, each wrapped in try/except). This pattern is safe, non-destructive, and idempotent.

### 3.2 Draw Insert / Storage Path

**File:** `lottery_api/database.py`
**Location:** `insert_draws()` method, specifically line 463 and the INSERT SQL at line 512

Current code:
```python
# line 453-463 (abbreviated)
numbers = draw.get('numbers', [])
if isinstance(numbers, str):
    parsed = json.loads(numbers)
    if isinstance(parsed, list):
        numbers = parsed
numbers_json = json.dumps(sorted(numbers))  # <-- always sorts
```

P213F would need to:
1. Detect whether the incoming `draw` has permutation game context (via `lottery_type` + `lottery_types.json`)
2. Preserve original ordering in `numbers_positional_json` for permutation games
3. Always store `sorted(numbers)` in `numbers_json` (no change to existing field)
4. Extend the INSERT SQL to include `numbers_positional`

The key challenge is that `insert_draws()` receives a list of draw dicts. It must look up whether the `lottery_type` is a permutation game. The `lottery_types.json` config or `LotteryConfig` must be accessible at insert time.

**Permutation lookup:** `lottery_api/data/lottery_types.json` defines `"isPermutation": true` for `3_STAR` and `4_STAR`. The config is loaded via `lottery_api/config.py` (`LotteryConfig` dataclass with `isPermutation: bool = False`). P213F must not modify the config structure.

### 3.3 CSV / Source Validation Path

**File:** `lottery_api/utils/csv_validator.py`
**Location:** Lines 286 and 451–452

This file already correctly sets `final_numbers = numbers if is_permutation else sorted(numbers)`. No change is needed in `csv_validator.py`. The draw dict that arrives at `insert_draws()` may have `numbers` already in draw order (if the source was a permutation-game CSV). P213F must not modify `csv_validator.py`.

### 3.4 Read APIs and Internal Readers

**File:** `lottery_api/database.py`
**Methods:** `get_draws()` (~line 531), and several other read methods (lines ~591, ~658, ~858, ~927)

All read paths use `json.loads(row['numbers'])` and return sorted arrays. These do not need to change for P213F. They should remain unchanged. Any future consumer of `numbers_positional` is out of scope for P213F.

**Note:** No existing code reads `numbers_positional` because it does not exist. No existing tests assume its absence or presence.

### 3.5 Tests

**Existing tests:** No tests currently test the permutation-order behavior of `insert_draws()`. Tests for DB insert behavior are sparse. `tests/test_p227b_star_box_play_semantics.py` tests box-play matching semantics but not storage.

P213F must add new targeted tests before or alongside the code change. Tests must use a temporary in-memory SQLite DB and must not touch the production DB.

### 3.6 Migration Script

No migration script currently exists for `draws` table column additions. The existing pattern (`ALTER TABLE ... ADD COLUMN ... DEFAULT NULL` inside try/except) is applied inline in `_init_database()`. P213F should follow this same pattern — no separate migration file needed.

---

## 4. Proposed P213F Code-Change Scope

### 4.1 Files Likely Modified

| File | Change Type | Description |
|---|---|---|
| `lottery_api/database.py` | Additive | Add `numbers_positional` column to CREATE TABLE; add try/except migration; modify `insert_draws()` to dual-write |

**No other source files should need modification for P213F.** `csv_validator.py`, `config.py`, `lottery_types.json`, and all read paths are unchanged.

### 4.2 Exact Behavior Changes

1. **New installs:** `draws` table is created with `numbers_positional TEXT DEFAULT NULL`
2. **Existing installs:** try/except migration adds `numbers_positional` safely
3. **Insert path:** For permutation games (`3_STAR`, `4_STAR`), `numbers_positional` receives `json.dumps(numbers)` (original draw order). For non-permutation games, `numbers_positional` receives `NULL`.
4. **Existing `numbers` field:** Unchanged — always receives `json.dumps(sorted(numbers))`
5. **All read paths:** Unchanged — continue to return sorted `numbers`

### 4.3 Non-Permutation Game Guarantee

Non-permutation games (`BIG_LOTTO`, `POWER_LOTTO`, `DAILY_539`) must be completely unaffected:
- `numbers` continues to store sorted arrays (no change)
- `numbers_positional` is `NULL` for all non-permutation rows
- No existing query, analysis, or strategy code is touched

### 4.4 Permutation Order Preservation Guarantee

For new inserts of `3_STAR` and `4_STAR` draws:
- The original number order from `csv_validator` is preserved in `numbers_positional`
- `numbers` continues to store the sorted version for backward compatibility

### 4.5 No Production DB Write Guarantee for P213F

P213F covers test/staging DB only:
- All tests use in-memory or temporary SQLite DB
- Production DB (`lottery_api/data/lottery_v2.db`) is not touched
- The schema migration in `_init_database()` would only affect the production DB when P213H explicitly authorizes it

---

## 5. Schema Semantics

| Field | Type | Value | Change |
|---|---|---|---|
| `numbers` | `TEXT NOT NULL` | JSON array of sorted integers (canonical) | **Unchanged** — sorted for all game types, new and historical |
| `numbers_positional` | `TEXT DEFAULT NULL` | JSON array in original draw order, for permutation games only | **New nullable column** |

### Semantics Rules

1. `numbers` is always sorted — it is the canonical field for all matching, analysis, and strategy code
2. `numbers_positional` is draw order for permutation games (`3_STAR`, `4_STAR`) only
3. `numbers_positional` is `NULL` for non-permutation games (`BIG_LOTTO`, `POWER_LOTTO`, `DAILY_539`)
4. `numbers_positional` is `NULL` for all existing historical rows until a re-ingestion is authorized (P213H)
5. No strategy should consume `numbers_positional` until separately authorized — it is infrastructure only at this stage
6. `numbers_positional IS NULL` does not mean the draw is invalid; it means positional data is not yet available for that row

---

## 6. Test Plan for P213F

### 6.1 Unit Tests — Permutation Storage Semantics

| Test | Purpose |
|---|---|
| `test_insert_3star_stores_positional_order` | Insert a 3_STAR draw with known order `[3,2,1]`; assert `numbers_positional = '[3, 2, 1]'` |
| `test_insert_3star_stores_sorted_numbers` | Same row; assert `numbers = '[1, 2, 3]'` |
| `test_insert_4star_stores_positional_order` | Same pattern for 4_STAR with order `[4,3,2,1]` |
| `test_insert_4star_stores_sorted_numbers` | Same row; assert `numbers = '[1, 2, 3, 4]'` |
| `test_duplicate_insert_ignored` | INSERT OR IGNORE — re-inserting same draw does not overwrite |

### 6.2 Unit Tests — Non-Permutation Backward Compatibility

| Test | Purpose |
|---|---|
| `test_insert_biglotto_numbers_positional_is_null` | Insert a BIG_LOTTO draw; assert `numbers_positional IS NULL` |
| `test_insert_power_lotto_numbers_positional_is_null` | Insert a POWER_LOTTO draw; assert `numbers_positional IS NULL` |
| `test_insert_daily_539_numbers_positional_is_null` | Insert a DAILY_539 draw; assert `numbers_positional IS NULL` |
| `test_existing_numbers_field_unchanged_for_all_types` | For all types, `numbers` remains sorted |

### 6.3 DB Schema Tests (Temp In-Memory DB Only)

| Test | Purpose |
|---|---|
| `test_draws_table_has_numbers_positional_column` | After `_init_database()`, `PRAGMA table_info(draws)` includes `numbers_positional` |
| `test_numbers_positional_is_nullable` | Column allows NULL without constraint violation |
| `test_migration_is_idempotent` | Calling `_init_database()` twice does not fail |

### 6.4 Integration Tests (Fixture / Mock Source)

| Test | Purpose |
|---|---|
| `test_csv_validator_to_db_round_trip_preserves_order` | Mock 3_STAR CSV row with `開出順序:3 2 1` → through csv_validator → insert → verify `numbers_positional = '[3, 2, 1]'` |
| `test_csv_validator_output_order_matches_db_positional` | For permutation games, csv_validator `final_numbers` equals DB `numbers_positional` |

### 6.5 Safety Tests

| Test | Purpose |
|---|---|
| `test_no_production_db_accessed` | All test DB operations use `:memory:` or a temp file path, not `lottery_api/data/lottery_v2.db` |
| `test_no_registry_mutation` | No strategy registry is read or written |
| `test_strategy_prediction_replays_not_touched` | `strategy_prediction_replays` table row count unchanged |

---

## 7. Migration and Recovery Boundaries

| Phase | Migration Type | DB Write | Authorization Required |
|---|---|---|---|
| P213E (this task) | None — design only | No | ✓ (current task) |
| P213F | Schema migration to test/staging DB only | No (production) | `"Authorize P213F 3_STAR/4_STAR positional code fix implementation and tests (no production DB write)"` |
| P213G | Source validation dry-run, no DB write | No | `"Authorize P213G 3_STAR/4_STAR historical draw re-download and dry-run source parser validation (no DB write to production)"` |
| P213H | Production schema migration + re-ingestion | **Yes** | `"Authorize P213H 3_STAR/4_STAR controlled production DB migration (DB write authorized, backup confirmed, dry-run passed)"` |

### P213H Pre-conditions (for future reference, not authorized yet)

Before any production DB write:
- Production DB backup confirmed and tested
- Rollback plan documented
- P213F tests pass on temp DB
- P213G dry-run parser validates `開出順序` extraction from actual source files
- Row count before/after verified
- Drift guard passes before and after
- Integrity check passes before and after
- `strategy_prediction_replays` row count unchanged (94,924)

---

## 8. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Breaking existing sorted assumptions in `numbers` | High | Option C never changes `numbers` semantics; sorted array is always written |
| `numbers_positional` confusion — consumers using wrong field | Medium | Clear semantics documented; `numbers` remains canonical; `numbers_positional` is infrastructure-only until separately authorized |
| Stale historical rows with NULL positional field | Medium | Expected and documented; NULL means "not yet available", not invalid |
| Source order ambiguity — real source format may differ from mock | Medium | P213G dry-run required to validate actual source format before P213H |
| Accidental production DB write during P213F | High | All P213F tests must use `:memory:` or temp path; production DB path forbidden in tests |
| Strategy overclaiming — using positional field for predictions | High | 3_STAR/4_STAR remain UNDERPOWERED_NO_SIGNAL (P227C); `numbers_positional` must not be used for strategy until separately authorized |
| Permutation detection failure — lottery_type not reliably checked | Medium | Use `lottery_types.json` config lookup; test all permutation/non-permutation cases explicitly |
| Migration failure on existing installs | Low | try/except pattern already used for 5+ columns in same codebase; safe and idempotent |

---

## 9. Recommended Next Step

**Recommended next direction: P213F — Additive positional storage code fix (test/staging DB only, no production DB write)**

P213E confirms:
1. Exactly one file needs modification (`database.py`)
2. The migration pattern is established and safe
3. `csv_validator.py` needs no changes
4. The test plan is fully specified (17 tests)
5. Non-permutation games are provably unaffected
6. No production DB write is needed in P213F

**Authorization phrase:**
```
Authorize P213F 3_STAR/4_STAR positional code fix implementation and tests (no production DB write)
```

---

## 10. Safety / No-Claim Attestation

This implementation design review:
- Makes **no claim** about lottery number predictability
- Makes **no claim** about higher winning probability
- Provides **no wagering recommendation**
- Does not authorize any strategy, production, recommendation, monitoring, or DB change
- Does not restart P211
- 3_STAR/4_STAR remain `UNDERPOWERED_NO_SIGNAL` from P227C
- P238B remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`

Safety boolean attestation:
- `no_code_changes = true`
- `no_db_write = true`
- `no_schema_change = true`
- `no_ingestion = true`
- `no_migration = true`
- `no_registry_mutation = true`
- `no_production_change = true`
- `no_monitoring_change = true`
- `no_strategy_authorization = true`
- `no_betting_advice = true`

---

## 11. Type B Same-PR Closeout Rationale

This task is **Type B** under P240D — Markdown and JSON artifacts only, no code changes, governance changes ≤4 files, ≤120 lines. **No separate closeout PR is required.**
