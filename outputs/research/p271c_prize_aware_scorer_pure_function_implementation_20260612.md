# P271C — Standalone Prize-Aware Scorer (Pure Function) Implementation

**Task ID:** P271C
**Branch:** `task/p271c-prize-aware-scorer-pure-function`
**repo_head_before_task:** `687cff5989b5b84df871655f2cfa8f797de954b8`
**Mode:** `prize_aware_scorer_pure_function_implementation`
**Final Classification:** `P271C_PRIZE_AWARE_SCORER_PURE_FUNCTION_COMPLETE`

---

## 1. Executive Summary

P271C implements a standalone, pure-function prize-aware scoring module,
`lottery_api/prize_aware_scorer.py`, per the contract defined in the merged
P271A (prize-aware endpoint scoring spec) and P271B (official prize rule
verification and scoring engine design) artifacts. The module classifies a
single ticket/row into its official prize tier for POWER_LOTTO (威力彩),
BIG_LOTTO (大樂透), and DAILY_539 (今彩539), and reports both the new
prize-aware result and the existing M3+ diagnostic side by side.

The module is deterministic, side-effect free, performs no I/O of any kind,
and does not import or connect to the replay pipeline, DB, registry,
production API, frontend, or strategy-selection code. 98/98 focused tests
pass; the combined P271A+P271B+P271C suite is 208/208.

This is **not** a replacement for, or migration of, existing M3+/replay
scoring. It is a new, additional, parallel evaluation tool.

---

## 2. Architecture and Parallel-Track Guarantee

- `lottery_api/prize_aware_scorer.py` is a flat module with **zero imports**
  from `lottery_api.routes`, `lottery_api.engine`, `lottery_api.data`, any DB
  module, any replay module, or any registry module. It imports nothing but
  `from __future__ import annotations`.
- It performs no file I/O, no DB access (no `sqlite3`), no network access,
  no subprocess calls, no environment-variable access, and no logging.
- `score_replay_row()` always returns **both** `is_prize_aware_win` /
  `any_prize_aware_win` (new) **and** `is_m3_plus` (existing P265A SSOT:
  `hit_count >= 3`, `special_hit` excluded) in the same result dict. Neither
  field is derived from or overrides the other.
- `existing_m3_replay_scoring_changed` is hard-coded `False` in every result.
- No file in `lottery_api/replay.py`, any existing M3+ implementation, any
  DB file, `hypothesis_registry.jsonl`, API/frontend routes, strategy files,
  or backtest scripts was modified by this task.

**File-structure note:** P271B's design proposed
`lottery_api/research/prize_aware_scoring/prize_aware_scorer.py` (a new
sub-package). This task's explicit file whitelist instead specifies
`lottery_api/prize_aware_scorer.py` as a flat module, and creating an
`__init__.py` / package configuration is an explicit STOP condition for
P271C. The flat-module path was used; **function names, signatures, tier
mappings, and semantics are unchanged** from the P271B design — only the
file location differs, with no scope expansion.

---

## 3. Source Contract and MANUAL_VERIFICATION_REQUIRED Limitation

The implementation is built strictly from:

- `outputs/research/p271a_prize_aware_endpoint_scoring_spec_20260611.json`
- `outputs/research/p271b_official_prize_rule_scoring_engine_design_20260611.json`

Both artifacts record `source_status = MANUAL_VERIFICATION_REQUIRED` for all
three official Taiwan Lottery prize-table pages (JavaScript SPAs, not
machine-readable via WebFetch/curl in this environment). Tier mappings were
instead sourced from internal repo documentation (`lottery_api/CLAUDE.md`
`calc_prize` docstrings for POWER_LOTTO/BIG_LOTTO, and
`calculate_win_probability.py` for DAILY_539), as documented in P271B.

`prize_aware_scorer.py` carries this limitation forward explicitly:
`SOURCE_VERIFICATION_STATUS = "MANUAL_VERIFICATION_REQUIRED"`, and every
`score_replay_row()` / `score_prize_aware_ticket()` result includes
`source_verification_status: "MANUAL_VERIFICATION_REQUIRED"`. No claim is
made that the official pages were machine-verified.

