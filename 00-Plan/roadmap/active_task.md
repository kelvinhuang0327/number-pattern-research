# Active Task — Today (2026-06-04)

> **No active worker task after P233C governance closeout.**
> P233B COMPLETE + MERGED (PR #277, merge commit `24f9f81`, 2026-06-04).
> P233B Final Classification: `P233B_LIFECYCLE_UNRESOLVED_NON_EXECUTABLE_STUB_UPDATE_MERGED`
> P233B result: LIFECYCLE_UNRESOLVED 20 → 0; added 20 non-executable stubs (REJECTED=12, RETIRED=8); no executable adapter added; DB unchanged 94924.
> P233C governance closeout (doc-only): `P233C_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_GOVERNANCE_CLOSEOUT_PR_OPEN`
> CEO Decision 2026-06-04: `CEO_DECISION_P233B_REGISTRY_HYGIENE_ACCEPTED_GOVERNANCE_CLOSEOUT`
> New research requires separate explicit user authorization.

---

## Context (verified read-only, 2026-06-04)

- HEAD == origin/main == `9035650` (PR #270 / P230C). Replay DB 94,924 rows (BIG 24,140 / DAILY_539 34,680 / POWER 36,104); bet_index nulls 0; dup keys 0; integrity `ok`; drift guard `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`.
- POWER_LOTTO first zone = 1–38 pick 6 (random baseline 36/38 = **0.947368**). Second zone = 1–8 pick 1 (random baseline **0.125**).
- DB-verified candidate: `midfreq_fourier_mk_3bet / POWER_LOTTO` = 4,500 rows / 1,500 draws / bet 1,2,3.
- P231A (`P231A_POWERLOTTO_REENTRY_PLAN_READY`) identified this as the **only** plausible first-zone candidate: P222 in-sample corrected-significant (Bonf q≈0.03) but **P223B cross-year unstable (2025 below baseline) → `CANDIDATE_NEEDS_MORE_OOS`, not deployable.**
- Second zone is NULL/display-only (P211A; predicted-special 0.1181 < 0.125). Must not enter scoring/recommendation.

---

## P231B — POWER_LOTTO First-Zone Backward-OOS Code Dry-Run

### 背景
P231A produced the plan + pre-registration for falsifying the only first-zone POWER_LOTTO candidate. This task runs the pre-registered backward-OOS dry-run, mirroring the proven P230A→P230B1 read-only pipeline used to reclassify the DAILY_539 survivor.

### 目標（code-only / artifact-only / ZERO DB write）
Run a read-only (`mode=ro`) backward-OOS dry-run of `midfreq_fourier_mk_3bet / POWER_LOTTO` **first-zone** hits on POWER_LOTTO draws strictly earlier than the common replay start (target `101000002`, 2012/01/05), and decide whether the candidate survives or is a historical artifact. No DB write, no replay rows, no promotion.

### Pre-Registration (frozen by P231A — do NOT change after seeing results)
- Candidate: `midfreq_fourier_mk_3bet / POWER_LOTTO`, strategy-level only.
- Primary metric: first-zone `hit_count`; baseline 36/38 = 0.947368.
- Secondary: special (second-zone) hit DISPLAYED SEPARATELY ONLY — never used for candidate scoring.
- Older window: target draws strictly earlier than 2012/01/05; report both adapter-min (P47 `MidFreqFourierMk3BetAdapter`, ~382) and conservative 100-warmup (~312) inventories.
- Success gates: mean > baseline AND CI not misleadingly below baseline AND block stability AND year/era split stability AND robustness to high-hit-tail removal AND no second-zone promotion.
- Failure gate: mean below baseline or unstable → classify `HISTORICAL_ARTIFACT_DIRECTION`, close candidate.

### 允許修改範圍（narrow allowlist）
- `scripts/p231b_powerlotto_first_zone_backward_oos_dryrun.py`
- `tests/test_p231b_powerlotto_first_zone_backward_oos_dryrun.py`
- `outputs/research/p231b_powerlotto_first_zone_backward_oos_dryrun_20260604.md`
- `outputs/research/p231b_powerlotto_first_zone_backward_oos_dryrun_20260604.json`

### 禁止修改範圍
- Any DB / `lottery_v2.db*` / registry / `production/*` / `data/*` / `runtime/*` / `logs/*`.
- Recommendation logic, strategy state, controlled-apply, registry lifecycle.
- `roadmap.md`, `CTO-Analysis.md`, `CURRENT_STATE.md`, `CEO-Decision.md` (governance sync is a separate task).
- The pre-existing dirty/untracked working-tree files — leave untouched; never `git add -A` / `git add .`.
- No new scan / feature search / window selection; no second-zone promotion; no betting advice.

### Phase 0 Verification (must pass before editing)
- `git rev-parse --show-toplevel` == `/Users/kelvin/Kelvin-WorkSpace/LotteryNew`; `--git-dir` == `.git`.
- `git rev-parse HEAD` == `git rev-parse origin/main`.
- Working on a **dev branch (NOT main)** — repo hook blocks all Edit/Write on `main`.
- `git diff --cached --name-only` == empty before edits.
- `sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"` == 94924 AND POWER_LOTTO == 36104; bet_index nulls 0; dup keys 0; integrity ok.
- `python3 scripts/replay_lifecycle_drift_guard.py --strict` == `REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`.

### STOP Conditions
- Repo/branch/HEAD/DB baseline diverges from Phase 0; on `main`; staged files exist before task.
- Any DB/registry/production write, controlled apply, deployment, or strategy promotion would be required.
- Any of the unrelated dirty/untracked files would be staged; drift guard fails.
- The candidate or gates would need to change after seeing results (pre-registration violation).

### 驗收標準
- `git diff --name-only` (vs branch base) lists **only** the 4 whitelisted P231B files.
- `dry_run=1` / `mode=ro` enforced; AST/test proves no DB write path is reachable.
- JSON parses; Markdown and JSON conclusions match; baseline 0.947368 used; second-zone reported separately.
- DB rows remain 94924 / POWER 36104; nulls 0; dup 0; integrity ok; drift guard PASS after task.
- Final classification ∈ {`P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_ABOVE_BASELINE`, `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_BELOW_BASELINE`, `P231B_BLOCKED`}.

### 測試指令
```bash
git rev-parse HEAD; git rev-parse origin/main
git branch --show-current            # must NOT be main
sqlite3 lottery_api/data/lottery_v2.db "SELECT COUNT(*) FROM strategy_prediction_replays;"  # 94924
python3 scripts/replay_lifecycle_drift_guard.py --strict
python3 -m pytest tests/test_p231b_powerlotto_first_zone_backward_oos_dryrun.py -q
git diff --name-only                 # after edits: only the 4 P231B files
```
(Full pytest suite optional; if not run, report NOT RUN — do not claim PASS.)

### 輸出報告位置
`outputs/research/p231b_powerlotto_first_zone_backward_oos_dryrun_20260604.{md,json}`
(branch e.g. `p231b-powerlotto-first-zone-backward-oos-dryrun`; branch+commit+PR authorized for THIS code-only / zero-DB-write task only, AND only after explicit user code-change authorization.)

### Required Completion Check
1. 是否真的完成
2. 測試結果 PASS / FAIL / NOT RUN
3. 仍卡住的唯一問題
4. 修改檔案清單
5. staged / commit / push 狀態
6. 是否允許進入下一輪
7. Final Classification
8. Worker是否需要強模型（YES — code semantics + leakage guard）

### Final Classification (this file)
`P231C_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_GOVERNANCE_CLOSEOUT_PR_OPEN`

---

## Holds / Frozen (unchanged)

- **DAILY_539 survivor** `midfreq_fourier_2bet` — `REJECTED_BY_BACKWARD_OOS / HISTORICAL_ARTIFACT_DIRECTION` (P230C). Do not treat as active survivor.
- **POWER_LOTTO first-zone candidate** `midfreq_fourier_mk_3bet` — `P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL`. Non-deployable. Observation-only. No promotion. No production/registry/recommendation change.
- **POWER_LOTTO second zone** — `DISPLAY_ONLY / NULL_EDGE` (P211A). Never enters scoring/recommendation.
- **3_STAR / 4_STAR** box-play — `UNDERPOWERED_NO_SIGNAL`; straight-play `BLOCKED_REINGEST_REQUIRED`.
- **P211** short/mid-window read-only diagnostic — `HELD_BY_USER` (2026-06-02 「先暫停」). Do not auto-resume.
- Production promotion / registry / DB write / recommendation-logic change / controlled apply / betting advice — all **unauthorized / frozen**.
- No active deployable candidate in any lottery after P231B, P232A scoreboard, and P233B registry hygiene. New research requires separate explicit user authorization.
- **P232A scoreboard** — `P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD_COMPLETE`. Historical evidence only. LIFECYCLE_UNRESOLVED resolved to 0 by P233B.
- **P233B registry hygiene** — `P233B_LIFECYCLE_UNRESOLVED_NON_EXECUTABLE_STUB_UPDATE_MERGED`. LIFECYCLE_UNRESOLVED 20→0. 12 REJECTED + 8 RETIRED non-executable stubs added. No executable adapter added. No deployable candidate created.

---

## Condensed Historical Index (all COMPLETE)

| Task ID | Final Classification | Status |
|---|---|---|
| P210 short/mid-window protocol | `..._DISCUSSION_READY` | COMPLETE (CEO-accepted) |
| P211 read-only diagnostic | — | **HELD by user** |
| P211A POWER_LOTTO second-zone diagnostic | NO_SIGNAL / display-only | COMPLETE (PR #255) |
| P221F cross-lottery feature-discovery protocol | `PROTOCOL_FROZEN` | COMPLETE (PR #256) |
| P222 cross-lottery feature-discovery scan | `CANDIDATES_FOUND_NEED_MORE_OOS` | COMPLETE (PR #257) |
| P223B candidate OOS cross-year validation | `OOS_VALIDATION_COMPLETE` | COMPLETE (PR #258) |
| P224 DAILY_539 survivor deeper validation | `SURVIVOR_NEEDS_MORE_OOS` | COMPLETE (PR #259) |
| P224B/P224C survivor future-OOS monitoring | `FUTURE_OOS_MONITORING_PROTOCOL_READY` | COMPLETE (PR #260) |
| P225 governance closeout sync | `..._COMPLETE` | COMPLETE (PR #261/#262) |
| P226–P227C 3_STAR/4_STAR box-play | `UNDERPOWERED_NO_SIGNAL` | COMPLETE (PR #263–#265) |
| P228 governance closeout sync | `..._COMPLETE` | COMPLETE (PR #266/#267) |
| P230A DAILY_539 backward-OOS extension plan | `..._PLAN_READY` | COMPLETE (PR #268) |
| P230B1 DAILY_539 backward-OOS code dry-run | `..._BELOW_BASELINE` | COMPLETE (PR #269) |
| P230C DAILY_539 survivor reclassification | `..._HISTORICAL_ARTIFACT` | COMPLETE (PR #270) |
| P231A POWER_LOTTO first-zone re-entry review | `P231A_POWERLOTTO_REENTRY_PLAN_READY` | COMPLETE (artifact only) |
| **P231B POWER_LOTTO first-zone backward-OOS dry-run** | **`P231B_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_DRYRUN_NULL`** | **COMPLETE (PR #272, merge commit `2beb24e`)** |
| P231C POWER_LOTTO first-zone governance closeout | `P231C_POWERLOTTO_FIRST_ZONE_BACKWARD_OOS_GOVERNANCE_CLOSEOUT_MERGED` | COMPLETE (PR #273) |
| **P232A All-catalog historical replay scoreboard** | **`P232A_ALL_CATALOG_STRATEGY_HISTORICAL_REPLAY_SCOREBOARD_COMPLETE`** | **COMPLETE (PR #274, merge commit `86d4f52`)** |
| P232B All-catalog scoreboard governance closeout | `P232B_ALL_CATALOG_SCOREBOARD_GOVERNANCE_CLOSEOUT_MERGED` | COMPLETE (PR #275) |
| **P233A Lifecycle-unresolved registry hygiene plan** | **`P233A_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_PLAN_MERGED`** | **COMPLETE (PR #276)** |
| **P233B Non-executable stub update (LIFECYCLE_UNRESOLVED 20→0)** | **`P233B_LIFECYCLE_UNRESOLVED_NON_EXECUTABLE_STUB_UPDATE_MERGED`** | **COMPLETE (PR #277, merge commit `24f9f81`)** |
| P233C Lifecycle unresolved registry hygiene governance closeout | `P233C_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_GOVERNANCE_CLOSEOUT_PR_OPEN` | IN PROGRESS (this task) |

Final Classification (this file): `P233C_LIFECYCLE_UNRESOLVED_REGISTRY_HYGIENE_GOVERNANCE_CLOSEOUT_PR_OPEN`
