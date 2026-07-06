# P335A — Test Results

Runner: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/venv/bin/python -m pytest`
(pytest 9.0.3, numpy 2.4.4, Python 3.14.4), from worktree
`/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p335a`.

## 1. P335A guard suite — **PASS (20/20)**

```
tests/test_p335a_power_lotto_second_zone_forward_wiring.py ....................  [100%]
20 passed in 0.30s
```

All three classes green: `TestSecondZonePredict` (10), `TestNullGuard` (8),
`TestForwardWiringPreventsNull` (2). No DB access; deterministic.

## 2. Reuse-fidelity check — **PASS**

For a fixed 300-draw synthetic history, `second_zone_predict()` returned **8**,
deterministic across repeats, and **equal to the live fused model's top-1**:
`PowerLottoSpecialPredictor.predict_top_n(history, n=3) == [8, 7, 6]` → helper
== `[0]`. Confirms the helper *is* the already-live model
(`tools/quick_predict.py::power_special_v3`), not a reinvented algorithm.

## 3. Relevant existing tests — non-DB PASS, DB-backed NOT RUN (DB absent)

Command: `pytest tests/test_p93_tier_b_replay_adapter_bootstrap_dryrun.py \
tests/test_p48_powerlotto_special_null_policy.py -q`
Result: **32 passed, 1 skipped, 6 failed** — all 6 failures are missing-DB:

```
sqlite3.OperationalError: no such table: strategy_prediction_replays
FAILED test_p93_...::test_production_db_row_count
FAILED test_p93_...::test_production_max_draw
FAILED test_p93_...::test_p93_strategies_absent_from_production
FAILED test_p48_...::TestProductionDBNullPolicy::test_no_null_actual_special_in_p48_rows
FAILED test_p48_...::TestProductionDBNullPolicy::test_all_p48_actual_special_in_valid_range
FAILED test_p48_...::TestProductionDBNullPolicy::test_p48_rows_have_correct_special_hit_semantics
```

Cause: the canonical 99MB DB is untracked (`lottery_api/.gitignore: *.db`), so a
fresh `origin/main` worktree has no `strategy_prediction_replays` table. These
DB-backed assertions are **NOT RUN** here (environment, not defect). The
non-DB unit/content assertions in the very same files **PASS (32)**.

### Non-causation proof (my change did not break them)

With the two new P335A files **moved out of the tree**, the identical command
produced the **identical** outcome — `6 failed, 32 passed, 1 skipped`, same
`no such table` errors. Therefore the failures are pre-existing DB-absence,
independent of this change. (Files restored afterward; `git status` = only the
2 new files.)

## 4. Side-effect hygiene

The DB-backed tests' `sqlite3.connect()` created stray 0-byte `.db` files
(gitignored). The stray untracked `lottery_api/data/lottery_v2.db` (0 bytes) was
removed; all tracked `.db` files remained byte-identical (git status clean). See
`db_invariance.md`.

## Verdict

- New null-guard tests: **PASS (20/20)**.
- Relevant existing non-DB tests: **PASS (32)**.
- DB-backed existing tests: **NOT RUN** (canonical DB absent in fresh worktree;
  proven non-causal to this change).
