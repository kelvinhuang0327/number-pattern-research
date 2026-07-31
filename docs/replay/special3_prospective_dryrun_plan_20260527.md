# P99 Special3 Prospective Dry-run Plan

**Phase**: P99  
**Date**: 20260527  
**Classification**: `P99_SPECIAL3_PROSPECTIVE_DRYRUN_PLAN_READY`  
**DB writes**: false  
**Replay rows changed**: 0  
**truth_level**: `SPECIAL3_PROSPECTIVE_DRYRUN`  
**target_draw**: `NEXT_AFTER_CURRENT_MAX`  
**evaluation_status**: `PENDING_ACTUAL_DRAW`  

---

## 1. P98 Input Evidence

| Item | Value |
|------|-------|
| P98 classification | `P98_SPECIAL3_OOS_PERMUTATION_REVIEW_READY` |
| 3_STAR draws loaded | 4,115 |
| History end draw | 115000024 (2026-01-28) |
| Strategies reviewed | 5 PROVISIONAL + 1 REJECT |
| DB writes | false |
| Replay rows | 54,462 (unchanged) |
| Source artifact | `outputs/replay/special3_oos_permutation_review_20260527.json` |

### P99 Candidates (from P98)

| Strategy | P98 OOS Edge @Top20 | Cohen's h | p-value | P98 Decision |
|----------|--------------------|-----------|---------|----|
| position_frequency_topk | +0.1546 | 0.5783 | <1e-15 | ADVANCE_TO_P99_CANDIDATE |
| sum_band_frequency | +0.1546 | 0.5783 | <1e-15 | ADVANCE_TO_P99_CANDIDATE |
| recent_position_hot_topk | +0.1476 | 0.5599 | <1e-15 | ADVANCE_TO_P99_CANDIDATE |
| ensemble_rank_v1 | +0.1258 | 0.4997 | <1e-15 | ADVANCE_TO_P99_CANDIDATE |
| span_band_frequency | +0.1079 | 0.4477 | <1e-15 | ADVANCE_TO_P99_CANDIDATE |

### Excluded from P99

| Strategy | Reason |
|----------|--------|
| position_cold_rebound_topk | REJECT_CONFIRMED (P97 avg_edge=−0.0449, never met threshold) |

### Ensemble v2

| Member | Role |
|--------|------|
| position_frequency_topk | Historical digit-position frequency |
| recent_position_hot_topk | Recency-weighted (last-50 draws) |
| sum_band_frequency | Digit-sum band signal |
| span_band_frequency | Digit-span band signal |

**Recommendation**: `PROCEED_TO_P99_DRY_RUN`  
**Fusion**: Reciprocal Rank Fusion (RRF, k=60), equal weights

---

## 2. Prospective Dry-run Protocol

### Draw Eligibility Rules

1. Lottery type must be `3_STAR` only
2. Target draw must have draw ID > `history_end_draw` (115000024) — **strict no-lookahead**
3. Draw must be officially published before evaluation begins
4. Evaluation only after winning number is confirmed and immutable

### No-Lookahead Rule

All predictions are generated using only draws with `CAST(draw AS INTEGER) ≤ CAST(history_end_draw AS INTEGER)`. The target draw is strictly excluded from all training data.

### Leading-Zero Serialization Rule

All ticket numbers are serialized as exactly 3 decimal characters with leading zeros:

| Ticket tuple | Serialized |
|-------------|-----------|
| (0, 0, 1) | `"001"` |
| (0, 5, 9) | `"059"` |
| (1, 2, 3) | `"123"` |
| (9, 9, 9) | `"999"` |

- Ticket range: `"000"` to `"999"` (1,000 possible tickets)
- Winning ticket serialization: same rule — draw `[0, 5, 9]` → `"059"`

### Top-N Variants

| Variant | Tickets | Coverage |
|---------|---------|----------|
| top10 | 10 | 1.0% |
| top20 | 20 | 2.0% |
| top50 | 50 | 5.0% |
| top100 | 100 | 10.0% |

### Prediction Cadence

`ONCE_PER_DRAW_CYCLE` — one prediction set per draw cycle, generated just before the draw. No rolling re-generation until a new draw is ingested.

### Output Schema (per prediction record)

