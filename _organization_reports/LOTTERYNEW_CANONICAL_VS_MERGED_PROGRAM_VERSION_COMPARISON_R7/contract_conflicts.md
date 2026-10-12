# Contract conflicts

## P541F strategy lifecycle and executability

- Paths: `lottery_api/models/replay_strategy_registry.py`, `tests/test_p541f_r2_social_wisdom_zone_split_observation_registry.py`.
- Canonical source/test contract: `biglotto_social_wisdom_anti_popularity` plus three zone-split bet IDs are target-native, executable, and `ONLINE`.
- Merged live source: `lottery_api/models/replay_strategy_registry.py` contains none of those IDs or registration hooks.
- Merged untracked test contract: only the social ID and zone-split bet-1 ID are proposed as non-executable `OBSERVATION` stubs, but that contract is not implemented by the merged registry.
- Impact: the merged test and source are internally inconsistent, and both differ from the canonical `ONLINE` contract. Strategy identity, lifecycle filters, registry membership, and replay/generation eligibility require an Owner decision before reconciliation.

## Ingest post-insert side effects

- Path: `lottery_api/routes/ingest.py`.
- Canonical contract: post-insert refresh calls only `scheduler.load_data()`.
- Merged live contract: the same endpoints additionally refresh payout outputs, resolve pending predictions, adjust strategy weights, apply learning integration, and schedule the next draw.
- Impact: the same API call has materially different DB/filesystem/background effects. Direct merge or replacement is unsafe without an explicit side-effect contract.

## Dirty-path collision kept outside equivalence

- Path: `index.html`.
- Classification: `DIRTY_PATH_COLLISION`.
- It is excluded from automatic equivalence, semantic adoption, and modification advice as required.
