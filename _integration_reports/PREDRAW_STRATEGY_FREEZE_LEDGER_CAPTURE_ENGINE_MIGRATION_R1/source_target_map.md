# Source-to-Target Map

## Task: PREDRAW_STRATEGY_FREEZE_LEDGER_CAPTURE_ENGINE_MIGRATION_R1

Source extraction root:
`/Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged/_git_ref_reference/LOTTERY_BRANCH_REF_EXTRACTION_R1/by_repository/repo_1_lotterynew/by_ref/refs_remotes_origin_task_p273a-prize-awa_0c2b9bd5/files`

Target root:
`/Users/kelvin/VibeCoding-WorkSpace/LotteryNewMeraged`

| Source Ref Relative Path | Extracted SHA-256 | Target Relative Path | Target Pre-existing | Migration Action | Source Contract Notes |
| --- | --- | --- | --- | --- | --- |
| `docs/p360a_predraw_metadata_preregistration.md` | `6152c2a19f67dad757b80a132d4cd28151fac25719253b1a1d6487355f2f944b` | `docs/p360a_predraw_metadata_preregistration.md` | False | `CREATE_FROM_SOURCE` | Documentation for predraw metadata preregistration. |
| `lottery_api/data/predraw_schedule_config.json` | `c4743850a5d644f9acb89ae4be1dbcbf14d596a22b0f46b142d4600285e7d021` | `lottery_api/data/predraw_schedule_config.json` | False | `CREATE_FROM_SOURCE` | Schedule config for predraw capture. |
| `lottery_api/data/predraw_strategy_freeze_registry.json` | `a5e1feaed2ac0d44444fb2ce7fbf9adbdb383e59aafa4943461507ff367b6f3e` | `lottery_api/data/predraw_strategy_freeze_registry.json` | False | `CREATE_FROM_SOURCE` | Freeze registry mapping strategy IDs to freeze rules. |
| `lottery_api/engine/predraw_ledger.py` | `5b2eb5d589e89b6d6a5123f7c7e4357ed3c7cf691e7e09aee993ebcdd83906ed` | `lottery_api/engine/predraw_ledger.py` | True (Identical) | `ALREADY_PRESENT_IDENTICAL` | Engine for predraw strategy freeze and ledger record creation. |
| `tools/predraw_capture_runner.py` | `08a66ce56036f1c05e940e491635ed2361b78bf8248a039752207f3ed41372f9` | `tools/predraw_capture_runner.py` | False | `CREATE_FROM_SOURCE` | Standalone CLI entrypoint for predraw capture runner. |
| `tools/predraw_ledger_verify.py` | `ea48288d828b2d285ca7660d302d16203c3af15d0f1f1e963022cbbfde964418` | `tools/predraw_ledger_verify.py` | True (Identical) | `ALREADY_PRESENT_IDENTICAL` | Standalone CLI entrypoint for predraw ledger verification. |
| `tests/test_p360a_predraw_metadata_instrumentation.py` | `c7e0284efc89b271b9f95c7a1fdab120d5c8c7726275288ece026516c65c23da` | `tests/test_p360a_predraw_metadata_instrumentation.py` | False | `CREATE_FROM_SOURCE` | Focused unit tests for metadata instrumentation & ledger engine. |
| `tests/test_p364_predraw_capture_runner.py` | `f022886f02a23f1efc9ebb8c42612f85ae4a5dcdc9d56e1a5a05c8dae6294d4f` | `tests/test_p364_predraw_capture_runner.py` | False | `CREATE_FROM_SOURCE` | Focused unit tests for predraw capture runner CLI. |
| `tests/test_p365_predraw_ledger_verify.py` | `94efc761e2e7f7de9fdbe32b5209c46c210c9620ee3c5410b65ba2f53eb90da2` | `tests/test_p365_predraw_ledger_verify.py` | True (Identical) | `ALREADY_PRESENT_IDENTICAL` | Focused unit tests for predraw ledger verifier CLI. |

## Excluded paths (Not Migrated in R1)

- `tools/quick_predict.py` (Belongs to cand_087b_quick_predict_ledger_opt_in)
- `lottery_api/routes/replay.py` (Belongs to cand_087c_replay_query_normalization)
