# P282B — BIG 6/49 Deduplicated Portfolio Replay & Diversified-Random Falsification

- **Final classification:** `P282B_BIG649_DEDUP_REPLAY_PR_OPEN_NULL_NO_PUBLICATION`
- **Deterministic digest:** `3fd3904548357472ffffac6018202e93451d3b3353e328a6a199f3f5ee8df50a`
- **Source main SHA:** `8b62b358aef3e9fce8962054c166e80c1944d00c`
- **Branch:** `task/p282b-big649-deduplicated-portfolio-replay`

**Research only — not a betting recommendation. No prediction-success claim, promotion, activation, or publication.**

## Primary question
Does deduplicating deterministic strategy tickets reduce duplicate exposure and improve draw-level prize-aware coverage/success vs the appropriate random baselines, without leakage?

## Headline answer
- **Duplicate exposure:** the raw deterministic portfolio has an overall duplicate rate of **0.3080** (7331 of 23804 tickets); 1500/1531 draws carry >=1 duplicate. Deduplication removes all of it (D duplicate rate 0).
- **Dedup vs raw success (D vs C):** success rates are identical by construction (LONG: D=0.2740, C=0.2740); dedup saves on average 4.886 tickets/draw without changing coverage.
- **Dedup vs random (D vs A, budget-matched, LONG):** D success 0.2740 vs random 0.2901 (diff -0.0161, MC p=0.9235, normal-approx p=0.9215, fixed_below_random).

## Target draw universe
- Deterministic source: `strategy_prediction_replays` (BIG_LOTTO, all PREDICTED).
- Outcome source: `draws_big_lotto_canonical_main`.
- Replay distinct target draws: 1552; canonical view draws: 2117.
- **Eligible draws: 1531** (excluded 21 non-canonical: `NON_CANONICAL_OUTCOME_UNRESOLVABLE (target_draw not in draws_big_lotto_canonical_main)`).

## Groups
- **A_INDEPENDENT_RANDOM** — B_d i.i.d. uniform 6/49 tickets; natural duplicates/overlap allowed
- **B_DIVERSIFIED_RANDOM** — B_d random tickets with pairwise main-overlap <= 2; rejection sampling (<= 4000 attempts/ticket); UNDERFILLED rather than relaxing the constraint
- **C_RAW_DETERMINISTIC_PORTFOLIO** — frozen per-draw strategy replay tickets, as stored (no outcome-based re-rank or selection)
- **D_DEDUPLICATED_DETERMINISTIC_PORTFOLIO** — Group C with exact-duplicate canonical ticket contents removed; no replacement; reduced-budget draws marked UNDERFILLED

Budget rule: every group requested the same per-draw budget B_d (the raw deterministic portfolio size). Seed = 282. MC iterations = 2000.

## Group-level metrics by window
### SHORT (most-recent 100 eligible draws)

| Group | prod | uniq | dup rate | underfill rate | coverage | max ov | prize-aware win | M3+ win |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| A | 15.88 | 15.88 | 0.0000 | 0.0000 | 43.08 | 3.05 | 0.3900 (39) | 0.2800 |
| B | 15.88 | 15.88 | 0.0000 | 0.0000 | 43.73 | 2.00 | 0.4300 (43) | 0.2400 |
| C | 15.88 | 10.78 | 0.3212 | 0.0000 | 35.24 | 5.98 | 0.2400 (24) | 0.1400 |
| D | 10.78 | 10.78 | 0.0000 | 0.9900 | 35.24 | 4.70 | 0.2400 (24) | 0.1400 |

### MID (most-recent 500 eligible draws)

| Group | prod | uniq | dup rate | underfill rate | coverage | max ov | prize-aware win | M3+ win |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| A | 15.98 | 15.98 | 0.0000 | 0.0000 | 42.95 | 3.02 | 0.3400 (170) | 0.2140 |
| B | 15.98 | 15.98 | 0.0000 | 0.0000 | 43.92 | 2.00 | 0.4200 (210) | 0.2660 |
| C | 15.98 | 11.05 | 0.3085 | 0.0000 | 35.16 | 6.00 | 0.2920 (146) | 0.2060 |
| D | 11.05 | 11.05 | 0.0000 | 0.9980 | 35.16 | 4.66 | 0.2920 (146) | 0.2060 |

### LONG (most-recent 1500 eligible draws)

| Group | prod | uniq | dup rate | underfill rate | coverage | max ov | prize-aware win | M3+ win |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| A | 15.83 | 15.83 | 0.0000 | 0.0000 | 42.59 | 3.00 | 0.3707 (556) | 0.2360 |
| B | 15.83 | 15.83 | 0.0000 | 0.0000 | 43.50 | 1.99 | 0.4007 (601) | 0.2613 |
| C | 15.83 | 10.94 | 0.3087 | 0.0000 | 34.83 | 6.00 | 0.2740 (411) | 0.1833 |
| D | 10.94 | 10.94 | 0.0000 | 0.9993 | 34.83 | 4.58 | 0.2740 (411) | 0.1833 |

### ALL (most-recent 1531 eligible draws)

