# P7 Controlled Replay Row Apply — Dry-run Report
**Date**: 2026-05-20  
**Scope**: `ONLINE_ONLY`  
**Rollback Batch ID**: `3a99697e-de3f-484c-aacc-5e9365c6b167`  
**p7_can_apply**: `False` (dry-run only)  

## Summary

| Metric | Count |
|--------|-------|
| Total P6 candidates | 121 |
| ONLINE candidates | 28 |
| RETIRED candidates (with lifecycle warning) | 93 |
| **PLAN_INSERT** | **28** |
| PLAN_MANUAL_REVIEW_REQUIRED | 93 |
| PLAN_SKIP_DUPLICATE | 0 |
| Other skip | 0 |
| DB rows verified (unchanged) | 460 |

## By Strategy

| Strategy | Lifecycle | PLAN_INSERT | Manual Review | Skip | Total |
|----------|-----------|-------------|---------------|------|-------|
| fourier_rhythm_3bet | ONLINE | 12 | 0 | 0 | 12 |
| ts3_regime_3bet | ONLINE | 16 | 0 | 0 | 16 |
| acb_1bet | RETIRED | 0 | 31 | 0 | 31 |
| acb_markov_midfreq_3bet | RETIRED | 0 | 31 | 0 | 31 |
| midfreq_acb_2bet | RETIRED | 0 | 31 | 0 | 31 |

## Backup Plan

> Before P7 actual apply, a DB snapshot must be created: sqlite3 lottery_v2.db .dump > backups/p7_pre_apply_YYYYMMDD.sql

- Snapshot target: `lottery_api/data/lottery_v2.db`
- Backup path: `backups/p7_pre_apply_20260520.sql`
- Verified row count before apply: 460
- Rollback command: `sqlite3 lottery_api/data/lottery_v2.db < backups/p7_pre_apply_20260520.sql`

## Rollback Plan

> All rows inserted in the P7 apply batch share rollback_batch_id. Rollback SQL: DELETE FROM strategy_prediction_replays WHERE controlled_apply_id IN (SELECT controlled_apply_id FROM p7_apply_log WHERE rollback_batch_id=?)

- Rollback batch ID: `3a99697e-de3f-484c-aacc-5e9365c6b167`
- Idempotency check: `SELECT COUNT(*) FROM strategy_prediction_replays WHERE strategy_id=? AND target_draw=? AND lottery_type=?`

## Safety Flags

| Flag | Value |
|------|-------|
| `p7_can_apply_globally` | `False` |
| `dry_run_only_globally` | `True` |
| `db_write_performed` | `False` |
| `replay_rows_generated` | `False` |
| `prediction_rows_generated` | `False` |

## CEO Authorization Gate

> P7 actual apply is **NOT** triggered by this script.
>
> This report covers scope `ONLINE_ONLY`.
> 28 rows are staged for dry-run insert.
> RETIRED lifecycle warnings must be reviewed before any actual apply.

若授權實際執行 P7 controlled apply，請回覆：

> `YES apply P7 controlled replay rows`