No prize-money amounts (NTD) are included anywhere in this module —
P271B explicitly noted these were not retrievable, and this task does not
add any monetary, EV, ROI, or betting-advice logic (forbidden by the task
contract).

---

## 4. Public Function Contract

### Primary entry point

```python
score_prize_aware_ticket(
    lottery_type,                 # "POWER_LOTTO" | "BIG_LOTTO" | "DAILY_539"
    predicted_main_numbers,       # sequence of distinct ints (6 or 5 numbers)
    actual_main_numbers,          # sequence of distinct ints (6 or 5 numbers)
    predicted_second_zone=None,   # POWER_LOTTO only: int 1-8
    actual_second_zone=None,      # POWER_LOTTO only: int 1-8
    actual_special_number=None,   # BIG_LOTTO only: int, not in actual_main_numbers
) -> dict
```

### Supporting pure functions

```python
classify_power_lotto_tier(hit_count: int, special_hit: int) -> str
classify_big_lotto_tier(hit_count: int, special_hit: int) -> str
classify_daily_539_tier(hit_count: int) -> str
classify_tier(lottery_type: str, hit_count: int, special_hit: int) -> str
is_any_prize_aware_win(lottery_type: str, hit_count: int, special_hit: int) -> bool
score_replay_row(lottery_type: str, hit_count: int, special_hit: int) -> dict
```

### Result dict (both `score_replay_row` and `score_prize_aware_ticket`)

| Key | Type | Meaning |
|---|---|---|
| `scoring_version` | str | `"prize_aware_v1"` |
| `lottery_type` | str | echoes input |
| `main_hit_count` | int | first-zone/main-number hit count |
| `special_hit` | int | 0 or 1 (second-zone / special-number hit) |
| `second_zone_hit` | int \| None | same as `special_hit` for POWER_LOTTO, else `None` |
| `any_prize_aware_win` | bool | True if `prize_tier` is not the game's NO_PRIZE tier |
| `prize_tier` / `tier_class` | str | official tier class string, e.g. `POWER_FIRST_PRIZE`, `BIG_NO_PRIZE` |
| `is_prize_aware_win` | bool | same as `any_prize_aware_win` |
| `is_m3_plus` | bool | `hit_count >= 3` (P265A SSOT, unchanged) |
| `endpoint_flags` | dict | `{any_prize_aware_win, m3_plus_diagnostic, consolation_or_above}` |
| `source_verification_status` | str | `"MANUAL_VERIFICATION_REQUIRED"` |
| `parallel_feature` | bool | `True` |
| `existing_m3_replay_scoring_changed` | bool | `False` |

---

## 5. Lottery-Specific Scoring Behavior

### POWER_LOTTO (威力彩) — 10 tiers

- First zone: pick 6 from 1-38. Second zone (特別號): pick 1 from 1-8.
- `special_hit = 1` iff `predicted_second_zone == actual_second_zone`.
- Tier classes: `POWER_FIRST_PRIZE` (6+1) down through
  `POWER_CONSOLATION_PRIZE` (1+1), and `POWER_NO_PRIZE` for all other
  combinations (per P271B `tier_mapping_by_lottery.POWER_LOTTO`, exact
  match — 10 tiers including the two M3+-invisible tiers
  `POWER_EIGHTH_PRIZE` (2+1) and `POWER_CONSOLATION_PRIZE` (1+1)).
- `score_prize_aware_ticket` requires both `predicted_second_zone` and
  `actual_second_zone`; `actual_special_number` must be `None`.

### BIG_LOTTO (大樂透) — 8 tiers

- Pick 6 main numbers from 1-49. Special number drawn separately.
- `special_hit = 1` iff `actual_special_number ∈ predicted_main_numbers`
  (the *six predicted main numbers*, not a separately predicted special
  number — per P271B `special_hit_logic`).
- Tier classes: `BIG_FIRST_PRIZE` (6, special irrelevant) down through
  `BIG_CONSOLATION_PRIZE` (2+special), and `BIG_NO_PRIZE` otherwise
  (8 tiers, exact match to P271B `tier_mapping_by_lottery.BIG_LOTTO`,
  including the M3+-invisible `BIG_CONSOLATION_PRIZE` (2+1)).
