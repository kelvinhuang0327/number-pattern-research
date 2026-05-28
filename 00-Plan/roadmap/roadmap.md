# Lottery Replay Roadmap

**Last Updated:** 2026-05-28 Asia/Taipei (CTO update after P125 adapter gap plan from P124 matrix)
**Owner:** CTO agent
**Primary Goal:** Make every implemented LotteryNew strategy replayable with honest historical prediction-vs-actual evidence across every supported lottery type and every implemented 1-5 bet-count variant. This must be done without fake rows, untracked DB writes, premature promotion, or no-change governance PR churn. Current system state: P124 proved zero native multi-bet rows exist; P125 identified 5 Tier-B controlled_apply candidates and 12 adapter_build candidates. P108 / P117 / P118 / 4_STAR triggers remain blocked.
**Repo Policy:** Use `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` only. Do not create a new repo. Implementation and governed tasks must run from canonical repo with `git rev-parse --git-dir == .git`; Claude/Codex auto-created worktree branches are not allowed.

---

## 1. Current Phase Snapshot

| Phase / Chain | Status | Evidence | CTO Note |
|---|---|---|---|
| P14D-P94 replay expansion baseline | [Confirmed] Complete | Drift guard row-count decomposition; P91-P94 docs/json | Replay baseline is now 54462 rows including P94 Tier B controlled apply. |
| P91 all-strategy replay expansion inventory | [Confirmed] Complete | `docs/replay/p91_all_strategy_replay_expansion_inventory_20260526.md` | Inventory identified 512 strategy universe entries, 31 row-backed strategy slots, and Tier B replay expansion candidates. |
| P92-P94 Tier B adapter / dry-run / controlled apply | [Confirmed] Complete | `p92_*`, `p93_*`, `p94_*` artifacts | P93/P94 added important multi-bet evidence, but current replay storage still needs explicit 1-5 bet-count truth modeling. |
| P105-P107B Special3 acceptance / partial evaluation / guard repair | [Confirmed] Complete | P119 evidence index; commits `ceea6e9`, `bfa2653`, `782e261`, `e79b5e9` | 3_STAR accepted for Special3 evaluation only; P108 remains blocked until 100 prospective draws. |
| P112-P117 prediction-helpfulness and OOS governance | [Confirmed] Complete | P112-P117 artifacts; PRs #238-#243 | Cross-lottery helpfulness, action matrix, temporal stability, BIG_LOTTO quarantine design, and POWER_LOTTO OOS design/checkpoint are in place. |
| P118 BIG_LOTTO actual quarantine | [Blocked] Exact phrase absent | P119-P123 trigger matrix | Requires exact phrase: `YES quarantine strategy fourier30_markov30_biglotto for stable negative evidence`. |
| P119 evidence trigger matrix | [Confirmed] Complete and merged | PR #244, merge `b778658`; `P119_EVIDENCE_TRIGGER_MATRIX_READY` | Canonical trigger matrix for P108, P117, P118, and 4_STAR provenance. |
| P120 trigger evaluation | [Confirmed] Complete and merged | PR #245, merge `91476ca`; `P120_ALL_TRIGGERS_BLOCKED` | Live DB re-evaluation confirmed all triggers blocked. |
| P121 trigger recheck | [Confirmed] Complete and merged | PR #246, merge `a2d7995`; `P121_ALL_TRIGGERS_STILL_BLOCKED` | First no-change recheck. |
| P122 trigger recheck + contamination guard | [Confirmed] Complete and merged | PR #247, merge `9dcef2e`; `P122_ALL_TRIGGERS_STILL_BLOCKED` | Third consecutive no-change state and cross-project contamination guard. |
| P123 scheduled/manual trigger recheck wrapper | [Confirmed] Complete and merged | PR #248, merge `684bffcea3080f8f1f31c5b9acc3a572907ec4f3`; `P123_SCHEDULED_TRIGGER_RECHECK_SETUP_READY` | Use `scripts/p123_scheduled_trigger_recheck.py` for future no-change checks. No crontab/launchd installed. |
| P124 multi-bet replay truth model + coverage matrix | [Confirmed] Complete | `outputs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.json`; `P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY` | Read-only audit. 36 strategy×lottery pairs mapped. Zero native_multi_bet; 16 first_bet_only_fallback gaps; 5 Tier-B adapters ready for controlled_apply; 9 need adapter_build. |
| P125 adapter gap plan from P124 matrix | [Confirmed] Complete | `outputs/replay/p125_adapter_gap_plan_from_p124_20260528.json`, `docs/replay/p125_adapter_gap_plan_from_p124_20260528.md`; `P125_ADAPTER_GAP_PLAN_READY` | Read-only plan. 5 controlled_apply_ready, 12 adapter_build_needed, 2 relabel_only, 4 RSRs. Proposed P126/P127/P128 sequence. 54 tests pass. No DB writes. |

