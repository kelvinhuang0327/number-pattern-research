# LotteryNew — Master Roadmap (2026-05-07 Successor)

> SUPERSEDED 2026-05-08: Priority table and next-focus guidance have been
> replaced by `00-LotteryPlan/20260508/lottery_roadmap_20260508.md`.
> This file remains as the 2026-05-07 historical baseline.

**Version:** 2026-05-07 successor v1.0
**Effective:** 2026-05-07
**Supersedes:**
- `00-LotteryPlan/lottery_roadmap_20260503.md` (origin)
- `00-LotteryPlan/MASTER_ROADMAP_CONVERGED_20260504.md` (converged)
- `00-LotteryPlan/20260506/LOTTERY_RESEARCH_REVALIDATION_ROADMAP_20260506.md` (P1 ranking)

**Author:** CTO Agent
**Authority:** `wiki/README.md → wiki/system/* → memory/lessons.md`
**Backing analysis:** `00-LotteryPlan/20260506/CTO_DAILY_ANALYSIS_20260507.md`

> 收斂原則：已驗證完成項目移入 §3 Completed Registry；只減不增；每 priority 帶可驗證 acceptance criteria；舊版以 SUPERSEDED 標記，不刪除。

---

## 1. Executive Summary

LotteryNew 經 2026-05-04 至 2026-05-06 三日治理衝刺，已**完成原 60-day plan 的 P0 + P1-Rank1~3**：rollback guard / outcome gate / no-audit-no-call / LLM caps / Circular-Bias CI / Hypothesis Registry / Strategy Eval v0.5 / Leakage Detector v0.5 / EvidenceCollector v0.1。

**現階段定位（保持不變，沿用 converged roadmap §2）：**
1. Statistical Validation Lab（NO SIGNAL 為科學成功）
2. Agent Orchestration Platform
3. Safe Autonomous Scheduling System
4. Transferable Backtesting Framework

**現階段最大單一阻塞：Leakage Detector 雙系統並存** — `tools/leakage_detector.py`（v0.5 新版，被 strategy_eval 引用）與 `lottery_api/models/backtest_framework.py:DataLeakageError`（舊版，被 RollingBacktester 直接使用）**互不引用**。Strategy Eval CLI 之外路徑形同空門。

**未來 14 天目標：**
1. 把已建立的治理閘鎖死（Module Boundaries、Forbidden Patterns 升 wiki、Cadence Gate）
2. 堵旁路（Leakage Detector 整合到 RollingBacktester）
3. 補完 trusted source-of-truth（Randomness Verdict 完整化）

**禁止行為**：任何新策略研究、任何 prediction-signal 探索、任何繞過 hypothesis pre-registration 的驗證。

---

## 2. Knowledge Gate Compliance

本 roadmap 僅基於 trusted sources：

- `wiki/README.md`
- `wiki/system/governance.md`
- `wiki/system/validation_gates.md`
- `wiki/system/controlled_edge_discovery.md`
- `wiki/system/randomness_final_verdict.md` (Minimal v1.0)
- `wiki/system/strategy_retirement_policy.md`
- `wiki/system/orchestrator.md`
- `wiki/system/feedback_loop.md`
- `memory/lessons.md` L01–L140

未引用 archive / rejected / 散落 root markdown 等 untrusted 來源。`outputs/` 僅用於驗證任務狀態，不作 verdict 依據。

---

## 3. Completed Items Registry — DO NOT RE-LIST

下列項目已驗證完成，不得列為待辦。CI gate 防回退。

### Phase -1 / Phase 0（Production Safety）

| 原 ID | 名稱 | 完成日期 | Source-of-truth |
|---|---|---|---|
| Phase -1 | H6 false rollback restore | 2026-05-04 | `scripts/h6_restore_false_rollback.py` + active=H6_gate_mk20→ew85 |
| P0-01 | Rollback Guard config-managed | 2026-05-04 | `orchestrator/rollback_guard.py`, 88 tests |
| P0-02 | Outcome Gate Unified Interface | 2026-05 | `orchestrator/outcome_gate.py` |
| P0-03 | No-audit-no-call CI Gate | 2026-05-04 | `tests/test_no_audit_no_call_ci.py` + `tools/scan_external_llm_calls.py` |
| P0-04 | Stale RUNNING Lock Auto-Release | 2026-05 | `orchestrator/stale_lock_recovery.py` |
| P0-05 | Restore Script Dry-Run / Backup | 2026-05-04 | `outputs/h6_pre_restore_backup.json` |
| P0-06 | EvidenceCollector v0.1 (3 sources) | 2026-05 | `orchestrator/evidence/collector.py` |
| GOV-01 | LLM Caps Enforcement (per-role/provider) | 2026-05-04 | `orchestrator/llm_caps.py`, 33 tests |

