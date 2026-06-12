# P271B — Official Prize Rule Verification & Scoring Engine Design

**Task ID:** P271B  
**Date:** 2026-06-11  
**Branch:** `task/p271b-official-prize-rule-scoring-engine-design`  
**Repo HEAD:** `ed7afe308d1770a5eda491163bbadac5635c34e9` (P271A merge)  
**Final Classification:** `P271B_OFFICIAL_PRIZE_RULE_SCORING_ENGINE_DESIGN_COMPLETE`

---

## Architectural Principle: Parallel Feature, Not Replacement

> **Prize-aware scoring is a NEW PARALLEL evaluation feature. It does NOT replace, override, deprecate, or migrate the existing M3+/replay scoring. Both tracks run concurrently in perpetuity. Any replacement or deprecation of M3+ requires separate explicit governance authorization.**

---

## 1. Executive Summary

P271B verifies the official prize tier rules for all three Taiwan Lottery games and produces a design artifact for a future prize-aware scoring engine skeleton.

**Key findings:**
- All three official Taiwan Lottery pages (`super_lotto638`, `lotto649`, `daily_cash`) are JavaScript SPAs — prize tables cannot be machine-read. Source status: **MANUAL_VERIFICATION_REQUIRED** for all three.
- Prize tier conditions were verified from internal repo documentation (`lottery_api/CLAUDE.md` `calc_prize` docstrings, `calculate_win_probability.py`), which embeds the production prize-determination logic.
- **P271A endpoint spec alignment: PASS** — all three `ANY_PRIZE_AWARE_WIN` endpoint conditions correctly capture all prize tiers with zero mismatches.
- Prize-aware scoring engine design produced as specification only. No Python module was implemented. Implementation is deferred to P271C.
- No backtest, no replay evaluation, no DB write, no strategy generated, no hit-rate improvement claimed.

---

## 2. Official Source URLs and Source Verification Status

| Lottery | Official URL | Extraction Method | Source Status |
|---|---|---|---|
| POWER_LOTTO (威力彩) | https://www.taiwanlottery.com/lotto/info/super_lotto638 | WebFetch attempted | MANUAL_VERIFICATION_REQUIRED |
| BIG_LOTTO (大樂透) | https://www.taiwanlottery.com/lotto/info/lotto649 | WebFetch attempted | MANUAL_VERIFICATION_REQUIRED |
| DAILY_539 (今彩539) | https://www.taiwanlottery.com/lotto/info/daily_cash | WebFetch attempted | MANUAL_VERIFICATION_REQUIRED |

**Extraction details:** Both WebFetch and Chrome browser MCP were attempted. All three Taiwan Lottery pages are JavaScript single-page applications — WebFetch returns navigation shell only (no prize tables rendered). Chrome MCP was unavailable in this session.

**Fallback internal source used:**
- `lottery_api/CLAUDE.md` lines 976–1023 — `calc_prize` function docstrings for BIG_LOTTO and POWER_LOTTO
- `lottery_api/calculate_win_probability.py` lines 65–70 — `match_levels` list for DAILY_539

These internal sources document the prize-determination logic embedded in the production `calc_prize` function. Prize amounts (NTD values) are NOT included in this artifact.

---

## 3. Verified POWER_LOTTO (威力彩) Prize Rule Mapping

**Game structure:** First zone: pick 6 from 1–38. Second zone (特別號): pick 1 from 1–8.  
**Special hit logic:** `special_hit = (predicted_special == actual_special)` — exact match.  
**Schema limitation:** `predicted_special` is only populated for ~25% of POWER_LOTTO replay rows (~9,000 of 36,104). Second-zone-dependent tiers cannot be evaluated for the remaining ~75%.

| Rank | Tier (zh) | hit_count | special_hit | tier_class | SQL Condition |
|---|---|---|---|---|---|
| 1 | 頭獎 | 6 | 1 | POWER_FIRST_PRIZE | hit_count=6 AND special_hit=1 |
| 2 | 貳獎 | 6 | 0 | POWER_SECOND_PRIZE | hit_count=6 AND special_hit=0 |
| 3 | 參獎 | 5 | 1 | POWER_THIRD_PRIZE | hit_count=5 AND special_hit=1 |
| 4 | 肆獎 | 5 | 0 | POWER_FOURTH_PRIZE | hit_count=5 AND special_hit=0 |
| 5 | 伍獎 | 4 | 1 | POWER_FIFTH_PRIZE | hit_count=4 AND special_hit=1 |
| 6 | 陸獎 | 4 | 0 | POWER_SIXTH_PRIZE | hit_count=4 AND special_hit=0 |
| 7 | 柒獎 | 3 | 1 | POWER_SEVENTH_PRIZE | hit_count=3 AND special_hit=1 |
| 8 | 捌獎 | 2 | 1 | POWER_EIGHTH_PRIZE | hit_count=2 AND special_hit=1 |
| 9 | 玖獎 | 3 | 0 | POWER_NINTH_PRIZE | hit_count=3 AND special_hit=0 |
| 10 | 普獎 | 1 | 1 | POWER_CONSOLATION_PRIZE | hit_count=1 AND special_hit=1 |
| — | No prize | other | — | POWER_NO_PRIZE | all other combinations |

