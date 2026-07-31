# P336A — Changed Files

Branch `task/p335a-power-lotto-second-zone-forward-wiring` @ base `ce2c042`
(== origin/main). **2 new files, 0 modifications, 0 deletions.**

`git status --short` (after work):
```
?? lottery_api/models/power_lotto_forward_replay_row.py
?? lottery_api/models/power_lotto_second_zone.py                       (P335A, preserved)
?? tests/test_p335a_power_lotto_second_zone_forward_wiring.py          (P335A, preserved)
?? tests/test_p336a_power_lotto_forward_row_generation_path.py
```
`git diff --stat` (tracked files): empty. Staged files: 0.

## New file 1 — `lottery_api/models/power_lotto_forward_replay_row.py` (196 lines)
SHA256: `1cdccb004bb6da23e935791f7958428f7512104d4a03c60f632313b608fc0e24`

The single forward POWER_LOTTO replay-row builder:
- `FIRST_ZONE_POOL=38`, `FIRST_ZONE_PICK=6`; re-exports `SPECIAL_MIN/SPECIAL_MAX/InsufficientHistoryError`.
- `_validate_first_zone(predicted_numbers)` — 6 distinct ints in `[1,38]`.
- `build_power_lotto_forward_replay_row(...)` — sources `predicted_special` from
  `second_zone_predict(history)` and runs `assert_power_lotto_predicted_special(row)`
  before returning a canonical forward row. **No DB access.**

## New file 2 — `tests/test_p336a_power_lotto_forward_row_generation_path.py` (221 lines)
SHA256: `0e91bb5806803ca4d5c7873109c4e73e60d53f9a15ed4423f6d0aaf7dd0ad020`

21 pure unit tests: `TestSufficientHistory` (7), `TestInsufficientHistoryFailsFast`
(4), `TestFirstZoneValidation` (6), `TestDryRunFlag` (2), `TestNoDbSideEffect` (1),
`TestCompletePathReusesExistingPredictor` (1). No DB, no network, no fs writes.

## Preserved P335A files (byte-identical, verified)
- `lottery_api/models/power_lotto_second_zone.py` — SHA256 `15b60f2c…` (== P335A record).
- `tests/test_p335a_power_lotto_second_zone_forward_wiring.py` — SHA256 `5e34c360…` (== P335A record).

## Files NOT modified (zero blast radius)
`p47_wave4_powerlotto_adapters.py`, `scripts/p48_powerlotto_wave4_production_apply.py`,
`p56_wave5_powerlotto_adapters.py`, `p93_tierb_replay_adapters.py`, `routes/replay.py`,
and all existing test modules — untouched.