---

## 2. Current Production Replay / Data Baseline

Verified during CTO review on 2026-05-28 using read-only SQL, P119-P123 artifacts, focused tests, drift guard, and branch governance guard.

| Metric | Value |
|---|---:|
| Production replay rows | 54462 |
| 3_STAR rows / max draw | 4179 / 115000106 |
| 4_STAR rows / max draw | 2922 / 115000103 |
| POWER_LOTTO rows / max draw | 1913 / 115000041 |
| P108 Special3 prospective count | 63 / 100 |
| P108 remaining draws | 37 |
| P117 POWER_LOTTO new draws after 115000041 | 0 |
| P117 partial / full remaining | 30 / 40 |
| P118 authorization phrase | absent |
| 4_STAR provenance artifact | not found |
| Current trigger runtime classification | `P122_ALL_TRIGGERS_STILL_BLOCKED` |

Replay row-count components from drift guard:

| Group / Apply ID | Rows | Status |
|---|---:|---|
| Legacy rows | 460 | [Confirmed] Present |
| P14D / P16 / P19B / P20 / P21B baseline rows | 10500 | [Confirmed] Present |
| P31B DAILY_539 retired rows | 7500 | [Confirmed] Present |
| P37 DAILY_539 Wave 2 rows | 9000 | [Confirmed] Present |
| P43 BIG_LOTTO Wave 3 rows | 9000 | [Confirmed] Present |
| P48 POWER_LOTTO Wave 4 rows | 4500 | [Confirmed] Present |
| P59 POWER_LOTTO Wave 5 rows | 1500 | [Confirmed] Present |
| P66 POWER_LOTTO Wave 6 rows | 3000 | [Confirmed] Present |
| P79 POWER_LOTTO draw-extension sentinels | 2 | [Confirmed] Present |
| P94 Tier B controlled apply rows | 7500 | [Confirmed] Present |

Multi-bet replay truth caveat:

| Item | Status | Roadmap Impact |
|---|---|---|
| Historical replay rows | [Confirmed] One replay row per strategy/draw is the dominant convention | Enough for first-bet replay, not necessarily enough for full 1-5 bet-count product truth. |
| P93 Tier B adapters | [Confirmed] Some adapters expose `get_all_bets()` | Useful foundation for true multi-bet replay, but not complete across all implemented strategies. |
| P94 bet-count benchmark | [Confirmed] Existing benchmark flags `DB_SINGLE_BET_ONLY` / `BET_COUNT_EXCEEDS_NATIVE` blockers | Next coverage work must distinguish native multi-bet truth from first-bet fallback. |
| 4_STAR | [Blocked] Source unknown | No 4_STAR backtest until provenance is accepted. |

---

## 3. Roadmap Alignment Assessment

