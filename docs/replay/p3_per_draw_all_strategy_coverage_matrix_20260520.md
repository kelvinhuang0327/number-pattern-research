# P3 Per-Draw All-Strategy Coverage Matrix — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Generated**: 2026-05-20  
**Script**: `scripts/p3_per_draw_all_strategy_coverage_matrix.py`  
**Safety**: zero DB writes · zero replay rows generated · zero strategy execution

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Active draw universe | **209 draws** |
| Registry strategies | **18** |
| Total matrix cells | **1,288** |
| ROW_BACKED (real data) | **300** (23.3%) |
| RECONSTRUCTIBLE (P7 ready) | **121** (9.4%) |
| NO_DATA | **867** (67.3%) |
| ARTIFACT_ONLY | 41 strategies (not in per-draw matrix) |
| Real replay successes | **300** |
| **Fake successes** | **0** ← invariant |
| Production rows | **460** (unchanged) |

---

## Active Draw Universe (209 draws)

| Lottery Type | Draw Range | Source | Draws |
|-------------|-----------|--------|-------|
| BIG_LOTTO | 99000056–99000105 | Existing replay rows | 50 |
| BIG_LOTTO | 115000025–115000044 | P7 ONLINE plan | 16 |
| POWER_LOTTO | 99000055–99000104 | Existing replay rows | 50 |
| POWER_LOTTO | 115000016–115000030 | P7 ONLINE plan | 12 |
| DAILY_539 | 99000212–99000261 | Existing replay rows | 50 |
| DAILY_539 | 115000049–115000084 | P7 RETIRED plan | 31 |
| **Total** | | | **209** |

---

## Visibility State Coverage

### ROW_BACKED (300 cells — 23.3%)

Real rows exist in `strategy_prediction_replays`. `should_count_as_success=True`.

| Lottery | Strategy | Draws | Rows |
|---------|----------|-------|------|
| BIG_LOTTO | biglotto_triple_strike | 50 (99000056–105) | 50 |
| BIG_LOTTO | biglotto_deviation_2bet | 50 (99000056–105) | 50 |
| POWER_LOTTO | power_precision_3bet | 50 (99000055–104) | 50 |
| POWER_LOTTO | power_orthogonal_5bet | 50 (99000055–104) | 50 |
| DAILY_539 | daily539_f4cold | 50 (99000212–261) | 50 |
| DAILY_539 | daily539_markov_cold | 50 (99000212–261) | 50 |
| **Total** | | | **300** |

*Note: The remaining 160 replay rows (460 total − 300 in matrix) are for draws outside
the current active draw universe window.*

### RECONSTRUCTIBLE (121 cells — 9.4%)

`prediction_items` data exists in DB. Replay rows can be inserted via P7 apply
without re-running strategy logic. `should_count_as_success=False` (pending apply).

| Lottery | Strategy | Lifecycle | Draws | P7 Status |
|---------|----------|-----------|-------|-----------|
| BIG_LOTTO | ts3_regime_3bet | ONLINE | 16 | PLAN_INSERT |
| POWER_LOTTO | fourier_rhythm_3bet | ONLINE | 12 | PLAN_INSERT |
| DAILY_539 | acb_1bet | RETIRED | 31 | PLAN_MANUAL_REVIEW |
| DAILY_539 | acb_markov_midfreq_3bet | RETIRED | 31 | PLAN_MANUAL_REVIEW |
| DAILY_539 | midfreq_acb_2bet | RETIRED | 31 | PLAN_MANUAL_REVIEW |
| **Total** | | | **121** | |

### NO_DATA (867 cells — 67.3%)

In registry for the lottery type, no replay rows, no prediction_items in DB.
`should_count_as_success=False`.

