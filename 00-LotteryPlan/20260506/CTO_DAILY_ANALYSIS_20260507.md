# CTO Daily Analysis — 2026-05-07

**Author:** CTO Agent
**Authority:** Knowledge Gate `wiki/README.md → wiki/system/* → memory/lessons.md`
**Inputs reviewed:**
- `00-LotteryPlan/lottery_roadmap_20260503.md` (master roadmap, original)
- `00-LotteryPlan/MASTER_ROADMAP_CONVERGED_20260504.md` (converged v1.0)
- `00-LotteryPlan/20260506/LOTTERY_RESEARCH_REVALIDATION_ROADMAP_20260506.md` (P1 re-prioritized)
- `00-LotteryPlan/20260506.md` (yesterday's hand-off report — P1-Rank3 verified)
- Live state: `wiki/system/*`, `tools/`, `orchestrator/`, `tests/`, `registry/`, `memory/lessons.md`

**Verdict in one sentence:**
> Roadmap 大方向正確、進度局部超前；下一階段最高 ROI 是「**把已建立的治理閘變成有牙齒的閘**」 — 而不是新增策略研究或新建抽象層。具體的單點阻塞是 Leakage Detector 未整合到 RollingBacktester，以及 Strategy Eval v0.5 仍是 dry-run-only。

---

## 1. Roadmap 對齊度

### 1.1 進度超前項（v.s. 原 60-day plan）

| Phase / 原 ID | 原計畫時程 | 實際完成 | 證據 |
|---|---|---|---|
| Phase -1 Recovery (codex 補充) | Day 1–7 | ✅ 2026-05-04 | active=H6_gate_mk20→ew85, restore script + backup verified |
| P0-01 Rollback Guard | Day 1–7 | ✅ 2026-05-04 | `orchestrator/rollback_guard.py`, 88 tests |
| P0-02 Outcome Gate Unified | Day 1–14 | ✅ done | `orchestrator/outcome_gate.py` |
| P0-03 No-audit-no-call CI | Day 7–14 | ✅ 2026-05-04 | `tests/test_no_audit_no_call_ci.py` + scanner |
| P0-04 Stale Lock Auto-Release | Day 7–14 | ✅ done | `orchestrator/stale_lock_recovery.py` |
| P0-05 Restore Dry-Run | Day 14–21 | ✅ done | `h6_pre_restore_backup.json` |
| GOV-01 LLM Caps Enforcement | Phase 1 | ✅ 2026-05-04 | `orchestrator/llm_caps.py`, 33 tests |
| **P1-Rank1 Circular-Bias CI Gate** | Day 21–28 | ✅ 2026-05-06 | `tests/test_no_circular_match.py` |
| **P1-Rank2 Hypothesis Registry CLI** | Day 21–28 | ✅ 2026-05-06 | `tools/registry/cli.py`, 29 tests |
| **P1-Rank3 Strategy Eval v0.5** | Day 28–42 | ✅ 2026-05-06 | `tools/strategy_eval/cli.py`, 39 tests |
| P0-06 EvidenceCollector v0.1 | Day 14–21 | ✅ 已啟動 | `orchestrator/evidence/collector.py` 在位 |

**判讀**：原 Master Roadmap 預期 60-day 才能完成 P0 + P1-Rank1~3，**實際在 ~14 天完成**。這是非常好的執行密度，但也意味著**roadmap 已大幅落後實況**，需要重整。

### 1.2 進度落後項

| 項目 | 原計畫 | 實際狀態 | 缺口 |
|---|---|---|---|
| **P1-Rank4 Randomness Verdict 完整版** | Day 28–35 | 🟡 `wiki/system/randomness_final_verdict.md` 為 **Minimal Version 1.0** | per-game 表、Reopen Conditions 完整化、Hard Stops 列表未補 |
| **Randomness Cadence Gate** | Day 35 | ❌ 未啟動 | `tests/test_randomness_audit_cadence.py` 不存在 |
| **P1-Rank5 Module Boundaries** | Day 35 | ❌ 未啟動 | `wiki/system/module_boundaries.md` 不存在 |
| **Forbidden Patterns → wiki** | 插入任務 | ❌ 仍在 `outputs/forbidden_strategy_patterns.md`（untrusted） | source-of-truth 仍在 untrusted layer |
| **Leakage Detector → RollingBacktester 整合** | 插入任務 | ❌ 兩套系統並存，互不引用 | `tools/leakage_detector.py`（v0.5）與 `lottery_api/models/backtest_framework.py:DataLeakageError`（舊）互不相通 |
| **Strategy Eval v0.5 → v1**（WF OOS、multi-window 完整） | Day 60–90 | ❌ Gate 4/5 仍只能標 INSUFFICIENT_METADATA / DRY_RUN_SKIPPED | strategy_eval 目前無法做出 real verdict（除了 DRY_RUN_ONLY） |
| **Multiple Testing Registry** | P1（90 day） | ❌ 未啟動 | grid search 仍需手動校正 |

### 1.3 Roadmap 結構性失準

1. **原 5/3 roadmap 把 EvidenceCollector 放在 Phase 3（Month 6–9）** — 但 codex 補充建議提早，實際也已啟動。原 roadmap 該章節已過時。
2. **原 roadmap 將 Strategy Eval v1 視為單一 deliverable** — 但實際拆成 v0.5（治理入口）→ v1（WF OOS 自動化）。Converged roadmap 已修正，2026-05-07 應正式承認。
3. **原 Phase 4（backtest_framework）在 Month 9–12** — 但 `lottery_api/models/backtest_framework.py` 已存在多月，與 `tools/leakage_detector.py` 並存，**抽象任務不是「從零建立」而是「合併與升格」**。原 roadmap 的描述需更新。
4. **「策略退役政策」（P2-06）** 已實質落地 — `wiki/system/strategy_retirement_policy.md` 完整 R01–R10 條款已存在；不應再列為 P1/P2 待辦。

---

## 2. 關鍵阻塞分析（Top 5）

### B1. Leakage Detector 雙系統並存（CRITICAL）
- 現況：`tools/leakage_detector.py` 是 P1-Rank3 中新建的 v0.5 minimal；`lottery_api/models/backtest_framework.py` 內含老的 `DataLeakageError` 與 `RollingBacktester`。兩者互不引用。
- 風險：任何走 `RollingBacktester` 的 backtest（即所有歷史腳本）**繞過 v0.5 leakage detector**。Strategy Eval v0.5 之外的路徑就是空門。
- 等同：governance gate **只擋 Strategy Eval CLI 入口，不擋舊的 backtest 路徑**。
- 解法：合併到單一介面 — `tools/leakage_detector.py` 應成為 `lottery_api.models.backtest_framework.RollingBacktester` 的 dependency；`DataLeakageError` 升格為 leakage_detector 的公開 API。

### B2. Strategy Eval v0.5 無實際評估能力（HIGH）
- 現況：Gate 4/5 在 cli.py 中明確標 `WARNING_INSUFFICIENT_METADATA` 與 `v0.5: per-window walk-forward OOS not implemented`。
- 風險：任何認為「跑 strategy_eval = 已驗證」的下游 agent 都會誤讀。目前 framework 只能擋下，不能 confirm。
- 影響：`controlled_edge_discovery.md §4` 列的 Gate G5 / G6 / G9 在 v0.5 形式上必過、實質未檢驗。
- 解法：v1 walk-forward OOS 自動化是接下來最大的單一工程任務（估 3–5 天）。但中期可以先把 Gate 4 從「missing → INSUFFICIENT_METADATA」改為「missing → BLOCK」，以避免錯誤晉級。

### B3. Module Boundaries 缺位（HIGH，但低工成本）
- 現況：過去 14 天新增 9 個 governance modules（rollback_guard / outcome_gate / stale_lock_recovery / llm_caps / evidence/collector / leakage_detector / registry / strategy_eval / scan_external_llm_calls），**沒有 module boundary 文件**。
- 風險：下個 agent 把 `leakage_detector` 邏輯 inline 到 strategy / 或把 `hypothesis_id` 寫死在 backtest script，governance 就被拆碎。
- 解法：寫 `wiki/system/module_boundaries.md`（0.5 天工作量）—— 這是**最高 leverage / 最低成本**的單一任務，因為它保護所有其他治理成果不被未來改動拆掉。

### B4. Randomness Final Verdict 仍是 Minimal（MEDIUM）
- 現況：trusted source-of-truth 不完整。per-game table、Reopen Conditions、Hard Stops 都沒列。
- 風險：T4 trigger（randomness deviation reopen edge discovery）形式上開放、實質無觸發機制 — 因為沒有 cadence gate 自動偵測過期，也沒有完整 verdict 可比較。
- 解法：Part A（verdict 完整化）+ Part B（cadence gate）+ Part C（wiki/README routing）—— 這就是 yesterday daily report 推薦的工作。

### B5. Forbidden Patterns 仍在 outputs/（LOW，但有 governance 一致性風險）
- 現況：`outputs/forbidden_strategy_patterns.md` 存在；`memory/lessons.md` L139 引用它；但 governance.md §高風險文件預設將 `outputs/` 視為 untrusted。
- 風險：trust hierarchy 不一致 — wiki 引用 untrusted location。任何 agent 重整 outputs/ 都可能誤刪。
- 解法：直接搬到 `wiki/system/forbidden_strategy_patterns.md`（0.25 天）。

---

## 3. 重新排序的優先順序

我**同意 2026-05-06 re-validation roadmap 的 5 個 Rank 大方向**，但根據 1) 已完成 Rank 1–3，與 2) 上述阻塞分析，把剩餘工作重排為：

