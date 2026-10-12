# Daily 539 Vertical Map

## Strategy Identity Resolution

- Primary Strategy Selected: `daily539_f4cold`
- Secondary Executable Strategy: `daily539_markov_cold`
- Registration SSOT: `lottery_api.models.replay_strategy_registry._REGISTRY`
- Adapter Classes:
  - `_Daily539F4ColdAdapter` -> `tools/predict_539_5bet_f4cold.py::predict`
  - `_Daily539MarkovColdAdapter` -> `tools/backtest_39lotto_comprehensive.py::MarkovStrategy`

## Lifecycle Status
- `daily539_f4cold`: `ONLINE`
- `daily539_markov_cold`: `ONLINE`
- Retired / Rejected Stubs registered for governance: `daily539_f4cold_3bet` (RETIRED), `daily539_f4cold_5bet` (RETIRED), `539_3bet_orthogonal` (REJECTED), etc.

## Data & Memory Boundaries
- DB Dependency: None (executes fully in-memory given history list)
- Network Access: None
- Output Contract:
  - `lottery_type`: `DAILY_539`
  - `numbers`: 5 unique integers in range [1..39]
  - `special`: None