- `score_prize_aware_ticket` requires `actual_special_number` (and rejects
  it if it overlaps `actual_main_numbers`); `predicted_second_zone` /
  `actual_second_zone` must be `None`.

### DAILY_539 (今彩539) — 4 tiers

- Pick 5 main numbers from 1-39. No special number, no second zone.
- `special_hit` is always 0.
- Tier classes: `D539_FIRST_PRIZE` (5) down through `D539_FOURTH_PRIZE` (2),
  and `D539_NO_PRIZE` for `hit_count < 2` (4 tiers, exact match to P271B
  `tier_mapping_by_lottery.DAILY_539`, including the M3+-invisible
  `D539_FOURTH_PRIZE` (hit_count=2)).
- `score_prize_aware_ticket` requires `predicted_second_zone`,
  `actual_second_zone`, and `actual_special_number` to all be `None`.

---

## 6. Input-Validation Behavior

`score_prize_aware_ticket` and `score_replay_row` raise `ValueError`
(deterministically, no silent normalization) for:

- Unsupported `lottery_type`
- Wrong number-of-numbers (not 6 for POWER_LOTTO/BIG_LOTTO, not 5 for
  DAILY_539)
- Duplicate numbers within `predicted_main_numbers` or
  `actual_main_numbers`
- Out-of-range numbers (outside each game's 1-N pool, or second-zone
  outside 1-8)
- Non-integer numbers (e.g. strings, floats)
- `bool` values passed where `int` is expected (Python `bool` is a subclass
  of `int`; explicitly rejected via `isinstance(x, bool)` checks)
- Missing POWER_LOTTO `predicted_second_zone`/`actual_second_zone`
- Unexpected POWER_LOTTO `actual_special_number` (must be `None`)
- Missing BIG_LOTTO `actual_special_number`
- Unexpected BIG_LOTTO `predicted_second_zone`/`actual_second_zone` (must
  be `None`)
- BIG_LOTTO `actual_special_number` that overlaps `actual_main_numbers`
- Unexpected DAILY_539 `predicted_second_zone`/`actual_second_zone`/
  `actual_special_number` (must all be `None`)

Sorting/order of `predicted_main_numbers` and `actual_main_numbers` does not
affect the result (hit count computed via set intersection); caller-supplied
lists/tuples are never mutated (read-only via `list()`/`set()` copies).

---

## 7. P271B Fixture Traceability

P271B's `unit_test_fixture_matrix` defines **33 fixtures**: 14 for
POWER_LOTTO, 13 for BIG_LOTTO, 6 for DAILY_539. The actual artifact count was
verified directly (not assumed) by `test_p271b_fixture_matrix_traceability`,
which:

1. Opens `outputs/research/p271b_official_prize_rule_scoring_engine_design_20260611.json`
   and asserts `len(POWER_LOTTO) == 14`, `len(BIG_LOTTO) == 13`,
   `len(DAILY_539) == 6`, total `== 33`.
2. For every one of the 33 fixtures, calls `score_replay_row(lottery_type,
   hit_count, special_hit)` and asserts `tier_class`, `any_prize_aware_win`,
   and `is_m3_plus` exactly match the fixture's `expected_tier`,
   `expected_win`, `expected_m3_plus`.

All 33/33 fixtures have an executable P271C test. None are design-only.

---

## 8. Test Results

- **Focused:** `./venv/bin/python -m pytest tests/test_p271c_prize_aware_scorer.py -q`
  → **98 passed**
- **Combined:** `./venv/bin/python -m pytest tests/test_p271a_prize_aware_endpoint_scoring_spec.py tests/test_p271b_official_prize_rule_scoring_engine_design.py tests/test_p271c_prize_aware_scorer.py -q`
  → **208 passed**
- `git diff --check` → clean (no whitespace errors)

The 98 focused tests cover all 33 required-test categories listed in the
task contract, including:

- Module import side-effect check, supported-type constants, exact
  `scoring_version` / `source_verification_status`, parallel-feature marker,
  `existing_m3_replay_scoring_changed == False`
