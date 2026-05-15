# CEO 最終裁示 — 同意「Merge Train + P6-lite」，但要硬化 5 個風險

**結論先講：你的根因分析正確、路線正確、優先序正確。我核准執行。**

但你提的 prompt 有 5 個會在執行中爆掉的隱性 risk，必須在動手前硬化。否則我們很可能跑到 Phase 5/6 才發現「schema 不支援 truth_level」或「API 不會回 regenerated rows」，又卡一輪。

---

## 1. 同意你的核心判斷

| 你提的判斷 | CEO 核准 |
|---|---|
| 卡點不是技術，是「rows 沒進可查詢資料層」 | ✅ 對 |
| 不再追 16/16，先 ship 6/16 V1 | ✅ 對 |
| 停止 P4 artifact parser、改做 Merge Train + P6-lite | ✅ 對 |
| Merge order #92 → #93 → #94 → #95 | ✅ 對 |
| 只 apply P3 的 300 rows，不碰 artifact-only / code-missing | ✅ 對 |
| V1 / V2 / V3 階段切分 | ✅ 對 |

不需要再開 P4 audit。這一輪結束時，使用者就要在 UI 看到 6 個策略各 50 筆 retrospective rows。

---

## 2. 必須硬化的 5 個風險（執行前先回答，否則必爆）

### Risk 1: Schema 可能根本不支援 `truth_level` / `provenance_hash` 欄位
`strategy_prediction_replays` 當初是為 ONLINE adapter rows 設計的，**很可能沒有** `truth_level`、`source`、`provenance_hash`、`controlled_apply_id` 欄位。  
→ Phase 4 必須**第一個動作**就 `PRAGMA table_info(strategy_prediction_replays);`，缺欄位的話，**先用 ALTER TABLE ADD COLUMN（NOT NULL DEFAULT … 或 nullable）**，這是 V1 不可避免的 schema migration。  
→ 若 CTO/agent 試圖用既有欄位 squeeze 進 metadata（例如塞進 status 或 notes），**直接 reject**。

### Risk 2: PR #94 的 truth-level badge 需要 API 回傳 `truth_level` 欄位
若 API endpoint 還沒把 `truth_level` 加進回傳 JSON，badge 永遠不會亮 — UI smoke 會 PASS（badge code 存在）但實際畫面看不到。  
→ Phase 8 API verification 必須**明確 grep** API response 是否含 `truth_level` key，不只是看 row 數。  
→ 若 API 不回傳，立即補一個 small backend PR（不算新 P4，是 P6-lite scope 內收尾）。

### Risk 3: Idempotency — apply 跑兩次會變成 600 rows
P3 的 300 rows 每筆 `(strategy_id, draw_no)` 應為自然 unique key。  
→ Phase 5 apply script 必須：
- 用 `INSERT ... ON CONFLICT(strategy_id, draw_no, truth_level) DO NOTHING`（SQLite 支援），或
- 先 SELECT 檢查，存在的 skip 並記錄
- 帶 `controlled_apply_id`（UUID 或 timestamp），方便 rollback 用 `DELETE WHERE controlled_apply_id = ?`

### Risk 4: Rollback 不能用「transaction log strategy」這種模糊字眼
→ 必須有**兩條 rollback path 同時備好**：
- **Path A（首選）**: `DELETE FROM strategy_prediction_replays WHERE controlled_apply_id = '<id>';`，跑完 row count 必須 = 300
- **Path B（保險）**: Phase 3 snapshot 的 DB binary backup file，直接 `cp` 覆蓋
- Path B 在 apply 後立刻測一次 restore 到臨時 copy 驗證可恢復，避免事後才發現 backup 壞了

