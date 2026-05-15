# LotteryNew — Master Roadmap Recalibration (2026-05-10)

**Version:** 2026-05-10 CTO product recalibration v1.9  
**Author:** CTO Agent  
**Effective date:** 2026-05-10  
**Supersedes:** `00-LotteryPlan/20260508/lottery_roadmap_20260508.md` v1.7  
**Primary source inputs:**
- Initial roadmap / daily planning prompt in `00-LotteryPlan/20260507/20260507.md`
- Daily handoff in `00-LotteryPlan/20260508/20260508.md`
- CTO/CEO analysis in `00-LotteryPlan/20260508/CTO_DAILY_ANALYSIS_20260509.md`
- Phase 4 handoff supplied on 2026-05-10
- Local repo state inspected on 2026-05-10

---

## 1. CTO Executive Decision

The roadmap must be corrected again around the real product objective:

```text
Ship Strategy Historical Replay as a read-only audit page.
```

The page must let the operator filter and inspect every strategy lifecycle
state already represented in the system: `ONLINE`, `OFFLINE`, `REJECTED`,
`OBSERVATION`, and `RETIRED`. For each strategy and historical draw, the user
must be able to see the predicted numbers beside the actual drawn numbers, with
hit count / hit numbers, in a table that matches the existing historical
prediction-record interaction pattern.

This is not a strategy promotion project and not an H6 rollback-monitoring
project. Replay remains an audit surface only: no edge claim, no betting
recommendation, no automatic lifecycle transition.

Therefore the next system optimization direction is:

```text
P0 — Replay Product Go-Live Closure on a clean origin/main branch.
```

The previous Phase 4 clean-branch objective remains necessary, but only as the
delivery vehicle. H6 CLI/E2E monitoring tests are no longer allowed to block the
Replay P0 unless `engine.h6_live_monitor` is explicitly included as a separate
H6 monitoring lane. The current clean worktree proves that `engine.h6_live_monitor`
is absent from `origin/main`; treating it as a Replay required-check asset would
expand scope into production rollback monitoring and violate the product P0
boundary.

---

## 2. Current System State

| Area | Current state | CTO assessment |
|---|---|---|
| Remote product baseline | `origin/main` includes replay empty-state honesty and replay API skeleton | Good base for product closure |
| Replay API | `/api/replay/strategies`, `/history`, `/summary`, `/runs`, `/freshness` exist | Needs contract hardening for full lifecycle display and data-scope consistency |
| Replay UI | `index.html` contains lifecycle filters and replay history table | Needs non-empty-state acceptance and parity with historical prediction list UX |
| Registry | Clean branch registry lists only six `ONLINE` adapters | Not enough for "all developed strategies"; lifecycle catalog must expand without enabling generation for non-ONLINE states |
| Replay DB | `strategy_prediction_replays` and `strategy_replay_runs` are source-of-truth | Product depends on canonical rows, not `outputs/replay/` artifacts |
| Phase 4 branch | Old branch has green CI but unrelated history | Delivery blocker only; rebuild on clean branch |
| Clean worktree | `feature/phase4-required-check-clean-20260510` exists, based on `origin/main` | Correct workspace for product PR, but scope needs reset |
| H6 blocker | `tests/test_h6_cli_scripts.py` fails because `engine.h6_live_monitor` is absent | H6 monitoring lane, not Replay P0 |
| Manifest | Locked manifest exists, but includes H6 tests | Must be revised to exclude H6 from Replay product P0 |
| Branch protection | `replay-default-validation` remains required; dedicated DB lane not required | Correct; do not change until clean PR observation evidence exists |

---

## 3. Roadmap Alignment Assessment

### 3.1 Still Aligned

| Direction | Status | Notes |
|---|---|---|
| Protected main workflow | Aligned | Branch protection should remain enabled |
| Replay lifecycle honesty | Aligned and advanced | PR #11 closed the empty-state UX gap |
| Dedicated DB lane observation-first policy | Aligned | Do not promote to required without clean PR evidence |
| No strategy mining / no edge claims | Aligned | Remains a hard stop |
| No DB binary commits / no production DB writes | Aligned | Especially important for Phase 4 rebuild |
| Replay DB as SSOT | Aligned | UI/API must read DB tables, never `outputs/replay/` |

### 3.2 Misaligned / Stale

