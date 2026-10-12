-- Migration: 0001_p0_schema_stabilization.sql
-- Purpose: Add P0 required columns to strategy_prediction_replays
--          (truth_level, controlled_apply_id, source, provenance_hash,
--           provenance_source, dry_run)
-- Safe: All ALTER TABLE ADD COLUMN are idempotent (SQLite allows re-run
--       with identical names only if guarded in the apply script).
-- Author: P0 Single-Repo Schema Stabilization (2026-05-19)
-- Do NOT run directly; use scripts/apply_p0_schema_migration.py

-- truth_level: provenance classification for this prediction row
ALTER TABLE strategy_prediction_replays
    ADD COLUMN truth_level TEXT DEFAULT NULL;

-- controlled_apply_id: batch identifier for controlled replay apply runs
ALTER TABLE strategy_prediction_replays
    ADD COLUMN controlled_apply_id TEXT DEFAULT NULL;

-- source: data source label (e.g. 'FIXTURE', 'ARTIFACT', 'PREDICTION_LOG')
ALTER TABLE strategy_prediction_replays
    ADD COLUMN source TEXT DEFAULT NULL;

-- provenance_hash: SHA256 of original artifact for reconstruction audit
ALTER TABLE strategy_prediction_replays
    ADD COLUMN provenance_hash TEXT DEFAULT NULL;

-- provenance_source: path or identifier of the artifact used for reconstruction
ALTER TABLE strategy_prediction_replays
    ADD COLUMN provenance_source TEXT DEFAULT NULL;

-- dry_run: if 1, row was inserted in dry-run mode and should not be treated
--          as production data
ALTER TABLE strategy_prediction_replays
    ADD COLUMN dry_run INTEGER DEFAULT 0;

-- Indexes for new columns used in queries / drift guard
CREATE INDEX IF NOT EXISTS idx_spr_controlled_apply_id
    ON strategy_prediction_replays(controlled_apply_id);

CREATE INDEX IF NOT EXISTS idx_spr_truth_level
    ON strategy_prediction_replays(truth_level);
