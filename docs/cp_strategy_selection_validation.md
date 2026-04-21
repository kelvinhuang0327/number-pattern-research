# CP-Based Strategy Selection Validation Report

## 1. Objective
Upgraded the "Best Strategy Summary" block to prioritize **Capital Efficiency (CP Value)** over raw Success Rate. This ensures that strategies are selected based on their "Hit Rate per Bet", preventing the bias toward high-bet-count strategies.

> [!NOTE]
> High success rate strategies are often capital inefficient. 
> CP-based selection reflects real-world constrained betting optimization.

## 2. CP Calculation Methodology
The CP value is calculated as follows:
**CP = (Success Rate % @ 300p) / (Number of Bets)**

### Manual Verification Example (Daily 539)
Based on current system data:
| Strategy Name | Bet Count | Success Rate (300p) | CP Calculation | CP Score |
| :--- | :---: | :---: | :--- | :---: |
| **midfreq_acb_2bet** | 2 | 30.00% | 30.00 / 2 | **15.000** (BEST) |
| **acb_markov_midfreq_3bet** | 3 | 39.00% | 39.00 / 3 | 13.000 |
| **f4cold_5bet** | 5 | 52.00% | 52.00 / 5 | 10.400 |

**Result**: Even though `f4cold_5bet` has a higher hit rate (52%), `midfreq_acb_2bet` is selected as the **Best Strategy** because it provides more "bang for the buck" (15.00% per bet vs 10.40%).

## 3. Sample API Response (`/api/decision/best-strategy-summary`)
```json
{
  "game": "今彩539",
  "game_id": "DAILY_539",
  "best_strategy": {
    "strategy_name": "midfreq_acb_2bet",
    "bet_count": 2,
    "success_rate_300": 30.0,
    "success_rate_500": 5.6,
    "success_rate_1500": 6.27,
    "cp_score": 15.0,
    "status": "PRODUCTION"
  },
  "all_strategies": [
    {
      "strategy_name": "midfreq_acb_2bet",
      "bet_count": 2,
      "cp_score": 15.0,
      "success_rate_300": 30.0,
      "status": "PRODUCTION"
    },
    {
      "strategy_name": "acb_markov_midfreq_3bet",
      "bet_count": 3,
      "cp_score": 13.0,
      "success_rate_300": 39.0,
      "status": "PRODUCTION"
    },
    {
      "strategy_name": "f4cold_5bet",
      "bet_count": 5,
      "cp_score": 10.4,
      "success_rate_300": 52.0,
      "status": "PRODUCTION"
    }
  ]
}
```

## 4. UI Layout (Final Render Mock)
The UI now features a primary card for the best CP strategy and an expandable detailed list for transparency.

```text
+------------------------------------------+
| 彩種：今彩539              [PRODUCTION]  |
|                                          |
| 最佳策略：midfreq_acb_2bet               |
| 最佳注數：2 注                            |
|                                          |
| CP值 (效率)：15.000                      |
| 300期成功率：30.00%                       |
| 500期成功率：5.60%                        |
| 1500期成功率：6.27%                       |
|                                          |
| 狀態：PRODUCTION                          |
|                                          |
| [展開明細 ▼]                             |
+------------------------------------------+
```

## 5. Verification Checklist
- [x] Best strategy is selected by MAX CP.
- [x] Backend dynamically calculates CP for all strategies.
- [x] Detail panel shows all strategies sorted by CP descending.
- [x] Missing 500p/1500p data handled as `null` / `N/A`.
- [x] No hardcoded selection.
