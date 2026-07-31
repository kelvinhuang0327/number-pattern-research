# P8 Reconstructible Backfill Dry-Run — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Script**: `scripts/p8_reconstructible_backfill_dry_run.py`  
**Tests**: `tests/test_p8_reconstructible_backfill_dry_run.py` — **37/37 PASS**  
**Output**: `outputs/replay/p8_reconstructible_backfill_dry_run_20260520.json`  
**Safety**: zero DB writes · zero strategy execution · dry_run_only=True

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total RECONSTRUCTIBLE candidates | **121** |
| Have prediction_items (predicted_numbers) | **121/121 — 100%** |
| Have draw result (actual_numbers) | **121/121 — 100%** |
| Have both (fully constructable) | **121/121 — 100%** |
| READY_FOR_ONLINE_APPLY | **28** (ONLINE lifecycle) |
| PENDING_HUMAN_REVIEW_RETIRED | **93** (RETIRED lifecycle) |
| Production rows | **460** (unchanged) |
| Projected after ONLINE apply | **488** |
| Projected after ONLINE+RETIRED apply | **581** |

**All 121 RECONSTRUCTIBLE rows can be fully constructed from existing DB data.**  
No strategy re-execution required. No data fabrication. No external data needed.

---

## Field Availability Per Row

For each of the 121 candidates, the following fields are available from existing DB tables:

| Field | Source Table | Available |
|-------|-------------|-----------|
| `predicted_numbers` | `prediction_items` (via `run_id`) | ✅ 121/121 |
| `actual_numbers` | `draws` | ✅ 121/121 |
| `actual_special` | `draws` | ✅ 121/121 |
| `target_date` | `draws` | ✅ 121/121 |
| `hit_count` | Computed: `predicted ∩ actual` | ✅ 121/121 |
| `hit_numbers` | Computed: `sorted(predicted ∩ actual)` | ✅ 121/121 |
| `history_cutoff_draw` | Computed: `draw_id - 1` | ✅ 121/121 |
| `provenance_hash` | P7 dry-run JSON | ✅ 121/121 |
| `controlled_apply_id` | P7 dry-run JSON | ✅ 121/121 |
| `truth_level` | Constant: `RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD` | ✅ 121/121 |
| `source` | Constant: `P7_CONTROLLED_APPLY` | ✅ 121/121 |
| `replay_run_id` | Set to NULL (P7 convention) | ✅ 121/121 |

**No fields are missing. All 121 rows are fully constructable.**

---

## Candidate Status Breakdown

### READY_FOR_ONLINE_APPLY (28) — ONLINE lifecycle

| Strategy ID | Lottery | Lifecycle | Draw Count |
|-------------|---------|-----------|-----------|
| fourier_rhythm_3bet | POWER_LOTTO | ONLINE | 12 |
| ts3_regime_3bet | BIG_LOTTO | ONLINE | 16 |

These 28 rows will be inserted when CEO phrase is received.  
`should_count_as_success = True` for all (actual_numbers and hit_count available).

**Sample payload preview (draw 115000030, fourier_rhythm_3bet):**
```json
{
  "lottery_type": "POWER_LOTTO",
  "target_draw": "115000030",
  "target_date": "2026/04/13",
  "strategy_id": "fourier_rhythm_3bet",
  "predicted_numbers": "[11, 16, 24, 26, 29, 38]",
  "actual_numbers": "[3, 10, 11, 16, 19, 24]",
  "hit_count": 3,
  "hit_numbers": "[11, 16, 24]",
  "truth_level": "RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD",
  "source": "P7_CONTROLLED_APPLY",
  "replay_run_id": null,
  "dry_run": 1
}
```

### PENDING_HUMAN_REVIEW_RETIRED (93) — RETIRED lifecycle

| Strategy ID | Lottery | Lifecycle | Draw Count |
|-------------|---------|-----------|-----------|
| acb_1bet | DAILY_539 | RETIRED | 31 |
| acb_markov_midfreq_3bet | DAILY_539 | RETIRED | 31 |
| midfreq_acb_2bet | DAILY_539 | RETIRED | 31 |

These 93 rows are data-complete but require:
1. Human review of lifecycle warnings (strategies are RETIRED)
2. `--scope INCLUDE_RETIRED_WITH_WARNING`
3. `--include-retired-reviewed` flag
4. Separate CEO authorization (distinct from ONLINE phrase)

`should_count_as_success = False` until lifecycle review completes.

---

## Why No DB Write This Round

1. **CEO authorization phrase not received.** The exact phrase `YES apply P7 controlled replay rows` was not present in this session.

2. **P7 controlled apply script owns the insert.** `scripts/p7_controlled_replay_row_apply.py` handles the actual insert when authorized; P8 only plans the payload.

3. **RETIRED rows require separate human review + authorization.** 93 rows cannot be mixed into the ONLINE apply without independent oversight.

4. **Production DB must remain at 460** until CEO phrase is received.

---

## P3 Coverage Impact (Post-Apply Projection)

| State | Now | After P7 ONLINE (488 rows) | After P7 ONLINE+RETIRED (581 rows) |
|-------|-----|---------------------------|-------------------------------------|
| ROW_BACKED | 300 (23.3%) | **328 (25.5%)** | **421 (32.7%)** |
| RECONSTRUCTIBLE | 121 (9.4%) | 93 (7.2%) | **0 (0%)** |
| NO_DATA | 867 (67.3%) | 867 (67.3%) | 867 (67.3%) |
| `real_replay_success_count` | 300 | **328** | **421** |
| `fake_success_count` | **0** | **0** | **0** |

The 867 NO_DATA cells are permanent structural gaps — strategies had no live predictions for those draws. They cannot be filled without fabricating data.

---

## Human Review Requirements (RETIRED)

Before the 93 RETIRED rows can be inserted:

1. Review each row's lifecycle warning in `outputs/replay/p7_controlled_apply_dry_run_20260520.json` under `all_plan_rows[lifecycle_state=RETIRED]`.
2. Confirm that inserting RETIRED strategy rows as historical-only data is acceptable.
3. Receive separate CEO authorization.
4. Use flags: `--scope INCLUDE_RETIRED_WITH_WARNING --include-retired-reviewed`.

Note: RETIRED rows create **historical-only** replay records. They do not affect production strategy selection or UI-visible strategy lists.

---

## Safety Confirmation

- ✅ **Zero DB writes** — opens DB with `PRAGMA query_only = ON`
- ✅ **Zero strategy execution** — no predict_func, no generate_numbers
- ✅ **Zero data fabrication** — all predicted/actual numbers from existing DB tables
- ✅ **Zero draw imports** — all draw data read from existing `draws` table
- ✅ **fake_success_count = 0** — RECONSTRUCTIBLE/PENDING rows marked `should_count_as_success=False`
- ✅ **Production rows = 460** — unchanged
- ✅ **37/37 tests PASS**
