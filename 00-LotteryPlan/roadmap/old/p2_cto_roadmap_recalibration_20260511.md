# P2 CTO Roadmap Recalibration — 2026-05-11

> Supersession note: After this artifact was produced, the product objective was restated as Strategy Historical Replay go-live for all developed strategy lifecycle states. The implementation priority is therefore superseded by `outputs/replay/p0_strategy_history_replay_product_plan_20260511.md`. This P2 no-write skeleton package remains valid as a governance lane, but it is no longer today's primary product P0.

## 1. CTO Decision

The system should remain in the P2 no-write governance lane. The most valuable next optimization is not real backfill execution, not DB mutation, and not PR merging. It is to close the no-write skeleton planning package, then proceed only to a dry-run-only skeleton implementation if explicitly requested.

Current state has advanced beyond the handoff wording: `outputs/replay/p2_no_write_skeleton_implementation_plan_20260510.md` already exists in dirty scope. Therefore today's P0 is not "create the plan from zero"; it is to verify, correct, and package the checklist, conclusion, and plan as one docs-only governance unit.

## 2. Evidence Reviewed

- `outputs/replay/p2_24h_no_write_skeleton_implementation_review_checklist_20260510.md`
- `outputs/replay/p2_no_write_skeleton_implementation_review_conclusion_20260510.md`
- `outputs/replay/p2_no_write_skeleton_implementation_plan_20260510.md`
- `docs/REPLAY_OPERATION_SOP.md`
- `wiki/system/replay_data_hygiene.md`
- Current worktree status in `/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean`
- GitHub PR status checked on 2026-05-11:
  - PR #33: open, mergeable, default/browser checks success, dedicated DB skipped
  - PR #34: open, mergeable, default/browser checks success, dedicated DB skipped
  - PR #25: open, mergeable, still superseded by PR #26 and not a merge candidate
  - PR #26: open, mergeable, default/browser checks success, dedicated DB skipped

## 3. Roadmap Alignment Assessment

Aligned:

- The project is correctly prioritizing replay lifecycle governance and no-write proof over new strategy research.
- `runtime_write_allowed=false` remains the right invariant for this phase.
- PR merge remains blocked without explicit user `YES`.
- Evidence reports and `outputs/replay/` artifacts remain audit artifacts, not runtime sources.
- The skeleton plan preserves dry-run-only posture and rejects hidden write paths.

Misaligned or stale:

- The handoff says the planning artifact has not been produced, but the current worktree already contains it.
- The plan previously said the next step was "planning only"; after review, the planning gate is now complete.
- Open PR queue management is becoming a product risk because many docs-only PRs are green but unmerged.
- Treating PR #33 / #34 as simply "green" is incomplete: the required/default and browser lanes passed, while the dedicated DB lane was skipped.

## 4. Reordered P0-P10

| Priority | Focus | Decision | Acceptance Criteria |
|---|---|---|---|
| P0 | Package no-write planning docs | Keep dirty scope to checklist + conclusion + plan + this CTO recalibration | `git diff --name-only` only lists approved docs; `git diff --check` passes; no code, DB, registry, or state changes |
| P1 | No-write skeleton implementation only | Allowed only after explicit request; create dry-run skeleton and tests, not apply logic | No `--execute`, `--apply`, `--write-db`; approval artifact required; production DB rejected; DB hash unchanged |
| P2 | PR queue governance | Keep #33/#34 open unless explicit YES; keep #25 superseded by #26 | PR table updated; no accidental merge; superseded PR not closed without instruction |
| P3 | Runtime-write invariant | Preserve `runtime_write_allowed=false` across every manifest row | Any true value blocks the task |
| P4 | Approval artifact hardening | Define exact approval schema before any skeleton run | `allowed_mode=dry_run_only`; `explicit_no_db_write=true`; target manifest SHA present |
| P5 | Output proof contract | Future skeleton output must prove no-write behavior | JSON/report include `apply_attempted=false`, `db_write_attempted=false`, before/after DB hashes |
| P6 | Manifest drift control | Prevent timestamp-only generator drift from entering PRs | generated_at-only drift restored; row-content drift requires new review |
| P7 | Production DB path rejection | Ensure future skeleton cannot target production DB | Production path blocked even in dry-run |
| P8 | Open PR consolidation | Reduce docs PR queue once explicit YES is given | Merge order documented; superseded PRs handled deliberately |
| P9 | Replay governance source-of-truth cleanup | Keep runtime logic separate from `outputs/replay/` artifacts | No evidence report becomes API/UI/runtime source |
| P10 | Real apply governance | Defer real apply until a separate approval gate exists | No backfill/apply/DB write/registry write/active state write in current phase |

