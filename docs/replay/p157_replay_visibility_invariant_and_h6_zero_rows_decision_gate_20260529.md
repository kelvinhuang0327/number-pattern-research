# P157: Replay Visibility Invariant and H6 Zero Rows Decision Gate

**Classification**: `P157_REPLAY_VISIBILITY_INVARIANT_CONFIRMED_H6_DECISION_GATE_READY`
**Task ID**: P157
**Generated**: 2026-05-30

---

## 1. Executive Summary

P157 confirms the **replay visibility invariant** and provides a decision gate for h6_gate_mk20_ew85.

**Core principle established**:
> `lifecycle` is a display label, badge, and filter signal.
> It **NEVER** excludes a strategy from the replay product catalog.
> All 40 strategies remain visible after P156C lifecycle updates.

P156C lifecycle updates (DB_ONLY → ONLINE/RETIRED) did NOT reduce visibility. All 17 RETIRED strategies have replay rows (from historical backfill) and are now queryable with a RETIRED badge.

h6_gate_mk20_ew85: OBSERVATION / 0 rows / visible with ⚠️ badge. **Recommended: Option A (no change)**.

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `.../zen-gates-ff6802` | ✅ MATCH |
| Canonical branch | `claude/zen-gates-ff6802` | ✅ MATCH |
| Production DB rows | 94924 | ✅ MATCH |
| Drift guard | PASS | ✅ PASS |

---

## 3. Replay Product Boundary

### Core Visibility Invariant

| Principle | Status |
|-----------|--------|
| All lifecycle strategies visible in replay | ✅ True |
| RETIRED strategies visible | ✅ True |
| REJECTED strategies visible | ✅ True |
| OBSERVATION strategies visible | ✅ True |
| No-data strategies visible | ✅ True |
| lifecycle is label not visibility gate | ✅ True |
| P156C updates reduced visibility | ❌ False |

**What lifecycle controls**:
- Display badge (ONLINE / RETIRED / REJECTED / OBSERVATION)
- Filter options (user can filter by lifecycle)
- Risk annotation (advisory note)
- Sort ordering

**What lifecycle does NOT control**:
- Whether a strategy appears in the catalog
- Whether historical replay rows are accessible

---

## 4. Post-P156C Catalog Visibility Audit

| Lifecycle | Count | Has Rows? | Queryable | Visible |
|-----------|-------|-----------|-----------|---------|
| ONLINE | 18 | All yes | ✅ | ✅ |
| RETIRED | 17 | All yes (historical backfill) | ✅ | ✅ |
| REJECTED | 4 | No | ❌ → REJECTED_NO_REPLAY_DATA badge | ✅ |
| OBSERVATION | 1 | No (h6_gate) | ❌ → ONLINE_ZERO_REPLAY_ROWS badge | ✅ |
| **Total** | **40** | | | ✅ |

**Key finding**: All 12 P156C-updated RETIRED strategies (formerly DB_ONLY) already had replay rows from historical controlled_apply (P37/P43/P48/P94/P126x). They are now `is_queryable=True` with a RETIRED lifecycle badge.

---

## 5. Lifecycle Visibility Matrix Summary

All 40 strategies: `visible_in_catalog = true` for all.

RETIRED strategies now showing as RETIRED badge + queryable (有回放資料) ✅

---

## 6. H6 Gate Zero Rows Audit

| Field | Value |
|-------|-------|
| strategy_id | h6_gate_mk20_ew85 |
| lifecycle | OBSERVATION |
| replay_rows | 0 |
| no_data_reason | ONLINE_ZERO_REPLAY_ROWS |
| visible_in_catalog | ✅ True |
| queryable | ❌ False (0 rows) |
| badge | ⚠️ ONLINE_ZERO_REPLAY_ROWS |
| should remain visible if RETIRED | ✅ True |

---

## 7. H6 Gate Decision Options

| Option | Label | Recommended | Requires Auth |
|--------|-------|-------------|--------------|
| **A** | Keep OBSERVATION — visible with ⚠️ badge | ✅ **YES** | ❌ No |
| B | Run controlled_apply dry-run readiness audit | No | ❌ No |
| C | Change lifecycle to RETIRED — still visible | No | ✅ Yes |

**Option A (recommended)**: No change needed. h6_gate_mk20_ew85 is correctly visible in the catalog. If replay rows are needed later, authorize controlled_apply in a future P-task.

**Important for Option C**: Even if lifecycle is changed to RETIRED, the strategy MUST remain visible in the replay catalog. The visibility invariant applies to all lifecycles.

---

## 8. Authorization Status

No authorization provided. P157 is read-only audit. No changes executed.

---

## 9. Tests and Verification

| Suite | Result |
|-------|--------|
| `tests/test_p157_replay_visibility_invariant_and_h6_zero_rows_decision_gate.py` | **48 passed** |
| Regression (P149-P156C) | **271 passed** |
| Total | **319 passed** |
| Drift guard | PASS |
| DB rows | 94924 (unchanged) |

---

## 10. Explicit Non-Actions

DB write ❌ / lifecycle update ❌ / replay rows 0/0/0 / controlled_apply ❌ / champion ❌ / live API ❌ / scheduler ❌.

---

## 11. Dirty File Hygiene Note

- `backups/` untracked — not staged
- `replay_strategy_registry.py` — NOT staged (unchanged in P157)

---

## 12. Remaining Risks

1. h6_gate_mk20_ew85 remains 0 replay rows (non-blocking; visible in catalog)
2. P108/P117/P118/4★ governance triggers BLOCKED (separate chain)
3. Champion evaluation blocked pending live evidence

---

## 13. Recommended Next Task

`P158_REPLAY_E2E_BROWSER_SMOKE_EXPANSION` — optional E2E browser smoke tests for replay UI, or general product closure confirmation.

---

## 14. Final Classification

```
P157_REPLAY_VISIBILITY_INVARIANT_CONFIRMED_H6_DECISION_GATE_READY
```

Replay visibility invariant confirmed. All 40 strategies visible. lifecycle is a label not an exclusion gate.
