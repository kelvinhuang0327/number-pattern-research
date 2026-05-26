# P82 Replay Freshness / Source Gap Guard

**Date**: 2026-05-26  
**Branch**: `p82-replay-freshness-guard`  
**Final Classification**: `P82_REPLAY_FRESHNESS_GUARD_PASS`  
**Type**: Read-only guard — no DB writes, no ingestion, no replay row apply

---

## Phase 1 — Existing Freshness Endpoint

`GET /api/replay/freshness` (lottery_api/routes/replay.py line 815)

| Field | Value |
|-------|-------|
| total_rows | 46962 |
| coverage_mode | UNKNOWN |
| POWER_LOTTO latest run_id | 9 |
| POWER_LOTTO run status | DONE |
| POWER_LOTTO run finished_at | 2026-05-23T09:44:36Z |

**Endpoint semantics**: Tracks `strategy_replay_runs` run IDs and timestamps, not draw-level coverage. It does **not** detect gaps between the latest draw in the `draws` table and strategy-level replay row coverage. The P82 guard script fills this gap.

---

## Phase 2 — P82 Guard Script

**Script**: `scripts/p82_replay_freshness_guard.py` — read-only.

### Design

The guard distinguishes between two strategy categories:

- **Batch A strategies** (`fourier_rhythm_3bet`, `fourier30_markov30_2bet`): expected to have a draw-ext row for the latest draw (P79 Batch A plan).
- **Historical-only strategies** (7 others): have batch backfill rows only; their max draw lagging behind latest is **expected and not a gap**.

### POWER_LOTTO Results

| Metric | Value |
|--------|-------|
| latest_draw | 115000041 |
| latest_draw_date | 2026/05/21 |
| replay_rows_total | 46962 |
| strategies_checked | 9 |
| Batch A covered | fourier_rhythm_3bet, fourier30_markov30_2bet |
| Batch A gap | (none) |
| draw_gap_detected | False |
| replay_gap_detected | False |
| batch_a_coverage_pct | 100.0% |

**Classification**: `FRESHNESS_PASS`

### Strategy Coverage Detail

| Strategy | max_draw | Category | Expected gap? |
|----------|----------|----------|---------------|
| fourier_rhythm_3bet | 115000041 | Batch A | N/A — covered |
| fourier30_markov30_2bet | 115000041 | Batch A | N/A — covered |
| power_orthogonal_5bet | 115000040 | Historical | YES — expected |
| power_precision_3bet | 115000040 | Historical | YES — expected |
| cold_complement_2bet | 115000040 | Historical | YES — expected |
| midfreq_fourier_2bet | 115000040 | Historical | YES — expected |
| midfreq_fourier_mk_3bet | 115000040 | Historical | YES — expected |
| pp3_freqort_4bet | 115000040 | Historical | YES — expected |
| zonal_entropy_2bet | 115000040 | Historical | YES — expected |

---

## Classification Logic

| Condition | Classification |
|-----------|---------------|
| No strategy has latest draw | `FRESHNESS_DRAW_GAP_CRITICAL` |
| Batch A strategy missing latest draw | `FRESHNESS_BATCH_A_GAP_WARNING` |
| All Batch A strategies covered | `FRESHNESS_PASS` |

---

## DB State

- `total_replay_rows`: 46962 (unchanged — no writes)
- POWER_LOTTO max draw: 115000041

---

## Summary

P82 guard confirms Batch A coverage is complete (100%) for POWER_LOTTO draw 115000041. The 7 historical-only strategies correctly lag at 115000040. No draw gap, no Batch A replay gap. Classification: `FRESHNESS_PASS`.
