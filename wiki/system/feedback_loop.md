# 分析回饋閉環（Feedback Loop）

> Source-of-truth：本檔。單期分析原始資料見 `docs/` 或 `docs/archive/`。

---

## 閉環結構

```
Draw Result → draw_analysis → failure_analysis → lesson capture → memory/lessons.md
                                                                    ↓
                                                          wiki/lessons/key_lessons.md (索引)
                                                                    ↓
                                                          策略重評估 → validation_gates
```

---

## 各分析類型說明

| 文件類型 | 用途 | 讀取入口 |
|----------|------|----------|
| `draw_analysis_*` | 單期開獎結果分析 | 已歸檔至 `docs/archive/`，不作為策略依據 |
| `failure_analysis_*` | 預測失敗原因分析 | 已歸檔至 `docs/archive/`；教訓摘要在 `memory/lessons.md` |
| `PREDICTION_REPORT_*` | 單期預測報告 | 已歸檔至 `docs/archive/`，不代表最新結論 |

---

## 教訓捕獲規則

1. 每次策略失敗必須記錄至 `memory/lessons.md`（正文）
2. 重大教訓更新 `wiki/lessons/key_lessons.md`（索引）
3. 失敗策略必須產生 `rejected/{strategy_name}.json`
4. 單期失敗不足以推翻策略結論，需累積多期或統計顯著才能重評估

## Strategy Interface & Feature Capture (extracted)

- Strategy interface: `strategy(history) -> List[List[int]]` (returns list of bet lists); use sorted numbers for non-permutation games, preserve order for permutation games.
- Feature capture: feature extractors must produce a reproducible feature matrix `(N_numbers, F_features)` and record feature definitions in `feature_library.py` with versioning.
- Failure-to-lessons flow: on failure_analysis, extract generalizable failure patterns (overfitting, leakage, window instability) into `memory/lessons.md` with tags: `leakage`, `stability`, `overfit`, `integration`.
- Recording conventions: each captured lesson must include: summary (1 line), affected modules, minimal repro steps or test case, and suggested mitigation.

---

## Prediction Tracker 結構

- API：`GET /api/prediction_tracker/{lottery_type}`
- 資料儲存：`data/` JSON 或 DB
- 詳細設計：`docs/prediction_tracker_data_flow_report.md`

---

## 相關連結

- 驗證閘：`wiki/system/validation_gates.md`
- 教訓索引：`wiki/lessons/key_lessons.md`
- 教訓正文：`memory/lessons.md`
