from wbc_backend.api.contracts import AnalyzeRequest
from wbc_backend.pipeline.service import PredictionService
from wbc_backend.reporting.strategy_replay_runtime_metadata import (
    prepare_runtime_strategy_metadata_request_kwargs,
)


def main(
    strategy_id: str | None = None,
    strategy_metadata_registry: str | None = None,
    current_lifecycle_state: str | None = None,
    strict_strategy_metadata: bool = False,
) -> None:
    service = PredictionService()
    strategy_metadata_kwargs = prepare_runtime_strategy_metadata_request_kwargs(
        strategy_id,
        registry_path=strategy_metadata_registry,
        current_lifecycle_state=current_lifecycle_state,
        strict=strict_strategy_metadata,
    )
    request = AnalyzeRequest(
        game_id="WBC26-TPE-AUS-001",
        line_total=7.5,
        line_spread_home=-1.5,
        **strategy_metadata_kwargs,
    )
    response = service.analyze(request)

    print("===== MARKDOWN REPORT =====")
    print(response.markdown_report)
    print("\n===== JSON REPORT =====")
    print(response.json_report)


if __name__ == "__main__":
    main()
