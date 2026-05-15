# LotteryNew — Strategy Historical Replay Roadmap Recalibration

**Version:** 2026-05-14 CTO recalibration v5.0 after CEO review  
**Owner:** CTO agent  
**Effective date:** 2026-05-14 Asia/Taipei  
**Primary product goal:** Strategy Historical Replay go-live, where every system-developed strategy across `ONLINE`, `OFFLINE`, `REJECTED`, `OBSERVATION`, and `RETIRED` can be inspected through a historical prediction-list-compatible table of prediction vs. actual draw comparison.  
**Source of truth policy:** `LotteryNew` is the consolidation target. Do not create additional repos. Existing sibling folders may be used only as temporary comparison/worktree sources until code is merged back and verified.

---

## 1. CEO Alignment Decision

CEO review is accepted.

The previous CTO roadmap correctly avoided fake truth, but it set the MVP bar too low for the user's stated goal. Tombstones are acceptable only for strategies that truly cannot be reconstructed after evidence-backed execution checks. The product target is not just "all 16 strategies visible"; it is "all feasible strategies have historical rows, and every row carries provenance."

New CTO position:

1. **P78 remains P0** because normal browser validation is blocked without configurable API base.
2. **Retrospective regeneration becomes the strategic product path**, not a deferred research lane.
3. **P1 must be executable evidence, not paperwork**: each canonical strategy must be mapped to code path, entry point, importability, dry-call feasibility, and failure reason.
4. **DB writes are allowed later in the roadmap** once provenance hash, truth-level labeling, snapshot, transaction log, and rollback are ready.
5. Fixture rows remain non-production and must never be counted as replay truth.

---

## 2. Current Verified State

Verified on 2026-05-14 from local workspace inspection, `LotteryNew-clean`, GitHub PR status, and prior DB/API reports.

| Area | Current state | CTO assessment |
|---|---|---|
| Workspace folders under `/Users/kelvin/Kelvin-WorkSpace` | `Lottery`, `LotteryNew`, `LotteryNew-clean` | `LotteryNew` is the consolidation target; `Lottery` is not a git repo; `LotteryNew-clean` is the same GitHub remote worktree |
| `LotteryNew` current branch | `feature/phase4-required-check-20260509` at `7306264` | Dirty/divergent; not safe as merge authority |
| `LotteryNew-clean` baseline | Same remote, `origin/main=d438fb6` | Existing worktree used for P78 PR; no new repo created |
| `origin/main` | `d438fb6 docs(replay/p77): audit same-origin API architecture (#91)` | P75/P76/P77 merged |
| P78 PR | PR #92 `frontend(replay/p78): add configurable API base` | Open; mergeable; CI green after strict-rule cleanup |
| P78 modified files | `index.html`, `outputs/replay/p78_configurable_api_base_report_20260513.md` | Correct scope |
| P78 local hardcode cleanup | Removed `localhost:8002` literal from `index.html` source comments | CEO static grep expectation satisfied |
| Runtime replay DB rows | 460 total | 420 `PREDICTED`, 40 `REPLAY_ERROR` |
| Latest valid replay runs | #5 BIG_LOTTO, #6 POWER_LOTTO, #7 DAILY_539 | 50-draw latest valid windows |
| Canonical strategy registry | 16 strategies | `ONLINE=6`, `REJECTED=4`, `OBSERVATION=1`, `RETIRED=5`, `OFFLINE=0` |
| Preliminary P1 inventory from P78 report | `EXECUTABLE_NOW=6`, `CODE_MISSING=10` | Useful but not final; P1 must do deeper executable proof + orphan artifact scan |

Replay truth distribution today:

| Truth Level | Count | Meaning |
|---|---:|---|
| `PRODUCTION_REPLAY` | 6 | Existing DB rows from executable ONLINE adapters |
| `DISPLAY_ONLY` | 5 | Evidence/metadata exists but no production replay rows yet |
| `MISSING_HISTORY` | 5 | No reconstructable history proven yet |
| `REGENERATED_RETROSPECTIVE` | 0 | Required for full target after P1-P6 |
| `FIXTURE_ONLY` | test mode only | Synthetic validation rows only |

---

## 3. Roadmap Alignment Assessment

Aligned:

| Direction | Status |
|---|---|
| Strategy Historical Replay is the core product priority | Keep |
| P78 configurable API base is launch-critical plumbing | Keep |
| Fixture rows must not be treated as real history | Keep |
| Strategy mining/promotion stays out of this phase | Keep |
| `REPLAY_ERROR` rows stay visible for audit | Keep |

