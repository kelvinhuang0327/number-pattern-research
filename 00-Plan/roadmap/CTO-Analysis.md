# CTO Analysis - After P125 Adapter Gap Plan From P124 Matrix

## 1. CTO Review Date

2026-05-28 Asia/Taipei.

Final CTO classification target: `CTO_ROADMAP_UPDATED_WITH_RISKS`.

## 2. Input Sources

- [Confirmed] User handoff report in the current conversation, limited to LotteryNew content.
- [Confirmed] `00-Plan/roadmap/roadmap.md` before this update: last updated after P124.
- [Confirmed] `00-Plan/roadmap/CTO-Analysis.md` before this update: last updated after P124.
- [Confirmed] Git pre-flight from canonical repo:
  - repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
  - branch: `main`
  - git-dir: `.git`
  - HEAD: `77d7d7d Merge P124 multi-bet replay truth and coverage matrix`
- [Confirmed] P124 merged via no-ff from `p124-multi-bet-truth-coverage-matrix` branch.
- [Confirmed] P119-P125 artifacts:
  - `outputs/replay/p119_evidence_trigger_matrix_20260527.json`
  - `outputs/replay/p120_trigger_evaluation_20260527.json`
  - `outputs/replay/p121_trigger_recheck_20260527.json`
  - `outputs/replay/p122_trigger_recheck_contamination_guard_20260527.json`
  - `outputs/replay/p123_scheduled_trigger_recheck_setup_20260527.json`
  - `outputs/replay/trigger_rechecks/p123_trigger_recheck_smoke_20260527.json`
  - `outputs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.json`
  - `outputs/replay/p125_adapter_gap_plan_from_p124_20260528.json`
  - `docs/replay/p125_adapter_gap_plan_from_p124_20260528.md`
- [Confirmed] Strategy replay / helpfulness references:
  - P91 all-strategy replay expansion inventory
  - P92 Tier B adapter audit / dry-run plan
  - P93 Tier B replay adapter bootstrap dry-run
  - P94 Tier B controlled apply
  - P112 cross-lottery prediction-helpfulness audit
  - P113 action decision matrix
  - P114 temporal stability audit
  - P115 BIG_LOTTO quarantine governance design
  - P116 POWER_LOTTO OOS monitoring design
  - P117 POWER_LOTTO OOS monitoring checkpoint
- [Confirmed] Read-only SQL during this CTO review:
  - `strategy_prediction_replays = 54462`
  - `3_STAR count/max = 4179 / 115000106`
  - `4_STAR count/max = 2922 / 115000103`
  - `POWER_LOTTO count/max = 1913 / 115000041`
- [Confirmed] Verification during this CTO review:
  - P125 tests: `54 passed`
  - P124 + P119-P123 regression: `345 passed`
  - Drift guard: `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`
  - Branch governance: `main`, HEAD `77d7d7d`, 54462 rows
- [Confirmed] Existing dirty worktree remains outside this CTO scope, including DB/history/pid/runtime/untracked files. CTO touched only `roadmap.md` and `CTO-Analysis.md`.

## 3. Roadmap Alignment Assessment

| Finding | Classification | CTO Assessment |
|---|---|---|
| P119 evidence trigger matrix | [Aligned] | Consolidated P105-P117 evidence and made trigger conditions deterministic. |
| P120-P122 repeated trigger rechecks | [Aligned] initially; [Outdated] as an ongoing pattern | They were useful to confirm no change, but three consecutive blocked states mean more no-change PRs are wasteful. |
| P123 scheduled/manual trigger wrapper | [Aligned] | Correctly replaces no-change PR churn with a reusable operator/manual wrapper. |
| P123 first worktree attempt STOP | [Aligned] / [Blocked] | The STOP was correct and exposed a real process risk: Claude/Codex worktree branches must be rejected. |
| P124 multi-bet truth and coverage matrix | [Aligned] | Proved zero native multi-bet rows exist. All 36 strategy×lottery pairs are first_bet_only_fallback or rejected. 5 Tier-B controlled_apply candidates and 12 adapter_build candidates identified. |
| P125 adapter gap plan | [Aligned] | Read-only plan artifact. Ranked 5 controlled_apply-ready, 12 adapter_build-needed. Proposed P126/P127/P128 next sequence. No DB writes. |
| Current system state | [Aligned] | Healthy standby / wait-for-authorization, not failure. |
| 4_STAR backtest | [Blocked] | Source unknown remains active; rows alone do not authorize backtest. |
| Multi-bet replay coverage | [Partially Mapped] | P124 proved gap; P125 defines remediation path. P126/P127/P128 required for actual coverage expansion. |
| OS scheduler install | [Deferred] | P123 did not install cron/launchd. Future scheduling requires explicit authorization. |

