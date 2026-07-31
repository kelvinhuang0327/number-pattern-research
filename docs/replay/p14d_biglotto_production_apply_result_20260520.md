# P14D — Big Lotto Production Apply Result

**Date:** 2026-05-20  
**Phase:** P14D_BIGLOTTO_PRODUCTION_APPLY  
**Classification:** P14D_PRODUCTION_APPLY_COMPLETE

---

## Apply Result

| Metric | Value |
|--------|-------|
| controlled_apply_id | `P14D_BIGLOTTO_TS3_1500_PROD_20260520` |
| strategy_id | `ts3_regime_3bet` |
| lottery_type | BIG_LOTTO |
| rows_before | 460 |
| inserted_count | **1500** ✓ |
| duplicate_count | 0 |
| error_count | 0 |
| rows_after_apply | **1960** ✓ |
| truth_level | `BIGLOTTO_SINGLE_STRATEGY_BACKFILL_VERIFIED` |
| source | `P14D_BIGLOTTO_PRODUCTION_APPLY` |
| production_apply | true |
| fake_success_count | 0 |

## Post-Apply Verification

| Check | Result |
|-------|--------|
| production rows = 1960 | ✓ |
| legacy rows unchanged (460) | ✓ |
| P14D rows = 1500 | ✓ |
| drift guard PASS | ✓ |
| governance guard PASS | ✓ |
| all tests PASS | ✓ |
| no DB/backup/pid staged | ✓ |

## New Canonical Baselines

| Component | Old | New |
|-----------|-----|-----|
| production rows | 460 | **1960** |
| drift guard total_count | 460 | **1960** |
| governance guard --expected-rows | 460 | **1960** |
| drift guard p14d bucket | — | **1500** |

## Rollback

```bash
python3 scripts/p14d_biglotto_production_apply.py --rollback --expected-rows 1960
# Returns production rows to 460
```

## Next Steps

- **P15**: Replay page/API integration — verify the replay list UI renders
  the 1500 `ts3_regime_3bet` BIG_LOTTO rows correctly using the production data.
- **P16**: Extend replay to the other two ONLINE BIG_LOTTO strategies
  (`biglotto_triple_strike`, `biglotto_deviation_2bet`) using the same
  P14B → P14C → P14D pipeline.
