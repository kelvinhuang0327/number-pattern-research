# P336A — Handoff Report

**Task ID:** `P336A_ONE_POWER_LOTTO_FORWARD_ROW_GENERATION_PATH_WITH_P335A_HELPER`
**Date/time:** 2026-07-01 22:17–22:2x CST (+0800), Asia/Taipei.
**Mode:** smallest safe forward-only code change. No DB write, no backfill, no
prediction, no pipeline resume, no push.

## 1. Evidence root
`/Users/kelvin/Kelvin-WorkSpace/p336a_one_power_lotto_forward_row_generation_path_20260701_221919`

## 2. Canonical HEAD + working branch
- `origin/main` HEAD = `ce2c042e7f4967841e6b31e17552d55bf4717f91` (live `ls-remote` == local).
- Worktree `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-p335a`, branch
  `task/p335a-power-lotto-second-zone-forward-wiring`, based at & still == `ce2c042`.

## 3. P335A files preserved
Yes — byte-identical: `power_lotto_second_zone.py` SHA256 `15b60f2c…`,
`test_p335a_…` SHA256 `5e34c360…` (both == P335A's recorded hashes).

## 4. Selected one row-generation path + rationale
**New module `lottery_api/models/power_lotto_forward_replay_row.py` →
`build_power_lotto_forward_replay_row(...)`.** Chosen over editing the p47 Gen-A
path because `generate_dryrun_rows` is imported by the **production apply**
`scripts/p48_powerlotto_wave4_production_apply.py:560` and 6+ tests — editing it
has high blast radius (violates "Minimal Impact"). The new module is additive,
isolated, forward-only, and wires both P335A entrypoints. See
`selected_path_rationale.md`.

## 5. Files changed (2 new, 0 modified)
- `lottery_api/models/power_lotto_forward_replay_row.py` (196 lines) — SHA256 `1cdccb00…`
- `tests/test_p336a_power_lotto_forward_row_generation_path.py` (221 lines) — SHA256 `0e91bb58…`

## 6. Exact code path wired to the P335A helper
```python
numbers = _validate_first_zone(predicted_numbers)          # 6 distinct ints [1..38]
predicted_special = second_zone_predict(history)           # P335A helper (raises <30)
row = { ..., "predicted_special": predicted_special, "dry_run": 0,
        "actual_numbers": None, "replay_status": "PREDICTED", ... }
assert_power_lotto_predicted_special(row)                  # P335A guard @ output boundary
return row
```
The only way past `second_zone_predict` is a real in-range value ⇒ the builder
returns a non-NULL-second-zone row **or raises** — never a silent default.

## 7. Tests
- **PASS (21/21):** `tests/test_p336a_power_lotto_forward_row_generation_path.py`
  (non-null for sufficient history; fail-fast raise for insufficient history/non-list;
  guard; forward semantics; determinism; first-zone validation; no-DB side-effect;
  complete path via real p47 first-zone predictor). Pure, no DB.
- **PASS (20/20):** P335A guard suite — no regression.
- **PASS:** existing non-DB assertions in `test_p47_…` / `test_p48_…null_policy`.
- **NOT RUN (1):** `test_p47_…::test_production_rows_unchanged` — asserts the 99 MB
  canonical DB exists; absent in a fresh worktree. Proven non-causal (identical
  error running the p47 file in isolation).

## 8. DB invariance
Canonical `lottery_api/data/lottery_v2.db` unchanged: 99,368,960 bytes, mtime
Jun 30 13:38:50 2026, SHA256 `9956c3bc…` (== baseline). Worktree stub
`data/lottery_v2.db` SHA256 `a552351a…` (== baseline). No stray `.db`. **PASS.**

## 9. No historical backfill
Confirmed — zero DB access, forward-only by construction; the 27,104 existing
NULL rows are untouched. See `no_backfill_confirmation.md`.

## 10. No prediction / betting / recommended-number claim
Confirmed — the builder attaches one second-zone integer purely so a *future*
replay row records a non-NULL prediction-time value. No numbers recommended, no
betting advice, no predictive-edge claim (prior negative POWER findings unchanged).

## 11. Git status
```
?? lottery_api/models/power_lotto_forward_replay_row.py
?? lottery_api/models/power_lotto_second_zone.py                (P335A, preserved)
?? tests/test_p335a_power_lotto_second_zone_forward_wiring.py   (P335A, preserved)
?? tests/test_p336a_power_lotto_forward_row_generation_path.py
```
0 staged; tracked diff empty; HEAD == origin/main == `ce2c042`.

## 12. Commit
**NOT RUN** — left uncommitted for review (task did not authorize commit).

## 13. Push
**NOT RUN** — gated on separate Owner authorization.

## 14. Remaining blocker
**BLOCKER-2 (unchanged):** the POWER_LOTTO persistence pipeline is dormant (no row
since 2026-05-29). The builder is the reusable, wired path a resume will call; it
only writes rows once persistence is separately authorized.

## 15. Recommended next single task
**P337A — Separately-authorized single-row *persistence rehearsal*:** call
`build_power_lotto_forward_replay_row` for ONE upcoming POWER_LOTTO target and
insert the resulting guarded row into a **temp/rehearsal DB only** (never
canonical), proving the end-to-end generate→guard→persist path. Forward-only; no
canonical DB write; no backfill; no edge claim.

## 16. Final classification
**`P336A_ONE_POWER_LOTTO_FORWARD_ROW_GENERATION_PATH_IMPLEMENTED_WITH_LIMITATIONS`**

One forward POWER_LOTTO row-generation path is defined, wired to
`second_zone_predict()` + `assert_power_lotto_predicted_special()`, and proven
(21/21) to yield a non-NULL second zone for sufficient history and to fail fast
otherwise — additive (2 new files, 0 modifications), DB-invariant, backfill-free.
Marked WITH_LIMITATIONS because persistence remains gated (BLOCKER-2): no running
pipeline calls it yet, and actually recording rows is a separate authorization.
Not committed, not pushed.
