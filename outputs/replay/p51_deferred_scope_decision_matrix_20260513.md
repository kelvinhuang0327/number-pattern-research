# P51 Deferred Scope Decision Matrix
**Date:** 2026-05-13  
**Agent:** Passive Monitoring & Deferred Scope Decision Agent  
**Round:** P51  
**Main SHA:** `7cc5b1b`

---

## 1. Current Project Closure State

| Milestone | Status |
|---|---|
| P25 Display-Only Catalog | ✅ FULLY CLOSED |
| Display-only UI (REJECTED / RETIRED / OBSERVATION / OFFLINE) | ✅ LIVE — UI-only, no DB write |
| ONLINE strategies unchanged | ✅ |
| Operator demo 7/7 live screenshots | ✅ On main |
| Governance docs P32–P48 | ✅ On main |
| PR #78 (P47 demo evidence) | ✅ MERGED |
| PR #79 (P48 closure archive) | ✅ MERGED |
| Final smoke 128 pass / 1 skip / 0 fail | ✅ |
| DB final state | ✅ CLEAN |

**P25 is closed. No further engineering action is required for P25.**

---

## 2. Deferred Scopes

### 2.1 No-Write Backfill Dry-Run Manifest

| Field | Value |
|---|---|
| **Description** | Generate a dry-run manifest listing all draw records that WOULD be written to production DB if backfill were authorized. No DB write occurs. Output is a read-only report file. |
| **Business Value** | Allows CTO / CEO to review exact data volume and scope before authorizing production backfill. Low-cost way to de-risk the next step. |
| **Risk** | LOW. No DB write. No product runtime change. Manifest only. |
| **Required Preconditions** | (a) All existing tests still passing (✅ already true); (b) CTO review of manifest format / output path |
| **Required YES Command** | `YES generate no-write backfill dry-run manifest` |
| **Recommended Priority** | **Option 2 — next logical step if backfill is desired** |

---

### 2.2 Production Backfill

| Field | Value |
|---|---|
| **Description** | Write historical draw records for REJECTED / RETIRED strategies into the production database. Enables historical accuracy for display-only catalog. |
| **Business Value** | Completes historical record for all strategy lifecycle transitions. Enables future analytics. |
| **Risk** | HIGH. Irreversible DB write. Requires dry-run manifest review first. Requires explicit operator authorization. |
| **Required Preconditions** | (a) No-write dry-run manifest reviewed and approved; (b) Full DB backup taken; (c) Explicit CTO written authorization |
| **Required YES Command** | `YES execute production backfill from approved manifest [manifest-SHA]` |
| **Recommended Priority** | **NOT RECOMMENDED NOW — requires dry-run first** |

---

### 2.3 OFFLINE Strategy Generation

| Field | Value |
|---|---|
| **Description** | Generate new OFFLINE-status strategy entries with defined parameters, to populate the "Coming Soon" display in the UI. |
| **Business Value** | Gives users visibility into planned future strategies. Signals ongoing system development. |
| **Risk** | MEDIUM. Requires lifecycle taxonomy decision. Risk of premature commitment to unvalidated strategies. |
| **Required Preconditions** | (a) OFFLINE strategy candidates defined and reviewed; (b) Strategy parameters validated against edge-discovery framework; (c) Governance approval |
| **Required YES Command** | `YES generate OFFLINE strategy entries for: [list of strategy names]` |
| **Recommended Priority** | **NOT RECOMMENDED NOW — no candidates defined** |

---

### 2.4 Strategy Mining / Edge Discovery

| Field | Value |
|---|---|
| **Description** | Run systematic backtest / signal search to discover new strategy candidates with measurable edge. |
| **Business Value** | Core long-term value driver. Enables ONLINE strategy pipeline to grow. |
| **Risk** | HIGH research overhead. Risk of spurious findings without proper validation gates. |
| **Required Preconditions** | (a) Data leakage prevention protocol verified; (b) Rolling validation framework confirmed; (c) Edge definition and minimum sample thresholds set |
| **Required YES Command** | `YES begin strategy mining cycle [method: e.g. frequency-gap / pair-coverage] on data range [start]–[end]` |
| **Recommended Priority** | **NOT RECOMMENDED NOW — requires foundational framework review first** |

---

### 2.5 Lifecycle Promotion

| Field | Value |
|---|---|
| **Description** | Promote a strategy from OBSERVATION → ONLINE, or demote from ONLINE → OBSERVATION / REJECTED. |
| **Business Value** | Keeps strategy registry accurate. Enables new strategies to go live. |
| **Risk** | HIGH if done without evidence. Any ONLINE strategy change affects production recommendations. |
| **Required Preconditions** | (a) Minimum live-run evidence period met; (b) Backtest + live comparison report approved; (c) CTO sign-off per strategy |
| **Required YES Command** | `YES promote strategy [name] from [current status] to [new status] based on evidence [report-SHA]` |
| **Recommended Priority** | **NOT RECOMMENDED NOW — no evidence report ready** |

---

### 2.6 Backend Startup Hardening / Operational Doc

| Field | Value |
|---|---|
| **Description** | Document the `PYTHONPATH` fix (P43) into a formal operator runbook. Optionally refactor `app.py` imports to be self-contained so `PYTHONPATH` is no longer needed. |
| **Business Value** | Reduces operator error on backend startup. Makes system more maintainable. |
| **Risk** | LOW (doc only). MEDIUM if import refactor (requires test regression). |
| **Required Preconditions** | Doc-only: none. Import refactor: full test suite pass required before and after. |
| **Required YES Command** | `YES create backend startup runbook` OR `YES refactor app.py imports to remove PYTHONPATH dependency` |
| **Recommended Priority** | **Option 3 — low-risk, operationally valuable** |

---

## 3. Recommended Priority Order

```
Priority 1: PASSIVE MONITORING
  → Run smoke weekly or on any main branch push
  → No action required unless failure detected
  → Current state: 128/1/0 ✅

Priority 2: NO-WRITE BACKFILL DRY-RUN MANIFEST
  → Low risk, unblocks backfill decision
  → YES command: "YES generate no-write backfill dry-run manifest"

Priority 3: BACKEND STARTUP HARDENING (doc only)
  → Low risk, high operational value
  → YES command: "YES create backend startup runbook"

NOT RECOMMENDED NOW:
  - Production backfill (requires dry-run first)
  - OFFLINE generation (no candidates)
  - Strategy mining (framework prerequisites)
  - Lifecycle promotion (no evidence)
```

---

## 4. Summary

P25 is fully closed. All deferred scopes require explicit YES authorization before any work begins.  
No engineering action should be taken based on this matrix without the corresponding YES command above.

*Generated by Passive Monitoring & Deferred Scope Decision Agent, Round P51, 2026-05-13*
