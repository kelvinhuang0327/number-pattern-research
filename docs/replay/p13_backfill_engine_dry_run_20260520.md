# P13: Backfill Engine Dry-Run — 2 ONLINE Strategies × 1500 Draws

**Phase**: P13  
**Date**: 2026-05-20  
**Classification**: P13_BACKFILL_ENGINE_DRY_RUN_READY  
**Output**: `outputs/replay/p13_backfill_engine_dry_run_20260520.json`  
**Script**: `scripts/p13_backfill_engine_dry_run.py`  
**Tests**: `tests/test_p13_backfill_engine_dry_run.py` — 20/20 PASS  

---

## 1. Objective

Build and execute a **read-only, dry-run backfill engine** that:

1. Runs **2 ONLINE strategies** (`daily539_f4cold`, `power_precision_3bet`) against the **1500 most recent draws** for each lottery type.
2. Generates **3000 candidate predictions** using real adapter calls — never fabricated numbers.
3. Computes causal hit metrics (predicted ∩ actual numbers) for each candidate.
4. Outputs a structured JSON report for human review before any DB apply.
5. **Does not write any rows to the database** (`production_rows_before == production_rows_after == 460`).

---

## 2. P12 → P13 Rationale

P12 identified a critical gap: the production DB had only 460 replay rows — far below the 1500-draw target required for statistical validation. The P12 gap analysis (`outputs/replay/p12_1500_draw_gap_analysis_20260520.json`) recommended:

- **Phase 1 strategies**: `daily539_f4cold` + `power_precision_3bet`
- **Draw window**: 1500 draws per strategy
- **Estimated candidates**: 3000 (2 × 1500)
- **Mode**: dry-run only — no DB write until CEO authorized apply gate (P14)

P13 implements that recommendation. P14 will be the gated apply phase.

---

## 3. Selected Strategies (Phase 1)

| # | Strategy ID | Strategy Name | Lottery Type | Min History |
|---|-------------|---------------|-------------|-------------|
| 1 | `daily539_f4cold` | 今彩539 F4 Cold | DAILY_539 | 100 |
| 2 | `power_precision_3bet` | 威力彩 Precision 3注 | POWER_LOTTO | 100 |

**Why these two?**  

- Both are `ONLINE` lifecycle — directly executable, no blocked state.
- Both have sufficient historical draw data: DAILY_539 has 5865 draws, POWER_LOTTO has 1912 draws.
- Both were recommended by P12 gap analysis as Phase 1 candidates with highest data availability.
- Neither is `ARTIFACT_ONLY`, `NO_DATA`, `REJECTED`, or `RETIRED`.

---

## 4. Draw Window and Causal History

**Target window**: last 1500 draws per lottery type (by integer draw number ascending).

| Lottery Type | Total Draws | Target Start Index | Target End Index | Min History at First Target |
|---|---|---|---|---|
| DAILY_539 | 5865 | 4365 | 5865 | 4365 draws |
| POWER_LOTTO | 1912 | 412 | 1912 | 412 draws |

**Causal guarantee**: for each target draw at index `i` in the full sorted list, the history slice is `all_draws[0:i]` — strictly prior draws only. This prevents any data leakage from future draws into the prediction.

---

## 5. Estimated vs Generated Candidates

| Metric | Value |
|--------|-------|
| `estimated_target_candidates` | 3000 |
| `generated_candidates` | 3000 |
| `ready_candidates` | 3000 |
| `blocked_candidates` | 0 |

All 3000 candidates reached `READY` status:

- No history shortfall (all targets had 412+ history draws, above `min_history=100`).
- No existing duplicate rows in `strategy_prediction_replays` for these (strategy, draw) pairs.
- No exceptions raised by either adapter across all 3000 calls.

---

## 6. Ready / Blocked Statistics

| Strategy | Total | READY | BLOCKED | Avg Hit Count | Special Hits |
|----------|-------|-------|---------|---------------|-------------|
| `daily539_f4cold` | 1500 | 1500 | 0 | 0.6727 | 0 |
| `power_precision_3bet` | 1500 | 1500 | 0 | 0.9967 | 0 |
| **Total** | **3000** | **3000** | **0** | — | — |

Notes:
- DAILY_539 special is always `None` (5-ball game, no powerball).
- Avg hit count is the mean number of predicted numbers that matched the actual draw.

---

## 7. Block Reasons

None. `block_reasons` dict is empty in the output JSON. All 3000 candidates were `READY`.

If any BLOCKED candidates had appeared, their reasons would have been one of:

