# LotteryNew — Long-term Master Roadmap (2026-2027)

**角色**: 長期系統架構與預測研究總顧問 **產出**: 可交付後續 Agent / Codex / Claude / Copilot 執行的長期 Master Roadmap **資料來源**: 嚴格遵守 Knowledge Gate（wiki/README.md → wiki/system/\* → memory/lessons.md） **產出日期**: 2026-05-03 **適用範圍**: 系統架構優化、預測研究有效性、自我學習排程

---

## 1\. Executive Summary

### 一頁摘要

LotteryNew 系統目前已從「彩票預測工具」演化為「具備 Orchestrator / Worker / LLM Governance / Outcome Recording / Rollback Guard」的多層自治平台。經 v2 predict-vs-actual SOP 驗證後，三款遊戲（big\_lotto、power\_lotto、daily\_539）在 Bonferroni \+ BH-FDR 校正後皆為 **NO SIGNAL**，且 randomness audit verdict 為 `WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION`。這不是系統失敗，而是科學上的有效結論——它本身就是這套方法論最大的資產。

### 最重要的三個問題

1. **方法論資產 \> 預測結果本身**: predict-vs-actual v2、permutation null、circular-match bias detector、multi-window 校正等工具，**遠比任何「彩票預測模型」更有遷移價值**。系統定位應從「lottery predictor」轉為「statistical research framework」。  
2. **Orchestrator 已具備自治輪廓但仍缺 evidence-driven planner**: 目前 Planner 多依賴 backlog / 人工判斷，尚未從 evidence（failed tests、stale data、pending outcomes、NO SIGNAL audit）自動產生任務。  
3. **Production mutation safety 已建立但需固化**: H6 daily\_539 false rollback、`MIN_OUTCOMES_FOR_ROLLBACK = 5` 補丁、`--confirm-production-outcome` 雙確認流程，這些 guard 必須升格為「平台級不可繞過 invariant」，而非散落於 script。

### 建議優先順序

1. **保護現有資產**（Phase 0 Stabilize）—— 讓 H6 rollback guard、no-audit-no-call、outcome dry-run 變成「平台 invariant」。  
2. **抽象出 backtest framework**（Phase 2 / 4）—— 把 v2 predict-vs-actual、permutation null、circular-bias detector 拉成 `tools/backtest_framework/`，做為遷移到 Stock/Betting 的核心。  
3. **建立 EvidenceCollector \+ Local Planner**（Phase 3）—— 讓系統從外部 LLM 依賴轉為 evidence 驅動的本地決策。  
4. **隨機性 audit 結案**（Phase 2）—— 給三款彩票最終科學裁定，避免無限重複研究低 ROI 方向。  
5. **Stock / Betting 遷移**（Phase 4）—— 在 Phase 2 完成後啟動，以 backtest framework 為核心。

### 90 天目標

- Phase 0 \+ 50% Phase 1 完成: 已知 production 風險固化、Orchestrator 模組邊界整理、UI Dashboard 收斂為單入口、單一 source-of-truth 確立。  
- Randomness Audit 三款彩票結論定調，產出 final verdict 文件（給彩票研究封項）。  
- LLM Governance: per-role / per-provider / per-task 配額落實，每日 Copilot/Claude/Codex 用量可在 Dashboard 視覺化。

### 6 個月目標

- Phase 1 \+ Phase 2 完成: 模組化重構 70%、Strategy Evaluation Framework v1 上線、Multiple Testing Registry 上線、OOS framework 自動化。  
- `tools/backtest_framework/` v0.1 釋出（pip-installable / 單獨 git submodule）。  
- 前 5 個 Stock / Betting POC 開始試跑，使用同一份 backtest framework。

### 12 個月目標

- Phase 3 \+ Phase 4 完成: EvidenceCollector \+ Local Planner 上線；外部 LLM 用量降至 \< 30% 任務數。  
- Stock / Betting 遷移落地，至少一個 domain 完成 walk-forward OOS 驗證並有可重現結論。  
- 彩票研究進入 maintenance-only 模式，僅保留 randomness audit 與 advisory；研發資源轉向 transferable framework。

---

## 2\. Current State Assessment

### 2.1 Architecture（架構）

**優勢**:

- Orchestrator 已分層: Planner / Worker / Light Worker / CTO / Copilot-Daemon，邊界相對清楚。  
- DB 表已有 `agent_tasks`, `active_strategy_state`, `strategy_reviews`, `strategy_live_state`, `llm_audit_events` 等核心 schema。  
- Knowledge Gate 已建立: wiki 為唯一入口，governance.md 強制執行。

**弱點**:

- `runtime/agent_orchestrator/` 與 `orchestrator/` 兩條路徑並存，邊界仍可能混淆。  
- 無正式 schema versioning：DB 修改靠手動 migration script。  
- API 散落（monitoring API、usage API、task API），缺單一 BFF（backend-for-frontend）層。  
- UI Dashboard 多入口：`monitoring_status.md`、`/api/strategy-states`、`/api/next-draw-summary`、Copilot-Daemon Dashboard 各自顯示，缺單一視圖。  
- Script-to-platform 邊界模糊：很多 production 行為仍以 script \+ 人工 confirm 方式執行（H6 outcome、rollback restore）。

### 2.2 Prediction Research（預測研究）

**優勢**:

- predict-vs-actual v2 已成 SOP，v1 已 INVALID。  
- multi-window（150/500/1500）+ permutation \+ Bonferroni \+ BH-FDR 已作為強制標準。  
- T0\_IDEA → T4\_DEPLOYABLE 五層 promotion gate 已建立，避免跳階晉級。  
- memory/lessons.md 已累積 27+ 條教訓，涵蓋 SHORT\_MOMENTUM / LATE\_BLOOMER 識別、Bonferroni 校正、circular-match bias 等。  
- Randomness audit script 已存在，最近一次 verdict `WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION`。

**弱點**:

- 三款彩票 verdict 為 NO SIGNAL，但仍有 ADVISORY\_ONLY 策略持續被監控，未做正式「研究封項」決定。  
- 沒有 Multiple Testing Registry：每次 grid search 都需重複校正，無集中記錄。  
- Walk-forward OOS 已有概念但未自動化（每次驗證仍需手動跑）。  
- Circular-bias detector 為手動 SOP，不是 CI gate。

### 2.3 Scheduling / Agent

**優勢**:

- Planner 已有 monitoring 自動降級邏輯（REPLACE\_WITH\_MONITORING）。  
- AUTO-MONITOR prompt contract 已定義（須查 4 個 DB table、三彩種規則、watchdog rules）。  
- dedupe\_key 已定 UTC \+ local 規則。

**弱點**:

- Planner 並非 evidence-driven：缺 EvidenceCollector，多依賴 backlog 與 LLM。  
- 無 task scoring formula：任務優先度靠人工排。  
- 失敗分類（failure\_category）已記錄，但 feedback loop 未自動化（失敗 → lesson → guard → next task）。  
- Stale RUNNING lock 風險：worker 進程死亡後鎖無自動釋放保證。

### 2.4 Monitoring / Rollback

**優勢**:

- H6 false rollback 已修補：`MIN_OUTCOMES_FOR_ROLLBACK = 5`、`MIN_CONSECUTIVE_NEGATIVE_FOR_EARLY_ROLLBACK = 3`、`EARLY_ROLLBACK_SAMPLE_SIZE = 30`。  
- restore script 存在且需 `--confirm-production-outcome`。  
- AUTO-MONITOR 支援 OK / WATCH / ESCALATE / DEGRADED 四級。

**弱點**:

- Rollback guard 為 constants in script，非 config-managed feature flag，難以測試。  
- 無 rollback simulation（dry-run rollback 不寫 DB）。  
- Drift score 與 consecutive\_losses 閾值散落於 monitor 程式，需固化為 governance config。

### 2.5 LLM Governance

**優勢**:

- Audit ATTEMPT 已強制：no-audit-no-call。  
- Per role / runner / provider / task 用量可追蹤。  
- Top tasks by LLM calls / Recent LLM Calls Dashboard 已存在。  
- Safe-run / Hard-off / Scheduler enabled-disabled 已有 toggle。

**弱點**:

- 配額（per role / per provider / hourly / daily cap）目前多為 default，不是 enforced policy。  
- Token / premium / rate limit parser 未統一介面（Claude/Codex/Copilot 各自解析）。  
- Copilot 用量視覺化已有，但 alert（超量警告）尚未自動化。

### 2.6 UI / Observability

**優勢**:

- Dashboard 已有 LLM usage、Copilot focus、active/shadow strategy。  
- `outputs/monitoring_status.md` 為 AUTO-MONITOR 標準產物，七節結構固定。

**弱點**:

- 多 Dashboard 並存，無統一 navigation。  
- Predict-vs-actual 結果 / Randomness audit 結果 / strategy lifecycle 視圖缺失。  
- Pending outcomes、rollback guard status、self-learning score changes 缺對應 UI。

### 2.7 Testing

**優勢**:

- predict-vs-actual v2 有 dry-run、isolated DB write test。  
- Outcome recording 已有三段 gate（dry-run → isolated DB → production with confirm）。

**弱點**:

- 缺 unit test pyramid（多為 integration / script test）。  
- 無 historical data validation regression suite（schema 漂移容易漏檢）。  
- 缺 no-production-mutation test 自動跑（CI 沒有 hook）。

### 2.8 Data Pipeline

**優勢**:

- `data/<game>_draws_full.csv` 為 source-of-truth；`predictions/retro/` 為 retro prediction 標準路徑。  
- causal slicing 已實作於 `scripts/retro_predictions.py`。

**弱點**:

- Data freshness check 不是 governance-enforced（stale data 風險仍在）。  
- 多份 derived data（feature matrix、feature\_library）缺版本管理。

---

## 3\. North Star Architecture

