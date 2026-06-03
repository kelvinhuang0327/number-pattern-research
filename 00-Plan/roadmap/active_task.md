# Active Task — Today (2026-06-03)

> **Single active task: `P225_GOVERNANCE_CLOSEOUT_SYNC` (doc-only).**
> Set by CEO Decision 2026-06-03 (P221F→P224C review, `CEO_DECISION_PARTIALLY_APPROVED`).
> P211 remains **HELD_BY_USER**. No strategy P225, no DB/registry/production write, no new research in this task.

---

## Context (verified read-only, 2026-06-03)

- HEAD == origin/main == `ebfc597` (P224C merge). Replay DB 94,924 rows (BIG 24,140 / DAILY_539 34,680 / POWER 36,104); bet_index nulls 0; dup keys 0; integrity `ok`; drift guard `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`.
- **Governance drift:** git HEAD is at P224C, but `roadmap.md §0` / `CURRENT_STATE.md` are stale at ~P216–P218. The chain **P211A / P221F / P222 / P223B / P224 / P224C is unrecorded** in the roadmap phase tables.
- **User two directions are already executed → NULL:** Direction #1 (window reframe) = P221F frozen windows (short 100/125/150, mid 500/750/1000, all-history=reference). Direction #2 (mine all-lottery × all-method) = P222 scan. Sole survivor `midfreq_fourier_2bet / DAILY_539` is fragile: clean-slice mean 0.6693 vs baseline 0.6410, one-sided **p=0.0674**, edge rests on 19 `hit_count=3` rows. → `WAIT_FOR_OOS`.
- **Stale fact to fix:** `CURRENT_STATE.md` "Latest User Direction" still says mid 100-300 / short 10-50 — wrong; should be **mid 500-1000 / short 100-150**.
- CEO-Decision.md + active_task.md were synced by the CEO in PR `p225-governance-closeout-sync`. This task covers the remaining two stale docs only.

---

## P225 — Governance Closeout Sync (record P211A–P224C; fix stale windows/metadata)

### 背景
After the P221F→P224C cross-lottery feature-discovery chain merged to main (HEAD `ebfc597`), the roadmap phase table and current-state doc were not updated. A fresh agent reading them would misjudge current state and could wrongly believe the survivor is promotable or that the active windows are 100-300/10-50.

### 目標（doc-only）
Bring two governance docs to truthful current state:
1. `00-Plan/roadmap/roadmap.md` §0.1 — add phase rows: **P211A** (second-zone bias-reduction diagnostic, NO_SIGNAL/display-only), **P221F** (cross-lottery feature-discovery protocol frozen), **P222** (scan COMPLETE, `CANDIDATES_FOUND_NEED_MORE_OOS`), **P223B** (`CANDIDATE_OOS_VALIDATION_COMPLETE`), **P224** (`SURVIVOR_NEEDS_MORE_OOS`), **P224C/P224B** (`FUTURE_OOS_MONITORING_PROTOCOL_READY`). Cite evidence paths under `outputs/research/`.
2. `roadmap.md` §0.4 — mark survivor `midfreq_fourier_2bet/DAILY_539` as **WAIT_FOR_OOS** (reopen gate: ≥300 new DAILY_539 draws, preferred 500); record user directions #1/#2 as **executed → NULL**; upgrade **3_STAR/4_STAR unmined frequency** from P3 → **P1** (7,101 draws, 0 replay rows — only unmined family).
3. `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md` — fix "Latest User Direction" windows to **mid 500-1000 / short 100-150**; bump State Marker to reflect P224C; add survivor `WAIT_FOR_OOS` to Holds.

### 允許修改範圍（narrow allowlist）
- `00-Plan/roadmap/roadmap.md`
- `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`
- (CEO-Decision.md + active_task.md already synced by CEO — do NOT re-touch.)

### 禁止修改範圍
- Any DB / `lottery_v2.db*` / registry / `production/*` / `data/*` / `runtime/*` / `logs/*`.
- Any code, recommendation logic, strategy state, or controlled-apply path.
- `CTO-Analysis.md` (CTO-owned; if CTO content needs change, note it as CTO follow-up).
- The **44 pre-existing dirty/untracked working-tree files** — leave untouched; never `git add -A` / `git add .`.
- No strategy P225, no backward-OOS replay generation, no second-zone promotion, no betting advice.

