# Current State — LotteryNew

**Last Reviewed:** 2026-06-03 Asia/Taipei (P228 governance closeout — P226–P227C star replay chain)
**State Marker:** `P228_STAR_REPLAY_GOVERNANCE_CLOSEOUT_COMPLETE_P226_P227C_UNDERPOWERED_NO_SIGNAL`
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
| Active worker task | none (P228 closeout complete) | [Confirmed] |
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
| **P228 governance closeout sync** | **COMPLETE (this task)** | roadmap.md + CURRENT_STATE.md updated to reflect P226–P227C. |

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

## Current Blockers / Holds

- [Blocked] P211 is held by user. Do not auto-resume.
- [Hold] DAILY_539 survivor `midfreq_fourier_2bet` = **WAIT_FOR_OOS**. Reopen requires ≥300 new DAILY_539 target draws (preferred 500) AND all P224B gates must pass. Failure = historical artifact.
- [Hold] 3_STAR / 4_STAR box-play = **UNDERPOWERED_NO_SIGNAL**. Not deployable. Need ≥10,000 3_STAR draws (have 4,179) or ≥17,000 4_STAR draws (have 2,922) for adequate power. Any re-scan must inherit P221F gate with fresh pre-registration.
- [Blocked] 3_STAR / 4_STAR straight-play = **BLOCKED_REINGEST_REQUIRED**. Positional order lost in DB sorted storage. Re-ingestion from raw positional source requires separate authorization.
- [Deferred] DAILY_539 survivor backward-OOS extension (P1.2) — ~4,376 un-replayed older draws; requires explicit DB-write authorization; inherits P224B gates.
- [Risk] Worktree contains existing dirty/untracked files outside governance scope; future tasks must use narrow write allowlists.
- [Resolved] Governance doc staleness at P217–P227C: resolved by P225 + P228 closeout; roadmap.md §0.1 and CURRENT_STATE.md now reflect P227C.

## Latest User Direction / Product Intent

- Direction #1 (window reframe): **operationalized** — P221F frozen as short 100/125/150, mid 500/750/1000, all-history=reference-only. Canonical window set for all future scans.
- Direction #2 (mine all-lottery × all-method): **executed (P222 + P226–P227C) — returned NULL/fragile**. Sole survivor fragile (DAILY_539, p=0.0674). 3_STAR/4_STAR UNDERPOWERED_NO_SIGNAL.
- Keep long-term / full-period frequency as reference/context only — never a gating condition.
- Treat NULL as a valid successful result.
- Do not treat historical replay evidence as betting advice or guaranteed predictive edge.
- Do not rerun the same P221F or P227C sweeps on the same data (manufactures false positives).

## Recommended Next Direction

No active deployable candidate in any lottery. Do not start new research without explicit user authorization. Queued options:

1. **DAILY_539 survivor backward-OOS extension** (P1.2) — ~4,376 un-replayed older DAILY_539 draws; faster than waiting ~1 year for 300 future draws; requires explicit DB-write authorization; inherits P224B gates.
2. **Passive monitoring** — wait for ≥300 new DAILY_539 draws (preferred 500), then recheck survivor per P224B protocol.
3. **3_STAR/4_STAR re-scan** — only after ≥10,000 total 3_STAR draws (currently 4,179) accumulate naturally, or after positional re-ingestion for straight-play; requires fresh pre-registration.

For any new research task, include:

- Canonical repo / branch / HEAD / DB baseline STOP guards
- Forbidden path guards
- Allowed write files (narrow)
- Required read-only checks
- Inherit P221F anti-overfit gate (pre-register windows and baselines before any scan)
- No DB / production / registry write unless explicitly authorized
- Required Completion Check