### P1 Governance Lock-in（2026-05-06 Revalidation 5 Ranks）

| 原 Rank | 名稱 | 完成日期 | Source-of-truth |
|---|---|---|---|
| Rank 1 | Circular-Bias CI Gate | 2026-05-06 | `tests/test_no_circular_match.py` + fixture; passing 14 tests |
| Rank 2 | Hypothesis Registry CLI | 2026-05-06 | `registry/hypotheses.jsonl` + `tools/registry/cli.py`; 29 tests |
| Rank 3 | Strategy Evaluation Framework v0.5 | 2026-05-06 | `tools/strategy_eval/cli.py` + `tools/leakage_detector.py`; 39 tests; 6-gate pipeline |
| Rank 3 inserted | Leakage Detector v0.5 (minimal) | 2026-05-06 | `tools/leakage_detector.py` |

### Other Locked Items

| 名稱 | Source-of-truth |
|---|---|
| Strategy Retirement Policy R01–R10 | `wiki/system/strategy_retirement_policy.md` |
| Hypothesis Registry sentinels | `registry/hypotheses.jsonl` (BIG_LOTTO, POWER_LOTTO sentinels) |
| Predict-vs-Actual v2 SOP | `wiki/system/predict_vs_actual_sop.md` |
| Controlled Edge Discovery Path | `wiki/system/controlled_edge_discovery.md` v1.2 |
| Daily 539 H6 Production | `wiki/games/daily_539.md` + `docs/H6_PRODUCTION_GO_LIVE_SUMMARY.md` |
| Worker GPT-5 mini config | `worker_copilot_model=gpt-5-mini` |
| Safe defaults | scheduler_enabled=0, planner=off, CTO=local, safe-run=on |
| LLM usage dashboard | Planner/Worker/CTO summary, Copilot focus |

### Locked Platform Invariants（CI 防回退）

1. no-audit-no-call（scanner + allowlist）
2. no-cap-no-call（cap_check → audit_attempt → execute → audit_result）
3. rollback-guard config-managed（min_outcomes_for_rollback=5；one-outcome rollback 永久禁用）
4. scheduler-default-off
5. planner-external-llm-cap=0
6. CTO-external-llm-cap=0
7. production-write-requires-confirm（`--write` AND `--confirm-production-outcome`）
8. no-auto-rollback（CTO review 必要）
9. multiple-comparison-correction-mandatory（Bonferroni + BH-FDR）
10. circular-bias-ci-gate（`tests/test_no_circular_match.py`）
11. backup-before-restore（restore script 寫前備份）
12. hypothesis-pre-registration-required（strategy_eval 必須 `--hypothesis-id`）

---

## 4. Updated Priority Table

### P0 — This Week (Day 1–3, 2026-05-07 → 2026-05-10)

| ID | Item | Days | Reason | Acceptance Criteria |
|---|---|---|---|---|
| **P0-A** | **Module Boundaries v0.1**（`wiki/system/module_boundaries.md`） | 0.5 | 過去 14 天新增 9 個 governance modules，無 boundary 文件保護 | 文件涵蓋：lottery_api / orchestrator / orchestrator/governance / orchestrator/evidence / scripts / tools/registry / tools/strategy_eval / tools/leakage_detector / wiki/system；至少 1–2 條紅線；wiki/README routing 已加 |
| **P0-B** | **Forbidden Patterns 升 wiki**（`wiki/system/forbidden_strategy_patterns.md`） | 0.25 | trust hierarchy 一致性；governance.md §高風險文件已將 outputs/ 列為 untrusted | 文件從 `outputs/` 完整搬入；舊位置加 superseded 標記；`memory/lessons.md` L139 引用更新 |
| **P0-C** | **Randomness Audit Cadence Gate**（`tests/test_randomness_audit_cadence.py` + metadata json） | 0.5 | T4 trigger 形式上開放、實質無偵測機制 | 測試讀 `outputs/randomness_audit/randomness_audit_summary.md` 解析 last_run_date；若超過 50 draws 或 audit 缺失 → fail/warn；不依賴網路 |

### P1 — Next Two Weeks (Day 3–14)

