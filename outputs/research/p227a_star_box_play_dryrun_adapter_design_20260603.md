# P227A — 3_STAR / 4_STAR Box-Play Dry-Run Adapter Design

**Date:** 2026-06-03
**Task:** `P227A_STAR_BOX_PLAY_DRYRUN_ADAPTER_DESIGN`
**Status:** COMPLETE / PLAN-ONLY / READ-ONLY
**Classification:** `P227A_STAR_BOX_PLAY_ADAPTER_DESIGN_READY` + `P227A_STAR_STRAIGHT_PLAY_BLOCKED_REINGEST_REQUIRED`
**Authorized by:** User explicit task prompt 2026-06-03

This document is a design artifact only. It does not implement code, modify tests, write DB rows, mutate registry, or change production state. It is not betting advice.

---

## Phase 0 Verification

| Check | Expected | Actual | Result |
|---|---|---|---|
| repo root | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | PASS |
| branch (Phase 0 verified on main) | `main` | `main` | PASS |
| git-dir | `.git` | `.git` | PASS |
| HEAD == origin/main | match | `2ac9f1f` == `2ac9f1f` | PASS |
| staged files | 0 | 0 | PASS |
| total replay rows | 94,924 | 94,924 | PASS |
| BIG_LOTTO rows | 24,140 | 24,140 | PASS |
| DAILY_539 rows | 34,680 | 34,680 | PASS |
| POWER_LOTTO rows | 36,104 | 36,104 | PASS |
| bet_index nulls | 0 | 0 | PASS |
| duplicate replay keys | 0 | 0 | PASS |
| PRAGMA integrity_check | `ok` | `ok` | PASS |
| drift guard | PASS | PASS | PASS |
| P226 artifacts present | yes | yes | PASS |

---

## 1. P226 Finding Recap

| Finding | Detail |
|---|---|
| 3_STAR draw rows | 4,179 (2007–2026), digits 0–9, no repeats observed, 100% sorted |
| 4_STAR draw rows | 2,922 (2007–2026), digits 0–9, no repeats observed, 100% sorted |
| 3_STAR replay rows | **0** (all aliases confirmed zero) |
| 4_STAR replay rows | **0** (all aliases confirmed zero) |
| Registry coverage | **None** for either lottery type |
| `lottery_types.json` | `isPermutation: true, repeatsAllowed: true` for both |
| DB storage | `numbers` stored as **sorted JSON array** — positional order **lost** |
| `calculate_match_score` | Uses `set` intersection — semantically wrong for permutations |
| Existing adapters | Zero support for digit-type lotteries |

---

## 2. Box-Play-Only Rationale

### Why current DB data supports box-play only

The `numbers` field in `draws` stores sorted digit arrays (e.g. `[5, 6, 9]`). For 3_STAR this means:
- Draw result `5-6-9` (hundreds=5, tens=6, units=9) and draw result `9-5-6` (hundreds=9, tens=5, units=6) are stored identically as `[5, 6, 9]`.
- All positional information is destroyed at ingest.

**Box-play** (combination mode) treats the draw as an unordered set of digits. A prediction of `{5, 6, 9}` wins if the actual draw contains exactly those three digits in any order. This is fully computable from sorted storage.

**Straight-play** (permutation/exact-order mode) requires knowing the order of digits. Since positional order is not stored, straight-play validation is impossible on current data.

### Why this limitation is inherent to the current ingest pipeline

The existing CSV validator for 3_STAR / 4_STAR (`lottery_api/test_star_lottery_logic.py` confirms `should_preserve_order: True`) expects order to be preserved, but the actual DB rows show 100% sorted outcomes, indicating the pipeline did not implement this. This is a data quality issue, not just a schema issue.

### Consequence for this design

This adapter design targets **box-play only**. All metric definitions, baselines, test cases, and feature families are defined under box-play semantics. Straight-play is explicitly out of scope and remains blocked until re-ingestion.

---

## 3. Straight-Play Blocked Rationale