### 3.1 模組圖（文字描述）

                          ┌─────────────────────────┐

                          │   UI Dashboard (Single) │

                          │   \- System Health        │

                          │   \- Tasks                │

                          │   \- LLM Usage            │

                          │   \- Strategies           │

                          │   \- Backtest             │

                          │   \- Outcomes             │

                          │   \- Self-learning Score  │

                          └────────────┬────────────┘

                                       │ BFF API (single entry)

                                       ▼

   ┌────────────────────────────────────────────────────────────┐

   │                    Orchestrator (Control Plane)             │

   │  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌─────────┐  │

   │  │  Local    │  │  Worker   │  │  Light    │  │  CTO    │  │

   │  │  Planner  │  │  (Codex/  │  │  Worker   │  │ Review  │  │

   │  │ (no LLM)  │  │   Claude) │  │ (Audit/   │  │(LLM ro) │  │

   │  │           │  │           │  │ monitoring│  │         │  │

   │  └───────────┘  └───────────┘  └───────────┘  └─────────┘  │

   │         ▲              ▲              ▲             ▲       │

   │         │ evidence     │ tasks        │ tasks       │       │

   │  ┌──────┴──────┐  ┌────┴──────┐  ┌────┴──────┐  ┌───┴────┐ │

   │  │  Evidence   │  │   Task    │  │  Failure  │  │ LLM    │ │

   │  │  Collector  │  │  Scorer   │  │  Taxonomy │  │Governor│ │

   │  └─────────────┘  └───────────┘  └───────────┘  └────────┘ │

   └─────────────────────────────────────────────────────────────┘

                                       │

                                       ▼

   ┌──────────────────────────────────────────────────────────────┐

   │                    Domain Plane                                │

   │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │

   │  │  Strategy    │  │  Backtest    │  │ Outcome Recorder   │ │

   │  │  Engine      │  │  Engine      │  │ (dry-run gated)    │ │

   │  │  (v2 SOP)    │  │  (multi-win) │  │                    │ │

   │  └──────────────┘  └──────────────┘  └────────────────────┘ │

   │  ┌──────────────┐  ┌──────────────┐  ┌────────────────────┐ │

   │  │  Randomness  │  │  Multiple    │  │ Rollback Guard     │ │

   │  │  Audit       │  │  Testing     │  │ (config-managed,   │ │

   │  │              │  │  Registry    │  │  simulatable)      │ │

   │  └──────────────┘  └──────────────┘  └────────────────────┘ │

   └──────────────────────────────────────────────────────────────┘

                                       │

                                       ▼

   ┌──────────────────────────────────────────────────────────────┐

   │                    Data Plane                                  │

   │  draws / predictions / outcomes / strategy\_states /            │

   │  agent\_tasks / llm\_audit\_events / backtest\_results /           │

   │  randomness\_audit\_results / method\_validation\_results          │

   │  \+ schema\_versions (canonical) \+ feature\_library\_versions      │

   └──────────────────────────────────────────────────────────────┘

                                       │

                                       ▼

   ┌──────────────────────────────────────────────────────────────┐

   │           tools/backtest\_framework/ (Transferable)             │

   │   permutation\_null  │  walk\_forward\_oos  │  bh\_fdr\_corr        │

   │   circular\_bias\_detector │ multi\_window  │  effect\_size        │

   │   leakage\_detector       │ preregistered\_hypothesis\_registry   │

   └──────────────────────────────────────────────────────────────┘

### 3.2 資料流

draws (csv)

   │

   ├─► retro\_predictions.py (causal slicing) ──► predictions/retro/\*.json

   │                                                         │

   │                                                         ▼

   │                                            predict\_vs\_actual.py (v2)

   │                                                         │

   │                                                         ▼

   │                                             predict\_vs\_actual results

   │                                       (multi-window \+ perm \+ Bonferroni \+ BH-FDR)

   │

   ├─► randomness\_audit.py ──► randomness\_audit\_results

   │

   └─► live prediction ──► live\_strategy\_predictions

                                  │

                                  ▼

                      (next\_draw triggers outcome flow)

                                  │

                                  ▼

                     outcome\_recorder (dry-run → isolated → production confirm)

                                  │

                                  ▼

                     live\_strategy\_outcomes / strategy\_live\_state

                                  │

                                  ▼

                     rollback\_guard (config-managed thresholds)

                                  │

                                  ▼

                     active\_strategy\_state (no auto-mutation)

### 3.3 任務流

Evidence Sources (failed tests, stale data, pending outcomes, NO SIGNAL audit, ...)

     │

     ▼

EvidenceCollector ──► EvidenceItem (source, severity, confidence, dedupe\_key, suggested\_task\_type, requires\_llm=false)

     │

     ▼

TaskScorer (severity × confidence × impact / risk × LLM\_cost) ──► priority lane

     │

     ▼

Local Planner (no external LLM) ──► tasks/\<date\>/QUEUED tasks

     │

     ├─► Light Worker (audit / monitoring / no-LLM)

     ├─► Worker (Codex / Claude with LLM Governor caps)

     └─► CTO Review (LLM read-only)

     │

     ▼

Task Outcome ──► failure\_taxonomy / lessons\_update / next-iteration evidence

### 3.4 LLM 呼叫流

任務需要外部 LLM

   │

   ▼

LLM Governor ── pre-call check ───┐

   │                              │

   ├─ per-role cap ────────┐      │

   ├─ per-provider cap ────┤      │

   ├─ per-task retry cap ──┤      │

   ├─ hourly / daily cap ──┘      │

   ├─ hard-off check              │

   │                              │

   ▼                              ▼

audit ATTEMPT ──► llm\_audit\_events (FORCED before call)

   │

   ▼ (only if attempt logged)

external LLM call (Claude / Codex / Copilot)

   │

   ▼

audit RESULT ──► llm\_usage\_events

   │

   ▼

Top-tasks dashboard / Copilot focus dashboard

### 3.5 Outcome Recording 流

draw event detected

   │

   ▼

startup catch-up (pending outcome detection)

   │

   ▼

dry-run outcome recording (no DB write)

   │

   ▼ (if dry-run pass)

isolated DB write test (sandbox DB)

   │

   ▼ (if isolated pass)

production write GUARDED:

   \- requires \--write

   \- requires \--confirm-production-outcome

   \- records audit event before write

   \- inserts into live\_strategy\_outcomes

### 3.6 Rollback 流

strategy\_live\_state changed

   │

   ▼

rollback\_guard check (config-managed):

   \- outcome\_count \>= MIN\_OUTCOMES\_FOR\_ROLLBACK (default 5\)

   \- if early rollback considered:

     \- consecutive\_negative \>= MIN\_CONSECUTIVE\_NEGATIVE\_FOR\_EARLY\_ROLLBACK (3)

     \- sample size \>= EARLY\_ROLLBACK\_SAMPLE\_SIZE (30)

   │

   ▼ (if guard PASS)

rollback proposal ──► CTO review (manual approve)

   │

   ▼ (manual approve only)

restore script with backup

   │

   ▼

audit event \+ active\_strategy\_state update

### 3.7 Self-learning 流

Task completed (success or fail)

   │

   ▼

outcome\_logger ──► task\_outcomes table

   │

   ▼

failure\_taxonomy update (if FAILED)

   │

   ▼

lessons\_update (if pattern recognized)

   │

   ▼

EvidenceCollector ingests new lesson as evidence

   │

   ▼

Next planner cycle picks up evidence ──► task scoring updated

---

## 4\. Long-term Roadmap

### Phase 0 — Stabilize / Safety（Month 0–1）

**Goal**: 鎖死目前已知 production 風險，把 H6 patch、no-audit-no-call、outcome dry-run 從 script-level 升格為平台 invariant。

**Deliverables**:

- D0.1 Rollback Guard config-managed module (`orchestrator/governance/rollback_guard.py`)，支援 simulation mode（不寫 DB）  
- D0.2 Outcome Recorder 標準介面（dry-run → isolated → production with confirm），所有 game 統一走此介面  
- D0.3 LLM no-audit-no-call enforcement test（CI 跑「拿掉 audit 就應該 raise」）  
- D0.4 Restore script with backup tested in dry-run，含 rollback simulation report  
- D0.5 Stale RUNNING lock detector \+ auto-release（worker pid dead → unlock）

**Files / Modules Affected**:

- `orchestrator/db.py`, `orchestrator/worker_tick.py`  
- `scripts/restore_*.py`  
- `tests/test_rollback_guard.py`（新）  
- `tests/test_no_audit_no_call.py`（新）  
- `wiki/system/stability_audit.md`（更新 governance 段）

**Risks**:

- Rollback guard 重構誤差可能誤觸發 / 失靈：須用 simulation mode 平行跑 30 天驗證一致性。  
- 若 CI 強制 no-audit-no-call，現有 test 可能 break：需 grep 全檔。

**Acceptance Criteria**:

- ✅ 所有 production write 路徑都有 audit ATTEMPT 紀錄（CI gate）  
- ✅ rollback simulation 與 actual rollback 結果在 30 天 hist data 上 100% 一致  
- ✅ stale lock 自動釋放在 mock crash 測試通過  
- ✅ outcome recorder 三段 gate 100% coverage

**Suggested Prompts for Execution Agents**:

ROLE: Phase 0 stabilization worker.

TASK: Refactor scripts/h6\_rollback\_\*.py into orchestrator/governance/rollback\_guard.py 

with config-managed thresholds. Add simulation mode (no DB write).

STRICT RULES:

\- Do not change production thresholds

\- Do not call external LLM

\- All thresholds must be readable from config, not hardcoded

ACCEPTANCE: tests/test\_rollback\_guard.py passes including simulation mode test.

EXPECTED VERDICT: PASS / FAIL with diff summary.

---

### Phase 1 — Architecture Consolidation（Month 1–3）

**Goal**: 模組化 / API 收斂 / Schema versioning / Single source of truth。

**Deliverables**:

- D1.1 Module boundary 定義文件（`wiki/system/module_boundaries.md`）：Orchestrator / Strategy Engine / Backtest Engine / Outcome Recorder / LLM Governance / UI 各自接口  
- D1.2 BFF API 層（`api/bff.py`）：UI 只透過此入口，不直接讀 DB  
- D1.3 Schema versioning 機制（`schemas/v{N}/`，migrations 集中管理）  
- D1.4 Config management 統一（`config/{env}.yaml` \+ `pydantic` settings）  
- D1.5 Feature flags（`config/feature_flags.yaml`）：safe-run、hard-off、scheduler enabled、自動 outcome write 預設 OFF  
- D1.6 UI Dashboard 收斂為單入口（`ui/index.html` 帶 nav，子頁面 mount）  
- D1.7 idempotency / dedupe key normalization（依 `wiki/system/orchestrator.md` Date Label Convention）

**Files / Modules Affected**:

- `orchestrator/` 整體  
- `api/` 新增 BFF  
- `schemas/` 新建  
- `config/` 重整  
- `ui/` 重整 nav

**Risks**:

- BFF 重構期間舊 API 並行運轉，需 dual-read 階段。  
- Schema versioning 引入後舊 migration 需追溯標記。

**Acceptance Criteria**:

- ✅ UI Dashboard 所有資料只走 BFF API  
- ✅ 所有 DB 修改要過 schema migration script  
- ✅ feature\_flags.yaml 所有 toggle 有對應 test  
- ✅ no orphaned config: every config key referenced in code, no stale keys  
- ✅ wiki/system/module\_boundaries.md 為 routing 入口

---

### Phase 2 — Scientific Validation（Month 3–6）

**Goal**: Randomness Audit 結案、Strategy Evaluation Framework v1、Multiple Testing Registry、Walk-forward OOS 自動化、Circular-bias Detector CI 化。

**Deliverables**:

- D2.1 Randomness Audit final verdict 文件（`wiki/system/randomness_final_verdict.md`），三款彩票各自結論  
- D2.2 Strategy Evaluation Framework v1（`tools/strategy_eval/`）：multi-window \+ permutation \+ Bonferroni \+ BH-FDR \+ walk-forward OOS 一鍵跑  
- D2.3 Multiple Testing Registry（`registry/hypotheses.jsonl`）：每個 hypothesis 預先註冊，禁止 post-hoc 校正豁免  
- D2.4 Circular-bias Detector CI gate（`tests/test_no_circular_match.py`）  
- D2.5 Leakage Detector（`tools/leakage_detector.py`）整合進 RollingBacktester  
- D2.6 Strategy retire policy 文件化（連續 N 期 NO SIGNAL → retire to `rejected/`）

**Files / Modules Affected**:

- `scripts/randomness_audit.py`（持續）  
- `scripts/predict_vs_actual.py`（v2 已存在，整合進 framework）  
- `tools/strategy_eval/`（新）  
- `registry/`（新）  
- `wiki/system/strategy_retire_policy.md`（新）

**Risks**:

- Hypothesis registry 增加流程負擔；要設計輕量 cli。  
- Circular-bias detector 過嚴可能 false-positive：需 tunable confidence。

**Acceptance Criteria**:

- ✅ 三款彩票 randomness audit 最終 verdict 寫入 wiki，且每月自動回測 1 次  
- ✅ strategy\_eval CLI 可一鍵跑完 multi-window \+ perm \+ Bonferroni \+ BH-FDR \+ WF OOS  
- ✅ 任何新 hypothesis 必須先 `register --hypothesis-id` 才允許跑驗證  
- ✅ CI 有 test\_no\_circular\_match.py，預設 fail on suspicious patterns

---

### Phase 3 — Self-learning Scheduler（Month 6–9）

**Goal**: EvidenceCollector \+ Local Planner \+ Task Scoring \+ Failure Taxonomy \+ Feedback Loop。

**Deliverables**:

- D3.1 EvidenceCollector module (`orchestrator/evidence/collector.py`)：18 種 evidence source（failed tests, stale data, missing outcomes, NO SIGNAL, monitoring degraded, LLM overuse, ...）  
- D3.2 EvidenceItem schema（source / severity / confidence / affected\_module / evidence\_text / suggested\_task\_type / expected\_impact / requires\_llm=false / dedupe\_key / acceptance\_criteria）  
- D3.3 Task Scoring formula module (`orchestrator/scoring.py`)  
- D3.4 Local Planner v2（`orchestrator/local_planner.py`）：predominantly evidence-driven，外部 LLM 僅在 explicit escalation  
- D3.5 Failure Taxonomy registry (`registry/failure_taxonomy.jsonl`)  
- D3.6 Lessons auto-update hook：repeated failures → guard  
- D3.7 Daily caps / forced exploration lanes / monitoring lanes 配置化

**Files / Modules Affected**:

- `orchestrator/planner_tick.py`（重構）  
- `orchestrator/evidence/`（新）  
- `orchestrator/scoring.py`（新）  
- `registry/failure_taxonomy.jsonl`（新）  
- `memory/lessons.md`（auto-append hook）

**Risks**:

- Evidence scoring 太敏感 → 任務洪水。需 daily cap \+ dedupe。  
- Local Planner 沒有 LLM → 任務生成多樣性下降。需 forced exploration lane。

**Acceptance Criteria**:

- ✅ 連續 30 天 Local Planner 任務佔比 \> 70%（外部 LLM tasks \< 30%）  
- ✅ failure\_taxonomy 有至少 12 類，每類有對應 guard 與 mitigation  
- ✅ 任務 dedupe 達 95% 以上（同一 evidence 不重複建任）

---

### Phase 4 — Transferable Framework（Month 9–12）

**Goal**: 把 backtest framework 抽象成獨立 package，遷移到 Stock / Betting POC。

**Deliverables**:

- D4.1 `tools/backtest_framework/` v0.1：generic backtest engine  
  - `permutation_null.py`  
  - `walk_forward_oos.py`  
  - `multi_window.py`  
  - `bh_fdr.py`  
  - `bonferroni.py`  
  - `circular_bias_detector.py`  
  - `leakage_detector.py`  
  - `effect_size.py`  
  - `hypothesis_registry.py`  
- D4.2 Generic Strategy Interface（`Strategy(history) -> List[Bet]`）抽象到 framework  
- D4.3 POC: Stock backtest（`apps/stock_poc/`），用同一份 framework  
- D4.4 POC: Sports Betting backtest（`apps/betting_poc/`）  
- D4.5 Documentation: `tools/backtest_framework/README.md`，含 lottery vs stock 對應 mapping  
- D4.6 Public API freeze（v1）：semantic versioning、changelog

**Files / Modules Affected**:

- 新 directory `tools/backtest_framework/`  
- 新 directory `apps/stock_poc/`、`apps/betting_poc/`

**Risks**:

- 抽象太早 → 介面不穩。先用兩個 domain 驗證後再 freeze。  
- 跨 domain config 漂移：需 sample data 與 schema spec。

**Acceptance Criteria**:

- ✅ Stock POC 用 framework 完成至少 3 個 hypothesis 的 walk-forward OOS  
- ✅ Betting POC 用 framework 完成至少 3 個 hypothesis 的 walk-forward OOS  
- ✅ Framework public API 通過 lottery / stock / betting 三 domain 共用驗證  
- ✅ Framework 在 lottery 上 reproduces v2 predict-vs-actual NO SIGNAL 結論

---

### Phase 5 — Long-term Research（Month 12+）

**Goal**: payout EV、unpopular-number EV、physical bias candidate detection、covering design、cross-domain。彩票進入 maintenance-only。

**Deliverables**:

- D5.1 Payout EV analysis: jackpot sharing risk × probability of hit；unpopular-number model（即使無 prediction signal，少人買號可能提高 expected payout）  
- D5.2 Covering design module: wheel system / 最小 bet 集合 maximize coverage  
- D5.3 Physical bias candidate detection（per-ball frequency drift、特定球出現異常）—— 但僅 advisory，no betting recommendation  
- D5.4 Cross-domain transfer plan: Novel-writing tools / A-B testing framework / marketing experiments 套同一 evidence-driven workflow  
- D5.5 Lottery research formal sunset 文件（若 verdict 持續 NO SIGNAL）

**Acceptance Criteria**:

- ✅ Payout EV model 對至少 3 期實際開獎有 walk-forward 評估  
- ✅ Cross-domain POC（Novel / A-B testing）至少完成 1 個  
- ✅ 若三款彩票 12 個月內 randomness audit 持續無偏差 → 進入 sunset

---

## 5\. Program Backlog（30+ items）

| ID | Workstream | Task | Priority | Expected ROI | Risk | LLM Needed? | Acceptance Criteria |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| P0-01 | Safety | Refactor rollback guard 為 config-managed module | P0 | High | Med | No | tests/test\_rollback\_guard.py 通過 \+ simulation mode |
| P0-02 | Safety | Outcome recorder 三段 gate 統一介面 | P0 | High | Med | No | 所有 game 走相同 interface |
| P0-03 | Safety | CI gate: no-audit-no-call enforcement | P0 | High | Low | No | tests/test\_no\_audit\_no\_call.py 通過 |
| P0-04 | Safety | Stale RUNNING lock auto-release | P0 | Med | Low | No | mock crash test 通過 |
| P0-05 | Safety | Restore script dry-run / backup test | P0 | High | Low | No | dry-run rollback simulation 與 prod 100% 一致 |
| P1-01 | Architecture | Module boundary doc | P1 | Med | Low | No | wiki/system/module\_boundaries.md 上線 |
| P1-02 | Architecture | BFF API layer | P1 | High | Med | No | UI 只透過 BFF |
| P1-03 | Architecture | Schema versioning \+ migration registry | P1 | High | Med | No | schemas/v{N}/ \+ CI migration test |
| P1-04 | Architecture | Config management (pydantic) | P1 | Med | Low | No | config/{env}.yaml \+ 100% coverage |
| P1-05 | Architecture | Feature flags 統一 | P1 | High | Low | No | safe-run/hard-off 為 flag-driven |
| P1-06 | Architecture | UI Dashboard 收斂單入口 | P1 | High | Med | No | ui/index.html 為唯一入口 |
| P1-07 | Architecture | Dedupe key normalization (UTC) | P1 | Med | Low | No | 全 codebase grep 通過 |
| P2-01 | Validation | Randomness audit final verdict per game | P1 | High | Low | No | wiki/system/randomness\_final\_verdict.md |
| P2-02 | Validation | Strategy Evaluation Framework v1 | P1 | High | Med | No | tools/strategy\_eval CLI 一鍵跑 |
| P2-03 | Validation | Multiple Testing Registry | P1 | High | Low | No | registry/hypotheses.jsonl \+ CLI |
| P2-04 | Validation | Circular-bias detector CI gate | P1 | High | Low | No | CI test 通過 |
| P2-05 | Validation | Leakage detector 整合 RollingBacktester | P1 | High | Med | No | DataLeakageError on offending input |
| P2-06 | Validation | Strategy retire policy doc \+ auto-trigger | P2 | Med | Low | No | strategies/{name} 連續 N 期 NO SIGNAL → moved |
| P2-07 | Validation | Walk-forward OOS 自動化 | P1 | High | Med | No | strategy\_eval 自動跑 WF OOS |
| P3-01 | Self-learning | EvidenceCollector module | P1 | High | Med | No | 18 種 evidence source 落地 |
| P3-02 | Self-learning | EvidenceItem schema | P1 | High | Low | No | schema 在 db \+ json schema 驗證 |
| P3-03 | Self-learning | Task Scoring formula | P1 | High | Med | No | 連續 30 天 task score 分布合理 |
| P3-04 | Self-learning | Local Planner v2 | P1 | High | High | No | 外部 LLM tasks \< 30% |
| P3-05 | Self-learning | Failure Taxonomy registry | P2 | High | Low | No | 12+ 類別 \+ mitigation |
| P3-06 | Self-learning | Lessons auto-update hook | P2 | Med | Low | No | repeated failure → guard 自動產生 |
| P3-07 | Self-learning | Daily caps / forced exploration lanes | P2 | Med | Low | No | config-managed lane setting |
| P4-01 | Framework | tools/backtest\_framework/ v0.1 | P2 | Very High | Med | No | 9 modules \+ tests |
| P4-02 | Framework | Generic Strategy interface 抽象 | P2 | Very High | Med | No | lottery / stock / betting 通用 |
| P4-03 | Framework | Stock POC | P2 | High | Med | No | 3+ hypotheses WF OOS |
| P4-04 | Framework | Betting POC | P2 | High | Med | No | 3+ hypotheses WF OOS |
| P4-05 | Framework | Documentation \+ semver freeze | P3 | High | Low | No | README \+ CHANGELOG \+ v1 tag |
| P5-01 | Research | Payout EV / unpopular-number model | P3 | Med | Low | No | 3 期 WF 評估 |
| P5-02 | Research | Covering design module | P3 | Low | Low | No | wheel system reference impl |
| P5-03 | Research | Physical bias candidate (advisory) | P3 | Low | Low | No | per-ball drift Dashboard |
| P5-04 | Research | Cross-domain POC: Novel / A-B testing | P3 | Med | Med | No | 1+ POC 完成 |
| GOV-01 | Governance | Per-role / per-provider LLM caps enforcement | P1 | High | Low | No | 超量自動 hard-off |
| GOV-02 | Governance | Token / premium / rate limit unified parser | P2 | Med | Low | No | 三 provider 共用 |
| GOV-03 | Governance | Copilot overuse alert | P2 | Med | Low | No | 超 80% daily cap → notify |

---

## 6\. Prediction Research Plan

### 6.1 短期應做（0–3 個月）

- 完成 randomness audit final verdict per game。把 chi-square uniformity / per-number frequency / odd-even / high-low / consecutive / same-tail / sum / range / autocorrelation lag 1–50 / runs test / rolling drift 全跑一輪，校正後做最終結論。  
- 把 v2 predict-vs-actual 作為唯一可信方法寫進 CI（任何新策略必須跑這個）。  
- Multiple Testing Registry 啟用，禁止 post-hoc 校正豁免。  
- Circular-bias detector CI 化。

### 6.2 中期應做（3–6 個月）

- Walk-forward OOS 自動化（150 / 500 / 1500 三窗口）。  
- Strategy Evaluation Framework v1 上線。  
- Backtest framework 抽象（為長期遷移做準備）。  
- Strategy retire policy 落地：連續 N 期 NO SIGNAL → `rejected/`。

### 6.3 長期應做（6–12 個月）

- Payout EV / unpopular-number EV: 即使 hit signal NO SIGNAL，jackpot sharing 與 unpopular-number selection 仍可能提供 EV 改善。但 EV 期望仍可能 \< 0；只做 advisory，不下注決策。  
- Physical bias candidate detection：long-term per-ball frequency drift 監控。發現後 advisory only。  
- Covering design module（wheel system）：保證最小 bet 集合最大覆蓋率。

### 6.4 應停止做的方向

- ❌ 任何「historical-pool max-hit」做為預測力評估（v1 已 INVALID）。  
- ❌ 任何不通過 Bonferroni / BH-FDR 的 grid search 結論。  
- ❌ 任何 SHORT\_MOMENTUM（150/500 正、1500 負）策略推進到 promotion。  
- ❌ 任何沒有 McNemar vs incumbent 的 promotion candidate 標記（強制封鎖）。  
- ❌ 任何主張「彩票一定能提升中獎率」的研究。  
- ❌ 鄰號共現 / Lift\<1.0 的注入策略（L08 已封）。  
- ❌ Gap Dynamic Threshold 類偽信號（L07）。

### 6.5 如何避免假陽性

1. 每個 hypothesis 預先註冊（registry/hypotheses.jsonl），禁止 post-hoc 校正豁免。  
2. 多窗口（150/500/1500）一致性要求。  
3. Permutation null（≥5000 simulations）。  
4. Bonferroni 跨遊戲、BH-FDR 跨策略。  
5. Circular-bias detector \+ leakage detector CI gate。  
6. 任何 effect size \< 統計噪音的不採納（L06）。  
7. Walk-forward OOS 強制。

### 6.6 如何定義成功

不只用「中獎率」，而用以下複合指標：

- **Predict-vs-actual mean hit**: 與超幾何 baseline 比較，permutation p（Bonferroni 校正後）。  
- **Per-strategy BH-FDR q \< 0.05**。  
- **Effect size**（Cohen's d）。  
- **Walk-forward OOS Sharpe \> 0**（不只 mean ROI）。  
- **Drawdown \< 25%**（穩定性）。  
- **Confidence interval 不跨越 0**。  
- **Coverage efficiency**（覆蓋率 / bet 數量）。  
- **Payout EV**（不只 hit count，須含 jackpot sharing risk）。

CLV（closing line value）類似指標：彩票無 closing line，不適用。但 sports betting 適用，這是 framework 遷移時要區分的點。

### 6.7 如何決定某策略 retire

任一條件成立 → retire to `rejected/{strategy_name}.json`：

- 連續 3 次 randomness audit / predict-vs-actual NO SIGNAL（Bonferroni 校正後）。  
- 三窗口任一窗口 ROI ≤ baseline。  
- McNemar vs incumbent p ≥ 0.05（無法戰勝現役）。  
- Walk-forward OOS Sharpe ≤ 0。  
- Drawdown ≥ 25%。  
- Stability audit 列入 SUSPENDED 三個月仍未恢復。

`rejected/` 必須記錄: 失敗原因、統計結果、適用條件、重測條件。

---

## 7\. Self-learning Scheduler Plan

### 7.1 EvidenceCollector

EvidenceCollector

  \- sources:

    1\. failed\_tests (CI / pytest output)

    2\. stale\_data (data/\*.csv mtime \> threshold)

    3\. missing\_outcomes (next\_draw passed but outcome not recorded)

    4\. monitoring\_degraded (AUTO-MONITOR DEGRADED status)

    5\. llm\_usage\_high (per-role / per-provider \> 80% cap)

    6\. copilot\_overuse (Copilot \> daily cap)

    7\. pending\_outcome (stuck in dry-run \> 24h)

    8\. rollback\_false\_positive (rollback proposed but guard blocked)

    9\. backtest\_anomaly (results outlier vs historical distribution)

    10\. strategy\_no\_signal (predict-vs-actual NO SIGNAL N consecutive)

    11\. randomness\_audit\_gap (no audit run in N days)

    12\. ui\_dashboard\_missing\_field (BFF returned null in expected field)

    13\. db\_schema\_mismatch (schema\_versions diverge from code expectation)

    14\. task\_failure\_taxonomy (new failure pattern detected)

    15\. repeated\_failure (same dedupe\_key fails N times)

    16\. queue\_health (QUEUED tasks aging \> threshold)

    17\. outdated\_docs\_wiki (wiki/\* references missing files)

    18\. high\_risk\_production\_state (active strategy degraded)

### 7.2 EvidenceItem schema

{

  "evidence\_id": "uuid",

  "source": "failed\_tests | stale\_data | ...",

  "severity": "CRITICAL | HIGH | MEDIUM | LOW",

  "confidence": 0.0-1.0,

  "affected\_module": "orchestrator | strategy\_engine | ...",

  "evidence\_text": "human readable context",

  "suggested\_task\_type": "fix\_test | refresh\_data | ...",

  "expected\_impact": "qualitative description",

  "requires\_llm": false,

  "dedupe\_key": "evidence:{source}:{affected\_module}:{utc\_date}",

  "acceptance\_criteria": \["test X passes", "metric Y \> Z"\],

  "first\_seen": "ISO8601",

  "last\_seen": "ISO8601",

  "occurrence\_count": 1

}

### 7.3 Scoring formula

task\_score \= 

    (severity\_weight\[severity\] 

     × confidence 

     × expected\_impact\_weight 

     × freshness\_factor)

  / (risk\_weight 

     × llm\_cost\_factor 

     × implementation\_size\_factor)

where:

  severity\_weight \= {CRITICAL: 8, HIGH: 5, MEDIUM: 3, LOW: 1}

  freshness\_factor \= 1 \+ log(1 \+ occurrence\_count)

  llm\_cost\_factor \= 1 (no LLM) or 2 (LLM needed)

  implementation\_size\_factor \= {S:1, M:2, L:4, XL:8}

  risk\_weight \= 1 (low) \- 4 (production-mutating)

### 7.4 Task generator

def generate\_task(evidence\_item, scoring\_context):

    if evidence\_item.dedupe\_key already in QUEUED/RUNNING tasks:

        return None  \# dedupe

    if evidence\_item.requires\_llm and llm\_governor.budget\_exhausted():

        return defer(evidence\_item)

    task \= Task(

        type=evidence\_item.suggested\_task\_type,

        priority=score(evidence\_item),

        worker\_type="light" if not evidence\_item.requires\_llm else "worker",

        acceptance\_criteria=evidence\_item.acceptance\_criteria,

        dedupe\_key=evidence\_item.dedupe\_key,

    )

    return task

### 7.5 Failure taxonomy

| Category | Description | Mitigation |
| :---- | :---- | :---- |
| FORMAT\_CONTRACT | Output 不符合 prompt 契約 | 限縮 prompt \+ 加 schema validator |
| VALIDATION | 統計檢驗失敗 | Auto-route to randomness audit \+ retire |
| LEAKAGE | 偵測到 data leakage | 阻擋 task \+ 通知 CTO review |
| CIRCULAR\_BIAS | v1-style historical pool max-hit | 直接 reject \+ 寫入 lesson |
| LLM\_BUDGET | 配額耗盡 | 排程到下個 cycle |
| PROVIDER\_ERROR | Claude / Codex 服務錯誤 | Retry with backoff，N 次失敗 → escalate |
| LOCK\_TIMEOUT | Worker lock 超時 | Auto-release \+ retry |
| STALE\_DATA | 資料過時 | 觸發 data refresh task |
| SCHEMA\_MISMATCH | DB schema vs code 不符 | 阻擋 \+ 提案 migration |
| AUDIT\_MISSING | LLM call 無 audit | hard-fail，禁止重試 |
| RECONCILE\_FAIL | dry-run 與 isolated 結果不一致 | 阻擋 production write |
| DUPLICATE\_TASK | dedupe\_key 衝突 | drop \+ 標記 lesson |

### 7.6 Memory / Lesson update

task completed → outcome\_logger writes task\_outcomes.jsonl

                    │

                    ├── if FAILED with new pattern → failure\_taxonomy.append

                    ├── if FAILED with same dedupe N times → memory/lessons.md auto-append

                    └── if SUCCESS with reusable pattern → templates/{slug}.md

每筆 lesson 記錄: summary（一句話）、affected\_modules、minimal repro、suggested mitigation（依 wiki/system/feedback\_loop.md 規範）。

### 7.7 Human approval points

下列必須人工確認：

1. Production DB write（`--confirm-production-outcome`）。  
2. Active strategy 變更（CTO review）。  
3. Rollback execution（restore script）。  
4. Schema migration（dry-run report 通過後手動 approve）。  
5. Hard-off 解除。  
6. LLM cap 上調。

### 7.8 LLM budget governance

Pre-call gate:

  1\. LLM Governor checks: per-role / per-provider / per-task / hourly / daily caps

  2\. audit ATTEMPT logged to llm\_audit\_events (REQUIRED)

  3\. if hard-off: BLOCK

  4\. if safe-run: BLOCK external mutation but allow read

Post-call:

  1\. tokens / cost recorded in llm\_usage\_events

  2\. Top tasks by LLM calls dashboard updated

  3\. if usage \> 80% of cap: emit copilot\_overuse / llm\_usage\_high evidence

### 7.9 Startup catch-up

on startup:

  1\. detect pending\_outcome (next\_draw passed but no outcome)

     → enqueue light\_worker outcome dry-run task

  2\. detect stale RUNNING locks (pid dead)

     → release lock \+ mark task FAILED with reason=lock\_timeout

  3\. detect stale data (mtime \> threshold)

     → enqueue data\_refresh task

  4\. detect missing migration (schema\_versions \< code expectation)

     → DO NOT auto-apply; create migration\_review task

---

## 8\. Architecture Refactoring Plan

### 8.1 模組拆分建議

| 現況 | 目標 |
| :---- | :---- |
| `orchestrator/*.py` 全部混在一起 | 拆 `orchestrator/control/` (planner / worker / scoring), `orchestrator/governance/` (rollback\_guard / llm\_governor / audit), `orchestrator/evidence/` |
| `scripts/predict_vs_actual.py` 為 standalone | 抽進 `tools/strategy_eval/` 並用 `tools/backtest_framework/` 元件 |
| `scripts/h6_*.py` 散落 | 收進 `orchestrator/governance/rollback_guard.py` |
| 多份 monitoring 入口 | 統一 `orchestrator/monitoring/` 並透過 BFF 暴露 |

### 8.2 API 統一策略

- 對 UI: 唯一入口 BFF（`api/bff.py`），所有 frontend 呼叫走此層。  
- 對 internal modules: 不 cross-module 直接讀 DB，必須透過 module 對外 interface。  
- 對 external（自動化 / scripts）: 提供穩定 CLI（`tools/*` 為主）。

### 8.3 DB Schema 整理

- 每個 table 對應一個 owner module。  
- 增加 `schema_versions` 表記錄各 module schema version。  
- migration scripts 入 `schemas/v{N}/` 並有 dry-run \+ apply 兩步驟。  
- 新增 `event_log` 表（append-only）作為 cross-module audit。

### 8.4 Config / Settings 管理

- `config/{env}.yaml`（dev / staging / prod）。  
- 統一用 pydantic settings 載入。  
- feature\_flags 與 governance 閾值（rollback / outcome / LLM cap）全進 config。  
- 任何「magic number」必須有 config key 對應。

### 8.5 Testing pyramid

              ┌──────────────────┐

              │  E2E (smoke)     │  10%

              ├──────────────────┤

              │  Integration     │  20%

              ├──────────────────┤

              │  Module          │  30%

              ├──────────────────┤

              │  Unit            │  40%

              └──────────────────┘

              \+ No-production-mutation regression

              \+ Historical data validation

              \+ Circular-bias / leakage CI gate

              \+ Audit-required CI gate

### 8.6 Deployment / startup flow

1\. read config/{env}.yaml

2\. verify schema\_versions \= code expectations (else block)

3\. startup catch-up (pending outcome, stale lock, stale data evidence)

4\. start orchestrator with feature\_flags loaded

5\. expose /health

6\. Local Planner first tick (evidence-driven)

### 8.7 Frontend Dashboard refactor

單一 nav，子頁面：

- System Health  
- Tasks（Today / Backlog / Failure Taxonomy）  
- LLM Usage（per role / per provider / Top tasks）  
- Strategies（active / shadow / lifecycle / signal status）  
- Backtest（multi-window / WF OOS / per-strategy）  
- Outcomes（pending / recorded / rollback guard status）  
- Self-learning（evidence feed / score changes / recommended next tasks）

---

## 9\. Risk Register（20+ risks）

| \# | Risk | Impact | Likelihood | Mitigation | Owner | Detection Signal |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| R01 | False rollback (再次發生) | Critical | Med | rollback\_guard config \+ simulation mode | Phase 0 | rollback proposal but outcome\_count \< threshold |
| R02 | Production DB unauthorized write | Critical | Low | \--confirm-production-outcome \+ CI test | Phase 0 | audit event missing on write |
| R03 | LLM 配額爆量（Claude / Codex / Copilot） | High | Med | per-role/per-provider caps \+ alert | Phase 1 | hourly usage \> 80% |
| R04 | Audit guard 被 bypass | Critical | Low | CI test \+ module-level enforcement | Phase 0 | LLM call 無對應 audit event |
| R05 | Stale RUNNING lock 卡住 worker | High | Med | auto-release on dead pid | Phase 0 | RUNNING \> N 小時 |
| R06 | Schema drift（DB vs code） | High | Med | schema\_versions \+ startup gate | Phase 1 | startup mismatch |
| R07 | Data freshness（draws CSV stale） | Med | High | stale\_data evidence \+ auto refresh task | Phase 3 | mtime \> 7 天 |
| R08 | False positive strategy（pre-correction） | Critical | High | Bonferroni \+ BH-FDR \+ registry | Phase 2 | strategy promoted without校正 |
| R09 | Circular-match bias | Critical | Low | CI gate test\_no\_circular\_match | Phase 2 | v1-style pool max-hit detected |
| R10 | Look-ahead leakage in backtest | Critical | Med | DataLeakageError on RollingBacktester | Phase 2 | predictor accesses target draw |
| R11 | UI 顯示誤導（stale data） | High | Med | BFF 標 last\_updated \+ freshness flag | Phase 1 | UI shows old metric without label |
| R12 | Repeated failures 形成 task 洪水 | Med | Med | dedupe \+ auto-retire | Phase 3 | same dedupe\_key \> N 次 |
| R13 | Local Planner 任務多樣性下降 | Med | Med | forced exploration lane \+ daily diversity check | Phase 3 | 同類 task \> 50% / day |
| R14 | Outcome 寫入但 schema 不對 | High | Low | dry-run \+ isolated DB \+ reconcile | Phase 0 | reconcile fail evidence |
| R15 | Strategy retire policy 過嚴 → 全停 | Med | Med | retire 需 CTO confirm | Phase 2 | 同月 \> 3 個 strategy retire |
| R16 | LLM provider rate limit 連鎖 | Med | High | unified rate parser \+ backoff | Phase 1 | 429 errors \> 5/hour |
| R17 | wiki / docs drift | Med | High | wiki freshness CI \+ governance | Continuous | wiki references missing file |
| R18 | Stale outcome (記錄到一半 crash) | High | Med | startup catch-up \+ reconcile | Phase 0 | pending \> 24h |
| R19 | Worker spurious LLM mutation | Critical | Low | safe-run \+ CTO review-only | Continuous | Worker 寫到 production without confirm |
| R20 | Cross-domain transfer leak（lottery 結論污染 stock） | High | Med | strict domain isolation in framework | Phase 4 | shared state across domains |
| R21 | Hypothesis registry 流程繞過 | High | Med | CI test 強制 hypothesis\_id 存在 | Phase 2 | strategy\_eval run without registered hypothesis |
| R22 | Self-learning bias loop（壞 evidence → 壞 task → 壞 evidence） | High | Med | human approval gate \+ diversity check | Phase 3 | task quality drift \> threshold |
| R23 | Backtest framework public API 過早 freeze | Med | Med | 兩 domain POC 後才 v1 freeze | Phase 4 | API change \> N per quarter |

---

## 10\. 30 / 60 / 90 Day Plan

### 30 天

**Target Outcomes**:

- Phase 0 完成 80%（rollback guard / outcome 三段 gate / no-audit CI / lock auto-release / restore dry-run）  
- Randomness audit final verdict 草稿（三款彩票）  
- LLM Governance per-role / per-provider caps 上線

**Deliverables**:

- `orchestrator/governance/rollback_guard.py` \+ tests  
- `orchestrator/governance/outcome_gate.py` \+ tests  
- `tests/test_no_audit_no_call.py`  
- `wiki/system/randomness_final_verdict.md`（草稿）

**Tests**:

- rollback simulation 30 天 hist 一致性測試  
- audit-required CI gate  
- stale lock release mock-crash test

**Measurable Success Criteria**:

- ✅ rollback false positive 0  
- ✅ production write 必有 audit event（100%）  
- ✅ stale RUNNING lock auto-release 在 mock test 通過  
- ✅ LLM per-day cap 自動觸發 hard-off 在 staging 驗證

### 60 天

**Target Outcomes**:

- Phase 0 完成 100%  
- Phase 1 完成 50%（module boundaries 文件、BFF API 雛形、schema versioning、feature flags）  
- Phase 2 啟動：Strategy Evaluation Framework v0.5、Hypothesis Registry v0.5

**Deliverables**:

- `wiki/system/module_boundaries.md`  
- `api/bff.py` v0.5  
- `schemas/v1/` migration registry  
- `config/feature_flags.yaml`  
- `tools/strategy_eval/` v0.5  
- `registry/hypotheses.jsonl`

**Tests**:

- BFF E2E smoke  
- Schema migration dry-run \+ apply  
- Hypothesis registry CI gate

**Measurable Success Criteria**:

- ✅ UI 90% 走 BFF（剩 10% 為 legacy 標記）  
- ✅ feature\_flags 100% test coverage  
- ✅ strategy\_eval CLI 一鍵跑通 power\_lotto / big\_lotto / daily\_539

### 90 天

**Target Outcomes**:

- Phase 1 完成 100%  
- Phase 2 完成 60%  
- Phase 3 啟動：EvidenceCollector v0.3 \+ Task Scoring v0.3

**Deliverables**:

- UI Dashboard 單入口完成  
- Strategy Evaluation Framework v1  
- Multiple Testing Registry（強制 CI）  
- Walk-forward OOS 自動化  
- `orchestrator/evidence/collector.py` v0.3  
- `orchestrator/scoring.py` v0.3

**Tests**:

- Circular-bias CI gate enforcing  
- Leakage detector 整合 RollingBacktester  
- EvidenceCollector 18 source 連續 7 天運轉

**Measurable Success Criteria**:

- ✅ UI 100% 走 BFF  
- ✅ 任何 promotion 都有 hypothesis\_id  
- ✅ EvidenceCollector daily output \> 0  
- ✅ Local Planner v0.5 task 佔比 \> 50%  
- ✅ randomness audit final verdict 三款彩票完成

---

## 11\. First 10 Execution Prompts（直接交給 Agent）

### Prompt 1 — Rollback Guard Refactor

ROLE: Phase 0 stabilization worker.

TASK: Refactor scripts/h6\_rollback\_\*.py into orchestrator/governance/rollback\_guard.py.

\- Move MIN\_OUTCOMES\_FOR\_ROLLBACK / MIN\_CONSECUTIVE\_NEGATIVE\_FOR\_EARLY\_ROLLBACK / 

  EARLY\_ROLLBACK\_SAMPLE\_SIZE into config/rollback\_guard.yaml.

\- Add simulation mode (no DB writes, returns proposed action).

\- Public API: RollbackGuard.evaluate(strategy\_state) \-\> RollbackDecision.

STRICT RULES:

\- Do not change current threshold values.

\- No external LLM calls.

\- All thresholds config-driven.

\- New code MUST be covered by tests/test\_rollback\_guard.py.

ACCEPTANCE CRITERIA:

\- pytest tests/test\_rollback\_guard.py passes.

\- Simulation mode returns identical decisions vs production for last 30 days hist.

\- DB writes only when simulation=False.

EXPECTED VERDICT: PASS (with diff summary) or FAIL with root cause.

### Prompt 2 — No-Audit-No-Call CI Gate

ROLE: Phase 0 stabilization worker.

TASK: Add CI test tests/test\_no\_audit\_no\_call.py that:

\- Mocks all LLM provider calls (Claude / Codex / Copilot).

\- Runs orchestrator worker with audit subsystem disabled.

\- Asserts that ANY external LLM invocation raises AuditMissingError.

STRICT RULES:

\- Must not bypass audit by removing the gate; gate must be at provider client layer.

\- Test must run \< 30s.

ACCEPTANCE CRITERIA:

\- Test fails before fix (i.e., reveals if any path bypasses audit).

\- Test passes after fix.

\- Documented in wiki/system/governance.md as platform invariant.

EXPECTED VERDICT: PASS / FAIL with bypass path list.

### Prompt 3 — Outcome Three-Gate Interface

ROLE: Phase 0 stabilization worker.

TASK: Unify outcome recording across all games into orchestrator/governance/outcome\_gate.py.

\- Three stages: dry\_run \-\> isolated\_db \-\> production\_with\_confirm.

\- production stage requires \--write AND \--confirm-production-outcome.

\- Each stage emits audit event before action.

STRICT RULES:

\- No automatic production write.

\- No skipping isolated\_db stage.

\- Each game must call same interface; remove per-game custom code.

ACCEPTANCE CRITERIA:

\- tests/test\_outcome\_gate.py 100% coverage.

\- 3 games (big\_lotto / power\_lotto / daily\_539) tested end-to-end.

\- production write audit events match write events 1:1.

EXPECTED VERDICT: PASS / FAIL with diff.

### Prompt 4 — Stale Lock Auto-Release

ROLE: Phase 0 stabilization worker.

TASK: Add stale RUNNING lock detection on orchestrator startup:

\- For each RUNNING task: check pid alive.

\- If dead: mark task FAILED with reason=lock\_timeout, release lock.

\- Emit failure\_taxonomy event LOCK\_TIMEOUT.

STRICT RULES:

\- Do not release locks for tasks with alive pids.

\- Do not auto-restart failed tasks (just mark FAILED).

\- Audit event before each release.

ACCEPTANCE CRITERIA:

\- Mock crash test passes.

\- After 7-day staging run, no stale lock \> 5 min.

EXPECTED VERDICT: PASS / FAIL.

### Prompt 5 — Restore Script Dry-Run Validation

ROLE: Phase 0 stabilization worker.

TASK: For each restore script:

\- Add \--dry-run flag (default OFF).

\- Add \--backup flag (mandatory before write).

\- Produce restore simulation report (which rows would change).

\- Output to outputs/restore\_simulation/\<timestamp\>/.

STRICT RULES:

\- No DB writes in dry-run mode.

\- Backup must succeed before any write.

\- audit event before backup and write.

ACCEPTANCE CRITERIA:

\- dry-run report matches actual restore on hist test data.

\- backup file exists before any write.

EXPECTED VERDICT: PASS / FAIL.

### Prompt 6 — Randomness Audit Final Verdict (per game)

ROLE: Phase 2 validation researcher.

TASK: For each of {big\_lotto, power\_lotto, daily\_539}:

1\. Run scripts/randomness\_audit.py with full hist data.

2\. Apply Bonferroni correction across 3 games.

3\. Apply BH-FDR within-game across all sub-tests.

4\. Produce final verdict in wiki/system/randomness\_final\_verdict.md, structured:

   \- Game / draws\_count / tests\_run / raw\_p / bonferroni\_p / bh\_fdr\_q / verdict

   \- Verdict \= SIGNIFICANT\_BIAS | WEAK\_DEVIATIONS\_NOT\_SIGNIFICANT | NO\_BIAS\_DETECTED

STRICT RULES:

\- Do not interpret NO\_BIAS as system failure (it is a valid scientific outcome).

\- Do not rerun until \> 100 new draws.

\- No external LLM call.

\- Must use scripts/predict\_vs\_actual.py v2 only.

ACCEPTANCE CRITERIA:

\- 3 verdicts written.

\- Each verdict references the audit script run timestamp.

\- wiki updated as routing.

EXPECTED VERDICT: VERDICT\_PER\_GAME (3 entries).

### Prompt 7 — Hypothesis Registry CLI

ROLE: Phase 2 validation worker.

TASK: Create registry/hypotheses.jsonl \+ tools/registry/cli.py:

\- register \--hypothesis-id \<id\> \--description \--predictor \--window

\- list \--status open|closed|retired

\- Each strategy\_eval run MUST reference \--hypothesis-id (else fail).

STRICT RULES:

\- jsonl is append-only (no in-place edit).

\- Each entry has timestamp, registrant, status, attempts.

\- CI gate: strategy\_eval requires registered hypothesis\_id.

ACCEPTANCE CRITERIA:

\- CLI usable.

\- strategy\_eval run without \--hypothesis-id fails.

\- Two example hypotheses registered.

EXPECTED VERDICT: PASS / FAIL.

### Prompt 8 — Circular-Bias Detector CI Gate

ROLE: Phase 2 validation worker.

TASK: Implement tests/test\_no\_circular\_match.py:

\- Scan codebase for patterns matching v1-style historical-pool max-hit:

  predictions vs ALL hist draws max-hit (not single target draw).

\- Allow only via approved annotation @approved\_circular\_match for legacy code.

\- Tests fail if new code introduces unmarked circular match.

STRICT RULES:

\- No false positive on v2 predict\_vs\_actual.py.

\- Must run \< 60s.

ACCEPTANCE CRITERIA:

\- Test passes on current codebase.

\- Test fails on intentional violation in test fixture.

EXPECTED VERDICT: PASS / FAIL with offending paths.

### Prompt 9 — EvidenceCollector v0.3

ROLE: Phase 3 self-learning worker.

TASK: Implement orchestrator/evidence/collector.py covering 6 sources:

1\. failed\_tests

2\. stale\_data

3\. missing\_outcomes

4\. monitoring\_degraded

5\. llm\_usage\_high

6\. strategy\_no\_signal

\- Each emits EvidenceItem (see schema in MASTER\_ROADMAP\_2026.md §7.2).

\- Persist to evidence/items.jsonl (append-only).

STRICT RULES:

\- Pure function: takes system snapshot, returns list\[EvidenceItem\].

\- No external LLM call.

\- requires\_llm=false default.

\- dedupe\_key follows orchestrator UTC date convention.

ACCEPTANCE CRITERIA:

\- Each of 6 sources has unit test producing at least one EvidenceItem on a known fixture.

\- Continuous 24h staging run produces non-empty stream.

EXPECTED VERDICT: PASS / FAIL with sample EvidenceItems.

### Prompt 10 — Local Planner v0.5 (no LLM)

ROLE: Phase 3 self-learning worker.

TASK: Implement orchestrator/local\_planner.py that:

\- Reads orchestrator/evidence/items.jsonl (recent N).

\- Applies orchestrator/scoring.py.

\- Produces top-K QUEUED tasks with dedupe\_key.

\- requires\_llm tasks deferred unless explicitly escalated.

STRICT RULES:

\- No external LLM call (CI test enforces).

\- Daily task cap (config-managed, default 30).

\- Must respect existing dedupe (skip if same key in QUEUED/RUNNING).

\- Forced exploration lane: 1 task per day from low-frequency category.

ACCEPTANCE CRITERIA:

\- 7-day staging: \> 50% tasks come from Local Planner (vs external LLM planner).

\- Failure taxonomy registry populated.

\- task diversity check: no single task type \> 50% per day.

EXPECTED VERDICT: PASS / FAIL with daily metrics.

---

## 12\. Final Recommendation

### 12.1 彩票策略研究是否值得繼續投入？

**保守建議：低 ROI，僅維持 maintenance-only 模式。**

依據:

- v2 predict-vs-actual 三款遊戲皆為 NO SIGNAL（Bonferroni × BH-FDR 後）。  
- Randomness audit 最近 verdict 為 `WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION`。  
- 三款遊戲 stability audit 均為 ADVISORY\_ONLY，Kelly 結果趨近 0，monetary ROI 深負。

**這不是失敗**——這是科學上有效且重要的結論：彩票本身在當前抽樣下沒有可被捕捉的時序信號。系統最大的資產是「能可靠得出 NO SIGNAL 結論」這件事本身。

繼續投入應限縮在: randomness audit 持續監控（每 50 期）、payout EV / unpopular-number advisory、physical bias candidate detection。**禁止再投入 prediction-signal 探索類研究**。

### 12.2 哪些方向值得繼續？

- ✅ Randomness audit（advisory，補完整結論）  
- ✅ Payout EV / unpopular-number EV（advisory only）  
- ✅ Physical bias candidate detection（advisory only）  
- ✅ Covering design / wheel system（如有人純粹娛樂用途）  
- ✅ Strategy retire policy 自動化

### 12.3 哪些方向應該停止？

- ❌ 任何 historical-pool max-hit 類預測力評估  
- ❌ 任何沒有 Bonferroni/BH-FDR 的 grid search  
- ❌ 任何 SHORT\_MOMENTUM 樣態的 promotion  
- ❌ 任何「保證提升中獎率」的研究路線  
- ❌ 鄰號共現 / Lift\<1.0 的注入策略  
- ❌ Gap Dynamic Threshold 偽信號  
- ❌ Day-of-Week 效應研究（L27 已封）  
- ❌ 跨彩種結論借用（L21）

### 12.4 系統工程優化是否值得投入？

**高 ROI，強烈建議投入。**

依據:

- Orchestrator / Worker / LLM Governance / Outcome Recording / Rollback Guard 已具備平台輪廓。  
- Phase 0–1（Stabilize \+ Architecture Consolidation）為其他 Phase 的前置條件，且風險低。  
- BFF / Schema versioning / Feature flags / Single source of truth 是任何長期 SaaS-like 系統的基礎能力。

### 12.5 排程自我學習是否值得投入？

**高 ROI，但需強治理與成本控制。**

依據:

- Local Planner（不依賴外部 LLM）讓系統可持續低成本運轉。  
- EvidenceCollector \+ Task Scoring 是把「人工 backlog 管理」轉為「自動 evidence-driven 排程」的核心。  
- Failure Taxonomy \+ Lessons auto-update 形成正回饋。

風險:

- Self-learning bias loop（壞 evidence 引出壞任務）需 human approval gate \+ diversity check。  
- LLM 配額需嚴控（per role / per provider / daily / hourly）。  
- 任何 production mutation 仍須手動確認，不允許 self-learning 自動 approve。

### 12.6 如何把這套方法轉成 Stock / Betting / Novel 的長期資產？

**關鍵是抽象 `tools/backtest_framework/`**，將以下元件變成 domain-agnostic：

- `permutation_null` (Monte Carlo baseline 必須複製 selection mechanism)  
- `walk_forward_oos`  
- `multi_window` (短/中/長一致性)  
- `bonferroni` \+ `bh_fdr`  
- `circular_bias_detector`  
- `leakage_detector`  
- `effect_size`  
- `hypothesis_registry`

**遷移策略**:

1. **Stock**: backtest 框架直接適用。Strategy interface 保持 `Strategy(history) -> List[Bet]`；Bet 改成 `Position(ticker, qty, side)`。短/中/長窗口仍適用。Closing line value 不存在，但 Sharpe / Sortino / drawdown 有。Look-ahead bias 風險更高，leakage detector 必跑。  
2. **Betting**: framework 直接適用。closing line value (CLV) 是強指標（lottery 沒有，sports 有），加進 framework。permutation null 對 sports outcome 適用。  
3. **Novel-writing / A-B testing / marketing**: framework 用於假設檢驗（multi-arm bandit、A-B significance、preregistered hypothesis）。EvidenceCollector / Local Planner 直接通用。

**保留的核心原則（不可改）**:

- no-audit-no-call  
- Local Planner first（外部 LLM 為例外）  
- multiple comparison correction 強制  
- circular-bias detector 強制  
- production write 雙人確認  
- preregistered hypothesis（禁 post-hoc 校正豁免）

---

## Appendix — Operating Constraints Reaffirmed

本 roadmap 全程遵守以下 hard constraints：

1. ✅ 不承諾彩票一定能提升中獎率。  
2. ✅ NO SIGNAL 解讀為科學成功（非系統失敗）。  
3. ✅ Circular-Match Bias 作為 CI gate，禁止重蹈 v1。  
4. ✅ Local Planner 預設不呼叫 Claude / Codex / Copilot。  
5. ✅ 未驗證自動寫 production DB 全面禁止。  
6. ✅ 自動 rollback 全面禁止；rollback 需人工確認。  
7. ✅ Audit guard 不得移除，CI gate 強制。  
8. ✅ Roadmap 含可執行 prompts、deliverables、acceptance criteria。  
9. ✅ 涵蓋 DB / API / UI / tests / governance（不只 AI）。  
10. ✅ 明確指出哪些方法可遷移到 Stock / Betting / Novel。

---

## Appendix — Trusted Sources Used

依 Knowledge Gate 規則，本 roadmap 僅基於以下 trusted sources：

- `wiki/README.md` — 知識路由  
- `wiki/system/governance.md` — 文件治理  
- `wiki/system/validation_gates.md` — 策略晉級規則  
- `wiki/system/stability_audit.md` — 穩定性稽核  
- `wiki/system/feedback_loop.md` — 回饋閉環  
- `wiki/system/predict_vs_actual_sop.md` — 預測能力驗證 SOP  
- `wiki/system/orchestrator.md` — Orchestrator 架構  
- `memory/lessons.md` — 歷次教訓（L01–L27+）

未引用 archive / rejected / 散落 root markdown 等 untrusted 來源。

---

**End of Master Roadmap (2026-2027) v1.0** 後續版本更新需在 `wiki/system/governance.md` 記錄日期與摘要。  


codex補充：
我同意這份 Master Roadmap 的大方向，而且它比一般「繼續優化預測模型」成熟很多。它最正確的地方是：把 LotteryNew 從「彩票預測系統」重新定位成「統計驗證 + Agent Orchestration + 可遷移 Backtesting Framework」，並且明確指出方法論資產比單一彩票策略更有價值。Roadmap 也把 Phase 0 安全固化、Phase 2 科學驗證、Phase 3 Evidence-driven Local Planner、Phase 4 轉移到 Stock / Betting 的順序列出來，這個方向我認同。

但我會做幾個調整，讓它更實際、更不容易又變成大型願景文件。

我的判斷

目前版本有三個優點：

方向正確：先穩定 production safety，再做架構收斂，再做科學驗證，最後才做 self-learning 和跨系統遷移。
方法論成熟：把 predict-vs-actual v2、permutation null、Bonferroni / BH-FDR、Circular-Match Bias detector 抽成 framework，是最高 ROI。Roadmap 也明確把這些列為可遷移資產。
治理意識正確：production mutation、rollback、LLM usage、no-audit-no-call 都被當成平台 invariant，不是單一 bug fix。Roadmap 的風險表也有列到 false rollback、LLM 配額爆量、audit bypass、schema drift、circular-match bias 等風險。

但我會修正四點：

我會調整的地方	原因
加一個 Phase -1：Current Recovery	目前 DAILY_539 還在 false rollback restore pending，不能直接進長期 phase
把「彩票研究」和「平台工程」分流	彩票預測 ROI 低，但平台工程 ROI 高，不能混在一起評估
EvidenceCollector 不要等到 Month 6–9	至少先做 v0.1，否則排程還是人工 backlog
Stock / Betting 遷移要設 gate	不能等 Framework 完美才開始，但也不能太早複製 Lottery 的 bug

所以我的整合版會改成：

Phase -1：Recovery / Restore / Runtime Safety
Phase 0：Platform Invariants
Phase 1：Architecture Consolidation
Phase 2：Scientific Closure for Lottery
Phase 3：Evidence-driven Scheduler v1
Phase 4：Generic Backtest Framework
Phase 5：Stock / Betting / Novel Migration
Phase 6：Long-term Research / Maintenance
整合版 Master Plan Prompt

下面這份是我建議你交給新模型的整合版 prompt。它比原 roadmap 更聚焦，而且把「現在還沒 restore 的狀態」納入第一階段。

# ROLE

你是 LotteryNew 系統的「長期架構治理與研究方法論總顧問」。

請基於目前 LotteryNew 的實際狀態，重新整理一份 2026–2027 長期優化 Master Plan。

這份計畫不是單次修 bug，也不是馬上改程式，而是要形成一份可拆成後續 Agent 任務的長期治理藍圖。

請把重點放在三大主軸：

1. 程式系統架構長期優化
2. 預測成功率 / 策略有效性提升與研究封項
3. 排程自我學習 / Evidence-driven Agent 優化

---

# CURRENT CONTEXT

LotteryNew 目前已具備以下能力：

## A. Orchestrator / Agent / LLM Governance

系統已有：

- Planner
- Worker
- Light Worker
- CTO Review
- Copilot-Daemon
- LLM Execution Control
- Safe-run / Hard-off
- Scheduler enabled / disabled
- LLM audit events
- LLM usage events
- Planner / Worker / CTO usage dashboard
- Copilot-Daemon focus
- top tasks by LLM calls
- no-audit-no-call 概念

目前原則：

- Local Planner 預設不呼叫 Claude / Codex / Copilot
- Worker 外部 LLM 呼叫必須受控
- CTO 外部 LLM 僅 review-only
- Claude / Codex / GitHub Copilot / Copilot-Daemon 外呼必須先寫 audit ATTEMPT
- 沒有 audit event 就不能外呼
- Copilot 用量需能依 role / runner / provider / task 追蹤

## B. H6 DAILY_539 false rollback

目前已知：

- DAILY_539 曾因第一筆 outcome ROI=-1.0 觸發錯誤 rollback
- root cause 是 outcome_count=1 仍被拿來做 30P / 50P rollback 判斷
- 已補 rollback guard：
  - MIN_OUTCOMES_FOR_ROLLBACK = 5
  - MIN_CONSECUTIVE_NEGATIVE_FOR_EARLY_ROLLBACK = 3
  - EARLY_ROLLBACK_SAMPLE_SIZE = 30
- 目前狀態是：
  - H6_ROLLBACK_GUARD_FIXED_RESTORE_PENDING
- restore script 已有：
  - scripts/h6_restore_false_rollback.py
- production active/shadow 是否已 restore 需另行確認

此狀態必須被納入 Phase -1，不可忽略。

## C. Outcome recording

目前已從人工流程升級成：

- startup catch-up
- pending outcome detection
- dry-run outcome recording
- isolated DB write test
- production write 需要：
  - --write
  - --confirm-production-outcome

目前方向是 manual-confirmed automation，不做未驗證的全自動 production outcome write。

## D. Predict-vs-Actual / Circular-Match Bias

目前已完成：

- v1 historical-pool max-hit 方法已被標為 INVALID
- root cause 是 Circular-Match Bias
- v2 方法改成：
  - prediction 只對 actual target draw
  - permutation null
  - Bonferroni
  - BH-FDR
- big_lotto / power_lotto 已顯示 NO SIGNAL
- daily_539 是否已正式納入同一個 v2 closure，請先確認，不可直接假設

重要方法論：

- 「預測 vs 歷史 pool 最大命中」不等於預測能力
- Monte Carlo baseline 必須複製 selection mechanism
- 多重比較校正是必要，不是選項
- 看起來像破解彩票的結果，要先懷疑 leakage / circular bias / baseline 錯誤

## E. Master Roadmap 初稿

現有 roadmap 已提出：

- Phase 0 Stabilize / Safety
- Phase 1 Architecture Consolidation
- Phase 2 Scientific Validation
- Phase 3 Self-learning Scheduler
- Phase 4 Transferable Framework
- Phase 5 Long-term Research

但請你重新整合成更可執行版本，補上：

- Phase -1 Recovery
- 更短的 30 / 60 / 90 天落地計畫
- 每個 phase 的 execution prompts
- 每個 phase 的 kill criteria / stop criteria
- 每個 phase 的 measurable outcomes

---

# MAIN OBJECTIVE

請產出一份「整合版長期優化計畫」，不是單純複製原 roadmap。

請回答：

1. 原 roadmap 哪些地方正確？
2. 哪些地方需要調整？
3. 哪些項目應提前？
4. 哪些項目應延後？
5. 哪些彩票研究方向應封項？
6. 哪些方法論應抽象成跨系統 framework？
7. 如何讓排程真的從 backlog-driven 變成 evidence-driven？
8. 如何保證 LLM 不會再爆量？
9. 如何讓 Stock / Betting / Novel 後續對齊這套架構？

---

# REQUIRED STRUCTURE

請用以下結構輸出。

## 1. Executive Decision

請明確回答：

- 是否同意原 roadmap？
- 同意比例大約多少？
- 最重要的修正是什麼？
- 現在最該做的第一件事是什麼？

請避免模糊說法。

## 2. Corrected North Star

請重新定義 LotteryNew 的北極星。

建議方向：

LotteryNew 不再定位為「彩票預測系統」，
而是定位為：

- statistical validation lab
- agent orchestration platform
- safe autonomous scheduling system
- transferable backtesting framework seed project

請說明這個定位的理由。

## 3. Phase -1 — Recovery / Restore / Runtime Safety

這是我要求你新增的階段。

目標：

- 確認 H6 false rollback 是否已 restore
- 若未 restore，先完成 dry-run verification
- 確認 rollback guard 已由 backend 載入
- 確認 DAILY_539 active/shadow 狀態正確
- 確認 pending outcome flow 不會再次造成 false rollback
- 暫停不必要的 H6 rollback follow-up

Deliverables：

- h6_guard_reload_restore_verification.md
- active/shadow restore status
- backend guard reload verification
- no immediate re-rollback verification
- daily_539 monitoring status reset or deferred safely

Acceptance Criteria：

- one-outcome ROI=-1.0 不會觸發 rollback
- active/shadow 正確或 restore pending clearly documented
- production mutation 有 backup
- no Worker / Planner accidental mutation
- no external LLM call

## 4. Phase 0 — Platform Invariants

目標：

把所有已知安全機制升級成平台 invariant，而不是散落 script。

必須包含：

- no-audit-no-call
- rollback guard config-managed
- outcome recorder dry-run / isolated / confirm-production
- stale RUNNING lock auto-release
- LLM cap enforcement
- safe-run / hard-off
- production write audit
- restore script backup required

請列出：

- work items
- priority
- risks
- files/modules
- tests
- acceptance criteria

## 5. Phase 1 — Architecture Consolidation

目標：

讓系統可長期維護。

必須包含：

- module boundaries
- BFF API
- schema versioning
- config management
- feature flags
- single source of truth
- dashboard consolidation
- DB path governance
- migration dry-run / apply
- startup health checks

請把 orchestrator / strategy engine / backtest engine / monitoring / outcome recorder / LLM governance / UI dashboard 的邊界定義清楚。

## 6. Phase 2 — Scientific Closure for Lottery

目標：

不是繼續找神奇策略，而是完成彩票研究的科學閉環。

必須包含：

- randomness audit final verdict
- predict-vs-actual v2 mandatory gate
- multiple testing registry
- circular-match bias CI gate
- leakage detector
- strategy retire policy
- NO SIGNAL closure criteria

請明確分類：

A. 值得做：
- randomness audit
- payout EV / unpopular-number advisory
- physical bias candidate advisory
- covering design advisory

B. 應停止：
- historical-pool max-hit
- uncorrected grid search
- short momentum promotion
- no McNemar / no OOS promotion
- 任何宣稱保證提高彩票中獎率的策略

## 7. Phase 3 — Evidence-driven Scheduler v1

目標：

讓 Planner 從 backlog-driven 變成 evidence-driven。

必須設計：

- EvidenceCollector
- EvidenceItem schema
- task scoring formula
- local planner
- task dedupe
- failure taxonomy
- lessons update loop
- feedback-to-guard loop
- LLM budget governance
- startup catch-up

請先設計 v0.1，不要等到半年後才開始。

v0.1 只需要 6 個 evidence source：

1. failed_tests
2. stale_data
3. missing_outcomes
4. monitoring_degraded
5. llm_usage_high
6. rollback_false_positive

## 8. Phase 4 — Generic Backtest Framework

目標：

把 Lottery 的方法論抽象成跨系統 framework。

必須包含：

- permutation_null
- walk_forward_oos
- multi_window
- bonferroni
- bh_fdr
- circular_bias_detector
- leakage_detector
- effect_size
- hypothesis_registry

請定義：

- package structure
- public API
- strategy interface
- data interface
- result schema
- registry schema
- tests

並說明如何套用到：

- Stock
- Betting
- Novel / A-B testing / marketing experiments

## 9. Phase 5 — Stock / Betting / Novel Migration

目標：

不是直接複製 Lottery 系統，而是複製它的 governance 和 validation framework。

請分別說明：

### Stock

需要：

- walk-forward OOS
- leakage detector
- transaction cost
- drawdown / Sharpe / Sortino
- no look-ahead
- hypothesis registry

### Betting

需要：

- CLV
- market odds
- bankroll / Kelly
- edge realism filter
- regime classifier
- liquidity / line movement

### Novel

需要：

- evidence-driven task planning
- UI / e2e test feedback
- content consistency checks
- prompt template regression
- no uncontrolled LLM spending

## 10. Revised 30 / 60 / 90 Day Plan

請重新排優先順序。

30 天內應該優先：

1. Phase -1 restore verification
2. rollback guard platform invariant
3. no-audit-no-call CI
4. LLM caps enforcement
5. EvidenceCollector v0.1
6. randomness audit final verdict draft

60 天內：

1. BFF API
2. schema versioning
3. module boundaries
4. Strategy Evaluation Framework v0.5
5. hypothesis registry
6. dashboard consolidation

90 天內：

1. Strategy Evaluation Framework v1
2. Circular-bias CI gate
3. Leakage detector
4. Local Planner v0.5
5. Generic backtest framework skeleton
6. Stock / Betting POC design

## 11. Program Backlog

請列至少 40 個任務。

每個任務包含：

| ID | Phase | Workstream | Task | Priority | ROI | Risk | LLM Needed? | Acceptance Criteria |

請特別標出：

- Must do now
- Do after restore
- Do after architecture
- Do after scientific closure
- Do only if signal exists

## 12. Kill Criteria / Stop Criteria

這一節很重要，原 roadmap 不夠強。

請定義：

### 彩票策略研究 stop criteria

例如：

- 三遊戲 randomness audit 無顯著偏差
- predict-vs-actual v2 連續 N 次 NO SIGNAL
- OOS Sharpe <= 0
- Bonferroni / BH-FDR 後不顯著
- effect size 小於 noise floor

達成後：

- 不再新增 prediction strategy
- 僅保留 advisory / monitoring

### Agent 任務 stop criteria

例如：

- 同一 dedupe_key 失敗 3 次
- Copilot usage 超 cap
- schema mismatch
- production mutation risk
- audit missing

### LLM usage stop criteria

例如：

- per-provider daily cap exceeded
- per-task call count > 3
- audit missing
- repeated failed calls
- token unavailable but call count high

## 13. Governance Rules

請產出不可違反的 governance rules：

- no audit, no call
- no dry-run, no production write
- no isolated DB test, no production outcome write
- no hypothesis registration, no strategy validation
- no OOS, no promotion
- no multiple testing correction, no signal claim
- no minimum outcome count, no rollback
- no user confirmation, no restore
- no local evidence, no planner task
- no cap, no external LLM

## 14. First 12 Execution Prompts

請產出 12 個可以直接交給 Agent 的 prompt。

每個 prompt 要包含：

- role
- task
- strict rules
- files to inspect
- acceptance criteria
- expected verdict

前 12 個建議包含：

1. H6 guard reload + restore dry-run verification
2. No-audit-no-call CI gate
3. LLM caps enforcement
4. Rollback guard config-managed module
5. Outcome gate unified interface
6. Stale RUNNING lock auto-release
7. EvidenceCollector v0.1
8. Randomness audit final verdict
9. Hypothesis registry CLI
10. Strategy Evaluation Framework v0.5
11. Circular-bias CI gate
12. BFF API consolidation

## 15. Final Recommendation

最後請明確回答：

1. 原 roadmap 是否可採用？
2. 採用前必須改哪三點？
3. 彩票預測研究是否繼續？
4. 系統工程是否繼續？
5. Self-learning scheduler 是否繼續？
6. Stock / Betting / Novel 何時開始遷移？
7. 第一個要交給 Agent 的任務是什麼？

---

# HARD RULES

請務必遵守：

1. 不要承諾彩票一定能提高中獎率。
2. 不要把 NO SIGNAL 視為失敗。
3. 不要忽略 Circular-Match Bias。
4. 不要建議日常 Planner 無限制呼叫 Claude / Codex / Copilot。
5. 不要建議自動 production DB write。
6. 不要建議自動 rollback。
7. 不要移除 audit guard。
8. 不要只寫願景，要給可執行的 phases / backlog / prompts。
9. 不要把 Stock / Betting / Novel 當成完全相同問題，要列 domain-specific risks。
10. 不要跳過 Phase -1 restore verification。

# EXPECTED FINAL POSITION

預期結論應該是：

- 原 roadmap 方向正確，但需要加入 Phase -1 Recovery。
- 彩票策略研究應降為 maintenance-only，不應再無限制尋找新策略。
- 系統工程、LLM governance、Evidence-driven Scheduler、Generic Backtest Framework 是最高 ROI。
- Stock / Betting / Novel 遷移值得做，但必須先完成 framework skeleton 和 governance rules。
- 第一個任務應是 H6 guard reload + restore dry-run verification。
我建議你採用的「實際執行版」

如果只看未來 30 天，我會排成這樣：

順序	任務	原因
1	H6 guard reload + restore dry-run verification	目前還有 false rollback restore pending，這是現況風險
2	No-audit-no-call CI gate	防止 Claude / Codex / Copilot 又失控
3	LLM caps enforcement	你已經遇到 Copilot 額度爆量
4	Rollback guard config-managed	現在只是 code constant，還不是平台 invariant
5	EvidenceCollector v0.1	先讓系統開始 evidence-driven，不要等 6 個月
6	Randomness audit final verdict	幫彩票研究收斂，避免無限挖策略
7	Hypothesis registry CLI	防止 post-hoc strategy mining
8	Strategy Evaluation Framework v0.5	把 predict-vs-actual 變成可重用框架

我的最終看法：

原 roadmap 可以採用 85%。
但必須先補 Phase -1 Recovery，
並把 EvidenceCollector v0.1 提前，
同時把「彩票預測研究」降級成 maintenance / advisory，
把主力轉到 system engineering + generic framework。

這樣比較不會繼續陷入「修一個策略、跑一次回測、再修一個 UI」的循環。