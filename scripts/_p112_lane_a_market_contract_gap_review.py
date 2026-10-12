# P112 Lane A Market-Contract Gap Review

## 目標
針對 Lane A（台灣運彩 MLB 市場）進行「市場合約對齊差距」診斷，僅限於 diagnostic-only，無任何 production、推薦、賠率、EV、Kelly、CLV、下注等邏輯。

## 輸入資料
- data/mlb_2026/derived/p101_two_lane_product_roadmap_realignment_summary.json
- data/mlb_2026/derived/p110_outcome_only_tracking_dashboard_contract_summary.json
- data/mlb_2026/derived/p111_outcome_only_tracking_dashboard_fixture_summary.json
- data/mlb_2026/derived/p109_outcome_only_tracking_drift_snapshot_summary.json
- data/mlb_2026/derived/p84e_2026_outcome_attached_prediction_rows.jsonl

## 輸出
- data/mlb_2026/derived/p112_lane_a_market_contract_gap_review_summary.json
- report/p112_lane_a_market_contract_gap_review_20260531.md

## 核心步驟
1. 解析 Lane A 合約（p101）與現有策略追蹤卡（p110/p111），確認支持的市場類型（moneyline/run_line/total_runs/first_five_innings）。
2. 針對每個市場類型，檢查現有 outcome-only 策略追蹤卡是否有對應策略（如 HIGH_FIP/MID_FIP/LOW_FIP）。
3. 比對合約要求的欄位（如 game_id、predicted_side、source_trace、odds）與 outcome-only pipeline 實際產出欄位。
4. 記錄所有「合約要求但 outcome-only pipeline 未覆蓋」的 gap，並標註 gap 類型（如缺少 odds、缺少 source_trace、策略未覆蓋等）。
5. 產出 diagnostic-only gap summary JSON 與 markdown 報告。
6. 嚴格標註 governance flag，禁止任何 production、推薦、賠率、EV、Kelly、CLV、下注等行為。

## 輸出格式
- summary.json: 每個市場類型的 gap list，包含 gap_type、required_fields、pipeline_fields、strategy_coverage、governance_flag。
- markdown: 條列 gap summary，並說明 diagnostic-only 性質。

## 測試
- 測試檔案：tests/test_p112_lane_a_market_contract_gap_review.py
- 驗證 gap summary 是否正確覆蓋所有合約要求。
- 驗證 governance flag 嚴格為 diagnostic-only。
