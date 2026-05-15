已完成 CTO 盤點與 roadmap 更新，沒有新增 repo，也沒有碰 replay DB 寫入。

**已更新**
- 新增 active roadmap：[docs/replay/strategy_historical_replay_roadmap_20260515.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/docs/replay/strategy_historical_replay_roadmap_20260515.md)
- 標記舊核心功能狀態文件為 legacy：[docs/IMPLEMENTATION_STATUS.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/docs/IMPLEMENTATION_STATUS.md)
- 標記舊 priority list 為 legacy：[docs/PRIORITY_FIXES.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/docs/PRIORITY_FIXES.md)

**目前進度判斷**
- Replay 頁面對 canonical 16 策略已基本成形。
- ONLINE 6 個策略：可顯示每期預測 vs 實際開獎。
- REJECTED 4 個策略：已有 V2 artifact retrospective rows，可顯示每期比對。
- RETIRED 5 個、OBSERVATION 1 個：目前是 catalog/tombstone 顯示，沒有假造回放列，這是正確安全設計。
- OFFLINE lifecycle 已支援，但目前 0 個 registered OFFLINE 策略。
- 最大落差是「所有系統開發過策略」尚未等於「canonical 16 策略」；repo 內有大量 strategy-like files，需要 P1 盤點分類後才能宣稱全覆蓋。

**重新排序後的重點方向**
- P0：確認 nightly drift guard 首次成功執行，守住 V1=300 / V2=200 / legacy=460 baseline。
- P1：做完整 canonical strategy inventory，定義哪些策略該進 registry、哪些只是研究工具或 superseded artifact。
- P2：在 current main 做 replay page operator acceptance，確認 UI 是否符合你的產品目標。
- P3：no-write audit V2 artifact metadata，特別是 `history_cutoff_draw` / provenance 完整性。
- P4：重建本地 `.venv`，恢復 pytest。
- P5-P10：文件權威清理、API contract hardening、SOP/observability、controlled replay expansion design、lifecycle governance、最後才回到策略研究優化。

**驗證**
- Drift guard 已再次 PASS：`REPLAY_LIFECYCLE_DRIFT_GUARD_PASS`
- Row counts：V1=300、V2=200、legacy=460、total=960
- V3 tombstone：6/6 zero rows
- Violations：0
- 本地 pytest 仍不可用，因 current system Python 沒有 `pytest`
- GitHub `replay-lifecycle-drift-guard` scheduled run 截至 `2026-05-15 10:02 CST` 尚未觀察到，PR #100 的一般 CI 已成功

**最值得優化的方向**
下一階段不要急著做新策略或 backfill。最值得聚焦的是：把「策略歷史回放」變成可信任的產品稽核面，也就是 canonical inventory、truth-level metadata、CI drift guard、operator acceptance 先全部穩住。

目前 final classification：

```text
REPLAY_ROADMAP_REFOCUSED_ON_CANONICAL_COVERAGE_AND_OPERATIONAL_TRUST
```

## CEO 二次審查

### 昨天進度真實性
- **真實但偏後勤**：drift guard PASS、baseline 鎖定（V1=300/V2=200/legacy=460）、V3 tombstone 守護、roadmap 重排
- **對使用者價值＝0**：沒有任何一條新的「策略 × 期數 × 預測 vs 開獎」row 被點亮
- 等於買保險，不等於蓋房子

### CTO 判斷評估
- ✅ 正確：不為 retired/observation 偽造 replay row
- ✅ 正確：先做 canonical inventory 再宣稱全覆蓋
- ⚠️ **盲點 1**：CTO 把宇宙界定為「canonical 16」，但 CEO 目標是「所有系統開發過的策略」。canonical registry ≠ 系統實際生產過預測的策略全集
- ⚠️ **盲點 2**：把 P0 押在 nightly drift guard 首次執行——這是運維 SLO，不是產品交付，對 replay 頁面落地零幫助
- ⚠️ **盲點 3**：把 operator acceptance（CEO 親自看頁面）放到 P2，等於延遲最便宜的驗證
- ⚠️ **盲點 4**：retired/observation 在頁面上「預測 vs 開獎」語義未定義，這是產品決策不是工程決策
- ⚠️ **盲點 5**：REJECTED 的 V2 artifact 是 retrospective（事後重現），不是 live prediction。UI 沒劃清信任邊界

