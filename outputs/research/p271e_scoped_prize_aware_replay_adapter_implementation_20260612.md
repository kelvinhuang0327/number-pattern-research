# P271E — Scoped Prize-Aware Replay Adapter

**Task ID:** P271E_SCOPED_PRIZE_AWARE_REPLAY_ADAPTER_IMPLEMENTATION  
**Date:** 2026-06-12  
**Branch:** `task/p271e-scoped-prize-aware-replay-adapter`  
**Status:** COMPLETE

---

## Summary

P271E implements a standalone, read-only scoped adapter (`lottery_api/prize_aware_replay_adapter.py`) that maps structurally eligible replay rows from the canonical DB into the `prize_aware_scorer` input contract established in P271C.

This adapter is **parallel** to the existing M3+/replay pipeline. It does not modify, replace, or interact with any existing scoring or prediction code.

---

## Safety Declarations

- **Standalone:** This module is entirely parallel. The existing M3+ replay pipeline was not modified. replay.py was not modified.
- **Read-only:** The canonical DB is opened exclusively with `sqlite3 URI mode=ro` (`_open_ro()`). No INSERT, UPDATE, DELETE, or DDL statement exists in the source.
- **No full historical evaluation:** The bounded smoke sample scored exactly 10 eligible rows per lottery type (30 total). No full historical evaluation was run.
- **No success rates or strategy aggregates:** The smoke summary contains no success rate, hit rate, tier frequency, strategy ranking, or baseline comparison. It contains only counts and safety flags.
- **POWER_LOTTO predicted second-zone provenance:** POWER rows missing `predicted_special` are excluded with reason `MISSING_PREDICTED_SECOND_ZONE` and **never filled, defaulted, inferred, or replaced** by the actual second-zone value.
- **MANUAL_VERIFICATION_REQUIRED:** `source_verification_status = "MANUAL_VERIFICATION_REQUIRED"` is propagated from the scorer on all outputs.
- **M3+ scoring unchanged:** All 30 smoke scorer calls returned `existing_m3_replay_scoring_changed=False`. Existing M3+ replay scoring is completely unaffected.
- **Not registered in production:** No API route, frontend integration, or registry entry was added.
- **P270C not executed:** No prize amounts, EV, ROI, or payout logic is implemented. Scorer results contain only structural tier classifications.

---

## Module Contract

**File:** `lottery_api/prize_aware_replay_adapter.py`

### Public API

| Function | Purpose |
|---|---|
| `iter_structurally_eligible_rows(db_path, lottery_type=None, limit=None)` | Yields eligible replay rows with mandatory positive-integer limit |
| `map_replay_row_to_scorer_input(row)` | Maps an eligible row to scorer kwargs |
| `score_bounded_smoke_sample(db_path, limit_per_lottery=10)` | Runs bounded smoke validation (max 10 rows/lottery) |
| `summarize_structural_exclusions(db_path, lottery_type=None)` | Returns exclusion reason counts by lottery type |

### Constants

- `ADAPTER_VERSION = "prize_aware_adapter_v1"`
- `SCORING_VERSION` — delegated to `prize_aware_scorer.SCORING_VERSION`
- `ALL_EXCLUSION_REASONS` — canonical tuple of 9 exclusion reason strings
- `SUPPORTED_LOTTERY_TYPES` — `("POWER_LOTTO", "BIG_LOTTO", "DAILY_539")`

---

## Structural Eligibility Rules

| Lottery Type | Condition |
|---|---|
| POWER_LOTTO | `predicted_special` (second-zone prediction) must be stored non-NULL in [1,8]; `actual_special` in [1,8]; valid 6-number main fields; causality ok |
| BIG_LOTTO | `actual_special` in [1,49]; valid 6-number main fields; causality ok |
| DAILY_539 | Valid 5-number main fields; both special fields must be NULL; causality ok |

All rows must also pass the draw-join check (exactly one matching draws row exists) and the causality check (`history_cutoff_draw < target_draw` as integers).

---

## Feasibility Snapshot (from P271D)

| Lottery Type | Total Rows | Eligible Rows | Status |
|---|---|---|---|
| POWER_LOTTO | 36,104 | ~9,000 (24.93%) | **PARTIAL** — only rows with stored predicted_special |
| BIG_LOTTO | 24,140 | 24,140 (100%) | **FULL** |
| DAILY_539 | 34,680 | 34,680 (100%) | **FULL** |

POWER_LOTTO has 27,104 rows excluded for `MISSING_PREDICTED_SECOND_ZONE`. These are never back-filled.

---

## Bounded Smoke Results

- **Scope:** 10 rows per lottery type (30 total)
- **Schema validation:** All 30 scorer calls returned complete schema — PASS
- **Deterministic check:** Two independent passes returned identical row order and results — PASS
- **DB write confirmed absent:** Row count unchanged before/after smoke run — PASS
- **Safety flags confirmed:** All safety flags (`full_historical_evaluation_run`, `success_rate_calculated`, `strategy_comparison_run`, `raw_actual_number_arrays_exported`) = `false`

---

## Tests

**File:** `tests/test_p271e_prize_aware_replay_adapter.py`  
**Result:** 53 passed, 4 skipped (artifact file checks, passed after artifact creation)

Test coverage:
- Import isolation and version constants
- DB URI mode=ro
- No SQL write statements
- Scorer imported; replay.py not imported
- Deterministic ordering
- Mandatory bounded limit enforcement
- POWER eligibility: `predicted_special` required, never filled
- BIG mapping: uses `actual_special`
- DAILY_539: rejects any auxiliary fields
- Join ambiguity / causality / cardinality / range / duplicate rejection
- Unsupported lottery type rejection
- Row non-mutation
- Scorer input contract for all 3 lotteries
- Scorer output schema (all required fields, `existing_m3_replay_scoring_changed=False`)
- Bounded smoke: ≤ 10 rows, deterministic, no forbidden metrics
- DB unchanged after smoke
- No replay.py / API / registry / prize-amount / EV/ROI references
- POWER full dataset not falsely declared fully eligible

---

## Files Changed (whitelist)

1. `lottery_api/prize_aware_replay_adapter.py` — new adapter module
2. `tests/test_p271e_prize_aware_replay_adapter.py` — 53 test cases
3. `outputs/research/p271e_scoped_prize_aware_replay_adapter_implementation_20260612.json`
4. `outputs/research/p271e_scoped_prize_aware_replay_adapter_implementation_20260612.md`
5. `outputs/research/p271e_scoped_prize_aware_replay_adapter_smoke_20260612.json`
6. `00-Plan/roadmap/active_task.md`
7. `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`

No other files were created or modified.
