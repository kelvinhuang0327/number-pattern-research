# P126 — Controlled Apply Dry-Run Plan for Tier-B Multi-Bet Adapters

**Generated:** 2026-05-28T03:43:38.897359+00:00
**Classification:** `P126_DRY_RUN_PLAN_READY`
**Source P124:** `outputs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.json`
**Source P125:** `outputs/replay/p125_adapter_gap_plan_from_p124_20260528.json`

---

## 1. Executive Summary

This is a **read-only dry-run plan**. No DB writes have been executed.

P126 plans the controlled apply of 5 Tier-B multi-bet adapter strategies
identified by P124 (coverage matrix) and P125 (adapter gap plan).

| Item | Value |
|---|---|
| Candidates | 5 |
| Current replay rows | 54462 |
| New rows if ALL applied | +18000 |
| Total rows after all applied | 72462 |
| DB writes in P126 | **0** |
| Apply authorization required | **YES — per strategy** |
| P128 storage design | **PENDING** |

---

## 2. DB Snapshot (Before Apply)

| Metric | Value |
|---|---|
| strategy_prediction_replays | 54462 |
| 3_STAR count / max draw | 4179 / 115000106 |
| 4_STAR count / max draw | 2922 / 115000103 |
| POWER_LOTTO count / max draw | 1913 / 115000041 |

---

## 3. Five Tier-B Controlled-Apply Candidates

### 3.1. `biglotto_echo_aware_3bet` (BIG_LOTTO / 3-bet)

| Field | Value |
|---|---|
| Quality label | `fallback_equivalent` |
| Risk level | `low_to_medium` |
| Existing rows (bet-1 only) | 1500 |
| Draw range | 102000012 — 115000055 |
| Target bets | 3 |
| New rows if applied | **+3000** |
| Total rows after apply | 4500 |
| Storage approach | `one_row_per_bet` |
| Provenance guard | `PASS` |
| Duplicate guard | `PASS` |
| Dry-run status | `READY` |
| Apply authorization | **REQUIRED** |

**Storage note:** For each of the 1500 draws: keep existing bet-1 row; add 2 additional row(s) for bet-2 through bet-3. Requires P128 storage design to be formally accepted before apply.

**Authorization phrase (copy-paste):**
```
YES authorize controlled_apply for biglotto_echo_aware_3bet because <reason>
```

### 3.2. `daily539_f4cold_5bet` (DAILY_539 / 5-bet)

| Field | Value |
|---|---|
| Quality label | `watchlist` |
| Risk level | `medium` |
| Existing rows (bet-1 only) | 1500 |
| Draw range | 110000190 — 115000121 |
| Target bets | 5 |
| New rows if applied | **+6000** |
| Total rows after apply | 7500 |
| Storage approach | `one_row_per_bet` |
| Provenance guard | `PASS` |
| Duplicate guard | `PASS` |
| Dry-run status | `READY` |
| Apply authorization | **REQUIRED** |

**Storage note:** For each of the 1500 draws: keep existing bet-1 row; add 4 additional row(s) for bet-2 through bet-5. Requires P128 storage design to be formally accepted before apply.

**Authorization phrase (copy-paste):**
```
YES authorize controlled_apply for daily539_f4cold_5bet because <reason>
```

### 3.3. `daily539_f4cold_3bet` (DAILY_539 / 3-bet)

| Field | Value |
|---|---|
| Quality label | `watchlist` |
| Risk level | `medium` |
| Existing rows (bet-1 only) | 1500 |
| Draw range | 110000190 — 115000121 |
| Target bets | 3 |
| New rows if applied | **+3000** |
| Total rows after apply | 4500 |
| Storage approach | `one_row_per_bet` |
| Provenance guard | `PASS` |
| Duplicate guard | `PASS` |
| Dry-run status | `READY` |
| Apply authorization | **REQUIRED** |

**Storage note:** For each of the 1500 draws: keep existing bet-1 row; add 2 additional row(s) for bet-2 through bet-3. Requires P128 storage design to be formally accepted before apply.

**Authorization phrase (copy-paste):**
```
YES authorize controlled_apply for daily539_f4cold_3bet because <reason>
```

