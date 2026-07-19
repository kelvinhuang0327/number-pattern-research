# P20T Remaining 16 Strategy Recovery — Final Report

P20T processed the exact 16 P20S backlog identities and left no generic engineering backlog. Twelve identities completed the standard strategy-preserving 20-ticket historical backtest and four identities received conclusive evidence-backed exclusions.

This is historical research for entertainment purposes only, not betting or investment advice. Historical rates do not imply future predictive advantage.

## Exact target set

`acb_hot_fourier_3bet_biglotto`, `apriori_3bet_biglotto`, `bet2_fourier_expansion_biglotto@rejected_json_historical`, `biglotto_10bet_combined`, `biglotto_5bet_orthogonal`, `biglotto_ts3_acb_4bet`, `biglotto_ts3_markov_freq_5bet`, `biglotto_zonal_pruning`, `cluster_pivot_biglotto`, `gap_dynamic_threshold_biglotto`, `hot_gap_return_biglotto`, `hot_stop_rebound_biglotto`, `markov_repeat_exception_biglotto`, `multiwindow_fourier_biglotto`, `neighbor_injection_biglotto`, `predict_biglotto_regime`

## Recovery answers

1. **Processed:** 16 identities (12 prior missing implementations, 4 prior partial backtests).
2. **Recovered and completed:** 12.
3. **Partial to complete:** 3.
4. **Historical sources recovered:** 4 identities use exact logic recovered from commit `28940a2572c051c6ba8b2ab6a077f706e800477d`.
5. **Documentation-only implementations:** 0. No strategy was invented from an incomplete document.
6. **New terminal resolutions:** 4.
7. **Exclusion evidence:**
- `bet2_fourier_expansion_biglotto@rejected_json_historical` → `INSUFFICIENT_ALGORITHM_SPECIFICATION`: rejected/bet2_fourier_expansion_biglotto.json defines rank7-14 and a 2:2:2 zone filter but not the complete ranking, combination, fallback, or tie-breaking procedure; the current P42 implementation is a proven distinct lineage
- `biglotto_zonal_pruning` → `OTHER_EVIDENCED_TERMINAL_EXCLUSION`: the exact committed zonal_pruned_predict can return 1-3 bets when pruning retains a non-empty short list; canonical cutoff 103000046 returned 3 against the governed 4-bet contract, and no committed backfill rule exists
- `hot_gap_return_biglotto` → `INSUFFICIENT_ALGORITHM_SPECIFICATION`: rejected/hot_gap_return_biglotto.json defines a candidate signal only; it leaves the base portfolio, candidate insertion, fallback, and ticket construction unspecified
- `multiwindow_fourier_biglotto` → `MISSING_IMPLEMENTATION_CONFIRMED`: all-ref history contains the rejected result artifact but no executable multi-window implementation; the artifact omits window weights, score fusion, and tie-breaking
8. **Final completed count:** 30.
9. **Final terminal-exclusion count:** 9.
10. **Engineering backlog:** 0.
11. **Credible paired advantages over random:** 0 (none).
12. **Overall conclusion:** unchanged; the historical comparison does not establish a future predictive advantage.
13. **Aliases/equivalents:** the prior P20S alias/equivalence rows remain non-independent; P20T found no new alias after parity testing the 16 targets.
14. **P20S reuse:** the 18 prior completed metrics were reused because all seven hash/constructor/dataset/database/shared-semantics gates passed (`True`). P20T ran full history only for the 12 recovered identities and reran the fixed random baseline needed for paired comparisons.

## Verification

- P20T validation status: `PASS`.
- Historical draws: 2125; common window: 2025.
- Every successful recovered portfolio contains exactly 20 unique legal tickets.
- Target/future mutation leakage preflights, timeout orchestration, independent metric recomputation, 39-row accounting, and canonical DB/status invariance passed.
- Large draw-level checkpoint files remain outside the committed evidence bundle.

Of the 39 governed Big Lotto strategy identities, `30` completed the standard 20-ticket historical backtest and `9` reached conclusive terminal exclusions; the remaining engineering backlog is `0`.
