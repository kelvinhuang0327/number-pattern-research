# P37: Wave 2 DAILY_539 Production Apply

**Date**: 2026-05-23
**Branch**: p37-wave2-daily539-production-apply
**Authorization phrase**: YES apply P37 production wave2 daily539

---

## Scope Summary

P37 applies 9000 P36-verified DAILY_539 replay rows to the production database.

- **Wave**: 2
- **Lottery type**: DAILY_539
- **Strategies**: 6 (all DRY_RUN, not ONLINE)
- **Rows per strategy**: 1500
- **Total rows inserted**: 9000
- **Production rows before**: 19960
- **Production rows after**: 28960

---

## Authorization

Authorization phrase confirmed present: `YES apply P37 production wave2 daily539`

This phrase was required for the production DB write to proceed. The apply script
validated the phrase in its header and logged it at runtime.

---

## Pre-flight Results

| Check | Result |
|-------|--------|
| Repo path | /Users/kelvin/Kelvin-WorkSpace/LotteryNew (PASS) |
| Branch | main (PASS) |
| HEAD includes P36 merge commit c4a8a4b | PASS |
| Production rows before apply | 19960 (PASS) |
| Drift guard (pre) | REPLAY_LIFECYCLE_DRIFT_GUARD_PASS |
| Branch governance guard (pre) | BRANCH_GOVERNANCE_PASS |

---

## Duplicate Check Results

| Strategy | Pre-existing rows | Result |
|----------|-------------------|--------|
| markov_1bet_539 | 0 | PASS |
| acb_single_539 | 0 | PASS |
| zone_gap_3bet_539 | 0 | PASS |
| 539_3bet_orthogonal | 0 | PASS |
| p0b_539_3bet_f_cold_fmid | 0 | PASS |
| p0c_539_3bet_f_cold_x2 | 0 | PASS |

**Duplicate check: PASS** — all Wave 2 strategies had zero pre-existing rows in production.

---

## Per-Strategy Inserted Rows

| Strategy | Inserted | Lifecycle | Errors |
|----------|----------|-----------|--------|
| markov_1bet_539 | 1500 | DRY_RUN | 0 |
| acb_single_539 | 1500 | DRY_RUN | 0 |
| zone_gap_3bet_539 | 1500 | DRY_RUN | 0 |
| 539_3bet_orthogonal | 1500 | DRY_RUN | 0 |
| p0b_539_3bet_f_cold_fmid | 1500 | DRY_RUN | 0 |
| p0c_539_3bet_f_cold_x2 | 1500 | DRY_RUN | 0 |
| **Total** | **9000** | **DRY_RUN** | **0** |

---

## Total Production Rows

| Milestone | Row Count |
|-----------|-----------|
| After P21B (DAILY_539 ONLINE strategies) | 12460 |
| After P31B (Wave 1 RETIRED strategies, +7500) | 19960 |
| After P37 (Wave 2 DRY_RUN strategies, +9000) | **28960** |

---

## Drift Guard / Branch Governance Guard Status

### Pre-apply (on main)
- Drift guard: `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`
- Governance guard: `BRANCH_GOVERNANCE_PASS — branch='main' rows=19960`

### Post-apply (on p37 branch)
- Drift guard: `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` (baseline updated to 28960)
- Governance guard: `BRANCH_GOVERNANCE_PASS — branch='p37-wave2-daily539-production-apply' rows=28960`

Drift guard baseline updated:
- `p37_apply_id`: `P37_DAILY539_WAVE2_9000_PROD_20260523`
- `p37_count`: 9000
- `total_count`: 28960 (was 19960)
- `ALLOWED_TRUTH_LEVELS` extended with `DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED`
- `known_apply_ids` extended with P37 apply ID

---

## Lifecycle Semantics Confirmation

All 9000 inserted rows maintain `lifecycle_status = DRY_RUN`.

- `dry_run = 0` (production rows — this is the DB column, not lifecycle status)
- `source = P37_WAVE2_PRODUCTION_APPLY`
- `truth_level = DAILY539_WAVE2_STRATEGY_BACKFILL_VERIFIED`
- `controlled_apply_id = P37_DAILY539_WAVE2_9000_PROD_20260523`
- **No rows were set to ONLINE**
- **No registry entries were mutated**
- **No `_REGISTRY` or `_ALL_ADAPTERS` were modified**

The strategies remain in DRY_RUN lifecycle and are available for replay analysis
but are NOT part of the live prediction pipeline.

---

## Transaction Details

- All 9000 rows were inserted inside a single `BEGIN EXCLUSIVE` transaction
- The transaction was committed atomically — all rows or none
- No partial inserts are possible; any failure would have rolled back the entire batch

---

## Adapter Source

Rows were generated using `lottery_api/models/p36_wave2_daily539_adapters.py`,
following the same algorithm as the P36 dry-run rehearsal. This ensures full
reproducibility between the rehearsal and production apply.

Each row uses a strictly causal history slice: all DAILY_539 draws strictly before
the target draw date are available to the predictor, with no data leakage.

---

## Recommended Next Phase

The 6 Wave 2 DAILY_539 strategies are now in production DB as DRY_RUN rows
and can be analyzed through the replay API and UI.

Recommended actions:

1. **Monitor Wave 2 replay performance** via the replay API at `/api/replay/`
2. **Compare Wave 2 vs Wave 1 and ONLINE strategies** using the replay coverage matrix
3. **Wave 3 planning** (BIG_LOTTO or POWER_LOTTO candidates) — reference P35 roadmap
4. **Promotion evaluation**: if any Wave 2 strategy achieves validation thresholds
   (three-window ROI > baseline, p < 0.05, Sharpe > 0), it may be considered for
   promotion to NEEDS_PROMOTION lifecycle via a future P-series PR

---

## Classification

`P37_WAVE2_DAILY539_PRODUCTION_APPLY_MERGED_TO_MAIN`
