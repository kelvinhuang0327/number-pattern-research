已完成 CTO roadmap 重排與文件落地。核心判斷很清楚：**P25 已完成「所有策略可見」的 Phase A，但你補充的真正目標是「所有曾開發策略都能逐期 prediction-vs-actual 比對」；這一段尚未完成。**

我已新增兩份文件：

- [strategy_history_replay_roadmap.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/docs/replay/strategy_history_replay_roadmap.md:1)  
  新的 living roadmap，已重排 P0-P10，明確把下一階段定為 Replay Truth Coverage。
- [p55_replay_truth_roadmap_review_20260512.md](/Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean/outputs/replay/p55_replay_truth_roadmap_review_20260512.md:1)  
  本輪 P55 CTO review / handoff，方便下一輪直接接續。

目前狀態確認：

| 項目 | 結論 |
|---|---|
| main | `186949e` |
| open PR sweep | `[]` |
| tracked replay DB | clean |
| active smoke | skipped，因本輪未明確要求 active smoke |
| untracked | `data/performance_history.json` 仍存在，未處理 |

最重要的進度判斷：

| Lifecycle | 目前畫面狀態 | prediction-vs-actual truth |
|---|---|---|
| ONLINE | 已有歷史預測清單 | 有，6 個策略、460 rows |
| REJECTED | display-only catalog | 無 production replay rows |
| RETIRED | display-only catalog | 無 production replay rows |
| OBSERVATION | display-only catalog | 無 production replay rows |
| OFFLINE | coming soon / empty | 目前 0 策略 |

重排後最該聚焦的方向是：

**P0-P3：Replay Truth Coverage**
P0 roadmap truth-level 對齊已完成。下一步應做 P1 all-lifecycle replay coverage manifest，再做 P2 non-ONLINE provenance recovery，最後才進 P3 no-write replay-row dry-run manifest。

關鍵阻塞是：非 ONLINE 策略目前是 lifecycle stubs，不能直接 replay generation；10 個非 ONLINE 策略沒有 production replay rows；OFFLINE 目前沒有 canonical entries；production backfill 仍未授權。

下一個最值得執行的 YES：

```text
YES generate all-lifecycle replay coverage manifest
```

這一步只做 no-write coverage manifest，不寫 DB、不 backfill、不 mining、不 promotion。它會把 16 個策略逐一標出 row count、missing-history reason、provenance class，這是進入真正全策略歷史回放前最穩的下一步。

# CEO 二次審查報告 — 2026-05-12

## 1. 對昨天成果的判斷

**結論：昨天的工作有完成度但沒有推進核心成熟度。**

- P23 Fixture Mode UI Toggle（PR #63 merged）+ PR #64 docs PR：執行品質高（94/94 tests、forbidden diff 全綠、DB clean），但這只是把 fixture mode 從 URL 手動切換改成 UI toggle，**對最終產品目標「全策略歷史預測 vs 實際開獎對照」沒有直接貢獻**。
- Fixture mode 仍是 synthetic only / advisory only，本質仍是給開發者驗收用的，不是給營運操作員看真實 replay truth 的途徑。
- 真正的產品 gap（非 ONLINE 的 10 個策略沒有 production replay rows）仍然存在，**昨天沒有縮短這段距離**。

換句話說：昨天是把「視覺層」與「fixture toggle UX」收尾，但 **資料層 / replay truth 層幾乎沒動**。

---

## 2. 對 CTO 判斷的二次審查

CTO 的方向判斷正確：「P25 = Phase A visibility 已完成，Phase B = replay truth coverage 尚未完成」。但有幾個盲點需要點出：

### 2.1 CTO 盲點 #1 — 沒有先搜尋既有歷史預測紀錄
CTO 直接跳到「provenance recovery / regeneration」，忽略了系統其實已經有 `prediction_logger`（JSONL）、`data/performance_history.json`、以及可能存在的策略執行 log。**在決定要不要 regenerate 之前，必須先做一輪「historical prediction inventory」**，因為：
- 已存在的歷史預測比 regenerate 更可信（沒有 look-ahead 風險）
- regenerate 一個 REJECTED 策略的歷史預測，是否會引入 hindsight bias 必須先審
- 如果某些 REJECTED/RETIRED 策略當時就有產出預測紀錄，**直接 ingest 比重跑安全得多**