| Status Code | Cause |
|---|---|
| `BLOCKED_INSUFFICIENT_HISTORY` | `len(history) < adapter.meta.min_history` |
| `BLOCKED_DUPLICATE_REPLAY_ROW` | `(strategy_id, lottery_type, draw)` already in DB |
| `BLOCKED_NO_STRATEGY_RUNNER` | `LifecycleNotExecutable` raised |
| `BLOCKED_NO_PREDICTION_PAYLOAD` | `RejectPrediction` raised by adapter |
| `BLOCKED_UNSUPPORTED_LOTTERY_TYPE` | `UnsupportedLotteryType` raised |
| `BLOCKED_INVALID_OUTPUT` | `InvalidOutput` raised |
| `BLOCKED_REPLAY_ERROR` | Any other unhandled exception |

---

## 8. Hit Count Calculation

For each `READY` candidate:

```
hit_numbers = sorted(set(predicted_numbers) ∩ set(actual_numbers))
hit_count   = len(hit_numbers)
special_hit = 1 if predicted_special == actual_special else 0
            # DAILY_539: always 0 (no powerball)
```

The `hit_count` field **always equals** `len(hit_numbers)`. This invariant is enforced by test #15.

Example (from `candidates_sample[0]`):
```
predicted_numbers = [7, 10, 25, 29, 34]
actual_numbers    = [8, 22, 23, 29, 31]
hit_numbers       = [29]
hit_count         = 1
special_hit       = 0
```

---

## 9. fake_success = 0 Guarantee

`fake_success_count = 0` is enforced at three levels:

1. **Script level**: every candidate has `counts_as_success = False` and `would_insert = False` unconditionally — set in `_make_candidate()` for all paths, never conditionally.
2. **JSON level**: the output JSON has `"fake_success_count": 0`.
3. **Test level**: test #8 (`test_fake_success_count_zero`) and test #14 (`test_counts_as_success_false_all`) assert this invariant.

A `READY` dry-run candidate has real predictions and real hit metrics, but is **never** logged as a success row. Success accounting only begins after P14's apply gate writes the rows under explicit authorization.

---

## 10. Why No DB Write

The P13 engine is intentionally **stateless and non-destructive**:

- `PRAGMA query_only = ON` is set on the SQLite connection.
- No `INSERT`, `UPDATE`, or `DELETE` statement is executed.
- `production_rows_before == production_rows_after == 460` is verified both at script end and in test #16.
- The DB row count is checked live from `sqlite3` at test time — not mocked.

This design ensures P13 can be re-run safely at any time without accumulating state, and that P14 apply is an explicit, irreversible, separately authorized operation.

---

## 11. P14 Apply Gate Design

The P14 apply gate (`scripts/p14_backfill_apply_gate.py`) must:

1. **Accept** the P13 dry-run JSON path and an **exact authorization phrase**: `"YES apply P13 Phase 1 backfill rows"`.
2. **Pre-apply checks** (must all pass before any write):
   - `fake_success_count == 0`
   - All READY candidates have non-fabricated `predicted_numbers` (not null, correct length per lottery type)
   - All `provenance_hash` values are unique across candidates
   - Current live DB row count matches `production_rows_before` from P13 JSON
   - CEO explicit sign-off on `ready_candidates` count (3000 expected)
3. **Apply**: write READY candidates as rows into `strategy_prediction_replays`.
4. **Post-apply verification**: row count = `production_rows_before + ready_candidates`.
5. **Rollback key**: `controlled_apply_id = 'P13_PHASE1_APPLY_<timestamp>'` stored per row.

**P14 is a one-way gate**. Once applied, rows cannot be undone without explicit `DELETE` audit. Do not run P14 without complete test suite passing and CEO sign-off.

---

## Appendix: Candidate Fields

Each candidate in `candidates_sample` has:

| Field | Type | Description |
|---|---|---|
| `strategy_id` | str | Adapter strategy ID |
| `strategy_name` | str | Human-readable name |
| `lottery_type` | str | DAILY_539 \| POWER_LOTTO |
| `draw_number` | str | Target draw ID (TEXT) |
| `draw_date` | str | Draw date (YYYY/MM/DD) |
| `prediction_status` | str | READY \| BLOCKED_* |
| `predicted_numbers` | list[int] \| null | From adapter (READY only) |
| `actual_numbers` | list[int] | From draws table |
| `hit_numbers` | list[int] | predicted ∩ actual |
| `hit_count` | int | len(hit_numbers) |
| `special_hit` | int | 0 or 1 |
| `history_cutoff_draw` | str | Last history draw used |
| `block_reason` | str \| null | BLOCKED reason (BLOCKED only) |
| `source_trace` | str | "P13_BACKFILL_ENGINE_DRY_RUN" |
| `provenance_hash` | str \| null | SHA-256 of strategy+draw+prediction+history |
| `truth_level` | str \| null | "CAUSAL_REPLAY_GENERATED" (READY only) |
| `dry_run_only` | bool | Always True |
| `would_insert` | bool | Always False |
| `counts_as_success` | bool | Always False |
