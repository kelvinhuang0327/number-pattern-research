# Current State — LotteryNew

**Last Reviewed:** 2026-06-03 Asia/Taipei (P225 governance closeout sync)
**State Marker:** `P225_GOVERNANCE_CLOSEOUT_SYNC_COMPLETE_P211A_P224C_RECORDED_SURVIVOR_WAIT_FOR_OOS`
**Purpose:** Project-specific state for future agents. Read this after `SHARED_AGENT_BOOTSTRAP.md` and `TASK_TEMPLATES.md`.

## Canonical Execution Context

| Item | Current State | Status |
|---|---|---|
| Project | LotteryNew | [Confirmed] |
| Canonical repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | [Confirmed] |
| Canonical branch | `main` | [Confirmed] |
| Current HEAD | HEAD must equal `origin/main`; verify with `git rev-parse HEAD` and `git rev-parse origin/main` before any task. Do not hardcode a live hash here — this field becomes stale after every PR merge. Last recorded PR merge: P225 governance closeout sync (merge of branch `p225-governance-closeout-roadmap-current-state`). | [Self-verifying] |
| `origin/main` | Must equal HEAD; see above. Verify with `git rev-parse origin/main`. | [Self-verifying] |
| Git dir | `.git` | [Confirmed] |
| Active worker task | P225 governance closeout in progress / complete after this task | [Confirmed] |
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
| `bet_index` column | present | [Confirmed] |
| `bet_index` nulls | 0 | [Confirmed] |
| Duplicate `(lottery_type,target_draw,strategy_id,bet_index)` keys | 0 | [Confirmed] |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | [Confirmed] |
| Latest known full test suite | 1097 passed / 0 failed | [Confirmed] handoff; [Unknown] not rerun on 2026-06-03 |
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
| P222 cross-lottery feature-discovery scan | COMPLETE — `CANDIDATES_FOUND_NEED_MORE_OOS` | 35 strategies x 3 lotteries; BIG_LOTTO=NULL; DAILY_539 and POWER_LOTTO have weak in-sample candidates. |
| P223B candidate OOS cross-year validation | COMPLETE | One survivor: `midfreq_fourier_2bet / DAILY_539` (on overlapping slice). Others: NEEDS_MORE_OOS / REJECTED. |
| P224 DAILY_539 survivor deeper validation | COMPLETE — `SURVIVOR_NEEDS_MORE_OOS` | Clean-slice p=0.0674; CI crosses baseline; edge rests on 19 hit=3 rows. **Not deployable. WAIT_FOR_OOS.** |
| P224B/P224C survivor future-OOS monitoring | COMPLETE — protocol accepted | Reopen gate: >=300 new DAILY_539 draws (preferred 500) + full P224B gate. |
| P225 governance closeout sync | COMPLETE (this task) | roadmap.md §0.1 + CURRENT_STATE.md updated to reflect P211A–P224C. |

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

## Current Blockers / Holds

- [Blocked] P211 is held by user. Do not auto-resume.
- [Hold] DAILY_539 survivor `midfreq_fourier_2bet` = **WAIT_FOR_OOS**. Reopen requires >=300 new DAILY_539 target draws (preferred 500) AND all P224B gates must pass. Failure = historical artifact.
- [Deferred] 3_STAR / 4_STAR replay-gap diagnostic (P1.1) — needs separate plan-only authorization.
- [Deferred] DAILY_539 survivor backward-OOS extension (P1.2) — needs explicit DB-write authorization.
- [Risk] Worktree contains existing dirty/untracked files outside governance scope; future tasks must use narrow write allowlists.
- [Resolved] Governance doc staleness at P217–P218: resolved by P225 closeout; roadmap.md §0.1 and CURRENT_STATE.md now reflect P224C.

## Latest User Direction / Product Intent

- Direction #1 (window reframe): **operationalized** — P221F frozen as short 100/125/150, mid 500/750/1000, all-history=reference-only. This is the canonical window set for all future scans.
- Direction #2 (mine all-lottery × all-method): **executed (P222) — returned NULL/fragile**. Sole survivor fragile at clean-slice p=0.0674.
- Keep long-term / full-period frequency as reference/context only — never a gating condition.
- Treat NULL as a valid successful result.
- Do not treat historical replay evidence as betting advice or guaranteed predictive edge.
- Do not rerun the same P221F sweep on the same data (manufactures false positives).

## Recommended Next Direction

Do not start new research without explicit user authorization. Queued authorized options:

1. **3_STAR / 4_STAR plan-only diagnostic** (P1.1) — only unmined lottery family; 7,101 draws, 0 replay rows; plan-only first, then separate read-only execution authorization.
2. **DAILY_539 survivor backward-OOS extension** (P1.2) — ~4,376 un-replayed older draws; faster than waiting for future draws; requires explicit DB-write authorization and inherits P224B gates.
3. **Passive monitoring** — wait for >=300 new DAILY_539 draws, then recheck survivor per P224B protocol.

For any new research task, include:

- Canonical repo / branch / HEAD / DB baseline STOP guards
- Forbidden path guards
- Allowed write files (narrow)
- Required read-only checks
- Inherit P221F anti-overfit gate (pre-register windows and baselines before any scan)
- No DB / production / registry write unless explicitly authorized
- Required Completion Check