| Group | prod | uniq | dup rate | underfill rate | coverage | max ov | prize-aware win | M3+ win |
|---|--:|--:|--:|--:|--:|--:|--:|--:|
| A | 15.55 | 15.55 | 0.0000 | 0.0000 | 41.97 | 2.96 | 0.3638 (557) | 0.2319 |
| B | 15.55 | 15.55 | 0.0000 | 0.0000 | 42.86 | 1.97 | 0.3926 (601) | 0.2560 |
| C | 15.55 | 10.76 | 0.3080 | 0.0000 | 34.35 | 5.90 | 0.2704 (414) | 0.1809 |
| D | 10.76 | 10.76 | 0.0000 | 0.9798 | 34.35 | 4.50 | 0.2704 (414) | 0.1809 |

## Primary comparison — D (dedup) vs A (independent random), budget-matched

paired same-draw observations; D fixed (U_d unique deterministic tickets) vs A budget-matched at U_d i.i.d. random; seed-fixed Bernoulli Monte Carlo over EXACT per-draw success probabilities, with a normal-approximation cross-check (using the exact Poisson-binomial mean/std); one-sided test for D above the random baseline

| Window | D rate | random rate | diff | MC p (D>rand) | normal-approx p | direction |
|---|--:|--:|--:|--:|--:|---|
| SHORT | 0.2400 | 0.2872 | -0.0472 | 0.8706 | 0.8525 | fixed_below_random |
| MID | 0.2920 | 0.2933 | -0.0013 | 0.5522 | 0.5265 | fixed_below_random |
| LONG | 0.2740 | 0.2901 | -0.0161 | 0.9235 | 0.9215 | fixed_below_random |
| ALL | 0.2704 | 0.2854 | -0.0150 | 0.9170 | 0.9111 | fixed_below_random |

## Secondary comparisons
### D vs B (diversified random, matched)
| Window | fixed rate | random rate | diff | MC p | direction |
|---|--:|--:|--:|--:|---|
| SHORT | 0.2400 | 0.2904 | -0.0504 | 0.9015 | fixed_below_random |
| MID | 0.2920 | 0.2974 | -0.0054 | 0.6212 | fixed_below_random |
| LONG | 0.2740 | 0.2950 | -0.0210 | 0.9665 | fixed_below_random |
| ALL | 0.2704 | 0.2903 | -0.0199 | 0.9590 | fixed_below_random |

### C vs A (full budget)
| Window | fixed rate | random rate | diff | MC p | direction |
|---|--:|--:|--:|--:|---|
| SHORT | 0.2400 | 0.3930 | -0.1530 | 1.0000 | fixed_below_random |
| MID | 0.2920 | 0.3951 | -0.1031 | 1.0000 | fixed_below_random |
| LONG | 0.2740 | 0.3917 | -0.1177 | 1.0000 | fixed_below_random |
| ALL | 0.2704 | 0.3850 | -0.1146 | 1.0000 | fixed_below_random |

### C vs B (full budget)
| Window | fixed rate | random rate | diff | MC p | direction |
|---|--:|--:|--:|--:|---|
| SHORT | 0.2400 | 0.3976 | -0.1576 | 1.0000 | fixed_below_random |
| MID | 0.2920 | 0.4008 | -0.1088 | 1.0000 | fixed_below_random |
| LONG | 0.2740 | 0.3986 | -0.1246 | 1.0000 | fixed_below_random |
| ALL | 0.2704 | 0.3917 | -0.1213 | 1.0000 | fixed_below_random |

### D vs C (dedup vs raw; descriptive)
| Window | D rate | C rate | identical | budget saved/draw |
|---|--:|--:|:-:|--:|
| SHORT | 0.2400 | 0.2400 | yes | 5.100 |
| MID | 0.2920 | 0.2920 | yes | 4.928 |
| LONG | 0.2740 | 0.2740 | yes | 4.886 |
| ALL | 0.2704 | 0.2704 | yes | 4.788 |

## Anti-leakage evidence
- Deterministic rows checked: 23804; causality violations (cutoff>=target): 0; null cutoffs: 0.
- Random construction reads outcomes: False; dedup reads outcomes: False; ticket replacements: 0; live/future tickets emitted: False.

## Statistical method & limitations
- Retrospective replay over historical draws; NOT prospective / out-of-sample.
- Deduplication cannot raise draw-level success vs the raw portfolio (D's winning set equals C's); any gain is budget/duplicate-exposure only.
- Diversified-random success probability is estimated (resampling), not closed-form; D-vs-B / C-vs-B are secondary.
- Source prize-tier mapping is MANUAL_VERIFICATION_REQUIRED (P271B/C).
- 21 replay target_draws excluded as non-canonical (no canonical outcome).

## Recommendation
No edge: deduplication reduces duplicate exposure / wasted budget but does not beat the matched random baseline. Treat dedup as a budget-efficiency control only; HOLD per maintenance mode (L90/L91). No further mining without a new external data source or explicit authorization.

## Safety flags
- `db_opened` = True
- `db_queried` = True
- `db_copied` = False
- `db_written` = False
- `no_prediction_success_claim` = True
- `no_strategy_promoted` = True
- `no_activation` = True
- `no_real_publication` = True
- `no_official_target_or_deadline_lookup` = True
- `no_pre_draw_manifest` = True
- `no_db_write_or_copy` = True
- `current_or_future_live_tickets_output` = False