| ID | Item | Days | Reason | Acceptance Criteria |
|---|---|---|---|---|
| **P1-A** | **Randomness Final Verdict 完整化** | 1.0 | source-of-truth 仍為 Minimal | 文件 §1 Final Verdict Summary、§2 Game-Level Verdict Table（per-game：draw-process verdict, predict-vs-actual verdict, monetization verdict, current strategy posture, allowed future action, source artifact）、§3 Evidence Source Table、§4 Reopen Conditions、§5 Hard Stops 全部補完；wiki/README routing 更新 |
| **P1-B** | **Leakage Detector ⇆ RollingBacktester 整合** | 1.5 | 雙系統並存 = 治理閘只擋 strategy_eval 入口 | `tools/leakage_detector.py:DataLeakageError` 升為公開 API；`lottery_api/models/backtest_framework.py:RollingBacktester` 改 import 此 API；舊 `DataLeakageError` 標 deprecated；新增 leakage 整合 test，破壞性 fixture FAIL |
| **P1-C** | **Strategy Eval v0.5 hardening** | 0.5 | Gate 4/5 仍是 dry-run-only；可能誤導下游 agent | Gate 4 missing data 從 WARNING → BLOCK（可選 `--allow-incomplete` flag 但不能 promotion）；Gate 5 在 verdict.classification 強制標 `INSUFFICIENT_METADATA`；report.json 加 `v05_limitation: true` 欄位 |
| **P1-D** | **Multiple Testing Registry** | 1.0 | grid search 仍需手動校正 | `registry/multiple_testing.jsonl`；CLI register/list/check；Strategy Eval Gate 6.5 自動 BH-FDR 跨 hypothesis family |

### P2 — Next Month (Day 14–35)

| ID | Item | Days | Reason | Acceptance Criteria |
|---|---|---|---|---|
| **P2-A** | **Strategy Eval v0.5 → v1**（Walk-forward OOS 自動化、multi-window 真實執行、leakage metadata enforcement） | 3–5 | 讓 strategy_eval 真正能 confirm，而不只是 block | Gate 5 在 150/500/1500p 各自跑完整 WF OOS；Gate 4 強制 leakage metadata；report.json schema bump 至 v1.0；舊版 v0.5 verdict（DRY_RUN_ONLY/INSUFFICIENT_METADATA）保留為 fallback |
| **P2-B** | **Strategy Eval report schema versioning** | 0.5 | 為未來 framework 抽象做準備 | report.json 加 schema_version 欄位；舊報告自動標 v0.5 |
| **P2-C** | **EvidenceCollector v0.1 → v0.3**（從 3 → 6 sources） | 2 | 已啟動，繼續推進 | 新增 failed_tests / stale_data / monitoring_degraded / strategy_no_signal；7-day staging 每日 ≥1 EvidenceItem |
| **P2-D** | **BFF API v0.5**（top-3 UI 資料來源收斂） | 2 | UI 多入口問題開始解決 | `api/bff.py` handles summary + strategies + tasks；UI 60% 走 BFF |

### P3 — Next Quarter (Day 35–90+)

| ID | Item | Reason |
|---|---|---|
| P3-01 | EvidenceCollector v1（18 sources） | 從 v0.3 漸進擴充 |
| P3-02 | Local Planner v0.5（evidence-driven, no LLM） | 需 EvidenceCollector v0.3+ stable |
| P3-03 | `tools/backtest_framework/` v0.1 skeleton | 從合併兩套 leakage detector + circular_bias_detector 開始抽象（不是從零） |
| P3-04 | Schema versioning + migration registry | DB schema 漂移防護 |
| P3-05 | Config management（pydantic settings） | 增量遷移；現有 DB settings 先保留 |
| P3-06 | Stock POC（用 backtest_framework v0.1） | 至少 3 個 hypothesis WF OOS |
| P3-07 | Betting POC（用 backtest_framework v0.1） | 至少 3 個 hypothesis WF OOS |

### STOP — 不再做

維持 converged roadmap §7 + revalidation roadmap §3 全部 STOP 條目：

