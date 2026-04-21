# Key Lessons

來源說明：本頁將現有 workspace 可驗證的 L14-L107 濃縮為單行索引；若原始正文在目前 checkout 與 git 歷史均不存在，會明確標示缺號，不補寫。

## 通用原則

- L14：正交覆蓋可作為有效的第 N 注策略。
- L15：Markov(w=30) 適合做正交補注，不適合單獨升格。
- L16：未做多重比較校正的 p<0.05 多半是假陽性。
- L17：150 正、500 正、1500 負是 SHORT_MOMENTUM 警訊。
- L18：150 負、1500 正是 LATE_BLOOMER，不能只看短窗。
- L19：外部報告若用弱基準，會把負邊際包裝成正策略。
- L20：不可重現的結果一律無效；seed=42、資料範圍、版本號必記。
- L21：不同彩種的有效訊號不可互借。
- L22：失敗記錄與重測條件比成功案例更有價值。
- L29：LaunchAgent 需保持系統目錄與專案 `.plist` 同步。
- L47：Permutation p-value 不能只報到抽樣下限，需同報 z-score / n_perm。
- L48：改生產腳本前必須先過 McNemar，不可先部署再驗證。
- L52：原始 `memory/lessons.md` 缺號；目前 workspace 找不到正文。
- L53：原始 `memory/lessons.md` 缺號；目前 workspace 找不到正文。
- L55：研究只能暫停，不能宣告永久封存。
- L61：McNemar gate 必須在部署前完成，而不是部署後補票。
- L64：Permutation test 不可直接 shuffle hits array。
- L76：通過閘門只是必要條件，不代表優於現役策略。
- L96：SB3 Track B 的 permutation null 應用 MC/Binomial 基線，不是保留均值的 label shuffle。
- L97：RL reward 的 cost-discount 會鼓勵低注低基準策略，造成 reward gaming。
- L98：170 train / 48 test 的 RL 資料量不足以支持可靠收斂。
- L99：Kelly 在深度負 EV 彩券中會收斂到 0，無法把資訊邊際轉成正資金 EV。
- L100：Decision layer 的 bet sizing 改善主要來自風險控制，不是新訊號。
- L101：conditional edge 會被 participation 稀釋；unconditional edge 才是誠實指標。
- L102：Anti-crowd / popularity 調整可 advisory，但當 effect size 小且 perm 不顯著時不應部署。
- L103：目前 checkout 與 git 歷史都沒有正文；僅見 backlog 對 L79-L106 的範圍引用。
- L104：目前無正式 lesson 正文；僅見其他研究用「pool structure ≠ exploitable temporal signal」類比引用。
- L105：目前 checkout 無正文，無法忠實還原。
- L106：目前 checkout 無正文，無法忠實還原。
- L107：目前 checkout 無正文，無法忠實還原。

## 今彩539

- L27：Day-of-Week 效應不存在，不應入選號邏輯。
- L28：F4 正交 + Cold 是首個通過驗證的 5 注策略。
- L30：3 注 overlap 會直接殺死覆蓋率優勢。
- L31：覆蓋率是必要條件，但仍需每注本身有正 Edge。
- L37：539 的 3 注策略容易被幾何覆蓋效益誤導。
- L38：單注 permutation 必須拉到 1500 期；ACB 因此確認通過。
- L39：單注強訊號不一定能成為有效第 N 注。
- L40：信號在全空間有效，移到殘餘池時常大幅衰減。
- L41：「高頻突斷」沒有統計信號，ACB 權重不該為單一期數調整。
- L42：多注設計時，信號正交性比單注強度更重要。
- L43：Markov 在 539 更適合作為正交組件，不適合獨立主策略。
- L44：MidFreq 是 MODERATE_DECAY，不應誤標成 STABLE。
- L45：UCB1 bandit 在 539 不如人工的溫度帶正交設計。
- L46：共現 Lift pair 在目前資料量下不可靠。
- L56：單注 perm 過關也不代表能與現役策略有效疊加。
- L66：ExtremeCol 這類硬閾值篩選會與 ACB 高度重疊並傷害覆蓋。
- L67：Conditional Fourier 在大資料庫下退化成 NO-OP。
- L68：局部信號應當微調全局 Fourier，而不是取代它。
- L69：先部署後驗證是反向流程，必須直接回退。
- L70：lag / echo 結論不能跨彩種直接套用到 539。
- L71：lag-2/3 雖有訊號痕跡，但整體仍劣於 MidFreq+ACB。
- L72：ACB boundary pool 擴大到 n<=8 改善不顯著，維持 n<=5。
- L73：Zone / Sum 在 539 是白噪音，ZPI v1/v2 全部 REJECT。
- L74：Consecutive Streak 在 539 不具可操作訊號。
- L75：lag-3 當第 4 注接近過關但不確定性太高，暫緩。
- L77：per-agent 降權至少要 200 期以上才有統計支撐。
- L78：ZoneRev 通過 perm 不代表 Zone 假設成立；有效來源其實是 MidFreq。
- L79：ACB × MidFreq 乘積失敗，因為冷號與中頻號在高分空間互斥。
- L80：數學構造出的自相關未必是可預測信號。
- L81：弱信號乘法疊加只會退化，不會放大 Edge。
- L82：H001~H008 全滅，539 頻率族信號空間已高度飽和。

