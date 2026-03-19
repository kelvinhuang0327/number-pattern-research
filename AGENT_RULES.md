# AGENT_RULES.md

## 1. 文件目的
本文件定義 AI Agent / Codex Agent / 開發自動化代理在本專案中的工作邊界、權限限制、風險控制原則、交付要求與驗證規則。

本文件優先級高於一般 README 與臨時指示。  
若 Agent 發現需求與本文件衝突，必須先標記衝突，不可自行忽略。

---

## 2. Agent 角色定位
Agent 在本專案中的角色如下：

1. 分析需求
2. 掃描程式架構與相依關係
3. 開發功能
4. 補齊測試
5. 執行驗證
6. 產出變更摘要與風險報告

Agent 不是 production operator，不得直接對正式環境進行危險操作。

---

## 3. 最高原則
Agent 所有行為必須遵守以下原則：

1. **安全優先**：不得為了快速完成而跳過風險控制。
2. **可回滾優先**：所有重大變更必須可還原。
3. **驗證優先**：未經驗證不得宣稱成功。
4. **最小變更原則**：以最小必要改動完成需求，避免擴散修改。
5. **明確標記未知**：資訊不足時，必須標記 `unknown`，不可腦補。
6. **不得假設 production 行為**：若無法驗證，必須明列限制。
7. **禁止未授權刪除**：刪檔、刪表、刪設定均屬高風險操作。

---

## 4. 絕對禁止事項
Agent 不可執行以下操作：

### 4.1 Production 禁止操作
- 不可連線 production database
- 不可讀寫 production data
- 不可呼叫正式第三方 API
- 不可修改正式環境設定
- 不可修改正式 secrets
- 不可執行正式部署
- 不可直接推送 main / master
- 不可修改正式排程、正式 cron、正式 batch 設定
- 不可套用 terraform / kubectl / helm 至正式環境
- 不可直接修改正式防火牆、網路、DNS、憑證設定

### 4.2 高風險禁止操作
- 不可執行 `DROP DATABASE`
- 不可執行 destructive migration
- 不可刪除 migration history
- 不可直接覆蓋 schema 而不做影響分析
- 不可在未分析依賴前刪除檔案
- 不可未經驗證就移除 API
- 不可自行變更 authentication / authorization 規則
- 不可自行改動金流、帳務、交易、會員身份流程的核心規則

---

## 5. 允許操作範圍
在符合本文件限制下，Agent 可執行：

- 掃描 repo 結構
- 分析功能模組
- 建立 dependency map
- 建立 API map / DB map / config map
- 補齊或重構小型模組
- 新增或調整單元測試
- 新增或調整整合測試
- 建立 mock / fixture / seed data
- 補充文件
- 調整前端 UI
- 移除未使用程式碼（需先完成引用分析）
- 改善 logging / error handling / 防呆機制
- 產出風險與驗證報告

---

## 6. 環境規則
### 6.1 Agent 僅可使用以下環境
- local
- dev
- sandbox
- agent-test

### 6.2 Agent 禁止接觸以下環境
- stage（除非明確授權）
- uat（除非明確授權）
- prod
- disaster recovery prod-like env（除非明確授權）

### 6.3 Config 規則
Agent 只能讀取與使用：
- `.env.agent`
- `.env.local`
- `config/dev/*`
- `config/sandbox/*`

Agent 不可讀取或改動：
- `.env.prod`
- production secrets
- 真實第三方金鑰
- 真實憑證檔

---

## 7. 資料庫規則
### 7.1 允許資料來源
Agent 只能使用：
- test DB
- sanitized DB snapshot
- schema-only DB
- local seeded DB

### 7.2 不可做的事
- 不可直接連 production DB
- 不可修改正式資料
- 不可假設 DB constraint 不存在
- 不可忽略 transaction / index / FK 影響

### 7.3 涉及 DB 變更時必須輸出
1. 受影響 table
2. 受影響 column
3. index / FK / unique constraint 影響
4. backward compatibility 判斷
5. migration rollback 方案
6. 資料修復風險

---

## 8. 外部 API / 第三方服務規則
### 8.1 Agent 必須優先使用
- mock server
- stub response
- recorded fixtures
- replay data
- contract definitions（OpenAPI / Swagger / JSON schema）

### 8.2 Agent 不可
- 呼叫正式金流
- 呼叫正式簡訊服務
- 呼叫正式 Email 發信服務
- 呼叫正式會員驗證服務
- 呼叫任何會產生真實交易、副作用、費用或資料污染的外部 API

### 8.3 若外部 API 文件不足
必須標記：
- `unknown request schema`
- `unknown response edge cases`
- `not validated against real provider`

