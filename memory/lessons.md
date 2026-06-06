# Lessons Learned

按主題分類，來源為歷次策略失敗與驗證結果。
每次用戶指正或策略拒絕後更新此檔。

---

## L114 — P246I 測試/文物人口斷言清理規則 (2026-06-06)

**來源：** P246I 清理

**規則：** 測試斷言中 `>= 22238` 反映的是 BIG_LOTTO 原始 DB 總列數（含加碼記錄），NOT 正規研究族群 (~2,113)。
兩者必須明確區分。修改方式：加 inline comment，不改斷言值（目前 DB 仍含 22,238 筆）。

**斷言政策：**
- 測試原始 DB 列數：`>= 22238` + 「raw total including add-on」注解
- 測試正規研究族群：`>= 2100 and <= 2200`（或驗證後 == 2113）
- 歷史文物：保留原始值，加 P246I 注解，在 P246I 報告中記錄修訂說明

**P238B 後續：** P238B NIST 審計在 22,238 筆混合族群執行，結果仍為 YELLOW OBSERVATION_ONLY。
正規族群重新審計（~2,113 筆）需在 P247 Type D 後另行授權。

---

## L113 — P246H 排程器快取的 canonical 化模式 (2026-06-05)

**來源：** P246H advanced_learning scheduler 追蹤

**關鍵發現：**
- `scheduler.get_data(lottery_type)` 是所有進階學習/優化路由的資料消費點
- `scheduler.data_by_type['BIG_LOTTO']` 由 `optimization.py:90` 的 `db.get_all_draws()` 填入（22,238 筆，含加碼記錄）
- `advanced_learning.py` 本身無 DB 匯入；以 scheduler 參數接收資料

**修正模式：在消費點（get_data）套用 canonical filter，而非修改資料填入端**
```python
def get_data(self, lottery_type: str) -> list:
    data = self.data_by_type.get(lottery_type, [])
    if lottery_type == 'BIG_LOTTO':
        # filter at return time — non-destructive
        return [d for d in data
                if '-' not in str(d.get('draw',''))
                and not (len(str(d.get('draw',''))) == 8 and str(d.get('draw','')).startswith('20'))
                and (not d.get('numbers') or max(d['numbers']) > 25)]
    return data
```

**優點：** 非破壞性（原始快取保留）、所有 get_data() 呼叫端自動受益

**P246E-H 總計：** 6 個確認研究呼叫端已完成 canonical 化

---

## L112 — P246G 直接 SQL 路徑的 canonical 化方式 (2026-06-05)

**來源：** P246G 剩餘研究呼叫端處理

**結論：** `drift_detector._load_draws()` 使用直接 SQLite（非 DatabaseManager），無法直接呼叫 `get_canonical_draws()`。正確做法：在 SQL 中加入 BIG_LOTTO 分支，附加 `AND draw NOT LIKE '%-%' AND NOT (LENGTH(draw)=8 AND draw LIKE '20%')`，加上 Python 後置過濾 `max(parsed) > 25`。

**5 個確認研究呼叫端已完成 canonical 化（P246E–G）：**
1. `tools/quick_predict.py:169`（P246E）
2. `tools/rsm_bootstrap.py:118`（P246F）
3. `lottery_api/engine/core_satellite.py:373`（P246F）
4. `lottery_api/engine/drift_detector._load_draws()`（P246G）
5. `lottery_api/backtest_framework.BacktestEngine.backtest():69`（P246G）

**仍延後：** `advanced_learning.py` scheduler.get_data() 路徑需獨立追蹤；60+ 歷史腳本非即時生產路徑

---

## L111 — P246F 研究呼叫端 canonical 化掃描要點 (2026-06-05)

**來源：** P246F 研究呼叫端掃描

**結論：** 已完成 3 個確認研究/策略呼叫端的 canonical 化：
1. `tools/quick_predict.py:169`（P246E）
2. `tools/rsm_bootstrap.py:118`（P246F）— RSM 策略 bootstrap，直接餵入 RollingStrategyMonitor
3. `lottery_api/engine/core_satellite.py:373`（P246F）— 從歷史生成策略注數

**仍需後續處理（P246G）：**
- `lottery_api/engine/drift_detector._load_draws()` — 使用直接 SQLite，非 DatabaseManager，需獨立修改 SQL
- `lottery_api/routes/advanced_learning.py` — scheduler.get_data() 路徑尚未追蹤
- `lottery_api/backtest_framework.py` + 60+ 歷史/探索腳本 — 批量掃描超出最小範圍

**重要：**
- `get_all_draws()` 和 `get_draws()` 保持不變（展示/歷史用途合法）
- 任何新 BIG_LOTTO 研究呼叫端都必須使用 `get_canonical_draws()` 而非 `get_all_draws()`

---

## L110 — P246E get_canonical_draws() 實作要點 (2026-06-05)

**來源：** P246E Phase 1 實作

**結論：** `database.py` 新增 `get_canonical_draws()` helper，BIG_LOTTO 三層過濾：
1. SQL: `draw NOT LIKE '%-%'`（排除 ADD_ON_PRIZE_EXCLUDED，19,100 筆）
2. SQL: `NOT (LENGTH(draw)=8 AND draw LIKE '20%')`（排除 DATE_FORMAT_ALIEN，375 筆）
3. Python: `max(numbers) > 25`（排除 SMALL_POOL_ALIEN，~650 筆）
結果：canonical 2,113 筆（與預期完全一致）。

**注意事項：**
- 非 BIG_LOTTO 類型使用直接 `lottery_type=?` 查詢，**不呼叫** `get_related_lottery_types()`，避免觸發 `apscheduler` 重量級匯入
- `get_all_draws()` 和 `get_draws()` **不修改**，繼續傳回全 22,238 筆（展示/歷史用途）
- `quick_predict.py` `load_history()` 改為呼叫 `get_canonical_draws()`
- Phase 2（DB View）和 Phase 3（Annotation Table）仍需 Type D 授權

---

## L109 — P246D BIG_LOTTO 加碼記錄隔離設計原則 (2026-06-05)

**來源：** P246D 隔離設計

**結論：** 隔離 BIG_LOTTO 加碼記錄的正確方式是過濾（filter/view），而非刪除。
P219 的 `draw NOT LIKE '%-%'` filter 是已驗證的黃金標準。資料庫目前無任何 canonical view，需新增。

**正確隔離路徑（分四階段）：**
1. **Phase 1（無需 DB 寫入）**: 在 `database.py` 新增 `get_canonical_draws()` helper，過濾 BIG_LOTTO 的加碼記錄（draw NOT LIKE '%-%' 且非 DATE_FORMAT_ALIEN）。更新研究/策略/回放呼叫端（key: `quick_predict.py:169`）。
2. **Phase 2（Type D）**: 建立 `draws_big_lotto_canonical_main` SQL view
3. **Phase 3（Type D）**: 建立 `draw_row_family_annotations` 標記表，Python 驅動偵測 SMALL_POOL_ALIEN（max(numbers)<=25）
4. **Phase 4**: 重新執行受影響文物/測試（P238B NIST、test_p238b >= 22238 → >= 2113）

**關鍵規則：**
- ADD_ON_PRIZE_EXCLUDED 列必須保留，任何 DELETE 操作均被拒絕
- 展示/歷史 API（`get_draws`、`get_all_draws`）可傳回全部記錄，但須標示加碼記錄類型
- `SMALL_POOL_ALIEN` 無法單靠 SQL 過濾，需 Python 判斷 max(numbers)>25

---

## L108 — P246C database.py 無 canonical filter 傳回混合族群 (2026-06-05)

**來源：** P246C 影響範圍審計

**結論：** `lottery_api/database.py` 的 `get_all_draws()` 與 `get_draws()` 以 `lottery_type IN (...)` 查詢，**不過濾 draw LIKE '%-%'**，傳回全部 22,238 筆 BIG_LOTTO 列（含 19,100 筆 ADD_ON_PRIZE_EXCLUDED）。

**影響：**
- 任何透過這兩個函數取得 BIG_LOTTO 資料的路徑，均使用混合族群
- `analysis/p219_*.py` 已正確使用 `draw NOT LIKE '%-%'` 過濾 — 不受影響
- P238B NIST 審計以 sample_size=22238 建立（含加碼記錄）— 歷史文物標記為 YELLOW
- 兩個測試硬編碼 `>= 22238`（test_p238b / test_p243a）— 隔離後需更新為 >= 2113

**適用原則：**
- 任何新 BIG_LOTTO 研究查詢必須加 `draw NOT LIKE '%-%'` filter（加碼記錄族群不匹配）
- 資料庫 API 路徑（顯示用途）可傳回全部記錄，但須標示記錄類型
- 測試斷言若依賴 BIG_LOTTO 總列數，需等 P247 Type D 隔離後再更新

---

## L107 — P246B 資料污染 vs 研究族群不匹配 (2026-06-05)

**來源：** P246B 用戶/領域指正

**結論：** P246 將 19,100 筆連字號 BIG_LOTTO 列（如 103000009-01）標記為 SIM_HYPHEN（模擬/合成資料），此標記錯誤。
用戶/領域指正：連字號 ID 為加碼或特別獎記錄，屬於真實彩券相關資料，非偽造資料。

**修正：**
- 舊標籤 `SIM_HYPHEN` → 正確標籤 `ADD_ON_PRIZE_EXCLUDED`
- 排除理由：**族群不匹配**（加碼/特別獎記錄類型與正規 6/49 主開獎不可比較），非資料偽造
- 這些記錄須**保留**（不得刪除），可移至隔離/審計表但須保留全部欄位與值
- 描述這些記錄為 fake / simulated / synthetic / invalid / contaminated 一律視為錯誤

**適用原則：**
- 資料污染（data contamination）= 數值與遊戲規則不符或來源錯誤（適用 DATE_FORMAT_ALIEN / SMALL_POOL_ALIEN）
- 族群不匹配（population mismatch）= 資料本身有效但與目標研究族群不同類型（適用 ADD_ON_PRIZE_EXCLUDED）
- 隔離計畫語言應用 segregation/exclusion/separation，勿用 quarantine contaminated rows
- ADD_ON_PRIZE_EXCLUDED 保留政策必須明示；Type D 才可執行 DB 操作

---

## 115000027 期驗證結論 (2026-02-26)

**L_027_A — Sum公式修正：統一目標 [mu-0.5σ, mu+0.5σ] 優於條件式目標**
- 原始：偏高→[mu-σ,mu], 偏低→[mu,mu+σ], 中性→[mu-0.5σ,mu+0.5σ]
- 修正：統一固定為 [mu-0.5σ, mu+0.5σ]，中性偏心更準
- 效益：1500期Edge +1.05% → +1.41%，perm p=0.020 → p=0.003（顯著提升）
- 三窗口：150=+2.25%, 500=+1.41%, 1500=+1.41% 全正
- 採納：已更新 quick_predict.py biglotto_p1_neighbor_cold_2bet()

**L_027_B — Streak Boost + 組合交互抵消效應**
- 邏輯：鄰域池加入短期連勝加分，捕捉#22類型連勝
- 實測：單獨Streak+OrigCold=+1.27%, 單獨Orig+Fusion=+1.27%, 合併Streak+Fusion=+0.65%（最差）
- 結論：兩個「改善」同時加入反而抵消，組件交互效應必須消融驗證
- 教訓：新特徵要獨立回測，組合前先確認無交互副作用

**L_027_C — Zone Constraint (硬過濾) 在冷號+Sum框架中反效果**
- 邏輯：Z3>=3後限制Z3候選，70.2%統計信號真實
- 實測：D+Zone=+1.20% < D=+1.41%，損失10期命中僅新增7期
- 結論：Zone信號在冷號Sum約束框架下不可操作（Sum尋優空間被縮小）
- 教訓：統計信號真實≠在現有框架下可操作，需考慮框架內部互動

---

## 驗證方法論

**L01 — 1500期三窗口是最低標準**
- 150 / 500 / 1500 三窗口全正才算通過
- 1000期單窗口不夠：SHORT_MOMENTUM 策略在500期內可偽裝成有效
- 來源：Cluster Pivot (500p +1.75% → 1500p -0.45%)
- 日期：2026-02-10

**L02 — 500期可能是幸運窗口**
- 結構過濾從 500期 +1.92% 崩壞至 1000期 -1.38% 的案例實際發生過
- 任何只在500期以內有效的策略，視為「幸運窗口」而非真實Edge
- 日期：2026-02-06

**L03 — Permutation Test 是必要的**
- P3 shuffle test（200次洗牌 × 1500期）可確認時序信號真實存在
- 若 real edge 在 shuffle 後消失 → 有時序信號
- 若 real edge 在 shuffle 後不消失 → 只是號碼分布偏好，非時序信號
- 來源：P3 對抗驗證 2026-02-18

**L04 — 確定性策略優先於隨機策略**
- 偏差互補（無隨機成分）的10種子方差=0，完全可重現
- 隨機策略的種子敏感性會模糊真實Edge評估
- 來源：2026-02-06

**L05 — Grid Search 結果必須Bonferroni校正**
- 38個號碼的多重比較，未校正的p<0.05全是假陽性
- Bonferroni門檻：p < 0.05 / 38 = 0.0013
- P1條件分支：16個偏移號碼，0個通過校正後門檻
- 來源：P1條件機率分支研究 2026-02-09

---

## 信號評估

**L06 — 微調幅度 < 統計噪音時，應找新信號源**
- Echo weight grid search：w=0.10全段最佳，但vs現行策略僅多2~3次M3+/1000期
- Markov重複號碼：boost=0.1最佳，但McNemar p=0.779，+2 hits/1500期
- 原則：改善幅度若無法通過McNemar，不採納
- 來源：2026-02-09, 2026-02-23

**L07 — Gap信號已被頻率窗口部分吸收**
- Gap Dynamic Threshold：16組grid search全部失敗
- Gap與freq部分重疊（高gap通常低freq），雙重加權造成扭曲
- Gap信號不應直接混入選號邏輯；需尋找非頻率域的新信號源
- 來源：2026-02-23

**L08 — 鄰號共現是直覺假象，Lift<1.0時嚴禁使用**
- Lift(13|14)=0.87x, Lift(33|34)=0.73x — 鄰號是負相關
- 鄰號注入後：-8 M3+/1000期
- 直觀的「鄰號會一起出現」完全不符合實證
- 來源：115000012期檢討 2026-02-10

**L09 — Sum均值回歸是強信號，但無法映射至個別號碼**
- Sum均值回歸 Lift=1.495x（z=8.93，p<0.0001）— 極強組合層信號
- 但「下期sum高」的條件下，各號碼Lift最高僅1.24x < 1.3x實用門檻
- 正確用法：做sum-range constraint過濾，而非條件頻率選號
- 來源：結構族群分類驗證 2026-02-23

**L10 — 條件偏移幅度太小，無法改變號碼排名**
- 38選6中單號碼基準15.8%，偏移5%→10-21%範圍
- 偏移量不足以改變排名，條件分支是統計假象
- 來源：P1條件機率分支 2026-02-09

**L11 — 極端結構是不可預測的低概率事件**
- 5:1大小比 = 7.3%歷史率
- Z1+Z3同時空缺 = 1.4%歷史率
- 冷號集群(4冷號) = 11.5%歷史率，FFT的結構性盲區
- 這類事件發生後分析原因是浪費時間，無法預測
- 來源：Gap Rebound研究, 115000013期檢討

---

## 策略設計

**L12 — Layer 1 / Layer 2 分離原則**
- L2投注結構優化無法彌補L1預測信號缺失
- Core-Satellite：大樂透 -0.89%，威力彩 -2.39%
- 正確做法：先確保L1信號品質，再考慮L2結構
- 來源：2026-02-06

**L13 — 注2-3品質守護**
- 任何改善注1的修改都可能損害注2-3
- Gap Rebound：3注GR=139 vs 原始146（損害品質）
- 條件分支：3注版本全部更差（原始140 vs 最佳條件139）
- 改動注1後必須重測全套注數的整體Edge
- 來源：2026-02-09

**L14 — 正交覆蓋是有效的第N注策略**
- 注之間零重疊（正交）可最大化覆蓋
- 大樂透5注：覆蓋30/49號（61.2%，零重疊）
- 威力彩5注：覆蓋30/38號（零重疊）
- 第N注用「剩餘號碼按近100期頻率排序」是有效的低成本補充
- 來源：5注策略驗證 2026-02-24

**L15 — Markov(w=30)是正交注的最佳組合**
- Markov單獨無效（-0.46%），但作為第4注正交有效（整體+1.70%）
- w=100時邊際降至+1.17%，必須用w=30
- 全窗口所有Markov window皆正時才採納
- 來源：2026-02-24

---

## 統計陷阱

**L16 — 未校正的p<0.05在多重比較中是假陽性**
- 38個號碼 × 多個regime = 大量假陽性機會
- 任何grid search結果必須套用Bonferroni校正
- 來源：P1條件分支 2026-02-09

**L17 — SHORT_MOMENTUM的識別特徵**
- 特徵：150期>0，500期>0，1500期<0（明顯衰減趨勢）
- 案例：Cluster Pivot (2.75 / 1.75 / -0.45)
- 案例：Markov單注 (--, --, -0.46)
- 對策：必須1500期才能排除此模式

