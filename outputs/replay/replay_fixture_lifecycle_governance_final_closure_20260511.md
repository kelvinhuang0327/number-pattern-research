# Replay Fixture-Mode + Lifecycle Taxonomy Governance Chain — Final Closure

**Date:** 2026-05-11  
**Report To:** CTO  
**Status:** CLOSED  
**Governance Chain:** Replay Fixture-Mode Epic + Lifecycle Taxonomy Lock

---

## 1. Closure Objective

This document formally closes the **Replay Fixture-Mode + Lifecycle Taxonomy governance chain**, spanning from the fixture artifact generator (PR #51) through the endpoint contract P11 update (PR #59).

The chain addressed four blocking problems:

| Blocking Problem | Resolution |
|---|---|
| Non-ONLINE rows could not be UI-validated (no production data) | Synthetic fixture artifact introduced in PR #51/#53 |
| Fixture artifact existed as JSON only — dashboard could not read it | API fixture-mode bridge + UI banner implemented in PR #53 |
| OFFLINE taxonomy classification undecided | CTO decision: Route B (OFFLINE deferred) — PR #57 |
| Core endpoint contract did not reflect taxonomy decisions | Contract updated to P11 — PR #59 |

---

## 2. Merged PR Chain

| PR | Commit | Merged At | Title |
|---|---|---|---|
| #51 | `7762118` | 2026-05-11 | feat(replay): add isolated non-online replay fixture artifact generator |
| #53 | `ce87159` | 2026-05-11 | feat(replay): add fixture mode replay history bridge |
| #54 | `142dc45` | 2026-05-11 | docs(replay): fixture mode browser e2e validation |
| #55 | `9f35999` | 2026-05-11 | docs(replay): close fixture mode epic |
| #56 | `7689189` | 2026-05-11 | docs(replay): add fixture mode SOP user guide |
| #57 | `f845ab7` | 2026-05-11 | docs(replay): decide offline classification taxonomy |
| #58 | `7e74070` | 2026-05-11 | docs(replay): update lifecycle taxonomy after offline decision |
| #59 | `4d33d75` | 2026-05-11 | docs(replay): update lifecycle endpoint contract with offline prohibition and fixture scope |

**main HEAD (final):** `4d33d75`

---

## 3. Final Product State

### 3a. Fixture Mode Behaviour

| Mode | Behaviour |
|---|---|
| `GET /api/replay/strategy-lifecycle` (default) | Reads production in-memory registry — no DB write |
| `GET /api/replay/replay-history?fixture_mode=false` | Production DB read path — unchanged |
| `GET /api/replay/replay-history?fixture_mode=true` | Returns synthetic fixture records from `outputs/replay/non_online_replay_fixture_20260511.json` |

### 3b. UI State

| UI Element | Status |
|---|---|
| Lifecycle registry card (`rp-lifecycle-registry-card`) | Displays all 4 formal states with counts |
| Strategy table (`rp-lc-tbody`) | One row per strategy, lifecycle badge per status |
| FIXTURE MODE banner | Displayed when `fixture_mode=true` is active |
| Non-ONLINE rows visualised | ✅ REJECTED / RETIRED / OBSERVATION all visible |
| OFFLINE filter | ❌ Not present — not a formal state |
| P23 UI Toggle Button | ❌ Deferred — not implemented |

### 3c. Fixture Artifact

| Item | Value |
|---|---|
| Path | `outputs/replay/non_online_replay_fixture_20260511.json` |
| Record count | 10 synthetic records |
| REJECTED | 4 |
| RETIRED | 5 |
| OBSERVATION | 1 |
| ONLINE | 0 |
| OFFLINE | 0 (never present) |

---

## 4. Final Lifecycle Taxonomy

Exactly **4 formal lifecycle states** are recognised system-wide:

| State | Meaning | Executable? | Source |
|---|---|---|---|
| `ONLINE` | Active — eligible for replay execution | ✅ Yes | Production registry |
| `OBSERVATION` | Under observation — classification pending | ❌ No | Production registry |
| `REJECTED` | Validation failed — permanently non-executable | ❌ No | Production registry |
| `RETIRED` | Deprecated / decommissioned | ❌ No | Production registry |

### OFFLINE — Deferred / Not a Formal State

`OFFLINE` is **not** a formal lifecycle state.

- Endpoint must never return `OFFLINE` as `lifecycle_status`
- `lifecycle_counts` must not contain an `OFFLINE` key
- UI must not add an OFFLINE filter
- Registry must not introduce OFFLINE strategy state
- Fixture mode must not add OFFLINE synthetic rows

Future introduction requires 7 prerequisites — none currently met. See `docs/replay/strategy_lifecycle_endpoint_contract.md` §2 for full list.

---

## 5. Final Fixture Mode Scope

| Dimension | Value |
|---|---|
| Supported states (`fixture_mode=true`) | REJECTED / RETIRED / OBSERVATION |
| ONLINE in fixture_mode=true | ❌ Not included |
| OFFLINE in fixture_mode=true | ❌ Never — not a formal state |
| Nature of records | Advisory-only |
| Origin | Synthetic — not derived from production replay execution |
| DB write | ❌ None |
| Production replay outcome | ❌ Fixture records do NOT represent production replay outcome |

### Required Fields on Every Fixture Record

| Field | Required Value |
|---|---|
| `source` | `"synthetic_fixture"` |
| `advisory_only` | `true` |
| `production_db_write` | `false` |
| `fixture_mode` | `true` |

---

## 6. Safety Invariants (All Rounds)

| Invariant | Final Status |
|---|---|
| Production DB write | ✅ NEVER executed |
| `data/lottery_v2.db` modified | ✅ CLEAN throughout |
| Registry modified | ✅ Never modified |
| Production DB backfill | ✅ Never executed |
| Strategy promotion / retirement action | ✅ Never executed |
| Scheduler / cron added | ✅ Never added |
| Strategy mining / edge discovery | ✅ Never executed |
| Branch protection changed | ✅ Never changed |
| P23 UI Toggle Button | ✅ Not implemented (deferred) |
| OFFLINE filter added | ✅ Never added |
| OFFLINE fixture records added | ✅ Never added |
| `--admin` merge override used | ✅ Never used |

---

## 7. Resolved Blockers

| Blocker | Resolution |
|---|---|
| Non-ONLINE rows unreachable in UI | Synthetic fixture artifact (PR #51) + API bridge (PR #53) |
| Dashboard cannot read fixture JSON directly | Fixture-mode route in `lottery_api/routes/replay.py` (PR #53) |
| OFFLINE taxonomy undecided | CTO decision memo: Route B — OFFLINE deferred (PR #57) |
| Core endpoint contract not synced with taxonomy | Contract P10 → P11, OFFLINE prohibition + fixture scope written (PR #59) |
| Lifecycle taxonomy doc not locked | Taxonomy update doc with formal states table (PR #58) |

---

## 8. Deferred / Out of Scope

| Item | Reason Deferred |
|---|---|
| P23 UI Toggle Button (`fixture_mode` toggle in UI) | Not required for governance closure; separate UX decision |
| Production DB backfill evaluation | Requires separate decision memo + CTO YES gate |
| OFFLINE lifecycle future introduction SOP | 7 prerequisites must be met first; none currently met |
| User-facing visual walkthrough / operation screenshots | Optional; can be produced on request |

---

## 9. CTO Recommended Next Steps

| Priority | Option | Description |
|---|---|---|
| Product UX | **Option A: P23 Fixture Mode UI Toggle Button** | Add explicit toggle in UI for `fixture_mode`; currently only API-level |
| Governance | **Option B: Production Replay Backfill Decision Memo** | Decide whether/how to backfill historical replay data to production DB |
| Operations | **Option C: Daily CTO Handoff Report** | Summarise system state, open items, and pending decisions |

**Not recommended now:** strategy mining / edge discovery — no governance basis yet.

---

## 10. Next-Round Executable Prompts

Use any of the following to start the next round:

```
Option A: P23 Fixture Mode UI Toggle Button
→ Add fixture_mode toggle button to the replay section in index.html.
  No DB write, no registry change, UI-only change.

Option B: Production Replay Backfill Decision Memo
→ Produce a CTO decision memo on whether to backfill historical replay data
  to data/lottery_v2.db. Present options, risks, and a YES/NO gate.

Option C: Daily CTO Handoff Report
→ Produce a structured daily handoff report covering:
  system state, open PRs, deferred items, and recommended next action.
```

---

## 11. Final Governance Markers

```
STRATEGY_LIFECYCLE_ENDPOINT_CONTRACT_PR59_MERGED_TO_MAIN
REPLAY_FIXTURE_LIFECYCLE_GOVERNANCE_FINAL_CLOSURE_READY
REPLAY_FIXTURE_LIFECYCLE_GOVERNANCE_FINAL_DB_CLEAN
```

---

## 12. Related Files

| File | Role |
|---|---|
| `docs/replay/strategy_lifecycle_endpoint_contract.md` | Core endpoint contract (P11) |
| `outputs/replay/replay_lifecycle_taxonomy_update_20260511.md` | Lifecycle taxonomy lock |
| `outputs/replay/offline_classification_decision_memo_20260511.md` | OFFLINE classification decision (Route B) |
| `outputs/replay/replay_fixture_mode_sop_user_guide_20260511.md` | SOP + User Guide for fixture mode |
| `outputs/replay/strategy_lifecycle_endpoint_contract_update_20260511.md` | Contract P11 update report |
| `outputs/replay/non_online_replay_fixture_20260511.json` | Synthetic fixture artifact (10 records) |
| `lottery_api/routes/replay.py` | Fixture mode API bridge |
| `tests/test_replay_api_contract.py` | 44 contract tests (all passing) |
| `tests/test_replay_browser_smoke.py` | 34 browser smoke tests (all passing) |
