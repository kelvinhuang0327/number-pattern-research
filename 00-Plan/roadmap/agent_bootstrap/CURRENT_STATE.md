# Current State — LotteryNew

**Last Reviewed:** 2026-06-04 Asia/Taipei (P235B Lofea feasibility governance closeout — P235A `FIT_AS_DESIGN_INSPIRATION_ONLY` merged PR #281; P234A governance follow-up merged PR #280; no deployable candidate; WAITING_FOR_USER_AUTHORIZATION)
**State Marker:** `P235B_LOFEA_FEASIBILITY_GOVERNANCE_CLOSEOUT_MERGED`
**Purpose:** Project-specific state for future agents. Read this after `SHARED_AGENT_BOOTSTRAP.md` and `TASK_TEMPLATES.md`.

## Canonical Execution Context

| Item | Current State | Status |
|---|---|---|
| Project | LotteryNew | [Confirmed] |
| Canonical repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | [Confirmed] |
| Canonical branch | `main` | [Confirmed] |
| Current HEAD | HEAD must equal `origin/main`; verify with `git rev-parse HEAD` and `git rev-parse origin/main` before any task. Do not hardcode a live hash here — this field becomes stale after every PR merge. Last recorded PR merge: P228 governance closeout (branch `p228-star-replay-governance-closeout`). | [Self-verifying] |
| `origin/main` | Must equal HEAD; see above. Verify with `git rev-parse origin/main`. | [Self-verifying] |
| Git dir | `.git` | [Confirmed] |
| Active worker task | none (P233C governance closeout complete) | [Confirmed] |
| P211 status | `HELD_BY_USER`; do not auto-resume or re-prompt | [Confirmed] |

## Forbidden Execution Paths

Do not dispatch or execute from:

- `.claude/worktrees/*`
- `/Users/kelvin/Kelvin-WorkSpace/_archive/lottery_stale_repos_20260602_162329/*`
- `/Users/kelvin/Kelvin-WorkSpace/workspace-AI/LotteryNew/`
- Any stale clone, backup folder, archive folder, or non-canonical repo

## Current Data / Artifact Baseline

| Check | Expected Current State | Status |
|---|---:|---|
| DB path | `lottery_api/data/lottery_v2.db` | [Confirmed] |
| SQLite integrity | `ok` | [Confirmed] |
| Replay table | `strategy_prediction_replays` | [Confirmed] |
| Replay rows | 94,924 | [Confirmed] |
| BIG_LOTTO rows | 24,140 | [Confirmed] |
| DAILY_539 rows | 34,680 | [Confirmed] |
| POWER_LOTTO rows | 36,104 | [Confirmed] |
| 3_STAR replay rows | 0 (zero — no replay rows exist) | [Confirmed] |
| 4_STAR replay rows | 0 (zero — no replay rows exist) | [Confirmed] |
| `bet_index` column | present | [Confirmed] |
| `bet_index` nulls | 0 | [Confirmed] |
| Duplicate `(lottery_type,target_draw,strategy_id,bet_index)` keys | 0 | [Confirmed] |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | [Confirmed] |
| P227B targeted tests | 42/42 PASS | [Confirmed] |
| P227C targeted tests | 27/27 PASS | [Confirmed] |
| Latest known full test suite | 1097 passed / 0 failed | [Confirmed] handoff; [Unknown] not rerun after P227C |
| Staged files | 0 | [Confirmed] |
| Dirty worktree | existing local modifications/untracked files outside governance scope | [Confirmed] |

Read-only baseline commands:

- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse --git-dir`
- `git rev-parse HEAD`
- `git rev-parse origin/main`
- `git diff --cached --name-only`
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT integrity_check FROM pragma_integrity_check;"`
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"`
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays WHERE bet_index IS NULL;"`
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM (SELECT lottery_type,target_draw,strategy_id,bet_index,COUNT(*) c FROM strategy_prediction_replays GROUP BY 1,2,3,4 HAVING c>1);"`
- `python3 scripts/replay_lifecycle_drift_guard.py --strict`

## Current Roadmap Phase

| Phase | State | Notes |
|---|---|---|
| P188-P205 migration / PR #249 | COMPLETE + MERGED | DB reconciled to 94,924 rows; DB binary remains local/untracked. |
| P206-P209 repo archive cleanup | COMPLETE | Stale `Lottery/` and `LotteryNew-clean/` are archived and marked DO_NOT_USE. |
| P210 short/mid-window protocol | COMPLETE / CEO accepted | Protocol is frozen as reference. |
| P211 read-only diagnostic | HELD_BY_USER | Do not start unless user explicitly authorizes P211 or a new direction. |
| P212–P218 governance chain | COMPLETE | See `active_task.md` historical index and `CEO-Decision.md` for details. |
| P211A POWER_LOTTO second-zone diagnostic | COMPLETE — NULL / display-only confirmed | Hit-rate edge NULL (all Bonferroni-corrected p > 0.04); second-zone remains display-only. |
| P221F cross-lottery feature-discovery protocol | COMPLETE — frozen | Windows: short 100/125/150, mid 500/750/1000, all-history=reference. Anti-overfit gate active. |
| P222 cross-lottery feature-discovery scan | COMPLETE — `CANDIDATES_FOUND_NEED_MORE_OOS` | 35 strategies × 3 lotteries; BIG_LOTTO=NULL; DAILY_539 / POWER_LOTTO have weak in-sample candidates. |
| P223B candidate OOS cross-year validation | COMPLETE | One survivor: `midfreq_fourier_2bet / DAILY_539` (on overlapping slice). Others: NEEDS_MORE_OOS / REJECTED. |
| P224 DAILY_539 survivor deeper validation | COMPLETE — `SURVIVOR_NEEDS_MORE_OOS` | Clean-slice p=0.0674; CI crosses baseline; edge rests on 19 hit=3 rows. **Not deployable. WAIT_FOR_OOS.** |
| P224B/P224C survivor future-OOS monitoring | COMPLETE — protocol accepted | Reopen gate: ≥300 new DAILY_539 draws (preferred 500) + full P224B gate. |
| P225 governance closeout sync | COMPLETE | roadmap.md §0.1 + CURRENT_STATE.md; PR #261 + PR #262. Records P217–P224C; fixes stale windows; marks survivor WAIT_FOR_OOS. |
| **P226 3_STAR/4_STAR replay-gap discovery** | **COMPLETE** — `P226_STAR_REPLAY_GAP_DISCOVERY_COMPLETE` | 3_STAR 4,179 draws; 4_STAR 2,922 draws; replay rows 0 for both. DB stores sorted numbers → **positional order lost**. Straight-play BLOCKED until re-ingestion. Box-play feasible. Baselines: 3_STAR 1/120=0.00833; 4_STAR 1/210=0.00476. PR #263 (with P227A). |
| **P227A 3_STAR/4_STAR box-play adapter design** | **COMPLETE** — `P227A_STAR_BOX_PLAY_ADAPTER_DESIGN_READY` | Design-only. Metric semantics: `star_box_exact_match` (multiset), `star_digit_overlap_count`, `star_calculate_box_score`. `calculate_match_score` prohibited. `dry_run=1` isolation. Power warning documented. PR #263. |
| **P227B 3_STAR/4_STAR box-play code dry-run** | **COMPLETE** — `P227B_STAR_BOX_PLAY_DRYRUN_CODE_COMPLETE` | `lottery_api/models/star_box_play.py` implemented. **42/42 targeted tests PASS.** No DB write. Straight-play BLOCKED. PR #264. |
| **P227C 3_STAR/4_STAR box-play dry-run scan** | **COMPLETE** — `P227C_STAR_BOX_PLAY_UNDERPOWERED_NO_SIGNAL` | 120 hypotheses (10 features × 6 windows × 2 lotteries). **69/69 targeted tests PASS.** 3_STAR: 0 Bonferroni, 1 BH-FDR weak (UNDERPOWERED). 4_STAR: 0 Bonferroni, 0 BH-FDR. **Both lotteries UNDERPOWERED_NO_SIGNAL. Not deployable.** PR #265. |
| **P228 governance closeout sync** | **COMPLETE** | roadmap.md + CURRENT_STATE.md updated to reflect P226–P227C. |
| **P230A DAILY_539 backward-OOS extension plan** | **COMPLETE** — `P230A_DAILY539_BACKWARD_OOS_EXTENSION_PLAN_READY` | Plan-only; identified 4,265 replayable backward draws; leakage guard; architecture design. PR #268. |
| **P230B1 DAILY_539 backward-OOS code-only dry-run** | **COMPLETE** — `P230B1_BACKWARD_OOS_DRYRUN_BELOW_BASELINE` | Zero DB write; backward-OOS mean 0.6375 < baseline 0.6410 (z=−0.32, p=0.626); all era/robustness checks fail. PR #269. |
| **P230C DAILY_539 survivor reclassification closeout** | **COMPLETE** — `P230C_DAILY539_SURVIVOR_RECLASSIFIED_HISTORICAL_ARTIFACT` | `midfreq_fourier_2bet / DAILY_539` reclassified from `WAIT_FOR_OOS` to `REJECTED_BY_BACKWARD_OOS / HISTORICAL_ARTIFACT_DIRECTION`. No new research started. |
| **P231A POWER_LOTTO first-zone re-entry review** | **COMPLETE** — `P231A_POWERLOTTO_REENTRY_PLAN_READY` | Plan + pre-registration for P231B. DB-verified candidate: `midfreq_fourier_mk_3bet / POWER_LOTTO`, 4,500 rows / 1,500 draws / bet 1,2,3. Cross-year unstable (2025 below baseline). Artifact only. |
| **P231B POWER_LOTTO first-zone backward-OOS dry-run** | **COMPLETE** — `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL` | Zero DB write; 382 replayable backward draws (2008–2012); deterministic bet-1 only. First-zone mean 0.96859 vs baseline 0.94737; CI crosses; p=0.3018; robustness fails. **PR #272 merged.** No production/registry/recommendation change. Candidate non-deployable. |
| **P231C POWER_LOTTO first-zone governance closeout** | **COMPLETE** — `P231C_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_GOVERNANCE_CLOSEOUT_MERGED` | Doc-only sync recording P231B NULL result into all governance files. PR #273. No code/DB/registry/production change. |
| **P232A All-catalog historical replay scoreboard** | **COMPLETE** — `P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD_COMPLETE` | Read-only scoreboard; 41 total strategy+lottery entries (21 catalog-registered incl. 8 ONLINE/4 REJECTED/5 RETIRED/1 OBS/3 DRY_RUN; 20 LIFECYCLE_UNRESOLVED); 36 replay-backed; 5 no-replay. lifecycle label only. Zero DB write. 20/20 tests PASS. Historical evidence only. PR #274. |
| **P232B All-catalog scoreboard governance closeout** | **COMPLETE** — `P232B_ALL_CATALOG_SCOREBOARD_GOVERNANCE_CLOSEOUT_MERGED` | Doc-only sync recording P232A complete. PR #275. |
| **P233A Lifecycle-unresolved registry hygiene plan** | **COMPLETE** — `P233A_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_PLAN_MERGED` | Read-only plan for 20 LIFECYCLE_UNRESOLVED entries. 12 REJECTED + 8 RETIRED suggestions. 18/18 tests PASS. PR #276. |
| **P233B Non-executable stub update** | **COMPLETE** — `P233B_LIFECYCLE_UNRESOLVED_NON_EXECUTABLE_STUB_UPDATE_MERGED` | 20 `_NON_EXECUTABLE_STUB` entries added to `replay_strategy_registry.py`. LIFECYCLE_UNRESOLVED 20→0. No executable adapter. Zero DB write. 10/10 tests PASS. PR #277. |
| **P233C Lifecycle unresolved registry hygiene governance closeout** | **COMPLETE** — `P233C_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_GOVERNANCE_CLOSEOUT` | Doc-only sync recording P233A/B complete. No code/DB/production change. |
| **P234 CTO statistical methods adoption analysis** | **COMPLETE** — `CTO_STATISTICAL_METHODS_ADOPTION_WITH_RISKS` | CTO analysis only. Scientific Statistical Diagnostics Layer framing adopted as read-only diagnostics, not implementation. P0.5 urgency demoted to P2 design-only. |
| **P234A Governance follow-up** | **COMPLETE** — `P234A_GOVERNANCE_FOLLOWUP_CEO_DECISION_PARTIALLY_APPROVED_P2_DESIGN_ONLY` | Doc-only. roadmap.md P0.5→P2.4; CTO-Analysis.md CEO Follow-Up Note added; namespace fixed (Lofea=P235A). PR #280 merged. |
| **P235A Lofea read-only feasibility review** | **COMPLETE** — `P235A_LOFEA_FEASIBILITY_REVIEW_COMPLETE_DESIGN_INSPIRATION_ONLY` | Read-only. Lofea = CC-BY-NC feature-engineering toolkit, 1/10-per-column lotteries. No deployable evidence. Adopt now = NO. Design inspiration only. PR #281 merged. |
| **P235B Lofea feasibility governance closeout** | **COMPLETE** — `P235B_LOFEA_FEASIBILITY_GOVERNANCE_CLOSEOUT_MERGED` | Doc-only closeout. active_task → WAITING_FOR_USER_AUTHORIZATION. No code/DB/production change. |

## Completed Milestones

- [Confirmed] Production replay DB migration complete: 54,462 rows to 94,924 rows with `bet_index` present.
- [Confirmed] PR #249 merged into `main`.
- [Confirmed] Drift guard passes against the 94,924-row baseline.
- [Confirmed] DB binaries are excluded from git-tracked source; evidence is maintained through manifests and validation checks.
- [Confirmed] P210 protocol accepted by CEO. P211 HELD_BY_USER.
- [Confirmed] P212–P218 governance chain complete; all pushed to `origin/main`.
- [Confirmed] Shared bootstrap files under `00-Plan/roadmap/agent_bootstrap/` are git-tracked source-controlled artifacts.
- [Confirmed] P211A: POWER_LOTTO second-zone hit-rate edge NULL; display-only confirmed.
- [Confirmed] P221F: cross-lottery protocol frozen (windows short 100/125/150, mid 500/750/1000).
- [Confirmed] P222 scan complete; BIG_LOTTO NULL; DAILY_539 / POWER_LOTTO weak candidates only.
- [Confirmed] P223B: only `midfreq_fourier_2bet / DAILY_539` reached cross-year survivor status (on overlapping slice).
- [Confirmed] P224: clean-slice dedup shows p=0.0674 (fails 0.05); edge fragile; survivor downgraded to WAIT_FOR_OOS.
- [Confirmed] P224B: future OOS monitoring protocol frozen; reopen gate defined.
- [Confirmed] P225 CEO decision: both user directions executed and returned NULL; governance docs synced.
- [Confirmed] P226: 3_STAR/4_STAR draw-side data confirmed; replay rows = 0; sorted storage identified; straight-play blocked.
- [Confirmed] P227A: box-play adapter design complete; straight-play blocked documented with re-ingestion requirement.
- [Confirmed] P227B: `star_box_play.py` implemented; 42/42 tests PASS; no DB write; `calculate_match_score` not used.
- [Confirmed] P227C: 120-hypothesis scan; UNDERPOWERED_NO_SIGNAL for both lotteries; 69/69 tests PASS; no DB write.
- [Confirmed] P230A: DAILY_539 backward-OOS extension plan ready; 4,265 replayable backward draws identified; leakage guard and dry-run architecture defined. PR #268.
- [Confirmed] P230B1: backward-OOS code-only dry-run complete; mean 0.6375 < baseline 0.6410 (z=−0.32, p=0.626); all era/robustness checks fail; zero DB write. `BELOW_BASELINE`. PR #269.
- [Confirmed] P230C: DAILY_539 survivor `midfreq_fourier_2bet` reclassified from WAIT_FOR_OOS → **REJECTED_BY_BACKWARD_OOS / HISTORICAL_ARTIFACT_DIRECTION**. No deployment. No P230B2 DB backfill recommended. No P225 model design recommended.
- [Confirmed] P231A: POWER_LOTTO first-zone re-entry review complete; `midfreq_fourier_mk_3bet / POWER_LOTTO` identified as the only first-zone candidate; pre-registration for P231B produced. Artifact only.
- [Confirmed] P231B: POWER_LOTTO first-zone backward-OOS code dry-run complete. 382 older draws (2008–2012); deterministic bet-1 only; zero DB write. Mean 0.96859 vs baseline 0.94737; CI crosses baseline; p=0.3018; **both robustness checks fail**; block stability mixed. Classification: **`P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL`**. 14 targeted tests (12/14 PASS, 2 env-skip). PR #272 merged, merge commit `2beb24e`. No production/registry/recommendation change. Candidate remains non-deployable.
- [Confirmed] P231C: POWER_LOTTO first-zone governance closeout complete. P231B NULL result recorded in all governance files (doc-only, no code/DB/registry/production change).
- [Confirmed] P232A: All-catalog historical replay scoreboard complete. 41 total strategy+lottery entries; 21 catalog-registered (8 ONLINE, 4 REJECTED, 5 RETIRED, 1 OBSERVATION, 3 DRY_RUN); 20 LIFECYCLE_UNRESOLVED (in replay DB but not in any catalog); 36 replay-backed; 5 no-replay. lifecycle is a label only. Zero DB write. 20/20 targeted tests PASS. No forbidden classification emitted. PR #274 merged.
- [Confirmed] P232B: All-catalog scoreboard governance closeout complete. PR #275.
- [Confirmed] P233A: Lifecycle-unresolved registry hygiene plan complete. Evidence-based lifecycle suggestions for 20 entries: 12 REJECTED (rejected/ archive) + 8 RETIRED (P59/P66/P79/P94/P126D production applies). 18/18 tests PASS. PR #276.
- [Confirmed] P233B: Non-executable stub update complete. 20 `_NON_EXECUTABLE_STUB` entries added to `replay_strategy_registry.py`. **LIFECYCLE_UNRESOLVED 20→0.** No executable adapter added. Zero DB write. 10/10 tests PASS. PR #277.
- [Confirmed] P233C: Lifecycle unresolved registry hygiene governance closeout complete. P233A/B results recorded in governance files (doc-only, no code/DB/production change).
- [Confirmed] P234: CTO statistical methods adoption analysis complete. Scientific Statistical Diagnostics Layer framing adopted as read-only diagnostics; P0.5 urgency demoted to P2.4 design-only by CEO. `CTO_STATISTICAL_METHODS_ADOPTION_WITH_RISKS`.
- [Confirmed] P234A: Governance follow-up doc-only. roadmap.md P0.5→P2.4; CTO-Analysis.md CEO Follow-Up Note; namespace Lofea=P235A. PR #280 merged.
- [Confirmed] P235A: Lofea read-only feasibility review complete. `FIT_AS_DESIGN_INSPIRATION_ONLY`. Lofea = CC-BY-NC feature-engineering toolkit, 1/10-per-column lotteries. No deployable predictive evidence. Adopt now = NO. Design inspiration only; any reuse must be natively re-derived + P221F + multiple-testing + walk-forward/OOS. PR #281 merged.
- [Confirmed] P235B: Lofea feasibility governance closeout complete. active_task → WAITING_FOR_USER_AUTHORIZATION. No code/DB/production change.

## Current Blockers / Holds

- [Blocked] P211 is held by user. Do not auto-resume.
- [Closed] DAILY_539 survivor `midfreq_fourier_2bet` = **REJECTED_BY_BACKWARD_OOS / HISTORICAL_ARTIFACT_DIRECTION** (P230C). P230B1 backward-OOS dry-run (4,265 draws, 2007/05–2021/08): mean 0.6375 < baseline 0.6410; all era/robustness checks fail. In-window edge is a historical artifact. **No deployment. No P230B2 DB backfill.** Production / registry / recommendation logic unchanged.
- [Closed / NULL] POWER_LOTTO first-zone candidate `midfreq_fourier_mk_3bet` = **`P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL`** (P231B). Backward-OOS 382 draws: mean 0.969 vs baseline 0.947; CI crosses baseline; p=0.30; both robustness checks below baseline; block stability mixed. **Non-deployable. Observation-only. No promotion. No production/registry/recommendation change.**
- [Hold] 3_STAR / 4_STAR box-play = **UNDERPOWERED_NO_SIGNAL**. Not deployable. Need ≥10,000 3_STAR draws (have 4,179) or ≥17,000 4_STAR draws (have 2,922) for adequate power. Any re-scan must inherit P221F gate with fresh pre-registration.
- [Blocked] 3_STAR / 4_STAR straight-play = **BLOCKED_REINGEST_REQUIRED**. Positional order lost in DB sorted storage. Re-ingestion from raw positional source requires separate authorization.
- [Risk] Worktree contains existing dirty/untracked files outside governance scope; future tasks must use narrow write allowlists.
- [Resolved] LIFECYCLE_UNRESOLVED: **0** (was 20). P233B added 20 non-executable stubs to `replay_strategy_registry.py`. All formerly-unresolved entries now have REJECTED or RETIRED labels. No executable adapter added.
- [Resolved] Governance doc staleness at P217–P232A: resolved by P225 + P228 + P231C + P232B closeout.
- [Resolved] DAILY_539 survivor backward-OOS extension (P1.2): resolved by P230A plan + P230B1 dry-run; result BELOW_BASELINE → reclassified in P230C.
- [Resolved] POWER_LOTTO first-zone backward-OOS (P1 candidate): resolved by P231B dry-run; result NULL → observation-only in P231C.

## Latest User Direction / Product Intent

- Direction #1 (window reframe): **operationalized** — P221F frozen as short 100/125/150, mid 500/750/1000, all-history=reference-only. Canonical window set for all future scans.
- Direction #2 (mine all-lottery × all-method): **executed (P222 + P226–P227C) — returned NULL/fragile**. Sole survivor fragile (DAILY_539, p=0.0674). 3_STAR/4_STAR UNDERPOWERED_NO_SIGNAL.
- Keep long-term / full-period frequency as reference/context only — never a gating condition.
- Treat NULL as a valid successful result.
- Do not treat historical replay evidence as betting advice or guaranteed predictive edge.
- Do not rerun the same P221F or P227C sweeps on the same data (manufactures false positives).

## Recommended Next Direction

No active deployable candidate in any lottery. **The P211A–P231B arc has exhausted all current in-window candidates. P232A all-catalog scoreboard confirms no deployable candidate. P233B registry hygiene resolved LIFECYCLE_UNRESOLVED to 0. P234/P234A CTO statistical-methods analysis complete (P2.4 design-only). P235A Lofea feasibility review complete (design-inspiration only, no deployable edge). Governance record is now complete.** Do not start new research without explicit user authorization. Queued options:

1. **Passive monitoring** — wait for ≥300 new DAILY_539 draws (preferred 500); per P224B protocol, new OOS evidence could reopen, but prior shifted toward NULL after P230B1 below-baseline.
2. **3_STAR/4_STAR re-scan** — only after ≥10,000 total 3_STAR draws (currently 4,179) accumulate naturally, or after positional re-ingestion for straight-play; requires fresh pre-registration.
3. **Explore entirely new strategies / hypotheses** — requires explicit authorization, fresh P221F pre-registration, and a new task prompt.
4. **POWER_LOTTO first-zone future OOS** — `midfreq_fourier_mk_3bet` remains observation-only (P231B NULL); future OOS monitoring only with explicit authorization and P221F gate.

Retired: DAILY_539 survivor backward-OOS extension (P1.2) — resolved; POWER_LOTTO first-zone backward-OOS (P231B) — resolved NULL.

For any new research task, include:

- Canonical repo / branch / HEAD / DB baseline STOP guards
- Forbidden path guards
- Allowed write files (narrow)
- Required read-only checks
- Inherit P221F anti-overfit gate (pre-register windows and baselines before any scan)
- No DB / production / registry write unless explicitly authorized
- Required Completion Check
