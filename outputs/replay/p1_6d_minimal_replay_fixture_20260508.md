# P1-6D Minimal Replay DB Fixture Implementation Report

Date: 2026-05-08  
Branch: `main`  
Workspace: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge`

## 1. Executive Summary
P1-6D completed by implementing a deterministic synthetic SQLite fixture generator and wiring dedicated DB validation to run real requires_db tests without fake pass behavior.

Key outcome:
- dedicated lane can now build and use a synthetic fixture and run requires_db tests with zero skips.
- if fixture is unavailable, dedicated script still fails fast.

## 2. P1-6C Policy Baseline
Baseline inputs reviewed:
- `outputs/replay/p1_6c_db_fixture_policy_20260508.md`
- `outputs/replay/p1_6c_requires_db_dependency_map_20260508.json`

P1-6C recommendation implemented:
- Minimal Synthetic SQLite Fixture as controlled primary source.

## 3. Fixture Design
New generator:
- `scripts/build_replay_test_fixture.py`

Design principles:
- deterministic, fixed IDs/timestamps
- minimal schema only for replay requires_db tests
- synthetic rows only
- no production DB copy
- no strategy edge semantics

Output behavior:
- accepts `--output` path
- safely recreates fixture file
- defaults to `/tmp/lottery_replay_test_fixture.db`

## 4. Tables Created
Minimal tables created:
1. `strategy_replay_runs`
2. `strategy_prediction_replays`

Columns are aligned to currently executed test queries and replay route contract reads.

## 5. Seed Data Design
Deterministic seeds include:
- 3 DONE runs (BIG_LOTTO / POWER_LOTTO / DAILY_539), within cadence window
- 1 FAILED_LEGACY run (non-cadence)
- 3 replay rows with valid `history_cutoff_draw < target_draw`
- non-error rows include `predicted_numbers`, `actual_numbers`, `hit_numbers`

No seed row is derived from real production output.

## 6. Why Fixture Is Synthetic and Non-Strategic
- IDs, timestamps, and numbers are synthetic fixture values.
- data is only for schema/contract/integrity/cadence testing.
- fixture does not encode or claim validated strategy performance.
- synthetic fixture does not represent validated strategy performance.

## 7. Dedicated DB Script Integration
Updated:
- `scripts/run_replay_ci_db_validation.py`

Enhancements:
1. supports DB path precedence:
   - `--db-path`
   - `LOTTERY_REPLAY_DB_PATH`
   - `LOTTERY_TEST_DB_PATH`
   - default path
2. fail-fast exit code `2` if DB path missing
3. enforces zero-skip for dedicated lane (exit `3` if skip exists)
4. compatibility bridge for test-level fixed `skipif` paths:
   - when external fixture path is used and default DB path is absent,
     script creates temporary symlink at `lottery_api/data/lottery_v2.db`
     for test discovery, then removes it after run.

This preserves test semantics while preventing silent skip.

## 8. GitHub Actions Integration
Updated workflow:
- `.github/workflows/replay-governance-ci.yml`

Dedicated lane now:
1. builds synthetic fixture via `scripts/build_replay_test_fixture.py`
2. exports fixture path to `LOTTERY_REPLAY_DB_PATH` and `LOTTERY_TEST_DB_PATH`
3. runs `scripts/run_replay_ci_db_validation.py`

`workflow_dispatch` input `db_path` remains available as controlled override.

## 9. Validation Results

### 9.1 Fixture build
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/build_replay_test_fixture.py \
  --output /tmp/lottery_replay_test_fixture.db
```
Result:
- built at `/private/tmp/lottery_replay_test_fixture.db`
- `strategy_replay_runs=4`
- `strategy_prediction_replays=3`

### 9.2 Fixture schema inspection
Confirmed tables:
- `strategy_replay_runs`
- `strategy_prediction_replays`

Row counts:
- `strategy_replay_runs`: 4
- `strategy_prediction_replays`: 3

### 9.3 Dedicated DB validation with fixture
```bash
LOTTERY_TEST_DB_PATH=/private/tmp/lottery_replay_test_fixture.db \
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/run_replay_ci_db_validation.py
```
Result:
- `32 passed, 4 deselected, 1 warning`
- zero skipped in dedicated lane
- dedicated script returned success

### 9.4 Dedicated DB validation without fixture
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/run_replay_ci_db_validation.py
```
Result:
- exit code `2`
- explicit fixture unavailable error

### 9.5 Default validation unchanged
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/run_replay_ci_default_validation.py
```
Result:
- `57 passed, 32 skipped, 1 warning`

### 9.6 Collect-only
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_freshness_cadence.py \
  tests/test_replay_api_contract.py \
  --collect-only -q
```
Result:
- `36 tests collected`

## 10. Zero-Skip / No-Fake-Pass Evidence
- Dedicated lane with valid synthetic fixture: requires_db tests execute and pass.
- Dedicated lane without fixture: explicit fail-fast, non-zero exit.
- Dedicated script rejects skip-based false green in dedicated mode.

## 11. Files Changed
- Added `scripts/build_replay_test_fixture.py`
- Modified `scripts/run_replay_ci_db_validation.py`
- Modified `.github/workflows/replay-governance-ci.yml`
- Added `outputs/replay/p1_6d_minimal_replay_fixture_20260508.md`
- Added `outputs/replay/p1_6d_fixture_schema_summary_20260508.json`

## 12. What Was Not Changed
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
- no test semantics relaxation for requires_db guard

## 13. Remaining Risks
1. Future replay schema/query changes may require fixture seed/schema updates.
2. Dedicated lane still depends on fixture build step health in CI runtime.
3. Route-level contract additions may expand minimal required dataset.

## 14. Follow-up Tasks
1. Add lightweight fixture integrity check step (schema checksum/version marker).
2. Add CI annotation/log export for fixture metadata in dedicated lane.
3. Consider making dedicated lane mandatory after several stable runs.

## 15. Final Recommendation
Adopt this synthetic fixture path as the dedicated DB lane default.  
It is deterministic, synthetic, non-strategic, and preserves fail-fast/no-fake-pass behavior.

Compliance confirmation:
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
- synthetic fixture does not represent validated strategy performance
