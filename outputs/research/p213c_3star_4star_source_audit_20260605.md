# P213C 3_STAR / 4_STAR Source Audit

**Date:** 2026-06-05
**Classification:** `P213C_SOURCE_AUDIT_SOURCE_CANDIDATE_FOUND_NEEDS_VALIDATION`
**Final Task Classification:** `P213C_3STAR_4STAR_SOURCE_AUDIT_COMPLETE`
**Task Type:** Type B (read-only source audit / artifact) under P240D governance simplification rules
**Status:** Read-only source audit only — no code changes, no DB write, no schema change, no ingestion
**Authorization:** `Authorize P213C 3_STAR/4_STAR source audit (read-only API inspection, no DB write)`

---

## 1. Scope and Non-Goals

### In Scope
- Local repo source audit for 3_STAR/4_STAR positional data
- Code path analysis for how data enters the DB
- Assessment of raw source format availability
- Same-PR governance closeout under P240D Type B rule

### Explicitly Out of Scope

| Forbidden Item | Status |
|---|---|
| Code changes | Not authorized |
| DB write | Not authorized |
| Schema change | Not authorized |
| Ingestion or re-ingestion | Not authorized |
| Registry mutation | Not authorized |
| Live API calls | Not performed (no governance authorization for live API calls; local repo evidence was sufficient) |
| Strategy promotion | Not authorized |
| Betting advice | Never authorized |

---

## 2. Confirmed Current-State Facts

### 2.1 Positional Order Is Lost in Current DB Storage

**Root cause (confirmed in P213B, re-confirmed here):**
- `lottery_api/database.py:463`: `numbers_json = json.dumps(sorted(numbers))` — always sorts
- P226: 100% of 4,179 3_STAR draws and 2,922 4_STAR draws stored sorted

### 2.2 The Game Configuration Explicitly Flags These as Permutation

**`lottery_api/data/lottery_types.json`:**
```json
"3_STAR": {"isPermutation": true, "repeatsAllowed": true, ...}
"4_STAR": {"isPermutation": true, "repeatsAllowed": true, ...}
```

`isPermutation: true` means draw order matters for straight-play (e.g., drawing 3-2-1 is different from 1-2-3).

### 2.3 The CSV Validator Correctly Preserves Permutation Order

**`lottery_api/utils/csv_validator.py:286`:**
```python
final_numbers = numbers if is_permutation else sorted(numbers)
```

**`lottery_api/utils/csv_validator.py:451–452`:**
```python
is_permutation = getattr(rules, 'isPermutation', False)
final_numbers = numbers if is_permutation else sorted(numbers)
```

The CSV validator ALREADY handles permutation games correctly — it preserves draw order when `isPermutation=True`. This is an existing, correct behavior.

### 2.4 The Database Layer Overrides This Behavior (The Bug)

The parsed, positional data from `csv_validator` gets sorted again by `database.py:463` before storage. This is the precise, single-line bug:

```python
# database.py:463 — THE BUG
numbers_json = json.dumps(sorted(numbers))  # sorts regardless of isPermutation
```

**The fix is one line**: change to respect the permutation flag. But this is a code change requiring separate authorization.

### 2.5 The Raw Source Format Has Draw Order

From `lottery_api/tools/debug_validator.py` (3_STAR mock content):
```
112000001期
開獎日期:112/01/01
大小順序:1 2 3        ← sorted order
開出順序:3 2 1        ← DRAW ORDER (positional)
1 2 3
```

From `lottery_api/tools/debug_comprehensive.py` (4_STAR mock content):
```
112000001
開獎日期:112/01/01
大小順序:1234         ← sorted order
開出順序:4321         ← DRAW ORDER (positional)
1234
```

The raw CSV/TXT format from the Taiwan Lottery includes BOTH `大小順序` (sorted) and `開出順序` (draw order). This means any historical source file in this format would contain recoverable positional data.

### 2.6 No 3_STAR/4_STAR API Endpoint in Current Fetcher

`lottery_api/fetcher/taiwan_lottery_fetcher.py` SOURCE_CONFIG only covers BIG_LOTTO, POWER_LOTTO, DAILY_539. The 3_STAR/4_STAR data must have been imported via the CSV/TXT upload route.

---

## 3. Source Audit Findings

### 3.1 CSV Upload Route Exists

**`lottery_api/routes/data.py:53–104`:** The application has a `/api/data/upload` and `/api/data/validate-csv` endpoint. This route uses `csv_validator` to parse uploaded CSV/TXT files for any lottery type including 3_STAR and 4_STAR.

This confirms the import path: original 3_STAR/4_STAR data was uploaded as CSV/TXT via this route → parsed by `csv_validator` (preserving draw order) → stored by `database.py` (re-sorted). The positional information was present at parse time but discarded before storage.

### 3.2 Raw CSV/TXT Source Files Not Found in Repo

No original 3_STAR/4_STAR historical CSV/TXT files were found in the repo working tree. The files likely existed when the data was originally imported but are not tracked in git or retained locally.

### 3.3 Backfill Engine Does Not Support 3_STAR/4_STAR

`lottery_api/fetcher/backfill_engine.py` docstring: "Auto-detect and fill missing draws" with examples only for BIG_LOTTO, POWER_LOTTO, DAILY_539. No evidence of 3_STAR/4_STAR support.

### 3.4 Taiwan Lottery Source Format is Known

From the mock content in debug tools, the Taiwan Lottery CSV/TXT format for 3_STAR/4_STAR includes `開出順序` (draw order). This format is used by the csv_validator. Any historical CSV/TXT file from the Taiwan Lottery for these games would contain recoverable positional data.

