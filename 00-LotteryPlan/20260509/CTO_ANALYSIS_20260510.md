已完成 CTO roadmapping 重新校準，直接更新了：

- [MASTER_ROADMAP_2026.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/MASTER_ROADMAP_2026.md)
- [lottery_roadmap_20260510.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/00-LotteryPlan/20260510/lottery_roadmap_20260510.md)
- [phase4_manifest_locked.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew/00-LotteryPlan/20260510/phase4_manifest_locked.md)

核心決策：

P0 已改為 **Replay Product Go-Live Closure**，也就是你補充的目標：策略歷史回放頁要能查所有 lifecycle 狀態的策略，並逐期顯示「策略當時預測」vs「實際開獎」的比對清單，互動形式對齊現有歷史預測清單。

我也確認 `engine.h6_live_monitor` 只存在於 noisy 主工作樹，不在 clean `origin/main` worktree。結論是：這屬於 **H6 monitoring / rollback lane**，不應繼續阻塞 Replay 產品 P0。因此 manifest 已從 15 檔收斂為 13 檔，並把：

- `tests/test_h6_cli_scripts.py`
- `tests/test_h6_e2e_phase4.py`
- `lottery_api/engine/h6_live_monitor.py`

明確列入 EXCLUDE 裁決。

新的優先序是：

P0 Replay 頁面上線閉環  
P1 lifecycle catalog + canonical row backfill  
P2 replay data completeness / freshness  
P3 clean branch / manifest / CI delivery  
P4 dedicated DB lane observation  
P5 replay UI contract hardening  
P6 H6 monitoring lane separation  
P7 forbidden-language sweep  
P8 blocked evidence normalization  
P9 branch protection / stale PR cleanup  
P10 advisory-only research lanes

未跑測試，因為本輪只做 CTO 分析與 roadmap/manifest 文件更新。

我以 CEO 身分對 CTO 的 20260510 校準做完二次審查。下面先講審查結論，再給你今天直接可執行的任務 prompt。

---

## CEO 二次審查

### 1. 昨天成果是否真的推進系統成熟度

部分推進，但有 workflow stuck：

| 維度 | 評估 |
|---|---|
| P1 dry-run manifest（42 / 15 / 26 / 1） | ✅ 有產出，read-only 正確 |
| `codex/p1-replay-lifecycle-rejected-canonical-promotion-plan` 已 push | ✅ |
| **PR 未開、CTO review 未做、26 blocked / 1 parse error 未處理** | ❌ 工作停在 ready 狀態 |
| 未寫 DB、未動 registry、未動 branch protection | ✅ 正確 |
| 未跑生產測試、未動 UI | ✅ 但也代表使用者看到的「Replay 頁面」沒有任何前進 |

結論：**研究/治理層推進，產品層原地不動。** 對「使用者要的回放頁」沒有任何可見 progress。

### 2. CTO 判斷是否合理 + 盲點

| 判斷 | 評價 |
|---|---|
| P0 從「clean branch rebuild」改為「Replay Product Go-Live Closure」 | ✅ 對齊使用者真正目標 |
| H6 從 P0 manifest 排除（15→13 檔） | ✅ 正確，`engine.h6_live_monitor` 確實不在 origin/main |
| Stop Rules（不改 branch protection、不 merge、不寫 DB） | ✅ 正確 |
| 將 lifecycle catalog backfill 設為 P1（P0 之後） | ⚠️ **盲點 1：P0 要顯示「all lifecycle states」，沒 catalog rows 時 P0 必然只能顯示 6 個 ONLINE → P0 與 P1 實質是同一個任務，不能拆順序，應併行** |
| 未提及「使用者已經無法管理 5+ 個 worktree」 | ❌ **盲點 2：完全漏掉組織層阻塞。`git worktree list` 顯示 7 個 worktree 在動，使用者已明說「無法管理」** |
| 「未跑測試，因為本輪只做 CTO 分析」 | ⚠️ **盲點 3：roadmap 改動後應 sanity-check「P0 可達性」，例如真的去 query 一次 `strategy_prediction_replays` 看有沒有非 ONLINE 資料，而不是直接寫 acceptance** |
| P0 acceptance 寫了 5 個 lifecycle filters，但沒驗證 DB 真的有對應資料 | ⚠️ **盲點 4：P0 可能變成空殼 UI（filter 點下去全 empty state）** |

### 3. Worktree 為什麼長這麼多 — 根因

從 `git worktree list` 看到實際狀況：

```
LotteryNew                         feature/phase4-required-check-20260509   ← noisy 主樹
LotteryNew-clean                   feature/phase4-required-check-clean-20260510
LotteryNew-main-postmerge          codex/p1-replay-lifecycle-rejected-...
LotteryNew-roadmap-20260509        codex/replay-required-check-roadmap-...
/private/tmp/lotterynew-phase4-clean                       phase4-clean
.claude/worktrees/gallant-rosalind-97a32a (本 session)
.claude/worktrees/vigilant-meninsky-6af4cd
```

加上 Finder 看到的 `LotteryNew-p0-release` 已脫離 git worktree control（孤兒目錄）。