### 2.2 CTO 盲點 #2 — P1 manifest 與 P2 provenance 應合併
CTO 把 P1 coverage manifest 與 P2 provenance recovery 拆成兩輪。實務上，coverage manifest 沒有 provenance 欄位是不完整的，會白做一輪。應該一次出齊：**每個策略 → lifecycle / row count / 既有預測紀錄來源 / adapter 是否可執行 / provenance 分類 / 阻塞原因**。

### 2.3 CTO 盲點 #3 — 沒有區分「retrospective regeneration」與「true historical prediction」
這是產品上**最危險的盲點**。如果我們用今天的程式碼去重跑一個 RETIRED 策略對 2 年前開獎的預測，這份「預測」並不是當年的真實預測，而是 retrospective backtest，**和 ONLINE 策略的 production replay truth 不是同一種東西**。UI 上如果不嚴格區分，就是 mis-claim。

CTO 提到了 `PRODUCTION_REPLAY` / `DISPLAY_ONLY` / `FIXTURE_ONLY` / `MISSING_HISTORY` badge，但缺少最關鍵的 `REGENERATED_RETROSPECTIVE` 這個 truth level。

### 2.4 CTO 判斷正確的部分
- production backfill 必須維持 blocked ✓
- strategy mining / OFFLINE introduction 繼續 defer ✓
- 下一步 `YES generate all-lifecycle replay coverage manifest` 是正確的 no-write 起點 ✓
- 不要在沒有 provenance 的情況下動 DB ✓

---

## 3. CEO 重排後的 P0–P10

| Priority | 焦點 | 為什麼是這個順序 | Gate |
|---|---|---|---|
| **P0** | Roadmap alignment（已完成） | CTO 已落地 | done |
| **P1** | **All-lifecycle replay inventory + provenance manifest（合併版）** | 一次出齊：16 策略的 row count、既有 prediction log 來源、adapter 可執行性、provenance class、阻塞原因。**這是今天該做的唯一一件事** | no-write，需 YES |
| **P2** | **Truth-level taxonomy decision memo** | 明確定義 PRODUCTION_REPLAY / REGENERATED_RETROSPECTIVE / DISPLAY_ONLY / FIXTURE_ONLY / MISSING_HISTORY 五級，並決定 UI 如何標示 | docs only |
| **P3** | **No-write retrospective generation dry-run（可執行的策略）** | 對 P1 中標記 REGENERATABLE 的策略，產生 dry-run prediction manifest，但不寫 DB、不寫任何持久檔案以外的 output | 需 YES |
| **P4** | **Storage lane decision**：production DB vs 獨立 replay evidence store | 決定 retrospective rows 要不要進 `strategy_prediction_replays`，還是另一張表/檔 | CTO YES |
| **P5** | **UI truth-level parity**：badge / 同 table shape 渲染各 truth level | 利用 P25 已完成的 catalog 基礎，補上 badge 與 truth level 區分 | 需 P2 完成 |
| **P6** | **Controlled retrospective backfill**（不是 production backfill） | 在 evidence store 或標註明確的 lane 寫入 retrospective rows | 需 explicit YES + snapshot |
| **P7** | **Post-apply smoke + live operator walkthrough** | 重跑 P23 等級的 browser + API 驗證 + 截圖 | only after P6 |
| **P8** | **Operational hardening**：backend startup runbook、`data/performance_history.json` 處理、DB dirty SOP | 降低操作摩擦，低風險 | low YES |
| **P9** | **OFFLINE policy（仍 defer）** | 沒有候選策略就不要造 OFFLINE 假鋪陳 | deferred |
| **P10** | **Strategy mining / lifecycle promotion（仍 defer）** | replay truth 沒收斂前不要新增雜訊 | deferred |

**今天最該聚焦：P1。** 這是 information-gathering，把後面 P2–P6 的決策路徑收斂出來。

---

## 4. 今天要直接執行的 Task Prompt

