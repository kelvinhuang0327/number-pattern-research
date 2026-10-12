Owner Authorization: AUTHORIZE_P541F_REGISTRY_SNAPSHOT_TEST_CONTRACT_MIGRATION_R10A

# [Continuation Delta — P541F_REGISTRY_SNAPSHOT_TEST_CONTRACT_MIGRATION_R10A]

```yaml
ORIGINAL_TASK_RULES_INHERITED: YES
SECOND_CONFIRMATION_REQUIRED: NO

UPDATED_ALLOWLIST:
  stale_registry_snapshot_test_paths:
    - tests/test_replay_strategy_lifecycle_registry.py
    - tests/test_replay_strategy_registry_online_candidates.py

STALE_TEST_NODES:
  - tests/test_replay_strategy_lifecycle_registry.py::TestOnlineStrategiesUnchanged::test_registry_contains_exactly_online_ids
  - tests/test_replay_strategy_lifecycle_registry.py::TestOnlineStrategiesUnchanged::test_list_strategies_online_filter_returns_all_eight
  - tests/test_replay_strategy_lifecycle_registry.py::TestDataIntegrity::test_total_adapter_count
  - tests/test_replay_strategy_lifecycle_registry.py::TestDataIntegrity::test_list_strategies_total_count
  - tests/test_replay_strategy_registry_online_candidates.py::TestRegistryCount::test_total_adapter_count_is_18
  - tests/test_replay_strategy_registry_online_candidates.py::TestRegistryCount::test_list_strategies_total_count_is_18
  - tests/test_replay_strategy_registry_online_candidates.py::TestRegistryCount::test_online_count_is_8
  - tests/test_replay_strategy_registry_online_candidates.py::TestNewOnlineStrategiesExist::test_all_8_online_ids_present

FROZEN_PRODUCTION_PATHS:
  - lottery_api/models/biglotto_social_wisdom_adapter.py
  - lottery_api/models/biglotto_zone_split_adapter.py
  - lottery_api/models/replay_strategy_registry.py
  - lottery_api/models/social_wisdom_predictor.py
  - lottery_api/models/p541d_r2_biglotto_selected_adapters.py

EXPECTED_HEAD:
  3d6df001da3a0633ab91f164d722b595ca76d2e1
```

The original R10A contract is unchanged. Edit only the minimal assertion
neighborhoods for the eight nodes above. The authoritative post-Option-A
registry baseline is 22 total entries, 12 ONLINE entries, and the existing
eight ONLINE IDs plus these four IDs:

- `biglotto_social_wisdom_anti_popularity`
- `biglotto_zone_split_3bet_bet1`
- `biglotto_zone_split_3bet_bet2`
- `biglotto_zone_split_3bet_bet3`

Do not edit `tests/test_replay_strategy_lifecycle_contract.py`: its separate
`total == 16` pin includes an unrelated pre-P541F P1.3 gap and is not authorized
by this continuation. Do not edit the P541D proposal, add production or registry
paths, change lifecycle or product semantics, or infer commit/push/PR authority.

