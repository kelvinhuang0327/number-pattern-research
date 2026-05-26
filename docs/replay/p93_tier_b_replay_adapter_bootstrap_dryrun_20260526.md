# P93 — Tier B Replay Adapter Bootstrap + Temp-DB Dry-run Rehearsal

**Date:** 2026-05-26  
**Classification:** `P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETE`  
**Branch:** `p93-tier-b-replay-adapter-bootstrap-dryrun`  
**Based on:** P92 Tier B Adapter Audit (PR #217, commit be650e0)

---

## Governance Assertions

| Assertion | Value |
|-----------|-------|
| DB writes to `lottery_v2.db` | **false** |
| Replay row insert into production | **false — 0 rows** |
| Lifecycle/champion/registry mutation | **false** |
| Official API ingestion | **false** |
| dry_run flag on all temp rows | **true (dry_run=1)** |
| Causal isolation enforced | **true** |
| Duplicate guard enforced | **true** |
| Temp DB path | `/tmp/p93_tierb_dryrun_rehearsal.db` |

---

## Production DB Baseline (Unchanged)

| Metric | Before | After |
|--------|--------|-------|
| `strategy_prediction_replays` row count | 46962 | 46962 |
| POWER_LOTTO max draw | 115000041 | 115000041 |
| P93 strategies in production | 0 | 0 |

---

## Adapter Table

| Strategy ID | RSM Source | Lottery | Adapter File | Bets | Status |
|-------------|-----------|---------|-------------|------|--------|
| `daily539_f4cold_3bet` | `f4cold_3bet` | DAILY_539 | `lottery_api/models/p93_tierb_replay_adapters.py` | 3 | adapter-ready |
| `daily539_f4cold_5bet` | `f4cold_5bet` | DAILY_539 | `lottery_api/models/p93_tierb_replay_adapters.py` | 5 | adapter-ready |
| `biglotto_echo_aware_3bet` | `echo_aware_3bet` | BIG_LOTTO | `lottery_api/models/p93_tierb_replay_adapters.py` | 3 | adapter-ready |
| `power_fourier_rhythm_2bet` | `fourier_rhythm_2bet` (POWER_LOTTO) | POWER_LOTTO | `lottery_api/models/p93_tierb_replay_adapters.py` | 2 | adapter-ready |
| `biglotto_ts3_markov_4bet_w30` | `ts3_markov_4bet_w30` | BIG_LOTTO | `lottery_api/models/p93_tierb_replay_adapters.py` | 4 | adapter-ready |

**Source functions:**

| Strategy ID | Source Function |
|-------------|----------------|
| `daily539_f4cold_3bet` | `tools/predict_539_5bet_f4cold.py::predict(hist)[:3]` |
| `daily539_f4cold_5bet` | `tools/predict_539_5bet_f4cold.py::predict(hist)` |
| `biglotto_echo_aware_3bet` | `tools/predict_biglotto_echo_3bet.py::echo_aware_mixed_3bet(history)` |
| `power_fourier_rhythm_2bet` | `tools/power_fourier_rhythm.py::fourier_rhythm_predict(history, n_bets=2, window=500)` |
| `biglotto_ts3_markov_4bet_w30` | `tools/backtest_biglotto_5bet_ts3markov.py::generate_ts3_markov_4bet(history, markov_window=30)` |

---

## Dry-run Row Counts by Strategy

| Strategy ID | Lottery | Target Window | Rows Generated | Status |
|-------------|---------|--------------|----------------|--------|
| `daily539_f4cold_3bet` | DAILY_539 | 1500 | 1500 | COMPLETE |
| `daily539_f4cold_5bet` | DAILY_539 | 1500 | 1500 | COMPLETE |
| `biglotto_echo_aware_3bet` | BIG_LOTTO | 1500 | 1500 | COMPLETE |
| `power_fourier_rhythm_2bet` | POWER_LOTTO | 1500 | 1500 | COMPLETE |
| `biglotto_ts3_markov_4bet_w30` | BIG_LOTTO | 1500 | 1500 | COMPLETE |
| **TOTAL** | | | **7500** | **COMPLETE** |

---

## Validation Results

| Check | Result |
|-------|--------|
| Causal integrity | PASS — `history = draws[:i]` strict slice |
| Duplicate guard (strategy×draw) | PASS — 0 duplicates |
| Number range validation | PASS — all ranges correct |
| BET counts | PASS — 3/5/3/2/4 as expected |
| hit_count calculation | PASS — intersection of predicted and actual |
| dry_run=1 on all temp rows | PASS — 7500/7500 |
| Production DB row count unchanged | PASS — 46962 before and after |
| POWER_LOTTO max draw unchanged | PASS — 115000041 |
| Temp DB path used | PASS — `/tmp/p93_tierb_dryrun_rehearsal.db` |

---

## Number Range Rules Applied

| Lottery | Main Numbers | Special |
|---------|-------------|---------|
| DAILY_539 | 1–39 (5 numbers) | None |
| BIG_LOTTO | 1–49 (6 numbers) | NULL in replay v0.1 |
| POWER_LOTTO | 1–38 (6 numbers) | NULL in replay v0.1 |

---

## Blockers

**None.** All 5 adapter-ready strategies from P92 completed dry-run successfully.

> Note: `biglotto_fourier_rhythm_2bet` (BIG_LOTTO) remains adapter-partial and is deferred to P94+ as documented in P92.

---

## Implementation Notes

### Adapter file scope
`lottery_api/models/p93_tierb_replay_adapters.py` contains 5 adapter classes plus a local `_P93_REGISTRY` dict. These adapters are **NOT** added to `replay_strategy_registry._REGISTRY` or `_ALL_ADAPTERS`. They are exclusively used by the dry-run rehearsal script. No lifecycle metadata is mutated.

### Multi-bet storage convention
All adapters follow the existing registry convention: **one replay row per (strategy, draw)** storing the **first bet** only. Multi-bet adapters return the full list from `get_all_bets()` for future analysis but `get_one_bet()` returns only the first bet (consistent with `_PowerFourierRhythm3BetAdapter` pattern).

### Python runtime
Source functions (`predict_539_5bet_f4cold.py`, `power_fourier_rhythm.py`, `backtest_biglotto_5bet_ts3markov.py`) require numpy/scipy. The rehearsal script must be run with `.venv/bin/python3` (Python 3.9 + numpy 2.0.2 + scipy 1.13.1).

---

## Recommended P94 Controlled Apply Scope

**Preconditions:**
1. All P93 tests PASS
2. Drift guard PASS
3. Branch governance PASS
4. `replay_rows` remains 46962 in production
5. POWER_LOTTO max draw remains 115000041
6. P93 `final_classification == P93_TIER_B_REPLAY_ADAPTER_BOOTSTRAP_DRYRUN_COMPLETE`

**P94 targets:** All 5 strategies (7500 rows total expected insert delta)

**Expected post-P94 total:** 54462 replay rows

**P94 note:** Before production insert, re-validate causal integrity and duplicate guard against the current production DB snapshot at P94 time.

---

## Artifacts Produced

| File | Purpose |
|------|---------|
| `lottery_api/models/p93_tierb_replay_adapters.py` | 5 adapter classes (dry-run only) |
| `scripts/p93_tierb_dryrun_rehearsal.py` | Temp-DB dry-run rehearsal script |
| `outputs/replay/p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.json` | Machine-readable report |
| `docs/replay/p93_tier_b_replay_adapter_bootstrap_dryrun_20260526.md` | This document |
| `tests/test_p93_tier_b_replay_adapter_bootstrap_dryrun.py` | Test suite |

---

## Final Statements

- **No production DB writes.** `lottery_api/data/lottery_v2.db` was not modified.
- **No replay row insert into `lottery_v2.db`.** All 7500 rows are in `/tmp/p93_tierb_dryrun_rehearsal.db` with `dry_run=1`.
- **No lifecycle/champion/registry mutation.** `replay_strategy_registry._REGISTRY` and `_ALL_ADAPTERS` were not modified.
- **No official API ingestion.** No external draw sources were called.
