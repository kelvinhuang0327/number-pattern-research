# P336A — Test Plan

Runner: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew/venv/bin/python -m pytest`
(pytest 9.0.3, Python 3.14.4), from worktree `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p335a`.
All P336A tests are pure/isolated — deterministic synthetic history, no DB.

## Required-validation coverage

| Requirement | Test(s) |
|-------------|---------|
| Non-NULL `predicted_special` for sufficient history | `TestSufficientHistory::test_predicted_special_non_null_in_range`, `::test_exactly_min_history_is_sufficient` |
| Insufficient history does not silently default (fails fast) | `TestInsufficientHistoryFailsFast::test_raises_and_returns_no_row[0,1,29]`, `::test_non_list_history_raises` |
| Path uses `second_zone_predict(history)` | all `TestSufficientHistory` (special value comes from the helper) + `TestCompletePath…` |
| Path uses `assert_power_lotto_predicted_special(row)` | builder calls it internally; `::test_row_passes_the_null_guard` re-asserts |
| Forward semantics (no backfill of actuals) | `::test_forward_semantics_actuals_unknown_status_predicted` |
| Deterministic prediction fields | `::test_prediction_fields_are_deterministic` |
| Canonical row shape | `::test_row_has_canonical_keys`, `::test_first_zone_is_sorted_distinct_in_range` |
| First-zone input validation | `TestFirstZoneValidation` (6) |
| `dry_run` flag / guard-bypass semantics | `TestDryRunFlag` (2) |
| No DB side-effect | `TestNoDbSideEffect::test_build_writes_no_database` (empty tmp CWD, asserts no `*.db`/`*.sqlite`) |
| Complete live path reuses existing predictor | `TestCompletePathReusesExistingPredictor::test_wires_real_p47_first_zone_predictor` |

## Regression / non-causation
- Re-run P335A guard suite (must stay 20/20).
- Run existing `test_p47_powerlotto_wave4_dryrun_rehearsal.py` +
  `test_p48_powerlotto_special_null_policy.py`; any failure must be the
  pre-existing missing-canonical-DB condition, proven by running the p47 file in
  isolation (identical error with/without P336A files present).

## DB invariance
Before/after: canonical `lottery_api/data/lottery_v2.db` (main repo) SHA256
`9956c3bc…` and worktree stub `data/lottery_v2.db` SHA256 `a552351a…` must be
unchanged; no stray `.db` created.
