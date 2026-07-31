# P271A Prize-Aware Endpoint & Scoring Specification

**Task:** P271A  
**Branch:** `task/p271a-prize-aware-endpoint-scoring-spec`  
**Repo HEAD:** `4435a48b7c43cad5464bb4d1cd70458e421faa90`  
**Generated:** 2026-06-11T13:51:55Z  
**Mode:** `prize_aware_endpoint_scoring_spec`  
**Final Classification:** `P271A_PRIZE_AWARE_ENDPOINT_SPEC_COMPLETE`

---

## Architectural Principle: Parallel Feature, Not Replacement

> **Prize-aware scoring is a NEW PARALLEL FEATURE alongside existing M3+/replay scoring.**
> It does NOT replace, deprecate, or modify the existing M3+ endpoint or any replay infrastructure.
> Both tracks run concurrently in perpetuity. M3+ is NOT deprecated.

| Track | Endpoint | Status |
|-------|----------|--------|
| Existing (unchanged) | M3+ (`hit_count >= 3`, special_hit excluded) | **PRESERVED** — P265A SSOT, all existing tests/API contracts/pre-registered hypotheses unchanged |
| New parallel track | `ANY_PRIZE_AWARE_WIN`, `TIER_CLASS`, `Mx_PLUS_SECOND/SPECIAL` | **ADDITIVE** — read-only computed metrics, reported alongside M3+, never instead of it |

**Coexistence rule:** Any future report that includes prize-aware rates **MUST** also include the M3+ rate for the same strategy cell. Neither track is a substitute for the other.

**No migration:** There is no path from M3+ to prize-aware. Deprecating M3+ requires a separate explicit governance decision.

---

## Safety Declarations

- **No backtest was run.** No replay data was queried for strategy performance analysis.
- **No DB write happened.** The `strategy_prediction_replays` table and all other DB tables are unchanged.
- **No registry mutation happened.** `hypothesis_registry.jsonl` was not modified.
- **No strategy was generated.** No strategy code, config, or recommendation was produced.
- **No hit-rate improvement is claimed.** This document specifies future evaluation endpoints only.
- **P270C remains not authorized.** P270 cross-strategy portfolio arc is closed.
- **Prize-aware endpoints defined here are future evaluation specifications only, not betting advice.**
- **Not investment advice. Not betting recommendations. Historical research only.**

---

## 1. Executive Summary

This specification defines **prize-aware success endpoints** for the three replay-backed Taiwan lottery types: POWER_LOTTO (威力彩), BIG_LOTTO (大樂透), and DAILY_539 (今彩539).

The existing P265A SSOT M3+ endpoint (`hit_count >= 3`, special_hit excluded) is a **main-number-only diagnostic**. It does not account for:
- POWER_LOTTO prizes that include second-zone (second-area) matches at lower hit counts (捌獎: 2+second, 普獎: 1+second)
- BIG_LOTTO prizes that include special-number matches at lower hit counts (普獎: 2+special)
- DAILY_539 prizes at the 2-match level (肆獎)

**Purpose:** This spec defines the endpoint names, SQL conditions, and schema requirements needed to implement prize-aware evaluation in future research tasks (P271B onward).

**Key insight:** The existing M3+ diagnostic remains valid as a backward-compatible research metric, but prize-aware endpoints provide a more complete picture of lottery-specific prediction value.

---

## 2. Official Source URLs and Source Verification Status

| Lottery | Official URL | Machine-Readable? | Source Status |
|---------|-------------|-------------------|---------------|
| POWER_LOTTO (威力彩) | https://www.taiwanlottery.com/lotto/info/super_lotto638 | NO — dynamically rendered JS SPA | MANUAL_VERIFICATION_REQUIRED |
| BIG_LOTTO (大樂透) | https://www.taiwanlottery.com/lotto/info/lotto649 | NO — dynamically rendered JS SPA | MANUAL_VERIFICATION_REQUIRED |
| DAILY_539 (今彩539) | https://www.taiwanlottery.com/lotto/info/daily_cash | NO — dynamically rendered JS SPA | MANUAL_VERIFICATION_REQUIRED |

**Note on source status:** All three official Taiwan Lottery pages returned only a navigation shell (not prize table content) when fetched via curl and WebFetch. This is consistent with dynamically rendered JavaScript SPAs.

