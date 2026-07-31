from __future__ import annotations

import json
import pickle
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from wbc_backend.config.settings import AppConfig
from wbc_backend.features.advanced import FEATURE_NAMES


@dataclass
class GateCheck:
    name: str
    passed: bool
    details: str
    value: float | None = None


@dataclass
class DeploymentGateReport:
    status: str
    selected_calibration: str
    checks: list[GateCheck] = field(default_factory=list)
    walkforward_summary: dict[str, Any] = field(default_factory=dict)
    selected_calibration_summary: dict[str, Any] = field(default_factory=dict)
    artifact_feature_counts: dict[str, int | None] = field(default_factory=dict)

    @property
    def blocking(self) -> bool:
        return any(not check.passed for check in self.checks)

    def ensure_ready(self) -> DeploymentGateReport:
        if self.blocking:
            raise DeploymentGateError(self)
        return self

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DeploymentGateError(RuntimeError):
    def __init__(self, report: DeploymentGateReport):
        self.report = report
        reasons = "; ".join(check.details for check in report.checks if not check.passed)
        super().__init__(f"Deployment gate blocked live prediction: {reasons or 'unknown reason'}")


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def _load_pickle(path: Path) -> Any:
    with path.open("rb") as fh:
        return pickle.load(fh)


def _artifact_feature_count(path: Path) -> int | None:
    if not path.exists():
        return None
    payload = _load_pickle(path)
    if isinstance(payload, dict) and "feature_count" in payload:
        return int(payload["feature_count"])
    model = payload.get("model") if isinstance(payload, dict) else payload
    for attr in ("n_features_in_", "feature_count_"):
        value = getattr(model, attr, None)
        if isinstance(value, int):
            return value
    x_mean = payload.get("x_mean") if isinstance(payload, dict) else None
    if x_mean is not None:
        return len(x_mean)
    return None


def evaluate_deployment_gate(config: AppConfig) -> DeploymentGateReport:
    gate_cfg = config.deployment_gate
    if not gate_cfg.enabled:
        return DeploymentGateReport(status="DISABLED", selected_calibration="none")

    checks: list[GateCheck] = []
    walkforward_summary: dict[str, Any] = {}
    calibration_payload: dict[str, Any] = {}
    selected_calibration = "none"
    selected_calibration_summary: dict[str, Any] = {}

    walkforward_path = Path(config.sources.walkforward_summary_json)
    if walkforward_path.exists():
        walkforward_summary = _load_json(walkforward_path)
        wf_games = int(walkforward_summary.get("games", 0))
        wf_brier = float(walkforward_summary.get("brier", 1.0))
        checks.append(
            GateCheck(
                name="walkforward_min_games",
                passed=wf_games >= gate_cfg.min_walkforward_games,
                details=f"walk-forward games={wf_games}, required>={gate_cfg.min_walkforward_games}",
                value=float(wf_games),
            )
        )
        checks.append(
            GateCheck(
                name="walkforward_brier",
                passed=wf_brier <= gate_cfg.max_walkforward_brier,
                details=f"walk-forward brier={wf_brier:.4f}, required<={gate_cfg.max_walkforward_brier:.4f}",
                value=wf_brier,
            )
        )
    else:
        checks.append(
            GateCheck(
                name="walkforward_summary_exists",
                passed=False,
                details=f"missing walk-forward summary: {walkforward_path}",
            )
        )

    calibration_path = Path(config.sources.calibration_compare_json)
    if calibration_path.exists():
        calibration_payload = _load_json(calibration_path)
        candidates: list[tuple[str, float, dict[str, Any]]] = []
        for name, entry in calibration_payload.items():
            summary = entry.get("summary", {})
            candidates.append((name, float(summary.get("ml_roi", -1.0)), summary))
        if candidates:
            selected_calibration, best_roi, selected_calibration_summary = max(candidates, key=lambda item: item[1])
            checks.append(
                GateCheck(
                    name="calibration_profile_roi",
                    passed=best_roi >= gate_cfg.min_best_calibration_ml_roi,
                    details=f"best calibration={selected_calibration}, ml_roi={best_roi:.4f}, required>={gate_cfg.min_best_calibration_ml_roi:.4f}",
                    value=best_roi,
                )
            )
            # ECE gate：目標 < 0.12（Platt Scaling 後應達 < 0.08）
            # 僅在 ECE 欄位存在於校準摘要時才判斷（舊格式校準文件豁免）
            raw_ece = selected_calibration_summary.get("ece")
            if raw_ece is not None:
                best_ece = float(raw_ece)
                max_ece = getattr(gate_cfg, "max_calibration_ece", 0.12)
                checks.append(
                    GateCheck(
                        name="calibration_ece",
                        passed=best_ece <= max_ece,
                        details=(
                            f"calibration={selected_calibration}, ECE={best_ece:.4f}, "
                            f"required<={max_ece:.4f} (target=0.08 after Platt Scaling)"
                        ),
                        value=best_ece,
                    )
                )
        else:
            checks.append(
                GateCheck(
                    name="calibration_profiles_available",
                    passed=False,
                    details=f"no calibration profiles found in {calibration_path}",
                )
            )
    else:
        checks.append(
            GateCheck(
                name="calibration_compare_exists",
                passed=False,
                details=f"missing calibration compare file: {calibration_path}",
            )
        )

    artifact_feature_counts: dict[str, int | None] = {}
    if gate_cfg.require_artifact_schema_match:
        expected = len(FEATURE_NAMES)
        artifact_dir = Path(config.sources.model_artifacts_dir)
        artifact_map = {
            "xgboost": artifact_dir / "xgb_model.pkl",
            "lightgbm": artifact_dir / "lgbm_model.pkl",
            "catboost": artifact_dir / "cat_model.pkl",
            "neural_net": artifact_dir / "nn_model.pkl",
        }
        for name, path in artifact_map.items():
            count = _artifact_feature_count(path)
            artifact_feature_counts[name] = count
            checks.append(
                GateCheck(
                    name=f"{name}_artifact_schema",
                    passed=count == expected,
                    details=f"{name} artifact feature_count={count}, expected={expected}",
                    value=float(count) if count is not None else None,
                )
            )

    status = "READY" if all(check.passed for check in checks) else "BLOCKED"
    return DeploymentGateReport(
        status=status,
        selected_calibration=selected_calibration,
        checks=checks,
        walkforward_summary=walkforward_summary,
        selected_calibration_summary=selected_calibration_summary,
        artifact_feature_counts=artifact_feature_counts,
    )
