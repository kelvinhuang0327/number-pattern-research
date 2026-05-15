# P2 Controlled Replay Backfill Dry-run Report — ts3_regime_3bet

**Date:** 2026-05-15  
**Branch:** `chore/p2-controlled-replay-backfill-dryrun-20260515`  
**Final Classification:** `P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED`  
**Blocked Reason:** PR #106 and PR #107 not yet merged to main  
**Dry-run Mode:** DRY_RUN ONLY — no DB writes  

---

## 1. 本輪目標

P1.4 (PR #107) 已解決 `ts3_regime_3bet` adapter binding (SAFE_RECONSTRUCTION)。
P2 目標是針對 9 個 PENDING `prediction_items` 執行 controlled replay backfill dry-run，驗證：

1. PR #106 / PR #107 是否已 merge 至 main（prerequisite）
2. Registry 狀態：ts3_regime_3bet adapter BOUND
3. Dry-run preview：9 筆 prediction_item 對應的 replay row 預覽
4. 輸出 JSON / CSV / report（不寫 DB）
5. Commit + Draft PR

**本輪 scope：**
- strategy_id: `ts3_regime_3bet`
- lottery_type: `BIG_LOTTO`
- Pending prediction_item IDs: 1069, 1070, 1071, 1090, 1091, 1092, 1093, 1094, 1095

---

## 2. Prerequisite Verification: PR #106 / PR #107

| PR | 標題 | 狀態 | mergedAt | 結果 |
|----|------|------|----------|------|
| [#106](https://github.com/kelvinhuang0327/number-pattern-research/pull/106) | feat(replay): add online strategies to registry proposal | **OPEN** | null | ❌ NOT MERGED |
| [#107](https://github.com/kelvinhuang0327/number-pattern-research/pull/107) | feat(replay): resolve ts3 regime adapter binding | **OPEN** | null | ❌ NOT MERGED |

**→ HARD STOP TRIGGERED**

兩個 PR 都尚未 merge。根據 P2 Mission 規則：
- 不執行 dry-run
- 不產生 backfill preview rows
- Final Classification: `P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED`

---

## 3. Registry / Adapter Verification

### main branch 當前 registry (PR merge 前)

Working branch 基於 `main` (commit `b98a1fe`)，registry 僅包含 6 個策略：

| strategy_id | status |
|-------------|--------|
| power_precision_3bet | ONLINE |
| power_orthogonal_5bet | ONLINE |
| biglotto_triple_strike | ONLINE |
| biglotto_deviation_2bet | ONLINE |
| daily539_f4cold | ONLINE |
| daily539_markov_cold | ONLINE |

`ts3_regime_3bet` **不在** main registry → `get_adapter("ts3_regime_3bet")` 拋出 `Unknown strategy_id`。

### 預期 merge 後狀態 (PR #106 + PR #107)

| PR | 新增 | 最終 registry 數量 |
|----|------|--------------------|
| PR #106 | fourier_rhythm_3bet, ts3_regime_3bet (PENDING) | 8 + stubs → 18 total |
| PR #107 | ts3_regime_3bet adapter → BOUND | 同上，binding 解除 |

---

## 4. Input Prediction Items

DB: `lottery_api/data/lottery_v2.db` (`mode=ro`)

所有 9 個 target prediction_items **均存在於 DB**，status 皆為 PENDING。

| id | run_id | bet_index | numbers | status | snapshot_source |
|----|--------|-----------|---------|--------|-----------------|
| 1069 | 167 | 0 | [5, 25, 26, 27, 31, 35] | PENDING | VALID |
| 1070 | 167 | 1 | [3, 12, 13, 15, 23, 43] | PENDING | VALID |
| 1071 | 167 | 2 | [11, 28, 29, 33, 38, 45] | PENDING | VALID |
| 1090 | 174 | 0 | [3, 5, 22, 34, 38, 49] | PENDING | VALID |
| 1091 | 174 | 1 | [16, 23, 29, 33, 36, 45] | PENDING | VALID |
| 1092 | 174 | 2 | [12, 18, 26, 27, 31, 46] | PENDING | VALID |
| 1093 | 175 | 0 | [12, 22, 23, 28, 34, 49] | PENDING | RECONSTRUCTED |
| 1094 | 175 | 1 | [7, 18, 27, 42, 45, 47] | PENDING | RECONSTRUCTED |
| 1095 | 175 | 2 | [6, 26, 31, 43, 44, 48] | PENDING | RECONSTRUCTED |

### Prediction Runs Summary

| run_id | latest_known_draw | latest_known_date | snapshot_source | target_draw | actual_available |
|--------|-------------------|-------------------|-----------------|-------------|-----------------|
| 167 | 115000048 | 2026/04/28 | VALID | 115000049 | ✅ [7, 22, 27, 35, 43, 48] special=45 |
| 174 | 115000050 | 2026/05/05 | VALID | 115000051 | ❌ not yet in DB |
| 175 | 115000049 | 2026/05/01 | RECONSTRUCTED | 115000050 | ✅ [4, 17, 23, 28, 33, 37] special=15 |

### Pre-flight Hit Preview (informational, for operator awareness)

| item_id | predicted | target_draw | actual | hit |
|---------|-----------|-------------|--------|-----|
| 1069 | [5, 25, 26, 27, 31, 35] | 115000049 | [7, 22, 27, 35, 43, 48] | 27, 35 → **2 hits** |
| 1070 | [3, 12, 13, 15, 23, 43] | 115000049 | [7, 22, 27, 35, 43, 48] | 43 → **1 hit** |
| 1071 | [11, 28, 29, 33, 38, 45] | 115000049 | [7, 22, 27, 35, 43, 48] | — → **0 hits** |
| 1090-1092 | ... | 115000051 | not available | actual_numbers_missing |
| 1093 | [12, 22, 23, 28, 34, 49] | 115000050 | [4, 17, 23, 28, 33, 37] | 23, 28 → **2 hits** |
| 1094 | [7, 18, 27, 42, 45, 47] | 115000050 | [4, 17, 23, 28, 33, 37] | — → **0 hits** |
| 1095 | [6, 26, 31, 43, 44, 48] | 115000050 | [4, 17, 23, 28, 33, 37] | — → **0 hits** |

*(This table is informational only — no replay rows were generated)*

---

## 5. Dry-run Result Summary

| 項目 | 值 |
|------|-----|
| Final Classification | `P2_TS3_REGIME_BACKFILL_DRYRUN_BLOCKED` |
| Adapter Bound | `false` |
| Items Found in DB | 9 / 9 |
| Items Missing from DB | 0 |
| Eligible Count | 0 |
| Blocked Count | 9 |
| Preview Rows Generated | 0 (HARD STOP: preview suppressed) |
| DB Written | `false` |

---

## 6. Preview Row Table

**Suppressed** per HARD STOP — PRs not merged.

Preview rows will be generated in the next run after PR #106 + PR #107 are merged.

---

## 7. Blocked Rows

All 9 items are blocked by:

| Block Reason | Affected Items |
|--------------|---------------|
| `adapter_binding_pending` — ts3_regime_3bet not in main registry | 1069-1095 (all 9) |
| `actual_numbers_missing` — draw 115000051 not yet in DB | 1090, 1091, 1092 |
| `run_id_175_reconstructed_snapshot` — lower provenance confidence | 1093, 1094, 1095 |

---

## 8. Risk Notes — run_id=175 RECONSTRUCTED

`prediction_run.id=175` has `snapshot_source=RECONSTRUCTED`. This means:
- The prediction was regenerated retroactively, not from a live schedule run
- The `predicted_numbers` in items 1093-1095 may differ from what would have been predicted at prediction time
- These items will use `truth_level=ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` when backfilled
- Lower replay confidence vs VALID runs (167, 174)

**Recommendation:** Items 1093-1095 should be backfilled with an additional note in `provenance_source` documenting the RECONSTRUCTED origin.

**Additional risk:** items 1090-1092 (run_id=174) target draw 115000051, which is **after the current max draw in DB** (115000050 as of 2026-05-08). These will become available once the next BIG_LOTTO draw is recorded.

---

## 9. Safety Confirmation

| Safety Flag | Value |
|-------------|-------|
| `db_written` | `false` |
| `replay_rows_inserted` | `false` |
| `prediction_items_promoted` | `false` |
| `backfill_committed` | `false` |
| `strategy_logic_changed` | `false` |
| `api_ui_backend_changed` | `false` |

DB opened with `sqlite3.connect(f"file:{db}?mode=ro", uri=True)` — write operations would raise `OperationalError`.

---

## 10. Operator Approval Request — Next Step

**Current status: BLOCKED — awaiting PR merge**

### Required actions before P2B can proceed:

1. **Review and merge PR #106**  
   `chore/p13-registry-online-proposal-20260515` → `main`  
   [https://github.com/kelvinhuang0327/number-pattern-research/pull/106](https://github.com/kelvinhuang0327/number-pattern-research/pull/106)

2. **Review and merge PR #107** (depends on #106)  
   `chore/p14-ts3-regime-adapter-binding-20260515` → `main`  
   [https://github.com/kelvinhuang0327/number-pattern-research/pull/107](https://github.com/kelvinhuang0327/number-pattern-research/pull/107)

3. **Verify draw 115000051 is in DB** (for items 1090-1092)  
   Once draw occurs, re-run to confirm `actual_numbers_missing` clears for those items.

4. **Re-run dry-run after merge**  
   ```bash
   git checkout main && git pull --ff-only origin main
   python3 scripts/p2_controlled_replay_backfill_dryrun.py \
     --db lottery_api/data/lottery_v2.db \
     --strategy-id ts3_regime_3bet \
     --prediction-item-ids 1069,1070,1071,1090,1091,1092,1093,1094,1095 \
     --json-out outputs/replay/p2_ts3_regime_backfill_dryrun_post_merge.json \
     --csv-out  outputs/replay/p2_ts3_regime_backfill_dryrun_post_merge.csv
   ```

5. **If dry-run shows READY** → proceed to P2B operator approval for DB write

### P2B expected scope (once unblocked)

| Item | Action |
|------|--------|
| Items 1069-1071 | Insert 3 replay rows (target=115000049, actual available) |
| Items 1090-1092 | Insert 3 replay rows (target=115000051, pending draw availability) |
| Items 1093-1095 | Insert 3 replay rows (target=115000050, RECONSTRUCTED, lower confidence) |
| truth_level | REGENERATED_RETROSPECTIVE (runs 167/174) / ARTIFACT_RECONSTRUCTED_RETROSPECTIVE (run 175) |
| controlled_apply_id | P2B_20260515 (operator to confirm) |
