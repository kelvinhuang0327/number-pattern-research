# P272B — Prospective OOS Detectability & Apply Go/No-Go Power Brief

- **Task ID:** `P272B_PROSPECTIVE_OOS_DETECTABILITY_POWER`
- **Artifact date:** 2026-06-14
- **Branch:** `task/p272b-prospective-oos-detectability-power` (base main `8b62b358aef3e9fce8962054c166e80c1944d00c`)
- **Decision classification:** `POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED`
- **Project classification:** `P271L_PREFLIGHT_COMPLETE_NOT_READY_FOR_APPLY`
- **Production apply:** `NOT_READY_FOR_APPLY`

> **Power feasibility is NOT evidence of a predictive edge.** This brief quantifies the future-draw sample size required to detect a historically observed M3+ excess at the pre-registered alpha/power; it makes no claim that such an edge exists. Every effect scenario failed multiplicity correction in P267C (0/36).

## Pre-registered contract
- Lotteries: DAILY_539, BIG_LOTTO, POWER_LOTTO
- Primary endpoint: P265A-compatible draw-level M3+ any-bet (hit_count>=3; special_hit excluded; denominator=distinct target_draw)
- Primary bet count: 1
- Test: exact one-sided (upper) binomial — `EXACT_BINOMIAL` (log-gamma PMF + forward-recurrence tail summation; not a normal/Poisson approximation)
- Power targets: [0.8, 0.9]
- Family alpha: 0.05; correction: Bonferroni m=3 -> per-test corrected alpha = 0.01666667; uncorrected = 0.05
- BH-FDR: descriptive_only; seed: 42 (no stochastic component)
- Calendar horizons (years): [1, 3, 5, 10]

## Decisive inputs (per lottery)

| Lottery | pool/pick | p0 (exact 1-bet M3+) | committed P267C | match | effect δ (pp) | p1 | draws/week | draws/year |
|---|---|---|---|---|---|---|---|---|
| DAILY_539 | 39/5 | 0.01004069 | 0.010041 | True | 1.32 | 0.02324069 | 6 | 313.0714 |
| BIG_LOTTO | 49/6 | 0.01863755 | 0.018638 | True | 1.23 | 0.03093755 | 2 | 104.3571 |
| POWER_LOTTO | 38/6 | 0.03869806 | 0.038698 | True | 1.48 | 0.05349806 | 2 | 104.3571 |

## Minimum prospective sample size N* (exact one-sided binomial)

Corrected alpha = Bonferroni m=3 (per-test); N* = smallest future-draw count whose exact power >= target.

| Lottery | alpha | power target | N* (draws) | k* | actual size | power@N* | normal-approx N | calendar years |
|---|---|---|---|---|---|---|---|---|
| DAILY_539 | 0.01666667 | 0.8 | 778 | 15 | 0.01383517 | 0.800279 | 660 | 2.485 |
| DAILY_539 | 0.01666667 | 0.9 | 1013 | 18 | 0.01610692 | 0.900484 | 943 | 3.236 |
| DAILY_539 | 0.05 | 0.8 | 537 | 10 | 0.04748218 | 0.800198 | 486 | 1.715 |
| DAILY_539 | 0.05 | 0.9 | 763 | 13 | 0.04796726 | 0.90074 | 732 | 2.437 |
| BIG_LOTTO | 0.01666667 | 0.8 | 1355 | 37 | 0.01579651 | 0.800665 | 1243 | 12.984 |
| BIG_LOTTO | 0.01666667 | 0.9 | 1805 | 47 | 0.01605209 | 0.900589 | 1718 | 17.296 |
| BIG_LOTTO | 0.05 | 0.8 | 973 | 26 | 0.0462711 | 0.800851 | 896 | 9.324 |
| BIG_LOTTO | 0.05 | 0.9 | 1343 | 34 | 0.04880817 | 0.900798 | 1306 | 12.869 |
| POWER_LOTTO | 0.01666667 | 0.8 | 1728 | 85 | 0.01644095 | 0.800955 | 1643 | 16.559 |
| POWER_LOTTO | 0.01666667 | 0.9 | 2304 | 110 | 0.01619076 | 0.900303 | 2230 | 22.078 |
| POWER_LOTTO | 0.05 | 0.8 | 1218 | 59 | 0.0493493 | 0.80039 | 1172 | 11.671 |
| POWER_LOTTO | 0.05 | 0.9 | 1707 | 80 | 0.0489744 | 0.900159 | 1675 | 16.357 |

