# P41 — Next Roadmap Decision Memo

**Date:** 2026-05-13
**Agent:** Post-Closure Production Readiness Agent
**Reports To:** CTO
**Round:** P41
**Context:** Display-only catalog (P25) is live, fully tested, and documented.
             Main SHA: `4590786` — all PRs #70–#73 merged.

---

## Baseline State

The display-only catalog closure is complete. There are no open PRs, no pending merges, and no failing tests. The system is in a clean, stable state. This memo evaluates the three available next actions.

**Explicit constraint:** Any production DB backfill, OFFLINE generation, strategy mining, or lifecycle promotion requires a NEW explicit YES gate before action.

---

## Option A — Operator Demo / Real Browser Walkthrough

**Purpose:** CEO or operator validates the display-only catalog behavior in a real browser session, using the documented SOP (p34_operator_sop_display_only_catalog_20260513.md).

**Scope:**
- Start dev server locally
- Navigate the replay catalog UI in a real browser
- Verify all 5 lifecycle modes display correctly (ONLINE, REJECTED, RETIRED, OBSERVATION, OFFLINE)
- Verify fixture mode ON/OFF toggle behavior
- No code changes required
- No DB writes permitted

**Prerequisites:**
- Resolve backend startup `ModuleNotFoundError` before session (pre-existing issue)
- Use the real browser — not playwright mocks

**Deliverables:**
- Operator sign-off confirmation (can be a simple in-chat YES from CTO/CEO)
- Optional: additional real-browser screenshots to complement P35 mocked captures

**Risk:** LOW
- No code change
- No DB change
- Feature is already tested and documented

**Effort:** LOW — 1 session, existing SOP, no new code

**Recommended:** ✅ YES — this is the next logical and safest step.

---

## Option B — No-Write Backfill Dry-Run Manifest

**Purpose:** Produce a read-only manifest describing which non-ONLINE strategies could theoretically receive replay history rows in the future, how many rows would be created, and what the data shape would look like — without writing anything.

**Scope:**
- Read-only analysis of `lottery_api/models/replay_strategy_registry.py`
- Count: REJECTED (4), RETIRED (5), OBSERVATION (1) = 10 strategies
- Estimate row count per strategy per lottery type
- Identify data dependencies and constraints
- Document: which fields would be populated, which would be empty/null
- Output: a markdown manifest only — NO DB WRITE

**Prerequisites:**
- CTO provides explicit YES gate for the dry-run analysis
- Confirm: no DB write is permitted in this phase
- No strategy promotion allowed during analysis

**Deliverables:**
- `outputs/relay/p42_backfill_dryrun_manifest_YYYYMMDD.md`
- Row count estimates per strategy
- Field-level schema for backfill rows
- Risk assessment per strategy

**Risk:** MEDIUM
- The dry-run itself is read-only and safe
- Risk is that dry-run output could be misread as approval for actual backfill
- Must clearly label all output as planning-only, not approved

**Effort:** MEDIUM — requires careful analysis of registry + DB schema

**Recommended:** Second priority — after operator demo confirms display-only behavior meets expectations.

---

## Option C — Stop Here and Monitor

**Purpose:** Declare the display-only catalog complete, make no further changes, and monitor the system in production for stability over the next sprint or release cycle.

**Scope:**
- No new PRs
- No new code changes
- No new analysis
- Monitor: test suite health, backend uptime, any user-reported issues

**Prerequisites:**
- CTO explicitly approves a monitoring freeze
- Define monitoring period (recommended: 1–2 weeks)
- Define re-activation criteria (e.g., user-reported issue, CTO YES for Option A or B)

**Deliverables:**
- None in this session
- Optional: a lightweight monitoring checklist

**Risk:** LOWEST — no change, no exposure
**Effort:** LOWEST — no new work

**Recommended:** Only if CTO wants to freeze all activity. Suitable if there are no upcoming operator demos or CEO reviews scheduled.

---

## Comparison Matrix

| Criterion | Option A (Demo) | Option B (Dry-run) | Option C (Monitor) |
|---|---|---|---|
| Risk | LOW | MEDIUM | LOWEST |
| Effort | LOW | MEDIUM | LOWEST |
| Requires new YES gate | No | YES | No |
| Produces new code | No | No | No |
| DB write risk | None | None (read-only) | None |
| Business value | HIGH — CEO validation | MEDIUM — planning asset | LOW — status quo |
| Recommended order | **1st** | **2nd** | **3rd / default** |

---

## Explicit Deferrals (All Options)

Regardless of which option is chosen, the following remain deferred until a separate explicit YES gate:

| Item | Why Deferred |
|---|---|
| Real production backfill | Requires schema review, data governance approval, new YES gate |
| OFFLINE strategy introduction | Not designed, no approval |
| Strategy mining / edge discovery | Not in scope for display-only catalog |
| Lifecycle promotion (any direction) | Requires governance review |
| Fixture mode DB isolation changes | No issue identified, no change needed |

---

## Final Recommendation

> **Proceed with Option A — Operator Demo.**
>
> The display-only catalog is stable, documented, and tested. The next highest-value action is to have the CTO or operator validate the feature in a real browser using the existing SOP. This requires no code changes, no DB writes, and confirms the feature meets the original product intent.
>
> If the operator demo confirms the feature is satisfactory, Option B (dry-run backfill manifest) can be initiated in the next round with a fresh YES gate.
>
> Option C is available as a fallback if no demos are planned in the near term.

---

*Memo generated by P41 Post-Closure Production Readiness Agent*
*main SHA: 4590786*
