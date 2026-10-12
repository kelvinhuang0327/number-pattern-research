from wbc_backend.api.contracts import AnalyzeRequest
from wbc_backend.pipeline.service import PredictionService


def main() -> None:
    service = PredictionService()
    request = AnalyzeRequest(game_id="WBC26-TPE-AUS-001", line_total=7.5, line_spread_home=-1.5)
    response = service.analyze(request)

    print("===== MARKDOWN REPORT =====")
    print(response.markdown_report)
    print("\n===== JSON REPORT =====")
    print(response.json_report)


if __name__ == "__main__":
    main()