### 3.4. `power_fourier_rhythm_2bet` (POWER_LOTTO / 2-bet)

| Field | Value |
|---|---|
| Quality label | `watchlist` |
| Risk level | `medium` |
| Existing rows (bet-1 only) | 1500 |
| Draw range | 101000003 — 115000041 |
| Target bets | 2 |
| New rows if applied | **+1500** |
| Total rows after apply | 3000 |
| Storage approach | `one_row_per_bet` |
| Provenance guard | `PASS` |
| Duplicate guard | `PASS` |
| Dry-run status | `READY` |
| Apply authorization | **REQUIRED** |

**Storage note:** For each of the 1500 draws: keep existing bet-1 row; add 1 additional row(s) for bet-2 through bet-2. Requires P128 storage design to be formally accepted before apply.

**Authorization phrase (copy-paste):**
```
YES authorize controlled_apply for power_fourier_rhythm_2bet because <reason>
```

### 3.5. `biglotto_ts3_markov_4bet_w30` (BIG_LOTTO / 4-bet)

| Field | Value |
|---|---|
| Quality label | `sub_baseline` |
| Risk level | `medium` |
| Existing rows (bet-1 only) | 1500 |
| Draw range | 102000012 — 115000055 |
| Target bets | 4 |
| New rows if applied | **+4500** |
| Total rows after apply | 6000 |
| Storage approach | `one_row_per_bet` |
| Provenance guard | `PASS` |
| Duplicate guard | `PASS` |
| Dry-run status | `READY` |
| Apply authorization | **REQUIRED** |

**Storage note:** For each of the 1500 draws: keep existing bet-1 row; add 3 additional row(s) for bet-2 through bet-4. Requires P128 storage design to be formally accepted before apply.

**Authorization phrase (copy-paste):**
```
YES authorize controlled_apply for biglotto_ts3_markov_4bet_w30 because <reason>
```

---

## 4. Duplicate Guard Summary

| Strategy | Duplicate Draws Found | Status |
|---|---|---|
| `biglotto_echo_aware_3bet` | 0 | `PASS` |
| `daily539_f4cold_5bet` | 0 | `PASS` |
| `daily539_f4cold_3bet` | 0 | `PASS` |
| `power_fourier_rhythm_2bet` | 0 | `PASS` |
| `biglotto_ts3_markov_4bet_w30` | 0 | `PASS` |

All candidates: zero duplicate draws. Existing rows are all bet-1 only (P94 source).
Future apply must NOT re-insert bet-1 rows; only add bet-2 through bet-N.

---

## 5. Provenance Guard Summary

| Strategy | Source | Truth Level | Status |
|---|---|---|---|
| `biglotto_echo_aware_3bet` | `P94_TIERB_CONTROLLED_APPLY` | `TIERB_DRYRUN_VALIDATED` | `PASS` |
| `daily539_f4cold_5bet` | `P94_TIERB_CONTROLLED_APPLY` | `TIERB_DRYRUN_VALIDATED` | `PASS` |
| `daily539_f4cold_3bet` | `P94_TIERB_CONTROLLED_APPLY` | `TIERB_DRYRUN_VALIDATED` | `PASS` |
| `power_fourier_rhythm_2bet` | `P94_TIERB_CONTROLLED_APPLY` | `TIERB_DRYRUN_VALIDATED` | `PASS` |
| `biglotto_ts3_markov_4bet_w30` | `P94_TIERB_CONTROLLED_APPLY` | `TIERB_DRYRUN_VALIDATED` | `PASS` |

All candidates: rows sourced from `P94_CONTROLLED_APPLY` with `TIERB_DRYRUN_VALIDATED` truth level.
Provenance is clean and trusted.

---

## 6. Storage Risk (From P125 RSR-1 through RSR-4)

### RSR-1: Native multi-bet storage format not decided

- **Status:** **BLOCKER FOR APPLY**
- **Description:** Current schema has no bet_index column. P126 plan assumes one-row-per-bet convention. P128 must formally decide between one-row-per-bet (N× row growth, simpler queries) vs. array-of-arrays per row (compact, breaks existing consumers).
- **Resolution:** P128 design decision or explicit Kelvin authorization of one-row-per-bet

