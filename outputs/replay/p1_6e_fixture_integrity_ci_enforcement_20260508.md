# P1-6E Fixture Integrity + Dedicated Lane CI Enforcement Report

Date: 2026-05-08  
Branch: `main`  
Workspace: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge`

## 1. Executive Summary
P1-6E completed by adding an explicit fixture integrity gate and hardening dedicated DB validation enforcement.

Main upgrades:
1. new fixture validator (`scripts/validate_replay_test_fixture.py`)
2. fixture metadata/versioning in generator (`fixture_metadata` table)
3. dedicated DB script supports pre-validation and still enforces zero-skip/no-fake-pass
4. workflow dedicated lane now runs fixture build -> integrity validate -> dedicated DB validation

## 2. P1-6D Baseline
P1-6D delivered synthetic fixture generation and dedicated lane integration, with:
- synthetic fixture builder
- dedicated requires_db pass path
- fail-fast when fixture missing

P1-6E extends this by adding explicit integrity verification before dedicated tests run.

## 3. Fixture Integrity Gate Design
Added:
- `scripts/validate_replay_test_fixture.py`

Validator checks:
1. DB file exists
2. required tables exist
3. required columns exist
4. metadata exists and marks synthetic-only fixture
5. minimum row counts are met
6. DONE coverage exists for required lottery types
7. `history_cutoff_draw < target_draw`
8. non-error replay rows include predicted/actual/hit fields

Validation failures return non-zero with clear error.

## 4. Fixture Metadata / Versioning
Updated builder:
- `scripts/build_replay_test_fixture.py`

Added metadata table:
- `fixture_metadata`
  - `fixture_name`
  - `fixture_version`
  - `schema_version`
  - `created_by`
  - `synthetic_only`
  - `created_at`

Current metadata:
- fixture_name: `replay_test_fixture`
- fixture_version: `v1`
- schema_version: `replay-schema-v1`
- synthetic_only: `1`

## 5. Dedicated DB Lane Enforcement
Updated:
- `scripts/run_replay_ci_db_validation.py`

Hardening:
1. supports `--validate-fixture` pre-check mode
2. invokes validator before pytest when enabled
3. fails if fixture validator fails
4. still fail-fast exit `2` when DB missing
5. still fails if requires_db tests are skipped (`exit 3`)
6. preserves no-fake-pass behavior

## 6. GitHub Actions Update
Updated:
- `.github/workflows/replay-governance-ci.yml`

Dedicated job now:
1. build synthetic fixture
2. run dedicated validation with `--validate-fixture`
3. enforce no-skip / no-fake-pass path

Default lane unchanged.

## 7. Validation Results

### 7.1 Build fixture
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/build_replay_test_fixture.py \
  --output /tmp/lottery_replay_test_fixture.db
```
Result:
- built successfully (`/private/tmp/lottery_replay_test_fixture.db`)
- metadata printed

### 7.2 Validate fixture integrity
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/validate_replay_test_fixture.py \
  --db /private/tmp/lottery_replay_test_fixture.db
```
Result:
- integrity PASS

### 7.3 Dedicated DB validation with fixture
```bash
LOTTERY_TEST_DB_PATH=/tmp/lottery_replay_test_fixture.db \
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/run_replay_ci_db_validation.py --validate-fixture
```
Result:
- `32 passed, 4 deselected, 1 warning`
- zero skipped

### 7.4 Default validation unchanged
```bash
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/run_replay_ci_default_validation.py
```
Result:
- `57 passed, 32 skipped, 1 warning`

### 7.5 Missing DB fail-fast
```bash
rm -f /tmp/lottery_replay_test_fixture_missing.db
LOTTERY_TEST_DB_PATH=/tmp/lottery_replay_test_fixture_missing.db \
/Library/Developer/CommandLineTools/usr/bin/python3 \
  scripts/run_replay_ci_db_validation.py --validate-fixture
```
Result:
- exit code `2`
- clear fixture unavailable error

## 8. Zero-Skip / No-Fake-Pass Evidence
- dedicated lane with valid fixture runs requires_db tests with zero skip.
- dedicated lane without fixture fails immediately.
- dedicated lane with invalid fixture fails integrity check before pytest.

## 9. Branch Protection Recommendation
Recommendation (policy only; no GitHub settings changed here):
1. keep default lane required now.
2. make dedicated lane required only after 5+ consecutive stable runs.
3. require dedicated lane integrity step + zero-skip proof before promotion.
4. if dedicated lane becomes required, keep manual override path documented for incident response.

## 10. Files Changed
- Added `scripts/validate_replay_test_fixture.py`
- Modified `scripts/build_replay_test_fixture.py`
- Modified `scripts/run_replay_ci_db_validation.py`
- Modified `.github/workflows/replay-governance-ci.yml`
- Added `outputs/replay/p1_6e_fixture_integrity_ci_enforcement_20260508.md`
- Added `outputs/replay/p1_6e_fixture_integrity_summary_20260508.json`

## 11. What Was Not Changed
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
- synthetic fixture does not represent validated strategy performance

## 12. Remaining Risks
1. fixture schema can still drift when tests or replay route contracts evolve.
2. metadata schema versioning is lightweight and may need stronger governance later.
3. dedicated lane still depends on CI runtime stability for fixture build/validation steps.

## 13. Follow-up Tasks
1. add schema-version assertion against expected value in workflow output annotation.
2. add CI artifact upload for fixture integrity summary logs (not DB file).
3. define explicit promotion checklist before turning dedicated lane into required check.

## 14. Final Recommendation
Adopt this integrity-gated dedicated lane as the new enforcement baseline.  
It preserves strict fail-fast semantics, prevents fake pass, and improves fixture governance while staying synthetic-only.