| Item | Reason |
|---|---|
| historical-pool max-hit | v1 INVALID（L132/L139；circular-match bias） |
| 任何形式的 circular-match bias | 同上 |
| 未經 Bonferroni / BH-FDR 校正的 grid search | 違反 invariant 8 |
| SHORT_MOMENTUM / LATE_BLOOMER promotion | L-lessons 已封 |
| 無 McNemar vs incumbent 的 promotion | validation_gates §強制封鎖 |
| 鄰號共現 / Lift<1.0 注入 | L08 |
| Gap Dynamic Threshold 偽信號 | L07 |
| Day-of-Week 效應 | L27 |
| 跨彩種結論借用 | L21 |
| MicroFish 2-bet 同家族微調復活 | L128 |
| H013 pool-size 同家族微調復活 | L129 |
| Pool-size / market-behavior / sales-related 新研究 | L129 |
| 「保證提升中獎率」研究路線 | scientific impossibility per NO SIGNAL verdict |
| Post-hoc unregistered hypothesis | R09 + Hypothesis Registry pre-flight gate |
| 任何主動 production write 不經 `--confirm-production-outcome` | invariant 7 |
| 任何 auto rollback | invariant 8 |
| **新增**：strategy_eval 結果為 DRY_RUN_ONLY / INSUFFICIENT_METADATA 時宣稱 NO_SIGNAL 結論 | v0.5 限制；混淆 confirm 與 absent |

---

## 5. Revised 30 / 60 / 90 Day Plan (from 2026-05-07)

### Next 30 Days (2026-05-07 → 2026-06-06)

**Target Outcome**: P0 完成；P1 全部完成；Strategy Eval 真正可用

| # | Deliverable | Source-of-truth | Success Criteria |
|---|---|---|---|
| 1 | `wiki/system/module_boundaries.md` | wiki | 9 modules 邊界清楚；至少 2 條紅線 |
| 2 | `wiki/system/forbidden_strategy_patterns.md` | wiki | 從 outputs/ 完整搬入 |
| 3 | `tests/test_randomness_audit_cadence.py` | tests | 50 draws cadence gate 可 fail 過期 audit |
| 4 | `wiki/system/randomness_final_verdict.md` 完整版 | wiki | 三遊戲 verdict 表、Reopen + Hard Stops 完整 |
| 5 | Leakage Detector ⇆ RollingBacktester 整合 | tools + lottery_api | 兩處同一 API；舊版 deprecated |
| 6 | Strategy Eval v0.5 hardening | tools | Gate 4/5 missing data → BLOCK |
| 7 | Multiple Testing Registry | registry | grid search 自動 BH-FDR |
| 8 | Strategy Eval v1（WF OOS 自動化） | tools | Gate 5 真實跑 150/500/1500p |

**Day 30 Measurable Success Criteria:**
- ✅ 治理閘 12 條 invariants 全部有 CI test 防回退
- ✅ Strategy Eval CLI 對 1 個 game 跑出 NO_SIGNAL or SIGNAL_NON_MONETIZABLE 真實 verdict（不是 DRY_RUN_ONLY）
- ✅ Leakage Detector 唯一 source（雙系統合併）
- ✅ Randomness audit cadence gate 阻擋 >50 draws 過期 verdict
- ✅ wiki source-of-truth 三大支柱（governance / validation_gates / randomness_final_verdict）全部完整

### Next 60 Days (2026-06-06 → 2026-07-06)

**Target Outcome**: 架構收斂；EvidenceCollector v0.3；Strategy Eval framework 進入抽象前準備

| # | Deliverable | Success Criteria |
|---|---|---|
| 1 | EvidenceCollector v0.3（6 sources） | 7-day staging 每日 ≥1 EvidenceItem/source |
| 2 | BFF API v0.5（top-3 UI sources） | UI 60% 走 BFF |
| 3 | Strategy Eval report schema v1.0 | versioned；舊報告 fallback |
| 4 | Local Planner v0.3（讀 evidence/items.jsonl，dedupe，無 LLM） | 7-day 跑出 ≥30% local-planner 任務 |
| 5 | `tools/backtest_framework/` v0.1 skeleton | 抽出 leakage_detector + circular_bias_detector 為獨立 modules |

**Day 60 Measurable Success Criteria:**
- ✅ Strategy Eval framework 跨 3 遊戲跑通
- ✅ EvidenceCollector v0.3 持續產出
- ✅ Local Planner 開始接管部分 backlog
- ✅ Backtest Framework 模組化第一步完成

### Next 90 Days (2026-07-06 → 2026-08-05)

**Target Outcome**: 架構抽象 + 跨 domain 驗證準備

| # | Deliverable | Success Criteria |
|---|---|---|
| 1 | EvidenceCollector v1（18 sources） | 18 sources, 14-day staging non-empty |
| 2 | Local Planner v0.5（任務佔比 ≥50%） | 外部 LLM tasks <50%/day |
| 3 | `tools/backtest_framework/` v0.1 完整版 | permutation_null + walk_forward_oos + circular_bias_detector + leakage_detector + bh_fdr + bonferroni |
| 4 | Stock POC seed | 1 hypothesis 用 framework 跑 WF OOS |
| 5 | Strategy retire policy auto-trigger | 連續 N 期 NO SIGNAL 自動 retire（仍需 CTO confirm） |

