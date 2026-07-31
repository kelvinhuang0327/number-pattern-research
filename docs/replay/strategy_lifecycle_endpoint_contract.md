# Strategy Lifecycle Endpoint Contract

**Version:** P11 (2026-05-11)  
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

## 2. Formal Lifecycle States

This endpoint recognises exactly **4 formal lifecycle states**:

| State | Meaning | Executable? |
|---|---|---|
| `ONLINE` | Active strategy, eligible for replay execution | ✅ Yes |
| `OBSERVATION` | Under observation — not yet classified | ❌ No |
| `REJECTED` | Validation failed — permanently non-executable | ❌ No |
| `RETIRED` | Deprecated / decommissioned — permanently non-executable | ❌ No |

`lifecycle_status` in every response object **must** be one of these 4 values. No other value is permitted.

### OFFLINE — Not a Formal State

`OFFLINE` is **not** a formal lifecycle state in this system.

| Prohibition | Detail |
|---|---|
| Endpoint response | Must **never** return `OFFLINE` as `lifecycle_status` |
| `lifecycle_counts` schema | Must **not** contain an `OFFLINE` key |
| UI filter | Must **not** add an OFFLINE filter option |
| Registry | Must **not** introduce an OFFLINE strategy state |
| Fixture mode | Must **not** add OFFLINE synthetic rows |
| Docs | Must **not** promote OFFLINE as a valid state |
| Agent self-introduction | Must **not** self-introduce OFFLINE without CTO YES gate |

Future introduction of OFFLINE requires all of the following prerequisites (none currently met):

1. Dedicated SOP for OFFLINE transition
2. Formal state transition rules (ONLINE → OFFLINE, OFFLINE → ONLINE)
3. UI semantics and filter design
4. Complete test coverage
5. Registry schema update
6. `lifecycle_counts` schema update
7. Explicit CTO YES gate

---

## 3. Hard Constraints

| Constraint | Value |
|---|---|
| DB write | **NEVER** — no `sqlite3.connect` in endpoint body |
| Replay backfill | **NEVER** |
| Strategy promotion | **NEVER** |
| Scheduler trigger | **NEVER** |
| Non-ONLINE → executable | **NEVER** |
| HTTP method | GET only (read-only) |

---

## 4. Response Schema

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

## 5. Expected Lifecycle Counts (Stable Registry State)

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

## 6. Fixture Mode Scope

The endpoint supports an optional `fixture_mode` query parameter.

### 6a. Parameter Behaviour

| Parameter | Value | Behaviour |
|---|---|---|
| `fixture_mode` | `false` (default) | Read from production in-memory registry — normal path |
| `fixture_mode` | `true` | Return synthetic fixture records — advisory only |

### 6b. Fixture Mode Supported States

`fixture_mode=true` returns synthetic records for **REJECTED / RETIRED / OBSERVATION only**.

| State | Supported in fixture_mode=true? |
|---|---|
| `ONLINE` | ❌ Not included |
| `REJECTED` | ✅ Included |
| `RETIRED` | ✅ Included |
| `OBSERVATION` | ✅ Included |
| `OFFLINE` | ❌ Never — not a formal state |

### 6c. Required Fixture Record Fields

Every synthetic fixture record **must** carry all of the following fields:

| Field | Required Value | Meaning |
|---|---|---|
| `source` | `"synthetic_fixture"` | Origin marker — not real replay data |
| `advisory_only` | `true` | Data is advisory — no operational use |
| `production_db_write` | `false` | Confirms no DB write occurred |
| `fixture_mode` | `true` | Confirms this record came from fixture path |

### 6d. Fixture Mode Constraints

- Fixture records **do not** represent production replay outcomes.
- Fixture mode **must not** write to `data/lottery_v2.db` or any production DB.
- Fixture mode **must not** trigger any registry modification.
- Fixture mode **must not** cause any strategy promotion or retirement action.
- Fixture mode data **must not** be used as strategy performance evidence.

---

## 7. Agent Guardrails

All agents (human and automated) operating against this endpoint or its contract **must** observe the following rules:

| Rule | Constraint |
|---|---|
| Taxonomy docs ≠ backfill auth | No taxonomy document constitutes authorization for production DB backfill |
| Fixture records ≠ performance evidence | No synthetic fixture record may be cited as evidence of strategy performance |
| No OFFLINE self-introduction | An agent must not self-introduce OFFLINE state without meeting all 7 prerequisites in Section 2 |
| No DB write from docs | Documentation updates must not trigger any DB write |
| No registry change from docs | Documentation updates must not modify the in-memory registry |

---

## 8. Response Marker

```
marker: "P7_STRATEGY_LIFECYCLE_ENDPOINT_READY"
```

---

## 9. Example Response (abbreviated)

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

## 10. Frontend Usage

The lifecycle registry card in `index.html` (`id="rp-lifecycle-registry-card"`) consumes this endpoint:

- **Function:** `rpLoadLifecycleRegistry()` — auto-called when user navigates to replay section
- **Badges rendered:** `rp-lc-badge-online`, `rp-lc-badge-rejected`, `rp-lc-badge-retired`, `rp-lc-badge-obs`
- **Table:** `rp-lc-table` / `rp-lc-tbody` — one row per strategy entry
- **XSS protection:** All server data passed through `_esc()` before `innerHTML` assignment

---

## 11. Explicitly Prohibited UI Actions

The lifecycle dashboard card **must not** contain any of the following actions:

| Prohibited Action | Reason |
|---|---|
| Promote strategy | Would change lifecycle state — not allowed |
| Retire strategy | Would change lifecycle state — not allowed |
| Backfill replay history | Would write to DB — not allowed |
| Run replay | Would execute strategy — not allowed |
| Scheduler trigger | Would launch cron/scheduler — not allowed |

---

## 12. Governance Markers

```
P7_STRATEGY_LIFECYCLE_ENDPOINT_READY
P10_LIFECYCLE_ENDPOINT_CONTRACT_DOC_READY
P11_LIFECYCLE_ENDPOINT_CONTRACT_OFFLINE_PROHIBITION_AND_FIXTURE_SCOPE
```

---

## 13. Related Files

| File | Role |
|---|---|
| `lottery_api/routes/replay.py` | Endpoint implementation |
| `lottery_api/models/replay_strategy_registry.py` | In-memory registry data source |
| `tests/test_replay_strategy_lifecycle_endpoint.py` | P7 endpoint tests (26 tests) |
| `tests/test_replay_strategy_lifecycle_contract.py` | P10 contract / snapshot tests |
| `tests/test_replay_strategy_lifecycle_dashboard_static.py` | P10 dashboard static smoke |
| `index.html` | Frontend lifecycle card |