**`POWER_ANY_PRIZE_AWARE_WIN`:** `hit_count >= 3 OR (hit_count >= 1 AND special_hit = 1)`  
**M3+ diagnostic (existing, unchanged):** `hit_count >= 3` — misses 捌獎 (2+1) and 普獎 (1+1).

---

## 4. Verified BIG_LOTTO (大樂透) Prize Rule Mapping

**Game structure:** Pick 6 main numbers from 1–49. Special number drawn from remaining 43 numbers.  
**Special hit logic:** `special_hit = (actual_special IN predicted_numbers)` — actual special appears in the 6 predicted numbers.  
**Schema note:** `actual_special` is 100% populated for BIG_LOTTO (24,140 rows). `special_hit` is always computable.

| Rank | Tier (zh) | hit_count | special_hit | tier_class | SQL Condition |
|---|---|---|---|---|---|
| 1 | 頭獎 | 6 | N/A | BIG_FIRST_PRIZE | hit_count=6 |
| 2 | 貳獎 | 5 | 1 | BIG_SECOND_PRIZE | hit_count=5 AND special_hit=1 |
| 3 | 參獎 | 5 | 0 | BIG_THIRD_PRIZE | hit_count=5 AND special_hit=0 |
| 4 | 肆獎 | 4 | 1 | BIG_FOURTH_PRIZE | hit_count=4 AND special_hit=1 |
| 5 | 伍獎 | 4 | 0 | BIG_FIFTH_PRIZE | hit_count=4 AND special_hit=0 |
| 6 | 陸獎 | 3 | 1 | BIG_SIXTH_PRIZE | hit_count=3 AND special_hit=1 |
| 7 | 柒獎 | 3 | 0 | BIG_SEVENTH_PRIZE | hit_count=3 AND special_hit=0 |
| 8 | 普獎 | 2 | 1 | BIG_CONSOLATION_PRIZE | hit_count=2 AND special_hit=1 |
| — | No prize | other | — | BIG_NO_PRIZE | all other combinations |

**`BIG_ANY_PRIZE_AWARE_WIN`:** `hit_count >= 3 OR (hit_count = 2 AND special_hit = 1)`  
**M3+ diagnostic (existing, unchanged):** `hit_count >= 3` — misses 普獎 (2+1).

---

## 5. Verified DAILY_539 (今彩539) Prize Rule Mapping

**Game structure:** Pick 5 main numbers from 1–39. No special number exists.  
**Special hit logic:** `special_hit` is always 0 for DAILY_539. No second-zone exists.

| Rank | Tier (zh) | hit_count | tier_class | SQL Condition |
|---|---|---|---|---|
| 1 | 頭獎 | 5 | D539_FIRST_PRIZE | hit_count=5 |
| 2 | 貳獎 | 4 | D539_SECOND_PRIZE | hit_count=4 |
| 3 | 參獎 | 3 | D539_THIRD_PRIZE | hit_count=3 |
| 4 | 肆獎 | 2 | D539_FOURTH_PRIZE | hit_count=2 |
| — | No prize | <2 | D539_NO_PRIZE | hit_count<2 |

**`D539_ANY_PRIZE_AWARE_WIN`:** `hit_count >= 2`  
**M3+ diagnostic (existing, unchanged):** `hit_count >= 3` — misses 肆獎 (hit_count=2).

---

## 6. Alignment Check Against P271A

| Endpoint | P271A Condition | Status | Coverage |
|---|---|---|---|
| POWER_ANY_PRIZE_AWARE_WIN | hit_count>=3 OR (hit_count>=1 AND special_hit=1) | **ALIGNED** | All 10 POWER_LOTTO tiers covered |
| BIG_ANY_PRIZE_AWARE_WIN | hit_count>=3 OR (hit_count=2 AND special_hit=1) | **ALIGNED** | All 8 BIG_LOTTO tiers covered |
| D539_ANY_PRIZE_AWARE_WIN | hit_count>=2 | **ALIGNED** | All 4 DAILY_539 tiers covered |