| Reason | Detail |
|---|---|
| Positional order lost | 100% of draw rows have `numbers == sorted(numbers)` |
| C(10,3) = 120 unique combos | All 120 appear in 4,179 draws — consistent with sorted combination storage, not permutation |
| No raw positional source | No separate column or supplementary table preserving digit order |
| re-ingestion required | Would need raw source CSV/API with columns `Digit1, Digit2, Digit3` in draw order |
| Separate authorization needed | Re-ingestion = DB write to `draws` table = explicitly unauthorized in this task |

**Classification:** `P227A_STAR_STRAIGHT_PLAY_BLOCKED_REINGEST_REQUIRED`

If straight-play is authorized in a future task, the design changes needed are: (a) re-ingest draws with positional columns preserved, (b) define per-position digit-frequency features, (c) define positional-match scoring (exact-position hit count), (d) revise baselines to use P(10,k) permutations.

---

## 4. Repeated-Digit Limitation

`lottery_types.json` declares `repeatsAllowed: true` (e.g. `5-5-5` is a valid 3_STAR draw). However, the current DB has **0** repeated-digit draws in both 3_STAR (4,179 rows) and 4_STAR (2,922 rows).

Possible explanations:
1. **Repeated digits are not drawn** in current lottery rules (C(10,k) with distinct digits only).
2. **Repeats were stripped** by the ingest pipeline.
3. **Repeats occurred historically** but are absent in the current data range.

**Design decision for this adapter:** The adapter must be designed to **handle repeated digits correctly** even if current data does not include them, because:
- `lottery_types.json` explicitly allows repeats.
- Ignoring the case would make the adapter fragile if data changes.
- A prediction of `[5, 5, 9]` must be treated differently from `[5, 6, 9]`.

Under **box-play with repeats**, the comparison is multiset equality (or multiset overlap), not set equality. The adapter must distinguish:
- `box_exact_multiset_match`: predicted multiset == actual multiset (e.g. `[5,5,9]` vs `[5,5,9]` → match; `[5,5,9]` vs `[5,6,9]` → no match)
- `box_exact_set_match`: predicted set == actual set (only valid when repeats are absent)

**Baseline caveat:** If draws are truly without repeats (as current data suggests), the combination space is C(10,k) and the correct box-play baseline is `1/C(10,k)`. If repeats are possible, the combination space is C(10+k-1, k) and baselines change significantly. The adapter must document which assumption is active.

---

## 5. Metric Definitions

### 5.1 Primary Metric: `star_box_exact_hit`

```
star_box_exact_hit = 1 if sorted(predicted_digits) == sorted(actual_digits) else 0
```

This is the only metric that directly corresponds to winning the lottery in box-play mode. It is binary per draw.

**Key constraint:** This metric requires `len(predicted_digits) == len(actual_digits) == pick_count`. For 3_STAR: pick_count = 3; for 4_STAR: pick_count = 4.

### 5.2 Secondary Metric: `star_digit_overlap_count`

```
star_digit_overlap_count = len(multiset_intersection(predicted_digits, actual_digits))
```

Where `multiset_intersection` counts shared digits with multiplicity. For distinct-digit draws:
```
star_digit_overlap_count = len(set(predicted_digits) & set(actual_digits))
```

This is analogous to `hit_count` in existing set-pick lotteries, but its meaning is different: in a 3-digit box lottery, `star_digit_overlap_count = 2` means 2 of 3 digits are shared — but this is not a prize-winning condition in standard box-play.

**Mapping to existing schema field:**
- Store `star_digit_overlap_count` in the `hit_count` column with an explicit label in `truth_level` or `source` to signal non-standard semantics.
- Do NOT allow any downstream code to compare `hit_count >= 2` against prize thresholds designed for 6-digit lotteries.

### 5.3 Why `calculate_match_score` Cannot Be Reused

```python
# Existing function — set-pick semantics
def calculate_match_score(predicted, actual):
    return len(set(predicted) & set(actual))
```

Problems for digit lotteries:
1. **Repeated-digit erasure:** `set([5,5,9]) == {5,9}` → a repeat is silently dropped.
2. **Wrong prize mapping:** For DAILY_539, `hit_count >= 3` has meaning (partial prize). For 3_STAR box, only `hit_count == 3` (all digits matched) means a win.
3. **Overcount for permutation:** `[9,6,5]` vs actual `[5,6,9]` → set intersection gives 3 (looks like exact match) but no digit is in the correct position.

