# P32: Replay UI/API Verification After P31B Production Apply

**Date**: 2026-05-23  
**Phase**: P32  
**Classification**: `P32_REPLAY_POST_P31B_VERIFICATION_MERGED_TO_MAIN`  
**Status**: ✅ PASS  
**Branch**: `p32-replay-verification-after-p31b-apply`

---

## Overview

P32 is a verification-only phase executed after P31B merged to main. Its purpose is to confirm that the 5 DAILY_539 retired strategies inserted in P31B are correctly queryable via API and UI, data quality is intact, and the production DB remains at the P31B baseline of 19960 rows.

**P32 does not write to the production DB.**

---

## P31B Baseline

| Field | Value |
|-------|-------|
| `controlled_apply_id` | `P31B_DAILY539_RETIRED_7500_PROD_20260523` |
| `truth_level` | `DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED` |
| `source` | `P31B_WAVE1_PRODUCTION_APPLY` |
| `replay_run_id` | `p31b_wave1_prod_20260523` |
| Pre-apply rows | 12460 |
| Rows inserted | 7500 |
| Post-apply rows | 19960 |

---

## Wave 1 Strategy IDs (P31B)

| strategy_id | lottery_type | lifecycle | rows |
|-------------|-------------|-----------|------|
| `acb_1bet` | DAILY_539 | RETIRED | 1500 |
| `acb_markov_midfreq` | DAILY_539 | RETIRED | 1500 |
| `acb_markov_midfreq_3bet` | DAILY_539 | RETIRED | 1500 |
| `midfreq_acb_2bet` | DAILY_539 | RETIRED | 1500 |
| `midfreq_fourier_2bet` | DAILY_539 | RETIRED | 1500 |

---

## Verification Results

### 1. DB-Level Verification

| Check | Result |
|-------|--------|
| Total production rows | ✅ 19960 |
| P31B total rows (all 5 strategies) | ✅ 7500 |
| Per-strategy rows (each) | ✅ 1500 |
| lottery_type = DAILY_539 | ✅ All rows |
| dry_run = 0 | ✅ All rows |
| replay_status = PREDICTED | ✅ All rows |
| predicted_numbers length = 5 | ✅ 0 violations |
| predicted_special = NULL | ✅ 0 non-null |
| hit_count == len(hit_numbers) | ✅ 0 mismatches |
| prediction_cutoff_date present | ✅ 0 null |
| prediction_generated_at present | ✅ 0 null |

### 2. Live API Verification (`http://localhost:8002`)

All endpoints tested via `curl` and Python `urllib.request`:

| Endpoint | Strategy | Result |
|----------|----------|--------|
| `/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539` | acb_1bet | ✅ total=1500 |
| `/api/replay/history?strategy_id=acb_markov_midfreq&...` | acb_markov_midfreq | ✅ total=1500 |
| `/api/replay/history?strategy_id=acb_markov_midfreq_3bet&...` | acb_markov_midfreq_3bet | ✅ total=1500 |
| `/api/replay/history?strategy_id=midfreq_acb_2bet&...` | midfreq_acb_2bet | ✅ total=1500 |
| `/api/replay/history?strategy_id=midfreq_fourier_2bet&...` | midfreq_fourier_2bet | ✅ total=1500 |
| `/api/replay/history?lifecycle_status=RETIRED&lottery_type=DAILY_539` | (all) | ✅ total=7500 |
| `/api/replay/history?strategy_id=acb_1bet&lifecycle_status=ONLINE` | acb_1bet | ✅ total=0 |
| `/api/replay/strategy-catalog` | (all 5) | ✅ lifecycle=RETIRED |
| `/api/replay/strategies?lifecycle_status=RETIRED` | (all 5) | ✅ present |

### 3. Pagination Verification

Tested with `acb_1bet`, `page_size=200`:

| Check | Result |
|-------|--------|
| `total` | ✅ 1500 |
| `pages` | ✅ 8 |
| Page 1 records | ✅ 200 |
| Page 2 records | ✅ 200 |
| Draws descending | ✅ Confirmed |

### 4. Data Quality Spot Check

Sample row (`acb_1bet`, draw range: 110000190–115000121):
- `predicted_numbers`: `[2, 15, 26, 30, 34]` (5 numbers ✅)
- `predicted_special`: NULL ✅
- `prediction_cutoff_date`: `"2026/05/16"` (present ✅)
- `prediction_generated_at`: `"2026-05-23T06:14:14.907591+00:00"` ✅

### 5. Catalog Verification

All 5 P31B strategies appear in `/api/replay/strategy-catalog` with:
- `lifecycle_state`: `RETIRED` ✅
- `primary_label`: `retired` ✅

> **Note**: `queryable=False` and `row_count=0` in the catalog are **expected** behavior.  
> The catalog's `row_count` comes from the P24 static inventory (not live DB).  
> The `queryable` field is governed by the P26 label model, which marks RETIRED strategies as non-catalog-queryable.  
> **Live row counts via `/api/replay/history` are the authoritative source** (1500 each ✅).

### 6. UI Smoke Test (`http://localhost:8081`)

Tested with browser automation (Playwright headless):

| Check | Result |
|-------|--------|
| Replay section (`#replay-section`) visible | ✅ |
| Lifecycle dropdown includes `⚪ 退役 (RETIRED)` | ✅ |
| Strategy dropdown shows all 5 as `[RETIRED]` | ✅ |
| Catalog panel shows `RETIRED 5` | ✅ |
| Query DAILY_539 + RETIRED → `共 7500 筆` | ✅ |

### 7. Guard Results

| Guard | Result |
|-------|--------|
| Drift guard (`--strict`) | ✅ PASS, total=19960 |
| Governance guard (`--expected-rows 19960`) | ✅ PASS |

---

## Lifecycle Semantics (Option A)

P31B used **Option A**: retired strategies with `replay_available=True`.

- Strategies remain `RETIRED` in the registry
- Rows are row-backed and queryable via `/api/replay/history`  
- Strategies are **not** promoted to `ONLINE`
- No registry changes in P32

---

## Files

| File | Description |
|------|-------------|
| `tests/test_p32_replay_post_p31b_verification.py` | 30-test verification suite |
| `outputs/replay/p32_replay_post_p31b_verification_20260523.json` | Output artifact |
| `docs/replay/p32_replay_post_p31b_verification_20260523.md` | This document |

---

## Governance

- Production DB: **read-only** throughout P32
- No rows added, modified, or deleted by P32
- Production rows before P32: **19960**
- Production rows after P32: **19960** (unchanged)
- `dry_run` flag: all P31B rows confirmed as `dry_run=0`
