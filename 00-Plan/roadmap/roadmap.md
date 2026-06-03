# Lottery Replay Roadmap

**Last Updated:** 2026-06-02 Asia/Taipei (CTO alignment after PR #249 merge + P209 repo archive closure)
**Owner:** CTO agent
**Primary Goal:** Keep LotteryNew replay, research, and product evidence truthful, reproducible, and governed. The current maturity bottleneck has shifted from migration rehearsal to short/mid-window strategy protocol design, anti-overfit validation, canonical repo dispatch safety, and honest product disclosure.
**Repo Policy:** Use `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` only. Do not create a new repo. Production DB, registry, and data writes require explicit governed authorization. CTO roadmap updates are limited to this file and `00-Plan/roadmap/CTO-Analysis.md`. CTO must not write `CEO-Decision.md`, `active_task.md`, `production/*`, `registry/*`, `data/*`, or any new repo.

---

## 0. Current Roadmap Override — 2026-06-02

This section is the current source of truth. The 2026-06-01 sections and P186-P196 appendices below are retained for history and are superseded where they conflict with this section.

### 0.1 Latest Phase Status

| Phase / Chain | Status | Evidence | CTO Note |
|---|---|---|---|
| P149-P159B replay product closure | [Confirmed] Complete | `00-Plan/roadmap/CEO-Decision.md`; prior P159B handoff | Historical product baseline accepted; now merged through the reconciliation chain. |
| R1/R2 POWER_LOTTO research P161-P178A | [Confirmed] Closed NULL result | `outputs/research/power_lotto/p178a_r2_research_closure_archive_20260601.*` | 17 strategies/candidates produced no corrected-significant OOS edge. Do not restart old R2 candidates. |
| P183-P188 DB migration chain | [Confirmed] Complete | `outputs/research/power_lotto/p188_production_db_migration_execution_20260601.*`; read-only SQLite check | Production local DB is now 94,924 rows with `bet_index` present and 0 duplicate keys. |
| P189-P205 post-migration / PR #249 chain | [Confirmed] Complete | git log `061bdc1`, `d119ea6`, `4a36b12`, `41449fb`, `a3e30ae`; handoff report | Drift guard, stale HEAD-only tests, DB binary exclusion, PR/CI, and merge are reported complete. |
| P206-P207 local main sync / branch cleanup decision | [Confirmed] Complete by handoff | user handoff report; current HEAD `061bdc19...` on `main` | Latest known full suite from handoff: 1097 passed, 0 failed; CTO did not rerun tests in this review. |
| P208-P209 repo archive cleanup closure | [Confirmed] Complete | `/Users/kelvin/Kelvin-WorkSpace/_archive/lottery_stale_repos_20260602_162329/README_DO_NOT_USE.md`; root `Lottery*` listing | `Lottery/` and `LotteryNew-clean/` are archived, not deleted; future dispatch must use only canonical `LotteryNew`. |
| SZC1/SZC2 second-zone containment | [Confirmed] Complete | existing SZC evidence cited in 2026-06-01 roadmap/CEO decision | Second-zone remains display-only / no-signal unless future pre-registered evidence beats random. |
| P210 short/mid-window strategy protocol | [Missing] / [Blocked] | user 2026-06-02 supplement | New direction is valid as a design target, but scope/windows/gates are not frozen and implementation is not authorized. |
| New worker task prompt / `active_task.md` | [Blocked] | current CTO instruction conflict | User asks for a prompt but also forbids CTO from producing worker prompts and limits CTO writes to two files. CTO does not update `active_task.md`. |

### 0.2 Current System Baseline

| System State | Value | Status |
|---|---:|---|
| Current repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | [Confirmed] |
| Current branch | `main` | [Confirmed] |
| Current HEAD | `061bdc19c0a59e6948e8335b888257a1f7c521f6` (`Merge pull request #249`) | [Confirmed] |
| Root `Lottery*` folders | only `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | [Confirmed] |
| Archived stale repos | `_archive/lottery_stale_repos_20260602_162329/{Lottery,LotteryNew-clean}` | [Confirmed] |
| Production replay table | `strategy_prediction_replays` | [Confirmed] |
| Production replay rows | 94,924 | [Confirmed] read-only SQLite |
| Production `bet_index` column | present | [Confirmed] read-only SQLite |
| Duplicate `(lottery_type,target_draw,strategy_id,bet_index)` keys | 0 | [Confirmed] read-only SQLite |
| POWER_LOTTO rows | 36,104 | [Confirmed] read-only SQLite |
| `bet_index` distribution | 1=54,302; 2=16,581; 3=15,041; 4=6,000; 5=3,000 | [Confirmed] read-only SQLite |
| Latest known full suite | 1097 passed / 0 failed | [Confirmed] handoff report; [Unknown] not rerun by CTO |
| Worktree status | dirty outside CTO scope | [Confirmed] `git status --short` |
| Formal 2026-06-02 CEO decision for P210 | absent from allowed CTO sources | [Unknown] |

### 0.3 Roadmap Alignment Assessment

| Item | Classification | Assessment |
|---|---|---|
| P188-P205 migration / PR completion | [Aligned] | This directly resolves the prior P0 canonical DB blocker and branch-protection / DB-binary risks. |
| P206-P209 repo archive cleanup | [Aligned] | Strongly aligns with "no new repo" and reduces wrong-repo dispatch risk. |
| P186/P187/P188 still shown as blockers in older sections | [Outdated] | The older 2026-06-01 blocker state is superseded by P188 completion and PR #249 merge. |
| Main/zen-gates split as current P0 | [Outdated] | Current local main is at 94,924 rows with `bet_index`; the split is no longer the top blocker. |
| Short/mid-window strategy direction | [Missing] | User's latest direction is not yet represented as a governed phase with frozen windows, scope, and validation gates. |
| Long-term frequency as primary filter | [Drift] / [Outdated] | Latest user direction demotes full-period frequency distribution to reference information only. |
| Reusing old POWER_LOTTO R2 candidates | [Outdated] / [Blocked] | P178A closed R2 active research; new work must be a new pre-registered protocol, not a rerun. |
| Worker prompt output today | [Blocked] | CTO cannot produce a new worker prompt or write `active_task.md` under the strict limits in this request. |

### 0.4 Reprioritized P0-P10

| Priority | Phase | Focus | Current Status | Acceptance Criteria |
|---|---|---|---|---|
| **P0.1** | P210 protocol governance | Freeze short/mid-window strategy scope before any implementation | [Blocked] CEO/user decision needed | Windows, lottery scope, metrics, baselines, holdout/walk-forward plan, multiple-testing correction, and "long-term as reference only" rule are documented. |
| **P0.2** | Anti-overfit validation gate | Prevent short-window noise from becoming false signal | [Missing] | Any future strategy claim must beat random and best-simple baselines under pre-registered walk-forward/OOS with corrected significance and CI. |
| **P0.3** | Canonical execution / repo dispatch guard | Ensure every agent uses only `LotteryNew/main` and not archived/stale worktrees | [Confirmed] baseline; [Missing] task guard template | Prompts and worker reports must STOP on `.claude/worktrees/*`, archive paths, wrong branch, wrong HEAD/DB baseline, or broad staging. |
| **P0.4** | CTO/CEO task-generation boundary | Resolve prompt-generation conflict for the next executable task | [Blocked] | CEO/Planner explicitly authorizes one task prompt or relaxes CTO prompt restriction; CTO writes only allowed files. |
| **P1.1** | Short/mid-window diagnostic implementation | Execute read-only analysis after P210 protocol approval | [Deferred] | Report/JSON only; no production write; no strategy promotion; compares 10-50 and 100-300 windows against random/simple baselines. |
| **P1.2** | Product disclosure and second-zone containment | Make UI/API wording consistent with NULL/no-signal evidence | [Deferred] | No surface implies guaranteed improvement, betting advice, or second-zone predictive edge. |
| **P1.3** | Post-merge quality gate maintenance | Keep drift guard, DB manifest, and CI assumptions aligned with 94,924-row local state | [Confirmed] baseline; [Deferred] maintenance | CI/test artifacts continue to pass; DB binary remains excluded from git; manifests evidence local DB state. |
| **P2.1** | Passive monitoring / reopen rules | Monitor POWER_LOTTO only under P178A reopen conditions | [Waiting] | Reopen only after >=500 new draws after 115000041, structural change, independent evidence, or explicit governance design. |
| **P2.2** | Archive retention / cleanup decision | Decide whether archived stale repos remain indefinitely | [Deferred] | No deletion without explicit destructive authorization; archive README remains clear. |
| **P3** | Other lottery research | DAILY_539, BIG_LOTTO, 3_STAR, 4_STAR research | [Deferred] | Separate authorization; must inherit P210 validation gates. |
| **P4** | Replay product backlog | UI polish, monitoring dashboards, operator reporting | [Deferred] | Does not consume P0/P1 validation or governance capacity. |
| **P5** | Optional scheduler / automation | Cron/launchd/automation setup | [Deferred] | Explicit OS-level authorization only. |
| **P6** | External reference review | Architecture notes only if useful | [Paused] | No clone/new repo. |
| **P7** | Worktree hygiene | Clean dirty runtime/data files | [Deferred but risky] | Only with explicit cleanup authorization and file allowlist. |
| **P8** | Future OOS re-evaluation | Retest only after new data thresholds | [Waiting] | Pre-registered configs; no post-hoc threshold tuning. |
| **P9** | Product packaging | Release notes / operational docs | [Deferred] | After P210/P1 evidence boundary is stable. |
| **P10** | Long-term cadence | Periodic governance review | [Deferred] | Low-cost checks without no-change churn. |

Upgrade / downgrade decisions:

| Item | Decision | Reason |
|---|---|---|
| Short/mid-window protocol | Upgrade to P0 | This is the next true maturity gate because implementation without frozen validation would overfit. |
| Anti-overfit validation | Upgrade to P0 | Short windows (10-50) are noisy; corrected significance and walk-forward gates are mandatory. |
| Canonical repo dispatch guard | Keep P0/P1 | Wrong worktree/repo dispatch repeatedly caused STOP conditions; archive now exists and must not be used. |
| P186/P187/P188 migration blocker | Downgrade to historical complete | Current DB is 94,924 rows with `bet_index`; PR #249 merged. |
| Long-term full-period frequency as filter | Downgrade / retire as primary filter | Latest direction makes it reference-only, not a gating condition. |
| Active POWER_LOTTO R2 optimization | Retire / keep closed | P178A closed R2 after NULL results. |
| Second-zone optimization | Retire as active goal; keep containment | Existing evidence remains below random; display-only unless future pre-registered proof appears. |
| P123 trigger standby and old apply chains | Keep P3+ guardrails | Useful history, not today's bottleneck. |

### 0.5 Critical Blockers

| Blocker | Impact | Why It Blocks | Risk If Ignored | Priority | Acceptance |
|---|---|---|---|---|---|
| Undefined short/mid-window protocol | Research correctness, product value | User direction is clear conceptually but windows, lottery scope, metrics, and baselines are not frozen | A worker may implement ad-hoc strategy search and overfit recent draws | P0.1 | Plan-only protocol documents 10-50 and 100-300 window sets, scope, baselines, OOS/walk-forward, correction, and no production writes. |
| Short-window overfitting / multiple testing | System correctness, trust | Many windows/strategies can create false positives | False "improved prediction" claims or strategy promotion from noise | P0.2 | Pre-registered evaluation, random and simple-frequency baselines, best-single-strategy baseline, CI, corrected p-values, and negative-result acceptance. |
| Task-prompt governance conflict | Workflow orchestration | Current request asks for a worker prompt but also forbids CTO from producing one and limits CTO writes to two files | CTO could violate governance or produce an unauthorized task | P0.4 | CEO/Planner supplies or authorizes the next prompt; CTO does not write `active_task.md`. |
| Wrong repo/worktree dispatch | Reproducibility, safety | `.claude/worktrees/*` and archived stale repos still exist and have incompatible states | Agents may run stale DB/code and produce invalid evidence | P0.3 | Every future task includes canonical repo/branch/DB STOP guard and archive DO_NOT_USE rule. |
| Evidence disclosure gap | Product maturity | Lottery outputs can be misread as betting advice or validated edge | User trust and safety risk from overclaiming | P1.2 | UI/API/report copy separates historical evidence from predictive claims and keeps second-zone display-only. |

### 0.6 Recommended System Optimization Directions

#### Direction A: Short/Mid-Window Strategy Protocol Governance

- **Roadmap phase:** P0.1 / P210.
- **Why important:** The user’s latest direction is promising but high-risk unless the evaluation design is frozen first.
- **System maturity gain:** Converts intuition into a reproducible research protocol before code or strategy changes.
- **Expected benefit:** Future work can test 10-50 and 100-300 draw windows without leaking future data or tuning after results.
- **Risk:** Too much freedom in window choice will manufacture false positives.
- **Acceptance:** Plan-only protocol defines scope, windows, baselines, OOS/walk-forward, correction method, report format, and no production writes.
- **Priority:** P0.

#### Direction B: Anti-Overfit Validation And Quality Gates

- **Roadmap phase:** P0.2 / P1.1.
- **Why important:** Short-term signals are noisy and must beat random/simple baselines, not just look better in-sample.
- **System maturity gain:** Makes "better prediction" claims falsifiable.
- **Expected benefit:** Negative results become acceptable and positive results become harder to fake.
- **Risk:** Slower iteration and fewer exciting results, but higher truthfulness.
- **Acceptance:** CI/report gate requires corrected significance, confidence intervals, fixed window registry, and explicit NULL classification.
- **Priority:** P0.

#### Direction C: Canonical Repo / DB Execution Integrity

- **Roadmap phase:** P0.3.
- **Why important:** The canonical repo is now cleanly identified, but stale worktrees/archive folders still exist.
- **System maturity gain:** Prevents dispatch, staging, or DB-baseline mistakes.
- **Expected benefit:** Less agent STOP churn and fewer invalid reports from stale repositories.
- **Risk:** Overly strict guards may block legitimate diagnostic work unless exceptions are explicit.
- **Acceptance:** Worker reports verify repo, branch, HEAD, DB rows, `bet_index`, duplicate keys, and archive/worktree STOP conditions.
- **Priority:** P0/P1.

#### Direction D: Evidence Disclosure And Recommendation Containment

- **Roadmap phase:** P1.2.
- **Why important:** Replay evidence and lottery prediction UI must not imply guaranteed improvement or wagering advice.
- **System maturity gain:** Aligns product language with NULL/no-signal research.
- **Expected benefit:** Higher operator trust and lower overclaiming risk.
- **Risk:** Product surfaces may lag research updates.
- **Acceptance:** Main-number, second-zone, lifecycle, provenance, and confidence states are labeled honestly; second-zone remains display-only.
- **Priority:** P1.

#### Direction E: Roadmap / Task Namespace Governance

- **Roadmap phase:** P0.4 / P1.3.
- **Why important:** P-number collisions and stale `active_task.md` have caused ambiguity.
- **System maturity gain:** Keeps CTO/CEO/Planner/Worker boundaries crisp.
- **Expected benefit:** Safer handoffs and fewer unauthorized worker tasks.
- **Risk:** Current request remains internally contradictory.
- **Acceptance:** Only CEO/Planner creates the next executable prompt; CTO records recommendations without producing worker prompts.
- **Priority:** P1.

### 0.7 Today's Recommended Focus

**CTO recommendation:** Focus today on **P210 short/mid-window strategy protocol discussion/design only** as the next CEO/Planner-authorized task direction. Do not implement code, do not write production/registry/data, do not create a new repo, do not rerun old POWER_LOTTO R2 candidates, and do not promote second-zone predictions.

The first executable worker prompt is **not emitted by CTO** because this request explicitly forbids CTO from producing a new worker task prompt and limits CTO writes to `roadmap.md` and `CTO-Analysis.md`.

Final current roadmap marker:

```text
CTO_ROADMAP_UPDATED_WITH_RISKS_20260602
```

---

> **⚠️ SUPERSEDED — §1–§7 below are the 2026-06-01 pre-migration snapshot (historical, NOT current truth).**
>
> Current truth is **§0 (Current Roadmap Override — 2026-06-02)** above, not the values below:
> - Production replay DB = **94,924 rows**, `bet_index` **present** (0 nulls), POWER_LOTTO **36,104** — not the `54462` / `absent` / `15142` shown below.
> - `P186` / `P188` production DB migration is **COMPLETE** (executed + merged via PR #249) — not `[Blocked]`.
> - Current `main` HEAD = `62077c7` (= `origin/main`) — not `d1a6817`.
>
> Do not read any §1–§7 baseline value, `[Confirmed]` stamp, blocker, or P0–P10 priority as current. See §0.

## 1. Phase Snapshot (2026-06-01 historical)

| Phase / Chain | Status | Evidence | CTO Note |
|---|---|---|---|
| P119-P128 trigger / multi-bet / storage design chain | [Confirmed] Complete, historical | P119-P128 artifacts and tests referenced in prior roadmap | Superseded as near-term focus by P149-P185 reconciliation and research closure. Keep as historical guardrail context. |
| P149-P159B replay product closure | [Confirmed] in handoff / [Drift] on main | `00-Plan/roadmap/CEO-Decision.md`; zen-gates handoff evidence | Replay product closure is accepted in the P159B/zen-gates state, but current `main` remains at 54462 rows and lacks `bet_index` in production DB. |
| R1/R2 POWER_LOTTO research P161-P178A | [Confirmed] Closed NULL result | `outputs/research/power_lotto/p161_*`, `p177_*`, `p178a_*` | 17 strategies/candidates produced zero corrected-significant OOS edge. No active POWER_LOTTO research, prototype, promotion, or controlled_apply is authorized. |
| P179 replay product governance backlog decision | [Confirmed] Complete | `outputs/research/power_lotto/p179_replay_product_governance_backlog_decision_gate_20260601.*` | Reprioritized toward main/zen-gates reconciliation and replay product backlog. |
| P180 combined reconciliation and replay backlog plan | [Confirmed] Complete | `outputs/research/power_lotto/p180_combined_reconciliation_and_replay_backlog_plan_20260601.*` | Plan-only. No execution, DB write, or merge. |
| P181 code/docs/tests parity plan | [Confirmed] Complete | `outputs/research/power_lotto/p181_code_docs_tests_parity_plan_20260601.*` | Defined Safe/Medium backport and test compatibility strategy. |
| P182 code/docs/tests parity backport | [Confirmed] Complete | `outputs/research/power_lotto/p182_code_docs_tests_parity_backport_20260601.*`; `active_task.md` history | Copied P161-P181 research artifacts/scripts/tests to main. No DB write; main DB still 54462 and no `bet_index`. |
| P183 controlled DB migration rehearsal plan | [Confirmed] Complete | `outputs/research/power_lotto/p183_controlled_db_migration_rehearsal_plan_20260601.*` | Found SQLite table recreation is required; simple `ALTER TABLE ADD COLUMN` is insufficient. |
| P184 controlled DB migration rehearsal on temp copy | [Confirmed] Complete | `outputs/research/power_lotto/p184_controlled_db_migration_rehearsal_temp_copy_20260601.*` | Schema rehearsal passed. Dedup `MAX(id)` reduces 54462 to 54302 base rows matching zen-gates `bet_index=1`. |
| P185 row-delta import rehearsal on temp copy | [Confirmed] Complete | `outputs/research/power_lotto/p185_row_delta_import_rehearsal_temp_copy_20260601.*`; read-only temp DB query | Full rehearsal passed: 40622 imported rows, final temp rows 94924, exact per-lottery and `bet_index` distribution match. Production DB unchanged. |
| P186 production DB migration authorization gate | [Blocked] CEO authorization required | P185 report Part F/G | Must approve dedup policy, immutable backup, production lock, SQL review, post-migration validation, and exact production phrase before any production DB write. |
| SZC1 second-zone containment diagnostic | [Confirmed] Complete | `outputs/research/power_lotto/szc1_second_zone_containment_diagnostic_20260601.*` | Final classification: `SECOND_ZONE_NO_SIGNAL_CONFIRMED`. No stable corrected-significant OOS edge above 0.125. |
| SZC2 second-zone score-guard static verification | [Confirmed] Complete | `outputs/research/power_lotto/szc2_second_zone_score_guard_audit_20260601.*` | Final classification: `SECOND_ZONE_DISPLAY_ONLY_CONFIRMED`. No static contamination of special fields into recommendation score/ranking/confidence/candidate selection. |
| New worker task prompt generation | [Blocked] | Current CTO instruction conflict | User asks for a prompt, but strict instructions also say CTO must not produce a new worker task prompt and may only update two files. No `active_task.md` update is performed by CTO. |

---

## 2. System Baseline (2026-06-01 historical — pre-migration)

Read-only checks performed by CTO on 2026-06-01:

| System State | Value | Status |
|---|---:|---|
| Current repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | [Confirmed] |
| Current branch | `main` | [Confirmed] |
| Current git-dir | `.git` | [Confirmed] |
| Current HEAD | `d1a6817 P128: define native multi-bet replay storage design` | [Confirmed] |
| Production main replay rows | 54462 | [Confirmed] read-only SQLite |
| Production main `bet_index` column | absent | [Confirmed] read-only SQLite |
| Production main POWER_LOTTO rows | 15142 | [Confirmed] read-only SQLite |
| P185 temp rehearsal rows | 94924 | [Confirmed] read-only SQLite |
| P185 temp `bet_index` column | present | [Confirmed] read-only SQLite |
| P185 temp POWER_LOTTO rows | 36104 | [Confirmed] read-only SQLite |
| P185 temp bet_index distribution | 1=54302, 2=16581, 3=15041, 4=6000, 5=3000 | [Confirmed] read-only SQLite |
| POWER_LOTTO active research | CLOSED | [Confirmed] P178A |
| POWER_LOTTO second-zone special hit rate | 0.1181 vs 0.125 random | [Confirmed] P161/P162 |
| New tests run by CTO in this review | Not run | [Confirmed] analysis-only task |

Known worktree risk:

- [Confirmed] The current git status is dirty before this CTO update, including DB/history/runtime/untracked files outside CTO scope.
- [Confirmed] CTO does not clean, stage, commit, or modify those files.
- [Inferred] Broad staging or production migration from this state would be risky without a production lock and explicit file allowlist.

---

## 3. Roadmap Alignment Assessment (2026-06-01 historical)

| Item | Classification | Assessment |
|---|---|---|
| P179-P185 reconciliation chain | [Aligned] | Correctly follows CEO/P177/P178A recommendation to prioritize main/zen-gates reconciliation over more POWER_LOTTO research. |
| P185 row-delta rehearsal completion | [Missing] | Completed artifact exists but roadmap was not fully updated before this CTO review. Added to current snapshot. |
| P186 as next step | [Blocked] | Production migration is technically rehearsed but cannot execute without CEO authorization gate. |
| P161-P178A POWER_LOTTO research closure | [Aligned] | Existing research properly reports NULL, no edge, no deployment, no wagering advice. |
| User request for second-zone optimization | [Drift] / [Blocked] | The request points at a new diagnostic/optimization path, but current evidence says second-zone is below random and POWER_LOTTO active research is closed. It must be containment/diagnostic-only unless CEO reopens scope. |
| Old P0 trigger-governance standby as top priority | [Outdated] | Still valid as a guardrail, but no longer the top maturity blocker. Current P0 is canonical DB reconciliation and migration gate. |
| Direct P126/P127 controlled applies | [Outdated] | Superseded by P184/P185 migration rehearsal and the 94924-row zen-gates reconciliation path. |
| Roadmap file structure before this update | [Outdated] | Mixed 2026-05-28 state, 2026-06-01 appended state, and corrupted table text. CTO rewrote into a compact current-state roadmap while preserving historical references. |
| Active task / worker prompt request | [Blocked] | CTO cannot write `active_task.md` or emit a new worker task prompt under the strict limitations in this request. |

---

## 4. Reprioritized P0-P10 (2026-06-01 historical)

| Priority | Phase | Focus | Current Status | Acceptance Criteria |
|---|---|---|---|---|
| **P0.1** | P186 production migration authorization gate | Decide whether production main may migrate from 54462/no `bet_index` to the validated 94924/`bet_index` state | [Blocked] CEO auth required | P186 plan-only artifact approves or rejects dedup policy, backup, production lock, SQL log, validation checklist, rollback, and exact execution phrase. No production DB write in P186. |
| **P0.2** | Canonical data reconciliation | Resolve main/zen-gates split as a governed system baseline | [Blocked] depends on P186 | Canonical baseline is documented; production DB remains unchanged unless separately authorized; tests and drift guards agree on target state. |
| **P0.3** | Second-zone special-ball containment and score guard | Prevent below-random special-ball predictions from being promoted, scored, or over-displayed as an edge | [Confirmed] Baseline governance active | Second-zone is locked as display-only / metrics-only. It must not enter recommendation score, ranking, confidence, or candidate selection. |
| **P0.4** | Governance conflict handling | Resolve current conflict between "produce prompt" and "no new worker task prompt" | [Blocked] CTO cannot override | No new `active_task.md` or worker prompt is produced by CTO; CEO must explicitly authorize a later Planner/Worker task if desired. |
| **P1.1** | Post-migration quality gate | Prepare tests, drift guards, and skip-marker transition for the migrated 94924-row state | [Deferred] after P186 decision | DB-dependent tests that currently SKIP on main have a clear PASS path after migration; drift guard target is updated only after production migration. |
| **P1.2** | Replay UI/API disclosure | Surface `bet_index`, lifecycle, provenance, and special-ball confidence honestly | [Deferred] | UI/API do not imply second-zone predictive edge or native multi-bet coverage where evidence is missing. |
| **P1.3** | Migration operator guide | Convert P184/P185 rehearsal evidence into an operator checklist | [Deferred] | Backup, lock, SQL, validation, rollback, and "no broad staging" steps are explicit and auditable. |
| **P2.1** | Passive monitoring | Monitor POWER_LOTTO only under P178A reopen conditions | [Waiting] | Reopen only after >=500 new draws after 115000041, documented structural change, independent evidence, or explicit new governance design. |
| **P2.2** | Second-zone diagnostic-only audit | If CEO authorizes, evaluate special-ball concentration, random/frequency/recency baselines, and rolling stability | [Blocked] needs CEO auth and prompt restriction resolution | Read-only artifact; no strategy promotion; final classification limited to no-signal, weak-observation-only, candidate-needs-more-evidence, or blocked. |
| **P3** | Other lottery research | DAILY_539, BIG_LOTTO, 3_STAR, 4_STAR research | [Deferred] | Separate authorization; 4_STAR still provenance-gated. |
| **P4** | Long-term replay product backlog | UI polish, monitoring dashboards, operator reporting | [Deferred] | Does not consume P0/P1 migration or containment capacity. |
| **P5** | Optional scheduler / automation | Cron/launchd/automation setup | [Deferred] | Explicit OS-level authorization only. |
| **P6** | External reference review | Architecture notes only if useful | [Paused] | No clone/new repo. |
| **P7** | Worktree hygiene | Clean-up or archive dirty runtime/data files | [Deferred but risky] | Only with explicit cleanup authorization and file allowlist. |
| **P8** | Future OOS re-evaluation | Retest only after new data thresholds | [Waiting] | Pre-registered configs, no post-hoc threshold tuning. |
| **P9** | Product packaging | Release notes / operational docs | [Deferred] | After migration baseline is decided. |
| **P10** | Long-term cadence | Periodic governance review | [Deferred] | Low-cost checks without no-change PR churn. |

Upgrade / downgrade decisions:

| Item | Decision | Reason |
|---|---|---|
| P186 production migration authorization gate | Upgrade to P0 | Production migration is the clearest blocker to canonical data, test parity, and replay product maturity. |
| Second-zone containment | Upgrade to P0.3 | P161/P162 show special-ball prediction is below random; product must not present it as an edge. |
| Active POWER_LOTTO optimization | Retire / keep closed | P178A closes active research after 17 NULL outcomes. |
| More feature-engineering prototypes | Downgrade to P3+ / blocked | Further search increases false-positive risk without new structural evidence. |
| P123 trigger standby | Downgrade from active P0 to standing guard | Still useful, but not today's bottleneck. |
| P126/P127 direct replay applies | Retire as near-term path | Superseded by P184/P185 migration reconciliation path. |

---

## 5. Critical Blockers (2026-06-01 historical)

| Blocker | Impact | Why It Blocks | Risk If Ignored | Priority | Acceptance |
|---|---|---|---|---|---|
| Main/zen-gates baseline split | Data quality, tests, product truth | Main has 54462 rows and no `bet_index`; validated target has 94924 rows and `bet_index` | Research/UI/tests run against different universes and produce inconsistent conclusions | P0.1/P0.2 | P186 decides gate; no production write until backup, lock, SQL, validation, rollback, and exact phrase are approved. |
| Irreversible dedup policy | Production DB safety | P184/P185 validated dropping 160 no-provenance rows, but production deletion is still irreversible without backup | Accidental loss of production rows or inability to audit rollback | P0.1 | CEO explicitly approves `MAX(id)` dedup policy and immutable backup procedure. |
| Second-zone below-random evidence | Product correctness | P161/P162 + SZC1 show no stable edge above 0.125 baseline | Product may overstate weak or negative evidence as an optimization signal | P0.3 | Special-ball output is display-only/metrics-only and excluded from recommendation score/ranking/confidence/candidate selection unless future pre-registered walk-forward corrected-significant evidence beats 0.125. |
| POWER_LOTTO research closure vs new optimization request | Workflow governance | P178A closes active research; user attachment asks for a new P185 second-zone task, while P185 already exists as DB rehearsal | Duplicate task IDs, scope drift, and unauthorized research restart | P0.4/P2.2 | CEO decides whether to authorize a new diagnostic-only task with a non-conflicting ID and no production changes. |
| Dirty worktree and runtime/data files | Release safety | Existing modified/untracked DB/history/runtime files are outside CTO scope | Broad staging could commit runtime state or DB artifacts | P1/P7 | Any implementation task uses a strict allowlist and refuses broad staging. |
| Roadmap corruption / stale sections | Governance clarity | Prior roadmap mixed old priorities, appended new phases, and corrupted rows | Planner may choose outdated P0/P1 tasks | P1 | This roadmap becomes current source of truth; CTO-Analysis explains rewrite reason. |

---

## 6. Recommended System Optimization Directions (2026-06-01 historical)

### Direction A: Canonical Data Reconciliation And Migration Gate

- **Roadmap phase:** P0.1/P0.2
- **Why important:** The validated replay universe is 94924 rows with `bet_index`; production main is still 54462 rows without `bet_index`.
- **System maturity gain:** Creates one canonical dataset for replay UI, research, tests, and drift guards.
- **Expected benefit:** Eliminates split-brain evidence and lets DB-dependent tests move from SKIP to PASS after authorized migration.
- **Risk:** Production DB migration is irreversible without backup; dedup drops 160 no-provenance rows.
- **Acceptance:** P186 gate is complete before any production write; production migration only with exact CEO phrase and lock/backup.
- **Priority:** P0

### Direction B: Second-Zone Special-Ball Evidence Containment (Now Enforced)

- **Roadmap phase:** P0.3 (enforced), P2.2 (future evidence-gated only)
- **Why important:** Existing special-ball evidence is below random and active research is closed.
- **System maturity gain:** Prevents a weak signal from contaminating recommendation quality, UI confidence, or future planning.
- **Expected benefit:** Users see special-ball outputs as low-confidence display/metrics information without contaminating recommendation score.
- **Risk:** Pressure to "optimize" can become overfitting or false-positive hunting.
- **Acceptance:** No second-zone promotion/candidate/online basis, no production scoring contamination, and no optimization restart unless future evidence is pre-registered + walk-forward + corrected-significant above 0.125.
- **Priority:** P0/P1

### Direction C: Post-Migration Quality Gate And Test Parity

- **Roadmap phase:** P1.1
- **Why important:** P182 added tests that intentionally SKIP on stale main. After migration, those gates must become meaningful.
- **System maturity gain:** Converts artifact evidence into enforceable CI and regression gates.
- **Expected benefit:** Fewer hidden mismatches between docs, scripts, and DB reality.
- **Risk:** Updating guards before migration would encode a false production state.
- **Acceptance:** Drift guard, skip markers, DB-dependent contracts, and P161-P185 checks align with actual production state after migration only.
- **Priority:** P1

### Direction D: Roadmap And Task Namespace Governance

- **Roadmap phase:** P0.4/P1.3
- **Why important:** The project now has a P185 DB rehearsal and a user-supplied P185 second-zone prompt candidate.
- **System maturity gain:** Prevents task-ID collisions, stale active_task handoff, and unauthorized worker prompt generation.
- **Expected benefit:** Planner/Worker handoff becomes safer and less ambiguous.
- **Risk:** If ignored, the next worker may execute the wrong P185.
- **Acceptance:** CEO/Planner assigns a non-conflicting ID for any future second-zone diagnostic and updates active task under proper authorization.
- **Priority:** P1

### Direction E: Product Disclosure For Replay Evidence

- **Roadmap phase:** P1.2/P4
- **Why important:** Replay product value comes from honest visibility, not claimed predictive edge.
- **System maturity gain:** UI/API clearly separate main-number hits, special-ball hits, bet_index coverage, lifecycle, provenance, and NULL research outcomes.
- **Expected benefit:** Better operator trust and less risk of overclaiming lottery recommendations.
- **Risk:** Product copy may lag research conclusions.
- **Acceptance:** User-facing surfaces do not imply guaranteed improvement, wagering advice, or validated second-zone edge.
- **Priority:** P1/P2

---

## 7. Today's Recommended Focus (2026-06-01 historical)

**CTO recommendation:** Keep focus on **P186/P187/P188 migration governance chain** while preserving enforced second-zone containment (SZC1/SZC2 complete, display-only guard active).

Do not do today:

- Do not create a new repo.
- Do not write production DB.
- Do not copy zen-gates DB over main.
- Do not run controlled_apply.
- Do not restart POWER_LOTTO feature engineering.
- Do not promote or score second-zone strategies as predictive.
- Do not use second-zone as promotion/candidate/online basis.
- Do not restart second-zone optimization without pre-registered walk-forward corrected-significant evidence above 0.125.
- Do not create or update `00-Plan/roadmap/active_task.md` from CTO.
- Do not emit a new worker task prompt from CTO under the current conflicting instructions.

Final roadmap marker:

```text
CTO_ROADMAP_UPDATED_WITH_RISKS_20260601
```

---

## P186 — Production DB Migration Authorization Gate — COMPLETE (2026-06-01)

**Classification**: `P186_PRODUCTION_DB_MIGRATION_AUTHORIZATION_GATE_READY`

12-condition authorization gate. Plan-only — no migration executed.

| Item | Value |
|------|-------|
| Production DB rows | 54,462 (UNCHANGED) |
| Migration executed | **NO** |
| P187 exact phrase defined | YES |
| P187 | BLOCKED — CEO exact phrase required |
| P178A closure | ACTIVE |

```text
CTO_ROADMAP_UPDATED_AFTER_P186_AUTHORIZATION_GATE_20260601
```

---

## P187 — Production DB Migration Dry-Run Checklist — COMPLETE (2026-06-01)

**Classification**: `P187_PRODUCTION_DB_MIGRATION_DRY_RUN_CHECKLIST_READY`

13-item dry-run checklist for production migration. Plan-only — no DB write.

| Item | Value |
|------|-------|
| Production DB rows | 54,462 (UNCHANGED) |
| Migration executed | NO |
| Checklist items | 13 DRC + 12 SQL review + backup/rollback |
| P188 | BLOCKED — CEO exact destructive phrase required |

```text
CTO_ROADMAP_UPDATED_AFTER_P187_DRY_RUN_CHECKLIST_20260601
```

---

## P188 — Production DB Migration Execution — COMPLETE (2026-06-01)

**Classification**: `P188_PRODUCTION_DB_MIGRATION_EXECUTED_RECONCILED_94924`

Production DB migration executed. DB-level reconciliation complete.

| Item | Value |
|------|-------|
| Production DB rows | **94,924** (migrated from 54,462) |
| bet_index | **PRESENT** |
| Backup | `backups/p188_lottery_v2_backup_20260601_153821.db` |
| Integrity check | ok |
| DB-level split | **RECONCILED** |
| Code/docs/tests parity | Completed in P182 |
| Commit/push | **NOT YET** — awaiting P189 authorization |
| P189 | BLOCKED |

```text
CTO_ROADMAP_UPDATED_AFTER_P188_PRODUCTION_DB_MIGRATION_20260601
```

---

## P189 — Post-Migration Verification and Commit Readiness Audit — COMPLETE (2026-06-01)

**Classification**: `P189_POST_MIGRATION_VERIFICATION_COMMIT_READINESS_READY`

| Item | Status |
|------|--------|
| Production DB | 94,924 rows, bet_index PRESENT |
| Drift guard | UPDATED → PASS |
| Tests | 600 PASS, 0 FAIL, 0 SKIP |
| Stage/commit/push | NOT YET |
| P190 | BLOCKED |

```text
CTO_ROADMAP_UPDATED_AFTER_P189_POST_MIGRATION_VERIFICATION_20260601
```

---

## P190 — Commit Readiness and Staging Plan — COMPLETE (2026-06-01)

**Classification**: `P190_COMMIT_READINESS_AND_STAGING_PLAN_READY`

Post-migration commit readiness audit + staging whitelist plan produced. No stage/commit/push.

| Item | Value |
|------|-------|
| Production DB rows | **94,924** (bet_index PRESENT) |
| Phase 0 verification | ALL PASS |
| Tests (P178A-P189) | **644 PASS, 0 FAIL, 0 SKIP** |
| Drift guard | PASS |
| Staged / committed / pushed | **0 / 0 / 0** |
| Staging whitelist | 8 groups (A-H) documented |
| Forbidden staging policy | Documented (*.pid, runtime/, .gstack/, .fuse_hidden*, DB.bak_*) |
| Commit message draft | Ready |
| P191 options | 5 authorization options defined |
| Post-migration verification | **COMPLETE** |
| Stage/commit/push | **DEFERRED to P191** |
| POWER_LOTTO R2 research | **CLOSED** (P178A) |
| P191 | **BLOCKED — CEO authorization required** |

```text
CTO_ROADMAP_UPDATED_AFTER_P190_COMMIT_READINESS_STAGING_PLAN_20260601
```

---

## P191 — Stage Reviewed Files and Create Local Commit — COMPLETE (2026-06-01)

**Classification**: `P191_STAGE_REVIEWED_FILES_LOCAL_COMMIT_READY`

Reviewed whitelist (109 files) staged and local commit created. No push.

| Item | Value |
|------|-------|
| Production DB rows | **94,924** (bet_index PRESENT) |
| Files staged | 109 (0 forbidden) |
| Local commit | **CREATED** |
| Push | **NOT YET** — P192 BLOCKED |
| POWER_LOTTO R2 research | **CLOSED** (P178A) |
| P192 | **BLOCKED — CEO authorization required** |

```text
CTO_ROADMAP_UPDATED_AFTER_P191_STAGE_LOCAL_COMMIT_20260601
```

---

## P192 — Push to origin/main — REJECTED (2026-06-01)

**Classification**: `P192_PUSH_REJECTED`

Direct push to main rejected by GitHub branch protection.

| Item | Value |
|------|-------|
| Push result | **REJECTED** — GH006 branch protection, required check `replay-default-validation` |
| Large file | lottery_v2.db = 96MB; backup = 51MB (exceed 50MB recommendation) |
| Local commit | `012d4a3` INTACT |
| origin/main | UNCHANGED |
| Remote/main reconciliation | **NOT YET** |

```text
CTO_ROADMAP_UPDATED_AFTER_P192_PUSH_REJECTED_20260601
```

---

## P193 — Push Rejection Remediation Plan — COMPLETE (2026-06-01)

**Classification**: `P193_PUSH_REJECTION_REMEDIATION_PLAN_READY`

Remediation plan produced. No file modifications. CTO recommends Option B (remove DB binaries).

| Item | Value |
|------|-------|
| Options assessed | 5 (A-E) |
| CTO primary | **Option B — Remove DB binaries from commit** |
| Remote/main | **NOT YET** |
| POWER_LOTTO R2 research | **CLOSED** (P178A) |
| P194 | **BLOCKED — CEO authorization required** |

```text
CTO_ROADMAP_UPDATED_AFTER_P193_PUSH_REJECTION_REMEDIATION_PLAN_20260601
```

---

## P194 — Remove DB Binaries from Local Commit Plan — COMPLETE (2026-06-01)

**Classification**: `P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY`

Binary removal plan produced. No file modifications in P194.

| Item | Value |
|------|-------|
| P191 local commit | `012d4a3` INTACT — should NOT be pushed as-is |
| Large binary inventory | lottery_v2.db = 96MB, backup = 51MB |
| SHA256 evidence | `a5ac27a6...` (prod DB), `5eea5313...` (backup) |
| Recommended approach | Approach 1: soft reset + recommit + manifest + .gitignore |
| Binary removal strategy | PLANNED (not yet executed) |
| POWER_LOTTO R2 research | **CLOSED** (P178A) |
| P195 | **BLOCKED — CEO authorization required** |

```text
CTO_ROADMAP_UPDATED_AFTER_P194_REMOVE_DB_BINARIES_PLAN_20260601
```

---

## P195 — Remove DB Binaries Execution Plan — COMPLETE (2026-06-01)

**Classification**: `P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_READY`

9-step execution plan for P196 produced. Manifest design ready. No file modifications.

| Item | Value |
|------|-------|
| P194 plan | COMPLETE |
| P196 execution plan | READY — soft reset + recommit + manifest + .gitignore |
| DB SHA256 evidence | `a5ac27a6...` (prod), `5eea5313...` (backup) |
| Manifest path | `docs/db_migration_manifest_p188_p191.json` |
| Binary removal | PLANNED (not yet executed) |
| POWER_LOTTO R2 research | **CLOSED** (P178A) |
| P196 | **BLOCKED — CEO authorization required** |

```text
CTO_ROADMAP_UPDATED_AFTER_P195_REMOVE_DB_BINARIES_EXECUTION_PLAN_20260601
```

---

## P196 — Remove DB Binaries: Soft Reset and Recommit — COMPLETE (2026-06-01)

**Classification**: `P196_REMOVE_DB_BINARIES_RECOMMIT_NON_BINARY_READY`

Binary-heavy P191 commit replaced with non-binary recommit. Local DB and backup preserved.

| Item | Value |
|------|-------|
| Binary-heavy P191 commit | **REPLACED** by non-binary local commit |
| DB binary in new commit | **NONE** |
| Production DB (local) | 94924 rows, 96MB — **LOCAL ONLY** |
| Backup DB (local) | 54462 rows, 51MB — **LOCAL ONLY** |
| Push | **NOT YET** |
| POWER_LOTTO R2 research | **CLOSED** (P178A) |
| P197 | **BLOCKED — CEO authorization required** |

```text
CTO_ROADMAP_UPDATED_AFTER_P196_REMOVE_DB_BINARIES_RECOMMIT_20260601
```
