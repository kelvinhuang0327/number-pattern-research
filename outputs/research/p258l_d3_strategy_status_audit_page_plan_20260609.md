# P258L — D3 Strategy Status Audit Page Plan

**Date:** 2026-06-09
**Status:** PLAN_ONLY
**Classification:** `P258L_D3_STRATEGY_STATUS_AUDIT_PAGE_PLAN_READY`

---

## Mandatory Safety Semantics

> **D3 is not a prediction model.**
> **Contract validation is not strategy evaluation.**
> **Passing contract validation does NOT imply improved prediction accuracy.**
> **NOT_YET_REJECTED is NOT approval.**
> **Passing validators does NOT allow production or recommendation use.**
> **This page is historical/read-only evidence only. It is NOT betting advice.**
> **Executable gate evaluation remains FORBIDDEN without separate explicit authorization.**

---

## Scope Declaration

P258L is a **plan artifact only** task. No UI files, no API route files, and no executable D3 code were modified. Specifically:

- No real candidate methods were used or run
- No executable gate evaluation was performed
- No null generation occurred
- No p-values were computed
- No paired tests or backtests were run
- No DB writes occurred
- No recommendation, production, registry, controlled_apply, or deployment paths were touched

---

## Page Contract

**Title:** D3 Strategy Status / Contract Audit

**Purpose:**
1. Show all strategies and their current evidence/lifecycle status
2. Show D3 contract-readiness status separately from lifecycle and evidence status
3. Prevent users from interpreting D3 contract status as approval, promotion, or prediction endorsement
4. Provide a historical/read-only evidence index — not betting advice

---

## Data Sources

| Source | Access | DB Write? |
|--------|--------|-----------|
| Strategy registry / lifecycle status | Read-only | No |
| P251 evidence dashboard payload (`GET /api/replay/evidence-dashboard`) | Read-only artifact-backed | No |
| P257A best-strategy overview payload (`GET /api/replay/best-strategy-overview`) | Read-only artifact-backed | No |
| P258A–P258K D3 contract-validation artifact chain | Read-only artifact files | No |

All data sources are read-only. Graceful degradation if P251 or P257 payloads are unavailable.

---

## Required Row Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `lottery_type` | string | ✓ | DAILY_539, BIG_LOTTO, POWER_LOTTO |
| `strategy_id` | string | ✓ | Unique registry identifier |
| `strategy_name` | string | — | Human-readable name if available |
| `lifecycle_status` | string | ✓ | ADOPTED, PROVISIONAL, REJECTED, RETIRED, HISTORICAL_ARTIFACT, EXPERIMENTAL |
| `evidence_status` | string | ✓ | VALIDATED, PENDING, NULL, REJECTED_BY_OOS, OBSERVATION_ONLY |
| `replay_row_count` | integer | — | Rows in strategy_prediction_replays |
| `draw_coverage` | string | — | E.g., "1500 draws", "short window only" |
| `best_n_bet_status` | string | — | P257A best-N-bet status if available |
| `latest_evidence_artifact` | string | — | Path/identifier of most recent evidence artifact |
| `d3_contract_status` | string | ✓ | One of 5 allowed values (see below) |
| `d3_contract_reason` | string | ✓ | Human-readable reason for d3_contract_status |
| `d3_not_approval_warning` | string | ✓ | "D3 contract status is NOT approval. NOT_YET_REJECTED is not approval." |
| `no_prediction_claim` | string | ✓ | "D3 is not a prediction model. Contract validation does not imply improved prediction accuracy." |
| `no_betting_advice` | string | ✓ | "This information is historical/read-only evidence only. It is not betting advice." |

---

## Allowed D3 Contract Statuses

| Status | Meaning | Implies Approval? |
|--------|---------|------------------|
| `NOT_EVALUATED_BY_D3` | Default — strategy not submitted to D3 contract validation | No |
| `CONTRACT_READY` | All D3 input contract boundaries valid. NOT_YET_REJECTED — not approval, not improved accuracy, not production-ready | No |
| `CONTRACT_BLOCKED` | ContractValidationError raised — fix contract issues before gate evaluation can proceed | No |
| `NOT_APPLICABLE_HISTORICAL_ARTIFACT` | Lifecycle is REJECTED/RETIRED/HISTORICAL_ARTIFACT — D3 not applicable | No |
| `NOT_APPLICABLE_NO_REPLAY` | No replay rows — D3 requires replay data | No |

### Forbidden D3 Contract Status Values

The following values must **never** appear in `d3_contract_status`:

- `APPROVED`
- `PROMOTED`
- `PRODUCTION_READY`
- `RECOMMENDED`
- `PREDICTIVE_EDGE_CONFIRMED`

---

## Page Filters

| Filter | Type |
|--------|------|
| `lottery_type` | Enum: DAILY_539, BIG_LOTTO, POWER_LOTTO, ALL |
| `lifecycle_status` | Multi-select string |
| `evidence_status` | Multi-select string |
| `d3_contract_status` | Multi-select enum (allowed values only) |
| `has_replay` | Boolean |
| `has_artifact` | Boolean |

---

## Required Safety Copy

Every row and every page render must include:

1. **D3 is not a prediction model.**
2. **Contract validation is not strategy evaluation.**
3. **NOT_YET_REJECTED is not approval.**
4. **Passing contract validation does not imply improved prediction accuracy.**
5. **This page is historical/read-only evidence only, not betting advice.**

---

## Future Task Split

| Task | Authorized Scope |
|------|-----------------|
| **P258M** (requires separate explicit authorization) | Read-only artifact-backed API contract only — no DB write, no recommendation/production/registry/deployment changes |
| **P258N** (requires separate explicit authorization after P258M) | UI display only |
| Running D3 on real candidate methods | FORBIDDEN — requires separate future task beyond P258N |

---

## Forbidden Executable Modules (Confirmed Absent)

- `candidate_ingest.py`
- `baseline_ingest.py`
- `null_factory.py`
- `gate_statistics.py`
- `gate_orchestrator.py`
- `gate_audit.py`
- `integration_runner.py`