**Requirement:** The star adapter must define a separate `star_calculate_match(predicted, actual, play_mode='box_exact')` function and **must not call `calculate_match_score`** for 3_STAR / 4_STAR draws.

### 5.4 Metric Table

| Metric name | Formula | Stored in | Box-play valid? | Straight-play valid? |
|---|---|---|---|---|
| `star_box_exact_hit` | `int(sorted(pred) == sorted(actual))` | `hit_count` (= 0 or pick_count) | ✅ | ❌ |
| `star_digit_overlap_count` | `len(multiset_intersect(pred, actual))` | `hit_count` | ✅ (secondary) | ❌ |
| `star_position_exact_hit` | `sum(p==a for p,a in zip(pred, actual))` | *not storable in current sorted DB* | N/A | ✅ (requires re-ingest) |
| `special_hit` | N/A (special=0 always) | `special_hit` = 0 always | — | — |

**For dry-run use:** Store `star_box_exact_hit` as `hit_count` (0 or pick_count). Store `star_digit_overlap_count` in a separate JSON field within `hit_numbers` (e.g. `{"overlap": 2, "box_exact": 0}`) to avoid confusion with set-pick semantics.

---

## 6. Baseline Definitions and Caveats

### 6.1 Current-storage baselines (no-repeat assumption)

These baselines assume the draws are combinations of k distinct digits from {0..9}.

| Lottery | Combination space | Box-play exact-match baseline |
|---|---|---|
| 3_STAR | C(10,3) = **120** | **1/120 ≈ 0.00833** |
| 4_STAR | C(10,4) = **210** | **1/210 ≈ 0.00476** |

For a strategy predicting one combination per draw, the expected hit rate under random selection equals these values.

### 6.2 If repeats are ever re-ingested (multiset baseline)

| Lottery | Multiset space | Box multiset exact-match baseline |
|---|---|---|
| 3_STAR | C(10+3-1,3) = C(12,3) = **220** | 1/220 ≈ 0.00455 |
| 4_STAR | C(10+4-1,4) = C(13,4) = **715** | 1/715 ≈ 0.00140 |

**Critical:** If the data changes to include repeats, both the feature computation and the baseline must be updated before any comparison is run. The adapter must include a `repeats_detected_in_data: bool` flag that gates which baseline is used.

### 6.3 Statistical power warning

With the current-storage baselines:

| Lottery | n_draws available | P(exact hit) baseline | Expected hits | 20% lift detection power (α=0.05) |
|---|---|---|---|---|
| 3_STAR | 4,179 | 0.00833 | ~35 hits total | Requires ~10,000 draws for 80% power |
| 4_STAR | 2,922 | 0.00476 | ~14 hits total | Requires ~17,000 draws for 80% power |

**Conclusion:** Both lotteries are statistically underpowered for exact-combo hit detection with current draw counts. Any P227B scan must include a power analysis gate and must classify underpowered results as `INSUFFICIENT_STATISTICAL_POWER`, not as NULL or positive signal.

### 6.4 Overlap-count baselines

For `star_digit_overlap_count >= k` where k < pick_count, the random baseline can be computed combinatorially. These are secondary metrics only and do not correspond to prize-winning conditions.

---

## 7. Adapter Design

### 7.1 File structure (proposed — no code written yet)

```
lottery_api/models/
  p227b_star_box_play_adapter.py        # new file, requires code-change authorization
  
tests/
  test_p227a_star_box_play_semantics.py  # new test file, requires code-change authorization
```

These files do not exist yet and must not be created until P227B is explicitly authorized.

### 7.2 Proposed adapter class: `StarBoxPlayAdapter`