**Prize tier matching conditions** (number-of-hits + special/second-zone logic) are sourced from internal repo documentation:
- `lottery_api/CLAUDE.md` — contains explicit `calc_prize` docstrings for POWER_LOTTO and BIG_LOTTO
- `lottery_api/calculate_win_probability.py` — explicitly enumerates DAILY_539 prize tiers (頭獎/貳獎/參獎/肆獎)
- `lottery_api/tools/predict_539.py` — confirms "No special number" for DAILY_539

**Prize amounts (NTD values) are NOT included in this spec.** They must be verified against the official Taiwan Lottery pages before any prize-amount-dependent analysis.

---

## 3. Existing Repo Lottery Type Mapping

| Internal Key | Game ID | Display Name | Replay Rows | Draw Rows |
|---|---|---|---|---|
| `POWER_LOTTO` | `super_lotto638` | 威力彩 | 36,104 | 1,917 |
| `BIG_LOTTO` | `lotto649` | 大樂透 | 24,140 | 2,114 (canonical) |
| `DAILY_539` | `daily_cash` | 今彩539 | 34,680 | 5,882 |

All three lottery types are backed by `strategy_prediction_replays` table with `replay_status = PREDICTED` rows. The `hit_count`, `special_hit`, `actual_special`, and `predicted_special` columns are the key fields for prize-aware scoring.

### Schema Inventory Summary

```
strategy_prediction_replays:
  hit_count        INTEGER  — main-number hits (0-6 for POWER/BIG; 0-5 for DAILY_539)
  special_hit      INTEGER  — 0/1; game-specific logic (see below)
  actual_special   INTEGER  — actual special/second-zone number
  predicted_special INTEGER  — predicted second-zone number (POWER_LOTTO only, 25% coverage)

special_hit logic by lottery_type:
  POWER_LOTTO:  predicted_special == actual_special (exact second-zone prediction match)
  BIG_LOTTO:    actual_special IN predicted_numbers (post-hoc check, always computable)
  DAILY_539:    always 0 (no special number)
```

**Critical schema limitation:** `predicted_special` is populated for only ~25% of POWER_LOTTO rows (9,000/36,104). For the remaining 75%, `special_hit = 0` by default. This affects lower-tier prize-aware endpoints that depend on second-zone hit.

---

## 4. POWER_LOTTO Prize-Aware Endpoint Spec

**Game rules:** Pick 6 from 1–38 (first zone) + Pick 1 from 1–8 (second zone/power number)

### Official Prize Tiers (source: lottery_api/CLAUDE.md)

| Rank | Name | First Zone Hits | Second Zone | Endpoint Condition |
|------|------|----------------|-------------|-------------------|
| 1st | 頭獎 | 6 | YES | `hit_count=6 AND special_hit=1` |
| 2nd | 貳獎 | 6 | NO | `hit_count=6 AND special_hit=0` |
| 3rd | 參獎 | 5 | YES | `hit_count=5 AND special_hit=1` |
| 4th | 肆獎 | 5 | NO | `hit_count=5 AND special_hit=0` |
| 5th | 伍獎 | 4 | YES | `hit_count=4 AND special_hit=1` |
| 6th | 陸獎 | 4 | NO | `hit_count=4 AND special_hit=0` |
| 7th | 柒獎 | 3 | YES | `hit_count=3 AND special_hit=1` |
| 8th | 捌獎 | 2 | YES | `hit_count=2 AND special_hit=1` |
| 9th | 玖獎 | 3 | NO | `hit_count=3 AND special_hit=0` |
| Consolation | 普獎 | 1 | YES | `hit_count=1 AND special_hit=1` |

### Endpoint Definitions

| Endpoint Name | SQL Condition | Prize Tiers Covered |
|---|---|---|
| `POWER_M1_PLUS_SECOND` | `hit_count >= 1 AND special_hit = 1` | 普獎 + above with second |
| `POWER_M2_PLUS_SECOND` | `hit_count >= 2 AND special_hit = 1` | 捌獎 + above with second |
| `POWER_M3_PLUS_SECOND` | `hit_count >= 3 AND special_hit = 1` | 柒獎 + above with second |
| `POWER_M4_PLUS_SECOND` | `hit_count >= 4 AND special_hit = 1` | 伍獎 + above with second |
| `POWER_M5_PLUS_SECOND` | `hit_count >= 5 AND special_hit = 1` | 參獎 + 頭獎 |
| `POWER_M6_PLUS_SECOND` | `hit_count = 6 AND special_hit = 1` | 頭獎 only |
| `POWER_M6_NO_SECOND` | `hit_count = 6 AND special_hit = 0` | 貳獎 only |
| `POWER_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)` | All 10 prize tiers |
| `POWER_TIER_CLASS` | Categorical (see JSON) | All 10 tiers + NO_PRIZE |
| `POWER_MAIN_M3_PLUS_DIAGNOSTIC` | `hit_count >= 3` | **DIAGNOSTIC ONLY** — not prize-aware |
| `POWER_MAIN_M4_PLUS_DIAGNOSTIC` | `hit_count >= 4` | **DIAGNOSTIC ONLY** — not prize-aware |

