from __future__ import annotations

import json
from pathlib import Path


def load_market_quality(path: str = "data/wbc_backend/market_validation.json") -> dict[str, float]:
    p = Path(path)
    if not p.exists():
        # Conservative fallback: only ML enabled before validation.
        return {"ML": 1.0, "RL": 0.0, "OU": 0.0}

    data = json.loads(p.read_text(encoding="utf-8"))
    ml = float(data.get("ML", {}).get("ml_roi", 0.0))
    rl = float(data.get("RL", {}).get("rl_roi", 0.0))
    ou = float(data.get("OU", {}).get("ou_roi", 0.0))

    def score(roi: float) -> float:
        if roi <= 0.0:
            return 0.0
        if roi >= 0.01:
            return 1.15
        return 1.0

    return {"ML": score(ml), "RL": score(rl), "OU": score(ou)}
