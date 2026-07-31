# P213D 3_STAR / 4_STAR Positional Schema and Code Fix Design

**Date:** 2026-06-05
**Classification:** `P213D_3STAR_4STAR_POSITIONAL_SCHEMA_CODE_FIX_DESIGN_COMPLETE`
**Task Type:** Type B (read-only design artifact) under P240D governance simplification rules
**Status:** Read-only design only — no code changes, no DB write, no schema change, no ingestion
**Authorization:** `Authorize P213D 3_STAR/4_STAR positional schema and code fix design (read-only design doc, no DB write)`

---

## 1. Scope and Non-Goals

### In Scope
- Design document for how positional order could be preserved in future ingestion and storage
- Analysis of current code paths causing order loss
- Evaluation of schema options
- Identification of authorization requirements for each future phase

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Code changes (any file) | Not authorized |
| DB write | Not authorized |
| Schema change | Not authorized |
| Ingestion or re-ingestion | Not authorized |
| Registry mutation | Not authorized |
| Live API calls | Not performed |
| Strategy promotion | Not authorized |
| Betting advice | Never authorized |
| Production/recommendation/monitoring change | Not authorized |

---

## 2. Current Root Cause

### 2.1 Code Path that Loses Positional Order

**Step 1 — CSV/TXT upload parses draw order correctly:**

`lottery_api/utils/csv_validator.py:286` and `:451–452`:
```python
is_permutation = getattr(rules, 'isPermutation', False)
final_numbers = numbers if is_permutation else sorted(numbers)
```
When `isPermutation=True` (as configured for 3_STAR and 4_STAR), the validator preserves the draw order from the raw source. The data enters the application layer with positional order intact.

**Step 2 — DB storage sorts unconditionally:**

`lottery_api/database.py:463`:
```python
numbers_json = json.dumps(sorted(numbers))
```
This runs for every lottery type, every draw, with no check for `isPermutation`. The positional information that was preserved by `csv_validator` is discarded here.

### 2.2 Why Existing DB Rows Cannot Recover Positional Order

- Current DB `draws.numbers` stores JSON arrays of sorted integers: e.g., `[5, 6, 9]`
- For a sorted array, there are `n!` possible original orderings (for 3_STAR: 6 possibilities, for 4_STAR: 24 possibilities)
- Without the raw source file, there is no way to determine which ordering was the actual draw order
- Original import CSV/TXT files are not present in the repo working tree (confirmed in P213C)
- Therefore, existing rows are not repairable from DB data alone; source files would need to be re-obtained

### 2.3 Confirmed Schema State

Current `draws` table columns (confirmed via `PRAGMA table_info`):
```
id | draw | date | lottery_type | numbers | special | created_at | jackpot_amount | sell_amount | total_amount
```
No `numbers_positional`, `draw_order`, or equivalent field exists.

---

## 3. Evidence Summary

| Evidence | Location | Confirms |
|---|---|---|
| `isPermutation: true` for 3_STAR and 4_STAR | `lottery_api/data/lottery_types.json:45,54` | Games explicitly flagged as permutation |
| `csv_validator.py` preserves permutation order | `lottery_api/utils/csv_validator.py:286,451–452` | Parser is already correct; no code change needed here |
| `database.py` sorts unconditionally | `lottery_api/database.py:463` | Single-line root cause |
| Raw TXT format includes `開出順序` | `lottery_api/tools/debug_validator.py` and `debug_comprehensive.py` | Source format has draw order; recovery from new source files is possible |
| Current DB rows are sorted | DB query: `SELECT numbers FROM draws WHERE lottery_type='3_STAR' LIMIT 10` → `[5, 6, 9]`, `[0, 6, 7]`, … | Existing rows cannot be corrected without raw source |
| No `numbers_positional` field in DB | `PRAGMA table_info(draws)` | Schema addition required for future positional storage |
| Original CSV/TXT files not in repo | P213C audit | External source re-download needed for recovery of historical draws |

---

## 4. Design Options

### Option A — Modify `draws.numbers` to not sort permutation games

**Description:** Change `database.py:463` to check `isPermutation` before sorting. For permutation games, store draw order in the existing `numbers` field.

```python
# Proposed change (do not implement in P213D)
lt_config = get_lottery_config(lottery_type)  # hypothetical
is_perm = lt_config.get('isPermutation', False)
numbers_json = json.dumps(numbers if is_perm else sorted(numbers))
```