| Previous roadmap claim | Actual state | Correction |
|---|---|---|
| P0 is clean branch rebuild itself | Clean branch is a delivery vehicle, not the product goal | P0 becomes Replay Product Go-Live Closure |
| H6 CLI/E2E belongs to Phase 4 Replay required-check | It imports missing `engine.h6_live_monitor` and touches rollback monitoring | Move to independent H6 lane; do not block Replay product PR |
| Six ONLINE adapters satisfy strategy coverage | User goal requires all developed lifecycle states | Add canonical lifecycle catalog/backfill as P0/P1 |
| REJECTED promotion can be first product step | It covers only one lifecycle state | Treat as part of broader lifecycle catalog, not standalone first goal |
| Dedicated DB lane can proceed from green CI branch | Branch has unrelated history and cannot PR | Green CI is insufficient; rebuild clean branch |
| Phase 4 asset set is clearly bounded | Manifest included non-Replay H6 tests | Update manifest and acceptance criteria |

---

## 4. Reordered Priority Ladder

### P0 — Replay Product Go-Live Closure

**Goal:** Make the Strategy Historical Replay page usable for the stated product
goal: all lifecycle states, every historical draw row, prediction vs actual
comparison, same interaction shape as the historical prediction list.

| Item | Acceptance criterion |
|---|---|
| Clean delivery branch | Branch is based on `origin/main`; merge-base exists |
| Lifecycle filters | UI/API support `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED` |
| Row-level comparison | Table shows target draw/date, strategy, predicted numbers, actual numbers, hit numbers/count, replay status, lifecycle status |
| Historical-list parity | Pagination/filtering/loading/empty states match the existing historical prediction record UX |
| Audit language | Page says replay is audit only; no edge claim, no betting recommendation |
| Source-of-truth | UI/API read DB tables only; `outputs/replay/` remains artifact-only |
| Validation | Replay API contract, browser smoke, fixture validation, no in-function import test pass |

### P1 — Lifecycle Catalog and Canonical Row Backfill

**Goal:** Expand from six `ONLINE` adapters to a canonical catalog that represents
all system-developed strategies without making non-ONLINE strategies generation
eligible.

| Item | Acceptance criterion |
|---|---|
| Catalog schema | Strategy metadata includes `strategy_id`, name, lottery, version, lifecycle, source provenance, generation eligibility |
| Non-ONLINE safety | `OFFLINE`, `REJECTED`, `OBSERVATION`, `RETIRED` can be displayed but are not replay-generated unless explicitly enabled |
| REJECTED subset | 15 schema-complete REJECTED rows may be promoted only with provenance |
| Blocked subset | 27 blocked REJECTED rows remain blocked until parse/schema repair |
| No fake rows | Missing lifecycle data appears as honest empty/candidate state, not invented history |

### P2 — Replay Data Completeness and Freshness

| Item | Acceptance criterion |
|---|---|
| Coverage mode | API returns `FULL`, `LIMITED`, or `UNKNOWN` consistently |
| Freshness | Latest `DONE` run per lottery is within cadence or marked stale |
| Causal integrity | `history_cutoff_draw < target_draw` is enforced and reported |
| Failed legacy visibility | Legacy errors are retained and clearly labeled |

### P3 — Clean Branch / Manifest / CI Delivery

| Item | Acceptance criterion |
|---|---|
| Manifest | Locked manifest includes Replay P0 assets only; H6 monitoring files excluded |
| No DB binaries | No `*.db`, `*.db-wal`, `*.db-shm` committed |
| Local validation | Product P0 tests pass on clean branch |
| CI smoke | Clean branch CI passes |
| PR | GitHub PR to `main` succeeds |

### P4 — Dedicated DB Lane Observation Evidence

| Item | Acceptance criterion |
|---|---|
| Fixture schema | Synthetic fixture mirrors required replay columns |
| Validator | Dedicated lane validates fixture only |
| Observation log | CI run IDs, head SHAs, conclusions, failure classes recorded |
| Required-check posture | Dedicated lane remains non-required until repeated green evidence exists |

### P5 — Replay UI Contract Hardening

| Item | Acceptance criterion |
|---|---|
| Canonical DOM | Badges include `data-lifecycle-status` and `data-replay-status` |
| Browser E2E | Tests assert canonical enum and visible localized labels |
| URL state | Filters/page state are restorable |

### P6 — H6 Monitoring Lane Separation

| Item | Acceptance criterion |
|---|---|
| Dependency decision | `engine.h6_live_monitor` either added with its deps in H6 lane or tests moved out of Replay PR |
| H6 validation | `test_h6_cli_scripts.py` and `test_h6_e2e_phase4.py` run only in H6 monitoring scope |
| No Replay blocking | Missing H6 module cannot block Replay P0 PR |

### P7 — Forbidden-Language Sweep Close-Loop

| Item | Acceptance criterion |
|---|---|
| Sweep lifecycle files | `index.html`, replay routes, registry, lifecycle docs |
| HIGH hits | 0 or explicitly justified |
| Product copy | No "best strategy", "edge ranking", "推薦投注", or promotion wording |

### P8 — Blocked Evidence Normalization