```python
# DESIGN ONLY — do not implement until P227B is authorized

class StarBoxPlayAdapterMeta:
    strategy_id: str          # e.g. "star3_digit_freq_box_1bet"
    strategy_name: str
    strategy_version: str     # e.g. "v0.1_dry_run"
    supported_lottery_types: List[str]  # ["3_STAR"] or ["4_STAR"]
    pick_count: int           # 3 for 3_STAR, 4 for 4_STAR
    repeats_allowed: bool     # False for current sorted data; True if re-ingested
    play_mode: str            # "box_exact" (only authorized mode)
    baseline: float           # 1/C(10,pick_count) for current no-repeat data

class StarBoxPlayAdapter:
    """
    Dry-run-only adapter for 3_STAR / 4_STAR box-play prediction replay.
    
    MUST NOT:
    - call calculate_match_score
    - write to strategy_prediction_replays with dry_run=0
    - compare hit_count to thresholds designed for 6-digit lotteries
    - assume positional order of stored draw digits
    - use special_hit (always 0 for star lotteries)
    
    MUST:
    - sort both predicted and actual before comparing (box-play)
    - validate len(predicted) == pick_count
    - validate all digits in 0..9
    - validate no repeated digits when repeats_allowed=False
    - store dry_run=1 in all output rows
    - store play_mode label in truth_level or source field
    """
    
    def _call_strategy(
        self, history: List[dict], lottery_type: str
    ) -> List[int]:
        """Return pick_count predicted digits, each in 0..9."""
        raise NotImplementedError
    
    @staticmethod
    def star_calculate_match(
        predicted: List[int],
        actual: List[int],
        play_mode: str = "box_exact"
    ) -> dict:
        """
        Compute digit-lottery match metrics.
        
        Returns:
            {
              "box_exact_hit": int,    # 1 if sorted(predicted)==sorted(actual), else 0
              "digit_overlap": int,    # len(multiset_intersection(predicted, actual))
              "play_mode": str,
              "predicted_sorted": List[int],
              "actual_sorted": List[int],
            }
        """
        pred_sorted = sorted(predicted)
        act_sorted = sorted(actual)
        box_exact = int(pred_sorted == act_sorted)
        # multiset intersection
        from collections import Counter
        overlap = sum((Counter(pred_sorted) & Counter(act_sorted)).values())
        return {
            "box_exact_hit": box_exact,
            "digit_overlap": overlap,
            "play_mode": play_mode,
            "predicted_sorted": pred_sorted,
            "actual_sorted": act_sorted,
        }
    
    def generate_dry_run_row(
        self,
        target_draw: str,
        target_date: str,
        history: List[dict],
        actual_numbers: List[int],
        bet_index: int = 1,
    ) -> dict:
        """
        Generate a single dry-run replay row dict.
        Does NOT write to DB. Returns a dict matching strategy_prediction_replays schema
        with dry_run=1 and play_mode labeled.
        """
        predicted = self._call_strategy(history, self.meta.lottery_type)
        match = self.star_calculate_match(predicted, actual_numbers)
        return {
            "lottery_type": self.meta.lottery_type,
            "target_draw": target_draw,
            "target_date": target_date,
            "strategy_id": self.meta.strategy_id,
            "strategy_name": self.meta.strategy_name,
            "strategy_version": self.meta.strategy_version,
            "history_cutoff_draw": history[-1]["draw"] if history else None,
            "replay_status": "PREDICTED",
            "predicted_numbers": predicted,                   # List[int], not sorted
            "actual_numbers": actual_numbers,                 # as stored in DB (sorted)
            "hit_numbers": match["predicted_sorted"],         # store sorted predicted for display
            "hit_count": match["box_exact_hit"] * self.meta.pick_count,  # 0 or pick_count
            "special_hit": 0,
            "dry_run": 1,                                     # ALWAYS 1 for dry-run
            "truth_level": f"BOX_PLAY_DRY_RUN_{self.meta.play_mode.upper()}",
            "source": "P227B_STAR_BOX_PLAY_DRY_RUN",
            # Extra fields for analysis (stored as JSON in hit_numbers or provenance)
            "_digit_overlap": match["digit_overlap"],         # secondary metric
            "_box_exact_hit": match["box_exact_hit"],         # primary metric (0 or 1)
            "_baseline": self.meta.baseline,                  # for reference
        }
```

### 7.3 Input schema requirements

The adapter's `history` parameter is a list of draw dicts with at least:
```python
{
    "draw": str,               # draw number as string
    "date": str,               # ISO date string
    "numbers": List[int],      # stored sorted, e.g. [5, 6, 9]
    "lottery_type": str,       # "3_STAR" or "4_STAR"
}
```

