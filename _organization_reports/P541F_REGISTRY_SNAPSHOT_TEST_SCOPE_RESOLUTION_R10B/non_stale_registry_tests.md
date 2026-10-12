# Non-stale R10 registry regression scope

R10 listed ten exact regression nodes. All ten are general preservation or
registry/lifecycle invariants; none pins the complete post-P541F registry ID set
or a fixed P541F-sensitive count.

## `tests/test_replay_strategy_lifecycle_registry.py`

- `TestOnlineStrategiesUnchanged::test_get_adapters_for_lottery_returns_only_online_adapters`
  checks that lottery-specific adapters are ONLINE.
- `TestDataIntegrity::test_strategy_ids_unique_across_all_adapters` checks
  uniqueness.
- `TestDataIntegrity::test_all_lifecycle_statuses_valid` checks lifecycle enum
  validity.
- `TestDataIntegrity::test_unknown_strategy_id_returns_none_from_lifecycle_status`
  checks unknown-ID behavior.

The same file has four separate stale assertions, so the file is allowlisted
for R10A, but only the eight-node combined stale scope in
`stale_registry_snapshot_scope.yaml` may be edited.

## `tests/test_replay_strategy_registry_online_candidates.py`

- `TestExistingEntriesUnchanged::test_original_6_online_ids_still_present`
  checks preservation by subset.
- `TestExistingEntriesUnchanged::test_original_non_online_ids_still_present`
  checks preservation by subset.
- `TestExistingEntriesUnchanged::test_original_online_strategies_still_executable`
  checks preserved executability.

The same file has four separate stale assertions, so the file is allowlisted
for R10A, but these three R10 nodes remain outside the edit neighborhoods.

## `tests/test_replay_strategy_lifecycle_contract.py`

- `TestLifecycleCountsSchema::test_lifecycle_counts_sum_equals_total` is a
  dynamic arithmetic invariant.
- `TestIdSets::test_exec_and_non_exec_ids_are_disjoint` is a dynamic
  disjointness invariant.
- `TestIdSets::test_only_online_strategies_are_executable` is a dynamic
  lifecycle/executability invariant.

This file is excluded from R10A. Its separate
`TestTotal::test_total_is_16` pin was already inconsistent with the pre-P541F
18-entry baseline documented by the other candidate files. Updating it to 22
would combine an older P1.3 contract repair with the P541F migration, violating
the packet's `no_unrelated_contract_conflict` condition.

## P541D boundary

R8 identifies `tests/test_p541d_r2_biglotto_selected_adapters.py` as the
superseded P541D proposal. It was not derived from an R10 regression node, was
not opened, and is not part of the continuation allowlist.

