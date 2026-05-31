# P159: Provenance Source UI Polish

**Classification**: `P159_PROVENANCE_SOURCE_UI_POLISH_READY`
**Task ID**: P159
**Generated**: 2026-05-30

---

## 1. Executive Summary

P159 adds `provenance_source` to the replay history detail panel. This was the last deferred item from P152.

- DB col 23 (`provenance_source`) existed since early P-tasks
- API already returned it since P150 (line 528, `replay.py`)
- Only UI polish needed — one line added to `rpRenderDetail` in `index.html`
- No DB writes, no API changes

**34 P159 tests pass. DB = 94924 unchanged.**

---

## 2. Canonical Repo / Branch Confirmation

| Field | Value | Status |
|-------|-------|--------|
| Canonical repo | `.../zen-gates-ff6802` | ✅ MATCH |
| Canonical branch | `claude/zen-gates-ff6802` | ✅ MATCH |
| Production DB rows | 94924 | ✅ MATCH |
| Drift guard | PASS | ✅ PASS |

---

## 3. P158B Smoke Recap

P158B confirmed all provenance fields present except `provenance_source`. P159 closes this final gap.

---

## 4. provenance_source Field Audit

| Item | Value |
|------|-------|
| DB has `provenance_source` | ✅ col 23 |
| Rows with provenance_source | 70500/94924 (74.3%) |
| API returned before P159 | ✅ Yes (P150) |
| API change required | ❌ No |
| UI display required | ✅ Yes (this task) |
| UI display completed | ✅ Yes |

Sample values: `P94_CONTROLLED_APPLY`, `p47_wave4_powerlotto_adapters.py`, `p31a_wave1_retired_adapters.py`, `p42_wave3_biglotto_adapters.py`

---

## 5. API Changes

**None.** `provenance_source` already in `/api/replay/history` response since P150.

---

## 6. UI Changes

### index.html — after `rp-detail-provenance-hash`:
```html
<div>
  <span>Provenance Source：</span>
  <code data-testid="rp-detail-provenance-source">
    ${r.provenance_source ? r.provenance_source : 'N/A（未提供）'}
  </code>
</div>
```

All P151/P152 regressions preserved: bet_index, all-catalog, no_data_reason, source, controlled_apply_id, provenance_hash, truth_level.

---

## 7. provenance_source Display Support

| Item | Status |
|------|--------|
| Visible in detail panel | ✅ `rp-detail-provenance-source` |
| Null handling | ✅ "N/A（未提供）" |
| Test coverage | ✅ |

---

## 8. Operator Guide Update

`docs/replay/REPLAY_PRODUCT_OPERATOR_GUIDE_20260529.md` updated with `provenance_source` explanation.

---

## 9. Tests and Verification

| Suite | Result |
|-------|--------|
| `tests/test_p159_provenance_source_ui_polish.py` | **34 passed** |
| Regression (P149–P158B) | **574 passed** |
| Total | **608 passed** |
| Drift guard | PASS |
| DB rows | 94924 (unchanged) |

---

## 10. Explicit Non-Actions

DB write ❌ / API change ❌ / lifecycle update ❌ / replay rows 0/0/0 / controlled_apply ❌ / champion ❌ / live API ❌ / scheduler ❌.

---

## 11. Dirty File Hygiene Note

- `backups/` untracked — not staged
- `lottery_api/models/replay_strategy_registry.py` NOT staged

---

## 12. Remaining Risks

1. 24424 rows have null `provenance_source` — displayed as N/A
2. h6_gate_mk20_ew85 still 0 rows — non-blocking
3. P108/P117/P118/4★ BLOCKED — separate chain

---

## 13. Recommended Next Task

**NONE** — All optional polish items completed.

---

## 14. Final Classification

```
P159_PROVENANCE_SOURCE_UI_POLISH_READY
```

All planned provenance metadata fields now displayed in replay UI:
`truth_level` / `source` / `controlled_apply_id` / `provenance_hash` / **`provenance_source`** ✅
