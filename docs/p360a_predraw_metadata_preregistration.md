# P360A Pre-Registration: Future True-OOS Evaluation Protocol

Status: **PRE-REGISTERED, NOT YET EXECUTABLE** (no live-eligible data exists yet).
Frozen: 2026-07-03T14:37:22Z, alongside `lottery_api/data/predraw_strategy_freeze_registry.json`.

This document exists to close the survivorship / optional-stopping gap the
Fable5 P360A design review flagged: the evaluation protocol (candidates,
metric, baseline, minimum N, multiplicity correction) is fixed **before**
any `LIVE_PREDRAW` record exists, so a future task cannot choose a
convenient N, metric, or candidate subset after peeking at live results.

## 1. Candidates (frozen, closed set — no additions without a new dated amendment)

The same 8 strategies P356→P359 already identified as the ONLINE registry
candidates. See `lottery_api/data/predraw_strategy_freeze_registry.json` for
the authoritative list with `code_git_sha_at_freeze`.

| strategy_id | lottery_type |
|---|---|
| power_precision_3bet | POWER_LOTTO |
| power_orthogonal_5bet | POWER_LOTTO |
| fourier_rhythm_3bet | POWER_LOTTO |
| biglotto_triple_strike | BIG_LOTTO |
| biglotto_deviation_2bet | BIG_LOTTO |
| ts3_regime_3bet | BIG_LOTTO |
| daily539_f4cold | DAILY_539 |
| daily539_markov_cold | DAILY_539 |

Any code, parameter, or version change to a candidate creates a **new**
frozen identity (new `strategy_version` + new freeze-registry entry); its
OOS-eligibility clock restarts from zero. It does not inherit accumulated
live records from the prior version.

## 2. Primary metric

Per-strategy **M3+ hit rate** over its own `select_eligible_records()`
output (LIVE_PREDRAW-eligible records only — see
`lottery_api/engine/predraw_ledger.py`), reported as:

```
Edge = observed_M3+_rate − baseline_M3+_rate(n_bets)
```

using the project's own established multi-bet correction (CLAUDE.md,
`lottery_api/CLAUDE.md`):

```
baseline_M3+_rate(N) = 1 − (1 − p_single)^N
```

where `p_single` is the theoretical (not empirical) hypergeometric
probability of matching ≥3 numbers on a single bet, computed once here and
independently re-verified against the values already on record in
`lottery_api/CLAUDE.md`:

| lottery_type | pool | pick | p_single (M3+, 1 bet) | cross-check |
|---|---|---|---|---|
| BIG_LOTTO | 49 | 6 | **1.8638%** | matches CLAUDE.md's "1.86%" |
| POWER_LOTTO | 38 | 6 | **3.8698%** | matches CLAUDE.md's "3.87%" |
| DAILY_539 | 39 | 5 | **1.0041%** | newly computed here (CLAUDE.md does not list a DAILY_539 M3+ baseline); same hypergeometric formula, `P(X≥3) = Σ_{m=3}^{5} C(5,m)·C(34,5-m) / C(39,5)` |

This baseline is theoretical/closed-form, not the empirical
`BASELINE_ABSENT` from P356→P359 (which referred to the absence of a
tracked *empirical comparison baseline column* in the replay corpus, a
different concept). Using the closed-form hypergeometric baseline here
means the eligible-vs-random comparison never depends on any other
strategy's replay data.

## 3. Minimum N and checkpoint schedule

**No new, smaller N is invented for live data.** The checkpoints below
reuse exactly the project's own pre-existing three-window standard
(`CLAUDE.md`: "必須通過1500期三窗口驗證 150/500/1500") — the bar is not
lowered just because live accrual is slow. What changes is only the data
source (live-eligible only, never retrospective), not the sample-size bar.

| Checkpoint | N (live-eligible draws) | Permitted analysis | Elapsed time estimate |
|---|---|---|---|
| Floor | < 150 per lottery_type | **counts only** — `p361_dry_run_audit()` returns `status="ACCUMULATING"`; no test of any kind may be run or reported | — |
| Window 1 | 150 | preliminary permutation test PERMITTED but must be labeled preliminary/underpowered; not a promotion decision | ~5–6 months (DAILY_539) / ~17–18 months (BIG_LOTTO, POWER_LOTTO, at ~2 draws/week) |
| Window 2 | 500 | same three-window methodology as any other strategy | ~1.6 years (DAILY_539) / ~4.8 years (BIG/POWER) |
| Window 3 | 1500 | full existing validation standard applies unmodified: three-window ROI > baseline, p<0.05, permutation test, walk-forward OOS, Sharpe > 0, McNemar vs. incumbent before any replacement (L48) | ~4.9 years (DAILY_539) / ~14.4 years (BIG/POWER) |

These elapsed-time figures are a **known, accepted cost** of doing this
honestly, not a problem to engineer around. A future task must not shrink
these thresholds to get a faster answer; that would reproduce exactly the
optional-stopping failure mode this document exists to prevent.

## 4. Multiplicity correction

Corrected **within each lottery_type's own candidate family**, not across
all 8 jointly — P358 already established that cross-lottery-type
comparison is not meaningful (different pools, different baselines,
different draw cadence), so a joint correction would either be too
conservative for the 2-candidate DAILY_539 family or too lax for the
3-candidate POWER_LOTTO/BIG_LOTTO families relative to their own actual
comparison count.

| lottery_type | candidates | family size | Bonferroni-corrected α (from 0.05) |
|---|---|---|---|
| POWER_LOTTO | power_precision_3bet, power_orthogonal_5bet, fourier_rhythm_3bet | 3 | 0.0167 |
| BIG_LOTTO | biglotto_triple_strike, biglotto_deviation_2bet, ts3_regime_3bet | 3 | 0.0167 |
| DAILY_539 | daily539_f4cold, daily539_markov_cold | 2 | 0.025 |

## 5. What this pre-registration does NOT do

- It does not create, backdate, or relabel any existing replay row. The
  entire existing `strategy_prediction_replays` corpus remains permanently
  non-OOS (P359's finding stands).
- It does not claim any candidate has, or will have, edge.
- It does not shorten the accrual timeline in section 3 for convenience.
- It does not authorize any performance computation below the Window-1
  floor (N=150 per lottery_type) — `p361_dry_run_audit()` is hard-coded to
  return counts only regardless of how it is called.
