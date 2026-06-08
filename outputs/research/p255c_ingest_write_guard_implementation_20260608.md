# P255C — Ingest Write Guard Implementation

**Date**: 2026-06-08  
**Task type**: Type C code-change  
**Classification**: INGEST_WRITE_GUARD_IMPLEMENTATION_COMPLETE  
**Authorization**: Authorize P255C Ingest Write Guard Implementation

---

## Executive Summary

P255C implements the P0 server-side write guards designed in P255B, eliminating the
critical gap where any POST to `/api/ingest/backfill` with an omitted `dry_run` field
would silently write to the database.

Two guardrails are implemented:
- **G01**: `BackfillRequest.dry_run` default changed from `False` → `True`
- **G02**: All non-dry-run writes require `apply_confirmed=True`, a valid `confirm_token`,
  `requested_by`, and `reason`. Validated server-side before the engine is called.

Guardrails G03–G08 (UI modal, audit log, SHA backup, idempotency, CORS, env gate)
are documented as deferred to P255D+.

---

## P255B Design Dependency

| Field | Value |
|-------|-------|
| P255B artifact | `outputs/research/p255b_ingest_write_guard_design_20260608.json` |
| P255B PR | #364 (MERGED) |
| P255B classification | INGEST_WRITE_GUARD_DESIGN_COMPLETE |
| Designs adopted | G01_default_dry_run_true, G02_server_side_confirm_token |

---

## Implemented Guardrails

### G01 — Default dry_run = True

**File**: `lottery_api/routes/ingest.py`  
**Change**: `BackfillRequest.dry_run: bool = True` (was `False`)

Any POST that omits `dry_run` now defaults to a safe read-only preview.
Callers must explicitly set `dry_run=False` (plus G02 confirmation) to write.

### G02 — Server-side Confirm Token

**File**: `lottery_api/routes/ingest.py`  
**New fields on BackfillRequest**:

| Field | Type | Default | Required for write |
|-------|------|---------|-------------------|
| `apply_confirmed` | `bool` | `False` | Yes — must be `True` |
| `confirm_token` | `Optional[str]` | `None` | Yes — must match server token |
| `requested_by` | `str` | `'unknown'` | Yes — non-empty, non-`'unknown'` |
| `reason` | `str` | `''` | Yes — non-empty |
| `expected_insert_count` | `Optional[int]` | `None` | No (deferred validation) |

**Token implementation**: `INGEST_WRITE_TOKEN` env var; fallback `p255-write-confirm`.
Full HMAC(secret, lottery_type+timestamp) with TTL is deferred to P255D.

**Validation function**: `_validate_write_confirmation(req)` called at the top of
`run_backfill()` before any engine interaction.

---

## Request Contract

```
POST /api/ingest/backfill

{
  "lottery_type": "BIG_LOTTO",         // str, default BIG_LOTTO
  "draw_list": null,                    // Optional[List[str]]
  "dry_run": true,                      // bool, default TRUE (G01)
  "max_draws": 30,                      // int 1-500
  "apply_confirmed": false,             // bool, default False (G02)
  "confirm_token": null,                // Optional[str] (G02)
  "requested_by": "unknown",            // str (G02)
  "reason": "",                         // str (G02)
  "expected_insert_count": null         // Optional[int] (G02, deferred use)
}
```

---

## Failure Mode Summary

| Scenario | Response |
|----------|----------|
| Omitted `dry_run` | `dry_run=True` (safe default) — 200 dry-run |
| `dry_run=True` explicit | 200 dry-run preview |
| `dry_run=False` + no `apply_confirmed` | 422 `write_not_confirmed` |
| `dry_run=False` + no `confirm_token` | 422 `missing_confirm_token` |
| `dry_run=False` + wrong `confirm_token` | 422 `invalid_confirm_token` |
| `dry_run=False` + no `requested_by` / `'unknown'` | 422 `missing_requested_by` |
| `dry_run=False` + empty `reason` | 422 `missing_reason` |
| `dry_run=False` + all valid → engine mocked | engine called, 200 (test only) |

---

## Dry-run Behavior

- `dry_run` defaults to `True` — no confirmation fields needed
- Engine receives `dry_run=True` → returns preview summary, no DB write
- Existing behavior for dry-run responses is preserved

---

## Confirmed-write Validation (Mock Only)

Tests use `unittest.mock.patch` to replace `_get_engine()` with a mock.
A valid confirmed-write request (correct token, all fields) passes all G02 checks
and would call `engine.run(dry_run=False, ...)` — but the real engine is never
invoked during tests, ensuring no DB write occurs.

---

## Deferred Guardrails

| ID | Title | Priority | Next Task |
|----|-------|----------|-----------|
| G03 | UI confirmation modal | P1 | P255D |
| G04 | Audit log extended fields | P1 | P255D |
| G05 | DB SHA backup integrity | P1 | P255D |
| G06 | Per-request idempotency key | P1 | P255D |
| G07 | CORS wildcard hardening | P2 | P255D |
| G08 | INGEST_WRITE_ENABLED env gate | P2 | P255D |

---

## Current Accepted Baseline

| Metric | Count | Source |
|--------|-------|--------|
| BIG_LOTTO raw | 22,239 | PR #360 ACCEPT_BACKFILL_DB_DRIFT_2026_0608 |
| BIG_LOTTO canonical | 2,114 | PR #360 |
| BIG_LOTTO ADD_ON | 19,100 | PR #360 |
| POWER_LOTTO raw | 1,917 | PR #360 |
| DAILY_539 raw | 5,882 | PR #360 |
| strategy_prediction_replays | 94,924 | P213L |

---

## Explicit Non-actions

- No frontend/UI modified
- No fetcher code modified (`fetcher/*` excluded from whitelist)
- No DB write during implementation or verification
- No DB schema migration
- No registry mutation
- No strategy promotion
- No betting advice
- No P247G constants changed
- No CORS changes (G07 deferred to P255D)
- No env write gate (G08 deferred to P255D)

---

## Required Completion Check

| Item | Status |
|------|--------|
| G01 default dry_run True | ✅ IMPLEMENTED |
| G02 server-side confirm token | ✅ IMPLEMENTED |
| G03–G08 deferred documented | ✅ DEFERRED |
| Tests created | ✅ tests/test_p255c_ingest_write_guard_implementation.py |
| No DB write during tests | ✅ CONFIRMED |
| No registry mutation | ✅ CONFIRMED |
| No strategy promotion | ✅ CONFIRMED |
| No betting advice | ✅ CONFIRMED |
| Baseline 22239/2114 preserved | ✅ CONFIRMED |
