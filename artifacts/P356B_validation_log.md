# P356B Validation Log

## Phase 0 Safety Re-check
- cwd: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew.worktrees/P356-all-strategy-inventory-replay`
- branch: `feature/P356-all-strategy-inventory-replay`
- HEAD: `e3265ad4baeb35d0e8e60d6df5915bdd4ddfa855`
- git status before:
```text
?? artifacts/
?? scripts/p356a_all_strategy_inventory.py
?? scripts/p356b_biglotto_replay.py
?? tests/test_p356a_inventory_artifacts.py
?? tests/test_p356b_biglotto_replay.py
```
- P356A artifacts exist: `True`
- P356A script/test exist: `True`
- canonical repo separate: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- immutable DB URI: `file:/Users/kelvin/Kelvin-WorkSpace/LotteryNew/lottery_api/data/lottery_v2.db?mode=ro&immutable=1`

## DB Before / After
- SHA before: `b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2`
- SHA after: `b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2`
- Draw rows before/after: `33362` / `33362`
- Replay rows before/after: `94924` / `94924`
- Replay runs before/after: `10` / `10`
- Distinct strategy IDs in strategy_prediction_replays: `35`
- Broad P356A DB strategy-like IDs: `42`

## Distinct Strategy ID Reconciliation
- The value `35` is the direct count of `strategy_prediction_replays.strategy_id`.
- The value `42` from P356A is the broader strategy-like DB evidence set, which also includes `strategy_replay_runs.strategy_scope` tokens and comma-joined scope labels.
- They are different definitions, not a data mutation.

## Artifact Guards
- Big Lotto lineages in manifest: `57`
- Eligible lineages: `10`
- Excluded lineages: `47`
- Every eligible strategy has rows for all windows: `True`
- Every excluded Big Lotto lineage has exclusion reason: `True`
- Known Big Lotto seed list fully accounted for: `True`

## Validation Commands
- `db_sha_guard`: PASS
- `draw_rows_guard`: PASS
- `replay_rows_guard`: PASS
- `eligible_rows_guard`: PASS
- `excluded_reason_guard`: PASS
- `seed_coverage_guard`: PASS

## Runtime Notes
- P356B generation command: `/Users/kelvin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 scripts/p356b_biglotto_replay.py`: PASS, `eligible=10`, `replay_rows=40`.
- The default `python3` lacked `numpy`, and the bundled Python 3.12.13 had `numpy` but not `scipy`. P356B used a process-local `scipy.fft` compatibility shim backed by `numpy.fft` for the three legacy Big Lotto callables that import only `fft` and `fftfreq`.
- No strategy source files were modified.

## Executed Validation Results
- `git status --short`: PASS; only P356A/P356B artifacts, scripts, and tests were untracked before commit staging.
- `git diff --check`: PASS.
- `git diff --cached --check`: PASS after normalizing generated CSV artifacts to LF line endings.
- `python3 -m py_compile scripts/p356a_all_strategy_inventory.py scripts/p356b_biglotto_replay.py tests/test_p356a_inventory_artifacts.py tests/test_p356b_biglotto_replay.py`: PASS.
- `python3 -m pytest tests/test_p356a_inventory_artifacts.py tests/test_p356b_biglotto_replay.py`: NOT RUN to completion because `/opt/homebrew/opt/python@3.14/bin/python3.14` has no `pytest` module.
- `pytest tests/test_p356a_inventory_artifacts.py tests/test_p356b_biglotto_replay.py`: PASS, 9 passed using Python 3.13.8 and pytest 9.0.3.
- DB SHA after validation: `b1d80e31f490a5a7595a91593641a8df9d488e0be243dc7bf74624dce3c25ee2`.
- Draw rows after validation: `33362`.
- Replay rows after validation: `94924`.
- Replay runs after validation: `10`.
