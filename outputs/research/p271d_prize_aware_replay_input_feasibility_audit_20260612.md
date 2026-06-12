# P271D — Prize-Aware Replay Input Feasibility Audit (Read-Only)

**Task ID:** P271D
**Branch:** `task/p271d-prize-aware-replay-input-feasibility`
**repo_head_before_task:** `a1fc805b02ae4cb44348344fddf3f14abbc456c7`
**Mode:** `prize_aware_replay_input_feasibility_audit`
**Final Classification:** `P271D_PARTIAL_LOTTERY_FEASIBILITY_GO_SCOPED_ADAPTER`

---

## 1. Executive Summary

This audit determines whether the canonical replay table
(`strategy_prediction_replays`) and draw-result table (`draws`) in
`lottery_api/data/lottery_v2.db` contain all inputs required by
`lottery_api.prize_aware_scorer.score_prize_aware_ticket` for POWER_LOTTO,
BIG_LOTTO, and DAILY_539.

**Result:**

- **BIG_LOTTO** — FULL feasibility. 24,140/24,140 (100%) replay rows have all
  required fields.
- **DAILY_539** — FULL feasibility. 34,680/34,680 (100%) replay rows have all
  required fields (and correctly have no auxiliary fields).
- **POWER_LOTTO** — PARTIAL feasibility. Only 9,000/36,104 (24.93%) replay
  rows have a non-NULL `predicted_special` (predicted second-zone) value,
  which the scorer requires. The remaining 27,104 rows (75.07%) are
  **BLOCKED** for full prize-aware replay evaluation.

Overall: **`P271D_PARTIAL_LOTTERY_FEASIBILITY_GO_SCOPED_ADAPTER`** — BIG_LOTTO
and DAILY_539 may proceed with a full-coverage future adapter; POWER_LOTTO may
proceed only with a scoped adapter limited to the 9,000-row subset with
`predicted_special` populated, with the other 27,104 rows excluded and tagged
with an explicit exclusion reason.

---

## 2. Scope and Explicit Non-Actions

This task performed **only** read-only schema/data-availability inspection.
It explicitly did **NOT**:

- Call `lottery_api.prize_aware_scorer` (not imported, not invoked)
- Compare any predicted value against any actual value
- Compute hit counts, special hits, tier classes, `any_prize_aware_win`, or
  any endpoint flag
- Compute success rates, lift, p-values, or strategy rankings
- Run a backtest or historical replay evaluation
- Write to the DB, modify any existing replay row, or mutate the Hypothesis
  Registry
- Modify `lottery_api/prize_aware_scorer.py`, `lottery_api/replay.py`, the
  DB/schema, API/frontend, or any strategy file
- Start P270C, temporal-window research, or feature mining

---

## 3. Canonical DB and Sources Inspected

- **Canonical DB path:** `lottery_api/data/lottery_v2.db` (per
  `tests/conftest.py` default resolution; `data/lottery_v2.db` is a smaller,
  unrelated dev copy and was not used).
- **DB open mode:** `sqlite3.connect('file:lottery_api/data/lottery_v2.db?mode=ro', uri=True)`
  — read-only URI mode. No `INSERT`/`UPDATE`/`DELETE`/`CREATE`/`DROP`/`ALTER`/
  `REPLACE`/`VACUUM`/`PRAGMA`-write statements were issued.
- **Tables inspected:**
  - `strategy_prediction_replays` — replay table (predicted/actual numbers,
    predicted/actual special, hit_count, special_hit, history_cutoff_draw,
    target_draw, generated_at, bet_index, strategy_id, lottery_type;
    `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)`)
  - `draws` — draw-result table (`UNIQUE(draw, lottery_type)`), used only for
    join-coverage checks
- **Source code inspected (not modified):** `lottery_api/prize_aware_scorer.py`
  (public contract / required input fields only), `tests/conftest.py` (DB
  path resolution)

All 36,104 (POWER_LOTTO) + 24,140 (BIG_LOTTO) + 34,680 (DAILY_539) =
94,924 replay rows currently have `replay_status = 'PREDICTED'`.

---

## 4. POWER_LOTTO Field Feasibility

| Requirement | Field | Availability |
|---|---|---|
| Predicted 6 first-zone numbers | `predicted_numbers` (JSON array, 1-38, len 6) | 36,104/36,104 (100%) parseable, in-range, no duplicates |
| Actual 6 first-zone numbers | `actual_numbers` (JSON array, 1-38, len 6) | 36,104/36,104 (100%) parseable, in-range, no duplicates |
| **Predicted second-zone number** | `predicted_special` (INTEGER 1-8) | **9,000/36,104 (24.93%) non-NULL**; 27,104/36,104 (75.07%) NULL |
| Actual second-zone number | `actual_special` (INTEGER 1-8) | 36,104/36,104 (100%) |