### 今天最該聚焦的方向

| 優先級 | 任務 | 為什麼是這個位置 |
|--------|------|------------------|
| **P0** | **產品語義凍結**：5 種 lifecycle（ONLINE/OFFLINE/REJECTED/RETIRED/OBSERVATION）在 replay 頁面的顯示規格（資料來源／比對方式／信任標籤），單一規格文件 | 沒這個，後面所有 code 都會反覆改 |
| **P1** | **策略全集盤點**（read-only）：列出所有曾產生過預測的策略 ID → 對映 lifecycle → 與 canonical 16 對 diff，輸出 `strategies_universe.csv` | 這才是真正的覆蓋率分母 |
| ~~P2~~ | （CEO 預留） | — |
| **P3** | **CEO 親自驗收 current main 的 replay 頁**，逐 lifecycle 給 must-fix / nice-to-have / out-of-scope | 最便宜的反饋迴路 |
| **P4** | REJECTED 的 V2 artifact row 加「事後重現／Retrospective」UI 標籤，劃清信任邊界 | 防止使用者誤讀 |
| **P5** | RETIRED/OBSERVATION 顯示策略根據 P0 規格落地（artifact / tombstone / "no data" 三選一） | 完成 lifecycle 覆蓋 |
| **P6** | Drift guard 觀察一輪 nightly cron 是否真跑通（降級版的原 CTO P0） | 護欄該驗但不擋產品 |
| **P7** | V2 artifact metadata（含 `history_cutoff_draw`／provenance）完整性 audit（no-write） | 信任 chain 補完 |
| **P8** | 重建 `.venv`，恢復本地 pytest | 工程基礎 |
| **P9** | API contract hardening + SOP/observability | 上線前體檢 |
| **P10** | Controlled replay expansion 設計 + 策略研究回歸 | 真正的「下一階段」 |

### 關鍵思維轉換
CTO 節奏是「先把護欄做好再蓋路」。**CEO 立場**：護欄已經夠了，今天切換成「把產品交付給使用者看」。不要再花一整天做 auditability。

---

### 今天執行的下一個任務 prompt

```text
角色：Replay Product Spec 凍結負責人（CEO 直派）

目標：在動任何 code 之前，凍結「策略歷史回放」頁面對 5 種 lifecycle 狀態
（ONLINE / OFFLINE / REJECTED / RETIRED / OBSERVATION）的顯示語義。

CEO 已決定的前提：
- Replay 頁面必須覆蓋「所有系統開發過的策略」，不只 canonical 16
- 顯示格式與「歷史預測清單」一致（每期 × 每策略 × 預測 vs 實際開獎）
- 不允許偽造 row；允許明示「事後重現 / 無資料 / tombstone」三種狀態
- 不允許寫 DB、不允許動 code、不允許動策略

需要輸出單一檔案：
  docs/replay/replay_display_semantics_spec_20260515.md

文件必須包含：

(1) 對每個 lifecycle status（5 種）填以下三欄：
   - 預測資料來源（live prediction log / V2 retrospective artifact /
     tombstone metadata / no data 四選一以上組合）
   - 比對方式（live diff / retrospective diff / N/A）
   - UI 信任標籤（LIVE / RETROSPECTIVE / FROZEN / NO_DATA）

(2) 三條 CEO 決策題，每題附 CTO 建議答案 + 風險：
   A. REJECTED 的 V2 artifact row 是否在 UI row level 強制標註
      「事後重現 Retrospective」？
   B. RETIRED 顯示退役前的最後 N 期預測軌跡？
      （候選：顯示全部 / 最後 30 期 / 只顯示 tombstone）
   C. OBSERVATION 期間若無預測 row，顯示 "no data" 還是隱藏？

(3) 對 P1（策略全集盤點）的輸入需求：
   為了讓 P1 知道要盤點哪些來源，列出 spec 預期觸及的
   「預測資料來源」清單（DB tables / artifact 路徑 / log 檔位置）

限制：
- read-only，不寫 DB，不動 code
- 不做新策略、不跑 backtest
- 只產出規格文件 + 對 CEO 的決策請求清單

完成條件：
- 規格文件 commit 進 docs/replay/，建立 PR draft（不要 merge）
- 三條決策題各 ≤ 100 字
- 對 CEO 的回報限 300 字內，含：規格鏈結、三題建議、風險旗標
```