| Item | Acceptance criterion |
|---|---|
| 27 blocked rows | Each has repairable / irreparable / parse-fix classification |
| Secondary-source rule | README backfill requires explicit CTO approval |
| Provenance | Every repaired row has source hash or traceable source path |

### P9 — Branch Protection Report / PR #2 Cleanup

| Item | Acceptance criterion |
|---|---|
| PR #2 decision | Merge, close as superseded, or replace with current report |
| Docs | Branch protection state matches GitHub settings |
| Stale statements | Removed or marked superseded |

### P10 — Worktree / Branch Hygiene

| Item | Acceptance criterion |
|---|---|
| Dirty source worktree | Marked source-only, not implementation workspace |
| Unrelated-history branch | Documented as non-PR evidence branch |
| Clean standard | Future implementation starts from clean `origin/main` worktree |

---

## 5. Critical Blockers

1. **Product completeness blocker.**  
   Current registry in the clean branch exposes only six `ONLINE` strategies.
   The requested page needs all lifecycle states for all developed strategies.

2. **Canonical data blocker.**  
   UI/API can display only rows that exist in `strategy_prediction_replays` plus
   catalog metadata. `outputs/replay/` artifacts cannot be used as runtime data.

3. **H6 scope blocker.**  
   `tests/test_h6_cli_scripts.py` imports `engine.h6_live_monitor`, which exists
   only in the noisy source worktree and not in clean `origin/main`. This is a
   separate H6 monitoring/rollback dependency, not a Replay product dependency.

4. **Unrelated-history branch blocker.**  
   `feature/phase4-required-check-20260509` has green CI but no merge base with
   `main`, so it remains evidence only, not a PR branch.

5. **Noisy source checkout blocker.**  
   The current source worktree is useful for evidence and file recovery, but not
   safe for commit packaging.

---

## 6. Today's Most Focused Optimization Direction

```text
P0 — Replay Product Go-Live Closure
```

The best use of engineering attention today is to finish the replay page as a
truthful product surface: lifecycle filters, all eligible strategy catalog
states, row-level prediction-vs-actual comparison, DB-only source-of-truth, and
non-empty-state tests. The clean branch rebuild remains part of this work, but
H6 monitoring must be split out so it does not hold the replay product hostage.

---

## 7. Stop Rules

- Do not change branch protection.
- Do not make `replay-dedicated-db-validation` required.
- Do not merge Replay P0 automatically.
- Do not use the unrelated-history branch as a merge branch.
- Do not commit DB binaries.
- Do not write production DB during validation.
- Do not run replay generation unless the task is explicitly scoped as a read-only fixture/backfill dry-run.
- Do not run strategy mining or edge discovery.
- Do not modify active strategy state.
- Do not include H6 monitoring / rollback files in the Replay P0 PR.
- Do not claim Replay product readiness from CI green alone; non-empty UI/API behavior must be verified.

---

## 8. Next Execution Prompt

```text
# ROLE
You are LotteryNew's P0 Replay Product Go-Live Agent, reporting to CTO/CEO.

# MISSION
Finish Strategy Historical Replay as a read-only audit product surface on a
clean origin/main-based branch. The page must support all lifecycle filters and
show row-level prediction-vs-actual comparison for historical draws, using DB
tables as source-of-truth. Split H6 monitoring out of this PR.

# WORKSPACE RULE
Use a clean origin/main-based worktree. Treat the noisy source checkout only as
a source of file content and evidence. Do not commit from the noisy checkout.

# BRANCH
feature/replay-product-golive-clean-20260510

# REQUIRED STEPS
1. Fetch latest origin/main.
2. Create or reuse a clean branch from origin/main.
3. Keep the manifest scoped to Replay assets only; exclude H6 monitoring tests and `engine.h6_live_monitor`.
4. Verify `/api/replay/strategies`, `/api/replay/history`, `/api/replay/summary`, and `/api/replay/freshness` return DB-backed, conservative audit payloads.
5. Make the replay UI table match the historical prediction-list interaction shape: lifecycle filter, strategy filter, pagination, predicted numbers, actual numbers, hit numbers/count, replay status.
6. Add or update tests for non-empty Replay rows and all lifecycle filters.
7. Run replay API contract, replay browser smoke, fixture validation, dedicated DB lane, and no-in-function-import tests.
8. Commit only if validation passes.
9. Push clean branch and create PR to main.
10. Do not merge, do not update branch protection, and do not run strategy mining.

# FINAL MARKER
P0_REPLAY_PRODUCT_PR_READY
or
P0_REPLAY_PRODUCT_BLOCKED_WITH_REASON
```

---

## 9. Final Marker

```text
MASTER_ROADMAP_20260510_REPLAY_PRODUCT_GOLIVE_RECALIBRATED
```
