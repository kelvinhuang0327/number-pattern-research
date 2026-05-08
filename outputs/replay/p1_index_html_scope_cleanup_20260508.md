# P1-4A — index.html Scope Cleanup Report
**Date:** 2026-05-08
**Branch:** release/p0-replay-20260508
**PR:** #1 (OPEN, base=main)
**Agent:** Senior Scope Cleanup Agent

---

## 1. Executive Summary

PR #1 contained a large non-replay frontend redesign mixed into `index.html`, creating B1 blocker.
This report documents the cleanup: the release branch `index.html` has been restored to main's version,
with only replay governance UI re-applied. The non-replay redesign remains safely preserved on
`feat/frontend-redesign-20260508`. B1 is now **RESOLVED**. B2 remains open pending CTO decision.

---

## 2. Preservation Branch

Non-replay frontend redesign was already saved to:

- `feat/frontend-redesign-20260508` (local + remote confirmed)
- Remote: `remotes/origin/feat/frontend-redesign-20260508`

**No redesign work was lost.** The non-replay changes are fully available for a future PR.

---

## 3. Before Cleanup Diff Summary

| Metric | Value |
|--------|-------|
| File | index.html |
| Lines in release branch | 2988 |
| Lines in main | 1319 |
| Diff insertions | +2249 |
| Diff deletions | -581 |
| Total diff lines | 3367 |

### Non-replay content detected in diff (B1 cause):
- `<script src="https://unpkg.com/lucide@latest">` — Lucide icons CDN
- `<link rel="stylesheet" href="professional-design.css?v=18">` — Non-replay CSS framework
- Entire inline `<style>` block (lines 24–449, 426 lines) — redesign CSS only
- `data-lucide="..."` icon attributes throughout nav buttons
- `<section id="next-draw-section">` — non-replay section
- `<section id="tracking-section">` — non-replay section
- `<section id="reviews-section">` — non-replay section
- `<section id="orchestration-section">` — non-replay section
- `<section id="cto-review-section">` — non-replay section
- Nav buttons for all above sections (with Lucide icons)
- `lucide.createIcons()` init script

---

## 4. After Cleanup Diff Summary

| Metric | Value |
|--------|-------|
| Lines in cleaned index.html | 1901 |
| Lines in main | 1319 |
| Diff insertions | +582 |
| Diff deletions | 0 |
| Total diff lines | 608 |

Diff size reduced from **3367 → 608 lines** (−82% reduction).
Insertions reduced from **+2249 → +582** (−74% reduction).

---

## 5. Replay Scope Kept

All replay governance UI elements confirmed present after cleanup:

| Element | Status |
|---------|--------|
| Nav button `data-section="replay"` | ✅ Present |
| `<section id="replay-section">` | ✅ Present |
| `rp-freshness-card` | ✅ Present |
| `rp-coverage-badge` | ✅ Present |
| `rp-legacy-error-note` | ✅ Present |
| `rp-freshness-table` / `rp-freshness-tbody` | ✅ Present |
| `rp-info-panel` (details/causal disclaimer) | ✅ Present |
| `rp-lottery-select` / `rp-strategy-select` / `rp-status-select` | ✅ Present |
| `rp-date-from` / `rp-date-to` | ✅ Present |
| `rp-query-btn` / `rp-summary-btn` | ✅ Present |
| `rp-summary-cards` / `rp-hist-body` | ✅ Present |
| `rp-prev-btn` / `rp-next-btn` / `rp-page-info` | ✅ Present |
| `/api/replay` fetch calls | ✅ Present |
| `// ===== REPLAY PAGE JS =====` block | ✅ Present (405 lines) |
| `history_cutoff` display | ✅ Present |
| Causal metadata display | ✅ Present |
| Conservative disclaimer | ✅ Present |
| Limited coverage wording | ✅ Present |
| No edge claim wording | ✅ Present |

---

## 6. Non-Replay Redesign Removed From PR

