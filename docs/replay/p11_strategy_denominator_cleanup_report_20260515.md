# P1.1 Strategy Denominator Cleanup Report

**Document type**: Operator Classification Report — Read-Only  
**Date**: 2026-05-15  
**Branch**: `docs/p11-strategy-denominator-cleanup-20260515`  
**Input PR**: #103 (P1 Strategy Universe Inventory)  
**Script**: `scripts/p11_strategy_denominator_cleanup_readonly.py`

---

## 1. 本輪目標

對 PR #103 P1 strategy universe inventory 中的 **73 個 artifact-only strategies** 進行 operator classification，
定義出「replay 產品應納入覆蓋率分母的乾淨策略集合」。

**執行規則：**
- ✅ Read-only 分類
- ❌ 未寫 DB
- ❌ 未補 replay row
- ❌ 未跑 backtest
- ❌ 未改策略邏輯
- ❌ 未改 API / UI / backend
- ❌ 未改 registry

---

## 2. 輸入來源

| 來源 | 內容 |
|------|------|
| `outputs/replay/p1_strategy_universe_inventory_20260515.json` (PR #103) | 89 total candidates, 73 artifact-only |
| `outputs/replay/p1_strategy_lifecycle_inventory_20260511.json` | 91 candidates with lifecycle classification, lottery_type, blocked_reason |
| `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json` | 15 promotable candidates (source: prediction_items) |
| `lottery_api/models/replay_strategy_registry.py` | 16 canonical registry strategies |
| `scripts/replay_lifecycle_drift_guard.py` | V3 tombstone 6 IDs |
| sqlite3 DB scan (`strategy_prediction_replays`, `prediction_items`) | Current row counts |

---

## 3. 分類規則

| 分類 | 意義 | 加入分母？ |
|------|------|-----------|
| **PRODUCT_DENOMINATOR** | 曾明確被評估為策略候選、有穩定 strategy_id、具 replay 顯示價值 | ✅ YES |
| **RESEARCH_ARCHIVE** | 研究中間產物、內部實驗標籤、無穩定 product identity | ❌ NO |
| **DUPLICATE_OR_SUPERSEDED** | 已有 canonical 等價版本在 registry 中 | ❌ NO（已計入 canonical 16）|
| **NON_STRATEGY_ARTIFACT** | 非策略的 artifact（report key、tool ID 等）| ❌ NO |
| **NEEDS_OPERATOR_DECISION** | 證據不足，待 operator 手動確認 | ⏳ PENDING |

---

## 4. 統計摘要

| 指標 | 數量 |
|------|------|
| 輸入 artifact-only candidates | **73** |
| → PRODUCT_DENOMINATOR | **53** |
| → RESEARCH_ARCHIVE | **15** |
| → DUPLICATE_OR_SUPERSEDED | **3** |
| → NON_STRATEGY_ARTIFACT | **0** |
| → NEEDS_OPERATOR_DECISION | **2** |
| Canonical registry (unchanged) | 16 |
| **建議 clean denominator** | **69** (16 + 53) |
| Replay COVERED (ONLINE + DB rows) | 6 |
| Replay PARTIAL (REJECTED/OBS + DB rows) | 4 |
| **Coverage rate before cleanup** | 6/89 = **6.7%** |
| **Coverage rate after cleanup** | 6/69 = **8.7%** |
| If NEEDS_OPERATOR_DECISION both → PRODUCT_DENOM | 6/71 = **8.5%** |

---

## 5. 73 Artifact-Only Strategies 分類結果

### 5-A. PRODUCT_DENOMINATOR (53 strategies)

All have `replay_display_eligible: true` in the previous inventory, stable strategy IDs, and identified lottery types.  
Recommended lifecycle: **REJECTED**. Recommended replay display: **FROZEN** (no DB rows).

#### Daily 539 (DAILY_539) — 21 strategies

| Strategy ID | Rejection Evidence (excerpt) |
|-------------|------------------------------|
| `539_3bet_orthogonal` | Signal quality insufficient (permutation p=0.2388) |
| `acb_extremecol_2bet_539` | ACB+ExtremeCol combination evaluated |
| `acb_lag_echo_2bet_539` | ACB+LagEcho combination evaluated |
| `acb_markov_extremecol_3bet_539` | ACB+Markov+ExtremeCol 3-bet evaluated |
| `acb_single_539` | McNemar p=0.0527 marginal, vs StateSpace p=0.194 |
| `bandit_ucb1_2bet_539` | Edge +1.84% << manual MidFreq+ACB (+4.44%) |
| `cold_burst_3bet_539` | Cold burst 3-bet evaluated |
| `condfourier_3bet_539` | Conditional Fourier 3-bet evaluated |
| `conditional_fourier_539` | Conditional Fourier evaluated (distinct from above) |
| `consecutive_pair_detector_539` | Lift 1.08x non-actionable |
| `ewma_539` | EWMA-based strategy evaluated |
| `extreme_col_539` | Base ExtremeCol evaluated |
| `extremecol_1bet_539` | ExtremeCol 1-bet variant evaluated |
| `habit_aware_fourier_v8_539` | Habit-aware Fourier v8 evaluated |
| `lag_echo_1bet_539` | LagEcho 1-bet evaluated |
| `lag_echo_acb_markov_3bet_539` | LagEcho+ACB+Markov 3-bet evaluated |
| `lift_pair_single_539` | 1500p Edge negative (-0.38%) |
| `mab_ucb1_539` | MAB UCB1 evaluated |
| `markov_1bet_539` | z=1.22 (p≈0.11), below significance |
| `midfreq_extremecol_2bet_539` | MidFreq+ExtremeCol 2-bet evaluated |
| `momentum_regime_switching_539` | Momentum regime-switching evaluated |
| `neighbor_acb_2bet_539` | Edge 2.79% vs 5.13% (McNemar p=0.0743) |
| `zone_gap_3bet_539` | Failed permutation test vs random baseline |

#### Big Lotto (BIG_LOTTO) — 17 strategies

| Strategy ID | Rejection Evidence (excerpt) |
|-------------|------------------------------|
| `acb_hot_fourier_3bet_biglotto` | McNemar p=0.545, not better than Triple Strike |
| `apriori_3bet_biglotto` | Apriori association rules 3-bet evaluated |
| `bet2_fourier_expansion_biglotto` | Fourier expansion 2-bet evaluated |
| `biglotto_6bet_zone_residual` | Zone residual 6-bet evaluated |
| `cluster_pivot_biglotto` | Cluster pivot evaluated |
| `cold_complement_biglotto` | Cold complement evaluated |
| `coldpool15_biglotto` | All 3 windows negative: -2.67%, -1.20%, -0.73% |
| `core_satellite_biglotto` | Core-satellite portfolio evaluated |
| `fourier30_markov30_biglotto` | Fourier(30)+Markov(30) combined evaluated |
| `gap_dynamic_threshold_biglotto` | Dynamic gap threshold evaluated |
| `hot_gap_return_biglotto` | Hot-gap return evaluated |
| `hot_stop_rebound_biglotto` | Edge ≈0, z=+0.02, p=0.4924 |
| `hot_streak_override_biglotto` | Hot streak override evaluated |
| `markov_2bet_biglotto` | Markov 2-bet evaluated |
| `markov_repeat_exception_biglotto` | Markov repeat exception evaluated |
| `markov_single_biglotto` | Markov single-number evaluated |
| `multiwindow_fourier_biglotto` | Multi-window Fourier evaluated |
| `neighbor_injection_biglotto` | Neighbour injection evaluated |
| `zone_cascade_guard_biglotto` | Zone cascade guard evaluated |

#### Power Lotto (POWER_LOTTO) — 9 strategies

| Strategy ID | Rejection Evidence (excerpt) |
|-------------|------------------------------|
| `fourier_w100_pp3_power` | Fourier w100 + PP3 Power Lotto evaluated |
| `gap_rebound_powerlotto` | Gap rebound evaluated |
| `p1_conditional_branch_powerlotto` | Follows p1_* product naming convention; formally evaluated |
| `power_echo_boost` | Power echo boost evaluated |
| `power_pp3v2_combined` | PP3v2 combined variant; distinct from power_precision_3bet |
| `power_z3gap_watch` | Z3 gap watch evaluated |
| `special_mab_decay_adjustment_power` | Special MAB decay adjustment evaluated |
| `structural_zone_guard_pp3_power` | Structural zone guard PP3 evaluated |

#### Unknown Lottery Type (UNKNOWN) — 4 strategies

| Strategy ID | Rejection Evidence (excerpt) |
|-------------|------------------------------|
| `short_term_hot_independent_bet` | Short-term hot independent bet evaluated |
| `streak_boost_neighbor_bet1` | Interaction cancellation, perm p=0.1 |
| `zone_constraint_cold_bet2` | Adding zone constraint reduced hit rate (71 < 74) |

---

### 5-B. RESEARCH_ARCHIVE (15 strategies)

These are internal experiment labels and prototype pipeline identifiers.  
**Should NOT appear in the replay product page.** Exclude from denominator.

#### H-series Hypothesis Labels (H001–H008)

| Strategy ID | Lottery Type | Why RESEARCH_ARCHIVE |
|-------------|-------------|----------------------|
| `H001` | UNKNOWN | Internal hypothesis numbering; no stable product name |
| `H002` | UNKNOWN | Parameter sweep label; no stable product name |
| `H003` | UNKNOWN | Parameter sweep label; no stable product name |
| `H004` | UNKNOWN | White noise test label; no stable product name |
| `H005` | UNKNOWN | Lift test label; no stable product name |
| `H006` | UNKNOWN | McNemar test label; no stable product name |
| `H007` | UNKNOWN | Window comparison label; no stable product name |
| `H008` | UNKNOWN | Parameter sweep label; no stable product name |

#### Phase-0 Pipeline Prototypes

| Strategy ID | Why RESEARCH_ARCHIVE |
|-------------|----------------------|
| `p0_neighbor_injection` | Phase-0 internal identifier; superseded by canonical neighbour strategies |
| `p0b_539_3bet_f_cold_fmid` | Phase-0B temp name; Signal Edge = -0.976% (negative) |
| `p0c_539_3bet_f_cold_x2` | Phase-0C temp name; Signal Edge = -0.176% (negative) |

#### Phase-2/3 Pipeline Prototypes

| Strategy ID | Why RESEARCH_ARCHIVE |
|-------------|----------------------|
| `p2_mab_fusion` | Phase-2 internal identifier; lottery_type=UNKNOWN |
| `p3_state_aware` | Phase-3 internal identifier; lottery_type=UNKNOWN |

#### SGP Research Series

| Strategy ID | Why RESEARCH_ARCHIVE |
|-------------|----------------------|
| `sgp_power_017_research` | Explicitly named "research"; SGP sub-graph sweep artifact |
| `sgp_v9_apex_powerlotto` | Version-numbered sweep (v9); Edge = -37.3% vs baseline |

---

### 5-C. DUPLICATE_OR_SUPERSEDED (3 strategies)

These are alternate-naming aliases of canonical registry strategies.  
Already counted in canonical 16 — exclude from denominator to avoid double-counting.

| Strategy ID | Canonical Equivalent | Convention Difference |
|-------------|---------------------|----------------------|
| `shlc_midfreq_power` | `power_shlc_midfreq` (REJECTED, 50 DB rows) | Suffix vs prefix lottery type |
| `ts3_acb_4bet_biglotto` | `biglotto_ts3_acb_4bet` (REJECTED, 50 DB rows) | Suffix vs prefix lottery type |
| `ts3_markov_freq_5bet_biglotto` | `biglotto_ts3_markov_freq_5bet` (REJECTED, 50 DB rows) | Suffix vs prefix lottery type |

---

### 5-D. NEEDS_OPERATOR_DECISION (2 strategies)

Both appeared in `p2_lifecycle_backfill_dry_run_manifest_20260510.json` as `lifecycle_status=ONLINE`  
with `source_evidence=lottery_api/data/lottery_v2.db:prediction_items`,  
indicating they generated real predictions at some point.  
**Currently: 0 rows in any DB table, not in canonical registry.**

| Strategy ID | Risk Flags | Missing Evidence |
|-------------|------------|-----------------|
| `fourier_rhythm_3bet` | was_live_no_tombstone, no_registry_entry | Was ONLINE in p2 dry run (prediction_items), but no current DB rows and no registry entry. Unclear if renamed, retired without tombstone, or false positive. |
| `ts3_regime_3bet` | was_live_no_tombstone, no_registry_entry, possible_ts3_variant | Same as above. May be a variant of canonical ts3 strategies. Operator must determine rename/merge/tombstone history. |

---

## 6. 建議 Clean Denominator

```
Clean denominator = canonical_16 + artifact-only PRODUCT_DENOMINATOR
                  = 16            + 53
                  = 69 strategies
```

**Breakdown of the 69-strategy clean denominator:**

| Category | Count | Lifecycle |
|----------|-------|-----------|
| ONLINE (in canonical, with DB rows) | 6 | ONLINE |
| REJECTED in canonical (with DB rows) | 4 | REJECTED |
| RETIRED in canonical (no DB rows, V3 tombstone) | 5 | RETIRED |
| OBSERVATION in canonical (no DB rows) | 1 | OBSERVATION |
| REJECTED artifact-only (PRODUCT_DENOMINATOR) | 53 | REJECTED (proposed) |
| **Total** | **69** | |

**Excluded from denominator:**
- 15 RESEARCH_ARCHIVE (internal experiment labels)
- 3 DUPLICATE_OR_SUPERSEDED (already counted via canonical)
- 2 NEEDS_OPERATOR_DECISION (pending decision → if both → PRODUCT_DENOM, denominator = 71)

---

## 7. Coverage Rate Before vs After Cleanup

| Metric | Before Cleanup | After Cleanup (clean denom) | If NOD both → PD |
|--------|---------------|---------------------------|-----------------|
| Denominator | 89 | **69** | 71 |
| COVERED (ONLINE+DB) | 6 | 6 | 6 |
| PARTIAL (REJECTED/OBS+DB) | 4 | 4 | 4 |
| COVERED rate | 6/89 = **6.7%** | 6/69 = **8.7%** | 6/71 = 8.5% |
| COVERED+PARTIAL rate | 10/89 = 11.2% | 10/69 = **14.5%** | 10/71 = 14.1% |

**Key insight:** The raw 6.7% was artificially low due to 15 research archives and 3 duplicates inflating the denominator. After cleanup, the true product coverage rate is **8.7%** — still a meaningful gap to address.

---

## 8. NEEDS_OPERATOR_DECISION 清單

### fourier_rhythm_3bet

**Evidence:**
- Appeared in `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json` as `lifecycle_status=ONLINE`
- `source_evidence=lottery_api/data/lottery_v2.db:prediction_items` → was live (generated predictions)
- Currently: 0 rows in `strategy_prediction_replays`, 0 rows in `prediction_items`
- Not in canonical registry

**Options for operator:**
1. **RENAMED** → If this was renamed to a canonical strategy, mark as `DUPLICATE_OR_SUPERSEDED` with `canonical_or_successor_strategy_id=<name>`. Exclude from denominator.
2. **RETIRED without tombstone** → Add tombstone to canonical registry as RETIRED (CODE_MISSING). Becomes PRODUCT_DENOMINATOR (retired live strategy).
3. **FALSE POSITIVE in dry run** → Mark as `RESEARCH_ARCHIVE`. Exclude from denominator.

### ts3_regime_3bet

**Evidence:**
- Same situation as `fourier_rhythm_3bet`
- Name suggests ts3 regime-switching variant — possible relation to `biglotto_ts3_acb_4bet` or `biglotto_ts3_markov_freq_5bet`

**Options for operator:**
1. **MERGED INTO canonical ts3** → Mark as `DUPLICATE_OR_SUPERSEDED` with canonical_or_successor_strategy_id.
2. **RETIRED without tombstone** → Add tombstone to registry.
3. **FALSE POSITIVE in dry run** → Mark as `RESEARCH_ARCHIVE`.

---

## 9. 不應進 Registry 的項目（15 RESEARCH_ARCHIVE）

The following **must not be added** to the canonical registry at any future point
without explicit new product evaluation and governance approval:

| Group | Items |
|-------|-------|
| H-series (8) | H001, H002, H003, H004, H005, H006, H007, H008 |
| Phase-0 prototypes (3) | p0_neighbor_injection, p0b_539_3bet_f_cold_fmid, p0c_539_3bet_f_cold_x2 |
| Phase-2/3 prototypes (2) | p2_mab_fusion, p3_state_aware |
| SGP research series (2) | sgp_power_017_research, sgp_v9_apex_powerlotto |

These should be stored in research logs only (not in registry, not in replay page).

---

## 10. 下一步建議

### Option A — P1.2: Registry Proposal (Recommended first)

Create a registry proposal for the 53 PRODUCT_DENOMINATOR strategies that are not yet in the canonical registry.  
This would establish official REJECTED lifecycle status for these strategies and make them visible in the replay page as `FROZEN` cards.

**P1.2 scope:**
- Add 53 strategies to registry as REJECTED (or confirm exclusion)
- Resolve NEEDS_OPERATOR_DECISION 2 (fourier_rhythm_3bet, ts3_regime_3bet)
- Finalise clean denominator (69 or 71)

**Estimated final state after P1.2:**
- Clean denominator = 69–71
- All PRODUCT_DENOMINATOR strategies appear in replay as FROZEN/NO_DATA
- Coverage rate = 8.7% COVERED (6 ONLINE strategies fully covered)

### Option B — P2: Replay Page Operator Acceptance (can proceed now)

Use canonical 16 as initial denominator for the replay page UI.  
P1.2 cleanup results feed into the "extended REJECTED" view as a separate phase.  
**No blocker** — PR #102 display semantics spec covers all lifecycle states including FROZEN/NO_DATA.

### Recommendation

**P2 can proceed in parallel** using canonical 16.  
**P1.2 should be resolved** before publishing a public-facing coverage rate (otherwise 8.7% will be the published number, not accounting for 53 un-displayed REJECTED strategies).

---

## 11. Safety Confirmation

| Non-goal | Confirmed |
|----------|-----------|
| 未新增策略 | ✅ |
| 未補 replay row | ✅ |
| 未寫 DB | ✅ |
| 未修改 API / UI / backend | ✅ |
| 未跑 backtest | ✅ |
| 未把 retrospective row 說成 live prediction | ✅ |
| 未修改 registry | ✅ |
| 未 merge PR | ✅ |
| JSON valid | ✅ |
| CSV rows = 1 header + 73 data | ✅ |
| No forbidden files (*.db, *.sqlite, *.pid) in diff | ✅ |

---

## Appendix: Source Files Referenced

- `outputs/replay/p1_strategy_lifecycle_inventory_20260511.json` — 91 candidates, lifecycle/lottery_type/blocked_reason
- `outputs/replay/p2_lifecycle_backfill_dry_run_manifest_20260510.json` — 15 promotable candidates from prediction_items
- `lottery_api/models/replay_strategy_registry.py` — 16 canonical strategies
- `scripts/replay_lifecycle_drift_guard.py` — V3 tombstone 6 IDs
- `docs/replay/replay_display_semantics_spec_20260515.md` — Display semantics for all 5 lifecycle states
