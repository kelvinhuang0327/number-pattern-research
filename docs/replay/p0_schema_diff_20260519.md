# P0 Schema Diff — 2026-05-19

## Migration Applied
`lottery_api/migrations/0001_p0_schema_stabilization.sql`

## DB Path
`lottery_api/data/lottery_v2.db`

## Backup Created
`backups/lottery_v2_pre_p0_20260519_192547.db`

## Columns Added to `strategy_prediction_replays`

| Column | Type | Default | Purpose |
|--------|------|---------|---------|
| `truth_level` | TEXT | NULL | Provenance classification (REGENERATED_RETROSPECTIVE / ARTIFACT_RECONSTRUCTED_RETROSPECTIVE / OFFICIAL / OFFICIAL_DRAW_RESULT) |
| `controlled_apply_id` | TEXT | NULL | Batch identifier for controlled replay apply runs (P5-P7 will populate) |
| `source` | TEXT | NULL | Data source label (FIXTURE / ARTIFACT / PREDICTION_LOG) |
| `provenance_hash` | TEXT | NULL | SHA256 of original artifact for reconstruction audit |
| `provenance_source` | TEXT | NULL | Path or identifier of artifact used for reconstruction |
| `dry_run` | INTEGER | 0 | Flag: 1 = inserted in dry-run mode, not production data |

## Indexes Added

| Index | Table | Column |
|-------|-------|--------|
| `idx_spr_controlled_apply_id` | `strategy_prediction_replays` | `controlled_apply_id` |
| `idx_spr_truth_level` | `strategy_prediction_replays` | `truth_level` |

## Row Impact
- Rows before: **460** (all legacy)
- Rows after: **460** (unchanged)
- All new columns are NULL/0 by default — no data migration required

## Safety
- Dry-run executed first with zero errors
- DB backed up before apply
- All columns are nullable with safe defaults
- No existing rows modified
- Migration is idempotent (re-run safe)

## Test Results After Migration
- `pytest tests/test_replay_api_contract.py` → **44/44 PASS** ✅
- `scripts/replay_lifecycle_drift_guard.py --strict` → **PASS** ✅

## Why Main Repo Differs From LotteryNew-clean
The LotteryNew-clean sibling repo had 975 rows across V1/V2/legacy/P2B/P2F/P3BC controlled apply IDs.
The main repo was never the target of those apply runs. Main repo drift guard baseline updated to
reflect 460 legacy rows (all controlled_apply_id IS NULL) as the correct P0 single-repo state.
P5-P7 historical reconstruction will add rows with controlled_apply_id values in the future.