### Phase 0 Verification (must pass before editing)
- `git rev-parse --show-toplevel` == `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`
- `git rev-parse --git-dir` == `.git`
- `git rev-parse HEAD` == `git rev-parse origin/main`
- Working on a **dev branch (NOT main)** — repo hook blocks all Edit/Write on `main`.
- `git diff --cached --name-only` == empty (0 staged) before edits.
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"` == 94924
- `python3 scripts/replay_lifecycle_drift_guard.py --strict` == `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`

### STOP Conditions
- Repo/branch/HEAD/DB baseline diverges from Phase 0.
- On `main` (cannot edit — create/checkout a dev branch first; branch+commit+push authorized for THIS doc-only task only).
- Staged files exist before task, or any non-whitelisted file would be staged.
- Task would require DB/registry/production write, controlled apply, deployment, or strategy promotion.
- Any of the 44 unrelated dirty/untracked files would be added.
- Drift guard fails.

### 驗收標準
- `git diff --name-only` (vs branch base) lists **only** `00-Plan/roadmap/roadmap.md` and `00-Plan/roadmap/agent_bootstrap/CURRENT_STATE.md`.
- roadmap §0.1 contains the six new phase rows with correct classifications + evidence paths.
- CURRENT_STATE windows read mid 500-1000 / short 100-150; survivor WAIT_FOR_OOS recorded.
- Drift guard still PASS after edits.
- 0 of the 44 unrelated files staged.

### 測試指令
```bash
git rev-parse HEAD; git rev-parse origin/main
git diff --cached --name-only        # expect empty before staging
python3 scripts/replay_lifecycle_drift_guard.py --strict
git diff --name-only                 # after edits: only the 2 whitelisted docs
```
(Full pytest suite optional; if not run, report NOT RUN — do not claim PASS.)

### 輸出報告位置
PR description for branch `p225-governance-closeout-sync-roadmap` (or appended to this task record). No separate JSON required for a doc-only sync.

### Required Completion Check
1. 是否真的完成
2. 測試結果 PASS / FAIL / NOT RUN
3. 仍卡住的唯一問題
4. 修改檔案清單
5. staged / commit / push 狀態
6. 是否允許進入下一輪
7. Final Classification

### Final Classification (target)
`P225_GOVERNANCE_CLOSEOUT_SYNC_COMPLETE`

---

## Holds / Frozen (unchanged)

- **P211** short/mid-window read-only diagnostic — `HELD_BY_USER` (2026-06-02 「先暫停」). Do not auto-resume.
- **DAILY_539 survivor** `midfreq_fourier_2bet` — `WAIT_FOR_OOS`. Reopen P225-strategy only after ≥300 (preferred 500) new DAILY_539 draws AND passing P224B gates. Backward-OOS extension (4,376 old draws) is a separate **DB-write** task needing explicit authorization.
- **3_STAR/4_STAR replay-gap** (P1.1) and other P222 candidates (P2) — queued; each needs separate explicit authorization before any scan.
- Production promotion / registry / DB write / recommendation-logic change / controlled apply / betting advice — all **unauthorized / frozen**.

---

## Condensed Historical Index (all COMPLETE)

| Task ID | Final Classification | Status |
|---|---|---|
| P210 short/mid-window protocol | `..._DISCUSSION_READY` | COMPLETE (CEO-accepted) |
| P211 read-only diagnostic | — | **HELD by user** |
| P212–P216 governance ratification chain | various `..._COMPLETE` | COMPLETE + MERGED (PR #250/#251/#252) |
| P217 current-state metadata sync | — | COMPLETE (PR #253, `c8ac14c`) |
| P218 structural HEAD metadata fix | — | COMPLETE (PR #254) |
| P211A second-zone bias-reduction diagnostic | NO_SIGNAL / display-only | COMPLETE (PR #255) |
| P221F cross-lottery feature-discovery protocol | `PROTOCOL_FROZEN` | COMPLETE (PR #256) |
| P222 cross-lottery feature-discovery scan | `CANDIDATES_FOUND_NEED_MORE_OOS` | COMPLETE (PR #257) |
| P223B candidate OOS cross-year validation | `OOS_VALIDATION_COMPLETE` | COMPLETE (PR #258) |
| P224 DAILY_539 survivor deeper validation | `SURVIVOR_NEEDS_MORE_OOS` | COMPLETE (PR #259) |
| P224B/P224C survivor future-OOS monitoring | `FUTURE_OOS_MONITORING_PROTOCOL_READY` | COMPLETE (PR #260, `ebfc597`) |

Final Classification (this file): `ACTIVE_TASK_P225_GOVERNANCE_CLOSEOUT_SYNC_SET`