## 4. Completed Work Assessment

### P119 - Evidence Trigger Matrix

- [Confirmed] Classification: `P119_EVIDENCE_TRIGGER_MATRIX_READY`.
- [Confirmed] Trigger matrix covers:
  - P108 Special3 100-draw re-evaluation
  - P117 POWER_LOTTO OOS retrigger
  - P118 BIG_LOTTO actual quarantine
  - 4_STAR provenance and backtest
- [Confirmed] All triggers were blocked at P119.
- [Confirmed] Current DB snapshot: replay rows 54462, 3_STAR 4179/max 115000106, 4_STAR 2922/max 115000103, POWER_LOTTO 1913/max 115000041.

### P120-P122 - Consecutive Trigger Rechecks

- [Confirmed] P120 classification: `P120_ALL_TRIGGERS_BLOCKED`.
- [Confirmed] P121 classification: `P121_ALL_TRIGGERS_STILL_BLOCKED`.
- [Confirmed] P122 classification: `P122_ALL_TRIGGERS_STILL_BLOCKED`.
- [Confirmed] P122 added cross-project contamination guard.
- [Confirmed] No P108, P117 OOS, P118 quarantine, or 4_STAR backtest was run.
- [Confirmed] No strategy promotion, lifecycle mutation, registry mutation, DB write, replay row delete, or replay row insert occurred.

### P123 - Scheduled / Manual Trigger Recheck Setup

- [Confirmed] PR #248 merged; merge commit `684bffcea3080f8f1f31c5b9acc3a572907ec4f3`.
- [Confirmed] Classification: `P123_SCHEDULED_TRIGGER_RECHECK_SETUP_READY`.
- [Confirmed] Created `scripts/p123_scheduled_trigger_recheck.py`.
- [Confirmed] First smoke artifact: `outputs/replay/trigger_rechecks/p123_trigger_recheck_smoke_20260527.json`.
- [Confirmed] First smoke classification: `P122_ALL_TRIGGERS_STILL_BLOCKED`.
- [Confirmed] P123 did not install crontab, create launchd plist, or register an OS scheduler.
- [Confirmed] P123 worktree guard requires `git-dir=.git`, rejects `.git/worktrees/`, `claude/`, and `codex/`.

### Replay Coverage / Prediction-Helpfulness Context

- [Confirmed] P91 identified 512 strategy universe entries and 31 row-backed strategy slots.
- [Confirmed] P92 found 5 adapter-ready Tier B strategies, 1 adapter-partial strategy, 3 already-covered strategies, and 1 rejected strategy.
- [Confirmed] P93 dry-run rehearsed 5 Tier B adapters, including 3/5-bet DAILY_539 and 2/3/4-bet BIG_LOTTO/POWER_LOTTO strategies.
- [Confirmed] P94 controlled apply added Tier B rows and P96 later set 54462 as accepted replay baseline.
- [Confirmed] P112 audited 36 row-backed strategies across POWER_LOTTO, DAILY_539, and BIG_LOTTO for prediction-helpfulness.
- [Confirmed] P112 excluded 3_STAR and 4_STAR: P108 blocked for 3_STAR, 4_STAR unauthorized due source_unknown.
- [Confirmed] P93/P94 evidence shows a multi-bet caveat: many replay rows are one row per strategy/draw and may represent only bet 1 unless a true multi-bet adapter path exists.

