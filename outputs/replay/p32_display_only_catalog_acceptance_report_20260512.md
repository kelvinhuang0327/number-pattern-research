# P32 Display-Only Catalog Acceptance Report
**Date:** 2026-05-12  
**Feature:** P25 Display-Only Catalog for Non-ONLINE Lifecycle Strategies  
**PR:** #66 (product mainline)  
**Commit:** `2e4c1e7`  
**Status:** ✅ ACCEPTED — CEO DEMO READY

---

## Feature Summary

PR #66 implements a **display-only catalog UI** for non-ONLINE lifecycle strategies in the Replay section of `index.html`.

### What Changed (UI only — no backend changes)

**`index.html`** (+88 lines net):

| Symbol | Purpose |
|--------|---------|
| `rpEscapeHtml(s)` | XSS-safe HTML escaping for all catalog output |
| `rpCatalogLifecycleBadge(lifecycle)` | Renders colored badge: REJECTED→🔴, RETIRED→⚪, OBSERVATION→🟡, OFFLINE→⚫ |
| `rpRenderCatalogDisplayMode(lifecycle, lotteryType)` | Fetches `GET /api/replay/strategies?lifecycle_status=X&lottery_type=Y`, renders read-only catalog rows| `rpRenderCatalogDisplayMode(lifecycle, lotteryType)` | Fetches `GET /api/replay/strategies?lifecycle_status=X&lottery_type=Y`, renders rla| `rpRenderCatalogDisplayMode(lifecycle, l ca| `rpRenderCatalogDisch| `rpRenderCatalogDisplayMode(lifecycle, lotteryType)` | Fetches `GET /ast Coverage |
|-----------|-------------|--------------|
| ON| ON| ON| ON| ON| ON| ON| ON| ON| ON| ON|Non-| gression tests pass |
| REJECTED | Catalog rows + 🔴 badge + "無歷史回放資料" disclaimer | ✅ Browser DOM check pass |
| RETIRED | Catalog rows + ⚪ badge + disclaimer | ✅ API + catalog display tests pass |
| OBSERVATION | Catalog rows + 🟡 badge + disclaimer | ✅ API + catalog display tests pass |
| OFFLINE | "coming soon" message + ⚫ badge | ✅ Browser DOM check pass ("coming soon") |

---

## Strategy Registry Status (16 entries)

| Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle | Count | Lifecycle* — all 16 entries covered, ONLINE count ma| Lifecy)
3. **UI strings** — badge labels, disclaimers, XSS escape correctness
4. **ONLINE non-regression** — standard replay path unchanged  
5. **Safety invariants** — no 5. **Safety invariants** — no 5. **Safety invariants** — no 5. **Safety invariants** 
##############################################################################################Lif###########################################################################################res#rved####################################l lifecycles
- ✅ XSS protection: all output through `rpEscapeHtml()`
- ✅ Disclaimer text on every non-ONLINE catalog row

---

## Markers

```
P32_DISPLAY_ONLY_CATALOG_ACCEPTANCE_PASS
P32_POST_MERGE_BROWSER_ACCEPTANCE_PASS
P32_CEO_DEMO_READY
P32_FINAL_MAIN_ACCEPTANCE_COMPLETE
```