All non-replay redesign content confirmed absent from PR diff after cleanup:

| Removed Element | Status |
|-----------------|--------|
| `professional-design.css` import | ✅ Removed |
| Lucide icons CDN script | ✅ Removed |
| `data-lucide="..."` icon attributes | ✅ Removed |
| Inline `<style>` block (426 lines of redesign CSS) | ✅ Removed |
| `next-draw-section` | ✅ Removed |
| `tracking-section` | ✅ Removed |
| `reviews-section` | ✅ Removed |
| `orchestration-section` | ✅ Removed |
| `cto-review-section` | ✅ Removed |
| Nav buttons with Lucide for above sections | ✅ Removed |
| `lucide.createIcons()` init | ✅ Removed |
| Visibility guard CSS (`.rv-hidden`, `.ui-hidden` in style block) | ✅ Removed |

---

## 7. Ambiguous Items

**None.**

The replay section uses only inline styles and standard CSS classes (`card`, `btn`, `form-control`,
`data-table`) that are already present in `styles.css` on main. No shared redesign resources were
required for replay UI. Separation was clean.

The replay nav button was re-implemented using main's emoji-icon format (matching all other nav buttons),
rather than the Lucide-icon format from the redesign branch. This preserves visual consistency with
main's existing nav style.

---

## 8. Validation Result

```
pytest tests/test_randomness_audit_cadence.py \
       tests/test_strategy_replay_history_cutoff_integrity.py \
       tests/test_replay_browser_smoke.py \
       tests/test_replay_api_contract.py \
       tests/test_replay_freshness_cadence.py -q
```

**Result: 57 passed, 32 skipped**

- 57 non-DB tests: PASSED
- 32 requires_db tests: SKIPPED (skip guard working correctly — DB not present in sandbox)
- 0 failures
- 0 errors

**Validation PASS. Safe to commit.**

---

## 9. Files Changed

| File | Action |
|------|--------|
| `index.html` | Restored to main + replay UI re-applied |
| `outputs/replay/p1_index_html_scope_cleanup_20260508.md` | Created (this report) |

---

## 10. What Was Not Changed

- No Replay API code modified
- No strategy state modified
- No replay generation performed
- No edge claim added
- No strategy ranking or promotion
- No production outcome written
- No DB files committed
- No test_mab_ensemble.py touched
- No in-memory DB fixture implemented
- No merge performed
- No force push performed
- No tag created

---

## 11. Remaining B2 — CI Live-DB Fixture Policy

**Status: STILL OPEN — requires CTO decision**

The `requires_db` skip guard was completed in P1-3. However, a CI policy decision is still pending:

**Option 1:** Accept `requires_db` skip guard for this PR
- DB-dependent tests skip cleanly in CI (no DB in sandbox)
- Non-DB tests (57) continue to pass
- PR merges without full DB test coverage in CI

**Option 2:** Require in-memory DB fixture before merge
- All 32 skipped tests would run against fixture data
- Higher confidence but requires additional implementation work
- In-memory DB fixture has not been implemented

This decision requires CTO authorization. B2 is not blocking code correctness — it is a CI policy question.

---

## 12. Final Recommendation

**B1 is resolved.** PR #1 now has a clean, focused scope:

- `index.html` only contains replay governance UI changes
- non-replay frontend redesign is preserved on `feat/frontend-redesign-20260508`
- PR #1 reviewer no longer needs to review unrelated frontend redesign
- Replay section is complete and self-contained

**Recommended next step:** CTO to decide B2 policy, then merge PR #1.

---

## Preservation Notice

> Non-replay frontend redesign has been saved to `feat/frontend-redesign-20260508`.
> PR #1 does not承擔 frontend redesign review responsibility.
> PR #1 scope is now exclusively: Replay Governance Release.
> No replay generation was performed. No edge claim was made.
> No strategy ranking or promotion occurred. No production outcome was written.

