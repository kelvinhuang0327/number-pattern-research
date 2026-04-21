# Alignment Report: Best Strategy Summary UI

## 1. Requirement Overview
The goal is to replace the "Decision V3 — 下期決策建議" section on the "策略回測展示" (Next Draw Prediction) page with a comprehensive overview of the best performing strategies for the three main lottery types.

### Required Fields for each Lottery:
1. **彩種名稱** (Lottery Name): 今彩539, 大樂透, 威力彩.
2. **目前最佳注數** (Best Bet Count).
3. **目前最佳策略名稱** (Best Strategy Name).
4. **歷史回測成功率** (Success Rate for 300 / 500 / 1500 draws).
5. **Strategy Status**: e.g., PRODUCTION, WATCH, MAINTENANCE.
6. **Edge**: (Optional) Strategy edge over random baseline.

### Constraints:
- **No Hardcoding**: Data must be pulled from the backend.
- **Comparative UI**: Use a clean, comparative layout (grid/cards).
- **Graceful N/A**: Handle missing data points appropriately.

---

## 2. Current State Analysis
- **Frontend**: `src/core/handlers/NextDrawHandler.js` handles the view logic and calls `/api/decision/` to render the "Decision V3" block.
- **Backend**: `/api/decision/` returns data based on `DecisionEngineV3`.
- **Strategy Metadata**: Stored in `lottery_api/data/strategy_states_{LOTTERY}.json` and `strategies/{LOTTERY}/{STRATEGY}/sim_result.json`.

---

## 3. Implementation Plan

### Step 1: Backend API Extension
Enhance the backend to provide a unified "Best Strategy Summary" response.
- **Target File**: `lottery_api/routes/decision.py`.
- **Logic**: 
    - Identify the current "Best" strategy for each lottery type (based on `status == PRODUCTION` and highest bet count or designated priority).
    - Read `strategy_states_*.json` for status, 300p rate, and edge.
    - Read `strategies/*/*/sim_result.json` to extract 500p and 1500p success rates.
- **Endpoint**: `GET /api/best-strategy-summary`

### Step 2: Frontend UI Update
Update the prediction page to display the new summary.
- **Target File**: `src/core/handlers/NextDrawHandler.js`.
- **Changes**:
    - Replace the call to `_loadDecisionV3` with a call to the new endpoint.
    - Update `_renderDecisionV3` (or rename it to `_renderBestStrategySummary`) to render a 3-column grid.
    - Use "Glassmorphism" cards for a premium feel.
    - Ensure field mapping matches the user requirement.

### Step 3: Validation
- Verify telemetry/backend logs to ensure correct file reading.
- Final UI check against the design aesthetics (Premium, Rich Aesthetics).

---

## 4. Proposed Data Mapping
- **今彩539**: `f4cold_5bet` (5注)
- **大樂透**: `p1_dev_sum5bet` (5注)
- **威力彩**: `pp3_freqort_4bet` (4注)

Success values will be sourced from the latest validated simulation results.
