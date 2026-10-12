# Local Vertical Map: Big Lotto Single Bet Generation (`lottery.prediction.generate`)

## Call Chain Overview

```text
public entrypoint: lottery.prediction.generate.generate_one_bet()
  │
  ▼
request model: lottery.prediction.domain.models.GenerateBetRequest
  │
  ▼
generate use case: lottery.prediction.use_cases.GenerateOneBetUseCase
  │
  ▼
strategy registry: lottery_api.models.replay_strategy_registry.get_adapter()
  │
  ▼
executable adapter: ReplayStrategyAdapter (_BigLottoTripleStrikeAdapter / _BigLottoTs3Regime3BetAdapter)
  │
  ▼
domain result model: lottery.prediction.domain.models.GenerateBetResult
  │
  ▼
focused verification: tests/test_lottery_prediction_generate_vertical.py
```

## Detailed Layer Mapping

| Layer | Canonical File Path | Public Symbols | Imports / Dependencies | DB Required? |
|---|---|---|---|---|
| **Public Entrypoint** | `lottery/prediction/generate.py` | `generate_one_bet`, `generate_biglotto_bet` | `GenerateBetRequest`, `GenerateOneBetUseCase` | No |
| **Request / Result Domain** | `lottery/prediction/domain/models.py` | `GenerateBetRequest`, `GenerateBetResult` | `dataclasses`, `typing` | No |
| **Domain Errors** | `lottery/prediction/domain/errors.py` | `InvalidStrategyError`, `InvalidOutputError`, `StrategyExecutionError` | standard exceptions | No |
| **Use Case** | `lottery/prediction/use_cases/generate_one_bet_use_case.py` | `GenerateOneBetUseCase` | `lottery_api.models.replay_strategy_registry` | No |
| **Strategy Registry / Catalog** | `lottery_api/models/replay_strategy_registry.py` | `get_adapter`, `list_strategies`, `ReplayStrategyAdapter` | `tools.predict_biglotto_*` | No |
| **Executable Adapter** | `lottery_api/models/replay_strategy_registry.py` | `_BigLottoTripleStrikeAdapter`, `_BigLottoTs3Regime3BetAdapter` | `tools/predict_biglotto_triple_strike.py` | No |
| **Focused Tests** | `tests/test_lottery_prediction_generate_vertical.py` | `test_*` | `pytest`, `lottery.prediction.generate` | No |

## Base Implementation & Selection Rationale

1. **Registry Base**: `lottery_api/models/replay_strategy_registry.py` is selected as the canonical strategy registry because it contains a well-tested, zero-DB, pure-Python causal adapter interface (`get_one_bet`) for Big Lotto strategies (`biglotto_triple_strike`, `ts3_regime_3bet`, `biglotto_deviation_2bet`).
2. **Target-Native Layering**: `lottery.prediction.generate` encapsulates the application use case without bypassing the strategy registry.
3. **Fail-Closed Guarantee**: Invalid strategy IDs, non-ONLINE statuses, invalid draw outputs (out of range, wrong count, duplicate numbers) are strictly rejected with typed domain exceptions without fallback.
