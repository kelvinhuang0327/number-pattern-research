# Lessons Learned

按主題分類，來源為歷次策略失敗與驗證結果。
每次用戶指正或策略拒絕後更新此檔。

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
- 實測：四窗口 edge = 30p+2.41%, 100p+0.41%, 300p+0.41%, 1500p+1.28%，全正✅
- Perm test (100 shuffles×1500p)：p=0.030, d=1.83 → SIGNAL ✅
- McNemar vs Fourier proxy (1500p)：net=+25, p=0.119 ❌（差 ~6 cases）
- 狀態：PROVISIONAL — 等待更多資料
- 重測條件：115000122（再+100期資料），McNemar 目標 net≥+32 p<0.05 升格 ADOPTED
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
