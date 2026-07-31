# Replay 頁面顯示語義規格（凍結版）

**文件 ID:** `replay_display_semantics_spec_20260515`
**Document type:** Product Spec - READ ONLY
**日期:** 2026-05-15
**狀態:** AWAITING_CEO_DECISION（三條決策題尚待確認；規格文字已凍結）
**授權來源:** CEO 直派凍結任務；依據 `wiki/system/replay_data_hygiene.md`、`wiki/system/controlled_edge_discovery.md`
**Scope:** 策略歷史回放頁面，涵蓋所有系統開發過的策略（不只 canonical 16）
**Constraint:** Read-only；不寫 DB；不動 code；不做新策略
**PR / candidate ref:** `docs/replay-display-semantics-spec-20260515`

---

## 0. Context

PR #100（replay lifecycle drift guard CI）已合併；candidate 文件記錄 post-merge drift guard 為 PASS。

Candidate 文件同時記錄 spec-freeze baseline：

| Group | Count / Invariant |
|-------|-------------------|
| V1 | 300 |
| V2 | 200 |
| Legacy | 460 |
| Total | 960 |
| V3 tombstone | 6/6 zero rows |

本文件凍結 Replay page 的 display semantics。此文件本身不代表任何 code、DB、strategy、API、UI 或 backend 變更已完成。

**Registry snapshot at spec freeze (2026-05-15):**

| Lifecycle Status | Count in Registry |
|------------------|-------------------|
| ONLINE | 6 |
| REJECTED | 4 |
| RETIRED | 5 |
| OBSERVATION | 1 |
| OFFLINE | 0 |
| **Total canonical** | **16** |
| V3 CODE_MISSING tombstone（zero rows enforced） | 6 |

---

## 一、CEO 前提確認（已決定，不可更改）

| 前提 | 說明 |
|------|------|
| **覆蓋範圍** | 所有系統開發過的策略（canonical 16 + extended rejected/、legacy artifacts），不只 canonical 16 |
| **顯示格式** | 每期 × 每策略 × 預測 vs 實際開獎，與「歷史預測清單」一致 |
| **不偽造 row** | 允許明示三種狀態：「事後重現 (Retrospective)」、「無資料 (No Data)」、「墓碑 (Tombstone)」 |
| **禁止** | 不寫 DB、不動 code、不動策略、不新增或回填 replay rows |

---

## 二、Lifecycle Status × 顯示語義對照表

> 現況資料基礎：
> - ONLINE 6 策略：各 70-90 生產 replay rows（V1 live / regenerated historical；run #1-#7 DONE）
> - REJECTED 4 策略（canonical stubs）+ extended rejected catalog
> - RETIRED 5 策略（canonical stubs；目前 0 生產 rows）
> - OBSERVATION 1 策略（`h6_gate_mk20_ew85`；目前 0 生產 rows in replay store）
> - OFFLINE 0 策略（目前無任何 OFFLINE registered strategy）

### 2.1 ONLINE

> Deployed and active. Currently generating predictions in the replay pipeline.

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | `strategy_prediction_replays` table（DB）。包含 V1 live replay rows；歷史 draw 的 rows 可能帶有 `truth_level = REGENERATED_RETROSPECTIVE`；當期 live rows 需依實際 row provenance 判定 |
| **比對方式** | live / replay diff：以 persisted predicted numbers 對比 `draws` table 實際開獎，每 draw row 顯示 hit count / special hit / miss |
| **UI lifecycle label** | `LIVE` |
| **Row-level trust badge** | 必須依 row provenance / `truth_level` 顯示；只有經確認為 draw-time live prediction 的 row 可標 `LIVE`；`REGENERATED_RETROSPECTIVE` row 必須標 `RETROSPECTIVE` |
| **顯示規則** | 每期逐行顯示預測 vs 開獎；顯示 `coverage_mode`（LIMITED / FULL）；FAILED_LEGACY run 的 error row 顯示 advisory，不隱藏 |
| **禁止** | 不得顯示其他策略 apply batch 的 rows；不得將 `truth_level` 為 retrospective 的 row 標為 `LIVE`；不得混入 V3 tombstone strategy rows；不得顯示「提高中獎率」、「推薦投注」等語言 |

---

### 2.2 OFFLINE