### P0（本週內必做，Day 1–3）

| Rank | Item | 估時 | Reason |
|---|---|---|---|
| **P0-A** | **Module Boundaries 文件** (`wiki/system/module_boundaries.md`) | 0.5 天 | 9 個新 governance modules 沒有 boundary 保護；每延一天，未來碎裂風險越大 |
| **P0-B** | **Forbidden Patterns → wiki** (`wiki/system/forbidden_strategy_patterns.md`) | 0.25 天 | trust hierarchy 一致性，極低工成本 |
| **P0-C** | **Randomness Audit Cadence Gate** (`tests/test_randomness_audit_cadence.py` + metadata json) | 0.5 天 | 不需先升 verdict 文件；cadence test 可獨立先建立（可 fail-soft） |

> 三項合計 ~1.25 天。**這是把已建立的治理 hard-lock**，沒有新研究，沒有架構大改。

### P1（兩週內，Day 3–14）

| Rank | Item | 估時 | Reason |
|---|---|---|---|
| **P1-A** | **Randomness Final Verdict 完整化** (per-game table + Reopen Conditions + Hard Stops) | 1 天 | 完成原 Rank 4 Part A；source-of-truth 收齊 |
| **P1-B** | **Leakage Detector ⇆ RollingBacktester 整合** (`tools/leakage_detector.py` 成為 RollingBacktester 的 dependency) | 1.5 天 | 堵唯一旁路；解決雙系統並存 |
| **P1-C** | **Strategy Eval v0.5 hardening**：Gate 4 missing data 從 WARNING 升為 BLOCK；Gate 5 加入「v1-pending」明確 disclaimer 並阻擋 promotion 路徑 | 0.5 天 | 不上 v1 也能避免誤判 |
| **P1-D** | **Multiple Testing Registry**（grid search 自動 BH-FDR） | 1 天 | 與 Hypothesis Registry 同源；目前缺位 |

