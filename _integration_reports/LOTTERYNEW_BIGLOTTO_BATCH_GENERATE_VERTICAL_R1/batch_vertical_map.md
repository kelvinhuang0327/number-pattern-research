# Big Lotto Batch Generation Vertical Map

## Existing Batch Symbols
- `lottery.prediction.batch_generate.generate_bets`
- `lottery.prediction.use_cases.generate_batch_use_case.GenerateBatchUseCase`
- `lottery.prediction.domain.models.GenerateBatchRequest`
- `lottery.prediction.domain.errors.InvalidBatchCountError`

## Related Conflict Copies
Conflict copies in repository (e.g. `wbc_backend/reporting/...__CONFLICT__...`) contain legacy replay reporting symbols, but no canonical batch generation application layer contracts.
Status of all related conflict copies: NOT_USED.

## Existing Consumers & Tests
- `tests/test_lottery_prediction_batch_generate_vertical.py`
- `lottery/prediction/__init__.py`

## Selected Contract
`generate_bets(*, strategy_id: str, count: int, lottery_type: str = "BIG_LOTTO", history: Optional[List[dict]] = None) -> tuple[GenerateBetResult, ...]`
Constraints:
- Bounded batch count: `1 <= count <= 20` (MAX_BATCH_SIZE)
- Strict `int` validation (`bool`, `float`, `str` rejected)
- Fail closed atomically on any single bet error
- Returns immutable ordered tuple of `GenerateBetResult`

## Reused Single-Bet Call Chain
`generate_bets` -> `GenerateBatchUseCase.execute` -> N x `GenerateOneBetUseCase.execute` -> `get_strategy_lifecycle_status` -> `get_adapter` -> `adapter.get_one_bet` -> `_validate_biglotto_numbers` -> `GenerateBetResult` collection
