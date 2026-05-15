已完成 CTO 重新校準，並直接新增最新版 roadmap：

[lottery_roadmap_20260512.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/00-LotteryPlan/roadmap/lottery_roadmap_20260512.md:1)

核心結論：

- P23 Fixture Mode UI Toggle 已進 `main`：`7d80a03 feat(replay): add fixture mode ui toggle (#63)`。
- PR #64 目前 **OPEN / MERGEABLE / CLEAN**，checks 通過，但你這輪沒有給 explicit YES，所以我沒有 merge。
- Replay 頁面骨架與 Fixture Mode toggle 已接近可驗收，但還缺 **真實 browser 點擊驗證**。
- Production replay DB 目前只有 6 個 `ONLINE` 策略有 replay rows，共 460 rows。
- `REJECTED=4 / RETIRED=5 / OBSERVATION=1` 目前是 fixture mode synthetic rows，可用來驗收 UI，但不是 production replay truth。
- `OFFLINE` 目前仍是 deferred：0 canonical rows、0 fixture rows、0 production rows。

我把 roadmap 重排為：

- **P0**：PR #64 YES-gated merge + post-merge browser validation
- **P1**：定義「所有系統開發過策略」與 production replay coverage 缺口
- **P2**：擴充 canonical strategy catalog，非 ONLINE 僅 display-only，不可生成
- **P3**：Fixture acceptance hardening，確認 REJECTED/RETIRED/OBSERVATION 真實 UI 顯示
- **P4**：Production replay backfill decision memo，不直接 backfill
- **P5**：No-write dry-run manifest
- **P6**：歷史預測清單 UX parity
- **P7**：operator SOP + screenshot walkthrough
- **P8**：DB mtime/test hygiene
- **P9**：worktree/PR hygiene
- **P10**：real apply、strategy mining、OFFLINE introduction 全部 defer

驗證：已跑 `git diff --check`，roadmap 無 whitespace error。  
注意：目前 `/Users/kelvin/Kelvin-WorkSpace/LotteryNew` 本身仍有既有 dirty 狀態，包含 `data/lottery_v2.db`；我沒有 restore，避免覆蓋非本輪變更。merge authority 建議繼續用 `LotteryNew-clean`。

Final markers:

```text
WAITING_FOR_USER_YES_GATE_PR64
LOTTERY_ROADMAP_20260512_RECALIBRATED_FOR_STRATEGY_HISTORY_REPLAY
```
# CEO 二次審查 — Strategy Historical Replay 上線方向

## 1. 昨天成果是否推進系統成熟度？

**部分推進，但不是核心成熟度。**

| 維度 | 推進程度 | 評語 |
|---|---|---|
| 工程嚴謹度 | ✅ 強推進 | 94/94 tests pass、UI contract 15/15、forbidden diff 2/2、DB clean restore SOP 已落地 |
| UI 可用性 | ✅ 中度推進 | Fixture Mode toggle 取代手動 URL query，operator UX 改善 |
| **產品核心目標** | ❌ **沒有推進** | 「所有系統開發過策略的歷史回放比對清單」這個核心需求，production replay rows 仍停在 6 個 ONLINE 策略 / 460 rows |
| 資料覆蓋 | ❌ 0% 推進 | REJECTED=0、RETIRED=0、OBSERVATION=0、OFFLINE=0 — 與昨天前完全相同 |
| 工作流安全 | ✅ 推進 | YES gate / no production write / fixture banner 都守住 |

**結論：昨天交付的是「包裝層」（toggle + banner + 報告），不是「資料層」。Fixture Mode 是驗收橋，不是產品。如果只看 PR 數量、tests pass、文件閉環，會誤判為高推進；但對照你今天再次確認的產品目標（所有策略的預測 vs 開獎比對清單），實際距離產品上線的差距沒有縮短。**

---

## 2. CTO 判斷合理性

### 合理部分

