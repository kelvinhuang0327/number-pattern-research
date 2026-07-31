from __future__ import annotations

import json
from pathlib import Path


def load_high_confidence_odds_bands(path: str = "data/wbc_backend/model_artifacts.json") -> dict[str, list[tuple[float, float]]]:
    p = Path(path)
    if not p.exists():
        return {"ML": [(1.50, 1.80)]}

    payload = json.loads(p.read_text(encoding="utf-8"))
    stats = payload.get("odds_band_stats", {})
    bands = stats.get("high_confidence_bands", [])

    parsed: list[tuple[float, float]] = []
    for b in bands:
        try:
            lo, hi = b.split("-")
            parsed.append((float(lo), float(hi)))
        except Exception:
            continue

    if not parsed:
        parsed = [(1.50, 1.80)]
    return {"ML": parsed}


def is_odds_in_conf_band(market: str, odds: float, conf_bands: dict[str, list[tuple[float, float]]]) -> bool:
    if market not in conf_bands:
        return True
    return any(lo <= odds <= hi for lo, hi in conf_bands[market])
