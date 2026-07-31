-- P184 Controlled DB Migration Rehearsal SQL Log
-- Date: 2026-06-01
-- Target: TEMP DB only (outputs/research/power_lotto/p184_rehearsal/lottery_v2_p184_temp_rehearsal_20260601.db)
-- Production DB: NOT TOUCHED
-- Authorization: YES start P184 controlled DB migration rehearsal on temp copy only

-- Step 3: Create replacement table with bet_index and new UNIQUE constraint
CREATE TABLE strategy_prediction_replays_new (
  id                       INTEGER PRIMARY KEY AUTOINCREMENT,
  lottery_type             TEXT NOT NULL,
  target_draw              TEXT NOT NULL,
  target_date              TEXT,
  strategy_id              TEXT NOT NULL,
  strategy_name            TEXT,
  strategy_version         TEXT,
  history_cutoff_draw      TEXT,
  replay_status            TEXT NOT NULL,
  reject_reason            TEXT,
  predicted_numbers        TEXT,
  predicted_special        INTEGER,
  actual_numbers           TEXT,
  actual_special           INTEGER,
  hit_numbers              TEXT,
  hit_count                INTEGER DEFAULT 0,
  special_hit              INTEGER DEFAULT 0,
  replay_run_id            INTEGER,
  generated_at             TEXT DEFAULT (datetime('now')),
  truth_level              TEXT DEFAULT NULL,
  controlled_apply_id      TEXT DEFAULT NULL,
  source                   TEXT DEFAULT NULL,
  provenance_hash          TEXT DEFAULT NULL,
  provenance_source        TEXT DEFAULT NULL,
  dry_run                  INTEGER DEFAULT 0,
  prediction_cutoff_date   TEXT,
  prediction_generated_at  TEXT,
  bet_index                INTEGER NOT NULL DEFAULT 1,
  UNIQUE(lottery_type, target_draw, strategy_id, bet_index),
  FOREIGN KEY (replay_run_id) REFERENCES strategy_replay_runs(id)
);

-- Step 4: Insert deduplicated rows (keep MAX(id) per group to resolve duplicates)
-- For non-duplicate rows: all qualify
-- For duplicate groups (same lottery_type, target_draw, strategy_id): keep the row with MAX(id)
INSERT INTO strategy_prediction_replays_new
  SELECT id, lottery_type, target_draw, target_date, strategy_id,
         strategy_name, strategy_version, history_cutoff_draw,
         replay_status, reject_reason, predicted_numbers, predicted_special,
         actual_numbers, actual_special, hit_numbers, hit_count, special_hit,
         replay_run_id, generated_at, truth_level, controlled_apply_id,
         source, provenance_hash, provenance_source, dry_run,
         prediction_cutoff_date, prediction_generated_at,
         1 as bet_index
  FROM strategy_prediction_replays
  WHERE id IN (
    SELECT MAX(id)
    FROM strategy_prediction_replays
    GROUP BY lottery_type, target_draw, strategy_id
  );

-- Step 5-6: Verify counts
SELECT COUNT(*) as new_table_rows FROM strategy_prediction_replays_new;
-- Expected: 54302 (54462 - 160 dedup drops)

-- Step 7: Verify no duplicates under new constraint
SELECT COUNT(*) as dup_check FROM (
  SELECT lottery_type, target_draw, strategy_id, bet_index, COUNT(*)
  FROM strategy_prediction_replays_new
  GROUP BY lottery_type, target_draw, strategy_id, bet_index
  HAVING COUNT(*) > 1
);
-- Expected: 0

-- Step 8-9: Table swap
DROP TABLE strategy_prediction_replays;
ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replays;
CREATE INDEX idx_spr_bet_index ON strategy_prediction_replays(bet_index);

-- Step 10-11: Verify final state
SELECT COUNT(*) as final_rows FROM strategy_prediction_replays;
PRAGMA table_info(strategy_prediction_replays);
PRAGMA integrity_check;