## 5. Unfinished Work Assessment

- [Blocked] P108 Special3 100-draw re-evaluation: 63/100 prospective draws; 37 remaining.
- [Blocked] P117 POWER_LOTTO OOS checkpoint: 0 new POWER_LOTTO draws; 30 remaining for partial, 40 for full.
- [Blocked] P118 BIG_LOTTO actual quarantine: exact authorization phrase absent.
- [Blocked] 4_STAR provenance/backtest: source_unknown caveat active; provenance artifact absent.
- [Missing] All implemented strategy x lottery x bet-count coverage matrix for the user goal: all supported lottery types and all implemented 1-5 bet-count variants.
- [Blocked] Multi-bet replay truth model: current row convention can underrepresent native multi-bet strategies.
- [Deferred] Runtime artifact retention policy for `outputs/replay/trigger_rechecks/`.
- [Deferred] OS scheduler installation; not authorized by P123.
- [Deferred] Worktree hygiene and DB staging policy remains valuable but outside this CTO task.

## 6. P0 / P1 / P2 / P3-P10 Reprioritization

| Priority | Work | Status | Rationale |
|---|---|---|---|
| **P0.1** | Trigger governance standby through P123 wrapper | [Confirmed] P123 ready | Prevent no-change PR churn and preserve healthy wait state. |
| **P0.2** | Canonical execution and contamination guard standardization | [Required] | Worktree branch and cross-project contamination are proven process risks. |
| **P0.3** | Multi-bet replay truth model | [Missing] | Correctness blocker for replaying all 1-5 bet combinations. |
| **P1.1** | All implemented strategy x lottery x 1-5 bet-count coverage matrix | [Ready for CEO approval] | Highest product-value next step while draw/authorization triggers are blocked. |
| **P1.2** | Adapter gap plan for truthful coverage completion | [Depends on P1.1] | Converts coverage gaps into ranked implementation phases without DB writes. |
| **P1.3** | Prediction-helpfulness guard for expansion | [Partially complete via P112-P114] | Coverage must not imply quality, promotion, or recommendation. |
| **P2** | Trigger-met execution paths | [Blocked] | P108/P117/P118/4_STAR tasks only after P123 classification changes. |
| **P3** | 4_STAR provenance path | [Blocked] | Backtest requires provenance and explicit authorization. |
| **P4** | Runtime trigger artifact retention / latest-pointer policy | [Deferred] | Prevent long-term trigger-recheck artifact noise. |
| **P5** | Optional scheduler installation | [Deferred] | Requires explicit OS-level authorization. |
| **P6** | Replay UI/API disclosure for bet-count truth | [Deferred] | UI should not misrepresent first-bet fallback as full multi-bet replay. |
| **P7** | Worktree hygiene / DB staging policy | [Deferred but risky] | Dirty working tree remains a staging hazard. |
| **P8** | Future OOS monitoring after draw thresholds | [Waiting on data] | P108/P117 re-enter only when thresholds are crossed. |
| **P9** | External reference review | [Paused] | New repo is forbidden and this is not critical path. |
| **P10** | Post-launch operations cadence | [Deferred] | Long-term monitoring and regression cadence. |

Changes from prior roadmap:

- [Confirmed] P105/P106/P107B are no longer current P0 blockers; they are completed and incorporated in P119 evidence.
- [Confirmed] P123 wrapper usage replaces future no-change P124/P125 trigger recheck PRs.
- [Confirmed] Worktree branch guard is upgraded to P0.
- [Confirmed] Multi-bet replay truth model is upgraded to P0.3 because the user's highest priority requires truthful 1-5 bet replay.
- [Confirmed] All implemented strategy coverage matrix is upgraded to P1.1.
- [Confirmed] 4_STAR backtest remains blocked.
- [Confirmed] OS scheduler installation remains deferred.

## 7. Critical Blockers

### Blocker 1: Trigger Wait-State

