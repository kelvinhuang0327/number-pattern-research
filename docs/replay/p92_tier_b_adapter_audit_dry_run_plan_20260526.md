# P92 — Tier B Adapter Audit + Dry-run Plan
**Date:** 2026-05-26
**Classification:** P92_TIER_B_ADAPTER_AUDIT_DRY_RUN_PLAN_READY
**Status:** EVIDENCE_ONLY — No DB writes, no row inserts, no lifecycle changes, no dry-run execution

## Context
P91 identified 9 Tier B RSM current strategy candidates for P92 adapter audit.
P92 answer: Which strategies have working adapters and are eligible for dry-run replay expansion?

RSM bootstrap covers two lottery types (POWER_LOTTO: `get_power_lotto_strategies_inline()`,
BIG_LOTTO: `get_big_lotto_strategies_inline()`). DAILY_539 f4cold_3bet and f4cold_5bet are
tracked in the RSM rolling monitor state (`data/rolling_monitor_DAILY_539.json`) but NOT
defined in `tools/rsm_bootstrap.py`. Their prediction code exists in
`tools/predict_539_5bet_f4cold.py`.

**NAMING COLLISION NOTE:** `fourier_rhythm_2bet` appears as an RSM name in BOTH POWER_LOTTO
(bound to `tools/power_fourier_rhythm.py`) and BIG_LOTTO (bound to
`tools/predict_biglotto_triple_strike.py`). These are treated as two separate audit entries (#5 and #6).

## Baseline
- Production rows: 46962
- POWER_LOTTO max draw: 115000041 (2026/05/21)
- DB writes: false | Replay row changes: 0
- P82 guard: FRESHNESS_PASS
- P86 guard: SOURCE_UNAVAILABLE (existing artifact, no new draw since last snapshot)

## Adapter Audit Results

| # | RSM Name | Lottery | Adapter Status | Blocker | DB Rows | Eligible for Dry-run |
|---|----------|---------|----------------|---------|---------|----------------------|
| 1 | f4cold_3bet | DAILY_539 | adapter-ready | none | 0 | Yes |
| 2 | f4cold_5bet | DAILY_539 | adapter-ready | none | 0 | Yes |
| 3 | deviation_complement_2bet | BIG_LOTTO | blocked-already-covered | biglotto_deviation_2bet in DB (1570 rows) | 1570 | No (already covered) |
| 4 | echo_aware_3bet | BIG_LOTTO | adapter-ready | none | 0 | Yes |
| 5 | fourier_rhythm_2bet | POWER_LOTTO | adapter-ready | none | 0 | Yes |
| 6 | fourier_rhythm_2bet | BIG_LOTTO | adapter-partial | needs replay wrapper; fourier_rhythm_bet() + cold_numbers_bet() composite in rsm_bootstrap but no replay adapter class exists | 0 | Conditional (P94+) |
| 7 | triple_strike_3bet | BIG_LOTTO | blocked-already-covered | biglotto_triple_strike in DB (1570 rows) | 1570 | No (already covered) |
| 8 | ts3_markov_4bet_w30 | BIG_LOTTO | adapter-ready | none | 0 | Yes |
| 9 | ts3_markov_freq_5bet_w30 | BIG_LOTTO | blocked-rejected | SUPERSEDED (lottery_api/CLAUDE.md line 511, 534-536); artifact at rejected/ts3_markov_freq_5bet_biglotto.json | 0 | No |
| 10 | orthogonal_5bet | POWER_LOTTO | blocked-already-covered | power_orthogonal_5bet in DB (1570 rows) | 1570 | No (already covered) |

**Notes on f4cold_3bet / f4cold_5bet (entries #1 and #2):**
- The existing `daily539_f4cold` adapter (1590 rows) calls `predict_539_5bet_f4cold.predict()`
  but stores only the first bet via `_extract_first_bet()` — 1 bet per draw row.
- `f4cold_3bet` RSM strategy uses the same predict() function but returns 3 bets per draw.
- `f4cold_5bet` RSM strategy returns all 5 bets per draw.
- These are genuinely different strategies (3-bet and 5-bet) with distinct strategy_ids.
- No replay rows exist under strategy_id `f4cold_3bet` or `f4cold_5bet`.
- RSM rolling monitor confirms 300 records each: f4cold_3bet (3 bets/draw), f4cold_5bet (5 bets/draw).

**Notes on fourier_rhythm_2bet BIG_LOTTO (entry #6):**
- RSM calls `fourier_rhythm_bet(history, window=500)` (returns 1 bet) + `cold_numbers_bet(history, window=100, exclude=set(bet1))` (returns 1 bet) as a composite 2-bet.
- These are sub-functions from `tools/predict_biglotto_triple_strike.py`, not a standalone predict function.
- No replay adapter class wrapping this composite exists in `lottery_api/models/replay_strategy_registry.py`.
- Classified adapter-partial: wrapper needs to be written before replay rows can be generated.

## Summary by Status
| Status | Count |
|--------|-------|
| adapter-ready | 5 (f4cold_3bet, f4cold_5bet, echo_aware_3bet, fourier_rhythm_2bet POWER, ts3_markov_4bet_w30) |
| adapter-partial | 1 (fourier_rhythm_2bet BIG_LOTTO) |
| blocked-already-covered | 3 (deviation_complement_2bet, triple_strike_3bet, orthogonal_5bet) |
| blocked-rejected | 1 (ts3_markov_freq_5bet_w30) |

**Total audit entries: 10** (9 RSM target strategies + 1 naming collision split)

## Adapter Function Details

### #1 f4cold_3bet — DAILY_539 (adapter-ready)
- **File:** `tools/predict_539_5bet_f4cold.py`
- **Function:** `predict(hist)` — returns list of 5 bets; take first 3 for f4cold_3bet
- **Inputs:** sorted draws list (ASC by date/draw)
- **Window requirement:** 500p Fourier + 100p cold
- **Min history:** 100 draws
- **Special numbers:** none (DAILY_539 has no special ball)
- **Proposed strategy_id:** `daily539_f4cold_3bet`

### #2 f4cold_5bet — DAILY_539 (adapter-ready)
- **File:** `tools/predict_539_5bet_f4cold.py`
- **Function:** `predict(hist)` — returns all 5 bets directly
- **Inputs:** sorted draws list (ASC by date/draw)
- **Window requirement:** 500p Fourier + 100p cold
- **Min history:** 100 draws
- **Special numbers:** none
- **Proposed strategy_id:** `daily539_f4cold_5bet`

### #4 echo_aware_3bet — BIG_LOTTO (adapter-ready)
- **File:** `tools/predict_biglotto_echo_3bet.py`
- **Function:** `echo_aware_mixed_3bet(history)` — returns list of 3 bets (6 numbers each)
- **Inputs:** sorted draws list
- **Special numbers:** BIG_LOTTO has special ball; check adapter for special handling
- **Proposed strategy_id:** `biglotto_echo_aware_3bet`

### #5 fourier_rhythm_2bet — POWER_LOTTO (adapter-ready)
- **File:** `tools/power_fourier_rhythm.py`
- **Function:** `fourier_rhythm_predict(history, n_bets=2, window=500)` — returns list of 2 bets
- **Inputs:** sorted draws list, n_bets=2
- **Special numbers:** POWER_LOTTO has special ball (1-8); tool may not generate special prediction
- **Proposed strategy_id:** `power_fourier_rhythm_2bet`

### #8 ts3_markov_4bet_w30 — BIG_LOTTO (adapter-ready)
- **File:** `tools/backtest_biglotto_5bet_ts3markov.py`
- **Function:** `generate_ts3_markov_4bet(history, markov_window=30)` — returns list of 4 bets
- **Inputs:** sorted draws list, markov_window=30
- **Special numbers:** BIG_LOTTO has special ball
- **Proposed strategy_id:** `biglotto_ts3_markov_4bet_w30`

## Dry-run Plan (P93 scope)

For each adapter-ready strategy:

### P93 Target 1: f4cold_3bet (DAILY_539)
- `strategy_id`: daily539_f4cold_3bet
- `lottery_type`: DAILY_539
- `adapter_function`: `tools/predict_539_5bet_f4cold.predict()[:3]`
- `expected rows at 1500 periods`: 1500
- `truth_level recommendation`: DAILY539_F4COLD_3BET_DRY_RUN_VERIFIED
- `controlled_apply_id pattern`: P93_DAILY539_F4COLD_3BET_1500_DRY_RUN_20260526
- `duplicate guard`: (strategy_id, target_draw) UNIQUE — enforced by DB constraint
- `rollback`: DELETE WHERE controlled_apply_id = 'P93_DAILY539_F4COLD_3BET_1500_DRY_RUN_20260526'
- `special number handling`: N/A (DAILY_539 has no special ball)
- `blocker`: None

### P93 Target 2: f4cold_5bet (DAILY_539)
- `strategy_id`: daily539_f4cold_5bet
- `lottery_type`: DAILY_539
- `adapter_function`: `tools/predict_539_5bet_f4cold.predict()` (all 5 bets)
- `expected rows at 1500 periods`: 1500
- `truth_level recommendation`: DAILY539_F4COLD_5BET_DRY_RUN_VERIFIED
- `controlled_apply_id pattern`: P93_DAILY539_F4COLD_5BET_1500_DRY_RUN_20260526
- `duplicate guard`: (strategy_id, target_draw) UNIQUE — enforced by DB constraint
- `rollback`: DELETE WHERE controlled_apply_id = 'P93_DAILY539_F4COLD_5BET_1500_DRY_RUN_20260526'
- `special number handling`: N/A
- `blocker`: None

### P93 Target 3: echo_aware_3bet (BIG_LOTTO)
- `strategy_id`: biglotto_echo_aware_3bet
- `lottery_type`: BIG_LOTTO
- `adapter_function`: `tools/predict_biglotto_echo_3bet.echo_aware_mixed_3bet(history)`
- `expected rows at 1500 periods`: 1500
- `truth_level recommendation`: BIGLOTTO_ECHO_AWARE_3BET_DRY_RUN_VERIFIED
- `controlled_apply_id pattern`: P93_BIGLOTTO_ECHO_AWARE_3BET_1500_DRY_RUN_20260526
- `duplicate guard`: (strategy_id, target_draw) UNIQUE — enforced by DB constraint
- `rollback`: DELETE WHERE controlled_apply_id = 'P93_BIGLOTTO_ECHO_AWARE_3BET_1500_DRY_RUN_20260526'
- `special number handling`: BIG_LOTTO has special ball — verify echo_aware_mixed_3bet returns main numbers only; predicted_special=NULL
- `blocker`: Confirm function returns list of bets (each 6-number list), not single flat list

### P93 Target 4: fourier_rhythm_2bet (POWER_LOTTO)
- `strategy_id`: power_fourier_rhythm_2bet
- `lottery_type`: POWER_LOTTO
- `adapter_function`: `tools/power_fourier_rhythm.fourier_rhythm_predict(history, n_bets=2, window=500)`
- `expected rows at 1500 periods`: 1500
- `truth_level recommendation`: POWER_FOURIER_RHYTHM_2BET_DRY_RUN_VERIFIED
- `controlled_apply_id pattern`: P93_POWER_FOURIER_RHYTHM_2BET_1500_DRY_RUN_20260526
- `duplicate guard`: (strategy_id, target_draw) UNIQUE — enforced by DB constraint
- `rollback`: DELETE WHERE controlled_apply_id = 'P93_POWER_FOURIER_RHYTHM_2BET_1500_DRY_RUN_20260526'
- `special number handling`: POWER_LOTTO special ball 1-8; predicted_special=NULL unless adapter generates it
- `blocker`: None

### P93 Target 5: ts3_markov_4bet_w30 (BIG_LOTTO)
- `strategy_id`: biglotto_ts3_markov_4bet_w30
- `lottery_type`: BIG_LOTTO
- `adapter_function`: `tools/backtest_biglotto_5bet_ts3markov.generate_ts3_markov_4bet(history, markov_window=30)`
- `expected rows at 1500 periods`: 1500
- `truth_level recommendation`: BIGLOTTO_TS3_MARKOV_4BET_W30_DRY_RUN_VERIFIED
- `controlled_apply_id pattern`: P93_BIGLOTTO_TS3_MARKOV_4BET_W30_1500_DRY_RUN_20260526
- `duplicate guard`: (strategy_id, target_draw) UNIQUE — enforced by DB constraint
- `rollback`: DELETE WHERE controlled_apply_id = 'P93_BIGLOTTO_TS3_MARKOV_4BET_W30_1500_DRY_RUN_20260526'
- `special number handling`: BIG_LOTTO has special ball; predicted_special=NULL
- `blocker`: None

## P94+ Scope (adapter-partial)

### fourier_rhythm_2bet (BIG_LOTTO) — adapter-partial
- Requires a new replay adapter class wrapping `fourier_rhythm_bet()` + `cold_numbers_bet()` composite
- File: `tools/predict_biglotto_triple_strike.py` contains both sub-functions
- Effort estimate: ~2 hours to write wrapper + replay adapter class
- Scope: P94 or later

## Policies
- blocked-already-covered: No new rows needed. Existing rows under the canonical strategy_id
  (biglotto_deviation_2bet, biglotto_triple_strike, power_orthogonal_5bet) serve the product requirement.
- blocked-rejected: No promotion. `ts3_markov_freq_5bet_w30` is SUPERSEDED per lottery_api/CLAUDE.md
  lines 511, 534-536. Artifact retained at `rejected/ts3_markov_freq_5bet_biglotto.json`.
- adapter-partial: `fourier_rhythm_2bet` BIG_LOTTO requires replay wrapper before dry-run.
  Out of P93 scope, deferred to P94+.

## Recommended P93 Scope
**5 adapter-ready strategies × 1500 periods = 7500 new rows**

| Strategy | Lottery | strategy_id | Expected Rows |
|----------|---------|-------------|---------------|
| f4cold_3bet | DAILY_539 | daily539_f4cold_3bet | 1500 |
| f4cold_5bet | DAILY_539 | daily539_f4cold_5bet | 1500 |
| echo_aware_3bet | BIG_LOTTO | biglotto_echo_aware_3bet | 1500 |
| fourier_rhythm_2bet | POWER_LOTTO | power_fourier_rhythm_2bet | 1500 |
| ts3_markov_4bet_w30 | BIG_LOTTO | biglotto_ts3_markov_4bet_w30 | 1500 |

**Post-P93 row total:** 46962 + 7500 = **54462**

**Preconditions for P93 execution:**
1. Write ReplayStrategyAdapter subclass for each strategy in `lottery_api/models/replay_strategy_registry.py`
2. Test adapter function call with last 10 draws before full 1500-period dry-run
3. Confirm special number handling for BIG_LOTTO and POWER_LOTTO adapters
4. Branch governance guard must confirm expected-rows before and after

## Governance
- DB writes: false
- Replay row changes: 0
- Lifecycle promotions: 0
- No dry-run execution in P92
- Branch: p92-tier-b-adapter-audit-dry-run-plan
- P82 guard: FRESHNESS_PASS
- P86 guard: SOURCE_UNAVAILABLE (existing artifact)
- Branch governance guard: BRANCH_GOVERNANCE_PASS (rows=46962)
