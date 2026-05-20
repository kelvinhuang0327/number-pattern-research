# P6 Catalog Apply Plan v1 — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Script**: `scripts/p6_catalog_apply_plan_v1.py`  
**Tests**: `tests/test_p6_catalog_apply_plan_v1.py` — **31/31 PASS**  
**Output**: `outputs/replay/p6_catalog_apply_plan_v1_20260520.json`  
**Safety**: zero DB writes · zero replay rows · all entries dry_run_only=True

---

## Executive Summary

| Metric | Value |
|--------|-------|
| Total entries in plan | **59** (18 registry + 41 artifact-only) |
| Current production rows | **460** |
| Projected after P7 ONLINE apply | **488** (+28) |
| Projected after ONLINE + RETIRED apply | **581** (+28 +93) |
| CEO phrase received | **NO** |
| Production apply performed | **NO** |

---

## Apply Decision Distribution

| Apply Decision | Count | Description |
|---------------|-------|-------------|
| `SKIP` | **6** | ROW_BACKED — already has rows, no action needed |
| `PLAN_INSERT_PENDING_P7_AUTH` | **2** | ONLINE RECONSTRUCTIBLE — awaiting CEO phrase |
| `PLAN_INSERT_PENDING_HUMAN_REVIEW` | **3** | RETIRED RECONSTRUCTIBLE — needs human review |
| `REGISTER_VISIBILITY_ONLY` | **7** | NO_DATA — mark in catalog, no row generation |
| `SKIP_NOT_REGISTERED` | **41** | ARTIFACT_ONLY — governance review required first |

---

## Decision Detail

### SKIP (6) — Already Done

Strategies with replay rows in `strategy_prediction_replays`. No action needed.

| Strategy ID | Lottery | Rows |
|-------------|---------|------|
| biglotto_deviation_2bet | BIG_LOTTO | 70 |
| biglotto_triple_strike | BIG_LOTTO | 70 |
| daily539_f4cold | DAILY_539 | 90 |
| daily539_markov_cold | DAILY_539 | 90 |
| power_orthogonal_5bet | POWER_LOTTO | 70 |
| power_precision_3bet | POWER_LOTTO | 70 |

---

### PLAN_INSERT_PENDING_P7_AUTH (2) — Awaiting CEO Authorization

**Estimated row delta: +28**

| Strategy ID | Lottery | Lifecycle | Draws | P7 Decision |
|-------------|---------|-----------|-------|-------------|
| fourier_rhythm_3bet | POWER_LOTTO | ONLINE | 12 | PLAN_INSERT |
| ts3_regime_3bet | BIG_LOTTO | ONLINE | 16 | PLAN_INSERT |

**Required**: CEO authorization phrase: `YES apply P7 controlled replay rows`  
**Status**: NOT RECEIVED — apply blocked.

Apply command (when authorized):
```bash
.venv/bin/python scripts/p7_controlled_replay_row_apply.py \
  --apply --scope ONLINE_ONLY \
  --backup backups/lottery_v2_pre_p7_controlled_apply_20260520.db \
  --expected-rows 460
```

---

### PLAN_INSERT_PENDING_HUMAN_REVIEW (3) — Awaiting Human Review

**Estimated row delta: +93**

| Strategy ID | Lottery | Lifecycle | Draws | P7 Decision |
|-------------|---------|-----------|-------|-------------|
| acb_1bet | DAILY_539 | RETIRED | 31 | PLAN_MANUAL_REVIEW_REQUIRED |
| acb_markov_midfreq_3bet | DAILY_539 | RETIRED | 31 | PLAN_MANUAL_REVIEW_REQUIRED |
| midfreq_acb_2bet | DAILY_539 | RETIRED | 31 | PLAN_MANUAL_REVIEW_REQUIRED |

