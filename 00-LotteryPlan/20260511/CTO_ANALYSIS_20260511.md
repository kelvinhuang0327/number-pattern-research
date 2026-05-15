已依照你補充的產品目標重新調整實作規劃，並新增：

[outputs/replay/p0_strategy_history_replay_product_plan_20260511.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/outputs/replay/p0_strategy_history_replay_product_plan_20260511.md)

也更新了：

[outputs/replay/p2_cto_roadmap_recalibration_20260511.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/outputs/replay/p2_cto_roadmap_recalibration_20260511.md)

重點調整如下：

- 今日主 P0 改回 **策略歷史回放功能上線**，P2 no-write skeleton 降為治理 lane，不再是產品主線。
- 現有頁面/API 已接近目標：有 replay section、lifecycle filter、strategy filter、history table、pagination、detail row。
- 真正缺口是資料與 catalog：目前 evidence 顯示只有 `ONLINE` 有 replay rows，`OFFLINE / REJECTED / OBSERVATION / RETIRED` 仍是 honest empty state。
- 新 P0 是先做 **全策略 lifecycle inventory + catalog contract**，確認所有系統開發過策略的來源、狀態、provenance、是否有 replay rows。
- 新 P1 才是實作 canonical strategy lifecycle catalog，並明確區分「可顯示」與「可生成 replay」，避免 rejected/offline 策略被誤納入生成。
- 新 P2 是 replay row backfill dry-run design，仍不寫 production DB。
- 新 P3 是 fixture / browser tests，證明五種 lifecycle 狀態都有非空 rows 時頁面能正確顯示 prediction vs actual。

我也保留安全邊界：不 backfill、不寫 DB、不改 active strategy state、不 merge PR、不把 `outputs/replay/` 當 runtime source。

驗證：dirty scope 仍只包含 docs artifacts；新增/更新文件的 diff hygiene check 通過。

好，我已查清狀態。先給你關鍵事實，再給 CEO 二次審查，最後直接輸出今天的執行 prompt。

---

## 實作進度確認（事實層）

| 項目 | 狀態 | 證據 |
|---|---|---|
| Replay 頁面骨架（lifecycle filter / strategy filter / history table / pagination / detail row） | **✅ 已上線 PR #12 已 merge** | `f710343 feat(replay): lifecycle full-state replay product go-live (#12)` |
| Post-merge closure / dry-run contract / planning | **✅ 已 merge #13-#16** | `git log --oneline -5` |
| OFFLINE / REJECTED / OBSERVATION / RETIRED **顯示有資料** | **❌ 全 0 row** | DB 只有 6 strategy_id 全 ONLINE：biglotto_deviation_2bet, biglotto_triple_strike, daily539_f4cold, daily539_markov_cold, power_orthogonal_5bet, power_precision_3bet |
| Lifecycle_status 來源 | DB 表沒這欄，從 `replay_strategy_registry.py` 取 | `strategy_prediction_replays` schema 無 lifecycle_status；route 用 registry join |
| Worktree 收斂 | **✅ 部分完成**：7→5 個（main-postmerge, roadmap-20260509, p0-release, /tmp 已消失） | `git worktree list` |
| Open PR queue | **❌ 失控**：**18 個 docs PR open（#17~#34），加 PR #2** | `gh pr list` |
| LotteryNew-clean dirty scope | 3 個 untracked（checklist, conclusion, plan）但 main 已往前跑 7 個 commit，這些檔處於懸空狀態 | `git status --short` |

---

## CEO 二次審查

### 1. 昨天成果是否真的推進系統成熟度

**部分是，但被治理 over-engineering 稀釋掉一半。**

| 真推進 | 假推進 |
|---|---|
| ✅ PR #12 把 lifecycle full-state replay 骨架真的 merge 上線 | ❌ 18 個 docs(replay) governance PR 累積、佔滿 queue |
| ✅ #13-#16 補完 closure、dry-run contract | ❌ 昨天大量時間在產 checklist / conclusion / plan / recalibration 四份「同一件事的不同視角文件」 |
| ✅ Worktree 從 7→5 收斂（執行 CEO 前一輪指令） | ❌ DB 仍只有 6 個 ONLINE 策略的 replay rows，OFFLINE/REJECTED/OBSERVATION/RETIRED 仍是 honest empty state |
| ✅ 維持 no-write 邊界 | ❌ 那 3 個 dirty file 跟 main 已往前跑的 commit 不同步，孤立掉了 |