- **Impact scope:** P108, P117, P118, 4_STAR.
- **Why blocker:** All governed execution paths need data or explicit authorization that is not present.
- **Risk if ignored:** Premature evaluation, OOS checkpoint, quarantine, or backtest would violate governance.
- **Priority:** P0.1.
- **Acceptance criteria:** Use P123 wrapper; if classification remains `P122_ALL_TRIGGERS_STILL_BLOCKED`, do not open a new branch, PR, or P-task.

### Blocker 2: Worktree Branch / Context Contamination Risk

- **Impact scope:** Repo integrity and multi-agent safety.
- **Why blocker:** P123 first attempt proved Claude worktree branch risk; prior prompts also had cross-project contamination.
- **Risk if ignored:** Work lands in wrong path/branch or inherits Betting/Stock/Novel/SCB governance.
- **Priority:** P0.2.
- **Acceptance criteria:** Every governed prompt checks repo path, branch, `git rev-parse --git-dir`, and project lock before implementation.

### Blocker 3: Multi-Bet Replay Truth Ambiguity

- **Impact scope:** Product correctness for all 1-5 bet-count combinations.
- **Why blocker:** Existing rows may represent only the first bet even when strategy names or adapters imply multiple bets.
- **Risk if ignored:** The UI/API could claim full multi-bet historical replay when only bet 1 was evaluated.
- **Priority:** P0.3.
- **Acceptance criteria:** Read-only truth model classifies every implemented strategy/bet-count variant as native multi-bet, first-bet-only fallback, adapter-missing, already-covered, unsupported, rejected, or fabrication-prohibited.

### Blocker 4: Incomplete All-Implemented-Strategy Coverage Matrix

- **Impact scope:** Product maturity and planning.
- **Why blocker:** The highest product goal needs a measurable gap list before implementation.
- **Risk if ignored:** Worker tasks may add rows opportunistically rather than completing all implemented strategies systematically.
- **Priority:** P1.1.
- **Acceptance criteria:** Matrix covers all implemented strategy IDs, lottery types, native bet counts, supported target bet counts 1-5, current replay rows, adapter status, quality label, and next action.

### Blocker 5: 4_STAR Source Unknown

- **Impact scope:** Data quality and backtest authorization.
- **Why blocker:** P104/P119-P123 preserve source_unknown; provenance artifact absent.
- **Risk if ignored:** Backtest on unverifiable actuals.
- **Priority:** P3.
- **Acceptance criteria:** Separate provenance acceptance artifact and explicit backtest authorization before any 4_STAR backtest.

## 8. Recommended System Optimization Directions

### 1. Make P123 The Standing Trigger Gate

- **Corresponding roadmap phase:** P0.1.
- **Why important:** It prevents no-change PR churn while keeping trigger checks deterministic.
- **System maturity gain:** Turns monitoring into a low-cost operator action.
- **Expected benefit:** Lower CI/agent cost and clearer standby state.
- **Risk:** Operators may assume cron/launchd is installed; it is not.
- **Acceptance:** P123 wrapper run from canonical repo; no branch/PR when classification remains blocked.
- **Priority:** P0.

### 2. Standardize Execution Guardrails

- **Corresponding roadmap phase:** P0.2.
- **Why important:** Worktree branch and cross-project contamination are not theoretical; both appeared in this workflow.
- **System maturity gain:** Protects canonical repo integrity.
- **Expected benefit:** Less recovery work and fewer accidental scope violations.
- **Risk:** Long prompt guard sections may drift until centralized.
- **Acceptance:** All future governed tasks check `show-toplevel`, branch, `git-dir=.git`, forbidden branch prefixes, and `PROJECT_CONTEXT_LOCK=LotteryNew`.
- **Priority:** P0.

### 3. Define The Multi-Bet Replay Truth Model

