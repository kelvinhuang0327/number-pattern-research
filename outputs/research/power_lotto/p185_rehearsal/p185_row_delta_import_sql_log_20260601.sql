-- P185 Row Delta Import Rehearsal SQL Log
-- Date: 2026-06-01
-- Target: TEMP DB only (outputs/research/power_lotto/p185_rehearsal/lottery_v2_p185_temp_rehearsal_20260601.db)
-- Production DB: NOT TOUCHED
-- Authorization: YES start P185 row delta import rehearsal on temp copy only

-- PHASE B: Schema migration with dedup
-- Step B-5/6: Create replacement table
CREATE TABLE strategy_prediction_replays_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  lottery_type TEXT NOT NULL, target_draw TEXT NOT NULL, target_date TEXT,
  strategy_id TEXT NOT NULL, strategy_name TEXT, strategy_version TEXT,
  history_cutoff_draw TEXT, replay_status TEXT NOT NULL, reject_reason TEXT,
  predicted_numbers TEXT, predicted_special INTEGER, actual_numbers TEXT,
  actual_special INTEGER, hit_numbers TEXT, hit_count INTEGER DEFAULT 0,
  special_hit INTEGER DEFAULT 0, replay_run_id TEXT, generated_at TEXT DEFAULT (datetime('now')),
  truth_level TEXT DEFAULT NULL, controlled_apply_id TEXT DEFAULT NULL,
  source TEXT DEFAULT NULL, provenance_hash TEXT DEFAULT NULL,
  provenance_source TEXT DEFAULT NULL, dry_run INTEGER DEFAULT 0,
  prediction_cutoff_date TEXT, prediction_generated_at TEXT,
  bet_index INTEGER NOT NULL DEFAULT 1,
  UNIQUE(lottery_type, target_draw, strategy_id, bet_index)
);

-- Step B-7: Insert deduplicated rows (MAX(id) per group, bet_index=1)
INSERT INTO strategy_prediction_replays_new
  SELECT id,lottery_type,target_draw,target_date,strategy_id,strategy_name,
    strategy_version,history_cutoff_draw,replay_status,reject_reason,
    predicted_numbers,predicted_special,actual_numbers,actual_special,
    hit_numbers,hit_count,special_hit,CAST(replay_run_id AS TEXT),
    generated_at,truth_level,controlled_apply_id,source,provenance_hash,
    provenance_source,dry_run,prediction_cutoff_date,prediction_generated_at,1
  FROM strategy_prediction_replays
  WHERE id IN (
    SELECT MAX(id) FROM strategy_prediction_replays
    GROUP BY lottery_type, target_draw, strategy_id
  );
-- Result: 54302 rows inserted

-- Step B-12: Table swap
DROP TABLE strategy_prediction_replays;
ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replays;
CREATE INDEX idx_spr_bet_index ON strategy_prediction_replays(bet_index);

-- PHASE C: Row delta import from zen-gates (read-only ATTACH)
ATTACH 'file:/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db?mode=ro' AS zg;

-- Step C-4/5: Insert multi-bet rows (bet_index > 1) from zen-gates
INSERT INTO strategy_prediction_replays
    (lottery_type,target_draw,target_date,strategy_id,strategy_name,strategy_version,
     history_cutoff_draw,replay_status,reject_reason,predicted_numbers,predicted_special,
     actual_numbers,actual_special,hit_numbers,hit_count,special_hit,replay_run_id,
     generated_at,truth_level,controlled_apply_id,source,provenance_hash,
     provenance_source,dry_run,prediction_cutoff_date,prediction_generated_at,bet_index)
SELECT lottery_type,target_draw,target_date,strategy_id,strategy_name,strategy_version,
     history_cutoff_draw,replay_status,reject_reason,predicted_numbers,predicted_special,
     actual_numbers,actual_special,hit_numbers,hit_count,special_hit,
     CAST(replay_run_id AS TEXT),generated_at,truth_level,controlled_apply_id,source,
     provenance_hash,provenance_source,dry_run,prediction_cutoff_date,prediction_generated_at,bet_index
FROM zg.strategy_prediction_replays WHERE bet_index > 1;
-- Result: 40622 rows inserted

DETACH zg;

-- Verification
SELECT COUNT(*) FROM strategy_prediction_replays;                    -- expect 94924
SELECT lottery_type, COUNT(*) FROM strategy_prediction_replays       -- BIG_LOTTO=24140, DAILY_539=34680, POWER_LOTTO=36104
  GROUP BY lottery_type;
SELECT bet_index, COUNT(*) FROM strategy_prediction_replays          -- 1=54302,2=16581,3=15041,4=6000,5=3000
  GROUP BY bet_index ORDER BY bet_index;
PRAGMA integrity_check;                                              -- expect: ok

-- This SQL log documents the production migration path.
-- Production execution requires explicit CEO authorization phrase.