| Item | Classification | Assessment |
|---|---|---|
| P119-P123 trigger governance chain | [Aligned] | Correctly stopped repeated no-change PRs and created a reusable manual/scheduled wrapper. |
| Current WAIT_FOR_DATA_OR_AUTHORIZATION state | [Aligned] | System is not broken; all active evaluation/quarantine/backtest gates are legitimately blocked. |
| Continuing P124/P125 no-change recheck PRs | [Outdated] | P123 replaces this pattern. No new P-task should be created only to confirm no trigger change. |
| Worktree branch guard | [Aligned] / [Blocked if absent] | A real Claude worktree branch failure occurred. Future tasks must verify `git-dir=.git` and reject `claude/` or `codex/` branches. |
| Cross-project contamination guard | [Aligned] / [Blocked if absent] | LotteryNew prompts must explicitly reject Betting-pool, Stock, Novel, SCB, and other project governance. |
| All implemented strategies historical replay | [Missing] / [Blocked] | Highest product priority now needs a dedicated all lottery type x 1-5 bet-count coverage gap map before further applies. |
| Current multi-bet replay representation | [Blocked] | Some multi-bet strategies are stored or evaluated as first-bet-only. This blocks correctness for "all 1-5 bet combinations." |
| 4_STAR backtest | [Blocked] | Rows exist but source/provenance remains unknown. Backtest remains unauthorized. |
| OS scheduler installation | [Deferred] | P123 intentionally did not install cron/launchd. Future scheduler install requires explicit authorization. |

---

## 4. Reprioritized P0-P10

| Priority | Phase | Focus | Current Status | Acceptance Criteria |
|---|---|---|---|---|
| **P0.1** | Trigger governance standby | Stop no-change P-task PRs; use P123 wrapper for operator/manual trigger checks | [Confirmed] P123 ready | If wrapper returns `P122_ALL_TRIGGERS_STILL_BLOCKED`, no branch/PR/task is opened. If a trigger changes, plan a separate governed task. |
| **P0.2** | Canonical execution guard | Standardize worktree / context contamination pre-flight | [Required] Pattern exists in P123 | Every future worker prompt checks repo path, branch, `git-dir=.git`, rejects `claude/` and `codex/`, and locks project to LotteryNew. |
| **P0.3** | Multi-bet replay truth model | Define how 1-5 bet combinations are represented, verified, and labeled | [Missing] | Read-only design/gap artifact distinguishes native multi-bet replay, first-bet-only fallback, unsupported, and prohibited fabrication. |
| **P1.1** | All implemented strategy x lottery x bet-count coverage matrix | Build read-only inventory for all implemented strategies across lottery types and 1-5 bet variants | [Ready for CEO approval] | Matrix covers strategy_id, lottery_type, native bet count, supported bet counts 1-5, replay rows, multi-bet availability, blockers, and next governed action. |
| **P1.2** | Adapter gap plan for coverage completion | Plan adapters for implemented strategies missing truthful replay coverage | [Depends on P1.1] | No DB writes; rank gaps by product value and implementation risk. |
| **P1.3** | Prediction-helpfulness guard for expansion | Ensure coverage expansion does not imply promotion or quality | [Confirmed] P112/P113/P114 exist | All replay rows remain honestly labeled: prediction-helpful, watchlist, fallback-equivalent, sub-baseline, quarantine-candidate, source-unknown, or coverage-only. |
| **P2** | Trigger-met execution paths | P108 / P117 / P118 / 4_STAR tasks only when trigger changes | [Blocked] | P123 wrapper classification changes away from `P122_ALL_TRIGGERS_STILL_BLOCKED`, then a separate governed task is planned. |
| **P3** | 4_STAR provenance path | Decide whether 4_STAR rows can be accepted for analysis | [Blocked] source unknown | Provenance acceptance artifact plus explicit backtest authorization before any 4_STAR backtest. |
| **P4** | Runtime trigger artifact policy | Decide retention / latest pointer policy for `outputs/replay/trigger_rechecks/` | [Deferred] | Avoid repo noise while preserving operator evidence. |
| **P5** | Optional scheduler installation | Cron/launchd/nightly setup | [Deferred] not authorized | Separate explicit authorization; no hidden OS scheduler mutation. |
| **P6** | Replay UI/API disclosure | Surface replay coverage, bet-count truth, and trigger wait status | [Deferred] | UI/API labels do not imply unverified multi-bet or source-unknown truth. |
| **P7** | Worktree hygiene / DB staging policy | Reduce accidental staging and handoff noise | [Deferred but risky] | Dirty runtime/backup/DB files are inventoried or cleaned only under explicit authorization. |
| **P8** | POWER_LOTTO / Special3 future OOS monitoring | Re-enter when draw thresholds are met | [Waiting on data] | P117/P108 thresholds met; no promotion without explicit governance. |
| **P9** | External reference review | Architecture note only if useful | [Paused] | No clone/new repo; not critical path. |
| **P10** | Post-launch operations cadence | Long-term monitoring and regression cadence | [Deferred] | Regular reports flag stale data, source unknowns, guard failures, and UI/API regressions. |

