已作為 CTO agent 重新校準並直接更新 roadmap：

[lottery_roadmap_20260512.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/00-LotteryPlan/roadmap/lottery_roadmap_20260512.md:1)

核心結論很直接：目前 Replay UI MVP 已接近可上線，但**尚不能誠實宣稱所有策略都有逐期 prediction-vs-actual 真實列**。現在真實狀態是：16 個策略都可見，6 個 ONLINE 有 production replay rows；REJECTED / OBSERVATION 是 `DISPLAY_ONLY`，RETIRED 是 `MISSING_HISTORY`，不能用 fixture 假裝真歷史。

我已把 roadmap 重排為：

- **P0**：P78 configurable API base，解除本機正常瀏覽器無法載入 API 的上線阻塞
- **P1**：全策略 replay truth gap manifest，確認哪些策略可 import / regenerate / tombstone
- **P2**：DAILY_539 40 筆 `FAILED_LEGACY` error rows 語意與來源標籤
- **P3-P5**：provenance-backed retrospective dry-run、storage lane、API contract
- **P6-P7**：UI parity 與受控 apply
- **P8-P10**：H6 evidence、OFFLINE policy、策略 mining/promotion 延後

我也把關鍵阻塞寫進 roadmap：目前工作區是 dirty/divergent feature branch，不能當 main authority；non-ONLINE 策略沒有真實逐期 row；fixture mode 必須嚴格隔離；retired 策略不可從記憶重建。

驗證摘要：`origin/main` 目前是 `d438fb6`，P75/P76/P77 已進 main；runtime replay DB 讀到 460 rows，其中 420 `PREDICTED`、40 `REPLAY_ERROR`，那 40 筆來自 run #3 `FAILED_LEGACY`。本次只更新 roadmap，沒有改 code、DB 或 registry。

# CEO 二次審查 — Replay Truth Coverage 上線決策

**日期:** 2026-05-13  
**身份:** CEO（CTO agent 上級）  
**對齊核心目標:** Strategy Historical Replay 上線，**所有已開發策略**（ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED）均能以「歷史預測清單同構表格」顯示逐期預測 vs 實際開獎比對。

---

## 1. 昨日成果是否真的推進系統成熟度

| 昨日交付 | 表面進度 | 對使用者目標的真實貢獻 |
|---|---|---|
| PR #89 startup hardening 進 main | 開發體驗 +1 | 不直接影響 replay 內容 |
| PR #90 Browser Visual QA evidence | 文件 +1 | 用 Playwright fetch monkey patch 取得，**未經正常瀏覽器驗證** |
| PR #91 Same-origin architecture audit | 分析報告 +1 | 結論是「需要 P78」— 本質為 meta-work |

**CEO 結論:** 昨日是 **infrastructure + diagnosis** 的一天，並非 **product** 的一天。三個 PR 全為 docs/ops 類別，**replay truth surface 真正的內容缺口（10 個非 ONLINE 策略無逐期資料）一行都沒推進**。系統成熟度的「可宣稱可上線度」沒有提升。

但這一天並非浪費 — P77 把 P78 的範圍鎖死，避免了「為了改 same-origin 順手改 backend」的 scope creep 風險。屬於必要但低收益的一天。

---

## 2. CTO 判斷是否合理

### 合理之處（保留）

- 把「MVP 可上線」與「full target 全策略逐期 row」拆開，避免假裝完成 — **正確**。
- 拒絕用 fixture 假裝真實 row — **正確**，這是不可妥協的紅線。
- RETIRED 5 個無原始碼可重建者 tombstone — **正確**。
- P78 是上線 prerequisite — **正確**。
- 不在本階段做策略 mining / promotion — **正確**。

### 過於保守 / 不對齊使用者目標之處

