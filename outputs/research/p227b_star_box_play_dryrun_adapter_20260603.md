# P227B — 3_STAR / 4_STAR Box-Play Dry-Run Adapter

**Date:** 2026-06-03
**Task:** `P227B_STAR_BOX_PLAY_DRYRUN_CODE_COMPLETE`
**Status:** COMPLETE / CODE-ONLY DRY-RUN
**Classification:** `P227B_STAR_BOX_PLAY_DRYRUN_CODE_COMPLETE` + `P227B_STAR_STRAIGHT_PLAY_REINGEST_REQUIRED`
**Authorized by:** User explicit task prompt 2026-06-03 (P227B code-change authorization)

This report covers the P227B implementation. No DB writes, no registry changes, no production changes.

---

## Phase 0 Verification

| Check | Expected | Actual | Result |
|---|---|---|---|
| repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | confirmed | PASS |
| branch | `main` → `p227b-star-box-play-code-dryrun` | confirmed | PASS |
| HEAD == origin/main | match | `a30a046` == `a30a046` | PASS |
| staged files | 0 | 0 | PASS |
| total replay rows | 94,924 | 94,924 | PASS |
| BIG_LOTTO rows | 24,140 | 24,140 | PASS |
| DAILY_539 rows | 34,680 | 34,680 | PASS |
| POWER_LOTTO rows | 36,104 | 36,104 | PASS |
| bet_index nulls | 0 | 0 | PASS |
| duplicate replay keys | 0 | 0 | PASS |
| PRAGMA integrity_check | `ok` | `ok` | PASS |
| drift guard | PASS | PASS | PASS |
| P227A artifacts tracked | 2 files | 2 files | PASS |

---

## Implemented Files

| File | Type | Description |
|---|---|---|
| `lottery_api/models/star_box_play.py` | Module | Pure metric functions: `star_box_exact_match`, `star_digit_overlap_count`, `star_calculate_box_score`, `get_box_baseline`, `validate_star_input`, `build_dryrun_row` |
| `tests/test_p227b_star_box_play_semantics.py` | Tests | 42 unit tests covering all metric cases, repeated digits, multiset semantics, dry_run isolation, `calculate_match_score` prohibition |
| `scripts/p227b_star_box_play_dryrun.py` | Script | Read-only dry-run summary: reads DB, demonstrates metrics on sample draws, writes JSON artifact, never writes DB |
| `outputs/research/p227b_star_box_play_dryrun_adapter_20260603.json` | Artifact | JSON summary (this task) |
| `outputs/research/p227b_star_box_play_dryrun_adapter_20260603.md` | Artifact | Markdown summary (this file) |

---

## Test Results

**42 / 42 PASS** (`tests/test_p227b_star_box_play_semantics.py`)

| Test group | Count | Result |
|---|---|---|
| Exact box match | 5 | PASS |
| Repeated digit handling | 4 | PASS |
| Overlap count (multiset) | 6 | PASS |
| Box score encoding | 5 | PASS |
| Baselines | 5 | PASS |
| Sorted-input limitation | 3 | PASS |
| Set vs multiset semantics | 2 | PASS |
| `calculate_match_score` prohibition | 1 | PASS |
| Input validation | 5 | PASS |
| `build_dryrun_row` | 6 | PASS |
| **Total** | **42** | **42 PASS, 0 FAIL** |

Key test: `test_overlap_repeated_digit_multiset_differs_from_set` confirms that `set` intersection gives the wrong result (1) when both inputs have repeated digits, while `Counter` intersection gives the correct result (2). This validates the requirement that `calculate_match_score` is not used.

---

## Metric Semantics

### `star_box_exact_match(predicted, actual) → bool`
Returns `True` if `Counter(predicted) == Counter(actual)`. Order-independent. Handles repeated digits correctly.

### `star_digit_overlap_count(predicted, actual) → int`
Returns `sum((Counter(predicted) & Counter(actual)).values())` — multiset intersection size. NOT a prize-winning threshold.

### `star_calculate_box_score(predicted, actual, pick_count) → (hit_count, exact_hit, overlap)`
- `hit_count`: `pick_count` if exact box hit, else `0`. Safe for `strategy_prediction_replays.hit_count` storage.
- `exact_hit`: boolean exact match flag.
- `overlap`: multiset overlap count (secondary metric).

