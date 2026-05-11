# P3 DB Dirt Root Cause - 2026-05-11

## 1. Summary

Classification: LOCAL-DEV-ONLY

The `data/lottery_v2.db` dirt is a local working-tree artifact, not evidence of a production DB leak.

## 2. Evidence

Read-only checks performed in the clean worktree:

- `git checkout main && git pull --ff-only` brought `main` to the latest merged state.
- `git stash push -m 'temp db dirt investigation' -- data/lottery_v2.db` isolated the local dirt.
- `git show HEAD:data/lottery_v2.db > /tmp/clean_db.bin` produced the clean copy from `HEAD`.
- Clean-copy schema inspection showed that the `strategy_prediction_replays` and `strategy_replay_runs` tables are not present in `HEAD`.
- Working-copy schema inspection showed both tables exist locally.
- Row counts in the working copy are zero:
  - `strategy_prediction_replays`: 0
  - `strategy_replay_runs`: 0
- Recent history scan over the last 7 days did not show any committed source code writing into those replay tables.

Interpretation:

- The dirty file contains local schema materialization without replay data rows.
- There is no evidence here of a merged PR writing production replay data.
- There is no evidence of a backfill job or registry mutation caused by committed source code in the last 7 days.

## 3. Disposition

Action taken:

- Restored the file to `HEAD` with `git checkout HEAD -- data/lottery_v2.db`.

No hot-fix PR is required from this investigation.

## 4. Restore Command

```bash
git checkout HEAD -- data/lottery_v2.db
```

## 5. Final Marker

- `P3_DB_DIRT_ROOT_CAUSE_LOCAL_DEV_ONLY`
