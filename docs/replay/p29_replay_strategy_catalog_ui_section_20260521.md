# P29 — Replay Strategy Catalog UI Section

**Date:** 2026-05-21  
**Phase:** P29_REPLAY_STRATEGY_CATALOG_UI_SECTION  
**Branch:** p29-replay-strategy-catalog-ui-section  
**Classification:** P29_CATALOG_UI_SECTION_READY

---

## 1. Objective

Add a compact "策略狀態總覽" section inside the existing replay page that:
- Reads `/api/replay/strategy-catalog` (P28 endpoint) as a read-only consumer
- Displays strategy counts by label
- Enforces `is_queryable` semantics (non-queryable rows do not trigger replay history queries)
- Shows CEO-mandated coverage footnote and non-row-backed note
- Never hardcodes label mappings — all fields consumed from API

---

## 2. Implementation

### HTML Section (`index.html`)

| Element | ID / test-id |
|---------|-------------|
| Card container | `rp-catalog-card` / `data-testid="rp-catalog-card"` |
| Title | `data-testid="rp-catalog-title"` — "📊 策略狀態總覽" |
| Total badge | `rp-catalog-total-badge` |
| Summary / chips | `rp-catalog-summary` / `rp-catalog-count-chips` |
| Coverage footnote | `rp-catalog-coverage-footnote` |
| Loading indicator | `rp-catalog-loading` |
| Error indicator | `rp-catalog-error` |
| Table tbody | `rp-catalog-tbody` |

### JS Functions

| Function | Purpose |
|----------|---------|
| `rpLoadCatalog()` | Fetches `/api/replay/strategy-catalog`, renders counts and rows |
| `rpInitCatalogClickHandler()` | Delegates click on tbody; non-queryable rows return early |

Both are wired in `DOMContentLoaded` and on nav section click.

---

## 3. Catalog Counts (from `/api/replay/strategy-catalog`)

| Metric | Value |
|--------|-------|
| Total strategies | **59** |
| Row-backed (`is_queryable=True`) | **8** |
| Artifact-only | **41** |
| Retired | **5** |
| Rejected-registered | **4** |
| Observation | **1** |

---

## 4. `is_queryable` Enforcement

- **Non-queryable rows** (`data-catalog-queryable="false"`): click handler returns early, no `rpQuery` call, `safe_user_message` exposed as title tooltip.
- **Queryable rows** (`data-catalog-queryable="true"`): click pre-fills `#rp-strategy-select` and triggers the existing replay history query.

---

## 5. CEO-Mandated Elements

| Element | Value |
|---------|-------|
| Coverage footnote | `📌 current row-backed coverage = 8/59 (~13.5%) of strategy universe` |
| Non-row-backed indicator | `（可重建候選尚未評估，將於後續階段處理）` |

---

## 6. Error Handling

- Failed catalog load: `console.warn` only (never `console.error`).
- Page remains fully functional; error banner shown; existing replay history unaffected.

---

## 7. CEO Opportunistic Observations

| Feature | Status |
|---------|--------|
| Lottery selector | ✅ PRESENT — `#rp-lottery-select` |
| Strategy selector | ✅ PRESENT — `#rp-strategy-select` |
| Date-range default half-year | ❌ ABSENT — user sets manually |
| 100/500/1000/1500 preset buttons | ✅ PRESENT — `#rp-preset-btns` |
| Pagination | ✅ PRESENT — `#rp-page-info`, smooth prev/next |

---

## 8. Tests

30 tests in `tests/test_p29_replay_strategy_catalog_ui_section.py` — all PASS.

| Category | Tests |
|----------|-------|
| HTML section presence | 8 |
| JS function definitions | 2 |
| No hardcoded label map | 1 |
| is_queryable enforcement | 1 |
| API catalog counts (59/8/41/5/4/1) | 6 |
| Per-strategy field validation | 4 |
| Production DB invariant | 1 |
| CEO coverage footnote | 1 |
| DOMContentLoaded wiring | 3 |
| Error path uses warn not error | 1 |
| Existing replay API unaffected | 1 |
| Miscellaneous | 1 |

---

## 9. Production DB

Production rows: **12460** (unchanged — no DB writes).

---

## 10. Next Recommendation: P30 — Reconstructible-Candidacy Evaluation (Read-Only)

The `reconstructible_candidate` field is already present in the P28 catalog response. P30 should evaluate which of the 51 non-row-backed strategies are reconstructible via existing `tools/` or `lottery_api/models/` code, producing a ranked list of candidates for the next backfill wave.

This is a read-only research phase — no DB writes, no adapter execution, no registry changes.