Upgrade / downgrade decisions:

| Item | Decision | Reason |
|---|---|---|
| P123 wrapper usage | Upgrade to P0 operating rule | Prevents wasteful no-change PRs and preserves wait-state discipline. |
| Worktree branch guard | Upgrade to P0 | A Claude worktree branch failure already happened; this is a real execution-safety blocker. |
| Multi-bet replay truth model | Upgrade to P0.3 | The top product goal requires correct 1-5 bet replay, not first-bet-only ambiguity. |
| All-strategy x 1-5 bet coverage matrix | Upgrade to P1.1 | This is the next highest-value work while draw/authorization triggers remain blocked. |
| Repeated P120/P121/P122 style recheck PRs | Retire | Superseded by P123 wrapper unless trigger classification changes. |
| 4_STAR backtest | Keep blocked | Source/provenance remains unknown. |
| OS scheduler install | Defer | P123 explicitly did not install cron/launchd. |

---

## 5. Critical Blockers

| Blocker | Impact | Why It Blocks | Risk If Ignored | Priority | Acceptance |
|---|---|---|---|---|---|
| Trigger wait-state | P108/P117/P118/4_STAR execution | All four triggers are currently blocked | Premature evaluation, quarantine, or backtest would violate governance | P0.1 | Use P123 wrapper; no new task if classification remains `P122_ALL_TRIGGERS_STILL_BLOCKED`. |
| Worktree branch execution risk | Repo integrity | Claude/Codex may create `.git/worktrees/` branches | Work could land in wrong repo path or branch | P0.2 | Future prompts require `git-dir=.git` and reject `claude/` / `codex/`. |
| Multi-bet replay truth ambiguity | Product correctness | Current rows often represent first bet only | "All 1-5 bet combinations" could be falsely presented as replay-backed | P0.3 | Formal truth model and coverage-gap matrix before new replay apply. |
| All implemented strategy coverage gap | Product maturity | P91 showed many strategy universe entries are not row-backed or not truthful multi-bet | Operator cannot inspect complete historical replay across all implemented strategies | P1.1 | Read-only matrix of all implemented strategies by lottery and bet count 1-5. |
| 4_STAR source unknown | Data quality | Provenance artifact absent | Unauthorized backtest on unverified data | P3 | Provenance decision before backtest. |
| Dirty worktree with DB/history/runtime files | Release safety | Existing modified/untracked files remain | Broad staging could commit DB/runtime state | P7 / universal guard | Forbidden staging scan clean in every governed task. |

---

## 6. Recommended System Optimization Directions

### Direction A: Trigger Recheck As An Operator Tool, Not A PR Factory

- **Roadmap phase:** P0.1
- **Why important:** P120-P122 proved repeated no-change PRs add cost without changing system state.
- **System maturity gain:** Converts periodic governance checks into a cheap, deterministic operator action.
- **Expected benefit:** Lower CI/agent cost, fewer noisy handoffs, clearer "wait for data or authorization" state.
- **Risk:** Operators may think P123 installed an OS scheduler; it did not.
- **Acceptance:** P123 wrapper run from canonical repo; no branch/PR when classification remains blocked.
- **Priority:** P0

### Direction B: Canonical Execution And Context Guard Standardization

