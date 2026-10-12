# Corrected Top Migration Candidates (R2A Verified)

## Recommended P0 Immediate Next Single Vertical

### 1. `cand_087a_predraw_ledger_engine`
- **Title**: Predraw Ledger Capture & Verification Engine
- **Source Ref**: `refs/remotes/origin/task/p273a-prize-aware-inferential-validation`
- **Scope**:
  - `docs/p360a_predraw_metadata_preregistration.md`
  - `lottery_api/data/predraw_schedule_config.json`
  - `lottery_api/data/predraw_strategy_freeze_registry.json`
  - `lottery_api/engine/predraw_ledger.py`
  - `tools/predraw_capture_runner.py`
  - `tools/predraw_ledger_verify.py`
- **Tests**:
  - `tests/test_p360a_predraw_metadata_instrumentation.py`
  - `tests/test_p364_predraw_capture_runner.py`
  - `tests/test_p365_predraw_ledger_verify.py`
- **Migration Risk**: `LOW`
- **Estimated Time**: 12 Hours
- **Justification**: Pure single vertical. Implements predraw strategy freeze and append-only ledger storage. Zero production DB writes, clear unit tests, no API contract breakage.

## Follow-up P1 Candidates (Split from cand_087)

### 2. `cand_087b_quick_predict_ledger_opt_in`
- **Title**: Quick Predict Predraw Ledger Opt-in Integration
- **Source Ref**: `refs/remotes/origin/task/p273a-prize-aware-inferential-validation`
- **Scope**: `tools/quick_predict.py`
- **Tests**: `tests/test_p360b_quick_predict_ledger_entrypoint.py`
- **Migration Risk**: `LOW`

### 3. `cand_087c_replay_query_normalization`
- **Title**: Replay Route Case & Whitespace Query Normalization
- **Source Ref**: `refs/remotes/origin/task/p273a-prize-aware-inferential-validation`
- **Scope**: `lottery_api/routes/replay.py`
- **Tests**: `tests/test_p354a_*`, `tests/test_p355a_*`
- **Migration Risk**: `LOW`
