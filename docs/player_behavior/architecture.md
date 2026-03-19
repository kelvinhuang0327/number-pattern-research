# Player Behavior / Split-Risk Analysis — Architecture

## Overview

This module implements **Track B** — a parallel, independent analysis layer that evaluates human number selection bias and prize split risk. It takes already-predicted tickets as input and produces advisory-only output.

## Two-Track Architecture

```
TRACK A (Prediction Engine)              TRACK B (Player Behavior)
───────────────────────────              ──────────────────────────
lottery_api/models/                       analysis/player_behavior/
lottery_api/engine/                         ├── __init__.py
tools/quick_predict.py                      ├── popularity_model.py
src/engine/PredictionEngine.js              ├── split_risk.py
                                            ├── anti_crowd.py
                                            └── reporting.py
```

**Critical invariant**: Track B never imports from Track A. Track B never feeds back into prediction scoring.

## Module Files

| File | Purpose |
|------|---------|
| `__init__.py` | Entry point `analyze_tickets()`, game config |
| `popularity_model.py` | 9-heuristic bias scoring engine (0-100 scale) |
| `split_risk.py` | Risk level mapping + prize structure info |
| `anti_crowd.py` | Low-popularity alternative suggestion |
| `reporting.py` | CLI and markdown formatters |

## Data Flow

```
Predicted tickets (List[Dict])
        │
        ▼
  analyze_tickets(bets, lottery_type)
        │
        ├── compute_popularity()  → score, flags, details
        ├── assess_split_risk()   → level, tiers, dilution
        └── suggest_anti_crowd()  → alternative (if score ≥ 50)
        │
        ▼
  Advisory dict (injected into modelInfo.player_behavior)
```

## Integration Points

1. **Backend API** (`lottery_api/routes/prediction.py`): Injected into `modelInfo.player_behavior` at the end of `_build_coordinator_result()`. Uses `try/except` — failure never blocks prediction.

2. **CLI** (`tools/quick_predict.py`): Printed after `print_prediction()` using `format_advisory_cli()`. Uses `try/except`.

3. **Frontend** (`src/engine/strategies/APIStrategy.js`): Appended in `generateReport()` by reading `result.modelInfo.player_behavior`. Markdown format.

## Safety Rules

1. `analysis/` never imports from `lottery_api/models/` or `lottery_api/engine/`
2. `analysis/` never writes to prediction logs or strategy states
3. All functions are pure: `List[int] + config → dict` (no DB, no side effects)
4. Module has zero impact if removed (all integration uses `try/except`)
5. All code includes disclaimer: "HEURISTIC model — NOT a predictive model"