## Calendar-horizon detectability (corrected alpha)

| Lottery | power target | N* (draws) | years required | within 1y | within 3y | within 5y | within 10y |
|---|---|---|---|---|---|---|---|
| DAILY_539 | 0.8 | 778 | 2.485 | False | True | True | True |
| DAILY_539 | 0.9 | 1013 | 3.236 | False | False | True | True |
| BIG_LOTTO | 0.8 | 1355 | 12.984 | False | False | False | False |
| BIG_LOTTO | 0.9 | 1805 | 17.296 | False | False | False | False |
| POWER_LOTTO | 0.8 | 1728 | 16.559 | False | False | False | False |
| POWER_LOTTO | 0.9 | 2304 | 22.078 | False | False | False | False |

## Governed-horizon search
- Result: `NO_GOVERNED_ACCEPTABLE_HORIZON_OR_THRESHOLD_FOUND`
- Searched: 00-Plan/, docs/, outputs/research/
- Governed horizon (years): None

Because no committed governed acceptable horizon or deployable threshold exists, neither GO nor NO_GO is selectable. **Decision: `POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED`.**

## Evidence manifest (decisive inputs)

| Input | Source | SHA-256 | Field | Value | Status |
|---|---|---|---|---|---|
| lottery_pool_and_pick | `lottery_api/CLAUDE.md` | `7124d1d519c464d4…` | header line '大樂透 (1-49選6) \| 威力彩 (1-38選6)' + DAILY_539 5/39 convention | DAILY_539=5/39, BIG_LOTTO=6/49, POWER_LOTTO=6/38 first zone (+1/8 second zone) | CONFIRMED |
| p265a_m3plus_endpoint_definition | `outputs/research/p265a_d3_m3_real_replay_success_rate_20260610.md` | `6c9d8af89381ddfc…` | draw_success_rule / success_metric | draw-level any-bet hit_count>=3; special_hit excluded; denominator=distinct target_draw | CONFIRMED |
| p0_one_bet_null_DAILY_539 | `outputs/research/p267c_m3plus_strategy_revalidation_20260610.json` | `3769596df51f6eaa…` | one_bet_baseline_sanity.DAILY_539.exact | 0.010041 | CONFIRMED |
| p0_one_bet_null_BIG_LOTTO | `outputs/research/p267c_m3plus_strategy_revalidation_20260610.json` | `3769596df51f6eaa…` | one_bet_baseline_sanity.BIG_LOTTO.exact | 0.018638 | CONFIRMED |
| p0_one_bet_null_POWER_LOTTO | `outputs/research/p267c_m3plus_strategy_revalidation_20260610.json` | `3769596df51f6eaa…` | one_bet_baseline_sanity.POWER_LOTTO.exact | 0.038698 | CONFIRMED |
| effect_scenario_observed_excess_DAILY_539 | `outputs/research/p270b_outcome_blind_portfolio_geometry_power_audit_20260611.json` | `37808a0166d22113…` | mde_summary.DAILY_539.p267c_best_uncorrected_excess_pp | 1.32 | CONFIRMED |
| effect_scenario_observed_excess_BIG_LOTTO | `outputs/research/p270b_outcome_blind_portfolio_geometry_power_audit_20260611.json` | `37808a0166d22113…` | mde_summary.BIG_LOTTO.p267c_best_uncorrected_excess_pp | 1.23 | CONFIRMED |
| effect_scenario_observed_excess_POWER_LOTTO | `outputs/research/p270b_outcome_blind_portfolio_geometry_power_audit_20260611.json` | `37808a0166d22113…` | mde_summary.POWER_LOTTO.p267c_best_uncorrected_excess_pp | 1.48 | CONFIRMED |
| p270b_mde_power_findings | `outputs/research/p270b_outcome_blind_portfolio_geometry_power_audit_20260611.json` | `37808a0166d22113…` | mde_summary.{lottery}.{n,alpha,power,z_alpha_2,z_beta,mde_increment_pp_*} | n=1000, alpha=0.0167, power=0.80, z_alpha_2=2.3934, z_beta=0.8416 (two-proportion portfolio MDE) | CONFIRMED |
| draw_cadence | `outputs/research/p268d1_draw_order_full_history_artifact_backfill_20260610.jsonl` | `f4accb6f527694e7…` | draw_date (per record, all 5 games, 2007..2026) | DAILY_539 6/wk (Mon-Sat), BIG_LOTTO 2/wk (Tue,Fri), POWER_LOTTO 2/wk (Mon,Thu) | CONFIRMED |
| governed_acceptable_horizon | `00-Plan/, docs/, outputs/research/ (bounded search)` | `—` | n/a | NO_GOVERNED_ACCEPTABLE_HORIZON_OR_THRESHOLD_FOUND | CONFIRMED_ABSENT |
| family_alpha_and_correction | `locked_contract (this artifact) + P270B alpha=0.0167 cross-check` | `—` | family_alpha / Bonferroni m | family alpha=0.05; Bonferroni m=3 -> per-test 0.016667 (P270B used rounded 0.0167) | CONFIRMED |

