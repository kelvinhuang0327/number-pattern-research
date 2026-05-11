# P21 Non-ONLINE Replay Fixture Generator - 2026-05-11

## 1. 本輪目標

根據 P20 fixture-only spec，實作 isolated non-ONLINE replay fixture artifact generator。

本輪只產出 JSON fixture artifact，不做任何 production replay 資料寫入。

## 2. Main Latest Commit

- `main` baseline commit: `f2ffdd2`

## 3. P20 Artifact Verification

已確認以下 artifacts 在 main 上存在：

- `outputs/replay/p20_non_online_replay_fixture_spec_20260511.md`
- `outputs/replay/p19_replay_product_follow_up_20260511.md`
- `outputs/replay/p18_replay_product_gap_inventory_20260511.md`

已確認 P20 markers：

- `P20_NON_ONLINE_FIXTURE_SPEC_REVIEWED`
- `P20_NON_ONLINE_STRATEGY_SCOPE_CONFIRMED`
- `P20_FIXTURE_ONLY_NO_WRITE_CONTRACT_DEFINED`
- `P20_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P20_NO_PROMOTION_ACTION_CONFIRMED`

## 4. Non-ONLINE Fixture Scope

Registry read-only inventory：

- total strategies: 16
- executable (ONLINE): 6
- non_executable (non-ONLINE): 10

non-ONLINE status coverage：

- REJECTED: 4
- RETIRED: 5
- OBSERVATION: 1
- OFFLINE: 0

## 5. Generator Summary

新增 script：

- `scripts/generate_non_online_replay_fixture.py`

設計特性：

- 僅使用 lifecycle registry public metadata API
- 僅輸出 JSON artifact
- deterministic（固定 fixture version + strategy identity hash）
- stable ordering by `lifecycle_status`, `lottery_type`, `strategy_id`
- 不呼叫 `get_adapter()`
- 不呼叫 `get_one_bet()`
- 不連 SQLite，不寫 DB

CLI：

```bash
python3 scripts/generate_non_online_replay_fixture.py \
  --output outputs/replay/non_online_replay_fixture_20260511.json
```

## 6. Fixture Artifact Schema

artifact top-level contract：

- `fixture_name`: `non_online_lifecycle_replay_fixture`
- `fixture_version`: `p21_20260511`
- `synthetic_only`: `true`
- `fixture_only`: `true`
- `source`: `non_online_lifecycle_fixture`
- `production_db_write`: `false`
- `backfill`: `false`
- `promotion_action`: `false`
- `strategy_count`: `10`
- `records`: fixture rows
- `markers`: governance markers

record-level contract：

- `strategy_id`
- `lottery_type`
- `lifecycle_status`
- `fixture_row_id`
- `draw_id`
- `draw_date`
- `prediction_payload`
- `actual_result_payload`
- `comparison_result`
- `synthetic_only`
- `fixture_only`
- `fixture_source`
- `governance_marker` (`P21_NON_ONLINE_FIXTURE_ROW`)

## 7. Fixture Artifact Path

- `outputs/replay/non_online_replay_fixture_20260511.json`

Artifact validation:

- JSON parse check: pass (`python3 -m json.tool`)
- marker grep checks: pass

## 8. Test Results

新增測試：

- `tests/test_non_online_replay_fixture_generator.py`

執行結果：

```text
10 passed in 0.04s
153 passed in 0.40s
```

涵蓋重點：

- artifact creates JSON
- synthetic_only / fixture_only flags
- production_db_write=false / backfill=false / promotion_action=false
- strategy_count=10 and exact non-ONLINE coverage
- lifecycle status preserved and no ONLINE included
- governance marker present in records
- generator source does not import sqlite3
- sqlite3.connect monkeypatch remains uncalled
- output path must include outputs/replay segment
- deterministic output across repeated runs

## 9. No SQLite Import / no sqlite3.connect Evidence

Evidence:

- script source has no `import sqlite3`
- dedicated test asserts sqlite import absence
- dedicated test patches `sqlite3.connect` and confirms zero calls

Result: no SQLite write path involved.

## 10. No DB Write Evidence

Implementation path is output-only JSON write to `outputs/replay/`.

No database manager usage, no replay table writes, and no runtime endpoint integration were introduced.

## 11. No Backfill Evidence

No backfill script was called.

No production replay rows were generated.

Artifact is fixture-only and explicitly marks:

- `backfill: false`
- `production_db_write: false`

## 12. No Promotion Evidence

No lifecycle transition action was introduced.

Artifact explicitly marks:

- `promotion_action: false`

No strategy promotion / retire / reactivation behavior was added.

## 13. Risks / Limitations

- Fixture rows are synthetic and must not be interpreted as production replay truth.
- `lottery_type` currently falls back to `UNKNOWN` for entries without explicit type metadata.
- This work does not resolve product-side fixture-mode UI rendering; it only provides artifact generation.

## 14. P22 Recommendation

P22 should focus on validation and optional fixture-mode contract checks:

- fixture artifact validation and smoke checks
- no-write endpoint mock contract (if needed, separately approved)
- preserve no production DB writes
- preserve no real backfill
- preserve no promotion
- preserve no scheduler changes

## 15. Final Markers

- `P21_NON_ONLINE_FIXTURE_GENERATOR_READY`
- `P21_NON_ONLINE_FIXTURE_ARTIFACT_READY`
- `P21_FIXTURE_RECORDS_COVER_10_NON_ONLINE_STRATEGIES`
- `P21_NO_SQLITE_WRITE_CONFIRMED`
- `P21_NO_DB_WRITE_NO_BACKFILL_CONFIRMED`
- `P21_NO_PROMOTION_ACTION_CONFIRMED`