**L18 — LATE_BLOOMER的識別特徵**
- 特徵：150期<0，但1500期>0（近期表現差但長期穩定）
- 案例：偏差互補 (-2.36% / -- / +0.51%)
- 含義：短期回測拒絕此策略是錯誤的，必須看長期
- 來源：2026-02-10

**L19 — Gemini報告可能使用弱基準**
- 案例：Gemini報告Orthogonal 3-Bet 4.73%，但正確基準是5.48%（3注），Edge=-0.75%
- Gemini使用了弱基準(Freq 1.60% < 隨機1.86%)掩蓋負邊際
- 所有外部報告必須驗算基準公式：P(N注) = 1-(1-P(1注))^N
- 來源：115000012期檢討 2026-02-10

---

## 系統架構

**L20 — 不可重現結果一律無效**
- 必須固定random seed（seed=42為標準）
- 所有回測腳本必須記錄seed、資料範圍、版本號
- 來源：CLAUDE.md可追溯原則

**L21 — 彩種結論不可互相借用**
- Fourier30+Markov30：威力彩有效（+0.91%），大樂透無效（-0.29%）
- 每個彩種需獨立驗證，不可因一個彩種有效就套用到另一個
- 來源：2026-02-10

**L22 — 策略失敗記錄比策略成功更有價值**
- rejected/ 目錄存放所有失敗案例
- 失敗原因、重測條件必須明確記錄
- 「不建議重測」和「條件X成立時可重測」是兩種不同結論

**L23 — 冷號信號與Fourier正交但互補效果有限**
- Draw 016 (04,10,13,24,31,35): 4/6為冷號，Fourier僅命中2/6
- 冷號偏差(w=100)捕獲4/6，比Fourier強在此類事件
- 但冷號集群事件僅佔0.7%，Adaptive切換(PP3+Cold) Edge +2.43% vs PP3 +2.23%
- McNemar p=0.606（不顯著，僅+3 hits/1500期），按L06原則不採納替換
- 結論: 冷號預警作為監控工具，不作為策略替換
- 來源: 2026-02-24 Draw 016 檢討會議

**L24 — PP3 Edge 修正: +2.23% (非+2.30%)**
- 原先記錄+2.30%為四捨五入誤差
- 精確值: 13.40% - 11.17% = +2.23% (z=2.74)
- 已更新 quick_predict.py STRATEGY_INFO
- 來源: 2026-02-24 P1回測精確計算

**L25 — 多窗口 Fourier 稀釋真實信號**
- 實驗: 100p/200p/500p 加權平均 rank (w=0.25/0.35/0.40)
- 結果: 1500p Edge -0.16% (現行 +1.38%)，McNemar p=0.008 **顯著劣化**，-23 hits
- 原因: 100p/200p 窗口信號稀疏 (49選6每號平均出現12次/100期)，FFT雜訊大於信號
- 結論: 大樂透 Fourier 必須用單窗口 500p，多窗口只會稀釋週期信號
- 來源: 2026-02-25 P1a 大樂透115000024期檢討

**L27 — 539 Day-of-Week 效應不存在**
- 全局卡方 p=0.9523，平均號碼差距僅0.96（< 1.0）
- 零個號碼通過 Bonferroni 校正 (p < 0.00026)
- 雖週一熱號[3,10,27,36]巧合包含4/5實際號碼，但屬隨機巧合
- 結論: 539 Day-of-Week 無信號，不應整合入選號邏輯
- 來源: 2026-02-25 P1b 539 115000048期檢討

**L28 — 539 5注Fourier正交是首個可行策略**
- F4正交+Cold: 1500p Edge +1.35% (z=2.4), 三窗口全正, STABLE
- Permutation p=0.030 (SIGNAL_DETECTED), Cohen's d=2.19
- McNemar vs 3注: p=0.000 (+43 hits/1500期)
- Shuffle均值+0.138%顯示有輕微號碼分布偏好（非純時序）
- 採PROVISIONAL狀態，需200期後重驗 (下次驗證期: 5992期)
- 關鍵設計: 注1-4 Fourier500p 正交(每注5號), 注5 Cold100正交
- 來源: 2026-02-25 P1a 539 115000048期檢討

**L26 — bet2 的 Fourier 擴展替換冷號是退步**
- 實驗: 把 TS3 的冷號bet2 替換為 Fourier rank 7-14 + Zone 2:2:2 過濾
- 結果: 1500p Edge +0.91% (現行冷號bet2 +1.38%)，McNemar net=-7 p=0.566 不顯著
- 原因: 冷號bet2的功能是「補捉Fourier盲區的逾期號碼」；改為Fourier候選等於兩注都選同一類信號
- 結論: TS3 注2 必須維持冷號基礎，不應改為Fourier擴展；「#47差1名次」是正常覆蓋雜訊
- 來源: 2026-02-25 P1b 大樂透115000024期檢討

**L29 — LaunchAgent 同步與守護機制**
- 症狀：重新開機後服務未自動啟動（http://localhost:8081 無法訪問）。
- 原因：`~/Library/LaunchAgents/` 下的 `.plist` 檔案版本過舊，缺少 `KeepAlive` 鍵與 `--foreground` 參數。導致 `start_all.sh` 啟動背景進程後腳本立即結束，`launchd` 判定任務完成且未自動重新啟動。
- 對策：同步專案根目錄的最新 `.plist` 到系統目錄，並使用 `launchctl load -w` 重新載入。
- 驗證：載入後檢查 `launchctl list | grep lottery` 確保有 PID，且 `lsof -i :8081` 端口正常監聽。
- 日期: 2026-02-25

**L30 — 539 3注 Bet Overlap 是覆蓋率殺手**
- 實驗: SumRange+GapPressure+ZoneShift 3-bet 539
- 結果: M2+ 31.60% vs random 3-bet 32.56% — 不優於 random (perm p=0.71)
- 但顯著優於舊策略 (McNemar p=0.0152, +29 draws/500期)
- 根因: 策略3注平均僅13.4 unique nums (34.4% coverage), random非重疊3注=15 unique (38.5%)
- **教訓: 3-bet 策略的 individual prediction quality 不如 inter-bet diversity 重要**
- **Rule: 任何 N-bet 組合策略，必須先確保 unique number coverage >= random N-bet baseline 的 coverage**
- 舊策略 (SumRange+Bayesian+ZoneBalance) 也未通過驗證 (edge -1.84% to -4.64%) — 兩個策略都不及 random
- 新模組 gap_pressure.py 和 zone_shift_detector.py 保留為建構元件
- 下一步: 加入 exclude set 正交化，或改為 4-5 bet 結構以增加 coverage
- 來源: 2026-02-26 115000050期檢討 P0 action items 回測

**L32 — MAB注選擇器在稀疏信號環境無效 (2026-02-27)**
- Thompson Sampling需要足夠樣本分辨arm差異：M3+率~4%，每arm選1000次才有~40次成功
- 各arm成功率差距2.8%~4.4%=1.6pp，Beta分佈無法收斂；結果比PP3固定配置差-1.13%
- **Rule: MAB需要 (1) M3+率>8% OR (2) 總樣本>5000期，才有足夠訊噪比**
- 目前威力彩M3+率~11%，但單arm被選次數~700，仍不足以讓MAB穩健收斂
- 來源: 115000017期研究 P2回測

**L33 — Echo lag-3 改善1500p但損害150p短期穩健性 (2026-02-27)**
- lag-2→lag-2∪lag-3: 1500p +0.14% 改善，但150p從+3.50%→+2.17%（劣化-1.33pp）
- 擴大Echo池使注3候選更分散（非更精確），短期雜訊增加
- **Rule: 候選池擴大需確認150p不劣化；若改善1500p但損害150p，視為SHORT_MOMENTUM升級副作用**
- 來源: 115000017期研究 P0-A回測

**L34 — Wavelet CWT計算成本不可行 (2026-02-27)**
- CWT(38號×500期×1500回測)計算量=FFT的~60倍，單次>25分鐘
- 在現有CPU環境不可用於完整回測；若需短期局部週期信號，改用「局部窗口FFT(128期)」替代
- **Rule: 信號改進方案需先做計算複雜度評估，O(N³)以上在1888期資料集上不可行**
- 來源: 115000017期研究 P1-B

**L35 — Sum Regime切換的樣本不足問題 (2026-02-27)**
- HIGH Regime(近30期均值>mu+0.3σ)僅佔3.3%(50期)，LOW 7.3%(109期)
- 條件切換引入不一致性，500p劣化-0.80pp，1500p劣化-0.20pp
- **Rule: Regime切換需要每個Regime至少>150個訓練樣本才可操作；目前HIGH Regime不足**
- 條件Regime的高Sum場景(如017期Sum=154)是尾端事件，無法靠30期均值可靠識別
- 來源: 115000017期研究 P0-B回測

**L36 — Ort5三域精化注4是PROVISIONAL候選 (2026-02-27)**
- 三窗口全部改善: 150=+6.76%(+1.34pp), 500=+2.49%(+0.20pp), 1500=+3.02%(+0.40pp)
- perm p=0.050 恰好達標，McNemar net=-6(不顯著)
- **Rule: 注4精化屬架構內調整，McNemar不顯著但三窗口全部改善，採PROVISIONAL監控200期**
- 監控門檻: RSM 100期 Edge>+3.5%則正式採納，<+2.5%則拒絕
- 來源: 115000017期研究 P1-A回測

**L37 — 539 3注策略的幾何覆蓋效益陷阱 (2026-02-27, 確認)**
- P0-B 3bet_F_Cold_Fmid: Signal Edge = **-0.976%**（perm p=0.71）
- P0-C 3bet_F_Cold_x2: Signal Edge = **-0.176%**（perm p=0.56）
- 共同根因: 非重疊3注(15/39=38.5%) shuffle均值=32.58%，比理論30.44%高 **+2.133%**（幾何覆蓋效益）
- 4種3注設計全數失敗（GapPressure/ZoneShift/Fmid/Cold2nd）
- **Rule: N注策略若 Signal Edge（vs shuffle）< 0，三窗口全正是分布偏好假象，必須拒絕**
- **Rule: 539 3注策略研究暫停。需找到 Signal Edge > +2% 的強信號才能突破幾何效益門檻**
- 為何5注通過: 5注覆蓋25/39(64%)，Fourier信號SNR足夠超越shuffle（perm p=0.030）
- 3注失敗原因: 15/39覆蓋率太低，幾何效益主導，Fourier信號被淹沒
- 來源: 115000051期 P0-B+P0-C 完整回測

**L38 — 單注 permutation 必須用 1500期窗口；ACB 確認通過 (2026-02-27)**
- 500期窗口: Signal Edge=+1.964%, p=0.066 (MARGINAL) — 統計力不足
- **1500期窗口: Signal Edge=+2.804%, p=0.002, z=3.485, Cohen's d=3.485 → PASS ✅✅**
- 根因: 1注M2+率≈11.4%，500期只有~57次命中，統計力不足；1500期=171次命中，功率充足
- **單注 shuffle bias ≈ 0**（+0.07%），確認無幾何偏好問題；Total Edge ≈ Signal Edge
- **Rule: 單注策略的 permutation 必須用 1500期窗口，500期嚴重低估統計顯著性**
- ACB 採納: PROVISIONAL（三窗口全正+perm p=0.002 Bonf通過）
  - 設計: freq_deficit×0.4 + gap_score×0.6 × boundary(±5邊界1.2x) × mod3(1.1x) + cross-zone
  - 最佳 window=100（敏感度: w50=+1.54%, w100=+2.87%, w200=+1.94%）
  - 近期預測穩定: 冷號集群 [4,9,20,21,39]；115000051命中#9,#39(M2+)驗證
- 來源: 115000051期 ACB permutation test（500次洗牌 × 1500期窗口）

**L39 — 單注信號不等於多注組合中的有效第N注 (2026-02-27)**
- ACB 單注: Signal Edge=+2.804%, p=0.002 → PASS ✅
- ACB 作為第6注加入F4Cold:
  - 邊際救援率: 3.80% (57/1500期) vs 隨機第6注期望: 5.29% → **71.8%效率 (sub-random)**
  - 5注 Signal Edge: +8.21% → 6注 Signal Edge: +5.78%（**稀釋-2.43pp**）
  - McNemar p<0.0001（57次救援統計顯著），但救援率低於基準預期
- **根因: ACB信號（頻率欠缺+gap）與F4Cold注5（冷號頻率排序）高度重疊**
  - 同樣選「欠缺的號碼」→ F4Cold注5已覆蓋大部分ACB會選的號碼
  - 信號空間重疊導致邊際貢獻低於一個隨機注
- **Rule: 單注通過 permutation ≠ 可加入任意N注組合。加入前必須：**
  1. 計算邊際救援率 vs 理論 P_GE2_1 × P(N-bet miss)
  2. 若效率 < 80%，信號重疊嚴重，應考慮替換而非疊加
  3. N注 Signal Edge 不應低於 (N-1)注 Signal Edge（稀釋警報）
- **建議路徑: ACB 應作為獨立策略參考，或研究替換 F4Cold 中的弱注（注5 Cold）**
- 來源: 115000051期 ACB 第6注邊際效益回測

**L40 — 信號強度依賴選號空間：全空間強，殘餘空間弱 (2026-02-27)**
- ACB 全空間單注: Signal Edge +2.804% (p=0.002) ✅
- ACB 替換F4Cold注5（殘餘池 rank21-39）: 5注整體 +0.04pp，McNemar p=1.000 ❌ 統計中性
- 注5成分: ACB edge +1.34% vs Cold +0.80% (+0.53pp), 但McNemar p=0.34 不顯著
- **根因: Fourier Top-20 已選走 rank 1-20 的高頻率/節律號碼**
  - 殘餘池只剩 rank 21-39 = 冷門/Gap 大的號碼
  - 在殘餘池中 Cold 和 ACB 都是選「相似號碼」— 信號差異縮小
- **Rule: 策略 A 的信號若依賴與策略 B 相同的號碼維度，正交排除後信號優勢會被大幅衰減**
- **Rule: 獨立回測通過 ≠ 正交疊加後依然有效。疊加前必須確認信號維度不重疊**
- 「截然不同的信號維度」才能維持各自的 Signal Edge（如 Fourier×Cold 是正交的）
- 來源: 115000051期 ACB 替換注5 完整回測

**L31 — 覆蓋率是必要條件但非充分條件**
- L30 修正: 正交化 (exclude set) 成功將 overlap 從 13.4→15 unique nums
- M2+ 提升: 31.60%→34.00% (+2.40pp)，確認 L30 根因診斷正確
- 但: perm test p=0.2388 (未通過) — random 3-bet 不重疊 baseline 也有 32.56%
- **教訓: 解決 coverage 後，瓶頸轉移到個別注的信號品質**
- **Rule: 多注策略需同時滿足 (1) 零重疊覆蓋 AND (2) 每注個別正 Edge**
- GapPressure + ZoneShift 的選號能力僅略優於 random (edge +1.44%, Z=0.69, 不顯著)
- 正面: McNemar vs old strategy p=0.0009 (+40 draws)，正交化本身是有效機制
- 結論: 3-bet 信號需要更強的底層預測器（如 Fourier-based），不能靠 coverage 單獨解決
- 來源: 2026-02-26 539 3-bet 正交化回測

---

## 115000028 期驗證結論 (2026-02-28)

**L_028_A — 單期結果不能推翻長期統計驗證**
- 錯誤: 因 028 期兩版本 2注 均命中 1/6，建議「暫緩恢復已驗證策略」
- 問題: 用 n=1 樣本推翻 n=1500 的統計結論，違反 L01 和 L03
- P1 v2 (p=0.003) vs P0 (較低顯著性) 的差異已由 1500 期驗證確立
- **Rule: 單期檢討只能識別結構性問題和新研究方向，不能用來推遲或否決已通過驗證的策略部署**
- 來源: 2026-02-28 028期檢討自我修正

**L_028_B — SUPERSEDED 策略不應用於選擇性比較**
- 錯誤: 引用舊5注(TS3+Markov+FreqOrt)的注5命中來論證「舊版也不差」
- 問題: 該架構已標記 SUPERSEDED（架構孤島），其注5 FreqOrt 的命中是廣泛殘留池覆蓋效應
- **Rule: 已被取代的策略不應在檢討中被拿來作為維持現狀的論據**
- 來源: 2026-02-28 028期檢討自我修正

---

## P2 高頻突斷研究結論 (2026-02-28)