- **Roadmap phase:** P0.2
- **Why important:** A Claude auto-worktree attempt already caused a correct STOP.
- **System maturity gain:** Prevents work from being performed in wrong repo paths or contaminated prompts.
- **Expected benefit:** Safer multi-agent workflow and less recovery overhead.
- **Risk:** Guard duplication across prompts can drift unless later centralized.
- **Acceptance:** Every future governed prompt checks `show-toplevel`, branch, `git-dir`, and project lock before implementation.
- **Priority:** P0

### Direction C: Multi-Bet Replay Truth Model For 1-5 Bet Counts

- **Roadmap phase:** P0.3
- **Why important:** The highest product goal requires all implemented strategies and 1-5 bet variants to be historically replayable.
- **System maturity gain:** Makes replay evidence truthful at the bet-count level, not merely at strategy/draw level.
- **Expected benefit:** Clear distinction between native 1/2/3/4/5-bet strategies, first-bet-only fallback, unsupported variants, and prohibited fabrication.
- **Risk:** Existing UI or reports may currently overstate multi-bet coverage.
- **Acceptance:** Read-only truth model and gap report; no DB write; no fabricated rows.
- **Priority:** P0

### Direction D: All-Implemented-Strategy Coverage Matrix

- **Roadmap phase:** P1.1
- **Why important:** P91 established the universe; the next useful step is a precise coverage matrix for implemented strategies by lottery and bet count.
- **System maturity gain:** Turns "all strategies replayed" into a measurable completion program.
- **Expected benefit:** Lets planner/worker pick the next adapter/apply work by value and correctness risk.
- **Risk:** Matrix may expose many unsupported or first-bet-only gaps; scope needs tight read-only boundaries first.
- **Acceptance:** Matrix includes lottery type, native bet count, supported bet counts 1-5, replay rows, adapter status, blocker, quality label, and next action.
- **Priority:** P1

### Direction E: Provenance-First Expansion For 4_STAR And Future Draws

- **Roadmap phase:** P2/P3
- **Why important:** Source-unknown data can exist in DB without analytical authorization.
- **System maturity gain:** Keeps data quality and replay expansion from drifting apart.
- **Expected benefit:** 4_STAR can become useful later without weakening governance.
- **Risk:** Pressure to backtest because rows exist.
- **Acceptance:** Provenance artifact and explicit authorization before 4_STAR backtest.
- **Priority:** P2/P3

---

## 7. Today's Focus

**CTO recommendation:** P124 proved zero native multi-bet rows. P125 produced the adapter gap plan. Next step is P126 (controlled apply for 5 Tier-B candidates) once explicit apply authorization is given.

Confirmed current state:

- [Confirmed] P124 branch `p124-multi-bet-truth-coverage-matrix` merged to `main` (commit `77d7d7d`).
- [Confirmed] P125 committed to `main` as "P125: add adapter gap plan from P124 matrix".
- [Confirmed] P125 classification: `P125_ADAPTER_GAP_PLAN_READY`.
- [Confirmed] DB invariants: replay rows `54462`, 3_STAR `4179/max=115000106`, 4_STAR `2922/max=115000103`, POWER_LOTTO `1913/max=115000041`.
- [Confirmed] P108 still needs 37 more Special3 draws.
- [Confirmed] P117 still needs 30/40 more POWER_LOTTO draws.
- [Confirmed] P118 exact phrase is absent.
- [Confirmed] 4_STAR provenance is absent; backtest unauthorized.
- [Confirmed] P125 installed no crontab and created no launchd plist.
- [Confirmed] Verification during this CTO update: P125 tests `54 passed`; P124 + P119-P123 regression `345 passed`; drift guard PASS.

Recommended near-term order:

