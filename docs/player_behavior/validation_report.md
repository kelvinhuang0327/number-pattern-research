# Player Behavior / Split-Risk Analysis — Validation Report

Generated: 2026-03-16

## 1. Prediction Output Unchanged

Verified by running `python3 tools/quick_predict.py` for all three games before and after module integration. Prediction numbers, strategies, and confidence values are identical. The advisory section appears **after** the prediction section and does not alter any prediction data.

| Game | Prediction Unchanged | Advisory Appears |
|------|---------------------|-----------------|
| BIG_LOTTO | YES | YES |
| POWER_LOTTO | YES | YES |
| DAILY_539 | YES | YES |

## 2. Module Standalone

```python
from analysis.player_behavior import analyze_tickets
result = analyze_tickets(
    [{'numbers': [3, 11, 18, 25, 34, 42]}], 'BIG_LOTTO'
)
# Returns valid dict with bets[], summary{}
```

All game types tested:
- BIG_LOTTO (49C6): score range observed 10-51
- POWER_LOTTO (38C6): score range observed 10-40
- DAILY_539 (39C5): score range observed 2-80

## 3. Report Generation Works

- CLI format: `format_advisory_cli()` produces clean terminal output
- Markdown format: `format_advisory()` produces valid markdown for frontend
- Frontend integration: `APIStrategy.js` reads `modelInfo.player_behavior` and appends advisory section

## 4. Anti-Crowd Triggers Correctly

| Input | Score | Anti-Crowd |
|-------|-------|-----------|
| [7, 8, 9, 17, 18, 28] | 51 | YES — replaced 07→33, 08→34 (score 25, -26pts) |
| [1, 2, 3, 7, 8] (539) | 80 | YES — replaced 07→32 (score 38, -42pts) |
| [3, 11, 18, 25, 34, 42] | 14 | NO — below threshold |
| [32, 35, 38, 41, 44, 47] | 34 | NO — below threshold |

## 5. Isolation Test

All integration points use `try/except` guards. If the `analysis/` module is removed:
- Backend API: prediction returns normally, `modelInfo.player_behavior` simply absent
- CLI: prediction prints normally, no advisory section
- Frontend: report generates normally without advisory section

## 6. Safety Verification

- [x] `analysis/` does NOT import from `lottery_api/models/` or `lottery_api/engine/`
- [x] `analysis/` does NOT write to any files, logs, or database
- [x] All functions are pure: `List[int] + config → dict`
- [x] All code includes "HEURISTIC model — NOT a predictive model" disclaimers
- [x] Zero schema changes to `PredictResponse` (uses existing `Optional[Dict]` modelInfo)