### RSR-2: No bet_index column in current schema

- **Status:** Non-blocking
- **Description:** After adding bet-2 through bet-N rows, there is no column to distinguish bet index. Consumer queries that do SELECT ... WHERE strategy_id=? will return all bets mixed. Schema migration (adding bet_index) requires P128.
- **Resolution:** Interim: encode bet index in source/controlled_apply_id field. Permanent: add bet_index column in P128.

### RSR-3: Drift guard must be updated for multi-bet row counts

- **Status:** Non-blocking
- **Description:** replay_lifecycle_drift_guard.py currently expects exactly 54462 rows. After multi-bet apply the expected count must be updated to 54462 + new_rows_applied.
- **Resolution:** Update drift guard expected count after each batch apply.

### RSR-4: API and UI consumers assume one-row-per-draw

- **Status:** Non-blocking
- **Description:** Existing API endpoints and dashboard likely assume one replay row per (strategy, draw) pair. Multi-bet rows will appear as duplicate draws without bet_index awareness.
- **Resolution:** Update API and UI in parallel with or after P128 schema decision.

---

## 7. Row Delta Summary

| Apply Order | Strategy | Bets | +Rows | Cumulative Total |
|---|---|---|---|---|
| 1 | `biglotto_echo_aware_3bet` | 3 | +3000 | 57462 |
| 2 | `daily539_f4cold_5bet` | 5 | +6000 | 63462 |
| 3 | `daily539_f4cold_3bet` | 3 | +3000 | 66462 |
| 4 | `power_fourier_rhythm_2bet` | 2 | +1500 | 67962 |
| 5 | `biglotto_ts3_markov_4bet_w30` | 4 | +4500 | 72462 |

**Total new rows if all 5 applied:** +18000
**Total replay rows after all applied:** 72462

---

## 8. Preconditions for Each Apply

All 5 candidates require ALL of the following before any DB write:

1. `db_invariant_confirmed` — replay_rows must equal expected value immediately before apply
2. `p128_storage_design_or_convention_accepted` — P128 decision OR explicit Kelvin authorization of one-row-per-bet
3. `provenance_guard PASS` — all existing rows from trusted P94 source
4. `duplicate_guard PASS` — no duplicate target_draw for the strategy
5. `staging_whitelist_clean` — `git diff --cached --name-only` must show only whitelisted files
6. `explicit_apply_authorization` — Kelvin must state the authorization phrase for each strategy individually

---

## 9. Recommended Apply Sequence

Apply one strategy at a time in ranked order. After each apply:
- Verify row count delta matches expected
- Run P126 tests and drift guard
- Do NOT proceed to next strategy until previous is verified

| Order | Strategy | Reason |
|---|---|---|
| 1 | `biglotto_echo_aware_3bet` | Highest rank, `fallback_equivalent` quality, lowest risk |
| 2 | `daily539_f4cold_5bet` | Second rank, DAILY_539 slot |
| 3 | `daily539_f4cold_3bet` | Third rank, DAILY_539 companion |
| 4 | `power_fourier_rhythm_2bet` | POWER_LOTTO slot, 2-bet only (smallest delta) |
| 5 | `biglotto_ts3_markov_4bet_w30` | Last, `sub_baseline` quality — apply only after 1-4 verified |

---

## 10. Explicit Non-Actions (P126 Governance)

| Action | Status |
|---|---|
| DB writes | **0** |
| scheduler installed | **No** |
| strategy promoted | **No** |
| fabricated rows | **0** |
| 4_STAR included | **No** |
| P108 executed | **No** |
| P117 executed | **No** |
| P118 executed | **No** |
| lottery_v2.db staged | **No** |
| lottery_history.json staged | **No** |

---

## 11. Final Classification

```
P126_DRY_RUN_PLAN_READY
```

**Next action:** Kelvin must provide per-strategy authorization phrases to proceed to P127 apply.
**Next task (if P128 deferred):** Explicitly authorize one-row-per-bet convention, then authorize each of the 5 candidates.
