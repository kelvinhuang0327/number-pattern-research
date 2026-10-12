from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from scipy.special import expit


def calibrate_home_win_prob(raw_prob: float, artifact_path: str = "data/wbc_backend/model_artifacts.json") -> float:
    path = Path(artifact_path)
    if not path.exists():
        return max(0.02, min(0.98, raw_prob))

    payload = json.loads(path.read_text(encoding="utf-8"))
    cal = payload.get("calibration", {})
    a = float(cal.get("a", 1.0))
    b = float(cal.get("b", 0.0))
    p = np.clip(raw_prob, 1e-6, 1 - 1e-6)
    logit = np.log(p / (1 - p))
    calibrated = float(expit(a * logit + b))
    return max(0.02, min(0.98, calibrated))
