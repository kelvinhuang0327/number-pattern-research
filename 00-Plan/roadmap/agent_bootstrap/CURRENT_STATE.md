# Current State — LotteryNew

**Last Reviewed:** 2026-06-03 Asia/Taipei  
**State Marker:** `P210_COMPLETE_P211_HELD_BY_USER_P212_HONESTY_CORRECTION_DONE`  
**Purpose:** Project-specific state for future agents. Read this after `SHARED_AGENT_BOOTSTRAP.md` and `TASK_TEMPLATES.md`.

## Canonical Execution Context

| Item | Current State | Status |
|---|---|---|
| Project | LotteryNew | [Confirmed] |
| Canonical repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | [Confirmed] |
| Canonical branch | `main` | [Confirmed] |
| Current HEAD | `061bdc19c0a59e6948e8335b888257a1f7c521f6` | [Confirmed] |
| `origin/main` | `061bdc19c0a59e6948e8335b888257a1f7c521f6` | [Confirmed] |
| Git dir | `.git` | [Confirmed] |
| Active worker task | none | [Confirmed] |
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
| POWER_LOTTO rows | 36,104 | [Confirmed] |
| `bet_index` column | present | [Confirmed] |
| `bet_index` nulls | 0 | [Confirmed] |
| Duplicate `(lottery_type,target_draw,strategy_id,bet_index)` keys | 0 | [Confirmed] |
| Drift guard | `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS` | [Confirmed] |
| Latest known full test suite | 1097 passed / 0 failed | [Confirmed] handoff; [Unknown] not rerun on 2026-06-03 |
| Staged files | 0 | [Confirmed] |
| Commit / push in current pause state | 0 / 0 | [Confirmed] |
| Dirty worktree | existing local modifications/untracked files outside this bootstrap adoption | [Confirmed] |

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
| Shared agent bootstrap adoption | CONTENT-APPROVED by CEO 2026-06-03; GIT-RATIFICATION PENDING | Files are **untracked, never committed**; provisional reference only until user authorizes a commit (`WAITING_FOR_USER_AUTHORIZATION`). |

## Completed Milestones

- [Confirmed] Production replay DB migration complete: 54,462 rows to 94,924 rows with `bet_index` present.
- [Confirmed] PR #249 merged into `main`.
- [Confirmed] Drift guard passes against the 94,924-row baseline.
- [Confirmed] DB binaries are excluded from git-tracked source; evidence is maintained through manifests and validation checks.
- [Confirmed] P210 protocol accepted by CEO.
- [Confirmed] P211 held by user decision; no active worker task.
- [CONTENT-APPROVED, GIT-RATIFICATION PENDING] Shared bootstrap files exist under `00-Plan/roadmap/agent_bootstrap/` — content approved by CEO 2026-06-03; git-ratification NOT YET DONE (untracked, never committed); treat as provisional reference until user authorizes a commit.

## Current Blockers / Holds

- [Blocked] P211 is held by user. Do not auto-resume.
- [Blocked] No active worker task exists.
- [Risk] Worktree contains existing dirty/untracked files outside the current governance scope; future tasks must use narrow write allowlists.
- [Risk] Root-level untracked bootstrap drafts were superseded by formal `agent_bootstrap/` files and should not be relied on.
- [Unknown] Whether the P210 report artifact should be committed or remain local reference; do not assume it is source-controlled.
- [WAITING_FOR_USER_AUTHORIZATION] Agent bootstrap git-ratification: `00-Plan/roadmap/agent_bootstrap/` (SHARED_AGENT_BOOTSTRAP.md / TASK_TEMPLATES.md / CURRENT_STATE.md) are **100% untracked** — `git ls-files` and `git log` both empty for this directory. Content is CEO-approved but institutional status (git protection) = NOT YET DONE. Files can be lost by `git clean` / accidental deletion with zero git trace. Do NOT treat these files as immutable or source-controlled until a user-authorized commit completes.

## Latest User Direction / Product Intent

- Keep long-term / full-period frequency as observation, context, or warning only.
- Use mid-term 100-300 draw windows as the primary stability window.
- Use short-term 10-50 draw windows only as auxiliary / recency features, never standalone proof.
- Preserve random baseline 0.125 for POWER_LOTTO second zone.
- Preserve Bonferroni threshold 0.0125 for the four P211 scheme families unless a future approved protocol changes the test family.
- Treat NULL as a valid successful result.
- Do not treat historical replay evidence as betting advice or guaranteed predictive edge.

## Recommended Next Direction

Do not start P211 automatically. If the user gives a new direction, first create or update a single task prompt with:

- Canonical repo / branch / HEAD / DB baseline STOP guards
- Forbidden path guards
- Allowed write files
- Required read-only checks
- No DB / production / registry write unless explicitly authorized
- Required Completion Check

If the user explicitly says to start P211, use P210 as frozen reference and keep the task read-only unless separately authorized.