**Finding:** The predicted second-zone value is genuinely absent for 75.07%
of POWER_LOTTO replay rows. Per explicit task instruction, this is treated as
a **blocking condition for full prize-aware replay evaluation**, not a
warning. No predicted second-zone value may be manufactured, defaulted,
randomized, or substituted from the actual second-zone.

**Feasibility:** PARTIAL — the 9,000 rows with `predicted_special` populated
are structurally eligible (all other fields/joins/causality are 100% present
for these rows too). The other 27,104 rows must be explicitly excluded by a
future adapter.

---

## 5. BIG_LOTTO Field Feasibility

| Requirement | Field | Availability |
|---|---|---|
| Predicted 6 main numbers | `predicted_numbers` (JSON array, 1-49, len 6) | 24,140/24,140 (100%) parseable, in-range, no duplicates |
| Actual 6 main numbers | `actual_numbers` (JSON array, 1-49, len 6) | 24,140/24,140 (100%) parseable, in-range, no duplicates |
| Actual special number | `actual_special` (INTEGER 1-49) | 24,140/24,140 (100%); 0/24,140 overlap `actual_numbers` |
| Predicted special number | N/A | **not required** — `predicted_special` is NULL for 24,140/24,140 (100%), which is CORRECT per the scorer's `special_hit_logic` (checks `actual_special ∈ predicted_main_numbers`) |

**Feasibility:** FULL — 24,140/24,140 (100%) rows have every field
`score_prize_aware_ticket` requires for BIG_LOTTO.

---

## 6. DAILY_539 Field Feasibility

| Requirement | Field | Availability |
|---|---|---|
| Predicted 5 numbers | `predicted_numbers` (JSON array, 1-39, len 5) | 34,680/34,680 (100%) parseable, in-range, no duplicates |
| Actual 5 numbers | `actual_numbers` (JSON array, 1-39, len 5) | 34,680/34,680 (100%) parseable, in-range, no duplicates |
| Auxiliary field | none required/allowed | `predicted_special` and `actual_special` are both NULL for 34,680/34,680 (100%) — **correctly absent**, matching the scorer's DAILY_539 contract |

**Feasibility:** FULL — 34,680/34,680 (100%) rows have every field
`score_prize_aware_ticket` requires for DAILY_539, with no auxiliary fields
present (as required).

---

## 7. Join and Causality Audit

For all three lottery types:

- **Lottery-type normalization:** `lottery_type` is stored as the exact
  uppercase string (`'POWER_LOTTO'`, `'BIG_LOTTO'`, `'DAILY_539'`) in both
  `strategy_prediction_replays` and `draws`, matching
  `prize_aware_scorer.SUPPORTED_LOTTERY_TYPES` exactly — deterministic.
- **Target-draw normalization:** `target_draw` is a TEXT draw identifier;
  `draws` has `UNIQUE(draw, lottery_type)`, so each
  `(lottery_type, target_draw)` maps to **at most one** `draws` row.
- **Join coverage:** 100% for all three lottery types
  (36,104/36,104, 24,140/24,140, 34,680/34,680).
- **Join independence:** the join key `(lottery_type, target_draw)` does not
  depend on any strategy-performance field (`hit_count`, `special_hit`,
  `strategy_id`, `bet_index` are not part of the join condition).
- **Causality:** `history_cutoff_draw` is present for 100% of rows in all
  three lottery types, and `int(history_cutoff_draw) < int(target_draw)`
  holds for 100% of rows (0 violations). `generated_at` is present for 100%
  of rows. No post-draw feature is needed to construct any scorer input.
  `prediction_cutoff_date` / `prediction_generated_at` columns exist but were
  NULL in the inspected rows; causality is therefore evidenced via
  draw-sequence ordering (`history_cutoff_draw < target_draw`), not literal
  wall-clock timestamps.

**Causality status (all 3 lotteries): CAUSALITY_VERIFIABLE**

---

## 8. Structural Eligibility Metrics

| Lottery | Total rows | Structurally eligible | Eligible % |
|---|---|---|---|
| POWER_LOTTO | 36,104 | 9,000 | 24.93% |
| BIG_LOTTO | 24,140 | 24,140 | 100% |
| DAILY_539 | 34,680 | 34,680 | 100% |

These are **data-availability** metrics only. No hit count, special hit,
second-zone hit, prize-aware win, tier class, endpoint flag, success
percentage, lift, p-value, or strategy-level result was computed.

For all three lottery types: 0 rows fail cardinality/range/duplicate
validation, 0 rows are missing an actual main result, and join coverage is
100%. The sole gating factor is POWER_LOTTO's `predicted_special` NULL rate.

---

## 9. Missing-Field and Exclusion Risks

- **POWER_LOTTO** — 27,104/36,104 (75.07%) rows lack `predicted_special`
  (predicted second-zone). This is the **only** missing-field risk identified
  across all three lottery types. A future adapter must exclude these rows
  with an explicit reason (e.g. `predicted_second_zone_missing`); it must not
  substitute a manufactured, default, random, or most-frequent value, and
  must not derive a "predicted" second-zone from the actual second-zone.
