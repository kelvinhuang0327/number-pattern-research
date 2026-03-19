# Backtest Integrity Protocol (抗前視偏差協議)

To ensure all future lottery strategy research is scientifically valid, all backtesting must adhere to the following "No-Lookahead" rules.

## 🛡️ The Three Pillars of Integrity

### 1. Temporal Isolation (時間隔離)
- **Rule**: Predictors must NEVER have access to the draw result being predicted or any subsequent results.
- **Implementation**: In any loop over `draws[N]`, the `history` slice must strictly be `draws[N+1:]` (assuming New-to-Old sorting).

### 2. State Immobility (狀態防護)
- **Rule**: Meta-strategies (selectors) must rank and select their component algorithms based *only* on the performance of draws **prior** to the current target draw.
- **Checklist**:
    - [ ] Rank components using the available history *before* the current draw.
    - [ ] Choose the best component.
    - [ ] Perform prediction for current draw.
    - [ ] *Only then* update performance stats with the current draw result.

### 3. Structural Verification (架構校驗)
- **Rule**: All new backtest scripts SHOULD utilize the `RollingBacktester` framework which is designed to prevent these errors.

---

## 🏗️ Technical Guardrails (Implemented)

### `DataLeakageError`
A new exception class introduced to the framework. If a predictor is passed a history containing the target draw, the system will raise an alert.

### Integrity Check Logic
The `RollingBacktester` now forces a strict index search to ensure the history slice always starts *after* the target draw.