**Day 90 Measurable Success Criteria:**
- ✅ Backtest framework 模組化，支援 lottery + stock 兩 domain
- ✅ Local Planner 運轉穩定
- ✅ 三遊戲 randomness audit 持續週期執行
- ✅ 任何 production mutation 仍須手動 confirm（invariant 不退）

---

## 6. Risk Register (Top 10, Refreshed)

| # | Risk | Impact | Likelihood | Mitigation | Detection Signal |
|---|---|---|---|---|---|
| R01 | Future agent 把 leakage_detector / strategy_eval 邏輯 inline 到 strategy 中 | HIGH | MED | Module Boundaries 文件 + CI 強制 | 跨 module import 違規 |
| R02 | Strategy Eval v0.5 INSUFFICIENT_METADATA 被誤讀為 NO_SIGNAL | HIGH | MED | hardening (P1-C) + 新增 STOP 條目 | report.json verdict.classification 與下游解讀衝突 |
| R03 | RollingBacktester 走舊 DataLeakageError 路徑，繞過 v0.5 leakage detector | CRITICAL | HIGH | P1-B 整合 | grep `lottery_api.*DataLeakageError` 沒導向新 API |
| R04 | Randomness Audit > 50 draws 未更新 | MEDIUM | HIGH | P0-C cadence gate | `outputs/randomness_audit/` mtime > threshold |
| R05 | 新 agent 增加策略 mining 任務（無 hypothesis_id） | HIGH | MED | strategy_eval 強制 `--hypothesis-id` + invariant 12 | strategy_eval run 缺 hypothesis_id |
| R06 | EvidenceCollector v0.1 staging 沒有實際輸出 | MEDIUM | MED | 加 monitoring task；7-day staging review | evidence/items.jsonl mtime > threshold |
| R07 | False rollback 重發（rollback_guard 配置漂移） | CRITICAL | LOW | invariant 3 + CI 88 tests | rollback proposal 違反 min_outcomes=5 |
| R08 | LLM 配額爆量 | HIGH | MED | invariant 1+2；llm_caps_dashboard | per-role/provider > 80% |
| R09 | wiki / docs drift（routing 失效） | MEDIUM | HIGH | wiki freshness CI（P3） | wiki/README routing 引用不存在檔案 |
| R10 | Module Boundaries 第一版過嚴 → 阻擋合理重構 | LOW | MED | v0.1 只列現況 + 1–2 條紅線；不規範細節 | 重構 PR 卡 boundary check |

---

## 7. 與前版 roadmap 的差異

### 7.1 與 2026-05-03 原版差異
- **拋棄**：Phase 0–5 線性月份切割（與實況落差太大）
- **保留**：四層定位、彩票 maintenance-only 結論、framework 遷移方向、所有 STOP 條目
- **新增**：Phase -1 Recovery、12 條 Locked Invariants、Completed Items Registry

### 7.2 與 2026-05-04 Converged 差異
- **採納**：所有 Locked Invariants、Stop List、四層定位
- **更新**：把 P0 全部標 DONE；EvidenceCollector v0.1 標 DONE
- **修正**：Strategy Eval v0.5 / v1 拆兩階段，明確 v0.5 限制

### 7.3 與 2026-05-06 Revalidation 差異
- **採納**：5 Rank 整體方向、Sequenced Acceptance Criteria 風格、Items Removed
- **更新**：Rank 1–3 全部標 DONE
- **重排**：把 Rank 5（Module Boundaries）提升到 P0-A；把 Cadence Gate 與 Verdict 完整化拆解；加入 Leakage Detector ⇆ RollingBacktester 整合 為新 P1
- **修正**：每日報告把 Module Boundaries 排在第三優先，本版升為第一

---

## 8. 每日 SOP（給下個 agent）

1. **開工前必讀**：
   - `wiki/README.md`
   - `wiki/system/governance.md`
   - 本檔案
   - `00-LotteryPlan/20260507/CTO_DAILY_ANALYSIS_20260507.md`

2. **若任務涉及 production state / DB / active strategy / rollback / outcome**：
   - 必須走 `--dry-run` → isolated DB → `--confirm-production-outcome` 三段
   - 不得 auto rollback
   - 不得修改 invariant 配置

