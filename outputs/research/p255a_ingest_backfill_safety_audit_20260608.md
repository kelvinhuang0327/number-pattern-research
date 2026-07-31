# P255A — Ingest / Backfill Safety Boundary Audit

**Date:** 2026-06-08  
**Task Type:** Type B read-only audit  
**Classification:** `INGEST_BACKFILL_SAFETY_AUDIT_COMPLETE`

## Executive Summary

P255A audits all ingest and backfill trigger paths to identify where non-dry-run writes can occur, whether any path auto-triggers a write on page load, and what server/UI guardrails are currently present.  The audit found one critical gap: `BackfillRequest.dry_run` defaults to `False`, meaning any API call that omits the field will write to the DB.  The frontend confirmation gate is UI-only and is not enforced at the server.  Eight guardrails are recommended before any future ingest UI or monitoring feature is authorized.  No DB write was performed in this audit.

## Incident Background

During the P254A/P254B fetcher-repair session (2026-06-08), after `lottery_api/fetcher/*` was restored (PR #361), the frontend ingest page was loaded.  Page load auto-fired only a READ-ONLY `GET /api/ingest/log`.  However, a subsequent manual backfill button click with the confirmation checkbox checked and `dry_run=false` triggered a real write, inserting 5 draws (BIG_LOTTO 115000059, POWER_LOTTO 115000045, DAILY_539 115000136/137/138).  These were accepted as legitimate missing draws via PR #360.

## Phase 0 Verification

| Item | Result |
|---|---|
| Repo | /Users/kelvin/Kelvin-WorkSpace/LotteryNew |
| Branch | main |
| HEAD | `270a718c36ea55b7...` |
| HEAD = origin/main | YES |
| PR #360 | MERGED |
| PR #361 | MERGED |
| PR #362 | MERGED |
| data/lottery_v2.db | Metadata-only touch (0 bytes content change) |

## Trigger Path Inventory

| ID | Path | Classification | Writes DB | Auto on load |
|---|---|---|:---:|:---:|
| T01 | GET /api/ingest/status | `READ_ONLY_LOG` | — | — |
| T02 | GET /api/ingest/scan-missing | `READ_ONLY_LOG` | — | — |
| T03 | POST /api/ingest/fetch-latest  (insert_if_new=False OR dry_run=Tr... | `DRY_RUN_SAFE` | — | — |
| T04 | POST /api/ingest/fetch-latest  (insert_if_new=True, dry_run=False... | `WRITE_CAPABLE_REQUIRES_GUARD` | YES | — |
| T05 | POST /api/ingest/backfill  (dry_run=True) | `DRY_RUN_SAFE` | — | — |
| T06 | POST /api/ingest/backfill  (dry_run=False)  <- INCIDENT PATH | `WRITE_CAPABLE_REQUIRES_GUARD` | YES | — |
| T07 | GET /api/ingest/log | `READ_ONLY_LOG` | — | YES |
| T08 | POST /api/ingest/log/clear | `WRITE_CAPABLE_REQUIRES_GUARD` | — | — |
| T09 | Frontend: AutoFetchManager._onBackfill()  (frontend confirmation ... | `WRITE_CAPABLE_REQUIRES_GUARD` | YES | — |
| T10 | Backend: _refresh_after_insert() internal chain | `WRITE_CAPABLE_REQUIRES_GUARD` | YES | — |
| T11 | FastAPI startup event: startup_event() | `READ_ONLY_LOG` | — | YES |
| T12 | Scheduler / cron / background task paths | `UNKNOWN_NEEDS_SCOPE` | — | — |
| T13 | Test-only paths: TestClient calls in test_p254a / test_p254b | `TEST_ONLY` | — | — |

## Write-Capable Path Analysis

### T04

**Path:** `POST /api/ingest/fetch-latest  (insert_if_new=True, dry_run=False)`

Calls db_manager.insert_draws() if draw is new.  On success calls _refresh_after_insert() which chains: resolve_pending(dry_run=False) + adjust_all_types(dry_run=False) + apply_learning(dry_run=False).  No server-side authorization token required.

### T06 **← INCIDENT PATH**

**Path:** `POST /api/ingest/backfill  (dry_run=False)  <- INCIDENT PATH`

BackfillRequest.dry_run defaults to False.  A POST without explicit dry_run=true WILL write.  On any insertion, calls _refresh_after_insert() (resolve_pending + weight_adjuster + learning_integrator, all dry_run=False).  This is the exact path that triggered the P254B incident (5 draws inserted: BIG_LOTTO 115000059, POWER_LOTTO 115000045, DAILY_539 115000136/137/138).

### T08

**Path:** `POST /api/ingest/log/clear`

Truncates ingest_log.jsonl.  Does not touch the DB.  Audit trail destruction risk.

### T09

**Path:** `Frontend: AutoFetchManager._onBackfill()  (frontend confirmation gate)`

Frontend soft gate: requires dryRun=true OR confirmed checkbox to be checked. If confirmed checkbox is already checked from a prior session and user clicks backfill without realizing, a non-dry-run write is sent.  Gate is UI-only, not server-enforced.

### T10

**Path:** `Backend: _refresh_after_insert() internal chain`

Calls resolve_pending(dry_run=False), adjust_all_types(dry_run=False), and apply_learning(dry_run=False).  These are additional write operations that cascade from a backfill insert.  There is no dry_run pass-through to this chain.

## Auto-Trigger Risk Analysis

### R01 [HIGH] BackfillRequest.dry_run defaults to False

In lottery_api/routes/ingest.py, BackfillRequest.dry_run = False. Any caller that omits dry_run (or sends dry_run=false) will trigger real DB writes. The incident path (T06) went through this default. Mitigation: change default to dry_run=True and require an explicit 'apply=true' flag or a server-side authorization token to perform writes.

- **File:** `lottery_api/routes/ingest.py:41`
- **Affected paths:** T06

### R02 [HIGH] Frontend confirmation gate is UI-only (not server-enforced)

AutoFetchManager._onBackfill() checks 'if (!dryRun && !confirmed) return'. This is enforced only in the browser JavaScript. Any direct HTTP POST to /api/ingest/backfill bypasses this gate entirely. During the P254B incident the frontend sent the POST after the user confirmed, but the server had no additional authorization layer. Mitigation: add a server-side 'apply_confirmed: bool = False' field to BackfillRequest that the server validates before allowing dry_run=False writes.

- **File:** `src/ui/AutoFetchManager.js:241-244`
- **Affected paths:** T06, T09

### R03 [MEDIUM] _refresh_after_insert() cascades multiple write operations with no dry_run option

After any successful non-dry-run insert (fetch-latest or backfill), _refresh_after_insert() fires resolve_pending(dry_run=False), adjust_all_types(dry_run=False), and apply_learning(dry_run=False). These are additional write paths that execute without any dry_run guard. A single accidental backfill insert triggers 3+ downstream write chains.

- **File:** `lottery_api/routes/ingest.py:72-110`
- **Affected paths:** T04, T06, T10

### R04 [MEDIUM] CORS allows wildcard origin in development mode

lottery_api/app.py CORS origins list includes '*'. In development this means any origin can POST to write-capable endpoints. No CORS restriction prevents a cross-origin page from triggering backfill writes. Mitigation: restrict CORS to explicit localhost origins only; remove '*'.

- **File:** `lottery_api/app.py:30-36`
- **Affected paths:** T04, T06

### R05 [LOW] AutoFetchManager._loadLog() auto-fires GET on page load (read-only, not a write risk)

The AutoFetchManager constructor calls this._loadLog() immediately on instantiation (App.js line 34 creates AutoFetchManager; AutoFetchManager._bindEvents line 79 calls _loadLog). This sends GET /api/ingest/log automatically on every page load. This is READ_ONLY and poses no write risk, but confirms the frontend does auto-contact the ingest API on every page load without user interaction.

- **File:** `src/ui/AutoFetchManager.js:79`
- **Affected paths:** T07

### R06 [LOW] No DB pre-write SHA checkpoint before backfill insert

Before calling db_manager.insert_draws(), neither the route nor the engine creates a SHA fingerprint or DB snapshot. If a partial write occurs (network failure mid-batch), there is no rollback point. The existing DB UNIQUE constraint prevents duplicates but does not protect against partial state. Mitigation: record DB file SHA256 to ingest_log before each write batch.

- **File:** `lottery_api/fetcher/backfill_engine.py:261-295`
- **Affected paths:** T04, T06

## Dry-Run Safety Assessment

| Endpoint | dry_run supported | default | Risk |
|---|:---:|---|---|
| `backfill_endpoint` | YES | `False` | HIGH — default is write-capable; caller must opt into dry_run=True |
| `fetch_latest_endpoint` | YES | `False` | LOW — default insert_if_new=False means no write even if dry_run=False |
| `scan_missing_endpoint` | — | `N/A` | NONE — GET endpoint, read-only by design |
| `log_endpoint` | — | `N/A` | NONE — GET endpoint, reads jsonl file only |
| `log_clear_endpoint` | — | `N/A` | LOW — truncates log file only, not DB |

## Non-Standard Draw Handling Assessment

**ADD_ON draw IDs** (e.g. `103000009-01`):

- Issue before P254A: int(draw[-6:]) raised ValueError for '009-01'
- Fix in P254A: _split() in missing_issue_detector.py now guards with draw.isdigit()
- Current safety: **SAFE — non-digit draws return None from _split(); loop skips them**

## Current Accepted Baseline

| Table / View | Count |
|---|---:|
| BIG_LOTTO raw draws | 22,239 |
| BIG_LOTTO canonical draws | 2,114 |
| BIG_LOTTO ADD_ON excluded | 19,100 |
| POWER_LOTTO raw draws | 1,917 |
| DAILY_539 raw draws | 5,882 |
| strategy_prediction_replays | 94,924 |

**Stale values — must NOT be reused:** BIG_LOTTO raw 22,238 / canonical 2,113 (invalidated 2026-06-08)

## Recommended Guardrails

### G01 [P0] Change BackfillRequest.dry_run default to True

In lottery_api/routes/ingest.py BackfillRequest, change 'dry_run: bool = False' to 'dry_run: bool = True'. All callers must explicitly opt into writes by passing dry_run=False. This is the single highest-impact change to prevent accidental writes.

- **File:** `lottery_api/routes/ingest.py:44`

### G02 [P0] Require explicit server-side confirmation token for write-capable backfill

Add an 'apply_confirmed: bool = False' field to BackfillRequest. Server rejects dry_run=False if apply_confirmed is not True. This ensures the server enforces authorization regardless of client behavior. This prevents direct API calls from bypassing the UI gate.

- **File:** `lottery_api/routes/ingest.py (new field in BackfillRequest)`

### G03 [P1] UI confirmation dialog before non-dry-run backfill

Replace the checkbox confirmation in AutoFetchManager with a modal dialog that explicitly states how many draws will be written and resets after each confirmation so it cannot be left in a pre-confirmed state across test sessions.

- **File:** `src/ui/AutoFetchManager.js:236-294`

### G04 [P1] Audit log entry for every DB write with pre/post row counts

Before and after each insert batch, record to ingest_log: pre_count, post_count, and a DB fingerprint. IngestLogger already exists; extend the 'ok' log entry to include counts.

- **File:** `lottery_api/fetcher/backfill_engine.py:262-274 (extend ingest_logger.log call)`

### G05 [P1] Controlled-apply style DB SHA backup before any write batch

Before calling db_manager.insert_draws(), compute sha256 of the DB file and log it to the audit log.  Optionally trigger a SQLite online-backup to a timestamped file for rollback capability.

- **File:** `lottery_api/fetcher/backfill_engine.py:_insert() (before insert_draws call)`

### G06 [P1] Server-side idempotency guard with per-batch insert token

Generate a unique idempotency_key per backfill request. Log the key before writes begin.  If the same key is replayed within 60 seconds, reject with 409 Conflict.  This prevents double-submit from network retry.

- **File:** `lottery_api/routes/ingest.py (new idempotency_key param)`

### G07 [P2] Remove wildcard CORS origin from production configuration

lottery_api/app.py origins list includes '*'.  Remove it and enumerate only the allowed local origins.  Gate the wildcard behind an env-var for dev-only mode.

- **File:** `lottery_api/app.py:30-36`

### G08 [P2] Write endpoint disabled unless explicit authorization env-var is set

Add INGEST_WRITE_ENABLED=false env-var.  When false, write-capable endpoints return 405 or force dry_run=True.  Set to true only during authorized maintenance windows.

- **File:** `lottery_api/routes/ingest.py (new env check at endpoint entry)`

## Recommended Next Task

HOLD.  No active deployable candidate.  Future ingest UI or monitoring work requires separate explicit user authorization before proceeding.  Implement guardrails G01+G02 before any future ingest write work is authorized.

## Scope Boundaries

- **already_accepted_baseline_drift:** PR #360 — BIG_LOTTO raw=22239, canonical=2114; do NOT reuse stale 22238/2113
- **fetcher_code_repair:** PR #361 — 5 modules restored, ADD_ON guard hardened
- **governance_closure:** PR #362 — incident chain documented, lessons L_P254_01/02/03 recorded
- **future_ingest_ui_monitoring:** NOT in scope — requires separate explicit user authorization
- **strategy_promotion:** Out of scope — no active deployable candidate
- **prediction_improvement:** Not claimed

## Explicit Non-Actions

- No DB write performed
- No registry mutation
- No strategy promotion
- No betting advice
- No fetcher code changed
- No API behavior changed
- No frontend modified
- No P247G constants changed

## Required Completion Check

| Item | Status |
|---|---|
| Completed | YES |
| Test Result | see pytest run |
| Single Blocking Issue | NONE |
| Modified Files | 4 (analysis script + json + md + test) |
| Staged | YES |
| Commit | YES |
| Push | YES |
| PR | YES |
| Merge | PENDING CI |
| Next Round Allowed | NO — WAITING_FOR_USER_AUTHORIZATION |
| Final Classification | `INGEST_BACKFILL_SAFETY_AUDIT_COMPLETE` |
| Strong Model Needed | NO |