# P246I — BIG_LOTTO Population Assertion Cleanup

**Task ID:** P246I · **Date:** 2026-06-05 · **Type:** Test/artifact comment cleanup (no DB write).
**Final Classification:** `P246I_BIG_LOTTO_POPULATION_ASSERTION_CLEANUP_COMPLETE`

---

## 1. Executive Summary

Tests and artifacts that implied raw BIG_LOTTO total (22,238) is the canonical research sample now have explicit inline comments distinguishing the two populations. No assertion values were changed. Historical artifacts are preserved.

---

## 2. Raw vs Canonical BIG_LOTTO Population Definitions

| Population | Count | Description | Appropriate for |
|---|---|---|---|
| **raw_total** | **22,238** | All BIG_LOTTO rows in DB | Raw display, DB integrity checks |
| **canonical_research** | **~2,113** | 6/49 main draws only (get_canonical_draws) | Strategy, NIST audit, backtest, PSI |
| **add_on_excluded** | **19,100** | Add-on/special prize records (valid, preserved) | Display with labeling, history |
| date_format_alien | 375 | Non-canonical (numbers not 6/49) | Non-canonical concern |
| small_pool_alien | ~650 | Likely mislabeled game (max≤25) | Non-canonical concern |

**ADD_ON_PRIZE_EXCLUDED rows are valid lottery-related records.** They are excluded from canonical research due to population mismatch, NOT data falseness.

---

## 3. Tests/Artifacts Updated

### `tests/test_p238b_nist_randomness_audit_artifact_build.py:146` — comment added

**Before:**
```python
assert active["BIG_LOTTO"] >= 22238
```

**After:**
```python
# P246I NOTE: BIG_LOTTO raw total = 22,238 (includes 19,100 ADD_ON_PRIZE_EXCLUDED add-on/special
# prize records). These are valid lottery-related records preserved in the DB. They are excluded
# from canonical 6/49 main-draw research (canonical count ~2,113) by get_canonical_draws().
# The P238B NIST audit ran on all raw rows (mixed population). A canonical-only re-audit is
# recommended after P247 Type D segregation. This assertion tests raw DB row count, NOT the
# canonical research population. See P246B/P246C/P246I for taxonomy and isolation details.
assert active["BIG_LOTTO"] >= 22238  # raw total (including add-on rows); canonical ~2,113
```

Assertion value **unchanged** — still tests raw DB row count (correct for current state).

### `tests/test_p243a_diagnostic_report_fixture_pack.py:58` — comment added

**Before:**
```python
sample_size=22238,
```

**After:**
```python
# P246I NOTE: sample_size=22238 = all BIG_LOTTO rows at P238B run time (2026-06-04),
# including 19,100 ADD_ON_PRIZE_EXCLUDED add-on/special prize records (valid but
# excluded from canonical 6/49 research). Canonical research population ~2,113.
# This fixture preserves the historical P238B state. Do not change the value;
# a canonical-population re-run requires separate authorization. See P246I.
sample_size=22238,  # historical: raw total (add-on-inclusive); canonical ~2,113
```

Fixture value **unchanged** — historical evidence preserved.

---

## 4. Historical Artifacts Left Unchanged

### `outputs/research/p238b_nist_randomness_audit_artifact_20260604.*`

The P238B NIST audit artifact was generated from all 22,238 BIG_LOTTO rows (mixed population). Classification `RANDOMNESS_AUDIT_YELLOW_OBSERVATION_ONLY` remains valid as a historical record of the raw-population audit.

**Not changed because:** The artifact is a historical scientific result. Changing it without re-running the audit would be misleading. A canonical-only re-audit (~2,113 rows) requires separate authorization after P247 Type D segregation.

**Superseding note (additive, recorded here):** P238B NIST result reflects the mixed BIG_LOTTO population (22,238 rows). After P247 Type D, the canonical 6/49 main-draw population (~2,113 rows) should be audited separately.

---

## 5. Updated Assertion Policy

| Scenario | Assertion |
|---|---|
| Testing raw DB row count | `>= 22238` with P246I comment distinguishing raw vs canonical |
| Testing canonical research count | `>= 2100 and <= 2200` (or `== 2113` after verification) |
| Historical fixture | Preserve value; add comment; note in P246I superseding record |
| P238B NIST re-run | Requires separate authorization; not in scope here |

---

## 6. Whether P238B/P243A Need Future Canonical Re-run

**P238B NIST:** YES — a canonical re-audit on ~2,113 draws is recommended after P247 Type D segregation. Requires separate authorization.

**P243A:** Fixture is historical. After P247 and canonical re-audit, a new P243A-style fixture with `sample_size=2113` may be created.

---

## 7. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ confirmed |
| No row deletion | ✅ confirmed |
| Historical artifacts preserved | ✅ values unchanged |
| Add-on rows preserved | ✅ still in DB |
| No registry mutation | ✅ confirmed |
| BIG_LOTTO gate | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |

**ADD_ON_PRIZE_EXCLUDED records (19,100 rows) are valid lottery-related records. They remain in the DB and accessible via raw methods. They are excluded from canonical research due to population mismatch.**

**Final Classification:** `P246I_BIG_LOTTO_POPULATION_ASSERTION_CLEANUP_COMPLETE`