**Critical:** The adapter must **not** assume `numbers` represents the order of drawing. All features must be derived from sorted combinations only.

### 7.4 Output schema for dry-run artifacts

Dry-run rows must have `dry_run = 1` at all times. The UNIQUE constraint on `(lottery_type, target_draw, strategy_id, bet_index)` means dry-run rows could collide with future production rows. To prevent this:

**Option A (recommended):** Use `strategy_id` with a `_dry_run` suffix (e.g. `star3_digit_freq_box_1bet_dry_run`). This ensures uniqueness without needing a separate table.

**Option B:** Use a separate in-memory artifact list (CSV/JSON/SQLite :memory:) for dry-run output, never touching `strategy_prediction_replays`. This avoids any DB write entirely.

**Recommendation:** Use Option B (in-memory / file-only dry-run) for P227B. This allows evaluation without any DB-write authorization. DB insertion can be a separate authorized step.

### 7.5 How to avoid polluting `strategy_prediction_replays`

1. The adapter's `generate_dry_run_row` method returns a dict only — it must never call any database function.
2. A separate orchestrator (`StarBoxPlayDryRunRunner`) accumulates dry-run rows into a list and writes them to a JSON/CSV artifact.
3. Only a separately authorized `StarBoxPlayDBWriter` (if ever created) would convert dry-run rows into DB rows with `dry_run=0`.
4. The UNIQUE schema constraint prevents accidental double-insertion.

---

## 8. Test Strategy

All tests listed here are design specifications only. They must not be implemented until P227B is authorized.

### 8.1 Unit tests for `star_calculate_match`

```python
# test_p227a_star_box_play_semantics.py (proposed — NOT IMPLEMENTED)

def test_box_exact_hit_correct():
    result = StarBoxPlayAdapter.star_calculate_match([5,6,9], [5,6,9])
    assert result["box_exact_hit"] == 1
    assert result["digit_overlap"] == 3

def test_box_exact_hit_wrong_order_is_still_hit():
    # box-play: order does not matter
    result = StarBoxPlayAdapter.star_calculate_match([9,6,5], [5,6,9])
    assert result["box_exact_hit"] == 1   # sorted both → [5,6,9] == [5,6,9]

def test_box_exact_miss():
    result = StarBoxPlayAdapter.star_calculate_match([1,2,3], [5,6,9])
    assert result["box_exact_hit"] == 0
    assert result["digit_overlap"] == 0

def test_partial_overlap():
    result = StarBoxPlayAdapter.star_calculate_match([5,6,1], [5,6,9])
    assert result["box_exact_hit"] == 0
    assert result["digit_overlap"] == 2

def test_prove_calculate_match_score_not_used():
    # set intersection would return 3 for [9,6,5] vs [5,6,9],
    # but we want box_exact semantics (which also return 1 for box_exact, 3 for overlap)
    # The critical test is for repeated digits:
    result = StarBoxPlayAdapter.star_calculate_match([5,5,9], [5,6,9])
    assert result["box_exact_hit"] == 0   # [5,5,9] != [5,6,9] sorted
    assert result["digit_overlap"] == 2   # multiset: 5 appears once in intersection
    # old calculate_match_score would give: len({5,9} & {5,6,9}) = 2 (SAME result here)
    # but for [5,5,5] vs [5,5,9]:
    result2 = StarBoxPlayAdapter.star_calculate_match([5,5,5], [5,5,9])
    assert result2["box_exact_hit"] == 0
    assert result2["digit_overlap"] == 2  # multiset: two 5s in intersection
    # old calculate_match_score: len({5} & {5,9}) = 1  ← WRONG (would be 1, not 2)
```

### 8.2 Unit tests for repeated-digit handling

```python
def test_repeated_digit_box_exact_match():
    # 3_STAR with triple: [5,5,5] vs [5,5,5]
    result = StarBoxPlayAdapter.star_calculate_match([5,5,5], [5,5,5])
    assert result["box_exact_hit"] == 1
    assert result["digit_overlap"] == 3

def test_repeated_digit_partial_overlap():
    result = StarBoxPlayAdapter.star_calculate_match([5,5,5], [5,5,9])
    assert result["box_exact_hit"] == 0
    assert result["digit_overlap"] == 2  # multiset: two 5s in intersection
```

