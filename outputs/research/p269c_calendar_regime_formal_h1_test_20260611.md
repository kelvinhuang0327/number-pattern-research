# P269C: Calendar Regime Formal H1 Test

**Date:** 2026-06-11 Asia/Taipei
**Classification:** `P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_PRIMARY_FAIL`
**Task Type:** Type D (Hypothesis Registry append + pre-registered statistical test)
**H1 verdict:** `H1_PRIMARY_FAIL`

**No-Claim Statement:** This artifact does not improve win rate, does not predict
lottery numbers, does not authorize betting advice, and does not constitute a
strategy recommendation.

---

## 0. Inherited Boundaries

- **P268 draw-order:** ALREADY_NULL — H2/H3 stay closed, not reopened.
- **P269A-Lite:** top recommendation NO_GO; C05/C06 = LOW-plausibility WATCHLIST only.
- **P269B:** READY_FOR_REGISTRY design (PR #414 merged). This task executes that design verbatim.
- **Low plausibility warning:** expected result was null (L82). Single-shot test —
  a null permanently closes C05/C06.

## 1. Pre-Registration (before any outcome look)

- Registry entry: `HR-P269C-H1-DAILY539-SATURDAY-M3PLUS-001` (EXISTS_IDENTICAL_SKIPPED)
- Status: `PRE_REGISTERED_BEFORE_TEST`, registered_at `2026-06-11T13:04:25.847732`
- Artifact computed_at `2026-06-11T13:05:05.838713` (registry append strictly first)
- Strategy: `acb_markov_midfreq_3bet` — P269B coverage rule; 15-way tie at 1,494 in-OOS
  draws broken by the P269B pre-named recommended primary candidate.

## 2. Method

- C05 only: DAILY_539 Saturday vs Mon-Fri, M3+ (P265A SSOT, special_hit excluded)
- Two-tailed permutation test, T=10,000, seed=42, alpha=0.01
- Endpoint: temporal OOS last 1,765 eligible draws
  (109000253..115000141);
  evaluable = OOS ∩ replay coverage = 1,494 draws
  (Sat 249, Mon-Fri 1245)
- C06 secondary: **NOT_RUN**. No weekday/threshold/lottery scans.

## 3. Result

| Quantity | Value |
|---|---|
| Saturday draws (evaluable) | 249 |
| Mon-Fri draws (evaluable) | 1245 |
| Saturday M3+ events | 8 |
| Mon-Fri M3+ events | 44 |
| Saturday M3+ rate | 3.2129% |
| Mon-Fri M3+ rate | 3.5341% |
| Rate diff (Sat − Mon-Fri) | -0.3213% |
| Permutations | 10,000 (seed=42) |
| Permuted \|stat\| ≥ observed | 8,526 |
| **p-value (two-tailed)** | **0.8526** |
| Alpha | 0.01 |
| Fisher backup | not triggered (events >= 5) |

## 4. Classification

**`H1_PRIMARY_FAIL`** → final classification **`P269C_CALENDAR_REGIME_FORMAL_H1_COMPLETE_PRIMARY_FAIL`**

Gate (pre-registered): PASS_POSITIVE iff p < 0.01 AND Saturday rate > Mon-Fri rate;
SIGNIFICANT_NEGATIVE iff p < 0.01 with Saturday < Mon-Fri; FAIL otherwise.

## 5. Recommended Next Task

P269D closeout / diagnostics-only NULL

## 6. Governance

- DB write: NO (read-only URI mode)
- Hypothesis Registry: append-only, one entry, before computation
- C06: NOT_RUN · scans: NONE · strategy: NONE · picks: NONE
- No hit-rate improvement claim. Not betting advice.
