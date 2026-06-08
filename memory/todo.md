# Project Todo

使用規則：
- 開始任務前標記 `[~]`，完成後標記 `[x]`
- 每個任務附上背景說明與完成標準
- 完成後在底部 **Review** 區段記錄結果

---

## 進行中 (In Progress)

_（目前無進行中任務）_

### P254A–P254B Fetcher repair + governance closure ✅ 2026-06-08 完成
- [x] ACCEPT_BACKFILL_DB_DRIFT_2026_0608 (PR #360): P247G constants updated to 22239/2114, acceptance artifacts created, merged
- [x] P254A fetcher repair (PR #361): 5 modules restored, ADD_ON isdigit fix, 249 tests pass (7 skipped), merged
- [x] P254B governance closure: JSON+MD artifacts, analysis script, tests, governance doc updates committed, PR merged
- [x] memory/lessons.md: L_P254_01–L_P254_03 appended
- No active follow-up unless user requests further ingest UI/monitoring work
- 完成標準：3 PRs merged；artifacts + tests PASS；governance docs updated；no DB write in P254B；no betting advice

### P249B roadmap sync + row label 清理 ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=f1ba0b8=origin/main，P249A merge 可見，active_task=WAITING_FOR_USER_AUTHORIZATION
- [x] 繼續 P249B 分支（從前次中斷繼續）
- [x] 更新 CURRENT_STATE.md：行計數標籤清楚區分 replay rows / draw rows / canonical rows
- [x] 更新 roadmap.md：P246B–P249A arc phase entry + §0.7 bullet + 更新 marker
- [x] 更新 active_task.md：P249B 完成記錄、WAITING_FOR_USER_AUTHORIZATION
- [x] 撰寫 analysis/p249b_roadmap_current_state_row_label_sync.py
- [x] 產出 P249B 文物（JSON+MD）
- [x] 撰寫 tests/test_p249b_roadmap_current_state_row_label_sync.py → 41/41 PASS
- [x] 全套 P248A + P249A + P249B: 137/137 PASS
- [x] 更新 memory/lessons.md（L126）
- 完成標準：標籤清楚；roadmap 同步；41 測試 PASS；無 DB write；無 overclaim

### P249A 後隔離 roadmap triage ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=080f21a=origin/main，P248A merge 可見，active_task=WAITING_FOR_USER_AUTHORIZATION
- [x] 讀取 governance files + 現有研究線狀態
- [x] 確認所有主要研究線關閉/NULL（DAILY_539/POWER_LOTTO/3_4STAR/BIG_LOTTO）
- [x] 發現 CURRENT_STATE "BIG_LOTTO rows | 24,140" = replay rows（非 draw rows）
- [x] 建立 8 個候選任務排名
- [x] 推薦：T1+T2（roadmap.md sync + CURRENT_STATE label fix，Type B doc-only）
- [x] 撰寫 analysis/p249a_post_isolation_roadmap_triage.py
- [x] 產出 P249A 文物（JSON+MD）
- [x] 撰寫 tests/test_p249a_post_isolation_roadmap_triage.py → 43/43 PASS
- [x] 全套 P247G + P248A + P249A: 163/163 PASS
- [x] 更新 memory/lessons.md（L125）
- 完成標準：8 候選任務 + 推薦明確；43 測試 PASS；無 DB write；無 overclaim

### P250A cross-lottery strategy replay inventory ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main 與 origin/main 同步、P249B merge 可見、dirty set 只含已知 tolerated runtime items + `data/lottery_v2.db` metadata-only touch
- [x] 讀取 current registry SSOT + P232A historical scoreboard 快照 + 現況 governance files
- [x] 盤點 38 個 current registry entries，並保留 3 個 POWER_LOTTO artifact-only entries 於歷史 replay/catalog view
- [x] Read-only DB 驗證：integrity ok、replay rows 94,924、draw rows 64,361、BIG_LOTTO canonical 2,113
- [x] 撰寫 analysis/p250a_cross_lottery_strategy_replay_inventory.py
- [x] 產出 P250A 文物（JSON+MD）
- [x] 撰寫 tests/test_p250a_cross_lottery_strategy_replay_inventory.py → 5/5 PASS
- [x] 更新 memory/lessons.md（L127）
- 完成標準：current registry / historical snapshot 分層清楚；41 inventory entries；無 DB write；無策略邏輯變更；無 betting advice

### P251A cross-lottery evidence dashboard dry-run plan ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=dd6f795=origin/main，P250B merge 可見，dirty set 仍只含既有 tolerated runtime items
- [x] 讀取 P250A inventory artifact（current registry SSOT + P232A historical snapshot）
- [x] 建立 dashboard data-contract dry-run plan，包含 global_summary / lottery_summary / badge vocabulary / column contracts / filter semantics / no-exclusion rules / stale snapshot warning / no betting advice / future candidates
- [x] 撰寫 analysis/p251a_cross_lottery_evidence_dashboard_dryrun_plan.py
- [x] 產出 P251A 文物（JSON+MD）
- [x] 撰寫 tests/test_p251a_cross_lottery_evidence_dashboard_dryrun_plan.py → 5/5 PASS
- [x] 交叉回歸 P250A tests → 5/5 PASS
- [x] 更新 memory/lessons.md（L128）
- 完成標準：dashboard contract 清楚區分 current registry vs historical snapshot；artifact-only rows 保持可見；無 DB write；無 UI/API 實作；無 betting advice

### P248A BIG_LOTTO canonical 隔離 governance closure ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=e87dc7b=origin/main，P247G merge 可見
- [x] 讀取 P247G artifact + governance files（CURRENT_STATE.md, active_task.md）
- [x] 確認 17 個 dependency artifacts 全部存在並通過 task_id 驗證
- [x] 建立 p248a-big-lotto-canonical-isolation-governance-closure 分支
- [x] 撰寫 analysis/p248a_big_lotto_canonical_isolation_governance_closure.py
- [x] 產出 P248A 文物（JSON+MD）
- [x] 更新 CURRENT_STATE.md（狀態標記、P246B–P248A completed milestone）
- [x] 更新 active_task.md（P248A 結案記錄、WAITING_FOR_USER_AUTHORIZATION）
- [x] 撰寫 tests/test_p248a_big_lotto_canonical_isolation_governance_closure.py → 53/53 PASS
- [x] 全套 P247E-G + P248A: 209/209 PASS
- [x] 更新 memory/lessons.md（L124）
- 完成標準：17 artifacts 驗證 OK；governance 更新；53 測試 PASS；無 DB write；無 overclaim

### P247G BIG_LOTTO canonical 隔離最終驗證 ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=41f7f58=origin/main，P247F merge 可見
- [x] DB/helper 全驗：view=2113, helper=2113, raw=22238, add_on=19100, integrity=ok
- [x] 15 個 active 路徑掃描：全部 OK（0 regression）
- [x] Raw access 驗：get_all_draws/get_draws 仍存在 database.py
- [x] 建立 p247g-big-lotto-canonical-isolation-final-guard 分支
- [x] 撰寫 analysis/p247g_big_lotto_canonical_isolation_final_guard.py
- [x] 產出 P247G 文物（JSON+MD）
- [x] 撰寫 tests/test_p247g_big_lotto_canonical_isolation_final_guard.py → 67/67 PASS
- [x] 全套 P247B-G: 266/266 PASS
- [x] 更新 memory/lessons.md（L123）
- [x] P247 弧（A→G）完全完成 ✅
- 完成標準：15 路徑全 canonical；regression guard 覆蓋；266 測試 PASS；無 DB write

### P247F BIG_LOTTO 分析工具遷移至 canonical helper ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=f5079f2=origin/main，P247E merge 可見，view=2113/helper=2113
- [x] 掃描 P247D 識別的 FUTURE_SCOPE 工具（9 個：5 analyze_* + 4 audit_*）
- [x] 確認全部 9 工具：研究用途、已使用正確 DB 路徑、只需單行方法替換
- [x] 建立 p247f-big-lotto-analysis-tool-migration 分支
- [x] 修改 9 個工具：get_all_draws('BIG_LOTTO') → get_canonical_draws('BIG_LOTTO')
- [x] 撰寫 analysis/p247f_big_lotto_analysis_tool_migration.py
- [x] 產出 P247F 文物（JSON+MD）
- [x] 撰寫 tests/test_p247f_big_lotto_analysis_tool_migration.py → 49/49 PASS
- [x] 全套 P247B-F: 199/199 PASS
- [x] 更新 memory/lessons.md（L122）
- [x] P247 弧（A→F）全部完成
- 完成標準：9 工具遷移完成；無殘留 raw BIG_LOTTO 呼叫；49 測試 PASS；無 DB write

### P247E get_canonical_draws 採用 DB canonical view ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=24ae45a=origin/main，P247D merge 可見，view=2113 confirmed
- [x] 讀取 database.py：了解現有 SQL+Python 雙層過濾結構
- [x] 建立 p247e-get-canonical-draws-view-adoption 分支
- [x] 更新 database.py：加入 _CANONICAL_VIEW_BIG_LOTTO + _big_lotto_canonical_view_exists() + view 優先路徑 + fallback
- [x] 撰寫 analysis/p247e_get_canonical_draws_view_adoption.py
- [x] 執行驗證：helper_rows=2113, view_path=True, shape_ok, limit_ok, fallback_ok
- [x] 產出 P247E 文物（JSON+MD）
- [x] 撰寫 tests/test_p247e_get_canonical_draws_view_adoption.py → 40/40 PASS
- [x] P246E + P247B/C/D 全部通過（182 總計）
- [x] 更新 memory/lessons.md（L121）
- 完成標準：helper 使用 view；fallback 安全；shape 不變；40 測試 PASS；無 DB write

### P247D BIG_LOTTO canonical view 消費者採用審計 ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=79717d1=origin/main，P247C merge 可見，dirty 僅 runtime files
- [x] 讀取 P247C/B/A 文物確認 view 已存在
- [x] 建立 p247d-big-lotto-canonical-view-consumer-adoption-audit 分支
- [x] 掃描 draws_big_lotto_canonical_main / get_canonical_draws / get_all_draws 使用者
- [x] 分類 21 個消費者路徑（3 VIEW_BACKED / 4 HELPER_CANONICAL / 1 KEEP_HELPER / 3 RAW / 7 FUTURE_SCOPE / 3 NOT_AFFECTED）
- [x] Read-only DB 驗證：view=2113, raw=22238, add_on=19100, integrity=ok
- [x] 撰寫 analysis/p247d_big_lotto_canonical_view_consumer_adoption_audit.py
- [x] 產出 P247D 文物（JSON+MD）
- [x] 撰寫 tests/test_p247d_big_lotto_canonical_view_consumer_adoption_audit.py → 41/41 PASS
- [x] P247A/B/C 全部通過（97/97）；總 P247 套件：138 測試全 PASS
- [x] 更新 memory/lessons.md（L120）
- 完成標準：採用審計文物完整；所有測試通過；無 DB write；無策略/生產修改

### P247C BIG_LOTTO view 後置核對與 dry-run 測試清理 ✅ 2026-06-06 完成
- [x] Phase 0 驗證：main=b47b9c2=origin/main，P247B merge 可見，dirty 僅 runtime files
- [x] 讀取 P247B/P247A 文物：確認 view_created=True, counts 全部正確
- [x] 建立 p247c-big-lotto-view-post-apply-reconciliation 分支
- [x] 撰寫 analysis/p247c_big_lotto_view_post_apply_reconciliation.py（read-only）
- [x] 執行分析：view=2113, raw=22238, add_on=19100, integrity=ok, all_checks=True
- [x] 修正 test_p247a_canonical_view_not_in_db → test_p247a_canonical_view_not_applied_by_p247a（artifact 驗證取代 live DB 查詢）
- [x] 產出 P247C 文物（JSON+MD）
- [x] 撰寫 tests/test_p247c_big_lotto_view_post_apply_reconciliation.py → 38/38 PASS
- [x] P247A 測試：28/28 PASS（無舊 failure）；P247B: 31/31 PASS；P246K: 33/33 PASS
- [x] 更新 memory/lessons.md（L119）
- 完成標準：所有 P247A/B/C 測試通過；無 DB write；read-only 核對正確

### P247B BIG_LOTTO canonical view 正式建立 ✅ 2026-06-06 完成
- [x] 確認 PR #327 (P247A) CI PASS (SUCCESS)，合併至 main；385/1skipped 通過
- [x] 讀取 P247A JSON 文物：確認 proposed SQL, counts, json1_available=True
- [x] Phase 0 驗證：branch=main, HEAD=d6eb331, dirty 僅 known runtime files
- [x] 建立 p247b-apply-big-lotto-canonical-view 分支
- [x] 撰寫 scripts/p247b_apply_big_lotto_canonical_view.py（dry-run + apply 模式）
- [x] Dry-run 驗證：所有 pre-apply 條件通過（raw=22238, add_on=19100, canon=2113, json1=True）
- [x] 建立 DB backup: p247b_lottery_v2_backup_20260606_113816.db + SHA256 ✅
- [x] 執行 CREATE VIEW draws_big_lotto_canonical_main → view 成功建立
- [x] Post-apply 驗證：view=2113, raw=22238, add_on=19100, integrity=ok, 無 hyphen/date-fmt/small-pool
- [x] 產出 P247B 文物（JSON+MD）
- [x] 撰寫 tests/test_p247b_apply_big_lotto_canonical_view.py → 31/31 PASS
- [x] 更新 memory/lessons.md（L118）
- 完成標準：VIEW 已建立；所有計數正確；raw rows 保留；DB integrity ok；31 測試 PASS

### P247A BIG_LOTTO DB 級正規分離 dry-run 計畫 ✅ 2026-06-06 完成
- [x] 確認 PR #326 (P246K) CI PASS，合併至 main；357+1skipped 通過
- [x] 讀取 DB read-only：確認全部計數正確（22238/19100/375/650/2113）
- [x] 確認 JSON1/json_each 可用：可在 VIEW 中直接過濾 SMALL_POOL_ALIEN
- [x] Dry-run proposed canonical view SQL：返回 2,113 ✅
- [x] 確認 VIEW 和 annotation table 未在 DB 中建立（dry-run only）
- [x] 產出 P247A 文物（JSON+MD）+ 測試 385+1skipped PASS
- [x] 更新 memory/lessons.md（L117）
- 完成標準：dry-run 計畫已驗證；SQL 未執行；Type D 需另行授權

### P246K 大樂透正規族群 NIST 重新審計 ✅ 2026-06-06 完成
- [x] 確認 PR #325 (P246J) CI PASS，合併至 main；324/324 通過
- [x] 以 get_canonical_draws("BIG_LOTTO") 載入 2,113 筆正規主開獎
- [x] 驗證排除規則：hyphen=0, date_fmt=0, small_pool=0, all max>25 ✅
- [x] 執行 5 項隨機性測試：全部 GREEN（p 均 > 0.05）
- [x] 結論：P238B YELLOW 係混合族群假訊號；正規族群與公平隨機 6/49 相容
- [x] 測試 357/1-SKIPPED；產出 P246K 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L116）
- 完成標準：正規族群 GREEN 已確認；無 DB 寫入；預測/策略無授權；GATE_RED 維持

### P246J BIG_LOTTO 加碼隔離弧結案 ✅ 2026-06-06 完成
- [x] 確認 PR #324 (P246I) CI PASS，合併至 main；288/288 通過
- [x] 確認 6 個生產研究路徑已 canonical 化（source 驗證全 PASS）
- [x] 撰寫 P246B-I 完整時間軸摘要
- [x] 記錄剩餘風險（無 DB-level canonical view；archived scripts；GATE_RED 維持）
- [x] 建議後續：P246K 正規族群 NIST 重新審計（無需 Type D）
- [x] 測試 324/324 PASS；產出 P246J 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L115）
- 完成標準：P246 弧已結案；加碼記錄隔離確認；GATE_RED 維持；無 DB 寫入

### P246I BIG_LOTTO 人口斷言清理 ✅ 2026-06-06 完成
- [x] 確認 PR #323 (P246H) CI PASS，合併至 main；258/258 通過
- [x] 掃描 22238/sample_size 相關測試/文物
- [x] test_p238b:146 加 P246I inline comment（斷言值保留 >= 22238）
- [x] test_p243a:58 加 P246I inline comment（sample_size=22238 歷史值保留）
- [x] P238B NIST 文物不修改（YELLOW 歷史結果保留）
- [x] 測試 288/288 PASS；產出 P246I 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L114）
- 完成標準：raw (22238) vs canonical (2113) 已明確區分；斷言值未改；無 DB 寫入

### P246H advanced_learning scheduler 追蹤 ✅ 2026-06-05 完成
- [x] 確認 PR #322 (P246G) CI PASS，合併至 main；229/229 通過
- [x] 追蹤 scheduler.get_data() 完整呼叫鏈：advanced_learning → scheduler → data_by_type
- [x] 找到根因：optimization.py:90 get_all_draws() 無過濾，22,238 筆進入快取
- [x] 在 scheduler.get_data() 消費點套用 canonical filter（非破壞性）
- [x] advanced_learning.py 呼叫端自動受益，無需修改 advanced_learning 本身
- [x] 測試 258/258 PASS；產出 P246H 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L113）
- 完成標準：P246E-H 共 6 個確認研究呼叫端已 canonical 化；無 DB 寫入

### P246G 剩餘 BIG_LOTTO 研究呼叫端 canonical 化 ✅ 2026-06-05 完成
- [x] 確認 PR #321 (P246F) CI PASS，合併至 main；199/199 通過
- [x] 更新 drift_detector._load_draws()：BIG_LOTTO 直接 SQL + Python 後置過濾（P246G）
- [x] 更新 backtest_framework.BacktestEngine.backtest()：get_canonical_draws()（P246G）
- [x] 延後 advanced_learning.py（scheduler.get_data() 路徑不透明）
- [x] 延後 60+ 歷史腳本（非即時生產路徑）
- [x] 測試 229/229 PASS；產出 P246G 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L112）
- 完成標準：5 個確認研究呼叫端已 canonical 化（P246E+F+G）；無 DB 寫入

### P246F BIG_LOTTO 研究呼叫端 canonical 化掃描 ✅ 2026-06-05 完成
- [x] 確認 PR #320 (P246E) CI PASS，合併至 main
- [x] 掃描 get_all_draws/get_canonical_draws 全呼叫端並分類
- [x] 更新 tools/rsm_bootstrap.py:118 → get_canonical_draws()（P246F）
- [x] 更新 lottery_api/engine/core_satellite.py:373 → get_canonical_draws()（P246F）
- [x] 確認 drift_detector、advanced_learning、backtest_framework 延後至 P246G
- [x] 測試 199/199 PASS；產出 P246F 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L111）
- 完成標準：3 個確認研究呼叫端已 canonical 化；加碼記錄 raw 存取保留；無 DB 寫入

### P246E BIG_LOTTO canonical draw helper 實作 ✅ 2026-06-05 完成
- [x] 確認 PR #319 (P246D) CI PASS，合併至 main
- [x] 在 database.py 新增 get_canonical_draws()：三層過濾（SQL×2 + Python×1）
- [x] canonical=2113，raw=22238，ADD_ON 19,100 筆保留在 DB
- [x] 更新 quick_predict.py load_history() 使用 get_canonical_draws()
- [x] 非 BIG_LOTTO 類型通過 (POWER_LOTTO、DAILY_539 count 不變)
- [x] 測試 165/165 PASS；產出 P246E 文物（JSON+MD）
- [x] 更新 memory/lessons.md（L110）
- 完成標準：isolation checks all pass；無 DB 寫入；加碼記錄 raw 存取保留

### P246D BIG_LOTTO 加碼記錄隔離設計 ✅ 2026-06-05 完成
- [x] 確認 PR #318 (P246C) CI PASS，合併至 main
- [x] 讀取 DB read-only：確認無 canonical view，共 22,238 筆 BIG_LOTTO
- [x] 評估 5 個隔離選項（OPT-A/B/C/D/E）；拒絕直接刪除（OPT-E）
- [x] 推薦四階段隔離路徑：Phase 1 code helper（無 DB 寫入）→ Phase 2 SQL view → Phase 3 annotation table → Phase 4 re-validate
- [x] 確認 Phase 1 立即可實作：新增 get_canonical_draws()，filter draw NOT LIKE '%-%'
- [x] 確認 quick_predict.py:169 是 Phase 1 首要更新目標
- [x] 產出 P246D 文物（JSON+MD）+ 測試 45/45 PASS（全 133 PASS）
- [x] 更新 memory/lessons.md（L109）
- 完成標準：隔離設計已明確；保留加碼記錄；P247 apply 仍需 Type D 授權

### P246C BIG_LOTTO 加碼記錄影響範圍審計 ✅ 2026-06-05 完成
- [x] 確認 PR #317 (P246B) CI PASS，合併至 main
- [x] 掃描全 repo：database.py get_all_draws/get_draws 無 canonical filter（DIRECTLY_AFFECTED）
- [x] 確認 P219 已正確過濾（draw NOT LIKE '%-%'）→ NOT_AFFECTED
- [x] 確認 P238B NIST 文物以 sample_size=22238 建立（含加碼記錄）→ DIRECTLY_AFFECTED
- [x] 發現 2 個測試硬編碼 22238（P238B test + P243A fixture）→ 隔離後需更新
- [x] 產出 P246C 文物（JSON+MD）+ 測試 41/41 PASS
- [x] 更新 memory/todo.md + lessons.md
- 完成標準：影響範圍已記錄；無 DB 寫入；P247 apply 仍需 Type D 授權

### P246B BIG_LOTTO 分類修正 ✅ 2026-06-05 完成
- [x] 修正 P246 SIM_HYPHEN 標籤 → ADD_ON_PRIZE_EXCLUDED
- [x] 確認 19,100 筆連字號列為加碼/特別獎記錄，非偽造資料
- [x] 產出 P246B 分類修正文物（JSON+MD）
- [x] 產出 P247 修正版排除計畫文物（JSON+MD，計畫 only，無 DB 寫入）
- [x] 測試 47/47 PASS
- [x] 更新 memory/lessons.md（L107）
- 完成標準：修正文物在 main 上；BIG_LOTTO 研究 gate 維持封鎖；不含 DB 寫入

### P219 外部10法診斷掃描 ✅ 2026-06-05 完成（predictive-NULL）
- [x] 背景：用戶（cost-no-object）授權跑全部10類外部方法，目標提高預測成功率
- [x] Pre-register（P221F gate）：`outputs/research/p219_..._plan_20260605.md`
- [x] 鎖定 clean distinct-real-draw 宇宙（BIG_LOTTO 排除 19,100 模擬列）
- [x] 實作 read-only 引擎（pure stdlib, MC/permutation nulls）：`analysis/p219_external_method_diagnostic_sweep.py`
- [x] 跑 10 families × 5 games = 44 tests，Bonferroni+BH 校正
- [x] 測試 10/10 PASS（假陽性控制 + 注入偏差功率 + 校正單調性 + 可重現 + 模擬列排除）
- [x] 裁決：predictive 家族全 NULL；唯一 corrected-sig 全為 BIG_LOTTO 資料污染 artifact
- [x] 完成標準：predictive-NULL 證明 + 資料污染根因（≥3 來源）+ feature-bottleneck report

---

## 待辦 Backlog

### 策略研究

- [x] **每日539策略驗證** ✅ 2026-02-25 完成
  - 首個通過三窗口驗證策略: `5bet_fourier4_cold` (PROVISIONAL)
  - 1500p Edge +1.35% (z=2.4), Permutation p=0.030 (SIGNAL_DETECTED)
  - 腳本: `tools/predict_539_5bet_f4cold.py`
  - **⚠️ 下次驗證: 5992期 (再200期後)**

- [ ] **大樂透 RSM 持續監控**
  - `data/rolling_monitor_BIG_LOTTO.json` 需定期更新（下次建議每100期）
  - 監控重點：ts3_markov_freq_5bet_w30 的 100p Edge(+0.04%) 是否回升

- [ ] **威力彩 RSM 持續監控**
  - `data/rolling_monitor_POWER_LOTTO.json` 需定期更新
  - 監控重點：fourier_rhythm_3bet ACCELERATING(z=+2.18) 是否持續或回歸；orthogonal_5bet 30p(-1.24%) 是否改善

- [ ] **大樂透 6注策略研究**
  - 目前最佳：5注 Edge +1.97%
  - 研究第6注是否可用「殘餘號碼按Zone平衡」填補

- [ ] **威力彩 4注策略**
  - 目前 3注 PP3 Edge +2.30%，5注正交 +3.53%
  - 4注是否存在有效組合？

### 系統建設

- [x] **建立策略生命週期文件夾**
  - 依 CLAUDE.md 規範建立 `strategies/` 目錄
  - 每個採納策略需有 `strategy.yaml` + `backtest_report.md`

- [ ] **rejected/ 重測條件觸發機制**
  - 定期（每100期新資料）掃描 rejected/*.json 的 `retest_conditions`
  - 確認是否有策略達到重測門檻

- [ ] **自動 Permutation Test 整合**
  - 目前 P3 shuffle test 是手動執行
  - 考慮整合至回測腳本，新策略自動跑200次shuffle

- [ ] **Sharpe Ratio 計算整合**
  - CLAUDE.md 要求 Sharpe Ratio > 0 才標記為有效
  - 目前回測腳本尚未輸出 Sharpe Ratio

### 文件補完

- [ ] **更新 lottery_api/CLAUDE.md 策略評分**
  - 已有 Edge 數據，但缺少 Stability / Significance / Complexity 欄位
  - 補充 Score 公式計算結果

- [x] **建立 strategies/ 目錄**
  - 為現有採納策略補充 strategy.yaml（Idea 階段文件）
  - **補齊 sim_result.json + performance_log.json (2026-02-24)**
    - 8策略 × 2文件 = 16個文件全部完成
  - **RSM 掃描補齊三個 PENDING 策略 (2026-02-24)**
    - BL 4注: STABLE z=+0.06，三窗口全正(+2.75/+1.75/+2.42%)
    - BL 5注: STABLE z=-0.22，(+1.04/+0.04/+2.37%)
    - PL 5注: STABLE z=-0.60，(-1.24/+3.09/+3.42%)

- [x] **補齊 2注策略 backtest_report.md**
  - big_lotto/2bet_fourier_rhythm, 2bet_deviation_complement
  - power_lotto/2bet_fourier_rhythm

- [x] **建立 research_plan_template.md**
  - 路徑：`memory/research_plan_template.md`
  - 新研究開始前複製使用

---

## 已完成 (Done)

### Workflow 基礎建設 (2026-02-24)
- [x] 建立根目錄 `CLAUDE.md`（策略生命週期、評分公式、驗證標準）
- [x] 建立 `rejected/` 目錄 + 12個已拒絕策略歸檔
- [x] 建立 `memory/lessons.md`（22條教訓）
- [x] 建立 `memory/todo.md`（本檔）
- [x] 建立 `strategies/` 目錄（8個採納策略完整生命週期文件）

### 1500期全面驗證 (2026-02-10)
- [x] 大樂透 8策略 × 3窗口驗證完成
- [x] 採納：Fourier Rhythm 2注、Triple Strike v2 3注、TS3+Markov(w=30) 4注、5注正交
- [x] 拒絕：Cluster Pivot、Cold Complement、Markov單注、Fourier30+Markov30

### P3 Permutation Test (2026-02-18)
- [x] 大樂透 5注 BL TS3+M4+FO：p=0.030, Cohen's d=2.13 ✅ SIGNAL DETECTED
- [x] 威力彩 PP3 3注：p=0.015, Cohen's d=2.18 ✅ SIGNAL DETECTED

### Gemini 2-bet 聯合驗證 (2026-02-24 結案)
- [x] Phase 13-17 驗證完成（commit d3df866）
- [x] Merge verify-gemini-2bet → main（commit ce7c10f）
- [x] 刪除分支 verify-gemini-2bet

### Gemini 協作驗證架構 (2026-01-26)
- [x] 建立 `.claude/gemini_collaboration_protocol.md`
- [x] 確立 Gemini 策略必須 Claude 獨立驗證規則

---

## Review 區段

> 每個任務完成後在此記錄：結果摘要、遇到的問題、後續影響

### 2026-06-05 — P219 外部10法診斷掃描（predictive-NULL + 資料污染發現）
- 結果：10 families × 5 games = 44 multiplicity-corrected tests。**forward-predictive 家族（M5/M8/M9）在所有遊戲全 NULL**（最佳 +0.49pp p=0.226 在污染資料上）。MI≈0，無 exploitable edge。再確認 L82/L91/P178A/P236A。
- 唯一 corrected-significant：全在 BIG_LOTTO（M1/M2/M3/M4/M6）+ 弱 539:M3（BH-only Bonferroni-FAIL）。
- 根因（裁決）：**非彩票偏差，而是 BIG_LOTTO `draws` 表資料污染** — 22,238 列僅 ~2,113 為真 6/49（19,100 模擬 + 375 date-format 異種 + 650 小池異種）。drift/changepoint 偵測到的是「資料管線斷點」，anomaly≠predictor。
- 問題：BIG_LOTTO raw `draws` 會污染任何分析；統計單位必須 = distinct real 6/49。
- 影響：(1) 用戶目標「提高預測成功率」= 無外部方法可達（fair-random）；(2) **flag 資料完整性任務**（read-only audit + quarantine plan，需另開 Type B/D，不在本任務改 DB）；(3) 教訓 L_P219_A/B/C 入 lessons.md。
- 產出：`analysis/p219_external_method_diagnostic_sweep.py`, `outputs/research/p219_..._{plan_,}20260605.{md,json}`, `tests/test_p219_..._sweep.py`（10/10 PASS）。

### 2026-02-24 — Workflow 基礎建設
- 結果：CLAUDE.md + rejected/ + memory/ + strategies/ 四件套建立完成
- 問題：`tasks/` 路徑不符合專案結構，已改為 `memory/`
- 影響：後續所有教訓追蹤統一寫入 `memory/lessons.md`

### 2026-02-24 — strategies/ 生命週期文件全部補完
- 結果：8策略 × 6文件 = 48個文件全部就位（含 sim_result.json + performance_log.json）
- RSM 掃描（2026-02-24，BIG_LOTTO 2105期 / POWER_LOTTO 1887期）：
  - BL 4注 ts3_markov_4bet_w30: **STABLE** 三窗口全正 (+2.75/+1.75/+2.42%) z=+0.06
  - BL 5注 ts3_markov_freq_5bet_w30: **STABLE** (+1.04/+0.04/+2.37%) z=-0.22，100p近中性需持續觀察
  - PL 5注 orthogonal_5bet: **STABLE** (-1.24/+3.09/+3.42%) z=-0.60，30p短暫負Edge屬正常波動
- 同步更新：BASELINES 支援4/5注、rsm_bootstrap.py 加入三個新策略

### 2026-06-05 — P245B 偏差閘門層設計（corrected, builds on P237C/P238B/P219）
- 結果：P245B 確立 sequential e-value + BOCD + 多重校正 + 資料完整性 閘門設計。P245A 缺席確認，不依賴。當前閘門：DAILY_539/POWER/3_STAR/4_STAR = YELLOW；BIG_LOTTO = GATE_RED_DATA_CONTAMINATION。GATE_OPEN 8 條件無一達成。24/24 tests PASS。
- 影響：偏差研究重啟有清晰、可審計的門檻；anomaly≠prediction 強制語言；BIG_LOTTO 資料清理仍需另開 Type D 授權。
- 產出：outputs/research/p245b_bias_gate_layer_20260605.{md,json}, tests/test_p245b_bias_gate_layer.py。

### 2026-06-05 — P246 BIG_LOTTO Data-Integrity Audit (GATE_RED confirmed, quarantine plan produced)
- 結果：22,238 rows = 2,113 canonical + 20,125 contaminated (90.5%). 三個污染家族：SIM_HYPHEN 19,100 / DATE_FORMAT_ALIEN 375 / SMALL_POOL_ALIEN 650（主要 P219 信號來源）。全部 P219 BIG_LOTTO corrected-significant signals 已解釋為資料污染。23/23 tests PASS。
- 影響：GATE_RED_DATA_CONTAMINATION 維持不變。Type D 授權 + 執行 quarantine + re-audit 方可升門。不授權任何策略/預測/生產推薦。
- 產出：analysis/p246_…py, outputs/research/p246_…20260605.{md,json}, tests/test_p246_….py。

### 2026-06-06 — P251C evidence dashboard API payload contract plan
- 已規劃 future-only read-only API payload contract，建議 endpoint 為 `/api/replay/evidence-dashboard`，與現有 replay audit 命名一致。
- P251C 維持 no route / no UI / no DB write / no registry mutation / no strategy promotion / no betting advice。
- 提醒：artifact tests 可能會 rewrite 既有 P251A/P251B markdown timestamp，完成後要 restore 再做 diff-check。

### 2026-06-06 — P251D evidence dashboard read-only API route
- 已在 replay router 實作 `GET /api/replay/evidence-dashboard`，直接回傳 P251B published artifact。
- 路由維持 read-only：no DB query, no registry mutation, no strategy promotion, no UI, no betting advice。
- 測試採 direct-call async route pattern，避免 app startup / scheduler / DB side effects。

### 2026-06-06 — P251E evidence dashboard API runtime smoke + governance closure
- 已完成 app/TestClient smoke，確認 `GET /api/replay/evidence-dashboard` 在 live app/router 上回傳 HTTP 200，且 payload 與 P251B published artifact 完全一致。
- 已完成 P251A–P251E dashboard API arc 治理收尾；後續若有新 dashboard 工作，應以現有 read-only artifact-backed route 為基礎，而不是重開 DB-backed 路徑。

### P255A–P255D Ingest Write Guard Arc ✅ 2026-06-08 完成
- [x] P255A (PR #363): Ingest/backfill safety audit — 5 write-capable paths, 8 guardrails recommended
- [x] P255B (PR #364): G01–G08 design specifications documented
- [x] P255C (PR #365): G01+G02 implemented in lottery_api/routes/ingest.py; 42 tests pass
- [x] P255D: Runtime smoke (8 cases PASS) + governance closure; DB baseline 22,239/2,114 confirmed
- Deferred G03–G08 (UI modal, audit log, SHA backup, idempotency, CORS, env gate): requires explicit authorization for P255E+
- 完成標準：G01/G02 live + smoke-tested; DB unchanged; arc closed; no DB write; no strategy promotion