### 2. CTO 判斷是否合理 + 盲點

| CTO 判斷 | 評價 |
|---|---|
| 把 P0 從 P2 no-write skeleton 改回「策略歷史回放上線」 | ✅ 正確 |
| 識別「真正缺口是資料 + catalog，不是 UI 骨架」 | ✅ 正確 |
| P0-A inventory → P0-B catalog contract → P1-A 才實作 | ⚠️ **盲點 1：計劃過剩。又是 inventory plan + contract plan，沒進到「實際補一筆 OFFLINE row 上去看效果」。今天要的是先讓畫面長出一筆非 ONLINE row** |
| 把 PR queue 放在 P7 | ⚠️ **盲點 2：18 個 open docs PR 已是組織級風險，使用者已說「無法管理」，CTO 仍排第 7 位。應該 P0** |
| 對 lifecycle_status 來源沒寫清楚 | ⚠️ **盲點 3：lifecycle_status 來自 registry 不是 DB 欄位。下一個 agent 若沒讀懂會去改 DB schema 而不是改 registry。CTO plan 沒講這個關鍵分叉** |
| 沒驗 PR #12 上線後 UI 實際行為 | ⚠️ **盲點 4：merge ≠ 上線品質。沒人去打開頁面切換 lifecycle filter 看看 empty state 文案、按鈕、API response shape 是否正確** |
| 那 3 個 untracked docs 仍 dirty 在 LotteryNew-clean | ⚠️ **盲點 5：main 已往前跑 7 commit 但這 3 個檔還 untracked。需決定：丟掉、commit、或挪到 archive。CTO 的 supersession note 承認問題但沒給乾淨方案** |

### 3. 你補充的產品目標 — 確認對齊

| 你的目標 | 對齊狀態 |
|---|---|
| 頁面查所有 lifecycle 狀態（ONLINE/OFFLINE/REJECTED/OBSERVATION/RETIRED） | ✅ filter UI 已存在；❌ catalog 中只有 6 個 ONLINE |
| 每一期 預測 vs 實際開獎比對清單 | ✅ schema/columns 已存在（predicted_numbers, actual_numbers, hit_numbers, hit_count）；❌ 非 ONLINE 策略沒 row |
| 顯示同歷史預測清單 | ✅ history table + pagination + detail row 已對齊 |

**結論：產品骨架已上線。下一步是「資料補進去」，不是「再寫第三份 plan」。**

---

## CEO 重排 P0~P10（取代 CTO 版本）

| 優先序 | 項目 | 與 CTO 版本差異 |
|---|---|---|
| **P0** | **PR Queue 收斂** — 處理 18 個 open docs PR 與 PR #25 superseded 狀態 | CTO 排 P7，CEO 提到 **P0**（否則 inventory PR 一進來就被埋沒） |
| **P1** | Strategy Lifecycle Inventory (read-only) — 一份 JSON 列出全系統所有策略（registry 6 個 ONLINE + rejected/ 42 筆 + strategies/ 目錄 + memory 中提到的策略） | 同 CTO P0，但要求**今天 commit + PR**，不要再生第二份 plan |
| **P2** | **Registry-level catalog 擴充（不寫 DB）** — 在 `replay_strategy_registry.py` 加入 OFFLINE/REJECTED/OBSERVATION/RETIRED 條目，標記 `replay_display_eligible=true, generation_eligible=false` | CTO 排 P1，沒明確區分「改 registry 不是改 DB」 |
| **P3** | Replay Row Backfill — **fixture-only**，給每個非 ONLINE 策略至少 1 row 在測試 fixture，**不寫 production DB** | 同 CTO P2 |
| **P4** | Non-empty lifecycle **browser smoke**：切到 OFFLINE、REJECTED 都看到 row，UI 行為驗證 | 同 CTO P3 |
| **P5** | **PR #12 Post-merge UX verification** — 用 browser 跑一次 lifecycle filter 切換、空狀態文案、API response 對齊產品定義 | CTO 漏掉 |
| **P6** | Source-of-truth invariant — outputs/replay/ 仍只是 evidence | 同 CTO P5 |
| **P7** | Worktree hygiene 收尾 — 確認 LotteryNew 標記 source-only，LotteryNew-clean 是唯一 working tree | 將前一輪未完工作收尾 |
| **P8** | 26 blocked REJECTED rows + 1 parse error 修復 — 給 P2 補燃料 | 同 CTO 之前 P8 |
| **P9** | Operational SOP — 一頁說明回放頁要怎麼讀、空狀態代表什麼 | 同 CTO P9 |
| **P10** | Real apply / backfill governance — defer | 同 CTO P10 |