### Risk 5: `dry_run_only=true` 在 JSONL 裡是 flag，進 DB 後語意必須翻轉
原 JSONL 是 dry-run artifact，`dry_run_only=true` 表示「這還沒進 DB」。  
進 DB 後這個值若仍寫成 true，下游 query 會誤判「這些不是 production data」，badge 就會錯標。  
→ 寫入 DB 的 row 該欄位（若保留）必須是 `dry_run_only=false`、`source='p6_lite_controlled_apply'`，並另開 `provenance_source='p3_retrospective_dryrun_20260513'` 區分 lineage。

---

## 3. 對應的 P0-P10 重排（V1 / V2 / V3 切版本）

| 優先 | 主題 | 屬於 |
|---|---|---|
| **P0** | Merge train #92 → #93 → #94 → #95 | V1 |
| **P1** | P6-lite schema check + ALTER TABLE（若需要） | V1 |
| **P2** | P6-lite controlled apply 300 rows（含 idempotency + rollback proof） | V1 |
| **P3** | API contract check + 若需要的最小 backend patch（讓 API 回傳 truth_level） | V1 |
| **P4** | UI smoke：6 策略可展開逐期 row + badge 正確顯示 | V1 |
| **P5** | V1 closure report + tag | V1 |
| **P6** | ARTIFACT_ONLY parser（4 個 REJECTED） | V2 |
| **P7** | ARTIFACT_ONLY import dry-run + controlled apply | V2 |
| **P8** | CODE_MISSING 6 個策略 tombstone 顯示 + 文件化 | V3 |
| **P9** | DAILY_539 `FAILED_LEGACY` 標籤 + h6 evidence commit | V3 |
| **P10** | OFFLINE policy / strategy mining / promotion | 全部延後 |

**今天唯一目標：V1（P0-P5）一氣呵成。**

---

## 4. 硬化版任務 Prompt（直接覆蓋你原 prompt 用這版）

