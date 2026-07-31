-- P188 Production DB Migration SQL Log
-- Date: 2026-06-01
-- Repo: /Users/kelvin/Kelvin-WorkSpace/LotteryNew, branch: main
-- Authorization: YES execute P188 production DB migration from main 54462 to reconciled 94924
--   using P185 rehearsal SQL, approve MAX(id) dedup dropping 160 null-provenance duplicate rows,
--   create timestamped backup, no controlled_apply
-- Backup: backups/p188_lottery_v2_backup_20260601_153821.db (54462 rows, integrity ok)

-- Step C-1: WAL mode
PRAGMA journal_mode=WAL;

-- Step C-2/3: Create replacement table with bet_index + UNIQUE(…, bet_index)
CREATE TABLE strategy_prediction_replays_new (
  id INTEGER PRIMARY KEY AUTOINCREMENT, lottery_type TEXT NOT NULL,
  target_draw TEXT NOT NULL, target_date TEXT, strategy_id TEXT NOT NULL,
  strategy_name TEXT, strategy_version TEXT, history_cutoff_draw TEXT,
  replay_status TEXT NOT NULL, reject_reason TEXT, predicted_numbers TEXT,
  predicted_special INTEGER, actual_numbers TEXT, actual_special INTEGER,
  hit_numbers TEXT, hit_count INTEGER DEFAULT 0, special_hit INTEGER DEFAULT 0,
  replay_run_id TEXT, generated_at TEXT DEFAULT (datetime('now')),
  truth_level TEXT DEFAULT NULL, controlled_apply_id TEXT DEFAULT NULL,
  source TEXT DEFAULT NULL, provenance_hash TEXT DEFAULT NULL,
  provenance_source TEXT DEFAULT NULL, dry_run INTEGER DEFAULT 0,
  prediction_cutoff_date TEXT, prediction_generated_at TEXT,
  bet_index INTEGER NOT NULL DEFAULT 1,
  UNIQUE(lottery_type, target_draw, strategy_id, bet_index));

-- Step C-4: Insert deduplicated base rows (MAX(id) per group, bet_index=1)
-- Result: 54302 rows
INSERT INTO strategy_prediction_replays_new
  SELECT id,lottery_type,target_draw,target_date,strategy_id,strategy_name,
    strategy_version,history_cutoff_draw,replay_status,reject_reason,
    predicted_numbers,predicted_special,actual_numbers,actual_special,
    hit_numbers,hit_count,special_hit,CAST(replay_run_id AS TEXT),
    generated_at,truth_level,controlled_apply_id,source,provenance_hash,
    provenance_source,dry_run,prediction_cutoff_date,prediction_generated_at,1
  FROM strategy_prediction_replays
  WHERE id IN (SELECT MAX(id) FROM strategy_prediction_replays
               GROUP BY lottery_type,target_draw,strategy_id);
-- Verified: 54302 rows, 0 duplicates

-- Step C-6: Import multi-bet rows from zen-gates (read-only)
ATTACH 'file:/Users/kelvin/Kelvin-WorkSpace/LotteryNew/.claude/worktrees/zen-gates-ff6802/lottery_api/data/lottery_v2.db?mode=ro' AS zg;
INSERT INTO strategy_prediction_replays_new
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
-- Verified: 40622 rows imported, final=94924, per-lottery EXACT, bet_index dist EXACT, 0 dups
DETACH zg;

-- Step C-13/14: Table swap + index
DROP TABLE strategy_prediction_replays;
ALTER TABLE strategy_prediction_replays_new RENAME TO strategy_prediction_replays;
CREATE INDEX IF NOT EXISTS idx_spr_bet_index ON strategy_prediction_replays(bet_index);

-- Post-migration verification
PRAGMA integrity_check;           -- ok
SELECT COUNT(*) FROM strategy_prediction_replays;  -- 94924
