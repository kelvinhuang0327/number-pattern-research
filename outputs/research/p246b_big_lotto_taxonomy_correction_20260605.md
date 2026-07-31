# P246B — BIG_LOTTO Taxonomy Correction

**Task ID:** P246B · **Date:** 2026-06-05 · **Type:** Read-only taxonomy correction artifact.
**Supersedes:** P246 taxonomy wording for SIM_HYPHEN row family only. Row counts preserved.
**Final Classification:** `P246B_BIG_LOTTO_TAXONOMY_CORRECTION_COMPLETE`

---

## 1. Correction Summary

P246 classified 19,100 hyphenated BIG_LOTTO rows as `SIM_HYPHEN` (simulation-like contamination).

**User/domain correction:** Hyphenated IDs such as `103000009-01` are **add-on or special prize records**, not simulated or fake data. They are valid lottery-related records that are outside the canonical BIG_LOTTO 6/49 main-draw research population.

> These rows must not be described as fake, simulated, synthetic, invalid, or contaminated.
> They are excluded from research due to **population mismatch** (add-on/special prize record type ≠ canonical 6/49 main draw), not because the data is false.

---

## 2. Corrected Taxonomy

| Family | Count | % | Corrected Label | Exclusion Basis |
|---|---|---|---|---|
| ~~SIM_HYPHEN~~ → **ADD_ON_PRIZE_EXCLUDED** | 19,100 | 85.89% | Add-on/special prize records | Population mismatch — not comparable to 6/49 main draws |
| `DATE_FORMAT_ALIEN` | 375 | 1.69% | Non-canonical (unchanged) | Numbers inconsistent with 6/49 pool; data-integrity concern |
| `SMALL_POOL_ALIEN` | 650 | 2.92% | Non-canonical (unchanged) | Numbers restricted to ≤25 pool; likely mislabeled game |
| ~~CANONICAL_PLAUSIBLE~~ → **CANONICAL_MAIN_DRAW** | 2,113 | 9.5% | Canonical 6/49 main draws | Intended research population |

**[Inferred]** ADD_ON_PRIZE_EXCLUDED classification is based on draw ID pattern (`draw LIKE '%-%'`) and user/domain correction. No authoritative source document was independently confirmed in this task.

---

## 3. What Changes vs P246

| P246 | P246B correction |
|---|---|
| Family label: `SIM_HYPHEN` | Corrected to: `ADD_ON_PRIZE_EXCLUDED` |
| Description: "100 synthetic variants per real draw date" | Corrected to: "add-on or special prize records" |
| Contamination count: 20,125 (SIM_HYPHEN + DATE_FORMAT + SMALL_POOL) | Row counts unchanged; ADD_ON rows are excluded-but-valid, not contamination |
| Section 4.1 heading: "Simulation Artifacts" | Corrected to: "Add-on / Special Prize Records" |
| Quarantine plan: "move contaminated rows" | Corrected P247 plan: "segregate with preservation; do not delete; do not describe as fake" |

**What does NOT change:**
- Total rows: 22,238
- ADD_ON_PRIZE_EXCLUDED count: 19,100
- DATE_FORMAT_ALIEN count: 375 (still a non-canonical concern)
- SMALL_POOL_ALIEN count: 650 (still a non-canonical concern)
- CANONICAL_MAIN_DRAW count: 2,113
- BIG_LOTTO research gate: **GATE_RED_PENDING_CANONICAL_SEPARATION** (blocked; reason updated from contamination to population mismatch + unresolved DATE_FORMAT/SMALL_POOL concerns)
- P219 signal explanation: all structural-break signals still explained by non-canonical row families (no exploitable edge)

---

## 4. ADD_ON_PRIZE_EXCLUDED — Corrected Description

**Count:** 19,100  
**Draw ID pattern:** `draw LIKE '%-%'` (e.g. `103000009-01`, `100000009-08`)  
**Year span:** 2011–2023  
**Numbers:** 6/49-compatible ranges (sum_mean ≈ 149.2, max ≈ 43.0, range 11–49)

> **These records are valid lottery-related records.** The hyphenated draw IDs indicate these are add-on or special prize records associated with BIG_LOTTO draw events, not canonical main draws.

**Exclusion basis:** Population mismatch. Add-on/special prize records are not comparable to canonical 6/49 main draws for the purpose of predictive modeling, randomness audits, frequency analysis, or bias research. They must be excluded from the canonical research sample for this reason, not because they are false or corrupted.

**P219 link:** Excluded at load time by `draw NOT LIKE '%-%'`; did not drive the P219 structural-break signals (which are explained by DATE_FORMAT_ALIEN and SMALL_POOL_ALIEN families).

---

## 5. Distinction: Data Contamination vs Research Population Mismatch

| Concept | Applies to | Meaning |
|---|---|---|
| **Data contamination** | DATE_FORMAT_ALIEN, SMALL_POOL_ALIEN | Numbers inconsistent with 6/49 game rules or IDs suggest import error. Remain non-canonical data-integrity concerns. |
| **Research population mismatch** | ADD_ON_PRIZE_EXCLUDED | Valid lottery records of a different record type (add-on/special prize) that are incomparable to canonical main draws. Excluded because they are the wrong population, not because they are false. |

---

## 6. Forbidden Claims

The following descriptions must NOT be applied to ADD_ON_PRIZE_EXCLUDED rows:

- "simulated"
- "fake"
- "synthetic"
- "invalid"
- "contaminated"
- "non-lottery data"
- "fabricated variants"

---

## 7. BIG_LOTTO Research Gate

**Current gate state:** `GATE_RED_PENDING_CANONICAL_SEPARATION`

BIG_LOTTO predictive and bias research remains blocked because:

1. The canonical main-draw dataset (CANONICAL_MAIN_DRAW, ~2,113 rows) has not been separated from non-canonical row families in the DB.
2. DATE_FORMAT_ALIEN (375 rows) and SMALL_POOL_ALIEN (650 rows) are still non-canonical concerns requiring cautious handling.
3. A corrected P247 segregation plan has been produced (artifact-only; DB apply requires separate Type D authorization).

**Unblocked condition:** After Type D segregation operation is authorized, executed, and verified — canonical main-draw count ~2,118; excluded rows preserved; drift guard PASS; no side effects on other lottery types.

---

## 8. Governance

| Rule | Status |
|---|---|
| No DB write | ✅ respected |
| No migration applied | ✅ plan artifact only |
| No strategy promotion | ✅ respected |
| No betting advice | ✅ respected |
| No P(win) claim | ✅ no exploitable edge |
| ADD_ON rows preserved | ✅ preservation required (not delete) |
| P246 row counts unchanged | ✅ preserved |
| BIG_LOTTO gate remains blocked | ✅ GATE_RED_PENDING_CANONICAL_SEPARATION |
| Type D gate for DB apply | ✅ required — not authorized here |

**Final Classification:** `P246B_BIG_LOTTO_TAXONOMY_CORRECTION_COMPLETE`