```text
# ROLE
你是 LotteryNew 的 V1 Closure Agent：Merge Train + P6-lite Controlled Apply。
向 CTO 回報，CTO 向 CEO 回報。
本輪只做 V1：讓 6 個 EXECUTABLE_NOW 策略的 retrospective rows 真正進入 production DB
並在 UI 可見。不做 P4 artifact parser、不碰 ARTIFACT_ONLY / CODE_MISSING。

# CONTEXT
- main HEAD 待 Phase 0 verify
- PR #92 (configurable API base)
- PR #93 (all-source executable evidence inventory)
- PR #94 (truth-level badge UI/API)
- PR #95 (P3 retrospective dry-run, 300 rows)
- P3 artifacts:
  - outputs/replay/p3_retrospective_candidate_rows_20260513.jsonl  (300 rows)
  - outputs/replay/p3_retrospective_candidate_summary_20260513.json
  - outputs/replay/p3_retrospective_regeneration_dryrun_report_20260513.md
- P3 結果：6/6 EXECUTABLE_NOW 策略；300/300 leakage guard PASS；
  全部 truth_level=REGENERATED_RETROSPECTIVE；DB/registry hash 未變。
- 阻塞根因：rows 未進可查詢資料層 + PR chain 未 merge。

# CEO 要求的 5 個必硬化點（執行前必須先在 Phase 4 / 5 處理，否則整輪 abort）
R1. SCHEMA: strategy_prediction_replays 必須有 truth_level / source / provenance_hash /
    provenance_source / controlled_apply_id 欄位，缺則需 ALTER TABLE ADD COLUMN
    （nullable 或 DEFAULT；不可破壞既有 460 rows 的讀取）
R2. API: replay endpoint 回傳 JSON 必須含 truth_level key；
    若不含，需在 V1 內補 minimal backend patch（不擴 scope）
R3. IDEMPOTENCY: 用 (strategy_id, draw_no, truth_level) unique；apply 必須 ON CONFLICT DO NOTHING
    或 SELECT-then-skip；每次 apply 帶 controlled_apply_id
R4. ROLLBACK: 兩條 path 都要 ready
   - Path A: DELETE FROM strategy_prediction_replays WHERE controlled_apply_id=?
   - Path B: DB binary snapshot restore；snapshot 取完後立刻 restore 到 tmp 路徑驗證可恢復
R5. SEMANTIC: 進 DB 的 row 必須 dry_run_only=false（若欄位存在）、
    source='p6_lite_controlled_apply'、provenance_source='p3_retrospective_dryrun_20260513'

# REQUIRED USER AUTHORIZATION
本輪需以下任一或全部明確指令才執行對應動作：
- YES merge PR #92
- YES merge PR #93
- YES merge PR #94
- YES merge PR #95
- YES apply P6-lite controlled retrospective rows
- YES patch API to expose truth_level (若 Phase 8 發現 API gap 才需要)
未授權則停在 readiness report，不得 merge / apply / schema migrate。

# STRICT RULES
- 不 strategy mining / promotion / demotion / retire / reactivate
- 不處理 ARTIFACT_ONLY / CODE_MISSING（V1 不做）
- 不用 fixture 假裝 truth
- 只 apply P3 的 300 rows，不多不少
- 不修改 registry
- apply 前必 snapshot + 驗證 backup 可恢復
- apply 必 transaction、必可 rollback
- 任何 hash / count / schema 不符合 → 立即 rollback 並 abort
- 不 force push、不動 branch protection
- merge order 嚴格 #92 → #93 → #94 → #95，前一個未 green 不可進下一個

# PHASE 0 — Preflight
cd /Users/kelvin/Kelvin-WorkSpace/LotteryNew-clean
git fetch origin && git checkout main && git pull --ff-only
git log --oneline -5
git status --short

對 #92 / #93 / #94 / #95 各跑：
  gh pr view <n> --json number,state,mergeable,mergeStateStatus,title,url
  gh pr checks <n>
  gh pr diff <n> --name-only

任何 PR 出現 *.db / *.sqlite / replay_strategy_registry.py 變更 → abort。

# PHASE 1 — Merge Train (YES-gated, sequential)
按 #92 → #93 → #94 → #95 順序：
  if received "YES merge PR #<n>":
    gh pr merge <n> --squash --delete-branch
    git checkout main && git pull --ff-only
    git log --oneline -3
    git status --short
  else:
    輸出 marker WAITING_FOR_YES_PR<n>_MERGE 並跳到 Phase 2（readiness report only）

# PHASE 2 — Validate P3 Artifacts On Main
驗證以下檔案在當前 main 存在（PR #95 merge 後）：
- outputs/replay/p3_retrospective_candidate_rows_20260513.jsonl
- outputs/replay/p3_retrospective_candidate_summary_20260513.json
- outputs/replay/p3_retrospective_regeneration_dryrun_report_20260513.md
- scripts/p3_retrospective_regeneration_dryrun.py

驗證內容：
- row count == 300
- 6 strategies × 50 rows
- 全部 truth_level == REGENERATED_RETROSPECTIVE
- 全部 dry_run_only == true (artifact 端)
- 全部含 provenance_hash
- 全部 history_window_end < draw_date

任一不符 → abort，輸出 V1_BLOCKED_P3_ARTIFACT_INVALID

# PHASE 3 — DB Snapshot + Restore Test (R4)
1. md5 lottery_api/data/lottery_v2.db → 記錄 hash_before
2. cp lottery_api/data/lottery_v2.db /tmp/lottery_v2.db.snapshot_$(date +%Y%m%d_%H%M%S)
3. md5 snapshot → 必須等於 hash_before
4. cp snapshot 到 /tmp/restore_test.db；sqlite3 簡單 SELECT 確認可讀
5. 紀錄 registry md5 (must stay unchanged through entire round)
產出 outputs/replay/p6_lite_preapply_snapshot_20260513.md

# PHASE 4 — Schema Check (R1)
sqlite3 lottery_api/data/lottery_v2.db ".schema strategy_prediction_replays"
sqlite3 ... "PRAGMA table_info(strategy_prediction_replays);"

必須存在欄位：strategy_id, draw_no, predicted_numbers, actual_numbers, hit_count
檢查是否存在：truth_level, source, provenance_hash, provenance_source,
              controlled_apply_id, dry_run_only

若缺欄位：
  在同一個 transaction 內 ALTER TABLE ADD COLUMN（nullable）
  每個 ALTER 後 PRAGMA 驗證
  記錄 schema_migration_log
  不可在此 phase 寫任何 row

若有 UNIQUE constraint 已涵蓋 (strategy_id, draw_no)：紀錄
若沒有：本輪在 apply script 用 SELECT-then-skip 達成 idempotency，不強行加 UNIQUE
（避免影響既有 460 rows）

產出 outputs/replay/p6_lite_schema_decision_20260513.md

# PHASE 5 — Build Controlled Apply Script (R3, R5)
建立 scripts/p6_lite_apply_retrospective_rows.py，必含：
- --dry-run / --apply / --rollback <controlled_apply_id>
- 讀取 P3 JSONL，validate 每筆 schema
- 產生本次 controlled_apply_id（uuid4 或 timestamp）
- 對每筆 row：
    SELECT 1 FROM strategy_prediction_replays
     WHERE strategy_id=? AND draw_no=? AND truth_level='REGENERATED_RETROSPECTIVE'
    如 exists → skip + log
    否則 INSERT 並覆寫欄位：
      truth_level='REGENERATED_RETROSPECTIVE'
      source='p6_lite_controlled_apply'
      provenance_source='p3_retrospective_dryrun_20260513'
      provenance_hash=原值
      controlled_apply_id=本次 id
      dry_run_only=0 (若該欄存在)
- 全部 INSERT 包在單一 transaction
- 寫 apply log: outputs/replay/p6_lite_apply_log_<controlled_apply_id>.jsonl
- --rollback path: DELETE WHERE controlled_apply_id=? 並回報刪除筆數

# PHASE 6 — Dry-run Apply
python scripts/p6_lite_apply_retrospective_rows.py --dry-run
必須輸出：
- would_insert == 300
- would_skip_existing == 0 (首次)
- invalid_rows == 0
- target_table=strategy_prediction_replays
- per-strategy breakdown 6 × 50
- DB hash unchanged

任一不符 → abort

# PHASE 7 — Apply (YES-gated)
條件：收到 "YES apply P6-lite controlled retrospective rows"
否則停止並輸出 P6_LITE_READY_BUT_AUTHORIZATION_MISSING

若 YES:
  python scripts/p6_lite_apply_retrospective_rows.py --apply
驗證:
- inserted == 300
- DB hash CHANGED
- registry hash UNCHANGED
- SELECT COUNT(*) WHERE truth_level='REGENERATED_RETROSPECTIVE' == 300
- SELECT COUNT(*) per strategy == 50 each (6 strategies)
- 既有 460 rows 不變（SELECT COUNT WHERE truth_level IS NULL OR truth_level='PRODUCTION_REPLAY' == 460）

若任何不符 → 立即執行 rollback Path A，並用 Path B 驗證 DB hash == hash_before

# PHASE 8 — API Contract Verification (R2)
啟動 backend (window.API_BASE 已可用)。
對 6 個 EXECUTABLE_NOW 策略各 curl 一次 replay endpoint。

驗證 response JSON：
- contains rows for the strategy
- 每筆 row 含 predicted_numbers / actual_numbers / hit_count
- 每筆 row 含 truth_level key（值為 REGENERATED_RETROSPECTIVE 或 PRODUCTION_REPLAY）
- row count >= 50（新 row）+ 既有 ONLINE rows

若 API 不回 truth_level：
  輸出 P6_LITE_BLOCKED_API_GAP
  等候 "YES patch API to expose truth_level"
  收到後在同 PR scope 內補最小改動（只加欄位透出，不改 query 邏輯）

# PHASE 9 — UI Browser Smoke
不需要 fetch monkey patch（P78 已上）。
開 http://localhost:8081，window.API_BASE 指向 8002。
驗證：
- 6 個 EXECUTABLE_NOW 策略可展開
- 每個策略展開後可見 50 筆 REGENERATED_RETROSPECTIVE rows + 既有 PRODUCTION_REPLAY rows
- badge 顯示正確（顏色 / 文字區分兩種 truth level）
- ARTIFACT_ONLY 策略沒有被誤顯示成有 rows
- CODE_MISSING 策略保持 tombstone

截圖：outputs/replay/p6_lite_ui_smoke_20260513.png

# PHASE 10 — V1 Closure Report
產出 outputs/replay/p6_lite_controlled_apply_report_20260513.md，必含：
1. V1 目標 + 完成度
2. Root cause（rows 未進可查詢資料層 + PR chain 未 merge）
3. Merge train 結果 (#92~#95)
4. Schema migration（若有）
5. Snapshot + restore test 證據
6. Dry-run / apply / row count 驗證
7. API verification（truth_level 是否暴露）
8. UI smoke screenshot
9. Rollback instructions (Path A SQL + Path B snapshot file path)
10. Hash 驗證（DB before/after、registry unchanged）
11. Remaining gaps：V2 (ARTIFACT_ONLY parser) / V3 (CODE_MISSING tombstone)
12. Next prompt：V2 ARTIFACT_ONLY parser kickoff

# FINAL CLASSIFICATION（擇一）
- V1_CLOSURE_COMPLETE  ← 目標
- V1_MERGE_TRAIN_PARTIAL_<list of merged PRs>
- V1_READY_BUT_AUTHORIZATION_MISSING
- V1_BLOCKED_P3_ARTIFACT_INVALID
- V1_BLOCKED_SCHEMA_GAP
- V1_BLOCKED_API_GAP
- V1_BLOCKED_UI_GAP
- V1_ROLLED_BACK

# FINAL MARKERS
- V1_PHASE0_BASELINE_VERIFIED
- V1_MERGE_TRAIN_PR92_MERGED / WAITING
- V1_MERGE_TRAIN_PR93_MERGED / WAITING
- V1_MERGE_TRAIN_PR94_MERGED / WAITING
- V1_MERGE_TRAIN_PR95_MERGED / WAITING
- V1_P3_ARTIFACT_VALIDATED
- V1_SNAPSHOT_RESTORE_TESTED
- V1_SCHEMA_OK / V1_SCHEMA_MIGRATED
- V1_DRYRUN_APPLY_PASS
- V1_APPLY_COMPLETE_<controlled_apply_id>
- V1_API_TRUTH_LEVEL_VERIFIED / V1_API_PATCH_REQUIRED
- V1_UI_SMOKE_PASS
- V1_DB_HASH_CHANGED_EXPECTED
- V1_REGISTRY_HASH_UNCHANGED
- V1_ROLLBACK_PATH_VERIFIED
```

---

## 5. 給你的一句話

**核准執行。今天的成功定義是：使用者打開頁面，6 個策略每個都能展開看到 50 筆逐期 prediction vs actual，badge 標 `REGENERATED_RETROSPECTIVE`，其餘 10 個策略維持目前 tombstone 顯示。**

不需要再開會、不需要再寫 manifest、不需要再排 P4。**直接用上面這版 prompt 跑，授權序：**

```
YES merge PR #92
YES merge PR #93
YES merge PR #94
YES merge PR #95
YES apply P6-lite controlled retrospective rows
```

（若 Phase 8 撞到 API gap，再加 `YES patch API to expose truth_level`，scope 內收尾，不開新 P。）

V2 / V3 之後再排。今天先把 V1 ship 掉。