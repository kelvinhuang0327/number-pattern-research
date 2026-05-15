# Player Behavior / Split-Risk Analysis — Repository Audit

Generated: 2026-03-16

## Prediction Report Generation Flow

### Backend (Track A)
1. **Entry**: `lottery_api/routes/prediction.py` — 5 prediction endpoints
2. **Core**: `_build_coordinator_result()` builds multi-bet prediction with strategy weights
3. **Output**: `PredictResponse` schema with `numbers`, `confidence`, `method`, `modelInfo`
4. **Key**: `modelInfo.bets[]` carries per-bet data; `modelInfo.analysis` carries metadata

### CLI (Track A)
1. **Entry**: `tools/quick_predict.py:main()` dispatches to game-specific predictors
2. **Output**: `print_prediction()` formats console report with bet numbers + strategy info
3. **Logging**: `_log_prediction_safe()` writes to JSONL prediction log

### Frontend (Track A)
1. **Entry**: `src/engine/strategies/APIStrategy.js` calls backend API
2. **Report**: `generateReport()` builds markdown text from API response
3. **Display**: `src/core/App.js:displayPredictionResult()` renders to `#prediction-report` div

## Integration Point for Track B

**Best approach**: Inject advisory data into `modelInfo.player_behavior` at the end of `_build_coordinator_result()`. This:
- Requires zero schema changes (modelInfo is `Optional[Dict]`)
- Flows automatically through normalization, caching, and response
- Is available to both frontend (via API) and CLI (via direct call)

## Files Identified

| File | Role | Modification Needed |
|------|------|-------------------|
| `lottery_api/routes/prediction.py` | API routes | Add advisory injection (~10 lines) |
| `tools/quick_predict.py` | CLI tool | Print advisory section (~15 lines) |
| `src/engine/strategies/APIStrategy.js` | Frontend report | Append advisory markdown (~20 lines) |
| `lottery_api/schemas.py` | Data schemas | NO CHANGE |
| `index.html` | HTML layout | NO CHANGE |

## Existing Anti-Popularity Code

`tools/reverse_optimization_anti_popular.py` — standalone POWER_LOTTO heuristic with basic birthday bias + hot number avoidance. Not reusable as a module. The new module will be a proper, game-agnostic, structured analysis framework.