| Dimension | Assessment |
|---|---|
| **Backward compatibility** | BREAKING — all existing consumers that expect `numbers` to be sorted for permutation games would break |
| **Code change scope** | 1 line in `database.py` + config lookup; low change volume |
| **Migration impact** | Existing 4,179 3_STAR and 2,922 4_STAR rows remain sorted; new rows would use draw order; creates mixed semantics in same column |
| **Legacy code risk** | Many scripts call `sorted(numbers)` explicitly (they re-sort), meaning they would still produce consistent results — but any code doing set comparison or equality check against stored values would break for new rows |
| **Test needs** | Must verify non-permutation games are unaffected; must verify existing sorted-row consumers handle mixed state |
| **Recommendation** | Not recommended as standalone fix; creates ambiguous column semantics |

### Option B — Add separate `numbers_positional` column for permutation games

**Description:** Add a nullable `numbers_positional TEXT` column to `draws`. For non-permutation games, it stays NULL. For permutation games, store draw order in `numbers_positional`; keep sorted order in existing `numbers`.

```sql
-- Schema migration (do not execute in P213D)
ALTER TABLE draws ADD COLUMN numbers_positional TEXT DEFAULT NULL;
```

At insert time for permutation games:
```python
# Proposed logic (do not implement in P213D)
numbers_json = json.dumps(sorted(numbers))  # existing field unchanged
positional_json = json.dumps(numbers) if is_permutation else None
```

| Dimension | Assessment |
|---|---|
| **Backward compatibility** | SAFE — existing `numbers` field semantics unchanged; all existing consumers unaffected |
| **Code change scope** | `database.py:463` area + `insert_draws` SQL + schema migration; moderate scope |
| **Migration impact** | Schema migration (ADD COLUMN) is non-destructive; existing rows get `NULL` for `numbers_positional` |
| **Legacy code risk** | Near-zero; new column is additive and optional |
| **Historical rows** | Remain NULL in `numbers_positional`; would require re-ingestion from source to populate |
| **Test needs** | New insert path; verify permutation rows get correct positional value; verify non-permutation rows get NULL |
| **Recommendation** | Safest additive option; cleanest separation of concerns |

### Option C — Dual-write canonical sorted numbers plus original positional sequence

**Description:** Combines Option B structure with explicit design to dual-write both orderings for all permutation game rows. `numbers` always stores sorted order (canonical for matching/analysis). `numbers_positional` always stores draw order for permutation games.

This is conceptually identical to Option B with a clear policy: **every new permutation-game insert must provide both fields**. Enforced via a NOT NULL constraint on `numbers_positional` for permutation game types (requires CHECK constraint or application-level enforcement).

| Dimension | Assessment |
|---|---|
| **Backward compatibility** | SAFE — same as Option B |
| **Strict enforcement** | Higher — cannot accidentally skip positional storage for new rows if constraint is added |
| **Complexity** | Slightly higher than B due to constraint design |
| **Historical rows** | Same as Option B — remain NULL until re-ingested from source |
| **Recommendation** | Best long-term design; same near-term implementation effort as Option B |

### Option D — No change / HOLD

**Description:** Keep current behavior. `numbers` stores sorted arrays. No positional field added. Straight-play research remains blocked.

| Dimension | Assessment |
|---|---|
| **Risk** | None — zero change |
| **Benefit** | None — positional data remains unavailable |
| **When appropriate** | If straight-play research is not a priority, or if source files cannot be obtained |
| **Recommendation** | Appropriate as default until user explicitly authorizes implementation |

---

## 5. Recommended Option

**Recommended: Option C (dual-write, additive `numbers_positional` column)**

**Rationale:**
- Preserves backward compatibility: existing `numbers` semantics unchanged for all lottery types
- Additive schema change (ADD COLUMN) is non-destructive and reversible
- Explicit dual-write policy prevents future ambiguity about which field to use for which purpose
- `csv_validator` is already correct; only `database.py` needs modification
- Schema migration is simple (one ALTER TABLE statement)
- No existing consumers break

**This is a design recommendation only. Implementation requires separate authorization (P213E or equivalent).**

---

## 6. Future Implementation Plan

### Phase 1 — P213D (this task, complete)
- Read-only design doc
- No code changes
- No DB changes

### Phase 2 — P213E: Additive code fix design review (no DB write)
- Detailed implementation spec for Option C
- Proposed diff for `database.py` (review-only, not applied)
- Proposed `ALTER TABLE` migration statement (review-only)
- Proposed insert-path test stubs
- **Authorization required:** `"Authorize P213E 3_STAR/4_STAR positional schema implementation design review (read-only, no DB write)"`