### 8.3 Tests for sorted-input limitation

```python
def test_adapter_sorts_before_comparison():
    # All DB draws are pre-sorted; adapter must also sort predicted
    result = StarBoxPlayAdapter.star_calculate_match([9,5,6], [5,6,9])
    assert result["predicted_sorted"] == [5,6,9]
    assert result["actual_sorted"] == [5,6,9]
    assert result["box_exact_hit"] == 1

def test_dry_run_flag_is_always_1():
    adapter = MockStar3Adapter()
    row = adapter.generate_dry_run_row("115000001", "2026-01-01", [...], [5,6,9])
    assert row["dry_run"] == 1

def test_truth_level_labels_dry_run():
    adapter = MockStar3Adapter()
    row = adapter.generate_dry_run_row("115000001", "2026-01-01", [...], [5,6,9])
    assert "DRY_RUN" in row["truth_level"]
    assert "BOX_PLAY" in row["truth_level"]
```

### 8.4 Anti-contamination tests

```python
def test_adapter_does_not_call_calculate_match_score():
    # Verify via import inspection that star_calculate_match
    # does not delegate to calculate_match_score
    import ast, inspect
    src = inspect.getsource(StarBoxPlayAdapter.star_calculate_match)
    tree = ast.parse(src)
    calls = [n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Name)]
    assert "calculate_match_score" not in calls

def test_no_special_hit_used():
    adapter = MockStar3Adapter()
    row = adapter.generate_dry_run_row("115000001", "2026-01-01", [...], [5,6,9])
    assert row["special_hit"] == 0

def test_dry_run_does_not_write_db(tmp_path, monkeypatch):
    # Verify generate_dry_run_row returns a dict and calls no DB methods
    db_calls = []
    monkeypatch.setattr("lottery_api.database.LotteryDatabase.insert_prediction",
                        lambda *a, **kw: db_calls.append(a))
    adapter = MockStar3Adapter()
    _ = adapter.generate_dry_run_row("115000001", "2026-01-01", [...], [5,6,9])
    assert db_calls == []
```

---

## 9. Future P227B Implementation Scope

### 9.1 Minimal files likely needed (if P227B is authorized)

| File | Action | Type |
|---|---|---|
| `lottery_api/models/p227b_star_box_play_adapter.py` | Create new | Code |
| `tests/test_p227a_star_box_play_semantics.py` | Create new | Test |
| `outputs/research/p227b_star_box_play_dryrun_results_YYYYMMDD.json` | Create new | Artifact |
| `outputs/research/p227b_star_box_play_dryrun_results_YYYYMMDD.md` | Create new | Artifact |

Files that must **NOT** be modified in P227B:
- `lottery_api/quick_strategy_evaluation.py` (existing `calculate_match_score`)
- `lottery_api/comprehensive_strategy_evaluation.py`
- `lottery_api/database.py`
- `lottery_api/models/p36_wave2_daily539_adapters.py` (and all p42, p47, p93)
- `strategy_prediction_replays` (DB table — no rows written unless separately authorized)
- `lottery_api/data/lottery_types.json`
- Any governance document

### 9.2 Separation of code dry-run from DB-write

| Layer | What it does | Authorization needed |
|---|---|---|
| `star_calculate_match` | Pure function; computes metrics | Code-change scope |
| `StarBoxPlayAdapter._call_strategy` | Pure function; generates digit prediction from history | Code-change scope |
| `StarBoxPlayAdapter.generate_dry_run_row` | Pure function; returns a dict (no DB) | Code-change scope |
| `StarBoxPlayDryRunRunner` | Iterates draws, collects dicts, writes JSON/CSV | Code-change scope |
| `StarBoxPlayDBWriter` | Inserts dry_run=1 rows into `strategy_prediction_replays` | **Separate DB-write authorization** |
| Promote to dry_run=0 | Marks rows as live production | **Separate production-promotion authorization** |

This separation means the functional code (pure functions + file writer) can be reviewed and tested without any DB involvement. Only the final `StarBoxPlayDBWriter` step requires DB-write authorization.

### 9.3 Pre-registration requirements before P227B