Needs correction:

| Previous assumption | Problem | CEO-aligned correction |
|---|---|---|
| 10 non-ONLINE strategies can remain tombstone/display-only until much later | User explicitly wants all developed strategies to show per-draw comparison when feasible | Move executable proof, dry-run regeneration, controlled apply, and UI parity into P1-P7 |
| P1 as a paper manifest | Could become paperwork without proving import/call feasibility | P1 becomes code-backed executable inventory |
| DB writes forbidden until late P7 | Full target requires storing generated/imported retrospective rows | Allow controlled apply at P6 after P3-P5 gates |
| DAILY_539 legacy errors as early P2 | Important, but not the main user-visible gap | Move to P4 |
| UI can wait for regenerated rows | Rows need truth-level UI before dry-run/apply path matures | P2 prepares `REGENERATED_RETROSPECTIVE` UI/API fields |

---

## 4. Reordered P0-P10

| Priority | Focus | Decision | Acceptance Criteria | Gate |
|---|---|---|---|---|
| **P0** | P78 configurable API base | Complete/merge PR #92, then consolidate patch back into `LotteryNew` | `window.API_BASE` supported; production default stays `/api/replay`; local dev can target backend origin; browser smoke requires no fetch monkey patch; diff limited to `index.html` + P78 report; DB/registry unchanged | Review/merge PR #92 |
| **P1** | Full-strategy executable evidence inventory | Replace paper manifest with import/instantiate/dry-call proof | All 16 canonical strategies plus orphan artifacts classified as `EXECUTABLE_NOW`, `EXECUTABLE_WITH_FIX`, `CODE_MISSING`, or `TOMBSTONE`; each row includes code path, import path, entry point, dry-call feasibility, failure reason, and provenance artifact | Read-only; no DB write |
| **P2** | Truth taxonomy v2 + UI badge readiness | Prepare UI/API for regenerated rows before dry-run/apply | `REGENERATED_RETROSPECTIVE` badge and contract are verified in static + browser checks; history rows can carry `truth_level` / provenance fields without breaking existing table | Frontend/API contract PR |
| **P3** | Retrospective regeneration dry-run | Generate candidate rows in memory/artifact only for P1 `EXECUTABLE_NOW` and approved `EXECUTABLE_WITH_FIX` strategies | Candidate table includes `(strategy_id, target_draw, predicted_numbers, actual_numbers, hit_numbers, hit_count, truth_level, provenance_hash)`; no DB write | `YES dry-run retrospective` |
| **P4** | DAILY_539 `FAILED_LEGACY` semantics | Label 40 legacy errors without blocking regeneration path | Error rows grouped by run/draw/exception; UI/API distinguish `legacy audit` from latest valid run; no deletion | Read-only investigation |
| **P5** | Storage lane + schema migration plan | Decide how retrospective rows enter durable storage | Decision recommends production DB with `truth_level` and provenance fields, or rejects with reason; includes snapshot, rollback, migration, fixture isolation, and duplicate prevention | CEO decision memo |
| **P6** | Controlled apply of retrospective rows | Apply P3-approved rows after P5 | DB snapshot; transaction log; row counts match manifest; provenance hashes stored; rollback verified; no lifecycle promotion | `YES production apply retrospective rows` |
| **P7** | UI parity: all-strategy table experience | Make every strategy open into the same historical prediction-list-compatible surface | For all 16 strategies: production/regenerated rows show table; tombstone only remains where P1 proves no code/artifact; URL filters persist; browser QA screenshots attached | Frontend PR + browser QA |
| **P8** | H6 OBSERVATION evidence commit | Make OBSERVATION evidence repo-backed | `h6_gate_mk20_ew85` evidence artifact committed or linked; registry unchanged; UI can cite evidence availability | Docs/evidence PR |
| **P9** | Workspace/PR/docs consolidation | Clean management surface after P0-P8 | PR #86/#88 triaged; `outputs/relay` vs `outputs/replay` resolved; `LotteryNew-clean` deltas merged into `LotteryNew`; delete/archive sibling folders only after user approval and verification | Docs/ops cleanup |
| **P10** | OFFLINE policy + strategy mining/promotion | Keep deferred | OFFLINE rules defined only after replay truth is signed off; no strategy mining or lifecycle promotion in this launch lane | Later phase |

---

## 5. Critical Blockers