| CTO 判斷 | 問題 | CEO 修正 |
|---|---|---|
| 「Non-ONLINE 策略沒有 per-draw row 是現實限制，未來再說」 | 使用者已明確說「**包含拒絕、觀察等所有系統上開發過的策略**」要看逐期比對。Tombstone 不滿足需求 | REJECTED / OBSERVATION 策略**若 strategy code 存在**，其預測是 deterministic — 可程式化重跑歷史開獎以產生 retrospective rows。這不是捏造，是 reproducible replay |
| P3-P5「provenance-backed retrospective」放在 P78 / manifest / 錯誤標記後面 | 真正符合使用者目標的工作被排到第 4-6 順位 | Retrospective regeneration 應該是 **戰略 P1**，而非 P3 |
| 「Do not write production DB during P0-P5」 | 全策略歷史 row 上線本來就需要寫 DB；把 DB 寫入延後到 P7 等於把上線延後一個月 | DB 寫入禁令應該在 P3（regeneration apply）解除，**前提是 provenance hash + truth_level 標籤 + snapshot rollback** |
| P1 是「產出 manifest（紙上分類）」 | Paperwork 先行容易停在報告，未驗證每個策略 code 是否真的可重跑 | P1 改為 **「以程式碼可執行性為證據的分類」** — 直接 dry-run 嘗試重跑，產出物是「可重跑/失敗原因」實證表 |

### 真正的盲點

1. **使用者目標的 bar 比 CTO 設定的 MVP bar 高一級。**  
   CTO 的 MVP = 「16 策略可見 + 6 ONLINE 有 row + 其餘 tombstone」。  
   使用者要的 = 「16 策略可見 + **每一個策略都能展開看逐期 row**」。  
   差距 = **10 個非 ONLINE 策略的 retrospective row**。Tombstone 不算交付。

2. **P78 雖然是 P0，但 P78 結束時系統仍然沒有產品價值前進。** P78 解決的是「我在瀏覽器看不到頁面」，不是「我看到的頁面內容完整」。P78 必須做，但不應該停在 P78 慶祝。

3. **REJECTED 策略的 audit 價值被低估。** CTO 把 REJECTED 視為「沒有真實 row 的 display-only」。但 REJECTED 策略當初被拒絕時，**backtest 過程本身就產生了 prediction**（拒絕的依據）。這些預測在 `lessons.md`、`rejected/*.json` 裡有殘留證據。應該系統性盤點。

4. **`DISPLAY_ONLY=5` 與 `MISSING_HISTORY=5` 的分類沒有源頭驗證。** CTO 只說「分類好了」，沒給出每個策略對應的 code path / artifact path。CEO 要求 P1 必須輸出 **per-strategy artifact map**（檔案路徑、可執行入口、blocker）。

5. **Truth-level 命名 vs UI 顯示沒有 round-trip 驗證。** Truth badges 已上線（PR #87），但**目前 truth-level 還沒有覆蓋 REGENERATED_RETROSPECTIVE** — UI 還沒準備好接受第 4 種 badge。P78 之後需要驗證 UI 對 REGENERATED 的展示是否相容。

---

## 3. 今天最應聚焦的系統優化方向

**主軸：把 Replay 從「6/16 真實 + 10/16 tombstone」推進到「16/16 有可信 row，每 row 帶 provenance」。**

執行節奏：
- 今天 = P0（P78 plumbing 解除上線 blocker）
- 明天 = P1（程式可執行性盤點，輸出可重跑策略清單）
- 後天起 = P3（dry-run regeneration），P4（DB 寫入 lane + UI badge 擴充）

不做：策略 mining、registry mutation、新功能、PR #88、路徑大重命名。

---

## 4. CEO 重新調整的 P0-P10