## 5. Critical Blockers

- **Approval blocker:** PR merges still require explicit `YES`; no agent should merge #33 or #34 autonomously.
- **Queue blocker:** PR #25 is still open and mergeable but superseded by PR #26, so it remains a mistaken-merge risk.
- **Scope blocker:** The dirty scope now includes a planning file that was not listed in the handoff's expected dirty scope. This is acceptable only if treated as a planning artifact and validated.
- **Safety blocker:** Any future attempt to add real apply, write DB, mutate registry, or set `runtime_write_allowed=true` must be blocked.
- **Evidence blocker:** Dedicated DB lane status is skipped in the checked PRs, so "green" should be read as required/default plus browser checks passing, not as full matrix execution.

## 6. Today's Most Focused Optimization Direction

P0 is to close the current docs-only package cleanly:

1. Keep the dirty scope limited to:
   - `outputs/replay/p2_24h_no_write_skeleton_implementation_review_checklist_20260510.md`
   - `outputs/replay/p2_no_write_skeleton_implementation_review_conclusion_20260510.md`
   - `outputs/replay/p2_no_write_skeleton_implementation_plan_20260510.md`
   - `outputs/replay/p2_cto_roadmap_recalibration_20260511.md`
2. Run `git diff --check`.
3. Do not create skeleton code in this same docs package.
4. If the user explicitly asks for implementation next, proceed only with no-write skeleton implementation.

## 7. Stop Rules

- Do not execute backfill.
- Do not execute apply.
- Do not write any DB.
- Do not write production DB.
- Do not modify registry.
- Do not modify active strategy state.
- Do not add a real apply mode.
- Do not set `runtime_write_allowed=true`.
- Do not treat `outputs/replay/` evidence as runtime source.
- Do not merge any PR without explicit `YES`.
- Do not close PR #25 without explicit instruction.

## 8. Next Executable Prompt

```text
# ROLE
You are LotteryNew's P2 No-Write Skeleton Implementation Agent.

# CURRENT STATE
P2_NO_WRITE_SKELETON_IMPLEMENTATION_PLAN_READY

# MISSION
Implement only the dry-run no-write skeleton and its tests.

# STRICT RULES
- Do not execute backfill.
- Do not execute apply.
- Do not write DB.
- Do not write production DB.
- Do not modify registry.
- Do not modify active strategy state.
- Do not add real apply mode.
- Do not accept --execute / --apply / --write-db.
- Do not merge PRs.
- Do not close PR #25.

# ALLOWED FILES
- scripts/p2_lifecycle_backfill_apply_skeleton.py
- tests/test_p2_lifecycle_backfill_apply_skeleton.py
- outputs/replay/p2_lifecycle_backfill_apply_skeleton_dry_run_20260510.json
- outputs/replay/p2_lifecycle_backfill_apply_skeleton_report_20260510.md

# ACCEPTANCE
- Missing approval artifact fails safely.
- Malformed approval artifact fails safely.
- Production DB path rejected.
- runtime_write_allowed=true rejected.
- Blocked and parse-error rows excluded.
- DB hash unchanged.
- No SQL write verbs accepted.
- Output report states no-write.

# FINAL MARKER
P2_NO_WRITE_SKELETON_IMPLEMENTATION_READY
or
P2_NO_WRITE_SKELETON_IMPLEMENTATION_BLOCKED_<reason>
```

## 9. Final Marker

P2_CTO_ROADMAP_RECALIBRATION_20260511_READY