- 拒絕「fixture rows = production truth」、堅持 YES gate、堅持不寫 production DB、繼續 defer OFFLINE — 全部正確。
- 識別出 production data coverage gap、催 post-merge browser validation — 方向對。
- Stop Rules 11 條完整、保守、可審計。

### 盲點與誤判

**盲點 #1：把 PR #64 docs merge 列為 P0，是流程慣性，不是產品價值。**
PR #64 是驗證報告，merge 與否不改變 operator 看到的頁面。把它列為 P0 等於把「行政結案」當成「產品推進」。應視為 P0 的附屬動作，而不是 P0 本身。

**盲點 #2：低估「Catalog inventory + Backfill decision」的關鍵路徑地位。**
CTO 把 P1（catalog reconciliation）和 P4（backfill memo）分開且把 backfill 排到 P4。但這兩件事才是「所有系統開發過策略可見」這個目標的真正瓶頸。沒有 catalog 全貌 + backfill 決策，後面 P3/P5/P6 全部是空轉。

**盲點 #3：UX parity（P6）排太後面。**
你今天再次強調「顯示畫面同歷史預測清單即可」— 這是產品目標的明文定義。CTO 把它排在 P6，落後於 fixture hardening 與 backfill memo。錯置優先級。

**盲點 #4：非 ONLINE 策略的「display-only catalog wiring」沒有獨立列項。**
目前 16 條 lifecycle metadata 是否真的在 UI 上「以空 replay history 也能可見」？CTO 沒有明確把這條切出來。實際上這是「fixture 關掉時，REJECTED/RETIRED/OBSERVATION 策略是否仍出現在 filter 與清單裡（顯示為 no replay data）」的關鍵驗收。

**誤判 #1：Browser validation 的權重被高估。**
真實點擊驗證重要，但工程量小、可在 1–2 小時內收尾。不應該佔據 P0 的整個視野。

**誤判 #2：把 OFFLINE 列為 P10 全 defer 是對的，但沒有對使用者明確說明：你列出的五種 lifecycle（ONLINE/OFFLINE/REJECTED/OBSERVATION/RETIRED）中 OFFLINE 仍會以 disabled / coming soon 形式出現嗎？這是產品語意決策，CTO 沒有提案。**

---

## 3. 重新排序的 P0–P10（CEO 版）

核心換軸：**從「PR 閉環優先」改為「產品資料覆蓋優先」**。

