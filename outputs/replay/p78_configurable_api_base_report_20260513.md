# P78 Configurable API Base — Implementation Report

**Date**: 2026-05-13  
**Branch**: `frontend/p78-configurable-api-base-20260513`  
**Operator**: P78 Configurable API Base Implementation Agent  
**Verdict**: `P78_CONFIGURABLE_API_BASE_IMPLEMENTED`

---

## 1. Round Objective

1. Implement `window.API_BASE` configurable variable in `index.html`
2. Fix local dev same-origin gap (lifecycle table 404 from port 8081)
3. Eliminate Playwright fetch monkey-patch requirement
4. Preserve production same-origin default
5. Attach P1 retrospective regeneration candidate inventory (CEO requirement)

---

## 2. Root Cause Recap (P77)

`index.html` used `const BASE = '/api/replay'` (hardcoded relative URL). `python3 -m http.server 8081` is a pure static file server with no proxy capability — all `/api/...` fetch calls from port 8081 returned 404. P76 browser QA required a Playwright `addInitScript` fetch monkey-patch workaround.

---

## 3. Implementation Summary

**File changed**: `index.html` (3 lines modified)

### Change 1: Replace `const BASE` declaration (line 2706)

**Before**:
```javascript
const BASE = '/api/replay';
```

**After**:
```javascript
// P78: configurable API base — set window.API_BASE to the backend origin for local dev
// Production default: window.API_BASE is undefined → BASE resolves to '/api/replay' (same-origin)
const API_BASE = (typeof window !== 'undefined' && window.API_BASE ? String(window.API_BASE) : '').replace(/\/$/, '');
const BASE = `${API_BASE}/api/replay`;
```

### Change 2: Hardcoded fetch call — summary endpoint

**Before**: `fetch('/api/replay/summary?lottery_type=' + ...)`  
**After**: `` fetch(`${API_BASE}/api/replay/summary?lottery_type=` + ...) ``

### Change 3: Hardcoded fetch call — lifecycle endpoint

**Before**: `fetch('/api/replay/strategy-lifecycle')`  
**After**: `` fetch(`${API_BASE}/api/replay/strategy-lifecycle`) ``

---

## 4. Production Default Verification

JS test (Node.js, 3 cases):

| Case | `window.API_BASE` input | `BASE` result | Status |
|------|------------------------|---------------|--------|
| Production default | `undefined` | `/api/replay` | ✅ PASS |
| Local dev no trailing slash | `'http://localhost:8002'` | `http://localhost:8002/api/replay` | ✅ PASS |
| Local dev with trailing slash | `'http://localhost:8002/'` | `http://localhost:8002/api/replay` | ✅ PASS |

No `localhost:8002` hardcoded in `index.html` source. ✅

---

## 5. Local Dev API Base Verification

Static checks:
- `window.API_BASE` reference: line 2708 ✅
- `const API_BASE`: line 2708 ✅
- `const BASE`: line 2709 ✅
- No hardcoded `localhost:8002` in `index.html` source ✅

---

## 6. Browser Smoke Test Result: PASS ✅

**Method**: `page.addInitScript(() => { window.API_BASE = 'http://localhost:8002'; })`  
**No fetch monkey-patch applied** (`fetchPatched: false` confirmed by DOM eval)

| Metric | Result |
|--------|--------|
| `#rp-lc-table-wrap` display | `block` ✅ |
| `#rp-lc-error` display | `none` ✅ |
| Truth badges | 16 ✅ |
| Table rows | 26 ✅ |
| `window.API_BASE` value | `http://localhost:8002` ✅ |
| Fetch monkey-patch needed | `false` ✅ **P78 goal achieved** |

Screenshot: `outputs/relay/p78_browser_smoke_lifecycle_20260513.png`

---

## 7. Safety Hash Verification

| File | Hash | Status |
|------|------|--------|
| `lottery_api/data/lottery_v2.db` | `de0e27bb800bc7183773a0dc596d66b8` | ✅ UNCHANGED |
| `lottery_api/models/replay_strategy_registry.py` | `3ea71cfc20c882714f3824ad68202f6e` | ✅ UNCHANGED |

