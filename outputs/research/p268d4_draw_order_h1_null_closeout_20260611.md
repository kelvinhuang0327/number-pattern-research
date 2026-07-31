# P268D-4: Draw-Order H1 NULL Closeout & Next-Frontier Pointer

Generated: 2026-06-11

## Boundary

This is a **closeout/governance artifact only**. P268D-4 performs no new statistical
computation, does not execute
`analysis/p268d3_h1_draw_order_confirmatory_permutation_test.py`, does not write to
`lottery_api/data/hypothesis_registry.jsonl`, and does not open any database
connection. All numeric results below are read directly from the already-merged
P268D-3 artifacts (PR #411, merged into `main` at `b3f1d4d`).

- P268D-3 source artifacts:
  - `outputs/research/p268d3_h1_draw_order_confirmatory_permutation_test_20260611.json`
  - `outputs/research/p268d3_h1_draw_order_confirmatory_permutation_test_20260611.md`
- P268D-3 script executed in this task: **NO**
- Hypothesis Registry write in this task: **NO**
- DB write in this task: **NO**

## P268D-3 Result Summary

- Registry entry `HR-P268D3-H1-DRAW-ORDER-EXIT-RANK-001`, status
  `PRE_REGISTERED_BEFORE_TEST`, registered before any H1 computation, append-only
  single entry.
- Data source: P268D-1 full-history `drawNumberAppear` JSONL artifact only (no DB
  connection of any kind).
- Method: within-draw permutation null, n_permutations=10,000, seed=42, 70%
  estimation / 30% holdout chronological split per `lottery_type`, 2026-04/05
  excluded, holdout sealed/not opened.

### Primary Result — DAILY_539

| Field | Value |
|---|---|
| n_estimation_draws | 4,076 |
| Observed statistic T_obs | 43.1695 |
| One-sided p-value | 0.3051 |
| alpha (pre-registered) | 0.01 |
| Classification | **H1_PRIMARY_FAIL** |

### Secondary / Exploratory Results

| Game | p-value | T_obs |
|---|---:|---:|
| BIG_LOTTO | 0.7057 | 43.0864 |
| POWER_LOTTO | 0.9854 | 21.6482 |
| 3_STAR | 0.3213 | 10.3164 |
| 4_STAR | 0.6838 | 6.4838 |

- H2/H3 run: **NO**
- DB write: **NO**
- Strategy generated: **NO**
- Hit-rate / success-rate improvement claim: **NO**

## Closeout Conclusion

**Draw-order line classification: DIAGNOSTICS-ONLY NULL CLOSURE.**

Per-ball mean exit-rank heterogeneity in the official `drawNumberAppear`
(draw-order) field was **NOT detected** for the primary game DAILY_539 in the
chronological estimation window (n=4,076 draws): the observed statistic
T_obs=43.1695 falls well within the within-draw-permutation null distribution
(one-sided **p=0.3051**), far above the pre-registered **alpha=0.01** threshold.
Classification: **H1_PRIMARY_FAIL**.

The four secondary/exploratory games — BIG_LOTTO (p=0.7057), POWER_LOTTO
(p=0.9854), 3_STAR (p=0.3213), and 4_STAR (p=0.6838) — were computed as
SECONDARY_EXPLORATORY ONLY, per the P268D-1 registry-freeze design. None approach
significance, and per the pre-registered pass/fail rules, secondary-game results
**cannot alone promote H1 to PASS**, change the H1 classification, or justify
proceeding to H2/H3 or any strategy.

### H1_holdout status

**SEALED_NOT_OPENED.** Because the primary DAILY_539 estimation-window criterion
FAILED (p=0.3051 >= alpha=0.01), the H1_PASS condition (estimation pass AND
holdout remains sealed for H2/H3 gating) was never met. The 30% holdout window for
all 5 games remains unopened and unused.

### H2/H3 authorization: **NOT AUTHORIZED**

H2 (earliness score → holdout inclusion frequency) and H3 (split-half stability)
were both gated on H1 (and H1_holdout) PASS per the P268D-1 registry-freeze
design. H1 PRIMARY_FAIL means this gate was never satisfied. **H2/H3 are NOT
authorized for the draw-order (`drawNumberAppear`) line and MUST NOT be run as a
continuation of P268D1-D3.**

### Strategy authorization: **NOT AUTHORIZED**

No strategy, betting recommendation, or number selection may be derived from the
draw-order (`drawNumberAppear`) exit-rank line. H1 — the foundational hypothesis
for this entire research line — failed at the pre-registered primary game and
significance level.

### Explicit Booleans

- No DB write: **true**
- No registry write: **true**
- No strategy: **true**
- No hit-rate / success-rate improvement claim: **true**
- No betting recommendation: **true**

## Next-Frontier Pointer

### Do NOT continue

- Draw-order (`drawNumberAppear`) H2 (earliness score / holdout inclusion frequency)
- Draw-order (`drawNumberAppear`) H3 (split-half stability)
- Any draw-order-derived strategy or number-selection method
- Re-running `analysis/p268d3_h1_draw_order_confirmatory_permutation_test.py`
  against the same H1 hypothesis (would not change the FAIL outcome and is
  non-idempotent w.r.t. the registry)

### Recommendation

Future success-rate research should shift to a **NEW external signal family**
distinct from the draw-order/exit-rank line closed by P268D1-P268D4 (e.g., a
different external field or data source not yet scouted), rather than reusing or
re-parameterizing this failed H1 hypothesis. Per L137/L91/L90 and related closed
lines, repeated re-testing of an already-FAIL'd hypothesis family without a
genuinely new signal source is expected to reproduce noise-level results and is
not a productive use of research budget.

### Open items

The P268D-1 full-history `drawNumberAppear` JSONL artifact (21,682 records,
2007-01..2026-05, all 5 games) remains available as a read-only data asset for any
**FUTURE, separately pre-registered hypothesis** that is not the H1
exit-rank-heterogeneity hypothesis closed here (e.g., a structurally different
statistic on the same field). Any such future hypothesis requires its own
Hypothesis Registry pre-registration and its own P221F gates; it is **NOT** a
continuation of H1/H2/H3 as designed in P268C/P268D1.

## P268D-3 PR Status

- PR #411: **MERGED** (merge commit `b3f1d4d`)

## Tests Run In This Task

- `./venv/bin/python -m pytest tests/test_p268d4_draw_order_h1_null_closeout.py -q`
- `git diff --check`

## Browser Check

NOT RUN

## Final Classification

`P268D4_DRAW_ORDER_H1_NULL_CLOSEOUT_COMPLETE`