**Never compare `hit_count` to M2+/M3+ thresholds designed for 6-digit lotteries.**

---

## Baselines

| Lottery | Combination space | Box-exact baseline |
|---|---|---|
| 3_STAR (no repeats, current DB) | C(10,3) = 120 | **1/120 ≈ 0.00833** |
| 4_STAR (no repeats, current DB) | C(10,4) = 210 | **1/210 ≈ 0.00476** |
| 3_STAR (with repeats, if re-ingested) | C(12,3) = 220 | 1/220 ≈ 0.00455 |
| 4_STAR (with repeats, if re-ingested) | C(13,4) = 715 | 1/715 ≈ 0.00140 |

Current DB: 0 repeated-digit draws observed in both lotteries. Active baseline = no-repeat.

---

## Statistical Power Warning

| Lottery | Available draws | Expected exact hits (baseline) | Draws needed for 80% power (20% lift, α=0.05) |
|---|---|---|---|
| 3_STAR | 4,179 | ~35 | ~10,000 |
| 4_STAR | 2,922 | ~14 | ~17,000 |

**Both lotteries are currently UNDERPOWERED for exact-combo signal detection.** Any future P227C scan must include a power analysis gate and classify results as `INSUFFICIENT_STATISTICAL_POWER` if below threshold. Do not interpret hit-rate fluctuations as evidence of signal.

---

## Dry-Run Limitations

- `dry_run = 1` in all `build_dryrun_row` outputs — never set to 0 without separate authorization.
- `truth_level = "BOX_PLAY_DRY_RUN_BOX_EXACT"` distinguishes from live replay rows.
- No rows written to `strategy_prediction_replays`.
- The demo in `scripts/p227b_star_box_play_dryrun.py` uses a naive "predict previous draw" approach purely for metric demonstration — it is not a real strategy.

---

## Straight-Play: Still Blocked

Straight-play (exact positional match) requires per-digit order information. Current DB stores all draws as sorted arrays — positional order is lost. Re-ingestion from a raw positional source is required before straight-play can be implemented. This remains a separate, unauthorized task.

---

## DB Unchanged

| Check | Before | After | Status |
|---|---|---|---|
| Total replay rows | 94,924 | 94,924 | UNCHANGED |
| 3_STAR replay rows | 0 | 0 | UNCHANGED |
| 4_STAR replay rows | 0 | 0 | UNCHANGED |
| PRAGMA integrity_check | `ok` | `ok` | PASS |
| Drift guard | PASS | PASS | PASS |

---

## No Production Changes

- No registry mutations.
- No production-data changes.
- No recommendation-logic changes.
- No `controlled_apply`.
- No strategy promotions.
- No betting advice or guaranteed prediction claims.

---

## Required Completion Check

1. **是否真的完成:** YES — pure metric module, 42-test suite, dry-run script, and both artifacts complete.
2. **測試結果:** **42/42 PASS** (`test_p227b_star_box_play_semantics.py`). Drift guard PASS. DB baseline PASS. Full pytest suite NOT RUN (targeted tests only).
3. **仍卡住的唯一問題:** Straight-play remains blocked (sorted storage; re-ingestion required, separate authorization). Statistical power is insufficient for both lotteries (~4,000/~3,000 draws vs ~10,000/~17,000 needed).
4. **修改檔案清單:**
   - `lottery_api/models/star_box_play.py` (new)
   - `tests/test_p227b_star_box_play_semantics.py` (new)
   - `scripts/p227b_star_box_play_dryrun.py` (new)
   - `outputs/research/p227b_star_box_play_dryrun_adapter_20260603.json` (new)
   - `outputs/research/p227b_star_box_play_dryrun_adapter_20260603.md` (new)
5. **staged / commit / push:** awaiting final staging verification.
6. **是否允許進入下一輪:** YES — P227C (full scan with power-analysis gate) would be the logical next step if authorized.
7. **Final Classification:** `P227B_STAR_BOX_PLAY_DRYRUN_CODE_COMPLETE` + `P227B_STAR_STRAIGHT_PLAY_REINGEST_REQUIRED`