Major contributors:
- BIG_LOTTO strategies applied to 99000xxx draws (pre-P7 draws): ts3_regime_3bet (50), biglotto_ts3_acb_4bet (50+16), biglotto_ts3_markov_freq_5bet (50+16)
- POWER_LOTTO: fourier_rhythm_3bet (50), power_shlc_midfreq (62), h6_gate_mk20_ew85 (62)
- DAILY_539: all 8 strategies applied to 115000xxx draws except 3 RECONSTRUCTIBLE ones

### ARTIFACT_ONLY (41 strategies — excluded from per-draw matrix)

Not in runtime registry. No lottery_type affiliation. Cannot be included in per-draw matrix.
Tracked separately in P2 full-catalog visibility plan.

---

## Display Status Mapping

| Display Status | Count | When |
|---------------|-------|------|
| SHOW_REPLAY_RESULT | 300 | ROW_BACKED — actual result available |
| SHOW_RECONSTRUCTIBLE_PENDING | 121 | RECONSTRUCTIBLE — P7 apply not yet done |
| SHOW_NO_DATA | 867 | NO_DATA — no source in DB |
| SHOW_ARTIFACT_ONLY | 0 | ARTIFACT_ONLY — not in per-draw matrix |

---

## Coverage by Lottery Type

| Lottery | Total Cells | ROW_BACKED | RECON | NO_DATA |
|---------|------------|------------|-------|---------|
| BIG_LOTTO | 330 | 100 (30.3%) | 16 (4.8%) | 214 (64.8%) |
| POWER_LOTTO | 310 | 100 (32.3%) | 12 (3.9%) | 198 (63.9%) |
| DAILY_539 | 648 | 100 (15.4%) | 93 (14.4%) | 455 (70.2%) |

---

## Critical Invariants

| Invariant | Value | Status |
|-----------|-------|--------|
| `fake_success_count` | **0** | ✅ PASS |
| `should_count_as_success=True` only for ROW_BACKED | verified | ✅ PASS |
| NO_DATA never counted as success | verified | ✅ PASS |
| ARTIFACT_ONLY never counted as success | verified | ✅ PASS |
| RECONSTRUCTIBLE (pending) never counted as success | verified | ✅ PASS |
| Production rows | **460** | ✅ PASS |

---

## Product Coverage Gap Analysis

The 67.3% NO_DATA rate is structural, not a data quality issue:

1. **Strategy × draw mismatch**: Most strategies don't have predictions for the legacy
   99000xxx draws (they were added to the registry later). This is expected.

2. **RETIRED/REJECTED strategies on new draws**: biglotto_ts3_acb_4bet,
   biglotto_ts3_markov_freq_5bet, power_shlc_midfreq, p1_deviation_2bet_539 were
   rejected before any live predictions were recorded.

3. **P7 pending**: 121 RECONSTRUCTIBLE cells will move to ROW_BACKED after P7 apply.
   Post-P7 ROW_BACKED coverage: 300+121 = 421 cells (32.7% of 1,288).

4. **h6_gate_mk20_ew85 (OBSERVATION)**: Shadow evaluation only; no predictions produced.

---

## Outputs

- **Matrix JSON**: `outputs/replay/p3_per_draw_all_strategy_coverage_matrix_20260520.json`
  (1,288 entries with full per-cell visibility detail)
- **Summary JSON**: `outputs/replay/p3_per_draw_all_strategy_coverage_summary_20260520.json`
  (coverage metrics, pcts, safety flags)
- **Tests**: `tests/test_p3_per_draw_all_strategy_coverage_matrix.py` — 32/32 PASS

---

## Safety Confirmation

- ✅ **Zero DB writes** — DB opened with `PRAGMA query_only = ON`
- ✅ **Zero replay rows generated** — no INSERT SQL exists in script
- ✅ **Zero strategy execution** — no predict_func or generate_numbers calls
- ✅ **Zero draw imports** — all draw data read from existing draws table
- ✅ **fake_success_count = 0** — invariant enforced and tested
- ✅ **Production rows = 460** — unchanged throughout
