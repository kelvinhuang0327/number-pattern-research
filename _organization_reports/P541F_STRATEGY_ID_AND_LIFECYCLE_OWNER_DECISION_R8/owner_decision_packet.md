# P541F Machine-Readable Owner Decision Packet

`implementation_authorized`, `registry_mutation_authorized`, and
`test_mutation_authorized` are `false` for every option in this packet. A token
printed below is inert report data. Authorization requires a later standalone
Owner message containing exactly one response token.

## Option A

```yaml
option_token: P541F_OPTION_A_ADOPT_CANONICAL_FOUR
response_token: AUTHORIZE_P541F_OPTION_A_ADOPT_CANONICAL_FOUR_R1
authoritative_strategy_ids:
  - biglotto_social_wisdom_anti_popularity
  - biglotto_zone_split_3bet_bet1
  - biglotto_zone_split_3bet_bet2
  - biglotto_zone_split_3bet_bet3
lifecycle_by_strategy_id:
  biglotto_social_wisdom_anti_popularity: ONLINE
  biglotto_zone_split_3bet_bet1: ONLINE
  biglotto_zone_split_3bet_bet2: ONLINE
  biglotto_zone_split_3bet_bet3: ONLINE
merged_stub_test_disposition:
  tests/test_p541d_r2_biglotto_selected_adapters.py: REWRITE_OR_SUPERSEDE_WITH_CANONICAL_TARGET_NATIVE_ACCEPTANCE
  tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py: REWRITE_TO_CANONICAL_FOUR_ONLINE_EXECUTABLE_CONTRACT
canonical_source_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
ordinary_paths_expected:
  - lottery_api/models/biglotto_social_wisdom_adapter.py
  - lottery_api/models/biglotto_zone_split_adapter.py
  - lottery_api/models/replay_strategy_registry.py
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_social_wisdom_adapter.py
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
implementation_authorized: false
registry_mutation_authorized: false
test_mutation_authorized: false
```

## Option B

```yaml
option_token: P541F_OPTION_B_PRESERVE_MERGED_STUBS
response_token: AUTHORIZE_P541F_OPTION_B_PRESERVE_MERGED_STUBS_R1
authoritative_strategy_ids:
  - biglotto_social_wisdom_anti_popularity
  - biglotto_zone_split_3bet_bet1
lifecycle_by_strategy_id:
  biglotto_social_wisdom_anti_popularity: OBSERVATION
  biglotto_zone_split_3bet_bet1: OBSERVATION
merged_stub_test_disposition:
  tests/test_p541d_r2_biglotto_selected_adapters.py: EXCLUDE_FROM_PRODUCTION_ACCEPTANCE_OR_REPAIR_MISSING_FIXTURE_AS_RESEARCH_ONLY
  tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py: RETAIN_AFTER_IMPLEMENTING_METADATA_STUBS_AND_REFRESHING_EXACT_PINS
canonical_source_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
ordinary_paths_expected:
  - lottery_api/models/replay_strategy_registry.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
implementation_authorized: false
registry_mutation_authorized: false
test_mutation_authorized: false
```

## Option C

```yaml
option_token: P541F_OPTION_C_SPLIT_AUTHORITY
response_token: AUTHORIZE_P541F_OPTION_C_SPLIT_AUTHORITY_R1
authoritative_strategy_ids:
  - biglotto_social_wisdom_anti_popularity
  - biglotto_zone_split_3bet_bet1
  - biglotto_zone_split_3bet_bet2
  - biglotto_zone_split_3bet_bet3
lifecycle_by_strategy_id:
  biglotto_social_wisdom_anti_popularity: OBSERVATION
  biglotto_zone_split_3bet_bet1: ONLINE
  biglotto_zone_split_3bet_bet2: ONLINE
  biglotto_zone_split_3bet_bet3: ONLINE
authority_by_strategy_id:
  biglotto_social_wisdom_anti_popularity: MERGED_STUB_PROPOSAL
  biglotto_zone_split_3bet_bet1: CANONICAL
  biglotto_zone_split_3bet_bet2: CANONICAL
  biglotto_zone_split_3bet_bet3: CANONICAL
merged_stub_test_disposition:
  tests/test_p541d_r2_biglotto_selected_adapters.py: SPLIT_SOCIAL_RESEARCH_EVIDENCE_FROM_SUPERSEDED_ZONE_BET1_EVIDENCE
  tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py: REWRITE_TO_ONE_SOCIAL_OBSERVATION_STUB_PLUS_THREE_CANONICAL_ZONE_ONLINE_IDS
canonical_source_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
ordinary_paths_expected:
  - lottery_api/models/biglotto_zone_split_adapter.py
  - lottery_api/models/replay_strategy_registry.py
  - tests/fixtures/biglotto_zone_split_p541d.json
  - tests/test_biglotto_zone_split_adapter.py
  - tests/test_p541d_r2_biglotto_selected_adapters.py
  - tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py
implementation_authorized: false
registry_mutation_authorized: false
test_mutation_authorized: false
```

## Option D

```yaml
option_token: P541F_OPTION_D_DEFER
response_token: DEFER_P541F_IDENTITY_DECISION_R1
authoritative_strategy_ids: []
lifecycle_by_strategy_id: {}
merged_stub_test_disposition:
  tests/test_p541d_r2_biglotto_selected_adapters.py: DEFER_UNCHANGED
  tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py: DEFER_UNCHANGED
canonical_source_commit: 3b32beb4543de9169dbfb2469b0577f8cc8a6f58
ordinary_paths_expected: []
implementation_authorized: false
registry_mutation_authorized: false
test_mutation_authorized: false
```

## Required standalone boundary

Exactly one of these may be sent by the Owner after this task:

```text
AUTHORIZE_P541F_OPTION_A_ADOPT_CANONICAL_FOUR_R1
AUTHORIZE_P541F_OPTION_B_PRESERVE_MERGED_STUBS_R1
AUTHORIZE_P541F_OPTION_C_SPLIT_AUTHORITY_R1
DEFER_P541F_IDENTITY_DECISION_R1
```

Until then:

```yaml
owner_decision_made: false
implementation_started: false
registry_modified: false
tests_modified: false
strategy_ids_created: false
lifecycle_changed: false
canonical_code_copied: false
```