- **Corresponding roadmap phase:** P0.3.
- **Why important:** The user's top priority cannot be met if first-bet-only rows masquerade as 1-5 bet replay.
- **System maturity gain:** Makes historical replay verifiable at the bet-count level.
- **Expected benefit:** Accurate gap planning for all lottery types and 1-5 bet variants.
- **Risk:** May reveal that existing row-backed coverage is less complete than strategy names imply.
- **Acceptance:** Read-only artifact; no DB writes; no fabricated rows; clear classifications for every implemented strategy variant.
- **Priority:** P0.

### 4. Build All-Strategy Bet-Count Coverage Matrix

- **Corresponding roadmap phase:** P1.1.
- **Why important:** It is the first concrete step toward "all implemented strategies historical replay."
- **System maturity gain:** Converts a broad product ambition into a measurable backlog.
- **Expected benefit:** Planners can rank adapter work and controlled apply work by gap severity and quality value.
- **Risk:** Scope can balloon if it includes unimplemented or rejected strategies without labels.
- **Acceptance:** Matrix covers strategy_id, lottery_type, native bet count, supported 1-5 target counts, replay rows, adapter status, blocker, quality label, and proposed next task type.
- **Priority:** P1.

### 5. Keep Provenance-First Expansion For Source-Unknown Data

- **Corresponding roadmap phase:** P2/P3.
- **Why important:** 4_STAR rows exist but remain source-unknown.
- **System maturity gain:** Prevents data availability from being confused with analysis authorization.
- **Expected benefit:** Future 4_STAR work can proceed safely once provenance is resolved.
- **Risk:** Backtest pressure may bypass source controls.
- **Acceptance:** Provenance accepted and backtest explicitly authorized before any 4_STAR analysis.
- **Priority:** P2/P3.

## 9. Roadmap Changes Applied

- [Confirmed] Updated `roadmap.md` from P104-current to P123-current.
- [Confirmed] Added P119-P123 phase status, PR/merge evidence, and current trigger wait-state.
- [Confirmed] Replaced P105/P106/P107 as current blockers with completed status from P119 evidence.
- [Confirmed] Added P123 wrapper as the canonical no-change trigger recheck path.
- [Confirmed] Added worktree branch guard and cross-project contamination guard as P0 execution rules.
- [Confirmed] Added multi-bet replay truth model as P0.3.
- [Confirmed] Added all implemented strategy x lottery x 1-5 bet-count coverage matrix as P1.1.
- [Confirmed] Preserved 4_STAR backtest block and source_unknown caveat.
- [Confirmed] Documented that CTO did not emit or write an `active_task.md` prompt because the instructions forbid new worker task prompt output and CTO may only update two files.
- [Confirmed] Did not modify `00-Plan/roadmap/CEO-Decision.md`.
- [Confirmed] Did not modify `00-Plan/roadmap/active_task.md`.
- [Confirmed] Did not write production DB, install scheduler, create repo, create branch, create PR, mutate lifecycle/champion/registry, run P108/P117/P118, or backtest 4_STAR.

## 10. Risks / Unknowns

- [Confirmed] All four triggers remain blocked: P108 needs 37 Special3 draws, P117 needs 30/40 POWER_LOTTO draws, P118 needs exact phrase, 4_STAR needs provenance.
- [Confirmed] P123 wrapper is not an installed scheduler.
- [Confirmed] Dirty worktree remains and includes DB/history/pid/runtime/untracked files; this CTO task did not clean them.
- [Confirmed] Current replay rows do not automatically prove full native multi-bet coverage.
- [Confirmed] 4_STAR source remains unknown.
- [Unknown] Whether future operator wants a real cron/launchd schedule.
- [Unknown] Whether `outputs/replay/trigger_rechecks/` should remain fully tracked, partly ignored, or use a latest pointer.
- [Unknown] Full number of implemented strategy x lottery x bet-count gaps until the proposed coverage matrix is built.
- [Inferred] The next high-value work is not another trigger recheck PR, but a read-only multi-bet coverage/gap audit.
- [Inferred] Some previously row-backed strategies may need relabeling as first-bet-only for product honesty.

## 11. CTO Final Recommendation