| Blocker | Severity | Why it matters | Resolution |
|---|---|---|---|
| 10/16 strategies do not yet have real per-draw rows | CRITICAL | This is the direct gap against the user's goal | P1 executable proof, P3 dry-run, P6 controlled apply |
| `LotteryNew` is dirty/divergent | HIGH | Cannot safely merge or delete sibling folders until the target is reconciled | Use PR #92/main as authority, then merge back intentionally |
| Multiple Lottery folders | HIGH | Operational confusion and "extra repo" management risk | Treat `LotteryNew` as target; `LotteryNew-clean` as temporary same-remote worktree; do not delete without final diff/export verification |
| P78 PR still unmerged | MEDIUM | P0 code is ready, but main and `LotteryNew` do not contain it until PR #92 is merged and reconciled | Review/merge PR #92, then verify `LotteryNew` receives the merged patch |
| `REGENERATED_RETROSPECTIVE` not proven round-trip in UI | MEDIUM | Generated rows would be ambiguous without a badge/contract | P2 before P3/P6 apply |
| Retired strategy code may truly be missing | MEDIUM | Some tombstones may remain valid, but only after proof | P1 must verify code/artifacts, including sibling folders and orphan strategies |
| Fixture mode can be misread as truth | HIGH | Synthetic rows could create false audit history | Keep fixture flags/banners; exclude from production mode and counts |
| DAILY_539 legacy error rows | MEDIUM | Must not confuse operators | P4 labeling |

---

## 6. Most Valuable Next Optimization Direction

The next optimization is **Replay Truth Coverage Completion**, specifically:

```text
P78 merge -> P1 executable proof -> P2 regenerated badge/contract -> P3 dry-run -> P5 storage decision -> P6 controlled apply -> P7 all-strategy UI parity
```

This is the shortest credible path from:

```text
6/16 real rows + 10/16 display/tombstone
```

to:

```text
16/16 visible, all feasible strategies backed by table rows, every row carrying truth_level and provenance
```

Do not spend the next phase on strategy mining, new strategies, broad UI redesign, or docs-only churn.

---

## 7. Workspace Consolidation Policy

| Folder | Current finding | Action |
|---|---|---|
| `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | Main target, but currently dirty/divergent feature branch | Keep as final home; merge verified PR/main changes back here |
| `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean` | Same GitHub remote worktree, contains P78 branch/PR work | Use only as temporary clean worktree until PR #92 is merged and copied/merged back |
| `/Users/kelvin/Kelvin-WorkSpace/Lottery` | Not a git repo | Treat as legacy data folder; inventory before deletion |

Deletion rule:

- Do not delete `Lottery` or `LotteryNew-clean` until `LotteryNew` contains the merged code, reports, DB lane decision, and any unique artifacts are inventoried.
- No new repo or new clone should be created.

---

## 8. Stop Rules

- P1 inventory is invalid if it only reads registry/docs; it must attempt import/instantiate/dry-call checks without executing live prediction writes.
- P2 regenerated truth-level support must land before P3 dry-run rows become a storage candidate.
- No DB write before P5 decision and P6 explicit apply gate.
- No production DB write without snapshot, transaction log, provenance hash, and rollback proof.
- Do not call fixture rows production replay.
- Do not hide `REPLAY_ERROR` rows.
- Do not promote/demote/retire/reactivate strategies during replay truth launch.
- Do not add another repo or unmanaged clone.
- Do not delete sibling folders without final user approval.

---

## 9. Immediate Execution Prompts

### A. Finish P0

```text
Review PR #92. If CI is green, merge P78 configurable API base, then verify `LotteryNew` receives the merged patch.
```

Expected result:

- P78 is in main.
- Normal browser local-dev path no longer needs fetch monkey patch.
- `LotteryNew` can be reconciled against the merged main.

### B. Start P1

```text
Run full-strategy executable evidence inventory for all 16 canonical strategies plus orphan artifacts across LotteryNew and LotteryNew-clean. Do not write DB.
```

Expected result:

- Final per-strategy table: `strategy_id`, lifecycle, code path, import path, entry point, dry-call feasibility, failure reason, provenance artifact, bucket.
- This supersedes the preliminary P78 inventory.

### C. Prepare P2

```text
Add/verify `REGENERATED_RETROSPECTIVE` UI/API round-trip support before regeneration dry-run.
```

Expected result:

- UI can display regenerated rows distinctly from production rows and fixtures.

---

## 10. Final Marker

`LOTTERY_ROADMAP_20260514_CEO_ALIGNED_REPLAY_TRUTH_COVERAGE_PLAN`
