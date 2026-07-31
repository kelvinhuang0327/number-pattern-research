# P247 — BIG_LOTTO Corrected Exclusion Plan (Artifact Only)

**Task ID:** P247_PLAN · **Date:** 2026-06-05 · **Type:** Future plan artifact only. No DB write authorized here.
**Depends On:** P246B taxonomy correction
**Operation Name:** BIG_LOTTO canonical research sample segregation — add-on prize and non-canonical row family exclusion from research dataset
**Final Classification:** `P247_BIG_LOTTO_CORRECTED_EXCLUSION_PLAN_ARTIFACT_ONLY`

> **IMPORTANT: This document is a plan artifact only. No DB modification has been performed. A separate explicit Type D human gate authorization is required before any DB operation may be executed.**

---

## 1. Purpose

This plan supersedes the quarantine plan in P246 §7. It corrects the language from "quarantine contaminated rows" to "segregate non-canonical row families with preservation."

Key corrections from P246 quarantine plan:
- ADD_ON_PRIZE_EXCLUDED (formerly SIM_HYPHEN) rows are **preserved**, not deleted.
- The operation is **segregation**, not quarantine of contaminated data.
- A segregation/audit table is preferred over permanent deletion.
- No row may be described as fake, simulated, or contaminated in audit tables or comments.

---

## 2. Row Families to Segregate

| Family | Count | Action | Preservation |
|---|---|---|---|
| **ADD_ON_PRIZE_EXCLUDED** | 19,100 | Move to segregation table | REQUIRED — valid lottery-related records |
| **DATE_FORMAT_ALIEN** | 375 | Move to segregation table | REQUIRED — non-canonical concern; cautious handling |
| **SMALL_POOL_ALIEN** | 650 | Move to segregation table | REQUIRED — likely mislabeled game |

**Do NOT** label any ADD_ON_PRIZE_EXCLUDED row as fake, simulated, synthetic, or invalid in any table comment, column value, or log entry.

---

## 3. Proposed DB Operations (Plan Only — NOT Authorized)

### Phase 1 — Backup

```bash
cp lottery_api/data/lottery_v2.db \
  backups/p247_big_lotto_segregation_backup_$(date +%Y%m%d_%H%M%S).db
sha256sum backups/p247_big_lotto_segregation_backup_*.db
```

SHA256 must be recorded before any write.

### Phase 2 — Segregation Table

Create `draws_big_lotto_excluded` table preserving all original columns plus metadata:

```sql
CREATE TABLE IF NOT EXISTS draws_big_lotto_excluded AS
  SELECT *, NULL AS row_family, NULL AS exclusion_reason, NULL AS excluded_at
  FROM draws WHERE 1=0;

-- ADD_ON_PRIZE_EXCLUDED (hyphenated IDs — add-on/special prize records)
INSERT INTO draws_big_lotto_excluded
  SELECT *, 'ADD_ON_PRIZE_EXCLUDED',
    'Add-on or special prize record — excluded due to population mismatch, not data falseness',
    datetime('now')
  FROM draws
  WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%';

-- DATE_FORMAT_ALIEN (8-digit YYYYMMDD IDs)
INSERT INTO draws_big_lotto_excluded
  SELECT *, 'DATE_FORMAT_ALIEN',
    'Non-canonical draw ID format (YYYYMMDD); numbers inconsistent with 6/49 pool',
    datetime('now')
  FROM draws
  WHERE lottery_type='BIG_LOTTO'
    AND LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%';

-- SMALL_POOL_ALIEN — requires Python-driven inspection (max(numbers)<=25)
-- See analysis/p246b_big_lotto_taxonomy_correction.py for Python segregation logic
```

After INSERT verification, remove from main `draws` table:

```sql
DELETE FROM draws
WHERE lottery_type='BIG_LOTTO' AND draw LIKE '%-%';

DELETE FROM draws
WHERE lottery_type='BIG_LOTTO'
  AND LENGTH(draw)=8 AND draw LIKE '20%' AND draw NOT LIKE '%-%';

-- SMALL_POOL_ALIEN: Python-driven DELETE after verification
```

### Phase 3 — Research Exclusion View (Optional)

```sql
CREATE VIEW IF NOT EXISTS draws_big_lotto_canonical AS
  SELECT * FROM draws
  WHERE lottery_type='BIG_LOTTO'
    AND draw NOT LIKE '%-%'
    AND LENGTH(draw) < 8;
-- Note: SMALL_POOL_ALIEN requires additional filter after Python-driven segregation
```

### Phase 4 — Verification

```sql
-- Canonical main draw count (expect ~2113–2118)
SELECT COUNT(*) FROM draws WHERE lottery_type='BIG_LOTTO';

-- Segregated counts by family
SELECT row_family, COUNT(*) FROM draws_big_lotto_excluded GROUP BY row_family;

-- Replay rows (must remain unchanged, baseline 94,924)
SELECT COUNT(*) FROM strategy_prediction_replays;

-- Non-BIG_LOTTO types (must be unchanged)
SELECT lottery_type, COUNT(*) FROM draws
WHERE lottery_type != 'BIG_LOTTO' GROUP BY lottery_type;

-- Integrity check
PRAGMA integrity_check;
```

---

## 4. Pre-Apply Checks

Before any DB write is authorized:

- [ ] P246B taxonomy correction artifact is on main and all tests pass
- [ ] replay rows = 94,924 (read-only check)
- [ ] PRAGMA integrity_check = ok
- [ ] No other DB write is in progress
- [ ] Drift guard PASS (read-only check)
- [ ] Non-BIG_LOTTO row counts are stable
- [ ] Backup does not already exist for this operation date
- [ ] Phase 0 branch/HEAD/status check passes on a dev branch (not main)

---

## 5. What This Plan Does NOT Authorize

- No strategy development or promotion on BIG_LOTTO
- No prediction research or GATE_OPEN for BIG_LOTTO
- No production recommendation change
- No registry mutation
- No controlled_apply
- No betting advice
- BIG_LOTTO research gate remains blocked until segregation is executed, verified, and a clean re-audit passes

---

## 6. Post-Apply Reconciliation

After Type D execution:

1. Re-run `python3 analysis/p246b_big_lotto_taxonomy_correction.py` on cleaned data
2. Expected: CANONICAL_MAIN_DRAW ~2118, all excluded families in `draws_big_lotto_excluded`
3. Gate reassignment candidate: GATE_RED → `GATE_CLOSED_PENDING_REAUDIT` (pending clean NIST-style re-audit)
4. Clean re-audit (P238B-style) required before any research gate opens

---

## 7. Governance

| Rule | Status |
|---|---|
| No DB write here | ✅ plan artifact only |
| ADD_ON rows preserved | ✅ required — segregation table, not deletion |
| Separate Type D gate required | ✅ explicitly stated |
| No betting advice | ✅ respected |
| No strategy promotion | ✅ respected |
| No production recommendation change | ✅ respected |
| Drift guard must pass post-apply | ✅ post-apply verification required |

**Final Classification:** `P247_BIG_LOTTO_CORRECTED_EXCLUSION_PLAN_ARTIFACT_ONLY`