### Phase 3 — P213F: Additive code implementation + tests (no DB write to production)
- Apply `database.py` change
- Apply schema migration to a test/staging DB only
- Add insert-path tests
- Validate non-permutation games are unaffected
- **Authorization required:** `"Authorize P213F 3_STAR/4_STAR positional code fix implementation and tests (no production DB write)"`

### Phase 4 — P213G: Dry-run source parser validation (no DB write to production)
- Re-obtain historical 3_STAR/4_STAR CSV/TXT source files
- Run dry-run parser to verify `開出順序` extraction
- Validate sample draws match known results
- Count rows before and after dry run
- **Authorization required:** `"Authorize P213G 3_STAR/4_STAR historical draw re-download and dry-run source parser validation (no DB write to production)"`

### Phase 5 — P213H: Controlled production DB migration (explicit DB write)
- Confirmed backup
- Dry-run passed
- Rollback plan in place
- Apply schema migration to production DB
- Re-ingest historical draws with positional data
- Verify counts and integrity before/after
- **Authorization required:** `"Authorize P213H 3_STAR/4_STAR controlled production DB migration (DB write authorized, backup confirmed, dry-run passed)"`

### Pre-conditions for any implementation phase
- DB backup confirmed before any schema/data change
- All non-permutation games remain unaffected (test coverage required)
- `strategy_prediction_replays` rows remain at 94,924 before and after
- Drift guard passes before and after
- Integrity check passes before and after

---

## 7. Future Authorization Phrases

| Step | Authorization Phrase |
|---|---|
| P213E implementation design review (no code) | `"Authorize P213E 3_STAR/4_STAR positional schema implementation design review (read-only, no DB write)"` |
| P213F additive code fix + tests (no production DB write) | `"Authorize P213F 3_STAR/4_STAR positional code fix implementation and tests (no production DB write)"` |
| P213G dry-run source parser validation (no production DB write) | `"Authorize P213G 3_STAR/4_STAR historical draw re-download and dry-run source parser validation (no DB write to production)"` |
| P213H controlled production DB migration (DB write) | `"Authorize P213H 3_STAR/4_STAR controlled production DB migration (DB write authorized, backup confirmed, dry-run passed)"` |
| HOLD / no action | *(none needed)* |

---

## 8. Risks and Mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Breaking non-permutation games | High | Option C uses existing `numbers` semantics unchanged; only additive new column for permutation games |
| Changing semantics of `draws.numbers` | High | Option C avoids this entirely; sorted `numbers` remains canonical for all games |
| Legacy code expecting sorted arrays | Medium | Most legacy code calls `sorted(numbers)` explicitly; additive column does not affect them |
| Mixed state in `numbers_positional` column (NULLs for historical rows) | Medium | Expected and documented; historical rows remain NULL until re-ingested from source |
| Current rows unrecoverable without raw source | High | Must be explicit in all documentation; no false recovery claim |
| Accidental DB write during design phases | High | Strict phase gate; no DB write until P213H with explicit authorization |
| Source files unavailable or format mismatch | Medium | P213G dry-run validation required before P213H; no production write until validated |
| Strategy overclaiming on positional data | High | 3_STAR/4_STAR remain UNDERPOWERED_NO_SIGNAL (P227C); positional fix does not create a strategy signal |

---

## 9. Safety / No-Claim Attestation

This design document:
- Makes **no claim** about lottery number predictability
- Makes **no claim** about higher winning probability
- Provides **no wagering recommendation**
- Does not authorize any strategy, production, recommendation, monitoring, or DB change
- Does not restart P211
- 3_STAR/4_STAR remain `UNDERPOWERED_NO_SIGNAL` from P227C; positional schema fix does not change this status
- P238B remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`

Safety boolean attestation:
- `no_code_changes = true`
- `no_db_write = true`
- `no_schema_change = true`
- `no_ingestion = true`
- `no_registry_mutation = true`
- `no_production_change = true`
- `no_monitoring_change = true`
- `no_strategy_authorization = true`
- `no_betting_advice = true`

---

## 10. Type B Same-PR Closeout Rationale

This task is **Type B** under P240D — Markdown and JSON artifacts only, no code changes, governance changes ≤4 files, ≤120 lines. **No separate closeout PR is required.**
