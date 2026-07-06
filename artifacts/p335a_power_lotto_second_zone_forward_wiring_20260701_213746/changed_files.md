# P335A — Changed Files

Branch `task/p335a-power-lotto-second-zone-forward-wiring` @ base `ce2c042`
(== origin/main). **2 new files, 0 modifications, 0 deletions.**

`git status --short`:
```
?? lottery_api/models/power_lotto_second_zone.py
?? tests/test_p335a_power_lotto_second_zone_forward_wiring.py
```
`git diff --stat` (tracked files): empty. Staged files: 0.

## New file 1 — `lottery_api/models/power_lotto_second_zone.py` (169 lines)

SHA256: `15b60f2cdf95bb965c089a5c6f25181349b3f3170cb2f2569736895cdbdc1fe8`

Canonical POWER_LOTTO second-zone helper (single source of truth):
- `SPECIAL_MIN=1`, `SPECIAL_MAX=8`, `MIN_HISTORY=30`, `_POWER_LOTTO_RULES`.
- `class InsufficientHistoryError(ValueError)`.
- `_frequency_fallback(history) -> int` — recent-special most-common (fallback).
- `second_zone_predict(history) -> int` — reuses `PowerLottoSpecialPredictor`;
  raises on insufficient history; returns int in [1,8]; deterministic.
- `assert_power_lotto_predicted_special(row) -> None` — fail-fast NULL guard for
  future POWER_LOTTO non-dry-run row-builders.

## New file 2 — `tests/test_p335a_power_lotto_second_zone_forward_wiring.py` (173 lines)

SHA256: `5e34c360617555355010760c73c96ae292e3c8449fd9a1a424fb5e576a2d60c5`

20 pure unit tests across `TestSecondZonePredict`, `TestNullGuard`,
`TestForwardWiringPreventsNull`. No DB, no network, no filesystem writes.

## Exact code path addressed

The Generation-B failure mode was a row-builder binding the literal
`"predicted_special": None` while a real model existed elsewhere. P335A closes
this **for all future paths** by providing the one function they must call:

```python
# before (Generation-B literal, source of 27,104 NULL rows):
"predicted_special": None,
# after (mandated wiring — single canonical call site):
from lottery_api.models.power_lotto_second_zone import second_zone_predict
"predicted_special": second_zone_predict(history),
# and, immediately before persisting a non-dry-run POWER_LOTTO row:
assert_power_lotto_predicted_special(row)   # raises if still NULL/out-of-range
```

No existing row-builder on `origin/main` currently binds a *computable*
POWER_LOTTO `predicted_special` to `None` (the offending `p132…p141` scripts are
not on origin/main; Tier-B is dry-run/frozen), so no in-tree call site was
edited — the deliverable is the reusable helper + guard the future
(separately-authorized) pipeline-resume must adopt. See `implementation_plan.md`.