---

## 8. P1 Retrospective Regeneration Candidate Inventory

*CEO-mandated read-only inventory. No execution, no DB write, no registry mutation.*

### 8.1 Registry Adapter Check Results

All 16 canonical strategies audited via `reg.get_adapter()` dry-check and `tools/predict_*.py` file scan.

| strategy_id | lifecycle | adapter class | get_one_bet | predict tool | bucket |
|------------|-----------|---------------|-------------|--------------|--------|
| `power_precision_3bet` | ONLINE | `_PowerPrecision3BetAdapter` | ✅ | `tools/predict_power_precision_3bet.py` | **EXECUTABLE_NOW** |
| `power_orthogonal_5bet` | ONLINE | `_PowerOrthogonal5BetAdapter` | ✅ | `tools/predict_power_orthogonal_5bet.py` | **EXECUTABLE_NOW** |
| `biglotto_triple_strike` | ONLINE | `_BigLottoTripleStrikeAdapter` | ✅ | `tools/predict_biglotto_triple_strike.py` | **EXECUTABLE_NOW** |
| `biglotto_deviation_2bet` | ONLINE | `_BigLottoDeviation2BetAdapter` | ✅ | `tools/predict_biglotto_deviation_2bet.py` | **EXECUTABLE_NOW** |
| `daily539_f4cold` | ONLINE | `_Daily539F4ColdAdapter` | ✅ | `tools/predict_539_5bet_f4cold.py` | **EXECUTABLE_NOW** |
| `daily539_markov_cold` | ONLINE | `_Daily539MarkovColdAdapter` | ✅ | `tools/predict_539_markov_cold.py` | **EXECUTABLE_NOW** |
| `biglotto_ts3_acb_4bet` | REJECTED | no adapter | ❌ | none | **CODE_MISSING** |
| `biglotto_ts3_markov_freq_5bet` | REJECTED | no adapter | ❌ | none | **CODE_MISSING** |
| `power_shlc_midfreq` | REJECTED | no adapter | ❌ | none | **CODE_MISSING** |
| `p1_deviation_2bet_539` | REJECTED | no adapter | ❌ | none | **CODE_MISSING** |
| `acb_1bet` | RETIRED | no adapter | ❌ | none | **CODE_MISSING** |
| `acb_markov_midfreq` | RETIRED | no adapter | ❌ | none | **CODE_MISSING** |
| `acb_markov_midfreq_3bet` | RETIRED | no adapter | ❌ | none | **CODE_MISSING** |
| `midfreq_acb_2bet` | RETIRED | no adapter | ❌ | none | **CODE_MISSING** |
| `midfreq_fourier_2bet` | RETIRED | no adapter | ❌ | none | **CODE_MISSING** |
| `h6_gate_mk20_ew85` | OBSERVATION | no adapter | ❌ | none | **CODE_MISSING** |

### 8.2 Bucket Summary

| Bucket | Count | Strategy IDs |
|--------|-------|-------------|
| **EXECUTABLE_NOW** | **6** | power_precision_3bet, power_orthogonal_5bet, biglotto_triple_strike, biglotto_deviation_2bet, daily539_f4cold, daily539_markov_cold |
| **EXECUTABLE_WITH_FIX** | **0** | — |
| **CODE_MISSING** | **10** | biglotto_ts3_acb_4bet, biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, p1_deviation_2bet_539, acb_1bet, acb_markov_midfreq, acb_markov_midfreq_3bet, midfreq_acb_2bet, midfreq_fourier_2bet, h6_gate_mk20_ew85 |
| **TOMBSTONE** | **0** | — |

### 8.3 Artifact Notes

REJECTED strategies have JSON artifacts in `rejected/` (not Python adapters):
- `rejected/ts3_acb_4bet_biglotto.json`
- `rejected/ts3_markov_freq_5bet_biglotto.json`
- `rejected/shlc_midfreq_power.json`
- `rejected/p1_deviation_2bet_539.json`

