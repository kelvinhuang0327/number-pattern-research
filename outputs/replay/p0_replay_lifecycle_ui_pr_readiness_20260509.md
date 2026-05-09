# P0 Replay Lifecycle UI — PR Readiness Review
**Date:** 2026-05-09  
**Reviewer:** P0-Replay-UI Review Executor  
**Branch:** codex/p0-replay-lifecycle-ui-20260509  
**Commit:** 21527b7  
**Report to:** CTO Agent

---

## Executive Summary

The P0 Replay Lifecycle UI branch passes all automated checks and satisfies the CEO-calibrated product goal: the `#replay-section` page now displays **all registered strategies across all lifecycle states** (ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED), with a working lifecycle filter dropdown, per-row lifecycle badge, and reject_reason column. The API contract is backward-compatible. All 63 tests pass. No DB binaries, no active strategy state, no branch protection changes in scope.

**Decision: P0_REPLAY_LIFECYCLE_UI_PR_READY**

Two non-blocking housekeeping notes documented below.

---

## Branch / Commit Verification

| Check | Result |
|-------|--------|
| Branch exists | ✅ `codex/p0-replay-lifecycle-ui-20260509` |
| Commit exists | ✅ `21527b7c1271c20186385e0f549dba420433fec6` |
| Parent | ✅ `32fc1c8` (main HEAD at time of branch) |
| Files in commit | ✅ Exactly 6 — all within COMMIT RULES |
| No DB binaries | ✅ CLEAN — no `.db` / `.db-wal` / `.db-shm` |
| No active strategy files | ✅ CLEAN — no H6 / orchestrator / production outcome files |
| No branch protection change | ✅ Not in scope |
| No force push / direct push main | ✅ PR flow only |
| Ahead of main by | 1 commit |

**Housekeeping note:** Commit `7306264` on `auto/inbox/20260430` has the **identical tree** (`288c0ee`) as `21527b7`. This is a pre-existing artefact of the working branch state and does not affect the P0 branch or PR. No action required for this PR; clean-up of `auto/inbox/20260430` can be done separately.

---

## Files Reviewed

| File | In scope | Overreach | Product gap | Hotfix needed |
|------|----------|-----------|-------------|---------------|
| `lottery_api/models/replay_strategy_registry.py` | ✅ | None | None | No |
| `lottery_api/routes/replay.py` | ✅ | None | Minor (see §API) | No |
| `index.html` | ✅ | None | None | No |
| `outputs/replay/p0_replay_lifecycle_ui_20260509.md` | ✅ | None | None | No |
| `outputs/replay/p0_replay_lifecycle_coverage_20260509.md` | ✅ | None | None | No |
| `outputs/replay/p0_replay_lifecycle_schema_diff_20260509.json` | ✅ | None | None | No |

---

## Lifecycle SSOT Review

| Check | Result |
|-------|--------|
| 5 canonical values present | ✅ ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED |
| `ACTIVE` not in canonical adapter output | ✅ All 6 adapters use `status="ONLINE"` |
| `ACTIVE` accepted as backward-compat alias | ✅ `_LEGACY_STATUS_MAP = {"ACTIVE": "ONLINE"}` |
| `normalise_lifecycle_status()` exists | ✅ |
| `_GENERATION_STATUSES = {"ONLINE", "ACTIVE"}` | ✅ Correct — generation still works for any ACTIVE alias |
| `list_strategies()` returns ALL by default | ✅ No filter → all lifecycle states returned |
| `lifecycle_status` filter on `list_strategies()` | ✅ Optional, normalised before matching |
| `get_strategy_lifecycle_status()` helper | ✅ Used by /history row enrichment |
| DB schema unchanged | ✅ In-memory only; migration plan documented but NOT executed |
| Active strategy state unchanged | ✅ ONLINE = functional rename only; no governance transition |
| H6 state unchanged | ✅ Not in commit |

---

## Coverage Audit Review

| Check | Result |
|-------|--------|
| `p0_replay_lifecycle_coverage_20260509.md` exists | ✅ |
| Coverage gap = 0 | ✅ **Coverage Gaps: 0** (all 6 ONLINE strategies have replay rows) |
| `REPLAY_ERROR` / `FAILED_LEGACY` correctly distinguished | ✅ 20 legacy errors from run #3 correctly noted as non-gap |
| 0 OFFLINE / REJECTED / OBSERVATION / RETIRED strategies noted | ✅ |
| Report defers non-ONLINE states to future catalog | ✅ "infrastructure is in place for future state transitions" |
| Report does NOT falsely claim product-complete for non-ONLINE states | ✅ |
| No replay generation triggered | ✅ Explicitly noted in report |

**Product gap clarification:** The page UI supports all 5 lifecycle states. The absence of OFFLINE/REJECTED/OBSERVATION/RETIRED data is a catalog gap (no such strategies exist yet), not a code gap. This is the correct interpretation and is properly documented.

---

