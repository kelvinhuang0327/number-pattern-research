# P97 Special3 / Special4 Dry-Run Closure — 2026-05-27

## Classification

`P97_SPECIAL3_SPECIAL4_DRYRUN_CLOSURE_READY`

## Scope

Dry-run analysis of 三星彩 (3_STAR / Special3) strategies and ingestion readiness documentation
for 四星彩 (4_STAR / Special4).

**Governance**: READ-ONLY. Zero DB writes. Replay row count unchanged at 54,462.

## Prior Phase Context

| Phase | PR | Commit | Description |
|-------|-----|--------|-------------|
| P94 | #223 | e.g. Tier B | Tier B Controlled Apply — added 7,500 replay rows |
| P95 | #224 | 57965db | Best Strategy Overview API + UI |
| P96 | #225 | 15a0943 | Governance Baseline Repair 46962 → 54462 |
| P97 | This PR | — | Special3/4 Dry-Run Closure |

## Output Artifacts

| File | Status | Description |
|------|--------|-------------|
| `outputs/replay/special3_leading_zero_check_20260527.md` | ✅ COMPLETE | Leading-zero serialization PASS |
| `outputs/replay/special3_baseline_dryrun_20260527.json` | ✅ COMPLETE | 6 strategies × 3 windows × 4 top-N |
| `outputs/replay/special3_baseline_dryrun_20260527.md` | ✅ COMPLETE | Human-readable summary |
| `outputs/replay/special3_baseline_dryrun_20260527/` | ✅ COMPLETE | Per-strategy JSON artifacts |
| `outputs/replay/special4_ingestion_plan_20260527.md` | ✅ COMPLETE | 4_STAR ingestion plan (DATA_GAP_BLOCKING) |
| `tests/test_p97_special3_special4_dryrun_closure.py` | ✅ 10/10 PASS | Evidence suite |

## Special3 Results Summary

**Draws**: 4,115 (`lottery_type='3_STAR'`, PASS leading-zero check)

| Strategy | Classification | Avg Edge |
|----------|--------------|----------|
| `position_frequency_topk` | PROVISIONAL | +0.284 |
| `recent_position_hot_topk` | PROVISIONAL | +0.264 |
| `position_cold_rebound_topk` | **REJECT** | −0.045 |
| `sum_band_frequency` | PROVISIONAL | +0.246 |
| `span_band_frequency` | PROVISIONAL | +0.173 |
| `ensemble_rank_v1` | PROVISIONAL | +0.269 |

Random baseline (analytical): Top-10=1%, Top-20=2%, Top-50=5%, Top-100=10%

## Special4 Status

`DATA_GAP_BLOCKING` — Schema declared, 0 rows in DB.
No 4_STAR backtest until ≥1,000 rows ingested + leading-zero check PASS.

## Governance Verification

| Guard | Expected | Actual | Status |
|-------|----------|--------|--------|
| `strategy_prediction_replays` rows | 54,462 | 54,462 | ✅ |
| `POWER_LOTTO max_draw` | 115000041 | 115000041 | ✅ |
| DB writes during P97 | 0 | 0 | ✅ |
| Tests passing | 72 governance | 72/72 | ✅ |

## Next Steps (P98)

1. Walk-forward OOS + permutation test for 5 PROVISIONAL strategies
2. `ensemble_rank_v1` without `position_cold_rebound_topk` (ensemble v2)
3. Sharpe Ratio computation before VALIDATED label
4. 4_STAR data ingestion (human task — source confirmation required)
