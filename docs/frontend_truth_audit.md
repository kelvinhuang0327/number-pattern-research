# Phase V.5 — Frontend Truth Audit & Consistency Enforcement

Generated: 2026-04-17

---

## Executive Summary

All frontend entry points displaying strategy data have been audited and enforced.
**Single source of truth: `validated_status` + `composite_score` from Phase V validation.**

No component is permitted to rank strategies by `edge_300p` or `cp_score` alone.

---

## Surface Scan Results

### Entry Point 1: `src/core/handlers/NextDrawHandler.js`
- **Data source**: `/api/decision/best-strategy-summary` (backend API)
- **Before Phase V.5**: Used `cp_score` as ranking metric; showed `success_rate_300/500/1500`
- **After Phase V.5**: ✅ **COMPLIANT** (updated in Phase V)
  - Shows `validated_status` badge (✅ VALIDATED / ⚠️ WATCH / ❌ REJECTED)
  - Ranks by `composite_score` (VALIDATED priority)
  - Shows 3-window edges: `edge_150p`, `edge_500p`, `edge_1500p`
  - Shows `perm_p`, `mcnemar_p`, `sharpe`
  - Shows `validation_warning` when best is WATCH fallback
  - Detail table sorted by `composite_score` (not CP score)

### Entry Point 2: `src/ui/PredictionTracker.js`
- **Data source**: `/api/tracking/schedule/history` → `detail.current_best_strategies[]` (backend API)
- **Before Phase V.5**: `_renderStrategyStatusBadge()` had no Phase V awareness; slot header showed only `strategy_status` (PRODUCTION/WATCH/ADVISORY_ONLY)
- **Violations found**:
  - `_renderStrategyStatusBadge()` — no `validated_status` / `VALIDATED` / `REJECTED` support
  - `_renderStrategySlot()` — no `validatedBadge`, no `missingDataWarning`
- **After Phase V.5**: ✅ **FIXED**
  - Added `_renderValidatedBadge(validatedStatus, dataComplete)` method
  - Slot headers now show both `strategy_status` AND `validated_status` badge
  - Data completeness guard: if `data_complete === false`, shows ⚠️ 資料不足 with missing fields listed
  - `missingDataWarning` injected into slot body

### Entry Point 3: `lottery_api/engine/prediction_tracker.py`
- **Role**: Provides `current_best_strategies` and `rsm_strategies` to tracking API
- **Before Phase V.5**: **3 violations**:
  1. `_derive_strategy_status()` — old logic only; ignored `validated_status`
  2. `_get_current_best_strategy_refs()` — ranked by `edge_300p` only; missing Phase V fields
  3. `_get_rsm_strategies()` — ranked by `edge_300p` only; missing Phase V fields
- **After Phase V.5**: ✅ **FIXED**
  - `_derive_strategy_status()` — Phase V priority: VALIDATED→PRODUCTION, WATCH→context, REJECTED→ADVISORY_ONLY
  - `_get_current_best_strategy_refs()` — now uses `composite_score` with VALIDATED>WATCH priority; includes `validated_status`, `edge_150p/500p/1500p`, `perm_p`, `mcnemar_p`, `data_complete`, `missing_phase_v_fields`
  - `_get_rsm_strategies()` — same Phase V ranking; includes all Phase V fields
  - Added `_rank_key_phase_v()` helper function used by both

### Entry Point 4: `src/ui/AutoLearningManager.js`
- **Data source**: `/api/auto-learning/evaluate-strategies` (backend API) for evaluation; local computation for `generateDualBetPrediction()`
- **Scope**: AutoLearning Lab section (research tool, separate from main strategy recommendation)
- **Before Phase V.5**: `generateDualBetPrediction()` performs local frontend scoring without Phase V disclaimer; report claimed "best strategy" without validation context
- **Violations found**:
  - `generateDualBetPrediction()` generates predictions locally using frontend strategy ensemble — this is a research lab tool and the output only appears in the AutoLearning section
  - Report shows `bestStrategy.strategy_name` as "best" without Phase V validation context
- **After Phase V.5**: ✅ **FIXED**
  - Added explicit disclaimer banner in report: "此預測使用自動學習評估策略（獨立實驗室功能），與首頁「最佳策略」（Phase V 三窗口驗證策略）無關。僅供研究參考。"
  - Note: `generateDualBetPrediction` local computation is acceptable for the lab context but clearly labeled as separate from Phase V validated strategies

### Entry Point 5: `lottery_api/routes/decision.py` — `/api/decision/best-strategy-summary`
- **Before Phase V.5**: Used CP score ranking, returned `success_rate_300/500/1500` (some from sim files)
- **After Phase V** (Phase V fix, not V.5): ✅ **COMPLIANT**
  - Returns `validated_status`, `composite_score`, `edge_150p/500p/1500p`, `perm_p`, `mcnemar_p`, `sharpe`
  - VALIDATED>WATCH>REJECTED priority
  - Shows `validation_warning` for WATCH fallback

### Entry Point 6: `lottery_api/routes/prediction.py` — `_derive_strategy_status()`
- **After Phase V** (Phase V fix): ✅ **COMPLIANT**
  - Uses `validated_status` when present; legacy fallback only when absent

---

## Data Source Verification

