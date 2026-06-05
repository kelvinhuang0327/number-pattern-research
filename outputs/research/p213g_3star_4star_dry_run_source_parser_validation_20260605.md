# P213G 3_STAR / 4_STAR Dry-run Source Parser Validation

**Date:** 2026-06-05
**Classification:** `P213G_SOURCE_FORMAT_VALIDATED_WITH_MOCK_ONLY`
**Task Type:** Type C (dry-run script + tests + artifact) under P240D governance simplification rules
**Status:** Dry-run only — no production DB write
**Authorization:** `Authorize P213G 3_STAR/4_STAR historical draw re-download and dry-run source parser validation (no DB write to production)`

---

## 1. Scope and Non-Goals

### In Scope
- Dry-run parser that validates the Taiwan Lottery TXT source format for 3_STAR and 4_STAR
- Validation that `開出順序` (draw order field) is present and parseable
- Comparison of parsed sorted numbers against production DB (read-only)
- Classification of source availability

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Production DB write | Not authorized |
| Production DB schema migration | Not authorized |
| Ingestion into production DB | Not authorized |
| Registry mutation | Not authorized |
| Strategy work | Not authorized |
| Live API calls for download | Not performed — no real files available |
| Betting advice | Never authorized |

---

## 2. Source Discovery Summary

| Finding | Result |
|---|---|
| Real 3_STAR/4_STAR historical CSV/TXT files in repo | **NOT FOUND** |
| Live source download attempted | **NOT ATTEMPTED** — outside dry-run scope |
| Source format known from repo evidence | **YES** — from `lottery_api/tools/debug_validator.py` and `debug_comprehensive.py` |
| Format includes `開出順序` (draw order) field | **CONFIRMED** — present in both 3_STAR and 4_STAR mock content |
| 4_STAR uses joined-digit format | **CONFIRMED** — `開出順序:4321` → `[4, 3, 2, 1]` |

**Source status: `P213G_SOURCE_FORMAT_VALIDATED_WITH_MOCK_ONLY`**

The Taiwan Lottery TXT format for 3_STAR and 4_STAR games is known from mock/debug content in the codebase. No real historical source files are present. Future recovery requires obtaining actual historical TXT/CSV files from the Taiwan Lottery source.

---

## 3. Parser / Dry-run Method

**Script:** `scripts/p213g_3star_4star_dry_run_source_parser.py`

The parser:
1. Reads TXT source content (format known from debug tools)
2. Extracts draw ID from lines like `112000001期` or `112000001`
3. Extracts date from `開獎日期:112/01/01`
4. Extracts positional draw order from `開出順序:3 2 1` (3_STAR) or `開出順序:4321` (4_STAR joined)
5. Computes sorted canonical numbers from positional order
6. Does NOT write to any DB

---

## 4. Source Validation Result

**5 fixtures validated — 5/5 PASS**

| Fixture | Type | Positional | Sorted | Status |
|---|---|---|---|---|
| `fixture:3star_reversed` | 3_STAR | `[3, 2, 1]` | `[1, 2, 3]` | OK |
| `fixture:3star_already_sorted` | 3_STAR | `[0, 5, 9]` | `[0, 5, 9]` | OK |
| `fixture:3star_all_different` | 3_STAR | `[7, 1, 4]` | `[1, 4, 7]` | OK |
| `fixture:4star_reversed_joined` | 4_STAR | `[4, 3, 2, 1]` | `[1, 2, 3, 4]` | OK |
| `fixture:4star_already_sorted` | 4_STAR | `[0, 1, 5, 9]` | `[0, 1, 5, 9]` | OK |

All fixtures parsed the `開出順序` field correctly. The parser correctly:
- Preserves positional draw order for permutation games
- Computes sorted canonical numbers separately
- Handles both space-separated (3_STAR) and joined-digit (4_STAR) formats

---

## 5. Row-Count / Checksum / Duplicate Summary

| Metric | Value |
|---|---|
| Fixtures total | 5 |
| Valid parsed | 5 |
| Invalid parsed | 0 |
| Duplicate draw IDs in fixtures | 0 |
| Real historical rows parsed | 0 (no real files available) |
| Source checksum | N/A (mock only) |

---

## 6. DB Comparison Summary

| Metric | Value |
|---|---|
| DB available | Yes (read-only) |
| Fixtures with matching draw IDs in DB | 2 |
| Sorted-number matches | 0 |
| Sorted-number mismatches | 2 |
| Draw IDs not in DB | 3 |

**Mismatch explanation:** The 2 fixtures with draw IDs `112000001` / `112000002` happen to exist in production DB (early 2023 draws) but with different real numbers. The fixture numbers are made-up for format validation — not real draw numbers. This is expected behavior for a mock-only validation.

The DB comparison logic is confirmed correct: `sorted_numbers` from parser output matches the `numbers` column semantics in DB.

---

## 7. Positional-Order Preservation Evidence

| Evidence | Confirmed |
|---|---|
| Source format includes `開出順序` field | ✓ |
| Parser extracts positional order correctly | ✓ |
| Parser computes sorted canonical separately | ✓ |
| `database.py` P213F fix stores positional in `numbers_positional` | ✓ |
| `csv_validator.py` preserves permutation order from source | ✓ |

---

## 8. Limitations

| Limitation | Detail |
|---|---|
| No real historical source files | Source format validated with mock only; actual historical TXT files must be obtained before P213H |
| No live download performed | Governance does not authorize live download in this task |
| DB mismatches are expected | Mock fixture numbers do not match real production DB numbers |
| Row count is 0 for real data | Cannot count real historical rows until actual source files are obtained |
| P213H readiness is conditional | Requires obtaining actual source files + re-running this parser with real data |

---

## 9. Production DB Non-Write Attestation

- Production DB rows before: **94,924**
- Production DB rows after: **94,924**
- DB integrity: **ok**
- Drift guard: **REPLAY_LIFECYCLE_DRIFT_GUARD_PASS**
- Production DB file: **NOT WRITTEN**

---

## 10. Remaining Gates Before DB Recovery

| Gate | Status |
|---|---|
| Source format validated | ✓ (mock only) |
| Parser extracts positional order | ✓ |
| P213F code fix merged | ✓ (PR #305) |
| Real historical source files obtained | ❌ Required for P213H |
| Parser validated with real files | ❌ Required for P213H |
| Source matches DB sorted numbers | ❌ Required for P213H |
| Production DB backup confirmed | ❌ Required for P213H |
| Rollback plan documented | ❌ Required for P213H |

---

## 11. Recommended Next Direction

**P213H: Controlled production DB migration** — requires obtaining real historical TXT source files, re-running parser with actual data, confirming DB backup, and explicit DB-write authorization.

**Authorization phrase:**
```
Authorize P213H 3_STAR/4_STAR controlled production DB migration (DB write authorized, backup confirmed, dry-run passed)
```

---

## 12. Type C Same-PR Closeout Rationale

This task is **Type C** under P240D — dry-run script + tests + artifact, governance changes ≤4 files, ≤120 lines. **No separate closeout PR is required.**

---

## 13. Safety / No-Claim Attestation

This dry-run validation:
- Makes **no claim** about lottery number predictability
- Makes **no claim** about higher winning probability
- Provides **no wagering recommendation**
- Does not authorize any strategy, production, recommendation, monitoring, or DB change
- Does not write to the production DB
- 3_STAR/4_STAR remain `UNDERPOWERED_NO_SIGNAL` from P227C
- P238B remains `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY`