```text
# ROLE
你是 LotteryNew 的 Replay Truth Coverage Inventory Agent。
向 CTO 回報，CTO 向 CEO 回報。
本輪不寫 DB、不 backfill、不 mining、不 promotion、不動 fixture artifact。
本輪只產出 read-only inventory + provenance manifest。

# CONTEXT
上一輪 P23 Fixture Mode UI Toggle 已收尾（PR #63 / #64 已處理）。
CTO 已將 roadmap 重排為 Replay Truth Coverage 為主軸。
CEO 二次審查確認：下一步唯一該做的是 P1 — All-lifecycle Replay Inventory + Provenance Manifest（合併版）。
main SHA: 186949e

已知資料切片（read-only）：
- registered strategies: 16
- ONLINE: 6 (有 production replay rows)
- REJECTED: 4 / RETIRED: 5 / OBSERVATION: 1 / OFFLINE: 0 (rows = 0)
- strategy_prediction_replays 共 460 rows，全部屬於 6 個 ONLINE 策略

# MISSION
針對 16 個註冊策略，產出 ONE manifest + ONE markdown report，包含：
- 每一個策略的 lifecycle / lottery type / production replay row count / status counts
- 是否存在「既有歷史預測紀錄」(JSONL log / performance_history / 其他檔案)
- adapter 是否可在不寫 DB 的情況下被執行（READABLE / EXECUTABLE / STUB_ONLY / MISSING）
- provenance class: PRODUCTION_REPLAY / REGENERATABLE / IMPORT_ONLY / EVIDENCE_ONLY / NOT_RECONSTRUCTABLE
- 阻塞原因（一句話）
- 建議 truth level（PRODUCTION_REPLAY / REGENERATED_RETROSPECTIVE 候選 / DISPLAY_ONLY / MISSING_HISTORY）

# STRICT RULES
- 不寫 production DB
- 不修改 data/lottery_v2.db（讀取必須 read-only；測完用 git checkout HEAD -- data/lottery_v2.db 還原）
- 不執行任何 strategy adapter 產出預測（本輪僅做靜態盤點，不 run predict）
- 不改 registry / lifecycle taxonomy / fixture artifact
- 不新增 OFFLINE filter / OFFLINE rows
- 不 promotion / retire / mining
- 不動 branch protection
- 沒有 explicit YES 不可開 PR；YES 後僅開 docs PR，不 merge

# STAGE A — Repo & DB Baseline
1. cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean
2. git fetch origin && git checkout main && git pull --ff-only
3. git log --oneline -5  → 確認 HEAD = 186949e
4. gh pr list --state open
5. git status --short data/lottery_v2.db
6. sqlite3 read-only 連線統計：
   - SELECT lifecycle_state, COUNT(*) FROM strategies GROUP BY lifecycle_state;
   - SELECT strategy_name, COUNT(*), SUM(CASE WHEN status='PREDICTED' THEN 1 ELSE 0 END),
            SUM(CASE WHEN status='REPLAY_ERROR' THEN 1 ELSE 0 END)
     FROM strategy_prediction_replays GROUP BY strategy_name;
7. 若 DB dirty：git checkout HEAD -- data/lottery_v2.db

# STAGE B — Historical Prediction Inventory（最重要）
對每一個策略檢查是否存在歷史預測紀錄：
1. grep prediction logger 路徑（JSONL / per-strategy log）
2. 檢查 data/performance_history.json 是否覆蓋該策略
3. 檢查 outputs/ 內是否有對應 strategy 的歷史結果檔
4. 檢查 lottery_api/ 內 adapter 檔案是否存在且 import 不報錯（不執行）
5. 對每個策略輸出：
   - has_existing_prediction_log: true/false
   - log_paths: [...]
   - adapter_module: path or null
   - adapter_importable: true/false
   - row_count_in_db: int

# STAGE C — Provenance Classification
依 Stage B 結果分類每個策略：
- PRODUCTION_REPLAY: 已有 DB rows (ONLINE 6 個)
- REGENERATABLE: adapter 可 import + 有確定性輸入 → 未來可 dry-run 產生 retrospective
- IMPORT_ONLY: 有既有 prediction log，但 adapter 無法重跑 → 只能 import
- EVIDENCE_ONLY: 只有評估報告，沒有逐期預測
- NOT_RECONSTRUCTABLE: 無 adapter、無 log、無 evidence

# STAGE D — Truth Level Candidate
給每個策略一個建議的 UI truth level：
- PRODUCTION_REPLAY（ONLINE 6 個）
- REGENERATED_RETROSPECTIVE 候選（之後 P3 才會真正產生）
- DISPLAY_ONLY（沿用 P25 catalog 處理）
- MISSING_HISTORY（標明無法重建）

# STAGE E — Produce Artifacts
產出兩份檔案：
1. outputs/replay/p56_all_lifecycle_replay_coverage_manifest_20260512.json
   {
     "generated_at": "2026-05-12",
     "main_sha": "186949e",
     "db_read_only_proof": {"sha256_before": "...", "sha256_after": "...", "match": true},
     "strategies": [
       {
         "name": "...",
         "lifecycle": "...",
         "lottery_type": "...",
         "row_count": int,
         "status_counts": {...},
         "has_existing_prediction_log": bool,
         "log_paths": [...],
         "adapter_module": "...",
         "adapter_importable": bool,
         "provenance_class": "...",
         "truth_level_candidate": "...",
         "blocker_reason": "..."
       },
       ... (16 entries)
     ]
   }

2. outputs/replay/p56_all_lifecycle_replay_coverage_report_20260512.md
   內容：
   - 摘要表格（16 列）
   - Provenance 分類統計
   - Truth Level 分布統計
   - 預期下一步 (P2 truth taxonomy decision memo / P3 dry-run scope)
   - Safety invariant 摘要 (production DB write: NO 等)
   - DB read-only proof
   - 待解決問題清單

# STAGE F — Docs PR（YES-gated）
僅在收到以下任一明確指令才執行：
- YES open coverage manifest docs PR
- Approve docs PR
- Merge gate is for docs only

若 YES：
1. branch: docs/p56-all-lifecycle-replay-coverage-manifest-20260512
2. git add outputs/replay/p56_all_lifecycle_replay_coverage_manifest_20260512.json
3. git add outputs/replay/p56_all_lifecycle_replay_coverage_report_20260512.md
4. git commit -m "docs(replay): all-lifecycle replay coverage manifest (P56)"
5. git push -u origin docs/p56-all-lifecycle-replay-coverage-manifest-20260512
6. gh pr create --base main \
     --title "docs(replay): all-lifecycle replay coverage manifest" \
     --body-file outputs/replay/p56_all_lifecycle_replay_coverage_report_20260512.md
7. 不 merge

# STAGE G — Final Report to CTO
回報以下欄位：
1. main SHA
2. 開啟 PR 清單
3. DB final status (clean / dirty 並已 restore)
4. 16 策略 provenance 分類統計
5. truth level 分布
6. 阻塞最嚴重的 3 個策略（NOT_RECONSTRUCTABLE 或 STUB_ONLY）
7. 建議下一步：
   - P2 truth taxonomy decision memo
   - P3 dry-run scope（哪幾個 REGENERATABLE 策略適合先做）
8. safety invariant 摘要
9. final markers

# FINAL MARKERS
- P56_REPLAY_COVERAGE_INVENTORY_COMPLETE
- P56_PROVENANCE_CLASSIFICATION_COMPLETE
- P56_NO_DB_WRITE_VERIFIED
- P56_DB_FINAL_CLEAN
- 若 docs PR 建立：P56_COVERAGE_MANIFEST_PR_OPEN_<URL>
- 若未收 YES：WAITING_FOR_USER_YES_GATE_P56_PR
```

---

## 5. 一句話總結給 CEO 自己

昨天 P23 是漂亮的收尾但不是推進；今天的唯一動作是 **P56 inventory + provenance manifest（read-only, no-write）**，把 16 個策略的「能不能重建歷史預測、要走哪條 truth lane」一次盤清楚，這是進入真正全策略歷史回放前的最後一個安全節點。