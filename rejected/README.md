# Rejected Strategies Archive

每個被拒絕的策略以 `{strategy_name}.json` 格式歸檔。
**舊策略不得刪除，只能歸檔。**

## Schema

```json
{
  "name": "策略名稱",
  "lottery": "BIG_LOTTO | POWER_LOTTO | DAILY_539",
  "rejected_date": "YYYY-MM-DD",
  "failure_reason": "失敗原因摘要",
  "pattern": "SHORT_MOMENTUM | INEFFECTIVE | STATISTICAL_ILLUSION | LATE_BLOOMER",
  "stats": {
    "edge_150p": null,
    "edge_500p": null,
    "edge_1500p": null,
    "baseline": null,
    "p_value": null,
    "z_score": null
  },
  "applicable_conditions": "此策略在哪些條件下曾短暫有效",
  "retest_conditions": "什麼情況下可重新測試",
  "notes": "補充說明"
}
```
