# P3 Replay Catalog API/UI Contract

Generated: 2026-05-20  
Phase: P3  
Status: DRY_RUN — strategy_catalog table NOT applied; all entries from P2/P1 dry-run JSON fallback

---

## 1. API Contract

### Source Module
- `lottery_api/services/replay_catalog_source.py` — catalog source adapter (read-only)
- `lottery_api/models/replay_catalog_api_contract.py` — response contract / builder

### Catalog Source Priority
```
1. Live DB strategy_catalog table  (P2 --apply required, NOT yet done)
2. outputs/replay/p2_catalog_apply_dry_run_20260520.json  ← current fallback
3. outputs/replay/p1_catalog_visibility_plan_20260519.json
```

### List Response Shape

```json
{
  "items": [...],
  "total": 59,
  "source_used": "p2_json",
  "filter_visibility": null,
  "filter_lifecycle": null,
  "summary_by_visibility": {
    "REGISTERED_WITH_REPLAY_ROWS": 6,
    "RECONSTRUCTIBLE": 12,
    "ARTIFACT_CANDIDATE": 41
  },
  "summary_by_lifecycle": {
    "ONLINE": 8,
    "NOT_REGISTERED": 41,
    "RETIRED": 5,
    "REJECTED": 4,
    "OBSERVATION": 1
  },
  "dry_run_only": true
}
```

### Per-Strategy Item Shape

```json
{
  "strategy_id": "power_precision_3bet",
  "display_name": "威力彩 Precision 3注",
  "lottery_type": "POWER_LOTTO",
  "lifecycle_state": "ONLINE",
  "catalog_visibility_state": "REGISTERED_WITH_REPLAY_ROWS",
  "has_replay_rows": true,
  "has_historical_predictions": false,
  "reconstructible_reason": null,
  "no_data_reason": null,
  "artifact_source_type": "CODE_SCAN",
  "source_paths": ["lottery_api/models/replay_strategy_registry.py"],
  "provenance_hash": null,
  "dry_run_only": true,
  "readiness": {
    "is_catalog_visible": true,
    "can_show_replay_rows": true,
    "can_show_no_data_message": false,
    "can_enter_reconstruction_queue": false,
    "is_artifact_only": false,
    "is_production_strategy": true
  },
  "state_message": {
    "summary": "有歷史預測資料",
    "detail": "...",
    "badge": "Has replay rows",
    "badge_zh": "可查看歷史預測",
    "can_show_replay": true,
    "is_success": true
  }
}
```

### Supported Filters
| Parameter | Values |
|-----------|--------|
| `filter_visibility` | `REGISTERED_WITH_REPLAY_ROWS`, `RECONSTRUCTIBLE`, `REGISTERED_NO_DATA`, `ARTIFACT_CANDIDATE`, `UNSUPPORTED` |
| `filter_lifecycle` | `ONLINE`, `OFFLINE`, `OBSERVATION`, `REJECTED`, `RETIRED`, `NOT_REGISTERED` |

---

## 2. UI Badge / State Mapping

| Visibility State | Badge (EN) | Badge (ZH) | Variant |
|-----------------|-----------|-----------|---------|
| `REGISTERED_WITH_REPLAY_ROWS` | Has replay rows | 可查看歷史預測 | `success` |
| `RECONSTRUCTIBLE` | Reconstructible | 可重建 / 尚未補資料 | `info` |
| `REGISTERED_NO_DATA` | No historical data | 無歷史資料 | `warning` |
| `ARTIFACT_CANDIDATE` | Artifact only | Artifact only / 未進 runtime | `muted` |
| `UNSUPPORTED` | Unsupported | 不支援 | `disabled` |

TypeScript source: `frontend/src/replay/replayCatalogState.ts`

---

## 3. Visibility State Semantics

### REGISTERED_WITH_REPLAY_ROWS
- Strategy is in DB registry **and** has ≥1 replay row
- `can_show_replay_rows = true`
- `is_success = true`
- Count: **6 strategies** (2 BIG_LOTTO, 2 POWER_LOTTO, 2 DAILY_539)

### RECONSTRUCTIBLE
- Strategy is registered or has artifact/log; rows **not yet backfilled**
- `can_show_replay_rows = false` — **never replay success**
- `can_enter_reconstruction_queue = true`
- Rows can be rebuilt in P5-P7 Historical Reconstruction
- Count: **12 strategies**

### REGISTERED_NO_DATA
- Strategy is in DB registry but has zero replay rows and no usable artifact
- `can_show_replay_rows = false`
- `can_show_no_data_message = true`
- Count: 0 in P2 dry-run (absorbed into RECONSTRUCTIBLE or UNSUPPORTED)

### ARTIFACT_CANDIDATE
- Found in code/artifact/rejected-JSON scan but **NOT in runtime registry**
- `is_artifact_only = true`
- `can_show_replay_rows = false`
- **Must NOT be treated as ONLINE or production**
- Count: **41 strategies** (mainly rejected strategies from `rejected/*.json`)

### UNSUPPORTED
- No artifact, no replay rows, no reconstruction path
- `can_show_no_data_message = true`
- Count: 0 in P2 dry-run

---

## 4. Which States Can Show Replay Rows

| State | can_show_replay_rows |
|-------|---------------------|
| `REGISTERED_WITH_REPLAY_ROWS` | ✅ YES |
| `RECONSTRUCTIBLE` | ❌ NO — shows reconstruction queue status |
| `REGISTERED_NO_DATA` | ❌ NO — shows no-data message |
| `ARTIFACT_CANDIDATE` | ❌ NO — shows artifact-only badge |
| `UNSUPPORTED` | ❌ NO — shows unsupported message |

---

## 5. Which States Show No-Data / Reconstructible Message

| State | can_show_no_data_message | can_enter_reconstruction_queue |
|-------|--------------------------|-------------------------------|
| `REGISTERED_NO_DATA` | ✅ | ❌ |
| `UNSUPPORTED` | ✅ | ❌ |
| `RECONSTRUCTIBLE` | ❌ | ✅ |
| `ARTIFACT_CANDIDATE` | ❌ | ❌ |
| `REGISTERED_WITH_REPLAY_ROWS` | ❌ | ❌ |

---

## 6. Hard Constraints Enforced

- `RECONSTRUCTIBLE` → `can_show_replay_rows = False` (enforced in readiness flags + tests)
- `ARTIFACT_CANDIDATE` → `is_artifact_only = True`, lifecycle must not be `ONLINE`
- `NO_DATA / UNSUPPORTED` → `can_show_replay_rows = False`
- `dry_run_only = True` for all fallback-JSON-sourced entries
- No DB writes in catalog load or API response build