| Field | Description |
|-------|-------------|
| `generated_at` | ISO8601 UTC timestamp of prediction generation |
| `history_end_draw` | Draw ID of last training draw (115000024) |
| `target_draw` | Draw ID to predict — `NEXT_AFTER_CURRENT_MAX` until known |
| `strategy_id` | Strategy identifier |
| `top_n` | Number of tickets in prediction set |
| `predicted_numbers` | List of top_n ticket tuples `[[d0,d1,d2], ...]` |
| `serialized_predictions` | Zero-padded strings `["059", "049", ...]` |
| `dry_run_only` | `true` (always) |
| `truth_level` | `SPECIAL3_PROSPECTIVE_DRYRUN` |
| `source_artifact` | Path to P98 evidence JSON |
| `evaluation_status` | `PENDING_ACTUAL_DRAW` → `EVALUATED` after result |
| `hit_result` | `null` → `HIT` or `MISS` after draw |

### Output Directory

`outputs/replay/`

---

## 3. Prospective Prediction Preview

**Training draws**: 4,115 (all available history)  
**History end**: draw 115000024 (2026-01-28, winning: [0,5,9] = "059")  
**Target draw**: NEXT_AFTER_CURRENT_MAX  

### Top20 Prediction Preview (first 5 tickets)

| Strategy | Top20 First 5 Tickets |
|----------|----------------------|
| position_frequency_topk | 059, 049, 069, 039, 058 |
| recent_position_hot_topk | (recency-weighted) |
| sum_band_frequency | (sum-band filtered) |
| span_band_frequency | (span-band filtered) |
| ensemble_rank_v1 | (5-member RRF) |
| ensemble_rank_v2 | (4-member RRF, no REJECT) |

Total predictions generated: **24** (6 strategies × 4 top_n variants)

---

## 4. Evaluation Method (when actual draw arrives)

1. Ingest new draw into `draws` table (human task — no script writes)
2. Fetch winning digits from DB for the confirmed target draw
3. Serialize winning ticket as 3-digit zero-padded string (same rule as predictions)
4. For each strategy × top_n: check if serialized winner is in `serialized_predictions`
5. Record `hit_result = HIT` or `MISS` per strategy per top_n
6. Update `evaluation_status = EVALUATED`
7. **No DB writes during evaluation** — update JSON artifact only
8. After 10+ evaluated draws: compute prospective hit rate, p-value, Sharpe Ratio

---

## 5. P100 Readiness Gate

Status: **NOT_YET_ELIGIBLE** (0 prospective draws evaluated; minimum 10 required)

| Criterion | Threshold | Current |
|-----------|-----------|---------|
| Prospective draws evaluated | ≥ 10 | 0 |
| Hit rate at top20 | > 15% | PENDING |
| p-value on prospective set | < 0.05 | PENDING |
| ensemble_v2 edge at top20 | > 0 | PENDING |
| Rolling 3-draw hit rate std | stable | PENDING |
| Sharpe Ratio | > 0 | PENDING |

---

## 6. Special4 (4_STAR) Status

| Item | Status |
|------|--------|
| 4_STAR DB rows | 0 |
| 4_STAR backtest | NOT RUN |
| Ingestion plan | Exists (P97 artifact) |
| Min rows for baseline | 1,000 |
| Status | **DATA_GAP_BLOCKING** |

No change from P98. 4_STAR remains blocked.

---

## 7. Governance Verification

| Guard | Status |
|-------|--------|
| DB writes | false |
| Replay rows changed | 0 |
| replay_rows total (before) | 54,462 |
| replay_rows total (after) | 54,462 |
| POWER_LOTTO max_draw | 115000041 (unchanged) |
| 4_STAR backtest | NOT RUN |
| Special3 production promotion | NOT DONE |
| Staged DB/backup/runtime files | NONE |
| Branch | `p99-special3-prospective-dryrun-planning` |

---

## 8. Next Steps (P100)

1. **Ingest new draws**: When 3_STAR draws after 115000024 are officially published, ingest them (human task)
2. **Evaluate predictions**: Run evaluation method (Section 4) on first 10 new draws
3. **Sharpe Ratio calculation**: Required before any strategy receives `VALIDATED` label
4. **P100 gate check**: After 10+ evaluated draws, re-run P100 readiness criteria
5. **ensemble_v2 promotion decision**: Only after P100 gate passes with p < 0.05 prospectively
6. **4_STAR ingestion**: Human task — confirm source authority and ingest ≥1,000 rows before any 4_STAR analysis

---

## 9. Phase Chain Summary

| Phase | Output | Commit |
|-------|--------|--------|
| P96 | Governance Baseline Repair | `15a0943` |
| P97 | Special3/Special4 Dry-Run Closure | `f447221` |
| P98 | Special3 OOS + Permutation Review | `8d695e1` |
| **P99** | **Special3 Prospective Dry-run Plan** | *(this PR)* |
