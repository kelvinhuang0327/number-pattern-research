# LotteryNew — Master Roadmap (2026-05-09 Post-PR10 Recalibration)

> **Superseded on 2026-05-10:** This roadmap is now superseded by
> `00-LotteryPlan/20260510/lottery_roadmap_20260510.md`.
> Reason: PR #11 has merged the empty-state honesty P0, while the Phase 4
> required-check branch is CI-green but not PR-ready because it has no common
> history with `main`. The active P0 is now clean origin/main-based Phase 4
> branch rebuild.

**Version:** 2026-05-09 CTO post-PR10 recalibration v1.7
**Effective:** 2026-05-09
**Supersedes:** v1.6 `Post-PR9 Replay Lifecycle Recalibrated`
**Author:** CTO Agent
**Verified remote main tip:** `3a2883b27049b7fc5dc878645c872813e1a43fd8` (`docs(replay): record non-online lifecycle catalog truth inventory and population plan (#10)`)
**Final handoff branch (pushed, not merged):** `codex/final-replay-lifecycle-cto-ceo-handoff-20260509` @ `16ca95b`
**Catalog truth boundary (from PR #10):**
```text
ONLINE      = 6  canonical rows
REJECTED    = 42 archive evidence rows (NOT yet canonical)
OBSERVATION = WATCH / PROVISIONAL candidate evidence only
OFFLINE     = 0  (NO_TRUSTED_EVIDENCE — explicit)
RETIRED     = 0  (NO_TRUSTED_EVIDENCE — explicit)
```

> North star after PR #10: paperwork is closed; lifecycle truth inventory exists. The next best optimization is to convert that truth into honest user-visible UX and to start canonical promotion of the only state with abundant trusted evidence (REJECTED). No more report-only rounds. P2 is reserved by CEO for later CTO scheduling.

---

## 1. CTO Executive Decision

v1.6 made `PR #9 Merge Status Report` the P0 and `Final PR #3-#9 Handoff` the P1. Both are now closed:

```text
PR #3   MERGED  d625a38  P0 Replay Lifecycle UI
PR #4   CLOSED          contaminated diff (replaced by PR #5)
PR #5   MERGED  50a36fd  clean docs / protection restoration replacement
PR #6   MERGED  0143999  P1 Replay Lifecycle Hardening
PR #7   MERGED  cb0c937  aligned lifecycle fixture validation
PR #8   MERGED  cbe5171  multi-state lifecycle fixture validation
PR #9   MERGED  c9219d5  browser E2E CI enablement
PR #10  MERGED  3a2883b  non-online lifecycle catalog truth inventory + population plan
Final handoff: pushed to codex/final-replay-lifecycle-cto-ceo-handoff-20260509 @ 16ca95b
```

`replay-default-validation = SUCCESS`, `replay-browser-e2e-validation = SUCCESS`, `replay-dedicated-db-validation = SKIPPED / not required`. `main` protection unchanged.

The most valuable immediate optimization is now:

```text
P0 — Empty-State Honesty Implementation
```

Reason: PR #10 produced the empty-state spec. Lifecycle UI today still renders blank tabs for OFFLINE / RETIRED / OBSERVATION. Implementing honest empty-state messaging (no fake completeness, no forbidden language) is the smallest user-visible step that closes the gap CEO has been flagging since 2026-05-08.

After P0, the next action is:

```text
P1 — REJECTED Archive Evidence Canonical Promotion (governance-gated)
```

Reason: REJECTED is the only non-ONLINE state with abundant trusted evidence (42 rows). Promoting them with strict provenance (`source_path`, `reason`, `effective_date`) is the highest-ROI canonical-data move. Must be governance-reviewed and additive-only, not a schema replacement.

P2 is reserved per CEO instruction; CTO will fill at next checkpoint.

---

## 2. Roadmap Alignment Assessment

### Aligned / Completed

| Area | Assessment | Evidence |
|---|---|---|
| Replay Lifecycle UI shell | DONE | PR #3 merged |
| Clean audit trail | DONE | PR #5 merged; PR #4 closed as contaminated |
| Drift guard hardening | DONE | PR #6 merged |
| Aligned + multi-state fixture | DONE | PR #7 / PR #8 merged |
| Browser E2E CI enablement | DONE | PR #9 merged; lane SUCCESS |
| Catalog truth inventory + population plan | DONE | PR #10 merged (read-only, plan-only) |
| Final CTO/CEO handoff | DONE | branch `codex/final-replay-lifecycle-cto-ceo-handoff-20260509` @ `16ca95b` |
| Branch protection | ALIGNED | `replay-default-validation` required only |

### Misaligned / Needs Correction

| Gap | Severity | Correction |
|---|---:|---|
| v1.6 P0/P1 already DONE; roadmap not yet recalibrated | High | This v1.7 supersedes v1.6 |
| Empty-state spec written but not implemented in `index.html` | High | New P0 |
| 42 REJECTED archive rows trusted but not canonical in registry | High | New P1 |
| PR #9 fix relaxed E2E test instead of hardening DOM contract | Med | New P4 (display-contract bidirectional) |
| Forbidden-language sweep produced but not acted on | Med | New P5 |
| Lifecycle drift guard absent (regression risk on registry shape) | Med | New P3 |
| Lifecycle provenance schema design pending | Med | New P6 |
| Browser lane stability unobserved over time | Low | New P7 |
| Dedicated DB lane scripts missing (lane skipped) | Low | New P8 |
| PR #4 residue not audited | Low | New P9 |
| Branch / report sprawl | Low | New P10 |

---

## 3. Updated Completed Registry

| Item | Status | Notes |
|---|---|---|
| P0 Replay Lifecycle UI | DONE | PR #3 |
| P0 clean docs replacement | DONE | PR #5 |
| P1 Replay Lifecycle Hardening | DONE | PR #6 |
| Aligned fixture validation | DONE | PR #7 |
| Multi-state fixture validation | DONE | PR #8 |
| Browser E2E CI enablement | DONE | PR #9 |
| Lifecycle catalog truth inventory + plan | DONE-PLAN-ONLY | PR #10; no DB write, no canonical promotion |
| PR #9 merge status verification | DONE | folded into final handoff |
| Final CTO/CEO handoff (PR #3-#10) | DONE | side branch pushed |
| Empty-state honesty implementation | TODO | P0 |
| REJECTED archive canonical promotion | TODO | P1 |
| Lifecycle drift guard CI | TODO | P3 |
| Display-contract bidirectional hardening | TODO | P4 |
| Forbidden-language sweep close-loop | TODO | P5 |
| Lifecycle provenance schema (design + dry-run) | TODO | P6 |
| Browser lane stability observation | TODO | P7 |
| Dedicated DB lane scripts | TODO | P8 |
| PR #4 contaminated-diff residue audit | TODO | P9 |
| Maintenance / branch hygiene | TODO | P10 |

---

## 4. Reordered Priority Ladder (P0, P1, P2-RESERVED, P3–P10)

### P0 — Empty-State Honesty Implementation

| Item | Acceptance criteria |
|---|---|
| Implement empty-state in `index.html #replay-section` | When lifecycle filter resolves to 0 rows, UI shows honest empty-state message (no fake completeness) |
| Source spec | `outputs/replay/p0_replay_lifecycle_empty_state_spec_*.md` (from PR #10) |
| Disclaimer & forbidden-language compliance | No forbidden term per `replay_data_hygiene §4`; existing disclaimer preserved |
| API empty-array contract | `/api/replay/strategies` and `/api/replay/history` must return `[]` with `data_scope` and `lifecycle_status` echo intact for empty filters |
| Validation | `replay-default-validation` PASS unchanged; `replay-browser-e2e-validation` PASS unchanged |
| Scope | UI text + minimal API empty-payload safety only; no registry, no DB, no migration |

### P1 — REJECTED Archive Evidence Canonical Promotion

| Item | Acceptance criteria |
|---|---|
| Provenance fields | `source_path`, `reason`, `effective_date` carried for each promoted entry |
| Read-only governance review | Each of the 42 archive rows mapped to a trusted `rejected/` artifact before promotion |
| Additive-only | No existing ONLINE entry mutated; lifecycle enum unchanged |
| Validation | `replay-default-validation` PASS; coverage audit re-run after promotion |
| Forbidden-language | Promotion text scrubbed of `SIGNAL`, `提高中獎率`, `推薦投注`, etc. |

### P2 — RESERVED (CEO instruction)

CTO will populate at next checkpoint after P0/P1 closure. Candidate fill: forbidden-language sweep close-loop OR lifecycle provenance schema design, depending on what surfaces during P0/P1.

### P3 — Lifecycle Drift Guard CI

| Item | Acceptance criteria |
|---|---|
| Registry shape test | New CI test asserts `replay_strategy_registry.LIFECYCLE_STATUSES = {ONLINE, OFFLINE, REJECTED, OBSERVATION, RETIRED}` |
| API filter contract | Test asserts `/api/replay/strategies?lifecycle_status=` accepts each enum value and `[]` for missing data |
| No silent regression | Test fails if lifecycle enum or filter param disappears |
| Required check posture | New test joins `replay-default-validation` lane (required); not a new lane |

### P4 — Lifecycle Display-Contract Bidirectional Hardening

| Item | Acceptance criteria |
|---|---|
| DOM contract | Lifecycle badge DOM must always carry canonical enum value as `data-lifecycle-status` attribute, regardless of localized label |
| Test direction | E2E test asserts `data-lifecycle-status="REJECTED"` (canonical), not the Chinese label |
| Reason | PR #9 patched the test side; this hardens the source side so canonical truth is always present |
| Scope | `index.html` badge renderer + one test update; no API change |

### P5 — Forbidden-Language Sweep Close-Loop

| Item | Acceptance criteria |
|---|---|
| Sweep result triage | Each HIGH severity hit either fixed or marked `EXPECTED_BY_GOVERNANCE` with rationale |
| Lifecycle-touched files re-checked | `lottery_api/routes/replay.py`, `lottery_api/models/replay_strategy_registry.py`, `index.html #replay-section`, `outputs/replay/p0_replay_lifecycle_*` |
| Final sweep | New sweep reports `HIGH=0` after fixes; report committed read-only |

### P6 — Lifecycle Provenance Schema (Design + Dry-Run)

| Item | Acceptance criteria |
|---|---|
| Schema-additive design | `replay_strategy_registry` gains `source_evidence`, `reason`, `effective_date` (additive only) |
| Dry-run migration script | Produces migration SQL/Python; **not executed** |
| Audit trail design | Includes actor, timestamp, source path, rollback note |
| No production write | Plan only; PR contains design + script, no DB mutation |

### P7 — Browser Lane Stability Observation

| Item | Acceptance criteria |
|---|---|
| Observation log | Track `replay-browser-e2e-validation` outcome across N consecutive PRs |
| Promotion criteria draft | Define what stability evidence is needed to make the lane required |
| No required-check change yet | Stay observation-only |

### P8 — Dedicated DB Lane Implementation (Per P2 Blueprint)

| Item | Acceptance criteria |
|---|---|
| Implement `scripts/build_replay_test_fixture.py` | Deterministic synthetic SQLite fixture builder per `p2_dedicated_db_lane_blueprint_*.md` |
| Implement `scripts/run_replay_ci_db_validation.py` | Validation runner against synthetic fixture only; never touches production DB path |
| Lane stays `workflow_dispatch` only | Do NOT make required; observation only |
| No DB binary commit | `.db` files remain `.gitignore` |

### P9 — PR #4 Contaminated-Diff Residue Audit

| Item | Acceptance criteria |
|---|---|
| Diff comparison | Identify any file in PR #4 whose final content on `main` resembles PR #4 (rather than canonical PR #5) |
| Adapter / fixture / registry sweep | Confirm no silent residue in lifecycle-touched code |
| Report-only output | `outputs/replay/p9_pr4_residue_audit_<date>.md` |

### P10 — Maintenance / Cleanup / Branch Hygiene

| Item | Acceptance criteria |
|---|---|
| Authoritative report-branch index | Catalog kept vs superseded branches |
| PR #4 branch non-authoritative tag | Documented in maintenance report |
| Retention rules | Backup / report branch retention rules and owners defined |

---

## 5. Key Blockers

| Blocker | Current state | Impact | Action |
|---|---|---|---|
| Empty-state UX absent | spec exists; UI not implemented | Lifecycle UI looks broken on non-ONLINE tabs | P0 |
| 42 REJECTED archive rows non-canonical | trusted evidence unused | Lifecycle UI cannot show real REJECTED | P1 |
| Drift guard absent | registry shape unprotected | Silent regression risk | P3 |
| Display-contract one-sided | test relaxed; DOM not hardened | Future label change re-introduces mismatch | P4 |
| Forbidden-language sweep open | report exists; no action | Hygiene drift risk | P5 |
| Provenance schema undefined | no canonical fields for evidence | Cannot scale catalog beyond 42 rows | P6 |
| Browser lane stability unknown | first PASS only | Premature to promote | P7 |
| Dedicated DB lane non-functional | scripts missing | Cannot validate full DB path | P8 |
| PR #4 residue unaudited | open question | Low but real governance debt | P9 |

---

## 6. Most Important System Optimization Direction

```text
Convert PR #10 lifecycle truth into honest user-visible UX (P0),
then promote the only abundant trusted evidence (REJECTED, P1).
Stop writing reports. Start shipping the truth.
```

Why this is correct:

1. PR #10 already produced four read-only artifacts (truth inventory, population plan, empty-state spec, forbidden-language sweep). Writing more without acting is governance debt, not progress.
2. Empty-state honesty is the smallest viable change that ends the "blank tab looks like a bug" UX.
3. REJECTED canonical promotion is the only non-ONLINE state with abundant trusted evidence; ignoring it is wasted asset.
4. Drift guard (P3) and display-contract harden (P4) are cheap insurance once P0/P1 land.
5. Strategy mining, edge discovery, and active-state mutation remain off-limits.

---

## 7. Stop Rules

Hard stops remain active:

- no direct push to `main`
- no force push
- no admin override
- no DB binary commits (`*.db`, `*.db-wal`, `*.db-shm`)
- no production DB writes
- no replay generation
- no strategy mining or edge discovery
- no active strategy state mutation (including H6_gate_mk20→ew85)
- no false PASS for local browser E2E when tooling is unavailable
- no branch protection changes unless explicitly approved
- no fake or placeholder lifecycle catalog rows
- no overclaim language in lifecycle UI / API / reports

---

## 8. Latest Execution Prompt

```text
# ROLE
你是 LotteryNew 的 Empty-State Honesty Implementation Worker（P0-Empty-State Executor），向 CTO agent 回報；CTO 向 CEO 回報。

# MISSION
PR #10 已 merge，產出 outputs/replay/p0_replay_lifecycle_empty_state_spec_<date>.md 與 catalog truth inventory。
但 lifecycle UI 在切到 OFFLINE / RETIRED / OBSERVATION tab 仍是空白外觀，使用者會誤判為 bug。
本輪任務：以 PR #10 的 empty-state spec 為依據，把 honest 空狀態文案落地到 index.html `#replay-section`，並確保 API 在 0 列時回傳的 payload 仍含 `data_scope` 與 `lifecycle_status` echo。
**嚴禁偽造 catalog 資料、嚴禁新增 edge claim、嚴禁修改 active strategy state、嚴禁 production DB 寫入。**

# KNOWLEDGE GATE（強制順序）
1. wiki/README.md
2. wiki/system/governance.md
3. wiki/system/replay_data_hygiene.md      ← §3、§4 必讀（forbidden language）
4. wiki/system/validation_gates.md
5. memory/lessons.md（依 routing 取相關段）
其他 root-level *.md / archive / legacy / *_report.md 預設不讀。

# CONTEXT
remote main tip:
  3a2883b27049b7fc5dc878645c872813e1a43fd8
  docs(replay): record non-online lifecycle catalog truth inventory and population plan (#10)
catalog truth boundary（from PR #10）:
  ONLINE      = 6
  REJECTED    = 42 archive rows (NOT yet canonical — that is P1)
  OBSERVATION = WATCH / PROVISIONAL candidate evidence
  OFFLINE     = 0 (NO_TRUSTED_EVIDENCE)
  RETIRED     = 0 (NO_TRUSTED_EVIDENCE)
existing artifacts on main:
  outputs/replay/p0_replay_lifecycle_empty_state_spec_<date>.md
  outputs/replay/p0_replay_lifecycle_catalog_truth_inventory_<date>.md
  outputs/replay/p0_replay_lifecycle_forbidden_language_sweep_<date>.md
checks:
  replay-default-validation        = SUCCESS（required）
  replay-browser-e2e-validation    = SUCCESS（informational）
  replay-dedicated-db-validation   = SKIPPED（not required）
branch protection: enabled, admins enforced.

# REQUIRED INSPECTION
使用 clean worktree（避免 noisy worktree 誤包 unrelated delta）：
  cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-main-postmerge
  git fetch origin --prune
  git checkout main
  git pull --ff-only
  git status --short
  git log --oneline -5 origin/main

讀取：
  outputs/replay/p0_replay_lifecycle_empty_state_spec_*.md      ← 文案 source-of-truth
  outputs/replay/p0_replay_lifecycle_forbidden_language_sweep_*.md ← 確認新增文案合規
  index.html `#replay-section`（找 #rp-lifecycle-select、表格 render）
  lottery_api/routes/replay.py（GET /api/replay/strategies、GET /api/replay/history）
  lottery_api/models/replay_strategy_registry.py（lifecycle enum）

# PRIMARY GOAL（P0 順序，不得跳號）

P0-A  Frontend Empty-State 落地
  - 在 index.html `#replay-section` 表格 render 區塊，當 lifecycle filter 結果為 0 列時：
    a) 顯示 honest 空狀態文案（沿用 PR #10 spec 文案，**逐字採用**，不得自創）
    b) 區分 `NO_TRUSTED_EVIDENCE`（OFFLINE / RETIRED）vs `CANDIDATE_ONLY`（OBSERVATION）vs `NOT_YET_CANONICAL`（REJECTED）三種空狀態
    c) 不顯示「最佳策略」「推薦」「提高中獎率」「SIGNAL」「NO_SIGNAL」等 forbidden 詞
    d) 沿用既有 disclaimer 樣式，不引入新前端框架
  - 不得新增任何 catalog row、不得用 placeholder fake row 補齊外觀

