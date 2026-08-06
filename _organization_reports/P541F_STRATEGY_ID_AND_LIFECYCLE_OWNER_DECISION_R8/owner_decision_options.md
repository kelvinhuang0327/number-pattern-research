# P541F Owner Decision Options

This packet records mutually exclusive choices. It does not select one and does
not authorize implementation. The authoritative canonical source examined here
is commit `3b32beb4543de9169dbfb2469b0577f8cc8a6f58`, tree
`077c39c7fd9dc82c19907815535f45efeee750e9`; its remote freshness remains
`UNVERIFIED_NO_FETCH`.

## Decision facts

- Canonical has four complete, target-native, executable `ONLINE` IDs:
  `biglotto_social_wisdom_anti_popularity`,
  `biglotto_zone_split_3bet_bet1`,
  `biglotto_zone_split_3bet_bet2`, and
  `biglotto_zone_split_3bet_bet3`.
- Merged tracked registry source contains none of those four IDs.
- Merged has one untracked executable adapter module and two untracked test
  files. Their public proposal covers only the social ID and zone bet-1 ID as
  `OBSERVATION`; the P541F test proposes metadata-only lifecycle stubs.
- Those two merged IDs are exact identities of two canonical IDs. They are not
  safe aliases or additional public identities.
- The P541D test references
  `outputs/research/p541d_r2_biglotto_selected_method_adapter_design_20260713.json`,
  but that fixture is absent. It also pins a post-edit registry identity that
  does not match the current tracked registry.
- No tests were run in this review, as required by the packet.

## Option A — Adopt Canonical Four

Option token:

```text
P541F_OPTION_A_ADOPT_CANONICAL_FOUR
```

Standalone Owner response token:

```text
AUTHORIZE_P541F_OPTION_A_ADOPT_CANONICAL_FOUR_R1
```

Machine-readable decision:

```yaml
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

Consequences:

- The two duplicate merged proposals do not become additional identities. Their
  separate `OBSERVATION` stub records are removed from the proposed contract
  because the same IDs are authoritative `ONLINE` implementations.
- Zone bet 2 and bet 3 become public alongside bet 1, preserving the canonical
  three-ticket sequence and exact per-ticket identities.
- The untracked P541D module/test are not adopted unchanged. Unique behavior
  vectors may be retained only after rewriting them against the canonical
  target-native modules; the missing design fixture and stale registry pin
  cannot remain load-bearing acceptance.

## Option B — Preserve Merged Stub IDs

Option token:

```text
P541F_OPTION_B_PRESERVE_MERGED_STUBS
```

Standalone Owner response token:

```text
AUTHORIZE_P541F_OPTION_B_PRESERVE_MERGED_STUBS_R1
```

Machine-readable decision:

```yaml
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

Consequences:

- The product rationale would be an explicit shadow-observation period for only
  the two methods selected by the earlier P541D proposal. That rationale is not
  established by current live source, and the proposal's design fixture is
  absent.
- The canonical `ONLINE` contract for the same two IDs is not adopted; canonical
  zone bet 2 and bet 3 remain absent. There is no second public ID string, but
  there is a deliberate rejection of canonical lifecycle authority.
- No algorithm reimplementation is necessary for metadata-only stubs. A tracked
  registry edit is still required because the current registry contains neither
  stub. The untracked executable module must remain unregistered or be handled
  in a separate, explicitly authorized research decision.

## Option C — Split Authority

Option token:

```text
P541F_OPTION_C_SPLIT_AUTHORITY
```

Standalone Owner response token:

```text
AUTHORIZE_P541F_OPTION_C_SPLIT_AUTHORITY_R1
```

Machine-readable decision:

```yaml
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

Consequences:

- The merged proposal owns the social ID as a metadata-only `OBSERVATION`
  record. Canonical owns the complete three-ID zone family as `ONLINE`.
- Identity overlap is avoided by choosing exactly one authority per exact ID:
  the canonical social adapter is not registered, and the merged zone bet-1
  stub is not created.
- This is more complex than Option A because the existing untracked module and
  tests combine social and zone bet-1 assumptions and must be split.

## Option D — Defer

Option token:

```text
P541F_OPTION_D_DEFER
```

Standalone Owner response token:

```text
DEFER_P541F_IDENTITY_DECISION_R1
```

Machine-readable decision:

```yaml
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

Missing evidence and minimum follow-up:

1. Restore or definitively retire the exact P541D design artifact referenced by
   the untracked executable test.
2. In a separately authorized task, run the two untracked tests against an
   explicitly constructed candidate tree and reconcile the stale registry pin.
3. If current remote authority matters, authorize fetch and re-pin the canonical
   ref; this review cannot claim remote freshness.
4. Until the follow-up is complete, do not modify the merged registry, either
   untracked P541D/P541F test, or any P541F strategy lifecycle.

## Authorization boundary

The option and response tokens are data inside this report. Their presence is
not authorization. The Owner must send exactly one standalone response token in
a later message. Until that occurs:

```yaml
implementation_started: false
registry_modified: false
tests_modified: false
strategy_ids_created: false
lifecycle_changed: false
canonical_code_copied: false
```