**Mismatches with P271A: NONE.** P271A endpoint conditions are verified correct against the internal prize rule documentation.

---

## 7. Parallel Track Design: Prize-Aware vs M3+ (Architecture Guard)

| Track | Endpoint | Standard | Status |
|---|---|---|---|
| Existing (unchanged) | M3+ (hit_count>=3, special_hit excluded) | P265A SSOT | UNCHANGED |
| New parallel | ANY_PRIZE_AWARE_WIN + tier_class | P271A spec | Design only (P271C required) |

**Coexistence rule:** Any future report including prize-aware rates MUST also include the M3+ rate for the same strategy cell. Neither track alone is sufficient.

**No migration path:** Deprecating or replacing M3+ requires a separate explicit governance authorization — it is NOT authorized by P271A or P271B.

**Protected consumers of M3+:**
- `replay.py history-overview` and `d3-strategy-status-coverage`
- P267C revalidation results (0/36 Bonferroni, NO_VALIDATED_M3_EDGE)
- P269C calendar regime H1 test
- P270B geometry power audit
- All pre-registered hypothesis registry entries using M3+ as their endpoint

---

## 8. Proposed Scoring Engine Design

**Module:** `lottery_api/research/prize_aware_scoring/prize_aware_scorer.py`

**Design principles:**
- Pure functions only — no DB access, no global state, no mutation
- Stateless — same inputs always produce same outputs
- No dependency on replay pipeline or M3+ scoring code
- No production API integration in this skeleton phase
- Parallel track — does not replace, override, or change M3+ scoring

**Proposed API:**

```python
# Primary entry point
def classify_tier(lottery_type: str, hit_count: int, special_hit: int) -> str:
    """Returns tier_class string. Raises ValueError for invalid inputs."""

# Boolean win check
def is_any_prize_aware_win(lottery_type: str, hit_count: int, special_hit: int) -> bool:
    """True if tier_class is not NO_PRIZE."""

# Full row scoring (both tracks in parallel)
def score_replay_row(lottery_type: str, hit_count: int, special_hit: int) -> dict:
    """Returns {tier_class, is_prize_aware_win, is_m3_plus, endpoint_flags}."""
```

**Forbidden imports for this module:**
- `lottery_api.routes`, `lottery_api.engine`, `lottery_api.data`
- Any DB connection, replay pipeline, or registry module

---

## 9. Input and Output Contract

### Input
| Parameter | Type | Validation |
|---|---|---|
| lottery_type | str | Must be POWER_LOTTO, BIG_LOTTO, or DAILY_539 |
| hit_count | int | 0 to max_pick_count; raise ValueError if out of range |
| special_hit | int | 0 or 1; DAILY_539 must always be 0 |

> **Schema limitation:** For POWER_LOTTO rows where `predicted_special` is NULL (~75% of rows), caller must pass `special_hit=0`. The scorer does not access DB to resolve NULL values.

### Output (`score_replay_row`)
| Field | Type | Semantics |
|---|---|---|
| tier_class | str | e.g. POWER_EIGHTH_PRIZE, BIG_CONSOLATION_PRIZE |
| is_prize_aware_win | bool | True if tier_class is not NO_PRIZE |
| is_m3_plus | bool | True if hit_count >= 3 (P265A SSOT, special_hit excluded) |
| endpoint_flags | dict | {any_prize_aware_win, m3_plus_diagnostic, consolation_or_above} |

---

## 10. Unit-Test Fixture Matrix for Future Implementation

### POWER_LOTTO (14 fixtures)
| hit_count | special_hit | expected_tier | expected_win | expected_m3_plus |
|---|---|---|---|---|
| 6 | 1 | POWER_FIRST_PRIZE | True | True |
| 6 | 0 | POWER_SECOND_PRIZE | True | True |
| 5 | 1 | POWER_THIRD_PRIZE | True | True |
| 5 | 0 | POWER_FOURTH_PRIZE | True | True |
| 4 | 1 | POWER_FIFTH_PRIZE | True | True |
| 4 | 0 | POWER_SIXTH_PRIZE | True | True |
| 3 | 1 | POWER_SEVENTH_PRIZE | True | True |
| 2 | 1 | POWER_EIGHTH_PRIZE | **True** | **False** ← M3+ misses |
| 3 | 0 | POWER_NINTH_PRIZE | True | True |
| 1 | 1 | POWER_CONSOLATION_PRIZE | **True** | **False** ← M3+ misses |
| 2 | 0 | POWER_NO_PRIZE | False | False |
| 1 | 0 | POWER_NO_PRIZE | False | False |
| 0 | 1 | POWER_NO_PRIZE | False | False |
| 0 | 0 | POWER_NO_PRIZE | False | False |