Before writing any code or running any scan, the following must be registered in a P227B plan document:

1. **Chosen play mode:** `box_exact` only (no straight-play).
2. **Strategy families to test** (from P226 candidate list): at minimum, `digit_frequency_all_position` and `sum_of_digits` and `last_seen_gap`.
3. **Window set:** short 100/125/150 and mid 500/750/1000 (P221F frozen).
4. **Primary metric:** `star_box_exact_hit` rate.
5. **Baseline:** `1/C(10,3) = 0.00833` for 3_STAR; `1/C(10,4) = 0.00476` for 4_STAR.
6. **Correction method:** Bonferroni or BH-FDR across all strategy families tested.
7. **Power analysis:** must report required N and classify as `INSUFFICIENT_STATISTICAL_POWER` if current draw count is below threshold.
8. **Success condition:** positive edge that survives correction, walk-forward OOS, and block stability — OR honest NULL / INSUFFICIENT_POWER.

---

## 10. Anti-Overfit Gate

All P227B work must inherit the P221F anti-overfit gate, extended for digit-type lotteries:

| Rule | Requirement |
|---|---|
| Pre-register play mode | `box_exact` only; no post-hoc switching to straight or partial |
| Pre-register windows | P221F frozen: short 100/125/150, mid 500/750/1000, all-history = reference |
| Pre-register baselines | C(10,k) for current no-repeat data; flag and recompute if repeats appear |
| Pre-register features | All feature families listed before any dry-run execution |
| Multiple-testing correction | Bonferroni or BH-FDR across all strategies and windows tested |
| Walk-forward / OOS | Non-overlapping blocks; no in-sample selection of best window |
| Power analysis | Compute required N; classify UNDERPOWERED if below threshold |
| NULL accepted | NULL result is a valid, successful outcome |
| No production claim | No strategy promotion, no recommendation-logic change, no betting advice from dry-run |
| Repeat-digit flag | `repeats_detected_in_data` must gate baseline selection |

---

## 11. Authorization Requirements

### Currently authorized (this task)
- Producing this design document and the companion JSON artifact.

### Requires separate explicit authorization
- Any code change to any file (even creating a new file).
- Any DB write (strategy_prediction_replays rows, even with dry_run=1).
- Re-ingestion of historical draw data with positional order.
- Registry mutation.
- Production-replay promotion (dry_run=0).
- Recommendation-logic changes.
- Strategy deployment.
- Any betting advice or prediction guarantee.

---

## 12. Post-Task Validation

| Check | Result |
|---|---|
| DB total replay rows | 94,924 (unchanged) |
| BIG_LOTTO rows | 24,140 (unchanged) |
| DAILY_539 rows | 34,680 (unchanged) |
| POWER_LOTTO rows | 36,104 (unchanged) |
| bet_index nulls | 0 (unchanged) |
| duplicate replay keys | 0 (unchanged) |
| PRAGMA integrity_check | `ok` (unchanged) |
| drift guard | PASS (unchanged) |
| staged files | 0 |
| New files written | `.md` and `.json` under `outputs/research/` only |
| Existing files modified | None |

---

## Required Completion Check

1. **是否真的完成:** YES — all 12 design scope items covered.
2. **測試結果:** Phase 0 PASS; drift guard PASS; DB baseline PASS; full pytest NOT RUN (plan-only task).
3. **仍卡住的唯一問題:** Straight-play is blocked (re-ingestion required). Box-play statistical power is low (~4,000 draws vs ~10,000 needed). Both are known limitations documented here.
4. **修改檔案清單:**
   - `outputs/research/p227a_star_box_play_dryrun_adapter_design_20260603.md` (new, local-only)
   - `outputs/research/p227a_star_box_play_dryrun_adapter_design_20260603.json` (new, local-only)
5. **staged / commit / push 狀態:** 0 / 0 / 0 — local-only untracked artifacts only.
6. **是否允許進入下一輪:** YES — P227B requires separate code-change + test + artifact authorization.
7. **Final Classification:** `P227A_STAR_BOX_PLAY_ADAPTER_DESIGN_READY` + `P227A_STAR_STRAIGHT_PLAY_BLOCKED_REINGEST_REQUIRED`