> Previously deployed, now suspended. Prediction generation is paused; existing rows are preserved in DB.

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | `strategy_prediction_replays` table（DB）中下線前已存在的歷史 rows；可能包含 `REGENERATED_RETROSPECTIVE` 或 legacy `NULL` truth_level |
| **比對方式** | frozen historical diff：只對已存 rows 執行 predicted vs actual comparison；新期數不再產生 |
| **UI lifecycle label** | `FROZEN` |
| **Row-level trust badge** | 不得因 lifecycle 為 OFFLINE 而覆蓋 row provenance；若 row truth_level 顯示 retrospective，row badge 仍須反映 retrospective |
| **顯示規則** | 顯示下線前的全部歷史 rows；明示「此策略已暫停（OFFLINE），以下為下線前歷史回放」；不再更新；無 predict-next-draw action |
| **空狀態（0 rows）** | 顯示 tombstone：「此策略已下線，無歷史回放資料」（`NO_DATA` 標籤） |
| **目前現況** | 0 個 OFFLINE 策略；此 spec 為預備定義 |
| **禁止** | 不得為 OFFLINE strategy 產生新 rows；不得將 OFFLINE rows 標為新 live predictions；不得隱藏 `FROZEN` lifecycle 狀態 |

---

### 2.3 REJECTED

> Evaluated during governance review and rejected. Strategy was never deployed to production prediction generation.

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | 組合定義：(a) 已 apply 到 `strategy_prediction_replays` 的 V2 rows（若存在，`truth_level = ARTIFACT_RECONSTRUCTED_RETROSPECTIVE`）；(b) `outputs/replay/v2_artifact_only_candidate_rows_*.jsonl` 作為 provenance / audit artifact，不直接作為 UI source；(c) registry / rejected metadata |
| **比對方式** | retrospective diff；若無 artifact/applied rows 則 N/A |
| **UI trust label** | `RETROSPECTIVE`（有 rows）或 `NO_DATA`（無 rows） |
| **Row-level trust badge** | 每個 artifact reconstructed row 必須顯示 `[RETROSPECTIVE - Artifact Reconstructed]` 或等價明確 badge；不得只靠 section-level badge |
| **顯示規則** | 有 rows 時顯示 table，且每 row 強制標示「事後重現 Retrospective」；tooltip 說明「此預測為 governance 拒絕後事後重現，非上線期間實際預測」；策略卡片標示 REJECTED + 拒絕原因摘要 |
| **0 rows 的 REJECTED 策略** | 顯示 tombstone：「此策略已被拒絕（REJECTED），無回放資料」（`NO_DATA` 標籤）；拒絕原因摘要（如有 `rejected/*.json`） |
| **禁止** | 不得 label artifact rows as live predictions；不得 invoke code generation for rejected strategies；不得新增 rows |
| **決策題 A（未決）** | REJECTED V2 artifact row 是否在 UI row level 強制標註「事後重現 Retrospective」？見第三節 |

---

### 2.4 RETIRED

> Formally retired after lifecycle end. Current canonical retired stubs have 0 production replay rows.

| 欄位 | 定義 |
|------|------|
| **目前資料來源** | tombstone metadata（`replay_strategy_registry.py` lifecycle_stub）；目前 0 生產 replay rows；無 V2 artifact |
| **未來可能資料來源** | 若未來透過另案 governance 合法補填或確認 retired historical rows，資料來源只能是 preserved historical rows in `strategy_prediction_replays`，並須保留 row-level provenance / truth_level |
| **比對方式** | 目前 N/A（無 rows 可比對）；若未來有 preserved rows，僅可做 frozen historical / retrospective diff |
| **UI trust label** | `NO_DATA`（目前 0 rows）或 `FROZEN`（未來有合法 historical rows） |
| **顯示規則（目前狀態）** | tombstone 顯示：策略名稱、退役說明（`provenance_note`）、lifecycle RETIRED badge；不顯示空的預測表格 |
| **未來 rows 顯示規則** | 若 CEO 另案批准補填或展示 historical trajectory，必須明示「This strategy is retired. Data shown is the historical prediction trajectory only.」並顯示 retirement date / reason |
| **禁止** | 不得 generate new rows；不得 label retired rows as `LIVE`；不得隱藏 retirement date / reason；不得以本 spec 當作 backfill 授權 |
| **決策題 B（未決）** | RETIRED 顯示退役前歷史軌跡的策略仍需 CEO 決策；見第三節 |

---

### 2.5 OBSERVATION

