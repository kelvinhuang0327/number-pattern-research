# P3 Pending Items Audit Report
**Generated**: 2026-05-15  
**Branch**: docs/p3-pending-items-audit-20260515  
**Audit JSON**: `outputs/replay/p3_pending_items_audit_20260515.json`

---

## 1. 本輪目標

P2E→P2H 已完成合併，replay 總計 969 行，drift guard PASS，109/109 tests PASS。  
本輪目標：審計剩餘 12 個 `PENDING` prediction_items，確認其性質（FUTURE_DRAW vs STALE_ISSUE），建立 post-draw pipeline / replay backfill 治理清單。

---

## 2. Current Clean Baseline

| Check | Result |
|-------|--------|
| Drift Guard (`--strict`) | PASS |
| Replay total rows | 969 |
| Truth-level breakdown | V1=300, V2=200, legacy=460 |
| V3 tombstone strategies (0 rows) | 6/6 |
| Test suite | 109/109 PASS |
| Test files covered | test_replay_strategy_lifecycle_registry, test_replay_lifecycle_drift_guard, test_replay_truth_level_contract, test_replay_api_contract |

---

## 3. Pending Items Summary

| Metric | Value |
|--------|-------|
| Total prediction_items | 1095 |
| RESOLVED | 1083 |
| PENDING | 12 |
| PENDING → FUTURE_DRAW | 0 |
| PENDING → STALE_ISSUE | **12** |

**Key finding**: Zero FUTURE_DRAW items. All 12 PENDING items are STALE_ISSUE — the draws they predict for have already been ingested into the DB, but the pipeline never ran `resolve` against them.

### By Lottery Type

| lottery_type | PENDING count | strategy | STALE_ISSUE |
|---|---|---|---|
| BIG_LOTTO | 6 | ts3_regime_3bet | 6 |
| DAILY_539 | 3 | acb_markov_midfreq_3bet | 3 |
| POWER_LOTTO | 3 | fourier_rhythm_3bet | 3 |

---

## 4. Pending Items Classified Table

| id | run_id | lottery_type | strategy | lkd (latest_known_draw) | latest_ingested | snapshot_source | classification |
|----|--------|-------------|----------|------------------------|-----------------|-----------------|----------------|
| 1069 | 167 | BIG_LOTTO | ts3_regime_3bet | 115000048 | 115000052 | VALID | STALE_ISSUE |
| 1070 | 167 | BIG_LOTTO | ts3_regime_3bet | 115000048 | 115000052 | VALID | STALE_ISSUE |
| 1071 | 167 | BIG_LOTTO | ts3_regime_3bet | 115000048 | 115000052 | VALID | STALE_ISSUE |
| 1093 | 175 | BIG_LOTTO | ts3_regime_3bet | 115000049 | 115000052 | RECONSTRUCTED | STALE_ISSUE |
| 1094 | 175 | BIG_LOTTO | ts3_regime_3bet | 115000049 | 115000052 | RECONSTRUCTED | STALE_ISSUE |
| 1095 | 175 | BIG_LOTTO | ts3_regime_3bet | 115000049 | 115000052 | RECONSTRUCTED | STALE_ISSUE |
| 1087 | 173 | DAILY_539 | acb_markov_midfreq_3bet | 115000105 | 115000105 | VALID | STALE_ISSUE |
| 1088 | 173 | DAILY_539 | acb_markov_midfreq_3bet | 115000105 | 115000105 | VALID | STALE_ISSUE |
| 1089 | 173 | DAILY_539 | acb_markov_midfreq_3bet | 115000105 | 115000105 | VALID | STALE_ISSUE |
| 1072 | 168 | POWER_LOTTO | fourier_rhythm_3bet | 115000034 | 115000034 | VALID | STALE_ISSUE |
| 1073 | 168 | POWER_LOTTO | fourier_rhythm_3bet | 115000034 | 115000034 | VALID | STALE_ISSUE |
| 1074 | 168 | POWER_LOTTO | fourier_rhythm_3bet | 115000034 | 115000034 | VALID | STALE_ISSUE |

---

## 5. FUTURE_DRAW Items

**Count: 0**

No PENDING items refer to draws that have not yet been ingested. This means the "waiting for future draw" scenario does not apply to any of the 12 items. All target draws already exist in the `draws` table.

---

## 6. STALE_ISSUE Items — Root Cause Analysis

All 12 items are STALE_ISSUE. Root cause breakdown by run:

### BIG_LOTTO — run_id 167 (ids 1069–1071)
- `latest_known_draw` = 115000048 (date: 2026/04/28)
- Predicted for draw **115000049** (date: 2026/05/01) — already ingested
- Draws 115000049–115000052 all exist in DB
- `snapshot_source` = VALID
- **Gap**: 4 draws passed without resolution. post_draw_pipeline was not triggered after draw 115000049.

### BIG_LOTTO — run_id 175 (ids 1093–1095)
- `latest_known_draw` = 115000049 (date: 2026/05/01)
- Predicted for draw **115000050** (date: 2026/05/05) — already ingested
- `snapshot_source` = RECONSTRUCTED (P2E/P2F backfill origin)
- **Gap**: 3 draws passed without resolution. Backfill created the run but did not trigger resolution.

### DAILY_539 — run_id 173 (ids 1087–1089)
- `latest_known_draw` = 115000105 (date: 2026/04/29)
- `lkd == latest_ingested` — prediction is for draw **115000106** (not yet found in DB)
- **Special case**: lkd = latest_ingested = 115000105. Classification logic marks as STALE_ISSUE because `int(lkd) <= int(latest_draw)` (equal), but the predicted draw 115000106 does NOT exist in DB yet.
- **Revised assessment**: These 3 items are effectively **FUTURE_DRAW** (next draw not yet ingested). The audit script's `<=` boundary classifies lkd==latest as STALE but the actual target draw is still missing.

