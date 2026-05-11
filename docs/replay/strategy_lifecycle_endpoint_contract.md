# Strategy Lifecycle Endpoint Contract

**Version:** P10 (2026-05-11)  
**Endpoint:** `GET /api/replay/strategy-lifecycle`  
**Implemented in:** `lottery_api/routes/replay.py`  
**Router registered in:** `lottery_api/app.py` (tag: `Replay`)

---

## 1. Purpose

Returns a **read-only snapshot** of the complete strategy lifecycle registry.  
All data is sourced from the in-memory registry (`lottery_api/models/replay_strategy_registry.py`).

This endpoint is the single authoritative source for:

- Which strategies are currently ONLINE (executable)
- Which strategies are classified as REJECTED / RETIRED / OBSERVATION (non-executable)
- Lifecycle counts summary

---

## 2. Hard Constraints

| Constraint | Value |
|---|---|
| DB write | **NEVER** — no `sqlite3.connect` in endpoint body |
| Replay backfill | **NEVER** |
| Strategy promotion | **NEVER** |
| Scheduler trigger | **NEVER** |
| Non-ONLINE → executable | **NEVER** |
| HTTP method | GET only (read-only) |

---

## 3. Response Schema

```json
{
  "total":                      <integer>,
  "lifecycle_counts":           <object>,
  "executable_strategy_ids":    <array of string>,
  "non_executable_strategy_ids":<array of string>,
  "strategies":                 <array of strategy objects>,
  "no_db_write":                <boolean — always true>,
  "no_db_write_note":           <string>,
  "marker":                     <string>,
  "disclaimer":                 <string>
}
```

### 3a. `lifecycle_counts` schema

```json
{
  "ONLINE":      <integer>,
  "REJECTED":    <integer>,
  "RETIRED":     <integer>,
  "OBSERVATION": <integer>
}
```

### 3b. Strategy object schema

Each entry in `strategies` contains exactly:

```json
{
  "strategy_id":              <string>,
  "strategy_name":            <string>,
  "strategy_version":         <string>,
  "supported_lottery_types":  <array of string>,
  "min_history":              <integer or null>,
  "lifecycle_status":         <string — one of: ONLINE, REJECTED, RETIRED, OBSERVATION>,
  "is_executable":            <boolean>
}
```

No callable objects, no adapter references, no DB handles appear in strategy entries.

---

## 4. Expected Lifecycle Counts (Stable Registry State)

| Status | Count |
|---|---|
| ONLINE | 6 |
| REJECTED | 4 |
| RETIRED | 5 |
| OBSERVATION | 1 |
| **total** | **16** |

`executable_strategy_ids` length: **6** (ONLINE only)  
`non_executable_strategy_ids` length: **10** (all non-ONLINE)

---

## 5. Response Marker

```
marker: "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY"
```

---

## 6. Example Response (abbreviated)

```json
{
  "total": 16,
  "lifecycle_counts": {
    "ONLINE": 6,
    "REJECTED": 4,
    "RETIRED": 5,
    "OBSERVATION": 1
  },
  "executable_strategy_ids": [
    "biglotto_deviation_2bet",
    "biglotto_triple_strike",
    "daily539_f4cold",
    "daily539_markov_cold",
    "power_orthogonal_5bet",
    "power_precision_3bet"
  ],
  "non_executable_strategy_ids": [
    "h6_gate_mk20_ew85",
    "biglotto_ts3_acb_4bet",
    "..."
  ],
  "strategies": [
    {
      "strategy_id": "power_precision_3bet",
      "strategy_name": "威力彩 Precision 3注",
      "strategy_version": "v0.1",
      "supported_lottery_types": ["POWER_LOTTO"],
      "min_history": 100,
      "lifecycle_status": "ONLINE",
      "is_executable": true
    },
    {
      "strategy_id": "h6_gate_mk20_ew85",
      "strategy_name": "H6 Gate MK20 EW85",
      "strategy_version": "v0.1",
      "supported_lottery_types": [],
      "min_history": null,
      "lifecycle_status": "OBSERVATION",
      "is_executable": false
    }
  ],
  "no_db_write": true,
  "no_db_write_note": "All data sourced from in-memory registry. No sqlite3 connection opened. No replay execution performed.",
  "marker": "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY",
  "disclaimer": "..."
}
```

---

## 7. Frontend Usage

The lifecycle registry card in `index.html` (`id="rp-lifecycle-registry-card"`) consumes this endpoint:

- **Function:** `rpLoadLifecycleRegistry()` — auto-called when user navigates to replay section
- **Badges rendered:** `rp-lc-badge-online`, `rp-lc-badge-rejected`, `rp-lc-badge-retired`, `rp-lc-badge-obs`
- **Table:** `rp-lc-table` / `rp-lc-tbody` — one row per strategy entry
- **XSS protection:** All server data passed through `_esc()` before `innerHTML` assignment

---

## 8. Explicitly Prohibited UI Actions

The lifecycle dashboard card **must not** contain any of the following actions:

| Prohibited Action | Reason |
|---|---|
| Promote strategy | Would change lifecycle state — not allowed |
| Retire strategy | Would change lifecycle state — not allowed |
| Backfill replay history | Would write to DB — not allowed |
| Run replay | Would execute strategy — not allowed |
| Scheduler trigger | Would launch cron/scheduler — not allowed |

---

## 9. Governance Markers

```
P7_STRATEGY_LIFECYCLE_ENDPOINT_READY
P10_LIFECYCLE_ENDPOINT_CONTRACT_DOC_READY
```

---

## 10. Related Files

| File | Role |
|---|---|
| `lottery_api/routes/replay.py` | Endpoint implementation |
| `lottery_api/models/replay_strategy_registry.py` | In-memory registry data source |
| `tests/test_replay_strategy_lifecycle_endpoint.py` | P7 endpoint tests (26 tests) |
| `tests/test_replay_strategy_lifecycle_contract.py` | P10 contract / snapshot tests |
| `tests/test_replay_strategy_lifecycle_dashboard_static.py` | P10 dashboard static smoke |
| `index.html` | Frontend lifecycle card |