**Required**:
1. Human review of 93 lifecycle warnings in P7 JSON
2. Separate CEO authorization (distinct from the ONLINE phrase)
3. Run flags: `--scope INCLUDE_RETIRED_WITH_WARNING --include-retired-reviewed`

**Status**: NOT AUTHORIZED — apply blocked.

---

### REGISTER_VISIBILITY_ONLY (7) — NO_DATA

In runtime registry, but no `prediction_items` in DB and no replay rows.  
**No row generation possible without re-running strategy logic (blocked).**

These should be marked as `NO_DATA` in any catalog/coverage UI display.

| Strategy ID | Lottery | Lifecycle | Why NO_DATA |
|-------------|---------|-----------|------------|
| biglotto_ts3_acb_4bet | BIG_LOTTO | REJECTED | Governance rejected; no predictions made |
| biglotto_ts3_markov_freq_5bet | BIG_LOTTO | REJECTED | Governance rejected; no predictions made |
| power_shlc_midfreq | POWER_LOTTO | REJECTED | Governance rejected; no predictions made |
| p1_deviation_2bet_539 | DAILY_539 | REJECTED | Governance rejected; no predictions made |
| acb_markov_midfreq | DAILY_539 | RETIRED | 0 prediction_items in DB |
| midfreq_fourier_2bet | DAILY_539 | RETIRED | 0 prediction_items in DB |
| h6_gate_mk20_ew85 | POWER_LOTTO | OBSERVATION | Shadow eval only; no predictions produced |

**Rule**: NO_DATA strategies must never be counted as replay successes.

---

### SKIP_NOT_REGISTERED (41) — ARTIFACT_ONLY

Not in runtime registry. Exist only as artifact files (primarily `rejected/*.json`).

All 41 entries sourced from P1 `artifact_candidates_extra`.  
None can be inserted into replay rows without:
1. Governance review
2. Registry registration
3. Separate authorization

**HARD RULE**: ARTIFACT_ONLY strategies must never be marked ONLINE via P6.

---

## Authorization Gate Summary

| Auth Gate | Status | Required Action |
|-----------|--------|----------------|
| CEO phrase `YES apply P7 controlled replay rows` | ❌ Not received | Blocks PLAN_INSERT_PENDING_P7_AUTH (2 strategies, 28 rows) |
| Human review + RETIRED flags | ❌ Not received | Blocks PLAN_INSERT_PENDING_HUMAN_REVIEW (3 strategies, 93 rows) |
| Artifact governance review | ❌ Not started | Blocks SKIP_NOT_REGISTERED (41 strategies) |

**No apply performed in this plan.**

---

## P3 Coverage Impact Projection

| Scenario | ROW_BACKED | RECONSTRUCTIBLE | NO_DATA |
|----------|-----------|-----------------|---------|
| Now (460 rows) | 300 (23.3%) | 121 (9.4%) | 867 (67.3%) |
| After P7 ONLINE (488 rows) | **328 (25.5%)** | 93 (7.2%) | 867 (67.3%) |
| After ONLINE + RETIRED (581 rows) | **421 (32.7%)** | 0 (0%) | 867 (67.3%) |
| After all registry strategies covered | **421 (32.7%)** | 0 (0%) | **867 (67.3%)** |

**The 867 NO_DATA cells are permanent structural gaps** — they represent draws where
strategies were not active or no predictions were made, and cannot be filled without
fabricating data.

---

## Safety Confirmation

- ✅ **Zero DB writes** — plan is read-only from P2/P3 JSON
- ✅ **Zero replay rows generated** — no INSERT SQL in script
- ✅ **Zero strategy execution** — no predict_func calls
- ✅ **Zero draw imports** — no external data
- ✅ **Production rows = 460** — unchanged
- ✅ **No ARTIFACT_ONLY marked ONLINE** — governance gate enforced
- ✅ **No NO_DATA counted as success** — fake_success_count = 0
- ✅ **No authorization received** — all apply decisions blocked correctly
- ✅ **31/31 tests PASS**
