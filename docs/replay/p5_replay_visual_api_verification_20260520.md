# P5 Replay Visual/API Verification — 2026-05-20

**Branch**: feat/p0-single-repo-stabilization-p1-catalog-plan-20260519  
**Script**: `scripts/p5_replay_visual_api_verification.py`  
**Output**: `outputs/replay/p5_replay_visual_api_verification_20260520.json`  
**Safety**: zero DB writes · read-only · dry_run_only=True

---

## Executive Summary

| Item | Status |
|------|--------|
| Current API can serve ROW_BACKED (460 rows) | ✅ Yes |
| Current API can serve RECONSTRUCTIBLE_PENDING | ❌ No (invisible — no rows in DB yet) |
| Current API can serve NO_DATA state | ❌ No (never returns empty strategies) |
| Current API can serve ARTIFACT_ONLY | ❌ No (not in registry) |
| Missing P3 fields in `/api/replay/history` | `visibility_state`, `display_status`, `should_count_as_success`, `source_trace` |
| Minimal patch applied | ✅ Yes — 4 fields added to history response (non-breaking) |
| UI redesign required | ❌ No |
| Production rows | **460** (unchanged) |

---

## Current API Endpoints

| Endpoint | Purpose | P3 Support |
|----------|---------|-----------|
| `GET /api/replay/strategies` | List 18 registered strategies | Partial (no visibility_state) |
| `GET /api/replay/history` | Paginated replay records from DB | ROW_BACKED only |
| `GET /api/replay/summary` | Aggregated hit-rate per strategy | ROW_BACKED only |
| `GET /api/replay/runs` | Replay run list | N/A |
| `GET /api/replay/freshness` | Data staleness check | N/A |
| `GET /api/replay/strategy-lifecycle` | Full registry snapshot | Lifecycle only |

---

## Field Audit: `/api/replay/history` Response

### Present (27 fields)
All fields a record currently carries.

| Category | Fields |
|----------|--------|
| Identity | `id`, `lottery`, `lottery_type`, `target_draw`, `target_date` |
| Strategy | `strategy_id`, `strategy_name`, `strategy_version`, `lifecycle_status`, `strategy_lifecycle_status` |
| Prediction | `predicted_numbers`, `predicted_special` |
| Result | `actual_numbers`, `actual_special`, `hit_numbers`, `hit_count`, `special_hit` |
| Status | `replay_status`, `reject_reason` |
| Provenance | `truth_level`*, `source`*, `provenance_hash`*, `provenance_source`, `controlled_apply_id` |
| Meta | `replay_run_id`, `generated_at`, `history_cutoff` |

*Fields marked with asterisk are present in schema but NULL for all 460 legacy rows.

### Missing P3 Required Fields (4 fields — gap)

| Field | Type | Needed For |
|-------|------|-----------|
| `visibility_state` | string | Show badge: ROW_BACKED / RECONSTRUCTIBLE / NO_DATA |
| `display_status` | string | Drive UI display mode per record |
| `should_count_as_success` | bool | Prevent fake success inflation |
| `source_trace` | string | Combined provenance chain |

---

## Display State Coverage

| State | API Support | Cell Count | % of P3 Matrix |
|-------|------------|-----------|----------------|
| `SHOW_REPLAY_RESULT` | ✅ via `/history` | 300 | 23.3% |
| `SHOW_RECONSTRUCTIBLE_PENDING` | ❌ invisible | 121 | 9.4% |
| `SHOW_NO_DATA` | ❌ invisible | 867 | 67.3% |
| `SHOW_ARTIFACT_ONLY` | ❌ invisible | 41 strategies | — |

**Only 23.3% of the P3 coverage matrix is currently surfaced by the API.**

---

## Minimal Patch Applied (P5 deliverable)

**Type**: API response field addition — non-breaking.  
**Endpoints affected**: `GET /api/replay/history` only.  
**No DB schema change. No UI restructure. Backward-compatible.**

### 4 New Fields Added to Each History Record

```json
{
  "visibility_state":         "ROW_BACKED",
  "display_status":           "SHOW_REPLAY_RESULT",
  "should_count_as_success":  true,
  "source_trace":             "null (for legacy rows without source/truth_level)"
}
```

For all 460 existing production rows:
- `visibility_state` = `"ROW_BACKED"` (they all come from `strategy_prediction_replays`)
- `display_status` = `"SHOW_REPLAY_RESULT"`
- `should_count_as_success` = `true` if `actual_numbers` and `hit_count` are not NULL
- `source_trace` = combined `source|truth_level|provenance_hash` or `null` for legacy rows

After P7 ONLINE apply (28 new rows):
- New rows will have `source_trace = "P7_CONTROLLED_APPLY|RECONSTRUCTED_FROM_DB_PREDICTION_PAYLOAD|<hash>"`

### What the Patch Does NOT Fix

The patch adds fields to existing rows in the response. It does **not**:
- Surface RECONSTRUCTIBLE strategies in `/history` (they have no DB rows yet)
- Surface NO_DATA strategies (not in `strategy_prediction_replays`)
- Surface ARTIFACT_ONLY strategies (not in registry)

To surface the full P3 matrix in the API/UI, a new endpoint would be needed:
`GET /api/replay/coverage?lottery_type=X` — returns the 1,288-cell matrix.  
**This is deferred to a future phase.**

---

## API Contract: After Patch

`test_replay_api_contract.py` — **44/44 PASS** (no regressions).

The new fields are additive-only. Existing contract tests pass unchanged.

---

## UI Assessment

| Concern | Decision |
|---------|---------|
| Replay UI major redesign | ❌ Deferred — maintain existing history list |
| Add visibility badge to each record | ✅ Feasible using `visibility_state` field |
| Show "Pending" banner for RECONSTRUCTIBLE | ✅ Feasible after P7 apply using `display_status` |
| Show "No data" for NO_DATA strategies | Requires new `/api/replay/coverage` endpoint |
| Fake success prevention | ✅ `should_count_as_success` now exposed |

---

## Safety Confirmation

- ✅ **Zero DB writes** — read-only audit
- ✅ **Zero replay rows generated** — no INSERT
- ✅ **Zero strategy execution** — no predict_func
- ✅ **Production rows = 460** — unchanged
- ✅ **API contract 44/44 PASS** — no regressions from patch