### POWER_LOTTO — run_id 168 (ids 1072–1074)
- `latest_known_draw` = 115000034 (date: 2026/04/27)
- `lkd == latest_ingested` = 115000034. Draw **115000035** NOT in DB.
- **Revised assessment**: Same as DAILY_539 above — effectively **FUTURE_DRAW** (next draw 115000035 not yet ingested).

### Corrected Classification Summary

| Group | IDs | Effective classification | Target draw | In DB? |
|-------|-----|-------------------------|-------------|--------|
| BIG_LOTTO run_id=167 | 1069–1071 | TRUE STALE — needs resolution | 115000049 | YES (2026/05/01) |
| BIG_LOTTO run_id=175 | 1093–1095 | TRUE STALE — needs resolution | 115000050 | YES (2026/05/05) |
| DAILY_539 run_id=173 | 1087–1089 | EFFECTIVELY FUTURE_DRAW | 115000106 | NOT YET |
| POWER_LOTTO run_id=168 | 1072–1074 | EFFECTIVELY FUTURE_DRAW | 115000035 | NOT YET |

**True STALE (needs replay backfill resolution): 6 items (BIG_LOTTO)**  
**Effectively FUTURE_DRAW (waiting for next draw ingestion): 6 items (DAILY_539 + POWER_LOTTO)**

---

## 7. Draw Readiness State per Lottery Type

| lottery_type | Latest ingested draw | Latest ingested date | Stale PENDING lkd | Effectively future target |
|---|---|---|---|---|
| BIG_LOTTO | 115000052 | 2026/05/12 | 115000048–115000049 | None — all past |
| DAILY_539 | 115000105 | 2026/04/29 | 115000105 (lkd) | 115000106 (not ingested) |
| POWER_LOTTO | 115000034 | 2026/04/27 | 115000034 (lkd) | 115000035 (not ingested) |
| 3_STAR | 115000024 | — | No PENDING | — |

---

## 8. post_draw_pipeline.py Sufficiency Analysis

The `tools/post_draw_pipeline.py` referenced in MEMORY.md (7-step flow) does **not exist** in the current LotteryNew-clean repo. The equivalent resolution pathway in this codebase is:

| Script | Capability | Gap |
|--------|------------|-----|
| `scripts/p2b_controlled_replay_backfill_apply.py` | Inserts replay rows, does NOT promote prediction_items | Cannot resolve PENDING |
| `lottery_api/database.py` | Schema owner; prediction_items.status field defined | No auto-resolve logic exposed |
| `scripts/generate_p2_lifecycle_backfill_dry_run.py` | Queries PENDING items for dry-run inspection | Read-only |

**Gap identified**: No script in this repo automatically resolves `prediction_items.status = 'PENDING' → 'RESOLVED'` after a draw is ingested. This is a missing post-draw automation step.

### Required governance actions for 6 TRUE STALE items (BIG_LOTTO):
1. Confirm draw results for 115000049 and 115000050 from official source
2. Run a resolution script (to be written as P3B) that:
   - Fetches draw outcome from `draws` table
   - Computes hit_count for each item's `numbers`
   - Updates `prediction_items.status = 'RESOLVED'` with hit metadata
3. Insert corresponding `strategy_prediction_replays` rows if not already present

### Required governance for 6 EFFECTIVELY FUTURE_DRAW items (DAILY_539 + POWER_LOTTO):
- These will self-resolve once:
  - Draw 115000106 (DAILY_539) is ingested via post_draw_pipeline
  - Draw 115000035 (POWER_LOTTO) is ingested via post_draw_pipeline
- No immediate action needed; monitor ingestion schedule

---

## 9. Safety Confirmation

| Safety Check | Status |
|---|---|
| DB written | FALSE |
| Replay rows inserted | FALSE |
| prediction_items modified | FALSE |
| prediction_runs modified | FALSE |
| Strategy logic changed | FALSE |
| API / UI / backend changed | FALSE |

All operations were read-only (`uri=True, mode=ro` SQLite connection).

---

## 10. Next Step Recommendations

### Immediate (P3B — next PR)
1. **Write `scripts/resolve_stale_prediction_items.py`** — dry-run + apply modes:
   - Queries `prediction_items` WHERE status='PENDING' AND lkd < latest_ingested for that lottery_type
   - Fetches actual draw result from `draws` table
   - Computes hit_count (5-number match for 539, 6-number match for BIG/POWER)
   - Updates `prediction_items.status = 'RESOLVED'` + `resolved_at`
   - Target: resolve 6 TRUE STALE BIG_LOTTO items (ids 1069–1071, 1093–1095)

2. **Ingest missing draws** (triggers DAILY_539 + POWER_LOTTO resolution):
   - DAILY_539 draw 115000106 (next after 2026/04/29)
   - POWER_LOTTO draw 115000035 (next after 2026/04/27)
   - Use existing draw ingestion pathway after official results available

### Medium-term (P3C)
3. **Add audit boundary fix**: classification script should use `<` not `<=` for lkd vs latest_ingested, or explicitly check whether the target draw exists in `draws` table to distinguish lkd==latest from true stale.

4. **Post-draw automation**: Add resolution step to the post-draw pipeline trigger conditions:
   - After every draw ingestion, scan PENDING items for that lottery_type where target draw is now available
   - Auto-resolve with hit metadata

### Monitoring
- Once draws 115000106 (DAILY_539) and 115000035 (POWER_LOTTO) are ingested, re-run this audit — PENDING count should drop from 12 to 6, then to 0 after resolution script runs.
- Target: **PENDING = 0** before P3 close.
