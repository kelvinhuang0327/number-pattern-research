# P545B R2 — Full 50/300/750 Per-Draw Evaluator

> Retrospective research reconciliation only. This is not a betting recommendation or future-performance claim.

## Result

- Frozen cells: **36**
- Independently evaluated opportunities: **27,000**
- Reconciled windows: **108/108 PASS**
- Committed retrospective classification reproduced: `PRIZE_AWARE_EDGE_CORRECTION_SURVIVING`
- Output classification: `P545B_R2_RETROSPECTIVE_EVALUATION_RECONCILED_NO_BETTING_RECOMMENDATION`

## Sole row-level evidence input

- Path: `outputs/research/p545c_r4_strategy_draw_opportunity_registry_20260711.json`
- Bytes: **52,393,107**
- SHA-256: `ea0a712fa5ba702c51271b5664fc95e5cac2feec5967ead3bd7d01cfcd7bc5d8`
- Semantic projection digest: `f2c28075a3b7020629a0c6bd41504609031ff84532a672dde4f26f0485434b39`
- Canonical payload digest: `34bbee9b9a3cd275025db282486f8bdd3dd5c14834813061acefce220ae0ed84`

## Statistical contract

- Primary windows: `50 / 300 / 750`; fixed Bonferroni family `m=108`.
- Exact distinct-ticket without-replacement null; exact binomial or Poisson-binomial tails.
- Wilson and Clopper-Pearson 95% intervals; BH-FDR remains descriptive only.
- P544C amended BIG_LOTTO special-hit scoring is recomputed per eligible attempt.

## Safety and limitations

- SQLite opened: **NO**
- Strategy combination or parameter search: **NO**
- Betting recommendation, ROI, or EV output: **NO**
- Upstream artifacts modified: **NO**

Canonical payload digest: `46c6f3bd3bc4c98582d77436395172acd5a56bc92bc2bb0c1b61b9c6f6612c46`