## API Contract Review

### GET /api/replay/strategies
| Check | Result |
|-------|--------|
| `lifecycle_status` query param added | ✅ |
| Returns ALL states when `lifecycle_status=None` | ✅ |
| `strategy_lifecycle_status` field in each entry | ✅ |
| `filter_lifecycle_status` in response | ✅ |
| Backward-compat `filter` key retained | ✅ |
| Invalid `lifecycle_status` behaviour | ℹ️ Silent empty result (no 422) — acceptable for P0 |

### GET /api/replay/history
| Check | Result |
|-------|--------|
| `lifecycle_status` query param added | ✅ |
| `strategy_lifecycle_status` per record | ✅ |
| Existing filters unchanged (lottery_type, strategy_id, replay_status, dates) | ✅ |
| `filter_lifecycle_status` in response | ✅ |
| Read-only disclaimer preserved verbatim | ✅ |
| `isinstance(lifecycle_status, str)` guard for direct-call test compat | ✅ Correct — prevents `Query()` object from being passed to `.upper()` when tests call routes directly |
| Empty lifecycle_strategy_ids short-circuit returns cleanly | ✅ |

**Minor note:** The `isinstance(str)` guard is non-standard but technically sound for the P0 context. A P1 refactor could introduce a pure function layer that FastAPI wraps, removing the guard.

---

## Frontend UI Review

All 27 static checks passed:

| Category | Checks | Result |
|----------|--------|--------|
| Lifecycle filter dropdown | `rp-lifecycle-select` exists, all 5 options (ONLINE/OFFLINE/REJECTED/OBSERVATION/RETIRED) + 全部 | ✅ 6/6 |
| Lifecycle badge | `rpLifecycleBadge()` function, badge column header `生命週期`, `strategy_lifecycle_status` used in rows | ✅ 3/3 |
| Reject reason | `拒絕原因` column header, `reject_reason` in row render | ✅ 2/2 |
| Required columns | target_draw, target_date, strategy_id, replay_status, predicted_numbers, actual_numbers, hit_numbers, hit_count | ✅ 8/8 |
| Table structure | `colspan="11"` (was 9), no regression | ✅ |
| URL state | `rp_lc` param written in `rpUpdateURL`, restored in `rpRestoreFromURL`, `validLC` list | ✅ 3/3 |
| Disclaimer | `不代表提高中獎率` preserved in negation context | ✅ |
| Limited coverage note | `LIMITED` / `limited coverage` present | ✅ |
| No new frontend framework | No React/Vue/Angular imports | ✅ |
| No forbidden tokens in output | NO_SIGNAL / NO_VALIDATED_EDGE not in output context | ✅ |

---

## Validation Results

| Suite | Count | Status |
|-------|-------|--------|
| `test_replay_api_contract.py` | 25 passed | ✅ |
| `test_replay_freshness_cadence.py` | 8 passed | ✅ |
| `test_replay_browser_smoke.py` | 30 passed | ✅ |
| **Total** | **63 passed / 0 failed** | ✅ |

**SKIPPED — `scripts/run_replay_ci_default_validation.py`:** File does not exist in the repository (pre-existing gap; not introduced by this PR). The task spec references this script but it was never committed. Equivalent validation was performed via `pytest` on the 3 test files above. This is not a blocker for PR.

**SKIPPED — `/Library/Developer/CommandLineTools/usr/bin/python3`:** macOS system binary not available in the Linux sandbox. Irrelevant to test execution (tests use `python3` from PATH).

---

## Product Readiness Assessment

The CEO's calibration goal is:

> "策略歷史回放頁面能顯示所有開發過的策略，含上線/下線/拒絕/觀察/退役，並針對每一期顯示預測 vs 實際開獎對照清單。"

| Criterion | Status |
|-----------|--------|
| Page displays all lifecycle states | ✅ UI supports all 5 states |
| Lifecycle filter dropdown | ✅ 全部/上線/下線/拒絕/觀察/退役 |
| Per-row lifecycle badge | ✅ Colour-coded badge in table |
| Predicted vs actual per draw | ✅ predicted_numbers / actual_numbers / hit_numbers / hit_count |
| Reject reason visible | ✅ Column added |
| Currently only ONLINE strategies have data | ✅ Expected — catalog gap, not code gap |
| Infrastructure ready for future lifecycle states | ✅ |

**Product completeness:** UI is **infrastructure-complete for all lifecycle states**. Data completeness for OFFLINE/REJECTED/OBSERVATION/RETIRED states depends on future strategy catalog population — correctly documented and out of scope for P0.

---

## PR Readiness Decision

**P0_REPLAY_LIFECYCLE_UI_PR_READY**

All blocking criteria satisfied:
- ✅ Branch exists and is correctly parented to main
- ✅ Commit 21527b7 contains exactly the 6 allowed files
- ✅ No DB binaries, no active strategy state, no branch protection change
- ✅ API contract backward-compatible
- ✅ UI requirements fully satisfied (27/27 checks)
- ✅ 63 tests pass / 0 fail
- ✅ Disclaimers and read-only semantics preserved