P0-B  API Empty-Payload Safety
  - GET /api/replay/strategies?lifecycle_status=OFFLINE 回傳：
      { "strategies": [], "filter_lifecycle_status": "OFFLINE",
        "filter_lottery_type": null, "data_scope": "ALL_REPLAY_ROWS" }
  - GET /api/replay/history?lifecycle_status=OFFLINE 回傳：
      { "records": [], "filter_lifecycle_status": "OFFLINE", "data_scope": "ALL_REPLAY_ROWS",
        並保留既有 disclaimer / causal integrity 欄位 }
  - 嚴禁改變 disclaimer 文案、嚴禁改變 read-only 性質

P0-C  Browser E2E 補測
  - tests/test_replay_lifecycle_browser_e2e.py 新增測試：
    切到 OFFLINE / RETIRED tab → DOM 應含 honest empty-state 文字（直接採 PR #10 spec 中文案 substring）
    切到 OBSERVATION tab → DOM 應含 candidate-only 文字
    切到 REJECTED tab → DOM 應含「尚未 canonical 化」或 spec 指定文字
  - 若無瀏覽器 → honest SKIP，不假 PASS

P0-D  Forbidden-Language 二次掃描
  - 對 P0-A 新增的 UI 文字與 P0-B 新增的 API payload 文字，
    依 wiki/system/replay_data_hygiene §4 forbidden 詞表掃描
  - 命中即修，不命中即在報告聲明 `HIGH=0`

