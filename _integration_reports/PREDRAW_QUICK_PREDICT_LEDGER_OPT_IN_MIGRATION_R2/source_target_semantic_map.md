# Source-Target Semantic Comparison Map: PREDRAW_QUICK_PREDICT_LEDGER_OPT_IN_MIGRATION_R2

## Context
Migrated opt-in predraw ledger integration into `tools/quick_predict.py` from source candidate `cand_087b_quick_predict_ledger_opt_in` (ref `refs/remotes/origin/task/p273a-prize-aware-inferential-validation`).

## Semantic Map

| Feature / Element | Extracted Source Version (`cand_087b`) | Current Workspace Target Version | Migration Decision |
|---|---|---|---|
| CLI Flag Name | `--write-predraw-ledger` (store_true) | `--write-predraw-ledger` | Preserved |
| CLI Path Flag | `--predraw-ledger-path` (str) | `--predraw-ledger-path` | Preserved |
| Environment Var | `LOTTERY_PREDRAW_LEDGER_PATH` | `LOTTERY_PREDRAW_LEDGER_PATH` | Preserved |
| Flag Default | Disabled (`False` / `None`) | Disabled (`False` / `None`) | Preserved |
| Ledger Engine Import | `from lottery_api.engine import predraw_ledger as pl` inside function | Inside `write_predraw_ledger_for_prediction()` | Avoids top-level side effects / import-time writes |
| Lifecycle Point | After `print_prediction` / dry-run output, inside lottery type loop | Same position in `main()` loop | Prevents ledger writes prior to successful prediction |
| Output Isolation | Respects `ledger_path` argument / env var / module default | Resolved via `resolve_predraw_ledger_path` | Isolates test / smoke runs |
| Failure Semantics | Fail-closed / catches `LiveEligibilityError` and `Exception` | Catches exceptions, logs warning, returns prediction result | Prediction never fails due to ledger error |
| Database Bounds | Reads `DB_PATH` in read-only mode via `predraw_ledger` | Read-only access only; zero DB writes | Strict read-only boundary preserved |
| Replay Scope | Separate vertical `cand_087c` | Excluded from this task | Replay APIs untouched (`lottery_api/routes/replay.py` untouched) |