3. **若任務涉及 strategy / backtest / edge claim**：
   - 必須先 `tools/registry/cli.py register --hypothesis-id ...`
   - 必須走 `tools/strategy_eval/cli.py evaluate ...`
   - 不得直接呼叫 `RollingBacktester` 而繞過 leakage detector
   - report.json 為 DRY_RUN_ONLY / INSUFFICIENT_METADATA 時，**禁止宣稱 NO_SIGNAL**

4. **若任務涉及 wiki / docs**：
   - 變更 wiki 必須在 `wiki/system/governance.md` 底部加更新記錄
   - 新增文件必須在 `wiki/README.md` routing 表加入

5. **任務完成回報格式（沿用 2026-05-06 daily report 格式）**：
   - Completed
   - Files Created / Modified
   - Validation（PASS / FAIL / NOT RUN）
   - Remaining Gaps
   - Final Marker（`P*_VERIFIED` 或 `P*_PARTIAL` 或 `P*_REQUIRES_FIX`）

---

## 9. Final Recommendation

### 彩票策略研究是否值得繼續投入？
**保守建議：低 ROI，僅維持 maintenance-only 模式。**
依據：v2 predict-vs-actual 三款 NO SIGNAL（Bonferroni × BH-FDR 後）；最近 randomness audit `WEAK_DEVIATIONS_NOT_SIGNIFICANT_AFTER_CORRECTION`。**這是科學成功，不是失敗**。

### 系統工程優化是否值得投入？
**高 ROI，強烈建議投入。** 過去 14 天在治理閘建立上的執行密度證明這條路可行。下一階段最高 ROI 是把已建立的閘**鎖死 + 堵旁路**，而不是立即抽象成跨 domain framework。

### 排程自我學習是否值得投入？
**中 ROI，已啟動，需強治理與成本控制。** EvidenceCollector v0.1 在位；下一步是 v0.3 + Local Planner v0.5。但 Local Planner 在 evidence sources 不穩前不應接管 production planning。

### Stock / Betting / Novel 遷移時程？
**Day 60–90 啟動 framework 抽象，Day 90+ 啟動 Stock POC**。比原 roadmap Phase 4 (Month 9–12) 提前約 3 個月，但這是**合併現有兩套 leakage detector + circular_bias_detector** 的副產物，不是從零建立。

---

## 10. Appendix — Trusted Sources Used

依 Knowledge Gate 規則，本 roadmap 僅基於以下 trusted sources：

- `wiki/README.md`
- `wiki/system/governance.md`
- `wiki/system/validation_gates.md`
- `wiki/system/controlled_edge_discovery.md`
- `wiki/system/randomness_final_verdict.md` (Minimal v1.0)
- `wiki/system/strategy_retirement_policy.md`
- `wiki/system/orchestrator.md`
- `wiki/system/predict_vs_actual_sop.md`
- `wiki/system/feedback_loop.md`
- `wiki/system/llm_governance.md`
- `wiki/system/stability_audit.md`
- `memory/lessons.md` (L01–L140)
- `00-LotteryPlan/lottery_roadmap_20260503.md` (作為 CTO 對齊比對的歷史錨點)
- `00-LotteryPlan/MASTER_ROADMAP_CONVERGED_20260504.md`
- `00-LotteryPlan/20260506/LOTTERY_RESEARCH_REVALIDATION_ROADMAP_20260506.md`
- `00-LotteryPlan/20260506.md` (yesterday's daily report)
- 直接驗證：`tools/`, `orchestrator/`, `tests/`, `registry/`, `outputs/randomness_audit/randomness_audit_summary.md`, `outputs/active_strategy_state.csv`

未引用 archive / rejected / 散落 root markdown 等 untrusted 來源。

---

## 11. Update Record

| Date | Author | Change |
|------|--------|--------|
| 2026-05-07 | CTO Agent | 建立 successor v1.0；以 Completed Registry 收斂 P0/P1-Rank1~3；重排剩餘 P0/P1/P2 priority；Module Boundaries 提升到 P0；Leakage Detector ⇆ RollingBacktester 整合升為 P1-B；新增第 12 條 invariant（hypothesis-pre-registration-required）與新 STOP 條目（v0.5 verdict 不得宣稱 NO_SIGNAL） |

**Final Marker:** `MASTER_ROADMAP_20260507_VERIFIED`

---

**End of Master Roadmap (2026-05-07 successor) v1.0**
後續更新請以新的 dated successor 形式提出，並在 `wiki/system/governance.md` 底部記錄日期與摘要。