**L41 — 「高頻突斷」無統計信號，ACB 權重不需調整**
- 定義: freq100 > expected(12.82) AND gap > 20
- 200期回測結果 (gap>20): Edge -1.01%, z=-0.34, p=0.672 — **NOT SIGNIFICANT**
- 參數敏感度: gap>15 edge+0.24% p=0.48, gap>25 edge-2.62% p=0.77, gap>30 edge+2.56% p=0.51 (n=13太小)
- 當前僅1個號碼符合條件 (#30: freq100=13, gap=29)
- **根因: 高頻突斷號碼的下期命中率 ≈ 隨機基準 (12.82%)，不具預測價值**
- ACB 的 freq_deficit×0.4 抵消 gap_score×0.6 是正確行為，不需調整
- **Rule: 不要因為單一案例 (#02 in 115000053) 調整通過驗證策略的權重**
- 來源: tools/monitor_high_freq_stop.py, 200期 walk-forward

---

## 115000054 期驗證結論 (2026-03-01)

**L42 — 多注策略的信號正交性比單注信號強度更重要**
- 場景: ACB(冷號獵人)在「全溫號」開獎組合 [02,08,15,29,31] 命中0個
- 分析: 4/5號碼為WARM (接近期望頻率), 1個HOT → ACB公式的freq_deficit為負值，完全排斥
- 解法: 三注覆蓋不同溫度帶 — Markov(HOT動量) + MidFreq(WARM回歸) + ACB(COLD壓力)
- 結果: P3a 3注 Edge +5.77% (1500p, z=2.23, p≈0.013) — **PENDING_VALIDATION**
- ⚠️ 修正: 原報告 perm p=0.005 是200次shuffle的報告下限，z=2.23 對應 p≈0.013（仍顯著但需McNemar確認）
- 之前4種3注設計(GapPressure/ZoneShift/正交版/F-Cold)全部FAIL — 因為它們都是同類信號多注
- **Rule: 多注設計時，每注應捕捉不同維度的信號(溫度帶/時間尺度)，而非同一信號的不同切片**
- 來源: tools/backtest_539_p0p5.py

**L43 — 馬可夫轉移矩陣對539：單注不顯著，但作為正交維度有組合價值**
- 場景: 上期[02,04,13,26,27]，Markov轉移Top5中包含08,29,31(本期實際開獎)
- 機制: 號碼間存在弱但穩定的轉移傾向，30期窗口足以捕捉
- ⚠️ 修正: 單注 z=1.22 (p≈0.11) **未通過顯著性門檻** → REJECTED 為獨立策略
- 已歸檔: rejected/markov_1bet_539.json
- **Rule: 單注未通過 p<0.05 時，不可標記為 ADOPTED。但可保留作為多注正交組件繼續研究**

**L44 — 均值回歸(MidFreq)是MODERATE_DECAY模式，非STABLE**
- 邏輯: 選頻率最接近期望值的號碼 → 零參數，無隨機性，計算成本極低
- 三窗口 Edge: 150p=+5.68%, 500p=+1.75%, 1500p=+1.02% — **短期高、長期低 = MODERATE_DECAY**
- ⚠️ 修正: 原標記 STABLE 是錯誤的。三窗口雖然全正，但呈明顯衰減趨勢
- 單注 z=1.94 (p≈0.026) — 邊界顯著，降為觀察
- 與ACB組合2注 P2c: Edge +4.44% (z=3.16) — **待 McNemar 驗證**
- **Rule: 三窗口全正但衰減幅度>3x (150p/1500p) 時，標記為 MODERATE_DECAY 而非 STABLE**

**L45 — UCB1 Bandit在539策略選擇中不如人工正交設計**
- 原因: 4個arm(markov/midfreq/acb/lift)的平均reward差異<0.01，UCB1無法有效區分
- 2注Bandit Edge +1.84% vs 人工MidFreq+ACB +4.44% (差距2.6pp)
- 3注Bandit Edge +3.10% vs 人工3注 +5.77% (差距2.67pp)
- **根因: Bandit需要arms之間有穩定的reward差異才能學習，但539每期reward太嘈雜(1/5概率)**
- **Rule: 當reward信號很弱時，人工先驗知識(溫度帶正交)優於在線學習**

**L46 — 共現Lift pair作為單注主策略不可靠**
- 機制: 找歷史Lift>1的配對作為錨點
- 問題: 1500p Edge -0.38%，15期以上高Lift pair的統計顯著性不足
- 需要的pair觀察量: C(39,2)=741 pairs, 500期窗口中每pair平均觀察<1次 → 噪音主導
- **Rule: 配對共現需要遠大於目前的數據量(>8000期)才能穩定估計**

**L47 — Permutation Test 的 p-value 報告下限問題 (2026-03-01 修正)**
- 問題: N次shuffle的最小可報告p = 1/(N+1)。200次shuffle → p_min = 1/201 ≈ 0.005
- 症狀: 多個策略同時報告p=0.005，看似全部高度顯著 — 實際上是碰到報告下限
- 正確做法:
  1. 使用 z-score 計算 p_from_z = 1 - Φ(z)，不受 shuffle 次數影響
  2. 增加 shuffle 次數至 ≥500 (p_min ≈ 0.002)
  3. 同時報告 p_empirical 和 p_from_z，取較大值
- 實際影響:
  - P0 (z=1.22): p_from_z ≈ 0.111 → **NOT SIGNIFICANT** (原報告 p=0.005 嚴重高估)
  - P1 (z=1.94): p_from_z ≈ 0.026 → 邊界顯著
  - P2c (z=3.16): p_from_z ≈ 0.001 → ✅ 顯著
  - P3a (z=2.23): p_from_z ≈ 0.013 → ✅ 顯著
- **Rule: 永遠不要只報告 p_empirical。必須同時計算 p_from_z 並在報告中標明 n_perms**
- **Rule: 若所有策略 p_empirical 都等於 p_min，表明 shuffle 次數不足，不可據此下結論**
- 來源: 用戶指正 2026-03-01

**L48 — 生產腳本變更必須通過 McNemar 驗證閘門 (2026-03-01 修正)**
- 錯誤: 將 predict_539() 3注路徑從 F4Cold 改為 P3a，未經 McNemar 對比就部署
- 問題: F4Cold 是目前唯一通過驗證的策略 (PROVISIONAL, perm p=0.030)
- P3a 雖然 Edge 更高 (+5.77% vs +1.35%)，但未與 F4Cold 做配對比較
- **Rule: 替換生產策略前必須通過:**
  1. 三窗口一致性 (全正) ✅
  2. Permutation test p < 0.05 (用 z-score) ✅ (z=2.23)
  3. McNemar test vs 現行策略 p < 0.05 ← **缺失**
  4. 前後兩策略在相同資料上配對比較
- **Rule: 回測結果再好，沒完成 McNemar 閘門就不能進 production**
- 來源: 用戶指正 2026-03-01

**L49 — Power Lotto Sum Lift 實測僅 +0.1%，報告值 42.7% 不成立 (2026-03-03)**
- P18 報告聲稱: prev_sum≥145 後次期 sum≤110 機率 = 42.7% (vs 基準 38.1%)
- 實測 (1789期全資料): prev_sum≥145 → next sum≤110 率 = 41.1% (vs 41.0% baseline) = **+0.1% lift**
- PP3_SumReversal 1500p Edge = +2.57% (vs PP3_orig +2.23%)，改善 +0.33pp
- 但 McNemar net=+5 (p=0.180) 不顯著；觸發率 23.9% (427/1789) 適中
- **Rule: P1 標記 PROVISIONAL (perm_p=0.000, 三窗口全正)，但 Sum 信號本身 lift 幾近於 0**
- **Rule: 策略改善可能來自 combinatorial diversity，而非被聲稱的 Sum 均值回歸信號**
- 來源: 115000018期 P1 回測 2026-03-03

**L50 — SHLC (短熱長冷矛盾指標) 在威力彩無預測力，P18 #11 是倖存者偏差 (2026-03-03)**
- SHLC = rank_500 / rank_100，閾值 >3.0 定義為「近期升溫」
- SHLC Top-10 信號增益 = +0.4% vs 隨機 (完全可忽略，p=0.595)
- PP3+SHLC_bet2 替換 Fourier 7-12: 1500p 從 +2.23% 劣化到 +1.90% (-0.33%)
- **Root cause: P18 #11 (rank_100=5, rank_500=34) 是 n=1 案例，符合 L12 的倖存者偏差**
- **Rule: 個別期次的矛盾信號（近期排名≠長期排名）不可作為策略設計依據**
- **Rule: 新指標需在完整 1500 期三窗口通過才可替換現有機制**
- 來源: 115000018期 P0 回測 2026-03-03

**L51 — PP3 Fourier 注2 (rank 7-12) 是有效的正交互補，不應被替換 (2026-03-03)**
- PP3 架構: 注1 = Fourier Top 1-6；注2 = Fourier Top 7-12；注3 = Echo+Cold
- 注2 作用: 以低重疊方式延伸信號域，整體注2 1500p Edge 為正
- SHLC 替換注2 後 1500p 下滑 -0.33%，驗證 Fourier 7-12 的互補性不可取代
- **Rule: 互補注的設計目標是 zero/low overlap + independent signal**
- **Rule: Fourier 7-12 已是正交補充的最優選擇；若要改善 PP3，應考慮增加第4注而非替換注2**
- 來源: 115000018期 P0 回測 2026-03-03

---

## 研究哲學原則

**L55 — 研究沒有永久封存，只有暫停研究 (2026-03-03)**
- **原則**: 任何策略或信號只能被「暫停研究」，不得標記為「永久封存」或「禁止再嘗試」
- **原因**: 科學研究的邊界是當前的理論框架、數據量和計算能力。這三者都會隨時間進步
- **正確語言**: 「在目前條件下（線性框架 / 資料量X期 / 計算能力Y）無信號，重啟條件：[具體條件]」
- **具體應用**:
  - Gap Pressure：「頻率窗口吸收下暫停」→ 重啟條件：與頻率正交的非線性Gap理論
  - 熱號休停回歸：「線性框架下Edge≈0」→ 重啟條件：非線性衰減模型或dataset>3000期
  - 冷號池pool=15：「Sum約束下小池更精準」→ 重啟條件：Sum公式重大更新後重驗
  - 連號對：「Lift≈1.0x」→ 重啟條件：Zone分層後的條件Lift分析
- **rejected/ 目錄的作用**: 存放「暫停中」的研究歸檔，附帶明確重啟條件，而非墓地
- **Rule: 系統中嚴禁出現「永久封存」「禁止再嘗試」等絕對性語言**
- 來源: 115000032期設計評審會議，用戶指正 2026-03-03

---

## 115000056 期 539 Neighbor-ACB 研究 (2026-03-04)

**L56 — 單注 perm p<0.01 ≠ 可疊加；邊際效率 < 80% 必須拒絕**
- 觸發: 056期鄰號命中 3/5（歷史8%），三專家建議研究 Neighbor-ACB 2注
- 設計: Bet1=鄰號池(平均8.3碼)→ACB Top-5; Bet2=全池ACB Top-5排除Bet1
- 結果: Neighbor-ACB V1 1500p Edge=+2.79%, perm p=0.005 (SIGNAL_DETECTED✅✅), STABLE
- 但: MidFreq+ACB 1500p Edge=+5.13%（現有ADOPTED），McNemar p=0.0743不顯著替換
- 4注合體計算: combined_rate=37.60% vs 4注baseline=38.43% → Edge=-0.83% ❌負值
- 邊際效率: 164(新增命中)/253(需要命中)=64.7% < L14門檻80%
- 重疊率: 55.1%的Neighbor命中已被MidFreq+ACB覆蓋
- **核心教訓**: 即使 perm p=0.005 確認信號真實，若被現有策略大量重疊(55%)，疊加組合的邊際效率不足以超越更高的基準線
- 重啟條件: 鄰號變體與MidFreq+ACB重疊率<40%，或鄰號+Gap/Sum過濾後邊際效率>80%
- 歸檔: `rejected/neighbor_acb_2bet_539.json`
---

## 115000032 期大樂透設計評審 (2026-03-04)

**L54 — Zone=0/≥4 後鄰域注系統性盲區 (已回測修正)**
- 觸發: 032期開獎 [05,26,27,35,45,46] sp=37，2注/3注僅命中1/6
- 原始假設: 上期Zone極端時鄰域池品質退化，建議動態升注
- **2026-03-05 BIG_LOTTO 2113期全量回測反駁**:
  - Zone=0觸發率21.25%; 覆蓋率差異 -2.84pp; t-test p=0.16 **不顯著**
  - Zone>=4 chi2 p=0.037 (邊界) 但 t-test p=0.28, 均值差異極小 (-0.054)
  - Z2=0最強但仍不顯著 (37.1% vs 43.15% = -5.84pp, n=167太小)
- **修正後結論: Zone=0 效果是方向性的但統計上不可操作**
  - 個別期 Z2=0 崩塌(028-031)是正常統計噪音，1500期 perm p=0.003 不受影響
  - RSM 加入 Zone 監控作為資訊性指標，不觸發自動升注
- **Rule 更新**: Zone 監控 = 資訊性顯示，不等同策略調整觸發條件
- 實作: `rolling_strategy_monitor.zone_status_from_draws()`
- 來源: 115000032期觀察 + 2113期回測統計驗證 (2026-03-05)

**L55 已確立 (見上方研究哲學原則段落)**

**L57 — 尾數多樣性約束是免費 Edge 提升**
- 觸發: 032期尾數5聚集3次 (#05,#35,#45)，P(≥3同尾)≈1.2%
- 實驗: enforce_tail_diversity(max_same_tail=2) 後處理，1500期A/B比較
- 結果: 大樂透5注 ΔEdge=+0.40% (2.64%→3.04%, perm p=0.000)
- 原理: 移除低頻尾數重複號，加入高頻替補，等效於「微弱的頻率優化」
- 1500期中有 732 注 (48.8%) 存在尾數違規 — 說明此約束作用範圍大
- **Rule: 後處理約束可以是免費的 Edge 提升。值得系統性搜索其他後處理約束**
- 已驗證: 大樂透 ✅ / 威力彩 ✅(2注) ⚠️(3注) / 539 中性

**L58 — 連號對在 5 注系統中已自然覆蓋 (98.4%)**
- 連號分布: 歷史49.6%的期數有≥1組連號
- 5注×6號 = 30號覆蓋 49號池 (61.2%)，自然產生連號機率極高
- 顯式連號注入對 Edge 無益 (ΔEdge: 0.00% ~ -0.40%)
- **Rule: 在決定添加約束前，先量化「自然覆蓋率」。若已>95%，約束多餘**
- 重啟條件: 注數降至3注以下時重新評估

**L59 — Gap 排序不如頻率排序 (冷號池研究)**
- 測試5種 gap 範圍 (8-15, 6-12, 6-18, 10-20) + Sum約束
- 全部劣於現行 pool=12 最低頻率: 最佳 +1.51% vs 現行 +3.04%
- 原因: 頻率排序自然包含 gap 信息 (高 gap ↔ 低頻率)，但頻率更平滑
- **Rule: 複合信號 (頻率) 通常優於單一信號 (gap)。避免降維打擊**

---

## 115000020 期研究結案 (2026-03-09/10, 威力彩)

**L60 — 單期事後最佳方法不可直接升格為策略**
- 020期: Deviation(w50) 命中3/6，事後看是最佳；但1500期回測 Dev Top6 avg=0.99 (基線)
- P(命中≥3 | 隨機期) ≈ 3.0%，這是幸運事件而非信號
- Lag-1重複≥3: 歷史3.2%，直接用上期號注入 Edge 僅 1.01x — 不是穩定策略
- **Rule: 單期分析報告只能產生研究假設，不能產生部署決策**

**L61 — McNemar 必須在部署前完成 (不是部署後補)**
- 020期優化先部署 PP3v2，再補跑 McNemar → 發現 hit≥1 V1勝 p=0.010，被迫回退
- 正確流程: Idea → Backtest → McNemar → 通過 → 部署
- **Rule: 驗證門 (McNemar gate) 在部署前，不在部署後。已部署再回退有歷史紀錄污染風險**

**L62 — hit=0 率翻倍是不可接受的風險 (即使 hit≥2 平手)**
- PP3v2 hit=0: 30期 vs PP3v1: 14期 (翻倍)
- hit≥2 McNemar p=0.848 平手，但 hit≥1 p=0.010 V1顯著勝
- 「最差表現期翻倍」是具體風險，不應被「平均表現相近」掩蓋
- **Rule: 評估策略時，除 Edge 外必須檢查「災難率」(hit=0 rate)，災難率上升應單獨觸發拒絕**

**L63 — Fourier 窗口改動需 1500期 McNemar，不能用 Top6 命中率比較**
- 020期報告: w=100 Top6 hit≥1=75.3% vs w=500 hit≥1=59.3% → 看似顯著
- 1500期 walk-forward McNemar: w100_only=8, w500_only=12, p=0.502 不顯著
- 差異原因: Top6 命中率是 in-sample / 事後統計，McNemar 是 OOS 直接比較
- **Rule: 任何「方法 A 比方法 B 更好」的聲明，必須用 OOS McNemar 驗證，不接受 in-sample 比較**

**L64 — Permutation test 正確實作: 不可 shuffle hits array**
- 錯誤做法: rng.permutation(actual_hits) → 不改變分布，p 恆=1.0 或 0.0
- 正確做法: scipy.stats.binomtest() 精確二項檢驗，或 bootstrap 隨機生成對照注
- **Rule: Permutation test 的 null hypothesis 必須明確定義「隨機基準」，shuffle 只能用於打亂標籤(如 label permutation)，不能用於打亂預測結果**

**L65 — CSN (Cold Safety Net) 特別號優化通過**
- Gap≥20 強制納入特別號候選 (而非原設想的 Gap≥15)
- 效果: +2.62% vs 原 V3 MAB +2.20%，已部署 special_predictor.py
- 最佳閾值由回測決定，不應預設 (Gap≥15 是直覺值，Gap≥20 是回測最優值)
- **Rule: 超參數閾值 (如 gap 門檻) 必須回測決定，不接受直覺設定**

**L66 — ACB 連續評分已隱含極端冷號信號，硬閾值篩選有害**
- ExtremeCol (gap≥25) 1注: p=0.363 LATE_BLOOMER; 與 MidFreq/ACB 合體後 McNemar 均劣化
- 根因: ACB gap_score 自然對 gap≥25 給高分，硬閾值過濾反而縮小覆蓋空間
- **Rule: 若新篩選器與現有評分系統高度相關 (ACB gap_score ≈ ExtremeCol)，合體必然弱化而非強化**
- 歸檔: `rejected/extremecol_1bet_539.json`, `rejected/acb_extremecol_2bet_539.json` 等 4 個
- 來源: 115000060/061 期檢討 2026-03-10

**L68 — 539 結構化選號與微調 (Habit-Aware & Zone Rebalancing) (2026-03-11)**
- 觸發: 115000062期 (11,12,14,17,32) 的序列爆發。
- 失敗檢討: 單純的「動量切換 (Momentum Switching)」在 150 期回測中失效 (-4.66pp M2+)，主因是信號共線性嚴重且觸發率過高 (70%)。
- 成功探索: 發現 539 號碼具有「戰術偏好 (Affinity)」，且區間聚集 (Zone Cluster) 具有週期性 (如 Zone 1 約 3.77 期週期)。
- 終極實作 (V8): 採用「傅立葉主導 + 局部微調」：
    1.  以全局傅立葉 (Global Fourier) 篩選前 10 名。
    2.  對前 10 名依據「預期爆發區間」與「號碼個別習慣」給予 5%~20% 的加權 (Bias)。
- 驗證: 1500期回測 M2+ 提升至 36.73% (+0.20pp)，Edge 提升至 +6.63%，z=5.62。
- **Rule: 不要用局部信號替換全局信號，應將局部信號作為全局信號的「排序微調器 (Fine-tuner)」。**
- 來源: 115000062 期研究。

**L67 — Conditional Fourier 在大資料庫中退化為 NO-OP**
- 539 有 5804 期資料，FFT window=500 → 每個號碼都有穩定頻譜，max(fourier_score) 幾乎永遠 > 任何合理閾值
- 門檻 0.25~0.40: LagEcho 路徑觸發率接近 0，等同純 Fourier (Edge +6.10% vs +6.17%)
- **Rule: 條件分支設計前必須確認觸發率，觸發率 < 5% 的分支是 NO-OP，不值得維護**
- 歸檔: `rejected/conditional_fourier_539.json`, `rejected/condfourier_3bet_539.json`
- 來源: 115000060/061 期檢討 2026-03-10
---

## L69 — 「先部署後驗證」反向流程警示 (2026-03-11)

**事件**: 連續兩次在正式驗證前就將未驗證策略部署至 quick_predict.py
- 第一次：Momentum Regime 切換 (EnhancedSerial) — 正式回測後 **150期 Edge=-0.32%**，三項全不通過 → REJECT
- 第二次：HabitFourier V8 (Zone+Echo+Neighbor bias) — 正式回測後 **150期 Edge=-0.98%**，三項全不通過 → REJECT

**兩次共同失敗根因**:
1. Echo/Neighbor bias 與已有的 Markov 注（注2）高度重疊，加入後無增量信息
2. 觸發條件 (threshold=0.6 / FFT strength>60) 均為任意值，無 sensitivity analysis
3. 用 062 期單期「成功案例」作為驗證依據 — 事後偏誤（L60）
4. 報告中的 z-score 數字無法數學重現

**Rule**: 
- `quick_predict.py` 的任何修改必須附帶「先完成 backtest → 再修改」的順序
- 正確流程：Idea → 獨立回測腳本 → 三窗口驗證 → McNemar → 通過後才修改生產腳本
- 如果看到「已部署，請確認」的請求，直接回退並要求先完成驗證
- 報告中的 z-score 必須可從 M+rate 和 n 重算，否則視為不可信

---

## L70 — Zone Cascade Guard + Hot-Streak Override → 全部 REJECTED (2026-03-14)

**事件**: 大樂透 115000035 期 [05,12,13,38,47,48] (Special:03) 檢討。
Coordinator-Direct(7agents) 最佳 M2 (命中 #12, #48)。

**根因分析**:
1. **Z2=0 系統性盲區**: 033期Z3=0 → 035期Z2=0，Zone=0連鎖事件未建模
2. **#47/48 被冷號策略排斥**: 近13期中 #47 出現5次 (38.5%), #48 出現4次 (30.8%)，遠超理論 12.2%
3. **雙連號對 (12-13, 47-48)**: 結構特徵未建模（但統計上無法可靠預測）
4. **特別號 #03 gap=62 期**: 歷史頻率正常 (ratio=1.02)，BIG_LOTTO 缺乏專用特別號預測器

**完整標準驗證結果** (2116期 BIG_LOTTO):

Zone Cascade + Hot-Streak 組合:
- 2-bet: REJECTED (1/4 checks) — Sharpe only
- 3-bet: REJECTED (2/4 checks) — three-window + Sharpe

參數掃描 (Zone boost × HS rate grid):
- **Hot-Streak alone: ALL configs FAIL** — 所有 hs_rate 組合三窗口皆不通過
- Zone-only zb=0.12: 唯一三窗口 PASS 配置 (edge=+0.77%, diff=+1)
- Combined: 表現不優於 Zone-only

Zone Cascade Only (zb=0.12) 完整驗證:
- 2-bet: REJECTED (2/4) — perm_p=0.73, 500p=-0.29%
- 3-bet: REJECTED (2/4) — perm_p=0.51, significance p=0.069
- McNemar: ZoneG-only=22 vs NoGuard-only=21 → **無顯著差異**
- OOS: 5-fold 中 3 fold 為負邊際

**最終判定**: 全部 REJECTED，已從 production code 移除
- `strategy_coordinator.py`: 移除 `_apply_zone_cascade_boost()`, `_apply_hot_streak_boost()`, `_ZONE_BOUNDS`
- `quick_predict.py`: 移除 `enforce_zone_coverage()`, `_ZONE_BOUNDS_QP`
- 歸檔: `rejected/zone_cascade_guard_biglotto.json`, `rejected/hot_streak_override_biglotto.json`

**教訓**:
- **Zone rebound probability 69.2% 是真實統計現象，但現有 agents 已隱式捕捉此信號** — 顯式 boost 產生噪音而非信號
- **Permutation test 是判斷「信號 vs 巧合」的終極測試** — p=0.51 表示簡單打亂時序即可獲得相同命中率
- **Hot-Streak (z>2.0) 本質上在捕捉已到峰值的號碼** — 偵測到≠持續，mean-reversion 意味著 boost 方向錯誤
- **三窗口 PASS ≠ 真實有效** — 必須搭配 permutation test 確認時間依賴性
- Lag-13 回聲為純偶合 (ACF 不顯著, P(≥3 overlap)=1.57% 但非 lag-13 特有)
- 特別號 #03 gap=62 有 CSN 安全網，但 BIG_LOTTO 特別號範圍 1-49, 比 POWER_LOTTO (1-8) 更分散

---

## 115000065期 設計評審 (2026-03-14)

**L69 — Sum 尾部事件 + Zone 極端集中是系統性預測盲區，應對策略是補充注而非直接預測**
- 115000065 期 [02,05,11,12,15]: Sum=45 (歷史第1%分位, -2.41σ), Z1=4/5 (出現率3.6%), 構成複合尾部事件
- 現有所有策略（ACB/MidFreq/Fourier）Sum約束設計偏向中心區間 → 尾部事件時系統性失效
- 正確應對：**不應試圖直接預測 1% 尾部事件**，而應設計 Zone Pressure Index (ZPI) 補充注機制
- ZPI 定義：各 Zone 的「期望累積出現次數 vs 實際出現次數」滾動差（100期窗口，嚴禁使用全量均值）
- 當 ZPI 閾值觸發時，注2 改為低號+熱號組合的「Zone補充注」
- 驗證要求：ZPI 補充注需 300期 Walk-Forward OOS，perm p < 0.05 才可採納
- 日期：2026-03-14

**L70 — Multi-lag Echo 必須對每種彩票獨立驗證，不可跨彩種套用結論**
- 115000065 期：#11,#12 在 062期出現後，lag=3 重複（062→063→064→065）
- Power Lotto lag-3 Echo 已 REJECT（見 L33），但 539 機制不同（39選5 vs 38選6+1特別號）
- 539 lag-1 Markov 已驗證有效，lag-2/3 尚未研究
- 行動：對 5806期 539 全數據執行 lag-1/2/3 Echo 回測，perm p<0.05 才採納
- 注意：539 lag 效應可能因「每日開獎」vs 威力彩「週期性開獎」而有本質差異
- 日期：2026-03-14

**L71 — Multi-lag Markov (lag-2/3) 通過三窗口但均劣於 MidFreq+ACB；lag-2 McNemar 顯著劣於基準 (2026-03-14)**
- 對 5809期 539 全量回測 (1500期 M2+ Edge)：
  - ACB+lag1: +2.99%, ACB+lag2: +2.53%, ACB+lag3: +3.13%, ACB+lag1+2+3: +3.26%
  - MidFreq+ACB 基準: +5.13%（仍為最強）
- McNemar vs 基準：lag-2 顯著差 (p=0.038, n10=187>n01=148)；其他 ns
- 結論：**lag 策略作為獨立2注替換方案不可採納**
- 下一步研究：lag 能否作為第3注提升覆蓋率（需和現行策略的 McNemar 比較）
- 教訓：lag Echo 信號存在但被 MidFreq 均值回歸信號遮蓋，細粒度 lag boost 不如組合策略

**L72 — ACB boundary pool 擴大 (n≤8) 邊際提升 Edge 但 McNemar 不顯著；維持 n≤5 (2026-03-14)**
- b8 1注: +3.20% vs b5 +2.93%（+0.27%）; McNemar p=0.454 → 不顯著
- b8+MidFreq 2注: +5.46% vs b5 +5.13%（+0.33%）; 趨勢正面但未達統計顯著
- 結論：**維持現有 n≤5 boundary bonus，等數據累積後重驗**

**L73 — 今彩539 Zone/Sum 序列是白噪音，ZPI v1 和 v2 全部 REJECT (2026-03-14)**
- 5809期全量 Ljung-Box 檢定：Z1 p=0.168, Z2 p=0.696, Z3 p=0.935, Sum p=0.901 — **全部不顯著**
- 所有 Zone/Sum ACF(lag 1-10) 絕對值 < 0.03，是純白噪音
- ZPI v1（缺口→爆發）lift=1.009-1.134，全部 p > 0.09 → REJECTED
- ZPI v2（動量持續）lift=0.975-1.089，全部 p > 0.13 → REJECTED（之前的「動量持續」推論錯誤）
- Sum 均值回歸：低值後 lag=2 回歸率 54.1%（p=0.062）邊際，未達顯著
- **關鍵教訓：539 的 Zone/Sum 預測邏輯不可從大樂透套用，兩者統計結構根本不同**
  - 大樂透：Sum 均值回歸 Lift=1.495x（顯著），Zone 結構有信號
  - 今彩539：Zone/Sum 完全隨機，任何 Zone-based 策略無效
- 當前 ZPI (2026-03-14): Z1=+13.7, Z2=-12.2, Z3=-1.5（純觀測值，無預測意義）
- **ZPI 研究正式結案，所有版本 REJECTED，不再開發新版本除非有新理論依據**

**L74 — 今彩539 Consecutive Streak 不具可操作信號 (2026-03-14)**
- #05 連續三期 (063-064-065) 是純統計偶發，非系統性模式
- 5809期全量：Streak=1 Lift=1.007（p=0.654），Streak=2 Lift=1.057（p=0.187）
- 門檻要求 Lift > 1.2x + p < 0.05，兩者均遠未達標 → REJECTED
- 個別號碼 #19 Streak=1 Lift=1.264（最高），但單號分析無足夠樣本做策略設計
- 連續回聲（Consecutive Streak）與 Lag-k Echo 是不同概念，但同樣在 539 無效

**L75 — lag-3 作第4注邊際效率分析：接近通過但不確定性高，暫緩 (2026-03-14)**
- 簡化模擬（5509期 walk-forward）：lag-3 新增 47 M3+ hits
- 計算：4th bet M3+/period = 0.853% vs 3-bet平均 0.896%，邊際效率≈95.2%（若正確計算）
- 但：模擬使用近似策略（非真實 acb_markov_midfreq），精度存疑
- 用戶前驗證報告：ACB+lag3 McNemar p=0.108（不顯著），ACB+lag1+2+3 p=0.150（不顯著）
- 結論：lag-3 信號本身統計弱，加入後 McNemar 不顯著，暫緩 → 等 ACB 系列有重大更新後重驗

**L76 — 通過閘門 ≠ 優於現有策略，DEPLOY 條件必須同時滿足「perm p<0.05 + 三窗口不弱於 baseline」(2026-03-14)**
- ZoneRev 2bet：perm p=0.005 通過，但三窗口全弱於 baseline（150p -2.67pp, 500p -0.20pp, 1500p -0.54pp）
- McNemar net=+8（baseline 微優），p=0.456 不顯著
- 分類：OBSERVE（RSM 備選監控），不部署為主要策略
- 教訓：閘門是「必要條件」而非「充分條件」——通過閘門只代表策略有效，不代表比現有更好

**L77 — Per-agent 降權需 200 期以上才有統計支撐 (2026-03-14)**
- 100 期 per-agent 追蹤：weibull_gap=10.00%(-2.82%), markov2=11.00%(-1.82%) 低於隨機基準 12.82%
- 但 100 期差距約 1.3σ，未達統計顯著
- 門檻：**200 期持續低於隨機基準**後才執行降權
- 架構建議：降權應在 StrategyCoordinator 中實作條件性啟用（regime guard），而非直接移除

**L78 — ZoneRev 通過 perm test 但 Zone 白噪音的表面矛盾解釋 (2026-03-14)**
- L73 確認：539 Zone ACF 白噪音（Ljung-Box p>0.17），ZPI 全部 REJECTED
- 但 ZoneRev 策略 perm p=0.005 通過 —— 不矛盾，因為：
  - ZoneRev 選號時結合 MidFreq 分數，Zone 只作為過濾條件
  - 策略有效性來自 MidFreq 成分，Zone reversion 是「無害的額外條件」
  - 但正因 Zone 無信號，Zone 條件無法提升 Edge，導致弱於純 MidFreq+ACB
- 教訓：策略通過回測 ≠ 設計假設成立；分解各成分貢獻才能判斷信號來源

**L79 — ACB × MidFreq 乘積分數失敗根因：兩信號定義互斥 (2026-03-15)**
- H001 假設：乘積分數同時滿足「ACB 高 + MidFreq 高」會更精準
- 實際失敗：ACB 高分 = 冷號（低頻率）；MidFreq 高分 = 中頻號（接近期望）—— 兩定義互斥
- 冷號（freq 低）不可能同時是中頻號（freq 接近均值），乘積強制矛盾條件 → 候選集品質崩潰
- 1500p Edge：Baseline +0.59pp → H001 -0.01pp；McNemar p=0.44 ns
- 教訓：特徵組合前必須先確認各特徵在「高分空間」是否相容，互斥的特徵相乘反效果
- 正確做法：加權平均允許各信號獨立貢獻；乘積只適合兩個指向「同一好方向」的指標

**L80 — 快速 Gate 邊界：數學構造的自相關 ≠ 預測信號 (2026-03-15)**
- H004 Gap Entropy：Ljung-Box p=0.850 → 白噪音 FAST_REJECT ✓（Gate 正確過濾）
- H003 ΔACB：Ljung-Box p=0.000 通過 Gate，但 Top-5 Lift=0.985 < 1.0（低於隨機）
- 根因：ΔACB = freq_300 - freq_30 是滑動窗口差，窗口重疊造成人工自相關，非預測信號
- H006 Cluster：Ljung-Box p=0.000，ACF lag1=0.08，效應偏小需確認
- 教訓：快速 Gate 能篩除白噪音，但無法識別「假性自相關」。數學衍生特徵（差值、比例）需額外「Lift 方向性測試」才算真正通過

**L81 — 弱信號的乘法組合不放大信號，強度過高反退化 (2026-03-15)**
- H002：Markov 條件 boost 乘入 ACB，參數掃描 mult=[0.1~1.0] 全部 McNemar p>0.27
- mult=0.1 最佳（net=+13 p=0.275），mult>0.5 開始退化（mult=0.8: net=-3）
- Markov lag-1 已知弱（Lift=1.134x，boost 改善僅+2 hits/1500 in BL context）
- 根因：乘法修正的效果上限受限於 Markov 信號強度（平均 relative boost ≈ ±20%），不足以改變候選排序
- 教訓：弱信號用乘法疊加不會放大。若信號 Lift < 1.2x，應考慮：(1) 加法補充注，(2) 獨立 agent 低權重，而非乘入主信號
- 正確用法：弱信號作為「並行 agent」（低權重）比乘法修正主信號更有效（已有 markov2 agent 驗證）

**L82 — 539 信號空間窮盡確認（H001~H008 全軍覆沒，2026-03-15）**
- H001(乘積)/H002(條件ACB)/H003(動量)/H004(Gap Entropy)/H005(配對共現)/H007(Fourier w1000)/H008(gap^p) 全部 REJECT
- 核心原因：所有假設都是「頻率信號的變體」，ACB+MidFreq 已充分覆蓋頻率維度
- H005 最乾淨：741對 0對 p<0.05（隨機應有~37對），彩票抽獎獨立性極強
- 改進上限估算：ACB 理論上限 ~3.5-4.5%，現有+2.90%，剩餘空間 <1.5pp，5810期數據不足以統計顯著
- L3 方法論審查觸發：詳見 docs/l3_methodology_review_2026_03_15.md
- 建議：進入維護模式（Monitor Mode）。RSM 監控 + 等待 per-agent 200期數據
- 保留研究：ACB fd/gs 加權比例優化（未系統測試）、H006 Frequency Cluster（最後待決）

---

## Cross-Game Strategy Transfer Study (2026-03-16)

**L83 — MidFreq 信號成功轉移至威力彩 (38C6)**
- MidFreq 在 POWER_LOTTO: edge=+1.27%, z=2.71, perm p=0.010, Cohen's d=2.75 → SIGNAL_DETECTED
- 「反極端頻率」原理（選擇最靠近期望頻率的號碼）在不同池大小間有效
- 39C5 (539) 和 38C6 (威力彩) 池大小接近，信號強度可比
- 教訓：零參數的統計穩定信號（如 MidFreq）比啟發式信號（如 ACB）更易跨彩種

**L84 — ACB 啟發式不可轉移至威力彩**
- ACB 在 POWER_LOTTO: edge=-0.39%, perm p=0.680 → NO_SIGNAL
- 失敗根因：boundary_bonus (n≤6, n≥33) 和 mod3_bonus 是 539 遊戲特性的擬合
- fd×0.4 + gs×0.6 加權比例基於 539 數據掃描，不適用於 6/38 結構
- 教訓：包含硬編碼啟發式（邊界加成、模3加成）的信號本質上是過擬合目標遊戲的

**L85 — 大樂透 49C6 稀釋所有頻率信號至偵測閾值以下**
- 所有 4 信號在 BIG_LOTTO 均未通過 p<0.05: ACB p=0.085, Fourier p=0.139, Markov p=0.388, MidFreq p=0.400
- 49 號碼池 vs 39/38 池：每號期望頻率降低 20%+，信號幅度按比例衰減
- 3注正交 edge=+1.07%, p=0.055 — 接近閾值但未過門
- 教訓：頻率型信號的偵測力受限於池大小。49C6 需要更長歷史（或更強信號）才能區分
- 下一步：嘗試遊戲專屬信號（結構位置、共現配對），而非轉移 539 信號

**L86 — 策略進化在低基準率遊戲嚴重過擬合**
- BIG_LOTTO 300p 進化: +6.51% → full OOS +0.12% (98% 幅度蒸發)
- POWER_LOTTO 300p 進化: +9.17% → full OOS +3.19% (65% 幅度蒸發)
- 539 進化表現較穩定（因基準率 11.4% 高得多，每 300p 有 ~34 命中 vs BIG_LOTTO 僅 ~5-6）
- 根因：低基準率 → 每窗口命中數極少 → 遺傳適應度噪音大 → 進化擬合噪音而非信號
- 教訓：基準率 < 5% 的遊戲，進化 eval_window 至少需 500p（確保 ~20+ 命中事件）

**L87 — 兩款遊戲均不可能正 EV（經濟現實驗證）**
- BIG_LOTTO: base EV=17.38 NTD (cost=50), ROI=-65.24%. 需 +3.50% 邊際才打平（當前最佳 +0.41%）
- POWER_LOTTO: base EV=54.68 NTD (cost=100), ROI=-45.32%. 需 +3.21% 邊際（當前最佳 +2.48%, 77%達標）
- Monte Carlo 10K 軌跡 × 2000 期：兩款遊戲所有初始資金 100% 破產率
- M3+ 獎級太低（400 NTD 對比投注成本）且 M4+ 概率太低，無法從頻率優勢獲利
- 教訓：預測邊際只在「邊際效益 × 對應獎級」足夠大時才有經濟價值。M3+ 邊際需搭配 M4+ 連帶提升才可能正 EV

**L88 — 進化策略通過全閘門不代表超越現有策略（POWER_LOTTO 3注驗證）(2026-03-16)**
- 進化3注 genome (score_blend, gate=midfreq@0.54): full OOS edge=+3.42%, p=0.005, d=4.11
- 三窗口全 PASS (150p=+6.17%, 500p=+7.83%, 1500p=+3.17%)
- McNemar vs fourier_rhythm_3bet: net=+16, p=0.458 — 統計等效，不顯著超越
- 300p 窗口 overfit: 300p=+9.17% → full OOS +3.42%（shrinkage 63%）
- 500p 窗口 re-evolution: 500p=+8.63% → full OOS +3.31%（shrinkage 62%）
- 現有 fourier_rhythm_3bet 300p edge=+3.16%（更穩定，不依賴進化搜尋）
- 教訓：進化搜尋在 M3+ 基準率 ~3.87% 場景中 shrinkage 穩定在 60%+。通過閘門（p<0.05 + 三窗口）≠ 超越現有。部署替換仍需 McNemar p<0.05
- 決策：進化3注作為 ALTERNATIVE 備選，不替換 fourier_rhythm_3bet（L76 原則再次確認）

**L89 — MicroFish 演化特徵工程無法挽救低基準率49C6遊戲 (2026-03-16)**
- BIG_LOTTO MicroFish: 33 特徵, 500p eval window, pop=200, gen=50
- 500p evolution edge: +3.14%, full OOS edge: +0.303% (overfit ratio 10.35x)
- 200-shuffle perm test: p=0.28 → NO_SIGNAL
- MicroFish 與 ACB 完全等效（both +0.303% edge），演化搜尋未發現新結構
- 根因：49C6 M3+ baseline=1.864%, 500p 僅有 ~9 個命中事件，演化只能擬合噪音
- 對比539: MicroFish McNemar net=+17 p=0.132（差3案例即可通過），基準率11.4%→有足夠命中
- 對比POWER_LOTTO: MidFreq p=0.010, Fourier p=0.035, 基準率3.87%→信號可偵測
- 教訓：MicroFish/演化方法的最低可行基準率約 ~3-4%。基準率 <2% 的遊戲，任何演化方法都會過擬合

**L90 — BIG_LOTTO 全信號空間窮盡（2026-03-16）**
- 完整測試 7 個信號族：ACB, MidFreq, Markov, Fourier（通用）+ Regime, P1_Neighbor, MicroFish（專用）
- 零信號通過 p<0.05 驗證門檻：
  - Fourier: +0.414%, p=0.14 (最佳)
  - ACB: +0.303%, p=0.07 (MARGINAL)
  - MicroFish: +0.303%, p=0.28
  - Markov: +0.192%, p=0.42
  - Regime: +0.081%, p=0.27
  - P1_Neighbor: +0.081%, p=0.48
  - MidFreq: +0.081%, p=0.40
- 多注正交 2注 p=0.0697 MARGINAL, 3注 p=0.1244 NO_SIGNAL
- 策略進化 500p 仍 overfit 5-10x (1注 10.35x, 2注 8.39x, 3注 5.18x)
- McNemar vs ts3_regime_3bet: net=-6, p=0.606 — 新策略未改善生產
- 經濟面：ROI -65.24%→-57.52%, 97-100% 破產率
- 結論：大樂透 49C6 正式進入維護模式，與 539 相同
  - 繼續使用 regime_2bet/ts3_regime_3bet/p1_dev_sum5bet 生產策略
  - 未來研究需全新信號家族（非頻率型），或等待池大小/規則變更
- 詳見 `BIG_LOTTO_strategy_report.md`, `big_lotto_strategy_results.json`

**L91 — BIG_LOTTO 49C6 與公平隨機過程統計不可區分（信號邊界研究，2026-03-16）**
- 最終信號邊界研究，6 階段嚴格統計分析：
- Phase 1 信息內容測試（6 項全部 CONSISTENT_WITH_RANDOM）：
  - Shannon entropy: p=0.916（每號熵與理論 Bernoulli(6/49) 一致）
  - Ljung-Box 自相關: binomial p=0.229（49 號中顯著數量不超預期）
  - 頻率穩定性 Chi2: binomial p=0.919（10 期區塊分佈均勻）
  - Wald-Wolfowitz Runs: binomial p=0.710（二元序列獨立）
  - 配對相關 BH FDR: 零拒絕（1176 配對無異常共現）
  - 排列熵: PE_norm=0.9999（極接近理論最大值，最高複雜度）
- Phase 2 信號強度估計：
  - 最佳 MI = 0.006 bits（window_20），佔基線熵 1.18%
  - MC 10K 隨機基線：mean edge=-0.0016%, 99th pct=+0.778%, 99.9th=+1.053%
  - 頻率 oracle（完美後見）：1500p 窗口僅 +0.736%
- Phase 3 方法空間覆蓋：7 族 33 變體 155 參數，覆蓋率 88.6%
- Phase 4 過擬合診斷：
  - 1000 隨機策略：0.0% 達 +3% （train 或 OOS）
  - Bonferroni 門檻 0.0071：7 信號零存活
  - BH FDR：零存活
  - 22 假設中期望假陽 1.1 個，實際觀測 0 個
- Phase 5 偵測天花板：
  - 最小可偵測邊際（power=0.80）：+0.789%
  - 噪音天花板：+0.778%（99th pct）
  - 最佳觀測 +0.414% → **WITHIN_NOISE + BELOW_DETECTION**
- 終極結論：**NO_EXPLOITABLE_SIGNAL**
  - BIG_LOTTO 49C6 在 2117 期數據和完整方法空間下與公平隨機無法區分
  - 最佳觀測邊際在噪音帶內且低於統計偵測極限
  - 永久結案，重新評估條件：數據量翻倍（>4000 期）或遊戲規則變更
- 詳見 `signal_boundary_report.md`, `signal_strength_estimate.json`, `method_space_coverage.json`, `overfit_diagnostics.json`

---

## 威力彩 115000067 研究治理 (2026-03-16)

**L92 — H4 Z1 Drought Detector REJECTED：Z1 空缺後無可操作的均值回歸**
- 假設：Z1(1-12) 連續 ≥2 期空缺後，下期 Z1 回歸概率上升，動態加 Z1 Pool
- 實測：Z1=0 頻率 8.39%（159/1894），Z1=0 後均值 1.950 vs 整體 1.891（Δ=+0.058）
- 策略效益：Z1 Boost 300p/1500p Δ=+0.00%，McNemar 完全無差異
- 結論：Z1 空缺是獨立隨機事件，次期無顯著回歸信號（確認 L11：極端結構不可預測）
- 歸檔：`rejected/h004_z1_drought_power.json`（待建）
- 重測條件：無（永久結案）

**L93 — H9 Pure MidFreq 2注 PROVISIONAL：perm 通過但 McNemar 未達標**
- 假設：近100期最接近期望頻率的12個號碼分2注（Pure MidFreq），優於現役 Fourier proxy
- 原始指標（~1500p）：四窗口 edge 全正，perm p=0.030，McNemar net=+25, p=0.119 ❌
- **2026-04-19 更新（全史 1853p vs midfreq_fourier_2bet）**：
  - H9 windows: 30p=-4.26%, 150p=-2.92%, 300p=-0.26%, 1500p=+1.14%, all=+1.04%
  - MF windows: 30p=-4.26%, 150p=-0.92%, 300p=+0.08%, 1500p=+1.94%, all=+1.48%
  - McNemar (full): b=65, c=73, net=**-8**, p=0.5514 ❌（由 +25 退步至 -8）
  - Perm test: obs_edge=+1.04%, perm_p=1.000 ❌
  - 升格條件：全部未達（net<0, p>0.05, windows 有負, H9 edge < MF edge）
- 狀態：**CONTINUE_SHADOW** — H9 全面劣於 midfreq_fourier_2bet，無升格依據
- 結論：H9 純 MidFreq 優勢原為小樣本雜訊，擴大至全史後優勢消失且反轉
- 重測條件修訂：若 net 重回 +25 以上且 p<0.05 才重新評估，否則維持 SHADOW
- window 靈敏度：w=150 在 300p edge=+2.41% > w=100 的 +0.41%，標記 H13 待驗證

**L94 — fourier_rhythm_3bet 30p 過熱警告（比 6.6x）**
- 30p=+12.16%, 100p=+1.83%, 300p=+3.16%
- 過熱比 30p/100p = 6.6x（警戒線 2x），屬短期爆發型 regime
- 處置：維持上線，下 30 期後重確認（預期均值回歸至 +3~5%）
- 原則：短期爆發不應觸發信心等級上調，亦不應觸發降權（300p 仍正）

**L95 — midfreq_fourier 系列 100p 連續負值監控**
- midfreq_fourier_2bet: 100p=-3.59%, midfreq_fourier_mk_3bet: 100p=-3.17%
- 已累積 ~100p 低於隨機基準，距 L77 降權門檻（200p）還需 ~100p
- 下次評估：115000122（2026-10），若仍負則執行降權標記


**L108 — PP3-Z3Gap CLOSED: 邊際衰退，無升格依據** (2026-04-19)
- 全史 1500p edge = 0.0156，升格門檻 +2.43%
- McNemar vs pp3_4bet: net=-94, p=0.0000
- perm_p = 0.100（MC null，500 shuffles）
- 邊際斜率為負（slope=-0.002954/50p）
- 結論：Z3 high-gap 策略不優於 pp3_freqort_4bet，結案。不再監控。



**L109 — H-PL-04 Consecutive Bonus: 威力彩連號信號無效** (2026-04-19)
- 600p edge=-0.0059, perm_p=0.74
- three_window_pass=False
- 連號出現率=0.759 vs 理論=0.789
- 結論：過去連號頻率無法預測下期連號組合，策略無效。結案。

**L110 — H-PL-02 Mod7: 週期性無效** (2026-04-19)
- 600p edge=0.0041, perm_p=0.36
- 無自相關（Ljung-Box p=0.2187）
- 結論：mod7 週期性不存在或不足以產生穩定邊際。結案。





**L111 — H-PL-01 Gap Pattern: 威力彩 Lag-1 間距信號無效** (2026-04-19)
- 600p edge=-0.0026, perm_p=0.616, three_window_pass=False
- Ljung-Box p=0.9517 → 間距序列無自相關
- structural_bias=True (chi2_p=0.0000, structural_bias=True)
- 結論：號碼間距穩定性無法預測下期選號。結案。

**L112 — H-PL-03 Zone Concentration: 威力彩三區分布信號無效** (2026-04-19)
- 600p edge=0.0024, perm_p=0.446, three_window_pass=False
- Zone autocorr Ljung-Box p=0.1918 → 無時序結構
- signal_coverage=0.012, conditional_edge=0.067
- 結論：三區分布模式無時序可利用信號。結案。

**L113 — 威力彩信號空間宣告窮盡** (2026-04-19)
- 測試假設：H9(REJECT), H-PL-01(FAIL), H-PL-02(FAIL), H-PL-03(FAIL), H-PL-04(FAIL), H-PL-05(FAIL), PP3-Z3Gap(CLOSED)
- combo_B verdict=CONTINUE_WATCH（未升格）
- Ensemble weak signal: FAIL
- 類比 BIG_LOTTO L91：已部署 3 策略（fourier_3bet / pp3_4bet / orthogonal_5bet）持續穩定運行
- 維護模式啟動：停止新假設掃描，僅執行 30p/100p 監控與週期性 drift check
- 重新激活條件：若任一現役策略 1500p edge 下降 > 1.5% 或新資料顯示分布轉移

**L114 — midfreq_fourier_2bet 500期 OOS 升格驗證失敗：McNemar 未過且 150p 轉負** (2026-04-21)
- 驗證範圍：POWER_LOTTO 共 1903 期，最新期數 115000031（2026/04/16）；500期 OOS gate 使用 seed=42、perm shuffles=200
- `benchmark_framework.py`（固定 seed=42）對 `midfreq_fourier_2bet` 給出 150/500/1500p empirical-random edge = +2.67% / +2.00% / +2.40%
- 但升格閘門以 RSM/perm 一致的理論 M3+ baseline(2bet=7.5899%) 判定：150p=-0.92% ❌, 500p=+2.41%, 1500p=+1.94% → 三窗口 FAIL
- Permutation test（最近 500 OOS）: real_rate=10.00%, edge=+2.41%, perm_p=0.0398, Cohen's d=1.997 → SIGNAL_DETECTED ✅
- McNemar vs `fourier_rhythm_3bet`（最近 500 OOS）: midfreq_only=31, fr3_only=45, net=-14, p=0.1359 ❌；未達替換門檻且方向為負
- 對照組近 500 OOS：`fourier_rhythm_3bet` edge=+1.63%，`pp3_freqort_4bet` edge=+3.20%；vs `pp3_freqort_4bet` 的 McNemar 為 net=-39, p=0.00016
- 2注邊際效率：bet1_rate=5.60%, bet2_rate=4.40%, bet2/bet1=78.6% < 80% ❌
- `tools/verify_no_data_leakage.py` 全部通過；本次回測可視為零洩漏有效結果 ✅
- 關聯監控：`midfreq_fourier_mk_3bet` 同期理論 edge 仍為 150p=+1.50%, 500p=+3.63%, 1500p=+2.50%；RSM snapshot 仍是 30p=-1.17%, 100p=-3.17%, 300p=+1.50%, trend=STABLE
- 決策：`midfreq_fourier_2bet` 不可取代、也不可並列 `fourier_rhythm_3bet` 成為獨立 production 2注策略；依本輪任務約束（McNemar 未過不得改 RSM）不修改 `strategy_states_POWER_LOTTO.json`
- 下一步：放棄本輪升格，改研究「PP3 + MidFreq 正交新組合」；若後續要正式標記 REJECTED，需在下一次協調更新時一併處理 RSM 狀態

**L117 — DAILY_539 weekday / calendar overlay 無法形成穩定正交訊號** (2026-04-22)
- H011 研究以 seed=42、N_PERM=200、MIN_HISTORY=300 驗證三個 calendar-only 候選：`weekday_residual_1bet`、`acb_calendar_overlay_2bet`、`acb_markov_calendar_3bet`
- Exploratory screen：weekday 全局 chi-square p=0.9281，39 個號碼中 nominal p<0.05 僅 3 個、Bonferroni survivors = 0；weekday 本體沒有可重現結構
- `weekday_residual_1bet`：150/500/1500p edge = -3.40% / -1.60% / -0.27%，perm p = 0.9602 / 0.7861 / 0.7313，全面 REJECT
- `acb_calendar_overlay_2bet`：raw edge = +1.13% / +3.46% / +2.99%，但 permutation 僅 1500p 過關 (p=0.0149, d=2.162)，150/500p 失敗；對 `midfreq_acb_2bet` 的 McNemar net = -10 / -21 / -39，1500p p=0.0263 且方向為負
- `acb_markov_calendar_3bet`：raw edge = +0.83% / +4.30% / +4.70%，但 permutation 僅 1500p 過關 (p=0.0149, d=2.569)，150/500p 失敗；對 `acb_markov_midfreq_3bet` 的 McNemar net = -10 / -11 / -26，三窗口皆未證明優於現役
- 多注邊際效率雖維持 >80%，但這只證明 bet 結構沒有崩壞，不代表 calendar 訊號成立；真正被否決的是三窗口穩定性與 incumbent superiority

**L118 — DAILY_539 cross-draw cluster / transition 殘差仍不足以突破現役策略** (2026-04-22)
- H012 研究以 seed=42、N_PERM=200、MIN_HISTORY=300 驗證三個跨期叢集候選：`cluster_residual_1bet`、`acb_cluster_overlay_2bet`、`acb_markov_cluster_3bet`
- Exploratory screen：lag-1/2/3 mean overlap = 0.646 / 0.658 / 0.642，幾乎等於隨機基準 0.641；P(overlap>=2) = 0.1143 / 0.1129 / 0.1146，也與隨機基準 0.1140 幾乎一致
- `cluster_residual_1bet`：150/500p raw edge = -2.73% / -1.80%，1500p 僅 +0.53%；perm p = 0.8706 / 0.9204 / 0.2687，Cohen's d = -1.026 / -1.336 / 0.600，單注本體直接 REJECT
- `acb_cluster_overlay_2bet`：raw edge = -1.54% / +1.46% / +3.99%，但 150p 還低於基準且 bet2 邊際效率只有 72.32%；permutation 僅 1500p 過關 (p=0.0050, d=3.105)
- `acb_markov_cluster_3bet`：raw edge = +0.83% / +3.90% / +6.17%，多注邊際效率全過，但 150/500p permutation 分別為 0.6766 / 0.1891、Cohen's d = -0.380 / 0.944，仍未達三窗口穩定正交訊號
- 因三個候選都未同時通過「三窗口全正 + permutation 全窗口 < 0.05 + Cohen's d 全窗口 > 1.0」，本輪無候選進入 McNemar 替換閘
- 教訓：**長窗 raw edge 不是跨期叢集訊號成立的證據。若跨期 overlap 診斷與隨機基準幾乎一致，且 150/500p permutation 不顯著，就應直接判定為「接近信號窮盡」而非繼續微調同家族權重**
- `tools/verify_no_data_leakage.py` 通過，且 H011 自身切片審計確認 train draw/date 永遠早於 target；本次 REJECT 屬有效負結果
- 結論：539 的 weekday / calendar family 在現有資料下不具可部署、也不具 watch 價值的穩定正交訊號；下一輪應改做跨期叢集或彩池規模，不要再重試 weekday 題

**L119 — POWER_LOTTO fourier_rhythm_3bet 的 500p OOS raw Edge 仍正，但 permutation 未過，只能列 WATCH** (2026-04-23)
- 驗證範圍：POWER_LOTTO 共 1903 期，最新期數 115000031；500 期 OOS 區間為 110000053 → 115000031，seed=42、perm shuffles=200
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 全部通過，屬零洩漏有效結果
- 500p OOS 三窗 raw Edge：前150=+4.16%（23/150）、全500=+1.63%（64/500）、近150=+1.50%（19/150）→ 三窗 raw Edge 皆為正
- 但 permutation test（`lottery_api/engine/perm_test.py`）結果為 real_edge=+1.63%、shuffle_mean=+0.39%、shuffle_std=1.44%、perm p=0.209、Cohen's d=0.862、verdict=NO_SIGNAL，未達 p<0.05 與 d>1.0
- 相對 `analysis/results/stage0_baseline.json` 的現役 baseline edge=+3.02%，本次 500p OOS edge 下滑至 +1.63%（-1.39pp）
- 影響模組：`tools/power_fourier_rhythm.py`、`lottery_api/engine/perm_test.py`、`analysis/results/power_fourier_500p_oos_20260423.json`
- 教訓：**威力彩 Fourier 主線即使三窗 raw Edge 全正，也不能跳過 permutation gate。當時序顯著性不足時，結論只能是 WATCH，不得標記為 CONFIRMED。**
- 下一步：Planner 應評估是否進入降權流程，並優先探索 `pp3_freqort_4bet` 降注或 Fourier 正交替代 3 注策略；在新的顯著性證據出現前，不修改 `strategy_states_POWER_LOTTO.json`

**L120 — POWER_LOTTO pp3_freqort_3bet 需靠 dual-score 重排才能守住邊際效率，但 permutation 未過仍只能 WATCH** (2026-04-23)
- 任務背景：目標是為 `fourier_rhythm_3bet` 找到 `pp3_freqort_4bet` 的降注 3 注替代候選，且不得破壞現役 4 注主線
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 全部通過，屬零洩漏有效結果
- A 方案（直接取 `pp3_freqort_4bet` 前 3 注）在 500p OOS 只有 64/500 命中，raw Edge +1.63%，相對同窗 4 注的 +3.20% Edge 僅保留 68.1%，連邊際效率 gate 都未過
- B 方案改為 history-only dual-score 重排：每期先生成 canonical 4 注，再依 `0.35*Fourier + 0.45*residual FreqOrt + 0.20*cold complement` 的 ticket score 取 3 注；500p OOS 三窗為前150=+5.50%（25/150）、全500=+2.83%（70/500）、近150=+2.83%（21/150），1500p OOS 仍有 +3.17%（215/1500）
- 邊際效率：B 方案對 `pp3_freqort_4bet` 的 500p edge retention = 88.5%，per-bet efficiency = 117.8%，成功守住 >80% 效率門檻
- 但 permutation（500p, 200 shuffles, seed=42）結果僅為 real_edge=+2.83%、shuffle_mean=+1.29%、shuffle_std=1.41%、perm p=0.154、Cohen's d=1.089；雖 d>1.0，但 p 未達 0.05，因此仍不得進入 McNemar
- 與 `fourier_rhythm_3bet` 相比，這代表新候選雖在 raw Edge 與 effect size 上都更好（+2.83% vs +1.63%，d=1.089 vs 0.862），但兩者都還停在 WATCH，不足以觸發替換
- 教訓：**威力彩 3 注替代案即使能把 4→3 注的邊際效率守在 80% 以上，若 permutation gate 仍未過，就只能列 WATCH，不能把 raw Edge 改善誤當成可部署替換。**
- 下一步：維持 `fourier_rhythm_3bet` 與 `pp3_freqort_3bet` 同為 WATCH、`pp3_freqort_4bet` 繼續主力；下一輪優先轉向威力彩特別號 V3 改善，而不是提前調整 `strategy_states_POWER_LOTTO.json`

**L121 — POWER_LOTTO 特別號 V3-based V4 正交強化若未超越現役 V3 top2，且 permutation 仍卡在門檻外，就應直接 REJECT** (2026-04-23)
- 任務背景：針對威力彩特別號 V3 做 V4 正交強化驗證，固定 `seed=42`、200 次 permutation，要求 top2 候選在 150 / 500 / 1500 期都維持正 Edge，且全窗口通過 permutation、Cohen's d、邊際效率與 Sharpe 閘門
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 與腳本內部 1500 次切片檢查皆 PASS，屬零洩漏有效負結果
- 共驗證 5 個 V3-based history-only top2 候選：`special_v4_regime_orthogonal_top2`、`special_v4_main_lift_residual_top2`、`special_v4_gap_markov2_balance_top2`、`special_v4_entropy_switch_top2`、`special_v4_bias_modulo_residual_top2`
- 最佳候選 `special_v4_regime_orthogonal_top2` 的 raw Edge 為 150=+5.67%（46/150）、500=+1.20%（131/500）、1500=+1.80%（402/1500），邊際效率與 Sharpe 全過
- 但同一候選的 permutation 仍停在 p=0.0796 / 0.2836 / 0.0547；Cohen's d 雖為 1.563 / 0.652 / 1.614，但 500p effect size 與 150/1500p permutation 仍未全過，因此不具升格資格
- 第二名 `special_v4_gap_markov2_balance_top2` 也只是 150=+6.33%、500=+2.60%、1500=+1.00%，但 permutation 仍為 0.0697 / 0.1393 / 0.2289；同樣只能停在 WATCH
- 現役 V3 top2 參考仍有更高的 raw Edge：150=+11.67%、500=+4.40%、1500=+2.33%，代表這輪 V4 重排連「超越現役基線」都做不到
- 因無任何候選同時通過全部閘門，McNemar 替換檢驗不觸發；結論必須明確標記為 `REJECT`
- 教訓：**特別號 V3 同家族的正交重排若只把 permutation 壓到接近門檻（例如 1500p p=0.0547）但仍未全過，且長窗 Edge 還低於現役 V3 top2，這不是「下一輪再微調」的 WATCH，而是應停止優先投入的 REJECT。**
- 下一步：保留現役 special V3，不修改 `strategy_states_POWER_LOTTO.json`；若要重啟特別號主線，必須帶入新的非同家族特徵來源，而不是再做 drought / Markov / analog / modulo 的權重微調

**L122 — POWER_LOTTO 2 注 regime gate 若只修復 raw Edge 與效率、卻無法讓 150p permutation 過關，仍應直接 REJECT** (2026-04-23)
- 任務背景：針對 `midfreq_fourier_2bet` 做非重跑版升格驗證，要求建立 history-only `midfreq_fourier_2bet_regime_gate_v1`，修正既有失敗點（150p 負 edge、McNemar 未過、邊際效率 <80%），並完成 150 / 500 / 1500 三窗口與 500p OOS McNemar 全套檢定
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 全部通過，屬零洩漏有效負結果
- 候選 gate 為固定優先序：若最近 10 期和值均值 `<114`，bet2 切到 `cold_residual_60`；否則若上一期與最近 30 期 hot-12 重疊 `>=4`，bet2 切到 `hot_residual_60`；其餘維持 baseline Fourier residual。這兩個條件都只用歷史可得特徵，不依賴當期標籤
- 此 gate 確實把 baseline 的 150p 失敗點修回正值：raw Edge 從 `-0.92% / +2.41% / +1.94%` 改善到 `+3.08% / +2.81% / +1.74%`，500p per-bet efficiency 也從 `78.6%` 拉到 `85.7%`
- 但正式 permutation（`lottery_api/engine/perm_test.py`, 200 shuffles, seed=42）仍顯示 150p 只有 `p=0.0995`, `Cohen's d=1.521`；500p / 1500p 雖通過（`p=0.0249 / 0.0249`, `d=2.280 / 2.345`），仍因短窗未全過而不得進入 500p McNemar
- 補充觀察：candidate 在 150p 的主要增益來自低和值 / hot-cluster 分流，但 1500p 反而略低於 baseline（`+1.74%` vs `+1.94%`），代表條件分流主要是在重排命中分布，未能把短窗改善轉成更強的時序顯著性
- 教訓：**威力彩 2 注 regime gate 即使把 150 / 500 / 1500p raw Edge 修成全正、並補回 >80% per-bet 效率，只要 150p permutation 仍未過，就應直接 REJECT，不把條件分流誤當成穩定時序訊號。**
- 下一步：停止把同一個 `midfreq_fourier` 家族的 regime 微調視為主優先升格路線；若要再挑戰 2 注升格，必須帶入新的 bet1 訊號或新的殘餘特徵家族，而不是只在 bet2 上做條件切換

**L123 — POWER_LOTTO PP3 + MidFreq 正交 V2 只留下弱長窗可遷移性，不能視為升格路線** (2026-04-23)
- 任務背景：依本輪 trusted scope，建立 `tools/research_power_pp3_midfreq_orthogonal_v2.py`，以 history-only 的 PP3 殘差分層、FreqOrt 殘差穩定度、跨窗一致性懲罰與 Fourier phase divergence 輔助訊號，驗證 6 個新候選（3bet/4bet 各 3 組），且明確避開 Winning Quality P2-1、special V3/V4 同家族重排與 `midfreq_fourier_2bet` regime gate 微調
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 全部通過，屬零洩漏有效結果
- 全部 6 個候選都完成 150 / 500 / 1500 三窗驗證與 200 次 permutation：`pp3_midfreq_residual_strata_4bet`、`pp3_midfreq_residual_strata_3bet`、`pp3_midfreq_stability_phase_4bet`、`pp3_midfreq_stability_phase_3bet`、`pp3_midfreq_consistency_guard_4bet`、`pp3_midfreq_consistency_guard_3bet`
- 最佳 4 注 `pp3_midfreq_residual_strata_4bet` 的 raw Edge 為 `+2.06% / +2.80% / +2.60%`，但 permutation 僅 1500p 通過（`p=0.5224 / 0.1741 / 0.0448`, `d=-0.002 / 1.002 / 1.770`），且 per-bet efficiency 只有 `71.4% / 73.1% / 65.4%`
- 最佳 3 注 `pp3_midfreq_residual_strata_3bet` 的 raw Edge 為 `+1.50% / +2.03% / +1.57%`，雖 500/1500p 的 Cohen's d 有 `1.095 / 1.313`，但 permutation 仍停在 `0.5075 / 0.1692 / 0.1294`，且 150/1500p per-bet efficiency 只有 `62.5% / 68.8%`
- 全案沒有任何候選同時通過「三窗口全正 + permutation 全窗 <0.05 + Cohen's d >1.0 + per-bet efficiency >80%」，因此 `PASS_TO_MCNEMAR = 0`；正式結論為 `WATCH`（5 候選） / `REJECT`（1 候選），不觸發對 `fourier_rhythm_3bet` 或 `pp3_freqort_4bet` 的 500p McNemar 替換檢驗
- 教訓：**PP3 + MidFreq 正交新家族在威力彩主號上仍有弱 1500p 長窗可遷移性，但無法跨窗、跨 bet-count 穩定轉成可升格訊號；若 150/500p permutation 與 per-bet efficiency 仍未過，就應停在 WATCH/REJECT，而不是再做同家族權重微調。**
- 下一步：若未來重啟主號研究，應引入新的 Layer-1 訊號來源或新的 bet 結構，而不是在同一組 PP3+MidFreq 殘差特徵上繼續做小幅重排

**L124 — POWER_LOTTO PP3 Sum Regime / Sum Reversal 長窗保留弱訊號，但短窗顯著性與 4bet 邊際效率未過時只能列 WATCH** (2026-04-23)
- 任務背景：依 trusted scope，針對 `pp3_sum_regime_detector` 與 `pp3_sum_reversal_filter` 完成 200p 監控 + 150 / 500 / 1500p 正式驗證，固定 `seed=42`、`n_perm=200`，且明確不重跑 WQ P2-1 與 special V3/V4 同家族
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 全部通過，屬零洩漏有效結果
- `pp3_sum_regime_detector` 的 200p / 150p / 500p / 1500p raw Edge 為 `+2.33% / +3.50% / +1.63% / +2.17%`，僅 1500p permutation 過關（`p=0.1791 / 0.2139 / 0.0398`, `d=1.124 / 0.806 / 2.155`）；對 `pp3_freqort_4bet` 的 per-bet efficiency 也只有 `98.7% / 68.2% / 88.6%`
- `pp3_sum_reversal_filter` 的 200p / 150p / 500p / 1500p raw Edge 為 `+0.83% / +2.17% / +1.83% / +2.50%`，同樣只有 1500p permutation 過關（`p=0.3085 / 0.2090 / 0.0100`, `d=0.626 / 0.939 / 2.491`）；對 `pp3_freqort_4bet` 的 per-bet efficiency 為 `61.1% / 76.5% / 102.2%`
- 兩個候選都未同時通過「150/500/1500 三窗全正 + permutation 全窗 <0.05 + Cohen's d >1.0 + per-bet efficiency >80%」，因此 `PASS_TO_MCNEMAR = 0`；對 `fourier_rhythm_3bet` 的替換 McNemar 直接跳過
- 教訓：**威力彩 PP3 的和值家族即使 200p 監控與 1500p 長窗仍保有正 raw Edge，也不能把「只有長窗 permutation 過關」誤當成升格訊號。只要 150/500p permutation 或對 `pp3_freqort_4bet` 的 per-bet efficiency 未全過，結論就只能是 WATCH，不進 McNemar，也不該再保留 provisional 幻覺。**
- 下一步：停止把 PP3 Sum family 視為優先升格路線；若要再挑戰 3 注升格，必須引入新的 Layer-1 訊號來源或新 bet 結構，而不是再微調 sum threshold / reversal constraint

**L125 — DAILY_539 pool-size / market-behavior 題在 trusted active data 缺欄位時，應直接產出資料可用性 REJECT** (2026-04-23)
- 任務背景：依 trusted scope 驗證 `H013 pool_size_regime`、`H013b pool_growth_shock`、`H013c pool_size_x_existing`，要求固定 `seed=42`、`n_perm=200`、完成 150 / 500 / 1500 三窗口與 leakage audit，且不得重跑 H011/H012 或 H001~H008 家族
- 研究腳本 `tools/research_daily539_poolsize_h013.py` 先用 `lottery_api.database.DatabaseManager` 從 `lottery_api/data/lottery_v2.db` 讀取 `draws`，確認 schema 有 `jackpot_amount` 欄位，但 `DAILY_539` 全量 5839 期中 `jackpot_amount = NULL` 的比例是 `5839/5839`，coverage = `0.00%`
- 依同一資料庫抽查三個正式窗口所需尾段 history span：150 期需要最近 450 期、500 期需要最近 800 期、1500 期需要最近 1800 期；三者的 non-null pool observations 全部都是 `0`
- `tools/verify_no_data_leakage.py` 與腳本內部 H013 slice audit 皆 PASS，表示問題不是切片或時序洩漏，而是 trusted active data 根本沒有可用的外生 pool-size 序列
- 進一步檢查 ingestion contract：`lottery_api/fetcher/taiwan_lottery_fetcher.py` 的 row normalization 只回傳 `{lotteryType, draw, date, numbers, special}`，沒有 pool / sales / jackpot 欄位，因此無法在不造假 proxy 的前提下建立 history-only 的 `pool_size_regime` 或 `pool_growth_shock`
- 教訓：**539 的 pool-size / market-behavior 題若 trusted active data 沒有 pool/sales 欄位，結論應明確標記為 data-availability REJECT，而不是硬套代理變數或把空欄位題目包裝成 signal failure。**
- 下一步：若要重啟 H013，只能先做 trusted ingestion/backfill，把可驗證的 pool-size 或 sales 欄位寫入 active data；在此之前不得重派同家族驗證

**L126 — POWER_LOTTO WATCH 主線若長窗仍有訊號、但 5x300 rolling permutation 大面積失敗，應降權而非誤升或硬拔除** (2026-04-23)
- 任務背景：針對 `fourier_rhythm_3bet` 做 failure-aware 的 8 小時決策驗證，固定 `seed=42`、`n_perm=200`，要求補齊 150 / 500 / 1500 正式驗證、5 個不重疊 300 期 rolling OOS 切片，並同時檢查唯一替代候選 `pp3_freqort_3bet` 是否具備升格前置條件
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 全部通過，屬零洩漏有效結果
- `fourier_rhythm_3bet` 的 150 / 500 / 1500p raw Edge 為 `+1.50% / +1.63% / +2.57%`，Permutation 為 `p=0.4975 / 0.2537 / 0.0100`，Cohen's d 為 `0.085 / 0.654 / 2.410`；表示長窗 1500p 仍保留時序訊號，但短中窗顯著性不足
- failure-aware 5x300 rolling OOS 切片全都維持正 raw Edge（`+1.17% / +2.17% / +5.83% / +2.83% / +0.83%`），但只有 slice_3 通過 permutation（`p=0.0199, d=2.411`），其餘 4 個切片皆失敗；最新 slice_5 更只剩 `p=0.5274, d=0.036`
- 這代表降權觸發來自「rolling temporal significance collapse」，而不是 raw Edge 直接翻負：在本輪量化規則下，`permutation_fail_ratio >= 0.8` 即應把 target 從主監控 WATCH 降為低優先 WATCH，但因 150 / 500 / 1500 raw Edge 仍全正，也不應直接判成 REJECT
- 替代候選 `pp3_freqort_3bet` 雖在 150 / 500 / 1500p raw Edge 為 `+2.83% / +2.83% / +3.17%`，且 1500p permutation 已過（`p=0.0050, d=2.822`），但 150p per-bet efficiency 只有 `79.89%`、150 / 500p permutation 仍失敗，因此 McNemar 不觸發，不能替換主線
- 教訓：**當 WATCH 主線長窗仍保留訊號，但 rolling 300p 切片有大面積 permutation 失敗時，正確動作是「降權留 WATCH + 轉向新 Layer-1 家族」，而不是因 raw Edge 全正就維持優先級，也不是在沒有替代者通過全部閘門時直接拔除主線。**
- 下一步：停止延伸現有 Fourier / PP3 / midfreq / special 同家族微調；若要重建 POWER_LOTTO 3bet 主線，必須引入新的非同家族 Layer-1 訊號來源

**L127 — POWER_LOTTO 非同家族 Layer-1 3bet 若只有 raw Edge 全正、但 permutation 與 4bet 邊際效率仍不過，整體結論應直接 REJECT_ALL** (2026-04-23)
- 任務背景：依 trusted orchestrator contract，驗證威力彩主號 3 注四個非同家族 Layer-1 history-only 候選：`dispersion_state_transition_3bet`、`odd_tail_imbalance_3bet`、`zone_transition_tensor_3bet`、`residue_structure_stability_3bet`；固定 `seed=42`、`n_perm=200`，並要求 150 / 500 / 1500 三窗口全部評估、對 `pp3_freqort_4bet` 的 per-bet efficiency >80%、通過 permutation / Cohen's d，才可觸發對 `fourier_rhythm_3bet` 的 McNemar
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 全部通過，且 leakage transcript 已保存到 `analysis/results/power_layer1_nonfamily_3bet_leakage_check_20260423.txt`
- 四個家族都完成正式驗證，其中三個候選的三窗口 raw Edge 皆為正：`dispersion_state_transition_3bet` = `+2.83% / +1.23% / +1.57%`、`zone_transition_tensor_3bet` = `+1.50% / +1.43% / +0.97%`、`residue_structure_stability_3bet` = `+2.17% / +3.23% / +1.77%`；`odd_tail_imbalance_3bet` 也有 `+0.83% / +0.83% / +0.77%`
- 但 permutation 沒有任何候選能全窗口壓到 `p < 0.05`：dispersion = `0.2886 / 0.5473 / 0.3184`，odd-tail = `0.3881 / 0.5871 / 0.4726`，zone = `0.2587 / 0.2090 / 0.4030`，residue = `0.4030 / 0.1194 / 0.2189`
- Cohen's d 也只有 `residue_structure_stability_3bet` 在 500p 達到 `1.393`；其餘窗口與候選都停在 `<=1.0`
- 對 `pp3_freqort_4bet` 的 per-bet efficiency 更沒有任何候選三窗口全過 80%：最佳 residue 仍只有 `61.1% / 134.9% / 72.2%`，zone 僅 `42.3% / 59.8% / 39.5%`
- 因此四個候選全部卡在 McNemar 前置閘，對 `fourier_rhythm_3bet` 的替換檢定完全不觸發；正式總結必須是 `REJECT_ALL_NONFAMILY_LAYER1_3BET`
- 教訓：**威力彩 3 注新家族即使能把多個候選的三窗口 raw Edge 同時拉正，也不能把這種「edge-only 好看」誤當成可升格訊號。只要 permutation 與對 `pp3_freqort_4bet` 的 per-bet efficiency 仍無任何候選全窗過關，正確結論就是整體 REJECT，而不是把其中最佳者包裝成 provisional。**
- 下一步：若要繼續挑戰 `fourier_rhythm_3bet`，必須引入新的特徵來源、外生資料或不同 validation 設計；不應立刻重跑 dispersion / odd-tail / zone-transition / residue-stability 這四個家族的微調版

**L128 — DAILY_539 MicroFish+MidFreq 2-bet 若短窗 McNemar 未過，就算三窗口 raw Edge / permutation / 邊際效率全過也不得升格** (2026-04-23)
- 任務背景：依 trusted orchestrator contract，對 `microfish_midfreq_2bet` 做正式升格驗證；active-code mapping 依 `tools/production_validation.py` 定義為 `MicroFish+MidFreq 2-bet`，即 bet1 使用 active MicroFish genome（本輪 `validated_strategy_set.json` top-1：`freq_zscore_80`、`freq_raw_150`、`freq_zscore_150`、`tail_entropy_10`、`markov_lag3_100`、`ix_gap_ratio_100_x_zone_deficit_100`、`ix_freq_deficit_100_x_ac_mean_100`、`nl_sq_entropy_binary_100`），bet2 使用排除 bet1 後的 MidFreq；對照現役為 `midfreq_acb_2bet`
- 固定使用 `ORDER BY CAST(draw AS INTEGER) DESC` 從 `lottery_api/data/lottery_v2.db` 取數，轉 ASC 後以 `history[:target_idx]` 做 walk-forward；`tools/verify_no_data_leakage.py` 與腳本內 slice audit 全部 PASS，且 leakage transcript 已保存到 `analysis/results/daily539_microfish_midfreq_promotion_no_leakage_20260423.txt`
- 候選在 150 / 500 / 1500p 的 raw Edge 分別為 `+11.79% / +11.06% / +7.33%`，對照現役 `midfreq_acb_2bet` 為 `+8.46% / +8.26% / +5.53%`；三窗口都保有正向 edge 優勢
- permutation 也全窗口通過：候選 `p=0.0050 / 0.0050 / 0.0050`，Cohen's d=`2.885 / 5.300 / 6.376`；bet2 邊際效率則為 `164.37% / 149.90% / 124.92%`，形式上已滿足升格前四道閘
- 但與現役的 McNemar 結果為 150p=`p=0.1797`, net=`+5`；500p=`p=0.0201`, net=`+14`；1500p=`p=0.0132`, net=`+27`。也就是說中長窗已呈現統計優勢，但短窗 150p 仍未證明穩定替換能力
- 因 trusted wiki 對 539 的 MicroFish 路徑明確要求「只有在 McNemar 驗證可穩定優於 MidFreq+ACB 時才可升格」，本輪結論必須是 `REJECT`，且維持 `midfreq_acb_2bet` 為現役 2 注主線
- 教訓：**539 的 MicroFish+MidFreq 2-bet 不能只看 raw Edge、permutation 與 per-bet efficiency。只要 150p McNemar 還沒有正式證明短窗穩定優於 `midfreq_acb_2bet`，就應視為「尚未取得 replacement proof」，結論必須維持 REJECT，而不是因為三窗口表面更強就提前升格。**
- 下一步：若要重啟同題，只能做 failure-aware 監控或等待新的外生/正交訊號來源；不應在現有 MicroFish + MidFreq 架構上再做同家族微調就宣稱可替代 incumbent

**L129 — DAILY_539 pool-size 題即使補齊 100% trusted data，也不保證產生預測訊號** (2026-04-23)
- 任務背景：DAILY_539 H013 pool-size / market-behavior 驗證，於 2026-04-23 完成 100% 數據補齊
- 數據補齊詳情：原始 DAILY_539 記錄 5839 期中 jackpot_amount 欄位 0% 覆蓋；從官方台灣彩券 API（api.taiwanlottery.com/TLCAPIWeB）回溯補齊 sell_amount 與 total_amount，最終達成 100% 覆蓋（2007-01-01 至 2026-04-23 全期）
- 驗證架構：H013（pool-size regime + ACB overlay 1 注）、H013b（pool growth shock + MidFreq+ACB overlay 2 注）、H013c（pool-size quartile + Markov-MidFreq 3 注）；三窗口 150 / 500 / 1500 期全部評估
- 正式驗證結果：
  - H013：edge ≈ 0%、p=1.0、Cohen's d ≈ 0（全窗口）
  - H013b：edge ≈ 0%、p=1.0、Cohen's d ≈ 0（全窗口）
  - H013c：edge ≈ 0%、p=1.0、Cohen's d ≈ 0（全窗口）
- **核心發現**：Pool-size 與市場行為特徵對 539 數字生成無預測力；不是數據不足造成的可用性 REJECT，而是基礎假說本身不成立
- 教訓：**外生市場特徵（如彩池規模、銷售金額）在某些彩遊中可能無任何時序預測價值。取得 100% 完整數據後如果仍是 p=1.0 邊界，應直接確認假說失效，不應為了「數據終於完整」就強行解釋。**
- 下一步：停止投入 pool-size / market-behavior / sales-related 類研究方向；若要探索外生信號，應限制在「規則變更相關」（如頭獎機率改變、號碼規則調整）

**L130 — POWER_LOTTO Winning Quality P2-1 popularity_score 代理模型跨窗口不穩定** (2026-04-23)
- 任務背景：WQ P2-1（基於 winning_quality.py 中 popularity_score() 估算號碼人氣，預期低人氣組合分獎人數少、單注收益更高的 3 注策略）正式驗證
- 驗證架構：150 / 500 / 1500 期三窗口，對照 fourier_rhythm_3bet 與 pp3_freqort_4bet，評估 raw Edge、permutation、Cohen's d、per-bet efficiency
- 結果摘要：
  - 150p：raw Edge +12.01%、perm p=0.0667（邊界）、d=1.281（通過）、efficiency 163.6% / 168.3%
  - 500p：raw Edge +7.74%、perm p=0.6333（未過）、d=-0.246（未過）、efficiency 130.3% / 100.9%
  - 1500p：raw Edge +7.47%、perm p=0.8000（未過）、d=-0.935（未過）、efficiency 112.0% / 97.5%
- **核心發現**：150p 單窗雖示出統計邊界訊號，但 500p / 1500p 時 permutation 與 effect size 完全失效；表示訊號非跨窗穩定的真實時序特徵，而是 150p 窗口內的幸運波動
- 後續嘗試改進無果：popularity_score 作為人氣代理主要基於啟發式估算（非真實頭獎分配數據），無真實商業資料支撐時無法形成穩定的分獎優化訊號
- 教訓：**商業 proxy（如人氣估算）作為分獎過濾時，跨窗口訊號不穩定是常見現象。若只有短窗統計邊界，且無法用真實資料（如真實中獎者數、真實單位獎金）驗證因果鏈，應直接判定為無可操作訊號。**
- 下一步：若要改進分獎優化，需要從「真實頭獎金額/中獎人數資料」而非啟發式人氣估算入手；當前工具集無此數據來源，此方向達驗證上限

**L131 — 三彩種全域信號窮盡審計結論（2026-04-23）** 
- 審計範圍：BIG_LOTTO、DAILY_539、POWER_LOTTO 三個彩遊全面信號耗盡檢查
- BIG_LOTTO：L90/L91 已確認全信號空間窮盡；2026-04-23 500 期監控報告確認無新 McNemar 替換候選；維持維護模式
- DAILY_539：H001~H008（L82）已全部 REJECT；H011（L117）、H012（L118）、H013（L129）、MicroFish（L128）於 2026-04-22 至 2026-04-23 期間依序完成驗證均 REJECT；頻率族信號空間高度飽和；維持維護模式
- POWER_LOTTO：主線 Fourier + PP3 + Orthogonal 成熟穩定；recent cycle（2026-04-23）測試 13 個新候選方向（Fourier downgrade、PP3 3bet、Sum Regime / Reversal、MidFreq regime gate、Orthogonal V2、nonfamily Layer-1 4 family、Special V3/V4、WQ P2-1），全部評定為 WATCH / PROVISIONAL 或 REJECT，無任何候選進入 McNemar 替換閘
- 核心結論：**三彩種在既有驗證框架（150/500/1500p 窗口、permutation test、McNemar gate、per-bet efficiency >=80%）與現有數據源下，已無可行升格訊號。所有主要假說家族（頻率、規則邊界、正交補注、市場外生、新結構）均已驗證；延伸尋優空間接近飽和。**
- 後續啟動新研究的前置條件：
  1. 外部條件變化（彩遊規則調整、號碼池大小變更、開獎頻率改變）
  2. 新認證數據源（真實獎金分配、真實中獎人數、官方池大小即時資料）
  3. 全新非同家族訊號假說（與現有 PP3/Fourier/MidFreq/Special 正交的完全新特徵來源）
- 教訓：**信號窮盡審計是策略研究的終點檢查。一旦確認「三窗口驗證 + 多家族搜索 + McNemar 閘 + 漏洩檢查」全部通過卻無候選晉級，表示當前假說集已耗盡。後續重啟應明確針對新信號源或新框架，而非在既有假說空間內無限微調。**
- 下一步：維持現役策略組合監控；暫停主動研究直至上述三項前置條件之一成立



**L132 — 循環匹配偏誤（Circular-Match Bias）導致假陽性 SIGNIFICANT（2026-05-01）**
- 任務背景：建立「預測號碼 vs 歷史開獎最佳命中期比對」分析管道（v1），用 Monte Carlo 顯著性檢定
- v1 方法（INVALID）：對每筆預測 P_T 掃描整個歷史 pool H[<T]，找 max_hit；MC baseline 用 uniform random
- 結果：POWER_LOTTO max_hit=6 觀察 231 次 vs 模擬期望 5 次（46x baseline，p=0.001）→ SIGNIFICANT（假陽性）
- 問題根源（循環匹配偏誤）：
  - 策略 P_T 本身是從 H[<T] 萃取的熱號/冷號/共現對
  - 將 P_T 掃過 1000+ 期 H[<T]，找到一期 6 個號全被開出，只代表「歷史曾有一期與策略偏好完全重合」
  - MC baseline（uniform 抽樣）不複製「從同一 pool 萃取」的 selection bias，baseline 嚴重偏低
  - 這是 LOOK-AHEAD BIAS 的同構變形：不是時間洩漏，而是「自己 vs 自己映射域的循環匹配」
- v2 修正方法（predict-vs-actual）：
  - 每筆 P_T 只與實際 target draw T 比對（單一目標，不是 pool）
  - 以 shuffle target_draw_ids 做 permutation null
  - 加 Bonferroni 跨遊戲校正 + BH-FDR 跨策略校正
  - 最終結論：兩遊戲、所有策略 → NO SIGNAL（預期中：合法彩票無記憶性）
- 處理：v1 輸出於 outputs/prediction_hit_analysis/INVALID.md 標記 INVALID；v2 SOP 進 wiki
- 教訓：
  1. 「預測 vs 歷史 pool 最大命中」不等於「預測能力」；後者必須是「預測 vs 實際目標期」
  2. MC baseline 必須複製與觀察分析相同的 selection mechanism，否則 p-value 無意義
  3. 任何命中率高到「破解彩票」程度的結果，必須先懷疑 baseline 設計，不是先慶祝
  4. 多重比較校正（Bonferroni/BH-FDR）是必要步驟，不是選項
  5. v1 INVALID 結果禁止進 wiki（即使加警告標籤也不行）
- 正確工具：scripts/predict_vs_actual.py；SOP：wiki/system/predict_vs_actual_sop.md

## L133 — Lottery draw-process randomness confirmed (2026-05-01)
- Formal audit (phases 1-6) found no significant deviation from uniform random after multiple testing correction
- NO SIGNAL from predict-vs-actual is consistent with draw-process randomness
- Future strategy claims must pass: (1) draw-process audit, (2) predict-vs-actual, (3) permutation null, (4) multiple testing correction, (5) circular-match bias check
- Tools: scripts/randomness_audit.py; SOP in wiki/system/randomness_audit_sop.md

##  H6 is valid but non-monetizable (2026-05-05)L134 
ew85 has confirmed +4.00pp edge at 3000p OOS (p<0.001 permutation test)
- Edge is statistically real, long-window stable (STABLE_LONG_WINDOW), and reproducible
81.29% ROI; H6's extra EV covers only 1.2% of the structural deficit
- Lesson: a confirmed statistical edge does NOT imply positive ROI in lottery context
- Classification: VALID_SIGNAL_NON_MONETIZABLE

##  M2+ edge is not equivalent to profitable edge (2026-05-05)L135 
 net profit = 0 NTD per M2 hit
- 91.19% of all M2+ hits are M2-only (break-even events)
- Measuring M2+ hit rate inflates apparent "edge" without measuring profitability
- Correct measure: M3+ hit rate, or better: net EV per draw
- Lesson: Always decompose hit rate by prize tier before claiming profitable edge

T4 promotion (2026-05-05)
- A strategy may pass all validation gates (permutation, McNemar, OOS) and still fail to produce positive ROI
- Payout EV analysis (cost vs expected payout by prize tier) must be completed before any production recommendation
- This is now an explicit gate in wiki/system/strategy_retirement_policy.md (R04)
- Reference: outputs/daily539_payout_ev_analysis.md

##  Lottery research should stop after scientific closure (2026-05-05)L137 
- Three formal signal-exhaustion audits + draw-process randomness audit confirm: no new research directions
- Continuing to mine without new external data or new feature source is p-hacking with extra steps
- Formal closure declared in outputs/research_closure_report.md
- All three games enter governance/maintenance mode from 2026-05-05 onwards
- Lesson: know when to stop; closure is a scientific output, not a failure

##  Future strategy proposals require Hypothesis Registry (2026-05-05)L138 
- Post-hoc hypothesis mining is permanently forbidden (retirement condition R09)
- Any new backtest must be preceded by a Hypothesis Registry entry with pre-registered signal, expected effect direction, and minimum sample size
- This prevents p-hacking and circular reasoning from accumulated backtest attempts
- Lesson: if you didn't pre-register it, it's exploratory, not confirmatory

##  historical-pool max-hit remains forbidden (2026-05-05)L139 
- The historical-pool max-hit evaluation method (comparing predictions to largest-overlap pool from historical draws) creates circular-match bias (L132-related)
- This inflates apparent hit rates to appear lottery-breaking, which is LOOK-AHEAD BIAS
- PERMANENTLY FORBIDDEN for all games, all future tasks
- Reference: wiki/system/forbidden_strategy_patterns.md (Trusted Wiki; outputs/ version SUPERSEDED 2026-05-07)

##  Production betting/outcome-write requires human review (2026-05-05)L140 
- No agent or script may write production betting outcomes, execute rollbacks, or modify lottery_v2.db without explicit human confirmation
- Rollback guard (MIN_OUTCOMES=5, MIN_CONSECUTIVE=3) enforces this automatically for H6
- For all other changes: add --dry-run step, obtain human sign-off, then execute
- Lesson: automated systems should gate, not execute, irreversible production changes

##  Enforcement layer required before every strategy eval report (2026-05-07)L141
- `enforce_strategy_evaluation_contract()` MUST be called in `cli.py` before `_build_report()` on every execution path
- `GovernanceViolationError` is the single error class for governance violations — only `tools/strategy_eval/enforcement.py` may raise it
- Enforcement result is stored in `report["enforcement"]` and is part of the governance audit trail
- Lesson: hard-code the enforcement call; never let report writing happen without it

##  Classification must go through classification_guard.py (2026-05-07)L142
- `classify_evaluation()` is the ONLY authorised path to a formal classification
- No report writer, script, or agent may assign a classification string directly
- `validate_classification()` rejects unknown strings — provides hard guard against typos and hallucinations
- Lesson: centralise classification logic; never scatter string literals across the codebase

##  DRY_RUN_ONLY and INSUFFICIENT_METADATA are NOT NO_VALIDATED_EDGE (2026-05-07)L143
- `DRY_RUN_ONLY`: evaluation ran in test mode, no statistical evaluation performed — NOT a signal conclusion
- `INSUFFICIENT_METADATA`: evaluation had missing metadata, cannot formally classify — NOT equivalent to "no edge found"
- `NO_VALIDATED_EDGE`: statistical evaluation complete, p >= 0.05 — this IS a formal conclusion
- Confusing these three inflates false negatives and masks data quality problems
- Lesson: three distinct states for three distinct failure modes; never collapse them

##  CANDIDATE_SIGNAL always escalates to REQUIRES_HUMAN_REVIEW (2026-05-07)L144
- `CANDIDATE_SIGNAL` is an intermediate classification — it is never the final output
- Any result with p < 0.05 + OOS data confirmed immediately becomes `REQUIRES_HUMAN_REVIEW`
- `REQUIRES_HUMAN_REVIEW` is a mandatory human gate; no auto-promotion is allowed
- Lesson: signal detection triggers human review, not automatic promotion

##  governance hard-lock modules and forbidden patterns locked (2026-05-07)L145
- Governance hard-lock completed for `module_boundaries` and `forbidden_strategy_patterns`; these are now trusted wiki controls, not optional guidance
- Leakage detector integration with RollingBacktester completed; this boundary and linkage must not be reworked without explicit governance change
- Lesson: treat this as closed P0 supervisor work; do not reopen or re-implement the same hard-lock task

##  P0.4 Replay Usability made history_cutoff user-visible (2026-05-07)L146
- P0.4 replay usability polish completed, including row drilldown, causal status display, and URL persistence
- `history_cutoff` is now user-visible in replay details and therefore part of product-level integrity, not just backend metadata
- Lesson: any replay-data hygiene drift now becomes a user-facing governance risk immediately

##  replay cutoff snapshot 460 clean, gate-first framing (2026-05-08)L147
- Replay DB snapshot: cutoff snapshot 460 rows, 0 missing history_cutoff_draw, 0 cutoff>=target violations
- Current state is clean; follow-up priority changed to CI gate-first for replay integrity rather than emergency repair
- Lesson: run integrity gate continuously and keep backfill as contingency-only tooling

##  randomness cadence gate added for stale-audit risk (2026-05-08)L148
- Last randomness audit run observed at 2026-05-01; cadence gate added to prevent silent staleness
- Policy v0.1 uses 14 calendar days or 50 draws (whichever first) as stale threshold
- Lesson: randomness audit cadence gate must stay active in CI to mitigate R04

## REPLAY_GOLIVE_READY_20260508 (2026-05-08)
- G1 PASSED: tests/test_replay_api_contract.py — 25 tests (freshness/summary/history contract + 3 deliberate-failure probes)
- G2 PASSED: docs/REPLAY_OPERATION_SOP.md created; wiki/system/replay_data_hygiene.md §9 pointer added
- G3 PASSED: scripts/snapshot_replay_db.py — snapshot written to outputs/db_snapshots/ with SHA256
- G4 PASSED: tests/test_replay_freshness_cadence.py — 8 tests; cadence policy v0.1 (≤14 days) added to wiki §3.2
- All 4 pre-go-live gates green. Replay API declared go-live ready.

## P0 Replay Release Marker Evidence — 2026-05-08

- P0_3_VERIFIED
  - Evidence: memory/lessons.md lessons sync; confirmed entries at L145 (P0.2 replay schema), L146 (P0.3 usability polish), L147 (cutoff snapshot 460 clean), L148 (randomness cadence gate). Keywords present: module_boundaries / forbidden_strategy_patterns / P0.4 / cutoff snapshot 460 / cadence gate.

- P0_4_REPLAY_BROWSER_SMOKE_VERIFIED
  - Evidence: tests/test_replay_browser_smoke.py, 30 passed (P0-6 freeze validation run 2026-05-08).

- P0_6_WORKTREE_DELTA_RELEASE_HANDOFF_FREEZE_VERIFIED
  - Evidence: outputs/replay/p0_replay_release_handoff_20260508.md, freeze validation 89 passed, 0 failed (P0-6 run 2026-05-08).

- REPLAY_GOLIVE_READY_20260508
  - Evidence: tests/test_replay_api_contract.py 25 passed; tests/test_replay_freshness_cadence.py 8 passed; docs/REPLAY_OPERATION_SOP.md; scripts/snapshot_replay_db.py. Recorded in memory/lessons.md under REPLA  - Evidence: tests/test_replay_api_contract.py 25 passed; tests/test_replay_freshnessEE_DELTA_RELEASE_HANDOFF_FREEZE_VERIFIED

---

## P219 外部10法診斷掃描 (2026-06-05)

**L_P219_A — 外部10法掃描全 predictive-NULL（再次確認 L82/L91/P178A/P236A）**
- 10 method families × 5 games = 44 multiplicity-corrected tests，pre-registered（P221F），統計單位=distinct real draws，全 MC/permutation 經驗 p。
- 三個 forward-predictive 家族（M5 Dirichlet / M8 freq-generator / M9 conformal）在所有 5 遊戲全 NULL：最佳 edge=BIG_LOTTO +0.49pp p=0.226（且在污染資料上），539/POWER edge 為負（L101 unconditional dilution），conformal set 比 trivial 還大。
- M10 bottleneck：MI(trailing-freq→next-hit) 在 clean 遊戲 ≈ 8.8e-6 bits（539）/ 1.6e-5（POWER），遠低於 min-detectable-edge（~1.7–2.2pp）。channel 為空，無 bottleneck 可拓寬。
- Evidence: analysis/p219_external_method_diagnostic_sweep.py; outputs/research/p219_external_method_diagnostic_sweep_20260605.{md,json}; tests/ 10/10 PASS.

**L_P219_B — BIG_LOTTO `draws` 表嚴重資料污染（核心發現，非預測信號）**
- BIG_LOTTO 22,238 列中僅 ~2,113 為可信 6/49（吻合 canonical「≈2,118 期」）。污染來源 ≥3：19,100 模擬列（hyphen 複合 ID `103000009-01..-100`）、375 date-format 異種（sum 74.7±2.4, max≤24, ID `20YYMMDD`）、~650 小池異種（2011-2014, max≤25, sum dip 至 ~100）。
- 任何 BIG_LOTTO 分析若用 raw `draws` 將被污染；統計單位必須 = distinct real 6/49 draws。
- Evidence: outputs/research/p219_..._20260605.md §4；read-only DB 重現（clean-set re-run + block trajectory + 539 control）。

**L_P219_C — drift/changepoint 偵測到的是「資料管線斷點」而非「彩票偏差」（anomaly≠predictor 實證）**
- 唯一通過 Bonferroni/BH 的 test 全在 BIG_LOTTO（M1 overlap, M4 CUSUM 11×null, M2 gap 4×, M3 drift 4×, M6 entropy/compression）+ 1 個弱 DAILY_539:M3_drift（BH-only, Bonferroni-FAIL, 1.2×, 無 M1/M4 佐證 → borderline false positive）。
- 移除 375 date 列後信號仍在（剩 650 小池列）→ 證明多重污染源。DAILY_539 為 clean+stationary 對照（10 blocks sum~100/max~33 全平）→ 方法不會在乾淨資料上製造假信號。
- 教訓：M3/M4 類偵測器對 mixed-source / non-stationary 歷史紀錄會「正確地」觸發，但偵測的是資料異質性，對下一期號碼零預測力。掃描出 corrected-significant ≠ 可利用 edge（L76 再確認）。

**L_P245B_A — P245B 確立偏差閘門架構（sequential e-value + BOCD + 多重校正 + 資料完整性）**
- 依賴 P236A/P237C/P238B/P219；P245A 缺席（不依賴）。
- 當前閘門狀態：539/POWER/3_STAR/4_STAR = GATE_YELLOW_OBSERVATION_ONLY（P238B），BIG_LOTTO = GATE_RED_DATA_CONTAMINATION（P219）。
- GATE_OPEN 需 e-value K≥100 + BOCD 同位確認 + 乾淨資料稽核 + ≥500 clean OOS draws + 獨立複驗窗口 + Bonferroni 通過 + 人類明確授權 + 研究任務預先登記——當前零條件達成。
- anomaly detection is NOT prediction；GATE_OPEN 仍不授權生產建議/下注建議/registry mutation。
- Evidence: outputs/research/p245b_bias_gate_layer_20260605.{md,json}; tests/ 24/24 PASS.

---

## P246 BIG_LOTTO Data-Integrity Audit (2026-06-05)

**L_P246_A — BIG_LOTTO draws table confirmed ~90.5% contaminated (3 families, fully quantified)**
- Total: 22,238 rows. Canonical plausible: 2,113 (≈2,118 expected; delta −5). Contaminated: 20,125 (90.5%).
- Family 1 — SIM_HYPHEN: 19,100 rows (85.9%). Hyphen composite IDs (103000009-01…-100). Excluded by P219 NOT LIKE '%-%' filter.
- Family 2 — DATE_FORMAT_ALIEN: 375 rows (1.7%). YYYYMMDD date-literal IDs (20090727). sum~74.7, max≤24 — NOT 6/49.
- Family 3 — SMALL_POOL_ALIEN: 650 rows (2.9%). Serial IDs but max(numbers)≤25 (~23.5% of serial rows). Likely 6/38 or older format mislabeled. Primary driver of all P219 structural-break signals.
- Evidence: analysis/p246_big_lotto_data_integrity_audit.py; outputs/research/p246_…20260605.{md,json}; 23/23 tests PASS.

**L_P246_B — All P219 BIG_LOTTO corrected-significant signals fully explained by contamination**
- M4 CUSUM (11× null): draw-sum jumps between ~75 (DATE_FORMAT) / ~100 (SMALL_POOL) and ~148 (real 6/49).
- M3 drift (4×) / M2 gap (4×): numbers 26–49 absent during alien eras → L1 drift and gap overdispersion.
- M1 markov / M6 entropy: restricted pool in alien blocks inflates consecutive overlap, lowers entropy.
- Anomaly is NOT predictor. GATE_RED_DATA_CONTAMINATION remains until Type D quarantine authorized and re-audit passes.