- **BIG_LOTTO** — none identified. `predicted_special` being NULL for 100% of
  rows is *expected and correct* (not required by the scorer), not a risk.
- **DAILY_539** — none identified. Both auxiliary columns being NULL for 100%
  of rows is *expected and correct* (matches the "no auxiliary field"
  contract), not a risk.

---

## 10. Future Parallel Adapter Design (Not Implemented)

A future, separately-authorized adapter (`prize_aware_replay_adapter`) would:

1. `SELECT` rows from `strategy_prediction_replays` for one `lottery_type` at
   a time.
2. `json.loads(predicted_numbers)` / `json.loads(actual_numbers)`, and read
   `predicted_special` / `actual_special`.
3. For **POWER_LOTTO**, skip (exclude with reason
   `predicted_second_zone_missing`) any row where `predicted_special IS NULL`
   (27,104/36,104 rows in the current dataset).
4. Map fields to `score_prize_aware_ticket(lottery_type,
   predicted_main_numbers, actual_main_numbers, predicted_second_zone,
   actual_second_zone, actual_special_number)` exactly as documented in
   `scorer_input_mapping_by_lottery` of the JSON artifact.
5. Call `lottery_api.prize_aware_scorer.score_prize_aware_ticket` — **deferred
   to the future adapter task; NOT performed in P271D**.
6. Write per-row results to a **new, separate, independently-versioned**
   artifact (e.g. JSONL under `outputs/research/`), carrying `strategy_id` and
   `bet_index` through only as pass-through identifiers.
7. Perform **no writes** to `strategy_prediction_replays`, `draws`, or any
   other existing table.
8. Leave `hit_count`, `special_hit`, `is_m3_plus`, and all other existing
   replay columns/semantics **completely untouched**.
9. Be independently versioned (its own `adapter_version` /
   `scoring_version`) and **enableable per lottery_type** — e.g. POWER_LOTTO
   scoped to the 9,000-row subset until/unless predicted second-zone coverage
   improves.

This design is descriptive only; the scorer was **not called** during P271D.

---

## 11. Existing Replay/M3+ Isolation Guarantee

- No row in `strategy_prediction_replays` or `draws` was modified.
- `hit_count`, `special_hit`, and all existing columns/semantics are
  unchanged (P265A SSOT: `is_m3_plus = hit_count >= 3`, `special_hit`
  excluded — unaffected).
- `lottery_api/prize_aware_scorer.py` was not modified.
- `lottery_api/replay.py` was not read or modified.
- No Hypothesis Registry write occurred.
- Any future adapter is designed (Section 10) to be a strictly additive,
  separately-versioned, read-only-on-existing-data parallel track.

---

## 12. Official-Source Limitation

`source_verification_status` remains `MANUAL_VERIFICATION_REQUIRED`, carried
forward unchanged from P271A/B/C. This audit inspected only the local DB
schema/data and `lottery_api/prize_aware_scorer.py`'s public contract; it does
not claim machine-verification of official Taiwan Lottery prize-table pages.

---

## 13. Recommended Next Task

**HOLD / WAITING_FOR_USER_AUTHORIZATION.**

- BIG_LOTTO and DAILY_539 replay data are structurally 100% feasible for a
  future read-only prize-aware adapter.
- POWER_LOTTO is feasible only for the 9,000-row (24.93%) subset with
  `predicted_special` populated; full-dataset POWER_LOTTO prize-aware replay
  evaluation remains **BLOCKED** until predicted second-zone coverage
  improves or a scoped POWER_LOTTO-only adapter is explicitly authorized.
- Any adapter implementation, scorer invocation (`score_prize_aware_ticket`
  called against real replay rows), or historical evaluation requires a new,
  separate, explicit P271E (or later) authorization with its own STOP
  conditions and file whitelist. P270C remains not authorized.

---

## 14. Final Classification

**`P271D_PARTIAL_LOTTERY_FEASIBILITY_GO_SCOPED_ADAPTER`**

- BIG_LOTTO: GO (full coverage)
- DAILY_539: GO (full coverage)
- POWER_LOTTO: GO_SCOPED (9,000/36,104 rows only; 27,104 rows BLOCKED pending
  predicted-second-zone coverage or separate scoped authorization)

---

## Declarations

- No prediction-versus-outcome comparison was run.
- The prize-aware scorer was not called.
- No prize-aware historical evaluation was run.
- No success rate, lift, p-value, or strategy ranking was calculated.
- DB access was read-only.
- No DB write happened.
- No registry mutation happened.
- Existing replay rows were not modified.
- Existing M3+/replay scoring remains unchanged.
- No production integration was added.
- No strategy was generated.
- No hit-rate improvement is claimed.
- Official source status remains `MANUAL_VERIFICATION_REQUIRED`.
- P270C remains unauthorized.
- Temporal-window research and feature mining were not started.