RETIRED `acb_*` and `midfreq_*` strategies: no code found. Likely pre-registry era strategies with no surviving implementation.

`h6_gate_mk20_ew85` (OBSERVATION): task result artifact at root `task_result_H6_gate_mk20_ew85.json`, no Python adapter or predict tool.

`biglotto_ts3_acb_4bet` / `biglotto_ts3_markov_freq_5bet`: strategy config in `strategies/big_lotto/4bet_ts3_markov_w30/` and `strategies/big_lotto/5bet_ts3_markov_freq/` (config/json only, no Python adapter).

### 8.4 P1 Conclusion

**EXECUTABLE_NOW = 6** (all 6 ONLINE strategies). These are the only candidates for P1 retrospective regeneration without additional code work. All have:
- `get_adapter(strategy_id)` → returns adapter with `get_one_bet()` callable
- Corresponding `tools/predict_*.py` entry point
- Matching lifecycle status = ONLINE

---

## 9. Known Limitations

1. **`window.API_BASE` must be set before page JS** — operators using the UI directly must either: (a) add `<script>window.API_BASE='http://localhost:8002'</script>` before opening index.html, or (b) use browser console before page load (not possible in standard flow). The `addInitScript` Playwright approach remains the cleanest automated QA method. For **manual local dev**, a `dev-config.js` file that sets `window.API_BASE` and is conditionally included would be the next improvement.
2. **CORS still required for cross-origin calls** — backend `allow_origins: ["*"]` is already set. Production same-origin deployment (relative URL) doesn't need CORS.
3. **10 of 16 strategies have no Python adapter** — P1 regeneration scope is limited to the 6 ONLINE strategies.
4. **`outputs/relay` typo** (PR #90) — P76 evidence was stored in `outputs/relay/` instead of `outputs/replay/`. Deferred to P79 docs cleanup.

---

## 10. Next Prompt — P1 Dry-Run Regeneration

> **P1 Mission**: Run retrospective regeneration for the 6 EXECUTABLE_NOW ONLINE strategies.
>
> Entry points:
> - `power_precision_3bet` → `tools/predict_power_precision_3bet.py`
> - `power_orthogonal_5bet` → `tools/predict_power_orthogonal_5bet.py`
> - `biglotto_triple_strike` → `tools/predict_biglotto_triple_strike.py`
> - `biglotto_deviation_2bet` → `tools/predict_biglotto_deviation_2bet.py`
> - `daily539_f4cold` → `tools/predict_539_5bet_f4cold.py`
> - `daily539_markov_cold` → `tools/predict_539_markov_cold.py`
>
> For each strategy:
> 1. Call `reg.get_adapter(strategy_id).get_one_bet(draw_date, historical_data)` for a dry-run date
> 2. Verify output schema (list of ints, correct length for lottery type)
> 3. Do NOT write to DB, do NOT create replay rows
> 4. Report: adapter output sample + any errors
> 5. Mark as P1_DRY_RUN_PASS or P1_DRY_RUN_FAIL per strategy

---

## 11. Final Markers

- ✅ P78_BASELINE_VERIFIED — main `d438fb6`
- ✅ P78_CONFIGURABLE_API_BASE_IMPLEMENTED
- ✅ P78_PRODUCTION_DEFAULT_VERIFIED — 3/3 JS cases PASS
- ✅ P78_LOCAL_DEV_API_BASE_VERIFIED — browser smoke PASS, no fetch monkey-patch
- ✅ P78_DB_UNCHANGED — `de0e27bb800bc7183773a0dc596d66b8`
- ✅ P78_REGISTRY_UNCHANGED — `3ea71cfc20c882714f3824ad68202f6e`
- ✅ P78_REPORT_CREATED
- ✅ P78_P1_CANDIDATE_INVENTORY_ATTACHED — EXECUTABLE_NOW=6, CODE_MISSING=10
- ⏳ P78_PR_OPENED — (Stage 10)
- ⏳ P78_READY_FOR_REVIEW