# REQUIRED VALIDATION
每完成一個 P0-x 步驟即執行：
  /Library/Developer/CommandLineTools/usr/bin/python3 \
    scripts/run_replay_ci_default_validation.py
Expected: 維持與 origin/main 等價的 PASS/SKIP 結構，不退步。

P0-C 完成後跑：
  pytest tests/test_replay_lifecycle_browser_e2e.py -v
無瀏覽器 → SKIP；不可假 PASS。

不執行 replay generation、不執行 strategy mining、不寫 production DB、不啟動 dedicated DB lane。

# REQUIRED REPORT
產出：
  outputs/replay/p0_replay_lifecycle_empty_state_implementation_<date>.md

報告必含：
  1. Executive Summary
  2. Files Changed（限 index.html / lottery_api/routes/replay.py / 對應測試）
  3. Empty-State 文案逐字對應 PR #10 spec 的證據
  4. API empty-payload contract 驗證
  5. Browser E2E 補測結果（PASS / SKIP）
  6. Forbidden-Language 掃描結果（HIGH=? / LOW=?）
  7. What Was Not Changed（active strategy / branch protection / DB / catalog rows）
  8. Remaining Risks
  9. Follow-up（指向 P1 REJECTED canonical promotion / P3 drift guard / P4 display-contract harden）
  10. Final Marker