| 優先 | 主題 | 與 CTO 差異 | 驗收條件 | Gate |
|---|---|---|---|---|
| **P0** | P78 configurable API base | 同 CTO，**只調整一點**：實作報告須附「下一步 P1 retrospective regeneration 適用策略名單」一節（read-only inventory） | `window.API_BASE` 支援；prod default 維持 `/api/replay`；local dev 可指向 8002；browser smoke 不再需要 fetch monkey patch；DB/registry hash 不變 | `YES implement P78` |
| **P1** | 全策略 **程式可執行性實證盤點**（取代 CTO 的紙上 manifest） | 不只分類，要實際嘗試 import / call 策略入口，輸出每個策略的可重跑性 | 16 策略 + 孤兒 artifact 全部分為：`EXECUTABLE_NOW` / `EXECUTABLE_WITH_FIX` / `CODE_MISSING` / `TOMBSTONE`；每筆附 code path、entry point、failure reason | Read-only investigation；no DB write |
| **P2** | Truth-level taxonomy v2 + UI badge 擴充準備 | 提前到 P2，因 P3 寫 row 前必須 UI 能呈現 | UI badge 支援 `REGENERATED_RETROSPECTIVE`；API contract 預留欄位；不寫 DB | Frontend PR |
| **P3** | Retrospective regeneration **dry-run**（無 DB 寫入） | 同 CTO P3，但強調**每個 EXECUTABLE_NOW 策略都要產出 candidate rows** | 對 P1 的 EXECUTABLE_NOW 策略，重跑歷史開獎，產出 in-memory `(strategy, draw, predicted, actual, hit_count)` 表；附 provenance hash；no DB write | `YES dry-run retrospective` |
| **P4** | DAILY_539 `FAILED_LEGACY` 40 筆語意標籤（CTO 原 P2 降級） | 因不影響使用者主路徑，降一級 | 錯誤分組，UI 顯示「legacy audit」標籤，與 latest run 區隔；no row deletion | Read-only investigation |
| **P5** | Storage lane 決議 + schema migration plan | 同 CTO P4 | 決議：寫進 production DB 並以 `truth_level` 欄位區分；附 rollback、snapshot、fixture 隔離方案 | CEO decision memo |
| **P6** | Controlled apply — **P3 dry-run 結果寫入 DB** | CTO 原 P7 提前 | snapshot、transaction log、row count、provenance hash 全備；rollback 可驗證；no lifecycle promotion | `YES production apply retrospective rows` |
| **P7** | UI parity 全策略統一表格驗證 | CTO 原 P6 | 16 策略點任意一個都能展開逐期 row；filter URL 持久化；tombstone / regenerated / production 三種狀態 UI 清楚 | Frontend PR + browser QA |
| **P8** | H6 OBSERVATION evidence commit | 同 CTO P8 | `h6_gate_mk20_ew85` artifact 進 repo；registry 不變 | Docs PR |
| **P9** | PR #88 / #86 處置 + `outputs/relay` vs `outputs/replay` 路徑統一 | 合併 CTO 兩個低優項 | 判定 superseded 即關閉；路徑收斂後不影響 evidence discovery | Docs cleanup |
| **P10** | OFFLINE policy + 策略 mining / promotion | 同 CTO P9-P10 | 在 replay truth surface 全部穩定簽收前不做 | 延後 |

**關鍵差異總結：**
- CEO 把 **regeneration dry-run（P3）→ apply（P6）→ UI parity（P7）** 提到中段，把 DAILY_539 legacy 錯誤、storage lane 紙上決議降到 P4-P5 之後。
- CEO 把 **「程式可執行性實證」當成 P1**，取代「紙上 manifest」，避免 paperwork 黑洞。

---

## 5. Stop Rules（沿用 CTO，補強兩點）

沿用 CTO 第 7 節全部，**新增**：

- **(新)** P1 盤點不得只看 registry / docs，必須嘗試 `import` / `instantiate` / `dry call` 每個策略入口，否則分類無效。
- **(新)** UI badge 對 `REGENERATED_RETROSPECTIVE` 的支援必須在 P3 dry-run 開始前完成（P2），避免「row 寫出來但 UI 不能標」。