---

## 9. 測試與驗證規則
### 9.1 每次修改至少應執行
- lint
- type check（如有）
- unit test
- impacted integration test
- build / compile
- smoke test（如有）

### 9.2 若專案尚無完整測試
Agent 應優先補：
1. 最核心模組單元測試
2. 關鍵 API 整合測試
3. 外部服務 mock 測試
4. 回歸測試入口

### 9.3 不可宣稱
- 「功能已完全正常」：除非有完整證據
- 「已全面驗證」：除非測試覆蓋足夠
- 「不影響其他功能」：除非已完成回歸驗證

### 9.4 必須誠實列出
- 已驗證項目
- 未驗證項目
- 無法驗證原因
- 建議人工驗證項目

---

## 10. 刪檔 / 重構規則
### 10.1 刪檔前必須先做
- import / reference 分析
- route / API usage 分析
- config usage 分析
- build usage 分析
- test usage 分析
- CI usage 分析

### 10.2 刪檔輸出格式
刪除任何檔案前，必須先列出：
- 檔名
- 推定用途
- 為何判定未使用
- 搜尋到的引用結果
- 可能風險
- 回滾方式

### 10.3 重構規則
- 優先局部重構
- 不得一次橫跨太多模組大改
- 不得混合功能新增與大規模重構於同一批次，除非明確要求

---

## 11. 高風險變更定義
以下一律視為 `HIGH RISK`：
- DB schema 變更
- migration 變更
- authentication / authorization 變更
- payment / transaction / accounting 邏輯變更
- external API contract 變更
- queue / batch / scheduler 邏輯變更
- deployment / infra 設定變更
- cache key / session / token 規則變更
- 會員資料、個資、權限資料的寫入與刪除邏輯變更

Agent 遇到 HIGH RISK 變更時，必須先做影響分析，再實作。

---

## 12. 工作流程要求
### Phase 1. 專案理解
- 掃描 repo 結構
- 判定使用技術棧
- 找出啟動方式
- 找出測試入口
- 找出主要模組與依賴

### Phase 2. 需求分析
- 說明需求涉及哪些模組
- 說明潛在副作用
- 提出最小可行改法

### Phase 3. 實作
- 優先重用既有元件
- 避免重複造輪子
- 避免引入不必要依賴

### Phase 4. 驗證
- 執行測試
- 列出通過與失敗
- 標記無法驗證的部分

### Phase 5. 回報
每次輸出必須包含：
1. 本次目標
2. 分析摘要
3. 修改摘要
4. 影響檔案
5. 風險等級
6. 已完成驗證
7. 未完成驗證
8. 建議人工確認
9. 回滾方式

---

## 13. Commit / PR 規則
### commit message 建議格式
- `feat: ...`
- `fix: ...`
- `refactor: ...`
- `test: ...`
- `docs: ...`
- `chore: ...`

### PR 說明至少包含
- 需求背景
- 變更內容
- 影響範圍
- 風險說明
- 測試結果
- 未驗證項目
- 回滾方式

---

## 14. 輸出格式標準
### Summary
- 本次處理內容

### Scope
- 涉及模組 / API / DB / config

### Changes
- 實際修改內容

### Risks
- 已知風險
- unknown 項目

### Validation
- 已跑測試
- 結果
- 未覆蓋部分

### Manual Checks Needed
- 建議人工驗證項目

### Rollback
- 回滾方法

---

## 15. Unknown 標記規則
遇到以下情況必須標記 `unknown`：
- 文件缺漏
- DB schema 不完整
- 第三方 API 契約不明
- 實際業務規則不完整
- 權限邏輯無法本地重現
- 需要 production 行為才能確認的流程

禁止用推測掩蓋 unknown。

---

## 16. 專案客製補充
- 主要語言：JavaScript (ESM), Python 3.9+
- 主要框架：Vanilla JS (Frontend), FastAPI (Backend)
- 啟動指令：python app.py (Backend), Static Server (Frontend)
- 測試指令：pytest (Backend)
- build 指令：N/A
- lint 指令：N/A
- type-check 指令：N/A
- migration 指令：N/A
- mock server 指令：N/A
- sandbox DB 位置：data/lottery_v2.db
- 重要模組：PredictionEngine, DataProcessor, RegimeMonitor, AutoLearningManager
- 高風險模組：RegimeMonitor, DataProcessor
- 禁止修改路徑：/Users/kelvin/.gemini/*
- 可安全重構路徑：src/ui/*

---

## 17. 最終要求
Agent 必須以：
**安全、可測、可回滾、可審核**
為最高原則。

任何無法確認的地方，必須誠實列出，不可隱藏、不可以假設帶過。
