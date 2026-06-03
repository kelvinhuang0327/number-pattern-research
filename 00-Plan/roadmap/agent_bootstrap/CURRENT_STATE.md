# Current State — LotteryNew

**Last Reviewed:** 2026-06-03 Asia/Taipei (P217 metadata sync)  
**State Marker:** `P210_COMPLETE_P211_HELD_BY_USER_P212_P216_GOVERNANCE_COMPLETE_REMOTE_RATIFIED`  
**Purpose:** Project-specific state for future agents. Read this after `SHARED_AGENT_BOOTSTRAP.md` and `TASK_TEMPLATES.md`.

## Canonical Execution Context

| Item | Current State | Status |
|---|---|---|
| Project | LotteryNew | [Confirmed] |
| Canonical repo | `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` | [Confirmed] |
| Canonical branch | `main` | [Confirmed] |
| Current HEAD | `6e220f244061a1be5aa8bddf7339f3139640c30d` (`Merge pull request #252`) | [Confirmed] |
| `origin/main` | `6e220f244061a1be5aa8bddf7339f3139640c30d` | [Confirmed] |
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
| P212 agent_bootstrap honesty correction | COMPLETE | CURRENT_STATE.md corrected from unqualified `adoption COMPLETE` → honest provisional state. |
| P213 agent_bootstrap git-ratification commit | COMPLETE | Commit `8d34f4c`; three bootstrap files now source-controlled on `origin/main`. |
| P214 post-ratification governance state sync | COMPLETE | `active_task.md` + `CEO-Decision.md` updated to reflect P213 completion. |
| P215 remote governance ratification (PR flow) | COMPLETE | Branch `bootstrap-governance-ratification` → PR #250 → required check passed → merged. `origin/main` = `4eb8051`. |
| P216 post-ratification roadmap/analysis doc sync | COMPLETE | CTO 2026-06-02 `roadmap.md` + `CTO-Analysis.md` committed via PR #252, merge `6e220f2`. |
| Shared agent bootstrap adoption | TRACKED / RATIFIED / COMPLETE | Files committed via `8d34f4c` and pushed to `origin/main` via PR #250 (merge `4eb8051`, 2026-06-03). All three files are now git-protected source-controlled artifacts. |

## Completed Milestones

- [Confirmed] Production replay DB migration complete: 54,462 rows to 94,924 rows with `bet_index` present.
- [Confirmed] PR #249 merged into `main`.
- [Confirmed] Drift guard passes against the 94,924-row baseline.
- [Confirmed] DB binaries are excluded from git-tracked source; evidence is maintained through manifests and validation checks.
- [Confirmed] P210 protocol accepted by CEO.
- [Confirmed] P211 held by user decision; no active worker task.
- [Confirmed] P212–P216 governance chain complete; all pushed to `origin/main` via PR #250 / PR #251 / PR #252.
- [Confirmed] Shared bootstrap files under `00-Plan/roadmap/agent_bootstrap/` are git-tracked source-controlled artifacts (committed `8d34f4c`, pushed via PR #250, merge `4eb8051`, 2026-06-03).

## Current Blockers / Holds

- [Blocked] P211 is held by user. Do not auto-resume.
- [Blocked] No active worker task exists.
- [Risk] Worktree contains existing dirty/untracked files outside the current governance scope; future tasks must use narrow write allowlists.
- [Risk] Root-level untracked bootstrap drafts were superseded by formal `agent_bootstrap/` files and should not be relied on.
- [Unknown] Whether the P210 report artifact should be committed or remain local reference; do not assume it is source-controlled.
- [Resolved] Agent bootstrap git-ratification: `00-Plan/roadmap/agent_bootstrap/` (SHARED_AGENT_BOOTSTRAP.md / TASK_TEMPLATES.md / CURRENT_STATE.md) are **git-tracked and remote-synced** — committed `8d34f4c`, pushed to `origin/main` via PR #250 (merge `4eb8051`, 2026-06-03). Files are now immutable git-protected artifacts. Treat as source-controlled.

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
