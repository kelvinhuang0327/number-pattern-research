# CTO Analysis - Replay Strategy Catalog After P31B + P32

## 1. CTO Review Date

2026-05-23 Asia/Taipei (P33 update after P31B Wave 1 production apply + P32 UI/API verification)

## 2. Input Sources

- [Confirmed] `PROJECT_CONTEXT_LOCK` for this run:
  - Project: LotteryNew
  - Canonical repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
  - Canonical branch: `main`
- [Confirmed] git state during P33 CTO review:
  - repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
  - branch: `main`
  - HEAD: `e704154 P32: replay UI/API verification after P31B apply (#168)`
  - prior relevant commits: `f6b05e8` P31B, `7d359c9` P31A, `2b6a657` P30, `8f9b2ce` P29
- [Confirmed] `00-Plan/roadmap/roadmap.md` before this update: described P31A/P31B/P32 as blocked/not started.
- [Confirmed] `00-Plan/roadmap/CTO-Analysis.md` before this update: described state after P30 only.
- [Confirmed] P31A evidence:
  - `docs/replay/p31a_wave1_daily539_retired_adapter_readiness_20260523.md`
  - `outputs/replay/p31a_wave1_daily539_retired_adapter_readiness_20260523.json`
  - PR #166; HEAD `7d359c9`; no-db-write confirmed
- [Confirmed] P31B evidence:
  - `docs/replay/p31b_wave1_daily539_retired_production_apply_20260523.md`
  - `outputs/replay/p31b_wave1_daily539_retired_production_apply_20260523.json`
  - PR #167; HEAD `f6b05e8`; production rows 12460 → 19960; 257 tests passed
  - `controlled_apply_id = "P31B_DAILY539_RETIRED_7500_PROD_20260523"`
- [Confirmed] P32 evidence:
  - `docs/replay/p32_replay_post_p31b_verification_20260523.md`
  - `outputs/replay/p32_replay_post_p31b_verification_20260523.json`
  - PR #168; HEAD `e704154`; 126 tests passed; production rows unchanged at 19960
- [Confirmed] P33 pre-flight verification:
  - production rows: 19960
  - `scripts/replay_lifecycle_drift_guard.py --strict` → PASS
  - `scripts/replay_branch_governance_guard.py --expected-branch main --expected-rows 19960` → PASS
  - branch: `main`

## 3. Roadmap Alignment Assessment

| Finding | Classification | CTO Assessment |
|---|---|---|
| Project lock now matches workspace | [Aligned] | The repo and branch match `LotteryNew`, `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`, and `main`. |
| P29 is merged to main | [Aligned] | Commit `8f9b2ce` and P29 docs confirm catalog UI exists. |
| P30 is merged to main | [Aligned] | Commit `2b6a657` and P30 docs/output confirm 51 non-row-backed strategies classified. |
| P31A is merged to main | [Aligned] | PR #166 (`7d359c9`): 5 DAILY_539 retired adapter wrappers wired; 7500 dry-run rows; no production DB write. |
| P31B is merged to main | [Aligned] | PR #167 (`f6b05e8`): Wave 1 production apply; 12460 → 19960 rows; 257 tests passed. |
| P32 is merged to main | [Aligned] | PR #168 (`e704154`): UI/API verification; 5 retired strategies queryable; 126 tests passed. |
| Previous roadmap described P31A/P31B as blocked | [Outdated] | P31A, P31B, P32 are all complete; roadmap updated in P33. |
| Date-range default half-year | [Missing] | P29/P32 observed this requested UX behavior is absent. Now P0 for P34. |
| Retired replay-backed labeling clarity in UI | [Missing] | RETIRED replay-backed strategies are queryable but `queryable=False` in catalog; UX gap. Now P0 for P34. |
| Wave 2 / manual-review cadence | [Missing] | P31B Wave 1 complete; 19 `needs_promotion` and 15 `manual_review` strategies need P35 planning. |
| Catalog freshness guard | [Drift] | Still P3; deferred behind P34 UI closure. |
| Incremental replay refresh design | [Drift] | Still P4; deferred behind P34 and Wave 2 planning. |