### 3.5 Summary Table

| Source Candidate | Found? | Has Positional Order? | Recovery Action |
|---|---|---|---|
| `draws` table in DB | Yes | No — sorted | Not useful for recovery |
| `lottery_types.json` | Yes | `isPermutation: true` (metadata only) | Confirms need for positional |
| `csv_validator.py` | Yes | Handles correctly (`is_permutation` logic) | Fix database.py bug |
| `debug_validator.py` mock | Yes | Format shows `開出順序` present | Confirms source format has order |
| Original import CSV/TXT files | NOT found in repo | Expected yes | Need re-download from source |
| Taiwan Lottery API/website | External — not audited locally | Unknown from repo alone | Requires external source audit |
| `backfill_engine.py` | Yes | No 3_STAR/4_STAR support | Cannot use for backfill |

---

## 4. Source Classification

**`P213C_SOURCE_AUDIT_SOURCE_CANDIDATE_FOUND_NEEDS_VALIDATION`**

**Why not BLOCKED:** The raw source format is known and confirmed to include `開出順序` (draw order). The `csv_validator` already handles this correctly.

**Why "needs validation":** The original CSV/TXT source files are not present in the repo. Recovery requires either re-downloading historical data from the Taiwan Lottery source or finding an existing archive. The external source has not been audited.

---

## 5. Recoverability Assessment

| Dimension | Assessment |
|---|---|
| **Root cause** | Identified and confirmed (`database.py:463` sorts always) |
| **Fix complexity** | Low — one-line code change in `database.py` |
| **Source format** | Known — Taiwan Lottery CSV/TXT with `開出順序` |
| **Source availability** | Unknown — original files not in repo; external access needed |
| **csv_validator readiness** | High — already handles `isPermutation: true` correctly |
| **DB schema readiness** | Requires: add `numbers_positional` column OR fix `numbers` handling |
| **Overall recoverability** | **POSSIBLE — source confirmation and code fix required** |
| **Confidence level** | Medium-high (source format known; source availability unknown) |

---

## 6. Future Path Options

### Recommended: P213D — Database Layer Fix Design (Type B)

Now that the bug is precisely identified, the next step is designing the database.py fix and the schema change (adding `numbers_positional` column or changing `numbers` behavior for permutation games).

**Authorization phrase:**
```
Authorize P213D 3_STAR/4_STAR positional schema and code fix design (read-only design doc, no DB write)
```

### Alternative: External Source Download (Type D)

Before a DB fix can be tested, the original historical CSV/TXT files for 3_STAR/4_STAR draws would need to be re-downloaded from the Taiwan Lottery. This is a data acquisition step, separate from the code fix.

**Authorization phrase:**
```
Authorize P213E 3_STAR/4_STAR historical draw re-download and dry-run ingestion (no DB write to production)
```

### HOLD Option

No action. System remains WAITING_FOR_USER_AUTHORIZATION.

---

## 7. Future Authorization Phrases

| Step | Authorization Phrase |
|---|---|
| Schema/code fix design | `"Authorize P213D 3_STAR/4_STAR positional schema and code fix design (read-only design doc, no DB write)"` |
| Historical re-download dry-run | `"Authorize P213E 3_STAR/4_STAR historical draw re-download and dry-run ingestion (no DB write to production)"` |
| Production re-ingestion | `"Authorize 3_STAR/4_STAR positional data re-ingestion (DB write authorized, backup confirmed, dry-run passed)"` |
| HOLD | *(none needed)* |

---

## 8. Risks and Mitigations

| Risk | Mitigation |
|---|---|
| Source data no longer available on Taiwan Lottery website | Check historical archives or cached sources; this risk exists but Taiwan Lottery typically keeps draw history |
| `開出順序` may not be guaranteed positional (could be another sorted variant) | Validate a sample of recent draws against known results |
| Changing `database.py` affects all lottery types | Use `isPermutation` flag check; only 3_STAR/4_STAR affected |
| `numbers` column type change breaks existing consumers | Add `numbers_positional` as new column; keep `numbers` as sorted |
| Duplicate draw IDs during re-ingestion | `INSERT OR IGNORE` already in place; count before/after |
| Accidental DB write | Phase C/D require separate explicit authorizations |
| Straight-play analysis underpowered | Even with positional data, sample sizes remain below power threshold |

---

## 9. Recommendation

**Recommended next direction: P213D — Database Layer Fix and Schema Design (Type B)**

The audit confirms:
1. The bug is precisely one line in `database.py`
2. The `csv_validator` is already correct
3. The source format is known to include positional data (`開出順序`)
4. The fix design is low-risk and bounded

The next step is designing the `database.py` fix (check `isPermutation` before sorting) and the schema approach (new `numbers_positional` column or change to `numbers` column), as a read-only design doc.

**Authorization phrase:**
```
Authorize P213D 3_STAR/4_STAR positional schema and code fix design (read-only design doc, no DB write)
```

---

## 10. No-Claim Attestation

This source audit:
- Makes **no claim** about lottery number predictability
- Makes **no claim** about higher winning probability
- Provides **no wagering recommendation**
- Does not authorize any strategy, production, recommendation, monitoring, or DB change
- Does not restart P211
- All safety booleans: False

---

## 11. Type B Same-PR Closeout Rationale

This task is **Type B** under P240D — Markdown and JSON artifacts only, no code changes, governance changes ≤4 files, ≤120 lines. **No separate closeout PR is required.**