| 優先 | 焦點 | 為什麼這個順序 | 驗收門檻 |
|---|---|---|---|
| **P0** | **Strategy Catalog 全量盤點 + Replay Coverage 缺口表** | 沒有這個表，所有 backfill / display 決策都是猜的；這是 1 天內可交付的純讀工作 | 一份對照表：`strategy_id × lifecycle × source(folder/memory/registry/db) × has_production_replay_rows × row_count × eligible_for_display`；涵蓋 registry 16 + rejected archives + memory 中所有 strategy 名稱 + DB 中所有 strategy_id |
| **P1** | **Replay 頁面顯示所有 catalog 策略（display-only 模式）** | 直接命中你的目標「所有策略我都看得到，不管是否上線」；在不寫 DB、不改 backend 下，UI 層把非 ONLINE 策略列入 filter 與清單（空 replay rows 顯示「無歷史回放資料」） | Filter 同時包含 ONLINE/OFFLINE/REJECTED/OBSERVATION/RETIRED；切換到 REJECTED 等 lifecycle，即使 production rows=0，也可看到 strategy 卡片與「無資料」狀態；OFFLINE 顯示 disabled 標示，不可生成 |
| **P2** | **Replay 清單 UX 與歷史預測清單對齊（parity）** | 你的目標明文要求；ux drift 等於產品定義不一致 | Filters / pagination / detail row / status label / 空狀態 / 行動裝置層 — 與歷史預測清單行為一致；snapshot diff 證明 |
| **P3** | **PR #64 YES-gated merge + post-merge real browser click 驗證** | 流程閉環，必要但小；和 P0/P1 並行即可 | merge ok、main 同步、Playwright 或手動點擊 ON/OFF 驗證、banner show/hide、`rp_fixture_mode` URL / API `fixture_mode=true` 都正確 |
| **P4** | **Production Replay Backfill Decision Memo（不執行，只決策）** | 沒這份備忘錄，非 ONLINE 策略永遠卡在 fixture 救火；必須由 CEO/CTO 在本週做決策 | 備忘錄回答：來源、方法、provenance、risk、rollback、DB hash 證明、approval gates、是否一次性 backfill 或持續產生；明確列出每一個策略的資料可得性 |
| **P5** | **Fixture Acceptance Hardening（保留為 demo lane）** | 在 P4 決策前，fixture 是唯一能驗收非 ONLINE UI 的途徑，但要更嚴格隔離 | Real browser 證明 REJECTED/RETIRED/OBSERVATION fixture rows 顯示完整 + banner 完整 + advisory 文案完整；不可被誤截圖當 production |
| **P6** | **No-write Replay Dry-run Manifest（依 P4 決策啟動）** | 如果 P4 memo 允許探索 backfill，產出候選清單但**不寫 DB** | 候選 rows、被擋原因、provenance hashes、before/after DB hash 不變 |
| **P7** | **Operator SOP + Screenshot Walkthrough** | 對非工程使用者，必須清楚區分 production mode vs fixture mode | 一份 SOP 含截圖；用詞無 edge claim、無 betting recommendation |
| **P8** | **DB mtime / Test hygiene SOP 化** | 反覆 dirty `lottery_v2.db` 是 PR 衛生噪音 | 測試 lane 改用 copied DB 或 auto-restore；CI 紀錄留存 |
| **P9** | **Worktree / Merge authority hygiene** | `LotteryNew-clean` 為唯一 merge authority；主 workspace 保留為 dirty source-only | 規則寫入 ops doc；本輪 commit 都從 clean worktree 出 |
| **P10** | **Defer：real apply、strategy mining、edge discovery、OFFLINE 引入、promote/retire 動作** | 嚴守 stop rules；需個別 YES gate 才能啟動 | 任何相關 PR 一律 block |

**最大調整**：
- 把 catalog 盤點與「所有策略可見」推到 P0/P1，把 PR #64 行政閉環降到 P3（仍今天做，但不再是第一順位）。
- 把 UX parity 拉到 P2，因為這是產品目標的明文。
- 把 backfill decision memo 從 P4（CTO 版）保留為 P4 但**前面三條為其輸入**，讓 memo 有事實依據可寫，而不是在資料不全下猜。

---

## 4. 今天最應聚焦方向（單句）

> **今天最有價值的優化不是 merge PR #64，而是先盤點「所有系統開發過策略」的完整名單與 production replay 覆蓋缺口，並讓 Replay 頁面在 production 模式下也能列出非 ONLINE 策略（即使無資料）。這一步直接命中產品目標，並讓 backfill 決策有事實依據。PR #64 在同一天內以次要任務閉環即可。**

---

## 5. 下一輪可直接執行的 task prompt