---

## 6. 今天開始執行的任務 prompt（P0 — P78）

CTO 的 P78 prompt 範圍正確，CEO **核准執行**，僅追加兩條輕量要求（不擴大 scope，只擴大 report 內容）。

```text
# ROLE
你是 LotteryNew 的 Configurable API Base Implementation Agent（P78）。
向 CTO 回報，CTO 向 CEO 回報。

# CONTEXT
main HEAD = d438fb6（P75/P76/P77 已 merged）
DB hash unchanged: de0e27bb800bc7183773a0dc596d66b8
Registry hash unchanged: 3ea71cfc20c882714f3824ad68202f6e

P77 architecture audit 結論：
- index.html 使用 `const BASE = '/api/replay'`
- local dev `python3 -m http.server 8081` 無法 proxy `/api` 到 backend 8002
- 推薦：P78_CONFIGURABLE_API_BASE_RECOMMENDED

CEO 補充指令：
- 本 PR 只改 index.html + report，不擴 scope
- 但 report 內必須額外附一節「P1 retrospective regeneration candidate
  strategies」，盤點 16 個 canonical strategies 中哪些有對應的可執行
  策略入口（檔案路徑 + entry point），作為 read-only inventory 供
  下一輪 P1 直接接續使用
- 不做 P1 的執行，只做盤點（grep / ls 等級的 read-only）

# MISSION
實作 P78 configurable API base：
- production default 維持 `/api/replay`
- local dev 可透過 `window.API_BASE='http://localhost:8002'` 指定
- 不再需要 Playwright fetch monkey patch
- report 增列 P1 candidate inventory（仍為 read-only）

# STRICT RULES
- 不寫 production DB
- 不修改 lottery_api/data/lottery_v2.db
- 不 commit *.db / *.sqlite / *.db-wal / *.db-shm
- 不修改 registry
- 不執行 backfill / adapter
- 不修改 backend route
- 不碰 branch protection / 不 direct push main
- 本輪只允許修改：
  - index.html
  - outputs/replay/p78_configurable_api_base_report_20260513.md
- 開 PR 但不 merge

# STEPS

1. 同步 main：
   cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
   git fetch origin
   git checkout main
   git pull --ff-only
   git log --oneline -5
   git status --short

2. 建立 branch：
   git checkout -b frontend/p78-configurable-api-base-20260513

3. 修改 index.html：
   舊：  const BASE = '/api/replay';
   新：  const API_BASE = (window.API_BASE || '').replace(/\/$/, '');
         const BASE = `${API_BASE}/api/replay`;

   驗收：
   - production default 仍為 `/api/replay`
   - window.API_BASE='http://localhost:8002' → BASE='http://localhost:8002/api/replay'
   - window.API_BASE='http://localhost:8002/' → BASE='http://localhost:8002/api/replay'（無雙斜線）
   - 不可 hardcode localhost:8002

4. Static verification：
   grep -n "window.API_BASE" index.html
   grep -n "const API_BASE" index.html
   grep -n "const BASE" index.html
   grep -n "/api/replay" index.html
   grep -n "localhost:8002" index.html   # 應為空

5. JS behavior 驗證（Node one-liner 即可，三個 case 都要 PASS）

6. Browser smoke（若 backend 8002 可用）：
   - curl http://localhost:8002/health
   - curl http://localhost:8002/api/replay/strategy-lifecycle
   - 開 http://localhost:8081，page load 前注入 window.API_BASE
   - 確認 lifecycle 表載入 16 strategies，無需 fetch monkey patch
   無法跑時標記 PARTIAL，不可虛構 PASS

7. P1 candidate inventory（CEO 新增，read-only 盤點）：
   對 lottery_api/models/replay_strategy_registry.py 中 16 個 canonical
   strategies，逐一 grep 對應的策略 module / entry point：
   - 檔案路徑（例如 strategies/biglotto_*.py）
   - import path
   - 是否可從 registry 取得 callable
   - lifecycle (ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED)
   
   輸出表格 columns:
   strategy_id | lifecycle | code_path | entry_point | importable | note

   分類 buckets:
   - EXECUTABLE_NOW（import 成功 + entry callable）
   - EXECUTABLE_WITH_FIX（有 code 但 import / signature 有問題）
   - CODE_MISSING（registry 有，repo 無對應檔）
   - TOMBSTONE（registry 無 code path 紀錄）

   禁止：執行任何策略 adapter、寫入 DB、修改 registry。
   只允許：read 檔案、grep、import dry-check。

8. 產出 report：
   outputs/replay/p78_configurable_api_base_report_20260513.md
   必含章節：
   - 本輪目標
   - root cause recap（P77）
   - implementation summary
   - production default verification
   - local dev API base verification
   - browser smoke 結果（PASS / PARTIAL / NOT RUN）
   - DB / registry hash 驗證
   - **P1 retrospective regeneration candidate inventory**（CEO 新增）
   - known limitations
   - next prompt（P1 dry-run regeneration）
   - final markers

9. Safety verification：
   git status --short
   md5 lottery_api/data/lottery_v2.db
   md5 lottery_api/models/replay_strategy_registry.py
   git diff --name-only main..HEAD

   diff 名單必須只有：
   - index.html
   - outputs/replay/p78_configurable_api_base_report_20260513.md

10. Commit & PR：
    git add index.html outputs/replay/p78_configurable_api_base_report_20260513.md
    git commit -m "frontend(replay/p78): add configurable API base + P1 inventory"
    git push -u origin frontend/p78-configurable-api-base-20260513
    gh pr create --base main \
      --title "frontend(replay/p78): add configurable API base" \
      --body-file outputs/replay/p78_configurable_api_base_report_20260513.md

11. 回報 CTO（CTO 再回報 CEO）：
    - PR URL
    - production default 驗證結果
    - local dev 驗證結果
    - browser smoke 狀態
    - DB / registry hash
    - **P1 candidate inventory 摘要**（EXECUTABLE_NOW 共幾個 / 各 bucket 分布）
    - known limitations & recommendation

# FINAL MARKERS
- P78_BASELINE_VERIFIED
- P78_CONFIGURABLE_API_BASE_IMPLEMENTED
- P78_PRODUCTION_DEFAULT_VERIFIED
- P78_LOCAL_DEV_API_BASE_VERIFIED | P78_LOCAL_DEV_API_BASE_PARTIAL
- P78_DB_UNCHANGED
- P78_REGISTRY_UNCHANGED
- P78_REPORT_CREATED
- P78_P1_CANDIDATE_INVENTORY_ATTACHED   ← CEO 新增
- P78_PR_OPENED
- P78_READY_FOR_REVIEW
```

---

## 7. 給後續鏈路的 10 行摘要

```text
CEO 二次審查結論：昨日為 infra + diagnosis 日，replay 真實內容缺口未動。
CTO 排序大方向正確，但對 non-ONLINE 策略過於保守，tombstone 不滿足使用者目標。
使用者明確要求「所有開發過的策略」都要看到逐期 row，需走 retrospective regeneration。
P0 = P78 維持不變，但 report 加上 P1 candidate inventory（不擴 code scope）。
P1 從「紙上 manifest」升級為「程式可執行性實證盤點」，杜絕 paperwork 黑洞。
P2 提前做 UI badge 對 REGENERATED_RETROSPECTIVE 的支援，避免 P3 寫 row 無處標。
P3 dry-run regeneration → P6 寫 DB → P7 UI parity 為核心產品路徑。
DAILY_539 legacy error、storage lane 紙面決議降為 P4-P5。
策略 mining / promotion 維持延後（P10）。
今天執行：上方 P78 + P1 inventory 任務 prompt，PR 開出但不 merge。
```