-- Migration: 0002_p2_catalog_table.sql
-- Purpose: Create strategy_catalog table for P2 controlled catalog apply.
--          This table stores the P1 visibility plan entries as a persistent,
--          queryable catalog accessible to the Replay UI.
--
-- Key safety constraints:
--   - DOES NOT touch strategy_prediction_replays (replay rows)
--   - DOES NOT touch prediction_items / prediction_runs
--   - catalog_visibility_state is informational; does NOT affect lifecycle_state
--   - dry_run_only=1 rows are inert catalog entries; never used for generation
--
-- Author: P2 Controlled Catalog Apply (2026-05-20)
-- Do NOT run directly; use scripts/p2_catalog_apply.py

CREATE TABLE IF NOT EXISTS strategy_catalog (
    id                          INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id                 TEXT NOT NULL,
    display_name                TEXT NOT NULL,
    lottery_type                TEXT NOT NULL,
    lifecycle_state             TEXT NOT NULL,
    catalog_visibility_state    TEXT NOT NULL,
    source_paths_json           TEXT,           -- JSON array of source paths
    artifact_source_type        TEXT,
    has_replay_rows             INTEGER NOT NULL DEFAULT 0,
    has_historical_predictions  INTEGER NOT NULL DEFAULT 0,
    replay_row_count            INTEGER NOT NULL DEFAULT 0,
    reconstructible_reason      TEXT,
    no_data_reason              TEXT,
    provenance_hash             TEXT,
    created_by_phase            TEXT NOT NULL DEFAULT 'P2',
    dry_run_only                INTEGER NOT NULL DEFAULT 1,
    created_at                  TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at                  TEXT NOT NULL DEFAULT (datetime('now')),

    -- Unique: one entry per strategy_id × lottery_type combination
    UNIQUE(strategy_id, lottery_type)
);

-- Indexes for query patterns used by replay UI and drift guard
CREATE INDEX IF NOT EXISTS idx_sc_visibility
    ON strategy_catalog(catalog_visibility_state);

CREATE INDEX IF NOT EXISTS idx_sc_lifecycle
    ON strategy_catalog(lifecycle_state);

CREATE INDEX IF NOT EXISTS idx_sc_has_replay_rows
    ON strategy_catalog(has_replay_rows);

CREATE INDEX IF NOT EXISTS idx_sc_has_historical
    ON strategy_catalog(has_historical_predictions);

CREATE INDEX IF NOT EXISTS idx_sc_strategy_id
    ON strategy_catalog(strategy_id);