> Under shadow evaluation. Results are for research/monitoring and must not be presented as production betting guidance.

| 欄位 | 定義 |
|------|------|
| **預測資料來源** | `live_strategy_predictions` table（DB）或 shadow prediction log（若 available）；目前 `h6_gate_mk20_ew85` 屬 observation / shadow-eval context |
| **比對方式** | 若有 rows，對 persisted prediction rows 與 `draws` table 實際開獎做 diff；若無 rows 則 N/A |
| **UI lifecycle label** | `OBSERVATION` |
| **Row-level trust badge** | `LIVE` 只可用於經確認為 draw-time live monitor 寫入的 row；retrospective/shadow regenerated rows 必須標 `RETROSPECTIVE` 或 `[OBSERVATION - Shadow Evaluation]`；無 rows 時為 `NO_DATA` |
| **顯示規則** | 策略卡片標示 OBSERVATION badge + 說明「此策略處於觀察期，預測僅供研究，不構成投注建議」；若有 rows，逐期顯示並保留 row provenance；若無，見決策題 C |
| **禁止** | 不得宣稱 observation results affect live output；不得把 shadow rows 當成正式 live output；不得隱藏 coverage gaps |
| **決策題 C（未決）** | OBSERVATION 期間若無 prediction row，顯示 "no data" 還是隱藏？見第三節 |

---

### 2.6 Summary Matrix

| Lifecycle | Lifecycle Label | Show Rows | Row Badge | No-Data Behaviour | New Rows Allowed |
|-----------|-----------------|-----------|-----------|-------------------|-----------------|
| ONLINE | `LIVE` | Always when rows exist | `LIVE` only for verified live rows; retrospective truth levels remain `RETROSPECTIVE` | N/A | Only by normal production pipeline, not by this spec |
| OFFLINE | `FROZEN` | Historical persisted rows only | Preserve row provenance | Tombstone + `NO_DATA` if zero rows | No |
| REJECTED | `RETROSPECTIVE` / `NO_DATA` | Conditional on applied artifact rows | Mandatory `[RETROSPECTIVE - Artifact Reconstructed]` | Tombstone + rejection reason | No |
| RETIRED | `NO_DATA` now; `FROZEN` if future legitimate rows exist | Currently no rows; future display requires CEO decision | Preserve row provenance | Tombstone now | No |
| OBSERVATION | `OBSERVATION` / `NO_DATA` | Conditional on shadow/live monitor rows | `OBSERVATION` / `RETROSPECTIVE`; `LIVE` only when row provenance supports it | Show `NO_DATA` placeholder unless CEO decides otherwise | No production rows from this spec |

---

## 三、CEO 決策題（三條）

### 決策題 A：REJECTED V2 artifact row 的 row-level 標註

**問題（<=100 字）：**
REJECTED 策略的 V2 retrospective artifact rows 是否在 UI **每一行**強制標示「事後重現 Retrospective」badge？還是僅在策略卡片層級標示一次即可？

**CTO 建議答案：** 強制 row-level 標註（每 row 都標 `RETROSPECTIVE` / `[RETROSPECTIVE - Artifact Reconstructed]`）。

**CTO 理由：**
V2 rows 是事後重現，不是上線期間的實際預測。若只在卡片或 section 層級標示，使用者在滾動瀏覽長表格或截圖單一 row 時容易誤將 retrospective 結果當成 live 記錄。row-level 標籤成本低，信任邊界收益高。

**風險：**
- 若不標：使用者可能誤讀 V2 rows 為「策略上線時的預測」；信任污染風險 HIGH
- 若標：UI 較擁擠，表格行密度增加；風險 LOW

---

### 決策題 B：RETIRED 顯示退役前最後 N 期預測軌跡

**問題（<=100 字）：**
RETIRED 策略目前 0 生產 replay rows。若未來補填或確認退役前軌跡，UI 應顯示：(a) 全部歷史、(b) 最後 30 期、(c) 只顯示 tombstone？

**Options:**
- A. 顯示全部歷史 rows，預設排序最新在前，加分頁。
- B. 顯示最後 30 期。
- C. 目前只顯示 tombstone（不顯示 rows）。

**Conservative resolution for this spec:** 目前階段採 C，只顯示 tombstone，因為現況是 0 production replay rows，且本 spec 不授權補填。Candidate branch 的 Option A（全部歷史 rows + 分頁）保留為未來若存在合法 preserved rows 時的 CEO decision input；P351C 文件中的「未來優先最後 30 期」亦保留為成本較低的替代方案。

