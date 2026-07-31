# P541F Option A bounded verification

## Source identity

- Canonical commit readability: PASS —
  `git cat-file -e 3b32beb4543de9169dbfb2469b0577f8cc8a6f58^{commit}`.
- Both adapter modules, the zone fixture, and all three focused test modules
  match the exact canonical SHA-256 values.
- The pre-existing Social Wisdom predictor already matches canonical SHA-256
  `a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b`.

## Runtime preflight

- `pytest.ini` configures only the project Python path and a `requires_db`
  marker; no coverage/build output is enabled.
- `.pytest_cache` existed before execution.
- `PYTHONDONTWRITEBYTECODE=1` and Python `-B` were used for Python commands.
- Expected runtime writes: task report root and existing `.pytest_cache/**`.
- Actual test runtime write: `.pytest_cache/v/cache/nodeids` modified.
- Unexpected runtime writes: none observed.

## AST and import

- AST parse: PASS — six changed Python files parsed.
- Import smoke: PASS — all four exact IDs resolve with `ONLINE` lifecycle;
  target adapter modules load; historical donor and lazy predictor do not load
  on registry import.

## Focused tests

Command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest \
  tests/test_biglotto_social_wisdom_adapter.py \
  tests/test_biglotto_zone_split_adapter.py \
  tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py -q
```

Result: PASS — `75 passed in 1.83s`.

## Relevant target regression

Ten exact node IDs were selected from existing registry/lifecycle tests to
cover preservation of prior ONLINE/non-ONLINE entries, registry resolution,
valid lifecycle values, uniqueness, lifecycle-count consistency, and
executable/non-executable separation.

Command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest \
  tests/test_replay_strategy_lifecycle_registry.py::TestOnlineStrategiesUnchanged::test_get_adapters_for_lottery_returns_only_online_adapters \
  tests/test_replay_strategy_lifecycle_registry.py::TestDataIntegrity::test_strategy_ids_unique_across_all_adapters \
  tests/test_replay_strategy_lifecycle_registry.py::TestDataIntegrity::test_all_lifecycle_statuses_valid \
  tests/test_replay_strategy_lifecycle_registry.py::TestDataIntegrity::test_unknown_strategy_id_returns_none_from_lifecycle_status \
  tests/test_replay_strategy_registry_online_candidates.py::TestExistingEntriesUnchanged::test_original_6_online_ids_still_present \
  tests/test_replay_strategy_registry_online_candidates.py::TestExistingEntriesUnchanged::test_original_non_online_ids_still_present \
  tests/test_replay_strategy_registry_online_candidates.py::TestExistingEntriesUnchanged::test_original_online_strategies_still_executable \
  tests/test_replay_strategy_lifecycle_contract.py::TestLifecycleCountsSchema::test_lifecycle_counts_sum_equals_total \
  tests/test_replay_strategy_lifecycle_contract.py::TestIdSets::test_exec_and_non_exec_ids_are_disjoint \
  tests/test_replay_strategy_lifecycle_contract.py::TestIdSets::test_only_online_strategies_are_executable \
  -q
```

Result: PASS — `10 passed in 0.37s`.

The full legacy registry test files were not run: several contain exact
pre-P541F total/count assertions by design. Full-suite execution is forbidden
by the owner packet; the canonical focused tests supply the new four-ID
contract while the selected node slice verifies unaffected invariants.

## Contract smoke

Each of the four authoritative IDs independently passed:

- catalog resolution;
- adapter and implementation loading;
- generation with a causal in-memory history;
- exactly six unique built-in integers in `[1, 49]`, with `special=None`;
- `InsufficientHistory` on empty history;
- `UnsupportedLotteryType` on a non-BIG_LOTTO request.

No DB, network, production output, or filesystem publication was used.

## Identity and duplication

```yaml
authoritative_ids_count: 4
duplicate_authoritative_ids: []
non_executable_stub_records_for_authoritative_ids: []
unauthorized_aggregate_ids_registered: []
all_public_ids_unique: true
```

## Static tools and diff

- Ruff: NOT RUN — TOOL NOT AVAILABLE.
- mypy: NOT RUN — TOOL NOT AVAILABLE.
- `git diff --check` on the tracked registry path: PASS.
- `git diff --no-index --check /dev/null` on all created/rewritten ordinary
  files: PASS.

## Test/run accounting before Judge

```text
LOCAL_FULL_SUITE_RUNS: 0
FOCUSED_TEST_RUNS: 1
RELEVANT_REGRESSION_RUNS: 1
INITIAL_JUDGE_RUNS: 0
DELTA_REJUDGE_RUNS: 0
FULL_JUDGE_RUNS: 0
EXACT_HEAD_CI_RUNS: 0
```