Do not open P124/P125 merely to re-confirm no trigger change. Use `scripts/p123_scheduled_trigger_recheck.py` from the canonical repo when data or authorization might have changed. If it returns `P122_ALL_TRIGGERS_STILL_BLOCKED`, stay in `WAIT_FOR_DATA_OR_AUTHORIZATION`.

Given the user's highest priority, the next CEO-approved governed work should be a read-only **multi-bet replay truth model and all implemented strategy x lottery x 1-5 bet-count coverage matrix**. This should inventory the current strategy universe and replay rows, classify true native multi-bet coverage versus first-bet-only fallback, and produce a precise gap list. It must not write DB rows, stage DB/history files, run P108/P117/P118, backtest 4_STAR, install schedulers, or promote strategies.

### CEO-Gated First Executable Task Status

- [Blocked] A full worker task prompt is not emitted by this CTO update because the instruction set explicitly says "CTO must not produce a new worker task prompt" and CTO may only update `roadmap.md` and `CTO-Analysis.md`.
- [Inferred] If CEO overrides that restriction later, the first executable task should be a read-only multi-bet replay coverage matrix, not a no-change trigger recheck PR.
- [Confirmed] `00-Plan/roadmap/active_task.md` was not modified.

## 12. CTO Summary In 5 Lines

1. [Confirmed] P123 is merged; wrapper `scripts/p123_scheduled_trigger_recheck.py` replaces no-change trigger PRs.
2. [Confirmed] Current runtime classification remains `P122_ALL_TRIGGERS_STILL_BLOCKED`; system is healthy standby.
3. [Blocked] P108, P117, P118, and 4_STAR remain blocked by data/provenance/authorization.
4. [P0] Future work must enforce `git-dir=.git` and project contamination guards.
5. [P1] Highest product-value next work is read-only all implemented strategy x lottery x 1-5 bet-count replay coverage truth mapping.

## 13. CEO Summary In 5 Lines

1. [Confirmed] Stop spending PRs on no-change trigger checks; use P123 wrapper manually when inputs change.
2. [Confirmed] No P108/P117/P118/4_STAR task is eligible today.
3. [Risk] Full historical replay across 1-5 bets is not yet proven because some rows are first-bet-only.
4. [Decision] Approve a read-only coverage/gap audit before any new replay apply.
5. [Guard] No DB writes, no scheduler install, no worktree branch, no cross-project governance.

Final Classification: `CTO_ROADMAP_UPDATED_WITH_RISKS`

---

## 14. P124 Follow-Up Note (2026-05-28)

P124 was completed as a read-only worker task on branch `p124-multi-bet-truth-coverage-matrix`.

### P124 Summary
- **Artifact:** `outputs/replay/p124_multi_bet_truth_and_coverage_matrix_20260528.json`
- **Classification:** `P124_MULTI_BET_TRUTH_AND_COVERAGE_MATRIX_READY`
- **DB snapshot confirmed:** replay_rows=54462, 3_STAR=4179/115000106, 4_STAR=2922/115000103, POWER_LOTTO=1913/115000041 (unchanged)
- **Coverage matrix:** 36 strategy×lottery pairs across DAILY_539, BIG_LOTTO, POWER_LOTTO
- **Key finding:** Zero strategies currently achieve `native_multi_bet` storage. All 36 pairs store exactly 1 predicted_numbers list per row.

### Gap Summary
| Gap Type | Count | Next Action |
|---|---|---|
| first_bet_only_fallback (with Tier-B adapter available) | 5 | controlled_apply |
| first_bet_only_fallback (adapter build required) | 9 | adapter_build |
| first_bet_only_fallback (partial adapter, relabel needed) | 2 | relabel_first_bet_only |
| already_covered (1-bet strategies) | 7 | no_action |
| rejected (expansion forbidden) | 13 | no_action |

### Confirmations
- [Confirmed] No DB writes, no staging of lottery_v2.db or lottery_history.json
- [Confirmed] No strategy promotion, lifecycle mutation, registry mutation
- [Confirmed] No P108/P117/P118 execution, no 4_STAR backtest, no scheduler install
- [Confirmed] P124 tests: 27 passed, P119-P123 regression: 318 passed
- [Confirmed] Drift guard: PASS, Branch governance: PASS