**風險：**
- Tombstone-only：使用者看不到退役前的預測表現；MEDIUM，可接受直到另案補填
- 最後 30 期：需要 V2 retrospective 或 preserved-row 確認工作；工程成本 MEDIUM
- 全部歷史：審計完整性最高，但需要 pagination 與 render budget 控制
- 未經決策直接顯示 rows：可能被誤解為本 spec 已授權 backfill；風險 HIGH

---

### 決策題 C：OBSERVATION 期間無預測 row 的 UI 處理

**問題（<=100 字）：**
OBSERVATION 策略若在某些期次沒有 prediction rows，UI 顯示 "no data" placeholder / 空行，還是完全隱藏這些期次或策略？

**Options:**
- A. 顯示 "no data" placeholder（策略卡片可見，rows 區域顯示提示訊息）。
- B. 隱藏（從列表過濾掉）。

**CTO 建議答案：** Option A，顯示 "no data" placeholder（不隱藏）。

**CTO 理由：**
隱藏缺失期次會讓使用者誤以為策略每期都有預測，無法判斷覆蓋率缺口。OBSERVATION 策略的存在本身即是資訊；顯示 `NO_DATA` placeholder 符合透明原則，也避免 CEO 策略全集盤點缺口。

**風險：**
- 顯示空行：表格密度增加，使用者需理解 "no data" 含義；LOW
- 隱藏：覆蓋率資訊遺失，可能掩蓋 H6 live monitor 或 shadow eval 的紀錄缺失；HIGH

---

## 四、P1 盤點所需的預測資料來源清單

> 此清單供 P1（策略全集盤點）使用，指明需要盤點的資料來源。盤點任務必須另案授權；本 spec 不執行 DB write 或 backfill。

### 4.1 DB Tables（`lottery_api/data/lottery_v2.db`）

| Table | 用途 | 覆蓋 Lifecycle |
|-------|------|----------------|
| `strategy_prediction_replays` | 主 Replay Store；V1 live/regenerated rows + V2 retrospective applied rows + legacy rows | ONLINE、OFFLINE、REJECTED、RETIRED（若未來有合法 rows） |
| `strategy_replay_runs` | Run lineage；status（DONE / FAILED / FAILED_LEGACY / CANCELLED）；coverage metadata | 所有（run provenance） |
| `live_strategy_predictions` | H6 live monitor / observation source（若有 rows） | OBSERVATION |
| `draws` | 實際開獎結果（BIG_LOTTO / DAILY_539 / POWER_LOTTO） | 所有（比對基準） |

**Known DB baseline at spec freeze:**

| Group | controlled_apply_id | truth_level | Count |
|-------|---------------------|-------------|-------|
| V1 | `20260514033100-13acaf34996e` | `REGENERATED_RETROSPECTIVE` | 300 |
| V2 | `20260514134953-cf683424` | `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` | 200 |
| Legacy | NULL | NULL | 460 |
| V3 tombstone | N/A | N/A | 0 (enforced) |

### 4.2 Artifact 路徑（`outputs/replay/`）

| 路徑 | 用途 | 狀態 |
|------|------|------|
| `outputs/replay/v2_artifact_only_candidate_rows_*.jsonl` | V2 retrospective candidate rows（REJECTED canonical stubs；200 rows） | Artifact-only；非 UI source |
| `outputs/replay/p3_retrospective_candidate_rows_20260513.jsonl` | 早期 retrospective candidate（300 rows；已被 V2 取代） | 歸檔參考 |
| `outputs/replay/p1_strategy_lifecycle_inventory_20260511.json` | 策略全集快照（91 candidates；含 lifecycle 分類） | P1 輸入參考 |
| `outputs/replay/strategy_catalog_inventory_20260512.md` | Canonical 16 + extended rejected 盤點 | P1 輸入參考 |
| `outputs/replay/replay_coverage_report_20260507.json` | Coverage report（LIMITED；50-draw window） | Freshness 參考 |
| `outputs/replay/replay_lifecycle_drift_guard_ci_baseline_20260514.json` | Drift guard baseline | P1 / audit 參考 |
| `outputs/replay/replay_lifecycle_drift_guard_ci_validation_20260514.json` | Drift guard validation | P1 / audit 參考 |
| `outputs/replay/replay_lifecycle_drift_guard_post_pr100_20260514.json` | Post PR #100 validation | P1 / audit 參考 |
| `outputs/replay/post_v3_release_completion_summary_20260514.md` | V3 completion summary | P1 / audit 參考 |
| `outputs/replay/p6_lite_preapply_snapshot_20260514.md` | Controlled apply snapshot | P1 / audit 參考 |
| `outputs/relay/` | Existing typo path (`relay` vs `replay`) | Cross-reference only |

