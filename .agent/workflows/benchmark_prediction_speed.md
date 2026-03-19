---
description: Benchmark prediction speed for different lottery types
---

# Benchmark Prediction Speed Workflow

此工作流用於自動化測試後端預測速度，驗證分類存儲優化是否生效。

## 步驟說明

1. **確保後端已啟動**
   ```bash
   ./start_backend.sh   # 確保載入最新的 scheduler.py
   ```

2. **同步所有數據到後端**（一次性）
   ```bash
   # 在瀏覽器 Console 執行或使用前端腳本
   await app.syncDataToBackend();
   ```

3. **執行效能基準測試**
   ```bash
   // 針對 BIG_LOTTO 使用 ensemble 模型，執行 20 次測試
   python3 benchmark_prediction_speed.py BIG_LOTTO ensemble 20
   ```

   // 也可以測試其他類型，例如 POWER_LOTTO、LOTTO_539
   python3 benchmark_prediction_speed.py POWER_LOTTO ensemble 20
   ```

4. **檢查輸出**
   - 若顯示平均耗時 <0.05 ms，代表已使用 O(1) 快速取得。
   - 若顯示 10‑50 ms，則可能仍在使用舊的遍歷過濾，需要確認 `scheduler.data_by_type` 已正確建立。

---

## 自動化（可選）

以下步驟示範如何在工作流中自動執行基準測試（使用 `// turbo` 註解自動執行）。

```markdown
// turbo
5. run_command: python3 benchmark_prediction_speed.py BIG_LOTTO ensemble 20
```

> **注意**：此指令會直接在本機執行，若您不希望自動執行，請手動在終端機執行第 3 步。

---

## 參考文件
- `benchmark_prediction_speed.py`（根目錄）
- `combined_change_report.md`（.agent）
- `scheduler.py`（後端）

---

*此工作流已完成，您可在 `.agent/workflows/benchmark_prediction_speed.md` 中查看與執行。*
