# P7 Controlled Replay Row Apply — Readiness Report
**Date**: 2026-05-20  
**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Phase**: P7 Dry-run Complete — Awaiting CEO Authorization for Actual Apply

---

## 1. P0–P6 Baseline Recap

| Phase | Commit | Status |
|-------|--------|--------|
| P0 Schema stabilization | `8b4ffc8` | STABLE |
| P1 Catalog visibility plan | `8b4ffc8` | 18 strategies, 6 REGISTERED, 12 RECONSTRUCTIBLE |
| P2 Lifecycle backfill dry-run | prior | DRY-RUN ONLY, no actual apply |
| P3 UI state contract | `a89a7ca` | 35 tests PASS |
| P4c3 Supported prediction apply | prior | no new rows this session |
| P5 Historical reconstruction plan | `9b895eb` | 128 plan cells (121 PLAN_INSERT, 7 SKIP) |
| P6 Source promotion policy | `9b895eb` | 121 approved / 7 rejected |

---

## 2. UI Visibility Recovery Recap

- **Commit**: `a89a7ca`
- **Gate**: `PUBLIC_VISIBLE_STATES = {REGISTERED_WITH_REPLAY_ROWS}` / `INTERNAL_ONLY_STATES = {ARTIFACT_CANDIDATE, RECONSTRUCTIBLE, REGISTERED_NO_DATA, UNSUPPORTED}`
- **API**: `GET /api/replay/strategies?public_only=true` → ONLINE / OBSERVATION only
- **Verified**: 35 tests PASS, drift guard PASS

---

## 3. P25 Repair Recap

- Fixed FastAPI `Query` coercion bug in `list_replay_strategies` → extracted `get_strategies_response()` sync helper
- Updated ONLINE baseline from 6 → 8 (P1.3 added `fourier_rhythm_3bet` + `ts3_regime_3bet`)
- **Result**: 35/35 PASS (was 27/35)

---

## 4. P6 Candidate Summary: 121 approved / 7 rejected

| Strategy | Lifecycle | Approved | Lifecycle Warning |
|----------|-----------|----------|-------------------|
| fourier_rhythm_3bet | ONLINE | 12 | None |
| ts3_regime_3bet | ONLINE | 16 | None |
| acb_1bet | RETIRED | 31 | Human review required |
| acb_markov_midfreq_3bet | RETIRED | 31 | Human review required |
| midfreq_acb_2bet | RETIRED | 31 | Human review required |

Rejected (7): all `REJECT_NOT_PLAN_INSERT` — no prediction data in DB

---

## 5. P7 Default Scope: ONLINE_ONLY

Default scope processes the safest subset first: the **28 ONLINE-lifecycle rows** with
no lifecycle warnings. RETIRED rows (93) are deferred to manual review until human
explicitly approves.

---

## 6. ONLINE PLAN_INSERT Count: **28**

| Strategy | Lottery | Draw count | Status |
|----------|---------|-----------|--------|
| fourier_rhythm_3bet | POWER_LOTTO | 12 | PLAN_INSERT |
| ts3_regime_3bet | BIG_LOTTO | 16 | PLAN_INSERT |

**Zero duplicates** — neither strategy has any existing rows in `strategy_prediction_replays`.

---

## 7. RETIRED Manual Review Count: **93**

All 93 RETIRED candidates are classified `PLAN_MANUAL_REVIEW_REQUIRED` under the default
`ONLINE_ONLY` scope. To include them, the operator must:

1. Explicitly review the lifecycle warnings in the P7 JSON
2. Re-run with `--scope INCLUDE_RETIRED_WITH_WARNING`
3. Receive separate CEO authorization before actual apply

---

## 8. Duplicate Check Result

| Strategy | Existing replay rows | Duplicates detected |
|----------|---------------------|---------------------|
| fourier_rhythm_3bet | 0 | 0 |
| ts3_regime_3bet | 0 | 0 |
| acb_1bet (RETIRED) | 0 | 0 |
| acb_markov_midfreq_3bet (RETIRED) | 0 | 0 |
| midfreq_acb_2bet (RETIRED) | 0 | 0 |

All 28 ONLINE PLAN_INSERT rows are clean — no duplicates.

---

## 9. Backup Plan

Before any actual P7 apply, a database snapshot **MUST** be created:

```bash
sqlite3 lottery_api/data/lottery_v2.db ".dump" > backups/p7_pre_apply_20260520.sql
```

- **Snapshot target**: `lottery_api/data/lottery_v2.db`
- **Verified row count before**: 460
- **Rollback command**: `sqlite3 lottery_api/data/lottery_v2.db < backups/p7_pre_apply_20260520.sql`

---

## 10. Rollback Plan

All rows inserted in a P7 apply batch share a `rollback_batch_id` (UUID).

```sql
DELETE FROM strategy_prediction_replays
WHERE controlled_apply_id IN (
    SELECT controlled_apply_id FROM p7_apply_log
    WHERE rollback_batch_id = '<rollback_batch_id>'
);
```

Idempotency check before any row insert:
```sql
SELECT COUNT(*) FROM strategy_prediction_replays
WHERE strategy_id=? AND target_draw=? AND lottery_type=?
```

---

## 11. Risk / Unknowns

| Risk | Severity | Status |
|------|----------|--------|
| RETIRED strategies have no production lifecycle | MEDIUM | Deferred to manual review; lifecycle_warning set |
| midfreq_acb_2bet P1 CODE_SCAN vs actual TIER_1 data | LOW | P5 re-detected correctly; documented |
| backup directory `backups/` may not exist | LOW | Must be created before actual apply |
| 93 RETIRED rows pending human review | HIGH | Not scheduled until `YES apply P7` received |
| ONLINE rows (28) have actual predicted numbers in DB | SAFE | Verified TIER_1 provenance hashes |

---

## 12. Test Coverage

| Suite | Tests | Result |
|-------|-------|--------|
| P7 apply plan contract | 39 | ✅ PASS |
| P7 controlled apply dry-run integration | 20 | ✅ PASS |
| P6 + P25 + replay API + P3 UI (regression) | 166 | ✅ PASS |
| **Total** | **225** | **✅ 225 PASS / 0 FAIL** |

Drift guard: **PASS** — `strategy_prediction_replays` = 460 rows (unchanged)

---

## 13. CEO Authorization Gate

P7 actual apply is **NOT** triggered by this dry-run.

This report covers **ONLINE_ONLY scope** (28 rows). RETIRED rows (93) require additional
human review before a separate authorization.

若授權實際執行 P7 controlled apply，請回覆：

> `YES apply P7 controlled replay rows`
