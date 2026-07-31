# P336A — Test Results

Runner: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/venv/bin/python -m pytest`
(pytest 9.0.3, Python 3.14.4), from worktree `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p335a`.

## 1. P336A suite — **PASS (21/21)**
```
tests/test_p336a_power_lotto_forward_row_generation_path.py ..................... [100%]
21 passed in 0.48s
```
All classes green: `TestSufficientHistory` (7), `TestInsufficientHistoryFailsFast`
(4), `TestFirstZoneValidation` (6), `TestDryRunFlag` (2), `TestNoDbSideEffect` (1),
`TestCompletePathReusesExistingPredictor` (1). No DB access; deterministic.

Key assertions confirmed:
- Sufficient history → `predicted_special` non-NULL, `int`, in `[1,8]` (helper
  returned `8` for the 150-draw synthetic history, matching P335A's fidelity result).
- Insufficient history (`0`, `1`, `29`, non-list) → raises `InsufficientHistoryError`,
  **no row produced** (no silent default).
- Row runs the P335A guard and re-passes it; forward semantics hold
  (`replay_status="PREDICTED"`, `actual_*`/`hit_*` = `None`).
- Complete path: real `predict_midfreq_fourier_mk_3bet_bet1` first zone + builder
  → non-NULL guarded second zone.
- No `.db`/`.sqlite` file created under an empty tmp CWD.

## 2. Combined P335A + P336A + existing p47/p48 — **88 passed, 3 skipped, 1 error**
Command:
```
pytest tests/test_p335a_power_lotto_second_zone_forward_wiring.py \
       tests/test_p336a_power_lotto_forward_row_generation_path.py \
       tests/test_p47_powerlotto_wave4_dryrun_rehearsal.py \
       tests/test_p48_powerlotto_special_null_policy.py -q
→ 88 passed, 3 skipped, 1 error
```
- P335A suite: **PASS (20/20)** — no regression.
- P336A suite: **PASS (21/21)**.
- The single **error** is `test_p47_…::test_production_rows_unchanged`, a
  module-scoped fixture that asserts the canonical 99 MB DB exists
  (`lottery_api/data/lottery_v2.db`). That DB is untracked/absent in a fresh
  origin/main worktree → **NOT RUN (environment, not defect)**.

## 3. Non-causation proof
Running the p47 file **in isolation** (P336A files not on the command line):
```
pytest tests/test_p47_powerlotto_wave4_dryrun_rehearsal.py -q
→ 35 passed, 1 error   (same test_production_rows_unchanged, same missing-DB AssertionError)
```
Identical error with/without P336A involvement ⇒ pre-existing DB-absence,
independent of this change. P336A modifies no existing file, so it cannot affect
DB presence or any existing test.

## Verdict
- New P336A path tests: **PASS (21/21)**.
- P335A dependency suite: **PASS (20/20)**.
- Existing non-DB assertions in p47/p48: **PASS**.
- DB-backed existing assertion: **NOT RUN** (canonical DB absent; proven non-causal).