---

## 15. P125 Follow-Up Note (2026-05-28)

P124 branch was merged to `main` (commit `77d7d7d`) as Phase 1 of P125.
P125 was then implemented as a read-only adapter gap plan on `main`.

### P125 Summary
- **Script:** `scripts/p125_adapter_gap_plan_from_p124.py`
- **JSON:** `outputs/replay/p125_adapter_gap_plan_from_p124_20260528.json`
- **Markdown:** `docs/replay/p125_adapter_gap_plan_from_p124_20260528.md`
- **Tests:** `tests/test_p125_adapter_gap_plan_from_p124.py` — 54 passed
- **Classification:** `P125_ADAPTER_GAP_PLAN_READY`

### P125 Outputs
| Section | Count |
|---|---|
| controlled_apply_ready (Tier-B, P126 scope) | 5 |
| adapter_build_needed (P127 scope) | 12 |
| relabel_only | 2 |
| no_action kept | 17 |
| replay_storage_design_risks | 4 (RSR-1 through RSR-4) |

### Confirmations (P125)
- [Confirmed] No DB writes, no staging of lottery_v2.db or lottery_history.json
- [Confirmed] No strategy promotion, lifecycle mutation, registry mutation
- [Confirmed] No P108/P117/P118 execution, no 4_STAR backtest, no scheduler install
- [Confirmed] No fabricated replay rows
- [Confirmed] P125 tests: 54 passed, P124 + P119-P123 regression: 345 passed
- [Confirmed] Drift guard: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
- [Confirmed] replay_rows = 54462 (unchanged before and after P125)

### Remaining Risks
| Risk | Status |
|---|---|
| Native multi-bet storage format not decided | P128 required before any apply |
| 5 Tier-B controlled_apply candidates need explicit authorization per apply | P126 gate |
| 12 adapter_build strategies need new get_all_bets() implementations | P127 gate |
| 4_STAR provenance still unresolved | Blocked indefinitely |
| P108 needs ~37 more Special3 draws | Blocked |
| P117 POWER_LOTTO OOS needs 30-40 more draws | Blocked |

### Next Task
**P126_CONTROLLED_APPLY_PLAN_FOR_TIER_B_MULTI_BET_ADAPTERS**
- Requires explicit apply authorization per strategy
- Must run dry-run before any apply
- Must verify no duplicate bet-1 rows
- Must confirm P128 storage design or explicitly authorize one-row-per-bet convention

### Next Task
`P125_ADAPTER_GAP_PLAN` — plan controlled_apply passes for the 5 Tier-B adapter-ready strategies and define adapter build specs for remaining multi-bet strategies.

---

## P126 — Controlled Apply Dry-Run Plan for Tier-B Multi-Bet Adapters

- **Task:** `P126_CONTROLLED_APPLY_PLAN_FOR_TIER_B_MULTI_BET_ADAPTERS`
- **Date:** 2026-05-28
- **Script:** `scripts/p126_controlled_apply_plan_tier_b_multi_bet.py`
- **JSON:** `outputs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.json`
- **MD:** `docs/replay/p126_controlled_apply_plan_tier_b_multi_bet_20260528.md`
- **Tests:** `tests/test_p126_controlled_apply_plan_tier_b_multi_bet.py` — 151 passed
- **Classification:** `P126_DRY_RUN_PLAN_READY`

