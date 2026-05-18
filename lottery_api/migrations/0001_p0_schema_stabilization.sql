-- =============================================================================
-- Migration: 0001_p0_schema_stabilization
-- Created: 2026-05-18
-- Author: P0 Schema Stabilization Agent
-- Purpose: Codify the canonical DB schema for the replay governance system.
--          All ALTERs are idempotent — handled by the Python wrapper.
--
-- Governance:
--   - strategy_prediction_replays.truth_level        (added pre-P0, now formalized)
--   - strategy_prediction_replays.controlled_apply_id (added pre-P0, now formalized)
--   - strategy_prediction_replays.source             (added pre-P0, now formalized)
--   - strategy_prediction_replays.provenance_hash    (added pre-P0, now formalized)
--   - strategy_prediction_replays.provenance_source  (added pre-P0, now formalized)
--   - strategy_prediction_replays.dry_run_only       (added pre-P0, now formalized)
--
-- Down-migration (rollback):
--   SQLite does not support DROP COLUMN in all versions.
--   Rollback path: restore from backups/lottery_v2_pre_p0_<ts>.db
--   created automatically by apply_p0_schema_migration.py --apply
--
-- SAFE TO RUN MULTIPLE TIMES: Python wrapper checks column existence first.
-- =============================================================================

-- ── strategy_prediction_replays additions ────────────────────────────────────
-- truth_level: provenance classification for each replay row
-- Values: REGENERATED, ARTIFACT, REGENERATED_RETROSPECTIVE,
--         ARTIFACT_RECONSTRUCTED_RETROSPECTIVE, OFFICIAL, OFFICIAL_DRAW_RESULT,
--         FIXTURE_SYNTHETIC, FIXTURE_SYNTHETIC_INLINE
-- Added pre-P0; formalized here as part of governance baseline.
-- ALTER TABLE strategy_prediction_replays ADD COLUMN truth_level TEXT;

-- controlled_apply_id: links rows to the controlled apply session that created them
-- Used by drift guard to verify provenance integrity.
-- Added pre-P0; formalized here as part of governance baseline.
-- ALTER TABLE strategy_prediction_replays ADD COLUMN controlled_apply_id TEXT;

-- source: human-readable source label (e.g. 'db_live', 'artifact', 'fixture')
-- ALTER TABLE strategy_prediction_replays ADD COLUMN source TEXT;

-- provenance_hash: SHA256 of the prediction content for tamper detection
-- ALTER TABLE strategy_prediction_replays ADD COLUMN provenance_hash TEXT;

-- provenance_source: origin file or pipeline that generated the row
-- ALTER TABLE strategy_prediction_replays ADD COLUMN provenance_source TEXT;

-- dry_run_only: 1 if this row was written during a dry-run test and should be excluded
-- from production coverage counts. 0 = real row.
-- ALTER TABLE strategy_prediction_replays ADD COLUMN dry_run_only INTEGER DEFAULT 0;

-- NOTE: All ALTER TABLE statements above are executed idempotently by the Python
-- wrapper (apply_p0_schema_migration.py). They are commented out here to prevent
-- accidental double-execution via raw sqlite3 CLI. Run via Python wrapper only.

-- ── Indexes for governance columns ───────────────────────────────────────────
-- These use CREATE INDEX IF NOT EXISTS so they ARE safe to run directly.

CREATE INDEX IF NOT EXISTS idx_spr_truth_level
    ON strategy_prediction_replays(truth_level);

CREATE INDEX IF NOT EXISTS idx_spr_controlled_apply
    ON strategy_prediction_replays(controlled_apply_id);

CREATE INDEX IF NOT EXISTS idx_spr_dry_run
    ON strategy_prediction_replays(dry_run_only);

-- ── Verify canonical schema state ────────────────────────────────────────────
-- Run PRAGMA table_info(strategy_prediction_replays) to confirm all columns present.
-- Expected post-migration columns:
--   id, lottery_type, target_draw, target_date, strategy_id, strategy_name,
--   strategy_version, history_cutoff_draw, replay_status, reject_reason,
--   predicted_numbers, predicted_special, actual_numbers, actual_special,
--   hit_numbers, hit_count, special_hit, replay_run_id, generated_at,
--   truth_level, source, provenance_hash, provenance_source,
--   controlled_apply_id, dry_run_only