---

## Required Hotfixes Before PR

**None.** The branch is PR-ready as-is.

---

## PR Created / Manual PR Command

`gh` CLI is not authenticated in this environment. Use the following command in a terminal with GitHub access:

```bash
gh pr create \
  --base main \
  --head codex/p0-replay-lifecycle-ui-20260509 \
  --title "feat(replay-ui): expose all-lifecycle strategy replay history" \
  --body "## Summary

Exposes all lifecycle states (ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED)
in the Strategy Historical Replay page (#replay-section).

## Changes

**P0-A — Lifecycle SSOT (replay_strategy_registry.py)**
- Expanded status enum from ACTIVE/RETIRED to 5 canonical values
- ACTIVE accepted as backward-compat alias → normalised to ONLINE
- list_strategies() returns ALL states by default; lifecycle_status filter added
- get_strategy_lifecycle_status() helper for API row enrichment

**P0-C — API Lifecycle Filter (routes/replay.py)**
- /api/replay/strategies: new lifecycle_status query param
- /api/replay/history: new lifecycle_status query param + strategy_lifecycle_status per record
- All existing filters, disclaimers, and read-only semantics unchanged

**P0-D — Frontend UI (index.html)**
- Lifecycle filter dropdown: 全部/上線/下線/拒絕/觀察/退役
- Lifecycle badge column (colour-coded) in history table
- Reject reason column (truncated, hover tooltip)
- URL state persistence (rp_lc param)

**P0-B — Coverage Audit (outputs/replay/)**
- 0 coverage gaps across all 6 ONLINE strategies
- FAILED_LEGACY rows correctly distinguished from coverage gaps
- Schema diff / migration plan documented (not executed)

## Validation
63 passed / 0 failed (test_replay_api_contract + test_replay_freshness_cadence + test_replay_browser_smoke)

## Hard Scope Boundaries
- No DB modified, no active strategy state changed, no branch protection changed
- No replay generation triggered, no edge discovery, no H6 modification

## Product Note
UI is infrastructure-complete for all lifecycle states.
OFFLINE/REJECTED/OBSERVATION/RETIRED data requires future strategy catalog population."
```

Alternatively, open a PR via GitHub web UI from branch `codex/p0-replay-lifecycle-ui-20260509` → `main`.

---

## Files Created / Modified

| File | Action |
|------|--------|
| `outputs/replay/p0_replay_lifecycle_ui_pr_readiness_20260509.md` | Created (this report) |

No code files modified in this review pass.

---

## Commit / Push Result

Readiness report committed to `codex/p0-replay-lifecycle-ui-20260509`:

```
docs(replay): record lifecycle ui pr readiness review
```

---

## What Was Not Changed

- `lottery_api/models/replay_strategy_registry.py` — not modified in review pass
- `lottery_api/routes/replay.py` — not modified in review pass
- `index.html` — not modified in review pass
- Production DB / `*.db` / `*.db-wal` / `*.db-shm` — untouched
- Active strategy state / H6 files — untouched
- Branch protection settings — untouched
- `docs/archive/`, `memory/`, `wiki/` — untouched
- PR #2 (`codex/p1-6g-branch-protection-execution`) — not touched; parallel flow

---

## Remaining Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| OFFLINE/REJECTED/OBSERVATION/RETIRED filter shows 0 results until catalog populated | Low | Expected; UI shows "查無資料" correctly |
| `isinstance(str)` guard for direct-call test compat is non-standard | Low | Acceptable for P0; P1 refactor to pure function recommended |
| Invalid lifecycle_status silently returns empty (no 422) | Low | Acceptable for P0; add explicit validation in P1 |
| Duplicate commit `7306264` on `auto/inbox/20260430` (identical tree) | Cosmetic | Housekeeping-only; does not affect this PR |
| `scripts/run_replay_ci_default_validation.py` missing from repo | Low | Pre-existing gap; equivalent coverage via pytest |

---

## Follow-up Tasks

| ID | Title | Priority |
|----|-------|----------|
| P1-replay-ui-e2e | Live browser E2E test for lifecycle filter interaction | P1 |
| P1-lifecycle-drift-guard | CI check for registry vs DB state divergence | P1 |
| P1-lifecycle-db-migration | Implement `strategy_lifecycle` DB table | P1 |
| P1-lifecycle-422-validation | Return 422 for invalid lifecycle_status values | P1 |
| P1-lifecycle-pure-function | Refactor route functions to pure functions wrapped by FastAPI | P1 |
| housekeeping | Clean up `auto/inbox/20260430` duplicate commit | Low |
| housekeeping | Add `scripts/run_replay_ci_default_validation.py` to repo | Low |

---

## Final Marker

**P0_REPLAY_LIFECYCLE_UI_PR_READY**