### P126 Row Delta Summary
| Apply Order | Strategy | Lottery | Bets | +New Rows | Total After |
|---|---|---|---|---|---|
| 1 | `biglotto_echo_aware_3bet` | BIG_LOTTO | 3 | +3000 | 57462 |
| 2 | `daily539_f4cold_5bet` | DAILY_539 | 5 | +6000 | 63462 |
| 3 | `daily539_f4cold_3bet` | DAILY_539 | 3 | +3000 | 66462 |
| 4 | `power_fourier_rhythm_2bet` | POWER_LOTTO | 2 | +1500 | 67962 |
| 5 | `biglotto_ts3_markov_4bet_w30` | BIG_LOTTO | 4 | +4500 | 72462 |
| **TOTAL** | | | | **+18| **TOTAL** | | | | **+18| **TOTAL** | | | | **+18| **TOTAL** | | | | Pro| **TOTAL** | | | | **+18| **TOTAL** | | | | **+18| **TOTAL** | | | |ONTROLLED_APPLY |
| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Duplin| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Duplin| DupliLA| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Duplinri| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Dupli| Duplin| Dupli|or lottery_history.json
- [Confirmed] No strategy promotion, scheduler install, lifecycle mutation
- [Confirmed] No P108/P117/P118 execution, no 4_STAR action, no fabricated rows
- [Confirmed] PRAGMA query_only = ON enforced on every DB connection
- [Confirmed] P126 tests: 151 passed; P125+P124+P119-P123 regression: 399 passed
- [Confirmed] Drift guard: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS
- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_28)- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_28)- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] reatio- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_28)- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_28)- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] reatio- [Confirmed] replay_rows = 54462 (unchanged be- [he- [Confirmed] replay_rows = 54462 (unchanged be- [Confirmed] replay_rows Kelvin

Final roadmap marker:

```text
CTO_ROADMAP_UPDATED_AFTER_P126_DRY_RUN_PLAN_20260528
```

---

## P128: Native Multi-Bet Replay Storage Design

**Task ID:** P128
**Classification:** P128_NATIVE_MULTI_BET_STORAGE_DESIGN_READY
**Commit:** pending (this session)
**DB rows before / after:** 54462 / 54462 (read-only — zero writes)

### Problem Resolved

P126 identified RSR-1 (no storage format decided for multi-bet rows) and RSR-2 (no bet_index column).
P128 resolves both. The current UNIQUE constraint `(lottery_type, target_draw, strategy_id, replay_run_id)`
has all P94 Tier-B rows with `replay_run_id=NULL` — SQLite's NULL-distinct behavior technically permits
multi-bet inserts today, but this is accidental, fragile, and not a valid convention.

### Decision

| Aspect | Decision |
|---|---|
| Storage model | one-row-per-bet (APPROVED) |
| bet_index column | Required — `INTEGER NOT NULL DEFAULT 1` |
| New UNIQUE constraint | `UNIQUE(lottery_type, target_draw, strategy_id, bet_index)` |
| Migration | SQL| Migration | SQL| Migration | SQL| Migration | SQL| Migration | SQL| Migration | SQL| Migrad �|� al| Migration | SQL| Migration | SQL| Migr## P126 A| Migratdiness Aft| Migration | SQL| Migration | SQL| Migration | SQL| Migratioly| Migration | SQL| Migration | SQn_| Migration | SQL| Migration | SQL| Migration | SQL| Migration | SQLses| Migration | SQL| ndidate)
3. Migration execution
4. RSR-3 (drift guard count update after apply)

### Artifacts

- `script- `script- `script- `script- `script- `script- `script- `script- `script- `script- `script- `script- `s528.j- `script- `script- `script- `script- `script- `script- `script- `script- `script- `script- `script- `bet_- `script- `script- `script- `script- `script- `script- `script- `script- `script- B wr- `script- [Co- `script- `script- ge- `scripec- `script- `script- `script- `script- `scripr, no strategy promotion
- [Confirmed] No 4_STAR / P108 / P117 / P118
- [Confirmed] PRAGMA query_only = ON on all DB connections
- [Confirmed] replay_rows = 54462 (unchanged)
- [Confirmed] RSR-1 resolved, RSR-2 resolved
- [Confirmed] P128 tests: 146 passed; P126+P125+P124 regression: 232 passed
- [Confirmed] Drift guard: REPLAY_LIFECYCLE_DRIFT_GUARD_PASS

Final roadmap marker:

```text
CTO_ROADMAP_UPDATED_AFTER_P128_STORAGE_DESIGN_20260528
```