### 4.3 策略定義檔案路徑

| 路徑 | 用途 | 覆蓋 Lifecycle |
|------|------|----------------|
| `lottery_api/models/replay_strategy_registry.py` | Canonical 16 adapter + lifecycle_stub 定義；`LIFECYCLE_STATUSES` SSOT | ONLINE、REJECTED、RETIRED、OBSERVATION |
| `rejected/*.json` | Extended rejected 策略定義（governance 正式拒絕記錄） | REJECTED（extended） |
| `lottery_api/data/rejected/*.json` | API 層 rejected 策略 | REJECTED（extended） |
| `strategies/`、`provisional/` | 研究中 / 暫存策略（需 P1 分類後確認 lifecycle） | UNKNOWN（需 P1 確認） |
| `scripts/p1_replay_truth_executable_inventory.py` | Inventory script | P1 參考 |
| `scripts/replay_lifecycle_drift_guard.py` | V3 tombstone list / invariant guard | P1 參考 |

### 4.4 Log 檔位置

| 路徑 | 用途 |
|------|------|
| `logs/` | 系統 runtime logs（含 H6 live monitor 執行記錄） |
| `outputs/replay/p6_lite_apply_log_*.jsonl` | V2 controlled apply log（可追溯哪些 rows 被寫入） |

### 4.5 P1 盤點分母定義

> P1 必須解決的核心問題：「策略全集」的邊界是什麼？

| 分母候選 | 估計數量 | 說明 |
|----------|----------|------|
| Canonical registry（`replay_strategy_registry.py`） | 16 | 目前唯一 SSOT；ONLINE 6 + REJECTED 4 + RETIRED 5 + OBSERVATION 1 |
| Canonical + extended rejected/（去重） | ~85 | canonical 16 + extended rejected catalog（扣除重複） |
| Canonical + rejected/ + strategies/ + provisional/ | TBD（P1 任務） | 需 P1 read-only 掃描確認 |
| 曾產生過 `live_strategy_predictions` rows 的策略 | TBD（P1 DB query） | H6 live monitor 寫入的實際運作策略 |

### 4.6 Repo Strategy File Search Rules

```bash
find lottery_api/ -name "strategy_*.py" -o -name "*_strategy.py"
find scripts/ -name "*strategy*" -o -name "*predict*" -o -name "*replay*"
grep -rn "class.*Strategy\\|def generate_prediction\\|def predict" lottery_api/ --include="*.py"
find . -name "rejected_*.json" -o -name "strategy_catalog*.json" -o -name "*.strategy.json"
find . -name "backtest_*.json" | xargs grep -l "strategy_id" 2>/dev/null
```

---

## 五、信任標籤定義（UI 實作參考）

| 標籤 | 中文 | 說明 | 視覺建議 |
|------|------|------|----------|
| `LIVE` | 即時回放 | 僅限經 row provenance 確認為 draw-time live prediction 的 row | 綠色 badge |
| `RETROSPECTIVE` | 事後重現 | Regenerated 或 artifact reconstructed rows；不得被標成 live | 黃色 badge；必須顯示 tooltip |
| `FROZEN` | 已凍結 | OFFLINE / RETIRED 策略的歷史 rows；不再更新 | 灰色 badge |
| `NO_DATA` | 無資料 | 無任何 replay rows；顯示 tombstone 或 placeholder | 淺灰 badge |
| `OBSERVATION` | 觀察中 | Shadow / observation context；不構成 live output 或投注建議 | 藍灰 badge；需顯示 context |

---

## 六、不允許的 UI 語言（依 `replay_data_hygiene.md §4`）

以下語言在 Replay 頁面中一律禁用：

- `SIGNAL` / `NO_SIGNAL` / `NO_VALIDATED_EDGE`
- "best strategy" / "最佳策略"
- "提高中獎率"
- "推薦投注"
- 任何 promotion / edge ranking 用語
- 任何暗示 retrospective rows 是 draw-time live predictions 的文案

