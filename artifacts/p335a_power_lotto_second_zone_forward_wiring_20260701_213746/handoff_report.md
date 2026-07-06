# P335A — Handoff Report

**Task ID:** `P335A_POWER_LOTTO_SECOND_ZONE_FORWARD_WIRING_IMPLEMENTATION`
**Date/time:** 2026-07-01 21:36–22:0x CST (+0800), Asia/Taipei
**Mode:** smallest safe forward-only code change. No DB write, no backfill, no
prediction, no pipeline resume, no push.

## 1. Evidence root
`/Users/kelvin/Kelvin-WorkSpace/p335a_power_lotto_second_zone_forward_wiring_20260701_213746`

## 2. Canonical HEAD + implementation branch
- `origin/main` HEAD = `ce2c042e7f4967841e6b31e17552d55bf4717f91` (exact match to required predecessor).
- Implementation worktree `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p335a`,
  branch `task/p335a-power-lotto-second-zone-forward-wiring`, based at & still == `ce2c042`.

## 3. Files changed (2 new, 0 modified)
- `lottery_api/models/power_lotto_second_zone.py` (169 lines) — SHA256 `15b60f2c…`
- `tests/test_p335a_power_lotto_second_zone_forward_wiring.py` (173 lines) — SHA256 `5e34c360…`

## 4. Exact code path fixed
The Generation-B failure mode was a row-builder binding the literal
`"predicted_special": None` while a working model existed elsewhere (the
Generation-A `_special_predict()` / the live `PowerLottoSpecialPredictor`). P335A
provides the **one canonical function** every future POWER_LOTTO row-builder must
call — `second_zone_predict(history)` (reusing `PowerLottoSpecialPredictor`, the
same model `tools/quick_predict.py::power_special_v3()` already runs live) — plus
`assert_power_lotto_predicted_special(row)`, a fail-fast NULL guard to run before
persisting a non-dry-run POWER_LOTTO row. This is the "one function, one
call-site, one guard" design mandated by P334A §4/§5, so the
Generation-A/Generation-B divergence cannot recur.

Note: the offending apply scripts P334A named (`p132…p141`) are **not on
origin/main** (side-branch `claude/zen-gates-ff6802` only); the sole in-tree
Generation-B POWER path (Tier-B `p93_tierb_replay_adapters.py`) is
`DRY_RUN`/`production_eligible=False` and content-phrase-guarded, so it was
deliberately not modified. Hence no in-tree call site was edited; the deliverable
is the reusable helper + guard the future pipeline-resume must adopt.

## 5. Tests
- **PASS (20/20):** `tests/test_p335a_power_lotto_second_zone_forward_wiring.py`
  (non-null-in-range, determinism, raise-on-insufficient, fallback, guard,
  end-to-end wiring prevents NULL). Pure, no DB.
- **PASS (32):** non-DB assertions in `test_p93_...` (Tier-B, untouched) and
  `test_p48_...null_policy` (the precedent mirrored).
- **NOT RUN:** DB-backed assertions in those two files (6) — canonical 99MB DB is
  untracked/absent in a fresh worktree; proven non-causal (identical failures
  with P335A files removed). Reuse-fidelity check confirmed
  `second_zone_predict == PowerLottoSpecialPredictor.predict_top_n[0]`.

## 6. DB invariance
Canonical `lottery_api/data/lottery_v2.db` unchanged: size 99,368,960, mtime
Jun 30 13:38:50 2026, SHA256 `9956c3bc…` (== baseline). Root `data/lottery_v2.db`
SHA256 `2095c687…` (== baseline). Never opened by P335A code. Stray 0-byte
gitignored sqlite stubs from existing DB-tests were removed. **PASS.**

## 7. No historical backfill
Confirmed — pure functions, zero DB access, forward-only by construction and by
docstring. The 27,104 existing NULL rows are untouched. See
`no_backfill_confirmation.md`.

## 8. No prediction / betting / recommended-number claim
Confirmed — helper returns a single integer only so a *future* replay row records
a non-NULL prediction-time value; no numbers recommended, no betting advice, no
predictive-edge claim (prior negative POWER findings unchanged).

## 9. Git status
`?? lottery_api/models/power_lotto_second_zone.py`
`?? tests/test_p335a_power_lotto_second_zone_forward_wiring.py`
0 staged; tracked diff empty; HEAD == origin/main == `ce2c042`.

## 10. Commit
**NOT RUN** — no commit created (task did not authorize commit; left uncommitted for review).

## 11. Push
**NOT RUN** — push explicitly gated on separate Owner authorization.

## 12. Remaining blocker
**BLOCKER-2 (unchanged from P334A):** no live POWER_LOTTO persistence pipeline
exists (no replay row since 2026-05-29). The helper + guard are the reusable
building blocks, but they only take effect once a POWER_LOTTO row-generation
path is (separately) authorized to resume and wired to call them. No such path
runs on `origin/main` today.

## 13. Recommended next single task
**P336A — Resume/define a single live POWER_LOTTO replay-row generation path
(separately authorized), wiring its row-builder to
`second_zone_predict()` + `assert_power_lotto_predicted_special()`** so new rows
carry a real `predicted_special`. Forward-only; no backfill; McNemar/edge claims
remain out of scope (prior POWER findings negative).

## 14. Final classification
**`P335A_POWER_LOTTO_SECOND_ZONE_FORWARD_WIRING_IMPLEMENTED_WITH_LIMITATIONS`**

Canonical helper + reusable NULL-guard + passing guard test are implemented,
minimal (2 new files, 0 modifications), DB-invariant, and backfill-free. Marked
WITH_LIMITATIONS because no active in-tree row-builder could be wired
(offending scripts are off origin/main; Tier-B is frozen dry-run; persistence
pipeline dormant) — activation is gated on the separately-authorized
pipeline-resume (BLOCKER-2). Not committed, not pushed.