### BIG_LOTTO (13 fixtures)
| hit_count | special_hit | expected_tier | expected_win | expected_m3_plus |
|---|---|---|---|---|
| 6 | 0 | BIG_FIRST_PRIZE | True | True |
| 6 | 1 | BIG_FIRST_PRIZE | True | True |
| 5 | 1 | BIG_SECOND_PRIZE | True | True |
| 5 | 0 | BIG_THIRD_PRIZE | True | True |
| 4 | 1 | BIG_FOURTH_PRIZE | True | True |
| 4 | 0 | BIG_FIFTH_PRIZE | True | True |
| 3 | 1 | BIG_SIXTH_PRIZE | True | True |
| 3 | 0 | BIG_SEVENTH_PRIZE | True | True |
| 2 | 1 | BIG_CONSOLATION_PRIZE | **True** | **False** ← M3+ misses |
| 2 | 0 | BIG_NO_PRIZE | False | False |
| 1 | 1 | BIG_NO_PRIZE | False | False |
| 1 | 0 | BIG_NO_PRIZE | False | False |
| 0 | 0 | BIG_NO_PRIZE | False | False |

### DAILY_539 (6 fixtures)
| hit_count | special_hit | expected_tier | expected_win | expected_m3_plus |
|---|---|---|---|---|
| 5 | 0 | D539_FIRST_PRIZE | True | True |
| 4 | 0 | D539_SECOND_PRIZE | True | True |
| 3 | 0 | D539_THIRD_PRIZE | True | True |
| 2 | 0 | D539_FOURTH_PRIZE | **True** | **False** ← M3+ misses |
| 1 | 0 | D539_NO_PRIZE | False | False |
| 0 | 0 | D539_NO_PRIZE | False | False |

---

## 11. Leakage and Misuse Prohibitions

- Prize-aware endpoints are evaluation endpoints for research analysis only.
- They are **NOT** betting advice and do **NOT** represent an approved prediction method.
- Prize-aware win rates do **NOT** imply improved prediction accuracy or improved win rates.
- Prize-aware scoring does **NOT** replace or deprecate M3+ scoring.
- The `score_replay_row` function must never be connected to a recommendation pipeline.
- No prize amounts (NTD) or payout data are included in this artifact.
- POWER_LOTTO second-zone results on the ~75% of rows with NULL `predicted_special` must be clearly flagged as INCOMPLETE when reported.

---

## 12. What This Task Did NOT Do

- **No backtest was run.**
- **No replay evaluation was run.**
- **No DB write happened.**
- **No registry mutation happened** (hypothesis_registry.jsonl unchanged).
- **No strategy was generated.**
- **No hit-rate improvement is claimed.**
- **Existing M3+/replay scoring remains unchanged.** The P265A SSOT M3+ metric is identical to before P271B.
- **Replacement/migration of M3+ is not authorized.**
- **P270C remains not authorized.**
- **P271C/P271D were not started.**
- No production, API, or frontend scoring runtime code was modified.
- No Python scoring module was implemented (design spec only).

---

## 13. Recommended Next Task

**State: HOLD / WAITING_FOR_USER_AUTHORIZATION**

If the user authorizes **P271C**:
- Implement `lottery_api/research/prize_aware_scoring/prize_aware_scorer.py` as a pure-function module
- Use the `unit_test_fixture_matrix` from Section 10 as the test basis (33 total fixtures across 3 lotteries)
- P271C must not modify any existing scoring code, must not write to DB, must not add columns to `strategy_prediction_replays`
- P271C must include coexistence tests confirming M3+ is unchanged after implementation
- Include POWER_LOTTO schema-limitation guard: flag results where `predicted_special` is NULL

If the user does not authorize P271C, this design artifact remains available for future reference. The system stays at HOLD.

---

*This artifact is specification and design documentation only. It does not constitute a prediction, a betting recommendation, an approved strategy, or a guaranteed win rate. Taiwan Lottery prize rules should be manually verified against official pages before any production use.*