**核心位移**：CTO 把 P0 放在「再寫一份 inventory plan + catalog contract plan」，CEO 把 P0 放在「PR queue 收掉」+ 「直接做 inventory + 直接動 registry」，因為產品的骨架 PR #12 已上線，**下一步就是「資料」，不是「文件」**。

---

## 今天直接執行的任務 Prompt

```text
# ROLE
你是 LotteryNew 的 P0 PR Queue Triage + Strategy Lifecycle Inventory Agent，
向 CTO 回報，CTO 向 CEO 回報。

# CONTEXT
- 產品骨架 PR #12 已 merge：lifecycle filter / history table / detail row 都已存在於 origin/main。
- DB 中 strategy_prediction_replays 僅含 6 個策略，全屬 ONLINE：
    biglotto_deviation_2bet, biglotto_triple_strike,
    daily539_f4cold, daily539_markov_cold,
    power_orthogonal_5bet, power_precision_3bet
- strategy_prediction_replays 表「沒有」lifecycle_status 欄位。
  Lifecycle 來源是 lottery_api/models/replay_strategy_registry.py 中每個 adapter 的 meta.lifecycle_status，
  route 用 registry join 來篩選。這代表新增 OFFLINE/REJECTED/OBSERVATION/RETIRED「下拉選單條目」
  只需動 registry，不必動 DB schema。
- 目前 GitHub 上有 18 個 open docs(replay) governance PR (#17~#34) + PR #2，必須先收斂。
- LotteryNew-clean 目前 3 個 untracked dirty files 與 main 已往前跑 7 commit 不同步，
  必須先決定它們的去處（archive / commit / discard）。

# MISSION（按順序，前一階段不過不能進下一階段）

## 階段 A — PR Queue Triage（必做，且必須在 1 小時內完成）
目標：把 18 個 open docs(replay) PR 收斂到「<= 3 個」open。

acceptance：
1. 用 gh pr list 取 #17~#34 + PR #2 全部 metadata（state, mergeable, base, head, title, created_at）
   寫入：
     outputs/replay/p0_pr_queue_triage_20260511.md
   每筆標記分類：
     - SUPERSEDED → 由更新 PR 取代，立即 close（PR #25 已知被 #26 supersede）
     - STALE_DOCS → 內容已被後續 PR 涵蓋 / merge 後重複 / 與 main 衝突無修復價值，close
     - KEEP → 仍有獨立價值，留 open，並指出後續處理計畫
2. 對 SUPERSEDED 與 STALE_DOCS：
     gh pr close <N> --comment "Superseded by #<M> / merged into main / triaged 2026-05-11"
   不需要刪 branch（保留 evidence）。
3. PR #25 必須 close（superseded by #26，已多輪確認）。
4. KEEP 集合 ≤ 3 個 PR；其餘全 close。
5. 報告必須列：close 前數量 / close 後數量 / 每筆裁決理由。
6. 不可 merge 任何 PR（merge 需 explicit YES）。
7. 不可 close PR #2 不確認來源 — 先讀內容再決定。

## 階段 B — Strategy Lifecycle Inventory（read-only）
目標：產出全系統策略清單，作為後續 catalog 補齊的 input。

acceptance：
1. 在 LotteryNew-clean 內建立 branch：
     feature/p1-strategy-lifecycle-inventory-20260511
2. 掃描以下來源並彙總：
     a) lottery_api/models/replay_strategy_registry.py 中所有 adapter（含 meta.lifecycle_status）
     b) rejected/ 目錄下 42 個 JSON（已知：15 promotable / 26 blocked / 1 parse error）
     c) strategies/ 目錄下所有 .py / .yaml 策略檔
     d) lottery_api/data/lottery_v2.db 中 strategy_prediction_replays 內的 distinct strategy_id
     e) memory/MEMORY.md 提到的策略（acb_1bet, midfreq_acb_2bet, 等等）
3. 寫入：
     outputs/replay/p1_strategy_lifecycle_inventory_20260511.json
     outputs/replay/p1_strategy_lifecycle_inventory_20260511.md
   每筆 candidate 含：
     - strategy_id
     - display_name
     - lottery_type (BIG_LOTTO / POWER_LOTTO / DAILY_539)
     - lifecycle_status (ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED / UNKNOWN)
     - source_paths[]
     - source_provenance_hash (sha256 of source file)
     - replay_row_count (從 DB 查 distinct strategy_id count)
     - blocked_reason (如 schema 不全 / parse error)
     - replay_display_eligible (bool — 是否可進下拉選單)
     - generation_eligible (bool — 是否可跑 replay generation，預設僅 ONLINE 為 true)
4. 必須給每個 lifecycle 狀態的計數摘要。
5. 不寫 DB。不改 registry。不改 active strategy state。

## 階段 C — Commit + PR（僅當階段 B 完成且乾淨）
1. 三份 dirty docs（checklist, conclusion, plan）裁決：
     - 若仍有獨立價值 → 移至 outputs/replay/archive/20260510/ 並 commit
     - 若已被 superseded → 不 commit，git clean -f outputs/replay/p2_24h_*_20260510.md
       outputs/replay/p2_no_write_skeleton_implementation_*_20260510.md
   裁決理由寫入：
     outputs/replay/p0_dirty_scope_resolution_20260511.md
2. git add outputs/replay/p0_pr_queue_triage_20260511.md
          outputs/replay/p1_strategy_lifecycle_inventory_20260511.*
          outputs/replay/p0_dirty_scope_resolution_20260511.md
   git diff --check
   git commit -m "docs(replay): triage pr queue and inventory all lifecycle strategies"
   git push -u origin feature/p1-strategy-lifecycle-inventory-20260511
   gh pr create --base main --title "docs(replay): triage pr queue and inventory all lifecycle strategies" \
     --body-file outputs/replay/p1_strategy_lifecycle_inventory_20260511.md
3. 不 merge。

# STRICT RULES（不容違反）
- 不執行 backfill
- 不寫 production DB
- 不改 registry adapters（今天只 inventory，不改 catalog；改 catalog 是下一輪 P2）
- 不改 active strategy state
- 不執行 strategy mining / edge discovery
- 不把 outputs/replay/ 當 runtime source
- 不 merge PR
- 不 close PR #2 不讀內容
- 不動 branch protection

# FINAL MARKERS
A 階段成功：
  P0_PR_QUEUE_TRIAGED_<closed_N>_OF_18
A 階段失敗：
  P0_PR_QUEUE_TRIAGE_BLOCKED_<reason>
B 階段成功：
  P1_STRATEGY_LIFECYCLE_INVENTORY_READY
B 階段失敗：
  P1_INVENTORY_BLOCKED_<reason>
C 階段成功：
  P0_P1_PR_OPEN_<URL>

# OUTPUT FORMAT（回報給 CTO）
1. PR Queue 收斂前/後計數 + 每筆裁決
2. Inventory 各 lifecycle 計數摘要（含 UNKNOWN）
3. registry vs DB row 兩面差距分析（哪些 registry 有但 DB 無 row、哪些 DB 有 row 但 registry 無）
4. 三份 dirty docs 裁決結果
5. PR URL
6. Final marker
7. 下一輪建議（重點：P2 是把非 ONLINE 加進 registry，不寫 DB）
```

---

## 一句話摘要

骨架已上線（PR #12），缺的不是再一份 plan，而是 **「先收 18 個 docs PR 的雜訊」+「把所有策略盤點出來」**；今天動到的只有 inventory.json 與 PR queue，不動 registry、不動 DB、不動 active state。