- All 14 POWER_LOTTO, 13 BIG_LOTTO, 6 DAILY_539 tier combinations
  (parametrized) plus NO_PRIZE boundary cases for each game
- BIG_LOTTO special-hit semantics (uses the 6 predicted main numbers)
- `any_prize_aware_win` ↔ `prize_tier` consistency, `endpoint_flags`
  consistency, coexistence of `is_m3_plus` and `any_prize_aware_win`
- Immutability and order-independence of input number lists
- Duplicate / wrong-count / out-of-range / non-integer / bool / unsupported
  rejections for both `score_replay_row` and `score_prize_aware_ticket`
- POWER_LOTTO second-zone missing/unexpected-special rejections
- BIG_LOTTO special-number missing/unexpected-second-zone/overlap
  rejections
- DAILY_539 unexpected auxiliary-field rejections
- Static source-code checks: no DB/replay/registry/strategy imports, no
  file/network/subprocess/env/logging access, no prize-amount/EV/ROI/
  recommendation output
- P271B fixture-matrix traceability (33/33)

---

## 9. Isolation from Replay/M3+/DB/API/Strategy Systems

- **Replay:** `lottery_api/replay.py` was not read or modified by the
  implementation (only referenced descriptively in this report and in
  P271B). No replay query was changed.
- **M3+:** `is_m3_plus = hit_count >= 3` is computed independently inside
  `prize_aware_scorer.py` and does not call into, import, or alter any
  existing M3+ code path.
- **DB:** No `sqlite3` import, no DB file opened, no schema or row read.
- **API/Frontend:** No route, handler, or frontend file was created or
  modified.
- **Strategy/Registry:** No strategy file, `hypothesis_registry.jsonl`, or
  `controlled_apply` code was read or modified.
- **Backtest/Replay evaluation:** None run.

Static checks in the test suite enforce the import/IO isolation claims by
parsing `lottery_api/prize_aware_scorer.py`'s AST and source text.

---

## 10. Prohibited Interpretations

This module and its tests **do not** establish, claim, or imply:

- Any improvement in hit rate, win rate, or prediction accuracy
- Any prize-money amount, expected value, ROI, or Kelly/betting-size
  recommendation
- Any change to, replacement of, or migration away from the existing
  M3+/replay scoring SSOT (P265A)
- Any newly generated or ranked strategy
- Any machine-verified confirmation of official Taiwan Lottery prize tables
  (status remains `MANUAL_VERIFICATION_REQUIRED`)
- Authorization for P270C, P271D, or any replay/backtest/DB-write task

---

## 11. What This Task Did Not Do

- Did not connect `prize_aware_scorer.py` to `replay.py`, any API route, or
  the frontend
- Did not run any replay evaluation, backtest, or strategy comparison
- Did not read or write the production DB (`lottery_v2.db`)
- Did not mutate `hypothesis_registry.jsonl`
- Did not modify `controlled_apply`, existing M3+ logic, or any P271A/P271B
  artifact
- Did not implement prize-money, EV, or ROI logic
- Did not start P270C, P271D, or any temporal-window/feature-mining task
- Did not create a worktree, clone another repo, or use a detached HEAD

---

## 12. Recommended Next Task

**HOLD / WAITING_FOR_USER_AUTHORIZATION.** The standalone prize-aware
scorer pure-function module is complete, tested (98/98 focused, 208/208
combined), and isolated from all production/replay/DB/strategy systems.
Any future work connecting `prize_aware_scorer.py` to the replay pipeline
for batch scoring (P271D or later) requires a new, separate explicit user
authorization with its own STOP conditions, per the
`parallel_feature_design.no_migration_path` guarantee in P271B. P270C
remains not authorized.

---

## Declarations

- This is a standalone parallel pure-function scorer.
- Existing M3+/replay scoring remains unchanged.
- No replay integration was added.
- No DB access or DB write occurred.
- No registry mutation occurred.
- No backtest or historical replay evaluation was run.
- No strategy was generated or selected.
- No hit-rate improvement is claimed.
- No prize-amount, EV, ROI, or betting-advice logic was implemented.
- Official source status remains `MANUAL_VERIFICATION_REQUIRED`.
- P270C remains not authorized.
- P271D was not started.