---

## 七、Non-Goals

| Non-Goal | Reason |
|----------|--------|
| Do not add new strategies | Strategy universe is frozen; new strategies require separate governance |
| Do not add / backfill replay rows | DB baseline is locked; this is display semantics only |
| Do not write to DB | Read-only display spec; no persistence changes |
| Do not modify API / routes | No changes to `lottery_api/routes/replay.py` or any backend |
| Do not modify UI / frontend | UI implementation is a separate PR |
| Do not modify `replay_strategy_registry.py` | Registry is frozen for this spec cycle |
| Do not run backtest | No strategy evaluation; this is a display spec |
| Do not label retrospective rows as live predictions | Core integrity rule; violation = spec breach |
| Do not commit `.db` / `.sqlite` / `.pid` / runtime artifacts | Clean repo policy |

---

## 八、Acceptance Criteria

| Criterion | Status |
|-----------|--------|
| All 5 lifecycle statuses have explicit display semantics defined | Defined in section 2 |
| REJECTED semantics are unambiguous (artifact vs live, badge mandatory) | Section 2.3 + decision A |
| RETIRED semantics are conservative for current 0-row state | Section 2.4 + decision B |
| OBSERVATION semantics preserve row provenance and no-data visibility | Section 2.5 + decision C |
| 3 CEO decision questions are written and actionable | Section 3 |
| P1 inventory can start directly from this document | Section 4 |
| No DB diff in this PR | Docs-only change |
| No code diff in this PR | Docs-only change |
| No strategy diff in this PR | Docs-only change |
| Retrospective rows never labeled as live predictions | Enforced in sections 2 and 6 |
| V3 tombstone display rule explicit | Section 9 |

---

## 九、V3 Tombstone Display Rule（Appendix）

V3 CODE_MISSING strategies（6 total）have zero rows in DB by design.

**V3 CODE_MISSING tombstone strategy IDs:**

```text
acb_1bet
acb_markov_midfreq
acb_markov_midfreq_3bet
midfreq_acb_2bet
midfreq_fourier_2bet
h6_gate_mk20_ew85
```

Display rule:

- Do not render a prediction row table for these strategies.
- Render a tombstone card showing:
  - Strategy ID
  - Classification: `CODE_MISSING`
  - Message: "This strategy's implementation code is not available. No prediction rows exist."
  - Trust label: `NO_DATA`
- Any V3 tombstone strategy appearing with DB rows is a `DRIFT_VIOLATION`.

---

## 十、Glossary

| Term | Definition |
|------|------------|
| `LIVE` | Prediction generated at draw time by active strategy code or verified live monitor source |
| `RETROSPECTIVE` | Prediction regenerated or reconstructed after the draw date |
| `FROZEN` | Strategy is inactive; existing rows are read-only |
| `NO_DATA` | No prediction rows exist for this strategy in the relevant period |
| `OBSERVATION` | Strategy is under shadow evaluation or monitoring; not production betting guidance |
| `REGENERATED_RETROSPECTIVE` | V1 truth_level: code re-ran on historical draws retrospectively |
| `ARTIFACT_RECONSTRUCTED_RETROSPECTIVE` | V2 truth_level: reconstructed from saved artifact, no live code run |
| `CODE_MISSING` | V3 classification: strategy code unavailable; zero DB rows enforced |
| Tombstone | Registry entry for a strategy with zero rows; metadata-only display |
| Drift Guard | CI script enforcing DB baseline row counts and V3 zero-row invariant |

---

## 十一、待 CEO 決定後的下一步

| 項目 | 前置條件 | 執行者 |
|------|----------|--------|
| code：row-level `RETROSPECTIVE` badge | 決策題 A 確認 | Frontend |
| code：RETIRED tombstone vs historical rows depth | 決策題 B 確認；另案資料授權 | Replay backend + Frontend |
| code：OBSERVATION no-data placeholder vs hide | 決策題 C 確認 | Frontend |
| P1：策略全集盤點 | 本文件 §4 清單；read-only 授權 | P1 盤點 Agent |
| P3：CEO 驗收 current main replay 頁 | P0 規格凍結（本文件） | CEO |

---

*本文件為 P0 規格凍結輸出。在三條決策題獲得 CEO 答案前，不得啟動對應 code 修改。*