根因：

1. 每次「重新校準」CTO 都新建一個 worktree（`-roadmap-20260509`、`-main-postmerge`、`-clean`）而沒回收舊的
2. `.claude/worktrees/*` 是 Claude Code 自動建的 ephemeral worktree，每個 session 一個，沒設清理上限
3. `/private/tmp/lotterynew-phase4-clean` 是臨時測試 worktree，沒清掉
4. `LotteryNew-p0-release` 已從 git worktree 表脫離但實體目錄留著

這必須在今天解決，否則下一輪 CTO 又會生第 8 個。

---

## 今天最應聚焦的優化方向（CEO 重排 P0~P10）

| 優先序 | 項目 | 與 CTO 版本差異 |
|---|---|---|
| **P0** | Replay 頁面 lifecycle **全狀態 + 逐期 預測 vs 開獎比對清單** 真實上線 | 同 CTO，但 **acceptance 必須包含「非 ONLINE 狀態真的能看到資料 row」** |
| **P1** | Worktree / Repo 收斂治理（解決 5+ 個 worktree 失控） | **CTO 完全漏掉，CEO 拉到 P1** |
| **P2** | Lifecycle catalog backfill（CTO 的 P1 拉前，與 P0 併行） | 因為 P0 acceptance 要有非 ONLINE 真資料 |
| **P3** | Clean branch / manifest / CI delivery | 同 CTO P3 |
| **P4** | Dedicated DB lane observation | 同 CTO P4 |
| **P5** | Replay UI contract hardening | 同 CTO P5 |
| **P6** | H6 monitoring lane 分離（不再進 Replay PR） | 同 CTO P6 |
| **P7** | Forbidden-language sweep | 同 CTO P7 |
| **P8** | 26 blocked rows + 1 JSON parse error 修復 | 同 CTO P8，但要與 P2 併進度 |
| **P9** | Branch protection / stale PR / 舊 `codex/p1-...` branch 收尾 | 加上昨天 push 但未開 PR 的 codex branch 去處決定 |
| **P10** | Worktree / Branch hygiene 守則（防再膨脹） | CTO P10 升級為「制度」而非「事後清理」 |

---

## 直接可執行的任務 Prompt（今天從這裡開始）