| Component | Data Source | Frontend Computation? | Compliant |
|-----------|-------------|----------------------|-----------|
| NextDrawHandler strategy summary | `/api/decision/best-strategy-summary` | No | ✅ |
| PredictionTracker slot status | `/api/tracking/schedule/history` | No | ✅ |
| prediction_tracker `current_best_strategies` | `strategy_states_*.json` via `_get_current_best_strategy_refs` | No | ✅ |
| prediction_tracker `rsm_strategies` | `strategy_states_*.json` via `_get_rsm_strategies` | No | ✅ |
| AutoLearning evaluation ranking | `/api/auto-learning/evaluate-strategies` | No (API) | ✅ with disclaimer |
| AutoLearning dual-bet prediction | Local ensemble scoring | Yes (lab tool) | ✅ with disclaimer |

---

## Cache / State Audit

- **`ApiClient.js`**: In-memory Map cache (session-scoped, 30s timeout). Does not cache strategy endpoint data. No `cache.set` calls for strategy endpoints. ✅
- **`NextDrawHandler._lastData`**: Session-only `null`-initialized cache. Cleared on `onRefresh()`. Does not persist across sessions. ✅
- **localStorage/sessionStorage**: No strategy data stored. ✅
- **IndexedDB**: No strategy ranking data stored. ✅

---

## Badge Standardization

All Phase V badges now use consistent styling across all entry points:

| Status | Label | Color |
|--------|-------|-------|
| VALIDATED | ✅ 已完整驗證 | `#00c864` (green) |
| WATCH | ⚠️ 觀察中（未完全驗證） | `#ffb400` (amber) |
| REJECTED | ❌ 未通過驗證 | `#e74c3c` (red) |
| data_complete=false | ⚠️ 資料不足 | `#e74c3c` |

---

## Regression Test — API vs Backend Truth

```
DAILY_539:
  n=1: acb_1bet            WATCH      cs=0.0349  ✅ data_complete
  n=2: midfreq_acb_2bet    VALIDATED  cs=0.0575  ✅ data_complete
  n=3: acb_markov_midfreq  VALIDATED  cs=0.0705  ✅ data_complete
  n=5: f4cold_5bet         VALIDATED  cs=0.0936  ✅ data_complete

BIG_LOTTO:
  n=2: regime_2bet         WATCH      cs=0.0234  ✅ data_complete
  n=3: ts3_regime_3bet     WATCH      cs=0.0182  ✅ data_complete
  n=4: p1_deviation_4bet   VALIDATED  cs=0.0343  ✅ data_complete
  n=5: p1_dev_sum5bet      WATCH      cs=0.0386  ✅ data_complete

POWER_LOTTO:
  n=2: midfreq_fourier_2bet    WATCH  cs=0.0279  ✅ data_complete
  n=3: midfreq_fourier_mk_3bet WATCH  cs=0.0347  ✅ data_complete
  n=4: pp3_freqort_4bet        WATCH  cs=0.0338  ✅ data_complete
  n=5: orthogonal_5bet         WATCH  cs=0.0419  ✅ data_complete
```

All 3 APIs return consistent data. No mismatch between pages.

---

## Fixes Applied

| File | Violation | Fix |
|------|-----------|-----|
| `lottery_api/engine/prediction_tracker.py` | `_derive_strategy_status()` used old logic | Updated to Phase V validated_status priority |
| `lottery_api/engine/prediction_tracker.py` | `_get_current_best_strategy_refs()` ranked by edge_300p | Replaced with composite_score + VALIDATED>WATCH priority |
| `lottery_api/engine/prediction_tracker.py` | `_get_current_best_strategy_refs()` missing Phase V fields | Added validated_status, edge_150p/500p/1500p, perm_p, mcnemar_p, data_complete |
| `lottery_api/engine/prediction_tracker.py` | `_get_rsm_strategies()` ranked by edge_300p | Replaced with Phase V ranking |
| `lottery_api/engine/prediction_tracker.py` | `_get_rsm_strategies()` missing Phase V fields | Added all Phase V fields |
| `src/ui/PredictionTracker.js` | `_renderStrategyStatusBadge()` no Phase V support | Added `_renderValidatedBadge()` method |
| `src/ui/PredictionTracker.js` | Strategy slots missing validation badge | Injected `validatedBadge` + `missingDataWarning` in all slot variants |
| `src/ui/AutoLearningManager.js` | Local computation presented without Phase V context | Added explicit disclaimer: "獨立實驗室功能，與首頁最佳策略無關" |

---

## Remaining Risks

| Risk | Severity | Status |
|------|----------|--------|
| AutoLearning `generateDualBetPrediction` does local frontend computation | Low | Mitigated with disclaimer; this is a research lab tool, output does not affect main strategy recommendation |
| POWER_LOTTO has no VALIDATED strategies (all WATCH) | Medium | Expected — POWER_LOTTO has fewer draws (1902) making 150-period window perm_p harder to reach; `validation_warning` shown to user |
| BIG_LOTTO has only 1 VALIDATED strategy (p1_deviation_4bet) | Medium | 11 strategies evaluated; most lack significant 150p edge; `validation_warning` shown for WATCH fallbacks |

---

## Success Criteria Verification

- [x] No frontend component uses `edge_300p` alone for ranking
- [x] All best strategies are VALIDATED or clearly marked with ⚠️ WATCH / validation_warning
- [x] All pages show consistent data (same backend source)
- [x] No stale or local ranking logic exists (except AutoLearning lab with disclaimer)
- [x] `validated_status` is single source of truth for all strategy displays
- [x] Data completeness guard implemented (missing fields → ⚠️ 資料不足)
