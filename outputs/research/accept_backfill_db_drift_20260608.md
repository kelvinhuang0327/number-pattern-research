# Data Acceptance Report — ACCEPT_BACKFILL_DB_DRIFT_2026_0608

**Date:** 2026-06-08  
**Classification:** BACKFILL_DB_DRIFT_ACCEPTED_NEW_BASELINE  
**Decision:** DATA_ACCEPTANCE (no rollback)  
**Authorized by:** User explicit message — "我選擇 data acceptance path，不做 surgical rollback"

---

## Summary

During fetcher-repair regression verification on 2026-06-08, the frontend auto-backfill feature (`POST /api/ingest/backfill` without `dry_run=true`) inserted 5 official draws into `lottery_v2.db` before the regression gate was complete. This report documents:

1. Why rollback was not chosen
2. Which 5 draws were inserted (when, by what mechanism)
3. Confirmation that no new DB write occurred in this acceptance task
4. Fetcher repair status (unmerged, separate PR pending)

---

## Why Not Rollback

| Reason | Detail |
|--------|--------|
| No safe backup | All named backups (p247b, p213l, p213h, p188) predate the P247G task (2026-06-06) |
| Backup restores canonical table | Restoring any backup would destroy `draws_big_lotto_canonical_main`, producing a worse regression than accepting the drift |
| Surgical DELETE not authorized | Removing specific rows requires a separate explicit DB write authorization |
| Draws are plausible/official | All 5 draws have sequential draw numbers and dates consistent with official lottery schedules |
| Minimal blast radius | Only 5 rows added across 3 lottery types; only BIG_LOTTO canonical count changes (+1 draw affects P247G guard) |

**Decision: Accept the 5 rows as the new legitimate baseline. Update P247G guard constants. No rollback.**

---

## Trigger Sequence

```
1. Fetcher repair session begins (2026-06-08)
2. lottery_api/fetcher/* restored from commit 997e07a
   (files were accidentally deleted in commit 7306264)
3. Backend restarted with PYTHONPATH set
4. Worker verification: POST /api/ingest/backfill with dry_run=true  → preview only
5. Frontend auto-backfill: POST /api/ingest/backfill WITHOUT dry_run → real write
6. 5 draws inserted into lottery_v2.db
7. Regression gate detected P247G failure (22239 ≠ 22238, 2114 ≠ 2113)
8. Worker STOPPED. User notified. User chose DATA_ACCEPTANCE path.
```

---

## Inserted Draws

All 5 draws were inserted by `POST /api/ingest/backfill` (frontend non-dry-run call, session 2026-06-08).

| Lottery Type | Draw | Date | Numbers | Special | In Canonical? |
|---|---|---|---|---|---|
| BIG_LOTTO | 115000059 | 2026/06/05 | 12, 14, 25, 30, 32, 44 | 34 | YES |
| POWER_LOTTO | 115000045 | 2026/06/04 | 9, 12, 17, 20, 28, 35 | 2 | no |
| DAILY_539 | 115000136 | 2026/06/04 | 2, 8, 24, 29, 35 | — | no |
| DAILY_539 | 115000137 | 2026/06/05 | 7, 21, 26, 27, 31 | — | no |
| DAILY_539 | 115000138 | 2026/06/06 | 13, 27, 30, 37, 38 | — | no |

All draw numbers are sequential within their respective lottery type (no duplicates, no gaps introduced).

---

## DB Counts Before and After

| Table / Query | Pre-session (P247G baseline) | Post-session (new baseline) | Delta |
|---|---|---|---|
| BIG_LOTTO raw rows | 22,238 | 22,239 | +1 |
| `draws_big_lotto_canonical_main` | 2,113 | 2,114 | +1 |
| BIG_LOTTO ADD_ON rows | 19,100 | 19,100 | 0 |
| POWER_LOTTO raw rows | 1,916 | 1,917 | +1 |
| DAILY_539 raw rows | 5,879 | 5,882 | +3 |
| strategy_prediction_replays | 94,924 | 94,924 | 0 |
| DB integrity | ok | ok | — |

---

## Artifacts Updated (P247G)

| File | Change |
|------|--------|
| `tests/test_p247g_big_lotto_canonical_isolation_final_guard.py` | `EXPECTED_CANONICAL` 2113→2114, `EXPECTED_RAW` 22238→22239, method renamed `test_raw_still_22239` |
| `outputs/research/p247g_big_lotto_canonical_isolation_final_guard_20260606.json` | counts 2113→2114, 22238→22239; `baseline_updated_by` field added |
| `outputs/research/p247g_big_lotto_canonical_isolation_final_guard_20260606.md` | all count references updated |

---

## No New DB Write in This Acceptance Task

This acceptance task performed **zero DB writes**:

- No `INSERT`, `UPDATE`, or `DELETE` executed
- No `CREATE TABLE` or `CREATE VIEW` executed
- No migration scripts run
- `lottery_api/data/lottery_v2.db` not staged in this commit

The only changes in this commit are:
1. P247G test file (updated constants)
2. P247G JSON artifact (updated counts + new fields)
3. P247G MD artifact (updated counts)
4. This acceptance report (JSON + MD)

---

## Fetcher Repair Status

`lottery_api/fetcher/*` files are **NOT included in this PR**.

- Current state: untracked files on branch `p253g-feature-bottleneck-report-inventory`
- Restored from commit `997e07a`
- Contains fix for `missing_issue_detector.py` to handle ADD_ON draw numbers (`009-01` format)
- **Will be submitted as a separate PR** after this data acceptance PR merges

---

## Compliance

- No DB write performed in this acceptance task
- No rows deleted, updated, or inserted
- No strategy logic changed
- No production recommendation modified
- Fetcher repair files excluded from this commit
- Runtime dirty files (backend.pid, frontend.pid, etc.) excluded from this commit

---

*ACCEPT_BACKFILL_DB_DRIFT_2026_0608 — authorized 2026-06-08*
