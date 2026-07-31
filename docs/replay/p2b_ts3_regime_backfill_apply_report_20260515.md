# P2B Controlled Replay Backfill Apply Report
**Strategy:** ts3_regime_3bet (BIG_LOTTO)  
**Apply ID:** P2B_20260515  
**Date:** 2026-05-15  
**Branch:** chore/p2b-controlled-replay-backfill-apply-20260515  

---

## 1. Executive Summary

This report documents the controlled backfill of 6 `strategy_prediction_replays` rows for the `ts3_regime_3bet` BIG_LOTTO strategy. The backfill covers prediction items from runs 167 and 175 targeting draws 115000049 (2026/05/01) and 115000050 (2026/05/05).

**Final Classification:** `P2B_CONTROLLED_REPLAY_BACKFILL_APPLIED`  
**Rows Inserted:** 6  
**Rows Blocked:** 3 (draw 115000051 not yet in DB)  
**Prediction Items Promoted:** 0  
**DB Safety:** Idempotent, FK-safe, WAL-mode write  

---

## 2. Prerequisite Chain

| Step | Classification | Notes |
|------|----------------|-------|
| PR #106 merged | Registry ONLINE | 16→18 strategies, ts3_regime_3bet ONLINE |
| PR #107 merged | Adapter bound | ts3_regime_3bet → _BigLottoTs3Regime3BetAdapter (SAFE_RECONSTRUCTION) |
| P2 dry-run (PR #108) | P2_TS3_REGIME_BACKFILL_DRYRUN_READY | 6 eligible, 3 blocked |
| P2B apply (this) | P2B_CONTROLLED_REPLAY_BACKFILL_APPLIED | 6 rows inserted |

---

## 3. Eligible Rows Inserted

| Replay Row ID | Item ID | Run ID | Target Draw | Draw Date | Predicted | Actual | Hits | Truth Level |
|---------------|---------|--------|-------------|-----------|-----------|--------|------|-------------|
| 1261 | 1069 | 167 | 115000049 | 2026/05/01 | 3 numbers | actual | 2 | REGENERATED_RETROSPECTIVE |
| 1262 | 1070 | 167 | 115000049 | 2026/05/01 | 3 numbers | actual | 1 | REGENERATED_RETROSPECTIVE |
| 1263 | 1071 | 167 | 115000049 | 2026/05/01 | 3 numbers | actual | 0 | REGENERATED_RETROSPECTIVE |
| 1264 | 1093 | 175 | 115000050 | 2026/05/05 | 3 numbers | actual | 2 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE |
| 1265 | 1094 | 175 | 115000050 | 2026/05/05 | 3 numbers | actual | 0 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE |
| 1266 | 1095 | 175 | 115000050 | 2026/05/05 | 3 numbers | actual | 0 | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE |

---

## 4. Blocked Rows (Not Inserted)

| Item ID | Run ID | Reason |
|---------|--------|--------|
| 1090 | 174 | actual_numbers_missing — draw 115000051 not yet in DB |
| 1091 | 174 | actual_numbers_missing — draw 115000051 not yet in DB |
| 1092 | 174 | actual_numbers_missing — draw 115000051 not yet in DB |

**Re-test trigger:** When draw 115000051 result lands in the draws table, run a follow-up P2C dry-run to verify and then a P2C apply for items 1090-1092.

---

## 5. Schema Adaptations

### No `prediction_item_id` Column in `strategy_prediction_replays`
The target table has no `prediction_item_id` column. Item provenance is stored in `provenance_source` (TEXT JSON):

```json
{
  "prediction_item_id": 1069,
  "run_id": 167,
  "risk_flags": [],
  "notes": "",
  "p2_dryrun_script": "scripts/p2_controlled_replay_backfill_dryrun.py",
  "p2b_apply_script": "scripts/p2b_controlled_replay_backfill_apply.py"
}
```

Post-apply queries must use `WHERE controlled_apply_id='P2B_20260515'` (not `prediction_item_id`).

### No `replay_run_id` Link
`replay_run_id` has FK to `strategy_replay_runs.id` (IDs 1-7). Prediction run IDs 167/175 reference `prediction_runs`, not `strategy_replay_runs`. Set `replay_run_id=NULL`; actual run linkage is via `provenance_source.run_id`.

---

## 6. Apply Script Safety Properties

- **Default mode:** DRY-RUN (requires explicit `--apply`)
- **Authorization gate:** `--controlled-apply-id P2B_20260515` exact match required
- **ID allowlist:** `{1069, 1070, 1071, 1093, 1094, 1095}`
- **Blocklist:** `{1090, 1091, 1092}` — explicitly refused even if requested
- **Idempotency:** Checks for existing `controlled_apply_id='P2B_20260515'` rows before any INSERT; aborts with `P2B_BLOCKED_IDEMPOTENCY` if found
- **FK safety:** `replay_run_id=NULL` to avoid FK violation
- **Transaction:** All 6 inserts in single `with conn:` block (atomic rollback on error)

---

## 7. Post-Apply Verification

```
POST_APPLY_DB_VERIFY_PASS
rows=6  prediction_items_not_promoted=True  blocked_items_not_inserted=True
```

Query used:
```sql
SELECT id, strategy_id, target_draw, truth_level, hit_count, controlled_apply_id, provenance_source
FROM strategy_prediction_replays
WHERE controlled_apply_id = 'P2B_20260515'
ORDER BY id;
-- Returns 6 rows: ids 1261–1266
```

---

## 8. Drift Guard Baseline Update

The drift guard baseline was updated to acknowledge P2B rows:

| Field | Before | After |
|-------|--------|-------|
| `total_count` | 960 | 966 |
| `p2b_apply_id` | (none) | `P2B_20260515` |
| `p2b_count` | (none) | 6 |
| `known_apply_ids` | {v1, v2, NULL} | {v1, v2, P2B_20260515, NULL} |

---

## 9. Governance Test Results

```
109 passed in 0.74s
tests/test_replay_strategy_lifecycle_registry.py  ✓ (all pass)
tests/test_replay_lifecycle_drift_guard.py         ✓ (all pass, including updated baseline)
tests/test_replay_truth_level_contract.py          ✓ (all pass)
tests/test_replay_api_contract.py                  ✓ (all pass)
```

---

## 10. Next Steps (P2C)

- **When draw 115000051 arrives:** Run P2C dry-run for items 1090-1092 → apply after verification
- **Drift guard:** Baseline updated; no follow-up PR needed for baseline drift
- **Prediction items 1069–1095:** Remain `PENDING` — promotion not in scope for P2B
- **Monitor:** Check ts3_regime_3bet registry health in regular drift guard runs

---

## Safety Summary

| Property | Status |
|----------|--------|
| DB written | ✅ 6 rows |
| Replay rows inserted | ✅ 6 rows (ids 1261-1266) |
| Prediction items promoted | ❌ NOT promoted (as designed) |
| Prediction runs updated | ❌ NOT updated (as designed) |
| Blocked items (1090-1092) inserted | ❌ NOT inserted (as designed) |
| Strategy logic changed | ❌ No change |
| API/UI/backend changed | ❌ No change |
| Idempotent | ✅ Refuses re-run |
| Governance tests | ✅ 109/109 PASS |