**Important:** `POWER_M1_PLUS_SECOND` through `POWER_ANY_PRIZE_AWARE_WIN` all require `special_hit`, which depends on `predicted_special`. Due to the 75% null rate in `predicted_special`, these endpoints will undercount second-zone-inclusive prizes for the ~27,000 rows where no second-zone prediction was made.

---

## 5. BIG_LOTTO Prize-Aware Endpoint Spec

**Game rules:** Pick 6 from 1–49 (main numbers); special number drawn from remaining 43 balls

### Official Prize Tiers (source: lottery_api/CLAUDE.md)

| Rank | Name | Main Hits | Special | Endpoint Condition |
|------|------|-----------|---------|-------------------|
| 1st | 頭獎 | 6 | (N/A) | `hit_count = 6` |
| 2nd | 貳獎 | 5 | YES | `hit_count = 5 AND special_hit = 1` |
| 3rd | 參獎 | 5 | NO | `hit_count = 5 AND special_hit = 0` |
| 4th | 肆獎 | 4 | YES | `hit_count = 4 AND special_hit = 1` |
| 5th | 伍獎 | 4 | NO | `hit_count = 4 AND special_hit = 0` |
| 6th | 陸獎 | 3 | YES | `hit_count = 3 AND special_hit = 1` |
| 7th | 柒獎 | 3 | NO | `hit_count = 3 AND special_hit = 0` |
| Consolation | 普獎 | 2 | YES | `hit_count = 2 AND special_hit = 1` |

**Note:** `special_hit` for BIG_LOTTO = `actual_special IN predicted_numbers`. `actual_special` is populated for 100% of BIG_LOTTO rows, so `special_hit` is always computable.

### Endpoint Definitions

| Endpoint Name | SQL Condition | Prize Tiers Covered |
|---|---|---|
| `BIG_M2_PLUS_SPECIAL` | `hit_count >= 2 AND special_hit = 1` | 普獎 + 肆獎 + 貳獎 |
| `BIG_M3_PLUS_SPECIAL` | `hit_count >= 3 AND special_hit = 1` | 陸獎 + 肆獎 + 貳獎 |
| `BIG_M4_PLUS_SPECIAL` | `hit_count >= 4 AND special_hit = 1` | 肆獎 + 貳獎 |
| `BIG_M5_PLUS_SPECIAL` | `hit_count >= 5 AND special_hit = 1` | 貳獎 only |
| `BIG_M6_MAIN` | `hit_count = 6` | 頭獎 only |
| `BIG_ANY_PRIZE_AWARE_WIN` | `hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)` | All 8 prize tiers |
| `BIG_TIER_CLASS` | Categorical (see JSON) | All 8 tiers + NO_PRIZE |
| `BIG_MAIN_M3_PLUS_DIAGNOSTIC` | `hit_count >= 3` | **DIAGNOSTIC ONLY** — misses 普獎 |
| `BIG_MAIN_M4_PLUS_DIAGNOSTIC` | `hit_count >= 4` | **DIAGNOSTIC ONLY** — not prize-aware |

---

## 6. DAILY_539 Prize-Aware Endpoint Spec

**Game rules:** Pick 5 from 1–39 (main numbers only); **no special number; no second zone**

### Official Prize Tiers (source: lottery_api/calculate_win_probability.py)

| Rank | Name | Main Hits | Endpoint Condition |
|------|------|-----------|-------------------|
| 1st | 頭獎 | 5/5 | `hit_count = 5` |
| 2nd | 貳獎 | 4/5 | `hit_count = 4` |
| 3rd | 參獎 | 3/5 | `hit_count = 3` |
| 4th | 肆獎 | 2/5 | `hit_count = 2` |

**No special number, no second zone.** `special_hit = 0` for all 34,680 DAILY_539 replay rows (confirmed from DB schema inventory).

### Endpoint Definitions