```text
# ROLE
你是 LotteryNew 的 P0 Replay Product Go-Live Agent + Worktree Hygiene Owner，
向 CTO 回報，CTO 向 CEO 回報。

# MISSION（今天要做兩件事，順序固定）

## 階段 A — Worktree 收斂（先做，不做完不能進階段 B）
目標：把 ~/Kelvin-WorkSpace/ 下與 LotteryNew 相關的 worktree
從目前 5 個目錄 + 多個 ephemeral worktree 收斂成 **唯一一個工作 worktree**。

acceptance：
1. 唯一保留 worktree：~/Kelvin-WorkSpace/LotteryNew-clean
   分支基於 origin/main，且乾淨 (git status 空)。
2. 其餘下列 worktree 須在 git 層 prune 掉並在檔案系統移除（先確認沒未推送 commit）：
   - ~/Kelvin-WorkSpace/LotteryNew-main-postmerge
   - ~/Kelvin-WorkSpace/LotteryNew-roadmap-20260509
   - ~/Kelvin-WorkSpace/LotteryNew-p0-release（孤兒，git worktree 已不認）
   - /private/tmp/lotterynew-phase4-clean
3. ~/Kelvin-WorkSpace/LotteryNew（noisy 主樹）保留，但**標記為 source-only**，
   今天起不在此 worktree 做任何 commit。請在該目錄根目錄寫入：
     SOURCE_ONLY_DO_NOT_COMMIT.md
4. 對任何尚未推到 origin 的 commit，先 push 到對應遠端 branch 後再刪 worktree。
5. 跑：
     git worktree list
   確認最終只剩：
     - LotteryNew (source-only)
     - LotteryNew-clean (sole working worktree)
     - .claude/worktrees/* (Claude session ephemeral，可保留)

## 階段 B — Replay Product Go-Live Closure（在 LotteryNew-clean 內做）
目標：完成「策略歷史回放頁」的 lifecycle 全狀態 + 逐期 預測 vs 開獎比對清單。

acceptance：
1. Branch：feature/replay-product-golive-clean-20260510，基於 origin/main。
2. 在動 UI 之前，先跑下列健康檢查並把結果寫入：
     outputs/replay/p0_replay_data_health_20260510.md
   - SELECT lifecycle_status, COUNT(*) FROM strategy_prediction_replays
       (確認 ONLINE / OFFLINE / REJECTED / OBSERVATION / RETIRED 各幾 row)
   - 列出哪幾個 lifecycle_status 完全沒資料 → 那是「P0 顯示為誠實 empty state」的明確清單。
   不允許靠 outputs/replay/ artifact 假裝 row 存在。
3. /api/replay/strategies, /history, /summary, /freshness 必須：
   - 接受 lifecycle_status 過濾參數
   - 回傳的每一 row 至少含：
       lottery, target_draw, target_date, strategy_id, lifecycle_status,
       predicted_numbers, actual_numbers, hit_numbers, hit_count, replay_status
   - 來源僅讀 DB 表 (strategy_prediction_replays + strategy_replay_runs + 策略 catalog)，
     **不得讀 outputs/replay/ 任何 .json/.md 當作 runtime data**。
4. UI（index.html / replay 區塊）：
   - lifecycle 篩選器顯示全部 5 狀態（即使某狀態為 0 row）
   - 表格欄位順序與「歷史預測清單」對齊：期別 / 日期 / 策略 / 預測號碼 / 實際號碼 / 命中號碼 / 命中數 / 狀態
   - 為 0 row 的 lifecycle 顯示誠實 empty state 文案（"目前無此狀態策略，等待 catalog backfill"），
     不可造假
5. 文案禁止任何「最佳策略」「推薦投注」「edge」「勝率」字眼（forbidden-language sweep HIGH=0）
6. 加 / 改測試（在 manifest 範圍內）：
   - tests/test_replay_api_contract.py 補：
       lifecycle_status=OFFLINE/REJECTED/OBSERVATION/RETIRED 各一個 case，
       不論 0 row 都要回 200 + 正確 schema
   - tests/test_replay_browser_smoke.py 補：
       切換 lifecycle filter 後表格 DOM 變更被觀察到
7. 不得納入：
   - tests/test_h6_cli_scripts.py
   - tests/test_h6_e2e_phase4.py
   - lottery_api/engine/h6_live_monitor.py
   manifest 維持 13 檔基線，新增檔請逐一在 manifest 註記。
8. 本輪不得：
   - 寫生產 DB
   - 修改 active strategy state
   - 修改 branch protection
   - 執行 strategy mining / edge discovery
   - 直接把昨天 codex/p1-...-promotion-plan 的 15 promotable rows 寫進 registry
     （那是 P2 的事；今天 P0 只負責「能誠實顯示」，不負責「灌資料」）

# REQUIRED COMMANDS（依序）

## A 階段
git worktree list
# 對每個要刪的 worktree：
cd <worktree>; git status --short; git fetch origin; git push origin HEAD:<branch> || true
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew
git worktree remove --force <path>   # 對 git 認得的
rm -rf <path>                         # 對孤兒目錄
git worktree prune
git worktree list

## B 階段
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean
git fetch origin --prune
git checkout -B feature/replay-product-golive-clean-20260510 origin/main

# 健康檢查
python3 - <<'PY'
import sqlite3
con = sqlite3.connect("lottery_api/data/lottery_v2.db")
for row in con.execute("""
  SELECT lifecycle_status, COUNT(*) FROM strategy_prediction_replays
  GROUP BY lifecycle_status
"""):
    print(row)
PY

# 跑驗證
python3 scripts/run_replay_ci_default_validation.py
python3 scripts/run_replay_ci_db_validation.py
python3 -m pytest tests/test_replay_api_contract.py tests/test_replay_browser_smoke.py -x

git diff --check

# Commit + push（僅當全部 PASS）
git add <P0 manifest 內列出的檔>
git commit -m "feat(replay): lifecycle full-state replay product go-live"
git push -u origin feature/replay-product-golive-clean-20260510

gh pr create --base main \
  --head feature/replay-product-golive-clean-20260510 \
  --title "feat(replay): lifecycle full-state replay product go-live" \
  --body-file outputs/replay/p0_replay_data_health_20260510.md

# 不得 merge。

# FINAL MARKERS
A 階段成功：
  WORKTREE_HYGIENE_CONVERGED_TO_LOTTERYNEW_CLEAN
A 階段失敗：
  WORKTREE_HYGIENE_BLOCKED_<reason>
B 階段成功：
  P0_REPLAY_PRODUCT_PR_OPEN
B 階段失敗：
  P0_REPLAY_PRODUCT_BLOCKED_<reason>

# 報告檔（commit 進 PR）
outputs/replay/p0_replay_data_health_20260510.md
outputs/replay/p0_replay_product_golive_pr_readiness_20260510.md

# 報告必須含
1. Worktree 收斂前/後 git worktree list
2. 各 lifecycle_status 的 row 數（含 0 row 列表）
3. API 真實回應樣本（每個 lifecycle 一筆）
4. UI 截圖描述 / DOM diff 摘要
5. 測試結果（含 pytest 通過數）
6. forbidden-language sweep 結果
7. 確認沒寫 DB / 沒改 registry / 沒改 branch protection
8. PR URL
```

---

## 摘要

- 昨天 P1 dry-run manifest 完成，但**產品頁零進展、PR 未開、worktree 失控**。
- CTO 校準把 P0 對齊真正目標方向正確，但**漏看 worktree 治理、漏驗 DB 真資料、把 P0/P1 順序拆錯**。
- 今天執行順序：**先 A（worktree 收斂到 LotteryNew-clean 唯一工作樹）→ 再 B（在 clean 樹上把 lifecycle 5 狀態 replay 頁開 PR）**。
- 上面那段 prompt 直接餵給下一個執行 agent 即可。