### P2（一個月內，Day 14–35）

| Rank | Item | 估時 | Reason |
|---|---|---|---|
| **P2-A** | **Strategy Eval v0.5 → v1**：Walk-forward OOS 自動化、multi-window 真實執行、leakage metadata enforcement | 3–5 天 | 讓 strategy_eval 真正能 confirm，不只 block |
| **P2-B** | **Strategy Eval report schema versioning** | 0.5 天 | 為未來 framework 抽象做準備 |
| **P2-C** | **EvidenceCollector v0.1 → v0.3**（從 3 source 擴到 6 source） | 2 天 | 已啟動，繼續推進 |
| **P2-D** | **BFF API v0.5**（top-3 UI 資料來源收斂） | 2 天 | UI 多入口問題開始解決 |

### P3（一季內，Day 35–90+）

依 converged + revalidation roadmap 既定方向：
- EvidenceCollector v1（18 sources）
- Local Planner v0.5（evidence-driven，no LLM）
- `tools/backtest_framework/` v0.1（從合併兩套 leakage detector 開始抽象）
- Stock / Betting POC

### STOP（不再做）

維持 converged roadmap §7：所有 prediction-signal 探索新研究、historical-pool max-hit、無 Bonferroni/BH-FDR 的 grid search、SHORT_MOMENTUM/LATE_BLOOMER promotion、Day-of-Week effect、cross-game borrowing、neighbor co-occurrence Lift<1.0 — 全部 STOP。

---

## 4. 我與每日報告（2026-05-06）的差異

