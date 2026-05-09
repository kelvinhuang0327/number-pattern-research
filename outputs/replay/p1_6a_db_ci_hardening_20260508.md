# P1-6A DB CI Hardening Report

Date: 2026-05-08  
Branch: `main`  
Workspace: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge`

## 1. Executive Summary
P1-6A completed with a lowest-risk implementation path for current repository state: no existing GitHub Actions workflows were found, while `requires_db` guard and `LOTTERY_TEST_DB_PATH` support already exist.  
This round adds explicit executable validation paths for:
- default replay governance validation (DB optional, `requires_db` may skip), and
- dedicated DB validation (DB required; missing DB fails fast).

No Replay API behavior was changed. No product behavior was changed.

## 2. Current DB Test Behavior
- `pytest.ini` registers marker `requires_db`.
- `tests/conftest.py` skips `requires_db` tests when DB fixture is unavailable.
- DB-dependent coverage sits in:
  - `tests/test_strategy_replay_history_cutoff_integrity.py`
  - `tests/test_replay_freshness_cadence.py` (only `TestFreshnessCadence`)
  - `tests/test_replay_api_contract.py`
- Non-DB replay governance coverage remains runnable without DB:
  - `tests/test_randomness_audit_cadence.py`
  - `tests/test_replay_browser_smoke.py`
  - `tests/test_replay_freshness_cadence.py::TestCadencePolicyLogic`

Observed baseline behavior in this workspace:
- Full suite command result: `57 passed, 32 skipped, 1 warning`
- DB-dependent tests are currently skipped when DB file is absent.

## 3. Chosen Approach
Chosen approach: **Output B (Local Dedicated DB Simulation scripts)** with a clear **default/dedicated matrix**.

Rationale by decision rule:
1. `.github/workflows/` does not exist in this repository (no existing CI config to safely extend in this round).
2. DB guard and env-path control already exist, so a script-based validation matrix is the fastest low-risk hardening step.
3. In-memory fixture implementation is intentionally deferred to avoid schema/seed drift risk in this round.

Implemented:
- `scripts/run_replay_ci_default_validation.py`
- `scripts/run_replay_ci_db_validation.py`

## 4. Why This Approach Is Lowest Risk
- No changes to Replay API or runtime logic.
- No changes to product/UI behavior.
- No test semantic weakening.
- Dedicated DB path now has explicit fail-fast behavior when DB fixture is missing (no false green).
- Creates an immediately runnable path for local/CI wrappers to call, while keeping fixture design choices open.

## 5. Files Changed
- Added `scripts/run_replay_ci_default_validation.py`
- Added `scripts/run_replay_ci_db_validation.py`
- Added `outputs/replay/p1_6a_db_ci_hardening_20260508.md`

## 6. Default CI Path
Command:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py
```

Underlying pytest target set:
- `tests/test_randomness_audit_cadence.py`
- `tests/test_strategy_replay_history_cutoff_integrity.py`
- `tests/test_replay_browser_smoke.py`
- `tests/test_replay_api_contract.py`
- `tests/test_replay_freshness_cadence.py`

Expected behavior:
- DB missing: non-DB tests pass; `requires_db` tests skip.
- DB present: all tests can execute.

## 7. Dedicated DB CI Path
Command:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_db_validation.py
```

Behavior:
1. Resolves DB path from `--db-path` > `LOTTERY_TEST_DB_PATH` > default DB path.
2. If DB file is missing, exits non-zero immediately with explicit error.
3. Runs only DB-dependent test files with `-m requires_db`.
4. Enforces zero-skip expectation for dedicated path; if skips remain, exits non-zero.

This prevents “DB-required lane” from silently passing while not actually running DB tests.

## 8. Validation Results

### 8.1 Required default validation command

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_randomness_audit_cadence.py \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_browser_smoke.py \
  tests/test_replay_api_contract.py \
  tests/test_replay_freshness_cadence.py \
  -q
```

Result:
- `57 passed, 32 skipped, 1 warning`

### 8.2 Required DB marker inspection command

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_freshness_cadence.py \
  tests/test_replay_api_contract.py \
  --collect-only -q
```

Result:
- `36 tests collected` (DB-dependent + policy-logic tests are visible in collection)

### 8.3 New script smoke tests

Default path script:
- Command: `/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_default_validation.py`
- Result: `57 passed, 32 skipped, 1 warning`

Dedicated DB path script:
- Command: `/Library/Developer/CommandLineTools/usr/bin/python3 scripts/run_replay_ci_db_validation.py`
- Result: **exit code 2** with explicit DB-missing error (expected in DB-absent workspace)

## 9. What Was Not Changed
- No replay generation.
- No strategy mining.
- No edge discovery.
- No Replay API behavior change.
- No active strategy state change.
- No DB files committed.
- No production outcome write.
- No `test_mab_ensemble.py` changes.
- No `index.html` changes.
- No frontend redesign branch operations.

## 10. Remaining Risks
1. Repository still has no native GitHub Actions workflow for replay validation orchestration.
2. Dedicated DB lane currently depends on external DB fixture provisioning policy (path + source of fixture).
3. Existing tests include class-level `skipif(not DB_PATH.exists())`; future enhancement can unify skip control via a single env-aware policy hook.

## 11. Follow-up Tasks
1. Add `.github/workflows/replay-validation.yml` with two jobs:
   - default replay validation (skip-allowed),
   - dedicated DB validation (fixture-required, fail-fast).
2. Decide fixture source for dedicated lane:
   - secure artifact download, or
   - controlled prebuilt DB snapshot path.
3. Optional test-hardening: replace duplicated class-level DB `skipif` checks with a centralized env-aware guard to reduce drift.

## 12. Final Recommendation
Adopt the new scripts immediately as the canonical replay CI matrix entrypoints.  
In the next round, wire these commands into GitHub Actions with an explicit DB-provisioned job so B2 moves from policy acceptance to fully automated CI enforcement.

---

Compliance confirmation:
- no replay generation
- no strategy mining
- no edge discovery
- no Replay API behavior change
- no active strategy state change
- no DB files committed
- no production outcome write