| Endpoint Name | SQL Condition | Prize Tiers Covered |
|---|---|---|
| `D539_M2_PLUS` | `hit_count >= 2` | 肆獎 + 參獎 + 貳獎 + 頭獎 |
| `D539_M3_PLUS` | `hit_count >= 3` | 參獎 + 貳獎 + 頭獎 |
| `D539_M4_PLUS` | `hit_count >= 4` | 貳獎 + 頭獎 |
| `D539_M5` | `hit_count = 5` | 頭獎 only |
| `D539_ANY_PRIZE_AWARE_WIN` | `hit_count >= 2` | All 4 prize tiers (identical to D539_M2_PLUS) |
| `D539_TIER_CLASS` | Categorical (see JSON) | All 4 tiers + NO_PRIZE |

**DAILY_539 special note:** `D539_M3_PLUS` is the same as the existing P265A M3+ diagnostic. It is prize-aware for 參獎/貳獎/頭獎 but misses 肆獎 (2-match). For complete prize coverage use `D539_ANY_PRIZE_AWARE_WIN` (= `D539_M2_PLUS`).

---

## 7. Tier-Class Mapping Table

### POWER_LOTTO Tier Classes (ordered by prize value)

| Tier Class | Rank | TW Name | Condition |
|---|---|---|---|
| `TIER_1_JACKPOT` | 1 | 頭獎 | hit=6, second=YES |
| `TIER_2_6TH_ONLY` | 2 | 貳獎 | hit=6, second=NO |
| `TIER_3_5TH_SECOND` | 3 | 參獎 | hit=5, second=YES |
| `TIER_4_5TH_ONLY` | 4 | 肆獎 | hit=5, second=NO |
| `TIER_5_4TH_SECOND` | 5 | 伍獎 | hit=4, second=YES |
| `TIER_6_4TH_ONLY` | 6 | 陸獎 | hit=4, second=NO |
| `TIER_7_3RD_SECOND` | 7 | 柒獎 | hit=3, second=YES |
| `TIER_8_2ND_SECOND` | 8 | 捌獎 | hit=2, second=YES |
| `TIER_9_3RD_ONLY` | 9 | 玖獎 | hit=3, second=NO |
| `CONSOLATION_1ST_SECOND` | 10 | 普獎 | hit=1, second=YES |
| `NO_PRIZE` | — | 未中獎 | all others |

### BIG_LOTTO Tier Classes (ordered by prize value)

| Tier Class | Rank | TW Name | Condition |
|---|---|---|---|
| `TIER_1_JACKPOT` | 1 | 頭獎 | hit=6 |
| `TIER_2_5TH_SPECIAL` | 2 | 貳獎 | hit=5, special=YES |
| `TIER_3_5TH_ONLY` | 3 | 參獎 | hit=5, special=NO |
| `TIER_4_4TH_SPECIAL` | 4 | 肆獎 | hit=4, special=YES |
| `TIER_5_4TH_ONLY` | 5 | 伍獎 | hit=4, special=NO |
| `TIER_6_3RD_SPECIAL` | 6 | 陸獎 | hit=3, special=YES |
| `TIER_7_3RD_ONLY` | 7 | 柒獎 | hit=3, special=NO |
| `CONSOLATION_2ND_SPECIAL` | 8 | 普獎 | hit=2, special=YES |
| `NO_PRIZE` | — | 未中獎 | all others |

### DAILY_539 Tier Classes (ordered by prize value)

| Tier Class | Rank | TW Name | Condition |
|---|---|---|---|
| `TIER_1_JACKPOT` | 1 | 頭獎 | hit=5 |
| `TIER_2_4TH` | 2 | 貳獎 | hit=4 |
| `TIER_3_3RD` | 3 | 參獎 | hit=3 |
| `TIER_4_2ND` | 4 | 肆獎 | hit=2 |
| `NO_PRIZE` | — | 未中獎 | hit<2 |

---

## 8. Parallel Track Design: Prize-Aware vs M3+ Diagnostics

Prize-aware endpoints run as a **new parallel track** alongside the existing M3+ diagnostic track. Neither replaces the other.

### Track Comparison

| Property | M3+ Track (existing) | Prize-Aware Track (new, parallel) |
|---|---|---|
| Endpoint | `hit_count >= 3` | `ANY_PRIZE_AWARE_WIN`, `TIER_CLASS`, `Mx_PLUS_*` |
| Standard | P265A SSOT | P271A spec |
| DB change | None | None — computed at query time |
| API change | None | New parallel queries only |
| Test change | None | New parallel test coverage only |
| Replaces M3+? | N/A | **NO** |

### Gap Analysis (informational only — not a replacement rationale)

