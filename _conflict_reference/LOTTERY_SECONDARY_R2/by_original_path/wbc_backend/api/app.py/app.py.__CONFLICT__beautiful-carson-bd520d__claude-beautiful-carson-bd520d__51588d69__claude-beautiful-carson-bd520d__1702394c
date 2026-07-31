"""
Framework-agnostic API backend.

Can be wrapped by FastAPI / Flask / Starlette in production.
"""
from __future__ import annotations

from wbc_backend.domain.schemas import AnalyzeRequest
from wbc_backend.pipeline.service import PredictionService
from wbc_backend.data.wbc_verification import WBCDataVerificationError
from wbc_backend.pipeline.deployment_gate import DeploymentGateError


_service: PredictionService | None = None


def _get_service() -> PredictionService:
    global _service
    if _service is None:
        _service = PredictionService()
    return _service


def analyze_game(
    game_id: str,
    line_total: float = 7.5,
    line_spread_home: float = -1.5,
    force_retrain: bool = False,
) -> dict:
    """
    Analyse a single game and return markdown + JSON reports.

    Parameters
    ----------
    game_id : str
        Game identifier (e.g. 'WBC26-TPE-AUS-001')
    line_total : float
        Over/Under line
    line_spread_home : float
        Home spread
    force_retrain : bool
        If True, retrain all models before predicting

    Returns
    -------
    dict with keys: 'markdown_report', 'json_report', 'game_output'
    """
    service = _get_service()

    if force_retrain:
        from wbc_backend.models.trainer import auto_train_models
        auto_train_models(service.config)

    req = AnalyzeRequest(
        game_id=game_id,
        line_total=line_total,
        line_spread_home=line_spread_home,
        force_retrain=force_retrain,
    )
    try:
        res = service.analyze(req)
    except WBCDataVerificationError as exc:
        return {
            "error": "WBC_DATA_NOT_VERIFIED",
            "message": str(exc),
            "issues": [
                {"code": issue.code, "message": issue.message, "severity": issue.severity}
                for issue in exc.result.issues
            ],
        }
    except DeploymentGateError as exc:
        return {
            "error": "DEPLOYMENT_GATE_BLOCKED",
            "message": str(exc),
            "checks": [
                {
                    "name": check.name,
                    "passed": check.passed,
                    "details": check.details,
                    "value": check.value,
                }
                for check in exc.report.checks
            ],
        }

    return {
        "markdown_report": res.markdown_report,
        "json_report": res.json_report,
        "game_output": res.game_output,
        "deployment_gate_report": res.deployment_gate_report,
    }


def train_models() -> dict:
    """Trigger model retrain."""
    from wbc_backend.models.trainer import auto_train_models
    service = _get_service()
    results = auto_train_models(service.config)
    return {
        "models_trained": len(results),
        "results": [
            {
                "model": r.model_name,
                "accuracy": r.accuracy,
                "logloss": r.logloss,
                "brier_score": r.brier_score,
            }
            for r in results
        ],
    }


def run_backtest() -> dict:
    """Trigger full backtest."""
    from wbc_backend.evaluation.backtester import run_full_backtest, format_backtest_report
    results = run_full_backtest()
    return {
        "report": format_backtest_report(results),
        "seasons": {
            season: {
                "roi": m.roi,
                "sharpe": m.sharpe_ratio,
                "max_drawdown": m.max_drawdown,
            }
            for season, m in results.items()
        },
    }


def self_improve() -> dict:
    """Trigger self-improvement cycle."""
    from wbc_backend.optimization.self_improve import self_improve as si
    service = _get_service()
    return si(config=service.config)
