# P258M — D3 Strategy Status Audit: Artifact-Backed API Contract

**Task ID:** P258M  
**Date:** 2026-06-09  
**Status:** `P258M_D3_STRATEGY_STATUS_AUDIT_API_CONTRACT_READY`  
**Classification:** `P258M_D3_STRATEGY_STATUS_AUDIT_API_CONTRACT_READY`

---

## Scope Declaration

This document defines the **API contract only** for the future D3 Strategy Status / Contract Audit query page.

**P258M does NOT implement:**
- The API route `GET /api/replay/d3-strategy-status-audit`
- Any UI file
- Any executable D3 gate module
- Any DB query or DB write
- Any recommendation, production, registry, controlled_apply, or deployment change

**P258M defines only:**
- Proposed route path and purpose
- Top-level payload field contract
- Per-row field contract
- Data source policy
- Allowed and forbidden D3 contract statuses
- Required filters
- Required safety disclaimers
- Future task split

---

## Proposed Route

```
GET /api/replay/d3-strategy-status-audit
```

### Purpose

1. Serve a read-only artifact-backed payload for the future D3 Strategy Status / Contract Audit page
2. List all strategies and their current lifecycle and evidence status
3. Show D3 contract-readiness status **separately** from lifecycle and evidence status
4. Prevent D3 contract status from being interpreted as approval, recommendation, or prediction endorsement
5. Provide a historical/read-only evidence index — **not betting advice**

---

## Data Source Policy

| Constraint | Value |
|---|---|
| First implementation | Artifact-backed only |
| DB query in first implementation | FORBIDDEN |
| DB write | FORBIDDEN |
| Registry mutation | FORBIDDEN |
| Production state mutation | FORBIDDEN |

**Allowed artifact sources:**
- `outputs/research/p258l_d3_strategy_status_audit_page_plan_20260609.json`
- `outputs/research/p251b_evidence_dashboard_artifact.json` (if available)
- `outputs/research/p257a_best_strategy_overview_artifact.json` (if available)
- `outputs/research/p258k_d3_integration_contract_documentation_closeout_20260609.json`

---

## Top-Level Payload Contract

| Field | Type | Required | Description |
|---|---|---|---|
| `schema_version` | string | YES | Payload schema version (e.g., `"1.0"`) |
| `generated_at` | string (ISO 8601) | YES | UTC timestamp when response was generated |
| `source_artifacts` | array of string | YES | Artifact file paths backing this payload |
| `route_path` | string | YES | Route path that served this response |
| `page_title` | string | YES | Display title (e.g., `"D3 Strategy Status / Contract Audit"`) |
| `summary` | object | YES | Summary counts by status dimensions |
| `filters` | object | YES | Available filter options keyed by filter name |
| `rows` | array | YES | Per-strategy row objects (see row contract below) |
| `safety_disclaimers` | array of string | YES | Required safety copy — always present |
| `forbidden_actions_confirmed` | object | YES | Explicit booleans confirming no write/mutation actions |
| `next_allowed_task` | string | YES | Next authorized task identifier |

---

## Per-Row Field Contract

| Field | Type | Required | Description |
|---|---|---|---|
| `lottery_type` | string | YES | e.g., `DAILY_539`, `BIG_LOTTO`, `POWER_LOTTO` |
| `strategy_id` | string | YES | Unique strategy identifier |
| `strategy_name` | string | NO | Human-readable name if available |
| `lifecycle_status` | string | YES | e.g., `ADOPTED`, `PROVISIONAL`, `REJECTED`, `RETIRED`, `HISTORICAL_ARTIFACT`, `EXPERIMENTAL` |
| `evidence_status` | string | YES | e.g., `VALIDATED`, `PENDING`, `NULL`, `REJECTED_BY_OOS`, `OBSERVATION_ONLY` |
| `replay_row_count` | integer | NO | Rows in `strategy_prediction_replays` |
| `draw_coverage` | string | NO | Draw coverage description |
| `best_n_bet_status` | string | NO | From P257A overview if available |
| `latest_evidence_artifact` | string | NO | Path/identifier of most recent evidence artifact |
| `d3_contract_status` | string | YES | **See allowed values below** |
| `d3_contract_reason` | string | YES | Human-readable reason for the status value |
| `d3_not_approval_warning` | string | YES | **Mandatory:** "D3 contract status is NOT approval. NOT_YET_REJECTED is not approval." |
| `no_prediction_claim` | string | YES | **Mandatory:** "D3 is not a prediction model. Contract validation does not imply improved prediction accuracy." |
| `no_betting_advice` | string | YES | **Mandatory:** "This information is historical/read-only evidence only. It is not betting advice." |

---

## D3 Contract Status Values

### Allowed

| Status | Meaning |
|---|---|
| `NOT_EVALUATED_BY_D3` | Strategy has not yet been evaluated by D3 |
| `CONTRACT_READY` | Meets D3 schema/provenance requirements — **NOT_YET_REJECTED, not approval** |
| `CONTRACT_BLOCKED` | Fails one or more D3 validators — blocked until contract issues are resolved |
| `NOT_APPLICABLE_HISTORICAL_ARTIFACT` | Historical artifact without active candidate data — D3 not applicable |
| `NOT_APPLICABLE_NO_REPLAY` | No replay rows — D3 not applicable |

### Forbidden

| Status | Reason |
|---|---|
| `APPROVED` | D3 is not an approval gate |
| `PROMOTED` | D3 does not promote strategies |
| `PRODUCTION_READY` | D3 does not determine production readiness |
| `RECOMMENDED` | D3 does not make recommendations |
| `PREDICTIVE_EDGE_CONFIRMED` | D3 is not a prediction model |

---

## Required Filters

| Filter | Type | Description |
|---|---|---|
| `lottery_type` | string enum | Filter by lottery type |
| `lifecycle_status` | string enum | Filter by lifecycle status |
| `evidence_status` | string enum | Filter by evidence status |
| `d3_contract_status` | string enum | Filter by D3 contract status |
| `has_replay` | boolean | Only strategies with replay rows |
| `has_artifact` | boolean | Only strategies with a latest evidence artifact |

---

## Required Safety Disclaimers

The following must always appear in the `safety_disclaimers` array:

1. D3 is not a prediction model.
2. Contract validation is not strategy evaluation.
3. NOT_YET_REJECTED is not approval.
4. Passing contract validation does not imply improved prediction accuracy.
5. This API is historical/read-only evidence, not betting advice.

---

## Future Task Split

| Task | Scope | Authorization Required |
|---|---|---|
| **P258N** | Implement read-only artifact-backed API route only | Separate explicit authorization after P258M merged |
| **P258O** | Implement UI display page only | Separate explicit authorization after P258N merged |
| Running D3 on real candidate methods | FORBIDDEN | Separate future task + explicit authorization beyond P258O |

**P258M does NOT automatically authorize P258N.**

---

## Forbidden Executable Modules (Confirmed Absent)

The following modules must NOT be created in P258M:

- `candidate_ingest.py`
- `baseline_ingest.py`
- `null_factory.py`
- `gate_statistics.py`
- `gate_orchestrator.py`
- `gate_audit.py`
- `integration_runner.py`

---

## Governance Reminders

- D3 is **not** an approval gate
- D3 is **not** a prediction model
- Contract validation is **not** strategy evaluation
- `NOT_YET_REJECTED` is **not** approval
- Passing contract validation does **not** imply improved prediction accuracy
- This API is **historical/read-only evidence only** — not betting advice

---

*Artifact backed by: P258L page plan, P258K closeout, P258F validators, P258I skeleton*
