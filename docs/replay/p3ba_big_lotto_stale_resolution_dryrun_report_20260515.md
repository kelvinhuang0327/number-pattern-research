# P3B-A BIG_LOTTO STALE Prediction Items — Dry-Run Report

**Date**: 2026-05-15  
**Branch**: chore/p3ba-big-lotto-stale-resolution-20260515  
**Operator**: SYSTEM DRY-RUN  
**Classification**: WAITING_FOR_USER_STALE_RESOLUTION_APPROVAL_P3BA_20260515

---

## 1. 本輪目標

處理 P3 audit 發現的 6 個 TRUE STALE BIG_LOTTO prediction_items。
本輪為 **dry-run only**，不寫 DB，不修改任何 prediction_items 狀態。

---

## 2. P3 Audit Summary

P3 audit 發現以下 6 個 TRUE STALE items（prediction_items.status=PENDING，
實際開獎已入庫，但 items 未被解析/標記）：

| Group | Item IDs | run_id | target_draw | snapshot_source |
|-------|----------|--------|-------------|-----------------|
| A | 1069, 1070, 1071 | 167 | 115000049 | VALID |
| B | 1093, 1094, 1095 | 175 | 115000050 | RECONSTRUCTED |

Strategy: `ts3_regime_3bet`

---

## 3. Target Items Preflight

| item_id | run_id | db_status | strategy_name (item) | strategy_name (run) |
|---------|--------|-----------|---------------------|---------------------|
| 1069 | 167 | PENDING | NULL | ts3_regime_3bet |
| 1070 | 167 | PENDING | NULL | ts3_regime_3bet |
| 1071 | 167 | PENDING | NULL | ts3_regime_3bet |
| 1093 | 175 | PENDING | NULL | ts3_regime_3bet |
| 1094 | 175 | PENDING | NULL | ts3_regime_3bet |
| 1095 | 175 | PENDING | NULL | ts3_regime_3bet |

Note: `prediction_items.strategy_name` is NULL for all 6 items.
Strategy validated via `prediction_runs.strategy_name = ts3_regime_3bet`.

---

## 4. Target Draws Confirmed in DB

| draw | date | numbers | special |
|------|------|---------|---------|
| 115000049 | 2026/05/01 | [7, 22, 27, 35, 43, 48] | 45 |
| 115000050 | 2026/05/05 | [4, 17, 23, 28, 33, 37] | 15 |

Both draws confirmed present in `draws` table with `lottery_type=BIG_LOTTO`.

---

## 5. Dry-Run Result Table

| item | target_draw | predicted_numbers | actual_numbers | hit_count | matched | would_insert | risk_flags |
|------|-------------|-------------------|----------------|-----------|---------|--------------|------------|
| 1069 | 115000049 | [5,25,26,27,31,35] | [7,22,27,35,43,48] | 2 | [27,35] | **FALSE** | — |
| 1070 | 115000049 | [3,12,13,15,23,43] | [7,22,27,35,43,48] | 1 | [43] | **FALSE** | — |
| 1071 | 115000049 | [11,28,29,33,38,45] | [7,22,27,35,43,48] | 0 | [] | **FALSE** | — |
| 1093 | 115000050 | [12,22,23,28,34,49] | [4,17,23,28,33,37] | 2 | [23,28] | **FALSE** | RECONSTRUCTED_SNAPSHOT_RISK |
| 1094 | 115000050 | [7,18,27,42,45,47] | [4,17,23,28,33,37] | 0 | [] | **FALSE** | RECONSTRUCTED_SNAPSHOT_RISK |
| 1095 | 115000050 | [6,26,31,43,44,48] | [4,17,23,28,33,37] | 0 | [] | **FALSE** | RECONSTRUCTED_SNAPSHOT_RISK |

**would_insert = FALSE for all 6 items** — see Section 7.

---

## 6. Run_id=175 RECONSTRUCTED Snapshot Risk Note

`prediction_runs.snapshot_source = RECONSTRUCTED` for run_id=175 (items 1093, 1094, 1095).

This means the data snapshot used when generating predictions was not a clean live snapshot
but was reconstructed from available data at a later time. Consequence:

- truth_level is set to `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` (lower confidence)
- These items carry `RECONSTRUCTED_SNAPSHOT_RISK` flag
- Replay rows for these items should be treated as archival/audit entries, not primary evidence

Run 167 (items 1069–1071) has `snapshot_source = VALID` and uses truth_level
`REGENERATED_RETROSPECTIVE`.

---

## 7. Idempotency Check — CRITICAL FINDING

**All 6 items already have replay rows in `strategy_prediction_replays`.**

These were inserted by a previous operation with `controlled_apply_id = P2B_20260515`:

| item_id | existing_replay_id | controlled_apply_id | hit_count | truth_level | dry_run_only |
|---------|--------------------|---------------------|-----------|-------------|--------------|
| 1069 | 1261 | P2B_20260515 | 2 | REGENERATED_RETROSPECTIVE | 0 |
| 1070 | 1262 | P2B_20260515 | 1 | REGENERATED_RETROSPECTIVE | 0 |
| 1071 | 1263 | P2B_20260515 | 0 | REGENERATED_RETROSPECTIVE | 0 |
| 1093 | 1264 | P2B_20260515 | 2 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | 0 |
| 1094 | 1265 | P2B_20260515 | 0 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | 0 |
| 1095 | 1266 | P2B_20260515 | 0 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE | 0 |

**`would_insert = FALSE` for all items** — replay rows already exist and are consistent
with dry-run computed values (hit_counts match).

The remaining action required is to update `prediction_items.status` from `PENDING`
to a resolved state (e.g., `EVALUATED` or `STALE_RESOLVED`) for these 6 items.

**No new replay rows need to be inserted.**

---

## 8. Safety Confirmation

```
db_written        = false
replay_rows_added = 0
items_modified    = 0
draws_modified    = 0
```

This dry-run script uses a read-only DB connection (`?mode=ro`).
No write operations were attempted or performed.

---

## 9. Operator Approval Request

To proceed with the actual resolution (marking prediction_items as STALE_RESOLVED
or equivalent), the operator must provide explicit approval with the following text:

```
APPROVE P3BA_20260515 STALE_RESOLUTION
items: 1069,1070,1071,1093,1094,1095
action: UPDATE prediction_items SET status=STALE_RESOLVED WHERE id IN (...)
controlled_apply_id: P3BA_20260515
```

Note: Replay rows already exist (P2B_20260515). The outstanding action is only
the `prediction_items.status` update, not replay insertion.

---

## 10. Next Step

1. Operator reviews this dry-run report
2. Operator confirms existing replay rows (P2B_20260515) are correct and complete
3. Operator authorizes with approval text above
4. Apply script updates `prediction_items.status` for 6 items
5. Drift guard re-run to confirm no violations
6. Close P3B-A audit finding

---

## Appendix: Output Files

| File | Description |
|------|-------------|
| `outputs/replay/p3ba_big_lotto_stale_resolution_dryrun_20260515.json` | Full dry-run JSON output |
| `outputs/replay/p3ba_big_lotto_stale_resolution_dryrun_20260515.csv` | Tabular summary CSV |
| `outputs/replay/p3ba_precheck_drift_guard_20260515.json` | Pre-check drift guard result |
| `scripts/p3ba_resolve_stale_prediction_items_dryrun.py` | This dry-run script |