| Lottery | M3+ Misses vs Prize-Aware | Parallel Prize-Aware Coverage |
|---|---|---|
| POWER_LOTTO | 捌獎 (hit=2, second=YES) and 普獎 (hit=1, second=YES) | `POWER_ANY_PRIZE_AWARE_WIN` adds these 2 tiers |
| BIG_LOTTO | 普獎 (hit=2, special=YES) | `BIG_ANY_PRIZE_AWARE_WIN` adds this 1 tier |
| DAILY_539 | 肆獎 (hit=2) | `D539_ANY_PRIZE_AWARE_WIN` adds this 1 tier |

### Rules for Both Tracks

- **M3+ track is preserved and unmodified** — all pre-registered hypotheses, API endpoints, and tests against M3+ continue as-is
- **Prize-aware track is additive** — new queries, new metrics, new test coverage only
- **Coexistence required** — any report including prize-aware rates must also report the M3+ rate for the same cell
- **No migration** — deprecating M3+ requires a separate explicit governance decision with user authorization

---

## 9. Leakage and Misuse Prohibitions

1. **Prize-aware endpoints are evaluation tools only.** They must not be used to generate betting recommendations.
2. **Endpoint rates must not be compared to unadjusted baselines.** Each endpoint has a different theoretical baseline probability; any comparison must use the correct lottery-specific and endpoint-specific baseline.
3. **Outcome columns may only be read for evaluation, not for training.** Replay rows with `replay_status = PREDICTED` are the only valid evaluation rows. No new replay rows may be generated as part of this spec.
4. **Special-hit coverage gap must be reported.** Any analysis using POWER_LOTTO second-zone endpoints must report the predicted_special null rate (~75%) as a limitation.
5. **Prize amounts are NOT in scope.** This spec defines match conditions only. Prize amounts require official source verification.
6. **No strategy selection.** Endpoint scores must not be used to select strategies for promotion without going through the full P221F gate.

---

## 10. Required Fields for Future Implementation

For a future P271B prize-aware scoring implementation:

| Field | Status | Source | Notes |
|---|---|---|---|
| `hit_count` | ✅ Present | `strategy_prediction_replays` | Main-number hits |
| `special_hit` | ✅ Present | `strategy_prediction_replays` | Computed as per game rules |
| `lottery_type` | ✅ Present | `strategy_prediction_replays` | Required for endpoint routing |
| `actual_special` | ✅ Present (POWER/BIG) | `strategy_prediction_replays` | 100% for POWER+BIG, 0% for 539 |
| `predicted_special` | ⚠️ Partial | `strategy_prediction_replays` | Only 25% for POWER_LOTTO; absent for BIG/539 |
| `tier_class` | ❌ Not stored | Derived | Must compute from hit_count + special_hit + lottery_type |
| `prize_aware_win` | ❌ Not stored | Derived | Must compute using ANY_PRIZE_AWARE_WIN condition |

**Implementation note:** `tier_class` and `prize_aware_win` should be computed as SQL CASE expressions or Python derived fields at query time. They must NOT be written to `strategy_prediction_replays` without explicit Type D authorization.

---

## 11. What This Task Did NOT Do

- Did NOT run any backtest
- Did NOT query replay rows for strategy performance
- Did NOT compare any strategy's performance on any metric
- Did NOT write to any database table
- Did NOT modify `hypothesis_registry.jsonl`
- Did NOT create or modify any production, API, or frontend code
- Did NOT generate any strategy
- Did NOT claim any hit-rate improvement
- Did NOT authorize P270C or any P270 continuation
- Did NOT start P271B, P271C, or P271D

---

## 12. Recommended Next Task

**P271B — Prize-Aware Endpoint Implementation and Scoring Query**

Prerequisites:
1. User authorization for P271B
2. Manual verification of prize tier match conditions against official Taiwan Lottery pages (https://www.taiwanlottery.com/lotto/info/super_lotto638, /lotto649, /daily_cash) — addresses MANUAL_VERIFICATION_REQUIRED status
3. Governance review of POWER_LOTTO `predicted_special` gap policy (whether to compute POWER second-zone endpoints only for rows with predicted_special != NULL, or to treat all NULL-predicted_special rows as "second-zone prediction not made = second-zone miss")

P271B scope (pending authorization):
- Add `prize_tier_class` and `prize_aware_win` computed SQL expressions to replay evaluation queries
- Run prize-aware success rate queries across all 36 replay-backed strategy cells (read-only, no DB write)
- Compare prize-aware rates to existing M3+ diagnostic rates
- Report gaps and coverage under the defined endpoints
