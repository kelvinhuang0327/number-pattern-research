# P25a — Full Replay Page Browser Verification

**Date**: 2026-05-21  
**Branch**: `p25a-full-replay-page-browser-verification`  
**Classification**: `P25A_FULL_REPLAY_PAGE_BROWSER_VERIFICATION_READY`

---

## Summary

Full browser E2E verification of the Lotto Insight Platform replay page
(`http://127.0.0.1:8081/`). Tested all 3 lottery types, all 8 ONLINE strategies,
period presets, cross-switching, pagination, hit-rate summary, and lifecycle registry
using Playwright via the gstack browser tooling.

All tests passed. Both console errors triaged as non-blocking.

---

## Environment

| Setting | Value |
|---------|-------|
| Replay page URL | `http://127.0.0.1:8081/` |
| API base | `http://127.0.0.1:8002` |
| API_BASE injection | `window.API_BASE = 'http://127.0.0.1:8002'` via `addInitScript` |
| Browser tool | Playwright (gstack `run_playwright_code`) |
| Browser pageId | `81e7db87-0eb3-4bea-9037-37123927fe95` |
| DB | `lottery_api/data/lottery_v2.db` |
| Production rows baseline | **12,460** |

---

## Console Error Triage

### Error A — `method-description-card` missing

- **Source**: `src/core/App.js:981` `updateMethodDescription()`
- **Root cause**: DOM elements `#method-description-card`, `#method-icon`,
  `#method-title`, `#method-description` exist only in
  `tools/web-demos/index.html:356`, not in root `index.html`.
  Function is called at startup when `simulationMethodSelect` initializes.
- **Scope**: Simulation section only — no impact on replay UI.
- **Verdict**: **NON-BLOCKING**

### Error B — 404 `/api/performance/regime`

- **Source**: `src/ui/UIManager.js:19` `updateWaterline()`
- **Root cause**: Uses relative path `/api/performance/regime` which hits port 8081
  (Python HTTP server) instead of port 8002 (FastAPI). Route IS defined at
  `lottery_api/routes/prediction.py:1788`. `ApiClient.js` uses the correct
  absolute URL but `UIManager.js` bypasses it.
- **Scope**: Waterline widget display only — graceful failure in `try/catch`,
  no crash, no replay data loss.
- **Verdict**: **NON-BLOCKING**

---

## E2E Test Results

### Lottery Type Queries

| Lottery Type | Total Rows | Strategy Options | HTTP Errors | Status |
|---|---|---|---|---|
| BIG_LOTTO | 4,640 | 6 | None | ✅ PASS |
| POWER_LOTTO | 4,640 | 6 | None | ✅ PASS |
| DAILY_539 | 3,180 | 9 | None | ✅ PASS |

### All 8 ONLINE Strategy Row Counts

| Strategy ID | Lottery | Expected (P24) | Actual | Match |
|---|---|---|---|---|
| `biglotto_deviation_2bet` | BIG_LOTTO | 1,570 | 1,570 | ✅ |
| `biglotto_triple_strike` | BIG_LOTTO | 1,570 | 1,570 | ✅ |
| `ts3_regime_3bet` | BIG_LOTTO | 1,500 | 1,500 | ✅ |
| `fourier_rhythm_3bet` | POWER_LOTTO | 1,500 | 1,500 | ✅ |
| `power_orthogonal_5bet` | POWER_LOTTO | 1,570 | 1,570 | ✅ |
| `power_precision_3bet` | POWER_LOTTO | 1,570 | 1,570 | ✅ |
| `daily539_f4cold` | DAILY_539 | 1,590 | 1,590 | ✅ |
| `daily539_markov_cold` | DAILY_539 | 1,590 | 1,590 | ✅ |

**Total ONLINE rows: 12,460 — exact governance baseline confirmed.**

### Period Presets

| Preset | Result | Status |
|---|---|---|
| 100期 | "前 100 期 / 共 100 筆" — exactly 100 rows | ✅ PASS |
| 500期 | Date-constrained → returns available rows in window | ✅ PASS |
| 1000期 | Date-constrained → returns available rows in window | ✅ PASS |
| 1500期 | Date-constrained → returns available rows in window | ✅ PASS |

### Cross-Switching Matrix

| Scenario | Status |
|---|---|
| BIG_LOTTO → POWER_LOTTO → DAILY_539 (full cycle) | ✅ PASS |
| DAILY_539 → BIG_LOTTO | ✅ PASS |
| POWER_LOTTO strategy switch (3 strategies) | ✅ PASS |
| BIG_LOTTO strategy → DAILY_539 switch | ✅ PASS |
| 1500期 preset → switch lottery type | ✅ PASS |

### Pagination

| Test | Result | Status |
|---|---|---|
| Next page (`rp-next-btn`) | Page 1→2, period 115000121→115000096 | ✅ PASS |
| Prev page (`rp-prev-btn`) | Page 2→1, back to period 115000121 | ✅ PASS |

### Hit Rate Summary

| Test | Result | Status |
|---|---|---|
| `rp-summary-btn` click | `rp-summary-cards` rendered | ✅ PASS |
| Summary content | "📊 命中率摘要（歷史回放）" + strategy hit-rate table | ✅ PASS |

### Lifecycle Registry (`rp-lc-table`)

| Lifecycle | Count |
|---|---|
| ONLINE (TruthLevel: LIVE) | 8 |
| REJECTED | 4 |
| OBSERVATION | 1 |
| RETIRED | 5 |
| **Total** | **18** |

Matches P24 Full Strategy Universe Inventory exactly. ✅

### Freshness Coverage Table

| Lottery | Run | Status | Draws | Success | Coverage |
|---|---|---|---|---|---|
| 大樂透 | #5 | DONE | 100 | 100% | ⚠️ LIMITED |
| 今彩539 | #7 | DONE | 100 | 100% | ⚠️ LIMITED |
| 威力彩 | #6 | DONE | 100 | 100% | ⚠️ LIMITED |

`LIMITED` is expected — freshness runs cover 100 draws per execution (not full 1500).
All runs are `DONE` with 100% success rate. ✅

---

## Known Non-Blockers (Pre-existing)

### NB-01: `App.js updateMethodDescription()` console error

Missing simulation DOM elements in root `index.html`. Simulation section is separate
from replay UI. Future P26 cleanup PR can guard with `if (el) { … }`.

### NB-02: `UIManager.js` relative URL for waterline

`fetch('/api/performance/regime')` should use the `API_BASE_URL` from `ApiClient.js`.
Waterline widget silently shows empty data. Future fix: pass base URL into `UIManager`.

---

## Governance Checks

| Check | Result |
|---|---|
| DB rows unchanged | ✅ 12,460 |
| `✅ Causal OK` on all sampled rows | ✅ Verified |
| No new strategies added | ✅ |
| No replay generation | ✅ |
| No production DB writes | ✅ |

---

## Final Classification

```
P25A_FULL_REPLAY_PAGE_BROWSER_VERIFICATION_READY
```

The replay page is fully operational across all 3 lottery types with all 8 ONLINE
strategies, correct pagination, lifecycle registry, and hit-rate summary verified via
live browser E2E on 2026-05-21.
