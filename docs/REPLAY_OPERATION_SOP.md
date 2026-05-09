# REPLAY_OPERATION_SOP.md
## Replay System — Operation Runbook (G2)

**Version:** v1.0  
**Date:** 2026-05-08  
**Authority:** This SOP is authoritative for operators managing the Strategy Historical Replay store in pre-go-live and production phases. It is referenced from `wiki/system/replay_data_hygiene.md §9`.

---

## §1 Scope

This runbook covers the `strategy_prediction_replays` + `strategy_replay_runs` tables in `lottery_api/data/lottery_v2.db`. It does NOT cover strategy governance, edge discovery, or live lottery fetches.

**Out of scope:** replay generation, strategy promotion, backfill apply, `outputs/` as API source.

---

## §2 Daily Checks

1. **Freshness check** — hit `/api/replay/freshness` and verify:
   - `latest_run_status` = `"DONE"` for each lottery type
   - `coverage_mode` is `"FULL"` or `"LIMITED"` (never `"UNKNOWN"` in steady state)
   - `has_legacy_errors` shown in UI with advisory only (not alarm)

2. **DB row count** — run:
   ```sql
   SELECT lottery_type, COUNT(*) FROM strategy_prediction_replays GROUP BY lottery_type;
   ```
   Confirm counts are stable (no unexpected growth or shrinkage).

3. **Latest run check** — confirm each lottery type has a `DONE` run with
   `started_at` ≤ 14 days ago (cadence policy §3.2 of `replay_data_hygiene.md`).

4. **Causal integrity** — any row where `history_cutoff_draw >= target_draw` is a defect.
   Query:
   ```sql
   SELECT COUNT(*) FROM strategy_prediction_replays
   WHERE history_cutoff_draw >= target_draw;
   ```
   Expected: `0`.

---

## §3 Anomaly Handling

| Anomaly | Action |
|---------|--------|
| `latest_run_status = FAILED` | Do NOT delete. Set status → `FAILED_LEGACY`, update `notes`, re-run manually with `--dry-run` first |
| `coverage_mode = UNKNOWN` | Inspect `strategy_replay_runs.notes` for the latest run. Re-run coverage report script. |
| `causal_violations > 0` | Stop UI display of affected rows. File an issue. Do NOT auto-fix inline. |
| `legacy_error_count` spikes | Check if a new broken run was added. Do NOT silently delete legacy rows. |
| DB file missing | Restore from latest snapshot in `outputs/db_snapshots/` (see §4). |

---

## §4 Rollback Steps

Before any schema change or bulk data operation:

1. **Take a snapshot** — run `scripts/snapshot_replay_db.py`. Verify SHA256 written to `outputs/db_snapshots/SHA256SUMS`.
2. **Verify** — confirm snapshot file size matches source.
3. **If rollback needed** — copy snapshot back:
   ```bash
   cp outputs/db_snapshots/lottery_v2_pre_replay_golive_<TIMESTAMP>.db \
      lottery_api/data/lottery_v2.db
   ```
4. **Verify integrity** — re-run `sha256sum` against the stored checksum.
5. **Never overwrite** a snapshot once written. Create a new one.

---

## §5 Forbidden Actions

The following actions are **strictly forbidden** without explicit written approval:

| Forbidden | Reason |
|-----------|--------|
| `DELETE FROM strategy_prediction_replays` | Destroys audit traceability |
| `UPDATE replay_status = 'DONE'` on a failed run | Masks real failure |
| Deleting `FAILED_LEGACY` runs from `strategy_replay_runs` | Audit traceability required |
| Using `outputs/replay/` as API/UI data source | `outputs/` is artifact-only |
| Adding `SIGNAL`, `NO_VALIDATED_EDGE`, "推薦投注" to any API response | Forbidden language per §4 of `replay_data_hygiene.md` |
| Running backfill apply without `--dry-run` verification first | Risk of data pollution |
| `--confirm-production-outcome` writes | Forbidden in all agents |

---

## §6 Go-Live Checklist

Before declaring go-live ready, all of the following must be green:

- [ ] **G1** — `tests/test_replay_api_contract.py` passes (25 tests, no skips)
- [ ] **G2** — This SOP exists and is linked from `wiki/system/replay_data_hygiene.md §9`
- [ ] **G3** — `scripts/snapshot_replay_db.py` runs cleanly; SHA256 written
- [ ] **G4** — `tests/test_replay_freshness_cadence.py` passes; cadence policy in wiki §3.2
- [ ] **Marker** — `REPLAY_GOLIVE_READY_20260508` recorded in `memory/lessons.md`

All 4 gates must be verified in CI (CDT python3) before production traffic is served from the replay API.