# COMMIT RULES
不得 direct push main。
建立分支：
  codex/p0-replay-lifecycle-empty-state-implementation

允許 commit：
  - index.html（僅 #replay-section empty-state render）
  - lottery_api/routes/replay.py（僅 empty-payload safety；不得改 disclaimer）
  - tests/test_replay_lifecycle_browser_e2e.py（新增 empty-state 測試）
  - outputs/replay/p0_replay_lifecycle_empty_state_implementation_<date>.md

不得 commit：
  - lottery_api/models/replay_strategy_registry.py（lifecycle enum 不變）
  - 任何 catalog row 內容變動
  - *.db / *.db-wal / *.db-shm
  - 任何 active strategy state 檔
  - docs/archive/** 任何變動

Commit 訊息：
  feat(replay-ui): honest empty-state for non-online lifecycle tabs
  test(replay): cover empty-state lifecycle browser e2e
  docs(replay): record empty-state implementation report

Push branch to origin。
不得自動開 PR；等 CTO 審查後才開。

# HARD SCOPE（嚴禁）
- 不得偽造或新增任何 catalog row
- 不得 promote REJECTED archive rows（那是 P1，不是本輪）
- 不得修改 lifecycle enum
- 不得改 disclaimer / read-only 性質
- 不得 production DB 寫入
- 不得 replay generation
- 不得 strategy mining / edge discovery
- 不得 active strategy state 變動（含 H6_gate_mk20→ew85）
- 不得 force push、不得 direct push main、不得 admin override
- 不得讓 dedicated DB lane 升級為 required
- 不得新增 edge claim、不得使用 forbidden 詞

# STOP CONDITION
若 PR #10 spec 文案不存在或與 wiki forbidden-language 衝突，
立即輸出：
  INSUFFICIENT TRUSTED DATA
並指明缺哪份 spec 段落 / 哪段 routing 未授權。

# FINAL MARKER
P0_REPLAY_LIFECYCLE_EMPTY_STATE_IMPLEMENTATION_READY
```

**Final Marker:** `MASTER_ROADMAP_20260509_POST_PR10_REPLAY_LIFECYCLE_RECALIBRATED`