每日報告建議優先順序為：
1. P1-Rank4（Randomness Verdict 完整版）
2. Forbidden Patterns 移 wiki
3. Module Boundaries

**我重排為**：
1. **Module Boundaries 優先於 Randomness Verdict**
2. **Cadence Gate 與 Verdict 完整化解耦**（cadence 先做、verdict 後升）
3. **Leakage Detector 整合升為 P1**（每日報告把它列在「7.1 風險」下、未進入優先順序）

理由：
- Module Boundaries 是「**保護傘**」 — 它保護所有 P1-Rank1~3 已建立的治理閘不被未來打散。**晚一天 = 多一份風險**。
- Cadence Gate 不需要等 verdict 完整化才能寫；先寫 cadence test 反而能逼 verdict 文件保持新鮮。
- Leakage Detector 整合是**治理閘真正有牙齒的關鍵** — 沒整合，strategy_eval 之外的路徑就是空門。每日報告認知到風險、但沒給優先序。

---

## 5. 對 Roadmap 文件的具體更新動作

我直接建立 **`00-LotteryPlan/20260507/lottery_roadmap_20260507.md`**，作為 2026-05-06 revalidation 的 successor。內容要點：

1. **Completed Items Registry** 加入 Rank 1–3、Phase -1、P0-01~P0-06、GOV-01。
2. **P0/P1/P2/P3 表格** 依本文件 §3 重排。
3. **Locked Invariants** 維持原 10 條。
4. **Stop List** 維持原 9 條 + 新增「strategy_eval 回到 historical-pool max-hit 任何變形」。
5. **30/60/90 day plan** 以 2026-05-07 為起點重算。
6. **明確聲明**：roadmap 未來只以 dated successor 方式更新，舊版不刪除、加 SUPERSEDED 標記。

---

## 6. 對 wiki 與 governance 的影響

下列 wiki 文件需在執行 P0-A、P0-B、P0-C 時同步更新（不在本次分析動作範圍內，列為下一個 agent 工作）：

- `wiki/README.md` — 加 routing：`wiki/system/module_boundaries.md`、`wiki/system/forbidden_strategy_patterns.md`、`tests/test_randomness_audit_cadence.py`
- `wiki/system/governance.md` — 在「高風險文件類型」表加 `forbidden_strategy_patterns` 入口移轉紀錄
- `wiki/system/validation_gates.md` — 新增 §Randomness Audit Cadence Gate
- `wiki/system/randomness_final_verdict.md` — 升級至完整版（保留 Minimal Version 為 Appendix）

---

## 7. 風險與不確定點

1. **Strategy Eval v1 工程量被低估的風險**：原 roadmap 把 v1 視為「自動化即可」，但實際上 walk-forward 需要 3-5 天的整合工作（包括 RollingBacktester 改動、prediction file 規格化、metadata enforcement）。應在 P2-A 接收前 spike 1 天確認規模。
2. **EvidenceCollector v0.1 是否真的有 daily output 的風險**：collector.py 在位但未驗證 7-day staging 是否實際產出 EvidenceItem。應加 monitoring task。
3. **Module Boundaries 過嚴的風險**：第一版若把規則寫死，可能阻擋合理重構。建議 v0.1 只列「現況」+「禁止跨界呼叫的 1–2 條紅線」，不規範細節。

---

## 8. 一頁摘要

**現況**：原 roadmap → converged → revalidation 三版迭代健康；P1-Rank1~3 在 14 天內完成（原計 60 天），執行密度高。

**主要差距**：roadmap 沒有反映 Phase 0 / P0-01~06 / GOV-01 已完成，且把 Strategy Eval v1、Leakage Detector 整合的工作量低估。

**最大單一阻塞**：Leakage Detector 雙系統並存 — `tools/leakage_detector.py`（v0.5）與 `lottery_api/.../DataLeakageError`（舊）未串接；strategy_eval 之外路徑全是旁路。

**最高 ROI 下一步**：
1. Module Boundaries（0.5 天）保護已建立的治理層
2. Forbidden Patterns 升 wiki（0.25 天）
3. Randomness Cadence Gate（0.5 天）
4. Leakage Detector 整合（1.5 天）
5. Randomness Verdict 完整化（1 天）

**禁止做**：任何新策略研究、任何沒有 hypothesis 預註冊的 grid search、任何試圖跳過 Strategy Eval 走捷徑驗證的提案。

**Final Marker**：`CTO_DAILY_ANALYSIS_20260507_VERIFIED`