## 大樂透

- L25：多窗口 Fourier 會稀釋大樂透真正的單窗口週期信號。
- L26：把冷號補注改成 Fourier 擴展會退步。
- L54：Zone=0 / >=4 的鄰域盲區存在觀察訊號，但不可操作，只能監控。
- L57：尾數多樣性約束是免費 Edge 提升。
- L58：5 注系統對連號已自然高覆蓋，額外約束多餘。
- L59：冷號池研究顯示 gap 排序不如頻率排序。
- L70：Zone cascade guard + hot-streak override 全面 REJECT。
- L85：49C6 讓所有頻率型訊號衰減到偵測閾值以下。
- L86：低基準率遊戲做演化搜尋時會 5x~10x 過擬合。
- L89：MicroFish 在 BIG_LOTTO 仍只是在擬合噪音。
- L90：BIG_LOTTO 全信號空間窮盡，進入維護模式。
- L91：完整信號邊界研究顯示 49C6 與公平隨機不可區分。

## 威力彩

- L23：冷號預警可當監控工具，但不足以替換 PP3。
- L24：PP3 真實精確 Edge 是 +2.23%，不是 +2.30%。
- L32：MAB 在威力彩這種稀疏訊號環境無效。
- L33：lag-3 Echo 雖改善長窗，但會損害短期穩健性。
- L34：Wavelet CWT 計算成本過高，不適合完整回測。
- L35：Sum Regime 切換受制於樣本不足，暫不可操作。
- L36：Ort5 注4 精化是 provisional 候選，但未達正式升格。
- L49：Power Lotto 的 Sum Lift 幾乎為 0，改善可能只是組合多樣性。
- L50：SHLC 屬倖存者偏差，無法穩定預測。
- L51：PP3 的 Fourier 注2 是有效正交互補，不應被替換。
- L60：單期回顧的最佳方法不能直接升格成策略。
- L62：hit=0 災難率翻倍時，即使平均 Edge 相近也應拒絕。
- L63：Fourier window 改動必須做 1500 期 OOS McNemar。
- L65：CSN 特別號最佳 gap 門檻需由回測決定。
- L83：MidFreq 是少數可成功跨遊戲轉移到威力彩的訊號。
- L84：ACB 的邊界與 mod3 啟發式無法轉移到威力彩。
- L87：威力彩在經濟現實下同樣不可能正 EV。
- L88：進化策略即使通過全閘門，也未必能超越現役 Fourier 主線。
- L92：Z1 drought detector 無法提供可操作均值回歸。
- L93：H9 Pure MidFreq 2 注 perm 過關但 McNemar 未達標，只能 shadow/watch。
- L94：fourier_rhythm_3bet 的 30p 過熱需監控，但不代表可直接升權。
- L95：midfreq_fourier 系列若連續 200 期低於基準，才考慮降權。

## 缺號備註

- 目前 lesson 編號在原始資料中本來就有缺號與跳號；本頁保留這些缺口，避免憑空補寫。