## Statistical & calendar limitations
- POWER FEASIBILITY IS NOT EVIDENCE OF A PREDICTIVE EDGE. This brief only answers 'how many future draws to detect an effect of magnitude delta'; it makes no claim that such an effect exists.
- Effect scenarios are the committed P267C best uncorrected per-lottery observed excesses (DAILY_539 +1.32pp / BIG_LOTTO +1.23pp / POWER_LOTTO +1.48pp). NONE survived Bonferroni or BH-FDR in P267C (0/36 cells); they are upper-plausible scenario magnitudes, not established edges.
- Bet-count nuance: p0 is the exact 1-bet M3+ hypergeometric baseline and the locked contract fixes primary_bet_count=1, but the committed observed excesses were measured at the draw-level any-bet endpoint on multi-bet cells (5/3/4 bets). The excess is applied here as a candidate prospective 1-bet effect magnitude; a true prospective 1-bet stream may exhibit a different effect size.
- The test is exact one-sided upper binomial (detecting excess). P267C/P270B used two-sided framing; a one-sided test needs no more N than two-sided at the same per-test alpha, so these N* are not inflated by sidedness.
- Draw cadence is derived from the modal weekday set over calendar year 2025 in the committed P268D1 draw_date field (DAILY_539 6/wk, BIG_LOTTO 2/wk, POWER_LOTTO 2/wk). Sporadic BIG_LOTTO add-on draws and rare DAILY_539 Sunday make-ups are excluded from the regular accrual rate; empirical full-history rates (5.80 / 2.11 / 2.00 per week) and CY2025 counts (316 / 118 / 104) bound the sensitivity.
- No committed governed acceptable detection horizon or deployable threshold exists; therefore neither GO nor NO_GO is selectable and the decision is POWER_QUANTIFIED_THRESHOLD_NOT_GOVERNED.
- Prospective detection further assumes a stable data-generating process over the multi-year accrual window and i.i.d. draw-level outcomes; regime drift or non-stationarity would invalidate the simple binomial model.

## Tests actually run
- Focused: `./venv/bin/python -m pytest tests/test_p272b_prospective_oos_detectability_power.py -q` → **61 passed**
- Regression P267C: **19 passed**
- Regression P270B: **12 passed**
- Regression P271L (preflight): **50 passed**
- Regression P271L (readonly schema): **72 passed**
- Full repository suite: **NOT_RUN**
- git diff --check: **PASS**; static forbidden-interface scan: **PASS**
- JSON parse: **PASS**; deterministic regeneration: **PASS**; MD/JSON consistency: **PASS**

## Governance assertions
- production_apply_authorized = False
- controlled_apply_started = False
- P271M_started = False
- P271N_started = False
- prediction_success_claim = False
- db_opened = False; db_write = False; registry_write = False

_Success classification: `P272B_PROSPECTIVE_OOS_DETECTABILITY_POWER_COMPLETE`._
