# Constraint / Postprocess Hypothesis Research

Date: 2026-04-29
Author: Researcher (automated draft)

## 1. New Hypothesis

假設：對現有投注候選（不新增生成 family）施加後處理約束（sum band、odd/even ratio、span、consecutive count、AC value、zone coverage）作為過濾器，可提高命中率（hit-rate）或短期 edge 的穩定性。此方法與已飽和的 generation family 不同：它不改變或新增生成邏輯（非 frequency / Fourier / Markov / anti_correlation / freq_rev / shadow_gap /cold_lowfreq 類），僅在候選集合上做結構性篩選，利用組合屬性（和、奇偶分布、區域覆蓋等）去除不合常態或高風險組合。

關鍵差異：非生成而是後處理過濾；假設信號源自組合結構特徵與抽樣分佈不對稱，而非頻率類時間序列信號。

## 2. Why This Could Improve Success Rate

因果/統計機制：歷史開獎分佈對組合屬性（總和區間、奇偶比、跨度、連號數、AC 值、區域覆蓋）呈現穩定的分佈偏好；現有生成方法會產生大量邊緣或極端組合，這些組合雖偶有命中但整體命中率低。透過基於歷史分佈的合理 bucket 篩選，可減少高方差、低密度組合進入最終投注集合，降低噪聲比例，理論上可提高集合的平均命中率與穩定性（需驗證）。此方法不主張直接提升 ROI，而是提升命中率/edge 指標的信噪比。

## 3. Required Data

- 主要資料來源（已存在，且禁止修改）：
  - lottery_api/data/lottery_v2.db (draws table) — 需的欄位：draw_id/ draw_date / numbers (或 n1..n6)
  - outputs/predictions/ or predictions/ 或 research/candidate_exports/ — 現有投注候選快照（若有）：每筆記錄應包含 strategy_id, candidate_numbers, generation_timestamp, candidate_score/edge。若不存在，需由現有 pipeline 匯出同樣格式的候選集（read-only）。
- 需產生的衍生特徵（在驗證腳本中生成，勿改寫 DB）：
  - sum (總和)
  - sum_band (例如 6-10 等分或等寬 bucket)
  - odd_count / even_count, odd_even_ratio
  - span (max-min)
  - consecutive_count (連號數)
  - AC value
  - zone_coverage (區域分布 e.g., 1..10,11..20... 每區命中數)
- 外部資料：無必要外部資料
- 已知缺失：若候選快照缺少 generation_timestamp 或 strategy_id，需在匯出階段補齊；若沒有候選快照，需先以只讀方式產生一份候選匯出（遵守 scope 禁止新增 generation family）。

## 4. Minimal Validation Plan

| Field | Value |
|---|---|
| sample_size | 150 draws (primary), sensitivity: 300 draws |
| test_window | last 500p for exploratory stats; primary evaluation on last 150 draws (chronological) |
| baseline | current best validated edge (use existing validated_strategy_set.json edge_150 or current ensemble hit-rate) |
| statistical_test | permutation test for edge difference (block-preserving chronological permutation) + McNemar for paired hit/no-hit at draw-level; report p-value and effect size (bootstrap CI) |
| expected_output | measurable increase in edge_150 or hit-rate over baseline (directional) with p<0.05; or at least consistent positive median effect in bootstrap replicates (do NOT claim ROI) |

Implementation notes:
- Use seed=42 for any random resampling/bootstrap
- Always use chronological train/test split to avoid leakage (train prior draws only)

## 5. Risk / Overfit Check

- sample_size_risk: medium — 150 draws yields moderate statistical power; effects must be reasonably large to detect reliably. Use sensitivity analysis with 300 draws.
- multiple_testing_risk: high — many constraint buckets and combinations will be tested; apply correction (Benjamini-Hochberg) and prefer pre-registered buckets (e.g., 5 sum bands, 4 zone-coverage classes) to limit tests.
- data_leakage_risk: low-to-medium — risk controllable by strict chronological slicing and by not using future information to define buckets; ensure buckets are defined using training/historical only.
- overfit_risk: medium — post-hoc selection of best buckets/combinations can overfit; mitigate by using holdout (e.g., primary 150 draws for evaluation, separate 150-draw validation) and by limiting combinatorial search.

## 6. Decision

WORTH_VALIDATION

理由：方法本質上是後處理過濾（不違反 "不得新增 generation family" 的限制），具有可实施的、低侵入性的实验路径。雖然 multiple-testing 與 sample-size 風險存在，但這些可通過事先限制 buckets、使用严格的训练/验证分割和统计修正来控制。收益在于如果成立，可在不改變生成器的前提下提高候選集合質量，故值得進一步驗證。

## 7. Next Task If Worth Validation (完整驗證任務 prompt)

Task Title: Constraint Postprocess Validation (chronological holdout)

Objective: Evaluate whether applying predefined postprocess constraint filters (sum_band, odd/even ratio, span, consecutive_count, AC value, zone_coverage) to existing candidate exports improves edge_150 / hit-rate vs baseline.

Scope & Rules:
- Do NOT modify lottery_api/data/lottery_v2.db
- Do NOT change any generation strategies or strategy_states
- Use only existing candidate exports (read-only). If absent, run a read-only export pipeline to produce candidates for the test horizon.
- Seed=42 for all resampling/bootstrapping

Steps (executable):
1. Input: candidates.json (export of candidate bets for the evaluation horizon) and draws from lottery_v2.db
2. Feature engineering: compute sum, sum_band (pre-registered 5 bands), odd_count, odd_even_ratio (buckets: 3/3,4/2,5/1,6/0), span buckets, consecutive_count buckets (0,1,2+), AC value buckets, zone_coverage buckets (e.g., 3 zones: low/mid/high; coverage 2/3/4+).
3. Pre-register at most 30 total bucket tests (to contain multiple-testing). Define the primary filter as: sum_band IN {center bands} AND zone_coverage >= 2.
4. Evaluation: for each draw in chronological test set (last 150 draws), compute whether any candidate passing the filter would have hit (paired with baseline candidate set). Compute edge_150 and paired hit matrix.
5. Statistical tests: McNemar on paired hit/no-hit; permutation test (chronological block-preserving) for edge difference; bootstrap CI (n=1000, seed=42).
6. Output: result JSON with metrics (edge_150, p-values, bootstrap CI), diagnostic plots (distribution of features, win-rate per bucket), and full reproducible script (Python) in research/outputs/constraint_validation_2026-04-29/.
7. Decision rule: If p<0.05 (corrected) AND effect direction consistent across bootstrap replicates, mark as PASS for deeper validation; else mark as FAIL/WATCH.

Deliverables:
- research/constraint_validation_report_2026-04-29.md (full results)
- research/outputs/constraint_validation_2026-04-29/*.json (metrics) and diagnostic PNGs
- scripts/validate_constraint_postprocess.py (bootstrap + permutation + McNemar implementation)
- A short README explaining how to run the script and reproduce results (uses seed=42)

Constraints to enforce in task: do not implement any new generation family; do not write to lottery_v2.db; limit buckets/tests to control multiple testing risk.

---

Notes:
- This report intentionally avoids frequency/Fourier/Markov hypotheses per contract.
- If candidate exports are missing, the first subtask is to produce a read-only snapshot of current candidates for the test horizon (no strategy changes).

