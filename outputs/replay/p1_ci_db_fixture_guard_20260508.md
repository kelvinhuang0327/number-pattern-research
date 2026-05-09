# P1-1 CI DB Fixture Guard — 2026-05-08

## Problem

PR #1 (`release/p0-replay-20260508` → `main`) had one remaining CI merge blocker:

> **7 live-DB tests would fail in CI** because `lottery_api/data/lottery_v2.db`
> is not committed and will not exist in the GitHub Actions runner environment.

Committing the DB binary was explicitly prohibited. The fix is to mark all
DB-dependent tests with `@pytest.mark.requires_db` and add conftest skip logic
so those tests are automatically skipped when the DB fixture is unavailable.

---

## Files Created / Modified

| Action | File |
|--------|------|
| CREATED | `pytest.ini` |
| CREATED | `tests/conftest.py` |
| MODIFIED | `tests/test_strategy_replay_history_cutoff_integrity.py` |
| MODIFIED | `tests/test_replay_freshness_cadence.py` |
| MODIFIED | `tests/test_replay_api_contract.py` |

No production code was touched. No replay API behavior was changed.
No replay data was modified. No DB binary was committed.

---

## Tests Marked `requires_db`

| File | Class | Tests |
|------|-------|-------|
| `test_strategy_replay_history_cutoff_integrity.py` | `TestReplayHistoryCutoffIntegrity` | 3 |
| `test_replay_freshness_cadence.py` | `TestFreshnessCadence` | 4 |
| `test_replay_api_contract.py` | `TestFreshnessContract` | 10 |
| `test_replay_api_contract.py` | `TestSummaryContract` | 7 |
| `test_replay_api_contract.py` | `TestHistoryContract` | 8 |
| **Total** | 5 classes | **32 tests** |

Tests NOT marked (no DB dependency):

| File | Class | Reason |
|------|-------|--------|
| `test_replay_freshness_cadence.py` | `TestCadencePolicyLogic` | Pure datetime math |
| `test_randomness_audit_cadence.py` | All | File / wiki checks only |
| `test_replay_browser_smoke.py` | All | HTML/JS static analysis only |

---

## DB Present Validation

Command:
```
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_freshness_cadence.py \
  tests/test_replay_api_contract.py -q
```

Result:
```
36 passed, 1 warning in 0.37s
```

- All 32 `requires_db` tests executed normally (no skips)
- All 4 `TestCadencePolicyLogic` tests passed
- No regressions

---

## DB Missing Validation

Command:
```
LOTTERY_TEST_DB_PATH=/tmp/nonexistent_lottery_v2.db \
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_freshness_cadence.py \
  tests/test_replay_api_contract.py -q
```

Result:
```
4 passed, 32 skipped, 1 warning in 0.31s
```

- 32 `requires_db` tests: SKIPPED (via conftest `pytest_runtest_setup` hook)
- 4 `TestCadencePolicyLogic` tests: PASSED (not DB-dependent, unaffected)
- Skip message: `requires local SQLite replay database fixture (checked: /tmp/nonexistent_lottery_v2.db)`
- Exit code: 0 (no failures)

---

## Non-DB Validation

Command:
```
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_randomness_audit_cadence.py \
  tests/test_replay_browser_smoke.py -q
```

Result:
```
53 passed in 0.12s
```

- 53 tests passed
- 0 skipped
- No effect from `requires_db` marker or conftest

---

## Full P0 Release Suite

Command:
```
/Library/Developer/CommandLineTools/usr/bin/python3 -m pytest \
  tests/test_randomness_audit_cadence.py \
  tests/test_strategy_replay_history_cutoff_integrity.py \
  tests/test_replay_browser_smoke.py \
  tests/test_replay_api_contract.py \
  tests/test_replay_freshness_cadence.py -q
```

Result:
```
89 passed, 1 warning in 0.39s
```

---

## How `pytest.ini` and `conftest.py` Work

### `pytest.ini`
Registers the `requires_db` marker to suppress pytest warnings:
```ini
[pytest]
markers =
    requires_db: tests that require local SQLite replay database fixture
```

### `tests/conftest.py`
Hooks into `pytest_runtest_setup`:
1. Checks if the test has `@pytest.mark.requires_db`
2. Resolves DB path: `LOTTERY_TEST_DB_PATH` env var → `lottery_api/data/lottery_v2.db`
3. If DB path does not exist → `pytest.skip(...)`

The env var `LOTTERY_TEST_DB_PATH` allows CI to control the check without
needing to rename, move, or delete any file.

---

## CI Behavior After This Change

| Environment | DB present? | `requires_db` tests | Non-DB tests |
|-------------|-------------|---------------------|--------------|
| Local dev | ✅ Yes | RUN (pass) | RUN (pass) |
| GitHub Actions CI | ❌ No | SKIPPED | RUN (pass) |
| CI with DB fixture | ✅ Yes | RUN | RUN |

In CI (no DB): exit code = 0, no failures, skips are visible in summary.

---

## What Is Still Not Included

- DB binary (`lottery_v2.db`) — NOT committed
- In-memory conftest DB fixture (Option B) — NOT implemented in this PR
- CI DB fixture provisioning (download or generate DB in CI) — NOT implemented
- `.gitignore` for `*.db-shm`, `*.db-wal` — NOT implemented (separate P1 item)
- `index.html` non-replay diff cleanup — NOT in scope

---

## Merge Impact

After this commit, merging PR #1 into `main` will result in:
- CI (no DB): 32 tests skipped, 57 tests run, 0 failed → green
- Local dev (DB present): 89 tests run, 0 skipped → green
- No replay API behavior changed
- No replay data modified
- No edge claim made
- No strategy promotion

---

## Issues Found

- `tests/test_mab_ensemble.py` has 6 pre-existing failures (KeyError) unrelated to
  P0 release scope. These are NOT part of the P1-1 commit and are out of scope.

---

## Follow-up Recommendations

| Priority | Item |
|----------|------|
| P1 | Implement CI DB fixture Option B: in-memory conftest.py with synthetic data |
| P1 | Add `.gitignore` for `*.db-shm`, `*.db-wal` |
| P1 | Review and clean `index.html` non-replay diff before merging PR #1 |
| P2 | Fix pre-existing `test_mab_ensemble.py` failures (out of P0/P1 scope) |
| P2 | Consider adding `LOTTERY_TEST_DB_PATH` documentation to `docs/REPLAY_OPERATION_SOP.md` |

---

## Final Marker

```
P1_1_CI_DB_FIXTURE_GUARD_VERIFIED
```

Evidence:
- `pytest.ini` created with `requires_db` marker definition ✅
- `tests/conftest.py` created with `pytest_runtest_setup` skip hook ✅
- `LOTTERY_TEST_DB_PATH` env override supported ✅
- 5 DB-dependent classes marked with `@pytest.mark.requires_db` (32 tests) ✅
- `TestCadencePolicyLogic` NOT marked (no DB dependency) ✅
- DB present validation: 36 passed, 0 skipped ✅
- DB missing simulation: 32 skipped, 4 passed, 0 failed ✅
- Non-DB suite: 53 passed, 0 skipped ✅
- Full P0 release suite: 89 passed ✅
- DB binary NOT committed ✅
- No replay API behavior changed ✅
- No replay data modified ✅
- No edge claim made ✅
- No force-push ✅
