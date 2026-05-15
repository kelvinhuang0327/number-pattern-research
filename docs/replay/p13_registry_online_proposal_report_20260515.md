# P1.3 Registry ONLINE Proposal Report
**Date:** 2026-05-15  
**Branch:** `chore/p13-registry-online-proposal-20260515`  
**Source PR:** #105 (P1.2 Operator Decision Resolution)  
**Classification:** P13_REGISTRY_ONLINE_PROPOSAL_READY

---

## 1. 本輪目標

將 P1.2 已確認的兩個 live production strategies 加入 replay canonical registry：

1. `fourier_rhythm_3bet` (POWER_LOTTO)
2. `ts3_regime_3bet` (BIG_LOTTO)

目標：
- 將 canonical registry 從 16 擴充到 18
- 不產生 replay rows
- 不跑 backfill
- 不寫 DB
- 不改策略邏輯
- 不改 UI/API/backend runtime behavior

---

## 2. P1.2 Evidence Summary

P1.2 (PR #105, `docs/p12-operator-decision-resolution-20260515`) 確認：

| 策略 | 決定 | lottery_type | 緊急程度 |
|------|------|-------------|---------|
| fourier_rhythm_3bet | PRODUCT_DENOMINATOR_ONLINE_CANDIDATE | POWER_LOTTO | HIGH |
| ts3_regime_3bet | PRODUCT_DENOMINATOR_ONLINE_CANDIDATE | BIG_LOTTO | HIGH |

**P1.1 NOD root cause:** DB scanner 只查 `strategy_id` 欄位，但 `prediction_items`/`prediction_runs` 使用 `strategy_name` 欄位。兩個策略的 active rows 從未被 P1.1 scan 到。

**Active DB rows (as of P1.2):**
- `fourier_rhythm_3bet`: prediction_run=168 VALID, 3 PENDING items (1072-1074)
- `ts3_regime_3bet`: prediction_runs=167(VALID)/174(VALID)/175(RECONSTRUCTED), 9 PENDING items (1069-1095)

---

## 3. Registry Changes

**File:** `lottery_api/models/replay_strategy_registry.py`

### Before P1.3
- 6 ONLINE adapters
- 10 non-ONLINE stubs (REJECTED/RETIRED/OBSERVATION)
- Total: 16 entries

### After P1.3
- 8 ONLINE adapters (+2)
- 10 non-ONLINE stubs (unchanged)
- Total: 18 entries

**New exception class added:** `AdapterBindingPending` — for ONLINE strategies whose predict_func is not yet bound in codebase. Distinct from `LifecycleNotExecutable` (which is for non-ONLINE strategies).

---

## 4. fourier_rhythm_3bet Entry Details

| Field | Value |
|-------|-------|
| strategy_id | fourier_rhythm_3bet |
| strategy_name | 威力彩 Fourier Rhythm 3注 |
| strategy_version | v0.1 |
| lottery_type | POWER_LOTTO |
| lifecycle_status | ONLINE |
| min_history | 100 |
| adapter_binding | BOUND |

**Predict function binding:**
```
tools.power_fourier_rhythm.fourier_rhythm_predict(history, n_bets=3, window=500)
```

**Evidence chain:**
1. RSM engine: `rolling_strategy_monitor.py:749` — `fourier_rhythm_3bet` with `fourier_3bet` callable
2. `tools/rsm_bootstrap.py:60` — same binding in bootstrap
3. DB: `prediction_runs.id=168` (VALID, target_draw=115000034, 2026-04-27)
4. DB: `prediction_items.id=1072,1073,1074` (PENDING)
5. P2 dry run: PROMOTABLE, `runtime_write_allowed=false`
6. `memory/lessons.md L94`: "ONLINE, recheck in 30 draws"

**Adapter class:** `_PowerFourierRhythm3BetAdapter` — fully executable, wraps `fourier_rhythm_predict`.

---

## 5. ts3_regime_3bet Entry Details

| Field | Value |
|-------|-------|
| strategy_id | ts3_regime_3bet |
| strategy_name | 大樂透 TS3+Regime 3注 |
| strategy_version | v0.1 |
| lottery_type | BIG_LOTTO |
| lifecycle_status | ONLINE |
| min_history | 100 |
| adapter_binding | PENDING (P1.4) |

**Adapter binding status: PENDING**

The predict_func for `ts3_regime_3bet` was NOT found in the current `tools/` codebase. Searches conducted:
- `grep -rn "ts3_regime\|regime_3bet"` across all `.py` files — 0 results in tools/
- No `predict_biglotto_ts3_regime*.py` file exists
- RSM `get_big_lotto_strategies()` does not list `ts3_regime_3bet`
- `rsm_bootstrap.get_big_lotto_strategies_inline()` does not list `ts3_regime_3bet`

The strategy was used as a production baseline but its callable was defined inline outside the current tracked codebase, or in a now-deleted/moved module.

**Evidence chain:**
1. DB: `prediction_runs.id=167,174,175` — 167 and 174 VALID, 175 RECONSTRUCTED
2. DB: `prediction_items.id=1069-1071` (run 167), `1090-1092` (run 174), `1093-1095` (run 175)
3. P2 dry run: all 9 items PROMOTABLE
4. `memory/lessons.md`: "繼續使用 regime_2bet/ts3_regime_3bet/p1_dev_sum5bet 生產策略"
5. `strategy_catalog_inventory_20260512.md:77`: listed as BIG_LOTTO monitoring reference strategy

**Adapter class:** `_BigLottoTs3Regime3BetPendingAdapter` — metadata registered, `get_one_bet()` raises `AdapterBindingPending` until P1.4 resolution.

**run_id=175 RECONSTRUCTED risk:** The RECONSTRUCTED snapshot source for prediction_run 175 means the snapshot was not taken at prediction time but reconstructed after the fact. This introduces audit risk — the numbers may not exactly reflect what was predicted pre-draw. This is documented but does NOT block registry addition. P2 backfill must document this risk per item.

---

## 6. Tests Added / Updated

### New test file
`tests/test_replay_strategy_registry_online_candidates.py` — 44 tests covering:
- Registry count = 18
- Both strategy IDs exist with ONLINE status
- Correct lottery_type for each
- No tombstone classification
- fourier_rhythm_3bet is get_adapter()-accessible and ONLINE-executable
- ts3_regime_3bet raises `AdapterBindingPending` (not `LifecycleNotExecutable`)
- All 16 original entries unchanged
- No DB writes (structural check, no module reload to avoid isolation issues)
- P1.3 governance metadata correctness

### Updated test file
`tests/test_replay_strategy_lifecycle_registry.py` — updated:
- `ONLINE_IDS` frozenset: 6 → 8 (added fourier_rhythm_3bet, ts3_regime_3bet)
- Docstring: updated to reflect 8 ONLINE strategies post-P1.3
- `test_list_strategies_online_filter_returns_all_six` → `...all_eight`

### Test results
| Test file | Result |
|-----------|--------|
| test_replay_strategy_registry_online_candidates.py | 44 PASS |
| test_replay_lifecycle_drift_guard.py | PASS |
| test_replay_truth_level_contract.py | PASS |
| test_replay_api_contract.py | PASS |
| test_replay_strategy_lifecycle_registry.py | 22 PASS |
| **Total** | **153 PASS, 0 FAIL** |

---

## 7. Risk Notes

### fourier_rhythm_3bet
- **Risk level: LOW**
- Fully bound, tested, callable confirmed in production RSM
- 3 PENDING items await P2 backfill promotion

### ts3_regime_3bet
- **Risk level: MEDIUM**
- Adapter binding PENDING — replay generation blocked until P1.4
- run_id=175 RECONSTRUCTED snapshot elevated audit risk
- 9 PENDING items cannot be promoted until P1.4 resolves callable

### General
- This PR only adds registry entries — no strategy logic touched
- `AdapterBindingPending` is a new exception type that is NOT `LifecycleNotExecutable`; callers must handle it separately
- Drift guard baseline was NOT modified (18-count change does not affect drift guard since drift guard monitors lifecycle counts, not total adapter counts)

---

## 8. Why No Backfill Was Run

Per P1.3 scope:
1. Registry proposal must precede backfill — you cannot backfill strategies that have no registry entry
2. P2 backfill requires `runtime_write_allowed=true` — not set in this PR
3. `ts3_regime_3bet` adapter binding is still PENDING — backfill cannot execute without a callable
4. Both strategies' PENDING items require operator review before promotion

P2 backfill remains the next step after P1.4 resolves ts3_regime_3bet adapter binding.

---

## 9. Next Step Recommendation

**P1.4 — ts3_regime_3bet Adapter Binding Resolution**

Action required:
1. Locate or reconstruct the `ts3_regime_3bet` predict_func
2. Options:
   a. Check git history for deleted/renamed files containing `ts3_regime` predict logic
   b. Check if it was an inline closure inside a now-deleted script
   c. Reconstruct from known components: TS3 triple strike + regime-switching (detect_regime from backtest_biglotto_enhancements.py)
3. Once callable is confirmed: replace `_BigLottoTs3Regime3BetPendingAdapter` with a full adapter
4. Run P2 backfill for `ts3_regime_3bet` items (runs 167, 174, 175)
5. Update drift guard baseline if needed

**After P1.4:**
- Run P2 backfill for both strategies
- Expected COVERED count: 6 → 8 (11.3%)

---

## 10. Safety Confirmation

| Check | Result |
|-------|--------|
| DB written | NO |
| Replay rows generated | NO |
| Backfill run | NO |
| Strategy logic changed | NO |
| API/UI/backend changed | NO |
| Existing registry entries removed | NO |
| PR merged | NO |
| Forbidden artifacts (.db, .sqlite, .pid) | NONE |