```text
# ROLE
你是 LotteryNew 的 Strategy Historical Replay Product Coverage Agent，
向 CTO 回報，CTO 向 CEO 回報。
本輪同時兼任 PR #64 Merge Gatekeeper（次要任務）。

# CONTEXT
- main 最新 commit：7d80a03 feat(replay): add fixture mode ui toggle (#63)
- PR #64 OPEN / MERGEABLE / CLEAN，等待 explicit YES
- Production replay rows：只有 6 個 ONLINE 策略 = 460 rows
- Fixture rows：REJECTED=4 / RETIRED=5 / OBSERVATION=1（synthetic）
- OFFLINE：0 canonical / 0 fixture / 0 production
- Registry：16 條 lifecycle metadata
- 產品目標（CEO 再次確認）：
  Replay 頁面必須能讓 operator 看見所有「系統開發過」的策略，
  涵蓋 ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED，
  以「每期預測 vs 實際開獎」比對清單呈現，
  UI 行為同歷史預測清單。

# MISSION
本輪以「資料覆蓋與顯示完整性」為主任務，PR #64 為次任務。

主任務（依序）：
  T1. 全量盤點：什麼是「所有系統開發過策略」？
  T2. Replay 頁面在 production 模式下，讓所有 catalog 策略都可見（即使 row=0）
  T3. UX 對齊：與歷史預測清單一致

次任務：
  T4. PR #64 YES-gated merge + post-merge real browser 驗證

# STRICT RULES
- 不寫 production DB
- 不改 data/lottery_v2.db
- 不改 registry metadata（schema），但可新增 display-only catalog 條目（不可生成、不執行）
- 不改 lifecycle taxonomy
- 不新增 OFFLINE filter 的可生成能力
- 不新增 OFFLINE fixture rows
- 不做 production DB backfill（僅可寫 memo / manifest）
- 不做 strategy promotion / retire / reactivate
- 不動 branch protection
- 不做 strategy mining / edge discovery
- 未收到 explicit YES 不可 merge PR #64
- 若測試造成 data/lottery_v2.db dirty，必須 restore 並記錄
- merge authority：使用 LotteryNew-clean，不可使用 dirty workspace

# STAGE A — Strategy Catalog 全量盤點（read-only）
1. 來源掃描：
   - lottery_api strategy folder
   - rejected/ archive folder
   - memory/MEMORY.md 中所有策略名稱
   - canonical lifecycle registry（16 條）
   - lottery_v2.db 中所有 distinct strategy_id（含 replay_history 表）
2. 產出對照表 outputs/replay/strategy_catalog_inventory_20260512.md：
   columns:
     strategy_id | lifecycle | source(folder/memory/registry/db) |
     has_production_replay_rows | production_row_count |
     has_fixture_rows | fixture_row_count |
     eligible_for_display | eligible_for_generation |
     provenance_note
3. 在表後加上 gap 分析：
   - 哪些策略在 catalog 但無 production rows
   - 哪些策略只在 memory 但 catalog 缺失
   - 哪些策略 lifecycle 不一致
4. 不修改任何 source data。

# STAGE B — Replay 頁面顯示完整性（UI-only 改動）
目標：production 模式下，filter REJECTED / RETIRED / OBSERVATION / OFFLINE 
時，即使 production rows=0，也要顯示該 lifecycle 下所有 catalog 策略，
以「無歷史回放資料」狀態呈現，不可空白。

1. 設計 spec：
   outputs/replay/p24_display_only_catalog_spec_20260512.md
   - filter 行為
   - 空 row 顯示樣式（不可誤導為 production hit）
   - OFFLINE 顯示為 disabled / coming soon
   - 不可有 betting recommendation 字樣
2. 實作（如時間允許）：
   - 從 catalog 拉出該 lifecycle 下所有 strategy_id
   - 若無 production replay rows，render「無歷史回放資料」row
   - 加 contract test：每個 lifecycle filter 至少顯示其 catalog 內的 strategy 清單
3. UI Contract:
   - 不可改變 ONLINE 既有顯示
   - 不可改變 fixture mode 行為
   - 不可新增 OFFLINE 生成能力

# STAGE C — UX Parity 對照（觀察 + 補丁清單）
1. 開啟現有歷史預測清單 + 新 Replay 清單兩頁對照
2. 列出差異點：filters / pagination / detail row / status label /
   empty state / 行動裝置 layout / export 或 sort（若歷史清單有）
3. 產出 outputs/replay/p24_ux_parity_gap_20260512.md
   - 必補項
   - 可延後項
   - 與 fixture mode 互動有無衝突
4. 本輪不需全部補完，僅輸出 gap list。

# STAGE D — PR #64 Gatekeeper（次任務）
1. cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean
2. git fetch origin
3. gh pr view 64 --json state,mergeable,mergeStateStatus,headRefName,baseRefName,url
4. gh pr checks 64
5. 若未收到 explicit YES：
   - 輸出 marker WAITING_FOR_USER_YES_GATE_PR64
   - 不 merge，但繼續完成 Stage A/B/C
6. 若收到 YES：
   - gh pr merge 64 --squash --delete-branch
   - git checkout main && git pull --ff-only
   - 跑 tests/test_replay_browser_smoke.py + tests/test_replay_api_contract.py
   - 真實 browser 驗證 toggle ON/OFF / banner / URL state / API param
   - 輸出 marker P23_FIXTURE_MODE_UI_TOGGLE_VALIDATION_PR64_MERGED_TO_MAIN
   - 輸出 marker P23_FIXTURE_MODE_TOGGLE_POST_MERGE_BROWSER_VALIDATION_PASS

# STAGE E — Produce CEO-facing Coverage Report
產出 outputs/replay/p24_strategy_replay_coverage_report_20260512.md
內容必須包含：
1. Catalog 全量清單（人類可讀摘要 + 完整表）
2. Production replay coverage gap
3. Display-only spec 摘要
4. UX parity gap 摘要
5. PR #64 merge 狀態
6. Browser validation 結果
7. Safety invariants：production write NO / registry schema NO /
   taxonomy NO / OFFLINE generation NO / fixture artifact NO / db clean YES
8. 今天未完成事項
9. 下一步建議：
   - Production Replay Backfill Decision Memo（CEO 主持）
   - Display-only UI 實作 PR（如本輪只交 spec）
   - UX parity 補丁 PR
   - Mining / OFFLINE introduction 仍 defer

# STAGE F — Docs PR（不 merge）
建立 branch：
  docs/p24-strategy-replay-coverage-20260512
commit：
  docs(replay): inventory all developed strategies and define display-only catalog
push & gh pr create --base main，不 merge。

# FINAL OUTPUT FORMAT
回報 CTO：
1. Catalog 全量數（總策略數 / 每 lifecycle 分布）
2. Production replay gap 摘要
3. Display-only spec 是否完成
4. UX parity gap 列表長度
5. PR #64 狀態 / 是否 merge
6. Browser validation PASS / FAIL
7. coverage report 路徑
8. docs PR URL
9. Safety invariant 摘要
10. data/lottery_v2.db final status
11. final markers
12. 對 P4（Backfill Decision Memo）的具體建議

# FINAL MARKERS
若未收到 YES：
  WAITING_FOR_USER_YES_GATE_PR64

若 catalog 盤點完成：
  P24_STRATEGY_CATALOG_INVENTORY_COMPLETE

若 display-only spec 完成：
  P24_DISPLAY_ONLY_CATALOG_SPEC_COMPLETE

若 UX parity gap list 完成：
  P24_UX_PARITY_GAP_LIST_COMPLETE

若 PR #64 merged：
  P23_FIXTURE_MODE_UI_TOGGLE_VALIDATION_PR64_MERGED_TO_MAIN

若 post-merge browser validation 通過：
  P23_FIXTURE_MODE_TOGGLE_POST_MERGE_BROWSER_VALIDATION_PASS

若 coverage report 與 docs PR 完成：
  P24_STRATEGY_REPLAY_COVERAGE_REPORT_PR_OPEN_<URL>

若 DB final clean：
  P24_POST_RUN_DB_CLEAN

最終總標：
  CEO_REVIEW_20260512_PRODUCT_COVERAGE_PRIORITY_LOCKED
```

---

## 6. 給 CTO 的一句結語

> 你昨天守住了所有 stop rules、交付了乾淨的工程閉環，但你把「行政結案」放在了「產品覆蓋」之前。今天請反轉軸線：先讓所有策略在 Replay 頁面被看見，再去 merge 那份驗證報告。PR #64 是必要動作，不是優先動作。