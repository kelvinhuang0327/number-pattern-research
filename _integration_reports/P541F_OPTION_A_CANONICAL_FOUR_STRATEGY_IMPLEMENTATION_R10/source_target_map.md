# P541F Option A source-to-target map

Canonical repository: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`  
Canonical commit: `3b32beb4543de9169dbfb2469b0577f8cc8a6f58`  
Target repository: `/Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged`

## `biglotto_social_wisdom_anti_popularity`

```yaml
strategy_id: biglotto_social_wisdom_anti_popularity
canonical_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
canonical_registry_path: lottery_api/models/replay_strategy_registry.py
canonical_implementation_path: lottery_api/models/biglotto_social_wisdom_adapter.py
canonical_adapter_path: lottery_api/models/biglotto_social_wisdom_adapter.py
canonical_test_paths:
  - tests/test_biglotto_social_wisdom_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
target_registry_path: lottery_api/models/replay_strategy_registry.py
target_implementation_path: lottery_api/models/biglotto_social_wisdom_adapter.py
target_adapter_path: lottery_api/models/biglotto_social_wisdom_adapter.py
target_test_paths:
  - tests/test_biglotto_social_wisdom_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
migration_action: COPY_EXACT_ADAPTER_AND_TESTS_PLUS_MINIMAL_REGISTRY_WIRING
```

## `biglotto_zone_split_3bet_bet1`

```yaml
strategy_id: biglotto_zone_split_3bet_bet1
canonical_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
canonical_registry_path: lottery_api/models/replay_strategy_registry.py
canonical_implementation_path: lottery_api/models/biglotto_zone_split_adapter.py
canonical_adapter_path: lottery_api/models/biglotto_zone_split_adapter.py
canonical_test_paths:
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
target_registry_path: lottery_api/models/replay_strategy_registry.py
target_implementation_path: lottery_api/models/biglotto_zone_split_adapter.py
target_adapter_path: lottery_api/models/biglotto_zone_split_adapter.py
target_test_paths:
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
migration_action: COPY_EXACT_ADAPTER_FIXTURE_AND_TESTS_PLUS_MINIMAL_REGISTRY_WIRING
```

## `biglotto_zone_split_3bet_bet2`

```yaml
strategy_id: biglotto_zone_split_3bet_bet2
canonical_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
canonical_registry_path: lottery_api/models/replay_strategy_registry.py
canonical_implementation_path: lottery_api/models/biglotto_zone_split_adapter.py
canonical_adapter_path: lottery_api/models/biglotto_zone_split_adapter.py
canonical_test_paths:
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
target_registry_path: lottery_api/models/replay_strategy_registry.py
target_implementation_path: lottery_api/models/biglotto_zone_split_adapter.py
target_adapter_path: lottery_api/models/biglotto_zone_split_adapter.py
target_test_paths:
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
migration_action: COPY_EXACT_ADAPTER_FIXTURE_AND_TESTS_PLUS_MINIMAL_REGISTRY_WIRING
```

## `biglotto_zone_split_3bet_bet3`

```yaml
strategy_id: biglotto_zone_split_3bet_bet3
canonical_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
canonical_registry_path: lottery_api/models/replay_strategy_registry.py
canonical_implementation_path: lottery_api/models/biglotto_zone_split_adapter.py
canonical_adapter_path: lottery_api/models/biglotto_zone_split_adapter.py
canonical_test_paths:
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
target_registry_path: lottery_api/models/replay_strategy_registry.py
target_implementation_path: lottery_api/models/biglotto_zone_split_adapter.py
target_adapter_path: lottery_api/models/biglotto_zone_split_adapter.py
target_test_paths:
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
migration_action: COPY_EXACT_ADAPTER_FIXTURE_AND_TESTS_PLUS_MINIMAL_REGISTRY_WIRING
```

## Supporting dependency

`lottery_api/models/social_wisdom_predictor.py` is already byte-identical to
the pinned canonical object (`sha256:
a00829b5d875cb8202c3bbd90ad7202fa6b95f568e3e8d821a6cdbffe6a95e3b`)
and requires no target write.
