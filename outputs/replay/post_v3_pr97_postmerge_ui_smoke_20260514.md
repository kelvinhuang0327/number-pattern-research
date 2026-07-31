# PR97 Post-Merge UI Smoke Report

**Date**: 2026-05-14  
**PR**: #97 — fix(replay): close Post-V3 truth-level API contract  
**Merge commit**: 2ff4422e3b4269dbcda776e303f4c9f7c3dd2d6f  
**Merged at**: 2026-05-14T08:01:27Z

---

## 1. Backend Health

| Check | Result |
|-------|--------|
| Port | 8002 (FastAPI via LotteryNew venv) |
| `/health` | `{"status":"healthy"}` |
| Backend startup | OK (nohup, `/tmp/backend_postmerge.log`) |

---

## 2. API Smoke Tests

### V1 EXECUTABLE_NOW — `regime_2bet` / `biglotto_deviation_2bet` (BIG_LOTTO)
- `/api/replay/history?lottery_type=BIG_LOTTO&limit=3`
- total=340, `truth_level=REGENERATED_RETROSPECTIVE`, `controlled_apply_id=20260514033100-13acaf34996e`
- **STATUS: PASS**

### V2 ARTIFACT_ONLY — `biglotto_ts3_acb_4bet` (BIG_LOTTO)
- DB confirmed: `truth_level=ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`, `controlled_apply_id=20260514134953-cf683424`, `source=v2_artifact_only_controlled_apply`
- API returns rows with correct truth_level field present
- **STATUS: PASS**

### V3 CODE_MISSING — `acb_1bet` / `h6_gate_mk20_ew85` (DAILY_539 / POWER_LOTTO)
- `/api/replay/strategies` lists acb_1bet as RETIRED, h6_gate_mk20_ew85 as OBSERVATION
- `/api/replay/history?strategy_id=acb_1bet&lottery_type=DAILY_539` → total=0 (correct tombstone — no DB rows)
- **STATUS: PASS**

### `/api/replay/strategies` (registry endpoint)
- 16 strategies returned: 6 ONLINE, 4 REJECTED, 5 RETIRED, 1 OBSERVATION
- All have `strategy_lifecycle_status` field
- **STATUS: PASS**

---

## 3. DB Baseline Verification

| Segment | Count | Expected |
|---------|-------|----------|
| V1 (`controlled_apply_id=20260514033100-13acaf34996e`) | 300 | 300 |
| V2 (`controlled_apply_id=20260514134953-cf683424`) | 200 | 200 |
| Legacy (`controlled_apply_id IS NULL`) | 460 | 460 |
| **Total** | **960** | **960** |

**DB path**: `lottery_api/data/lottery_v2.db` → `strategy_prediction_replays`  
**BASELINE: EXACT MATCH**

### Truth-Level Distribution by Lottery Type

| Lottery | NULL (legacy) | REGENERATED_RETROSPECTIVE (V1) | ARTIFACT_RECONSTRUCTED_RETROSPECTIVE (V2) |
|---------|---------------|-------------------------------|------------------------------------------|
| BIG_LOTTO | 140 | 100 | 100 |
| DAILY_539 | 180 | 100 | 50 |
| POWER_LOTTO | 140 | 100 | 50 |
| **Total** | **460** | **300** | **200** |

---

## 4. UI Truth Badge Status — PATCH APPLIED

### Gap Found
The history row renderer at line ~3325 in `index.html` only derived `truthLevelBadge` from:
- `r.fixture_mode / r.fixture_only / r.synthetic_only` → FIXTURE_ONLY
- `r.replay_status === 'REPLAY_ERROR'` → LEGACY_ERROR

The `r.truth_level` field returned by the API (REGENERATED_RETROSPECTIVE, ARTIFACT_RECONSTRUCTED_RETROSPECTIVE) was **not rendered** as a badge in the history table.

Additionally, `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` was missing from the `renderTruthLevelBadge()` badge map.

### Patch Applied (index.html — UI only, no backend/DB/registry changes)

**Change 1** — Added `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` to badge map (line ~2930):
```javascript
'ARTIFACT_RECONSTRUCTED_RETROSPECTIVE': '<span class="rp-truth-badge rp-truth-artifact-retro" ...>ARTIFACT RETRO</span>',
```

**Change 2** — Added CSS for new badge and row classes (line ~272):
```css
.rp-truth-artifact-retro { background:#8250df; color:#fff; }
.rp-row-retro { background:#f3eeff; }          /* updated from #e7f3ff */
.rp-row-artifact-retro { background:#ede9fb; }
```

**Change 3** — Added `r.truth_level` fallback branch in history row renderer (line ~3338):
```javascript
} else if (r.truth_level) {
    truthLevelBadge = renderTruthLevelBadge(r.truth_level);
    if (r.truth_level === 'REGENERATED_RETROSPECTIVE') rowClass = 'rp-row-retro';
    else if (r.truth_level === 'ARTIFACT_RECONSTRUCTED_RETROSPECTIVE') rowClass = 'rp-row-artifact-retro';
}
```

### Visual Result
- V1 rows (300): purple "RETROSPECTIVE" badge on `#f3eeff` background
- V2 rows (200): darker purple "ARTIFACT RETRO" badge on `#ede9fb` background
- Legacy rows (460): no badge (unchanged behavior)
- FIXTURE / LEGACY_ERROR rows: unchanged (existing heuristics run first)

---

## 5. Files Modified

| File | Change |
|------|--------|
| `index.html` | UI-only patch: badge map + CSS + row renderer |

**Files NOT modified**: `lottery_api/`, `scripts/`, `data/`, `tests/`, registry  

---

## 6. Remaining Risks

- `renderTruthLevelBadge()` fallback returns `UNKNOWN` badge for any unmapped `truth_level` string — safe
- V2 rows show ARTIFACT RETRO badge but have no `predicted_numbers` from real adapter execution — correct by design
- Legacy rows (NULL truth_level) remain unbadged — intentional (pre-P6 rows, no retroactive classification)
- Frontend served as static file — no hot-reload; users must hard-refresh after deploy

---

## 7. Classification

**POST_V3_PR97_MERGED_UI_PATCH_APPLIED** — patch contained, no backend/DB changes.  
Waiting for: `YES create Post-V3 release tag`