| Rank | Work | Why |
|---|---|---|
| 1 | P126 controlled_apply dry-run and apply for 5 Tier-B candidates | P125 identified the 5 candidates; they have working adapters; controlled_apply just needs explicit authorization |
| 2 | P127 adapter build for 12 missing get_all_bets() adapters | Unlocks replay expansion for 12 more strategy×lottery pairs after adapters are tested |
| 3 | P128 native multi-bet storage design | RSR-1 blocks any multi-bet expansion until format is decided; design must precede any apply |
| 4 | Operator/manual P123 trigger check only when data or authorization may have changed | Maintains healthy standby without PR churn |

CTO prompt boundary:

- [Confirmed] This CTO update does not create or modify `00-Plan/roadmap/active_task.md`.
- [Confirmed] This CTO update modifies only `roadmap.md` and `CTO-Analysis.md`.

Final roadmap marker:

```text
CTO_ROADMAP_UPDATED_AFTER_P125_ADAPTER_GAP_PLAN_20260528
```

---

## Phase Snapshot After P126

| Task | Status | Classification | DB Rows |
|---|---|---|---|
| P119 | DONE | P119_EVIDENCE_TRIGGER_MATRIX_LOCKED | 54462 |
| P120 | DONE | P120_TRIGGER_EVALUATION_DONE | 54462 |
| P121 | DONE | P121_TRIGGER_RECHECK_DONE | 54462 |
| P122 | DONE | P122_CONTAMINATION_GUARD_PASS | 54462 |
| P123 | DONE | P123_SCHEDULED_TRIGGER_RECHECK_SETUP_DONE | 54462 |
| P124 | DONE | P124_MERGED_TO_MAIN_WITH_ACKNOWLEDGED_ROADMAP_FILE_VIOLATION | 54462 |
| P125 | DONE | P125_ADAPTER_GAP_PLAN_READY | 54462 |
| P126 | DONE | P126_DRY_RUN_PLAN_READY | 54462 (no writes) |

Updated near-term order (post-P126):

| Rank | Work | Why |
|---|---|---|
| 1 | P128 native multi-bet storage design | RSR-1 blocks any multi-bet apply until format decided |
| 2 | P126 Apply — authorize and execute for 5 Tier-B candidates | Requires P128 decision or one-row-per-bet explicit authorization, then per-strategy phrase f| 2 | P126 Apply — authorize and execute for 5 Tier-B candidates | Requires P128 decisio in para| 2 | P126 Apply — authoregy| 2 | P126 Apply — authorize and exel P123 | 2 | P126 Applyly| 2 | P126 Apply — authorize and execute for 5 Tier-ns healt| 2 | P126 Apply — authorize and execute for 5 Tiers | 2 | P126 Apply — authorize and execute for 5 Tma| 2 | P126 Apply — authorize and execute for 5 modifie| 2 | P126 Apply — authorize and execute for 5 Tier-B candidar:

```text
CTO_ROADMAP_UPDATED_AFTER_P126_DRY_RUN_PLAN_20260528
```

---

## P128: Native Multi-Bet Replay Storage Design

**Status:** COMPLETE
**Classification:** P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY

### RSR Tracking

| RSR | Description | Status |
|---|---|---|
| RSR-1 | No storage format decided | ✅ RESOLVED — Option A (one-row-per-bet + bet_index) |
| RSR-2 | No bet_index column | ✅ RESOLVED — migration plan defined |
| RSR-3 | Drift guard count update | ⏳ Remaining — after P126 apply |
| RSR-4 | API/UI consumer update | ⏳ Remaining — parallel track |

### Updated Near-Term Order (post-P128)

| Rank | Work | Why |
|---|---|---|
| 1 | Migration authorization | `YES authorize migration_plan_p128 because <reason>` required from Kelvin |
| 2 | Execute P128 migration plan | 18-step SQLite table recreation; adds bet_index column |
| 3 | P126 Apply (5 Tier-B candidates) | Requires migration + 5 per-strategy auth phrases |
| 4 | RSR-3: update drift guard | After apply; expected count = 72462 |
| 5 | RSR-4: API/UI consumer update | Add WHERE bet_index = 1 filters |

```text
CTO_ROADMAP_UPDATED_AFTER_P128_STORAGE_DESIGN_20260528
```
