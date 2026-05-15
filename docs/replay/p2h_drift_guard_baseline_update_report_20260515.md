# P2H Drift Guard Baseline Update Report — 2026-05-15

## 1. 本輪目標

更新 `replay_lifecycle_drift_guard.py` 的 baseline，以反映 PR #115（P2F_20260515 controlled replay backfill）合併後的新狀態。

- total replay rows: 966 → 969
- 新增 `OFFICIAL` 至 `ALLOWED_TRUTH_LEVELS`
- 新增 `P2F_20260515` 至 known controlled_apply_ids

## 2. PR #115 Merge Summary

- PR #115: `data(replay): apply p2f controlled replay backfill for ts3_regime_3bet (#115)`
- Commit: `c29293f`
- 插入 3 rows: prediction items 1090–1092, strategy `ts3_regime_3bet`, draw `115000051`
- `controlled_apply_id = 'P2F_20260515'`
- `truth_level = 'OFFICIAL'`（新枚舉值，P2F 首次引入）

## 3. Drift Guard Violations BEFORE Update

執行 `python3 scripts/replay_lifecycle_drift_guard.py --strict` 產生 3 violations：

```
VIOLATIONS (3):
  - total row count mismatch: expected 966, got 969
  - Unexpected truth_level value 'OFFICIAL' found (3 rows)
  - Unexpected controlled_apply_id 'P2F_20260515' found (3 rows)

Final classification: REPLAY_LIFECYCLE_DRIFT_GUARD_FAIL
```

## 4. Changes Made

### `scripts/replay_lifecycle_drift_guard.py`

1. **docstring**: 更新 baseline 描述，加入 P2F 行（total 966 → 969）
2. **BASELINE dict**: 新增 `p2f_apply_id` 和 `p2f_count=3`，`total_count` 966 → 969
3. **ALLOWED_TRUTH_LEVELS**: 新增 `"OFFICIAL"`
4. **run_checks()**: 新增 `p2f_count` SQL query 和 violation check
5. **row_counts**: 新增 `"p2f"` key
6. **known_apply_ids**: 新增 `BASELINE["p2f_apply_id"]`
7. **expected keys loop**: 新增 `"OFFICIAL"` 至 truth_level 初始化

### `tests/test_replay_lifecycle_drift_guard.py`

1. **docstring**: 更新 baseline 說明（total 960 → 969，加入 P2F=3，OFFICIAL truth_level）
2. **ALLOWED_TRUTH_LEVELS**: 新增 `"OFFICIAL"`
3. **test_db_counts_match_baseline**: 更新 docstring、新增 p2b/p2f assertions、total 966 → 969

## 5. Drift Guard Result AFTER Update

```
Row counts — V1=300  V2=200  legacy=460  total=969
V3 tombstone strategies with 0 rows: 6/6
truth_level — REGENERATED=303  ARTIFACT=203  OFFICIAL=3  null=460

No violations found.

Final classification: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
Status: PASS
```

JSON output: `outputs/replay/p2h_post_merge_drift_guard_verify_20260515.json`

## 6. Test Results Before / After

| Test | Before | After |
|------|--------|-------|
| test_script_compiles | PASS | PASS |
| test_strict_mode_passes | **FAIL** | PASS |
| test_json_output_schema | PASS | PASS |
| test_no_v3_fake_rows | PASS | PASS |
| test_truth_level_enum_clean | **FAIL** | PASS |
| test_db_counts_match_baseline | **FAIL** | PASS |
| All other replay contract tests | 103 PASS | 103 PASS |
| **Total** | **3 FAIL, 106 total** | **109 PASS** |

## 7. Safety Confirmation

- `db_written`: false
- `replay_rows_inserted`: false（total=969，與 P2F merge 後一致）
- `prediction_items_modified`: false
- `strategy_logic_changed`: false
- `api_ui_backend_changed`: false
- `forbidden_artifacts` (*.db, *.sqlite, *.pid): none detected

## 8. Coverage Summary

| controlled_apply_id | rows |
|--------------------|------|
| `20260514033100-13acaf34996e` (V1) | 300 |
| `20260514134953-cf683424` (V2) | 200 |
| NULL (legacy) | 460 |
| `P2B_20260515` | 6 |
| `P2F_20260515` | 3 |
| **Total** | **969** |

Truth level distribution:
- `REGENERATED_RETROSPECTIVE`: 303
- `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`: 203
- `OFFICIAL`: 3
- `null`: 460

## 9. Next Step Recommendation

- P2H 更新完成，baseline 已對齊 969 rows。
- CI drift guard 應持續監控（cron job 或 pre-merge check）。
- 下一個 controlled backfill（如 P2I 或後續 apply）合併後需再執行本流程更新 baseline。
- OFFICIAL truth_level 已正式進入 allowed set，後續 backfill 可繼續使用。