## 4. Completed Work Assessment

- [Confirmed] P29 Replay Strategy Catalog UI Section is complete and merged.
- [Confirmed] P30 Reconstructible-Candidacy Evaluation is complete and merged. `needs_promotion=24`, `manual_review=15`, `executable_no=12`.
- [Confirmed] P31A Wave 1 DAILY_539 Retired Adapter Readiness is complete and merged (PR #166):
  - 5 retired DAILY_539 adapter wrappers wired.
  - 7500 dry-run candidate rows generated (1500 × 5 strategies).
  - Temp DB rehearsal passed.
  - Production rows remained 12460 throughout P31A.
  - No production DB write in P31A.
- [Confirmed] P31B Wave 1 Production Apply is complete and merged (PR #167):
  - `controlled_apply_id = "P31B_DAILY539_RETIRED_7500_PROD_20260523"`
  - 7500 rows inserted: 5 strategies × 1500 rows each.
  - Production rows advanced from 12460 to 19960.
  - `dry_run=0` confirmed for all inserted rows.
  - `truth_level = "DAILY539_RETIRED_STRATEGY_BACKFILL_VERIFIED"`
  - Duplicate detection passed; drift guard PASS; governance guard PASS.
  - 257 tests passed.
- [Confirmed] P32 Replay UI/API Verification Post-P31B is complete and merged (PR #168):
  - All 5 DAILY_539 retired strategies confirmed queryable via `/api/replay/history`.
  - API: `total=1500` per strategy, `total=7500` with lifecycle filter RETIRED.
  - UI smoke: `共 7500 筆`, catalog panel `RETIRED=5`.
  - 126 tests passed.
  - Production rows confirmed unchanged at 19960.
  - Drift guard PASS; governance guard PASS.
- [Confirmed] P33 pre-flight at time of this analysis:
  - branch: `main`, HEAD: `e704154`
  - production rows: 19960
  - drift guard: PASS
  - governance guard: PASS

## 5. Unfinished Work Assessment

- [Missing] P34 date-range default half-year has not been implemented. Observed in P29 and P32 reviews.
- [Missing] P34 UI/catalog labeling for RETIRED replay-backed strategies: `queryable=False` in catalog can confuse operators. UI should clarify that these 7500 rows are accessible via lifecycle filter.
- [Missing] P35 Wave 2 candidate planning: 19 remaining `needs_promotion` strategies have no ranked plan.
- [Missing] P36 Wave 2 dry-run / temp rehearsal: cannot apply Wave 2 rows without adapter readiness evidence.
- [Deferred] Catalog freshness guard (P3): not started.
- [Deferred] Incremental replay refresh design (P4): not started.
- [Deferred] Manual-review strategy resolution (P5): 15 strategies in holding state.
- [Deferred] Performance/pagination hardening (P6): not tested at 19960+ row scale.
- [Deferred] Artifact consolidation (P8): P21B-P33 evidence not indexed.
- [Inferred] `executable_no=12` should remain out of apply waves unless new evidence overturns P30.

## 6. P0 / P1 / P2 / P3-P10 Reprioritization

| Priority | Phase | Decision |
|---|---|---|
| P0 | P34 UI usability gap | New immediate: half-year date default + retired replay-backed labeling clarity in UI/catalog. No production DB write. |
| P1 | P35 Wave 2 candidate planning | Plan remaining 19 `needs_promotion` strategies from P30. No production write. |
| P2 | P36 Wave 2 dry-run / temp rehearsal | Dry-run and temp DB rehearsal for Wave 2 candidates. Production rows remain 19960. |
| P3 | Catalog freshness guard | Read-only guard for P24/P28/P29/P30 catalog drift. |
| P4 | Incremental replay refresh design | Future-draw maintenance design after Wave 1 coverage. |
| P5 | Manual-review strategy resolution | Resolve 15 `manual_review` strategies with a rubric. |
| P6 | Performance and pagination hardening | Prepare for row growth from 19960 to 28960+. |
| P7 | Apply authorization governance hardening | Formalize multi-wave apply authorization. |
| P8 | Artifact consolidation | Index P21B-P33 reports, outputs, and test evidence. |
| P9 | Post-launch operations | Monitor future draws, stale replay rows, stale strategy states. |
| P10 | Wave 2 production apply (gated) | Apply Wave 2 rows after P35/P36 pass and explicit YES gate. |

Changes from prior roadmap:

- [Confirmed] P31A is complete and retired as active blocker.
- [Confirmed] P31B is complete and retired as active blocker. Production rows now 19960.
- [Confirmed] P32 is complete and retired as active blocker. API/UI verified.
- [Confirmed] P34 becomes the new P0: UI usability gap (half-year default + RETIRED labeling clarity).
- [Confirmed] P35 Wave 2 candidate planning becomes P1.
- [Confirmed] P36 Wave 2 dry-run becomes P2.
- [Confirmed] Catalog freshness guard remains P3.
- [Confirmed] Incremental replay refresh remains P4.
- [Confirmed] Manual-review resolution deferred to P5.
- [Inferred] Broad UI redesign remains paused; CEO wants existing historical prediction-list style.

## 7. Critical Blockers

## 7. Critical Blockers

### Blocker 1: Date-Range Default Half-Year Is Absent

- **Impact scope:** Replay page usability.
- **Why blocker:** User explicitly expects a half-year default date range; observed in P29 and confirmed absent in P32.
- **Risk if ignored:** Replay page remains usable but not aligned with desired default workflow.
- **Priority:** P0 (P34)
- **Acceptance:** Replay page defaults to half-year date range while 100/500/1000/1500 presets and pagination pass browser smoke.

### Blocker 2: Retired Replay-Backed Strategy Labeling Unclear

- **Impact scope:** Catalog/UI trust and operator discoverability.
- **Why blocker:** P31B inserted 7500 rows for 5 RETIRED DAILY_539 strategies, but the catalog still shows `queryable=False` and `row_count=0` for them. Operators may not know to use the lifecycle filter.
- **Risk if ignored:** 7500 replay rows remain hidden to operators who do not know the workaround.
- **Priority:** P0 (P34)
- **Acceptance:** UI or catalog clearly communicates that RETIRED replay-backed strategies (5 strategies, 7500 rows) are queryable via lifecycle filter; no ONLINE relabeling.

### Blocker 3: Wave 2 Candidate Plan Missing

- **Impact scope:** Medium-term replay coverage expansion.
- **Why blocker:** P31B Wave 1 proved the apply pipeline, but 19 remaining `needs_promotion` strategies have no plan.
- **Risk if ignored:** Coverage expansion stalls at 19960 rows.
- **Priority:** P1 (P35)
- **Acceptance:** Ranked Wave 2 plan: scope, effort, lottery type, expected rows per strategy; no production write.

### Blocker 4: Wave 2 Dry-Run / Temp Rehearsal Not Done

- **Impact scope:** Data integrity for next apply wave.
- **Why blocker:** The P31A rehearsal pattern must be applied before any Wave 2 production apply.
- **Risk if ignored:** Unsafe production write without adapter readiness evidence.
- **Priority:** P2 (P36)
- **Acceptance:** Wave 2 strategies generate dry-run rows; temp DB rehearsal passes; production rows remain 19960; no production DB write.

## 8. Recommended System Optimization Directions

### 1. P34 Replay UI Usability Gap Closure

- **Roadmap phase:** P0
- **Why important:** Wave 1 is live (19960 rows). Operators must be able to discover and use RETIRED replay-backed rows without confusion.
- **System maturity gain:** Closes the date-range default gap and RETIRED labeling clarity without schema changes or production DB writes.
- **Expected benefit:** Half-year default UX; RETIRED strategies surfaced clearly to operators via lifecycle filter guidance.
- **Risk:** Date default can conflict with period preset if not tested carefully.
- **Acceptance:** Half-year default exists; presets/pagination pass browser smoke; RETIRED labeling does not confuse with ONLINE.
- **Priority:** P0

### 2. P35 Wave 2 Candidate Planning

- **Roadmap phase:** P1
- **Why important:** P31B Wave 1 proved the apply pipeline. Keeping 19 remaining `needs_promotion` strategies without a plan stalls medium-term coverage expansion.
- **System maturity gain:** Extends governance from 5-strategy Wave 1 to ranked multi-lottery Wave 2 candidates.
- **Expected benefit:** Ranked, evidence-backed list for the next apply wave.
- **Risk:** Planning too broadly before P34 UX closure can blur priorities.
- **Acceptance:** Wave 2 list includes scope, effort, lottery type, expected rows; no production write.
- **Priority:** P1

### 3. P36 Wave 2 Dry-Run / Temp Rehearsal

- **Roadmap phase:** P2
- **Why important:** The P31A dry-run pattern is proven governance. Must be applied to Wave 2 before any production apply.
- **System maturity gain:** Maintains rehearsal-before-apply safety for each apply wave.
- **Expected benefit:** Confirms Wave 2 adapters generate correct rows; catches issues before production.
- **Risk:** Skipping rehearsal risks applying rows with incorrect prediction metadata.
- **Acceptance:** Wave 2 dry-run rows generated; temp DB rehearsal passes; production rows remain 19960.
- **Priority:** P2

### 4. Catalog Freshness Guard

- **Roadmap phase:** P3
- **Why important:** P24/P28/P29/P30/P31B have all expanded the catalog and row store; guard prevents future drift.
- **System maturity gain:** Automates the manual cross-check done in every CTO review.
- **Expected benefit:** Read-only guard catches catalog/registry divergence early.
- **Risk:** Over-engineering can slow iteration.
- **Acceptance:** Read-only guard; no DB writes; alert on divergence.
- **Priority:** P3

### 5. Manual-Review Strategy Resolution

- **Roadmap phase:** P5
- **Why important:** P30 left 15 `manual_review` strategies in holding state; these need human judgment.
- **System maturity gain:** Converts an open classification into actionable accept/reject decisions.
- **Expected benefit:** Shrinks the unknown pool and clarifies maximum replay coverage ceiling.
- **Risk:** Rushing decisions on complex composites can produce wrong coverage estimates.
- **Acceptance:** Decision rubric separates monitoring frameworks, unclear composites, and true executable candidates.
- **Priority:** P5

## 9. Roadmap Changes Applied

- [Confirmed] Updated `00-Plan/roadmap/roadmap.md` to reflect main HEAD `e704154` (post P31B + P32 merge).
- [Confirmed] Marked P31A Wave 1 adapter readiness as complete and merged (PR #166).
- [Confirmed] Marked P31B Wave 1 production apply as complete and merged (PR #167).
- [Confirmed] Marked P32 UI/API verification as complete and merged (PR #168).
- [Confirmed] Updated production row baseline to 19960.
- [Confirmed] Updated row-backed strategies count to 13 (8 ONLINE + 5 RETIRED replay-backed).
- [Confirmed] Added P31B Wave 1 row distribution table (5 strategies × 1500 rows).
- [Confirmed] Added note clarifying RETIRED strategies remain retired (no ONLINE promotion).
- [Confirmed] Updated catalog label summary with notes on RETIRED replay-backed behavior.
- [Confirmed] Set new P0 to P34 UI usability gap (half-year default + RETIRED labeling clarity).
- [Confirmed] Set new P1 to P35 Wave 2 candidate planning.
- [Confirmed] Set new P2 to P36 Wave 2 dry-run / temp rehearsal.
- [Confirmed] Demoted catalog freshness guard to P3, incremental refresh to P4.
- [Confirmed] Updated critical blockers to reflect post-P32 state.
- [Confirmed] Updated "Today's Focus" to P34.
- [Confirmed] Did not create a new repo.
- [Confirmed] Did not write production DB.
- [Confirmed] Did not modify `00-Plan/roadmap/CEO-Decision.md`.
- [Confirmed] Did not write `production/*`, `registry/*`, or `data/*`.
- [Confirmed] Did not change any strategy lifecycle to ONLINE.
- [Confirmed] Did not mutate `_REGISTRY` or `_ALL_ADAPTERS`.

## 10. Risks / Unknowns

- [Confirmed] Production DB row count is 19960 during P33 CTO review.
- [Confirmed] P32/replay API tests, drift guard, and branch governance guard pass during P33 review.
- [Confirmed] P31A, P31B, and P32 artifacts all exist and are merged.
- [Risk] RETIRED replay-backed strategies in the catalog still show `queryable=False`; without P34 UI labeling guidance, operators may not discover the lifecycle filter workaround.
- [Risk] 19 remaining `needs_promotion` strategies have no Wave 2 plan; coverage expansion may stall without P35 planning.
- [Risk] Wave 2 apply without rehearsal (P36) could corrupt replay rows; must maintain P31A rehearsal governance pattern.
- [Risk] Date-range default half-year remains absent; persistent UX mismatch.
- [Unknown] Performance behavior of the replay API/UI at 19960+ rows has not been tested under concurrent load.
- [Unknown] Whether 15 `manual_review` strategies will resolve to promotable or rejectable when human-reviewed.
- [Inferred] `executable_no=12` should remain out of apply waves unless new evidence overturns P30.

## 11. CTO Final Recommendation

P31A, P31B, and P32 are all complete. The replay store now holds 19960 production rows with 13 row-backed strategies (8 ONLINE + 5 RETIRED). The Wave 1 pipeline — adapter readiness, gated production apply, and post-apply verification — is proven.

Proceed next with P34: close the two identified UX gaps before starting Wave 2 planning. First, add a half-year date range default to the replay page. Second, surface clear UI/catalog guidance that the 5 RETIRED replay-backed strategies (7500 rows) are queryable via the lifecycle filter — without relabeling them as ONLINE.

After P34 is merged, proceed with P35 Wave 2 candidate planning for the 19 remaining `needs_promotion` strategies, followed by P36 dry-run / temp rehearsal before any Wave 2 production apply.

Do not apply Wave 2 rows without both P35 planning evidence and P36 rehearsal evidence. Do not promote any RETIRED strategy to ONLINE.

## 12. CTO Summary In 10 Lines

1. [Confirmed] Project lock matches LotteryNew on `main` at HEAD `e704154`.
2. [Confirmed] P31A merged (PR #166): 5 DAILY_539 retired adapter wrappers wired; 7500 dry-run rows; no production DB write.
3. [Confirmed] P31B merged (PR #167): Wave 1 production apply; 12460 → 19960 rows; `controlled_apply_id = P31B_DAILY539_RETIRED_7500_PROD_20260523`; 257 tests passed.
4. [Confirmed] P32 merged (PR #168): All 5 retired strategies confirmed queryable via API and UI; 126 tests passed.
5. [Confirmed] Production rows = 19960; drift guard PASS; governance guard PASS.
6. [Confirmed] P33 roadmap update: P31A/P31B/P32 marked complete; production baseline updated; P0-P10 reprioritized.
7. [Confirmed] New P0 = P34: date-range default half-year + RETIRED replay-backed labeling clarity.
8. [Confirmed] New P1 = P35: Wave 2 candidate planning (19 remaining `needs_promotion` strategies).
9. [Confirmed] New P2 = P36: Wave 2 dry-run / temp rehearsal before any Wave 2 production apply.
10. [Confirmed] No production DB write, no CEO-Decision.md modification, no ONLINE promotion, no registry mutation in P33.

Final Classification: P33_ROADMAP_UPDATE_AFTER_P31B_P32_MERGED_TO_MAIN
