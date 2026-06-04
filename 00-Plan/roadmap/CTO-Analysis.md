# CTO Analysis - Roadmap Alignment And System Optimization Direction

## 2026-06-04 CTO Statistical Methods Adoption Analysis

Final Classification: `CTO_STATISTICAL_METHODS_ADOPTION_WITH_RISKS`

### CEO Follow-Up Note (2026-06-04 — P234A governance follow-up)

CEO verdict: **`CEO_DECISION_PARTIALLY_APPROVED`** (PR #279 pending merge).

- **ADOPTED:** The read-only diagnostics-only framing. No predictability claim, no promotion, mandatory correction/OOS. The 8-method inventory and gap analysis are accurate.
- **REJECTED/DEMOTED:** The **P0.5 "build now" urgency**. 7/8 methods already exist and are already enforced: P221F gate (multiple-testing correction, pre-registered windows), Bonferroni/BH-FDR in P222/P223B/P227C, rolling windows in RSM/P114/P224. The only genuinely new work — consolidation + a feature-bottleneck report schema — has **no current consumer** until a future authorized research run needs it. Demoted to **P2 design-only**.
- **NAMESPACE FIX:** P234 = CTO statistical-methods adoption analysis (this document). Any Lofea feasibility review must be **P235A**, not P234/P234A.
- **IMPLEMENTATION BOUNDARY:** No build authorized. Any implementation step requires separate explicit user authorization. Options authorized on-request only: OPT-B P235A Lofea read-only feasibility review, OPT-C P234 statistical-methods diagnostics inventory (design-doc only).

### 0. Input Sources And Scope

- [Confirmed] Required roadmap source read: `00-Plan/roadmap/roadmap.md`.
- [Confirmed] User-requested `ai_workflow/current_state.md` does not exist in this repo. Closest current-state SSOT is `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`, which was read instead.
- [Confirmed] Current state source read: `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`.
- [Confirmed] Handoff attachment read: `/Users/kelvin/.codex/attachments/415c49a6-38b7-47bf-9789-b7fb1d4cdd30/pasted-text.txt`.
- [Confirmed] Replay / validation / diagnostics / registry sources reviewed include `lottery_api/models/replay_strategy_registry.py`, `scripts/p232a_all_catalog_strategy_replay_scoreboard.py`, `outputs/research/p221_cross_lottery_feature_discovery_protocol_20260603.md`, `outputs/research/p222_cross_lottery_feature_discovery_scan_20260603.md`, `outputs/research/p223b_candidate_oos_cross_year_validation_20260603.md`, `outputs/research/p224_daily539_midfreq_fourier_2bet_deeper_validation_20260603.md`, `scripts/p227c_star_box_play_dryrun_scan.py`, `outputs/research/p227c_star_box_play_dryrun_scan_20260603.md`, `scripts/p230b1_daily539_backward_oos_dryrun.py`, `scripts/p231b_powerlotto_first_zone_backward_oos_dryrun.py`, `scripts/p51_powerlotto_wave4_rolling_window_mcnemar_gate.py`, `scripts/p114_temporal_stability_audit.py`, `scripts/special3_oos_permutation_review.py`, `scripts/special3_baseline_dryrun.py`, `tools/baseline_validator.py`, `lottery_api/engine/rolling_strategy_monitor.py`, `lottery_api/models/feature_analyzer.py`, `lottery_api/models/feature_importance.py`, `lottery_api/feature_importance_analyzer.py`, official draw ingestion dry-runs, and P226/P232/P233 reports.
- [Confirmed] Current repo and branch check at review time: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`, branch `main`, HEAD equals `origin/main` (`6cf2e1ac1b65e59b8691b45df9b8efc241c9deaa`).
- [Confirmed] Worktree is dirty outside CTO scope before this update. CTO touched only `00-Plan/roadmap/roadmap.md` and `00-Plan/roadmap/CTO-Analysis.md`.
- [Confirmed] This is analysis and roadmap documentation only. No DB write, production write, executable registry change, active-task update, strategy creation, or hypothesis creation was performed.
- [Unknown] Full test suite was not rerun for this doc-only analysis.

### 1. CTO Method Adoption Summary

[Confirmed] The project already has a mature replay / governance spine: causal replay adapters, read-only scoreboards, lifecycle registry labels, non-executable stubs, strict DB baselines, and recent P221F/P222/P223B/P224/P227C/P230B1/P231B validation artifacts that treat NULL as success.

[Confirmed] Most of the eight open-source-style statistical methods already exist somewhere, but they are split across one-off scripts, reports, legacy research files, and production-adjacent monitoring code. They are not yet a single reusable `Scientific Statistical Diagnostics Layer`.

[Inferred] The highest-value adoption path is to consolidate these methods as read-only diagnostics that explain false positives, no-edge outcomes, underpowered scans, and feature bottlenecks. The layer should not create new strategies or imply lottery predictability.

[Confirmed] Roadmap should be adjusted. A new P0.5 direction, `Scientific Statistical Diagnostics Layer`, was added to `roadmap.md` as recommended / not implemented.

### 2. Eight-Method Evaluation Table

| # | Method | Current System State | System Maturity Value | Replay / Validation Help | Lowers False Positive? | Explains No-Edge / Failed Strategy? | Roadmap? | Priority |
|---:|---|---|---|---|---|---|---|---|
| 1 | historical draw parser | [Partial] Official draw ingestion dry-runs exist for BIG_LOTTO / DAILY_539 / POWER_LOTTO; controlled import has authorization gates. P226 confirms 3_STAR / 4_STAR positional order is lost in current DB. | High for data integrity and source provenance. | Prevents replay against malformed, duplicated, or position-destroyed draw data. | Indirectly yes, by preventing invalid baselines and leakage. | Yes, especially for blocked star straight-play and date-format inconsistencies. | Yes, as inventory/parser audit only. | P1 |
| 2 | number frequency / position frequency | [Partial] Frequency features exist in strategy code, P221F feature families, P222 draw-side structural summary, P227C digit frequency, and Special3 position-frequency dry-runs. Position frequency is blocked for 3_STAR / 4_STAR straight-play because DB stores sorted arrays. | Medium; useful descriptive inventory, dangerous if promoted as signal. | Helps inspect feature coverage and lottery-specific data feasibility. | Only with correction/OOS; otherwise it increases false positives. | Yes, can show frequency features are baseline-like or underpowered. | Yes, diagnostics-only. | P2 |
| 3 | rolling window statistics | [Confirmed/Partial] P221F fixed windows, P222 tail checks, P224 tail/block stability, P230B1/P231B block splits, P114 temporal audit, and RSM 30/100/300 exist. Windows and labels vary. | Very high; rolling behavior is central to anti-overfit review. | Separates transient windows from stable OOS behavior. | Yes, when windows are pre-registered. | Yes, shows unstable blocks, weak tails, era failures. | Yes, centralize under diagnostics layer. | P0 |
| 4 | null simulation / random baseline | [Confirmed/Partial] P232A baselines, P222 random/uniform/all-history comparisons, P227C binomial baselines, Special3 Monte Carlo/binomial, and `tools/baseline_validator.py` exist. Some older baseline formulas/names are inconsistent. | Very high; every replay metric needs a lottery-specific null. | Makes strategy metrics comparable to expected random outcomes. | Yes, essential. | Yes, supports `NULL_OR_BASELINE_LIKE`, `UNDERPOWERED_NO_SIGNAL`, and below-baseline decisions. | Yes, P0. | P0 |
| 5 | permutation test | [Partial] P51 bootstrap/permutation, Special3 analytical binomial "permutation" review, rejected archives, and older research artifacts use this idea. Not centralized and naming is inconsistent. | High for non-parametric sanity checks and distribution-free stress tests. | Useful for feature scans and paired comparisons when analytical assumptions are weak. | Yes, if pre-registered and corrected. | Yes, can distinguish weak observations from random-like behavior. | Yes, but after baseline/correction SSOT. | P1 |
| 6 | multiple testing correction | [Confirmed/Partial] P222/P223B/P227C explicitly use Bonferroni and/or BH-FDR; P221F requires correction. Older scripts and ad-hoc research are inconsistent. | Critical; project scans many strategies/windows/features. | Prevents broad scans from promoting noise. | Yes, directly. | Yes, explains why raw p-values fail after family correction. | Yes, mandatory P0 gate. | P0 |
| 7 | signal stability diagnostics | [Confirmed/Partial] P224/P230B1/P231B block/year/era/robustness checks, P114 temporal stability labels, P227C power gate, and RSM trend classifier exist. Schema and terminology vary. | Very high; stability is the bridge between statistical result and governance decision. | Identifies fragile edges, hit-count concentration, era dependence, and underpowered observations. | Yes, by requiring consistency beyond one lucky segment. | Yes, this is the best explanation layer for failed strategies. | Yes, P0/P1. | P0 |
| 8 | feature bottleneck report | [Missing/Partial] P226 replay-gap discovery, P232A scoreboard, P233A/B registry hygiene, and P221F inventories behave like bottleneck reports, but no unified report exists. | High for CTO/Planner decisions; prevents running analyses that data cannot support. | Shows missing replay rows, no parser support, blocked positional data, insufficient power, and lifecycle mismatch before validation. | Indirectly yes, by blocking invalid scans. | Yes, especially for no-data/no-replay/underpowered outcomes. | Yes, as read-only report. | P1 |

### 3. Existing System Gap Analysis

#### Already Exists

- [Confirmed] Causal replay adapters with strict prior-history rule in `replay_strategy_registry.py`.
- [Confirmed] Lifecycle registry and non-executable stubs; `LIFECYCLE_UNRESOLVED` is now 0 after P233B.
- [Confirmed] All-catalog historical replay scoreboard (P232A) with row/draw/bet-index metrics, random baselines, and historical-only caveats.
- [Confirmed] P221F anti-overfit protocol: frozen windows, fixed universe, predeclared baselines, unit labels, zero-row inclusion, no post-hoc window selection.
- [Confirmed] P222/P223B/P224/P227C/P230B1/P231B provide corrected p-values, OOS/tail/block checks, robustness checks, power warnings, and NULL classifications.
- [Confirmed] Official draw ingestion dry-runs and controlled import gates exist for key lottery types.

#### Partially Exists But Incomplete

- [Partial] Historical parser is not a unified parser layer; 3_STAR / 4_STAR straight-play is blocked by sorted storage and positional loss.
- [Partial] Frequency/position-frequency diagnostics exist, but are scattered and not separated cleanly from older strategy / retrospective code.
- [Partial] Rolling windows exist in several forms: P221F uses 100/125/150 and 500/750/1000; RSM uses 30/100/300; P51 uses W150/W500/W1500; P114 uses thirds plus rolling_100/250.
- [Partial] Random/null baselines are repeated in many scripts rather than centralized; P51 contains comments showing historical confusion around POWER_LOTTO baseline semantics.
- [Partial] Permutation / binomial / bootstrap tests exist but naming differs and not all reports expose method assumptions consistently.
- [Partial] Stability diagnostics exist, but labels differ (`MIXED`, `WATCHLIST`, `UNDERPOWERED_NO_SIGNAL`, `HISTORICAL_ARTIFACT_DIRECTION`, etc.) and are not one schema.

#### Completely Missing

- [Confirmed] No reusable `Scientific Statistical Diagnostics Layer` module/report schema exists yet.
- [Confirmed] No unified feature bottleneck report that joins parser readiness, replay coverage, feature availability, statistical power, registry lifecycle, and validation gates.
- [Inferred] No single multiple-testing ledger records family size across strategy × lottery × window × feature scans outside each individual artifact.
- [Inferred] No single diagnostics-only API contract that downstream validation/report/dashboard code can consume without touching production or registry.

#### Existing But Inconsistent

- [Confirmed] Naming mixes `diagnostic`, `validation`, `dry-run`, `scoreboard`, `promotion gate`, `monitor`, and `recommendation`.
- [Confirmed] Units are sometimes row-level, draw-level, bet-index-level, strategy-level, or special-zone; newer reports label them, older code may not.
- [Confirmed] `RollingStrategyMonitor` writes `data/rolling_monitor_*.json` and has recommendation-oriented language, which does not match the current read-only governance layer.
- [Confirmed] `feature_discovery_and_retrospective.py` is retrospective single-draw feature discovery and should be treated as historical research / anti-pattern evidence, not a source of new hypotheses.
- [Confirmed] Special-zone metrics are now display-only in governance, but older code and reports require continued containment checks.

### 4. P0 / P1 / P2 / P3+ Priority Ordering

| Priority | Methods / Work | Rationale |
|---|---|---|
| P0 | multiple testing correction; null/random baseline SSOT; rolling-window/statistical unit labels; signal stability diagnostics | These are already active correctness gates and directly prevent false positives. |
| P1 | historical draw parser inventory; permutation/binomial test API; feature bottleneck report | Needed to make diagnostics reusable and explain blocked/no-edge outcomes before any validation run. |
| P2 | number frequency / position frequency summaries; descriptive feature inventory; dashboard-ready historical summaries | Useful for visibility, but high risk if interpreted as predictive signal. Keep diagnostics-only. |
| P3+ | report/dashboard UI and strategy governance integration | Should wait until the diagnostics schema is stable. Governance integration should block or label only, not promote. |

### 5. Roadmap Adjustment Decision

[Confirmed] Roadmap requires adjustment. `Scientific Statistical Diagnostics Layer` should be added because the project already uses scientific methods but lacks a unified read-only layer.

[Confirmed] Applied roadmap update:

- Added P234 row in §0.1 with final classification `CTO_STATISTICAL_METHODS_ADOPTION_WITH_RISKS`.
- Added P0.5 `Scientific Statistical Diagnostics Layer` in §0.4.
- Added §0.6 Direction F describing scope, boundary, required gates, and priority.
- Added P234 note in §0.7 current state summary.

[Confirmed] No roadmap update authorizes implementation, worker prompt generation, DB write, production write, executable registry write, strategy promotion, or new strategy/hypothesis creation.

### 6. Recommended Phased Adoption Sequence

| Phase | Name | Scope | Allowed Outputs | Explicitly Forbidden |
|---|---|---|---|---|
| Phase 0 | read-only inventory | Inventory existing parsers, baselines, windows, correction methods, stability labels, feature availability, replay coverage, and lifecycle coverage. | `outputs/research/*` inventory artifact and docs only. | New hypotheses, strategy code, DB/registry/production writes. |
| Phase 1 | diagnostics-only | Centralize baseline calculations, correction methods, rolling windows, stability summaries, and bottleneck report schema. | Read-only diagnostic JSON/MD artifacts. | Any recommendation ranking or claim of improved win rate. |
| Phase 2 | validation framework integration | Let replay validation consume diagnostics as gates: corrected p, OOS/walk-forward, power status, stability, unit labels. | Validation artifacts and tests for schema/gates. | Promotion from diagnostics alone; registry mutation. |
| Phase 3 | report / dashboard | Display historical-only diagnostics, no-edge explanations, underpowered warnings, and parser/replay coverage. | UI/report surfaces labeled historical-only. | Betting advice, deployability rankings, second-zone promotion. |
| Phase 4 | strategy governance integration | Use diagnostics to block unsafe promotion, quarantine stale claims, or require more OOS. | Governance labels only with explicit authorization. | Automatic ONLINE promotion or executable adapter creation. |

### 7. Risks And Guardrails

| Risk | Assessment | Guardrail |
|---|---|---|
| System may imply random lottery numbers are predictable | [Confirmed] High risk if frequency/rolling windows are surfaced casually. | Every artifact says historical-only, not betting advice, not future edge proof, not win-rate improvement. |
| Data snooping / p-hacking | [Confirmed] High risk because project scans strategies × lotteries × windows × features. | Pre-register universe, windows, baselines, family size, metric units, and acceptance taxonomy before scanning. |
| Multiple testing omitted | [Confirmed] Must be required for any scan with more than one feature/window/strategy. | Bonferroni as strict gate; BH-FDR only exploratory unless pre-authorized. |
| OOS / walk-forward omitted | [Confirmed] Must be required before any validation-framework integration. | Backward-OOS may falsify but not confirm deployment; future OOS preferred. |
| Production / registry / DB impact | [Inferred] Low if isolated; high if wired to RSM/recommendation. | Diagnostics layer must be read-only, artifact-only, and cannot call executable promotion paths. |
| Scope expansion | [Confirmed] High if "feature discovery" becomes strategy research. | No new hypotheses/strategies in P234 adoption. Feature bottleneck reports describe constraints only. |
| Legacy naming confusion | [Confirmed] Existing names like "promotion gate" and "recommendation" can conflict with current governance. | Normalize diagnostics labels and separate old research from current governance artifacts. |
| Star-lottery positional semantics | [Confirmed] Straight-play blocked until re-ingestion. | Parser/bottleneck report must mark positional features blocked and avoid set-intersection scoring for straight-play. |

### 8. CTO Final Recommendation

Adopt the eight open-source-style statistical methods only as a **Scientific Statistical Diagnostics Layer**, not as a strategy engine. The layer is valuable because it can make the current no-edge reality more explainable, reduce false-positive promotion risk, and expose parser/replay/feature bottlenecks before costly validation work starts.

The first adoption unit should be Phase 0 inventory plus Phase 1 diagnostics-only design. Do not start implementation from this analysis alone; do not create a worker prompt here; do not write DB, production, executable registry, or recommendation logic; do not introduce new hypotheses or strategies; do not claim improved lottery win rate.

Final Classification: `CTO_STATISTICAL_METHODS_ADOPTION_WITH_RISKS`

---

## 1. CTO Review Date

2026-06-02 Asia/Taipei.

Final CTO classification target: `CTO_ROADMAP_UPDATED_WITH_RISKS`.

## 2. Input Sources

- [Confirmed] Current roadmap before this update: `00-Plan/roadmap/roadmap.md`.
- [Confirmed] Current CTO analysis before this update: `00-Plan/roadmap/CTO-Analysis.md`.
- [Confirmed] Read-only CEO / active-task context: `00-Plan/roadmap/CEO-Decision.md`, `00-Plan/roadmap/active_task.md`.
- [Confirmed] User handoff attachment: `/Users/kelvin/.codex/attachments/51fdb507-325c-4600-8bdf-ecbe6a71ab06/pasted-text.txt`.
- [Confirmed] Current repo / git checks as of 2026-06-02 CTO review: repo `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`, branch `main`, HEAD at that review = `061bdc19c0a59e6948e8335b888257a1f7c521f6` (immutable historical snapshot; not current HEAD — verify current HEAD with `git rev-parse HEAD`).
- [Confirmed] Current SQLite checks on `lottery_api/data/lottery_v2.db`: integrity `ok`, `strategy_prediction_replays` rows 94,924, `bet_index` present, 0 duplicate replay keys, POWER_LOTTO rows 36,104.
- [Confirmed] Current archive evidence: `/Users/kelvin/Kelvin-WorkSpace/_archive/lottery_stale_repos_20260602_162329/README_DO_NOT_USE.md`.
- [Confirmed] Current git log evidence: PR #249 merge `061bdc1`; P203 `d119ea6`; P200 `4a36b12`; P193-P198 `41449fb`; P188-P196 `a3e30ae`.
- [Confirmed] Existing research/governance artifacts under `outputs/research/power_lotto/`, including P178A closure, P188 migration, P189 verification, P196 DB binary manifest.
- [Confirmed] Git status was dirty before CTO edits and includes files outside CTO scope. CTO touched only allowed roadmap files.
- [Unknown] A formal 2026-06-02 CEO final decision for the user’s new P210 short/mid-window direction is not present in the allowed sources.
- [Unknown] CTO did not rerun the full test suite in this analysis-only review; latest known test counts are from the handoff.

## 3. Roadmap Alignment Assessment

| Item | Classification | Assessment |
|---|---|---|
| P188 production DB migration and P189-P205 PR chain | [Aligned] | This resolves the prior P0 main/zen-gates split and DB-binary/branch-protection risks. |
| P206-P209 canonical repo/archive cleanup | [Aligned] | Directly supports the no-new-repo policy and reduces agent dispatch mistakes. |
| Roadmap still treating P186/P187/P188 as blockers | [Outdated] | Current local main is 94,924 rows with `bet_index`; those blockers are historical. |
| P178A POWER_LOTTO R2 closure | [Aligned] | Old R2 candidate reruns remain retired; new work must be a fresh protocol. |
| User’s short/mid-window direction | [Missing] | Roadmap lacked a governed P210 phase for 10-50 and 100-300 draw windows. |
| Long-term frequency as primary filter | [Drift] | Latest user direction demotes long-term/full-period frequency to reference information only. |
| Worker prompt output request | [Blocked] | CTO is simultaneously asked to output a worker prompt and forbidden from producing one or writing `active_task.md`. |

## 4. Completed Work Assessment

### Reconciliation / DB / PR Chain

- [Confirmed] P188 production DB migration was executed and current local DB has 94,924 rows, `bet_index` present, and 0 duplicate replay keys.
- [Confirmed] P189 post-migration verification and drift-guard transition were reported complete.
- [Confirmed] P196 removed DB binaries from pushable history and preserved DB evidence via manifest; `git ls-files` confirms the DB binary itself is not tracked.
- [Confirmed] P200 repaired stale HEAD-only commit tests.
- [Confirmed] P203 refreshed randomness audit cadence.
- [Confirmed] P205 merged PR #249 into `main`; local HEAD is the PR #249 merge commit.

### Repo Governance / Dispatch Chain

- [Confirmed] Handoff reports P206 local main sync and P207 branch cleanup decision complete.
- [Confirmed] `Lottery/` and `LotteryNew-clean/` are archived under `_archive/lottery_stale_repos_20260602_162329/` with `README_DO_NOT_USE.md`.
- [Confirmed] Root `/Users/kelvin/Kelvin-WorkSpace/Lottery*` listing shows only `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`.

### Research / Evidence Chain

- [Confirmed] P161-P178A POWER_LOTTO R1/R2 research remains NULL/closed; no active old-candidate optimization is authorized.
- [Confirmed] Second-zone evidence remains no-signal / below random in prior evidence and containment decisions.
- [Confirmed] Latest user direction is not to use long-term frequency as a primary filter; it should become reference/observation only.

### Test / Verification Status From Sources

- [Confirmed] Handoff reports P200 full suite: 1074 passed, 0 failed, 0 skipped.
- [Confirmed] Handoff reports P203: 1097 passed, 0 failed.
- [Confirmed] Handoff reports P204 PR CI green: default SUCCESS, browser SUCCESS, dedicated-db SKIPPED acceptable.
- [Confirmed] Handoff reports P206/P207: 1097 passed, 0 failed.
- [Unknown] CTO did not rerun tests in this review; no new test result is claimed.

## 5. Unfinished Work Assessment

- [Missing] P210 short/mid-window strategy protocol: no frozen windows, lottery scope, metric hierarchy, holdout plan, or acceptance taxonomy yet.
- [Blocked] First executable worker prompt: current instructions forbid CTO from generating a worker prompt and writing `active_task.md`; no 2026-06-02 CEO final decision for P210 is present.
- [Missing] Anti-overfit gate for short-window research: multiple-testing correction, CI, and walk-forward/OOS gates must be defined before implementation.
- [Missing] Long-term frequency governance: full-period frequency must be explicitly demoted to reference-only in future protocols.
- [Deferred] Product disclosure: UI/API/report wording still needs to remain aligned with NULL/no-signal evidence and no wagering advice.
- [Deferred] Archive deletion decision: archive should remain unless explicit destructive authorization is provided.
- [Deferred] Dirty worktree cleanup: outside CTO scope and requires a file allowlist.

## 6. P0 / P1 / P2 / P3-P10 Reprioritization

| Priority | Work | Status | Rationale |
|---|---|---|---|
| **P0.1** | P210 short/mid-window protocol governance | [Blocked] | This is the next correctness gate before any new strategy work. |
| **P0.2** | Anti-overfit validation gate | [Missing] | 10-50 draw windows are noisy; false positives are the main system risk. |
| **P0.3** | Canonical repo / DB execution guard | [Confirmed] baseline; [Missing] future task guard | Archive/worktree dispatch errors previously caused STOP and can invalidate results. |
| **P0.4** | CTO/CEO task-generation boundary | [Blocked] | The current prompt conflicts with itself; CTO cannot emit the worker task. |
| **P1.1** | Read-only short/mid-window diagnostic execution | [Deferred] | Valuable only after P210 protocol is approved. |
| **P1.2** | Product disclosure and second-zone containment | [Deferred] | Protects product trust and avoids implying lottery edge. |
| **P1.3** | Post-merge quality gate maintenance | [Confirmed] baseline; [Deferred] | Keep tests, DB manifest, and drift assumptions synchronized. |
| **P2.1** | Passive POWER_LOTTO monitoring | [Waiting] | Reopen only under P178A conditions or new governance. |
| **P2.2** | Archive retention / cleanup decision | [Deferred] | Keep archive unless destructive deletion is explicitly approved. |
| **P3-P10** | Other lottery research, scheduler, external review, packaging, cadence | [Deferred] | Maintain continuity but do not consume P0/P1 capacity. |

Upgrade / downgrade decisions:

- [Confirmed] Short/mid-window protocol is upgraded to P0 because the user’s new direction cannot safely proceed without frozen validation.
- [Confirmed] Anti-overfit validation is upgraded to P0 because short windows can easily generate false positives.
- [Confirmed] P186/P187/P188 migration blockers are downgraded to historical complete because current local DB is reconciled.
- [Confirmed] Long-term/full-period frequency is downgraded from potential filter to reference-only observation.
- [Confirmed] Active POWER_LOTTO R2 optimization and second-zone optimization remain retired/contained unless a new pre-registered protocol is approved.
- [Inferred] P206-P209 repo/archive guardrails should remain high priority even though cleanup itself is complete.

## 7. Critical Blockers

### Blocker 1: P210 Protocol Undefined

- **Impact scope:** strategy correctness, research reproducibility, product value.
- **Why blocker:** The new direction names short/mid windows, but does not yet freeze exact windows, lottery scope, metrics, baselines, or evidence thresholds.
- **Risk if ignored:** A worker can tune windows after seeing results and create false signal.
- **Recommended priority:** P0.1.
- **Acceptance criteria:** Plan-only protocol defines 10-50 and 100-300 window sets, scope, baselines, OOS/walk-forward design, multiple-testing correction, CI, NULL taxonomy, and no production writes.

### Blocker 2: Short-Window Overfit Risk

- **Impact scope:** correctness, trust, future strategy promotion.
- **Why blocker:** Short windows have small sample sizes; testing many windows/strategies without correction makes false positives likely.
- **Risk if ignored:** Recent-noise patterns become "optimized" recommendations.
- **Recommended priority:** P0.2.
- **Acceptance criteria:** Every future result compares against random, simple-frequency, and best-single-strategy baselines with corrected significance and confidence intervals.

### Blocker 3: Task Prompt Governance Conflict

- **Impact scope:** agent/workflow orchestration.
- **Why blocker:** The request asks CTO to output a worker prompt but also forbids CTO from producing a new worker task prompt and limits writes to two files.
- **Risk if ignored:** CTO violates governance or creates an unauthorized `active_task.md`.
- **Recommended priority:** P0.4.
- **Acceptance criteria:** CEO/Planner explicitly authorizes or produces the next task prompt; CTO does not write `active_task.md`.

### Blocker 4: Wrong Repo / Worktree Dispatch

- **Impact scope:** reproducibility, DB correctness, operational safety.
- **Why blocker:** Archived stale repos and `.claude/worktrees/*` still exist and can carry incompatible DB/code states.
- **Risk if ignored:** Future evidence can be generated from stale data and look valid.
- **Recommended priority:** P0.3.
- **Acceptance criteria:** Future tasks STOP unless repo is `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`, branch is `main`, DB rows are 94,924, `bet_index` is present, duplicate keys are 0, and path is not archive/worktree.

### Blocker 5: Product Evidence Disclosure Gap

- **Impact scope:** product maturity and user trust.
- **Why blocker:** Lottery outputs can be misread as betting advice or a validated edge, especially with second-zone fields.
- **Risk if ignored:** Product overclaims historical replay evidence.
- **Recommended priority:** P1.2.
- **Acceptance criteria:** Reports/UI/API clearly label historical evidence, NULL results, second-zone display-only status, and no wagering advice.

## 8. Recommended System Optimization Directions

### 1. Short/Mid-Window Strategy Protocol Governance

- **Corresponding roadmap phase:** P0.1 / P210.
- **Why important:** It turns the latest user intuition into a safe, testable research design before implementation.
- **System maturity gain:** Prevents ad-hoc research from becoming unverified product claims.
- **Expected benefit:** A stable protocol for 10-50 and 100-300 draw windows that can produce credible positive or NULL results.
- **Risk:** Window choice can become post-hoc tuning if not frozen.
- **Acceptance:** Plan-only artifact; no code/data/production writes; windows, metrics, baselines, OOS/walk-forward, correction, and final classification taxonomy documented.
- **Suggested priority:** P0.

### 2. Anti-Overfit Validation And Quality Gate

- **Corresponding roadmap phase:** P0.2 / P1.1.
- **Why important:** Short windows can look powerful while being statistical noise.
- **System maturity gain:** Makes future strategy claims falsifiable and comparable.
- **Expected benefit:** Protects the system from false-positive promotion and gives Planner/Worker a reusable gate.
- **Risk:** Slower iteration and fewer promoted candidates.
- **Acceptance:** Corrected significance, CI, random/simple/best-single baselines, draw-level OOS, and NULL-is-valid classification are mandatory.
- **Suggested priority:** P0.

### 3. Canonical Repo / DB Execution Integrity

- **Corresponding roadmap phase:** P0.3.
- **Why important:** The project just resolved stale repo sprawl; future work must not regress.
- **System maturity gain:** Makes every result traceable to the same DB and branch baseline.
- **Expected benefit:** Fewer STOPs, fewer invalid reports, safer staging.
- **Risk:** Guard exceptions may be needed for read-only historical comparison, but must be explicit.
- **Acceptance:** Worker reports verify repo/branch/HEAD/DB rows/`bet_index`/duplicates and reject archive/worktree paths.
- **Suggested priority:** P0/P1.

### 4. Evidence Disclosure And Recommendation Containment

- **Corresponding roadmap phase:** P1.2.
- **Why important:** Replay/product evidence must not be mistaken for guaranteed prediction or betting guidance.
- **System maturity gain:** Keeps product semantics aligned with research truth.
- **Expected benefit:** Higher trust and safer user interpretation.
- **Risk:** UI/API language can lag behind research conclusions.
- **Acceptance:** Main-number, second-zone, lifecycle, provenance, confidence, and NULL/no-signal states are labeled honestly.
- **Suggested priority:** P1.

### 5. Roadmap / Task Namespace Governance

- **Corresponding roadmap phase:** P0.4 / P1.3.
- **Why important:** Prior P-number collisions and active-task write races created execution ambiguity.
- **System maturity gain:** Keeps CTO/CEO/Planner/Worker boundaries clear.
- **Expected benefit:** Less wrong-task execution and less unauthorized prompt generation.
- **Risk:** Current request remains contradictory until CEO/Planner resolves it.
- **Acceptance:** Next task prompt is created only by CEO/Planner authorization; CTO records recommendations only.
- **Suggested priority:** P1.

## 9. Roadmap Changes Applied

- [Confirmed] Updated `00-Plan/roadmap/roadmap.md` Last Updated to 2026-06-02 Asia/Taipei.
- [Confirmed] Added `## 0. Current Roadmap Override — 2026-06-02` so old 2026-06-01 sections remain historical but no longer control current priorities.
- [Confirmed] Marked P188-P205 as complete/aligned and P186/P187/P188 blockers as outdated.
- [Confirmed] Marked P206-P209 repo/archive cleanup as complete/aligned.
- [Confirmed] Added P210 short/mid-window protocol governance as current P0.
- [Confirmed] Added anti-overfit validation and canonical repo dispatch guard as P0.
- [Confirmed] Downgraded long-term/full-period frequency to reference-only and retired old R2/second-zone optimization as active goals.
- [Confirmed] Documented the worker-prompt / `active_task.md` conflict and did not write `active_task.md`.
- [Confirmed] CTO modified only `00-Plan/roadmap/roadmap.md` and `00-Plan/roadmap/CTO-Analysis.md`.

## 10. Risks / Unknowns

- [Unknown] No formal 2026-06-02 CEO final decision for P210 exists in the checked files.
- [Unknown] CTO did not rerun the full test suite; latest pass counts are from the handoff report.
- [Unknown] Exact P210 scope is not frozen: all lotteries vs POWER_LOTTO vs second-zone-specific remains undecided.
- [Unknown] Exact short/mid windows are not frozen beyond the user's approximate 10-50 and 100-300 ranges.
- [Confirmed] Current worktree is dirty outside CTO scope; broad staging remains unsafe.
- [Confirmed] Archived stale repos exist and must not be used for dispatch.
- [Confirmed] Production DB binary is intentionally local/untracked; reproducibility relies on manifests and validation checks, not git-tracked DB files.
- [Inferred] The highest next maturity gain is protocol + validation governance, not immediate code implementation.

## 11. CTO Final Recommendation

Proceed with **P210 short/mid-window strategy protocol design only** as the next system direction, pending CEO/Planner authorization. The protocol must be plan-only: no code implementation, no production DB write, no registry/data write, no controlled_apply, no strategy promotion, no betting advice, and no new repo.

The protocol should explicitly encode the user's latest rule: long-term/full-period frequency distribution is reference/observation only, not a primary filter. Primary evidence should focus on pre-registered short windows (about 10-50 draws) and mid windows (about 100-300 draws), tested with walk-forward/OOS, corrected significance, confidence intervals, and simple/random/best-single baselines.

**First executable task prompt status:** [Blocked]. CTO does not emit a worker prompt and does not write `00-Plan/roadmap/active_task.md` because this same request forbids CTO from producing a new worker task prompt and limits CTO writes to two files. A CEO/Planner decision is needed to create the next executable prompt.

## 12. CTO Summary In 5 Lines

1. [Confirmed] Migration and PR #249 are complete; current local main DB is 94,924 rows with `bet_index`.
2. [Confirmed] Stale repos are archived; only `LotteryNew/main` should be used for future dispatch.
3. [Missing] The new short/mid-window strategy direction needs a plan-only P210 protocol before implementation.
4. [Blocked] CTO cannot emit today’s worker prompt or write `active_task.md` under the current restrictions.
5. [Inferred] The best next optimization is validation governance, not immediate strategy code.

## 13. CEO Summary In 5 Lines

1. Prior migration blocker is resolved; the new blocker is safe definition of short/mid-window research.
2. Approve a plan-only P210 if you want workers to proceed.
3. Keep long-term frequency as reference-only and require anti-overfit gates for short windows.
4. Do not allow production/data/registry writes or strategy promotion in the first P210 step.
5. Have CEO/Planner produce the one executable prompt; CTO is blocked from doing so here.

Final Classification: `CTO_ROADMAP_UPDATED_WITH_RISKS`

---

## Historical CTO Analysis — 2026-06-01 And Later Appendices

# CTO Analysis - Roadmap Alignment And System Optimization Direction

## 1. CTO Review Date

2026-06-01 Asia/Taipei.

Final CTO classification target: `CTO_ROADMAP_UPDATED_WITH_RISKS`.

## 2. Input Sources

- [Confirmed] Current roadmap before this update: `00-Plan/roadmap/roadmap.md`.
- [Confirmed] Current CTO analysis before this update: `00-Plan/roadmap/CTO-Analysis.md`.
- [Confirmed] CEO decision and active-task state:
  - `00-Plan/roadmap/CEO-Decision.md`
  - `00-Plan/roadmap/active_task.md` (read only; not modified)
- [Confirmed] User-supplied attachment: `/Users/kelvin/.codex/attachments/c3fa47b0-8143-410e-a7fc-c49d7c0ec99e/pasted-text.txt`.
- [Confirmed] P161/P162 second-zone and baseline evidence:
  - `outputs/research/power_lotto/p161_effectiveness_baseline_20260531.md`
  - `outputs/research/power_lotto/p162_p161_result_closure_20260531.md`
- [Confirmed] P177/P178A POWER_LOTTO closure evidence:
  - `outputs/research/power_lotto/p177_r2_closure_decision_review_20260601.md`
  - `outputs/research/power_lotto/p178a_r2_research_closure_archive_20260601.md`
- [Confirmed] P179-P185 governance, parity, and migration rehearsal artifacts:
  - `outputs/research/power_lotto/p179_replay_product_governance_backlog_decision_gate_20260601.md`
  - `outputs/research/power_lotto/p180_combined_reconciliation_and_replay_backlog_plan_20260601.md`
  - `outputs/research/power_lotto/p181_code_docs_tests_parity_plan_20260601.md`
  - `outputs/research/power_lotto/p182_code_docs_tests_parity_backport_20260601.md`
  - `outputs/research/power_lotto/p183_controlled_db_migration_rehearsal_plan_20260601.md`
  - `outputs/research/power_lotto/p184_controlled_db_migration_rehearsal_temp_copy_20260601.md`
  - `outputs/research/power_lotto/p185_row_delta_import_rehearsal_temp_copy_20260601.md`
- [Confirmed] Read-only git preflight:
  - repo: `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
  - branch: `main`
  - git-dir: `.git`
  - HEAD: `d1a6817 P128: define native multi-bet replay storage design`
- [Confirmed] Read-only SQLite checks:
  - production main DB: 54462 replay rows, `bet_index` absent, POWER_LOTTO rows 15142
  - P185 temp rehearsal DB: 94924 replay rows, `bet_index` present, POWER_LOTTO rows 36104
  - P185 temp `bet_index` distribution: 1=54302, 2=16581, 3=15041, 4=6000, 5=3000
- [Confirmed] Code search found special-number display and analysis paths in UI/API code, including `src/core/App.js`, `src/core/handlers/UIDisplayHandler.js`, `analysis/power_lotto/p161_effectiveness_baseline.py`, and `analysis/power_lotto/p167_ensemble_voting_research.py`.
- [Confirmed] No new tests were run in this CTO review. Test status below is cited from existing artifacts only.
- [Confirmed] No web search was used; all evidence is local project state.

## 3. Roadmap Alignment Assessment

| Finding | Classification | CTO Assessment |
|---|---|---|
| P179-P185 work sequence | [Aligned] | It follows the post-P178A recommendation: stop active POWER_LOTTO research and resolve replay product governance / main-vs-zen-gates reconciliation. |
| P185 row-delta import rehearsal | [Missing] | The artifact exists and passed, but roadmap had not cleanly incorporated it. Roadmap now marks it complete and P186 blocked. |
| P186 production migration gate | [Blocked] | Production migration is not authorized. Gate must approve dedup, backup, production lock, SQL log, validation, rollback, and exact execution phrase. |
| P161-P178A research closure | [Aligned] | Correctly reports a NULL result, closes active POWER_LOTTO research, and forbids promotion/wagering claims. |
| User's second-zone optimization request | [Drift] / [Blocked] | The requested direction conflicts with P178A active-research closure and current special-ball evidence below random. CTO reframes it as containment/diagnostic-only, not optimization or promotion. |
| Existing roadmap P0 trigger standby | [Outdated] | Still useful as a guardrail, but no longer the top maturity blocker. Current P0 is canonical data reconciliation and migration authorization. |
| P126/P127 direct applies | [Outdated] | Superseded by P184/P185 validated migration path toward the 94924-row state. |
| Roadmap file quality | [Outdated] | The file mixed 2026-05-28 priorities, 2026-06-01 appended updates, and corrupted table text. A compact rewrite was necessary to keep it usable. |
| Worker prompt request | [Blocked] | The request simultaneously asks for a worker prompt and forbids CTO from producing a new worker task prompt. CTO follows the stricter boundary and does not write `active_task.md`. |

## 4. Completed Work Assessment

### Replay Product / Reconciliation Chain

- [Confirmed] P179 completed a replay product governance backlog decision gate.
- [Confirmed] P180 completed a combined main/zen-gates reconciliation and replay backlog plan.
- [Confirmed] P181 completed a code/docs/tests parity plan.
- [Confirmed] P182 copied P161-P181 research artifacts/scripts/tests to main without DB write.
- [Confirmed] P183 produced the controlled DB migration rehearsal plan and identified that SQLite table recreation is required.
- [Confirmed] P184 schema rehearsal on temp copy passed; 160 no-provenance rows are removed by the validated `MAX(id)` dedup policy.
- [Confirmed] P185 row-delta import rehearsal on temp copy passed; final temp DB exactly matches zen-gates with 94924 rows.

### POWER_LOTTO Research Chain

- [Confirmed] P161 baseline used 94924-row zen-gates state and found POWER_LOTTO strategies statistically indistinguishable from random after multiple-test correction.
- [Confirmed] P161/P162 special-ball result: predicted-special rows n=9000, hit rate 0.1181 vs random 0.125, below baseline.
- [Confirmed] P167/P170/P173/P176 did not produce a corrected-significant OOS edge.
- [Confirmed] P177 recommended closing active POWER_LOTTO research.
- [Confirmed] P178A formally closed active POWER_LOTTO research, prototypes, promotion, deployment, and controlled_apply; no wagering recommendation.

### Test / Verification Status From Artifacts

- [Confirmed] P177 reports P161-P176 tests: 980 passed.
- [Confirmed] P178A reports P161-P177 tests: 1054 passed.
- [Confirmed] P182 reports drift guard PASS and 54,462-row main DB unchanged.
- [Confirmed] P183 reports P178A-P182 tests: 309 passed / 4 skipped.
- [Confirmed] P184 reports P178A-P183 tests: 361 passed / 5 skipped.
- [Confirmed] P185 reports full rehearsal PASS and production DB write = 0.
- [Unknown] Current full test-suite status was not rerun during this CTO review.

## 5. Unfinished Work Assessment

- [Blocked] P186 production DB migration authorization gate: no CEO authorization yet.
- [Blocked] Production migration execution: cannot happen until P186 gate and exact authorization phrase are complete.
- [Blocked] Main/zen-gates canonical state: main remains 54462 rows without `bet_index`; validated target is 94924 rows with `bet_index`.
- [Missing] Post-migration quality gate: tests currently designed to SKIP on stale main need a controlled transition after migration.
- [Missing] Product disclosure for special-ball confidence: current evidence says special-ball is below random, but UI/API code can display special predictions.
- [Blocked] Second-zone diagnostic task: user supplied a candidate prompt, but CTO cannot emit worker prompts here; P178A also blocks active POWER_LOTTO research unless CEO reopens scope.
- [Deferred] Passive monitoring: P178A says reopen only after >=500 new POWER_LOTTO draws, structural change, independent evidence, pre-registered hypothesis, or explicit CEO governance.
- [Deferred] Dirty worktree cleanup: outside CTO scope and requires explicit file allowlist.

## 6. P0 / P1 / P2 / P3-P10 Reprioritization

| Priority | Work | Status | Rationale |
|---|---|---|---|
| **P0.1** | P186 production DB migration authorization gate | [Blocked] | The migration path is rehearsed, but production write safety is unresolved. |
| **P0.2** | Canonical main/zen-gates reconciliation | [Blocked] | Split-brain DB state blocks truthful replay product, test parity, and research reproducibility. |
| **P0.3** | Second-zone special-ball containment | [Missing] / [Blocked] | Existing evidence is below random; product must not present special-ball as an edge. |
| **P0.4** | Governance conflict resolution for prompt generation | [Blocked] | CTO is forbidden to create a worker task prompt in this request. |
| **P1.1** | Post-migration quality gate and drift guard transition | [Deferred] | Needed immediately after migration, but must not precede actual production state. |
| **P1.2** | Replay UI/API disclosure for `bet_index`, provenance, lifecycle, and special-ball confidence | [Deferred] | Product maturity depends on honest labeling and avoiding overclaiming. |
| **P1.3** | Migration operator guide from P184/P185 evidence | [Deferred] | Converts rehearsal knowledge into safe operational execution. |
| **P2.1** | Passive POWER_LOTTO monitoring under P178A reopen rules | [Waiting] | Low-cost future option; not active research. |
| **P2.2** | Second-zone diagnostic-only audit if CEO authorizes | [Blocked] | Could be useful, but only read-only and non-promotional with non-conflicting task ID. |
| **P3-P10** | Other lottery research, scheduler, external review, packaging, long-term cadence | [Deferred] | Keep roadmap continuity, but do not consume P0/P1 resources. |

Upgrade / downgrade decisions:

- [Confirmed] P186 gate is upgraded to P0 because it controls production DB safety.
- [Confirmed] Main/zen-gates reconciliation remains P0 because current main cannot represent multi-bet replay truth.
- [Inferred] Second-zone containment should be P0/P1 because known below-random evidence can affect product correctness if shown as a recommendation signal.
- [Confirmed] Active POWER_LOTTO feature engineering is retired/closed under P178A.
- [Confirmed] Additional strategy prototypes are downgraded unless reopen conditions are met.
- [Confirmed] P123 trigger checks are retained as standing governance, not today's primary P0.
- [Confirmed] Direct controlled_apply/apply work is downgraded until canonical migration is resolved.

## 7. Critical Blockers

### Blocker 1: Main/Zen-Gates Baseline Split

- **Impact scope:** data quality, replay product correctness, tests, research reproducibility.
- **Why blocker:** main has 54462 replay rows and no `bet_index`; the validated target state has 94924 rows and `bet_index`.
- **Risk if ignored:** UI, tests, and research can report different truths depending on checkout/DB.
- **Priority:** P0.1/P0.2.
- **Acceptance criteria:** P186 gate completes before any production write; canonical baseline is documented; production migration only executes under exact CEO authorization.

### Blocker 2: Production Migration Safety

- **Impact scope:** production DB integrity.
- **Why blocker:** P184/P185 validate a migration that drops 160 no-provenance rows and imports 40622 rows. This is safe in rehearsal, not automatically safe in production.
- **Risk if ignored:** irreversible row loss, no rollback path, or inconsistent DB during live writers.
- **Priority:** P0.1.
- **Acceptance criteria:** immutable backup, production lock, approved `MAX(id)` dedup, reviewed SQL, post-migration validation, rollback plan, exact phrase.

### Blocker 3: Second-Zone Special-Ball Negative Evidence

- **Impact scope:** product correctness and user trust.
- **Why blocker:** P161/P162 show special-ball hit rate below random; continuing to treat it as an optimization target risks overfitting.
- **Risk if ignored:** weak or negative signal may contaminate recommendation score, UI confidence, or future research planning.
- **Priority:** P0.3.
- **Acceptance criteria:** special-ball output remains display-only / random-baseline comparison unless a future read-only diagnostic proves stable OOS evidence.

### Blocker 4: Research Closure vs New Optimization Request

- **Impact scope:** agent/workflow governance.
- **Why blocker:** P178A closes active POWER_LOTTO research; user attachment asks for a new P185 second-zone task while P185 already exists as DB rehearsal.
- **Risk if ignored:** duplicate task IDs, unauthorized research restart, or worker executing the wrong scope.
- **Priority:** P0.4/P2.2.
- **Acceptance criteria:** CEO assigns a new non-conflicting task ID and explicitly authorizes diagnostic-only scope; no CTO-generated worker prompt in this review.

### Blocker 5: Dirty Worktree And Runtime/Data Files

- **Impact scope:** release safety and staging discipline.
- **Why blocker:** many DB/history/runtime/untracked files are dirty before CTO work begins.
- **Risk if ignored:** accidental staging of runtime DB state or hidden generated artifacts.
- **Priority:** P1/P7.
- **Acceptance criteria:** future implementation task uses strict file allowlist; no broad staging; cleanup only under explicit authorization.

## 8. Recommended System Optimization Directions

### 1. Canonical Data Reconciliation And Migration Gate

- **Corresponding roadmap phase:** P0.1/P0.2.
- **Why important:** The system needs one truthful replay dataset.
- **System maturity gain:** Converts rehearsed migration evidence into a governed production decision.
- **Expected benefit:** Test parity, UI correctness, and research reproducibility all improve.
- **Risk:** Production DB write is irreversible without backup and lock discipline.
- **Acceptance:** P186 authorization gate complete; no production DB write during P186.
- **Priority:** P0.

### 2. Second-Zone Special-Ball Evidence Containment

- **Corresponding roadmap phase:** P0.3/P2.2.
- **Why important:** Current special-ball results are below random, so "optimization" is risky language.
- **System maturity gain:** Protects product recommendations from weak-signal contamination.
- **Expected benefit:** Clear user-facing confidence boundary: display-only until proven otherwise.
- **Risk:** Overfitting or false-positive hunting if scope becomes strategy development.
- **Acceptance:** No promotion/scoring; any future diagnostic is read-only, baseline-compared, walk-forward guarded, and CEO-authorized.
- **Priority:** P0/P1.

### 3. Post-Migration Quality Gate

- **Corresponding roadmap phase:** P1.1.
- **Why important:** P182 backported tests that intentionally skip on stale main.
- **System maturity gain:** Makes test results reflect the canonical DB state.
- **Expected benefit:** Future regression failures become meaningful instead of environment artifacts.
- **Risk:** Updating drift guards before migration would encode false state.
- **Acceptance:** After production migration only, update drift guard/markers so DB-dependent contracts PASS against canonical main.
- **Priority:** P1.

### 4. Roadmap And Task Namespace Governance

- **Corresponding roadmap phase:** P0.4/P1.3.
- **Why important:** P185 is already used for DB row-delta rehearsal; the user attachment also labels a second-zone task P185.
- **System maturity gain:** Prevents wrong-task execution by Planner/Worker.
- **Expected benefit:** Cleaner handoff and lower multi-agent error risk.
- **Risk:** Without cleanup, active_task/roadmap/CEO files diverge again.
- **Acceptance:** Future second-zone task uses a new ID and is created only by CEO/Planner authorization, not by CTO in this review.
- **Priority:** P1.

### 5. Product Disclosure For Replay Evidence

- **Corresponding roadmap phase:** P1.2/P4.
- **Why important:** Replay product value is evidence transparency, not lottery edge claims.
- **System maturity gain:** UI/API can separate main hits, special hits, bet slots, provenance, lifecycle, and NULL results.
- **Expected benefit:** Users do not confuse display evidence with betting advice.
- **Risk:** Product copy may lag research conclusions.
- **Acceptance:** No UI/API text implies guaranteed improvement, wagering advice, or validated special-ball edge.
- **Priority:** P1/P2.

## 9. Roadmap Changes Applied

- [Confirmed] Rewrote `00-Plan/roadmap/roadmap.md` into a compact current-state roadmap because the prior file was not maintainable: mixed stale priorities, appended P179-P185 sections, and corrupted table rows.
- [Confirmed] Preserved historical continuity by summarizing P119-P128, P149-P159B, P161-P178A, and P179-P185 rather than deleting their evidence trail.
- [Confirmed] Updated `Last Updated` to 2026-06-01 Asia/Taipei.
- [Confirmed] Added P185 as complete and P186 as blocked.
- [Confirmed] Upgraded P186 migration gate and canonical reconciliation to P0.
- [Confirmed] Added second-zone special-ball containment as P0/P1.
- [Confirmed] Marked active POWER_LOTTO research as closed under P178A.
- [Confirmed] Downgraded old trigger standby and direct controlled_apply work from near-term focus.
- [Confirmed] Documented the worker-prompt conflict and did not modify `00-Plan/roadmap/active_task.md`.
- [Confirmed] CTO modified only `00-Plan/roadmap/roadmap.md` and `00-Plan/roadmap/CTO-Analysis.md`.
- [Confirmed] CTO did not write `CEO-Decision.md`, `active_task.md`, `production/*`, `registry/*`, `data/*`, or any new repo.

## 10. Risks / Unknowns

- [Confirmed] Production main DB remains 54462 rows and lacks `bet_index`.
- [Confirmed] P185 temp rehearsal reaches 94924 rows and matches zen-gates exactly by counts/distribution.
- [Confirmed] Production migration is still blocked by CEO authorization.
- [Confirmed] P161/P162 special-ball result is below random: 0.1181 vs 0.125.
- [Confirmed] P178A closes active POWER_LOTTO research and forbids promotion/deployment/controlled_apply.
- [Confirmed] Current worktree is dirty outside CTO scope.
- [Confirmed] User attachment requests a new P185 second-zone task, but P185 is already used for DB row-delta rehearsal.
- [Unknown] Whether special-ball predictions currently affect any production scoring or only UI display; code search confirms display paths, not weighting semantics.
- [Unknown] Whether CEO wants to authorize a diagnostic-only second-zone audit with a new task ID.
- [Unknown] Whether P186 should proceed immediately or the user wants a risk-review-only pause.
- [Inferred] The highest maturity gain is migration governance, not additional strategy research.
- [Inferred] Second-zone work should focus on containment/disclosure first, not "improvement."

## 11. CTO Final Recommendation

Proceed with **P186 production DB migration authorization gate only** as the next roadmap-level focus. P186 must be plan/gate-only: no production DB write, no copy from zen-gates, no controlled_apply, no research restart. It should explicitly approve or reject the dedup policy, backup, production lock, SQL log, validation checklist, rollback, and exact production execution phrase.

For the user's "second-zone optimization" supplement: do not optimize or promote second-zone special-ball strategies now. Current evidence is below random and POWER_LOTTO active research is closed. The correct system direction is containment: display-only or random-baseline-comparison until CEO explicitly authorizes a new read-only diagnostic with a non-conflicting task ID.

**CEO-gated first executable task prompt status:** [Blocked]. CTO does not emit a worker task prompt and does not write `active_task.md` because the same request explicitly forbids CTO from producing a new worker task prompt and limits CTO writes to two files.

## 12. CTO Summary In 5 Lines

1. [Confirmed] P185 rehearsal passed on temp DB; production main remains 54462 rows with no `bet_index`.
2. [Blocked] P186 production migration authorization gate is the current P0.
3. [Confirmed] POWER_LOTTO R1/R2 research is closed with NULL results across 17 candidates.
4. [Confirmed] Second-zone special hit rate is below random, so optimization/promotion is not allowed.
5. [Blocked] No worker prompt or `active_task.md` update is produced by CTO under this request.

## 13. CEO Summary In 5 Lines

1. Approve P186 gate if you want to move toward the validated 94924-row canonical DB.
2. Do not approve production migration execution until P186 defines backup, lock, SQL, rollback, and exact phrase.
3. Treat second-zone as display-only / diagnostic-only unless new evidence beats random OOS.
4. Keep POWER_LOTTO active research closed under P178A.
5. Assign a new task ID if you later want a second-zone diagnostic; do not reuse P185.

Final Classification: `CTO_ROADMAP_UPDATED_WITH_RISKS`

---

## P186 — CTO Assessment: Production Migration Authorization Gate (2026-06-01)

**Status**: `P186_PRODUCTION_DB_MIGRATION_AUTHORIZATION_GATE_READY`

### Gate Complete

12 authorization conditions defined. P187 is the first task that will write to production DB. It is **DESTRUCTIVE and irreversible without a backup**.

### Critical Requirements for P187

| Requirement | Why |
|-------------|-----|
| Exact phrase (verbatim) | No paraphrase accepted — typo-resistant authorization |
| Timestamped backup (verified, chmod 444) | Without this, rollback is impossible |
| Production lock (all writers stopped) | Concurrent writes during table recreation = corruption |
| SQL from P185 rehearsal log | No ad-hoc SQL in production migration |

### CTO Recommendation

Proceed to P187 **only** with the exact phrase and only after verifying all 15 preflight checklist items pass. The backup step (PF-12/13/14) is the single most critical safety gate.

**Do NOT** run P187 without:
1. Verbatim exact authorization phrase
2. Verified immutable backup (54462 rows confirmed)
3. All API writers stopped

```text
CTO_ROADMAP_UPDATED_AFTER_P186_AUTHORIZATION_GATE_20260601
```

---

## P187 — CTO Assessment: Dry-Run Checklist (2026-06-01)

**Status**: `P187_PRODUCTION_DB_MIGRATION_DRY_RUN_CHECKLIST_READY`

### Checklist Ready for Operator Use

The 13-item DRC checklist is the definitive pre-migration gate. Operator must complete all items in order, stopping on any failure. DRC-13 is the final go/no-go gate that requires explicit operator confirmation of all prior items.

**Critical gates**: DRC-06 (exact phrase verbatim), DRC-11 (backup verified + chmod 444), DRC-10 (writers stopped).

### P188 Authorization

Destructive P188 may proceed **only** if:
1. Exact phrase provided verbatim in P188 prompt
2. All 13 DRC items pass in order
3. Backup verified at 54,462 rows and immutable before first SQL statement

If backup step (DRC-11) fails for any reason, P188 must STOP — do not proceed without verified backup.

```text
CTO_ROADMAP_UPDATED_AFTER_P187_DRY_RUN_CHECKLIST_20260601
```

---

## P188 — CTO Assessment: Production DB Migration (2026-06-01)

**Status**: `P188_PRODUCTION_DB_MIGRATION_EXECUTED_RECONCILED_94924`

### Migration Outcome

Production DB migrated: 54,462 → 94,924 rows. bet_index PRESENT. The DB-level reconciliation between main and zen-gates is **COMPLETE**. Backup exists at `backups/p188_lottery_v2_backup_20260601_153821.db` (54,462 rows, integrity ok).

### Remaining P189 Actions

| Action | Priority |
|--------|----------|
| Update drift guard (54462→94924, accept new CA IDs) | **HIGH** |
| Fix 9 stale pre-migration contract test assertions | HIGH |
| Remove/update requires_zen_gates_db skip markers | MEDIUM |
| Evaluate commit/push plan for P182-P188 changes | HIGH |
| UI: multi-bet display, bet_index filter | LOW |

### CTO Recommendation

**Primary**: `YES start P189 post-migration verification and commit readiness audit`

The drift guard update is critical — it currently FAILS which could mask future regressions. Fix it before any commit. The 9 stale test assertions should be updated or marked as archive-only.

**Do NOT rollback** unless a data integrity issue is discovered. The backup is available if needed.

```text
CTO_ROADMAP_UPDATED_AFTER_P188_PRODUCTION_DB_MIGRATION_20260601
```

---

## P189 — CTO Assessment: Post-Migration Verification (2026-06-01)

**Status**: `P189_POST_MIGRATION_VERIFICATION_COMMIT_READINESS_READY`

All technical post-migration checks PASS: drift guard PASS at 94924, 600 tests PASS, 0 FAIL, backup verified. The repo is **commit-ready** from a technical standpoint.

**CTO Recommendation**: `YES start P190 commit readiness and staging plan only`

Before any git stage/commit/push: review which files should be committed together (DB file may be excluded per `.gitignore`), draft commit message, and confirm with user.

```text
CTO_ROADMAP_UPDATED_AFTER_P189_POST_MIGRATION_VERIFICATION_20260601
```
```

---

## P190 — CTO Assessment: Commit Readiness and Staging Plan (2026-06-01)

**Status**: `P190_COMMIT_READINESS_AND_STAGING_PLAN_READY`

### CTO Assessment

P190 completed a thorough commit readiness audit and produced an 8-group staging whitelist for P191. All Phase 0 preconditions verified: DB=94924 rows, bet_index PRESENT, integrity_check=ok, drift guard PASS, 644 tests PASS, 0 staged files. No DB writes, no stage/commit/push performed.

### Key Governance Points

| Point | Status |
|-------|--------|
| DB rows = 94924 | CONFIRMED |
| bet_index = PRESENT | CONFIRMED |
| Drift guard = PASS | CONFIRMED |
| Tests 644 PASS | CONFIRMED |
| stage/commit/push | **NOT YET — P191 BLOCKED** |
| POWER_LOTTO research | **CLOSED** (P178A) |
| Forbidden staging policy | Documented and enforced |

### CTO Recommendation for P191

**P191 MUST NOT use `git add -A` or `git add .`**. The working tree contains forbidden files: `*.pid`, `runtime/`, `.gstack/`, `.fuse_hidden*`, `lottery_api/data/*.db.bak_*`. Any broad staging would commit process state, OS temp files, and old DB backups.

P191 staging sequence:
1. Run `PRAGMA wal_checkpoint(TRUNCATE)` on lottery_v2.db before staging
2. Stage Group A (DB) + Group B (backup) + Group C (research) + Group D (tests) + Group E (drift guard/config) + Group F (analysis) + Group H (roadmap)
3. Run forbidden scan: `git diff --cached --name-only` — verify no forbidden files
4. Run full test suite (644 tests) before committing
5. Create local commit first (Option B) before any push decision

**Recommended P191 Authorization**: `YES start P191 stage reviewed files and create local commit only, no push`

This creates a reversible local commit. Push to origin/main requires a separate explicit CEO authorization (Option C).

**Do NOT select P191 Option C (push)** without first verifying:
- Branch protection rules (`gh api repos/.../branches/main/protection`)
- CI configuration
- That no forbidden files are staged

```text
CTO_ROADMAP_UPDATED_AFTER_P190_COMMIT_READINESS_STAGING_PLAN_20260601
```

---

## P191 — CTO Assessment: Stage Reviewed Files and Local Commit (2026-06-01)

**Status**: `P191_STAGE_REVIEWED_FILES_LOCAL_COMMIT_READY`

### CTO Assessment

P191 staged 109 files (0 forbidden) and created a local commit. WAL checkpoint ran successfully before staging (lottery_v2.db-wal = 0 bytes). Full pre-commit test suite passed. No push executed — this is a local commit only.

| Check | Status |
|-------|--------|
| WAL checkpoint | TRUNCATE — .db-wal = 0 bytes |
| Forbidden staging scan | PASSED (0 forbidden files) |
| Files staged | 109 |
| Local commit created | YES |
| Push | NO |
| Tests | PASS |
| DB rows | 94924 |

### CTO Recommendation for P192

**Do not push** without verifying:
1. Branch protection rules: `gh api repos/{owner}/{repo}/branches/main/protection`
2. CI configuration
3. That the commit hash is correct with `git log -1 --oneline`

**Recommended P192 Authorization**: `YES start P192 push authorization gate only`

This creates a gate that verifies the local commit before any push decision.

**Direct push option**: `YES start P192 push local commit to origin main` — only if branch protection and CI are confirmed acceptable.

```text
CTO_ROADMAP_UPDATED_AFTER_P191_STAGE_LOCAL_COMMIT_20260601
```

---

## P192-P193 — CTO Assessment: Push Rejection and Remediation Plan (2026-06-01)

**P192 Status**: `P192_PUSH_REJECTED`  
**P193 Status**: `P193_PUSH_REJECTION_REMEDIATION_PLAN_READY`

### Push Rejection Root Causes

| Cause | Detail |
|-------|--------|
| Branch protection (GH006) | `replay-default-validation` status check required before merging to `main`. Direct push is blocked. |
| Large binary warning | `lottery_api/data/lottery_v2.db` = 96 MB (approaching GitHub 100 MB hard limit). `backups/p188_*.db` = 51 MB (over 50 MB recommendation). |

### CTO Recommendation for P194

**Primary: Option B — Remove DB binaries from the P191 commit before any PR/push.**

The production DB and backup are runtime artifacts, not source code. Committing a 96 MB SQLite binary causes:
1. Every clone downloads 96 MB (grows with data ingestion)
2. Approaching GitHub's 100 MB hard limit
3. Slower CI, higher LFS/storage costs if tracked

**Removing from git does NOT delete the local file.** The production DB must remain at `lottery_api/data/lottery_v2.db` (94924 rows, bet_index PRESENT) and the backup at `backups/p188_*.db`.

**P194 should plan the binary removal (git reset --soft + re-commit without binaries) before any push attempt.**

After binary removal, open a PR from a feature branch. Branch protection (`replay-default-validation`) will be satisfied by the CI run on the PR.

### Must NOT:
- Bypass branch protection
- Force push  
- Delete local production DB
- Push DB binary without a clear binary-storage strategy

```text
CTO_ROADMAP_UPDATED_AFTER_P192_P193_PUSH_REJECTION_REMEDIATION_20260601
```

---

## P194 — CTO Assessment: Remove DB Binaries Plan (2026-06-01)

**Status**: `P194_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_PLAN_READY`

### Binary Inventory in P191 Commit

| File | Size | SHA256 prefix | Action |
|------|------|---------------|--------|
| `lottery_api/data/lottery_v2.db` | 96MB | `a5ac27a6` | REMOVE from git, keep locally |
| `backups/p188_lottery_v2_backup_20260601_153821.db` | 51MB | `5eea5313` | REMOVE from git, keep locally |
| `backups/p188_*.db.sha256` | <1KB | N/A | KEEP in git (audit evidence) |

### CTO Recommendation for P195

**Execute Approach 1 (soft reset + recommit) then Approach 3 (feature branch PR).**

P195 should:
1. `git reset --soft HEAD~1` — undo P191 commit, keep staged content
2. `git restore --staged lottery_api/data/lottery_v2.db` — unstage (NOT delete local file)
3. `git restore --staged backups/p188_*.db` — unstage (NOT delete local file)
4. Create `docs/db_migration_manifest_p188_p191.json` with sha256, row counts, byte sizes
5. Update `.gitignore` to exclude DB paths permanently
6. Recommit without binaries

After P195, P196 should create a feature branch and open a PR to satisfy `replay-default-validation`.

**Production DB must NOT be deleted at any step.** The 94924-row migrated state with bet_index is the authoritative local state.

```text
CTO_ROADMAP_UPDATED_AFTER_P194_REMOVE_DB_BINARIES_PLAN_20260601
```

---

## P195 — CTO Assessment: Remove DB Binaries Execution Plan (2026-06-01)

**Status**: `P195_REMOVE_DB_BINARIES_FROM_LOCAL_COMMIT_EXECUTION_PLAN_READY`

### Execution Plan Summary

P196 will execute 9 steps to remove DB binaries from the local P191 commit:

| Step | Action | Safety |
|------|--------|--------|
| 1 | Create `docs/db_migration_manifest_p188_p191.json` | Before any git op |
| 2 | `git reset --soft HEAD~1` | Local only; files untouched |
| 3-4 | `git restore --staged *.db` | Unstage, NOT delete |
| 5-6 | Update .gitignore + stage manifest | Prevent future DB commits |
| 7 | Recommit without binaries | New clean commit |
| 8 | Verify DB = 94924 rows, tests PASS | Full safety gate |
| 9 | STOP — no push | P197 handles PR |

### DB Evidence After Binary Removal

The manifest will contain:
- Production DB SHA256: `a5ac27a6887d8c1d8da97349dbc97c36e9429270dd45f81b3b67a8d5793c4f87`
- Production DB rows: 94924, size: 99,368,960 bytes
- Backup SHA256: `5eea53135fb65369a3dd90512e7f8bfc4411b756abadf00a03b2b9b7d4e24da9`
- Backup rows: 54462, size: 53,374,976 bytes

### CTO Recommendation for P196

**Authorize P196 Option A** when ready:
```
YES execute P196 remove DB binaries from local commit using soft reset and recommit non-binary files, no push
```

> ⚠️ Use `git reset --soft` NOT `--hard`  
> ⚠️ Use `git restore --staged` NOT `git rm`  
> ✅ Verify DB rows = 94924 before AND after reset  
> ✅ Do NOT push — push goes through P197 feature branch + PR  

```text
CTO_ROADMAP_UPDATED_AFTER_P195_EXECUTION_PLAN_20260601
```

---

## P196 — CTO Assessment: Remove DB Binaries and Recommit (2026-06-01)

**Status**: `P196_REMOVE_DB_BINARIES_RECOMMIT_NON_BINARY_READY`

P196 executed the soft reset and recommit. The P191 binary-heavy commit (`012d4a3`) has been replaced by a non-binary local commit. The production DB (`lottery_api/data/lottery_v2.db`, 96MB, 94924 rows) and backup (`backups/p188_*.db`, 51MB) remain intact locally and are excluded from git tracking via `.gitignore`.

### Verification Evidence
- Production DB SHA256: `a5ac27a6887d8c1d8da97349dbc97c36e9429270dd45f81b3b67a8d5793c4f87`
- Backup SHA256: `5eea53135fb65369a3dd90512e7f8bfc4411b756abadf00a03b2b9b7d4e24da9`
- Manifest: `outputs/research/power_lotto/p196_db_binary_external_storage_manifest_20260601.json`

### CTO Recommendation for P197

Create a feature branch from the current clean local commit, push it to origin, open a PR to main, let `replay-default-validation` CI run, then merge.

**P197 Authorization (recommended):** `YES start P197 create PR branch and push for CI no merge`

```text
CTO_ROADMAP_UPDATED_AFTER_P196_REMOVE_DB_BINARIES_RECOMMIT_20260601
```
